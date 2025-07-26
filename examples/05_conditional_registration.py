"""
Conditional Registration Example

This example demonstrates how to use conditional registration in Whiskey
to register services based on runtime conditions like environment variables,
feature flags, and custom logic.
"""

import asyncio
import os
from datetime import datetime
from typing import Annotated, Protocol

from whiskey import Container, provide, singleton
from whiskey.core.conditions import (
    all_conditions,
    any_conditions,
    env_equals,
    env_exists,
    env_truthy,
    not_condition,
)
from whiskey.core.decorators import Inject, set_default_container


# Logging interface
class Logger(Protocol):
    def log(self, message: str) -> None: ...


# Environment-specific loggers
@provide(condition=env_equals("ENV", "development"))
class DevLogger:
    def __init__(self):
        print("DevLogger initialized - development mode")

    def log(self, message: str) -> None:
        print(f"🔧 DEV: {message}")


@provide(condition=env_equals("ENV", "production"))
class ProdLogger:
    def __init__(self):
        print("ProdLogger initialized - production mode")

    def log(self, message: str) -> None:
        # In real app, this would log to syslog/external service
        print(f"📊 PROD: {message}")


@provide(condition=env_equals("ENV", "test"))
class TestLogger:
    def __init__(self):
        print("TestLogger initialized - test mode")
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)
        print(f"🧪 TEST: {message}")


# Feature flag based services
@singleton(condition=env_truthy("ENABLE_CACHING"))
class CacheService:
    def __init__(self):
        print("CacheService initialized - caching enabled")
        self.data = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


@provide(condition=not_condition(env_truthy("ENABLE_CACHING")))
class NoCacheService:
    def __init__(self):
        print("NoCacheService initialized - caching disabled")

    def get(self, key: str) -> str | None:
        return None  # Always cache miss

    def set(self, key: str, value: str) -> None:
        pass  # No-op


# Database selection based on multiple conditions
@singleton(
    name="primary",
    condition=all_conditions(env_exists("DATABASE_URL"), env_equals("DB_TYPE", "postgres")),
)
class PostgresDatabase:
    def __init__(self):
        url = os.getenv("DATABASE_URL", "postgres://localhost")
        print(f"PostgresDatabase initialized with: {url}")
        self.url = url

    def query(self, sql: str) -> list:
        return [{"db": "postgres", "sql": sql}]


@singleton(
    name="primary",
    condition=all_conditions(env_exists("DATABASE_URL"), env_equals("DB_TYPE", "mysql")),
)
class MySQLDatabase:
    def __init__(self):
        url = os.getenv("DATABASE_URL", "mysql://localhost")
        print(f"MySQLDatabase initialized with: {url}")
        self.url = url

    def query(self, sql: str) -> list:
        return [{"db": "mysql", "sql": sql}]


@singleton(name="primary", condition=not_condition(env_exists("DATABASE_URL")))
class SQLiteDatabase:
    def __init__(self):
        print("SQLiteDatabase initialized - fallback database")
        self.url = "sqlite:///app.db"

    def query(self, sql: str) -> list:
        return [{"db": "sqlite", "sql": sql}]


# External API client with complex conditions
@provide(
    condition=all_conditions(
        env_exists("API_KEY"), env_exists("API_URL"), not_condition(env_equals("ENV", "test"))
    )
)
class ExternalAPIClient:
    def __init__(self):
        api_key = os.getenv("API_KEY")
        api_url = os.getenv("API_URL")
        print(f"ExternalAPIClient initialized - API: {api_url}")
        self.api_key = api_key
        self.api_url = api_url

    def call_api(self, endpoint: str) -> dict:
        return {"status": "success", "endpoint": endpoint, "api": "real"}


@provide(
    condition=any_conditions(
        not_condition(env_exists("API_KEY")),
        not_condition(env_exists("API_URL")),
        env_equals("ENV", "test"),
    )
)
class MockAPIClient:
    def __init__(self):
        print("MockAPIClient initialized - using mock API")

    def call_api(self, endpoint: str) -> dict:
        return {"status": "success", "endpoint": endpoint, "api": "mock"}


# Time-based conditional service
def is_business_hours() -> bool:
    """Check if current time is during business hours (9 AM - 5 PM)."""
    current_hour = datetime.now().hour
    return 9 <= current_hour < 17


@provide(condition=is_business_hours)
class BusinessHoursService:
    def __init__(self):
        print("BusinessHoursService initialized - business hours active")

    def process_request(self, request: str) -> str:
        return f"Processing during business hours: {request}"


@provide(condition=lambda: not is_business_hours())
class AfterHoursService:
    def __init__(self):
        print("AfterHoursService initialized - after hours mode")

    def process_request(self, request: str) -> str:
        return f"Queued for next business day: {request}"


# Service that uses conditionally registered dependencies
class ApplicationService:
    def __init__(
        self,
        logger: Annotated[Logger, Inject()],
        cache: Annotated[CacheService | NoCacheService, Inject()],
        api_client: Annotated[ExternalAPIClient | MockAPIClient, Inject()],
    ):
        self.logger = logger
        self.cache = cache
        self.api_client = api_client
        print("ApplicationService initialized")

    def do_work(self) -> dict:
        self.logger.log("Starting work...")

        # Try to get from cache
        cached_result = self.cache.get("work_result")
        if cached_result:
            self.logger.log("Found cached result")
            return {"result": cached_result, "source": "cache"}

        # Call external API
        api_result = self.api_client.call_api("/data")
        self.logger.log(f"API call result: {api_result}")

        # Cache the result
        result_str = str(api_result)
        self.cache.set("work_result", result_str)

        return {"result": api_result, "source": "api"}


def setup_environment(scenario: str):
    """Set up environment variables for different scenarios."""
    # Clear existing environment
    env_vars = ["ENV", "ENABLE_CACHING", "DATABASE_URL", "DB_TYPE", "API_KEY", "API_URL"]
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

    if scenario == "development":
        os.environ["ENV"] = "development"
        os.environ["ENABLE_CACHING"] = "true"
        os.environ["DATABASE_URL"] = "postgres://dev-db"
        os.environ["DB_TYPE"] = "postgres"
        os.environ["API_KEY"] = "dev-key"
        os.environ["API_URL"] = "https://dev-api.example.com"

    elif scenario == "production":
        os.environ["ENV"] = "production"
        os.environ["ENABLE_CACHING"] = "true"
        os.environ["DATABASE_URL"] = "mysql://prod-db"
        os.environ["DB_TYPE"] = "mysql"
        # No API credentials in prod (uses mock)

    elif scenario == "test":
        os.environ["ENV"] = "test"
        os.environ["ENABLE_CACHING"] = "false"
        # No database URL (uses SQLite)
        # API client will be mocked

    elif scenario == "minimal":
        # Minimal setup - most services will use fallbacks
        pass


async def run_scenario(scenario: str):
    """Run a specific scenario and show which services are registered."""
    print(f"\n{'=' * 50}")
    print(f"SCENARIO: {scenario.upper()}")
    print("=" * 50)

    setup_environment(scenario)

    # Create new container for each scenario
    container = Container()
    set_default_container(container)

    # Import after setting up environment so decorators evaluate conditions
    # (In a real app, you'd structure this differently)

    print("\nEnvironment variables:")
    relevant_vars = ["ENV", "ENABLE_CACHING", "DATABASE_URL", "DB_TYPE", "API_KEY", "API_URL"]
    for var in relevant_vars:
        value = os.getenv(var, "NOT SET")
        print(f"  {var}: {value}")

    print("\nRegistered services:")
    for key in container.keys_full():
        service_type, name = key
        name_str = f"[{name}]" if name else ""
        print(f"  - {service_type.__name__}{name_str}")

    # Try to resolve and use the application
    try:
        print("\nResolving ApplicationService...")
        app_service = await container.resolve(ApplicationService)

        print("\nExecuting work...")
        result = app_service.do_work()
        print(f"Work result: {result}")

        # Try to resolve database if available
        try:
            db = await container.resolve(
                PostgresDatabase | MySQLDatabase | SQLiteDatabase, name="primary"
            )
            query_result = db.query("SELECT * FROM users")
            print(f"Database query result: {query_result}")
        except KeyError:
            print("No database service registered")

        # Try time-based services
        try:
            business_service = await container.resolve(BusinessHoursService)
            request_result = business_service.process_request("test request")
            print(f"Business hours result: {request_result}")
        except KeyError:
            try:
                after_hours_service = await container.resolve(AfterHoursService)
                request_result = after_hours_service.process_request("test request")
                print(f"After hours result: {request_result}")
            except KeyError:
                print("No time-based service available")

    except KeyError as e:
        print(f"Failed to resolve ApplicationService: {e}")
        print("This scenario doesn't have all required services registered")


async def main():
    """Demonstrate conditional registration with different scenarios."""
    print("=== Conditional Registration Example ===")

    scenarios = ["development", "production", "test", "minimal"]

    for scenario in scenarios:
        await run_scenario(scenario)
        await asyncio.sleep(0.1)  # Small delay for readability

    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print("=" * 50)
    print("Conditional registration allows you to:")
    print("- Register different services based on environment")
    print("- Use feature flags to enable/disable functionality")
    print("- Combine multiple conditions with AND/OR/NOT logic")
    print("- Create fallback services when conditions aren't met")
    print("- Support different deployment environments seamlessly")


if __name__ == "__main__":
    asyncio.run(main())
