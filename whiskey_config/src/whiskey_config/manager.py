"""Configuration manager that combines multiple sources."""

import asyncio
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from .schema import (
    ConfigurationError,
    create_dataclass_from_dict,
    dataclass_to_dict,
    get_value_at_path,
    is_dataclass_instance,
    merge_configs,
)
from .sources import ConfigurationSource, EnvironmentSource, FileSource


T = TypeVar("T")


class ConfigurationManager:
    """Manages configuration from multiple sources."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.sources: List[ConfigurationSource] = []
        self._config_data: Dict[str, Any] = {}
        self._config_instance: Optional[Any] = None
        self._schema: Optional[Type] = None
        self._watch_task: Optional[asyncio.Task] = None
        self._change_callbacks: List[Any] = []
    
    def add_source(self, source: ConfigurationSource) -> None:
        """Add a configuration source.
        
        Args:
            source: Configuration source to add
        """
        self.sources.append(source)
    
    def set_schema(self, schema: Type[T]) -> None:
        """Set the configuration schema.
        
        Args:
            schema: Dataclass type defining configuration structure
        """
        self._schema = schema
    
    async def load(self) -> None:
        """Load configuration from all sources."""
        # Load from each source
        config_data = {}
        
        for source in self.sources:
            try:
                source_data = await source.load()
                if source_data:
                    config_data = merge_configs(config_data, source_data)
            except Exception as e:
                raise ConfigurationError(f"Failed to load from {source}: {e}")
        
        # Store raw config data
        self._config_data = config_data
        
        # Create schema instance if defined
        if self._schema:
            try:
                self._config_instance = create_dataclass_from_dict(self._schema, config_data)
            except ConfigurationError:
                raise
            except Exception as e:
                raise ConfigurationError(f"Failed to create configuration instance: {e}")
    
    async def reload(self) -> bool:
        """Reload configuration from sources that support it.
        
        Returns:
            True if configuration changed, False otherwise
        """
        changed = False
        new_config_data = self._config_data.copy()
        
        for source in self.sources:
            if source.can_reload():
                try:
                    updated_data = await source.reload()
                    if updated_data is not None:
                        new_config_data = merge_configs(new_config_data, updated_data)
                        changed = True
                except Exception as e:
                    # Log error but continue with other sources
                    print(f"Warning: Failed to reload from {source}: {e}")
        
        if changed:
            old_data = self._config_data
            self._config_data = new_config_data
            
            # Recreate schema instance
            if self._schema:
                old_instance = self._config_instance
                try:
                    self._config_instance = create_dataclass_from_dict(self._schema, new_config_data)
                except Exception as e:
                    # Rollback on error
                    self._config_data = old_data
                    self._config_instance = old_instance
                    raise ConfigurationError(f"Failed to reload configuration: {e}")
            
            # Notify callbacks
            await self._notify_changes(old_data, new_config_data)
        
        return changed
    
    def get(self, path: str = "", default: Any = None) -> Any:
        """Get configuration value at path.
        
        Args:
            path: Dotted path to value (e.g., "database.host")
            default: Default value if path not found
            
        Returns:
            Configuration value or default
        """
        try:
            if self._config_instance and not path:
                return self._config_instance
            
            config = self._config_instance if self._config_instance else self._config_data
            return get_value_at_path(config, path)
        except ConfigurationError:
            return default
    
    def get_typed(self, config_type: Type[T], path: str = "") -> T:
        """Get typed configuration section.
        
        Args:
            config_type: Dataclass type to convert to
            path: Optional path to configuration section
            
        Returns:
            Typed configuration instance
            
        Raises:
            ConfigurationError: If conversion fails
        """
        data = self.get(path)
        
        if is_dataclass_instance(data):
            # Already a dataclass instance
            if not isinstance(data, config_type):
                raise ConfigurationError(
                    f"Configuration at '{path}' is {type(data).__name__}, not {config_type.__name__}"
                )
            return data
        
        if not isinstance(data, dict):
            raise ConfigurationError(f"Configuration at '{path}' is not a dict")
        
        return create_dataclass_from_dict(config_type, data, path)
    
    def get_raw(self) -> Dict[str, Any]:
        """Get raw configuration data as dictionary.
        
        Returns:
            Raw configuration dictionary
        """
        return self._config_data.copy()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values.
        
        Args:
            updates: Dictionary of updates to apply
        """
        old_data = self._config_data.copy()
        self._config_data = merge_configs(self._config_data, updates)
        
        # Update schema instance
        if self._schema:
            try:
                self._config_instance = create_dataclass_from_dict(self._schema, self._config_data)
            except Exception as e:
                # Rollback on error
                self._config_data = old_data
                raise ConfigurationError(f"Failed to update configuration: {e}")
        
        # Notify changes synchronously (caller should handle async)
        asyncio.create_task(self._notify_changes(old_data, self._config_data))
    
    def add_change_callback(self, callback: Any) -> None:
        """Add a callback for configuration changes.
        
        Args:
            callback: Async function to call on changes
        """
        self._change_callbacks.append(callback)
    
    async def _notify_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> None:
        """Notify callbacks of configuration changes."""
        changes = self._find_changes(old_data, new_data)
        
        for path, (old_value, new_value) in changes.items():
            for callback in self._change_callbacks:
                try:
                    await callback({
                        "path": path,
                        "old_value": old_value,
                        "new_value": new_value
                    })
                except Exception as e:
                    print(f"Error in config change callback: {e}")
    
    def _find_changes(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        path: str = ""
    ) -> Dict[str, tuple]:
        """Find changes between two configurations.
        
        Returns:
            Dictionary mapping paths to (old_value, new_value) tuples
        """
        changes = {}
        
        # Check for changed/new keys
        for key, new_value in new_data.items():
            key_path = f"{path}.{key}" if path else key
            
            if key not in old_data:
                changes[key_path] = (None, new_value)
            elif isinstance(new_value, dict) and isinstance(old_data[key], dict):
                # Recursively check nested dicts
                nested_changes = self._find_changes(old_data[key], new_value, key_path)
                changes.update(nested_changes)
            elif old_data[key] != new_value:
                changes[key_path] = (old_data[key], new_value)
        
        # Check for removed keys
        for key in old_data:
            if key not in new_data:
                key_path = f"{path}.{key}" if path else key
                changes[key_path] = (old_data[key], None)
        
        return changes
    
    async def start_watching(self, interval: float = 1.0) -> None:
        """Start watching for configuration changes.
        
        Args:
            interval: Check interval in seconds
        """
        if self._watch_task:
            return
        
        async def watch_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.reload()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Error watching configuration: {e}")
        
        self._watch_task = asyncio.create_task(watch_loop())
    
    def stop_watching(self) -> None:
        """Stop watching for configuration changes."""
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
    
    @classmethod
    def from_sources(cls, sources: List[Union[str, ConfigurationSource]], **kwargs) -> "ConfigurationManager":
        """Create manager from source specifications.
        
        Args:
            sources: List of source specifications
            **kwargs: Additional arguments
                env_prefix: Prefix for environment variables
                
        Returns:
            Configured manager instance
        """
        manager = cls()
        env_prefix = kwargs.get("env_prefix", "")
        
        for source in sources:
            if isinstance(source, ConfigurationSource):
                manager.add_source(source)
            elif isinstance(source, str):
                if source == "ENV":
                    manager.add_source(EnvironmentSource(prefix=env_prefix))
                else:
                    # Assume it's a file path
                    manager.add_source(FileSource(source))
            else:
                raise ValueError(f"Invalid source: {source}")
        
        return manager