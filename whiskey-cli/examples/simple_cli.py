"""Simple CLI example showing the basics."""

import click
from whiskey import Application, inject
from whiskey_cli import cli_extension


# Service
class GreetingService:
    """Service that creates greetings."""
    
    def greet(self, name: str) -> str:
        return f"Hello, {name}! Welcome to Whiskey CLI."
    
    def farewell(self, name: str) -> str:
        return f"Goodbye, {name}! Thanks for using Whiskey."


# Create app with CLI extension
app = Application()
app.use(cli_extension)

# Register service
app.container[GreetingService] = GreetingService()


# Commands
@app.command()
@click.argument("name")
@inject
def hello(name: str, greeting: GreetingService):
    """Say hello to someone."""
    message = greeting.greet(name)
    click.echo(message)


@app.command()
@click.argument("name")
@click.option("--shout", is_flag=True, help="Shout the goodbye")
@inject
def goodbye(name: str, shout: bool, greeting: GreetingService):
    """Say goodbye to someone."""
    message = greeting.farewell(name)
    if shout:
        message = message.upper()
    click.echo(message)


@app.command()
def version():
    """Show version information."""
    click.echo("Simple CLI v1.0.0")


# Run the CLI
if __name__ == "__main__":
    app.run_cli()