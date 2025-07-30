"""Test demonstrating improvements to the factory decorator in Phase 2.2."""

import pytest
from whiskey.core.decorators import factory, get_app
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
class TestFactoryDecoratorImprovements:
    """Test the improved factory decorator with automatic key inference."""
    
    def test_automatic_key_inference_new_capability(self):
        """NEW: Factory can now infer key from return type hint."""
        
        # This is the new capability - previously this would fail
        @factory
        def create_database() -> Database:
            return Database("auto-inferred")
        
        app = get_app()
        
        # Should be registered and resolvable
        assert Database in app.container
        db = app.resolve(Database)
        assert isinstance(db, Database)
        assert db.connection_string == "auto-inferred"
    
    def test_backward_compatibility_maintained(self):
        """All existing usage patterns still work."""
        
        # Pattern 1: Explicit positional key (existing)
        @factory(UserService)
        def create_user_service() -> UserService:
            return UserService(Database())
        
        # Pattern 2: Explicit key parameter (existing)
        @factory(key=Cache)
        def create_cache():
            return Cache()
        
        # Pattern 3: String key (existing)
        @factory(key="custom_service")
        def create_custom():
            return "custom_service_instance"
        
        app = get_app()
        
        # All should work as before
        assert UserService in app.container
        assert Cache in app.container
        assert "custom_service" in app.container
        
        user_service = app.resolve(UserService)
        cache = app.resolve(Cache)
        custom = app.resolve("custom_service")
        
        assert isinstance(user_service, UserService)
        assert isinstance(cache, Cache)
        assert custom == "custom_service_instance"
    
    def test_improved_error_messages(self):
        """Error messages are now much more helpful."""
        
        # Old error would be: "Factory decorator requires a key"
        # New error provides specific guidance
        with pytest.raises(ValueError) as exc_info:
            @factory
            def create_something():
                return "something"
        
        error_msg = str(exc_info.value)
        
        # Should contain helpful guidance
        assert "Cannot determine factory key" in error_msg
        assert "Add a return type hint" in error_msg
        assert "Specify key explicitly" in error_msg
        assert "create_something" in error_msg
        assert "@factory(key=YourType)" in error_msg
    
    def test_consistent_with_other_decorators(self):
        """Factory decorator now follows same patterns as @component/@singleton."""
        
        # Clean, consistent syntax like @component
        @factory
        def create_database() -> Database:
            return Database("consistent")
        
        # With options like @component
        @factory(scope=Scope.SINGLETON)
        def create_singleton_cache() -> Cache:
            return Cache()
        
        app = get_app()
        
        # Both should work
        db = app.resolve(Database)
        cache1 = app.resolve(Cache)
        cache2 = app.resolve(Cache)
        
        assert db.connection_string == "consistent"
        assert cache1 is cache2  # Should be singleton
    
    def test_ide_and_type_checker_friendly(self):
        """Factory decorator preserves type information."""
        
        @factory
        def create_user_service() -> UserService:
            return UserService(Database())
        
        # Function should retain its type information
        # (This is more about IDE support, but we can test basic preservation)
        assert create_user_service.__name__ == "create_user_service"
        assert hasattr(create_user_service, '__annotations__')
        
        # Should be able to call the function directly too
        direct_result = create_user_service()
        assert isinstance(direct_result, UserService)
    
    def test_multiple_factories_same_type_with_names(self):
        """Can register multiple factories for same type using names."""
        
        @factory(name="primary")
        def create_primary_db() -> Database:
            return Database("primary")
        
        @factory(name="backup")
        def create_backup_db() -> Database:
            return Database("backup")
        
        app = get_app()
        
        # Should be able to resolve by name
        primary = app.resolve(Database, name="primary")
        backup = app.resolve(Database, name="backup")
        
        assert primary.connection_string == "primary"
        assert backup.connection_string == "backup"
    
    def test_complex_factory_with_dependencies(self):
        """Factory with dependency injection and custom configuration."""
        
        # Register dependency first
        @factory
        def create_database() -> Database:
            return Database("injected")
        
        # Factory with dependency injection
        @factory(scope=Scope.SINGLETON, tags={"service", "user"})
        def create_user_service(db: Database) -> UserService:
            return UserService(db)
        
        app = get_app()
        
        # Should work with dependency injection
        service1 = app.resolve(UserService)
        service2 = app.resolve(UserService)
        
        assert isinstance(service1, UserService)
        assert service1 is service2  # Singleton
        assert service1.db.connection_string == "injected"


@pytest.mark.unit
class TestFactoryDecoratorMigrationScenarios:
    """Test migration from old to new factory decorator patterns."""
    
    def test_migration_add_return_type_hints(self):
        """Developers can migrate by adding return type hints."""
        
        # OLD PATTERN (still works)
        @factory(key=Database)
        def create_db_old():
            return Database("old_pattern")
        
        # NEW PATTERN (preferred)
        @factory
        def create_db_new() -> Database:
            return Database("new_pattern")
        
        app = get_app()
        
        # Both work, but new pattern is cleaner
        # Note: We registered both under Database, so one will override the other
        # In real code, you'd use names or different types
        db = app.resolve(Database)
        assert isinstance(db, Database)
    
    def test_migration_guidance_in_errors(self):
        """Error messages guide developers through migration."""
        
        try:
            @factory
            def create_service():
                return "service"
        except ValueError as e:
            error_msg = str(e)
            
            # Should provide clear migration path
            assert "Add a return type hint" in error_msg
            assert "def create_service() -> YourType:" in error_msg
            assert "@factory(key=YourType)" in error_msg
            
            # Shows both old and new approaches
            assert "Specify key explicitly" in error_msg
            assert "Use positional key syntax" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])