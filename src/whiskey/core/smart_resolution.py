"""Smart resolution system for async/sync API consistency.

This module implements the solution for Phase 2.1: Clarify async/sync API consistency.
It provides a unified resolve() method that works intelligently in both sync and async contexts
without the complex workarounds and confusing method names of the current system.

Key improvements:
1. resolve() works in both sync and async contexts automatically
2. Clear separation between smart and explicit resolution methods
3. Simplified dict-like access with better async factory handling
4. Consistent API across Container and Application classes
5. Better error messages guiding users to the right method

Design principles:
- Smart by default: resolve() adapts to context
- Explicit when needed: resolve_sync() and resolve_async() for guaranteed behavior
- Clear error messages: guide users to the right method when automatic resolution fails
- Performance: avoid unnecessary asyncio overhead in pure sync contexts
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class SmartResolver:
    """Smart resolution mixin that provides context-aware resolve() method."""

    def resolve(self, key: str | type, *, name: str | None = None, **context) -> Any:
        """Smart resolution that works in both sync and async contexts.

        This method automatically detects the context and returns either:
        - In sync context: The resolved instance directly
        - In async context: An awaitable that resolves to the instance

        Args:
            key: Component key (string or type)
            name: Optional name for named components
            **context: Additional context for scoped resolution

        Returns:
            In sync context: The resolved instance
            In async context: Awaitable[instance]

        Examples:
            # In sync context
            db = container.resolve(Database)

            # In async context
            db = await container.resolve(Database)

            # Works in both contexts automatically
        """
        # Check if we're in an async context
        try:
            asyncio.get_running_loop()
            # We're in an async context - return a coroutine
            return self._resolve_async_impl(key, name=name, **context)
        except RuntimeError:
            # No event loop - we're in sync context
            return self._resolve_sync_impl(key, name=name, **context)

    def resolve_sync(
        self, key: str | type, *, name: str | None = None, overrides: dict | None = None, **context
    ) -> T:
        """Explicitly synchronous resolution.

        Use this when you need guaranteed synchronous behavior, even in async contexts.
        This method will never return an awaitable.

        Args:
            key: Component key (string or type)
            name: Optional name for named components
            overrides: Override values for dependency injection
            **context: Additional context for scoped resolution

        Returns:
            The resolved instance (never awaitable)

        Raises:
            RuntimeError: If the component requires async resolution
        """
        # Check if the registered provider is async before attempting resolution
        try:
            descriptor = self.registry.get(key, name)
            if callable(descriptor.provider) and asyncio.iscoroutinefunction(descriptor.provider):
                # This is an async factory - fail with clear error
                key_name = key.__name__ if hasattr(key, "__name__") else repr(key)
                raise RuntimeError(
                    f"Cannot resolve async factory '{key}' synchronously. "
                    f"Use 'await container.resolve({key_name})' or move to an async context."
                )
        except KeyError:
            pass  # Let normal resolution handle this

        # Pass overrides through context
        if overrides:
            context["overrides"] = overrides

        try:
            return self._resolve_sync_impl(key, name=name, context=context)
        except Exception as e:
            # Check for async-related errors in the message
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in ["async factory", "coroutine", "async"]):
                key_name = key.__name__ if hasattr(key, "__name__") else repr(key)
                raise RuntimeError(
                    f"Cannot resolve '{key}' synchronously due to async requirements. "
                    f"Use 'await container.resolve({key_name})' or move to an async context."
                ) from e
            else:
                # Re-raise other errors
                raise

    async def resolve_async(self, key: str | type, *, name: str | None = None, **context) -> T:
        """Explicitly asynchronous resolution.

        Use this when you need guaranteed asynchronous behavior and want to support
        async factories even in mixed sync/async code.

        Args:
            key: Component key (string or type)
            name: Optional name for named components
            **context: Additional context for scoped resolution

        Returns:
            The resolved instance
        """
        return await self._resolve_async_impl(key, name=name, **context)

    def _resolve_sync_impl(
        self, key: str | type, name: str | None = None, context: dict | None = None
    ) -> Any:
        """Internal synchronous resolution implementation."""
        # This should delegate to the existing resolve_sync logic
        # Subclasses will implement this
        raise NotImplementedError("Subclasses must implement _resolve_sync_impl")

    async def _resolve_async_impl(
        self, key: str | type, name: str | None = None, context: dict | None = None
    ) -> Any:
        """Internal asynchronous resolution implementation."""
        # This should delegate to the existing async resolve logic
        # Subclasses will implement this
        raise NotImplementedError("Subclasses must implement _resolve_async_impl")


class SmartDictAccess:
    """Smart dict-like access that handles async factories intelligently."""

    def __getitem__(self, key: str | type) -> Any:
        """Get a component using dict-like syntax with smart async handling.

        This method tries to resolve synchronously first, but provides clear
        guidance when async resolution is needed.

        Args:
            key: Component key (string or type)

        Returns:
            The resolved component instance

        Raises:
            RuntimeError: If async resolution is required (with helpful message)
            KeyError: If component is not registered
        """
        # Check if component is registered first
        if key not in self:
            raise KeyError(f"Component '{key}' not found in container")

        # Check if the registered provider is async before attempting resolution
        try:
            descriptor = self.registry.get(
                key
            )  # This should be available since key is in container
            if callable(descriptor.provider) and asyncio.iscoroutinefunction(descriptor.provider):
                # This is an async factory - provide clear guidance
                key_name = key.__name__ if hasattr(key, "__name__") else repr(key)
                raise RuntimeError(
                    f"Component '{key}' requires async resolution because it uses an async factory. "
                    f"Use 'await container.resolve({key_name})' or move to an async context."
                )
        except KeyError:
            pass  # Let normal resolution handle this

        try:
            # Try sync resolution
            return self._resolve_sync_impl(key)
        except Exception as e:
            # Check for async-related errors in the message
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in ["async factory", "coroutine", "async"]):
                key_name = key.__name__ if hasattr(key, "__name__") else repr(key)
                raise RuntimeError(
                    f"Component '{key}' requires async resolution. "
                    f"Use 'await container.resolve({key_name})' or move to an async context."
                ) from e
            else:
                # Re-raise other errors
                raise


class SmartCalling:
    """Smart function calling that works in both sync and async contexts."""

    def call(self, func: callable, *args, **kwargs) -> Any:
        """Smart function calling with dependency injection.

        This method automatically detects the context and handles both sync and async functions.

        Args:
            func: The function to call
            *args: Positional arguments
            **kwargs: Keyword arguments (override injection)

        Returns:
            In sync context: The function result
            In async context: Awaitable[result] if func is async, otherwise result
        """
        # Check if we're in an async context
        try:
            asyncio.get_running_loop()
            # We're in async context - use async calling
            return self._call_async_impl(func, args, kwargs)
        except RuntimeError:
            # No event loop - we're in sync context
            return self._call_sync_impl(func, args, kwargs)

    def call_sync(self, func: callable, *args, **kwargs) -> Any:
        """Explicitly synchronous function calling.

        This method guarantees synchronous execution without complex workarounds.

        Args:
            func: The function to call
            *args: Positional arguments
            **kwargs: Keyword arguments (override injection)

        Returns:
            The function result (never awaitable)

        Raises:
            RuntimeError: If the function requires async calling
        """
        # Check if function is async upfront
        if asyncio.iscoroutinefunction(func):
            func_name = getattr(func, "__name__", str(func))
            raise RuntimeError(
                f"Cannot call async function '{func_name}' synchronously. "
                f"Use 'await container.call({func_name})' or 'await container.call_async({func_name})'."
            )

        try:
            return self._call_sync_impl(func, args, kwargs)
        except Exception as e:
            # Check for async-related errors in the message
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in ["async function", "coroutine", "async"]):
                func_name = getattr(func, "__name__", str(func))
                raise RuntimeError(
                    f"Cannot call '{func_name}' synchronously due to async requirements. "
                    f"Use 'await container.call({func_name})' or move to an async context."
                ) from e
            else:
                # Re-raise other errors
                raise

    async def call_async(self, func: callable, *args, **kwargs) -> Any:
        """Explicitly asynchronous function calling.

        Args:
            func: The function to call
            *args: Positional arguments
            **kwargs: Keyword arguments (override injection)

        Returns:
            The function result
        """
        return await self._call_async_impl(func, args, kwargs)

    def _call_sync_impl(self, func: callable, args: tuple, kwargs: dict) -> Any:
        """Internal synchronous calling implementation."""
        raise NotImplementedError("Subclasses must implement _call_sync_impl")

    async def _call_async_impl(self, func: callable, args: tuple, kwargs: dict) -> Any:
        """Internal asynchronous calling implementation."""
        raise NotImplementedError("Subclasses must implement _call_async_impl")


def detect_async_context() -> bool:
    """Detect if we're currently in an async context.

    Returns:
        True if there's a running event loop, False otherwise
    """
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def is_async_callable(func: callable) -> bool:
    """Check if a callable is async (coroutine function).

    Args:
        func: The callable to check

    Returns:
        True if the callable is async
    """
    return asyncio.iscoroutinefunction(func)


def create_context_aware_error(operation: str, key: Any, error: Exception) -> Exception:
    """Create a context-aware error message with guidance.

    Args:
        operation: The operation that failed (e.g., "resolve", "call")
        key: The key/function that failed
        error: The original error

    Returns:
        Enhanced error with context-specific guidance
    """
    in_async = detect_async_context()
    key_name = getattr(key, "__name__", str(key))

    if "async factory" in str(error).lower():
        if in_async:
            suggestion = f"Use 'await container.{operation}({key_name})' for async factories"
        else:
            suggestion = f"Use 'container.{operation}_async({key_name})' or move to async context"
    else:
        if in_async:
            suggestion = f"Consider using 'container.{operation}_sync({key_name})' for guaranteed sync behavior"
        else:
            suggestion = f"Use 'await container.{operation}({key_name})' if you need async support"

    return type(error)(f"{error}. {suggestion}")
