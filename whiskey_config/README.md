# Whiskey Config Extension ⚙️

Powerful configuration management for Whiskey applications with hot reloading, validation, and seamless dependency injection integration.

## Why Whiskey Config?

Managing configuration across development, staging, and production environments is challenging. Whiskey Config provides:

- **Type-Safe Configuration**: Use dataclasses with full type validation
- **Multiple Sources**: Layer configs from files, environment variables, and CLI
- **Hot Reloading**: Change configuration without restarting your application
- **DI Integration**: Inject configuration values directly into your components
- **Schema Validation**: Catch configuration errors early
- **Secret Management**: Secure handling of sensitive values

## Installation

```bash
pip install whiskey[config]  # Includes whiskey-config
# or
pip install whiskey-config

# With format support
pip install whiskey-config[yaml]   # YAML support
pip install whiskey-config[toml]   # TOML support
pip install whiskey-config[all]    # All formats
```

## Quick Start

```python
from dataclasses import dataclass
from whiskey import Whiskey, inject
from whiskey_config import config_extension, Setting

# Create app with config extension
app = Whiskey()
app.use(config_extension)

# Define your configuration schema
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "myapp"
    user: str = "postgres"
    password: str = ""
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

@dataclass
class AppConfig:
    debug: bool = False
    secret_key: str = ""
    database: DatabaseConfig = None
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()

# Configure sources and options
app.configure_config(
    schema=AppConfig,
    sources=[
        "config.yaml",        # Base configuration
        "config.local.yaml",  # Local overrides (gitignored)
        "ENV"                 # Environment variables
    ],
    env_prefix="MYAPP_",
    watch=True,               # Enable hot reloading
    watch_interval=1.0        # Check every second
)

# Use configuration in your services
@app.component
class DatabaseService:
    def __init__(self, config: Annotated[DatabaseConfig, Inject()]):
        self.config = config
        self.connection = None
    
    async def connect(self):
        self.connection = await create_connection(self.config.url)

# Or inject specific values
@inject
async def create_server(
    host: str = Setting("server.host", default="0.0.0.0"),
    port: int = Setting("server.port", default=8000),
    debug: bool = Setting("debug")
):
    server = Server(host, port)
    if debug:
        server.enable_debug_mode()
    return server
```

## Core Features

### 1. Configuration Sources

Layer configuration from multiple sources in priority order:

```python
app.configure_config(
    schema=AppConfig,
    sources=[
        "config.yaml",       # 1. Base configuration
        "config.prod.yaml",  # 2. Environment-specific
        "config.local.yaml", # 3. Local overrides
        "ENV",              # 4. Environment variables (highest priority)
        "CLI"               # 5. Command-line arguments
    ]
)
```

#### File Formats

**YAML** (recommended):
```yaml
debug: false
server:
  host: 0.0.0.0
  port: 8000
  workers: 4

database:
  host: localhost
  port: 5432
  name: myapp
  user: postgres
  password: ${DB_PASSWORD}  # Environment variable substitution

redis:
  url: redis://localhost:6379
  ttl: 3600
```

**JSON**:
```json
{
  "debug": false,
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 4
  },
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "myapp"
  }
}
```

**TOML**:
```toml
debug = false

[server]
host = "0.0.0.0"
port = 8000
workers = 4

[database]
host = "localhost"
port = 5432
name = "myapp"
```

#### Environment Variables

```bash
# Simple values
export MYAPP_DEBUG=true
export MYAPP_SECRET_KEY="super-secret-key"

# Nested values use double underscore
export MYAPP_DATABASE__HOST=db.example.com
export MYAPP_DATABASE__PORT=5432
export MYAPP_DATABASE__PASSWORD="secure-password"

# Lists use comma separation
export MYAPP_ALLOWED_HOSTS="localhost,example.com,*.example.com"

# JSON for complex values
export MYAPP_FEATURES='{"auth": true, "api_v2": false}'
```

### 2. Dependency Injection Patterns

#### Inject Entire Config

```python
@app.component
class Whiskey:
    def __init__(self, config: Annotated[AppConfig, Inject()]):
        self.config = config
        self.debug = config.debug
```

#### Inject Config Sections

```python
from whiskey_config import ConfigSection

@app.component
class DatabaseManager:
    def __init__(self, 
                 db_config: DatabaseConfig = ConfigSection(DatabaseConfig, "database")):
        self.config = db_config
        self.pool = None
    
    async def connect(self):
        self.pool = await create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.name,
            user=self.config.user,
            password=self.config.password
        )
```

#### Inject Individual Settings

```python
from whiskey_config import Setting

@inject
async def create_redis_client(
    url: str = Setting("redis.url"),
    ttl: int = Setting("redis.ttl", default=3600),
    debug: bool = Setting("debug")
) -> Redis:
    client = Redis.from_url(url)
    if debug:
        client.set_debug(True)
    return client

# With type conversion
@inject
def configure_server(
    workers: int = Setting("server.workers", cast=int),
    timeout: float = Setting("server.timeout", cast=float, default=30.0),
    allowed_hosts: list[str] = Setting("allowed_hosts", cast=lambda x: x.split(","))
):
    pass
```

### 3. Hot Reloading

Enable configuration changes without restarting:

```python
app.configure_config(
    schema=AppConfig,
    sources=["config.yaml", "ENV"],
    watch=True,                    # Enable watching
    watch_interval=1.0,            # Check every second
    watch_callback=on_config_reload # Optional callback
)

@app.on("config.changed")
async def handle_config_change(event_data):
    changed_path = event_data["path"]
    old_value = event_data["old_value"]
    new_value = event_data["new_value"]
    
    print(f"Config changed: {changed_path}")
    print(f"  Old: {old_value}")
    print(f"  New: {new_value}")
    
    # React to specific changes
    if changed_path.startswith("database."):
        await reconnect_database()
    elif changed_path == "debug":
        set_log_level("DEBUG" if new_value else "INFO")
```

### 4. Validation and Schemas

Use dataclass features for validation:

```python
from dataclasses import dataclass, field
from typing import List, Optional
import re

def validate_email(email: str) -> str:
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise ValueError(f"Invalid email: {email}")
    return email

def validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {port}")
    return port

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = field(default=8000, metadata={"validator": validate_port})
    workers: int = 4
    
    def __post_init__(self):
        self.port = validate_port(self.port)
        if self.workers < 1:
            raise ValueError("Workers must be at least 1")

@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int = 587
    username: str
    password: str
    from_email: str = field(metadata={"validator": validate_email})
    
    def __post_init__(self):
        self.from_email = validate_email(self.from_email)
```

### 5. Secret Management

Handle sensitive configuration securely:

```python
from whiskey_config import Secret, SecretStr

@dataclass
class SecurityConfig:
    # Secret values are masked in logs/debug output
    api_key: SecretStr = field(default_factory=lambda: SecretStr(""))
    database_password: Secret[str] = field(default_factory=lambda: Secret(""))
    private_key: Secret[bytes] = field(default_factory=lambda: Secret(b""))
    
    def __post_init__(self):
        # Validate secrets exist in production
        if not self.api_key.get_secret_value():
            raise ValueError("API key is required")

# Use secrets
@inject
async def connect_to_api(
    config: Annotated[SecurityConfig, Inject()]
):
    headers = {
        "Authorization": f"Bearer {config.api_key.get_secret_value()}"
    }
    # Secret value is only exposed when explicitly requested
```

### 6. Dynamic Configuration

Register configuration providers for dynamic values:

```python
from whiskey_config import ConfigProvider

@app.config_provider("feature_flags")
class FeatureFlagProvider(ConfigProvider):
    async def get(self, key: str) -> Any:
        # Fetch from feature flag service
        return await feature_service.is_enabled(key)
    
    async def watch(self, callback):
        # Subscribe to changes
        await feature_service.subscribe(callback)

# Use dynamic config
@inject
async def handle_request(
    new_feature: bool = Setting("feature_flags.new_ui")
):
    if new_feature:
        return render_new_ui()
    return render_old_ui()
```

## Advanced Patterns

### Configuration Inheritance

```python
@dataclass
class BaseConfig:
    app_name: str = "myapp"
    version: str = "1.0.0"
    debug: bool = False

@dataclass
class DevelopmentConfig(BaseConfig):
    debug: bool = True
    database_host: str = "localhost"

@dataclass
class ProductionConfig(BaseConfig):
    debug: bool = False
    database_host: str = "db.production.internal"
    ssl_required: bool = True

# Select based on environment
env = os.getenv("APP_ENV", "development")
ConfigClass = {
    "development": DevelopmentConfig,
    "production": ProductionConfig
}[env]

app.configure_config(
    schema=ConfigClass,
    sources=["config.yaml", "ENV"]
)
```

### Computed Properties

```python
@dataclass
class AppConfig:
    base_url: str
    api_version: str = "v1"
    
    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/{self.api_version}"
    
    @property
    def webhook_url(self) -> str:
        return f"{self.base_url}/webhooks"

# Use computed properties
@inject
def setup_api_client(
    api_url: str = Setting("api_url")  # Uses the @property
):
    return APIClient(api_url)
```

### Environment-Specific Files

```python
import os

env = os.getenv("APP_ENV", "development")

sources = [
    "config/base.yaml",           # Shared configuration
    f"config/{env}.yaml",         # Environment-specific
    "config/local.yaml",          # Local overrides
    "ENV"                         # Environment variables
]

app.configure_config(
    schema=AppConfig,
    sources=[s for s in sources if os.path.exists(s) or s == "ENV"]
)
```

### Configuration Profiles

```python
@dataclass
class ProfileConfig:
    profiles: dict[str, dict] = field(default_factory=dict)
    active_profile: str = "default"
    
    def get_profile_value(self, key: str):
        profile = self.profiles.get(self.active_profile, {})
        return profile.get(key, self.profiles["default"].get(key))

# config.yaml
profiles:
  default:
    cache_ttl: 3600
    rate_limit: 100
  
  performance:
    cache_ttl: 7200
    rate_limit: 1000
  
  development:
    cache_ttl: 0
    rate_limit: 0

active_profile: ${PROFILE:default}
```

## Testing

Mock configuration for tests:

```python
import pytest
from whiskey.testing import create_test_app

@pytest.fixture
def app():
    app = create_test_app()
    app.use(config_extension)
    
    # Use test configuration
    test_config = AppConfig(
        debug=True,
        database=DatabaseConfig(
            host="localhost",
            port=5432,
            name="test_db"
        )
    )
    
    app.configure_config(
        schema=AppConfig,
        sources=[],  # No external sources
        initial=test_config  # Provide config directly
    )
    
    return app

def test_with_different_config(app):
    # Override specific values
    with app.config_context(debug=False):
        service = app.container.resolve_sync(MyService)
        assert not service.debug_mode
```

## Best Practices

### 1. Use Type-Safe Schemas

```python
# ✅ Good - type-safe with validation
@dataclass
class Config:
    port: int = 8000
    host: str = "localhost"
    
    def __post_init__(self):
        if not 1 <= self.port <= 65535:
            raise ValueError(f"Invalid port: {self.port}")

# ❌ Avoid - no type safety
config = {
    "port": "8000",  # String instead of int!
    "host": "localhost"
}
```

### 2. Layer Configuration Appropriately

```python
# ✅ Good - clear precedence
sources = [
    "config/defaults.yaml",    # 1. Built-in defaults
    "config/app.yaml",         # 2. Whiskey config  
    "/etc/myapp/config.yaml",  # 3. System config
    "~/.myapp/config.yaml",    # 4. User config
    ".myapp.yaml",             # 5. Project config
    "ENV"                      # 6. Environment (highest)
]

# ❌ Avoid - confusing precedence
sources = ["ENV", "config.yaml", "defaults.yaml"]
```

### 3. Validate Early

```python
# ✅ Good - validate on startup
@app.on_startup
async def validate_config():
    config = await app.container.resolve(AppConfig)
    
    if not config.secret_key:
        raise ValueError("SECRET_KEY must be set in production")
    
    if config.database.password == "default":
        logger.warning("Using default database password!")
```

### 4. Document Configuration

```python
@dataclass
class APIConfig:
    """External API configuration.
    
    Configure these via environment variables:
    - API_ENDPOINT: The API base URL
    - API_TIMEOUT: Request timeout in seconds
    - API_RETRY_COUNT: Number of retries on failure
    """
    endpoint: str = field(
        default="https://api.example.com",
        metadata={"help": "API base URL"}
    )
    timeout: int = field(
        default=30,
        metadata={"help": "Request timeout in seconds"}
    )
    retry_count: int = field(
        default=3,
        metadata={"help": "Number of retries on failure"}
    )
```

## Examples

See the `examples/` directory for complete examples:
- `basic_config.py` - Simple configuration setup
- `multi_env.py` - Multi-environment configuration
- `hot_reload.py` - Configuration with hot reloading
- `secrets.py` - Secure secret management

## Contributing

We welcome contributions! See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.