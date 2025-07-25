"""Enhanced lifecycle management extension for Whiskey applications."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set, Tuple

from whiskey import Application, ComponentMetadata, Initializable, Disposable


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component_type: type
    status: str = "unknown"  # healthy, unhealthy, degraded, unknown
    message: str | None = None
    last_check: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class DependencyNode:
    """Node in the dependency graph."""
    component_type: type
    metadata: ComponentMetadata
    dependencies: Set[type] = field(default_factory=set)
    dependents: Set[type] = field(default_factory=set)
    startup_time: float | None = None
    retry_count: int = 0


class LifecycleManager:
    """Manages advanced lifecycle features."""
    
    def __init__(self, app: Application):
        self.app = app
        self.health_status: Dict[type, ComponentHealth] = {}
        self.dependency_graph: Dict[type, DependencyNode] = {}
        self.startup_order: List[type] = []
        self.readiness_checks: Dict[str, Callable] = {}
        self.retry_policies: Dict[type, Dict[str, Any]] = {}
        self._initialized_components: Set[type] = set()
        
    def build_dependency_graph(self) -> None:
        """Build the component dependency graph."""
        # Create nodes for all components
        for comp_type, metadata in self.app._component_metadata.items():
            node = DependencyNode(
                component_type=comp_type,
                metadata=metadata,
                dependencies=metadata.requires.copy()
            )
            self.dependency_graph[comp_type] = node
            
        # Build reverse dependencies (dependents)
        for comp_type, node in self.dependency_graph.items():
            for dep in node.dependencies:
                if dep in self.dependency_graph:
                    self.dependency_graph[dep].dependents.add(comp_type)
                    
    def calculate_startup_order(self) -> List[type]:
        """Calculate optimal startup order using topological sort."""
        # Build in-degree map
        in_degree = {comp: len(node.dependencies) for comp, node in self.dependency_graph.items()}
        
        # Start with components that have no dependencies
        queue = [comp for comp, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            # Sort by priority for components at the same level
            queue.sort(key=lambda c: self.dependency_graph[c].metadata.priority)
            
            # Process all components at this level in parallel
            level = queue[:]
            queue = []
            order.extend(level)
            
            # Reduce in-degree for dependents
            for comp in level:
                for dependent in self.dependency_graph[comp].dependents:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
                        
        return order
        
    async def startup_with_retry(self, component_type: type, max_retries: int = 3, delay: float = 1.0) -> bool:
        """Start a component with retry logic."""
        node = self.dependency_graph.get(component_type)
        if not node:
            return True
            
        # Check if already initialized
        if component_type in self._initialized_components:
            return True
            
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                # Only initialize if has the initialize method
                # Don't resolve yet - that happens in the application's normal flow
                if issubclass(component_type, Initializable):
                    # Trigger the initialization hook that was registered
                    await self.app._initialize_component(component_type)
                    
                node.startup_time = time.time() - start_time
                self._initialized_components.add(component_type)
                
                # Mark as healthy
                self.health_status[component_type] = ComponentHealth(
                    component_type=component_type,
                    status="healthy",
                    message=f"Started in {node.startup_time:.2f}s"
                )
                
                await self.app.emit("component.started", {
                    "type": component_type,
                    "time": node.startup_time,
                    "attempt": attempt + 1
                })
                
                return True
                
            except Exception as e:
                node.retry_count = attempt + 1
                
                if attempt < max_retries - 1:
                    await self.app.emit("component.retry", {
                        "type": component_type,
                        "error": str(e),
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    })
                    await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff
                else:
                    # Final failure
                    self.health_status[component_type] = ComponentHealth(
                        component_type=component_type,
                        status="unhealthy",
                        message=f"Failed after {max_retries} attempts: {e}"
                    )
                    
                    if node.metadata.critical:
                        raise RuntimeError(f"Critical component {component_type.__name__} failed to start: {e}")
                    
                    await self.app.emit("component.failed", {
                        "type": component_type,
                        "error": str(e),
                        "critical": node.metadata.critical
                    })
                    
                    return False
                    
    async def parallel_startup(self) -> None:
        """Start components in parallel where possible."""
        self.build_dependency_graph()
        self.startup_order = self.calculate_startup_order()
        
        # Group by dependency level
        levels: List[List[type]] = []
        processed = set()
        
        for comp in self.startup_order:
            if comp in processed:
                continue
                
            # Find all components that can start at this level
            level = []
            for candidate in self.startup_order:
                if candidate in processed:
                    continue
                    
                # Check if all dependencies are satisfied
                node = self.dependency_graph[candidate]
                if all(dep in processed for dep in node.dependencies):
                    level.append(candidate)
                    
            if level:
                levels.append(level)
                processed.update(level)
                
        # Start each level in parallel
        for level_idx, level in enumerate(levels):
            await self.app.emit("lifecycle.level_starting", {
                "level": level_idx,
                "components": [c.__name__ for c in level]
            })
            
            # Start all components in this level concurrently
            tasks = []
            for comp_type in level:
                retry_policy = self.retry_policies.get(comp_type, {"max_retries": 3, "delay": 1.0})
                task = self.startup_with_retry(
                    comp_type,
                    max_retries=retry_policy["max_retries"],
                    delay=retry_policy["delay"]
                )
                tasks.append(task)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check for critical failures
            for comp_type, result in zip(level, results):
                if isinstance(result, Exception):
                    node = self.dependency_graph[comp_type]
                    if node.metadata.critical:
                        raise result
                        
    async def check_component_health(self, component_type: type) -> ComponentHealth:
        """Check health of a specific component."""
        try:
            component = await self.app.container.resolve(component_type)
            
            # Look for health check method
            health_check = None
            if hasattr(component, "health_check"):
                health_check = component.health_check
            elif hasattr(component, "healthcheck"):
                health_check = component.healthcheck
            elif hasattr(component, "is_healthy"):
                health_check = component.is_healthy
                
            if health_check:
                result = await health_check() if asyncio.iscoroutinefunction(health_check) else health_check()
                
                # Parse result
                if isinstance(result, bool):
                    status = "healthy" if result else "unhealthy"
                    message = None
                elif isinstance(result, dict):
                    status = result.get("status", "healthy")
                    message = result.get("message")
                else:
                    status = "healthy"
                    message = str(result)
                    
                health = ComponentHealth(
                    component_type=component_type,
                    status=status,
                    message=message,
                    last_check=time.time()
                )
            else:
                # No health check, assume healthy if instantiated
                health = ComponentHealth(
                    component_type=component_type,
                    status="healthy",
                    message="No health check defined",
                    last_check=time.time()
                )
                
        except Exception as e:
            health = ComponentHealth(
                component_type=component_type,
                status="unhealthy",
                message=str(e),
                last_check=time.time()
            )
            
        self.health_status[component_type] = health
        return health
        
    async def check_all_health(self) -> Dict[type, ComponentHealth]:
        """Check health of all components."""
        tasks = []
        for comp_type in self.dependency_graph:
            tasks.append(self.check_component_health(comp_type))
            
        await asyncio.gather(*tasks, return_exceptions=True)
        return self.health_status
        
    def add_readiness_check(self, name: str, check: Callable) -> None:
        """Add a readiness check."""
        self.readiness_checks[name] = check
        
    async def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """Check if application is ready."""
        results = {}
        all_ready = True
        
        for name, check in self.readiness_checks.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    result = await check()
                else:
                    result = check()
                    
                results[name] = {"ready": bool(result), "message": str(result) if result else None}
                if not result:
                    all_ready = False
                    
            except Exception as e:
                results[name] = {"ready": False, "error": str(e)}
                all_ready = False
                
        # Check component health as part of readiness
        health = await self.check_all_health()
        for comp_type, status in health.items():
            name = f"component.{comp_type.__name__}"
            results[name] = {
                "ready": status.status in ["healthy", "degraded"],
                "status": status.status,
                "message": status.message
            }
            if status.status not in ["healthy", "degraded"]:
                all_ready = False
                
        return all_ready, results
        
    def visualize_dependencies(self) -> str:
        """Generate a text representation of the dependency graph."""
        lines = ["Dependency Graph:"]
        lines.append("=" * 50)
        
        for comp_type in self.startup_order:
            node = self.dependency_graph[comp_type]
            indent = "  "
            
            # Component info
            status = self.health_status.get(comp_type, ComponentHealth(comp_type))
            status_icon = {
                "healthy": "✅",
                "unhealthy": "❌", 
                "degraded": "⚠️",
                "unknown": "❓"
            }.get(status.status, "❓")
            
            lines.append(f"{status_icon} {comp_type.__name__}")
            
            # Metadata
            if node.metadata.priority != 0:
                lines.append(f"{indent}Priority: {node.metadata.priority}")
            if node.metadata.provides:
                lines.append(f"{indent}Provides: {', '.join(node.metadata.provides)}")
            if node.metadata.critical:
                lines.append(f"{indent}Critical: Yes")
                
            # Dependencies
            if node.dependencies:
                dep_names = [d.__name__ for d in node.dependencies]
                lines.append(f"{indent}Depends on: {', '.join(dep_names)}")
                
            # Dependents
            if node.dependents:
                dep_names = [d.__name__ for d in node.dependents]
                lines.append(f"{indent}Required by: {', '.join(dep_names)}")
                
            # Performance
            if node.startup_time:
                lines.append(f"{indent}Startup time: {node.startup_time:.3f}s")
            if node.retry_count > 0:
                lines.append(f"{indent}Retries: {node.retry_count}")
                
            lines.append("")
            
        return "\n".join(lines)


def lifecycle_extension(app: Application) -> None:
    """Enhanced lifecycle management extension."""
    
    # Create lifecycle manager
    manager = LifecycleManager(app)
    
    # Store manager in app for access
    app.lifecycle_manager = manager
    
    # Override the component registration to prevent automatic init hooks
    original_component = app.component
    
    def enhanced_component(cls: type | None = None, **kwargs):
        """Enhanced component registration that disables automatic init hooks."""
        def register(component_cls: type) -> type:
            # Get or create metadata (preserve existing from decorators like @requires)
            if component_cls in app._component_metadata:
                metadata = app._component_metadata[component_cls]
                metadata.name = kwargs.get("name") or metadata.name
            else:
                metadata = ComponentMetadata(
                    component_type=component_cls,
                    name=kwargs.get("name"),
                )
                app._component_metadata[component_cls] = metadata
            
            # Register with container
            app.container.register(component_cls, component_cls, **kwargs)
            
            # DON'T add automatic lifecycle hooks - lifecycle extension manages this
            
            # Only add disposal hooks (shutdown is still managed normally)
            if issubclass(component_cls, Disposable):
                async def dispose():
                    await app._dispose_component(component_cls)
                app.on_shutdown(dispose)
            
            # Fire registration event during configure phase
            async def emit_event():
                await app.emit("component.registered", {
                    "type": component_cls,
                    "metadata": metadata
                })
            app.on_configure(emit_event)
            
            return component_cls
            
        if cls is None:
            return register
        return register(cls)
    
    # Replace component method
    app.component = enhanced_component
    app.provider = enhanced_component
    app.managed = enhanced_component
    app.system = enhanced_component
    app.service = enhanced_component
    
    # Replace default startup with parallel startup
    original_startup = app.startup
    
    async def enhanced_startup():
        """Enhanced startup with dependency management."""
        # Run early lifecycle phases first
        await app._run_hooks("configure")
        await app._run_hooks("before_startup")
        
        await app.emit("lifecycle.analyzing_dependencies")
        
        # Build and visualize dependencies
        manager.build_dependency_graph()
        graph = manager.visualize_dependencies()
        await app.emit("lifecycle.dependency_graph", {"graph": graph})
        
        # Start components in parallel (this handles the startup phase)
        await manager.parallel_startup()
        
        # Run remaining hooks
        await app._run_hooks("after_startup")
        await app._run_hooks("ready")
        await app.emit("application.ready")
        
    # Override startup
    app.startup = enhanced_startup
    
    # Add retry policy decorator
    def retry(max_retries: int = 3, delay: float = 1.0):
        """Configure retry policy for a component."""
        def decorator(cls: type) -> type:
            manager.retry_policies[cls] = {
                "max_retries": max_retries,
                "delay": delay
            }
            return cls
        return decorator
        
    app.add_decorator("retry", retry)
    
    # Add health endpoint handler
    @app.on_ready
    async def setup_health_endpoint():
        """Set up health check endpoint."""
        
        async def health_handler():
            """Check application health."""
            health = await manager.check_all_health()
            
            # Aggregate status
            all_healthy = all(h.status == "healthy" for h in health.values())
            has_critical_failure = any(
                h.status == "unhealthy" and manager.dependency_graph[h.component_type].metadata.critical
                for h in health.values()
            )
            
            return {
                "status": "unhealthy" if has_critical_failure else "degraded" if not all_healthy else "healthy",
                "components": {
                    comp.__name__: {
                        "status": h.status,
                        "message": h.message,
                        "last_check": h.last_check
                    }
                    for comp, h in health.items()
                }
            }
            
        # Make available for web frameworks
        app.health_handler = health_handler
        
    # Add readiness endpoint handler  
    @app.on_ready
    async def setup_readiness_endpoint():
        """Set up readiness check endpoint."""
        
        async def readiness_handler():
            """Check application readiness."""
            ready, results = await manager.check_readiness()
            
            return {
                "ready": ready,
                "checks": results
            }
            
        app.readiness_handler = readiness_handler
        
    # Background health monitoring
    @app.task
    async def health_monitor():
        """Monitor component health periodically."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            try:
                health = await manager.check_all_health()
                
                # Emit events for unhealthy components
                for comp_type, status in health.items():
                    if status.status == "unhealthy":
                        await app.emit("component.unhealthy", {
                            "type": comp_type,
                            "message": status.message,
                            "critical": manager.dependency_graph[comp_type].metadata.critical
                        })
                        
            except Exception as e:
                await app.emit("health_check.error", {"error": str(e)})
                
    # CLI commands (for whiskey-cli integration)
    app.lifecycle_manager = manager
    
    # Add readiness check helpers
    app.add_readiness_check = manager.add_readiness_check
    app.check_readiness = manager.check_readiness
    
    # Graceful degradation on shutdown
    original_shutdown = app.shutdown
    
    async def graceful_shutdown():
        """Shutdown with graceful degradation."""
        await app.emit("lifecycle.graceful_shutdown_starting")
        
        # Shutdown in reverse dependency order
        shutdown_order = list(reversed(manager.startup_order))
        
        for comp_type in shutdown_order:
            try:
                await app._dispose_component(comp_type)
            except Exception as e:
                await app.emit("component.shutdown_error", {
                    "type": comp_type,
                    "error": str(e)
                })
                
        # Run remaining shutdown hooks
        await app._run_hooks("after_shutdown")
        
    app.shutdown = graceful_shutdown