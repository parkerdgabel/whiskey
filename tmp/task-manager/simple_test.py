#!/usr/bin/env python3
"""Simple test of the CLI extension."""

from whiskey import Whiskey, inject, singleton
from whiskey_cli import cli_extension


# Services
@singleton
class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


# Create app
app = Whiskey()
app.use(cli_extension)


# Commands
@app.command()
def hello():
    """Say hello."""
    print("Hello, World!")


@app.command()
def greet(name: str):
    """Greet someone by name."""
    print(f"Hello, {name}!")


@app.command()
@inject
def greet_service(name: str, service: GreetingService):
    """Greet using the greeting service."""
    message = service.greet(name)
    print(message)


@app.command()
@app.option("--count", default="1", help="Number of times to greet")
@app.option("--excited", is_flag=True, help="Add excitement")
def multi_greet(name: str, count: str, excited: bool):
    """Greet someone multiple times."""
    suffix = "!" if excited else "."
    for i in range(int(count)):
        print(f"Hello, {name}{suffix}")


if __name__ == "__main__":
    app.run_cli()