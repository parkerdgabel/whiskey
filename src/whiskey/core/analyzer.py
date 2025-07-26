"""Type analysis engine for smart dependency injection.

This module provides comprehensive analysis of type hints to determine
which parameters should be auto-injected, handling all edge cases and
providing clear rules for ambiguous scenarios.
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Union, get_args, get_origin

# Handle Python version differences
try:
    from typing import Literal, get_type_hints
except ImportError:
    from typing_extensions import Literal

try:
    from typing import _GenericAlias
except ImportError:
    _GenericAlias = None


class InjectDecision(Enum):
    """Possible outcomes for injection analysis."""

    YES = "inject"  # Definitely inject this parameter
    NO = "skip"  # Never inject this parameter
    OPTIONAL = "optional"  # Inject if available, else None
    ERROR = "error"  # Cannot resolve, should raise error


class InjectResult:
    """Result of injection analysis for a parameter.

    Provides the decision and additional context for resolution.
    """

    def __init__(
        self,
        decision: InjectDecision,
        type_hint: Any = None,
        reason: str = "",
        inner_type: Any = None,
        candidates: list[Any] = None,
    ):
        self.decision = decision
        self.type_hint = type_hint
        self.reason = reason
        self.inner_type = inner_type  # For Optional[T], get the T
        self.candidates = candidates or []  # For Union types

    def __bool__(self) -> bool:
        """True if should inject."""
        return self.decision in (InjectDecision.YES, InjectDecision.OPTIONAL)

    def __repr__(self) -> str:
        return f"InjectResult({self.decision.value}, {self.type_hint}, '{self.reason}')"


class TypeAnalyzer:
    """Analyzes type hints to determine injection behavior.

    This class implements comprehensive rules for determining which
    parameters should be auto-injected based on their type hints,
    handling all edge cases in a predictable manner.

    Rules:
        1. Never inject parameters with non-None defaults
        2. Never inject built-in types (str, int, list, etc.)
        3. Never inject generic types with parameters (List[T], Dict[K,V])
        4. Inject Optional[T] only if T is registered, else None
        5. Inject Union types only if exactly one member is registered
        6. Resolve forward references then apply rules
        7. Don't inject standard library types unless explicitly registered
        8. Always inject user-defined types that are registered
    """

    # Built-in types that should never be injected
    BUILTIN_TYPES = {
        str,
        int,
        float,
        bool,
        list,
        dict,
        tuple,
        set,
        frozenset,
        bytes,
        bytearray,
        type(None),
        object,
        type,
        slice,
        range,
        enumerate,
        zip,
        reversed,
        filter,
        map,
        complex,
        memoryview,
        property,
        staticmethod,
        classmethod,
        super,
    }

    # Standard library modules to avoid injecting from
    STDLIB_MODULES = {
        "builtins",
        "sys",
        "os",
        "io",
        "time",
        "datetime",
        "json",
        "pickle",
        "pathlib",
        "urllib",
        "http",
        "socket",
        "threading",
        "asyncio",
        "collections",
        "itertools",
        "functools",
        "operator",
        "math",
        "random",
        "string",
        "re",
        "struct",
        "array",
        "copy",
        "pprint",
        "reprlib",
        "enum",
        "decimal",
        "fractions",
        "statistics",
        "hashlib",
        "hmac",
        "secrets",
        "uuid",
        "csv",
        "xml",
        "html",
        "email",
        "base64",
        "binascii",
        "codecs",
        "unicodedata",
        "stringprep",
        "readline",
        "rlcompleter",
        "sqlite3",
        "zlib",
        "gzip",
        "bz2",
        "lzma",
        "zipfile",
        "tarfile",
        "tempfile",
        "glob",
        "fnmatch",
        "shutil",
        "logging",
    }

    def __init__(self, registry=None):
        """Initialize the type analyzer.

        Args:
            registry: Optional ServiceRegistry for checking registrations
        """
        self.registry = registry
        self._analysis_cache: dict[Any, InjectResult] = {}

    def should_inject(self, param: inspect.Parameter, type_hint: Any = None) -> InjectResult:
        """Determine if a parameter should be auto-injected.

        Args:
            param: The parameter to analyze
            type_hint: Optional explicit type hint (uses param.annotation if None)

        Returns:
            InjectResult with decision and context
        """
        # Use provided type hint or parameter annotation
        if type_hint is None:
            type_hint = param.annotation

        # Rule 1: Never inject if has non-None default
        if param.default not in (param.empty, None):
            return InjectResult(InjectDecision.NO, type_hint, "Has non-None default value")

        # Handle missing annotations
        if type_hint == param.empty or type_hint is None:
            return InjectResult(InjectDecision.NO, type_hint, "No type annotation")

        # Use cached result if available
        cache_key = (type_hint, param.name)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        # Analyze the type hint
        result = self._analyze_type_hint(type_hint)

        # Cache the result
        self._analysis_cache[cache_key] = result

        return result

    def _analyze_type_hint(self, type_hint: Any) -> InjectResult:
        """Analyze a specific type hint for injection rules.

        Args:
            type_hint: The type hint to analyze

        Returns:
            InjectResult with decision and context
        """
        # Rule 2: Never inject built-in types
        if type_hint in self.BUILTIN_TYPES:
            return InjectResult(InjectDecision.NO, type_hint, "Built-in type")

        # Handle string annotations (forward references)
        if isinstance(type_hint, str):
            return self._handle_forward_reference(type_hint)

        # Get origin and args for complex types
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        # Handle generic types and special forms
        if origin is not None:
            return self._analyze_generic_type(type_hint, origin, args)

        # Rule 7: Check if it's from standard library
        if self._is_stdlib_type(type_hint):
            return InjectResult(
                InjectDecision.NO, type_hint, "Standard library type (not registered)"
            )

        # Rule 8: User-defined types - check if registered
        if self.registry and self.registry.has(type_hint):
            return InjectResult(InjectDecision.YES, type_hint, "Registered user type")

        # Check if it's a class we could potentially instantiate
        if inspect.isclass(type_hint):
            # For unregistered classes, we can still try to create them
            # if they don't require parameters or all parameters can be injected
            return InjectResult(
                InjectDecision.YES, type_hint, "Unregistered class (will attempt auto-creation)"
            )

        # Default: don't inject unknown types
        return InjectResult(InjectDecision.NO, type_hint, "Unknown type")

    def _analyze_generic_type(self, type_hint: Any, origin: Any, args: tuple) -> InjectResult:
        """Analyze generic types and special forms.

        Args:
            type_hint: The full type hint
            origin: The origin type (e.g., list for List[str])
            args: Type arguments (e.g., (str,) for List[str])

        Returns:
            InjectResult with decision and context
        """
        # Rule 3: Never inject generic types with parameters
        if args and origin in (list, dict, tuple, set, frozenset):
            return InjectResult(
                InjectDecision.NO, type_hint, f"Generic type {origin.__name__} with parameters"
            )

        # Handle Union types (including Optional)
        if origin is Union:
            return self._analyze_union_type(type_hint, args)

        # Handle Protocol types
        if self._is_protocol(origin):
            return self._analyze_protocol_type(type_hint, origin)

        # Handle Literal types
        if origin is Literal:
            return InjectResult(
                InjectDecision.NO, type_hint, f"Literal types cannot be injected: {args}"
            )

        # Handle Callable types
        if origin in (type(Callable), type(Callable[..., Any])):
            return self._analyze_callable_type(type_hint, args)

        # Handle typing constructs
        if hasattr(origin, "__module__") and origin.__module__ == "typing":
            # Most typing constructs should not be injected
            return InjectResult(InjectDecision.NO, type_hint, f"Typing construct: {origin}")

        # Handle generic types (e.g., Service[T])
        if self._is_generic_type(origin):
            return self._analyze_generic_service_type(type_hint, origin, args)

        # Handle other generic types - analyze the origin
        return self._analyze_type_hint(origin)

    def _analyze_union_type(self, type_hint: Any, args: tuple) -> InjectResult:
        """Analyze Union types, including Optional.

        Args:
            type_hint: The Union type hint
            args: Union member types

        Returns:
            InjectResult with decision and context
        """
        # Check if this is Optional[T] (Union[T, None])
        if len(args) == 2 and type(None) in args:
            # This is Optional[T]
            inner_type = args[0] if args[1] is type(None) else args[1]

            # Rule 4: Inject Optional[T] only if T is registered
            return InjectResult(
                InjectDecision.OPTIONAL,
                type_hint,
                f"Optional type - inject {inner_type} if available",
                inner_type=inner_type,
            )

        # Rule 5: For other Union types, only inject if exactly one member is registered
        if self.registry:
            registered_members = []
            for arg in args:
                if self.registry.has(arg):
                    registered_members.append(arg)

            if len(registered_members) == 1:
                return InjectResult(
                    InjectDecision.YES,
                    type_hint,
                    f"Union with single registered member: {registered_members[0]}",
                    inner_type=registered_members[0],
                )
            elif len(registered_members) > 1:
                return InjectResult(
                    InjectDecision.ERROR,
                    type_hint,
                    f"Ambiguous Union - multiple registered members: {registered_members}",
                    candidates=registered_members,
                )

        # No registered members
        return InjectResult(InjectDecision.NO, type_hint, "Union with no registered members")

    def _handle_forward_reference(self, type_str: str) -> InjectResult:
        """Handle string type annotations (forward references).

        Args:
            type_str: The string type annotation

        Returns:
            InjectResult with decision and context
        """
        # Try to resolve the forward reference more systematically
        resolved_type = None
        
        try:
            # Method 1: Walk the stack looking for the type in any frame's globals
            frame = inspect.currentframe()
            while frame:
                if type_str in frame.f_globals:
                    candidate = frame.f_globals[type_str]
                    # Verify it's actually a class
                    if inspect.isclass(candidate):
                        resolved_type = candidate
                        break
                frame = frame.f_back
                    
            # Method 2: Try to resolve in loaded modules
            if resolved_type is None:
                import sys
                frame = inspect.currentframe()
                for _ in range(15):  # Look back more frames
                    if frame is None:
                        break
                    module_name = frame.f_globals.get('__name__')
                    if module_name and module_name in sys.modules:
                        module = sys.modules[module_name]
                        if hasattr(module, type_str):
                            candidate = getattr(module, type_str)
                            if inspect.isclass(candidate):
                                resolved_type = candidate
                                break
                    frame = frame.f_back

            # Method 3: Try built-ins
            if resolved_type is None and hasattr(__builtins__, type_str):
                candidate = getattr(__builtins__, type_str)
                if inspect.isclass(candidate):
                    resolved_type = candidate

            # If we found a valid type, analyze it
            if resolved_type is not None and inspect.isclass(resolved_type):
                return self._analyze_type_hint(resolved_type)

        except Exception:
            pass

        # Rule 6: Cannot resolve forward reference
        return InjectResult(
            InjectDecision.ERROR, type_str, f"Cannot resolve forward reference: '{type_str}'"
        )

    def _is_stdlib_type(self, type_hint: Any) -> bool:
        """Check if a type is from the standard library.

        Args:
            type_hint: The type to check

        Returns:
            True if the type is from standard library
        """
        if not hasattr(type_hint, "__module__"):
            return False

        module = type_hint.__module__
        if not module:
            return False

        # Check if it's from a standard library module
        root_module = module.split(".")[0]
        return root_module in self.STDLIB_MODULES

    def _is_protocol(self, type_hint: Any) -> bool:
        """Check if a type is a Protocol.

        Args:
            type_hint: The type to check

        Returns:
            True if the type is a Protocol
        """
        try:
            # Check if it's a subclass of Protocol
            if hasattr(type_hint, "__mro__"):
                return any(
                    hasattr(base, "__module__")
                    and base.__module__ == "typing"
                    and base.__name__ == "Protocol"
                    for base in type_hint.__mro__
                )

            # Check for typing.Protocol marker
            return hasattr(type_hint, "_is_protocol") and type_hint._is_protocol
        except (AttributeError, TypeError):
            return False

    def _analyze_protocol_type(self, type_hint: Any, origin: Any) -> InjectResult:
        """Analyze Protocol types for injection.

        Args:
            type_hint: The Protocol type hint
            origin: The origin type

        Returns:
            InjectResult with decision and context
        """
        # Protocol types can be injected if there's a registered implementation
        if self.registry and self.registry.has(type_hint):
            return InjectResult(
                InjectDecision.YES, type_hint, "Registered Protocol implementation found"
            )

        # Look for implementations that satisfy the protocol
        if self.registry:
            # Find types that might implement this protocol
            candidates = []
            for descriptor in self.registry.list_all():
                if self._implements_protocol(descriptor.service_type, type_hint):
                    candidates.append(descriptor.service_type)

            if len(candidates) == 1:
                return InjectResult(
                    InjectDecision.YES,
                    type_hint,
                    f"Single Protocol implementation found: {candidates[0]}",
                    inner_type=candidates[0],
                )
            elif len(candidates) > 1:
                return InjectResult(
                    InjectDecision.ERROR,
                    type_hint,
                    f"Multiple Protocol implementations found: {candidates}",
                    candidates=candidates,
                )

        return InjectResult(InjectDecision.NO, type_hint, "No Protocol implementation registered")

    def _implements_protocol(self, implementation: type, protocol: type) -> bool:
        """Check if a type implements a protocol.

        This is a simplified check - in practice, you'd want more
        sophisticated protocol checking.
        """
        try:
            # For runtime_checkable protocols, use isinstance
            if hasattr(protocol, "__runtime_checkable__"):
                # Create a dummy instance to test (not ideal, but works)
                return hasattr(implementation, "__annotations__")

            # Basic duck typing check - see if implementation has required methods
            if hasattr(protocol, "__annotations__"):
                for method_name in protocol.__annotations__:
                    if not hasattr(implementation, method_name):
                        return False
                return True

            return False
        except (AttributeError, TypeError):
            return False

    def _analyze_callable_type(self, type_hint: Any, args: tuple) -> InjectResult:
        """Analyze Callable type hints.

        Args:
            type_hint: The Callable type hint
            args: Type arguments

        Returns:
            InjectResult with decision
        """
        # Callable types generally shouldn't be auto-injected unless explicitly registered
        if self.registry and self.registry.has(type_hint):
            return InjectResult(InjectDecision.YES, type_hint, "Registered Callable found")

        return InjectResult(
            InjectDecision.NO, type_hint, "Callable types require explicit registration"
        )

    def _is_generic_type(self, type_hint: Any) -> bool:
        """Check if a type is a generic type that could have implementations.

        Args:
            type_hint: The type to check

        Returns:
            True if it's a generic type we should try to resolve
        """
        try:
            # Check if it's a user-defined generic class
            if hasattr(type_hint, "__origin__") or hasattr(type_hint, "__parameters__"):
                # It's generic, but check if it's from user code
                module = getattr(type_hint, "__module__", "")
                if module and not self._is_stdlib_module(module):
                    return True

            return False
        except (AttributeError, TypeError):
            return False

    def _is_stdlib_module(self, module_name: str) -> bool:
        """Check if a module name is from the standard library."""
        if not module_name:
            return False
        root_module = module_name.split(".")[0]
        return root_module in self.STDLIB_MODULES

    def _analyze_generic_service_type(
        self, type_hint: Any, origin: Any, args: tuple
    ) -> InjectResult:
        """Analyze generic service types like Service[T].

        Args:
            type_hint: The full generic type
            origin: The origin type (e.g., Service)
            args: Type arguments (e.g., (T,))

        Returns:
            InjectResult with decision
        """
        # For generic service types, we try to resolve the origin type
        # The container might have a factory that handles the generic parameters

        if self.registry and self.registry.has(origin):
            return InjectResult(
                InjectDecision.YES,
                type_hint,
                f"Generic service type registered: {origin} with args {args}",
                inner_type=origin,
            )

        # Also check if the full generic type is registered
        if self.registry and self.registry.has(type_hint):
            return InjectResult(InjectDecision.YES, type_hint, "Full generic type registered")

        return InjectResult(
            InjectDecision.NO, type_hint, f"Generic type not registered: {origin}[{args}]"
        )

    def analyze_callable(self, func: callable) -> dict[str, InjectResult]:
        """Analyze all parameters of a callable for injection.

        Args:
            func: The callable to analyze

        Returns:
            Dict mapping parameter names to InjectResults
        """
        sig = inspect.signature(func)
        results = {}

        # Get type hints for better forward reference resolution
        try:
            type_hints = get_type_hints_safe(func)
        except Exception:
            type_hints = {}

        for param_name, param in sig.parameters.items():
            # Skip 'self' and 'cls' parameters
            if param_name in ("self", "cls"):
                continue

            # Use type hint if available, otherwise use annotation
            type_hint = type_hints.get(param_name, param.annotation)

            result = self.should_inject(param, type_hint)
            results[param_name] = result

        return results

    def can_auto_create(self, cls: type) -> bool:
        """Check if a class can be auto-created (all params injectable).

        Args:
            cls: The class to check

        Returns:
            True if all required parameters can be injected
        """
        if not inspect.isclass(cls):
            return False

        try:
            sig = inspect.signature(cls.__init__)
        except (ValueError, TypeError):
            return False

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # If parameter has default, it's not required
            if param.default != param.empty:
                continue

            # Check if we can inject this parameter
            result = self.should_inject(param)
            if result.decision == InjectDecision.NO:
                return False
            if result.decision == InjectDecision.ERROR:
                return False

        return True

    def detect_circular_dependency(
        self, start_type: type, visited: set[type] = None, path: list[type] = None
    ) -> list[type] | None:
        """Detect circular dependencies in type hierarchy.

        Args:
            start_type: The type to start analysis from
            visited: Set of already visited types
            path: Current path being explored

        Returns:
            List representing the circular path, or None if no cycle
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if start_type in visited:
            # Found cycle - return the circular path
            cycle_start = path.index(start_type) if start_type in path else 0
            return path[cycle_start:] + [start_type]

        if not inspect.isclass(start_type):
            return None

        visited.add(start_type)
        path.append(start_type)

        try:
            # Get type hints for better resolution
            type_hints = get_type_hints_safe(start_type.__init__)
            sig = inspect.signature(start_type.__init__)
        except (ValueError, TypeError):
            visited.remove(start_type)
            path.remove(start_type)
            return None

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Use type hint if available, otherwise annotation
            type_hint = type_hints.get(param_name, param.annotation)
            if type_hint == param.empty:
                continue

            # Extract the actual type for checking
            actual_type = self._extract_dependency_type(type_hint)
            if actual_type and inspect.isclass(actual_type):
                # Recursively check this parameter's type
                cycle = self.detect_circular_dependency(actual_type, visited.copy(), path.copy())
                if cycle:
                    return cycle

        visited.remove(start_type)
        path.remove(start_type)
        return None

    def _extract_dependency_type(self, type_hint: Any) -> type | None:
        """Extract the concrete type from a type hint for dependency analysis.

        Args:
            type_hint: The type hint to analyze

        Returns:
            The concrete type, or None if it can't be determined
        """
        # Handle direct types
        if inspect.isclass(type_hint):
            return type_hint

        # Handle Optional[T] -> T
        if self._is_optional(type_hint):
            args = get_args(type_hint)
            inner_type = args[0] if args[1] is type(None) else args[1]
            return self._extract_dependency_type(inner_type)

        # Handle Union types - only if single non-None type
        origin = get_origin(type_hint)
        if origin is Union:
            args = get_args(type_hint)
            non_none_types = [arg for arg in args if arg is not type(None)]
            if len(non_none_types) == 1:
                return self._extract_dependency_type(non_none_types[0])

        # Handle generic types - extract origin
        if origin is not None and inspect.isclass(origin):
            return origin

        return None

    def _is_optional(self, type_hint: Any) -> bool:
        """Check if a type hint is Optional[T]."""
        origin = get_origin(type_hint)
        if origin is Union:
            args = get_args(type_hint)
            return len(args) == 2 and type(None) in args
        return False

    def analyze_dependency_tree(
        self, root_type: type, max_depth: int = 10
    ) -> dict[type, list[type]]:
        """Analyze the full dependency tree for a type.

        Args:
            root_type: The root type to analyze
            max_depth: Maximum depth to prevent infinite recursion

        Returns:
            Dict mapping types to their direct dependencies
        """
        dependency_tree = {}
        visited = set()

        def _analyze_type(current_type: type, depth: int = 0):
            if depth >= max_depth or current_type in visited:
                return

            visited.add(current_type)
            dependencies = []

            try:
                type_hints = get_type_hints_safe(current_type.__init__)
                sig = inspect.signature(current_type.__init__)

                for param_name, param in sig.parameters.items():
                    if param_name == "self":
                        continue

                    type_hint = type_hints.get(param_name, param.annotation)
                    if type_hint == param.empty:
                        continue

                    dependency_type = self._extract_dependency_type(type_hint)
                    if dependency_type and inspect.isclass(dependency_type):
                        dependencies.append(dependency_type)
                        _analyze_type(dependency_type, depth + 1)

                dependency_tree[current_type] = dependencies

            except (ValueError, TypeError):
                dependency_tree[current_type] = []

        _analyze_type(root_type)
        return dependency_tree

    def clear_cache(self) -> None:
        """Clear the analysis cache."""
        self._analysis_cache.clear()


def get_type_hints_safe(func: callable) -> dict[str, Any]:
    """Safely get type hints, handling errors gracefully.

    Args:
        func: The callable to get type hints for

    Returns:
        Dict of type hints, empty if analysis fails
    """
    try:
        # Try the standard way first
        from typing import get_type_hints

        return get_type_hints(func)
    except (NameError, AttributeError, TypeError):
        # Fall back to raw annotations
        return getattr(func, "__annotations__", {})


# Utility functions for common type checks


def is_optional(type_hint: Any) -> bool:
    """Check if a type hint is Optional[T]."""
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        return len(args) == 2 and type(None) in args
    return False


def get_optional_inner(type_hint: Any) -> Any:
    """Get the inner type from Optional[T]."""
    if is_optional(type_hint):
        args = get_args(type_hint)
        return args[0] if args[1] is type(None) else args[1]
    return type_hint


def is_union(type_hint: Any) -> bool:
    """Check if a type hint is a Union type."""
    return get_origin(type_hint) is Union


def is_generic_with_args(type_hint: Any) -> bool:
    """Check if a type hint is a generic type with arguments."""
    origin = get_origin(type_hint)
    args = get_args(type_hint)
    return origin is not None and len(args) > 0
