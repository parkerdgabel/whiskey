"""Minimal type definitions for Whiskey framework."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Initializable(Protocol):
    """Protocol for services that need initialization."""
    
    async def initialize(self) -> None:
        """Initialize the service."""
        ...


@runtime_checkable
class Disposable(Protocol):
    """Protocol for services that need cleanup."""
    
    async def dispose(self) -> None:
        """Clean up the service."""
        ...