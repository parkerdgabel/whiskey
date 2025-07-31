"""Type analysis engine for automatic dependency injection decisions.

This module implements Whiskey's smart type analyzer that examines type hints
to automatically determine which parameters should be injected. It handles
complex scenarios including Optional types, Union types, forward references,
generics, and standard library types with clear, predictable rules.

Classes:
    InjectDecision: Enumeration of injection decisions (YES, NO, OPTIONAL, ERROR)
    InjectResult: Detailed result of injection analysis for a parameter
    TypeAnalyzer: Main analyzer for type hint examination

Injection Rules:
    1. Never inject parameters with non-None defaults
    2. Never inject built-in types (str, int, list, dict, etc.)
    3. Never inject generic types with parameters (List[T], Dict[K,V])
    4. Inject Optional[T] only if T is registered, else None
    5. Inject Union types only if exactly one member is registered
    6. Resolve forward references then apply rules
    7. Don't inject standard library types unless explicitly registered
    8. Always inject user-defined types that are registered

Functions:
    get_type_hints_safe: Safely extract type hints handling errors
    is_optional: Check if a type is Optional[T]
    get_optional_inner: Extract T from Optional[T]
    is_union: Check if a type is a Union
    is_generic_with_args: Check if type has generic parameters
    is_builtin_type: Check if type is a Python built-in
    is_stdlib_type: Check if type is from standard library
    is_protocol: Check if type is a Protocol

Example:
    >>> from whiskey.core import TypeAnalyzer, ComponentRegistry
    >>> 
    >>> registry = ComponentRegistry()
    >>> registry.register(Database, PostgresDB)
    >>> 
    >>> analyzer = TypeAnalyzer(registry)
    >>> 
    >>> # Analyze a callable
    >>> def process(name: str, db: Database, cache: Optional[Cache]):
    ...     pass
    >>> 
    >>> results = analyzer.analyze_callable(process)
    >>> # results['name'] = InjectResult(NO, str, "built-in type")
    >>> # results['db'] = InjectResult(YES, Database, "registered component")
    >>> # results['cache'] = InjectResult(OPTIONAL, Cache, "optional type")

See Also:
    - whiskey.core.container: Uses analyzer for injection decisions
    - whiskey.core.registry: Component registration state
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Callable, ClassVar, Union, get_args, get_origin

from .errors import TypeAnalysisError
from .generic_resolution import GenericTypeResolver

# Handle Python version differences
try:
    from typing import Literal
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
        candidates: list[Any] | None = None,
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
    
    def __eq__(self, other) -> bool:
        """Check equality based on all attributes."""
        if not isinstance(other, InjectResult):
            return False
        return (
            self.decision == other.decision
            and self.type_hint == other.type_hint
            and self.reason == other.reason
            and self.inner_type == other.inner_type
            and self.candidates == other.candidates
        )


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
    BUILTIN_TYPES: ClassVar[set[type]] = {
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
    STDLIB_MODULES: ClassVar[set[str]] = {
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
            registry: Optional ComponentRegistry for checking registrations
        """
        self.registry = registry
        self._analysis_cache: dict[Any, InjectResult] = {}
        self._callable_cache: dict[Any, dict[str, InjectResult]] = {}  # Cache for entire callable analysis
        self._generic_resolver = GenericTypeResolver(registry)

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

        # Rule 1: Never inject if has any default value (except for Optional[T] = None)
        if param.default is not inspect.Parameter.empty:
            # Special case: Optional[T] = None should still be considered for injection
            if param.default is None and self._is_optional(type_hint):
                # Continue analysis - Optional with None default can still be injected
                pass
            else:
                return InjectResult(InjectDecision.NO, type_hint, "Has default value")

        # Handle missing annotations
        if type_hint == inspect.Parameter.empty or type_hint is None:
            return InjectResult(InjectDecision.NO, type_hint, "No type annotation")

        # Create efficient cache key - only type hint matters for analysis
        # Use id() for better performance with complex types
        cache_key = self._create_cache_key(type_hint)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        # Analyze the type hint
        result = self._analyze_type_hint(type_hint)

        # Cache the result with size limit to prevent unbounded growth
        self._cache_result(cache_key, result)

        return result

    def _analyze_type_hint(self, type_hint: Any) -> InjectResult:
        """Analyze a specific type hint for injection rules.

        Args:
            type_hint: The type hint to analyze

        Returns:
            InjectResult with decision and context
        """
        # Check if we've already analyzed this exact type hint
        type_cache_key = self._create_cache_key(type_hint)
        if type_cache_key in self._analysis_cache:
            return self._analysis_cache[type_cache_key]
        
        # Perform the actual analysis
        result = self._analyze_type_hint_uncached(type_hint)
        
        # Cache the result
        self._cache_result(type_cache_key, result)
        return result
    
    def _analyze_type_hint_uncached(self, type_hint: Any) -> InjectResult:
        """Perform the actual type hint analysis without caching.
        
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
            # For unregistered classes, be conservative and don't inject
            # The container will handle auto-creation if needed
            return InjectResult(
                InjectDecision.NO, type_hint, "Not registered (auto-creation handled by container)"
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
        if origin is Callable or (hasattr(origin, '__name__') and origin.__name__ == 'Callable'):
            return self._analyze_callable_type(type_hint, args)

        # Handle typing constructs
        if hasattr(origin, "__module__") and origin.__module__ == "typing":
            # Most typing constructs should not be injected
            return InjectResult(InjectDecision.NO, type_hint, f"Typing construct: {origin}")

        # Handle generic types (e.g., Service[T])
        if self._is_generic_type(origin):
            return self._analyze_generic_component_type(type_hint, origin, args)

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

            # Rule 4: Check if T is something that should never be injected
            inner_result = self._analyze_type_hint(inner_type)
            if inner_result.decision == InjectDecision.NO and (
                "generic type" in inner_result.reason.lower() or
                "built-in type" in inner_result.reason.lower() or
                "standard library type" in inner_result.reason.lower()
            ):
                # If T is a built-in, generic, or stdlib type, Optional[T] should not be injected either
                return InjectResult(
                    InjectDecision.NO,
                    type_hint,
                    f"Optional type with non-injectable inner type: {inner_result.reason}",
                    inner_type=inner_type,
                )
            else:
                # For user types (registered or not), Optional[T] can be injected if available
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
                    f"Ambiguous Union type - multiple registered members: {registered_members}",
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
        # This method is called when we have a string annotation that couldn't be resolved
        # by get_type_hints_safe. At this point, we should check if the type might be
        # registered in the container by name
        
        if self.registry and self.registry.has(type_str):
            return InjectResult(
                InjectDecision.YES, 
                type_str, 
                f"Forward reference '{type_str}' found in registry"
            )
        
        # Try to resolve the string to an actual type in common namespaces
        # This handles cases where a class is defined but not registered
        resolved_type = self._try_resolve_string_annotation(type_str)
        if resolved_type is not None:
            # Recursively analyze the resolved type
            return self._analyze_type_hint(resolved_type)
        
        # If not in registry and can't resolve, we can't inject it
        return InjectResult(
            InjectDecision.NO,
            type_str,
            f"Forward reference '{type_str}' not found in registry"
        )

    def _try_resolve_string_annotation(self, type_str: str) -> type | None:
        """Try to resolve a string annotation to an actual type.
        
        Args:
            type_str: The string type annotation
            
        Returns:
            The resolved type or None if it can't be resolved
        """
        # Try to find the type in the calling frame's globals
        import inspect
        
        try:
            # Get the calling frame (skipping internal analyzer frames)
            frame = inspect.currentframe()
            while frame:
                if frame.f_globals.get('__name__') != __name__:
                    # Found a frame outside the analyzer
                    globals_dict = frame.f_globals
                    if type_str in globals_dict:
                        potential_type = globals_dict[type_str]
                        if inspect.isclass(potential_type):
                            return potential_type
                    break
                frame = frame.f_back
                
        except Exception:
            # If frame inspection fails, fall back to safe methods
            pass
        
        return None

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
                if self._implements_protocol(descriptor.component_type, type_hint):
                    candidates.append(descriptor.component_type)

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

    def _analyze_generic_component_type(
        self, type_hint: Any, origin: Any, args: tuple
    ) -> InjectResult:
        """Analyze generic component types like Component[T].

        Args:
            type_hint: The full generic type
            origin: The origin type (e.g., Component)
            args: Type arguments (e.g., (T,))

        Returns:
            InjectResult with decision
        """
        # First check if the exact generic type is registered
        if self.registry and self.registry.has(type_hint):
            return InjectResult(InjectDecision.YES, type_hint, "Full generic type registered")

        # Use the generic resolver to find concrete implementations  
        concrete_type = self._generic_resolver.resolve_generic(type_hint)
        if concrete_type:
            return InjectResult(
                InjectDecision.YES,
                type_hint,
                f"Generic type resolved to concrete implementation: {concrete_type}",
                inner_type=concrete_type,
            )

        # Check if the origin type is registered (fallback)
        if self.registry and self.registry.has(origin):
            return InjectResult(
                InjectDecision.YES,
                type_hint,
                f"Generic origin type registered: {origin} with args {args}",
                inner_type=origin,
            )

        # Analyze the generic type for additional information
        analysis = self._generic_resolver.analyze_generic_type(type_hint)
        
        if analysis['is_protocol'] and analysis['concrete_implementations']:
            # Protocol with registered implementations
            if len(analysis['concrete_implementations']) == 1:
                return InjectResult(
                    InjectDecision.YES,
                    type_hint,
                    f"Protocol with single implementation: {analysis['concrete_implementations'][0]}",
                    inner_type=analysis['concrete_implementations'][0],
                )
            else:
                return InjectResult(
                    InjectDecision.ERROR,
                    type_hint,
                    f"Ambiguous protocol - multiple implementations: {analysis['concrete_implementations']}",
                    candidates=analysis['concrete_implementations'],
                )

        return InjectResult(
            InjectDecision.NO, 
            type_hint, 
            f"Generic type not resolvable: {origin}[{args}] - no concrete implementations found"
        )

    def analyze_callable(self, func: callable) -> dict[str, InjectResult]:
        """Analyze all parameters of a callable for injection.

        Args:
            func: The callable to analyze

        Returns:
            Dict mapping parameter names to InjectResults
        """
        # Check callable cache first
        func_cache_key = self._create_callable_cache_key(func)
        if func_cache_key in self._callable_cache:
            return self._callable_cache[func_cache_key].copy()  # Return copy to prevent mutation
        
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError) as e:
            raise TypeAnalysisError(f"Cannot analyze non-callable object: {e}") from e
        
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

        # Cache the results
        self._cache_callable_result(func_cache_key, results)
        return results
    
    def _create_callable_cache_key(self, func: callable) -> tuple:
        """Create a cache key for callable analysis.
        
        Args:
            func: The callable to create a key for
            
        Returns:
            Tuple that can be used as a cache key
        """
        try:
            # Use the function object directly if possible
            return (func,)
        except TypeError:
            # If not hashable, use id and qualname
            return (id(func), getattr(func, '__qualname__', str(func)))
    
    def _cache_callable_result(self, cache_key: tuple, results: dict[str, InjectResult]) -> None:
        """Cache callable analysis results with size management.
        
        Args:
            cache_key: The cache key
            results: The analysis results to cache
        """
        max_callable_cache_size = 500  # Reasonable limit for callable cache
        
        if len(self._callable_cache) >= max_callable_cache_size:
            # Remove oldest entries (simple FIFO for performance)
            oldest_keys = list(self._callable_cache.keys())[:50]  # Remove 10% of entries
            for old_key in oldest_keys:
                del self._callable_cache[old_key]
        
        self._callable_cache[cache_key] = results

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
            if param.default != inspect.Parameter.empty:
                continue

            # Check if we can inject this parameter
            result = self.should_inject(param)
            if result.decision == InjectDecision.NO:
                return False
            if result.decision == InjectDecision.ERROR:
                return False

        return True

    def detect_circular_dependency(
        self, start_type: type, visited: set[type] | None = None, path: list[type] | None = None
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
            return [*path[cycle_start:], start_type]

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
            if type_hint == inspect.Parameter.empty:
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
                    if type_hint == inspect.Parameter.empty:
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

    def _create_cache_key(self, type_hint: Any) -> tuple:
        """Create an efficient cache key for type hints.
        
        Args:
            type_hint: The type hint to create a key for
            
        Returns:
            Tuple that can be used as a cache key
        """
        # For basic types, use the type itself
        if isinstance(type_hint, type):
            return (type_hint,)
        
        # For string annotations, use the string directly
        if isinstance(type_hint, str):
            return (type_hint,)
        
        # For complex types (generics, unions), use a combination of id and repr
        # This handles cases like Optional[List[str]] efficiently
        try:
            # Try to use the type hint directly if it's hashable
            return (type_hint,)
        except TypeError:
            # If not hashable, use id and repr as fallback
            return (id(type_hint), repr(type_hint))
    
    def _cache_result(self, cache_key: tuple, result: InjectResult) -> None:
        """Cache an analysis result with size management.
        
        Args:
            cache_key: The cache key
            result: The analysis result to cache
        """
        # Implement LRU-like behavior with size limit
        max_cache_size = 1000  # Reasonable limit for type analysis cache
        
        if len(self._analysis_cache) >= max_cache_size:
            # Remove oldest entries (simple FIFO for performance)
            # In a production system, you might want a proper LRU cache
            oldest_keys = list(self._analysis_cache.keys())[:100]  # Remove 10% of entries
            for old_key in oldest_keys:
                del self._analysis_cache[old_key]
        
        self._analysis_cache[cache_key] = result

    def clear_cache(self) -> None:
        """Clear all analysis caches."""
        self._analysis_cache.clear()
        self._callable_cache.clear()
        self._generic_resolver.clear_cache()

    def register_generic_implementation(self, generic_type: Any, concrete_type: type) -> None:
        """Register a concrete implementation for a generic type.
        
        Args:
            generic_type: The generic type (e.g., Repository[User])
            concrete_type: The concrete implementation class
            
        Example:
            >>> analyzer.register_generic_implementation(Repository[User], UserRepository)
        """
        self._generic_resolver.register_concrete(generic_type, concrete_type)
        # Clear cache since new implementations might change resolution decisions
        self.clear_cache()

    def get_generic_resolver(self) -> GenericTypeResolver:
        """Get the generic type resolver for advanced configuration.
        
        Returns:
            The GenericTypeResolver instance
        """
        return self._generic_resolver


def get_type_hints_safe(func: callable) -> dict[str, Any]:
    """Safely get type hints, handling errors gracefully.

    Args:
        func: The callable to get type hints for

    Returns:
        Dict of type hints, empty if analysis fails
    """
    try:
        # Try the standard way first with proper namespace
        from typing import get_type_hints
        
        # Get the module where the function is defined
        module = inspect.getmodule(func)
        globalns = getattr(module, '__dict__', {}) if module else {}
        
        # Also include the function's own globals if available
        if hasattr(func, '__globals__'):
            globalns = {**globalns, **func.__globals__}
        
        # Try to get local namespace from the function's closure
        localns = {}
        if hasattr(func, '__code__'):
            # For methods, include the class namespace
            if hasattr(func, '__qualname__') and '.' in func.__qualname__:
                class_name = func.__qualname__.rsplit('.', 1)[0]
                if class_name in globalns:
                    cls = globalns[class_name]
                    if hasattr(cls, '__annotations__'):
                        localns.update(cls.__annotations__)
        
        return get_type_hints(func, globalns=globalns, localns=localns, include_extras=True)
    except (NameError, AttributeError, TypeError) as e:
        # If get_type_hints fails, try to resolve forward references manually
        annotations = getattr(func, "__annotations__", {})
        if not annotations:
            return {}
        
        # Try to resolve string annotations manually
        resolved = {}
        for name, annotation in annotations.items():
            if isinstance(annotation, str):
                # Try to resolve the string annotation
                try:
                    # Get the function's module and globals
                    module = inspect.getmodule(func)
                    if module and hasattr(module, '__dict__'):
                        # Try to find the type in the module
                        if annotation in module.__dict__:
                            resolved[name] = module.__dict__[annotation]
                        elif hasattr(func, '__globals__') and annotation in func.__globals__:
                            resolved[name] = func.__globals__[annotation]
                        else:
                            # Keep as string if can't resolve
                            resolved[name] = annotation
                    else:
                        resolved[name] = annotation
                except Exception:
                    resolved[name] = annotation
            else:
                resolved[name] = annotation
        
        return resolved


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
    """Check if a type hint is a Union type (excluding Optional)."""
    origin = get_origin(type_hint)
    if origin is Union:
        # Check if it's Optional (Union with None)
        args = get_args(type_hint)
        return not (len(args) == 2 and type(None) in args)
    return False


def is_generic_with_args(type_hint: Any) -> bool:
    """Check if a type hint is a generic type with arguments."""
    origin = get_origin(type_hint)
    args = get_args(type_hint)
    return origin is not None and len(args) > 0
