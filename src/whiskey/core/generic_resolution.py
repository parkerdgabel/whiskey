"""Enhanced generic type resolution for dependency injection.

This module provides advanced support for resolving generic types in dependency
injection scenarios. It handles complex cases like Generic[T], Repository[User],
Service[T], and other parameterized types that require sophisticated resolution.

Classes:
    GenericTypeResolver: Core resolver for generic types
    TypeParameterBinder: Binds type parameters to actual types
    GenericRegistry: Registry for generic type mappings

Features:
    - Generic type variance analysis (covariant, contravariant, invariant)
    - Type parameter binding and substitution
    - Generic constraint validation
    - Automatic concrete type discovery
    - Protocol and ABC generic support

Example:
    >>> from whiskey.core.generic_resolution import GenericTypeResolver
    >>> from typing import Generic, TypeVar
    >>>
    >>> T = TypeVar('T')
    >>> class Repository(Generic[T]):
    ...     def __init__(self):
    ...         self.items: list[T] = []
    >>>
    >>> resolver = GenericTypeResolver()
    >>> # Register concrete implementations
    >>> resolver.register_concrete(Repository[User], UserRepository)
    >>> resolver.register_concrete(Repository[Product], ProductRepository)
    >>>
    >>> # Resolve generic types
    >>> user_repo_type = resolver.resolve(Repository[User])
    >>> # Returns UserRepository class

See Also:
    - whiskey.core.analyzer: Uses this for enhanced type analysis
    - whiskey.core.container: Container integration for generic resolution
"""

from __future__ import annotations

import inspect
from collections import defaultdict
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

from .errors import TypeAnalysisError


class GenericTypeResolver:
    """Advanced resolver for generic types in dependency injection.

    This class provides sophisticated resolution of generic types, handling
    type parameter binding, variance analysis, and automatic discovery of
    concrete implementations.

    Features:
        - Resolve Generic[T] to concrete implementations
        - Handle complex type hierarchies
        - Support for bounded TypeVars
        - Automatic type parameter inference
        - Integration with existing type analyzer
    """

    def __init__(self, registry=None):
        """Initialize the generic type resolver.

        Args:
            registry: Optional ComponentRegistry for checking registrations
        """
        self.registry = registry
        self._generic_mappings: dict[Any, list[type]] = defaultdict(list)
        self._type_parameter_cache: dict[tuple, dict] = {}
        self._variance_cache: dict[type, dict] = {}

    def register_concrete(self, generic_type: Any, concrete_type: type) -> None:
        """Register a concrete implementation for a generic type.

        Args:
            generic_type: The generic type (e.g., Repository[User])
            concrete_type: The concrete implementation class

        Example:
            >>> resolver.register_concrete(Repository[User], UserRepository)
            >>> resolver.register_concrete(Service[Product], ProductService)
        """
        origin = get_origin(generic_type)
        if origin is None:
            raise TypeAnalysisError(f"Expected generic type, got {generic_type}")

        self._generic_mappings[generic_type].append(concrete_type)

        # Also register by origin for fallback
        self._generic_mappings[origin].append(concrete_type)

    def resolve_generic(self, generic_type: Any) -> type | None:
        """Resolve a generic type to a concrete implementation.

        Args:
            generic_type: The generic type to resolve

        Returns:
            Concrete implementation class, or None if not found

        Example:
            >>> concrete = resolver.resolve_generic(Repository[User])
            >>> # Returns UserRepository if registered
        """
        # Direct lookup first
        if generic_type in self._generic_mappings:
            candidates = self._generic_mappings[generic_type]
            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1:
                # Multiple candidates - need disambiguation
                return self._disambiguate_candidates(generic_type, candidates)

        # Try origin-based lookup
        origin = get_origin(generic_type)
        if origin and origin in self._generic_mappings:
            candidates = self._generic_mappings[origin]
            return self._find_compatible_implementation(generic_type, candidates)

        # Try automatic discovery
        return self._discover_implementation(generic_type)

    def _disambiguate_candidates(self, generic_type: Any, candidates: list[type]) -> type | None:
        """Disambiguate multiple candidates for a generic type.

        Args:
            generic_type: The generic type being resolved
            candidates: List of candidate implementations

        Returns:
            Best matching candidate, or None if ambiguous
        """
        # Get type arguments for analysis
        args = get_args(generic_type)
        if not args:
            return candidates[0]  # No args to disambiguate with

        # Score candidates based on compatibility
        scored_candidates = []
        for candidate in candidates:
            score = self._score_candidate_compatibility(generic_type, candidate, args)
            if score > 0:
                scored_candidates.append((score, candidate))

        if not scored_candidates:
            return None

        # Sort by score (highest first)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Return best candidate if it's clearly better
        if len(scored_candidates) == 1 or scored_candidates[0][0] > scored_candidates[1][0]:
            return scored_candidates[0][1]

        return None  # Ambiguous

    def _score_candidate_compatibility(
        self, generic_type: Any, candidate: type, args: tuple
    ) -> int:
        """Score how well a candidate matches a generic type.

        Args:
            generic_type: The generic type being resolved
            candidate: Candidate implementation
            args: Type arguments from the generic type

        Returns:
            Compatibility score (higher is better, 0 means incompatible)
        """
        score = 0

        # Check if candidate is a generic implementation
        if hasattr(candidate, "__orig_bases__"):
            for base in candidate.__orig_bases__:
                base_origin = get_origin(base)
                if base_origin == get_origin(generic_type):
                    base_args = get_args(base)
                    if base_args:
                        # Compare type arguments
                        for expected_arg, actual_arg in zip(args, base_args):
                            if expected_arg == actual_arg:
                                score += 10  # Exact match
                            elif self._is_compatible_type(expected_arg, actual_arg):
                                score += 5  # Compatible match
                    else:
                        score += 2  # Generic base without args

        # Check method signatures for compatibility
        score += self._analyze_method_compatibility(candidate, args)

        # Prefer registered components
        if self.registry and self.registry.has(candidate):
            score += 3

        return score

    def _is_compatible_type(self, expected: Any, actual: Any) -> bool:
        """Check if two types are compatible.

        Args:
            expected: Expected type
            actual: Actual type

        Returns:
            True if types are compatible
        """
        try:
            # Direct match
            if expected == actual:
                return True

            # Check inheritance
            if inspect.isclass(expected) and inspect.isclass(actual):
                return issubclass(actual, expected) or issubclass(expected, actual)

            # Check generic compatibility
            expected_origin = get_origin(expected)
            actual_origin = get_origin(actual)

            if expected_origin and actual_origin and expected_origin == actual_origin:
                # Same generic origin, check args
                expected_args = get_args(expected)
                actual_args = get_args(actual)
                if len(expected_args) == len(actual_args):
                    return all(
                        self._is_compatible_type(e, a)
                        for e, a in zip(expected_args, actual_args)
                    )

            return False
        except (TypeError, AttributeError):
            return False

    def _analyze_method_compatibility(self, candidate: type, args: tuple) -> int:
        """Analyze method signatures for type parameter compatibility.

        Args:
            candidate: Candidate implementation class
            args: Type arguments from generic type

        Returns:
            Compatibility score from method analysis
        """
        score = 0

        try:
            # Get type hints for the candidate's methods
            for method_name in dir(candidate):
                if method_name.startswith("_"):
                    continue

                method = getattr(candidate, method_name)
                if not callable(method):
                    continue

                try:
                    type_hints = get_type_hints(method)
                    for hint in type_hints.values():
                        # Check if method uses types compatible with our args
                        for arg in args:
                            if self._is_compatible_type(hint, arg):
                                score += 1
                except Exception:
                    continue
        except Exception:
            pass

        return score

    def _find_compatible_implementation(
        self, generic_type: Any, candidates: list[type]
    ) -> type | None:
        """Find a compatible implementation from candidates.

        Args:
            generic_type: The generic type to match
            candidates: List of candidate implementations

        Returns:
            Best matching implementation, or None
        """
        args = get_args(generic_type)
        if not args:
            return candidates[0] if candidates else None

        # Score all candidates
        best_candidate = None
        best_score = 0

        for candidate in candidates:
            score = self._score_candidate_compatibility(generic_type, candidate, args)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        return best_candidate if best_score > 0 else None

    def _discover_implementation(self, generic_type: Any) -> type | None:
        """Attempt to automatically discover an implementation.

        Args:
            generic_type: The generic type to find implementation for

        Returns:
            Discovered implementation, or None
        """
        if not self.registry:
            return None

        origin = get_origin(generic_type)
        if not origin:
            return None

        # Look for classes that inherit from the generic origin
        for descriptor in self.registry.list_all():
            component_type = descriptor.component_type

            if not inspect.isclass(component_type):
                continue

            # Check if this class implements our generic
            if hasattr(component_type, "__orig_bases__"):
                for base in component_type.__orig_bases__:
                    if get_origin(base) == origin:
                        # Found a potential implementation
                        if self._is_implementation_compatible(generic_type, component_type, base):
                            return component_type

        return None

    def _is_implementation_compatible(
        self, target_generic: Any, impl_class: type, impl_base: Any
    ) -> bool:
        """Check if an implementation is compatible with target generic.

        Args:
            target_generic: The generic type we want to resolve
            impl_class: Implementation class
            impl_base: The generic base of the implementation

        Returns:
            True if compatible
        """
        target_args = get_args(target_generic)
        impl_args = get_args(impl_base)

        if not target_args and not impl_args:
            return True  # Both are raw generics

        if len(target_args) != len(impl_args):
            return False  # Different number of type parameters

        # Check each type argument
        for target_arg, impl_arg in zip(target_args, impl_args):
            if not self._is_compatible_type(target_arg, impl_arg):
                # Check if impl_arg is a TypeVar that could be bound
                if isinstance(impl_arg, TypeVar):
                    # TypeVar can potentially be bound to target_arg
                    if not self._can_bind_typevar(impl_arg, target_arg):
                        return False
                else:
                    return False

        return True

    def _can_bind_typevar(self, typevar: TypeVar, target_type: Any) -> bool:
        """Check if a TypeVar can be bound to a target type.

        Args:
            typevar: The TypeVar to bind
            target_type: The type to bind it to

        Returns:
            True if binding is valid
        """
        # Check bounds
        if typevar.__bound__:
            if not self._is_compatible_type(target_type, typevar.__bound__):
                return False

        # Check constraints
        return not (typevar.__constraints__ and not any(self._is_compatible_type(target_type, constraint) for constraint in typevar.__constraints__))

    def analyze_generic_type(self, generic_type: Any) -> dict[str, Any]:
        """Analyze a generic type and return detailed information.

        Args:
            generic_type: The generic type to analyze

        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "is_generic": False,
            "origin": None,
            "args": [],
            "type_vars": [],
            "is_protocol": False,
            "is_abc": False,
            "concrete_implementations": [],
            "resolvable": False,
        }

        origin = get_origin(generic_type)
        args = get_args(generic_type)

        if origin is not None:
            analysis["is_generic"] = True
            analysis["origin"] = origin
            analysis["args"] = list(args)

            # Extract TypeVars
            analysis["type_vars"] = [arg for arg in args if isinstance(arg, TypeVar)]

            # Check if it's a Protocol
            analysis["is_protocol"] = self._is_protocol_type(origin)

            # Check if it's an ABC
            analysis["is_abc"] = self._is_abc_type(origin)

            # Find concrete implementations
            analysis["concrete_implementations"] = self._generic_mappings.get(generic_type, [])

            # Check if resolvable
            analysis["resolvable"] = (
                len(analysis["concrete_implementations"]) > 0
                or self._discover_implementation(generic_type) is not None
            )

        return analysis

    def _is_protocol_type(self, type_hint: Any) -> bool:
        """Check if a type is a Protocol."""
        try:
            if hasattr(type_hint, "__mro__"):
                return any(
                    hasattr(base, "__module__")
                    and base.__module__ == "typing"
                    and getattr(base, "__name__", "") == "Protocol"
                    for base in type_hint.__mro__
                )
            return hasattr(type_hint, "_is_protocol") and type_hint._is_protocol
        except (AttributeError, TypeError):
            return False

    def _is_abc_type(self, type_hint: Any) -> bool:
        """Check if a type is an Abstract Base Class."""
        try:
            import abc

            return (
                inspect.isclass(type_hint)
                and issubclass(type_hint, abc.ABC)
                and bool(getattr(type_hint, "__abstractmethods__", set()))
            )
        except (TypeError, AttributeError):
            return False

    def get_type_parameters(self, generic_type: Any) -> list[TypeVar]:
        """Get type parameters from a generic type.

        Args:
            generic_type: The generic type to analyze

        Returns:
            List of TypeVar parameters
        """
        if hasattr(generic_type, "__parameters__"):
            return list(generic_type.__parameters__)

        # For parameterized generics, extract from args
        args = get_args(generic_type)
        return [arg for arg in args if isinstance(arg, TypeVar)]

    def bind_type_parameters(self, generic_type: Any, bindings: dict[TypeVar, Any]) -> Any:
        """Bind type parameters to create a concrete type.

        Args:
            generic_type: The generic type with parameters
            bindings: Dictionary mapping TypeVars to concrete types

        Returns:
            Concrete type with parameters bound
        """
        origin = get_origin(generic_type)
        if not origin:
            return generic_type

        args = get_args(generic_type)
        if not args:
            return generic_type

        # Substitute type parameters
        new_args = []
        for arg in args:
            if isinstance(arg, TypeVar) and arg in bindings:
                new_args.append(bindings[arg])
            else:
                new_args.append(arg)

        # Create new parameterized type
        try:
            return origin[tuple(new_args)]
        except (TypeError, AttributeError):
            # Fallback for types that don't support parameterization
            return generic_type

    def infer_type_parameters(
        self, generic_class: type, concrete_class: type
    ) -> dict[TypeVar, Any]:
        """Infer type parameter bindings from a concrete implementation.

        Args:
            generic_class: The generic base class
            concrete_class: Concrete implementation

        Returns:
            Dictionary mapping TypeVars to inferred types
        """
        bindings = {}

        if not hasattr(concrete_class, "__orig_bases__"):
            return bindings

        # Find the generic base in the concrete class's bases
        for base in concrete_class.__orig_bases__:
            base_origin = get_origin(base)
            if base_origin == generic_class or base_origin == get_origin(generic_class):
                # Found matching base, extract type arguments
                base_args = get_args(base)
                generic_params = self.get_type_parameters(generic_class)

                for param, arg in zip(generic_params, base_args):
                    if isinstance(param, TypeVar):
                        bindings[param] = arg

                break

        return bindings

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._type_parameter_cache.clear()
        self._variance_cache.clear()


class TypeParameterBinder:
    """Helper class for binding type parameters in generic types."""

    def __init__(self):
        self._bindings: dict[TypeVar, Any] = {}

    def bind(self, typevar: TypeVar, concrete_type: Any) -> None:
        """Bind a TypeVar to a concrete type.

        Args:
            typevar: The TypeVar to bind
            concrete_type: The concrete type to bind it to
        """
        # Validate the binding
        if typevar.__bound__ and not self._is_subtype(concrete_type, typevar.__bound__):
            raise TypeAnalysisError(
                f"Type {concrete_type} is not compatible with bound {typevar.__bound__}"
            )

        if typevar.__constraints__ and not any(
            self._is_subtype(concrete_type, constraint)
            for constraint in typevar.__constraints__
        ):
            raise TypeAnalysisError(
                f"Type {concrete_type} does not satisfy constraints {typevar.__constraints__}"
            )

        self._bindings[typevar] = concrete_type

    def get_binding(self, typevar: TypeVar) -> Any:
        """Get the binding for a TypeVar.

        Args:
            typevar: The TypeVar to look up

        Returns:
            Bound type, or the TypeVar itself if not bound
        """
        return self._bindings.get(typevar, typevar)

    def substitute(self, type_hint: Any) -> Any:
        """Substitute bound TypeVars in a type hint.

        Args:
            type_hint: The type hint to substitute

        Returns:
            Type hint with substitutions applied
        """
        if isinstance(type_hint, TypeVar):
            return self.get_binding(type_hint)

        origin = get_origin(type_hint)
        if origin:
            args = get_args(type_hint)
            new_args = tuple(self.substitute(arg) for arg in args)
            try:
                return origin[new_args]
            except (TypeError, AttributeError):
                return type_hint

        return type_hint

    def _is_subtype(self, child: Any, parent: Any) -> bool:
        """Check if child is a subtype of parent."""
        try:
            if inspect.isclass(child) and inspect.isclass(parent):
                return issubclass(child, parent)
            return child == parent
        except TypeError:
            return False


def create_generic_resolver(registry=None) -> GenericTypeResolver:
    """Create a new generic type resolver with optional registry.

    Args:
        registry: Optional ComponentRegistry

    Returns:
        Configured GenericTypeResolver instance
    """
    return GenericTypeResolver(registry)
