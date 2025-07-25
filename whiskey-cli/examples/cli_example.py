"""CLI application example using Whiskey."""

import click
from whiskey import inject, singleton
from whiskey_cli import cli


# Service definitions
@singleton
class ConfigService:
    """Configuration service."""
    
    def __init__(self):
        self.api_url = "https://api.example.com"
        self.timeout = 30


@singleton  
class DataService:
    """Service for data operations."""
    
    def __init__(self, config: ConfigService):
        self.config = config
        self._cache = {}
    
    async def fetch_data(self, key: str) -> str:
        """Fetch data by key."""
        if key in self._cache:
            return self._cache[key]
        
        # Simulate fetching data
        data = f"Data for {key} from {self.config.api_url}"
        self._cache[key] = data
        return data
    
    def list_cached(self) -> list[str]:
        """List cached keys."""
        return list(self._cache.keys())


# Build the CLI application
app = (
    cli()
    .configure(lambda c: setattr(c, "name", "WhiskeyCLI"))
    .service(ConfigService, implementation=ConfigService)
    .service(DataService, implementation=DataService)
)


# Define commands
@app.command()
@click.argument("key")
@inject
async def fetch(key: str, data_service: DataService):
    """Fetch data by key."""
    result = await data_service.fetch_data(key)
    click.echo(f"Fetched: {result}")


@app.command()
@inject
def list_cache(data_service: DataService):
    """List cached data keys."""
    keys = data_service.list_cached()
    if keys:
        click.echo("Cached keys:")
        for key in keys:
            click.echo(f"  - {key}")
    else:
        click.echo("No cached data")


@app.command()
@inject
def config(config_service: ConfigService):
    """Show configuration."""
    click.echo(f"API URL: {config_service.api_url}")
    click.echo(f"Timeout: {config_service.timeout}s")


# Command that doesn't need the app
@app.command(needs_app=False)
def version():
    """Show version information."""
    click.echo("WhiskeyCLI v0.1.0")


# Run the CLI
if __name__ == "__main__":
    app.run()