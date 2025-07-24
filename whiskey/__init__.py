"""Whiskey - Next-generation dependency injection and IoC framework for Python AI applications."""

from loguru import logger

__version__ = "0.1.0"

# Core exports
# AI-specific exports
from whiskey.ai.context import AIContext, ConversationScope
from whiskey.core.container import Container
from whiskey.core.decorators import inject, provide, singleton
from whiskey.core.scopes import Scope, ScopeType

__all__ = [
    "AIContext",
    "Container",
    "ConversationScope",
    "Scope",
    "ScopeType",
    "inject",
    "provide",
    "singleton",
]

# Configure default logger
logger.disable("whiskey")  # Disabled by default, users can enable with logger.enable("whiskey")