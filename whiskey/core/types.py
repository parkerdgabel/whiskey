"""Core type definitions for Whiskey framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Protocol,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from typing_extensions import ParamSpec, TypeAlias, runtime_checkable

T = TypeVar("T")
P = ParamSpec("P")

# Type aliases
ServiceKey: TypeAlias = Union[type[T], str]
ServiceFactory: TypeAlias = Callable[..., T]
ServiceProvider: TypeAlias = Callable[..., Any]


class ScopeType(str, Enum):
    """Core scope types. Additional scopes can be registered as strings."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"


@dataclass
class ServiceDescriptor:
    """Describes a service registration."""

    service_type: type[Any]
    implementation: type[Any] | None = None
    factory: ServiceFactory | None = None
    instance: Any | None = None
    scope: ScopeType | str = ScopeType.TRANSIENT
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    dependencies: list[ServiceKey] = field(default_factory=list)

    def __post_init__(self):
        if not any([self.implementation, self.factory, self.instance]):
            raise ValueError(
                "ServiceDescriptor must have either implementation, factory, or instance"
            )


@dataclass
class InjectionPoint:
    """Represents a point where dependency injection occurs."""

    parameter_name: str
    service_key: ServiceKey
    is_optional: bool = False
    is_list: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Injectable(Protocol):
    """Protocol for injectable types."""

    __whiskey_injectable__: bool = True


@runtime_checkable
class Disposable(Protocol):
    """Protocol for services that need cleanup."""

    async def dispose(self) -> None:
        """Clean up resources."""
        ...


@runtime_checkable
class Initializable(Protocol):
    """Protocol for services that need initialization."""

    async def initialize(self) -> None:
        """Initialize the service."""
        ...


@dataclass
class ResolverContext:
    """Context for dependency resolution."""

    container: Any  # Avoid circular import
    scope: Any  # Scope instance
    resolved: set[ServiceKey] = field(default_factory=set)
    stack: list[ServiceKey] = field(default_factory=list)
    parent: ResolverContext | None = None

    def create_child(self) -> ResolverContext:
        """Create a child context for nested resolution."""
        return ResolverContext(
            container=self.container,
            scope=self.scope,
            resolved=self.resolved.copy(),
            stack=self.stack.copy(),
            parent=self,
        )


def is_generic_type(tp: type) -> bool:
    """Check if a type is generic."""
    return get_origin(tp) is not None


def get_type_args(tp: type) -> tuple:
    """Get type arguments for a generic type."""
    return get_args(tp)


def is_optional_type(tp: type) -> bool:
    """Check if a type is Optional[T]."""
    origin = get_origin(tp)
    if origin is Union:
        args = get_args(tp)
        return type(None) in args
    # Handle Python 3.10+ union syntax (X | None)
    if hasattr(tp, "__class__") and hasattr(tp.__class__, "__name__"):
        if tp.__class__.__name__ == "UnionType":
            import types
            if isinstance(tp, types.UnionType):
                args = get_args(tp)
                return type(None) in args
    return False


def unwrap_optional(tp: type) -> type:
    """Get the inner type from Optional[T]."""
    if is_optional_type(tp):
        args = get_args(tp)
        return next(arg for arg in args if arg is not type(None))
    return tp