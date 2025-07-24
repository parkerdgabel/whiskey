"""Command bus for CQRS and command handling in IoC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, TypeVar

from loguru import logger

from whiskey.core.decorators import inject

T = TypeVar("T")


@dataclass
class Command(ABC):
    """Base class for commands."""
    pass


@dataclass
class Query(ABC, Generic[T]):
    """Base class for queries."""
    pass


class CommandHandler(ABC, Generic[T]):
    """Base class for command handlers."""
    
    @abstractmethod
    async def handle(self, command: Command) -> T:
        """Handle the command."""
        pass


class QueryHandler(ABC, Generic[T]):
    """Base class for query handlers."""
    
    @abstractmethod
    async def handle(self, query: Query[T]) -> T:
        """Handle the query."""
        pass


class CommandBus:
    """
    Command bus for handling commands and queries with automatic DI.
    
    Implements CQRS pattern for better separation of concerns.
    """
    
    def __init__(self):
        self._command_handlers: dict[type[Command], type[CommandHandler] | Callable] = {}
        self._query_handlers: dict[type[Query], type[QueryHandler] | Callable] = {}
        self._middleware: list[Callable] = []
    
    def register_command(
        self,
        command_type: type[Command],
        handler: type[CommandHandler] | Callable[..., Awaitable[Any]]
    ) -> None:
        """Register a command handler."""
        self._command_handlers[command_type] = handler
        logger.debug(f"Registered command handler for {command_type.__name__}")
    
    def register_query(
        self,
        query_type: type[Query[T]],
        handler: type[QueryHandler[T]] | Callable[..., Awaitable[T]]
    ) -> None:
        """Register a query handler."""
        self._query_handlers[query_type] = handler
        logger.debug(f"Registered query handler for {query_type.__name__}")
    
    def command(self, command_type: type[Command]):
        """Decorator to register a command handler."""
        def decorator(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self.register_command(command_type, handler)
            return handler
        return decorator
    
    def handle_query(self, query_type: type[Query[T]]):
        """Decorator to register a query handler."""
        def decorator(handler: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            self.register_query(query_type, handler)
            return handler
        return decorator
    
    async def execute(self, command: Command) -> Any:
        """Execute a command."""
        handler_type = self._command_handlers.get(type(command))
        
        if not handler_type:
            raise ValueError(f"No handler registered for command {type(command).__name__}")
        
        # If it's a class, instantiate it with DI
        if isinstance(handler_type, type):
            from whiskey.core.decorators import get_default_container
            container = get_default_container()
            handler = await container.resolve(handler_type)
            return await handler.handle(command)
        else:
            # It's a function, inject dependencies
            injected = inject(handler_type)
            return await injected(command)
    
    async def query(self, query: Query[T]) -> T:
        """Execute a query."""
        handler_type = self._query_handlers.get(type(query))
        
        if not handler_type:
            raise ValueError(f"No handler registered for query {type(query).__name__}")
        
        # If it's a class, instantiate it with DI
        if isinstance(handler_type, type):
            from whiskey.core.decorators import get_default_container
            container = get_default_container()
            handler = await container.resolve(handler_type)
            return await handler.handle(query)
        else:
            # It's a function, inject dependencies
            injected = inject(handler_type)
            return await injected(query)


# Example Commands and Queries

@dataclass
class CreateUserCommand(Command):
    """Example command for creating a user."""
    username: str
    email: str
    password: str


@dataclass
class GetUserQuery(Query[dict[str, Any]]):
    """Example query for getting a user."""
    user_id: str


@dataclass
class UpdateUserCommand(Command):
    """Example command for updating a user."""
    user_id: str
    updates: dict[str, Any]