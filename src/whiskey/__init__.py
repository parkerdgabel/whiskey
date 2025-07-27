<<<<<<< HEAD
"""Whiskey - Simple, Pythonic dependency injection for modern Python applications.

Whiskey is a lightweight, type-safe dependency injection framework designed
for Python developers who value simplicity and clarity. It provides powerful
IoC (Inversion of Control) capabilities without the complexity often
associated with enterprise DI frameworks.

Key Features:
    - Dict-like container API for intuitive service registration
    - Automatic injection based on type hints - no annotations needed
    - Named dependencies for multiple implementations
    - Conditional registration based on runtime conditions
    - Lazy resolution for efficient resource usage
    - Async-first design with sync support
    - Rich application framework with lifecycle management
    - Event system with wildcard patterns
    - Component discovery and auto-registration
    - Extensible with plugins for web, CLI, AI, and more

Quick Start:
    >>> from whiskey import Container, inject, singleton, component
    >>>
    >>> # Define services with decorators
    >>> @singleton
    ... class Database:
    ...     def __init__(self):
    ...         self.connection = "postgresql://localhost/myapp"
    >>>
    >>> @component
    ... class UserService:
    ...     def __init__(self, db: Database):  # Automatically injected!
    ...         self.db = db
    ...     
    ...     async def get_user(self, user_id: int):
    ...         return await self.db.query(f"SELECT * FROM users WHERE id={user_id}")
    >>>
    >>> # Use dependency injection in functions
    >>> @inject
    ... async def process_user(user_id: int, service: UserService):
    ...     # user_id passed manually, service auto-injected
    ...     return await service.get_user(user_id)
    >>>
    >>> # Call the function - service is injected automatically
    >>> user = await process_user(123)

For more information, see the documentation at:
https://github.com/yourusername/whiskey
"""
=======
"""Whiskey - Simple, Pythonic dependency injection for AI applications."""
>>>>>>> origin/main

__version__ = "0.1.0"

# Core exports
<<<<<<< HEAD
from whiskey.core.application import Whiskey
# Builder pattern removed - use Whiskey() directly
from whiskey.core.container import Container
from whiskey.core.decorators import (
    call,
    call_sync,
    component,
    configure_app,
    factory,
    get_app,
    inject,
    invoke,
    on_error,
    on_shutdown,
    on_startup,
    provide,
    resolve,
    resolve_async,
    scoped,
    singleton,
    when_debug,
    when_env,
    when_production,
    wrap_function,
)
from whiskey.core.lazy import Lazy, lazy_inject
from whiskey.core.registry import Scope
from whiskey.core.scopes import ContextVarScope, ScopeType
from whiskey.core.types import Disposable, Initializable, Inject

# Legacy aliases for backward compatibility
Application = Whiskey
=======
from whiskey.core.application import Application, ApplicationConfig, ComponentMetadata
from whiskey.core.container import Container
from whiskey.core.decorators import factory, inject, provide, scoped, singleton
from whiskey.core.scopes import ContextVarScope, Scope, ScopeType
from whiskey.core.types import Disposable, Initializable
>>>>>>> origin/main

__all__ = [
    # Core DI
    "Container",
    "inject",
<<<<<<< HEAD
    "singleton",
    "factory",
    "scoped",
    "component",
    "provide",  # Alias for component
    # Application Framework
    "Whiskey",
    "Application",  # Legacy alias
    # "create_app",  # Removed - use Whiskey() directly
=======
    "provide",
    "singleton",
    "factory",
    "scoped",
>>>>>>> origin/main
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
<<<<<<< HEAD
    # Lazy
    "Lazy",
    "lazy_inject",
    # Types
    "Inject",
    "Initializable",
    "Disposable",
    # Lifecycle
    "on_startup",
    "on_shutdown",
    "on_error",
    # Conditional
    "when_env",
    "when_debug",
    "when_production",
    # Utilities
    "call",
    "call_sync",
    "invoke",
    "wrap_function",
    "resolve",
    "resolve_async",
    "get_app",
    "configure_app",
]
=======
    # Application
    "Application",
    "ApplicationConfig",
    "ComponentMetadata",
    # Types
    "Initializable",
    "Disposable",
]
>>>>>>> origin/main
