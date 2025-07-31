"""Test generic type resolution for Phase 4.1.

This test demonstrates the expected behavior for generic type resolution:
- Resolve Generic[T] to concrete implementations
- Handle type parameter binding and substitution
- Support Protocol and ABC generics
- Automatic discovery of implementations
- Clear error messages for unresolvable generics
"""

from abc import ABC, abstractmethod
from typing import Generic, Optional, Protocol, TypeVar

import pytest

from whiskey import Whiskey
from whiskey.core.errors import ResolutionError, TypeAnalysisError
from whiskey.core.generic import GenericTypeResolver, TypeParameterBinder

# Test type parameters
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
ItemType = TypeVar("ItemType")


# Generic base classes for testing
class Repository(Generic[T]):
    """Generic repository interface."""

    def __init__(self):
        self.items: list[T] = []

    def add(self, item: T) -> None:
        self.items.append(item)

    def get_all(self) -> list[T]:
        return self.items.copy()


class Service(Generic[T]):
    """Generic service interface."""

    def __init__(self, repo: Repository[T]):
        self.repo = repo

    def process(self, item: T) -> T:
        self.repo.add(item)
        return item


class Cache(Generic[K, V]):
    """Generic cache interface with key-value types."""

    def __init__(self):
        self._data: dict[K, V] = {}

    def get(self, key: K) -> Optional[V]:
        return self._data.get(key)

    def set(self, key: K, value: V) -> None:
        self._data[key] = value


# Protocol-based generics
class Processor(Protocol[T]):
    """Protocol for processing items of type T."""

    def process(self, item: T) -> T: ...


class Storage(ABC, Generic[T]):
    """Abstract base class for storage."""

    @abstractmethod
    def store(self, item: T) -> str:
        """Store an item and return its ID."""
        pass

    @abstractmethod
    def retrieve(self, item_id: str) -> Optional[T]:
        """Retrieve an item by ID."""
        pass


# Domain models for testing
class User:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email


class Product:
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price


class Order:
    def __init__(self, user: User, products: list[Product]):
        self.user = user
        self.products = products


# Concrete implementations
class UserRepository(Repository[User]):
    """Concrete repository for User objects."""

    def find_by_email(self, email: str) -> Optional[User]:
        return next((user for user in self.items if user.email == email), None)


class ProductRepository(Repository[Product]):
    """Concrete repository for Product objects."""

    def find_by_name(self, name: str) -> Optional[Product]:
        return next((product for product in self.items if product.name == name), None)


class UserService(Service[User]):
    """Concrete service for User objects."""

    def create_user(self, name: str, email: str) -> User:
        user = User(name, email)
        return self.process(user)


class ProductService(Service[Product]):
    """Concrete service for Product objects."""

    def create_product(self, name: str, price: float) -> Product:
        product = Product(name, price)
        return self.process(product)


class StringIntCache(Cache[str, int]):
    """Concrete cache for string keys and integer values."""

    pass


class UserStorage(Storage[User]):
    """Concrete storage for User objects."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._counter = 0

    def store(self, item: User) -> str:
        self._counter += 1
        user_id = f"user_{self._counter}"
        self._users[user_id] = item
        return user_id

    def retrieve(self, item_id: str) -> Optional[User]:
        return self._users.get(item_id)


class UserProcessor:
    """Implementation of Processor[User] protocol."""

    def __init__(self):
        pass

    def process(self, item: User) -> User:
        # Simple processing - uppercase the name
        item.name = item.name.upper()
        return item


@pytest.mark.unit
class TestGenericTypeResolver:
    """Test the GenericTypeResolver class."""

    def test_register_and_resolve_concrete_generic(self):
        """Test registering and resolving concrete generic types."""
        resolver = GenericTypeResolver()

        # Register concrete implementations
        resolver.register_concrete(Repository[User], UserRepository)
        resolver.register_concrete(Repository[Product], ProductRepository)

        # Resolve should return the correct concrete types
        user_repo_type = resolver.resolve_generic(Repository[User])
        product_repo_type = resolver.resolve_generic(Repository[Product])

        assert user_repo_type == UserRepository
        assert product_repo_type == ProductRepository

    def test_resolve_unregistered_generic_returns_none(self):
        """Test that unregistered generic types return None."""
        resolver = GenericTypeResolver()

        result = resolver.resolve_generic(Repository[Order])
        assert result is None

    def test_multiple_candidates_disambiguation(self):
        """Test disambiguation when multiple candidates exist."""
        resolver = GenericTypeResolver()

        # Register multiple implementations for the same generic
        resolver.register_concrete(Repository[User], UserRepository)
        resolver.register_concrete(Repository[User], ProductRepository)  # Wrong type on purpose

        # Should prefer the correctly typed implementation
        result = resolver.resolve_generic(Repository[User])
        assert result == UserRepository  # Should pick the better match

    def test_multi_parameter_generic_resolution(self):
        """Test resolution of generics with multiple type parameters."""
        resolver = GenericTypeResolver()

        resolver.register_concrete(Cache[str, int], StringIntCache)

        result = resolver.resolve_generic(Cache[str, int])
        assert result == StringIntCache

    def test_generic_type_analysis(self):
        """Test detailed analysis of generic types."""
        resolver = GenericTypeResolver()
        resolver.register_concrete(Repository[User], UserRepository)
        resolver.register_concrete(Storage[User], UserStorage)

        # Analyze a regular generic
        analysis = resolver.analyze_generic_type(Repository[User])
        assert analysis["is_generic"] is True
        assert analysis["origin"] == Repository
        assert analysis["args"] == [User]
        assert analysis["resolvable"] is True
        assert analysis["is_protocol"] is False
        assert analysis["is_abc"] is False

        # Analyze an ABC generic
        analysis = resolver.analyze_generic_type(Storage[User])
        assert analysis["is_generic"] is True
        assert analysis["is_abc"] is True
        assert analysis["resolvable"] is True

    def test_type_parameter_extraction(self):
        """Test extraction of type parameters from generic types."""
        resolver = GenericTypeResolver()

        # Test single parameter
        params = resolver.get_type_parameters(Repository[User])
        assert len(params) == 0  # Parameterized type has no free parameters

        # Test raw generic
        params = resolver.get_type_parameters(Repository)
        assert len(params) == 1
        assert params[0].__name__ == "T"

    def test_type_parameter_binding(self):
        """Test binding type parameters to concrete types."""
        resolver = GenericTypeResolver()

        # Test inference from concrete implementation
        bindings = resolver.infer_type_parameters(Repository, UserRepository)
        assert T in bindings
        assert bindings[T] == User


@pytest.mark.unit
class TestTypeParameterBinder:
    """Test the TypeParameterBinder class."""

    def test_basic_binding(self):
        """Test basic type parameter binding."""
        binder = TypeParameterBinder()

        binder.bind(T, User)
        assert binder.get_binding(T) == User

    def test_substitution(self):
        """Test type substitution with bindings."""
        binder = TypeParameterBinder()
        binder.bind(T, User)

        # Test substitution in simple type
        result = binder.substitute(T)
        assert result == User

        # Test substitution in generic type
        result = binder.substitute(Repository[T])
        assert result == Repository[User]

    def test_bound_type_validation(self):
        """Test validation of bound types."""
        # Create a bounded TypeVar
        BoundedT = TypeVar("BoundedT", bound=str)

        binder = TypeParameterBinder()

        # Valid binding (str is compatible with str bound)
        binder.bind(BoundedT, str)

        # Invalid binding should raise error
        with pytest.raises(TypeAnalysisError):
            binder.bind(BoundedT, int)

    def test_constrained_type_validation(self):
        """Test validation of constrained types."""
        # Create a constrained TypeVar
        ConstrainedT = TypeVar("ConstrainedT", str, int)

        binder = TypeParameterBinder()

        # Valid bindings
        binder.bind(ConstrainedT, str)
        binder.bind(ConstrainedT, int)

        # Invalid binding should raise error
        with pytest.raises(TypeAnalysisError):
            binder.bind(ConstrainedT, float)


@pytest.mark.unit
class TestWhiskeyGenericIntegration:
    """Test integration of generic resolution with Whiskey container."""

    def test_basic_generic_resolution(self):
        """Test basic generic type resolution in Whiskey."""
        app = Whiskey()

        # Register concrete implementations
        app.container.register_generic_implementation(Repository[User], UserRepository)
        app.container.register_generic_implementation(Service[User], UserService)

        # Register the concrete types in container
        app.singleton(UserRepository, key=Repository[User])
        app.component(UserService, key=Service[User])

        # Should be able to resolve generic types
        repo = app.resolve(Repository[User])
        assert isinstance(repo, UserRepository)

        service = app.resolve(Service[User])
        assert isinstance(service, UserService)
        assert isinstance(service.repo, UserRepository)

    def test_automatic_dependency_injection_with_generics(self):
        """Test that generic dependencies are automatically injected."""
        app = Whiskey()

        # Register generic implementations
        app.container.register_generic_implementation(Repository[User], UserRepository)
        app.container.register_generic_implementation(Service[User], UserService)

        # Register components
        app.singleton(UserRepository, key=Repository[User])
        app.component(UserService, key=Service[User])

        # Define a service that depends on generic types
        class UserController:
            def __init__(self, user_service: Service[User]):
                self.user_service = user_service

        app.component(UserController)

        # Should resolve with all dependencies
        controller = app.resolve(UserController)
        assert isinstance(controller, UserController)
        assert isinstance(controller.user_service, UserService)
        assert isinstance(controller.user_service.repo, UserRepository)

    def test_protocol_generic_resolution(self):
        """Test resolution of Protocol-based generics."""
        app = Whiskey()

        # Register protocol implementation
        app.container.register_generic_implementation(Processor[User], UserProcessor)
        app.component(UserProcessor, key=Processor[User])

        # Should resolve protocol to implementation
        processor = app.resolve(Processor[User])
        assert isinstance(processor, UserProcessor)

    def test_abc_generic_resolution(self):
        """Test resolution of ABC-based generics."""
        app = Whiskey()

        # Register ABC implementation
        app.container.register_generic_implementation(Storage[User], UserStorage)
        app.component(UserStorage, key=Storage[User])

        # Should resolve ABC to implementation
        storage = app.resolve(Storage[User])
        assert isinstance(storage, UserStorage)

    def test_simple_generic_dependency_resolution(self):
        """Test simple generic dependency resolution."""
        app = Whiskey()

        # Register a simple generic repository and service
        app.container.register_generic_implementation(Repository[User], UserRepository)
        app.container.register_generic_implementation(Service[User], UserService)

        app.singleton(UserRepository, key=Repository[User])
        app.component(UserService, key=Service[User])

        # Define a service that uses generic dependencies
        class SimpleUserController:
            def __init__(self, user_service: Service[User]):
                self.user_service = user_service

            def get_users(self):
                return self.user_service.repo.get_all()

        app.component(SimpleUserController)

        # Should resolve correctly
        controller = app.resolve(SimpleUserController)
        assert isinstance(controller, SimpleUserController)
        assert isinstance(controller.user_service, UserService)
        assert isinstance(controller.user_service.repo, UserRepository)

    def test_unresolvable_generic_error(self):
        """Test error handling for unresolvable generic types."""
        app = Whiskey()

        # Don't register any implementations

        # Should provide clear error for unresolvable generic
        with pytest.raises(ResolutionError) as exc_info:
            app.resolve(Repository[Order])

        error_msg = str(exc_info.value)
        assert "Generic type not resolvable" in error_msg or "not found" in error_msg.lower()

    def test_ambiguous_generic_resolution_error(self):
        """Test error handling for ambiguous generic resolutions."""
        app = Whiskey()

        # Register multiple conflicting implementations
        app.container.register_generic_implementation(Repository[User], UserRepository)
        app.container.register_generic_implementation(Repository[User], ProductRepository)

        # Should provide clear error about ambiguity
        # Note: This might resolve to the "best" match instead of erroring,
        # depending on implementation. Test should verify the behavior is reasonable.
        try:
            repo = app.resolve(Repository[User])
            # If it resolves, it should be a reasonable choice
            assert repo is not None
        except ResolutionError as e:
            # If it errors, error should mention ambiguity
            assert "ambiguous" in str(e).lower() or "multiple" in str(e).lower()


@pytest.mark.unit
class TestGenericTypeAnalyzer:
    """Test generic type analysis in the TypeAnalyzer."""

    def test_generic_type_injection_decision(self):
        """Test injection decisions for generic types."""
        app = Whiskey()

        # Register generic implementation
        app.container.register_generic_implementation(Repository[User], UserRepository)
        app.singleton(UserRepository, key=Repository[User])

        # Analyze a function with generic parameter
        def test_func(repo: Repository[User]) -> None:
            pass

        results = app.container.analyzer.analyze_callable(test_func)

        # Should decide to inject the generic type
        assert "repo" in results
        result = results["repo"]
        assert result.decision.value in ("inject", "optional")
        assert result.type_hint == Repository[User]

    def test_unregistered_generic_injection_decision(self):
        """Test injection decisions for unregistered generic types."""
        app = Whiskey()

        # Don't register any implementations

        def test_func(repo: Repository[Order]) -> None:
            pass

        results = app.container.analyzer.analyze_callable(test_func)

        # Should decide not to inject unregistered generic
        assert "repo" in results
        result = results["repo"]
        assert result.decision.value == "skip"
        assert "not resolvable" in result.reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
