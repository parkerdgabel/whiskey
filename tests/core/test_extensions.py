"""Tests for the extension system."""

import pytest
from whiskey import Application, singleton


class TestExtensions:
    """Test application extensions."""
    
    def test_extend_method(self):
        """Test extending an application with a function."""
        app = Application()
        
        # Track if extension was called
        called = False
        
        # Define service outside so we can reference it
        @singleton
        class TestService:
            def get_value(self) -> str:
                return "test"
        
        def test_extension(app: Application) -> None:
            nonlocal called
            called = True
            app.container.register_singleton(TestService, TestService)
        
        # Apply extension
        result = app.extend(test_extension)
        
        # Should return self for chaining
        assert result is app
        assert called
        
        # Service should be registered
        service = app.container.resolve_sync(TestService)
        assert service.get_value() == "test"
    
    def test_use_method(self):
        """Test using multiple extensions at once."""
        app = Application()
        
        calls = []
        
        def ext1(app: Application) -> None:
            calls.append("ext1")
            app.container.register_singleton(str, instance="hello", name="msg1")
        
        def ext2(app: Application) -> None:
            calls.append("ext2")
            app.container.register_singleton(str, instance="world", name="msg2")
        
        def ext3(app: Application) -> None:
            calls.append("ext3")
            app.container.register_singleton(str, instance="!", name="msg3")
        
        # Apply multiple extensions
        result = app.use(ext1, ext2, ext3)
        
        # Should return self for chaining
        assert result is app
        
        # All extensions should be called in order
        assert calls == ["ext1", "ext2", "ext3"]
        
        # All services should be registered
        assert app.container.resolve_sync(str, name="msg1") == "hello"
        assert app.container.resolve_sync(str, name="msg2") == "world"
        assert app.container.resolve_sync(str, name="msg3") == "!"
    
    def test_method_chaining(self):
        """Test chaining extend and use methods."""
        app = Application()
        
        def ext1(app): 
            app.container.register_singleton(int, instance=1, name="one")
        
        def ext2(app):
            app.container.register_singleton(int, instance=2, name="two")
        
        def ext3(app):
            app.container.register_singleton(int, instance=3, name="three")
        
        # Chain methods
        result = app.extend(ext1).use(ext2, ext3)
        
        assert result is app
        assert app.container.resolve_sync(int, name="one") == 1
        assert app.container.resolve_sync(int, name="two") == 2
        assert app.container.resolve_sync(int, name="three") == 3
    
    async def test_extensions_in_config(self):
        """Test extensions loaded from ApplicationConfig."""
        from whiskey import ApplicationConfig
        
        calls = []
        
        # Define service outside
        class StartupService:
            def __init__(self):
                self.initialized = True
        
        def startup_extension(app: Application) -> None:
            calls.append("startup")
            app.service(StartupService)
        
        # Create app with extensions in config
        config = ApplicationConfig(
            name="TestApp",
            extensions=[startup_extension]
        )
        app = Application(config)
        
        # Extensions should be applied during startup
        await app.startup()
        
        assert "startup" in calls
        
        # Service should be available
        service = await app.container.resolve(StartupService)
        assert service.initialized
        
        await app.shutdown()
    
    def test_extension_with_app_decorators(self):
        """Test extensions can use app decorators."""
        app = Application()
        
        startup_called = False
        service_registered = False
        
        # Define service outside
        class ExtensionService:
            def __init__(self):
                nonlocal service_registered
                service_registered = True
        
        def full_extension(app: Application) -> None:
            @app.on_startup
            async def startup():
                nonlocal startup_called
                startup_called = True
            
            app.service(ExtensionService)
        
        app.extend(full_extension)
        
        # Startup hooks should be registered (one from @app.on_startup, one from @app.service)
        assert len(app._startup_hooks) == 2
        
        # Service should work when resolved
        service = app.container.resolve_sync(ExtensionService)
        assert service_registered