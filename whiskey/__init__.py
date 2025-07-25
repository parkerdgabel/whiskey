"""Whiskey - Next-generation dependency injection and IoC framework for Python AI applications."""

from loguru import logger

__version__ = "0.1.0"

# Core exports
from whiskey.core.container import Container
from whiskey.core.decorators import inject, provide, singleton, factory
from whiskey.core.scopes import Scope, ScopeType, ContextVarScope
from whiskey.core.discovery import autodiscover, discoverable, scope

# IoC exports
from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.events import Event, EventBus
from whiskey.core.commands import Command, Query, CommandBus
from whiskey.core.bootstrap import ApplicationBuilder, standalone

# Plugin exports
from whiskey.plugins import WhiskeyPlugin, BasePlugin

__all__ = [
    # Core DI
    "Container",
    "inject",
    "provide",
    "singleton",
    "factory",
    "Scope",
    "ScopeType",
    "ContextVarScope",
    
    # Discovery
    "autodiscover",
    "discoverable",
    "scope",
    
    # IoC
    "Application",
    "ApplicationConfig",
    "ApplicationBuilder",
    "standalone",
    "Event",
    "EventBus",
    "Command",
    "Query",
    "CommandBus",
    
    # Plugins
    "WhiskeyPlugin",
    "BasePlugin",
]

# Configure default logger
logger.disable("whiskey")  # Disabled by default, users can enable with logger.enable("whiskey")