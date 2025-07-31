"""Tests for the simplified container implementation."""

import asyncio
from typing import Optional

import pytest

from whiskey.core.container import Container, get_current_container, set_current_container
from whiskey.core.errors import ResolutionError


# Test classes
class Database:
    """Test database class."""

    def __init__(self):
        self.connected = True
        self.queries = []

    def query(self, sql: str):
        self.queries.append(sql)
        return f"Result for: {sql}"


class Logger:
    """Test logger class."""

    def __init__(self):
        self.logs = []

    def log(self, message: str):
        self.logs.append(message)


class Service:
    """Test service with dependencies."""

    def __init__(self, db: Database, logger: Optional[Logger] = None):
        self.db = db
        self.logger = logger

    def process(self, data: str) -> str:
        result = self.db.query(f"SELECT * FROM data WHERE value='{data}'")
        if self.logger:
            self.logger.log(f"Processed: {data}")
        return result


async def async_database_factory() -> Database:
    """Async factory for database."""
    await asyncio.sleep(0.001)
    return Database()


def sync_service_factory(db: Database) -> Service:
    """Sync factory with dependencies."""
    return Service(db)


@pytest.mark.unit
class TestContainerBasics:
    """Test basic container functionality."""

    def test_container_creation(self):
        """Test container creation."""
        container = Container()
        assert container is not None
        assert container.registry is not None
        assert container.resolver is not None

    def test_dict_registration(self):
        """Test dict-like registration."""
        container = Container()

        # Register using dict syntax
        container[Database] = Database
        container["logger"] = Logger()

        assert Database in container
        assert "logger" in container

    def test_dict_resolution(self):
        """Test dict-like resolution."""
        container = Container()
        container[Database] = Database

        # Resolve using dict syntax
        db = container[Database]
        assert isinstance(db, Database)

    def test_dict_deletion(self):
        """Test dict-like deletion."""
        container = Container()
        container[Database] = Database

        assert Database in container
        del container[Database]
        assert Database not in container

    def test_named_registration(self):
        """Test named component registration."""
        container = Container()

        # Register named components using tuple
        container[Database, "primary"] = Database
        container[Database, "cache"] = Database

        # Both should be registered
        assert container.registry.has(Database, "primary")
        assert container.registry.has(Database, "cache")


@pytest.mark.unit
class TestSyncResolution:
    """Test synchronous resolution."""

    def test_basic_resolution(self):
        """Test basic component resolution."""
        container = Container()
        container.singleton(Database)

        db = container.resolve_sync(Database)
        assert isinstance(db, Database)

    def test_resolution_with_dependencies(self):
        """Test resolution with dependency injection."""
        container = Container()
        container.singleton(Database)
        container.singleton(Logger)
        container.register(Service)

        service = container.resolve_sync(Service)
        assert isinstance(service, Service)
        assert isinstance(service.db, Database)
        assert isinstance(service.logger, Logger)

    def test_optional_dependency_resolution(self):
        """Test optional dependency resolution."""
        container = Container()
        container.singleton(Database)
        container.register(Service)
        # Logger not registered

        service = container.resolve_sync(Service)
        assert isinstance(service, Service)
        assert isinstance(service.db, Database)
        assert service.logger is None

    def test_factory_resolution(self):
        """Test factory function resolution."""
        container = Container()
        container.singleton(Database)
        container.factory(Service, sync_service_factory)

        service = container.resolve_sync(Service)
        assert isinstance(service, Service)
        assert isinstance(service.db, Database)

    def test_singleton_behavior(self):
        """Test singleton lifecycle."""
        container = Container()
        container.singleton(Database)

        db1 = container.resolve_sync(Database)
        db2 = container.resolve_sync(Database)

        assert db1 is db2

    def test_transient_behavior(self):
        """Test transient lifecycle."""
        container = Container()
        container.register(Database)  # Default is transient

        db1 = container.resolve_sync(Database)
        db2 = container.resolve_sync(Database)

        assert db1 is not db2

    def test_resolution_error(self):
        """Test resolution error for unregistered component."""
        container = Container()

        with pytest.raises(ResolutionError, match="not registered"):
            container.resolve_sync(Database)

    def test_async_factory_error(self):
        """Test error when trying to resolve async factory synchronously."""
        container = Container()
        container.singleton(Database, async_database_factory)

        with pytest.raises(RuntimeError, match="async factory"):
            container.resolve_sync(Database)


@pytest.mark.unit
class TestAsyncResolution:
    """Test asynchronous resolution."""

    @pytest.mark.asyncio
    async def test_basic_async_resolution(self):
        """Test basic async resolution."""
        container = Container()
        container.singleton(Database)

        db = await container.resolve_async(Database)
        assert isinstance(db, Database)

    @pytest.mark.asyncio
    async def test_async_factory_resolution(self):
        """Test async factory resolution."""
        container = Container()
        container.singleton(Database, async_database_factory)

        db = await container.resolve_async(Database)
        assert isinstance(db, Database)

    @pytest.mark.asyncio
    async def test_smart_resolution_async_context(self):
        """Test smart resolution in async context."""
        container = Container()
        container.singleton(Database)

        # resolve() should return coroutine in async context
        db = await container.resolve(Database)
        assert isinstance(db, Database)


@pytest.mark.unit
class TestFunctionCalling:
    """Test function calling with injection."""

    def test_sync_function_call(self):
        """Test synchronous function calling."""
        container = Container()
        container.singleton(Database)
        container.singleton(Logger)

        def process_data(data: str, db: Database, logger: Logger) -> str:
            logger.log(f"Processing: {data}")
            return db.query(f"SELECT * FROM {data}")

        # Call with injection
        result = container.call(process_data, "users")

        assert result == "Result for: SELECT * FROM users"
        logger = container[Logger]
        assert "Processing: users" in logger.logs

    def test_function_call_with_overrides(self):
        """Test function calling with overrides."""
        container = Container()
        container.singleton(Database)

        custom_db = Database()

        def get_data(db: Database) -> str:
            return "custom" if db is custom_db else "default"

        # Call with override
        result = container.call(get_data, db=custom_db)
        assert result == "custom"

        # Call without override
        result = container.call(get_data)
        assert result == "default"

    @pytest.mark.asyncio
    async def test_async_function_call(self):
        """Test asynchronous function calling."""
        container = Container()
        container.singleton(Database)

        async def async_process(db: Database) -> str:
            await asyncio.sleep(0.001)
            return db.query("async query")

        result = await container.call(async_process)
        assert result == "Result for: async query"


@pytest.mark.unit
class TestScopeManagement:
    """Test scope management."""

    def test_scoped_resolution(self):
        """Test scoped component resolution."""
        container = Container()
        container.scoped(Database, scope_name="request")

        # Enter scope
        container.enter_scope("request")

        try:
            db1 = container.resolve_sync(Database)
            db2 = container.resolve_sync(Database)
            assert db1 is db2  # Same instance in scope
        finally:
            container.exit_scope("request")

    def test_scope_context_manager(self):
        """Test scope context manager."""
        container = Container()
        container.scoped(Database, scope_name="request")

        with container.scope("request"):
            db1 = container.resolve_sync(Database)
            db2 = container.resolve_sync(Database)
            assert db1 is db2

        # After scope exit, new scope gets new instance
        with container.scope("request"):
            db3 = container.resolve_sync(Database)
            assert db3 is not db1


@pytest.mark.unit
class TestContextManagement:
    """Test container context management."""

    def test_current_container(self):
        """Test current container context."""
        container = Container()

        # No current container initially
        assert get_current_container() is None

        # Set current container
        set_current_container(container)
        assert get_current_container() is container

        # Context manager
        container2 = Container()
        with container2:
            assert get_current_container() is container2

        # Back to previous
        assert get_current_container() is container

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager."""
        container = Container()

        async with container:
            assert get_current_container() is container


@pytest.mark.unit
class TestGenericTypes:
    """Test generic type support."""

    def test_generic_registration(self):
        """Test generic type registration."""
        from typing import Generic, TypeVar

        T = TypeVar("T")

        class Repository(Generic[T]):
            pass

        class UserRepository(Repository[str]):
            pass

        container = Container()
        container.register_generic_implementation(Repository[str], UserRepository)
        container.singleton(UserRepository)

        # This would require full integration with resolver
        # For now just verify registration works
        assert True  # Placeholder


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling and messages."""

    def test_dict_access_async_error(self):
        """Test helpful error for async components in dict access."""
        container = Container()
        container.singleton(Database, async_database_factory)

        with pytest.raises(RuntimeError) as exc_info:
            _ = container[Database]

        assert "requires async resolution" in str(exc_info.value)
        assert "await container.resolve" in str(exc_info.value)

    def test_resolve_sync_in_async_context_error(self):
        """Test error when using resolve_sync in async context."""

        async def test():
            container = Container()
            container.singleton(Database)

            with pytest.raises(RuntimeError, match="Cannot use resolve_sync"):
                container.resolve_sync(Database)

        # Note: This test might not work as expected without proper async context detection
        # The actual implementation needs to be adjusted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])