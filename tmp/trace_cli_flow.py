#!/usr/bin/env python3
"""Trace actual CLI execution flow."""

import sys
import os

# Add debug prints to the CLI extension
cli_ext_path = os.path.join(os.path.dirname(__file__), '..', 'whiskey_cli', 'src', 'whiskey_cli', 'extension.py')

print(f"CLI extension path: {cli_ext_path}")

# Let's check what's actually happening by looking at the error traceback more carefully
# The error says it's coming from line 409, which is in the run_cli function

# Create a test to run through the actual CLI
from whiskey import Whiskey, inject, singleton
from whiskey_cli import cli_extension

@singleton  
class TestService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

app = Whiskey()
app.use(cli_extension)

@app.command()
@inject
def greet(name: str, service: TestService):
    message = service.greet(name)
    print(message)

# The error stack trace shows:
# 1. /whiskey_cli/src/whiskey_cli/extension.py:409 - in run_cli's exception handler
# 2. RuntimeWarning: coroutine 'Container.call' was never awaited
# 3. Error: asyncio.run() cannot be called from a running event loop

# This suggests the error is NOT in wrapped_callback, but somewhere else!
# Let's examine where line 409 is...

import inspect
import whiskey_cli.extension

# Get the source of run_cli
for name, obj in inspect.getmembers(whiskey_cli.extension):
    if name == 'cli_extension':
        print(f"\nFound cli_extension function")
        # The run_cli is defined inside cli_extension
        break

# Actually, let's just run with more detailed error handling
if __name__ == "__main__":
    import traceback
    try:
        app.run_cli()
    except Exception as e:
        print(f"\nDetailed error trace:")
        traceback.print_exc()
        print(f"\nError type: {type(e)}")
        print(f"Error message: {e}")