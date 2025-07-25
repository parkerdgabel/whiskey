"""Example demonstrating Pythonic autodiscovery in Whiskey.

This example shows how Whiskey automatically discovers and wires components
based on Python conventions:
- Type hints for dependency injection
- Naming conventions for scoping (_service, _repository, etc.)
- Module-level exports with __all__
- Factory functions (create_*, make_*, build_*)
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from whiskey import Application, ApplicationConfig, autodiscover


# Example 1: Convention-based discovery
# Files ending with _service are singleton by default

class UserRepository:
    """This will be auto-discovered because it has typed dependencies."""
    
    def __init__(self):
        self.users = {}
    
    async def save(self, user_id: str, name: str) -> None:
        self.users[user_id] = name
    
    async def get(self, user_id: str) -> str | None:
        return self.users.get(user_id)


class UserService:
    """Automatically singleton because class name ends with 'Service'."""
    
    def __init__(self, repository: UserRepository):
        # Type hint enables automatic injection
        self.repository = repository
    
    async def create_user(self, user_id: str, name: str) -> None:
        await self.repository.save(user_id, name)
        print(f"Created user: {name} ({user_id})")


# Example 2: Factory functions are discovered

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432


def create_database_config() -> DatabaseConfig:
    """Factory functions starting with create_/make_/build_ are auto-discovered."""
    return DatabaseConfig(host="db.example.com", port=5432)


# Example 3: Protocol-based discovery

class Logger(Protocol):
    """Protocols can be used for loose coupling."""
    def log(self, message: str) -> None: ...


class ConsoleLogger:
    """Implements Logger protocol - will be discovered."""
    
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")


# Example 4: Explicit exports with __all__

class _InternalHelper:
    """This won't be discovered (starts with _)."""
    pass


class PublicAPI:
    """This will be discovered because it's in __all__."""
    
    def __init__(self, logger: ConsoleLogger):
        self.logger = logger
    
    def process(self) -> None:
        self.logger.log("Processing...")


# Export specific classes
__all__ = ["PublicAPI", "UserService", "UserRepository"]


# Example 5: Using the discovered components

async def main():
    # Create application with autodiscovery
    app = Application(ApplicationConfig(
        name="AutoDiscoveryExample",
        # Could specify packages to scan
        # component_scan_packages=["myapp.services", "myapp.repositories"],
        # Or paths
        # component_scan_paths=["./src/services", "./src/repositories"],
    ))
    
    # Manually trigger discovery for this example
    # (normally done automatically during app.startup())
    autodiscover(__name__)
    
    async with app.lifespan():
        # All components are automatically wired
        user_service = await app.container.resolve(UserService)
        await user_service.create_user("123", "Alice")
        
        # Repository is also available
        repository = await app.container.resolve(UserRepository)
        user = await repository.get("123")
        print(f"Retrieved user: {user}")
        
        # Factory-created config is available
        config = await app.container.resolve(DatabaseConfig)
        print(f"Database config: {config.host}:{config.port}")
        
        # Protocol implementations work
        logger = await app.container.resolve(ConsoleLogger)
        logger.log("Autodiscovery complete!")


if __name__ == "__main__":
    asyncio.run(main())