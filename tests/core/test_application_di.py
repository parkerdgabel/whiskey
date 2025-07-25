"""Tests for dependency injection at framework boundaries."""

import asyncio
import pytest

from whiskey import Application, inject


class TestApplicationDI:
    """Test dependency injection in Application class."""
    
    @pytest.mark.unit
    async def test_main_function_injection(self):
        """Test @inject works with main function."""
        app = Application()
        
        class TestService:
            def __init__(self):
                self.called = False
                
            def process(self):
                self.called = True
                
        app.container.register(TestService, scope="singleton")
        
        @inject
        async def main(service: TestService):
            service.process()
            
        # Run the app with injected main
        async def run_test():
            async with app.lifespan():
                app.container[Application] = app
                await main()
                
        await run_test()
        
        # Verify service was injected and called
        service = await app.container.resolve(TestService)
        assert service.called
    
    @pytest.mark.unit
    async def test_event_handler_injection(self):
        """Test @inject works with event handlers."""
        app = Application()
        events_processed = []
        
        class EventProcessor:
            def process(self, event_data):
                events_processed.append(event_data)
                
        app.container[EventProcessor] = EventProcessor()
        
        @app.on("test.event")
        @inject
        async def handle_event(data: dict, processor: EventProcessor):
            processor.process(data)
            
        async with app.lifespan():
            await app.emit("test.event", {"id": 1})
            
        assert events_processed == [{"id": 1}]
    
    @pytest.mark.unit
    async def test_lifecycle_hook_injection(self):
        """Test @inject works with lifecycle hooks."""
        app = Application()
        startup_called = False
        ready_called = False
        
        class StartupService:
            def initialize(self):
                nonlocal startup_called
                startup_called = True
                
        class ReadyService:
            def mark_ready(self):
                nonlocal ready_called
                ready_called = True
                
        app.container[StartupService] = StartupService()
        app.container[ReadyService] = ReadyService()
        
        @app.on_startup
        @inject
        async def startup_hook(service: StartupService):
            service.initialize()
            
        @app.on_ready
        @inject
        async def ready_hook(service: ReadyService):
            service.mark_ready()
            
        async with app.lifespan():
            pass
            
        assert startup_called
        assert ready_called
    
    @pytest.mark.unit
    async def test_background_task_injection(self):
        """Test @inject works with background tasks."""
        app = Application()
        task_runs = []
        
        class TaskService:
            def run(self, count):
                task_runs.append(count)
                
        app.container[TaskService] = TaskService()
        
        run_count = 0
        task_should_run = True
        
        @app.task
        @inject
        async def background_task(service: TaskService):
            nonlocal run_count, task_should_run
            while task_should_run and run_count < 3:
                service.run(run_count)
                run_count += 1
                await asyncio.sleep(0.01)
                
        async with app.lifespan():
            await asyncio.sleep(0.05)
            task_should_run = False
            
        assert task_runs == [0, 1, 2]
    
    @pytest.mark.unit
    async def test_app_main_decorator(self):
        """Test @app.main decorator works."""
        app = Application()
        main_called = False
        
        class MainService:
            def start(self):
                nonlocal main_called
                main_called = True
                
        app.container[MainService] = MainService()
        
        @app.main
        @inject
        async def main(service: MainService):
            service.start()
            
        # Simulate app.run() behavior
        async def simulate_run():
            async with app.lifespan():
                main_func = getattr(app, '_main_func', None)
                assert main_func is not None
                app.container[Application] = app
                await main_func()
                
        await simulate_run()
        assert main_called
    
    @pytest.mark.unit
    async def test_wildcard_event_injection(self):
        """Test wildcard event handlers with injection."""
        app = Application()
        events = []
        
        class Logger:
            def log(self, event_type, data):
                events.append((event_type, data))
                
        app.container[Logger] = Logger()
        
        @app.on("user.*")
        @inject
        async def log_user_events(data: dict, logger: Logger):
            logger.log("user_event", data)
            
        async with app.lifespan():
            await app.emit("user.created", {"id": 1})
            await app.emit("user.updated", {"id": 2})
            await app.emit("post.created", {"id": 3})  # Should not match
            
        assert events == [
            ("user_event", {"id": 1}),
            ("user_event", {"id": 2})
        ]
    
    @pytest.mark.unit
    async def test_error_handler_injection(self):
        """Test error handlers with injection."""
        app = Application()
        errors_logged = []
        
        class ErrorLogger:
            def log_error(self, error_data):
                errors_logged.append(error_data)
                
        app.container[ErrorLogger] = ErrorLogger()
        
        @app.on_error
        @inject
        async def handle_error(error_data: dict, logger: ErrorLogger):
            logger.log_error(error_data)
            
        @app.on_startup
        async def failing_hook():
            raise ValueError("Test error")
            
        # Start the app and catch the error
        with pytest.raises(ValueError):
            await app.startup()
            
        # Check error was logged
        assert len(errors_logged) == 1
        assert errors_logged[0]["message"] == "Test error"
        assert errors_logged[0]["phase"] == "startup"
    
    @pytest.mark.unit 
    async def test_singleton_sharing_across_boundaries(self):
        """Test singletons are shared across all injection boundaries."""
        app = Application()
        
        class SharedCounter:
            def __init__(self):
                self.count = 0
                
            def increment(self):
                self.count += 1
                
        app.container.register(SharedCounter, scope="singleton")
        
        @app.on_startup
        @inject
        async def startup(counter: SharedCounter):
            counter.increment()  # 1
            
        @app.on("test")
        @inject 
        async def handler(data: dict, counter: SharedCounter):
            counter.increment()  # 2
            
        @app.task
        @inject
        async def task(counter: SharedCounter):
            counter.increment()  # 3
            await asyncio.sleep(0.01)
            
        @inject
        async def main(counter: SharedCounter):
            counter.increment()  # 4
            await app.emit("test", {})
            await asyncio.sleep(0.02)
            
        async def run_test():
            async with app.lifespan():
                app.container[Application] = app
                await main()
                
        await run_test()
        
        # All should share the same instance
        counter = await app.container.resolve(SharedCounter)
        assert counter.count == 4