"""Configuration extension for Whiskey applications."""

from typing import Any, Dict, List, Optional, Type, Union

from whiskey import Application

from .manager import ConfigurationManager
from .providers import ConfigSection, Setting
from .schema import is_dataclass_type
from .sources import ConfigurationSource


def config_extension(app: Application) -> None:
    """Configuration extension that adds configuration management to Whiskey applications.
    
    This extension provides:
    - Multiple configuration sources (files, environment variables)
    - Type-safe configuration using dataclasses
    - Configuration validation
    - Hot reloading support
    - Dependency injection integration
    
    Example:
        from dataclasses import dataclass
        from whiskey import Application
        from whiskey_config import config_extension
        
        app = Application()
        app.use(config_extension)
        
        @dataclass
        class AppConfig:
            debug: bool = False
            host: str = "localhost"
            port: int = 8000
        
        app.configure_config(
            schema=AppConfig,
            sources=["config.json", "ENV"],
            env_prefix="MYAPP_"
        )
        
        @app.component
        class Server:
            @inject
            def __init__(self, config: AppConfig):
                self.config = config
    """
    # Create configuration manager
    config_manager = ConfigurationManager()
    
    # Store manager in app
    app.config_manager = config_manager
    
    # Register manager as singleton
    app.container[ConfigurationManager] = config_manager
    
    # Configure method
    def configure_config(
        schema: Optional[Type] = None,
        sources: Optional[List[Union[str, ConfigurationSource]]] = None,
        env_prefix: str = "",
        watch: bool = False,
        watch_interval: float = 1.0
    ) -> None:
        """Configure the configuration extension.
        
        Args:
            schema: Optional dataclass type defining configuration structure
            sources: List of configuration sources
            env_prefix: Prefix for environment variables
            watch: Enable hot reloading
            watch_interval: Watch interval in seconds
        """
        # Set schema if provided
        if schema:
            if not is_dataclass_type(schema):
                raise ValueError("Schema must be a dataclass type")
            config_manager.set_schema(schema)
            # Register schema type for injection
            app.container.register(schema, factory=lambda: config_manager.get())
        
        # Add sources
        if sources:
            temp_manager = ConfigurationManager.from_sources(
                sources,
                env_prefix=env_prefix
            )
            for source in temp_manager.sources:
                config_manager.add_source(source)
        
        # Start watching if enabled
        if watch:
            @app.on_startup
            async def start_config_watching():
                await config_manager.start_watching(watch_interval)
            
            @app.on_shutdown
            async def stop_config_watching():
                config_manager.stop_watching()
    
    app.configure_config = configure_config
    
    # Load configuration on startup
    @app.on_startup
    async def load_configuration():
        """Load configuration on application startup."""
        await config_manager.load()
        await app.emit("config.loaded", {"manager": config_manager})
    
    # Configuration change events
    async def on_config_change(data: Dict[str, Any]) -> None:
        """Handle configuration changes."""
        await app.emit("config.changed", data)
    
    config_manager.add_change_callback(on_config_change)
    
    # Config decorator
    def config(name: str):
        """Decorator to register a configuration section.
        
        The decorated class should be a dataclass defining the configuration structure.
        
        Example:
            @app.config("database")
            @dataclass
            class DatabaseConfig:
                host: str = "localhost"
                port: int = 5432
        """
        def decorator(cls: Type) -> Type:
            if not is_dataclass_type(cls):
                raise ValueError(f"Config class {cls.__name__} must be a dataclass")
            
            # Register as injectable with factory
            app.container.register(
                cls,
                factory=lambda: config_manager.get_typed(cls, name)
            )
            
            # Store config metadata
            if not hasattr(app, "_config_sections"):
                app._config_sections = {}
            app._config_sections[name] = cls
            
            return cls
        return decorator
    
    app.add_decorator("config", config)
    
    # Feature flag support
    def feature(flag_name: str, default: bool = False):
        """Decorator for feature flags.
        
        Example:
            @app.feature("new_feature")
            async def new_feature_handler():
                # Only executed when feature is enabled
                pass
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                enabled = config_manager.get(f"features.{flag_name}", default)
                if enabled:
                    return await func(*args, **kwargs)
                return None
            return wrapper
        return decorator
    
    app.add_decorator("feature", feature)
    
    # Update configuration method
    def update_config(updates: Dict[str, Any]) -> None:
        """Update configuration at runtime.
        
        Args:
            updates: Dictionary of configuration updates
        """
        config_manager.update(updates)
    
    app.update_config = update_config
    
    # Get configuration method
    def get_config(path: str = "", default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            path: Dotted path to value
            default: Default if not found
            
        Returns:
            Configuration value
        """
        return config_manager.get(path, default)
    
    app.get_config = get_config
    
    # Register Setting provider factory
    def create_setting_provider(setting: Setting):
        """Create a factory for Setting provider."""
        setting.set_manager(config_manager)
        return setting
    
    # Register ConfigSection provider factory  
    def create_config_section_provider(section: ConfigSection):
        """Create a factory for ConfigSection provider."""
        section.set_manager(config_manager)
        return section
    
    # Make Setting and ConfigSection available for injection
    app.container.register(Setting, factory=create_setting_provider)
    app.container.register(ConfigSection, factory=create_config_section_provider)
    
    # Health check for configuration
    @app.on_ready
    async def setup_config_health():
        """Set up configuration health check."""
        
        async def config_health_check():
            """Check configuration health."""
            try:
                # Check if configuration is loaded
                if not config_manager._config_data:
                    return {
                        "healthy": False,
                        "message": "Configuration not loaded"
                    }
                
                # Check if schema validation passes
                if config_manager._schema and not config_manager._config_instance:
                    return {
                        "healthy": False,
                        "message": "Configuration schema validation failed"
                    }
                
                return {
                    "healthy": True,
                    "sources": len(config_manager.sources),
                    "watching": config_manager._watch_task is not None
                }
            except Exception as e:
                return {
                    "healthy": False,
                    "error": str(e)
                }
        
        # Make available for monitoring
        if hasattr(app, "add_health_check"):
            app.add_health_check("configuration", config_health_check)