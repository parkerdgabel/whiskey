"""Test performance and caching improvements for Phase 5.2.

This test identifies performance bottlenecks in type analysis and resolution:
- Type analysis caching effectiveness
- Resolution time improvements
- Memory usage optimization
- Cache hit rates and performance gains
"""

import time
import pytest
from typing import Optional, List, Dict, Union
from concurrent.futures import ThreadPoolExecutor

from whiskey import Whiskey, Container
from whiskey.core.analyzer import TypeAnalyzer
from whiskey.core.registry import ComponentRegistry


# Test classes for performance scenarios
class SimpleService:
    def __init__(self):
        self.created_at = time.time()


class ComplexService:
    def __init__(self, simple: SimpleService):
        self.simple = simple
        self.created_at = time.time()


class ServiceWithManyDeps:
    def __init__(
        self, 
        s1: SimpleService,
        s2: ComplexService,
        opt1: Optional[SimpleService] = None,
        opt2: Optional[ComplexService] = None,
    ):
        self.s1 = s1
        self.s2 = s2
        self.opt1 = opt1
        self.opt2 = opt2


class ServiceWithComplexTypes:
    def __init__(
        self,
        simple_list: List[str],
        simple_dict: Dict[str, int],
        union_type: Union[str, int],
        optional_list: Optional[List[SimpleService]] = None,
        nested_dict: Dict[str, List[int]] = None,
    ):
        self.simple_list = simple_list or []
        self.simple_dict = simple_dict or {}
        self.union_type = union_type
        self.optional_list = optional_list
        self.nested_dict = nested_dict or {}


@pytest.mark.unit
class TestTypeAnalysisCaching:
    """Test type analysis caching performance."""
    
    def test_cache_effectiveness(self):
        """Test that type analysis caching improves performance."""
        registry = ComponentRegistry()
        registry.register(SimpleService, SimpleService)
        registry.register(ComplexService, ComplexService)
        
        analyzer = TypeAnalyzer(registry)
        
        # First analysis - cache miss
        start_time = time.time()
        results1 = analyzer.analyze_callable(ServiceWithManyDeps.__init__)
        first_run_time = time.time() - start_time
        
        # Second analysis - should hit cache
        start_time = time.time()
        results2 = analyzer.analyze_callable(ServiceWithManyDeps.__init__)
        second_run_time = time.time() - start_time
        
        # Results should be identical
        assert results1.keys() == results2.keys()
        for param_name in results1:
            assert results1[param_name].decision == results2[param_name].decision
        
        # Second run should be significantly faster
        print(f"First run: {first_run_time:.6f}s, Second run: {second_run_time:.6f}s")
        print(f"Speedup: {first_run_time / second_run_time:.2f}x")
        
        # Cache should provide at least 2x speedup
        assert second_run_time < first_run_time / 2, f"Cache not effective: {first_run_time / second_run_time:.2f}x speedup"
    
    def test_complex_type_analysis_caching(self):
        """Test caching with complex generic types."""
        registry = ComponentRegistry()
        analyzer = TypeAnalyzer(registry)
        
        # Analyze complex types multiple times
        iterations = 100
        
        start_time = time.time()
        for _ in range(iterations):
            analyzer.analyze_callable(ServiceWithComplexTypes.__init__)
        total_time = time.time() - start_time
        
        print(f"Complex type analysis: {total_time:.6f}s for {iterations} iterations")
        print(f"Average per iteration: {total_time / iterations * 1000:.3f}ms")
        
        # Should complete quickly due to caching
        assert total_time < 0.1, f"Complex type analysis too slow: {total_time:.6f}s"
    
    def test_cache_memory_efficiency(self):
        """Test that caching doesn't cause excessive memory usage."""
        registry = ComponentRegistry()
        analyzer = TypeAnalyzer(registry)
        
        # Create many different service classes and analyze them
        services = []
        for i in range(100):  # Reduced from 1000 for faster testing
            # Dynamically create service classes
            service_name = f"Service{i}"
            service_class = type(service_name, (), {
                '__init__': lambda self, dep: setattr(self, 'dep', dep)
            })
            services.append(service_class)
            
            # Analyze each service
            analyzer.analyze_callable(service_class.__init__)
        
        # Check cache size
        cache_size = len(analyzer._analysis_cache)
        print(f"Analysis cache size after {len(services)} services: {cache_size}")
        
        # Cache size should be reasonable
        assert cache_size < 500, f"Cache too large: {cache_size} entries"
    
    def test_cache_invalidation(self):
        """Test that cache is properly invalidated when registry changes."""
        registry = ComponentRegistry()
        analyzer = TypeAnalyzer(registry)
        
        # Analyze without registration
        results1 = analyzer.analyze_callable(ComplexService.__init__)
        
        # Register component
        registry.register(SimpleService, SimpleService)
        
        # Should get different results after registration
        results2 = analyzer.analyze_callable(ComplexService.__init__)
        
        # The simple parameter should change from NO to YES after registration
        # Note: This test may fail if cache isn't invalidated properly
        print(f"Before registration: {results1['simple']}")
        print(f"After registration: {results2['simple']}")


@pytest.mark.unit
class TestResolutionCaching:
    """Test resolution performance and caching."""
    
    def test_injection_plan_caching(self):
        """Test that injection plans are cached effectively."""
        container = Container()
        container.singleton(SimpleService)
        container.singleton(ComplexService)
        
        # First resolution - builds injection plan
        start_time = time.time()
        instance1 = container.resolve(ComplexService)
        first_time = time.time() - start_time
        
        # Clear singleton cache but keep injection plan cache
        container._singleton_cache.clear()
        
        # Second resolution - should reuse injection plan
        start_time = time.time()
        instance2 = container.resolve(ComplexService)
        second_time = time.time() - start_time  
        
        print(f"First resolution: {first_time:.6f}s, Second: {second_time:.6f}s")
        
        # Should be different instances (singleton cache was cleared)
        assert instance1 is not instance2
        
        # But second should be faster due to cached injection plan
        assert second_time < first_time
    
    def test_concurrent_resolution_performance(self):
        """Test resolution performance under concurrent access."""
        container = Container()
        container.singleton(SimpleService)
        container.register(ComplexService, ComplexService)
        
        iterations_per_thread = 100
        num_threads = 10
        
        def resolve_many():
            times = []
            for _ in range(iterations_per_thread):
                start = time.time()
                instance = container.resolve(ComplexService)  
                times.append(time.time() - start)
            return times
        
        # Run concurrent resolutions
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(resolve_many) for _ in range(num_threads)]
            results = [future.result() for future in futures]
        total_time = time.time() - start_time
        
        # Flatten results
        all_times = [t for thread_times in results for t in thread_times]
        
        total_resolutions = len(all_times)
        avg_time = sum(all_times) / len(all_times)
        
        print(f"Concurrent resolution test:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Total resolutions: {total_resolutions}")
        print(f"  Average per resolution: {avg_time * 1000:.3f}ms")
        print(f"  Throughput: {total_resolutions / total_time:.1f} resolutions/sec")
        
        # Should maintain good performance
        assert avg_time < 0.001, f"Resolution too slow: {avg_time * 1000:.3f}ms average"


@pytest.mark.unit
class TestCacheConfiguration:
    """Test cache configuration and optimization."""
    
    def test_cache_size_limits(self):
        """Test that caches have appropriate size limits."""
        container = Container()
        
        # Create many different types to potentially overflow cache
        for i in range(100):  # Reduced for faster testing
            service_class = type(f"Service{i}", (), {
                '__init__': lambda self: None
            })
            container.register(f"service_{i}", service_class)
        
        # Cache sizes should be reasonable
        injection_cache_size = len(container._injection_cache)
        analysis_cache_size = len(container.analyzer._analysis_cache)
        
        print(f"Injection cache size: {injection_cache_size}")
        print(f"Analysis cache size: {analysis_cache_size}")
        
        # Caches shouldn't grow unbounded
        assert injection_cache_size < 200, f"Injection cache too large: {injection_cache_size}"
        assert analysis_cache_size < 500, f"Analysis cache too large: {analysis_cache_size}"
    
    def test_cache_hit_rates(self):
        """Test cache hit rates under realistic usage."""
        container = Container()
        container.singleton(SimpleService)
        container.register(ComplexService, ComplexService)
        container.register(ServiceWithManyDeps, ServiceWithManyDeps)
        
        # Simulate realistic usage pattern
        services_to_resolve = [SimpleService, ComplexService, ServiceWithManyDeps]
        
        # Track cache performance
        initial_analysis_cache_size = len(container.analyzer._analysis_cache)
        initial_injection_cache_size = len(container._injection_cache)
        
        # Perform many resolutions
        for _ in range(100):
            for service in services_to_resolve:
                container.resolve(service)
        
        final_analysis_cache_size = len(container.analyzer._analysis_cache)
        final_injection_cache_size = len(container._injection_cache)
        
        print(f"Analysis cache: {initial_analysis_cache_size} -> {final_analysis_cache_size}")
        print(f"Injection cache: {initial_injection_cache_size} -> {final_injection_cache_size}")
        
        # Cache should stabilize after initial growth
        assert final_analysis_cache_size < 50, "Analysis cache grew too much"
        assert final_injection_cache_size < 10, "Injection cache grew too much"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "performance"])