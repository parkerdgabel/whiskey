"""Tests for the command bus system."""

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from whiskey.core.commands import Command, CommandBus, CommandHandler, Query
from whiskey.core.exceptions import ServiceNotFoundError
from ..conftest import SimpleService


@dataclass
class CreateUserCommand(Command):
    """Test command for creating a user."""
    username: str
    email: str


@dataclass
class UpdateUserCommand(Command):
    """Test command for updating a user."""
    user_id: int
    username: str | None = None
    email: str | None = None


@dataclass
class GetUserQuery(Query):
    """Test query for getting a user."""
    user_id: int


@dataclass
class ListUsersQuery(Query):
    """Test query for listing users."""
    limit: int = 10
    offset: int = 0


class TestCommand:
    """Test Command base class."""
    
    @pytest.mark.unit
    def test_command_creation(self):
        """Test creating commands."""
        cmd = CreateUserCommand(username="john", email="john@example.com")
        
        assert cmd.username == "john"
        assert cmd.email == "john@example.com"
    
    @pytest.mark.unit
    def test_command_is_dataclass(self):
        """Test commands are dataclasses."""
        cmd = UpdateUserCommand(user_id=1, username="jane")
        
        # Should have dataclass features
        assert hasattr(cmd, "__dataclass_fields__")
        assert cmd.user_id == 1
        assert cmd.username == "jane"
        assert cmd.email is None


class TestQuery:
    """Test Query base class."""
    
    @pytest.mark.unit
    def test_query_creation(self):
        """Test creating queries."""
        query = GetUserQuery(user_id=123)
        
        assert query.user_id == 123
    
    @pytest.mark.unit
    def test_query_defaults(self):
        """Test query default values."""
        query = ListUsersQuery()
        
        assert query.limit == 10
        assert query.offset == 0


class TestCommandBus:
    """Test CommandBus functionality."""
    
    @pytest.mark.unit
    def test_command_bus_creation(self, container):
        """Test creating command bus."""
        bus = CommandBus(container)
        
        assert bus._container is container
        assert len(bus._handlers) == 0
        assert len(bus._middleware) == 0
    
    @pytest.mark.unit
    def test_register_string_handler(self, container):
        """Test registering handler with string command type."""
        bus = CommandBus(container)
        
        async def handler(cmd):
            return f"Handled: {cmd}"
        
        bus.register("test_command", handler)
        
        assert "test_command" in bus._handlers
        assert bus._handlers["test_command"] is handler
    
    @pytest.mark.unit
    def test_register_typed_handler(self, container):
        """Test registering handler with typed command."""
        bus = CommandBus(container)
        
        async def handler(cmd: CreateUserCommand):
            return f"Created user: {cmd.username}"
        
        bus.register(CreateUserCommand, handler)
        
        assert "CreateUserCommand" in bus._handlers
        assert bus._handlers["CreateUserCommand"] is handler
    
    @pytest.mark.unit
    def test_handler_decorator(self, container):
        """Test @handler decorator."""
        bus = CommandBus(container)
        
        @bus.handler(CreateUserCommand)
        async def create_user_handler(cmd: CreateUserCommand):
            return {"id": 1, "username": cmd.username}
        
        assert "CreateUserCommand" in bus._handlers
        assert bus._handlers["CreateUserCommand"] is create_user_handler
    
    @pytest.mark.unit
    async def test_execute_string_command(self, container):
        """Test executing command by string type."""
        bus = CommandBus(container)
        
        @bus.handler("test_command")
        async def handler(cmd):
            return f"Executed: {cmd['action']}"
        
        result = await bus.execute("test_command", {"action": "test"})
        
        assert result == "Executed: test"
    
    @pytest.mark.unit
    async def test_execute_typed_command(self, container):
        """Test executing typed command."""
        bus = CommandBus(container)
        
        @bus.handler(CreateUserCommand)
        async def handler(cmd: CreateUserCommand):
            return {"id": 1, "username": cmd.username, "email": cmd.email}
        
        cmd = CreateUserCommand(username="john", email="john@example.com")
        result = await bus.execute(cmd)
        
        assert result == {"id": 1, "username": "john", "email": "john@example.com"}
    
    @pytest.mark.unit
    async def test_execute_unregistered_command(self, container):
        """Test executing unregistered command raises error."""
        bus = CommandBus(container)
        
        with pytest.raises(KeyError) as exc_info:
            await bus.execute("unregistered_command", {})
        
        assert "No handler registered for command: unregistered_command" in str(exc_info.value)
    
    @pytest.mark.unit
    async def test_handler_with_dependencies(self, container):
        """Test handler with dependency injection."""
        bus = CommandBus(container)
        
        container.register_singleton(SimpleService)
        
        received_service = None
        
        @bus.handler(CreateUserCommand)
        async def handler(cmd: CreateUserCommand, service: SimpleService):
            nonlocal received_service
            received_service = service
            return {"username": cmd.username, "service": service.value}
        
        cmd = CreateUserCommand(username="john", email="john@example.com")
        result = await bus.execute(cmd)
        
        assert result["username"] == "john"
        assert result["service"] == "simple"
        assert isinstance(received_service, SimpleService)
    
    @pytest.mark.unit
    async def test_query_execution(self, container):
        """Test executing queries."""
        bus = CommandBus(container)
        
        @bus.handler(GetUserQuery)
        async def get_user_handler(query: GetUserQuery):
            return {"id": query.user_id, "username": f"user_{query.user_id}"}
        
        query = GetUserQuery(user_id=42)
        result = await bus.execute(query)
        
        assert result == {"id": 42, "username": "user_42"}
    
    @pytest.mark.unit
    async def test_middleware_execution(self, container):
        """Test middleware execution chain."""
        bus = CommandBus(container)
        
        execution_log = []
        
        class LoggingMiddleware:
            async def process(self, command, next_handler):
                execution_log.append(f"before_{command.__class__.__name__}")
                result = await next_handler(command)
                execution_log.append(f"after_{command.__class__.__name__}")
                return result
        
        bus.add_middleware(LoggingMiddleware())
        
        @bus.handler(CreateUserCommand)
        async def handler(cmd: CreateUserCommand):
            execution_log.append("handler")
            return {"username": cmd.username}
        
        cmd = CreateUserCommand(username="john", email="john@example.com")
        await bus.execute(cmd)
        
        assert execution_log == [
            "before_CreateUserCommand",
            "handler",
            "after_CreateUserCommand"
        ]
    
    @pytest.mark.unit
    async def test_multiple_middleware(self, container):
        """Test multiple middleware in chain."""
        bus = CommandBus(container)
        
        execution_order = []
        
        class Middleware1:
            async def process(self, command, next_handler):
                execution_order.append("m1_before")
                result = await next_handler(command)
                execution_order.append("m1_after")
                return result
        
        class Middleware2:
            async def process(self, command, next_handler):
                execution_order.append("m2_before")
                result = await next_handler(command)
                execution_order.append("m2_after")
                return result
        
        bus.add_middleware(Middleware1())
        bus.add_middleware(Middleware2())
        
        @bus.handler("test_command")
        async def handler(cmd):
            execution_order.append("handler")
            return "result"
        
        await bus.execute("test_command", {})
        
        assert execution_order == [
            "m1_before",
            "m2_before",
            "handler",
            "m2_after",
            "m1_after"
        ]
    
    @pytest.mark.unit
    async def test_middleware_can_modify_command(self, container):
        """Test middleware can modify commands."""
        bus = CommandBus(container)
        
        class ModifyingMiddleware:
            async def process(self, command, next_handler):
                # Modify command if it's a dict
                if isinstance(command, dict):
                    command["modified"] = True
                # For dataclass commands, we'd need to replace the instance
                return await next_handler(command)
        
        bus.add_middleware(ModifyingMiddleware())
        
        received_command = None
        
        @bus.handler("dict_command")
        async def handler(cmd):
            nonlocal received_command
            received_command = cmd
            return "handled"
        
        await bus.execute("dict_command", {"original": True})
        
        assert received_command == {"original": True, "modified": True}
    
    @pytest.mark.unit
    async def test_middleware_can_short_circuit(self, container):
        """Test middleware can prevent handler execution."""
        bus = CommandBus(container)
        
        handler_called = False
        
        class AuthMiddleware:
            async def process(self, command, next_handler):
                # Simulate auth check failure
                if getattr(command, "requires_auth", False):
                    return {"error": "Unauthorized"}
                return await next_handler(command)
        
        bus.add_middleware(AuthMiddleware())
        
        @bus.handler("protected_command")
        async def handler(cmd):
            nonlocal handler_called
            handler_called = True
            return "success"
        
        # Command that doesn't require auth
        result = await bus.execute("protected_command", {})
        assert handler_called
        assert result == "success"
        
        # Reset
        handler_called = False
        
        # Command that requires auth
        @dataclass
        class ProtectedCommand:
            requires_auth: bool = True
        
        bus.register(ProtectedCommand, handler)
        
        result = await bus.execute(ProtectedCommand())
        assert not handler_called
        assert result == {"error": "Unauthorized"}
    
    @pytest.mark.unit
    async def test_handler_error_propagation(self, container):
        """Test errors in handlers are propagated."""
        bus = CommandBus(container)
        
        @bus.handler("failing_command")
        async def failing_handler(cmd):
            raise ValueError("Handler error")
        
        with pytest.raises(ValueError) as exc_info:
            await bus.execute("failing_command", {})
        
        assert "Handler error" in str(exc_info.value)
    
    @pytest.mark.unit
    async def test_sync_handler_support(self, container):
        """Test sync handlers are supported."""
        bus = CommandBus(container)
        
        @bus.handler("sync_command")
        def sync_handler(cmd):
            return f"Sync result: {cmd['value']}"
        
        result = await bus.execute("sync_command", {"value": "test"})
        
        assert result == "Sync result: test"
    
    @pytest.mark.unit
    def test_register_duplicate_handler(self, container):
        """Test registering duplicate handlers overwrites."""
        bus = CommandBus(container)
        
        async def handler1(cmd):
            return "handler1"
        
        async def handler2(cmd):
            return "handler2"
        
        bus.register("test_command", handler1)
        bus.register("test_command", handler2)
        
        # Should have overwritten
        assert bus._handlers["test_command"] is handler2
    
    @pytest.mark.unit
    async def test_command_result_transformation(self, container):
        """Test middleware can transform results."""
        bus = CommandBus(container)
        
        class TransformMiddleware:
            async def process(self, command, next_handler):
                result = await next_handler(command)
                # Transform result
                if isinstance(result, dict):
                    result["transformed"] = True
                return result
        
        bus.add_middleware(TransformMiddleware())
        
        @bus.handler("transform_command")
        async def handler(cmd):
            return {"original": True}
        
        result = await bus.execute("transform_command", {})
        
        assert result == {"original": True, "transformed": True}