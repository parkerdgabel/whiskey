"""Example demonstrating request/response interceptors."""

import asyncio
import time
from whiskey import Whiskey, inject
from whiskey_http import http_extension


app = Whiskey()
app.use(http_extension)


# HTTP client with interceptors
@app.http_client("api", base_url="https://jsonplaceholder.typicode.com")
class APIClient:
    """API client with logging and metrics."""

    def __init__(self):
        self.request_count = 0
        self.total_time = 0.0

    @app.request_interceptor
    async def log_request(self, request):
        """Log outgoing requests."""
        print(f"🔵 {request.method} {request.url}")

        # Add custom header
        request.headers["X-Client"] = "whiskey-http"

        # Track request count
        self.request_count += 1

        # Store start time in request extensions
        request.extensions["start_time"] = time.time()

        return request

    @app.response_interceptor
    async def log_response(self, response):
        """Log responses with timing."""
        # Calculate duration
        start_time = response.request.extensions.get("start_time", time.time())
        duration = time.time() - start_time
        self.total_time += duration

        # Log response
        status_emoji = "✅" if response.status_code < 400 else "❌"
        print(f"{status_emoji} {response.status_code} - {response.url} ({duration:.2f}s)")

        return response


# Service using the client
@app.component
class DataService:
    def __init__(self, api: APIClient):
        self.api = api

    async def fetch_multiple(self):
        """Fetch multiple resources to demonstrate interceptors."""
        # Fetch users
        users = await self.api.get("/users", params={"_limit": 3})

        # Fetch posts for each user
        for user in users.json():
            await self.api.get(f"/users/{user['id']}/posts", params={"_limit": 2})

        # Get stats
        avg_time = self.api.total_time / self.api.request_count if self.api.request_count > 0 else 0

        return {
            "total_requests": self.api.request_count,
            "total_time": f"{self.api.total_time:.2f}s",
            "average_time": f"{avg_time:.2f}s",
        }


@inject
async def main(service: DataService):
    """Demonstrate interceptors."""
    print("🚀 Starting requests with interceptors...\n")

    stats = await service.fetch_multiple()

    print("\n📊 Statistics:")
    print(f"  Total Requests: {stats['total_requests']}")
    print(f"  Total Time: {stats['total_time']}")
    print(f"  Average Time: {stats['average_time']}")


if __name__ == "__main__":
    app.run(main)
