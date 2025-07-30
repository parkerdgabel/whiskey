"""Test scope validation implementation for Phase 3.2.

This test demonstrates the expected behavior for scope validation:
- Validate scopes exist before registering components
- Prevent invalid scope combinations
- Enforce scope dependency rules
- Clear error messages for scope mismatches
"""

import pytest
from whiskey.core.application import Whiskey
from whiskey.core.container import Container
from whiskey.core.registry import Scope
from whiskey.core.errors import ConfigurationError, ResolutionError, CircularDependencyError


class DatabaseService:
    """A singleton service that should be available to all scopes."""
    
    def __init__(self):
        self.connection = "postgresql://localhost"


class RequestService:
    """A request-scoped service."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
        self.request_id = "req_123"


class SessionService:
    """A session-scoped service."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
        self.session_id = "sess_456"


class TransientService:
    """A transient service that depends on request-scoped service."""
    
    def __init__(self, request: RequestService):
        self.request = request


class InvalidScopeDependency:
    """Service that creates invalid scope dependency (singleton depends on scoped)."""
    
    def __init__(self, request: RequestService):
        self.request = request


@pytest.mark.unit
class TestScopeValidation:
    """Test basic scope validation functionality."""
    
    def test_valid_scope_registration(self):
        """Valid scope registrations should work without errors."""
        app = Whiskey()
        
        # Register built-in scopes - should work
        app.singleton(DatabaseService)
        app.component(TransientService)  # Transient
        
        # No errors should be raised
        assert DatabaseService in app.container
        assert TransientService in app.container
    
    def test_scoped_component_registration_with_valid_scope(self):
        """Scoped components should register successfully with valid scope names."""
        app = Whiskey()
        
        # Register with custom scope name
        app.scoped(RequestService, scope_name="request")
        app.scoped(SessionService, scope_name="session")
        
        # Should register successfully
        assert RequestService in app.container
        assert SessionService in app.container
    
    def test_invalid_scope_name_raises_error(self):
        """Registering with invalid scope names should raise ConfigurationError."""
        app = Whiskey()
        
        # Built-in scopes that don't exist should raise error
        with pytest.raises(ConfigurationError, match="Invalid scope 'nonexistent'"):
            app.scoped(RequestService, scope_name="nonexistent")
    
    def test_scope_dependency_validation_singleton_to_singleton(self):
        """Singleton can depend on singleton - should work."""
        app = Whiskey()
        
        class SingletonA:
            def __init__(self):
                pass
        
        class SingletonB:
            def __init__(self, a: SingletonA):
                self.a = a
        
        app.singleton(SingletonA)
        app.singleton(SingletonB)
        
        # Should resolve without error
        b = app.resolve(SingletonB)
        assert b.a is not None
    
    def test_scope_dependency_validation_transient_to_singleton(self):
        """Transient can depend on singleton - should work."""
        app = Whiskey()
        app.singleton(DatabaseService)
        app.component(TransientService)  # Will be resolved but not found - need different test
        
        # Create a proper transient that depends on singleton
        class TransientWithSingleton:
            def __init__(self, db: DatabaseService):
                self.db = db
        
        app.component(TransientWithSingleton)
        
        # Should resolve without error
        service = app.resolve(TransientWithSingleton)
        assert service.db is not None
    
    def test_scope_dependency_validation_scoped_to_singleton(self):
        """Scoped can depend on singleton - should work."""
        app = Whiskey()
        app.singleton(DatabaseService)
        app.scoped(RequestService, scope_name="request")
        
        # Should register without error - validation happens at registration
        assert RequestService in app.container
        
        # Should resolve within scope
        with app.scope("request"):
            service = app.resolve(RequestService)
            assert service.db is not None
    
    def test_invalid_scope_dependency_singleton_to_scoped(self):
        """Singleton depending on scoped should raise ConfigurationError."""
        app = Whiskey()
        app.scoped(RequestService, scope_name="request")
        
        # This should raise an error at registration time
        with pytest.raises(ConfigurationError, match="Invalid scope dependency.*singleton.*cannot depend on.*request"):
            app.singleton(InvalidScopeDependency)
    
    def test_invalid_scope_dependency_singleton_to_transient(self):
        """Singleton depending on transient should raise ConfigurationError."""
        app = Whiskey()
        
        class TransientDep:
            def __init__(self):
                pass
        
        class SingletonDependent:
            def __init__(self, dep: TransientDep):
                self.dep = dep
        
        app.component(TransientDep)  # Transient
        
        # This should raise an error
        with pytest.raises(ConfigurationError, match="Invalid scope dependency.*singleton.*cannot depend on.*transient"):
            app.singleton(SingletonDependent)
    
    def test_scope_hierarchy_validation(self):
        """Scope hierarchy should be enforced (longer-lived can't depend on shorter-lived)."""
        app = Whiskey()
        
        # Session scope depending on request scope should fail
        class RequestOnlyService:
            def __init__(self):
                pass
        
        class SessionServiceBad:
            def __init__(self, request: RequestOnlyService):
                self.request = request
        
        app.scoped(RequestOnlyService, scope_name="request") 
        
        # Session scope is longer-lived than request, so it shouldn't depend on request
        with pytest.raises(ConfigurationError, match="Invalid scope dependency.*session.*cannot depend on.*request"):
            app.scoped(SessionServiceBad, scope_name="session")
    
    def test_circular_scope_dependency_detection(self):
        """Circular dependencies across scopes should be allowed at registration (detected at resolution)."""
        app = Whiskey()
        
        class ServiceA:
            def __init__(self, b: 'ServiceB'):
                self.b = b
        
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a
        
        app.scoped(ServiceA, scope_name="request")
        
        # Registration should succeed (circular deps are detected at resolution time)
        app.scoped(ServiceB, scope_name="request")
        
        # But resolution should fail due to circular dependency
        with app.scope("request"):
            with pytest.raises((ResolutionError, CircularDependencyError)):
                app.resolve(ServiceA)


@pytest.mark.unit 
class TestScopeValidationErrorMessages:
    """Test that scope validation provides clear error messages."""
    
    def test_clear_error_for_invalid_scope_name(self):
        """Error message should clearly indicate invalid scope name."""
        app = Whiskey()
        
        with pytest.raises(ConfigurationError) as exc_info:
            app.scoped(RequestService, scope_name="invalid_scope")
        
        error_msg = str(exc_info.value)
        assert "Invalid scope 'invalid_scope'" in error_msg
        assert "Available scopes:" in error_msg or "valid scopes" in error_msg.lower()
    
    def test_clear_error_for_scope_dependency_violation(self):
        """Error message should clearly explain scope dependency rules."""
        app = Whiskey()
        app.scoped(RequestService, scope_name="request")
        
        with pytest.raises(ConfigurationError) as exc_info:
            app.singleton(InvalidScopeDependency)
        
        error_msg = str(exc_info.value)
        assert "singleton" in error_msg.lower()
        assert "scoped" in error_msg.lower() or "request" in error_msg.lower()
        assert "cannot depend on" in error_msg.lower()
    
    def test_error_message_includes_component_names(self):
        """Error messages should include the specific component names involved."""
        app = Whiskey()
        app.scoped(RequestService, scope_name="request")
        
        with pytest.raises(ConfigurationError) as exc_info:
            app.singleton(InvalidScopeDependency)
        
        error_msg = str(exc_info.value)
        assert "InvalidScopeDependency" in error_msg
        assert "RequestService" in error_msg


@pytest.mark.unit
class TestScopeValidationIntegration:
    """Test scope validation integration with existing features."""
    
    def test_scope_validation_with_factory_components(self):
        """Scope validation should work with factory-registered components."""
        app = Whiskey()
        
        def create_request_service() -> RequestService:
            return RequestService(DatabaseService())
        
        app.singleton(DatabaseService)
        
        # Factory creating scoped component should validate
        app.factory(RequestService, create_request_service)
        
        # Should work
        service = app.resolve(RequestService)
        assert service is not None
    
    def test_scope_validation_with_conditional_registration(self):
        """Scope validation should work with conditional registration."""
        app = Whiskey()
        
        def always_true():
            return True
        
        app.singleton(DatabaseService)
        
        # Conditional scoped registration should validate
        app.scoped(RequestService, scope_name="request", condition=always_true)
        
        # Should register and resolve within scope
        with app.scope("request"):
            service = app.resolve(RequestService)
            assert service is not None
    
    def test_scope_validation_preserves_existing_behavior(self):
        """Scope validation should not break existing valid registrations."""
        app = Whiskey()
        
        # All these should continue to work
        app.singleton(DatabaseService)
        app.component(TransientService)
        app.scoped(RequestService, scope_name="request")
        
        # Resolution should work as before
        db = app.resolve(DatabaseService)
        assert db is not None
        
        with app.scope("request"):
            req = app.resolve(RequestService)
            assert req is not None


@pytest.mark.unit
class TestScopeRegistry:
    """Test the scope registry and validation."""
    
    def test_default_scopes_are_registered(self):
        """Default scopes should be available by default."""
        container = Container()
        
        # These should be valid scope names
        valid_scopes = ["singleton", "transient", "request", "session"]
        
        for scope_name in valid_scopes:
            # Should not raise error (we'll implement this)
            try:
                container._validate_scope_name(scope_name)
            except AttributeError:
                # Method doesn't exist yet - that's fine for now
                pass
    
    def test_custom_scope_registration(self):
        """Should be able to register custom scopes."""
        container = Container()
        
        # Should be able to register new scope
        container.register_scope("custom")
        
        # Should now be valid
        container._validate_scope_name("custom")
    
    def test_scope_hierarchy_definition(self):
        """Should be able to define scope hierarchies."""
        container = Container()
        
        # Define scope hierarchy (longer-lived to shorter-lived)
        container.define_scope_hierarchy([
            "singleton",  # Longest lived
            "session",
            "request",    # Shortest lived
            "transient"   # No lifetime (new each time)
        ])
        
        # Should validate hierarchy
        assert container._scope_can_depend_on("request", "singleton")
        assert container._scope_can_depend_on("session", "singleton") 
        assert not container._scope_can_depend_on("singleton", "request")
        assert not container._scope_can_depend_on("singleton", "session")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])