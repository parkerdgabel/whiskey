"""Test cases demonstrating current factory decorator syntax issues.

This test suite identifies and validates fixes for Phase 2.2: Redesign factory decorator syntax.

Current Issues:
1. Confusing parameter requirements - @factory requires a key but syntax is unclear
2. Inconsistent with other decorators (@component, @singleton don't require explicit keys)
3. Multiple confusing calling patterns
4. Error messages don't help developers understand correct usage
5. No clear way to register factories without explicit keys
6. Type inference is not utilized

Goals for redesign:
1. Make factory decorator consistent with other decorators
2. Utilize return type hints for automatic key inference
3. Provide clear, helpful error messages
4. Support multiple intuitive calling patterns
5. Better integration with IDE and type checkers
"""

import pytest
from whiskey.core import Container
from whiskey.core.decorators import factory, get_app
from whiskey.core.registry import Scope


class Database:
    def __init__(self, connection_string: str = "localhost"):
        self.connection_string = connection_string


class UserService:
    def __init__(self, db: Database):
        self.db = db


@pytest.mark.unit
class TestCurrentFactoryDecoratorIssues:
    """Test current issues with factory decorator syntax."""
    
    def test_confusing_key_requirement(self):
        """Factory requires explicit key unlike other decorators."""
        
        # This fails - confusing because @component doesn't need explicit key
        with pytest.raises(ValueError, match="Factory decorator requires a key"):
            @factory
            def create_database():
                return Database()
    
    def test_inconsistent_with_other_decorators(self):
        """Factory decorator is inconsistent with @component/@singleton."""
        
        # @component automatically uses the class as key
        from whiskey.core.decorators import component
        
        @component
        class AutomaticKeyComponent:
            pass
        
        # But @factory requires explicit key even when return type is clear
        @factory(Database)  # Why can't this be inferred from return type?
        def create_database() -> Database:
            return Database()
        
        app = get_app()
        assert AutomaticKeyComponent in app.container
        assert Database in app.container
    
    def test_multiple_confusing_calling_patterns(self):
        """Multiple ways to use @factory are confusing."""
        
        # Pattern 1: @factory(Class)
        @factory(Database)
        def create_db1() -> Database:
            return Database("pattern1")
        
        # Pattern 2: @factory(key=Class)  
        @factory(key=UserService)
        def create_user1() -> UserService:
            return UserService(Database())
        
        # Pattern 3: @factory(key="string")
        @factory(key="db_factory")
        def create_db2() -> Database:
            return Database("pattern3")
        
        # All work but syntax is inconsistent and confusing
        app = get_app()
        assert Database in app.container
        assert UserService in app.container
        assert "db_factory" in app.container
    
    def test_type_inference_not_utilized(self):
        """Factory decorator doesn't use return type hints for key inference."""
        
        # This should work - return type is clear!
        # But currently fails because key is required
        with pytest.raises(ValueError, match="Factory decorator requires a key"):
            @factory
            def create_user_service() -> UserService:
                return UserService(Database())
    
    def test_unhelpful_error_messages(self):
        """Error messages don't guide developers to correct usage."""
        
        try:
            @factory
            def some_factory():
                return "something"
        except ValueError as e:
            # Error message doesn't suggest solutions
            assert "Factory decorator requires a key" in str(e)
            # Should suggest: "Add return type hint or specify key parameter"
    
    def test_no_clear_best_practice(self):
        """No clear guidance on best practice usage."""
        
        # All these patterns work but which should developers use?
        
        @factory(Database)
        def method1() -> Database:
            return Database("method1")
        
        @factory(key=Database)  # Redundant but valid
        def method2() -> Database:
            return Database("method2")
        
        # Ideally, the cleanest syntax should be:
        # @factory
        # def create_database() -> Database:
        #     return Database()


@pytest.mark.unit
class TestDesiredFactoryDecoratorAPI:
    """Test the desired improved factory decorator API."""
    
    def test_automatic_key_inference(self):
        """Factory should infer key from return type hint."""
        
        # This should work - return type is clear
        # @factory  # Should infer Database from return type
        # def create_database() -> Database:
        #     return Database("auto-inferred")
        
        # For now, this is what we want to achieve
        pass
    
    def test_explicit_key_when_needed(self):
        """Factory should support explicit key when return type is not sufficient."""
        
        # When multiple factories return same type
        # @factory(key="primary_db")
        # def create_primary_db() -> Database:
        #     return Database("primary")
        
        # @factory(key="backup_db")  
        # def create_backup_db() -> Database:
        #     return Database("backup")
        
        pass
    
    def test_consistent_with_other_decorators(self):
        """Factory should follow same patterns as @component/@singleton."""
        
        # Should work like:
        # @factory  # <- Clean, like @component
        # def create_service() -> UserService:
        #     return UserService(Database())
        
        # @factory(scope=Scope.SINGLETON)  # <- Explicit options like @component
        # def create_cache() -> Database:
        #     return Database("cached")
        
        pass
    
    def test_helpful_error_messages(self):
        """Error messages should guide developers to correct usage."""
        
        # Should provide helpful guidance like:
        # "Cannot infer factory key from function 'create_something' without return type hint. 
        #  Add return type hint or specify key parameter: @factory(key=YourType)"
        
        pass
    
    def test_ide_and_type_checker_support(self):
        """Factory decorator should work well with IDEs and type checkers."""
        
        # Return type hint should be preserved
        # IDE should understand that create_service() returns UserService
        # Type checker should validate return type matches declared type
        
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])