"""Tests for the TypeAnalyzer module.

This module tests the critical type analysis engine that determines
dependency injection decisions for parameters.
"""

import asyncio
import inspect
from typing import Any, ForwardRef, Optional, Protocol, Union
from unittest.mock import Mock

import pytest

from whiskey.core.analyzer import (
    InjectDecision,
    InjectResult,
    TypeAnalyzer,
    get_optional_inner,
    get_type_hints_safe,
    is_generic_with_args,
    is_optional,
    is_union,
)
from whiskey.core.errors import TypeAnalysisError
from whiskey.core.registry import ServiceRegistry


# Helper functions
def create_mock_parameter(name: str, annotation: Any, default: Any = inspect.Parameter.empty):
    """Create a mock parameter for testing."""
    param = Mock()
    param.name = name
    param.annotation = annotation
    param.default = default
    param.empty = inspect.Parameter.empty
    return param


# Test classes and types
class SimpleService:
    def __init__(self):
        self.value = "simple"


class DatabaseService:
    def __init__(self, connection_string: str = "default"):
        self.connection_string = connection_string


class ComplexService:
    def __init__(self, db: DatabaseService, simple: SimpleService):
        self.db = db
        self.simple = simple


class ServiceWithOptionals:
    def __init__(self, required: SimpleService, optional: Optional[DatabaseService] = None):
        self.required = required
        self.optional = optional


class ServiceWithUnion:
    def __init__(self, service: Union[SimpleService, DatabaseService]):
        self.service = service


# Protocol for testing
class DatabaseProtocol(Protocol):
    def query(self, sql: str) -> list[dict]: ...


class ProtocolService:
    def __init__(self, db: DatabaseProtocol):
        self.db = db


# Forward reference setup
ForwardService = ForwardRef("ForwardService")


class ServiceWithForwardRef:
    def __init__(self, forward: ForwardService):
        self.forward = forward


class TestTypeAnalyzer:
    """Test the TypeAnalyzer class functionality."""

    @pytest.fixture
    def registry(self):
        """Create a service registry for testing."""
        registry = ServiceRegistry()
        registry.register(SimpleService, SimpleService)
        registry.register(DatabaseService, DatabaseService)
        registry.register(ComplexService, ComplexService)
        return registry

    @pytest.fixture
    def analyzer(self, registry):
        """Create a TypeAnalyzer instance."""
        return TypeAnalyzer(registry)

    def test_initialization(self, registry):
        """Test TypeAnalyzer initialization."""
        analyzer = TypeAnalyzer(registry)
        assert analyzer.registry is registry
        assert analyzer._analysis_cache == {}
        assert analyzer.BUILTIN_TYPES is not None
        assert str in analyzer.BUILTIN_TYPES
        assert int in analyzer.BUILTIN_TYPES

    def test_builtin_types_detection(self, analyzer):
        """Test that builtin types are correctly identified."""
        builtin_types = [str, int, float, bool, list, dict, tuple, set, bytes]
        for builtin_type in builtin_types:
            assert builtin_type in analyzer.BUILTIN_TYPES

    def test_should_inject_builtin_types(self, analyzer):
        """Test that builtin types are not injected."""
        param = create_mock_parameter("test_param", str)

        result = analyzer.should_inject(param, str)
        assert result.decision == InjectDecision.NO
        assert "built-in" in result.reason.lower() or "builtin" in result.reason.lower()

    def test_should_inject_registered_service(self, analyzer):
        """Test injection decision for registered services."""
        param = create_mock_parameter("simple", SimpleService)

        result = analyzer.should_inject(param, SimpleService)
        assert result.decision == InjectDecision.YES
        assert result.type_hint == SimpleService

    def test_should_inject_unregistered_service(self, analyzer):
        """Test injection decision for unregistered services."""

        class UnregisteredService:
            pass

        param = Mock()
        param.name = "unregistered"
        param.annotation = UnregisteredService
        param.default = inspect.Parameter.empty

        result = analyzer.should_inject(param, UnregisteredService)
        assert result.decision == InjectDecision.NO
        assert "not registered" in result.reason.lower()

    def test_should_inject_optional_type(self, analyzer):
        """Test injection decision for Optional types."""
        param = Mock()
        param.name = "optional_service"
        param.annotation = Optional[SimpleService]
        param.default = None

        result = analyzer.should_inject(param, Optional[SimpleService])
        assert result.decision == InjectDecision.OPTIONAL
        assert result.inner_type == SimpleService

    def test_should_inject_union_type_error(self, analyzer):
        """Test that Union types result in error."""
        param = Mock()
        param.name = "union_service"
        param.annotation = Union[SimpleService, DatabaseService]
        param.default = inspect.Parameter.empty

        result = analyzer.should_inject(param, Union[SimpleService, DatabaseService])
        assert result.decision == InjectDecision.ERROR
        assert "union type" in result.reason.lower()

    def test_should_inject_with_default_value(self, analyzer):
        """Test injection decision for parameters with default values."""
        param = Mock()
        param.name = "service_with_default"
        param.annotation = SimpleService
        param.default = "some_default"

        result = analyzer.should_inject(param, SimpleService)
        assert result.decision == InjectDecision.NO
        assert "has default value" in result.reason.lower()

    def test_analyze_callable_simple_function(self, analyzer):
        """Test analyzing a simple function."""

        def test_func(simple: SimpleService, db: DatabaseService):
            return f"{simple.value} - {db.connection_string}"

        result = analyzer.analyze_callable(test_func)

        assert len(result) == 2
        assert "simple" in result
        assert "db" in result
        assert result["simple"].decision == InjectDecision.YES
        assert result["db"].decision == InjectDecision.YES

    def test_analyze_callable_with_mixed_params(self, analyzer):
        """Test analyzing function with mixed parameter types."""

        def test_func(simple: SimpleService, user_id: int, name: str = "default"):
            return f"{simple.value} - {user_id} - {name}"

        result = analyzer.analyze_callable(test_func)

        assert len(result) == 3
        assert result["simple"].decision == InjectDecision.YES
        assert result["user_id"].decision == InjectDecision.NO  # builtin type
        assert result["name"].decision == InjectDecision.NO  # has default

    def test_analyze_callable_with_optional(self, analyzer):
        """Test analyzing function with Optional parameters."""

        def test_func(simple: SimpleService, optional_db: Optional[DatabaseService] = None):
            return simple.value

        result = analyzer.analyze_callable(test_func)

        assert len(result) == 2
        assert result["simple"].decision == InjectDecision.YES
        assert result["optional_db"].decision == InjectDecision.OPTIONAL
        assert result["optional_db"].inner_type == DatabaseService

    def test_analyze_callable_async_function(self, analyzer):
        """Test analyzing async functions."""

        async def async_test_func(simple: SimpleService):
            return simple.value

        result = analyzer.analyze_callable(async_test_func)

        assert len(result) == 1
        assert result["simple"].decision == InjectDecision.YES

    def test_analyze_callable_class_method(self, analyzer):
        """Test analyzing class methods."""
        result = analyzer.analyze_callable(ComplexService.__init__)

        # Should analyze all parameters except 'self'
        assert "self" not in result
        assert "db" in result
        assert "simple" in result
        assert result["db"].decision == InjectDecision.YES
        assert result["simple"].decision == InjectDecision.YES

    def test_can_auto_create_simple_class(self, analyzer):
        """Test auto-creation capability for simple classes."""
        assert analyzer.can_auto_create(SimpleService)

    def test_can_auto_create_complex_class(self, analyzer):
        """Test auto-creation capability for classes with dependencies."""
        assert analyzer.can_auto_create(ComplexService)

    def test_cannot_auto_create_with_builtin_params(self, analyzer):
        """Test that classes with builtin parameters cannot be auto-created."""

        class ServiceWithBuiltins:
            def __init__(self, name: str, count: int):
                pass

        assert not analyzer.can_auto_create(ServiceWithBuiltins)

    def test_cannot_auto_create_unregistered_dependencies(self, analyzer):
        """Test auto-creation fails for unregistered dependencies."""

        class UnregisteredDep:
            pass

        class ServiceWithUnregistered:
            def __init__(self, dep: UnregisteredDep):
                pass

        assert not analyzer.can_auto_create(ServiceWithUnregistered)

    def test_caching(self, analyzer):
        """Test that analysis results are cached."""

        def test_func(simple: SimpleService):
            return simple.value

        # First call
        result1 = analyzer.analyze_callable(test_func)

        # Second call should use cache
        result2 = analyzer.analyze_callable(test_func)

        assert result1 == result2
        # Cache is keyed by (type_hint, param_name) tuples, not the function itself
        assert len(analyzer._analysis_cache) > 0

    def test_clear_cache(self, analyzer):
        """Test cache clearing functionality."""

        def test_func(simple: SimpleService):
            return simple.value

        # Populate cache
        analyzer.analyze_callable(test_func)
        assert len(analyzer._analysis_cache) > 0

        # Clear cache
        analyzer.clear_cache()
        assert len(analyzer._analysis_cache) == 0

    def test_error_handling_invalid_callable(self, analyzer):
        """Test error handling for invalid callables."""
        with pytest.raises(TypeAnalysisError):
            analyzer.analyze_callable("not a callable")

    def test_forward_reference_handling(self, analyzer):
        """Test handling of forward references."""

        # This is a complex scenario that may need special handling
        def test_func(forward: "SimpleService"):
            return forward

        result = analyzer.analyze_callable(test_func)

        # Should handle forward reference gracefully
        assert "forward" in result
        # The decision may vary based on implementation


class TestUtilityFunctions:
    """Test utility functions in the analyzer module."""

    def test_get_type_hints_safe_normal_function(self):
        """Test get_type_hints_safe with normal function."""

        def test_func(x: int, y: str) -> bool:
            return True

        hints = get_type_hints_safe(test_func)
        assert hints == {"x": int, "y": str, "return": bool}

    def test_get_type_hints_safe_no_annotations(self):
        """Test get_type_hints_safe with function without annotations."""

        def test_func(x, y):
            return True

        hints = get_type_hints_safe(test_func)
        assert hints == {}

    def test_get_type_hints_safe_error_handling(self):
        """Test get_type_hints_safe error handling."""

        def test_func(x: "NonExistentType"):
            return x

        # Should not raise error, just return empty dict
        hints = get_type_hints_safe(test_func)
        assert isinstance(hints, dict)

    def test_is_optional(self):
        """Test Optional type detection."""
        assert is_optional(Optional[str])
        assert is_optional(Union[str, None])
        assert not is_optional(str)
        assert not is_optional(Union[str, int])

    def test_get_optional_inner(self):
        """Test extracting inner type from Optional."""
        assert get_optional_inner(Optional[str]) == str
        assert get_optional_inner(Union[str, None]) == str
        assert get_optional_inner(Union[None, str]) == str

    def test_is_union(self):
        """Test Union type detection."""
        assert is_union(Union[str, int])
        assert is_union(Union[str, int, float])
        assert not is_union(Optional[str])  # Should not be considered Union
        assert not is_union(str)

    def test_is_generic_with_args(self):
        """Test generic type with arguments detection."""
        from typing import Dict, List

        assert is_generic_with_args(List[str])
        assert is_generic_with_args(Dict[str, int])
        assert not is_generic_with_args(List)
        assert not is_generic_with_args(str)


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def analyzer(self):
        registry = ServiceRegistry()
        return TypeAnalyzer(registry)

    def test_analyze_lambda_function(self, analyzer):
        """Test analyzing lambda functions."""
        lambda_func = lambda x: x

        result = analyzer.analyze_callable(lambda_func)

        # Lambda with no type hints
        assert "x" in result
        assert result["x"].decision == InjectDecision.NO

    def test_analyze_builtin_function(self, analyzer):
        """Test analyzing builtin functions."""
        result = analyzer.analyze_callable(len)

        # Builtin functions may have special handling
        assert isinstance(result, dict)

    def test_analyze_method_with_self(self, analyzer):
        """Test that 'self' parameter is properly excluded."""

        class TestClass:
            def method(self, param: str):
                pass

        result = analyzer.analyze_callable(TestClass.method)

        # 'self' should be excluded from analysis
        assert "self" not in result
        assert "param" in result

    def test_analyze_static_method(self, analyzer):
        """Test analyzing static methods."""

        class TestClass:
            @staticmethod
            def static_method(param: str):
                pass

        result = analyzer.analyze_callable(TestClass.static_method)

        assert "param" in result

    def test_analyze_class_method(self, analyzer):
        """Test analyzing class methods."""

        class TestClass:
            @classmethod
            def class_method(cls, param: str):
                pass

        result = analyzer.analyze_callable(TestClass.class_method)

        # 'cls' should be excluded from analysis
        assert "cls" not in result
        assert "param" in result

    def test_complex_generic_types(self, analyzer):
        """Test handling of complex generic types."""
        from typing import Dict, List

        def test_func(items: List[str], mapping: Dict[str, int]):
            pass

        result = analyzer.analyze_callable(test_func)

        # Complex generics should not be injected
        assert result["items"].decision == InjectDecision.NO
        assert result["mapping"].decision == InjectDecision.NO

    def test_circular_dependency_detection(self, analyzer):
        """Test that circular dependencies are handled."""

        # This would be handled at resolution time, but analyzer should be aware
        class CircularA:
            def __init__(self, b: "CircularB"):
                pass

        class CircularB:
            def __init__(self, a: CircularA):
                pass

        # Register both services
        analyzer.registry.register(CircularA, CircularA)
        analyzer.registry.register(CircularB, CircularB)

        # Should be able to analyze without infinite recursion
        result = analyzer.analyze_callable(CircularA.__init__)
        assert "b" in result

    def test_none_type_handling(self, analyzer):
        """Test handling of None type."""

        def test_func(param: None):
            pass

        result = analyzer.analyze_callable(test_func)

        assert result["param"].decision == InjectDecision.NO


class TestInjectResult:
    """Test the InjectResult dataclass."""

    def test_inject_result_creation(self):
        """Test creating InjectResult objects."""
        result = InjectResult(decision=InjectDecision.YES, type_hint=str, reason="test reason")

        assert result.decision == InjectDecision.YES
        assert result.type_hint == str
        assert result.reason == "test reason"
        assert result.inner_type is None

    def test_inject_result_with_inner_type(self):
        """Test InjectResult with inner type for Optional."""
        result = InjectResult(
            decision=InjectDecision.OPTIONAL,
            type_hint=Optional[str],
            inner_type=str,
            reason="optional type",
        )

        assert result.inner_type == str

    def test_inject_result_equality(self):
        """Test InjectResult equality comparison."""
        result1 = InjectResult(InjectDecision.YES, str, "reason")
        result2 = InjectResult(InjectDecision.YES, str, "reason")
        result3 = InjectResult(InjectDecision.NO, str, "different reason")

        assert result1 == result2
        assert result1 != result3


class TestInjectDecision:
    """Test the InjectDecision enum."""

    def test_inject_decision_values(self):
        """Test that all expected values exist."""
        assert InjectDecision.YES
        assert InjectDecision.NO
        assert InjectDecision.OPTIONAL
        assert InjectDecision.ERROR

    def test_inject_decision_string_representation(self):
        """Test string representation of decisions."""
        assert str(InjectDecision.YES) == "InjectDecision.YES"
        assert str(InjectDecision.NO) == "InjectDecision.NO"
        assert str(InjectDecision.OPTIONAL) == "InjectDecision.OPTIONAL"
        assert str(InjectDecision.ERROR) == "InjectDecision.ERROR"


@pytest.mark.asyncio
class TestAsyncIntegration:
    """Test analyzer integration with async code."""

    @pytest.fixture
    def analyzer(self):
        registry = ServiceRegistry()
        registry.register(SimpleService, SimpleService)
        return TypeAnalyzer(registry)

    async def test_analyze_async_callable(self, analyzer):
        """Test analyzing async callables."""

        async def async_func(service: SimpleService):
            await asyncio.sleep(0.01)
            return service.value

        result = analyzer.analyze_callable(async_func)

        assert "service" in result
        assert result["service"].decision == InjectDecision.YES

    async def test_analyze_async_method(self, analyzer):
        """Test analyzing async methods."""

        class AsyncService:
            async def async_method(self, service: SimpleService):
                return service.value

        result = analyzer.analyze_callable(AsyncService.async_method)

        assert "self" not in result
        assert "service" in result
        assert result["service"].decision == InjectDecision.YES
