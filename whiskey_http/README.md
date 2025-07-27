# whiskey-http

HTTP client extension for Whiskey that enables declarative HTTP client creation with dependency injection support.

## Features

- 🔌 **Declarative Client Registration** - Register HTTP clients with `@app.http_client()`
- 🌐 **Base URL Management** - Configure base URLs and environments
- 🔄 **Request/Response Interceptors** - Add middleware for logging, auth, retry logic
- ⚡ **Async-First** - Built on httpx for modern async Python
- 💉 **DI Integration** - Clients are automatically injectable
- 🔧 **Configurable** - Timeouts, retries, headers, and more
- 📊 **OpenTelemetry Support** - Built-in observability

## Installation

```bash
pip install whiskey-http
```

## Quick Start

```python
from whiskey import Whiskey
from whiskey_http import http_extension

app = Whiskey()
app.use(http_extension)

# Register a simple HTTP client
@app.http_client("github")
class GitHubClient:
    base_url = "https://api.github.com"
    headers = {"Accept": "application/vnd.github.v3+json"}

# Use in your services
@app.component
class UserService:
    def __init__(self, github: GitHubClient):
        self.github = github
    
    async def get_user(self, username: str):
        response = await self.github.get(f"/users/{username}")
        return response.json()
```

## Advanced Usage

### Request Interceptors

```python
@app.http_client("api", base_url="https://api.example.com")
@app.request_interceptor
async def add_auth_header(request):
    request.headers["Authorization"] = f"Bearer {get_token()}"
    return request

@app.response_interceptor
async def log_response(response):
    logger.info(f"{response.request.method} {response.url} - {response.status_code}")
    return response
```

### Retry Configuration

```python
@app.http_client("flaky_api")
class FlakyAPIClient:
    base_url = "https://flaky.example.com"
    retry = {
        "attempts": 3,
        "backoff": "exponential",
        "on_status": [500, 502, 503, 504]
    }
```

### Circuit Breaker

```python
@app.http_client("protected_api")
class ProtectedAPIClient:
    base_url = "https://protected.example.com"
    circuit_breaker = {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "expected_exception": httpx.HTTPStatusError
    }
```

## API Reference

See the [API documentation](https://whiskey.dev/extensions/http) for detailed reference.