"""Whiskey - Simple, Pythonic dependency injection for modern Python applications.

Whiskey is a lightweight, type-safe dependency injection framework designed
for Python developers who value simplicity and clarity. It provides powerful
IoC (Inversion of Control) capabilities without the complexity often
associated with enterprise DI frameworks.

Key Features:
    - Dict-like container API for intuitive service registration
    - Explicit injection with Annotated types
    - Named dependencies for multiple implementations
    - Conditional registration based on runtime conditions  
    - Lazy resolution for efficient resource usage
    - Async-first design with sync support
    - Rich application framework with lifecycle management
    - Event system with wildcard patterns
    - Component discovery and auto-registration
    - Extensible with plugins for web, CLI, AI, and more

Quick Start:
    >>> from whiskey import Container, inject, Inject, Lazy
    >>> from typing import Annotated
    >>> 
    >>> # Create container and register services
    >>> container = Container()
    >>> container[Database] = Database("postgresql://...")
    >>> container[Database, "readonly"] = ReadOnlyDB("postgresql://replica")
    >>> 
    >>> # Use dependency injection with named and lazy dependencies
    >>> @inject
    ... async def get_user(
    ...     user_id: int,
    ...     db: Annotated[Database, Inject(name="readonly")],
    ...     cache: Annotated[Lazy[Cache], Inject()]
    ... ):
    ...     # Cache is only initialized if accessed
    ...     cached = cache.value.get(f"user:{user_id}")
    ...     if cached:
    ...         return cached
    ...     user = await db.find_user(user_id)
    ...     cache.value.set(f"user:{user_id}", user)
    ...     return user

For more information, see the documentation at:
https://github.com/yourusername/whiskey
"""

__version__ = "0.1.0"

# Core exports
from whiskey.core.application import Application
from whiskey.core.container import Container
from whiskey.core.decorators import factory, inject, service, scoped, singleton, component
from whiskey.core.scopes import ContextVarScope, ScopeType
from whiskey.core.registry import Scope
from whiskey.core.builder import create_app

__all__ = [
    # Core DI
    "Container",
    "inject",
    "service",
    "singleton",
    "factory",
    "scoped",
    "component",
    # Application Framework
    "Application",
    "create_app",
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
]