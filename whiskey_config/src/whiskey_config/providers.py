"""Dependency injection providers for configuration."""

from typing import Any, Optional

from .manager import ConfigurationManager
from .schema import ConfigurationError

# Global config manager set by extension
_config_manager: Optional[ConfigurationManager] = None


class Setting:
    """Provider that injects a specific configuration value.

    Usage:
        @inject
        def __init__(self, debug: bool = Setting("debug")):
            self.debug = debug
    """

    def __init__(self, path: str, default: Any = None):
        """Initialize setting provider.

        Args:
            path: Dotted path to configuration value
            default: Default value if not found
        """
        self.path = path
        self.default = default
        self._manager: Optional[ConfigurationManager] = None

    def set_manager(self, manager: ConfigurationManager) -> None:
        """Set the configuration manager.

        Args:
            manager: Configuration manager instance
        """
        self._manager = manager

    def __call__(self) -> Any:
        """Get the configuration value.

        Returns:
            Configuration value

        Raises:
            ConfigurationError: If manager not set or value not found
        """
        manager = self._manager or _config_manager
        if not manager:
            raise ConfigurationError("Configuration manager not set for Setting provider")

        value = manager.get(self.path, self.default)
        if value is None and self.default is None:
            raise ConfigurationError(f"Required configuration setting '{self.path}' not found")

        return value

    def __repr__(self) -> str:
        """String representation."""
        return f"Setting('{self.path}')"


class ConfigSection:
    """Provider that injects a typed configuration section.

    Usage:
        @inject
        def __init__(self, db_config: DatabaseConfig = ConfigSection(DatabaseConfig, "database")):
            self.db_config = db_config
    """

    def __init__(self, config_type: type, path: str = ""):
        """Initialize config section provider.

        Args:
            config_type: Dataclass type for the section
            path: Optional path to section
        """
        self.config_type = config_type
        self.path = path
        self._manager: Optional[ConfigurationManager] = None

    def set_manager(self, manager: ConfigurationManager) -> None:
        """Set the configuration manager.

        Args:
            manager: Configuration manager instance
        """
        self._manager = manager

    def __call__(self) -> Any:
        """Get the typed configuration section.

        Returns:
            Typed configuration instance

        Raises:
            ConfigurationError: If manager not set or conversion fails
        """
        manager = self._manager or _config_manager
        if not manager:
            raise ConfigurationError("Configuration manager not set for ConfigSection provider")

        return manager.get_typed(self.config_type, self.path)

    def __repr__(self) -> str:
        """String representation."""
        return f"ConfigSection({self.config_type.__name__}, '{self.path}')"
