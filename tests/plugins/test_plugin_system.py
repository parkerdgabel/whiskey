"""Tests for the Whiskey plugin system."""

import pytest

from whiskey import Application, ApplicationConfig, Container
from whiskey.plugins import (
    BasePlugin,
    PluginDependencyError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginRegistry,
    get_plugin_registry,
    register_plugin_manually,
)
from whiskey.plugins.testing import MockService, create_test_plugin


class TestPluginRegistry:
    """Test the plugin registry."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry."""
        registry = PluginRegistry()
        return registry
    
    def test_register_plugin(self, registry):
        """Test registering a plugin."""
        plugin_class = create_test_plugin("test1")
        from whiskey.plugins import PluginMetadata
        
        metadata = PluginMetadata(
            name="test1",
            version="1.0.0",
            description="Test plugin",
            plugin_class=plugin_class,
        )
        
        registry.register_plugin(metadata)
        assert len(registry.list_plugins()) == 1
        assert registry.get_plugin("test1") == metadata
    
    def test_register_duplicate_plugin(self, registry):
        """Test registering duplicate plugins raises error."""
        plugin_class = create_test_plugin("test1")
        from whiskey.plugins import PluginMetadata
        
        metadata = PluginMetadata(
            name="test1",
            version="1.0.0",
            description="Test plugin",
            plugin_class=plugin_class,
        )
        
        registry.register_plugin(metadata)
        
        with pytest.raises(PluginError, match="already registered"):
            registry.register_plugin(metadata)
    
    def test_get_nonexistent_plugin(self, registry):
        """Test getting a non-existent plugin raises error."""
        with pytest.raises(PluginNotFoundError):
            registry.get_plugin("nonexistent")
    
    def test_load_plugin(self, registry):
        """Test loading a plugin."""
        services_registered = []
        
        def register(container):
            services_registered.append("registered")
            container.register_singleton(MockService)
        
        plugin_class = create_test_plugin("test1", register_func=register)
        from whiskey.plugins import PluginMetadata
        
        metadata = PluginMetadata(
            name="test1",
            version="1.0.0",
            description="Test plugin",
            plugin_class=plugin_class,
        )
        
        registry.register_plugin(metadata)
        plugin = registry.load_plugin("test1")
        
        assert plugin is not None
        assert plugin.name == "test1"
        assert metadata.loaded is True
        assert metadata.instance == plugin
    
    def test_resolve_dependencies_simple(self, registry):
        """Test resolving simple plugin dependencies."""
        # Create plugins with dependencies
        plugin1 = create_test_plugin("plugin1")
        plugin2 = create_test_plugin("plugin2")
        plugin3 = create_test_plugin("plugin3")
        
        # plugin3 depends on plugin2, plugin2 depends on plugin1
        class Plugin3WithDeps(plugin3):
            @property
            def dependencies(self):
                return ["plugin2"]
        
        class Plugin2WithDeps(plugin2):
            @property
            def dependencies(self):
                return ["plugin1"]
        
        from whiskey.plugins import PluginMetadata
        
        # Register in any order
        registry.register_plugin(PluginMetadata(
            name="plugin3",
            version="1.0.0",
            description="",
            plugin_class=Plugin3WithDeps,
        ))
        registry.register_plugin(PluginMetadata(
            name="plugin1",
            version="1.0.0",
            description="",
            plugin_class=plugin1,
        ))
        registry.register_plugin(PluginMetadata(
            name="plugin2",
            version="1.0.0",
            description="",
            plugin_class=Plugin2WithDeps,
        ))
        
        # Resolve dependencies
        order = registry.resolve_dependencies()
        
        # Check order is correct
        assert order.index("plugin1") < order.index("plugin2")
        assert order.index("plugin2") < order.index("plugin3")
    
    def test_circular_dependency_detection(self, registry):
        """Test that circular dependencies are detected."""
        # Create plugins with circular dependencies
        plugin1 = create_test_plugin("plugin1")
        plugin2 = create_test_plugin("plugin2")
        
        class Plugin1Circular(plugin1):
            @property
            def dependencies(self):
                return ["plugin2"]
        
        class Plugin2Circular(plugin2):
            @property
            def dependencies(self):
                return ["plugin1"]
        
        from whiskey.plugins import PluginMetadata
        
        registry.register_plugin(PluginMetadata(
            name="plugin1",
            version="1.0.0",
            description="",
            plugin_class=Plugin1Circular,
        ))
        registry.register_plugin(PluginMetadata(
            name="plugin2",
            version="1.0.0",
            description="",
            plugin_class=Plugin2Circular,
        ))
        
        with pytest.raises(PluginDependencyError, match="Circular dependency"):
            registry.resolve_dependencies()
    
    def test_missing_dependency(self, registry):
        """Test that missing dependencies are detected."""
        plugin1 = create_test_plugin("plugin1")
        
        class Plugin1WithMissingDep(plugin1):
            @property
            def dependencies(self):
                return ["nonexistent"]
        
        from whiskey.plugins import PluginMetadata
        
        registry.register_plugin(PluginMetadata(
            name="plugin1",
            version="1.0.0",
            description="",
            plugin_class=Plugin1WithMissingDep,
        ))
        
        with pytest.raises(PluginDependencyError, match="not found"):
            registry.resolve_dependencies()


class TestPluginIntegration:
    """Test plugin integration with the application."""
    
    @pytest.fixture
    def clean_registry(self):
        """Ensure clean plugin registry."""
        registry = get_plugin_registry()
        registry.clear()
        yield registry
        registry.clear()
    
    async def test_plugin_lifecycle(self, clean_registry):
        """Test full plugin lifecycle."""
        # Track lifecycle events
        events = []
        
        def register(container):
            events.append("register")
            container.register_singleton(MockService, instance=MockService("test"))
        
        def initialize(app):
            events.append("initialize")
            
            @app.on_startup
            async def plugin_startup():
                events.append("startup")
            
            @app.on_shutdown
            async def plugin_shutdown():
                events.append("shutdown")
        
        # Create and register plugin
        plugin_class = create_test_plugin(
            "lifecycle",
            register_func=register,
            initialize_func=initialize,
        )
        register_plugin_manually("lifecycle", plugin_class)
        
        # Create app with plugin
        app = Application(ApplicationConfig(
            plugins=["lifecycle"],
            auto_discover=False,
        ))
        
        # Run lifecycle
        async with app.lifespan():
            # Check service is available
            service = await app.container.resolve(MockService)
            assert service.value == "test"
        
        # Check events occurred in correct order
        assert events == ["register", "initialize", "startup", "shutdown"]
    
    async def test_plugin_event_handlers(self, clean_registry):
        """Test plugin event handlers with DI."""
        from dataclasses import dataclass
        
        @dataclass
        class TestEvent:
            value: str
        
        received_events = []
        
        def initialize(app):
            @app.on(TestEvent)
            async def handle_test_event(event: TestEvent, service: MockService):
                received_events.append((event.value, service.value))
        
        def register(container):
            container.register_singleton(MockService, instance=MockService("injected"))
        
        # Create and register plugin
        plugin_class = create_test_plugin(
            "events",
            register_func=register,
            initialize_func=initialize,
        )
        register_plugin_manually("events", plugin_class)
        
        # Create app
        app = Application(ApplicationConfig(
            plugins=["events"],
            auto_discover=False,
        ))
        
        async with app.lifespan():
            # Emit event
            await app.event_bus.emit(TestEvent("test"))
            
            # Wait for processing
            import asyncio
            await asyncio.sleep(0.1)
        
        # Check handler received event with injected service
        assert len(received_events) == 1
        assert received_events[0] == ("test", "injected")
    
    async def test_plugin_middleware(self, clean_registry):
        """Test plugin middleware registration."""
        from typing import Any, Callable
        
        processed = []
        
        class TestMiddleware:
            async def process(self, event: Any, next: Callable):
                processed.append(f"before:{type(event).__name__}")
                result = await next(event)
                processed.append(f"after:{type(event).__name__}")
                return result
        
        def initialize(app):
            @app.middleware
            class PluginMiddleware(TestMiddleware):
                pass
        
        # Create and register plugin
        plugin_class = create_test_plugin(
            "middleware",
            initialize_func=initialize,
        )
        register_plugin_manually("middleware", plugin_class)
        
        # Create app
        app = Application(ApplicationConfig(
            plugins=["middleware"],
            auto_discover=False,
        ))
        
        async with app.lifespan():
            # Register a simple handler
            @app.on("test")
            async def handler(event):
                processed.append("handler")
            
            # Emit event
            await app.event_bus.emit("test")
            
            # Wait for processing
            import asyncio
            await asyncio.sleep(0.1)
        
        # Check middleware wrapped the handler
        assert processed == ["before:str", "handler", "after:str"]
    
    async def test_plugin_background_tasks(self, clean_registry):
        """Test plugin background tasks."""
        task_runs = []
        
        def initialize(app):
            @app.task(interval=0.05, run_immediately=True)
            async def plugin_task(service: MockService):
                task_runs.append(service.value)
        
        def register(container):
            container.register_singleton(MockService, instance=MockService("task"))
        
        # Create and register plugin
        plugin_class = create_test_plugin(
            "tasks",
            register_func=register,
            initialize_func=initialize,
        )
        register_plugin_manually("tasks", plugin_class)
        
        # Create app
        app = Application(ApplicationConfig(
            plugins=["tasks"],
            auto_discover=False,
        ))
        
        async with app.lifespan():
            # Wait for task to run a few times
            import asyncio
            await asyncio.sleep(0.2)
        
        # Check task ran multiple times with injected service
        assert len(task_runs) >= 3
        assert all(run == "task" for run in task_runs)
    
    async def test_selective_plugin_loading(self, clean_registry):
        """Test selective plugin loading."""
        loaded = []
        
        def create_tracking_plugin(name):
            def register(container):
                loaded.append(name)
            
            return create_test_plugin(name, register_func=register)
        
        # Register multiple plugins
        for name in ["plugin1", "plugin2", "plugin3"]:
            register_plugin_manually(name, create_tracking_plugin(name))
        
        # Load only specific plugins
        app = Application(ApplicationConfig(
            plugins=["plugin1", "plugin3"],
            auto_discover=False,
        ))
        
        async with app.lifespan():
            pass
        
        # Check only selected plugins were loaded
        assert sorted(loaded) == ["plugin1", "plugin3"]
    
    async def test_plugin_exclusion(self, clean_registry):
        """Test plugin exclusion."""
        loaded = []
        
        def create_tracking_plugin(name):
            def register(container):
                loaded.append(name)
            
            return create_test_plugin(name, register_func=register)
        
        # Register multiple plugins
        for name in ["plugin1", "plugin2", "plugin3"]:
            register_plugin_manually(name, create_tracking_plugin(name))
        
        # Exclude specific plugins
        app = Application(ApplicationConfig(
            exclude_plugins=["plugin2"],
            auto_discover=False,
        ))
        
        async with app.lifespan():
            pass
        
        # Check excluded plugin was not loaded
        assert sorted(loaded) == ["plugin1", "plugin3"]