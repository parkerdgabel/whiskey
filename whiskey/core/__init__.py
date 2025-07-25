"""Core Whiskey dependency injection framework."""

from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.container import Container
from whiskey.core.decorators import (
    factory,
    get_default_container,
    inject,
    provide,
    scoped,
    set_default_container,
    singleton,
)
from whiskey.core.scopes import ContextVarScope, Scope, ScopeType
from whiskey.core.types import Disposable, Initializable

__all__ = [
    # Container
    "Container",
    "get_default_container",
    "set_default_container",
    # Decorators
    "provide",
    "singleton",
    "factory",
    "inject",
    "scoped",
    # Application
    "Application",
    "ApplicationConfig",
    # Scopes
    "Scope",
    "ContextVarScope",
    "ScopeType",
    # Types
    "Initializable",
    "Disposable",
]