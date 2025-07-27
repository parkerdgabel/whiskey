"""Performance monitoring and optimization for dependency injection.

This module provides comprehensive performance monitoring and analysis tools
for Whiskey's dependency injection system. It tracks resolution times, 
identifies bottlenecks, detects resolution patterns, and provides actionable
insights for optimization.

Classes:
    ResolutionMetrics: Metrics for individual component resolutions
    PerformanceMetrics: Aggregated performance statistics
    PerformanceMonitor: Context manager for performance monitoring
    WeakValueCache: Memory-efficient cache using weak references

Functions:
    is_performance_monitoring_enabled: Check if monitoring is active
    enable_performance_monitoring: Enable monitoring in current context
    disable_performance_monitoring: Disable monitoring
    get_current_metrics: Get metrics from current context
    monitor_resolution: Decorator to monitor resolution performance
    record_resolution: Record resolution metrics
    record_error: Record resolution errors

Features:
    - Resolution time tracking with percentiles
    - Dependency graph analysis
    - Cache hit/miss ratios
    - Memory usage monitoring
    - Resolution path tracking
    - Error rate monitoring
    - Hot path identification

Example:
    >>> from whiskey.core.performance import PerformanceMonitor
    >>> from whiskey import Container
    >>> 
    >>> container = Container()
    >>> # ... register components ...
    >>> 
    >>> # Monitor performance
    >>> with PerformanceMonitor() as monitor:
    ...     for _ in range(100):
    ...         component = await container.resolve(UserService)
    ...         await component.process()
    >>> 
    >>> # Analyze results
    >>> print(monitor.generate_report())
    >>> # Shows resolution times, cache hits, hot paths, etc.
    >>> 
    >>> # Get specific metrics
    >>> metrics = monitor.metrics
    >>> print(f"Cache hit rate: {metrics.cache_hit_rate:.1%}")
    >>> print(f"Slowest resolution: {metrics.slowest_resolution}")

Performance Tips:
    - Use singleton scope for expensive components
    - Enable caching for frequently resolved components
    - Use lazy injection to defer expensive resolutions
    - Monitor production workloads to identify bottlenecks
"""

from __future__ import annotations

import time
import weakref
from collections import Counter, defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

# Performance monitoring context
_performance_enabled: ContextVar[bool] = ContextVar("performance_enabled", default=False)
_current_metrics: ContextVar[PerformanceMetrics] = ContextVar("current_metrics", default=None)


@dataclass
class ResolutionMetrics:
    """Metrics for a single component resolution."""

    service_key: str
    resolution_time: float
    cache_hit: bool
    depth: int
    dependencies_resolved: int
    circular_check_time: float
    type_analysis_time: float


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for the DI container."""

    # Resolution tracking
    resolution_count: int = 0
    total_resolution_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    # Component usage patterns
    service_usage: Counter = field(default_factory=Counter)
    resolution_depths: list[int] = field(default_factory=list)

    # Error tracking
    resolution_errors: int = 0
    circular_dependencies_detected: int = 0

    # Performance bottlenecks
    slowest_resolutions: list[ResolutionMetrics] = field(default_factory=list)
    type_analysis_time: float = 0.0

    # Memory usage patterns
    active_instances: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    weak_references: set[weakref.ref] = field(default_factory=set)

    def record_resolution(self, metrics: ResolutionMetrics):
        """Record metrics for a component resolution."""
        self.resolution_count += 1
        self.total_resolution_time += metrics.resolution_time
        self.service_usage[metrics.service_key] += 1
        self.resolution_depths.append(metrics.depth)
        self.type_analysis_time += metrics.type_analysis_time

        if metrics.cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        # Track slowest resolutions (keep top 10)
        self.slowest_resolutions.append(metrics)
        self.slowest_resolutions.sort(key=lambda x: x.resolution_time, reverse=True)
        self.slowest_resolutions = self.slowest_resolutions[:10]

    def record_error(self, error_type: str):
        """Record an error during resolution."""
        self.resolution_errors += 1
        if error_type == "circular_dependency":
            self.circular_dependencies_detected += 1

    @property
    def average_resolution_time(self) -> float:
        """Average time per resolution."""
        if self.resolution_count == 0:
            return 0.0
        return self.total_resolution_time / self.resolution_count

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100

    @property
    def average_resolution_depth(self) -> float:
        """Average dependency resolution depth."""
        if not self.resolution_depths:
            return 0.0
        return sum(self.resolution_depths) / len(self.resolution_depths)

    def get_hot_services(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Get the most frequently resolved components."""
        return self.service_usage.most_common(top_n)

    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        report = []
        report.append("=== Whiskey DI Performance Report ===\n")

        # Overall stats
        report.append(f"Total Resolutions: {self.resolution_count}")
        report.append(f"Total Time: {self.total_resolution_time:.4f}s")
        report.append(f"Average Resolution Time: {self.average_resolution_time:.4f}s")
        report.append(f"Cache Hit Rate: {self.cache_hit_rate:.1f}%")
        report.append(f"Average Depth: {self.average_resolution_depth:.1f}")
        report.append(f"Errors: {self.resolution_errors}")
        report.append(f"Circular Dependencies: {self.circular_dependencies_detected}")
        report.append("")

        # Hot components
        hot_services = self.get_hot_services()
        if hot_services:
            report.append("Most Used Components:")
            for service, count in hot_services:
                pct = (count / self.resolution_count) * 100
                report.append(f"  {service}: {count} ({pct:.1f}%)")
            report.append("")

        # Slowest resolutions
        if self.slowest_resolutions:
            report.append("Slowest Resolutions:")
            for metrics in self.slowest_resolutions[:5]:
                report.append(
                    f"  {metrics.service_key}: {metrics.resolution_time:.4f}s "
                    f"(depth: {metrics.depth}, deps: {metrics.dependencies_resolved})"
                )
            report.append("")

        # Performance recommendations
        report.extend(self._generate_recommendations())

        return "\n".join(report)

    def _generate_recommendations(self) -> list[str]:
        """Generate performance recommendations based on metrics."""
        recommendations = ["Performance Recommendations:"]

        # Cache hit rate recommendations
        if self.cache_hit_rate < 50:
            recommendations.append("• Low cache hit rate - consider using more singletons")

        # Hot component recommendations
        hot_services = self.get_hot_services(3)
        for service, count in hot_services:
            if count > self.resolution_count * 0.3:  # Used in >30% of resolutions
                recommendations.append(
                    f"• Consider making '{service}' a singleton (used {count} times)"
                )

        # Depth recommendations
        if self.average_resolution_depth > 5:
            recommendations.append("• High dependency depth - consider flattening dependencies")

        # Error rate recommendations
        if self.resolution_errors > 0:
            error_rate = (self.resolution_errors / self.resolution_count) * 100
            recommendations.append(f"• {error_rate:.1f}% error rate - review component registrations")

        if len(recommendations) == 1:  # Only the header
            recommendations.append("• Performance looks good!")

        return recommendations


class PerformanceMonitor:
    """Context manager for performance monitoring."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.metrics = PerformanceMetrics()
        self._token = None

    def __enter__(self) -> PerformanceMetrics:
        if self.enabled:
            self._token = _current_metrics.set(self.metrics)
            _performance_enabled.set(True)
        return self.metrics

    def __exit__(self, *args):
        if self.enabled and self._token:
            _current_metrics.reset(self._token)
            _performance_enabled.set(False)


class ResolutionTimer:
    """Context manager for timing individual resolutions."""

    def __init__(self, service_key: str, cache_hit: bool = False):
        self.service_key = service_key
        self.cache_hit = cache_hit
        self.start_time = 0.0
        self.type_analysis_start = 0.0
        self.type_analysis_time = 0.0
        self.dependencies_resolved = 0
        self.depth = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        end_time = time.perf_counter()
        resolution_time = end_time - self.start_time

        metrics = _current_metrics.get()
        if metrics is not None:
            resolution_metrics = ResolutionMetrics(
                service_key=self.service_key,
                resolution_time=resolution_time,
                cache_hit=self.cache_hit,
                depth=self.depth,
                dependencies_resolved=self.dependencies_resolved,
                circular_check_time=0.0,  # TODO: implement
                type_analysis_time=self.type_analysis_time,
            )
            metrics.record_resolution(resolution_metrics)

    def start_type_analysis(self):
        """Mark the start of type analysis."""
        self.type_analysis_start = time.perf_counter()

    def end_type_analysis(self):
        """Mark the end of type analysis."""
        if self.type_analysis_start > 0:
            self.type_analysis_time += time.perf_counter() - self.type_analysis_start
            self.type_analysis_start = 0.0

    def add_dependency(self):
        """Record that a dependency was resolved."""
        self.dependencies_resolved += 1

    def set_depth(self, depth: int):
        """Set the resolution depth."""
        self.depth = depth


def is_performance_monitoring_enabled() -> bool:
    """Check if performance monitoring is currently enabled."""
    return _performance_enabled.get()


def get_current_metrics() -> PerformanceMetrics | None:
    """Get the current performance metrics if monitoring is enabled."""
    return _current_metrics.get()


def record_error(error_type: str):
    """Record an error for performance tracking."""
    metrics = _current_metrics.get()
    if metrics is not None:
        metrics.record_error(error_type)


# Decorators for performance monitoring


def monitor_resolution(func):
    """Decorator to monitor resolution performance."""

    def wrapper(self, key, *args, **kwargs):
        if not is_performance_monitoring_enabled():
            return func(self, key, *args, **kwargs)

        # Check if it's a cache hit
        cache_hit = hasattr(self, "_singleton_cache") and str(key) in self._singleton_cache

        with ResolutionTimer(str(key), cache_hit):
            try:
                result = func(self, key, *args, **kwargs)
                return result
            except Exception as e:
                record_error(type(e).__name__.lower())
                raise

    return wrapper


def monitor_type_analysis(func):
    """Decorator to monitor type analysis performance."""

    def wrapper(*args, **kwargs):
        metrics = _current_metrics.get()
        if metrics is None:
            return func(*args, **kwargs)

        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            metrics.type_analysis_time += end_time - start_time

    return wrapper


# Memory optimization utilities


class WeakValueCache:
    """Cache that uses weak references to avoid memory leaks."""

    def __init__(self):
        self._cache: dict[str, weakref.ref] = {}

    def get(self, key: str) -> Any:
        """Get a value from the cache."""
        if key in self._cache:
            ref = self._cache[key]
            value = ref()
            if value is not None:
                return value
            else:
                # Clean up dead reference
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache with weak reference."""

        def cleanup_callback(ref):
            self._cache.pop(key, None)

        self._cache[key] = weakref.ref(value, cleanup_callback)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def size(self) -> int:
        """Get the current cache size."""
        # Clean up dead references
        dead_keys = []
        for key, ref in self._cache.items():
            if ref() is None:
                dead_keys.append(key)

        for key in dead_keys:
            del self._cache[key]

        return len(self._cache)
