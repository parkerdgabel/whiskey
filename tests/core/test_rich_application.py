"""Tests for rich IoC Application features."""

import asyncio
import pytest

from whiskey import Application, ApplicationConfig, ComponentMetadata, Initializable, Disposable


class TestRichApplication:
    """Test rich Application functionality."""
    
    @pytest.mark.unit
    async def test_component_decorator_aliases(self):
        """Test different component registration decorators."""
        app = Application()
        
        @app.component
        class Component1:
            pass
            
        @app.provider
        class Component2:
            pass
            
        @app.managed
        class Component3:
            pass
            
        @app.system
        class Component4:
            pass
        
        # All should be registered
        assert Component1 in app.container
        assert Component2 in app.container
        assert Component3 in app.container
        assert Component4 in app.container
    
    @pytest.mark.unit
    async def test_component_metadata(self):
        """Test component metadata system."""
        app = Application()
        
        @app.priority(10)
        @app.provides("database", "storage")
        @app.requires(str, int)
        @app.critical
        @app.component
        class TestComponent:
            pass
        
        metadata = app.get_metadata(TestComponent)
        assert metadata is not None
        assert metadata.priority == 10
        assert metadata.provides == {"database", "storage"}
        assert metadata.requires == {str, int}
        assert metadata.critical is True
    
    @pytest.mark.unit
    async def test_event_system(self):
        """Test built-in event emitter."""
        app = Application()
        events_received = []
        
        @app.on("test.event")
        async def handler1(data):
            events_received.append(("handler1", data))
        
        @app.on("test.*")  # Wildcard
        async def handler2(data):
            events_received.append(("handler2", data))
        
        await app.emit("test.event", {"value": 1})
        await app.emit("test.other", {"value": 2})
        
        assert len(events_received) == 3
        assert ("handler1", {"value": 1}) in events_received
        assert ("handler2", {"value": 1}) in events_received
        assert ("handler2", {"value": 2}) in events_received
    
    @pytest.mark.unit
    async def test_rich_lifecycle_phases(self):
        """Test all lifecycle phases execute in order."""
        app = Application()
        phases = []
        
        @app.on_configure
        async def configure():
            phases.append("configure")
        
        @app.before_startup
        async def before_startup():
            phases.append("before_startup")
        
        @app.on_startup
        async def startup():
            phases.append("startup")
        
        @app.after_startup
        async def after_startup():
            phases.append("after_startup")
        
        @app.on_ready
        async def ready():
            phases.append("ready")
        
        @app.before_shutdown
        async def before_shutdown():
            phases.append("before_shutdown")
        
        @app.on_shutdown
        async def shutdown():
            phases.append("shutdown")
        
        @app.after_shutdown
        async def after_shutdown():
            phases.append("after_shutdown")
        
        async with app.lifespan():
            assert phases[:5] == ["configure", "before_startup", "startup", "after_startup", "ready"]
        
        assert phases == [
            "configure", "before_startup", "startup", "after_startup", "ready",
            "before_shutdown", "shutdown", "after_shutdown"
        ]
    
    @pytest.mark.unit
    async def test_error_handling(self):
        """Test error lifecycle hooks."""
        app = Application()
        errors_caught = []
        
        @app.on_error
        async def error_handler(error_data):
            errors_caught.append(error_data)
        
        @app.on_startup
        async def failing_startup():
            raise ValueError("Startup failed")
        
        with pytest.raises(ValueError):
            await app.startup()
        
        assert len(errors_caught) == 1
        assert errors_caught[0]["message"] == "Startup failed"
        assert errors_caught[0]["phase"] == "startup"
    
    @pytest.mark.unit
    async def test_extension_hooks(self):
        """Test extension API."""
        app = Application()
        
        # Test adding lifecycle phase
        app.add_lifecycle_phase("custom", after="startup")
        assert "custom" in app._lifecycle_phases
        assert app._lifecycle_phases.index("custom") == app._lifecycle_phases.index("startup") + 1
        
        # Test adding decorator
        def test_decorator(cls):
            cls.test_attr = True
            return cls
        
        app.add_decorator("test_dec", test_decorator)
        assert hasattr(app, "test_dec")
        
        @app.test_dec
        class TestClass:
            pass
        
        assert TestClass.test_attr is True
    
    @pytest.mark.unit
    async def test_get_components_by_metadata(self):
        """Test querying components by metadata."""
        app = Application()
        
        @app.provides("database")
        @app.component
        class DB1:
            pass
        
        @app.provides("database", "cache")
        @app.component
        class DB2:
            pass
        
        @app.provides("email")
        @app.component
        class Email:
            pass
        
        # Test get by provides
        db_components = app.get_components_providing("database")
        assert len(db_components) == 2
        assert DB1 in db_components
        assert DB2 in db_components
        
        cache_components = app.get_components_providing("cache")
        assert len(cache_components) == 1
        assert DB2 in cache_components
    
    @pytest.mark.unit
    async def test_lifecycle_events(self):
        """Test that lifecycle events are emitted."""
        app = Application()
        events = []
        
        @app.on("application.ready")
        async def on_ready():
            events.append("ready")
        
        @app.on("application.stopping")
        async def on_stopping():
            events.append("stopping")
        
        async with app.lifespan():
            assert "ready" in events
        
        assert "stopping" in events