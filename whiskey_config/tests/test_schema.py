"""Tests for configuration schema utilities."""

from dataclasses import dataclass
from typing import Optional

import pytest

from whiskey_config.schema import (
    ConfigurationError,
    convert_value,
    create_dataclass_from_dict,
    dataclass_to_dict,
    get_value_at_path,
    is_dataclass_instance,
    is_dataclass_type,
    merge_configs,
)


@dataclass
class SimpleConfig:
    """Simple test configuration."""

    name: str
    port: int
    enabled: bool = True


@dataclass
class NestedConfig:
    """Nested configuration."""

    host: str
    port: int = 8080


@dataclass
class ComplexConfig:
    """Complex configuration with nesting."""

    version: str
    debug: bool
    server: NestedConfig
    tags: list[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class TestDataclassChecks:
    """Test dataclass type and instance checks."""

    def test_is_dataclass_type(self):
        """Test checking if object is a dataclass type."""
        assert is_dataclass_type(SimpleConfig) is True
        assert is_dataclass_type(ComplexConfig) is True
        assert is_dataclass_type(str) is False
        assert is_dataclass_type(dict) is False

    def test_is_dataclass_instance(self):
        """Test checking if object is a dataclass instance."""
        instance = SimpleConfig(name="test", port=8080)
        assert is_dataclass_instance(instance) is True
        assert is_dataclass_instance(SimpleConfig) is False
        assert is_dataclass_instance("string") is False
        assert is_dataclass_instance({}) is False


class TestTypeConversion:
    """Test type conversion utilities."""

    def test_convert_basic_types(self):
        """Test converting basic types."""
        # Bool
        assert convert_value("true", bool) is True
        assert convert_value("false", bool) is False
        assert convert_value("yes", bool) is True
        assert convert_value("no", bool) is False
        assert convert_value(1, bool) is True
        assert convert_value(0, bool) is False

        # Int
        assert convert_value("42", int) == 42
        assert convert_value(42.5, int) == 42

        # Float
        assert convert_value("3.14", float) == 3.14
        assert convert_value(3, float) == 3.0

        # String
        assert convert_value(42, str) == "42"
        assert convert_value(True, str) == "True"

    def test_convert_none(self):
        """Test converting None values."""
        assert convert_value(None, str) is None
        assert convert_value(None, int) is None

    def test_convert_list(self):
        """Test converting to list types."""
        # From comma-separated string
        result = convert_value("a,b,c", list[str])
        assert result == ["a", "b", "c"]

        # From list
        result = convert_value([1, 2, 3], list[int])
        assert result == [1, 2, 3]

        # Type conversion within list
        result = convert_value(["1", "2", "3"], list[int])
        assert result == [1, 2, 3]

        # Single value to list
        result = convert_value("single", list[str])
        assert result == ["single"]

    def test_convert_optional(self):
        """Test converting Optional types."""
        # Optional[int]
        result = convert_value("42", Optional[int])
        assert result == 42

        # Optional with None
        result = convert_value(None, Optional[str])
        assert result is None

    def test_convert_dataclass(self):
        """Test converting to dataclass types."""
        data = {"name": "test", "port": "8080", "enabled": "false"}
        result = convert_value(data, SimpleConfig)

        assert isinstance(result, SimpleConfig)
        assert result.name == "test"
        assert result.port == 8080
        assert result.enabled is False

    def test_convert_invalid(self):
        """Test conversion errors."""
        with pytest.raises(ConfigurationError):
            convert_value("not a number", int)

        with pytest.raises(ConfigurationError):
            convert_value("string", SimpleConfig)


class TestDataclassCreation:
    """Test creating dataclass instances from dictionaries."""

    def test_create_simple_dataclass(self):
        """Test creating simple dataclass."""
        data = {"name": "test", "port": 8080}
        result = create_dataclass_from_dict(SimpleConfig, data)

        assert isinstance(result, SimpleConfig)
        assert result.name == "test"
        assert result.port == 8080
        assert result.enabled is True  # default value

    def test_create_with_type_conversion(self):
        """Test creating with automatic type conversion."""
        data = {"name": "test", "port": "9000", "enabled": "false"}
        result = create_dataclass_from_dict(SimpleConfig, data)

        assert result.name == "test"
        assert result.port == 9000
        assert result.enabled is False

    def test_create_nested_dataclass(self):
        """Test creating nested dataclass."""
        data = {
            "version": "1.0",
            "debug": True,
            "server": {"host": "localhost", "port": 8080},
            "tags": ["web", "api"],
        }
        result = create_dataclass_from_dict(ComplexConfig, data)

        assert isinstance(result, ComplexConfig)
        assert result.version == "1.0"
        assert result.debug is True
        assert isinstance(result.server, NestedConfig)
        assert result.server.host == "localhost"
        assert result.server.port == 8080
        assert result.tags == ["web", "api"]

    def test_missing_required_field(self):
        """Test error on missing required field."""
        data = {"port": 8080}  # missing 'name'

        with pytest.raises(ConfigurationError, match="Required field 'name' is missing"):
            create_dataclass_from_dict(SimpleConfig, data)

    def test_default_factory(self):
        """Test using default factory."""
        data = {"version": "1.0", "debug": False, "server": {"host": "test"}}
        result = create_dataclass_from_dict(ComplexConfig, data)

        assert result.tags == []  # from __post_init__


class TestDataclassToDict:
    """Test converting dataclass to dictionary."""

    def test_simple_dataclass_to_dict(self):
        """Test converting simple dataclass to dict."""
        config = SimpleConfig(name="test", port=8080, enabled=False)
        result = dataclass_to_dict(config)

        assert result == {"name": "test", "port": 8080, "enabled": False}

    def test_nested_dataclass_to_dict(self):
        """Test converting nested dataclass to dict."""
        config = ComplexConfig(
            version="1.0",
            debug=True,
            server=NestedConfig(host="localhost", port=9000),
            tags=["a", "b"],
        )
        result = dataclass_to_dict(config)

        assert result == {
            "version": "1.0",
            "debug": True,
            "server": {"host": "localhost", "port": 9000},
            "tags": ["a", "b"],
        }

    def test_non_dataclass_passthrough(self):
        """Test non-dataclass objects pass through."""
        assert dataclass_to_dict("string") == "string"
        assert dataclass_to_dict(42) == 42
        assert dataclass_to_dict([1, 2, 3]) == [1, 2, 3]


class TestConfigMerging:
    """Test configuration merging."""

    def test_merge_simple_configs(self):
        """Test merging simple configurations."""
        base = {"a": 1, "b": 2, "c": 3}
        override = {"b": 20, "d": 4}

        result = merge_configs(base, override)
        assert result == {"a": 1, "b": 20, "c": 3, "d": 4}

    def test_merge_nested_configs(self):
        """Test merging nested configurations."""
        base = {"server": {"host": "localhost", "port": 8080}, "debug": False}
        override = {"server": {"port": 9000}, "debug": True}

        result = merge_configs(base, override)
        assert result == {"server": {"host": "localhost", "port": 9000}, "debug": True}

    def test_merge_with_new_keys(self):
        """Test merging adds new keys."""
        base = {"a": 1}
        override = {"b": 2}

        result = merge_configs(base, override)
        assert result == {"a": 1, "b": 2}

    def test_merge_replaces_non_dict_values(self):
        """Test non-dict values are replaced, not merged."""
        base = {"list": [1, 2, 3], "value": "old"}
        override = {"list": [4, 5], "value": "new"}

        result = merge_configs(base, override)
        assert result == {"list": [4, 5], "value": "new"}


class TestGetValueAtPath:
    """Test getting values at paths."""

    def test_get_from_dict(self):
        """Test getting value from dictionary."""
        config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "user", "password": "pass"},
            }
        }

        assert get_value_at_path(config, "database.host") == "localhost"
        assert get_value_at_path(config, "database.port") == 5432
        assert get_value_at_path(config, "database.credentials.username") == "user"
        assert get_value_at_path(config, "") == config

    def test_get_from_dataclass(self):
        """Test getting value from dataclass."""
        config = ComplexConfig(
            version="1.0", debug=True, server=NestedConfig(host="localhost", port=8080)
        )

        assert get_value_at_path(config, "version") == "1.0"
        assert get_value_at_path(config, "server.host") == "localhost"
        assert get_value_at_path(config, "server.port") == 8080

    def test_get_invalid_path(self):
        """Test error on invalid path."""
        config = {"a": {"b": 1}}

        with pytest.raises(ConfigurationError, match="No key 'c' at path 'a.c'"):
            get_value_at_path(config, "a.c")

        with pytest.raises(ConfigurationError, match="Cannot navigate into"):
            get_value_at_path(config, "a.b.c")
