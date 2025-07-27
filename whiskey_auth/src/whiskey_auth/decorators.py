"""Authentication and authorization decorators."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, TypeVar

from whiskey import inject
from whiskey_auth.core import AuthContext, AuthenticationError, AuthorizationError, Permission, Role

F = TypeVar("F", bound=Callable[..., Any])


def requires_auth(func: F) -> F:
    """Require authentication for the decorated function.

    This decorator ensures that a user is authenticated before
    the function is called. It works with both sync and async functions.

    Args:
        func: Function to protect

    Returns:
        Wrapped function that checks authentication

    Raises:
        AuthenticationError: If user is not authenticated

    Example:
        >>> @requires_auth
        >>> async def protected_endpoint(user: CurrentUser):
        >>>     return f"Hello {user.username}"
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get the current container and resolve auth context
            from whiskey.core.container import get_current_container

            container = get_current_container()
            if container:
                try:
                    auth_context = await container.resolve(AuthContext)
                except Exception:
                    auth_context = None
            else:
                auth_context = kwargs.get("auth_context")

            # Check authentication
            if not auth_context or not auth_context.is_authenticated:
                raise AuthenticationError("Authentication required")

            # Remove auth_context from kwargs if it was there
            kwargs.pop("auth_context", None)

            # Call original function
            return await func(*args, **kwargs)

        # Apply inject to enable DI for the original function
        return inject(async_wrapper)
    else:

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get the current container and resolve auth context
            from whiskey.core.container import get_current_container

            container = get_current_container()
            if container:
                try:
                    auth_context = container.resolve_sync(AuthContext)
                except Exception:
                    auth_context = None
            else:
                auth_context = kwargs.get("auth_context")

            # Check authentication
            if not auth_context or not auth_context.is_authenticated:
                raise AuthenticationError("Authentication required")

            # Remove auth_context from kwargs if it was there
            kwargs.pop("auth_context", None)

            return func(*args, **kwargs)

        # Apply inject to enable DI for the original function
        return inject(sync_wrapper)


def requires_permission(*permissions: str | Permission) -> Callable[[F], F]:
    """Require specific permissions for the decorated function.

    Args:
        *permissions: One or more permissions required (ANY of them)

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        AuthorizationError: If user lacks required permissions

    Example:
        >>> @requires_permission("admin", "moderator")
        >>> async def admin_action(user: CurrentUser):
        >>>     # User must have either admin OR moderator permission
        >>>     pass
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Get the current container and resolve auth context
                from whiskey.core.container import get_current_container

                container = get_current_container()
                if container:
                    try:
                        auth_context = await container.resolve(AuthContext)
                    except Exception:
                        auth_context = None
                else:
                    auth_context = kwargs.get("auth_context")

                # First check authentication
                if not auth_context or not auth_context.is_authenticated:
                    raise AuthenticationError("Authentication required")

                # Check permissions (user needs ANY of the specified permissions)
                has_permission = any(auth_context.has_permission(perm) for perm in permissions)

                if not has_permission:
                    perm_names = [str(p) for p in permissions]
                    raise AuthorizationError(
                        f"User lacks required permissions: {', '.join(perm_names)}"
                    )

                # Remove auth_context from kwargs if it was there
                kwargs.pop("auth_context", None)

                return await func(*args, **kwargs)

            return inject(async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Get the current container and resolve auth context
                from whiskey.core.container import get_current_container

                container = get_current_container()
                if container:
                    try:
                        auth_context = container.resolve_sync(AuthContext)
                    except Exception:
                        auth_context = None
                else:
                    auth_context = kwargs.get("auth_context")

                # First check authentication
                if not auth_context or not auth_context.is_authenticated:
                    raise AuthenticationError("Authentication required")

                has_permission = any(auth_context.has_permission(perm) for perm in permissions)

                if not has_permission:
                    perm_names = [str(p) for p in permissions]
                    raise AuthorizationError(
                        f"User lacks required permissions: {', '.join(perm_names)}"
                    )

                # Remove auth_context from kwargs if it was there
                kwargs.pop("auth_context", None)

                return func(*args, **kwargs)

            return inject(sync_wrapper)

    return decorator


def requires_role(*roles: str | Role) -> Callable[[F], F]:
    """Require specific roles for the decorated function.

    Args:
        *roles: One or more roles required (ANY of them)

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        AuthorizationError: If user lacks required roles

    Example:
        >>> @requires_role("admin", "moderator")
        >>> async def moderate_content(user: CurrentUser):
        >>>     # User must have either admin OR moderator role
        >>>     pass
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Get the current container and resolve auth context
                from whiskey.core.container import get_current_container

                container = get_current_container()
                if container:
                    try:
                        auth_context = await container.resolve(AuthContext)
                    except Exception:
                        auth_context = None
                else:
                    auth_context = kwargs.get("auth_context")

                # First check authentication
                if not auth_context or not auth_context.is_authenticated:
                    raise AuthenticationError("Authentication required")

                # Check roles (user needs ANY of the specified roles)
                has_role = any(auth_context.has_role(role) for role in roles)

                if not has_role:
                    role_names = [str(r) for r in roles]
                    raise AuthorizationError(f"User lacks required roles: {', '.join(role_names)}")

                # Remove auth_context from kwargs if it was there
                kwargs.pop("auth_context", None)

                return await func(*args, **kwargs)

            return inject(async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Get the current container and resolve auth context
                from whiskey.core.container import get_current_container

                container = get_current_container()
                if container:
                    try:
                        auth_context = container.resolve_sync(AuthContext)
                    except Exception:
                        auth_context = None
                else:
                    auth_context = kwargs.get("auth_context")

                # First check authentication
                if not auth_context or not auth_context.is_authenticated:
                    raise AuthenticationError("Authentication required")

                has_role = any(auth_context.has_role(role) for role in roles)

                if not has_role:
                    role_names = [str(r) for r in roles]
                    raise AuthorizationError(f"User lacks required roles: {', '.join(role_names)}")

                # Remove auth_context from kwargs if it was there
                kwargs.pop("auth_context", None)

                return func(*args, **kwargs)

            return inject(sync_wrapper)

    return decorator


def requires_all_permissions(*permissions: str | Permission) -> Callable[[F], F]:
    """Require ALL specified permissions for the decorated function.

    Unlike requires_permission which needs ANY permission, this decorator
    requires the user to have ALL specified permissions.

    Args:
        *permissions: All permissions required

    Returns:
        Decorator function

    Example:
        >>> @requires_all_permissions("read", "write", "delete")
        >>> async def full_access_operation(user: CurrentUser):
        >>>     # User must have read AND write AND delete permissions
        >>>     pass
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Get the current container and resolve auth context
                from whiskey.core.container import get_current_container

                container = get_current_container()
                if container:
                    try:
                        auth_context = await container.resolve(AuthContext)
                    except Exception:
                        auth_context = None
                else:
                    auth_context = kwargs.get("auth_context")

                # First check authentication
                if not auth_context or not auth_context.is_authenticated:
                    raise AuthenticationError("Authentication required")

                # Check that user has ALL permissions
                missing_perms = [
                    str(perm) for perm in permissions if not auth_context.has_permission(perm)
                ]

                if missing_perms:
                    raise AuthorizationError(
                        f"User lacks required permissions: {', '.join(missing_perms)}"
                    )

                # Remove auth_context from kwargs if it was there
                kwargs.pop("auth_context", None)

                return await func(*args, **kwargs)

            return inject(async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Get the current container and resolve auth context
                from whiskey.core.container import get_current_container

                container = get_current_container()
                if container:
                    try:
                        auth_context = container.resolve_sync(AuthContext)
                    except Exception:
                        auth_context = None
                else:
                    auth_context = kwargs.get("auth_context")

                # First check authentication
                if not auth_context or not auth_context.is_authenticated:
                    raise AuthenticationError("Authentication required")

                missing_perms = [
                    str(perm) for perm in permissions if not auth_context.has_permission(perm)
                ]

                if missing_perms:
                    raise AuthorizationError(
                        f"User lacks required permissions: {', '.join(missing_perms)}"
                    )

                # Remove auth_context from kwargs if it was there
                kwargs.pop("auth_context", None)

                return func(*args, **kwargs)

            return inject(sync_wrapper)

    return decorator
