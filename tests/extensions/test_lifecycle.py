"""Tests for lifecycle extension."""

import asyncio
import pytest

from whiskey import Application, Initializable, Disposable
from whiskey.extensions import lifecycle_extension


class TestLifecycleExtension:
    """Test lifecycle extension functionality."""
    
    @pytest.mark.unit
    async def test_parallel_startup(self):
        """Test components start in parallel when possible."""
        app = Application().use(lifecycle_extension)
        startup_order = []
        
        # Independent components that can start in parallel
        @app.component
        @app.priority(10)
        class Service1(Initializable):
            async def initialize(self):
                startup_order.append("service1_start")
                await asyncio.sleep(0.1)
                startup_order.append("service1_end")
        
        @app.component  
        @app.priority(10)
        class Service2(Initializable):
            async def initialize(self):
                startup_order.append("service2_start")
                await asyncio.sleep(0.1)
                startup_order.append("service2_end")
        
        # Dependent component
        @app.component
        @app.requires(Service1, Service2)
        class Service3(Initializable):
            def __init__(self, s1: Service1, s2: Service2):
                self.s1 = s1
                self.s2 = s2
                
            async def initialize(self):
                startup_order.append("service3")
        
        async with app.lifespan():
            # Check that service1 and service2 started in parallel
            # The first 4 items should be the starts and ends of service1/2 in some order
            starts_and_ends = startup_order[:4]
            assert "service1_start" in starts_and_ends
            assert "service2_start" in starts_and_ends
            assert "service1_end" in starts_and_ends
            assert "service2_end" in starts_and_ends
            
            # Service3 should be last
            assert startup_order[4] == "service3"
    
    @pytest.mark.unit
    async def test_retry_mechanism(self):
        """Test component retry on failure."""
        app = Application().use(lifecycle_extension)
        attempt_count = 0
        
        @app.component
        @app.retry(max_retries=3, delay=0.01)
        class FlakyService(Initializable):
            async def initialize(self):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count < 3:
                    raise ConnectionError("Not ready yet")
        
        async with app.lifespan():
            assert attempt_count == 3  # Failed twice, succeeded on third
    
    @pytest.mark.unit
    async def test_critical_component_failure(self):
        """Test that critical component failure stops startup."""
        app = Application().use(lifecycle_extension)
        
        @app.component
        @app.critical
        @app.retry(max_retries=2, delay=0.01)
        class CriticalService(Initializable):
            async def initialize(self):
                raise RuntimeError("Critical failure")
        
        @app.component
        class NormalService:
            pass
        
        with pytest.raises(RuntimeError, match="Critical component.*failed to start"):
            await app.startup()
    
    @pytest.mark.unit
    async def test_non_critical_component_failure(self):
        """Test that non-critical component failure doesn't stop startup."""
        app = Application().use(lifecycle_extension)
        events = []
        
        @app.on("component.failed")
        async def on_failed(data):
            events.append(data)
        
        @app.component
        @app.retry(max_retries=1, delay=0.01)
        class OptionalService(Initializable):
            async def initialize(self):
                raise RuntimeError("Optional service failed")
        
        @app.component
        class RequiredService:
            pass
        
        async with app.lifespan():
            # Should complete despite optional service failure
            assert len(events) == 1
            assert not events[0]["critical"]
    
    @pytest.mark.unit
    async def test_health_checks(self):
        """Test component health checking."""
        app = Application().use(lifecycle_extension)
        
        @app.component
        class HealthyService:
            async def health_check(self):
                return {"status": "healthy", "message": "All good"}
        
        @app.component
        class DegradedService:
            def healthcheck(self):  # Alternative method name
                return {"status": "degraded", "message": "Running slow"}
        
        @app.component
        class UnhealthyService:
            async def is_healthy(self):  # Another alternative
                return False
        
        async with app.lifespan():
            health = await app.lifecycle_manager.check_all_health()
            
            assert health[HealthyService].status == "healthy"
            assert health[DegradedService].status == "degraded"
            assert health[UnhealthyService].status == "unhealthy"
    
    @pytest.mark.unit
    async def test_readiness_checks(self):
        """Test readiness check system."""
        app = Application().use(lifecycle_extension)
        
        @app.on_ready
        async def setup_checks():
            app.add_readiness_check("database", lambda: True)
            app.add_readiness_check("cache", lambda: False)
            
            async def async_check():
                await asyncio.sleep(0.01)
                return True
            app.add_readiness_check("async_service", async_check)
        
        async with app.lifespan():
            ready, results = await app.check_readiness()
            
            assert not ready  # Not ready because cache check failed
            assert results["database"]["ready"] is True
            assert results["cache"]["ready"] is False
            assert results["async_service"]["ready"] is True
    
    @pytest.mark.unit
    async def test_dependency_graph_building(self):
        """Test dependency graph construction."""
        app = Application().use(lifecycle_extension)
        
        @app.component
        class ServiceA:
            pass
        
        @app.component
        @app.requires(ServiceA)
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a
        
        @app.component
        @app.requires(ServiceA, ServiceB)
        class ServiceC:
            def __init__(self, a: ServiceA, b: ServiceB):
                self.a = a
                self.b = b
        
        async with app.lifespan():
            manager = app.lifecycle_manager
            
            # Check dependencies
            assert ServiceA in manager.dependency_graph[ServiceB].dependencies
            assert ServiceA in manager.dependency_graph[ServiceC].dependencies
            assert ServiceB in manager.dependency_graph[ServiceC].dependencies
            
            # Check dependents
            assert ServiceB in manager.dependency_graph[ServiceA].dependents
            assert ServiceC in manager.dependency_graph[ServiceA].dependents
            assert ServiceC in manager.dependency_graph[ServiceB].dependents
            
            # Check startup order
            order = manager.startup_order
            assert order.index(ServiceA) < order.index(ServiceB)
            assert order.index(ServiceB) < order.index(ServiceC)
    
    @pytest.mark.unit
    async def test_graceful_shutdown(self):
        """Test components shut down in reverse order."""
        app = Application().use(lifecycle_extension)
        shutdown_order = []
        
        class TrackedDisposable(Disposable):
            def __init__(self, name):
                self.name = name
                
            async def dispose(self):
                shutdown_order.append(self.name)
        
        @app.component
        class ServiceA(TrackedDisposable):
            def __init__(self):
                super().__init__("A")
        
        @app.component
        @app.requires(ServiceA)
        class ServiceB(TrackedDisposable):
            def __init__(self, a: ServiceA):
                super().__init__("B")
                self.a = a
        
        @app.component
        @app.requires(ServiceB)
        class ServiceC(TrackedDisposable):
            def __init__(self, b: ServiceB):
                super().__init__("C")
                self.b = b
        
        async with app.lifespan():
            pass  # Just let it start and stop
        
        # Should shutdown in reverse dependency order
        assert shutdown_order == ["C", "B", "A"]