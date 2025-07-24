"""Automatic component discovery and registration system.

This module provides Pythonic autodiscovery based on:
- Type hints in __init__ methods for automatic injection
- Convention-based discovery (files ending with _service, _repository, etc.)
- Module-level __all__ exports
- Simple decorators when explicit configuration is needed
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, get_type_hints

from loguru import logger

from whiskey.core.container import Container
from whiskey.core.decorators import get_default_container, provide, singleton
from whiskey.core.types import ScopeType

T = TypeVar("T")


# Convention-based scope mapping
NAMING_CONVENTIONS = {
    "_service": ScopeType.SINGLETON,
    "_repository": ScopeType.SINGLETON,
    "_controller": ScopeType.REQUEST,
    "_handler": ScopeType.REQUEST,
    "_factory": ScopeType.SINGLETON,
    "_manager": ScopeType.SINGLETON,
    "_provider": ScopeType.SINGLETON,
}


class AutoDiscovery:
    """Automatic discovery and registration of components."""
    
    def __init__(self, container: Container | None = None):
        self.container = container or get_default_container()
        self._discovered: Set[type] = set()
        self._modules_processed: Set[str] = set()
    
    def discover_package(self, package_name: str) -> None:
        """Discover components in a package using Python conventions.
        
        Args:
            package_name: Package to scan (e.g., 'myapp.services')
        """
        logger.info(f"Discovering components in package: {package_name}")
        
        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            logger.error(f"Failed to import package {package_name}: {e}")
            return
        
        # Process the package module itself
        self._process_module(package)
        
        # Process submodules
        if hasattr(package, "__path__"):
            for _, module_name, _ in pkgutil.walk_packages(
                package.__path__, 
                prefix=f"{package_name}."
            ):
                if module_name in self._modules_processed:
                    continue
                
                try:
                    module = importlib.import_module(module_name)
                    self._process_module(module)
                except ImportError as e:
                    logger.warning(f"Failed to import module {module_name}: {e}")
    
    def discover_path(self, path: Path | str) -> None:
        """Discover components in a directory.
        
        Args:
            path: Directory to scan
        """
        path = Path(path)
        if not path.exists() or not path.is_dir():
            logger.error(f"Invalid path: {path}")
            return
        
        logger.info(f"Discovering components in path: {path}")
        
        # Find all Python files
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            
            # Check if file matches naming conventions
            for suffix, scope in NAMING_CONVENTIONS.items():
                if py_file.stem.endswith(suffix):
                    self._process_file(py_file, path, default_scope=scope)
                    break
            else:
                # Process files without specific suffix too
                self._process_file(py_file, path)
    
    def _process_file(
        self, 
        file_path: Path, 
        base_path: Path,
        default_scope: ScopeType = ScopeType.TRANSIENT
    ) -> None:
        """Process a single Python file."""
        # Convert to module name
        relative_path = file_path.relative_to(base_path.parent)
        module_name = str(relative_path).replace("/", ".").replace("\\", ".")[:-3]
        
        if module_name in self._modules_processed:
            return
        
        try:
            module = importlib.import_module(module_name)
            self._process_module(module, default_scope=default_scope)
        except ImportError as e:
            logger.debug(f"Skipping {module_name}: {e}")
    
    def _process_module(
        self, 
        module: Any,
        default_scope: ScopeType = ScopeType.TRANSIENT
    ) -> None:
        """Process a module for discoverable components."""
        module_name = module.__name__
        if module_name in self._modules_processed:
            return
        
        self._modules_processed.add(module_name)
        logger.debug(f"Processing module: {module_name}")
        
        # Check __all__ for explicit exports
        exported_names = getattr(module, "__all__", None)
        
        # Find classes in the module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Skip imported classes
            if obj.__module__ != module_name:
                continue
            
            # Skip private classes unless exported
            if name.startswith("_") and (exported_names is None or name not in exported_names):
                continue
            
            # Check if already decorated
            if hasattr(obj, "__whiskey_injectable__"):
                continue
            
            # Check if it's a discoverable component
            if self._is_discoverable(obj, name, exported_names):
                scope = self._determine_scope(obj, module_name, default_scope)
                self._register_component(obj, scope)
        
        # Also look for factory functions
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if obj.__module__ != module_name:
                continue
            
            # Check for factory pattern: create_*, make_*, build_*
            if any(name.startswith(prefix) for prefix in ["create_", "make_", "build_"]):
                self._process_factory_function(obj, name)
    
    def _is_discoverable(self, cls: type, name: str, exported_names: list[str] | None) -> bool:
        """Check if a class should be auto-discovered."""
        # Explicitly exported
        if exported_names and name in exported_names:
            return True
        
        # Has dependencies in __init__
        if hasattr(cls, "__init__"):
            sig = inspect.signature(cls.__init__)
            # Has typed parameters beyond self
            if len(sig.parameters) > 1:
                return any(
                    param.annotation != param.empty 
                    for name, param in sig.parameters.items() 
                    if name != "self"
                )
        
        # Follows naming convention
        name_lower = name.lower()
        return any(name_lower.endswith(suffix.lstrip("_")) for suffix in NAMING_CONVENTIONS)
    
    def _determine_scope(
        self, 
        cls: type, 
        module_name: str,
        default_scope: ScopeType
    ) -> ScopeType:
        """Determine appropriate scope for a class."""
        # Check class name
        name_lower = cls.__name__.lower()
        for suffix, scope in NAMING_CONVENTIONS.items():
            if name_lower.endswith(suffix.lstrip("_")):
                return scope
        
        # Check module name
        for suffix, scope in NAMING_CONVENTIONS.items():
            if module_name.endswith(suffix.lstrip("_")):
                return scope
        
        return default_scope
    
    def _register_component(self, cls: type, scope: ScopeType) -> None:
        """Register a discovered component."""
        if cls in self._discovered:
            return
        
        self._discovered.add(cls)
        
        logger.debug(f"Auto-registering {cls.__name__} with scope {scope}")
        
        # Mark as injectable
        cls.__whiskey_injectable__ = True
        cls.__whiskey_scope__ = scope
        
        # Register with container
        self.container.register(
            service_type=cls,
            implementation=cls,
            scope=scope,
        )
    
    def _process_factory_function(self, func: Callable, name: str) -> None:
        """Process a factory function."""
        sig = inspect.signature(func)
        return_type = sig.return_annotation
        
        if return_type == sig.empty:
            return
        
        # Extract what it creates from the name
        # create_database -> Database, make_user_service -> UserService
        logger.debug(f"Found factory function: {name} -> {return_type}")
        
        # Register as a factory
        self.container.register(
            service_type=return_type,
            factory=func,
            scope=ScopeType.SINGLETON,
        )


def autodiscover(*packages: str, paths: list[str | Path] | None = None) -> None:
    """Convenience function to autodiscover components.
    
    Args:
        *packages: Package names to scan
        paths: Additional paths to scan
    
    Example:
        autodiscover("myapp.services", "myapp.repositories")
        autodiscover("myapp", paths=["./plugins"])
    """
    discovery = AutoDiscovery()
    
    for package in packages:
        discovery.discover_package(package)
    
    if paths:
        for path in paths:
            discovery.discover_path(path)


# Simplified decorators for when explicit configuration is needed

def discoverable(cls: type[T]) -> type[T]:
    """Mark a class as explicitly discoverable.
    
    Use this when a class doesn't follow conventions but should be discovered.
    
    @discoverable
    class MySpecialComponent:
        def __init__(self, dep: SomeDependency):
            self.dep = dep
    """
    cls.__whiskey_discoverable__ = True
    return cls


def scope(scope_type: ScopeType | str) -> Callable[[type[T]], type[T]]:
    """Explicitly set the scope for a discoverable component.
    
    @scope(ScopeType.REQUEST)
    class MyRequestHandler:
        pass
    """
    def decorator(cls: type[T]) -> type[T]:
        cls.__whiskey_scope__ = scope_type
        return cls
    
    return decorator