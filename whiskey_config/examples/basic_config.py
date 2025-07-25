"""Basic configuration example using Whiskey Config extension."""

import os
from dataclasses import dataclass

from whiskey import inject
from whiskey_config import Setting, config_extension


# Define configuration schema using dataclasses
@dataclass
class DatabaseConfig:
    """Database configuration."""

    host: str = "localhost"
    port: int = 5432
    username: str = "user"
    password: str = "password"
    database: str = "myapp"

    def __post_init__(self):
        """Validate configuration."""
        if not self.username:
            raise ValueError("Database username is required")
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    debug: bool = False


@dataclass
class AppConfig:
    """Main application configuration."""

    name: str = "MyApp"
    version: str = "1.0.0"
    debug: bool = False
    database: DatabaseConfig = None
    server: ServerConfig = None

    def __post_init__(self):
        """Initialize nested configs if not provided."""
        if self.database is None:
            self.database = DatabaseConfig()
        if self.server is None:
            self.server = ServerConfig()


# Create application
app = Application()
app.use(config_extension)

# Configure with multiple sources
app.configure_config(
    schema=AppConfig,
    sources=[
        "config.json",  # Base configuration file
        "ENV",  # Override with environment variables
    ],
    env_prefix="MYAPP_",  # E.g., MYAPP_DEBUG=true
    watch=True,  # Enable hot reloading
)


# Register configuration sections
@app.config("database")
@dataclass
class DatabaseSettings:
    """Database-specific settings."""

    connection_pool_size: int = 10
    timeout: int = 30
    retry_count: int = 3


# Components can inject configuration
@app.component
class DatabaseService:
    """Service that uses database configuration."""

    @inject
    def __init__(self, config: DatabaseConfig, settings: DatabaseSettings):
        self.config = config
        self.settings = settings
        print(f"Connecting to database at {config.host}:{config.port}")
        print(f"Pool size: {settings.connection_pool_size}")


@app.component
class WebServer:
    """Web server that uses configuration."""

    @inject
    def __init__(
        self,
        server_config: ServerConfig,
        debug: bool = Setting("debug"),
        app_name: str = Setting("name"),
    ):
        self.config = server_config
        self.debug = debug
        self.app_name = app_name

    def start(self):
        """Start the server."""
        mode = "debug" if self.debug else "production"
        print(f"Starting {self.app_name} server in {mode} mode")
        print(f"Listening on {self.config.host}:{self.config.port}")
        print(f"Workers: {self.config.workers}")


# Feature flags
@app.feature("new_dashboard")
async def show_new_dashboard():
    """Show new dashboard if feature is enabled."""
    print("New dashboard is enabled!")
    return "New Dashboard"


@app.feature("experimental_api", default=False)
async def experimental_endpoint():
    """Experimental API endpoint."""
    print("Experimental API called")
    return {"status": "experimental"}


# Configuration change handlers
@app.on("config.loaded")
async def on_config_loaded(data):
    """Handle configuration loaded event."""
    manager = data["manager"]
    config = manager.get()
    print(f"Configuration loaded for {config.name} v{config.version}")


@app.on("config.changed")
async def on_config_changed(data):
    """Handle configuration changes."""
    print(f"Configuration changed at {data['path']}")
    print(f"Old value: {data['old_value']}")
    print(f"New value: {data['new_value']}")


# Main application
@app.main
@inject
async def main(config: AppConfig, db_service: DatabaseService, server: WebServer):
    """Main application entry point."""
    print(f"\n{config.name} v{config.version}")
    print("=" * 40)

    # Start server
    server.start()

    # Test feature flags
    if app.get_config("features.new_dashboard", False):
        await show_new_dashboard()

    # Demonstrate runtime config update
    print("\nUpdating configuration...")
    app.update_config({"debug": True, "server": {"workers": 8}})

    # Access raw configuration
    raw_config = app.config_manager.get_raw()
    print(f"\nRaw configuration keys: {list(raw_config.keys())}")


# Create example configuration file
def create_example_config():
    """Create an example config.json file."""
    import json

    config = {
        "name": "MyApplication",
        "version": "2.0.0",
        "debug": False,
        "database": {
            "host": "db.example.com",
            "port": 5432,
            "username": "appuser",
            "database": "production",
        },
        "server": {"host": "0.0.0.0", "port": 8080, "workers": 4},
        "features": {"new_dashboard": True, "experimental_api": False},
    }

    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    print("Created config.json")


if __name__ == "__main__":
    # Set some environment variables for demo
    os.environ["MYAPP_DEBUG"] = "true"
    os.environ["MYAPP_DATABASE_PASSWORD"] = "secret123"
    os.environ["MYAPP_SERVER_WORKERS"] = "6"

    # Create example config file
    create_example_config()

    # Run application
    app.run()
