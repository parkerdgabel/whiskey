"""Type definitions and protocols for the Whiskey framework.

This module defines the core protocols (interfaces) used throughout
Whiskey for lifecycle management and other cross-cutting concerns.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Initializable(Protocol):
    """Protocol for services that need asynchronous initialization.
    
    Services implementing this protocol will have their initialize()
    method called during application startup or when first resolved,
    depending on the configuration.
    
    Examples:
        >>> class Database(Initializable):
        ...     async def initialize(self):
        ...         self.connection = await connect_to_db()
        ...         await self.connection.execute("SELECT 1")  # Test connection
        
        >>> @app.component
        ... class CacheService(Initializable):
        ...     async def initialize(self):
        ...         self.client = await create_redis_client()
        ...         await self.client.ping()
    """
    
    async def initialize(self) -> None:
        """Initialize the service.
        
        This method should perform any asynchronous setup required
        before the service can be used, such as:
        - Establishing network connections
        - Loading configuration
        - Warming up caches
        - Validating external dependencies
        
        Raises:
            Any exception during initialization will prevent the
            service from being used and may stop application startup
            if the component is marked as critical.
        """
        ...


@runtime_checkable
class Disposable(Protocol):
    """Protocol for services that need cleanup on shutdown.
    
    Services implementing this protocol will have their dispose()
    method called during application shutdown or when their scope ends.
    
    Examples:
        >>> class Database(Disposable):
        ...     async def dispose(self):
        ...         if self.connection:
        ...             await self.connection.close()
        
        >>> @scoped("request")
        ... class RequestLogger(Disposable):
        ...     async def dispose(self):
        ...         # Flush any buffered logs
        ...         await self.flush_logs()
    """
    
    async def dispose(self) -> None:
        """Clean up the service resources.
        
        This method should release any resources held by the service:
        - Close network connections
        - Flush buffers
        - Release file handles
        - Cancel background tasks
        
        Note:
            Dispose methods should be idempotent and handle being
            called multiple times gracefully.
        """
        ...