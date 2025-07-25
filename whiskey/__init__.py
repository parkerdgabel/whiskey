"""Whiskey - Simple, Pythonic dependency injection for AI applications."""

__version__ = "0.1.0"

# Core exports
from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.container import Container
from whiskey.core.decorators import factory, inject, provide, scoped, singleton
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
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
    # Application
    "Application",
    "ApplicationConfig",
    # Types
    "Initializable",
    "Disposable",
]