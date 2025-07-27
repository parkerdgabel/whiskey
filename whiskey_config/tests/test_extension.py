"""Tests for the configuration extension."""

import asyncio
import json
from dataclasses import dataclass

import pytest

from whiskey import Application, inject
from whiskey_config import Setting, config_extension


@dataclass
class TestDatabaseConfig:
    """Test database configuration."""

    host: str = "localhost"
    port: int = 5432
    username: str = "user"
    password: str = "pass"


@dataclass
class TestAppConfig:
    """Test application configuration."""

    name: str = "TestApp"
    debug: bool = False
    database: TestDatabaseConfig = None

    def __post_init__(self):
        if self.database is None:
            self.database = TestDatabaseConfig()


class TestConfigExtension:
    """Test configuration extension functionality."""

    @pytest.mark.asyncio
    async def test_extension_setup(self):
        """Test basic extension setup."""
        app = Application()
        app.use(config_extension)

        # Check that extension adds required attributes
        assert hasattr(app, "config_manager")
        assert hasattr(app, "configure_config")
        assert hasattr(app, "update_config")
        assert hasattr(app, "get_config")

        # Check decorators
        assert hasattr(app, "config")
        assert hasattr(app, "feature")
        assert "config" in app._component_decorators
        assert "feature" in app._component_decorators

    @pytest.mark.asyncio
    async def test_configure_with_schema(self, temp_dir):
        """Test configuring with schema."""
        config_file = temp_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "name": "MyApp",
                    "debug": True,
                    "database": {"host": "db.example.com", "port": 3306},
                }
            )
        )

        app = Application()
        app.use(config_extension)

        app.configure_config(schema=TestAppConfig, sources=[str(config_file)], env_prefix="TEST_")

        async with app.lifespan():
            # Schema should be registered for injection
            config = await app.container.resolve(TestAppConfig)
            assert config.name == "MyApp"
            assert config.debug is True
            assert config.database.host == "db.example.com"
            assert config.database.port == 3306

    @pytest.mark.asyncio
    async def test_config_decorator(self):
        """Test @app.config decorator."""
        app = Application()
        app.use(config_extension)

        @app.config("database")
        @dataclass
        class DbConfig:
            host: str = "localhost"
            port: int = 5432

        # Configure with data
        app.configure_config(sources=[], env_prefix="TEST_")

        async with app.lifespan():
            # Manually set config data after startup
            app.config_manager._config_data = {
                "database": {"host": "configured.host", "port": 9999}
            }

            # Should be injectable
            db_config = await app.container.resolve(DbConfig)
            assert db_config.host == "configured.host"
            assert db_config.port == 9999

    @pytest.mark.asyncio
    async def test_setting_injection(self, temp_dir):
        """Test Setting provider injection."""
        config_file = temp_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {"app_name": "TestApp", "debug": True, "server": {"host": "0.0.0.0", "port": 8080}}
            )
        )

        app = Application()
        app.use(config_extension)
        app.configure_config(sources=[str(config_file)])

        @app.component
        class Service:
            @inject
            def __init__(
                self,
                name: str = Setting("app_name"),
                debug: bool = Setting("debug"),
                host: str = Setting("server.host"),
                port: int = Setting("server.port", default=3000),
            ):
                self.name = name
                self.debug = debug
                self.host = host
                self.port = port

        async with app.lifespan():
            service = await app.container.resolve(Service)
            assert service.name == "TestApp"
            assert service.debug is True
            assert service.host == "0.0.0.0"
            assert service.port == 8080

    @pytest.mark.asyncio
    async def test_setting_default_value(self):
        """Test Setting with default value."""
        app = Application()
        app.use(config_extension)
        app.configure_config(sources=[])

        @app.component
        class Service:
            @inject
            def __init__(self, missing: str = Setting("missing.value", default="default")):
                self.missing = missing

        async with app.lifespan():
            service = await app.container.resolve(Service)
            assert service.missing == "default"

    @pytest.mark.asyncio
    async def test_feature_flag(self):
        """Test feature flag functionality."""
        app = Application()
        app.use(config_extension)

        # Configure with features
        app.config_manager._config_data = {"features": {"new_feature": True, "beta_feature": False}}

        results = []

        @app.feature("new_feature")
        async def enabled_feature():
            results.append("enabled")
            return "enabled"

        @app.feature("beta_feature")
        async def disabled_feature():
            results.append("disabled")
            return "disabled"

        @app.feature("missing_feature", default=True)
        async def default_enabled():
            results.append("default")
            return "default"

        # Test features
        result = await enabled_feature()
        assert result == "enabled"

        result = await disabled_feature()
        assert result is None  # Feature disabled

        result = await default_enabled()
        assert result == "default"

        assert results == ["enabled", "default"]

    @pytest.mark.asyncio
    async def test_configuration_events(self):
        """Test configuration events."""
        app = Application()
        app.use(config_extension)

        events = []

        @app.on("config.loaded")
        async def on_loaded(data):
            events.append(("loaded", data))

        @app.on("config.changed")
        async def on_changed(data):
            events.append(("changed", data))

        app.configure_config(sources=[])

        async with app.lifespan():
            # Should emit loaded event
            assert len(events) == 1
            assert events[0][0] == "loaded"

            # Update config
            app.update_config({"new_key": "value"})

            # Wait for async event
            await asyncio.sleep(0.1)

            # Should have change event
            assert len(events) == 2
            assert events[1][0] == "changed"
            assert events[1][1]["path"] == "new_key"
            assert events[1][1]["new_value"] == "value"

    @pytest.mark.asyncio
    async def test_update_config_method(self):
        """Test update_config method."""
        app = Application()
        app.use(config_extension)
        app.configure_config(sources=[])

        app.config_manager._config_data = {"a": 1, "b": 2}

        app.update_config({"a": 10, "c": 3})

        assert app.get_config("a") == 10
        assert app.get_config("b") == 2
        assert app.get_config("c") == 3

    @pytest.mark.asyncio
    async def test_get_config_method(self):
        """Test get_config method."""
        app = Application()
        app.use(config_extension)
        app.configure_config(sources=[])

        app.config_manager._config_data = {"app": {"name": "test", "version": "1.0"}}

        assert app.get_config() == app.config_manager._config_data
        assert app.get_config("app.name") == "test"
        assert app.get_config("app.version") == "1.0"
        assert app.get_config("missing", "default") == "default"

    @pytest.mark.asyncio
    async def test_hot_reload_configuration(self, temp_dir):
        """Test hot reload functionality."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"counter": 0}')

        app = Application()
        app.use(config_extension)

        changes = []

        @app.on("config.changed")
        async def track_changes(data):
            changes.append(data)

        app.configure_config(sources=[str(config_file)], watch=True, watch_interval=0.1)

        async with app.lifespan():
            assert app.get_config("counter") == 0

            # Update file
            await asyncio.sleep(0.15)
            config_file.write_text('{"counter": 1}')

            # Wait for reload
            await asyncio.sleep(0.15)
            assert app.get_config("counter") == 1

            # Check change event
            assert len(changes) == 1
            assert changes[0]["path"] == "counter"
            assert changes[0]["old_value"] == 0
            assert changes[0]["new_value"] == 1

    @pytest.mark.asyncio
    async def test_schema_validation_error(self):
        """Test schema validation error handling."""
        app = Application()
        app.use(config_extension)

        with pytest.raises(ValueError, match="Schema must be a dataclass"):
            app.configure_config(schema=str)  # Not a dataclass

    @pytest.mark.asyncio
    async def test_config_decorator_validation(self):
        """Test config decorator validation."""
        app = Application()
        app.use(config_extension)

        with pytest.raises(ValueError, match="must be a dataclass"):

            @app.config("invalid")
            class NotADataclass:
                pass

    @pytest.mark.asyncio
    async def test_environment_override(self, temp_dir, monkeypatch):
        """Test environment variable override."""
        config_file = temp_dir / "config.json"
        config_file.write_text(json.dumps({"debug": False, "port": 8080}))

        # Set environment variables
        monkeypatch.setenv("MYAPP_DEBUG", "true")
        monkeypatch.setenv("MYAPP_PORT", "9000")

        app = Application()
        app.use(config_extension)
        app.configure_config(sources=[str(config_file), "ENV"], env_prefix="MYAPP_")

        async with app.lifespan():
            # Environment should override file
            assert app.get_config("debug") is True
            assert app.get_config("port") == 9000
