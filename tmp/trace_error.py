#!/usr/bin/env python3
"""Trace where the error is coming from."""

import sys
import asyncio
import warnings
import traceback

# Capture warnings
def warning_handler(message, category, filename, lineno, file=None, line=None):
    print(f"\n=== WARNING CAPTURED ===")
    print(f"Message: {message}")
    print(f"Category: {category.__name__}")
    print(f"Location: {filename}:{lineno}")
    print(f"Line: {line}")
    traceback.print_stack()
    print("=== END WARNING ===\n")

warnings.showwarning = warning_handler

# Now run our test
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
    print(f"SUCCESS: {message}")
    return 0  # Explicit success

# Override sys.argv to simulate CLI call
sys.argv = ['trace_error.py', 'greet', 'TestUser']

print("=== Starting CLI execution ===")
try:
    app.run_cli()
    print("=== CLI execution completed ===")
except SystemExit as e:
    print(f"=== SystemExit with code: {e.code} ===")
except Exception as e:
    print(f"=== Exception: {type(e).__name__}: {e} ===")
    traceback.print_exc()