# Whiskey Config Extension

Configuration management extension for the Whiskey framework.

## Features

- Multiple configuration sources (environment variables, files, CLI)
- Type-safe configuration using dataclasses
- Configuration validation
- Hot reloading support
- Seamless integration with Whiskey's dependency injection

## Installation

```bash
pip install whiskey-config
```

For YAML support:
```bash
pip install whiskey-config[yaml]
```

For TOML support:
```bash
pip install whiskey-config[toml]
```

## Quick Start

```python
from dataclasses import dataclass
from whiskey import Application
from whiskey_config import config_extension

app = Application()
app.use(config_extension)

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    username: str = ""
    password: str = ""

@dataclass
class AppConfig:
    debug: bool = False
    database: DatabaseConfig = None

# Configure the extension
app.configure_config(
    schema=AppConfig,
    sources=["config.json", "ENV"],
    env_prefix="MYAPP_"
)

# Use configuration in components
@app.component
class DatabaseService:
    @inject
    def __init__(self, config: DatabaseConfig):
        self.config = config
```

## Configuration Sources

### Environment Variables

```bash
export MYAPP_DEBUG=true
export MYAPP_DATABASE_HOST=db.example.com
export MYAPP_DATABASE_PORT=5432
```

### JSON Files

```json
{
  "debug": false,
  "database": {
    "host": "localhost",
    "port": 5432,
    "username": "user",
    "password": "secret"
  }
}
```

### YAML Files (optional)

```yaml
debug: false
database:
  host: localhost
  port: 5432
  username: user
  password: secret
```

## Advanced Usage

### Configuration Sections

```python
@app.config("api")
@dataclass
class APIConfig:
    endpoint: str = "https://api.example.com"
    timeout: int = 30

# Inject specific configuration section
@inject
def process_api(config: APIConfig):
    # Use API configuration
    pass
```

### Individual Settings

```python
from whiskey_config import Setting

@app.component
class Service:
    @inject
    def __init__(self, 
                 debug: bool = Setting("debug"),
                 db_host: str = Setting("database.host")):
        self.debug = debug
        self.db_host = db_host
```

### Configuration Events

```python
@app.on("config.changed")
async def on_config_change(data):
    print(f"Configuration changed: {data['path']}")
```

## License

MIT