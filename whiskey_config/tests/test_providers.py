"""Tests for configuration providers."""

from dataclasses import dataclass

import pytest

from whiskey_config.manager import ConfigurationManager
from whiskey_config.providers import ConfigSection, Setting
from whiskey_config.schema import ConfigurationError


@dataclass
class DatabaseConfig:
    """Test database configuration."""

    host: str
    port: int = 5432


class TestSettingProvider:
    """Test Setting provider functionality."""

    def test_setting_creation(self):
        """Test creating Setting provider."""
        setting = Setting("database.host")
        assert setting.path == "database.host"
        assert setting.default is None

        setting_with_default = Setting("debug", default=False)
        assert setting_with_default.path == "debug"
        assert setting_with_default.default is False

    def test_setting_without_manager(self):
        """Test calling Setting without manager."""
        # Clear global config manager for this test
        import whiskey_config.providers

        original_manager = whiskey_config.providers._config_manager
        whiskey_config.providers._config_manager = None

        try:
            setting = Setting("test.path")

            with pytest.raises(ConfigurationError, match="Configuration manager not set"):
                setting()
        finally:
            # Restore original manager
            whiskey_config.providers._config_manager = original_manager

    def test_setting_with_manager(self):
        """Test Setting with configuration manager."""
        manager = ConfigurationManager()
        manager._config_data = {"database": {"host": "localhost", "port": 5432}, "debug": True}

        # Test getting value
        setting = Setting("database.host")
        setting.set_manager(manager)
        assert setting() == "localhost"

        # Test nested path
        setting = Setting("database.port")
        setting.set_manager(manager)
        assert setting() == 5432

        # Test top-level value
        setting = Setting("debug")
        setting.set_manager(manager)
        assert setting() is True

    def test_setting_with_default(self):
        """Test Setting with default value."""
        manager = ConfigurationManager()
        manager._config_data = {"existing": "value"}

        # Missing value with default
        setting = Setting("missing.value", default="default")
        setting.set_manager(manager)
        assert setting() == "default"

        # Existing value ignores default
        setting = Setting("existing", default="ignored")
        setting.set_manager(manager)
        assert setting() == "value"

    def test_setting_required_missing(self):
        """Test required setting that's missing."""
        manager = ConfigurationManager()
        manager._config_data = {}

        setting = Setting("required.setting")  # No default
        setting.set_manager(manager)

        with pytest.raises(ConfigurationError, match="Required configuration setting"):
            setting()

    def test_setting_repr(self):
        """Test Setting string representation."""
        setting = Setting("test.path", default="default")
        assert repr(setting) == "Setting('test.path')"


class TestConfigSectionProvider:
    """Test ConfigSection provider functionality."""

    def test_config_section_creation(self):
        """Test creating ConfigSection provider."""
        section = ConfigSection(DatabaseConfig)
        assert section.config_type == DatabaseConfig
        assert section.path == ""

        section_with_path = ConfigSection(DatabaseConfig, "database")
        assert section_with_path.config_type == DatabaseConfig
        assert section_with_path.path == "database"

    def test_config_section_without_manager(self):
        """Test calling ConfigSection without manager."""
        # Clear global config manager for this test
        import whiskey_config.providers

        original_manager = whiskey_config.providers._config_manager
        whiskey_config.providers._config_manager = None

        try:
            section = ConfigSection(DatabaseConfig)

            with pytest.raises(ConfigurationError, match="Configuration manager not set"):
                section()
        finally:
            # Restore original manager
            whiskey_config.providers._config_manager = original_manager

    def test_config_section_with_manager(self):
        """Test ConfigSection with configuration manager."""
        manager = ConfigurationManager()
        manager._config_data = {"host": "localhost", "port": 5432}

        # Get full config as type
        section = ConfigSection(DatabaseConfig)
        section.set_manager(manager)

        result = section()
        assert isinstance(result, DatabaseConfig)
        assert result.host == "localhost"
        assert result.port == 5432

    def test_config_section_with_path(self):
        """Test ConfigSection with path."""
        manager = ConfigurationManager()
        manager._config_data = {
            "app": {"name": "test"},
            "database": {"host": "db.example.com", "port": 3306},
        }

        section = ConfigSection(DatabaseConfig, "database")
        section.set_manager(manager)

        result = section()
        assert isinstance(result, DatabaseConfig)
        assert result.host == "db.example.com"
        assert result.port == 3306

    def test_config_section_type_error(self):
        """Test ConfigSection with invalid data."""
        manager = ConfigurationManager()
        manager._config_data = {
            "database": "not a dict"  # Wrong type
        }

        section = ConfigSection(DatabaseConfig, "database")
        section.set_manager(manager)

        with pytest.raises(ConfigurationError):
            section()

    def test_config_section_repr(self):
        """Test ConfigSection string representation."""
        section = ConfigSection(DatabaseConfig, "database")
        assert repr(section) == "ConfigSection(DatabaseConfig, 'database')"
