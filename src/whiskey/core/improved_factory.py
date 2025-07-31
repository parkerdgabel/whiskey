"""Improved factory decorator with better syntax and type inference.

This module implements the solution for Phase 2.2: Redesign factory decorator syntax.
The new factory decorator provides:

1. Automatic key inference from return type hints
2. Consistent syntax with other decorators (@component, @singleton)
3. Clear, helpful error messages
4. Better IDE and type checker support
5. Multiple intuitive calling patterns

Design principles:
- Convention over configuration: infer key from return type when possible
- Fail fast with helpful messages: guide developers to correct usage
- Consistent API: follow same patterns as other decorators
- Type safety: preserve type information for IDEs and type checkers
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar, get_type_hints

from .registry import Scope

T = TypeVar("T")


class ImprovedFactoryDecorator:
    """Improved factory decorator with automatic type inference."""

    def __init__(
        self,
        key_or_func=None,
        *,
        key: str | type | None = None,
        name: str | None = None,
        scope: Scope = Scope.TRANSIENT,
        tags: set[str] | None = None,
        condition: Callable[[], bool] | None = None,
        lazy: bool = False,
        app=None,  # Whiskey instance
    ):
        self.key_or_func = key_or_func
        self.explicit_key = key
        self.name = name
        self.scope = scope
        self.tags = tags
        self.condition = condition
        self.lazy = lazy
        self.app = app

    def __call__(self, func: Callable | None = None) -> Callable:
        """Handle different calling patterns for the factory decorator."""

        # Pattern: @factory (without parentheses) - key_or_func is the function
        if (
            func is None
            and self.key_or_func is not None
            and callable(self.key_or_func)
            and not inspect.isclass(self.key_or_func)
        ):
            func = self.key_or_func
            self.key_or_func = None

        # Pattern: @factory() or @factory(key=...) or @factory(SomeClass) - return decorator
        if func is None:
            return self._create_decorator()

        # We have a function, apply the decorator
        return self._register_factory(func)

    def _create_decorator(self) -> Callable[[Callable], Callable]:
        """Create the actual decorator function."""

        def decorator(func: Callable) -> Callable:
            return self._register_factory(func)

        return decorator

    def _register_factory(self, func: Callable) -> Callable:
        """Register the factory function with the container."""

        # Determine the key to use
        factory_key = self._determine_factory_key(func)

        # Get the target app
        from .decorators import _get_default_app

        target_app = self.app or _get_default_app()

        # Register the factory
        target_app.factory(
            factory_key,
            func,
            name=self.name,
            scope=self.scope,
            tags=self.tags,
            condition=self.condition,
            lazy=self.lazy,
        )

        return func

    def _determine_factory_key(self, func: Callable) -> str | type:
        """Determine the key to use for factory registration."""

        # 1. If explicit key provided via parameter, use it
        if self.explicit_key is not None:
            return self.explicit_key

        # 2. If key provided as first positional argument (e.g., @factory(Database))
        if self.key_or_func is not None and (
            not callable(self.key_or_func) or inspect.isclass(self.key_or_func)
        ):
            return self.key_or_func

        # 3. Try to infer key from return type hint
        try:
            type_hints = get_type_hints(func)
            return_type = type_hints.get("return")

            if return_type is not None:
                # Validate that return type is suitable as a key
                if self._is_valid_factory_key(return_type):
                    return return_type
                else:
                    raise ValueError(
                        f"Cannot use return type '{return_type}' as factory key. "
                        f"Return type must be a concrete class or string. "
                        f"For generic types like List[T], specify key explicitly: "
                        f"@factory(key=YourConcreteType)"
                    )

        except (NameError, AttributeError) as e:
            # Handle forward references or other type hint issues
            self._raise_helpful_error(func, f"Could not resolve return type hint: {e}")

        # 4. No key could be determined - provide helpful error
        self._raise_helpful_error(func, "No factory key specified and no return type hint found")

    def _is_valid_factory_key(self, type_hint: Any) -> bool:
        """Check if a type hint can be used as a factory key."""

        # Allow concrete classes
        if inspect.isclass(type_hint):
            return True

        # Allow strings
        if isinstance(type_hint, str):
            return True

        # Reject generic types with parameters (List[T], Dict[K,V], etc.)
        origin = getattr(type_hint, "__origin__", None)
        if origin is not None:
            return False

        # Reject other complex types
        return False

    def _raise_helpful_error(self, func: Callable, base_message: str) -> None:
        """Raise a helpful error message with guidance."""

        func_name = getattr(func, "__name__", "unknown")

        error_message = (
            f"Cannot determine factory key for function '{func_name}': {base_message}.\n\n"
            f"Solutions:\n"
            f"1. Add a return type hint:\n"
            f"   @factory\n"
            f"   def {func_name}() -> YourType:\n"
            f"       return YourType()\n\n"
            f"2. Specify key explicitly:\n"
            f"   @factory(key=YourType)\n"
            f"   def {func_name}():\n"
            f"       return YourType()\n\n"
            f"3. Use positional key syntax:\n"
            f"   @factory(YourType)\n"
            f"   def {func_name}():\n"
            f"       return YourType()"
        )

        raise ValueError(error_message)


def create_improved_factory_decorator():
    """Create the improved factory decorator function."""

    def factory(
        key_or_func=None,
        *,
        key: str | type | None = None,
        name: str | None = None,
        scope: Scope = Scope.TRANSIENT,
        tags: set[str] | None = None,
        condition: Callable[[], bool] | None = None,
        lazy: bool = False,
        app=None,
    ) -> Callable | Callable[[Callable], Callable]:
        """Improved factory decorator with automatic key inference.

        This decorator can be used in multiple ways:

        1. With automatic key inference (recommended):
           @factory
           def create_service() -> UserService:
               return UserService()

        2. With explicit key:
           @factory(key=UserService)
           def create_service():
               return UserService()

        3. With positional key:
           @factory(UserService)
           def create_service():
               return UserService()

        4. With options:
           @factory(scope=Scope.SINGLETON)
           def create_cache() -> RedisCache:
               return RedisCache()

        Args:
            key_or_func: Either the factory key or the function (when used without parentheses)
            key: Explicit key for the factory (alternative to positional key)
            name: Optional name for named components
            scope: Component scope (default: transient)
            tags: Set of tags for categorization
            condition: Optional registration condition
            lazy: Whether to use lazy resolution
            app: Optional Whiskey instance (uses default if None)

        Returns:
            The decorated function
        """

        decorator = ImprovedFactoryDecorator(
            key_or_func=key_or_func,
            key=key,
            name=name,
            scope=scope,
            tags=tags,
            condition=condition,
            lazy=lazy,
            app=app,
        )

        # Only pass key_or_func as func if it's a function (not a class)
        func_to_pass = (
            key_or_func if callable(key_or_func) and not inspect.isclass(key_or_func) else None
        )
        return decorator(func_to_pass)

    return factory


# Create the improved factory decorator
improved_factory = create_improved_factory_decorator()
