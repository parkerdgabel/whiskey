#!/usr/bin/env python3
"""Test how to handle nested async calls."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

async def async_function():
    """An async function we want to call from sync context."""
    await asyncio.sleep(0.1)  # Simulate async work
    return "async result"

def sync_function_that_needs_async():
    """A sync function that needs to call async code."""
    # This is the problem we face in container.call_sync
    # We're in an event loop but need to await something
    
    # Option 1: Use asyncio.create_task (but still need to await)
    # task = asyncio.create_task(async_function())
    # return await task  # Can't await in sync function!
    
    # Option 2: Use a thread pool to run async code
    # This doesn't work well because we lose the asyncio context
    
    # Option 3: Don't call sync methods from async context!
    # This is the real solution
    
    print("sync_function_that_needs_async called")
    return "sync result"

async def main():
    """Main async function."""
    print("In main async function")
    
    # This is what happens in CLI:
    # We're in async context (cli_main)
    # But Click calls sync functions
    # Which try to use call_sync
    
    # If we're already in async context, we should use async methods
    try:
        # This simulates what happens in our CLI wrapper
        result = sync_function_that_needs_async()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

# Test the scenario
asyncio.run(main())