"""Whiskey - Next-generation dependency injection and IoC framework for Python AI applications."""

from loguru import logger

__version__ = "0.1.0"

# Core exports
from whiskey.core.container import Container
from whiskey.core.decorators import inject, provide, singleton, factory
from whiskey.core.scopes import Scope, ScopeType

# IoC exports
from whiskey.core.application import Application, ApplicationConfig
from whiskey.core.events import Event, EventBus
from whiskey.core.commands import Command, Query, CommandBus

# AI-specific exports
from whiskey.ai.context import AIContext, ConversationScope
from whiskey.ai.models import (
    ChatCompletionModel,
    EmbeddingModel,
    Message,
    ChatCompletion,
    EmbeddingResponse,
)

__all__ = [
    # Core DI
    "Container",
    "inject",
    "provide",
    "singleton",
    "factory",
    "Scope",
    "ScopeType",
    
    # IoC
    "Application",
    "ApplicationConfig",
    "Event",
    "EventBus",
    "Command",
    "Query",
    "CommandBus",
    
    # AI
    "AIContext",
    "ConversationScope",
    "ChatCompletionModel",
    "EmbeddingModel",
    "Message",
    "ChatCompletion",
    "EmbeddingResponse",
]

# Configure default logger
logger.disable("whiskey")  # Disabled by default, users can enable with logger.enable("whiskey")