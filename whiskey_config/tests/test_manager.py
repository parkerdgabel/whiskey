"""Tests for configuration manager."""

import asyncio
import json
from dataclasses import dataclass

import pytest

from whiskey_config.manager import ConfigurationManager
from whiskey_config.schema import ConfigurationError
from whiskey_config.sources import EnvironmentSource, FileSource


@dataclass
class TestConfig:
    """Test configuration schema."""

    name: str
    version: str
    debug: bool = False


@dataclass
class DatabaseConfig:
    """Database configuration."""

    host: str
    port: int = 5432


@dataclass
class AppConfig:
    """Application configuration."""

    name: str
    database: DatabaseConfig
    debug: bool = False


class TestConfigurationManager:
    """Test configuration manager functionality."""

    @pytest.mark.asyncio
    async def test_add_source(self):
        """Test adding configuration sources."""
        manager = ConfigurationManager()
        source1 = EnvironmentSource()
        source2 = FileSource("config.json")

        manager.add_source(source1)
        manager.add_source(source2)

        assert len(manager.sources) == 2
        assert manager.sources[0] == source1
        assert manager.sources[1] == source2

    @pytest.mark.asyncio
    async def test_load_from_single_source(self, config_file):
        """Test loading from single source."""
        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))

        await manager.load()

        assert manager._config_data["name"] == "TestApp"
        assert manager._config_data["version"] == "1.0.0"
        assert manager._config_data["debug"] is True

    @pytest.mark.asyncio
    async def test_load_from_multiple_sources(self, config_file, env_vars):
        """Test loading and merging from multiple sources."""
        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))
        manager.add_source(EnvironmentSource(prefix="MYAPP_"))

        await manager.load()

        # File has debug=true, env has debug=false
        assert manager._config_data["debug"] is False  # env overrides
        # File has database.host=localhost, env has database.host=db.example.com
        assert manager._config_data["database"]["host"] == "db.example.com"
        # File has server.workers=2, env has server.workers=4
        assert manager._config_data["server"]["workers"] == 4

    @pytest.mark.asyncio
    async def test_load_with_schema(self, temp_dir):
        """Test loading with schema validation."""
        config_data = {
            "name": "TestApp",
            "database": {"host": "localhost", "port": 5432},
            "debug": True,
        }

        config_file = temp_dir / "config.json"
        config_file.write_text(json.dumps(config_data))

        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))
        manager.set_schema(AppConfig)

        await manager.load()

        assert isinstance(manager._config_instance, AppConfig)
        assert manager._config_instance.name == "TestApp"
        assert isinstance(manager._config_instance.database, DatabaseConfig)
        assert manager._config_instance.database.host == "localhost"

    @pytest.mark.asyncio
    async def test_load_schema_validation_error(self, temp_dir):
        """Test schema validation error during load."""
        config_data = {
            "name": "TestApp",
            # Missing required 'database' field
            "debug": True,
        }

        config_file = temp_dir / "config.json"
        config_file.write_text(json.dumps(config_data))

        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))
        manager.set_schema(AppConfig)

        with pytest.raises(ConfigurationError):
            await manager.load()

    def test_get_value(self):
        """Test getting configuration values."""
        manager = ConfigurationManager()
        manager._config_data = {"name": "app", "server": {"host": "localhost", "port": 8080}}

        assert manager.get() == manager._config_data
        assert manager.get("name") == "app"
        assert manager.get("server.host") == "localhost"
        assert manager.get("server.port") == 8080
        assert manager.get("missing", "default") == "default"

    def test_get_typed(self):
        """Test getting typed configuration sections."""
        manager = ConfigurationManager()
        manager._config_data = {"host": "localhost", "port": 3306}

        config = manager.get_typed(DatabaseConfig)
        assert isinstance(config, DatabaseConfig)
        assert config.host == "localhost"
        assert config.port == 3306

    def test_get_typed_nested(self):
        """Test getting typed nested configuration."""
        manager = ConfigurationManager()
        manager._config_data = {"name": "app", "database": {"host": "db.example.com", "port": 5432}}

        db_config = manager.get_typed(DatabaseConfig, "database")
        assert isinstance(db_config, DatabaseConfig)
        assert db_config.host == "db.example.com"

    def test_get_raw(self):
        """Test getting raw configuration data."""
        manager = ConfigurationManager()
        manager._config_data = {"a": 1, "b": 2}

        raw = manager.get_raw()
        assert raw == {"a": 1, "b": 2}

        # Should be a copy
        raw["c"] = 3
        assert "c" not in manager._config_data

    @pytest.mark.asyncio
    async def test_update_configuration(self):
        """Test updating configuration."""
        manager = ConfigurationManager()
        manager._config_data = {"debug": False, "version": "1.0"}

        changes = []

        async def track_changes(data):
            changes.append(data)

        manager.add_change_callback(track_changes)

        manager.update({"debug": True, "new_key": "value"})

        assert manager._config_data["debug"] is True
        assert manager._config_data["new_key"] == "value"
        assert manager._config_data["version"] == "1.0"

        # Wait for async callback
        await asyncio.sleep(0.1)
        assert len(changes) == 2

    @pytest.mark.asyncio
    async def test_reload_changed_file(self, temp_dir):
        """Test reloading when file changes."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"version": 1}')

        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))

        await manager.load()
        assert manager._config_data["version"] == 1

        # No change
        changed = await manager.reload()
        assert changed is False

        # Change file
        config_file.write_text('{"version": 2}')
        changed = await manager.reload()
        assert changed is True
        assert manager._config_data["version"] == 2

    @pytest.mark.asyncio
    async def test_reload_with_schema(self, temp_dir):
        """Test reloading with schema validation."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"name": "app", "version": "1.0", "debug": false}')

        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))
        manager.set_schema(TestConfig)

        await manager.load()
        assert manager._config_instance.version == "1.0"

        # Update with valid data
        config_file.write_text('{"name": "app", "version": "2.0", "debug": true}')
        await manager.reload()
        assert manager._config_instance.version == "2.0"
        assert manager._config_instance.debug is True

    @pytest.mark.asyncio
    async def test_reload_rollback_on_error(self, temp_dir):
        """Test rollback on reload error."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"name": "app", "version": "1.0"}')

        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))
        manager.set_schema(TestConfig)

        await manager.load()
        original_data = manager._config_data.copy()
        original_instance = manager._config_instance

        # Update with invalid data (missing required field)
        await asyncio.sleep(0.01)  # Ensure file modification time changes
        config_file.write_text('{"version": "2.0"}')

        with pytest.raises(ConfigurationError):
            await manager.reload()

        # Should rollback to original
        assert manager._config_data == original_data
        assert manager._config_instance == original_instance

    @pytest.mark.asyncio
    async def test_change_notifications(self):
        """Test configuration change notifications."""
        manager = ConfigurationManager()
        manager._config_data = {"a": 1, "b": {"c": 2}}

        changes = []

        async def track_changes(data):
            changes.append(data)

        manager.add_change_callback(track_changes)

        # Update configuration
        manager.update(
            {
                "a": 10,  # changed
                "b": {"c": 2, "d": 3},  # added b.d
                "e": 4,  # new key
            }
        )

        await asyncio.sleep(0.1)

        # Check changes
        change_paths = {c["path"] for c in changes}
        assert "a" in change_paths
        assert "b.d" in change_paths
        assert "e" in change_paths

        # Verify change details
        a_change = next(c for c in changes if c["path"] == "a")
        assert a_change["old_value"] == 1
        assert a_change["new_value"] == 10

    @pytest.mark.asyncio
    async def test_watch_configuration(self, temp_dir):
        """Test watching configuration for changes."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"counter": 0}')

        manager = ConfigurationManager()
        manager.add_source(FileSource(str(config_file)))
        await manager.load()

        # Start watching
        await manager.start_watching(interval=0.1)

        try:
            # Change file
            await asyncio.sleep(0.15)
            config_file.write_text('{"counter": 1}')

            # Wait for reload
            await asyncio.sleep(0.15)
            assert manager._config_data["counter"] == 1

        finally:
            manager.stop_watching()

    def test_from_sources_factory(self):
        """Test creating manager from source specifications."""
        manager = ConfigurationManager.from_sources(["config.json", "ENV"], env_prefix="TEST_")

        assert len(manager.sources) == 2
        assert isinstance(manager.sources[0], FileSource)
        assert manager.sources[0].path.name == "config.json"
        assert isinstance(manager.sources[1], EnvironmentSource)
        assert manager.sources[1].prefix == "TEST_"

    def test_from_sources_with_instances(self):
        """Test factory with source instances."""
        source = FileSource("custom.json")
        manager = ConfigurationManager.from_sources([source, "ENV"])

        assert len(manager.sources) == 2
        assert manager.sources[0] == source
        assert isinstance(manager.sources[1], EnvironmentSource)
