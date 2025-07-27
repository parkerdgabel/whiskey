#!/usr/bin/env python
"""Basic CLI example - Getting started with Whiskey CLI.

This example demonstrates:
- Creating a CLI app with Whiskey
- Defining simple commands with arguments and options
- Using dependency injection in commands
- Running the CLI with the new standardized run API

Usage:
    python 01_basic_cli.py hello World
    python 01_basic_cli.py hello World --shout
    python 01_basic_cli.py goodbye Alice
    python 01_basic_cli.py version
"""

from whiskey import Whiskey, component, inject
from whiskey_cli import cli_extension


# Define a service that will be injected into commands
@component
class GreetingService:
    """Service that creates greetings."""

    def greet(self, name: str) -> str:
        return f"Hello, {name}! Welcome to Whiskey CLI."

    def farewell(self, name: str) -> str:
        return f"Goodbye, {name}! Thanks for using Whiskey."


# Create the application
app = Whiskey()
app.use(cli_extension)


# Define CLI commands
@app.command()
@app.argument("name", help="Name of the person to greet")
@app.option("--shout", is_flag=True, help="Shout the greeting")
@inject
def hello(name: str, shout: bool, service: GreetingService):
    """Say hello to someone."""
    message = service.greet(name)
    if shout:
        message = message.upper()
    print(message)


@app.command()
@app.argument("name")
@inject
def goodbye(name: str, service: GreetingService):
    """Say goodbye to someone."""
    message = service.farewell(name)
    print(message)


@app.command()
def version():
    """Show version information."""
    print("Whiskey CLI Example v1.0.0")
    print("Using the new standardized run API")


# Main entry point
if __name__ == "__main__":
    # The new way: app.run() automatically uses the CLI runner
    app.run()

    # You can also use app.run_cli() for direct CLI execution
    # app.run_cli()

    # Or run with a custom main function instead of CLI
    # @inject
    # async def main(service: GreetingService):
    #     print(service.greet("Developer"))
    # app.run(main)
