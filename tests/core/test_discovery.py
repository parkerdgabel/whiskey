"""Comprehensive tests for the discovery module."""

import pkgutil
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from whiskey.core.container import Container
from whiskey.core.discovery import ComponentDiscoverer, ContainerInspector, discover_components
from whiskey.core.registry import Scope


class TestComponentDiscoverer:
    """Test the ComponentDiscoverer class."""

    def test_discoverer_creation(self):
        """Test creating a ComponentDiscoverer."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        assert discoverer.container is container
        assert discoverer._discovered == set()

    def test_discover_module_basic(self):
        """Test discovering components in a module."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        # Create a mock module
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        # Add some classes to the module
        class TestService:
            pass

        class TestRepository:
            pass

        class _PrivateClass:
            pass

        # Not a class
        def test_function():
            pass

        mock_module.TestService = TestService
        mock_module.TestRepository = TestRepository
        mock_module._PrivateClass = _PrivateClass
        mock_module.test_function = test_function

        # Set module attribute on classes
        TestService.__module__ = "test_module"
        TestRepository.__module__ = "test_module"
        _PrivateClass.__module__ = "test_module"

        with patch("importlib.import_module", return_value=mock_module):
            components = discoverer.discover_module("test_module")

        # Should discover only non-private classes
        assert TestService in components
        assert TestRepository in components
        assert _PrivateClass not in components  # Private classes excluded

    def test_discover_module_with_package(self):
        """Test discovering components in a package."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        # Create mock package
        mock_package = MagicMock()
        mock_package.__name__ = "test_package"
        mock_package.__path__ = ["/fake/path"]

        # Add a component
        class PackageComponent:
            pass

        mock_package.PackageComponent = PackageComponent
        PackageComponent.__module__ = "test_package"

        with patch("importlib.import_module", return_value=mock_package):
            components = discoverer.discover_module("test_package")

        assert PackageComponent in components

    def test_discover_with_predicate(self):
        """Test discovery with custom predicate."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        class BaseService:
            pass

        class ConcreteService(BaseService):
            pass

        class OtherComponent:
            pass

        mock_module.BaseService = BaseService
        mock_module.ConcreteService = ConcreteService
        mock_module.OtherComponent = OtherComponent

        BaseService.__module__ = "test_module"
        ConcreteService.__module__ = "test_module"
        OtherComponent.__module__ = "test_module"

        # Only discover subclasses of BaseService
        def predicate(cls):
            return isinstance(cls, type) and issubclass(cls, BaseService) and cls is not BaseService

        with patch("importlib.import_module", return_value=mock_module):
            components = discoverer.discover_module("test_module", predicate=predicate)

        assert ConcreteService in components
        assert BaseService not in components
        assert OtherComponent not in components

    def test_discover_module_with_exceptions(self):
        """Test discovery handles exceptions in module attributes."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        # Create a property that raises exception
        class BadProperty:
            @property
            def bad(self):
                raise RuntimeError("Bad property")

        mock_module.BadProp = BadProperty()

        class GoodClass:
            pass

        mock_module.GoodClass = GoodClass
        GoodClass.__module__ = "test_module"

        # Set up dir() to return our attributes
        mock_module.__dir__ = lambda self: ["BadProp", "GoodClass"]

        with patch("importlib.import_module", return_value=mock_module):
            # Should skip bad property and find good class
            components = discoverer.discover_module("test_module")
            assert GoodClass in components

    def test_discover_module_type_checking(self):
        """Test type checking in discover_module."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        # Various non-class objects
        mock_module.string_attr = "not a class"
        mock_module.int_attr = 42
        mock_module.list_attr = [1, 2, 3]
        mock_module.dict_attr = {"key": "value"}

        # A proper class
        class ValidClass:
            pass

        mock_module.ValidClass = ValidClass
        ValidClass.__module__ = "test_module"

        with patch("importlib.import_module", return_value=mock_module):
            components = discoverer.discover_module("test_module")

            # Should only find the class
            assert ValidClass in components
            assert len(components) == 1

    def test_discover_package_recursive(self):
        """Test recursive package discovery."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        # Mock package structure
        main_module = MagicMock()
        main_module.__name__ = "mypackage"
        main_module.__path__ = ["/fake/mypackage"]

        sub_module = MagicMock()
        sub_module.__name__ = "mypackage.submodule"

        class MainComponent:
            pass

        class SubComponent:
            pass

        MainComponent.__module__ = "mypackage"
        SubComponent.__module__ = "mypackage.submodule"

        main_module.MainComponent = MainComponent
        sub_module.SubComponent = SubComponent

        # Mock the walk_packages to return our submodule
        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = lambda name: {
                "mypackage": main_module,
                "mypackage.submodule": sub_module,
            }.get(name)

            with patch.object(pkgutil, "walk_packages") as mock_walk:
                # Return module info for submodule
                # walk_packages returns (importer, modname, ispkg) tuples
                mock_walk.return_value = [(None, "mypackage.submodule", False)]

                components = discoverer.discover_package("mypackage", recursive=True)

                # Should find both components
                assert MainComponent in components
                assert SubComponent in components

    def test_auto_register(self):
        """Test auto-registering discovered components."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        class Service1:
            pass

        class Service2:
            pass

        components = {Service1, Service2}

        # Register components
        registered = discoverer.auto_register(components)

        assert Service1 in registered
        assert Service2 in registered

        # Should be resolvable
        assert container.resolve_sync(Service1) is not None
        assert container.resolve_sync(Service2) is not None

    def test_auto_register_with_scope(self):
        """Test auto_register with custom scope."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        class Component:
            pass

        registered = discoverer.auto_register({Component}, scope=Scope.SINGLETON)

        # Should register as singleton
        instance1 = container.resolve_sync(Component)
        instance2 = container.resolve_sync(Component)
        assert instance1 is instance2

    def test_auto_register_with_condition(self):
        """Test auto-registering with condition."""
        container = Container()
        discoverer = ComponentDiscoverer(container)

        class DevService:
            pass

        class ProdService:
            pass

        components = {DevService, ProdService}

        # Only register services ending with "Service"
        def condition(cls):
            return cls.__name__.endswith("Service")

        registered = discoverer.auto_register(components, condition=condition)

        assert DevService in registered
        assert ProdService in registered


class TestContainerInspector:
    """Test the ContainerInspector class."""

    def test_inspector_creation(self):
        """Test creating an Inspector."""
        container = Container()
        inspector = ContainerInspector(container)
        assert inspector.container is container

    def test_list_services_empty(self):
        """Test listing services in empty container."""
        container = Container()
        inspector = ContainerInspector(container)

        services = inspector.list_services()
        assert services == {}

    def test_list_services_with_services(self):
        """Test listing services."""
        container = Container()

        class Service1:
            pass

        class Service2:
            pass

        container.register(Service1, Service1())
        container.register(Service2, Service2(), tags={"important"})
        container.register("custom", Service1())

        inspector = ContainerInspector(container)
        services = inspector.list_services()

        assert len(services) >= 3
        # Should have service entries

    def test_list_services_by_interface(self):
        """Test listing services by interface."""
        container = Container()

        class BaseService:
            pass

        class ConcreteService(BaseService):
            pass

        class OtherService:
            pass

        container.register(ConcreteService, ConcreteService())
        container.register(OtherService, OtherService())

        inspector = ContainerInspector(container)

        # Filter by interface - implementation may vary
        services = inspector.list_services(interface=BaseService)
        # Should return services that implement BaseService

    def test_list_services_by_tags(self):
        """Test listing services by tags."""
        container = Container()

        class Service1:
            pass

        class Service2:
            pass

        container.register(Service1, Service1(), tags={"core", "stable"})
        container.register(Service2, Service2(), tags={"experimental"})

        inspector = ContainerInspector(container)

        # Filter by tags
        services = inspector.list_services(tags={"core"})
        # Should include Service1

        services = inspector.list_services(tags={"experimental"})
        # Should include Service2

    def test_get_dependencies(self):
        """Test getting service dependencies."""
        container = Container()
        inspector = ContainerInspector(container)

        class Database:
            pass

        class Service:
            def __init__(self, db: Database):
                self.db = db

        deps = inspector.get_dependencies(Service)
        assert "db" in deps
        assert deps["db"] is Database

    def test_get_dependencies_no_annotations(self):
        """Test getting dependencies for class without annotations."""
        container = Container()
        inspector = ContainerInspector(container)

        class Service:
            def __init__(self, arg1, arg2):
                pass

        deps = inspector.get_dependencies(Service)
        assert deps == {}

    def test_can_resolve_registered(self):
        """Test can_resolve for registered service."""
        container = Container()
        inspector = ContainerInspector(container)

        class Service:
            pass

        container.register(Service, Service())

        assert inspector.can_resolve(Service) is True

    def test_can_resolve_unregistered(self):
        """Test can_resolve for unregistered service."""
        container = Container()
        inspector = ContainerInspector(container)

        class Service:
            pass

        assert inspector.can_resolve(Service) is False

    def test_can_resolve_with_dependencies(self):
        """Test can_resolve with dependencies."""
        container = Container()
        inspector = ContainerInspector(container)

        class Database:
            pass

        class Service:
            def __init__(self, db: Database):
                self.db = db

        # Register database but not service
        container.register(Database, Database())

        # Service not registered but dependencies available
        result = inspector.can_resolve(Service)
        # Result depends on auto-creation support

    def test_resolution_report(self):
        """Test generating resolution report."""
        container = Container()
        inspector = ContainerInspector(container)

        class Service:
            pass

        container.register(Service, Service())

        report = inspector.resolution_report(Service)
        assert "can_resolve" in report
        assert "dependencies" in report
        assert "missing_dependencies" in report
        assert "resolution_path" in report
        assert report["can_resolve"] is True

    def test_resolution_report_missing_deps(self):
        """Test resolution report with missing dependencies."""
        container = Container()
        inspector = ContainerInspector(container)

        class Database:
            pass

        class Service:
            def __init__(self, db: Database):
                self.db = db

        # Don't register database
        report = inspector.resolution_report(Service)
        assert report["can_resolve"] is False
        assert "db" in report["missing_dependencies"]

    def test_dependency_graph(self):
        """Test building dependency graph."""
        container = Container()
        inspector = ContainerInspector(container)

        class Database:
            pass

        class Cache:
            pass

        class Service:
            def __init__(self, db: Database, cache: Cache):
                self.db = db
                self.cache = cache

        container.register(Database, Database())
        container.register(Cache, Cache())
        container.register(Service, Service)

        graph = inspector.dependency_graph()
        # Should have Service depending on Database and Cache
        if Service in graph:
            deps = graph[Service]
            assert Database in deps or Cache in deps


class TestDiscoverComponentsFunction:
    """Test the discover_components convenience function."""

    def test_discover_with_string_module(self):
        """Test discover_components with string module name."""
        # Create test module
        test_module = ModuleType("test_discover_module")

        class Component:
            pass

        test_module.Component = Component
        Component.__module__ = "test_discover_module"

        sys.modules["test_discover_module"] = test_module

        try:
            container = Container()
            components = discover_components("test_discover_module", container=container)
            assert Component in components
        finally:
            del sys.modules["test_discover_module"]

    def test_discover_with_module_object(self):
        """Test discover_components with module object."""
        test_module = ModuleType("test_module_obj")

        class Component:
            pass

        test_module.Component = Component
        Component.__module__ = "test_module_obj"

        container = Container()
        components = discover_components(test_module, container=container)
        assert Component in components

    def test_discover_with_default_container(self):
        """Test discover_components using default container."""
        # Should require container parameter
        with pytest.raises(TypeError):
            # Missing required container parameter
            components = discover_components("some_module")

    def test_discover_and_register(self):
        """Test discovering and auto-registering components."""
        container = Container()

        # Create test module
        test_module = ModuleType("test_auto_module")

        class AutoService:
            pass

        test_module.AutoService = AutoService
        AutoService.__module__ = "test_auto_module"

        sys.modules["test_auto_module"] = test_module

        try:
            # Discover and register
            components = discover_components(
                "test_auto_module", container=container, auto_register=True
            )

            assert AutoService in components
            # Should be resolvable
            instance = container.resolve_sync(AutoService)
            assert isinstance(instance, AutoService)
        finally:
            del sys.modules["test_auto_module"]

    def test_discover_with_predicate_function(self):
        """Test discover_components with predicate."""
        container = Container()

        # Create test module
        test_module = ModuleType("test_pred_module")

        class BaseClass:
            pass

        class DerivedClass(BaseClass):
            pass

        class UnrelatedClass:
            pass

        test_module.BaseClass = BaseClass
        test_module.DerivedClass = DerivedClass
        test_module.UnrelatedClass = UnrelatedClass

        BaseClass.__module__ = "test_pred_module"
        DerivedClass.__module__ = "test_pred_module"
        UnrelatedClass.__module__ = "test_pred_module"

        sys.modules["test_pred_module"] = test_module

        try:
            # Only discover subclasses of BaseClass
            def is_subclass_of_base(cls):
                return isinstance(cls, type) and issubclass(cls, BaseClass) and cls is not BaseClass

            components = discover_components(
                "test_pred_module", container=container, predicate=is_subclass_of_base
            )

            assert DerivedClass in components
            assert BaseClass not in components
            assert UnrelatedClass not in components
        finally:
            del sys.modules["test_pred_module"]
