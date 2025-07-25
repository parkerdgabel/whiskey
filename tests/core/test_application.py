"""Tests for the simplified Application class."""

import asyncio
import pytest

from whiskey import Application, ApplicationConfig, Disposable, Initializable


class TestApplication:
    """Test Application functionality."""
    
    @pytest.mark.unit
    def test_application_creation(self):
        """Test basic application creation."""
        app = Application()
        assert app is not None
        assert app.container is not None
        assert isinstance(app.config, ApplicationConfig)
    
    @pytest.mark.unit
    def test_application_with_config(self):
        """Test application with custom config."""
        config = ApplicationConfig(name="TestApp")
        app = Application(config)
        assert app.config.name == "TestApp"
    
    @pytest.mark.unit
    async def test_service_registration(self):
        """Test service registration through app."""
        app = Application()
        
        @app.service
        class TestService:
            def __init__(self):
                self.value = "test"
        
        service = await app.container.resolve(TestService)
        assert service.value == "test"
    
    @pytest.mark.unit
    async def test_lifecycle_hooks(self):
        """Test startup and shutdown hooks."""
        app = Application()
        startup_called = False
        shutdown_called = False
        
        @app.on_startup
        async def startup():
            nonlocal startup_called
            startup_called = True
        
        @app.on_shutdown
        async def shutdown():
            nonlocal shutdown_called
            shutdown_called = True
        
        async with app.lifespan():
            assert startup_called
            assert not shutdown_called
        
        assert shutdown_called
    
    @pytest.mark.unit
    async def test_service_initialization(self):
        """Test automatic service initialization."""
        app = Application()
        initialized = False
        
        @app.service
        class TestService(Initializable):
            async def initialize(self):
                nonlocal initialized
                initialized = True
        
        async with app.lifespan():
            assert initialized
    
    @pytest.mark.unit
    async def test_service_disposal(self):
        """Test automatic service disposal."""
        app = Application()
        disposed = False
        
        @app.service
        class TestService(Disposable):
            async def dispose(self):
                nonlocal disposed
                disposed = True
        
        async with app.lifespan():
            # Force service creation
            await app.container.resolve(TestService)
            assert not disposed
        
        assert disposed
    
    @pytest.mark.unit
    async def test_background_tasks(self):
        """Test background task management."""
        app = Application()
        task_started = False
        task_cancelled = False
        
        @app.task
        async def background_task():
            nonlocal task_started
            task_started = True
            try:
                await asyncio.sleep(10)  # Long running task
            except asyncio.CancelledError:
                nonlocal task_cancelled
                task_cancelled = True
                raise
        
        async with app.lifespan():
            await asyncio.sleep(0.1)  # Let task start
            assert task_started
            assert not task_cancelled
        
        assert task_cancelled
    
    @pytest.mark.unit
    def test_extensions(self):
        """Test extension support."""
        app = Application()
        extension_called = False
        
        def test_extension(app: Application) -> None:
            nonlocal extension_called
            extension_called = True
            app.container[str] = lambda: "from extension"
        
        app.extend(test_extension)
        assert extension_called
        
        result = app.container.resolve_sync(str)
        assert result == "from extension"
    
    @pytest.mark.unit
    def test_use_multiple_extensions(self):
        """Test using multiple extensions."""
        app = Application()
        calls = []
        
        def ext1(app: Application) -> None:
            calls.append("ext1")
        
        def ext2(app: Application) -> None:
            calls.append("ext2")
        
        def ext3(app: Application) -> None:
            calls.append("ext3")
        
        app.use(ext1, ext2, ext3)
        assert calls == ["ext1", "ext2", "ext3"]
    
    @pytest.mark.unit
    def test_extensions_from_config(self):
        """Test extensions loaded from config."""
        extension_called = False
        
        def test_extension(app: Application) -> None:
            nonlocal extension_called
            extension_called = True
        
        config = ApplicationConfig(
            name="TestApp",
            extensions=[test_extension]
        )
        
        app = Application(config)
        assert extension_called
    
    @pytest.mark.unit
    async def test_method_chaining(self):
        """Test method chaining."""
        app = Application()
        
        def ext1(app): pass
        def ext2(app): pass
        
        # Should return self for chaining
        result = app.extend(ext1).use(ext2)
        assert result is app
    
    @pytest.mark.unit
    async def test_sync_hooks(self):
        """Test sync hooks work too."""
        app = Application()
        sync_startup = False
        sync_shutdown = False
        
        @app.on_startup
        def startup():
            nonlocal sync_startup
            sync_startup = True
        
        @app.on_shutdown
        def shutdown():
            nonlocal sync_shutdown
            sync_shutdown = True
        
        async with app.lifespan():
            assert sync_startup
        
        assert sync_shutdown