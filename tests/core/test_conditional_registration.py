"""Tests for conditional registration feature."""

import os
import pytest

from whiskey import Container, provide, singleton, factory, scoped
from whiskey.core.conditions import (
    evaluate_condition, env_equals, env_exists, env_truthy,
    all_conditions, any_conditions, not_condition
)
from whiskey.core.decorators import set_default_container


class BaseService:
    """Base service for testing."""
    pass


class DevService(BaseService):
    """Development service."""
    pass


class ProdService(BaseService):
    """Production service."""
    pass


class MockService(BaseService):
    """Mock service for testing."""
    pass


class TestConditionalRegistration:
    """Test conditional registration functionality."""
    
    @pytest.fixture
    def container(self):
        """Create a test container."""
        return Container()
    
    @pytest.fixture(autouse=True)
    def reset_env(self):
        """Reset environment variables before/after each test."""
        # Save current env
        saved_env = dict(os.environ)
        yield
        # Restore env
        os.environ.clear()
        os.environ.update(saved_env)
    
    def test_evaluate_condition_basics(self):
        """Test basic condition evaluation."""
        # None means always true
        assert evaluate_condition(None) is True
        
        # Boolean values
        assert evaluate_condition(True) is True
        assert evaluate_condition(False) is False
        
        # Callable conditions
        assert evaluate_condition(lambda: True) is True
        assert evaluate_condition(lambda: False) is False
        
        # Exception in condition means false
        assert evaluate_condition(lambda: 1/0) is False
    
    def test_env_conditions(self):
        """Test environment-based condition factories."""
        # env_equals
        os.environ["TEST_VAR"] = "value"
        assert evaluate_condition(env_equals("TEST_VAR", "value")) is True
        assert evaluate_condition(env_equals("TEST_VAR", "other")) is False
        assert evaluate_condition(env_equals("MISSING", "value")) is False
        
        # env_exists
        assert evaluate_condition(env_exists("TEST_VAR")) is True
        assert evaluate_condition(env_exists("MISSING")) is False
        
        # env_truthy
        os.environ["TRUE_VAR"] = "true"
        os.environ["ONE_VAR"] = "1"
        os.environ["YES_VAR"] = "yes"
        os.environ["ON_VAR"] = "on"
        os.environ["FALSE_VAR"] = "false"
        
        assert evaluate_condition(env_truthy("TRUE_VAR")) is True
        assert evaluate_condition(env_truthy("ONE_VAR")) is True
        assert evaluate_condition(env_truthy("YES_VAR")) is True
        assert evaluate_condition(env_truthy("ON_VAR")) is True
        assert evaluate_condition(env_truthy("FALSE_VAR")) is False
        assert evaluate_condition(env_truthy("MISSING")) is False
    
    def test_composite_conditions(self):
        """Test composite condition helpers."""
        os.environ["VAR1"] = "true"
        os.environ["VAR2"] = "false"
        
        # all_conditions
        assert evaluate_condition(
            all_conditions(
                env_exists("VAR1"),
                env_equals("VAR1", "true")
            )
        ) is True
        
        assert evaluate_condition(
            all_conditions(
                env_exists("VAR1"),
                env_equals("VAR1", "false")
            )
        ) is False
        
        # any_conditions
        assert evaluate_condition(
            any_conditions(
                env_equals("VAR1", "false"),
                env_equals("VAR2", "false")
            )
        ) is True
        
        assert evaluate_condition(
            any_conditions(
                env_equals("VAR1", "false"),
                env_equals("VAR2", "true")
            )
        ) is False
        
        # not_condition
        assert evaluate_condition(
            not_condition(env_equals("VAR1", "false"))
        ) is True
        
        assert evaluate_condition(
            not_condition(env_equals("VAR1", "true"))
        ) is False
    
    def test_conditional_provide_decorator(self, container):
        """Test @provide with conditions."""
        set_default_container(container)
        
        # Register with true condition
        @provide(condition=True)
        class ServiceA:
            pass
        
        # Register with false condition
        @provide(condition=False)
        class ServiceB:
            pass
        
        # Register with lambda condition
        os.environ["ENABLE_C"] = "true"
        @provide(condition=lambda: os.getenv("ENABLE_C") == "true")
        class ServiceC:
            pass
        
        # Check registrations - check if actually in container
        assert ServiceA in container
        assert ServiceB not in container
        assert ServiceC in container
    
    def test_conditional_singleton_decorator(self, container):
        """Test @singleton with conditions."""
        set_default_container(container)
        
        os.environ["ENV"] = "dev"
        
        @singleton(condition=env_equals("ENV", "dev"))
        class DevConfig:
            value = "development"
        
        @singleton(condition=env_equals("ENV", "prod"))
        class ProdConfig:
            value = "production"
        
        # Only dev should be registered
        assert DevConfig in container
        assert ProdConfig not in container
        
        # Verify singleton behavior
        config1 = container.resolve_sync(DevConfig)
        config2 = container.resolve_sync(DevConfig)
        assert config1 is config2
    
    def test_conditional_factory_decorator(self, container):
        """Test @factory with conditions."""
        set_default_container(container)
        
        os.environ["USE_MOCK"] = "true"
        
        @factory(BaseService, condition=env_truthy("USE_MOCK"))
        def create_mock_service() -> BaseService:
            return MockService()
        
        @factory(BaseService, name="prod", condition=env_equals("ENV", "prod"))
        def create_prod_service() -> BaseService:
            return ProdService()
        
        # Only mock should be registered
        assert BaseService in container
        assert (BaseService, "prod") not in container
        
        service = container.resolve_sync(BaseService)
        assert isinstance(service, MockService)
    
    def test_conditional_scoped_decorator(self, container):
        """Test @scoped with conditions."""
        set_default_container(container)
        
        # Register a custom scope
        from whiskey.core.scopes import Scope
        class TestScope(Scope):
            pass
        
        container.register_scope("test", TestScope)
        
        os.environ["ENABLE_FEATURE"] = "yes"
        
        @scoped("test", condition=env_truthy("ENABLE_FEATURE"))
        class FeatureService:
            pass
        
        @scoped("test", condition=env_equals("MISSING", "value"))
        class DisabledService:
            pass
        
        # Only feature should be registered
        assert FeatureService in container
        assert DisabledService not in container
    
    def test_conditional_named_services(self, container):
        """Test conditions with named services."""
        set_default_container(container)
        
        os.environ["DB_TYPE"] = "postgres"
        
        @provide(name="primary", condition=env_equals("DB_TYPE", "postgres"))
        class PostgresDB:
            pass
        
        @provide(name="primary", condition=env_equals("DB_TYPE", "mysql"))
        class MySQLDB:
            pass
        
        # Only postgres should be registered
        assert (PostgresDB, "primary") in container
        assert (MySQLDB, "primary") not in container
        
        # Resolve returns the correct type
        db = container.resolve_sync(PostgresDB, name="primary")
        assert isinstance(db, PostgresDB)
    
    def test_multiple_conditional_registrations(self, container):
        """Test multiple services with different conditions."""
        set_default_container(container)
        
        os.environ["FEATURE_A"] = "true"
        os.environ["FEATURE_B"] = "false"
        os.environ["ENV"] = "staging"
        
        @provide(condition=env_truthy("FEATURE_A"))
        class FeatureAService:
            pass
        
        @provide(condition=env_truthy("FEATURE_B"))
        class FeatureBService:
            pass
        
        @provide(condition=any_conditions(
            env_equals("ENV", "dev"),
            env_equals("ENV", "staging")
        ))
        class NonProdService:
            pass
        
        @provide(condition=all_conditions(
            env_exists("FEATURE_A"),
            not_condition(env_truthy("FEATURE_B"))
        ))
        class SpecialService:
            pass
        
        # Check which services are registered
        assert FeatureAService in container
        assert FeatureBService not in container
        assert NonProdService in container
        assert SpecialService in container
    
    def test_runtime_condition_change(self, container):
        """Test that conditions are evaluated at decoration time."""
        set_default_container(container)
        
        # Set initial condition
        os.environ["DYNAMIC"] = "false"
        
        @provide(condition=env_truthy("DYNAMIC"))
        class DynamicService:
            pass
        
        # Service should not be registered
        assert DynamicService not in container
        
        # Change environment after decoration
        os.environ["DYNAMIC"] = "true"
        
        # Service still not registered (conditions are evaluated at decoration time)
        assert DynamicService not in container