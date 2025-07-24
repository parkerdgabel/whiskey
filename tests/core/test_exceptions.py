"""Tests for exception types."""

import pytest

from whiskey.core.exceptions import (
    CircularDependencyError,
    ConfigurationError,
    InjectionError,
    InvalidServiceError,
    LifecycleError,
    ResolutionError,
    ScopeError,
    ServiceNotFoundError,
    WhiskeyError,
)
from ..conftest import SimpleService, DependentService


class TestWhiskeyError:
    """Test base WhiskeyError."""
    
    @pytest.mark.unit
    def test_whiskey_error_is_exception(self):
        """Test WhiskeyError is an Exception."""
        error = WhiskeyError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"


class TestServiceNotFoundError:
    """Test ServiceNotFoundError."""
    
    @pytest.mark.unit
    def test_service_not_found_basic(self):
        """Test basic ServiceNotFoundError."""
        error = ServiceNotFoundError(SimpleService)
        
        assert error.service_key is SimpleService
        assert "SimpleService" in str(error)
        assert "not found in container" in str(error)
    
    @pytest.mark.unit
    def test_service_not_found_with_available(self):
        """Test ServiceNotFoundError with available services."""
        available = ["Service1", "Service2", "Service3"]
        error = ServiceNotFoundError(SimpleService, available)
        
        assert error.available == available
        error_str = str(error)
        assert "Available services:" in error_str
        assert "Service1" in error_str
        assert "Service2" in error_str
        assert "Service3" in error_str
    
    @pytest.mark.unit
    def test_service_not_found_truncates_available(self):
        """Test ServiceNotFoundError truncates long available list."""
        available = [f"Service{i}" for i in range(10)]
        error = ServiceNotFoundError(SimpleService, available)
        
        error_str = str(error)
        assert "Service0" in error_str
        assert "Service4" in error_str
        assert "Service5" not in error_str  # Truncated
        assert "and 5 more" in error_str


class TestCircularDependencyError:
    """Test CircularDependencyError."""
    
    @pytest.mark.unit
    def test_circular_dependency_error(self):
        """Test CircularDependencyError shows chain."""
        chain = [SimpleService, DependentService, SimpleService]
        error = CircularDependencyError(chain)
        
        assert error.dependency_chain == chain
        error_str = str(error)
        assert "Circular dependency detected:" in error_str
        assert "SimpleService -> DependentService -> SimpleService" in error_str
    
    @pytest.mark.unit
    def test_circular_dependency_with_strings(self):
        """Test CircularDependencyError with string service keys."""
        chain = ["ServiceA", "ServiceB", "ServiceA"]
        error = CircularDependencyError(chain)
        
        error_str = str(error)
        assert "ServiceA -> ServiceB -> ServiceA" in error_str


class TestInjectionError:
    """Test InjectionError."""
    
    @pytest.mark.unit
    def test_injection_error(self):
        """Test InjectionError with context."""
        error = InjectionError(
            target=DependentService,
            parameter="simple",
            reason="Service not found"
        )
        
        assert error.target is DependentService
        assert error.parameter == "simple"
        assert error.reason == "Service not found"
        
        error_str = str(error)
        assert "Failed to inject 'simple'" in error_str
        assert "DependentService" in error_str
        assert "Service not found" in error_str
    
    @pytest.mark.unit
    def test_injection_error_with_string_target(self):
        """Test InjectionError with string target."""
        error = InjectionError(
            target="Unknown",
            parameter="param",
            reason="Failed"
        )
        
        assert "Failed to inject 'param' into Unknown" in str(error)


class TestResolutionError:
    """Test ResolutionError."""
    
    @pytest.mark.unit
    def test_resolution_error_basic(self):
        """Test basic ResolutionError."""
        error = ResolutionError(
            service_type=SimpleService,
            reason="No implementation provided"
        )
        
        assert error.service_type is SimpleService
        assert error.reason == "No implementation provided"
        assert error.suggestion is None
        
        error_str = str(error)
        assert "Failed to resolve SimpleService" in error_str
        assert "No implementation provided" in error_str
    
    @pytest.mark.unit
    def test_resolution_error_with_suggestion(self):
        """Test ResolutionError with suggestion."""
        error = ResolutionError(
            service_type=SimpleService,
            reason="Missing dependency",
            suggestion="Register the dependency first"
        )
        
        assert error.suggestion == "Register the dependency first"
        
        error_str = str(error)
        assert "💡 Suggestion:" in error_str
        assert "Register the dependency first" in error_str


class TestOtherExceptions:
    """Test other exception types."""
    
    @pytest.mark.unit
    def test_scope_error(self):
        """Test ScopeError."""
        error = ScopeError("Invalid scope")
        assert isinstance(error, WhiskeyError)
        assert str(error) == "Invalid scope"
    
    @pytest.mark.unit
    def test_invalid_service_error(self):
        """Test InvalidServiceError."""
        error = InvalidServiceError("Service configuration invalid")
        assert isinstance(error, WhiskeyError)
        assert str(error) == "Service configuration invalid"
    
    @pytest.mark.unit
    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Invalid configuration")
        assert isinstance(error, WhiskeyError)
        assert str(error) == "Invalid configuration"
    
    @pytest.mark.unit
    def test_lifecycle_error(self):
        """Test LifecycleError."""
        error = LifecycleError("Initialization failed")
        assert isinstance(error, WhiskeyError)
        assert str(error) == "Initialization failed"


class TestExceptionHierarchy:
    """Test exception hierarchy and inheritance."""
    
    @pytest.mark.unit
    def test_all_exceptions_inherit_from_whiskey_error(self):
        """Test all exceptions inherit from WhiskeyError."""
        exceptions = [
            ServiceNotFoundError("test", []),
            CircularDependencyError([]),
            ScopeError("test"),
            InvalidServiceError("test"),
            InjectionError("target", "param", "reason"),
            ConfigurationError("test"),
            LifecycleError("test"),
            ResolutionError(SimpleService, "test"),
        ]
        
        for error in exceptions:
            assert isinstance(error, WhiskeyError)
            assert isinstance(error, Exception)