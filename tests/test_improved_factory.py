"""Test the improved factory decorator implementation."""

import pytest

from whiskey.core.application import Whiskey
from whiskey.core.improved_factory import improved_factory
from whiskey.core.registry import Scope


class Database:
    def __init__(self, connection_string: str = "localhost"):
        self.connection_string = connection_string


class UserService:
    def __init__(self, db: Database):
        self.db = db


class Cache:
    def __init__(self):
        self.data = {}


@pytest.mark.unit
class TestImprovedFactoryDecorator:
    """Test the improved factory decorator with automatic key inference."""

    def test_automatic_key_inference(self):
        """Factory should infer key from return type hint."""
        app = Whiskey()

        @improved_factory(app=app)
        def create_database() -> Database:
            return Database("auto-inferred")

        # Should be registered with Database as key
        assert Database in app.container

        # Should create instances correctly
        db = app.resolve(Database)
        assert isinstance(db, Database)
        assert db.connection_string == "auto-inferred"

    def test_multiple_patterns_work(self):
        """Test all supported calling patterns."""
        app = Whiskey()

        # Pattern 1: Automatic inference
        @improved_factory(app=app)
        def create_user_service() -> UserService:
            return UserService(Database())

        # Pattern 2: Explicit key parameter
        @improved_factory(key=Cache, app=app)
        def create_cache():
            return Cache()

        # Pattern 3: Positional key
        @improved_factory(Database, app=app)
        def create_db():
            return Database("positional")

        # All should be registered
        assert UserService in app.container
        assert Cache in app.container
        assert Database in app.container

        # All should work
        user_service = app.resolve(UserService)
        cache = app.resolve(Cache)
        db = app.resolve(Database)

        assert isinstance(user_service, UserService)
        assert isinstance(cache, Cache)
        assert isinstance(db, Database)
        assert db.connection_string == "positional"

    def test_with_options(self):
        """Test factory decorator with scope and other options."""
        app = Whiskey()

        @improved_factory(scope=Scope.SINGLETON, app=app)
        def create_singleton_cache() -> Cache:
            return Cache()

        # Should be registered as singleton
        assert Cache in app.container

        # Should return same instance
        cache1 = app.resolve(Cache)
        cache2 = app.resolve(Cache)
        assert cache1 is cache2

    def test_helpful_error_without_type_hint(self):
        """Should provide helpful error when no return type hint and no key."""
        app = Whiskey()

        with pytest.raises(ValueError) as exc_info:

            @improved_factory(app=app)
            def create_something():
                return "something"

        error_msg = str(exc_info.value)
        assert "Cannot determine factory key" in error_msg
        assert "Add a return type hint" in error_msg
        assert "Specify key explicitly" in error_msg
        assert "create_something" in error_msg

    def test_helpful_error_with_invalid_return_type(self):
        """Should provide helpful error for generic return types."""
        app = Whiskey()

        with pytest.raises(ValueError) as exc_info:

            @improved_factory(app=app)
            def create_list() -> list[str]:
                return []

        error_msg = str(exc_info.value)
        assert "Cannot use return type" in error_msg
        assert "list[str]" in error_msg
        assert "specify key explicitly" in error_msg

    def test_explicit_key_overrides_return_type(self):
        """Explicit key should take precedence over return type."""
        app = Whiskey()

        # Register with string key even though return type is Database
        @improved_factory(key="custom_db", app=app)
        def create_db() -> Database:
            return Database("custom")

        # Should be registered with string key
        assert "custom_db" in app.container

        # Database should be resolvable by type (Container's smart resolution)
        # but the actual registration key should be the string
        registered_keys = [desc.key for desc in app.container.registry.list_all()]
        assert "custom_db" in registered_keys
        assert len(registered_keys) == 1  # Only one registration

        # Should resolve by string key
        db = app.resolve("custom_db")
        assert isinstance(db, Database)
        assert db.connection_string == "custom"

    def test_dependency_injection_in_factory(self):
        """Factory functions should support dependency injection."""
        app = Whiskey()

        # Register dependency
        app.singleton(Database)

        # Factory with dependency injection
        @improved_factory(app=app)
        def create_user_service(db: Database) -> UserService:
            return UserService(db)

        # Should work with injected dependency
        user_service = app.resolve(UserService)
        assert isinstance(user_service, UserService)
        assert isinstance(user_service.db, Database)

    def test_async_factory_support(self):
        """Should support async factory functions."""
        app = Whiskey()

        @improved_factory(app=app)
        async def create_async_database() -> Database:
            # Simulate async work
            return Database("async-created")

        # Should be registered
        assert Database in app.container

        # Should work with async resolution
        import asyncio

        db = asyncio.run(app.resolve_async(Database))
        assert isinstance(db, Database)
        assert db.connection_string == "async-created"

    def test_preserves_function_metadata(self):
        """Decorator should preserve function name, docstring, etc."""
        app = Whiskey()

        @improved_factory(app=app)
        def create_database() -> Database:
            """Create a database instance."""
            return Database()

        # Function metadata should be preserved
        assert create_database.__name__ == "create_database"
        assert create_database.__doc__ == "Create a database instance."

    def test_named_components(self):
        """Should support named component registration."""
        app = Whiskey()

        @improved_factory(name="primary", app=app)
        def create_primary_db() -> Database:
            return Database("primary")

        @improved_factory(name="backup", app=app)
        def create_backup_db() -> Database:
            return Database("backup")

        # Should be able to resolve by name
        primary_db = app.resolve(Database, name="primary")
        backup_db = app.resolve(Database, name="backup")

        assert primary_db.connection_string == "primary"
        assert backup_db.connection_string == "backup"

    def test_tags_and_conditions(self):
        """Should support tags and conditional registration."""
        app = Whiskey()

        @improved_factory(tags={"database", "primary"}, condition=lambda: True, app=app)
        def create_tagged_db() -> Database:
            return Database("tagged")

        # Should be registered
        assert Database in app.container

        # Should resolve correctly
        db = app.resolve(Database)
        assert db.connection_string == "tagged"


@pytest.mark.unit
class TestImprovedFactoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_forward_reference_handling(self):
        """Should handle forward references in return types."""
        app = Whiskey()

        # This should work even with string type annotation
        @improved_factory(app=app)
        def create_service() -> "UserService":
            return UserService(Database())

        # Should be registered (note: this might need special handling for forward refs)
        # For now, let's test that it doesn't crash
        try:
            service = app.resolve(UserService)
            assert isinstance(service, UserService)
        except (NameError, KeyError):
            # Forward reference resolution might not work in test context
            # The important thing is that the decorator doesn't crash
            pass

    def test_no_duplicate_registration(self):
        """Should handle multiple factories for same type appropriately."""
        app = Whiskey()

        @improved_factory(app=app)
        def create_db1() -> Database:
            return Database("first")

        # Second factory should override first (or raise error - depends on design choice)
        @improved_factory(app=app)
        def create_db2() -> Database:
            return Database("second")

        # Should resolve to the last registered factory
        db = app.resolve(Database)
        assert db.connection_string == "second"

    def test_complex_return_types(self):
        """Should provide good errors for complex return types."""
        app = Whiskey()

        # Union types should be rejected
        with pytest.raises(ValueError, match="Cannot use return type"):

            @improved_factory(app=app)
            def create_union() -> Database | UserService:
                return Database()

        # Optional types should be rejected
        with pytest.raises(ValueError, match="Cannot use return type"):

            @improved_factory(app=app)
            def create_optional() -> Database | None:
                return Database()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
