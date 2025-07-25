"""Extended tests for the Application class decorators and functionality.

This file contains additional comprehensive tests for the Application class.
"""

import asyncio
import os
import pytest
from typing import Any, Callable
from unittest.mock import Mock, patch

from whiskey.core.application import (
    Application, 
    ConditionalDecoratorHelper,
    set_current_app,
    get_current_app,
    create_default_app
)
from whiskey.core.container import Container
from whiskey.core.registry import Scope
from whiskey.core.errors import ConfigurationError


# Test services for testing
class TestService:
    def __init__(self):
        self.value = "test"


class DatabaseService:
    def __init__(self, connection_string: str = "default"):
        self.connection_string = connection_string


class CacheService:
    def __init__(self):
        self.cache = {}


def create_test_service():
    """Factory function for testing."""
    return TestService()


class TestApplicationServiceDecorator:
    """Test the @app.service decorator."""
    
    def test_service_decorator_without_parentheses(self):
        """Test @app.service without parentheses."""
        app = Application()
        
        @app.service
        class TestServiceClass:
            def __init__(self):
                self.value = "test"
        
        # Service should be registered with default settings
        assert TestServiceClass in app.container
        
        # Decorator should return the class
        assert TestServiceClass is not None
        
        service = app.container.resolve_sync(TestServiceClass)
        assert service.value == "test"
    
    def test_service_decorator_with_parentheses(self):
        """Test @app.service() with parentheses and options."""
        app = Application()
        
        @app.service(name="primary", scope=Scope.SINGLETON, tags={"core"})
        class DatabaseServiceClass:
            def __init__(self):
                self.connected = True
        
        assert DatabaseServiceClass in app.container
        
        # Should be singleton
        service1 = app.container.resolve_sync(DatabaseServiceClass, name="primary")
        service2 = app.container.resolve_sync(DatabaseServiceClass, name="primary")
        assert service1 is service2
    
    def test_service_decorator_with_key(self):
        """Test @app.service with custom key."""
        app = Application()
        
        @app.service(key="my_service")
        class ServiceWithCustomKey:
            pass
        
        assert "my_service" in app.container
        assert ServiceWithCustomKey not in app.container  # Should not be registered under class
    
    def test_service_decorator_with_condition(self):
        """Test @app.service with condition."""
        app = Application()
        condition_called = False
        
        def test_condition():
            nonlocal condition_called
            condition_called = True
            return True
        
        @app.service(condition=test_condition)
        class ConditionalService:
            pass
        
        # Resolve should trigger condition check
        service = app.container.resolve_sync(ConditionalService)
        assert condition_called
    
    def test_service_decorator_lazy(self):
        """Test @app.service with lazy resolution."""
        app = Application()
        
        @app.service(lazy=True)
        class LazyService:
            pass
        
        # Should be registered
        assert LazyService in app.container


class TestApplicationSingletonDecorator:
    """Test the @app.singleton decorator."""
    
    def test_singleton_decorator_without_parentheses(self):
        """Test @app.singleton without parentheses."""
        app = Application()
        
        @app.singleton
        class SingletonService:
            def __init__(self):
                self.id = id(self)
        
        # Should be registered as singleton
        service1 = app.container.resolve_sync(SingletonService)
        service2 = app.container.resolve_sync(SingletonService)
        
        assert service1 is service2
        assert service1.id == service2.id
    
    def test_singleton_decorator_with_options(self):
        """Test @app.singleton with options."""
        app = Application()
        
        @app.singleton(name="cache", tags={"infrastructure"})
        class CacheServiceClass:
            pass
        
        assert CacheServiceClass in app.container
        
        # Should still be singleton
        service1 = app.container.resolve_sync(CacheServiceClass, name="cache")
        service2 = app.container.resolve_sync(CacheServiceClass, name="cache")
        assert service1 is service2


class TestApplicationScopedDecorator:
    """Test the @app.scoped decorator."""
    
    def test_scoped_decorator_default(self):
        """Test @app.scoped with default scope name."""
        app = Application()
        
        @app.scoped
        class ScopedService:
            pass
        
        # Should be registered as scoped
        assert ScopedService in app.container
    
    def test_scoped_decorator_with_scope_name(self):
        """Test @app.scoped with custom scope name."""
        app = Application()
        
        @app.scoped(scope_name="request")
        class RequestScopedService:
            pass
        
        assert RequestScopedService in app.container


class TestApplicationFactoryDecorator:
    """Test the @app.factory decorator."""
    
    def test_factory_decorator_with_key(self):
        """Test @app.factory with required key."""
        app = Application()
        
        @app.factory(key="test_service")
        def create_test_service():
            return TestService()
        
        assert "test_service" in app.container
        
        service = app.container.resolve_sync("test_service")
        assert isinstance(service, TestService)
        assert service.value == "test"
    
    def test_factory_decorator_without_key_raises_error(self):
        """Test @app.factory without key raises ConfigurationError."""
        app = Application()
        
        with pytest.raises(ConfigurationError, match="Factory decorator requires 'key' parameter"):
            @app.factory
            def bad_factory():
                return TestService()
    
    def test_factory_decorator_with_options(self):
        """Test @app.factory with various options."""
        app = Application()
        
        @app.factory(key="db_service", scope=Scope.SINGLETON, name="primary")
        def create_database():
            return DatabaseService("production")
        
        assert "db_service" in app.container
        
        # Should be singleton
        service1 = app.container.resolve_sync("db_service", name="primary")
        service2 = app.container.resolve_sync("db_service", name="primary")
        assert service1 is service2
        assert service1.connection_string == "production"


class TestApplicationComponentDecorator:
    """Test the @app.component decorator."""
    
    def test_component_decorator_with_class(self):
        """Test @app.component with class (should register as service)."""
        app = Application()
        
        @app.component
        class ComponentService:
            pass
        
        assert ComponentService in app.container
        service = app.container.resolve_sync(ComponentService)
        assert isinstance(service, ComponentService)
    
    def test_component_decorator_with_function(self):
        """Test @app.component with function (should register as factory)."""
        app = Application()
        
        @app.component(key="component_service")
        def create_component():
            return TestService()
        
        assert "component_service" in app.container
        service = app.container.resolve_sync("component_service")
        assert isinstance(service, TestService)
    
    def test_component_decorator_function_without_key_raises_error(self):
        """Test @app.component with function but no key raises error."""
        app = Application()
        
        with pytest.raises(ConfigurationError, match="Factory registration requires 'key' parameter"):
            @app.component
            def bad_component():
                return TestService()
    
    def test_component_decorator_with_invalid_target(self):
        """Test @app.component with invalid target raises error."""
        app = Application()
        
        with pytest.raises(ConfigurationError, match="Cannot register .* as component"):
            app.component("not_a_class_or_function")
    
    def test_component_decorator_with_options(self):
        """Test @app.component with various options."""
        app = Application()
        
        @app.component(scope=Scope.SINGLETON, tags={"core"})
        class ComponentWithOptions:
            pass
        
        assert ComponentWithOptions in app.container
        
        # Should be singleton
        service1 = app.container.resolve_sync(ComponentWithOptions)
        service2 = app.container.resolve_sync(ComponentWithOptions)
        assert service1 is service2


class TestApplicationConditionalDecorators:
    """Test conditional decorators like @app.when_env."""
    
    def test_when_env_returns_helper(self):
        """Test when_env returns ConditionalDecoratorHelper."""
        app = Application()
        
        helper = app.when_env("TEST_MODE", "active")
        assert isinstance(helper, ConditionalDecoratorHelper)
        assert helper.app is app
        assert helper.condition is not None
    
    def test_when_env_with_value(self):
        """Test when_env condition with specific value."""
        app = Application()
        
        with patch.dict(os.environ, {"TEST_MODE": "active"}):
            helper = app.when_env("TEST_MODE", "active")
            assert helper.condition( in app.container is True
        
        with patch.dict(os.environ, {"TEST_MODE": "inactive"}):
            helper = app.when_env("TEST_MODE", "active")
            assert helper.condition( in app.container is False
    
    def test_when_env_existence_only(self):
        """Test when_env condition checking only existence."""
        app = Application()
        
        with patch.dict(os.environ, {"DEBUG": "any_value"}):
            helper = app.when_env("DEBUG")
            assert helper.condition( in app.container is True
        
        with patch.dict(os.environ, {}, clear=True):
            helper = app.when_env("DEBUG")
            assert helper.condition( in app.container is False
    
    def test_when_debug(self):
        """Test when_debug conditional decorator."""
        app = Application()
        
        with patch.dict(os.environ, {"DEBUG": "true"}):
            helper = app.when_debug()
            assert helper.condition( in app.container is True
        
        with patch.dict(os.environ, {"DEBUG": "false"}):
            helper = app.when_debug()
            assert helper.condition( in app.container is False
        
        # Test various truthy values
        for value in ["1", "yes", "TRUE"]:
            with patch.dict(os.environ, {"DEBUG": value}):
                helper = app.when_debug()
                assert helper.condition( in app.container is True
    
    def test_when_production(self):
        """Test when_production conditional decorator."""
        app = Application()
        
        with patch.dict(os.environ, {"ENV": "production"}):
            helper = app.when_production()
            assert helper.condition( in app.container is True
        
        with patch.dict(os.environ, {"ENV": "prod"}):
            helper = app.when_production()
            assert helper.condition( in app.container is True
        
        with patch.dict(os.environ, {"ENV": "development"}):
            helper = app.when_production()
            assert helper.condition( in app.container is False


class TestConditionalDecoratorHelper:
    """Test the ConditionalDecoratorHelper class."""
    
    def test_conditional_service(self):
        """Test conditional service registration."""
        app = Application()
        condition = lambda: True
        helper = ConditionalDecoratorHelper(app, condition)
        
        @helper.service
        class ConditionalService:
            pass
        
        assert ConditionalService in app.container
    
    def test_conditional_singleton(self):
        """Test conditional singleton registration."""
        app = Application()
        condition = lambda: True
        helper = ConditionalDecoratorHelper(app, condition)
        
        @helper.singleton
        class ConditionalSingleton:
            pass
        
        assert ConditionalSingleton in app.container
        
        # Should be singleton
        service1 = app.container.resolve_sync(ConditionalSingleton)
        service2 = app.container.resolve_sync(ConditionalSingleton)
        assert service1 is service2
    
    def test_conditional_factory(self):
        """Test conditional factory registration."""
        app = Application()
        condition = lambda: True
        helper = ConditionalDecoratorHelper(app, condition)
        
        @helper.factory(key="conditional_factory")
        def create_conditional():
            return TestService()
        
        assert "conditional_factory" in app.container
    
    def test_conditional_component(self):
        """Test conditional component registration."""
        app = Application()
        condition = lambda: True
        helper = ConditionalDecoratorHelper(app, condition)
        
        @helper.component
        class ConditionalComponent:
            pass
        
        assert ConditionalComponent in app.container


class TestApplicationFunctionCalling:
    """Test Application function calling methods."""
    
    async def test_call_method(self):
        """Test app.call() method."""
        app = Application()
        
        # Register a service
        app.container[TestService] = TestService
        
        async def test_func(service: TestService):
            return service.value
        
        result = await app.call(test_func)
        assert result == "test"
    
    def test_call_sync_method(self):
        """Test app.call_sync() method."""
        app = Application()
        
        # Register a service
        app.container[TestService] = TestService
        
        def test_func(service: TestService):
            return service.value
        
        result = app.call_sync(test_func)
        assert result == "test"
    
    async def test_invoke_method(self):
        """Test app.invoke() method."""
        app = Application()
        
        # Register a service
        app.container[TestService] = TestService
        
        async def test_func(service: TestService, override_value: str = "default"):
            return f"{service.value}-{override_value}"
        
        result = await app.invoke(test_func, override_value="custom")
        assert result == "test-custom"
    
    def test_wrap_function_method(self):
        """Test app.wrap_function() method."""
        app = Application()
        
        # Register a service
        app.container[TestService] = TestService
        
        def test_func(service: TestService):
            return service.value
        
        wrapped_func = app.wrap_function(test_func)
        result = wrapped_func()
        assert result == "test"


class TestApplicationConvenience:
    """Test Application convenience methods."""
    
    def test_resolve_sync_method(self):
        """Test app.resolve() method."""
        app = Application()
        app.container[TestService] = TestService
        
        service = app.resolve(TestService)
        assert isinstance(service, TestService)
        assert service.value == "test"
    
    async def test_resolve_async_method(self):
        """Test app.resolve_async() method."""
        app = Application()
        app.container[TestService] = TestService
        
        service = await app.resolve_async(TestService)
        assert isinstance(service, TestService)
        assert service.value == "test"
    
    def test_configure_method(self):
        """Test app.configure() method."""
        app = Application()
        configured = False
        
        def config_func(application):
            nonlocal configured
            configured = True
            assert application is app
            application.container["configured"] = "value"
        
        result = app.configure(config_func)
        
        assert result is app  # Should return self for chaining
        assert configured
        assert app.container.resolve_sync("configured" in app.container == "value"
    
    def test_dict_like_access(self):
        """Test dict-like access to container."""
        app = Application()
        
        # Test __setitem__
        app["test_key"] = "test_value"
        
        # Test __getitem__
        assert app["test_key"] == "test_value"
        
        # Test __contains__
        assert "test_key" in app
        assert "nonexistent_key" not in app


class TestGlobalApplicationManagement:
    """Test global application instance management."""
    
    def test_set_and_get_current_app(self):
        """Test set_current_app and get_current_app."""
        app = Application()
        
        # Initially should be None
        assert get_current_app() is None
        
        # Set current app
        set_current_app(app)
        assert get_current_app() is app
        
        # Set different app
        app2 = Application()
        set_current_app(app2)
        assert get_current_app() is app2
    
    def test_create_default_app(self):
        """Test create_default_app function."""
        app = create_default_app()
        
        assert isinstance(app, Application)
        assert get_current_app() is app


class TestApplicationIntegration:
    """Test Application integration scenarios."""
    
    def test_multiple_decorator_types(self):
        """Test using multiple decorator types together."""
        app = Application()
        
        @app.service
        class RegularService:
            pass
        
        @app.singleton
        class SingletonService:
            pass
        
        @app.factory(key="factory_service")
        def create_factory_service():
            return TestService()
        
        @app.component
        class ComponentService:
            pass
        
        # All should be registered
        assert RegularService in app.container
        assert SingletonService in app.container
        assert "factory_service" in app.container
        assert ComponentService in app.container
        
        # Verify singleton behavior
        s1 = app.container.resolve_sync(SingletonService)
        s2 = app.container.resolve_sync(SingletonService)
        assert s1 is s2
    
    def test_conditional_registration_integration(self):
        """Test conditional registration with environment variables."""
        app = Application()
        
        with patch.dict(os.environ, {"FEATURE_ENABLED": "true"}):
            @app.when_env("FEATURE_ENABLED", "true").service
            class FeatureService:
                pass
        
        # Should be registered since condition is met
        assert FeatureService in app.container
    
    async def test_full_lifecycle_with_decorators(self):
        """Test complete lifecycle with decorated services."""
        app = Application()
        
        # Add lifecycle callbacks
        startup_called = False
        shutdown_called = False
        
        def startup():
            nonlocal startup_called
            startup_called = True
        
        def shutdown():
            nonlocal shutdown_called
            shutdown_called = True
        
        app._startup_callbacks.append(startup)
        app._shutdown_callbacks.append(shutdown)
        
        # Register services with decorators
        @app.singleton
        class DatabaseServiceIntegration:
            def __init__(self):
                self.connection = "connected"
        
        @app.service
        class UserServiceIntegration:
            def __init__(self, db: DatabaseServiceIntegration):
                self.db = db
        
        # Test full lifecycle
        async with app:
            assert startup_called
            
            # Resolve services
            user_service = app.resolve(UserServiceIntegration)
            assert user_service.db.connection == "connected"
            
            # Verify singleton behavior
            db1 = app.resolve(DatabaseServiceIntegration)
            db2 = app.resolve(DatabaseServiceIntegration)
            assert db1 is db2
        
        assert shutdown_called


class TestApplicationErrorScenarios:
    """Test Application error handling scenarios."""
    
    def test_factory_without_key_parameter_error(self):
        """Test factory decorator raises error without key parameter."""
        app = Application()
        
        with pytest.raises(ConfigurationError, match="Factory decorator requires 'key' parameter"):
            @app.factory  # Missing required key parameter
            def bad_factory():
                return TestService()
    
    def test_component_with_non_callable_non_class(self):
        """Test component decorator with invalid target type."""
        app = Application()
        
        with pytest.raises(ConfigurationError, match="Cannot register .* as component"):
            app.component("not_valid_target")
    
    def test_function_component_without_key(self):
        """Test function component registration without key raises error."""
        app = Application()
        
        with pytest.raises(ConfigurationError, match="Factory registration requires 'key' parameter"):
            @app.component  # Function needs key parameter
            def function_without_key():
                return TestService()


class TestApplicationEdgeCases:
    """Test Application edge cases and unusual scenarios."""
    
    def test_decorator_returns_same_class(self):
        """Test that decorators return the same class instance."""
        app = Application()
        
        @app.service
        class OriginalClass:
            pass
        
        # Decorator should return the exact same class
        assert OriginalClass.__name__ == "OriginalClass"
        
        # Should be able to instantiate normally
        instance = OriginalClass()
        assert isinstance(instance, OriginalClass)
    
    def test_multiple_registrations_same_service(self):
        """Test registering the same service multiple times with different configurations."""
        app = Application()
        
        @app.service(name="primary")
        class MultiRegisterService:
            def __init__(self, config="default"):
                self.config = config
        
        @app.service(name="secondary")
        class MultiRegisterService:  # Same class, different name
            def __init__(self, config="secondary"):
                self.config = config
        
        # Both should be accessible
        primary = app.container.resolve_sync(MultiRegisterService, name="primary")
        secondary = app.container.resolve_sync(MultiRegisterService, name="secondary")
        
        # They should be different instances (transient scope)
        assert primary is not secondary
    
    def test_empty_tags_set(self):
        """Test service registration with empty tags set."""
        app = Application()
        
        @app.service(tags=set())
        class ServiceWithEmptyTags:
            pass
        
        assert ServiceWithEmptyTags in app.container
    
    def test_none_condition(self):
        """Test service registration with None condition."""
        app = Application()
        
        @app.service(condition=None)
        class ServiceWithNoneCondition:
            pass
        
        assert ServiceWithNoneCondition in app.container
        service = app.container.resolve_sync(ServiceWithNoneCondition)
        assert isinstance(service, ServiceWithNoneCondition)
