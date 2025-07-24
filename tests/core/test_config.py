"""Tests for configuration management."""

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from whiskey.core.config import ConfigurationManager, EnvironmentSource, YamlSource


class TestEnvironmentSource:
    """Test EnvironmentSource functionality."""
    
    @pytest.mark.unit
    async def test_env_source_get(self):
        """Test getting values from environment."""
        # Set test env var
        os.environ["WHISKEY_TEST_KEY"] = "test_value"
        
        try:
            source = EnvironmentSource()
            value = await source.get("test_key")
            assert value == "test_value"
            
            # Test with default
            value = await source.get("missing_key", default="default")
            assert value == "default"
        finally:
            os.environ.pop("WHISKEY_TEST_KEY", None)
    
    @pytest.mark.unit
    async def test_env_source_set(self):
        """Test setting values to environment."""
        source = EnvironmentSource()
        
        await source.set("new_key", "new_value")
        
        assert os.environ.get("WHISKEY_NEW_KEY") == "new_value"
        
        # Cleanup
        os.environ.pop("WHISKEY_NEW_KEY", None)
    
    @pytest.mark.unit
    async def test_env_source_custom_prefix(self):
        """Test environment source with custom prefix."""
        os.environ["MYAPP_CONFIG_VALUE"] = "custom"
        
        try:
            source = EnvironmentSource(prefix="MYAPP_")
            value = await source.get("config_value")
            assert value == "custom"
        finally:
            os.environ.pop("MYAPP_CONFIG_VALUE", None)


class TestYamlSource:
    """Test YamlSource functionality."""
    
    @pytest.mark.unit
    async def test_yaml_source_basic(self):
        """Test basic YAML source reading."""
        config_data = {
            "database": {
                "host": "localhost",
                "port": 5432
            },
            "app": {
                "name": "TestApp",
                "debug": True
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            source = YamlSource(temp_path)
            
            # Test nested access
            assert await source.get("database.host") == "localhost"
            assert await source.get("database.port") == 5432
            assert await source.get("app.name") == "TestApp"
            assert await source.get("app.debug") is True
            
            # Test missing key
            assert await source.get("missing.key") is None
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.unit
    async def test_yaml_source_set(self):
        """Test setting values in YAML source."""
        initial_data = {"key": "value"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(initial_data, f)
            temp_path = f.name
        
        try:
            source = YamlSource(temp_path)
            
            # Set new value
            await source.set("new_key", "new_value")
            
            # Verify it's stored
            assert await source.get("new_key") == "new_value"
            
            # Verify file is updated
            source2 = YamlSource(temp_path)
            assert await source2.get("new_key") == "new_value"
        finally:
            os.unlink(temp_path)


class TestConfigurationManager:
    """Test ConfigurationManager functionality."""
    
    @pytest.mark.unit
    async def test_config_manager_basic(self):
        """Test basic configuration manager operations."""
        manager = ConfigurationManager()
        
        # Add environment source
        os.environ["WHISKEY_TEST_VALUE"] = "from_env"
        try:
            manager.add_source(EnvironmentSource())
            
            value = await manager.get("test_value")
            assert value == "from_env"
        finally:
            os.environ.pop("WHISKEY_TEST_VALUE", None)
    
    @pytest.mark.unit
    async def test_config_manager_multiple_sources(self):
        """Test configuration with multiple sources."""
        manager = ConfigurationManager()
        
        # Create YAML file
        yaml_data = {"shared_key": "from_yaml", "yaml_only": "yaml_value"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_data, f)
            temp_path = f.name
        
        # Set env var
        os.environ["WHISKEY_SHARED_KEY"] = "from_env"
        os.environ["WHISKEY_ENV_ONLY"] = "env_value"
        
        try:
            # Add sources (env first - higher priority)
            manager.add_source(EnvironmentSource())
            manager.add_source(YamlSource(temp_path))
            
            # Env should win for shared key
            assert await manager.get("shared_key") == "from_env"
            
            # Both unique keys should work
            assert await manager.get("env_only") == "env_value"
            assert await manager.get("yaml_only") == "yaml_value"
        finally:
            os.unlink(temp_path)
            os.environ.pop("WHISKEY_SHARED_KEY", None)
            os.environ.pop("WHISKEY_ENV_ONLY", None)
    
    @pytest.mark.unit
    async def test_config_manager_cache(self):
        """Test configuration caching."""
        manager = ConfigurationManager()
        
        # Add a source that tracks access
        access_count = 0
        
        class CountingSource:
            async def get(self, key, default=None):
                nonlocal access_count
                access_count += 1
                return "value" if key == "test" else default
            
            async def set(self, key, value):
                pass
        
        manager.add_source(CountingSource())
        
        # First access
        assert await manager.get("test") == "value"
        assert access_count == 1
        
        # Second access should use cache
        assert await manager.get("test") == "value"
        assert access_count == 1
    
    @pytest.mark.unit
    async def test_config_manager_set(self):
        """Test setting configuration values."""
        manager = ConfigurationManager()
        
        # Set value
        await manager.set("new_key", "new_value")
        
        # Should be in cache
        assert await manager.get("new_key") == "new_value"
    
    @pytest.mark.unit
    def test_configure_dataclass(self):
        """Test configuring a dataclass."""
        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432
            database: str = "test"
        
        manager = ConfigurationManager()
        
        # Set some config values
        asyncio.run(manager.set("databaseconfig.host", "production.db"))
        asyncio.run(manager.set("databaseconfig.port", 3306))
        
        # Configure the dataclass
        config = manager.configure(DatabaseConfig)
        
        assert config.host == "production.db"
        assert config.port == 3306
        assert config.database == "test"  # Default value
    
    @pytest.mark.unit
    async def test_reload_configuration(self):
        """Test reloading configuration."""
        manager = ConfigurationManager()
        
        # Add value to cache
        await manager.set("cached_key", "cached_value")
        assert "cached_key" in manager._cache
        
        # Reload
        await manager.reload()
        
        # Cache should be cleared
        assert "cached_key" not in manager._cache