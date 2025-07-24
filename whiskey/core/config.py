"""Configuration management for IoC."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, get_type_hints

from loguru import logger

try:
    import yaml
except ImportError:
    yaml = None  # Make yaml optional

T = TypeVar("T")


class ConfigSource(ABC):
    """Base class for configuration sources."""
    
    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        pass


class EnvironmentSource(ConfigSource):
    """Configuration source from environment variables."""
    
    def __init__(self, prefix: str = "WHISKEY_"):
        self.prefix = prefix
    
    async def get(self, key: str, default: Any = None) -> Any:
        env_key = f"{self.prefix}{key.upper()}"
        return os.environ.get(env_key, default)
    
    async def set(self, key: str, value: Any) -> None:
        env_key = f"{self.prefix}{key.upper()}"
        os.environ[env_key] = str(value)


class YamlSource(ConfigSource):
    """Configuration source from YAML files."""
    
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self._data: dict[str, Any] = {}
        self._load()
    
    def _load(self):
        """Load configuration from file."""
        if self.file_path.exists():
            with open(self.file_path) as f:
                self._data = yaml.safe_load(f) or {}
    
    async def get(self, key: str, default: Any = None) -> Any:
        # Support nested keys like "database.host"
        keys = key.split(".")
        value = self._data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    async def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        data = self._data
        
        # Navigate to nested location
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        
        data[keys[-1]] = value
        
        # Save to file
        with open(self.file_path, "w") as f:
            yaml.dump(self._data, f)


class ConfigurationManager:
    """
    Manages configuration from multiple sources with IoC integration.
    
    Supports:
    - Multiple configuration sources (env, files, remote)
    - Type-safe configuration classes
    - Hot reloading
    - Validation
    """
    
    def __init__(self):
        self._sources: list[ConfigSource] = []
        self._cache: dict[str, Any] = {}
        self._config_classes: dict[type, Any] = {}
    
    def add_source(self, source: ConfigSource) -> None:
        """Add a configuration source."""
        self._sources.append(source)
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        # Check cache
        if key in self._cache:
            return self._cache[key]
        
        # Check sources in order
        for source in self._sources:
            value = await source.get(key, None)
            if value is not None:
                self._cache[key] = value
                return value
        
        return default
    
    async def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._cache[key] = value
        
        # Update all sources
        for source in self._sources:
            await source.set(key, value)
    
    def configure(self, config_class: type[T]) -> T:
        """
        Create a configuration instance from a dataclass.
        
        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432
            database: str = "myapp"
        
        db_config = config.configure(DatabaseConfig)
        """
        if config_class in self._config_classes:
            return self._config_classes[config_class]
        
        # Get type hints
        hints = get_type_hints(config_class)
        
        # Create instance with values from configuration
        kwargs = {}
        for field_name, field_type in hints.items():
            value = asyncio.run(self.get(f"{config_class.__name__.lower()}.{field_name}"))
            if value is not None:
                kwargs[field_name] = value
        
        instance = config_class(**kwargs)
        self._config_classes[config_class] = instance
        
        return instance
    
    async def reload(self) -> None:
        """Reload configuration from all sources."""
        self._cache.clear()
        
        # Reload file-based sources
        for source in self._sources:
            if hasattr(source, "_load"):
                source._load()
        
        logger.info("Configuration reloaded")


# Configuration decorators

def config_value(key: str, default: Any = None):
    """
    Decorator to inject configuration values.
    
    @inject
    async def connect_db(host: str = config_value("database.host", "localhost")):
        return await connect(host)
    """
    def get_value():
        from whiskey.core.decorators import get_default_container
        container = get_default_container()
        config_mgr = container.resolve_sync(ConfigurationManager)
        return asyncio.run(config_mgr.get(key, default))
    
    return get_value


def config_class(prefix: str | None = None):
    """
    Decorator to create configuration classes with automatic binding.
    
    @config_class("database")
    @dataclass
    class DatabaseConfig:
        host: str = "localhost"
        port: int = 5432
    """
    def decorator(cls: type[T]) -> type[T]:
        # Register with container
        from whiskey.core.decorators import get_default_container
        container = get_default_container()
        
        # Create factory that loads from configuration
        async def factory(config_mgr: ConfigurationManager) -> T:
            return config_mgr.configure(cls)
        
        container.register_singleton(cls, factory=factory)
        
        return cls
    
    return decorator