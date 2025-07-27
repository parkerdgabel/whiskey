<<<<<<< HEAD
"""Type definitions, protocols, and interfaces for lifecycle management.

This module defines the core protocols and type definitions used throughout
the Whiskey framework. It provides standard interfaces for service lifecycle
management, allowing services to hook into initialization and disposal phases.

Classes:
    Inject: DEPRECATED - Legacy marker for explicit injection
    Initializable: Protocol for services requiring async initialization
    Disposable: Protocol for services requiring cleanup

Protocols:
    The module uses Python's Protocol feature (PEP 544) to define structural
    interfaces that services can implement without explicit inheritance. This
    provides duck-typing with static type checking support.

Lifecycle Patterns:
    Services can implement these protocols to participate in lifecycle:
    
    1. Initialization (Initializable):
       - Called during app startup or first resolution
       - Used for async setup (connections, resource allocation)
       - Failures prevent service usage
    
    2. Disposal (Disposable):
       - Called during app shutdown or scope cleanup
       - Used for resource cleanup (closing connections, flushing)
       - Should be idempotent and handle multiple calls

Example:
    >>> from whiskey.core.types import Initializable, Disposable
    >>> 
    >>> @singleton
    ... class DatabasePool(Initializable, Disposable):
    ...     def __init__(self, config: Config):
    ...         self.config = config
    ...         self.pool = None
    ...     
    ...     async def initialize(self):
    ...         # Create connection pool on startup
    ...         self.pool = await create_pool(
    ...             dsn=self.config.database_url,
    ...             min_size=10,
    ...             max_size=20
    ...         )
    ...     
    ...     async def dispose(self):
    ...         # Clean up connections on shutdown
    ...         if self.pool:
    ...             await self.pool.close()

Note:
    The @runtime_checkable decorator allows isinstance() checks against
    protocols at runtime, enabling dynamic lifecycle management.
"""
=======
"""Minimal type definitions for Whiskey framework."""
>>>>>>> origin/main

from typing import Protocol, runtime_checkable


<<<<<<< HEAD
class Inject:
    """Legacy marker class for explicit dependency injection.

    DEPRECATED: Whiskey now uses automatic injection based on type hints.
    This class is kept for backward compatibility only.

    In modern Whiskey, you simply use type hints:

    Examples:
        Old way (deprecated):
        >>> from typing import Annotated
        >>> @inject
        >>> def process(db: Annotated[Database, Inject()]):
        ...     return db.query()

        New way (automatic):
        >>> @inject
        >>> def process(db: Database):  # Automatically injected!
        ...     return db.query()
        >>>
        >>> @inject
        >>> def handler(cache: Cache, user_id: int):
        ...     # cache is auto-injected, user_id must be passed
        ...     return cache.get(f"user:{user_id}")
    """

    def __init__(self, name: str = None, optional: bool = False):
        """Initialize injection marker.

        Args:
            name: Optional name for named dependencies (deprecated)
            optional: If True, None is returned if dependency not found (deprecated)
        """
        import warnings
        warnings.warn(
            "Inject() is deprecated. Whiskey now uses automatic injection based on type hints.",
            DeprecationWarning,
            stacklevel=2
        )
        self.name = name
        self.optional = optional


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
=======
@runtime_checkable
class Initializable(Protocol):
    """Protocol for services that need initialization."""
    
    async def initialize(self) -> None:
        """Initialize the service."""
>>>>>>> origin/main
        ...


@runtime_checkable
class Disposable(Protocol):
<<<<<<< HEAD
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
=======
    """Protocol for services that need cleanup."""
    
    async def dispose(self) -> None:
        """Clean up the service."""
        ...
>>>>>>> origin/main
