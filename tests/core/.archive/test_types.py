"""Tests for type utilities and data classes."""

import sys
from typing import Optional, Union

import pytest

from whiskey.core.types import (
    InjectionPoint,
    ResolverContext,
    ScopeType,
    ServiceDescriptor,
    get_type_args,
    is_generic_type,
    is_optional_type,
    unwrap_optional,
)

from ..conftest import SimpleService


class TestScopeType:
    """Test ScopeType enum."""

    @pytest.mark.unit
    def test_scope_type_values(self):
        """Test ScopeType has expected values."""
        assert ScopeType.SINGLETON.value == "singleton"
        assert ScopeType.TRANSIENT.value == "transient"
        assert ScopeType.REQUEST.value == "request"
        assert ScopeType.SESSION.value == "session"
        assert ScopeType.CONVERSATION.value == "conversation"
        assert ScopeType.AI_CONTEXT.value == "ai_context"
        assert ScopeType.BATCH.value == "batch"
        assert ScopeType.STREAM.value == "stream"

    @pytest.mark.unit
    def test_scope_type_is_string_enum(self):
        """Test ScopeType behaves as string."""
        assert isinstance(ScopeType.SINGLETON, str)
        assert ScopeType.SINGLETON == "singleton"


class TestServiceDescriptor:
    """Test ServiceDescriptor data class."""

    @pytest.mark.unit
    def test_descriptor_with_implementation(self):
        """Test creating descriptor with implementation."""
        descriptor = ServiceDescriptor(service_type=SimpleService, implementation=SimpleService)

        assert descriptor.service_type is SimpleService
        assert descriptor.implementation is SimpleService
        assert descriptor.factory is None
        assert descriptor.instance is None
        assert descriptor.scope == ScopeType.TRANSIENT

    @pytest.mark.unit
    def test_descriptor_with_factory(self):
        """Test creating descriptor with factory."""

        def factory():
            return SimpleService()

        descriptor = ServiceDescriptor(service_type=SimpleService, factory=factory)

        assert descriptor.factory is factory
        assert descriptor.implementation is None

    @pytest.mark.unit
    def test_descriptor_with_instance(self):
        """Test creating descriptor with instance."""
        instance = SimpleService()
        descriptor = ServiceDescriptor(service_type=SimpleService, instance=instance)

        assert descriptor.instance is instance
        assert descriptor.implementation is None

    @pytest.mark.unit
    def test_descriptor_with_metadata(self):
        """Test descriptor with metadata."""
        descriptor = ServiceDescriptor(
            service_type=SimpleService,
            implementation=SimpleService,
            scope=ScopeType.SINGLETON,
            name="test",
            metadata={"version": "1.0"},
        )

        assert descriptor.scope == ScopeType.SINGLETON
        assert descriptor.name == "test"
        assert descriptor.metadata["version"] == "1.0"

    @pytest.mark.unit
    def test_descriptor_validation(self):
        """Test descriptor requires implementation, factory, or instance."""
        with pytest.raises(ValueError) as exc_info:
            ServiceDescriptor(service_type=SimpleService)

        assert "must have either implementation, factory, or instance" in str(exc_info.value)

    @pytest.mark.unit
    def test_descriptor_dependencies(self):
        """Test descriptor tracks dependencies."""
        descriptor = ServiceDescriptor(
            service_type=SimpleService, implementation=SimpleService, dependencies=[str, int]
        )

        assert len(descriptor.dependencies) == 2
        assert str in descriptor.dependencies
        assert int in descriptor.dependencies


class TestInjectionPoint:
    """Test InjectionPoint data class."""

    @pytest.mark.unit
    def test_injection_point_creation(self):
        """Test creating injection point."""
        point = InjectionPoint(
            parameter_name="service", service_key=SimpleService, is_optional=False
        )

        assert point.parameter_name == "service"
        assert point.service_key is SimpleService
        assert not point.is_optional
        assert not point.is_list

    @pytest.mark.unit
    def test_injection_point_optional(self):
        """Test optional injection point."""
        point = InjectionPoint(
            parameter_name="service", service_key=SimpleService, is_optional=True
        )

        assert point.is_optional

    @pytest.mark.unit
    def test_injection_point_metadata(self):
        """Test injection point with metadata."""
        point = InjectionPoint(
            parameter_name="service", service_key=SimpleService, metadata={"qualifier": "primary"}
        )

        assert point.metadata["qualifier"] == "primary"


class TestResolverContext:
    """Test ResolverContext data class."""

    @pytest.mark.unit
    def test_resolver_context_creation(self, container):
        """Test creating resolver context."""
        scope = container.scope_manager.get_scope(ScopeType.SINGLETON)
        context = ResolverContext(container=container, scope=scope)

        assert context.container is container
        assert context.scope is scope
        assert len(context.resolved) == 0
        assert len(context.stack) == 0
        assert context.parent is None

    @pytest.mark.unit
    def test_resolver_context_state(self, container):
        """Test resolver context maintains state."""
        scope = container.scope_manager.get_scope(ScopeType.SINGLETON)
        context = ResolverContext(container=container, scope=scope)

        # Add to state
        context.resolved.add(SimpleService)
        context.stack.append(SimpleService)

        assert SimpleService in context.resolved
        assert SimpleService in context.stack

    @pytest.mark.unit
    def test_create_child_context(self, container):
        """Test creating child context."""
        scope = container.scope_manager.get_scope(ScopeType.SINGLETON)
        parent = ResolverContext(container=container, scope=scope)

        # Add state to parent
        parent.resolved.add(SimpleService)
        parent.stack.append(SimpleService)

        # Create child
        child = parent.create_child()

        # Child has copy of state
        assert SimpleService in child.resolved
        assert SimpleService in child.stack
        assert child.parent is parent

        # Child state is independent
        child.resolved.add(str)
        assert str not in parent.resolved


class TestTypeUtilities:
    """Test type utility functions."""

    @pytest.mark.unit
    def test_is_generic_type(self):
        """Test is_generic_type function."""
        assert is_generic_type(list[str])
        assert is_generic_type(dict[str, int])
        assert is_generic_type(Optional[str])
        assert is_generic_type(Union[str, int])

        assert not is_generic_type(str)
        assert not is_generic_type(int)
        assert not is_generic_type(SimpleService)

    @pytest.mark.unit
    def test_get_type_args(self):
        """Test get_type_args function."""
        args = get_type_args(list[str])
        assert args == (str,)

        args = get_type_args(dict[str, int])
        assert args == (str, int)

        args = get_type_args(Optional[str])
        assert str in args
        assert type(None) in args

        args = get_type_args(Union[str, int, None])
        assert set(args) == {str, int, type(None)}

    @pytest.mark.unit
    def test_is_optional_type(self):
        """Test is_optional_type function."""
        assert is_optional_type(Optional[str])
        assert is_optional_type(Union[str, None])
        # Only test union syntax on Python 3.10+
        if sys.version_info >= (3, 10):
            assert is_optional_type(str | None)

        assert not is_optional_type(str)
        assert not is_optional_type(Union[str, int])
        assert not is_optional_type(list[str])

    @pytest.mark.unit
    def test_unwrap_optional(self):
        """Test unwrap_optional function."""
        assert unwrap_optional(Optional[str]) is str
        assert unwrap_optional(Union[str, None]) is str
        # Only test union syntax on Python 3.10+
        if sys.version_info >= (3, 10):
            assert unwrap_optional(str | None) is str

        # Non-optional types return unchanged
        assert unwrap_optional(str) is str
        assert unwrap_optional(list[str]) is list[str]

    @pytest.mark.unit
    def test_complex_optional_types(self):
        """Test handling complex optional types."""
        # Optional of generic
        assert is_optional_type(Optional[list[str]])
        assert unwrap_optional(Optional[list[str]]) == list[str]

        # Multiple unions with None
        union_type = Union[str, int, None]
        assert is_optional_type(union_type)

        # Nested optionals (though unusual)
        assert is_optional_type(Optional[Optional[str]])
