"""Test configuration and fixtures for whiskey-config tests."""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_file(temp_dir):
    """Create a test configuration file."""
    config = {
        "name": "TestApp",
        "version": "1.0.0",
        "debug": True,
        "database": {
            "host": "localhost",
            "port": 5432,
            "username": "testuser",
            "password": "testpass",
        },
        "server": {"host": "0.0.0.0", "port": 8000, "workers": 2},
        "features": {"new_feature": True, "beta_feature": False},
    }

    config_path = temp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    return config_path


@pytest.fixture
def env_vars():
    """Set up test environment variables."""
    original_env = os.environ.copy()

    # Set test environment variables
    test_vars = {
        "MYAPP_DEBUG": "false",
        "MYAPP_DATABASE_HOST": "db.example.com",
        "MYAPP_DATABASE_PORT": "3306",
        "MYAPP_SERVER_WORKERS": "4",
        "MYAPP_FEATURES_BETA_FEATURE": "true",
    }

    for key, value in test_vars.items():
        os.environ[key] = value

    yield test_vars

    # Restore original environment
    for key in test_vars:
        if key in os.environ:
            del os.environ[key]

    for key, value in original_env.items():
        os.environ[key] = value


@pytest.fixture
def yaml_config_file(temp_dir):
    """Create a YAML configuration file."""
    yaml_content = """
name: TestApp
version: 2.0.0
debug: false
database:
  host: db.yaml.com
  port: 5433
  username: yamluser
  password: yamlpass
server:
  host: 127.0.0.1
  port: 8080
  workers: 8
"""

    config_path = temp_dir / "config.yaml"
    config_path.write_text(yaml_content)
    return config_path


@pytest.fixture
def toml_config_file(temp_dir):
    """Create a TOML configuration file."""
    toml_content = """
name = "TestApp"
version = "3.0.0"
debug = true

[database]
host = "db.toml.com"
port = 5434
username = "tomluser"
password = "tomlpass"

[server]
host = "localhost"
port = 9000
workers = 16
"""

    config_path = temp_dir / "config.toml"
    config_path.write_text(toml_content)
    return config_path
