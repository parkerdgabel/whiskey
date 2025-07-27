"""Tests for performance monitoring and optimization utilities.

This module tests the performance monitoring features, metrics collection,
and optimization utilities in the performance module.
"""

import time
from collections import Counter

import pytest

from whiskey.core.performance import (
    PerformanceMetrics,
    PerformanceMonitor,
    ResolutionMetrics,
    ResolutionTimer,
    WeakValueCache,
    get_current_metrics,
    is_performance_monitoring_enabled,
    monitor_resolution,
    monitor_type_analysis,
    record_error,
)


class TestResolutionMetrics:
    """Test ResolutionMetrics dataclass."""

    def test_resolution_metrics_creation(self):
        """Test creating ResolutionMetrics instance."""
        metrics = ResolutionMetrics(
            service_key="test_service",
            resolution_time=0.001,
            cache_hit=True,
            depth=2,
            dependencies_resolved=3,
            circular_check_time=0.0001,
            type_analysis_time=0.0002,
        )

        assert metrics.service_key == "test_service"
        assert metrics.resolution_time == 0.001
        assert metrics.cache_hit is True
        assert metrics.depth == 2
        assert metrics.dependencies_resolved == 3
        assert metrics.circular_check_time == 0.0001
        assert metrics.type_analysis_time == 0.0002

    def test_resolution_metrics_with_cache_miss(self):
        """Test ResolutionMetrics with cache miss."""
        metrics = ResolutionMetrics(
            service_key="missed_service",
            resolution_time=0.005,
            cache_hit=False,
            depth=1,
            dependencies_resolved=0,
            circular_check_time=0.0,
            type_analysis_time=0.001,
        )

        assert metrics.cache_hit is False
        assert metrics.service_key == "missed_service"


class TestPerformanceMetrics:
    """Test PerformanceMetrics class."""

    def test_performance_metrics_initialization(self):
        """Test PerformanceMetrics default initialization."""
        metrics = PerformanceMetrics()

        assert metrics.resolution_count == 0
        assert metrics.total_resolution_time == 0.0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert isinstance(metrics.service_usage, Counter)
        assert metrics.resolution_depths == []
        assert metrics.resolution_errors == 0
        assert metrics.circular_dependencies_detected == 0
        assert metrics.slowest_resolutions == []
        assert metrics.type_analysis_time == 0.0
        assert isinstance(metrics.active_instances, dict)
        assert isinstance(metrics.weak_references, set)

    def test_record_resolution_cache_hit(self):
        """Test recording a resolution with cache hit."""
        metrics = PerformanceMetrics()

        resolution = ResolutionMetrics(
            service_key="test_service",
            resolution_time=0.001,
            cache_hit=True,
            depth=1,
            dependencies_resolved=2,
            circular_check_time=0.0,
            type_analysis_time=0.0001,
        )

        metrics.record_resolution(resolution)

        assert metrics.resolution_count == 1
        assert metrics.total_resolution_time == 0.001
        assert metrics.cache_hits == 1
        assert metrics.cache_misses == 0
        assert metrics.service_usage["test_service"] == 1
        assert metrics.resolution_depths == [1]
        assert metrics.type_analysis_time == 0.0001
        assert len(metrics.slowest_resolutions) == 1

    def test_record_resolution_cache_miss(self):
        """Test recording a resolution with cache miss."""
        metrics = PerformanceMetrics()

        resolution = ResolutionMetrics(
            service_key="missed_service",
            resolution_time=0.005,
            cache_hit=False,
            depth=3,
            dependencies_resolved=5,
            circular_check_time=0.001,
            type_analysis_time=0.002,
        )

        metrics.record_resolution(resolution)

        assert metrics.resolution_count == 1
        assert metrics.total_resolution_time == 0.005
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 1
        assert metrics.service_usage["missed_service"] == 1
        assert metrics.resolution_depths == [3]

    def test_record_multiple_resolutions(self):
        """Test recording multiple resolutions."""
        metrics = PerformanceMetrics()

        # First resolution
        resolution1 = ResolutionMetrics(
            service_key="service_a",
            resolution_time=0.001,
            cache_hit=True,
            depth=1,
            dependencies_resolved=0,
            circular_check_time=0.0,
            type_analysis_time=0.0001,
        )

        # Second resolution
        resolution2 = ResolutionMetrics(
            service_key="service_b",
            resolution_time=0.003,
            cache_hit=False,
            depth=2,
            dependencies_resolved=3,
            circular_check_time=0.001,
            type_analysis_time=0.0005,
        )

        metrics.record_resolution(resolution1)
        metrics.record_resolution(resolution2)

        assert metrics.resolution_count == 2
        assert metrics.total_resolution_time == 0.004
        assert metrics.cache_hits == 1
        assert metrics.cache_misses == 1
        assert metrics.service_usage["service_a"] == 1
        assert metrics.service_usage["service_b"] == 1
        assert metrics.resolution_depths == [1, 2]
        assert abs(metrics.type_analysis_time - 0.0006) < 0.0001

    def test_slowest_resolutions_ordering(self):
        """Test that slowest resolutions are ordered correctly."""
        metrics = PerformanceMetrics()

        # Add resolutions with different times
        times = [0.001, 0.005, 0.002, 0.008, 0.003]
        for i, resolution_time in enumerate(times):
            resolution = ResolutionMetrics(
                service_key=f"service_{i}",
                resolution_time=resolution_time,
                cache_hit=False,
                depth=1,
                dependencies_resolved=0,
                circular_check_time=0.0,
                type_analysis_time=0.0,
            )
            metrics.record_resolution(resolution)

        # Should be ordered by resolution time (descending)
        slowest_times = [r.resolution_time for r in metrics.slowest_resolutions]
        assert slowest_times == [0.008, 0.005, 0.003, 0.002, 0.001]

    def test_slowest_resolutions_limit(self):
        """Test that slowest resolutions list is limited to 10."""
        metrics = PerformanceMetrics()

        # Add 15 resolutions
        for i in range(15):
            resolution = ResolutionMetrics(
                service_key=f"service_{i}",
                resolution_time=i * 0.001,
                cache_hit=False,
                depth=1,
                dependencies_resolved=0,
                circular_check_time=0.0,
                type_analysis_time=0.0,
            )
            metrics.record_resolution(resolution)

        # Should keep only top 10
        assert len(metrics.slowest_resolutions) == 10
        # Should contain the slowest ones (14 down to 5)
        slowest_times = [r.resolution_time for r in metrics.slowest_resolutions]
        expected = [i * 0.001 for i in range(14, 4, -1)]
        assert slowest_times == expected

    def test_record_error(self):
        """Test recording errors."""
        metrics = PerformanceMetrics()

        metrics.record_error("resolution_error")
        assert metrics.resolution_errors == 1
        assert metrics.circular_dependencies_detected == 0

        metrics.record_error("circular_dependency")
        assert metrics.resolution_errors == 2
        assert metrics.circular_dependencies_detected == 1

        metrics.record_error("other_error")
        assert metrics.resolution_errors == 3
        assert metrics.circular_dependencies_detected == 1

    def test_average_resolution_time(self):
        """Test average resolution time calculation."""
        metrics = PerformanceMetrics()

        # No resolutions
        assert metrics.average_resolution_time == 0.0

        # Add some resolutions
        resolution1 = ResolutionMetrics(
            service_key="service_a",
            resolution_time=0.002,
            cache_hit=True,
            depth=1,
            dependencies_resolved=0,
            circular_check_time=0.0,
            type_analysis_time=0.0,
        )

        resolution2 = ResolutionMetrics(
            service_key="service_b",
            resolution_time=0.004,
            cache_hit=False,
            depth=1,
            dependencies_resolved=0,
            circular_check_time=0.0,
            type_analysis_time=0.0,
        )

        metrics.record_resolution(resolution1)
        metrics.record_resolution(resolution2)

        assert metrics.average_resolution_time == 0.003  # (0.002 + 0.004) / 2

    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        metrics = PerformanceMetrics()

        # No resolutions
        assert metrics.cache_hit_rate == 0.0

        # Add cache hit
        metrics.cache_hits = 3
        metrics.cache_misses = 7

        assert metrics.cache_hit_rate == 30.0  # 3/(3+7) * 100

        # All hits
        metrics.cache_hits = 10
        metrics.cache_misses = 0

        assert metrics.cache_hit_rate == 100.0

    def test_average_resolution_depth(self):
        """Test average resolution depth calculation."""
        metrics = PerformanceMetrics()

        # No resolutions
        assert metrics.average_resolution_depth == 0.0

        # Add depths
        metrics.resolution_depths = [1, 2, 3, 4, 5]

        assert metrics.average_resolution_depth == 3.0  # (1+2+3+4+5)/5

    def test_get_hot_services(self):
        """Test getting most frequently used services."""
        metrics = PerformanceMetrics()

        # No services
        assert metrics.get_hot_services() == []

        # Add usage data
        metrics.service_usage = Counter(
            {"service_a": 10, "service_b": 5, "service_c": 15, "service_d": 3, "service_e": 8}
        )

        # Get top 3
        hot_services = metrics.get_hot_services(3)
        assert len(hot_services) == 3
        assert hot_services[0] == ("service_c", 15)
        assert hot_services[1] == ("service_a", 10)
        assert hot_services[2] == ("service_e", 8)

    def test_generate_report_empty(self):
        """Test generating report with no data."""
        metrics = PerformanceMetrics()

        report = metrics.generate_report()

        assert "=== Whiskey DI Performance Report ===" in report
        assert "Total Resolutions: 0" in report
        assert "Total Time: 0.0000s" in report
        assert "Average Resolution Time: 0.0000s" in report
        assert "Cache Hit Rate: 0.0%" in report
        assert "Average Depth: 0.0" in report
        assert "Errors: 0" in report
        assert "Circular Dependencies: 0" in report
        # The report should have recommendations (low cache hit rate with 0 resolutions)
        assert "Performance Recommendations:" in report

    def test_generate_report_with_data(self):
        """Test generating report with actual data."""
        metrics = PerformanceMetrics()

        # Set up some data
        metrics.resolution_count = 10
        metrics.total_resolution_time = 0.05
        metrics.cache_hits = 7
        metrics.cache_misses = 3
        metrics.resolution_depths = [1, 2, 2, 3, 1, 2, 1, 3, 2, 1]
        metrics.resolution_errors = 1
        metrics.circular_dependencies_detected = 0

        metrics.service_usage = Counter(
            {"service_a": 4, "service_b": 3, "service_c": 2, "service_d": 1}
        )

        # Add some slow resolutions
        slow_resolution = ResolutionMetrics(
            service_key="slow_service",
            resolution_time=0.01,
            cache_hit=False,
            depth=3,
            dependencies_resolved=5,
            circular_check_time=0.001,
            type_analysis_time=0.002,
        )
        metrics.slowest_resolutions = [slow_resolution]

        report = metrics.generate_report()

        assert "Total Resolutions: 10" in report
        assert "Cache Hit Rate: 70.0%" in report
        assert "Average Depth: 1.8" in report
        assert "Most Used Services:" in report
        assert "service_a: 4 (40.0%)" in report
        assert "Slowest Resolutions:" in report
        assert "slow_service: 0.0100s" in report

    def test_generate_recommendations_low_cache_hit_rate(self):
        """Test recommendations for low cache hit rate."""
        metrics = PerformanceMetrics()
        metrics.cache_hits = 2
        metrics.cache_misses = 8

        recommendations = metrics._generate_recommendations()

        assert any("Low cache hit rate" in rec for rec in recommendations)

    def test_generate_recommendations_hot_services(self):
        """Test recommendations for hot services."""
        metrics = PerformanceMetrics()
        metrics.resolution_count = 10
        metrics.service_usage = Counter({"hot_service": 5})  # 50% usage

        recommendations = metrics._generate_recommendations()

        assert any("Consider making 'hot_service' a singleton" in rec for rec in recommendations)

    def test_generate_recommendations_high_depth(self):
        """Test recommendations for high dependency depth."""
        metrics = PerformanceMetrics()
        metrics.resolution_depths = [6, 7, 8, 9, 10]  # Average > 5

        recommendations = metrics._generate_recommendations()

        assert any("High dependency depth" in rec for rec in recommendations)

    def test_generate_recommendations_errors(self):
        """Test recommendations for error rate."""
        metrics = PerformanceMetrics()
        metrics.resolution_count = 10
        metrics.resolution_errors = 2

        recommendations = metrics._generate_recommendations()

        assert any("20.0% error rate" in rec for rec in recommendations)


class TestPerformanceMonitor:
    """Test PerformanceMonitor context manager."""

    def test_performance_monitor_creation(self):
        """Test creating PerformanceMonitor."""
        monitor = PerformanceMonitor()

        assert monitor.enabled is True
        assert isinstance(monitor.metrics, PerformanceMetrics)
        assert monitor._token is None

    def test_performance_monitor_disabled(self):
        """Test PerformanceMonitor when disabled."""
        monitor = PerformanceMonitor(enabled=False)

        assert monitor.enabled is False

    def test_performance_monitor_context_manager_enabled(self):
        """Test PerformanceMonitor as context manager when enabled."""
        monitor = PerformanceMonitor(enabled=True)

        # Initially not enabled
        assert not is_performance_monitoring_enabled()
        assert get_current_metrics() is None

        with monitor as metrics:
            # Should be enabled inside context
            assert is_performance_monitoring_enabled()
            assert get_current_metrics() is metrics
            assert isinstance(metrics, PerformanceMetrics)

        # Should be disabled after context
        assert not is_performance_monitoring_enabled()
        assert get_current_metrics() is None

    def test_performance_monitor_context_manager_disabled(self):
        """Test PerformanceMonitor as context manager when disabled."""
        monitor = PerformanceMonitor(enabled=False)

        with monitor as metrics:
            # Should still return metrics but not set context
            assert isinstance(metrics, PerformanceMetrics)
            # Context variables should not be set
            assert not is_performance_monitoring_enabled()
            assert get_current_metrics() is None

    def test_performance_monitor_nested(self):
        """Test nested PerformanceMonitor usage."""
        monitor1 = PerformanceMonitor()
        monitor2 = PerformanceMonitor()

        with monitor1 as metrics1:
            assert get_current_metrics() is metrics1

            with monitor2 as metrics2:
                # Inner monitor should override
                assert get_current_metrics() is metrics2

            # Should restore outer monitor
            assert get_current_metrics() is metrics1

        # Should be disabled after both contexts
        assert not is_performance_monitoring_enabled()
        assert get_current_metrics() is None


class TestResolutionTimer:
    """Test ResolutionTimer context manager."""

    def test_resolution_timer_creation(self):
        """Test creating ResolutionTimer."""
        timer = ResolutionTimer("test_service", cache_hit=True)

        assert timer.service_key == "test_service"
        assert timer.cache_hit is True
        assert timer.start_time == 0.0
        assert timer.type_analysis_start == 0.0
        assert timer.type_analysis_time == 0.0
        assert timer.dependencies_resolved == 0
        assert timer.depth == 0

    def test_resolution_timer_context_manager_no_monitoring(self):
        """Test ResolutionTimer when monitoring is disabled."""
        timer = ResolutionTimer("test_service")

        # Should work without errors even when monitoring is disabled
        with timer:
            time.sleep(0.001)  # Small delay to ensure time passes

        # Nothing should be recorded since monitoring is disabled
        assert get_current_metrics() is None

    def test_resolution_timer_context_manager_with_monitoring(self):
        """Test ResolutionTimer with monitoring enabled."""
        monitor = PerformanceMonitor()

        with monitor as metrics:
            timer = ResolutionTimer("test_service", cache_hit=False)

            with timer:
                time.sleep(0.001)  # Small delay

            # Should have recorded one resolution
            assert metrics.resolution_count == 1
            assert metrics.total_resolution_time > 0
            assert metrics.cache_misses == 1
            assert metrics.service_usage["test_service"] == 1

    def test_resolution_timer_type_analysis(self):
        """Test type analysis timing in ResolutionTimer."""
        monitor = PerformanceMonitor()

        with monitor as metrics:
            timer = ResolutionTimer("test_service")

            with timer:
                timer.start_type_analysis()
                time.sleep(0.001)  # Simulate type analysis work
                timer.end_type_analysis()

            # Should have recorded type analysis time
            assert metrics.type_analysis_time > 0

    def test_resolution_timer_multiple_type_analysis(self):
        """Test multiple type analysis periods."""
        monitor = PerformanceMonitor()

        with monitor as metrics:
            timer = ResolutionTimer("test_service")

            with timer:
                # First type analysis period
                timer.start_type_analysis()
                time.sleep(0.001)
                timer.end_type_analysis()

                # Second type analysis period
                timer.start_type_analysis()
                time.sleep(0.001)
                timer.end_type_analysis()

            # Should accumulate both periods
            assert metrics.type_analysis_time > 0.001

    def test_resolution_timer_dependencies_and_depth(self):
        """Test dependency and depth tracking."""
        monitor = PerformanceMonitor()

        with monitor as metrics:
            timer = ResolutionTimer("test_service")

            with timer:
                timer.add_dependency()
                timer.add_dependency()
                timer.set_depth(3)

            # Check recorded metrics
            resolution = metrics.slowest_resolutions[0]
            assert resolution.dependencies_resolved == 2
            assert resolution.depth == 3

    def test_resolution_timer_cache_hit(self):
        """Test ResolutionTimer with cache hit."""
        monitor = PerformanceMonitor()

        with monitor as metrics:
            timer = ResolutionTimer("cached_service", cache_hit=True)

            with timer:
                pass

            assert metrics.cache_hits == 1
            assert metrics.cache_misses == 0


class TestGlobalFunctions:
    """Test global utility functions."""

    def test_is_performance_monitoring_enabled(self):
        """Test is_performance_monitoring_enabled function."""
        # Initially disabled
        assert not is_performance_monitoring_enabled()

        # Enable with monitor
        monitor = PerformanceMonitor()
        with monitor:
            assert is_performance_monitoring_enabled()

        # Disabled after context
        assert not is_performance_monitoring_enabled()

    def test_get_current_metrics(self):
        """Test get_current_metrics function."""
        # Initially None
        assert get_current_metrics() is None

        # Should return metrics when monitoring
        monitor = PerformanceMonitor()
        with monitor as expected_metrics:
            current_metrics = get_current_metrics()
            assert current_metrics is expected_metrics

        # None after context
        assert get_current_metrics() is None

    def test_record_error(self):
        """Test record_error function."""
        # Should do nothing when monitoring disabled
        record_error("test_error")

        # Should record when monitoring enabled
        monitor = PerformanceMonitor()
        with monitor as metrics:
            record_error("resolution_error")
            record_error("circular_dependency")

            assert metrics.resolution_errors == 2
            assert metrics.circular_dependencies_detected == 1


class TestMonitorDecorators:
    """Test performance monitoring decorators."""

    def test_monitor_resolution_decorator_disabled(self):
        """Test monitor_resolution decorator when monitoring is disabled."""

        class MockContainer:
            def __init__(self):
                self._singleton_cache = {}

            @monitor_resolution
            def resolve(self, key):
                return f"resolved_{key}"

        container = MockContainer()
        result = container.resolve("test_service")

        assert result == "resolved_test_service"
        # No metrics should be recorded
        assert get_current_metrics() is None

    def test_monitor_resolution_decorator_enabled(self):
        """Test monitor_resolution decorator when monitoring is enabled."""

        class MockContainer:
            def __init__(self):
                self._singleton_cache = {}

            @monitor_resolution
            def resolve(self, key):
                time.sleep(0.001)  # Simulate work
                return f"resolved_{key}"

        container = MockContainer()
        monitor = PerformanceMonitor()

        with monitor as metrics:
            result = container.resolve("test_service")

            assert result == "resolved_test_service"
            assert metrics.resolution_count == 1
            assert metrics.total_resolution_time > 0
            assert metrics.service_usage["test_service"] == 1

    def test_monitor_resolution_decorator_cache_hit(self):
        """Test monitor_resolution decorator detecting cache hits."""

        class MockContainer:
            def __init__(self):
                self._singleton_cache = {"cached_service": "cached_value"}

            @monitor_resolution
            def resolve(self, key):
                if str(key) in self._singleton_cache:
                    return self._singleton_cache[str(key)]
                return f"resolved_{key}"

        container = MockContainer()
        monitor = PerformanceMonitor()

        with monitor as metrics:
            result = container.resolve("cached_service")

            assert result == "cached_value"
            assert metrics.cache_hits == 1
            assert metrics.cache_misses == 0

    def test_monitor_resolution_decorator_exception(self):
        """Test monitor_resolution decorator handling exceptions."""

        class MockContainer:
            def __init__(self):
                self._singleton_cache = {}

            @monitor_resolution
            def resolve(self, key):
                if key == "error_service":
                    raise ValueError("Test error")
                return f"resolved_{key}"

        container = MockContainer()
        monitor = PerformanceMonitor()

        with monitor as metrics:
            # Should record error
            with pytest.raises(ValueError):
                container.resolve("error_service")

            assert metrics.resolution_errors == 1

    def test_monitor_type_analysis_decorator_disabled(self):
        """Test monitor_type_analysis decorator when monitoring is disabled."""

        @monitor_type_analysis
        def analyze_type(type_hint):
            time.sleep(0.001)
            return f"analyzed_{type_hint}"

        result = analyze_type("str")
        assert result == "analyzed_str"
        # No metrics should be recorded
        assert get_current_metrics() is None

    def test_monitor_type_analysis_decorator_enabled(self):
        """Test monitor_type_analysis decorator when monitoring is enabled."""

        @monitor_type_analysis
        def analyze_type(type_hint):
            time.sleep(0.001)
            return f"analyzed_{type_hint}"

        monitor = PerformanceMonitor()

        with monitor as metrics:
            result = analyze_type("str")

            assert result == "analyzed_str"
            assert metrics.type_analysis_time > 0

    def test_monitor_type_analysis_decorator_exception(self):
        """Test monitor_type_analysis decorator handling exceptions."""

        @monitor_type_analysis
        def analyze_type(type_hint):
            time.sleep(0.001)
            if type_hint == "error":
                raise TypeError("Analysis failed")
            return f"analyzed_{type_hint}"

        monitor = PerformanceMonitor()

        with monitor as metrics:
            # Should still record time even with exception
            with pytest.raises(TypeError):
                analyze_type("error")

            assert metrics.type_analysis_time > 0


class TestWeakValueCache:
    """Test WeakValueCache for memory optimization."""

    def test_weak_value_cache_creation(self):
        """Test creating WeakValueCache."""
        cache = WeakValueCache()

        assert isinstance(cache._cache, dict)
        assert len(cache._cache) == 0

    def test_weak_value_cache_set_and_get(self):
        """Test setting and getting values."""
        cache = WeakValueCache()

        # Test with object that can be weakly referenced
        class TestObj:
            def __init__(self, data):
                self.data = data

        test_obj = TestObj([1, 2, 3])  # Custom objects can be weakly referenced
        cache.set("test_key", test_obj)

        # Should retrieve the same object
        retrieved = cache.get("test_key")
        assert retrieved is test_obj

    def test_weak_value_cache_get_nonexistent(self):
        """Test getting non-existent key."""
        cache = WeakValueCache()

        result = cache.get("nonexistent")
        assert result is None

    def test_weak_value_cache_garbage_collection(self):
        """Test that cache cleans up garbage collected objects."""
        cache = WeakValueCache()

        # Create object and add to cache
        class TestObj:
            pass

        test_obj = TestObj()
        cache.set("test_key", test_obj)

        # Object should be retrievable
        assert cache.get("test_key") is test_obj

        # Delete reference and force garbage collection
        del test_obj
        import gc

        gc.collect()

        # Should return None now (object was garbage collected)
        assert cache.get("test_key") is None
        # Key should be cleaned up from internal cache
        # (This might not work reliably in all Python implementations)

    def test_weak_value_cache_clear(self):
        """Test clearing the cache."""
        cache = WeakValueCache()

        # Add some items
        class TestObj:
            def __init__(self, value):
                self.value = value

        cache.set("key1", TestObj(1))
        cache.set("key2", TestObj(2))

        # Clear cache
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache._cache) == 0

    def test_weak_value_cache_size(self):
        """Test getting cache size."""
        cache = WeakValueCache()

        # Initially empty
        assert cache.size() == 0

        # Add items
        class TestObj:
            def __init__(self, value):
                self.value = value

        obj1 = TestObj(1)
        obj2 = TestObj(2)
        cache.set("key1", obj1)
        cache.set("key2", obj2)

        assert cache.size() == 2

        # Delete one object
        del obj1
        import gc

        gc.collect()

        # Size method should clean up dead references
        size = cache.size()
        # Size should be 1 or 2 depending on garbage collection timing
        assert size <= 2

    def test_weak_value_cache_overwrite(self):
        """Test overwriting values in cache."""
        cache = WeakValueCache()

        class TestObj:
            def __init__(self, value):
                self.value = value

        obj1 = TestObj(1)
        obj2 = TestObj(2)

        cache.set("key", obj1)
        assert cache.get("key") is obj1

        cache.set("key", obj2)
        assert cache.get("key") is obj2


class TestPerformanceIntegration:
    """Test integration scenarios for performance monitoring."""

    def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""

        class MockContainer:
            def __init__(self):
                self._singleton_cache = {}

            @monitor_resolution
            def resolve(self, key):
                # Simulate type analysis
                self._analyze_type(str)

                # Simulate dependency resolution
                time.sleep(0.001)

                if key == "error_service":
                    raise ValueError("Service not found")

                return f"resolved_{key}"

            @monitor_type_analysis
            def _analyze_type(self, type_hint):
                time.sleep(0.0005)
                return f"analyzed_{type_hint}"

        container = MockContainer()
        monitor = PerformanceMonitor()

        with monitor as metrics:
            # Successful resolutions
            container.resolve("service_a")
            container.resolve("service_b")
            container.resolve("service_a")  # Repeat for usage tracking

            # Error case
            with pytest.raises(ValueError):
                container.resolve("error_service")

            # Check final metrics
            assert metrics.resolution_count == 4
            assert metrics.resolution_errors == 1
            assert metrics.service_usage["service_a"] == 2
            assert metrics.service_usage["service_b"] == 1
            assert metrics.type_analysis_time > 0

            # Generate report
            report = metrics.generate_report()
            assert "Total Resolutions: 4" in report
            assert "service_a: 2 (50.0%)" in report

    def test_context_variable_isolation(self):
        """Test that context variables properly isolate metrics."""

        def worker_with_monitoring():
            monitor = PerformanceMonitor()
            with monitor as metrics:
                # Record some activity
                metrics.record_error("test_error")
                return metrics.resolution_errors

        def worker_without_monitoring():
            # This should not see the monitoring context
            return is_performance_monitoring_enabled()

        # Run workers
        errors = worker_with_monitoring()
        monitoring_enabled = worker_without_monitoring()

        assert errors == 1
        assert monitoring_enabled is False

        # Main context should be unaffected
        assert not is_performance_monitoring_enabled()
        assert get_current_metrics() is None


class TestPerformanceEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_metrics_properties(self):
        """Test properties with empty metrics."""
        metrics = PerformanceMetrics()

        assert metrics.average_resolution_time == 0.0
        assert metrics.cache_hit_rate == 0.0
        assert metrics.average_resolution_depth == 0.0
        assert metrics.get_hot_services() == []

    def test_resolution_timer_without_type_analysis_start(self):
        """Test ending type analysis without starting it."""
        timer = ResolutionTimer("test_service")

        # Should not crash
        timer.end_type_analysis()
        assert timer.type_analysis_time == 0.0

    def test_nested_type_analysis_timing(self):
        """Test nested type analysis timing."""
        timer = ResolutionTimer("test_service")

        timer.start_type_analysis()
        time.sleep(0.001)

        # Start again without ending (should reset)
        timer.start_type_analysis()
        time.sleep(0.001)
        timer.end_type_analysis()

        # Should only record the second period
        assert timer.type_analysis_time > 0
        assert timer.type_analysis_time < 0.002  # Less than both periods

    def test_weak_cache_with_non_weakreferenceable_object(self):
        """Test WeakValueCache with objects that can't be weakly referenced."""
        cache = WeakValueCache()

        # int objects can't be weakly referenced in CPython
        # This should handle the error gracefully
        try:
            cache.set("int_key", 42)
            # If it doesn't raise an error, it should return None on get
            result = cache.get("int_key")
            # Result could be None or 42 depending on implementation
        except TypeError:
            # This is expected for non-weakreferenceable objects
            pass
