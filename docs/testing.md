# Testing with Whiskey

Dependency injection makes testing easier by allowing you to swap real implementations with test doubles. This guide covers testing strategies and utilities for Whiskey applications.

## Testing Benefits

With dependency injection, you can:
- **Isolate components** - Test units in isolation
- **Mock dependencies** - Replace real services with mocks
- **Control state** - Provide specific test data
- **Test edge cases** - Simulate errors and edge conditions
- **Speed up tests** - Avoid slow external dependencies

## Basic Testing

### Unit Testing Components

```python
import pytest
from unittest.mock import Mock, AsyncMock
from whiskey import Container

# Component to test
class UserService:
    def __init__(self, db: Database, cache: Cache):
        self.db = db
        self.cache = cache
    
    async def get_user(self, user_id: int):
        # Check cache first
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        
        # Fetch from database
        user = await self.db.find_user(user_id)
        if user:
            await self.cache.set(f"user:{user_id}", user)
        return user

# Test
@pytest.mark.asyncio
async def test_get_user_from_cache():
    # Create mocks
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    
    # Setup cache to return user
    mock_cache.get.return_value = {"id": 1, "name": "Alice"}
    
    # Create service with mocks
    service = UserService(mock_db, mock_cache)
    
    # Test
    user = await service.get_user(1)
    
    # Assertions
    assert user["name"] == "Alice"
    mock_cache.get.assert_called_once_with("user:1")
    mock_db.find_user.assert_not_called()  # Should not hit DB

@pytest.mark.asyncio
async def test_get_user_from_database():
    # Create mocks
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    
    # Setup cache miss and DB hit
    mock_cache.get.return_value = None
    mock_db.find_user.return_value = {"id": 1, "name": "Bob"}
    
    # Create service
    service = UserService(mock_db, mock_cache)
    
    # Test
    user = await service.get_user(1)
    
    # Assertions
    assert user["name"] == "Bob"
    mock_cache.get.assert_called_once_with("user:1")
    mock_db.find_user.assert_called_once_with(1)
    mock_cache.set.assert_called_once_with("user:1", {"id": 1, "name": "Bob"})
```

### Testing with Container

```python
from whiskey.testing import create_test_container

@pytest.fixture
def test_container():
    """Create a test container with mocks"""
    container = create_test_container()
    
    # Register mocks
    container.add_singleton(Database, instance=AsyncMock())
    container.add_singleton(Cache, instance=AsyncMock())
    
    return container

@pytest.mark.asyncio
async def test_user_service_with_container(test_container):
    # Register the service
    test_container.add_transient(UserService)
    
    # Resolve with mocked dependencies
    service = await test_container.resolve(UserService)
    
    # Configure mocks
    db = await test_container.resolve(Database)
    db.find_user.return_value = {"id": 1, "name": "Charlie"}
    
    # Test
    user = await service.get_user(1)
    assert user["name"] == "Charlie"
```

## Testing Patterns

### 1. Test Doubles Pattern

Create test doubles for external dependencies:

```python
class FakeDatabase:
    """Fake database for testing"""
    def __init__(self):
        self.users = {
            1: {"id": 1, "name": "Test User"},
            2: {"id": 2, "name": "Another User"}
        }
    
    async def find_user(self, user_id: int):
        return self.users.get(user_id)
    
    async def create_user(self, name: str):
        user_id = len(self.users) + 1
        user = {"id": user_id, "name": name}
        self.users[user_id] = user
        return user

# Use in tests
@pytest.fixture
def fake_db():
    return FakeDatabase()

async def test_with_fake_db(fake_db):
    service = UserService(fake_db, Mock())
    user = await service.get_user(1)
    assert user["name"] == "Test User"
```

### 2. Builder Pattern for Test Data

```python
class UserBuilder:
    """Builder for test users"""
    def __init__(self):
        self.user = {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "active": True
        }
    
    def with_id(self, user_id: int):
        self.user["id"] = user_id
        return self
    
    def with_name(self, name: str):
        self.user["name"] = name
        return self
    
    def inactive(self):
        self.user["active"] = False
        return self
    
    def build(self):
        return self.user.copy()

# Usage
def test_inactive_user():
    user = UserBuilder().inactive().build()
    assert not user["active"]
```

### 3. Fixture Composition

```python
@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.find_user.return_value = {"id": 1, "name": "Test"}
    return db

@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get.return_value = None
    return cache

@pytest.fixture
def user_service(mock_db, mock_cache):
    return UserService(mock_db, mock_cache)

@pytest.mark.asyncio
async def test_composed_fixtures(user_service, mock_db):
    # Fixtures are composed automatically
    user = await user_service.get_user(1)
    assert user["name"] == "Test"
    mock_db.find_user.assert_called_once()
```

## Testing Whiskey Applications

### Application Testing

```python
from whiskey import Whiskey
import pytest

@pytest.fixture
async def app():
    """Create test application"""
    app = Whiskey(name="test_app", debug=True)
    
    # Register test components
    @app.singleton
    class TestConfig:
        def __init__(self):
            self.test_mode = True
    
    @app.component
    class TestService:
        def __init__(self, config: TestConfig):
            self.config = config
    
    # Initialize app
    async with app:
        yield app

@pytest.mark.asyncio
async def test_application(app):
    # Resolve and test components
    service = await app.resolve(TestService)
    assert service.config.test_mode is True
```

### Testing Lifecycle Events

```python
@pytest.mark.asyncio
async def test_startup_shutdown():
    app = Whiskey()
    startup_called = False
    shutdown_called = False
    
    @app.on_startup
    async def startup():
        nonlocal startup_called
        startup_called = True
    
    @app.on_shutdown
    async def shutdown():
        nonlocal shutdown_called
        shutdown_called = True
    
    # Run lifecycle
    async with app:
        assert startup_called
    
    assert shutdown_called
```

## Integration Testing

### Database Integration Tests

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    """Spin up test PostgreSQL container"""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture
async def db_connection(postgres):
    """Create test database connection"""
    import asyncpg
    
    conn = await asyncpg.connect(
        host=postgres.get_container_host_ip(),
        port=postgres.get_exposed_port(5432),
        user=postgres.username,
        password=postgres.password,
        database=postgres.database
    )
    
    # Setup schema
    await conn.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100)
        )
    """)
    
    yield conn
    await conn.close()

@pytest.mark.asyncio
async def test_real_database(db_connection):
    # Test with real database
    await db_connection.execute(
        "INSERT INTO users (name) VALUES ($1)",
        "Test User"
    )
    
    row = await db_connection.fetchrow(
        "SELECT * FROM users WHERE name = $1",
        "Test User"
    )
    
    assert row["name"] == "Test User"
```

### API Integration Tests

```python
from httpx import AsyncClient
from whiskey_web import create_asgi_app

@pytest.fixture
async def client(app):
    """Create test HTTP client"""
    asgi_app = create_asgi_app(app)
    async with AsyncClient(app=asgi_app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.get("/users/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1
```

## Testing Utilities

### Mock Injection

```python
from whiskey.testing import mock_injection

@mock_injection({
    Database: AsyncMock(find_user=AsyncMock(return_value={"id": 1})),
    Cache: AsyncMock(get=AsyncMock(return_value=None))
})
async def test_with_mock_injection():
    # Dependencies are automatically mocked
    service = await resolve(UserService)
    user = await service.get_user(1)
    assert user["id"] == 1
```

### Snapshot Testing

```python
@pytest.mark.asyncio
async def test_service_snapshot(snapshot):
    """Test service output matches snapshot"""
    service = create_test_service()
    result = await service.complex_operation()
    
    # Compare with snapshot
    assert result == snapshot
```

### Parameterized Tests

```python
@pytest.mark.parametrize("user_id,expected_name", [
    (1, "Alice"),
    (2, "Bob"),
    (3, "Charlie"),
])
@pytest.mark.asyncio
async def test_multiple_users(user_id, expected_name):
    service = create_test_service()
    user = await service.get_user(user_id)
    assert user["name"] == expected_name
```

## Testing Best Practices

### 1. Test Isolation

Each test should be independent:

```python
@pytest.fixture(autouse=True)
def reset_container():
    """Reset container before each test"""
    from whiskey import _default_app
    _default_app = None
    yield
    _default_app = None
```

### 2. Descriptive Test Names

```python
def test_user_service_returns_cached_user_when_cache_hit():
    """Test names should describe the scenario"""
    pass

def test_user_service_fetches_from_db_when_cache_miss():
    """Be specific about the behavior being tested"""
    pass
```

### 3. Arrange-Act-Assert Pattern

```python
@pytest.mark.asyncio
async def test_aaa_pattern():
    # Arrange - Setup test data and mocks
    mock_db = AsyncMock()
    mock_db.find_user.return_value = {"id": 1, "name": "Test"}
    service = UserService(mock_db, AsyncMock())
    
    # Act - Execute the behavior
    user = await service.get_user(1)
    
    # Assert - Verify the outcome
    assert user["name"] == "Test"
    mock_db.find_user.assert_called_once_with(1)
```

### 4. Test Edge Cases

```python
@pytest.mark.asyncio
async def test_user_not_found():
    mock_db = AsyncMock()
    mock_db.find_user.return_value = None
    
    service = UserService(mock_db, AsyncMock())
    user = await service.get_user(999)
    
    assert user is None

@pytest.mark.asyncio
async def test_database_error():
    mock_db = AsyncMock()
    mock_db.find_user.side_effect = DatabaseError("Connection lost")
    
    service = UserService(mock_db, AsyncMock())
    
    with pytest.raises(DatabaseError):
        await service.get_user(1)
```

### 5. Use Fixtures for Common Setup

```python
@pytest.fixture
def common_test_data():
    """Reusable test data"""
    return {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ],
        "api_key": "test-key-123"
    }

def test_with_fixtures(common_test_data):
    users = common_test_data["users"]
    assert len(users) == 2
```

## Performance Testing

```python
import pytest
import time

@pytest.mark.asyncio
async def test_performance():
    service = create_service()
    
    start = time.time()
    for _ in range(1000):
        await service.process()
    duration = time.time() - start
    
    # Assert performance requirement
    assert duration < 1.0  # Should complete in under 1 second
```

## Testing Checklist

- [ ] Unit tests for each component
- [ ] Integration tests for external dependencies
- [ ] Edge case coverage
- [ ] Error handling tests
- [ ] Performance tests for critical paths
- [ ] Mocked external services
- [ ] Test data builders
- [ ] Proper test isolation
- [ ] Clear test documentation
- [ ] CI/CD integration

## Next Steps

- Explore [Advanced Patterns](advanced.md) for complex testing scenarios
- Check out [Examples](examples.md) with full test suites
- Learn about testing specific [Extensions](extensions.md)