"""Tests for configuration sources."""

import json
import os
from pathlib import Path

import pytest

from whiskey_config.sources import EnvironmentSource, FileSource


class TestEnvironmentSource:
    """Test environment variable configuration source."""
    
    @pytest.mark.asyncio
    async def test_load_with_prefix(self, env_vars):
        """Test loading environment variables with prefix."""
        source = EnvironmentSource(prefix="MYAPP_")
        config = await source.load()
        
        assert config["debug"] is False
        assert config["database"]["host"] == "db.example.com"
        assert config["database"]["port"] == 3306
        assert config["server"]["workers"] == 4
        assert config["features"]["beta"]["feature"] is True
    
    @pytest.mark.asyncio
    async def test_load_without_prefix(self):
        """Test loading all environment variables."""
        os.environ["TEST_VAR"] = "test_value"
        
        try:
            source = EnvironmentSource(prefix="")
            config = await source.load()
            
            # Should include all environment variables
            assert "test" in config
            assert config["test"]["var"] == "test_value"
        finally:
            del os.environ["TEST_VAR"]
    
    @pytest.mark.asyncio
    async def test_type_conversion(self):
        """Test automatic type conversion."""
        test_vars = {
            "TEST_BOOL_TRUE": "true",
            "TEST_BOOL_FALSE": "false",
            "TEST_INT": "42",
            "TEST_FLOAT": "3.14",
            "TEST_LIST": "item1,item2,item3",
            "TEST_STRING": "just a string"
        }
        
        for key, value in test_vars.items():
            os.environ[key] = value
        
        try:
            source = EnvironmentSource(prefix="TEST_")
            config = await source.load()
            
            assert config["bool"]["true"] is True
            assert config["bool"]["false"] is False
            assert config["int"] == 42
            assert config["float"] == 3.14
            assert config["list"] == ["item1", "item2", "item3"]
            assert config["string"] == "just a string"
        finally:
            for key in test_vars:
                del os.environ[key]
    
    @pytest.mark.asyncio
    async def test_nested_structure(self):
        """Test nested configuration structure."""
        os.environ["APP_DATABASE_HOST"] = "localhost"
        os.environ["APP_DATABASE_PORT"] = "5432"
        os.environ["APP_DATABASE_CREDENTIALS_USERNAME"] = "user"
        os.environ["APP_DATABASE_CREDENTIALS_PASSWORD"] = "pass"
        
        try:
            source = EnvironmentSource(prefix="APP_")
            config = await source.load()
            
            assert config["database"]["host"] == "localhost"
            assert config["database"]["port"] == 5432
            assert config["database"]["credentials"]["username"] == "user"
            assert config["database"]["credentials"]["password"] == "pass"
        finally:
            for key in list(os.environ.keys()):
                if key.startswith("APP_"):
                    del os.environ[key]
    
    def test_can_reload(self):
        """Test that environment source can reload."""
        source = EnvironmentSource()
        assert source.can_reload() is True


class TestFileSource:
    """Test file configuration sources."""
    
    @pytest.mark.asyncio
    async def test_load_json_file(self, config_file):
        """Test loading JSON configuration file."""
        source = FileSource(str(config_file))
        config = await source.load()
        
        assert config["name"] == "TestApp"
        assert config["version"] == "1.0.0"
        assert config["debug"] is True
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, temp_dir):
        """Test loading non-existent file returns empty config."""
        source = FileSource(str(temp_dir / "nonexistent.json"))
        config = await source.load()
        
        assert config == {}
    
    @pytest.mark.asyncio
    async def test_auto_detect_format(self, temp_dir):
        """Test automatic format detection."""
        # JSON
        json_file = temp_dir / "config.json"
        json_file.write_text('{"test": "json"}')
        source = FileSource(str(json_file))
        assert source.format == "json"
        
        # YAML
        yaml_file = temp_dir / "config.yaml"
        yaml_file.touch()
        source = FileSource(str(yaml_file))
        assert source.format == "yaml"
        
        # TOML
        toml_file = temp_dir / "config.toml"
        toml_file.touch()
        source = FileSource(str(toml_file))
        assert source.format == "toml"
    
    def test_unknown_format(self, temp_dir):
        """Test unknown file format raises error."""
        unknown_file = temp_dir / "config.txt"
        unknown_file.touch()
        
        with pytest.raises(ValueError, match="Unknown file format"):
            FileSource(str(unknown_file))
    
    @pytest.mark.asyncio
    async def test_reload_on_change(self, temp_dir):
        """Test reloading when file changes."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"version": 1}')
        
        source = FileSource(str(config_file))
        
        # Initial load
        config = await source.load()
        assert config["version"] == 1
        
        # No change
        result = await source.reload()
        assert result is None
        
        # Change file
        config_file.write_text('{"version": 2}')
        result = await source.reload()
        assert result is not None
        assert result["version"] == 2
    
    @pytest.mark.asyncio
    async def test_reload_deleted_file(self, temp_dir):
        """Test reloading when file is deleted."""
        config_file = temp_dir / "config.json"
        config_file.write_text('{"exists": true}')
        
        source = FileSource(str(config_file))
        await source.load()
        
        # Delete file
        config_file.unlink()
        result = await source.reload()
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_load_yaml_file(self, yaml_config_file):
        """Test loading YAML configuration file."""
        # This will fail without PyYAML installed
        source = FileSource(str(yaml_config_file))
        
        try:
            config = await source.load()
            assert config["name"] == "TestApp"
            assert config["version"] == "2.0.0"
            assert config["database"]["host"] == "db.yaml.com"
        except ImportError as e:
            assert "PyYAML" in str(e)
    
    @pytest.mark.asyncio
    async def test_load_toml_file(self, toml_config_file):
        """Test loading TOML configuration file."""
        # This will fail without tomli installed
        source = FileSource(str(toml_config_file))
        
        try:
            config = await source.load()
            assert config["name"] == "TestApp"
            assert config["version"] == "3.0.0"
            assert config["database"]["host"] == "db.toml.com"
        except ImportError as e:
            assert "tomli" in str(e)
    
    def test_can_reload(self, config_file):
        """Test that file source can reload."""
        source = FileSource(str(config_file))
        assert source.can_reload() is True