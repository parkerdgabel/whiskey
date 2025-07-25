"""Tests for named dependencies feature."""

from typing import Annotated

import pytest

from whiskey import Container, factory, provide, singleton
from whiskey.core.decorators import Inject


class Database:
    """Base database interface."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string


class PostgresDB(Database):
    """PostgreSQL implementation."""

    pass


class MySQLDB(Database):
    """MySQL implementation."""

    pass


class Service:
    """Service that uses multiple databases."""

    def __init__(
        self,
        primary_db: Annotated[Database, Inject(name="primary")],
        readonly_db: Annotated[Database, Inject(name="readonly")],
    ):
        self.primary_db = primary_db
        self.readonly_db = readonly_db


class TestNamedDependencies:
    """Test named dependencies functionality."""

    @pytest.fixture
    def container(self):
        """Create a test container."""
        return Container()

    def test_register_and_resolve_named_services(self, container):
        """Test basic named service registration and resolution."""
        # Register different implementations with names
        primary_db = PostgresDB("postgres://primary")
        readonly_db = PostgresDB("postgres://readonly")

        container.register(Database, primary_db, name="primary")
        container.register(Database, readonly_db, name="readonly")

        # Resolve by name
        resolved_primary = container.resolve_sync(Database, name="primary")
        resolved_readonly = container.resolve_sync(Database, name="readonly")

        assert resolved_primary is primary_db
        assert resolved_readonly is readonly_db
        assert resolved_primary is not resolved_readonly

    def test_dict_syntax_with_named_services(self, container):
        """Test dict-like syntax with named services."""
        primary_db = PostgresDB("postgres://primary")
        readonly_db = MySQLDB("mysql://readonly")

        # Register using dict syntax
        container[Database, "primary"] = primary_db
        container[Database, "readonly"] = readonly_db

        # Check containment
        assert (Database, "primary") in container
        assert (Database, "readonly") in container
        assert (Database, "nonexistent") not in container

        # Retrieve using dict syntax
        assert container[Database, "primary"] is primary_db
        assert container[Database, "readonly"] is readonly_db

    def test_named_singleton_services(self, container):
        """Test named services with singleton scope."""
        # Register instances since Database requires connection_string
        container.register_singleton(
            Database, instance=PostgresDB("postgres://primary"), name="primary"
        )
        container.register_singleton(
            Database, instance=MySQLDB("mysql://readonly"), name="readonly"
        )

        # Multiple resolutions should return same instance
        primary1 = container.resolve_sync(Database, name="primary")
        primary2 = container.resolve_sync(Database, name="primary")
        readonly1 = container.resolve_sync(Database, name="readonly")
        readonly2 = container.resolve_sync(Database, name="readonly")

        assert primary1 is primary2
        assert readonly1 is readonly2
        assert primary1 is not readonly1
        assert isinstance(primary1, PostgresDB)
        assert isinstance(readonly1, MySQLDB)

    def test_named_factory_functions(self, container):
        """Test named services with factory functions."""

        def create_primary_db() -> Database:
            return PostgresDB("postgres://primary")

        def create_readonly_db() -> Database:
            return MySQLDB("mysql://readonly")

        container.register_factory(Database, create_primary_db, name="primary")
        container.register_factory(Database, create_readonly_db, name="readonly")

        primary = container.resolve_sync(Database, name="primary")
        readonly = container.resolve_sync(Database, name="readonly")

        assert isinstance(primary, PostgresDB)
        assert isinstance(readonly, MySQLDB)
        assert primary.connection_string == "postgres://primary"
        assert readonly.connection_string == "mysql://readonly"

    @pytest.mark.asyncio
    async def test_inject_named_dependencies(self, container):
        """Test dependency injection with named services."""
        # Register named databases
        container[Database, "primary"] = PostgresDB("postgres://primary")
        container[Database, "readonly"] = MySQLDB("mysql://readonly")

        # Register service that depends on named databases
        container[Service] = Service

        # Resolve service
        service = await container.resolve(Service)

        assert isinstance(service.primary_db, PostgresDB)
        assert isinstance(service.readonly_db, MySQLDB)
        assert service.primary_db.connection_string == "postgres://primary"
        assert service.readonly_db.connection_string == "mysql://readonly"

    def test_named_service_not_found(self, container):
        """Test error when named service is not found."""
        # Register unnamed service
        container[Database] = PostgresDB("postgres://default")

        # Should not fall back to unnamed when looking for named
        with pytest.raises(KeyError, match="Named service Database\\[primary\\] not registered"):
            container.resolve_sync(Database, name="primary")

    def test_delete_named_service(self, container):
        """Test deletion of named services."""
        container[Database, "primary"] = PostgresDB("postgres://primary")
        container[Database, "readonly"] = MySQLDB("mysql://readonly")

        assert (Database, "primary") in container
        assert (Database, "readonly") in container

        # Delete one named service
        del container[Database, "primary"]

        assert (Database, "primary") not in container
        assert (Database, "readonly") in container

    def test_named_decorators(self, container):
        """Test decorators with name parameter."""
        # Set default container for decorators
        from whiskey.core.decorators import set_default_container

        set_default_container(container)

        @provide(name="smtp")
        class SMTPEmailService:
            pass

        @singleton(name="config")
        class AppConfig:
            pass

        @factory(Database, name="test")
        def create_test_db() -> Database:
            return PostgresDB("postgres://test")

        # Resolve named services
        smtp = container.resolve_sync(SMTPEmailService, name="smtp")
        config1 = container.resolve_sync(AppConfig, name="config")
        config2 = container.resolve_sync(AppConfig, name="config")
        test_db = container.resolve_sync(Database, name="test")

        assert isinstance(smtp, SMTPEmailService)
        assert isinstance(config1, AppConfig)
        assert config1 is config2  # Singleton
        assert isinstance(test_db, PostgresDB)

    def test_can_resolve_named(self, container):
        """Test can_resolve with named services."""
        container[Database, "primary"] = PostgresDB("postgres://primary")

        assert container.can_resolve(Database, name="primary")
        assert not container.can_resolve(Database, name="readonly")
        assert not container.can_resolve(Database)  # Unnamed not registered

    @pytest.mark.asyncio
    async def test_named_services_with_scopes(self, container):
        """Test named services work with custom scopes."""
        from whiskey.core.scopes import Scope

        # Register a custom scope
        class RequestScope(Scope):
            pass

        container.register_scope("request", RequestScope)

        # Register named services with scope using factories
        container.register(
            Database,
            factory=lambda: PostgresDB("postgres://primary"),
            name="primary",
            scope="request",
        )
        container.register(
            Database, factory=lambda: MySQLDB("mysql://readonly"), name="readonly", scope="request"
        )

        # Use scope
        async with container.scope("request"):
            primary1 = await container.resolve(Database, name="primary")
            primary2 = await container.resolve(Database, name="primary")
            readonly1 = await container.resolve(Database, name="readonly")

            # Same instance within scope
            assert primary1 is primary2
            assert isinstance(primary1, PostgresDB)
            assert isinstance(readonly1, MySQLDB)

        # New scope creates new instances
        async with container.scope("request"):
            primary3 = await container.resolve(Database, name="primary")
            assert primary3 is not primary1
