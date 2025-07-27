#!/usr/bin/env python3
"""Demo app showcasing Whiskey CLI extension capabilities."""

from whiskey import Whiskey, inject, singleton, component
from whiskey_cli import cli_extension
from datetime import datetime
import json


# Services
@singleton
class ConfigService:
    """Manages application configuration."""
    
    def __init__(self):
        self.config = {
            "app_name": "Whiskey CLI Demo",
            "version": "1.0.0",
            "debug": False
        }
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        self.config[key] = value


@component
class MessageService:
    """Formats messages."""
    
    def __init__(self, config: ConfigService):
        self.config = config
    
    def format_greeting(self, name: str) -> str:
        app_name = self.config.get("app_name")
        return f"Welcome to {app_name}, {name}!"
    
    def format_info(self, data: dict) -> str:
        return json.dumps(data, indent=2)


# Create app
app = Whiskey()
app.use(cli_extension)


# Basic commands
@app.command()
def version():
    """Show version information."""
    print("Whiskey CLI Demo v1.0.0")


@app.command()
def echo(text: str):
    """Echo the input text."""
    print(text)


# Command with dependency injection
@app.command()
@inject
def welcome(name: str, service: MessageService):
    """Welcome a user with a formatted message."""
    message = service.format_greeting(name)
    print(message)


# Command with manual options (work around the option decorator issue)
@app.command()
def repeat(text: str, times: int = 3):
    """Repeat text multiple times."""
    for i in range(times):
        print(f"{i+1}: {text}")


# Groups
config_group = app.group("config", description="Configuration commands")


@config_group.command("show")
@inject
def show_config(config: ConfigService):
    """Show current configuration."""
    print("Current Configuration:")
    for key, value in config.config.items():
        print(f"  {key}: {value}")


@config_group.command("set")
@inject  
def set_config(key: str, value: str, config: ConfigService):
    """Set a configuration value."""
    # Try to parse value as JSON for proper types
    try:
        parsed_value = json.loads(value)
    except:
        parsed_value = value
    
    config.set(key, parsed_value)
    print(f"Set {key} = {parsed_value}")


# Utility commands
@app.command()
def now():
    """Show current date and time."""
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@app.command()
@inject
def info(config: ConfigService, service: MessageService):
    """Show application information."""
    data = {
        "name": config.get("app_name"),
        "version": config.get("version"),
        "timestamp": datetime.now().isoformat(),
        "debug": config.get("debug")
    }
    print(service.format_info(data))


# Demonstrating different parameter types
@app.command()
def calc(operation: str, a: str, b: str):
    """Perform a calculation."""
    try:
        a_float = float(a)
        b_float = float(b)
    except ValueError:
        print("Error: Invalid numbers")
        return
    
    operations = {
        "add": lambda x, y: x + y,
        "sub": lambda x, y: x - y,
        "mul": lambda x, y: x * y,
        "div": lambda x, y: x / y if y != 0 else "Error: Division by zero"
    }
    
    if operation in operations:
        result = operations[operation](a_float, b_float)
        print(f"{a} {operation} {b} = {result}")
    else:
        print(f"Unknown operation: {operation}")
        print("Available: add, sub, mul, div")


if __name__ == "__main__":
    app.run_cli()