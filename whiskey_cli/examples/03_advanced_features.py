#!/usr/bin/env python
"""Advanced CLI features demonstration.

This example demonstrates:
- Mixed CLI and programmatic usage with app.run()
- Lifecycle hooks (on_startup, on_shutdown)
- Event emission and handling
- Conditional command registration
- Integration with async services
- Custom main function alongside CLI

Usage:
    # Run as CLI
    python 03_advanced_features.py status
    python 03_advanced_features.py process data.txt --format json
    python 03_advanced_features.py admin:reset --force
    
    # Run with --main flag to use custom main function
    python 03_advanced_features.py --main
"""

import sys
import asyncio
from typing import Optional
from whiskey import Whiskey, inject, singleton, component
from whiskey_cli import cli_extension


# Services
@singleton
class ConfigService:
    """Application configuration."""
    
    def __init__(self):
        self.debug = "--debug" in sys.argv
        self.environment = "development"
        self.api_url = "https://api.example.com"


@component
class DataProcessor:
    """Process data in various formats."""
    
    async def process(self, filename: str, format: str) -> dict:
        """Simulate async data processing."""
        print(f"🔄 Processing {filename} as {format}...")
        await asyncio.sleep(1)  # Simulate work
        return {
            "file": filename,
            "format": format,
            "records": 42,
            "status": "success"
        }


@singleton
class EventLogger:
    """Log application events."""
    
    def __init__(self):
        self.events = []
    
    def log(self, event: str, data: dict = None):
        """Log an event."""
        self.events.append({"event": event, "data": data})
        if len(self.events) % 5 == 0:
            print(f"📊 Logged {len(self.events)} events")


# Create application
app = Whiskey()
app.use(cli_extension)


# Lifecycle hooks
@app.on_startup
async def startup(config: ConfigService):
    """Run when application starts."""
    print(f"🚀 Starting in {config.environment} mode")
    if config.debug:
        print("🐛 Debug mode enabled")


@app.on_shutdown
async def shutdown(logger: EventLogger):
    """Run when application stops."""
    print(f"\n👋 Shutting down (logged {len(logger.events)} events)")


# Event handlers
@app.on("command.executed")
def log_command(command: str, logger: EventLogger):
    """Log every command execution."""
    logger.log("command", {"name": command})


# Regular commands
@app.command()
@inject
def status(config: ConfigService, logger: EventLogger):
    """Show application status."""
    print(f"✅ Application Status")
    print(f"   Environment: {config.environment}")
    print(f"   Debug: {config.debug}")
    print(f"   API URL: {config.api_url}")
    print(f"   Events logged: {len(logger.events)}")
    
    # Emit event
    app.emit("command.executed", "status")


@app.command()
@app.argument("filename", help="File to process")
@app.option("--format", "-f", default="json", help="Output format (json, xml, csv)")
@app.option("--output", "-o", help="Output file (optional)")
@inject
async def process(
    filename: str,
    format: str,
    output: Optional[str],
    processor: DataProcessor,
    logger: EventLogger
):
    """Process a data file asynchronously."""
    # Process the file
    result = await processor.process(filename, format)
    
    # Show results
    print(f"✅ Processing complete!")
    print(f"   Records: {result['records']}")
    print(f"   Status: {result['status']}")
    
    if output:
        print(f"   Output saved to: {output}")
    
    # Log event
    logger.log("file.processed", result)
    app.emit("command.executed", "process")


# Conditional commands (only in debug mode)
@app.when_debug().command(name="admin:reset", group="admin")
@inject
def admin_reset(config: ConfigService):
    """Reset application (debug only)."""
    print("⚠️  Admin command - only available in debug mode")
    print(f"Resetting {config.environment} environment...")
    print("✅ Reset complete")


# Command available only with --admin flag
if "--admin" in sys.argv:
    @app.command(name="admin:users", group="admin")
    @inject
    def list_users(logger: EventLogger):
        """List all users (admin only)."""
        print("👥 Admin Users:")
        print("   - admin@example.com")
        print("   - developer@example.com")
        logger.log("admin.users.listed")


# Custom main function (alternative to CLI)
@inject
async def custom_main(
    config: ConfigService,
    processor: DataProcessor,
    logger: EventLogger
):
    """Run custom logic instead of CLI."""
    print("🎯 Running custom main function\n")
    
    # Show config
    print(f"Configuration:")
    print(f"  Environment: {config.environment}")
    print(f"  Debug: {config.debug}")
    
    # Process some data
    result = await processor.process("example.json", "json")
    print(f"\nProcessed {result['records']} records")
    
    # Show event log
    print(f"\nLogged {len(logger.events)} events during this session")
    
    return "Custom main completed successfully"


# Main entry point with mode selection
if __name__ == "__main__":
    if "--main" in sys.argv:
        # Run custom main function
        print("=" * 50)
        result = app.run(custom_main)
        print(f"\nResult: {result}")
        print("=" * 50)
    else:
        # Run as CLI (default)
        app.run()
        
    # Note: You can also mix both modes in your application:
    # - Use CLI for administration tasks
    # - Use custom main for batch processing
    # - Use the same services and DI container for both!