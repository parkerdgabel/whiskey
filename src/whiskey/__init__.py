"""Whiskey - Simple, Pythonic dependency injection for modern Python applications.

Whiskey is a lightweight, type-safe dependency injection framework designed
for Python developers who value simplicity and clarity. It provides powerful
IoC (Inversion of Control) capabilities without the complexity often
associated with enterprise DI frameworks.

Key Features:
    - Dict-like container API for intuitive service registration
    - Explicit injection with Annotated types
    - Async-first design with sync support
    - Rich application framework with lifecycle management
    - Event system with wildcard patterns
    - Component discovery and auto-registration
    - Extensible with plugins for web, CLI, AI, and more

Quick Start:
    >>> from whiskey import Container, inject, Inject
    >>> from typing import Annotated
    >>> 
    >>> # Create container and register services
    >>> container = Container()
    >>> container[Database] = Database("postgresql://...")
    >>> 
    >>> # Use dependency injection
    >>> @inject
    ... async def get_user(
    ...     user_id: int,
    ...     db: Annotated[Database, Inject()]
    ... ):
    ...     return await db.find_user(user_id)

For more information, see the documentation at:
https://github.com/yourusername/whiskey
"""

__version__ = "0.1.0"

# Core exports
from whiskey.core.application import Application, ApplicationConfig, ComponentMetadata
from whiskey.core.container import Container
from whiskey.core.decorators import factory, inject, provide, scoped, singleton, Inject
from whiskey.core.discovery import ComponentDiscoverer, ContainerInspector, discover_components
from whiskey.core.scopes import ContextVarScope, Scope, ScopeType
from whiskey.core.types import Disposable, Initializable

__all__ = [
    # Core DI
    "Container",
    "inject",
    "provide",
    "singleton",
    "factory",
    "scoped",
    "Inject",
    # Discovery
    "ComponentDiscoverer",
    "ContainerInspector",
    "discover_components",
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
    # Application
    "Application",
    "ApplicationConfig",
    "ComponentMetadata",
    # Types
    "Initializable",
    "Disposable",
]