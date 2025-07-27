"""Integration example showing HTTP extension with other Whiskey features."""

from dataclasses import dataclass

from whiskey import Whiskey, inject
from whiskey_asgi import asgi_extension
from whiskey_http import http_extension

# Create app with both HTTP and ASGI extensions
app = Whiskey()
app.use(http_extension)
app.use(asgi_extension)


# Data models
@dataclass
class Post:
    id: int
    title: str
    body: str
    user_id: int


@dataclass
class User:
    id: int
    name: str
    email: str


# External API client
@app.http_client("jsonplaceholder", base_url="https://jsonplaceholder.typicode.com")
class JSONPlaceholderClient:
    """Client for JSONPlaceholder API."""

    @app.request_interceptor
    async def log_requests(self, request):
        """Log all outgoing requests."""
        print(f"📤 {request.method} {request.url}")
        return request


# Service layer using the HTTP client
@app.singleton
class BlogService:
    """Service for managing blog data."""

    def __init__(self, api: JSONPlaceholderClient):
        self.api = api
        self._cache = {}

    async def get_posts(self, limit: int = 10) -> list[Post]:
        """Get posts from API with caching."""
        cache_key = f"posts:{limit}"

        if cache_key in self._cache:
            print("📦 Returning cached posts")
            return self._cache[cache_key]

        response = await self.api.get("/posts", params={"_limit": limit})
        data = response.json()

        posts = [Post(**post) for post in data]
        self._cache[cache_key] = posts

        return posts

    async def get_post(self, post_id: int) -> Post:
        """Get a single post."""
        response = await self.api.get(f"/posts/{post_id}")
        return Post(**response.json())

    async def get_user(self, user_id: int) -> User:
        """Get user information."""
        response = await self.api.get(f"/users/{user_id}")
        data = response.json()
        return User(id=data["id"], name=data["name"], email=data["email"])

    async def create_post(self, title: str, body: str, user_id: int) -> Post:
        """Create a new post."""
        response = await self.api.post(
            "/posts", json={"title": title, "body": body, "userId": user_id}
        )

        # Clear cache on write
        self._cache.clear()

        return Post(**response.json())


# ASGI routes using the service
@app.get("/posts")
@inject
async def list_posts(service: BlogService, limit: int = 10):
    """List blog posts."""
    posts = await service.get_posts(limit)
    return [{"id": p.id, "title": p.title} for p in posts]


@app.get("/posts/{post_id}")
@inject
async def get_post(post_id: int, service: BlogService):
    """Get a single post with author info."""
    post = await service.get_post(post_id)
    user = await service.get_user(post.userId)

    return {
        "post": {"id": post.id, "title": post.title, "body": post.body},
        "author": {"name": user.name, "email": user.email},
    }


@app.post("/posts")
@inject
async def create_post(request, service: BlogService):
    """Create a new post."""
    data = await request.json()

    post = await service.create_post(
        title=data["title"], body=data["body"], user_id=data.get("userId", 1)
    )

    return {"id": post.id, "title": post.title}, 201


# Middleware to add CORS headers
@app.middleware()
async def cors_middleware(request, call_next):
    """Add CORS headers to responses."""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
    return response


# CLI command to test the service
if hasattr(app, "command"):  # Check if CLI extension is loaded

    @app.command()
    @app.option("--limit", default=5, help="Number of posts to fetch")
    @inject
    async def test_api(limit: int, service: BlogService):
        """Test the blog API integration."""
        print(f"\n🚀 Testing Blog API (limit={limit})\n")

        # Get posts
        posts = await service.get_posts(limit)
        print(f"📋 Found {len(posts)} posts:")
        for post in posts[:3]:
            print(f"  - [{post.id}] {post.title}")

        if len(posts) > 3:
            print(f"  ... and {len(posts) - 3} more\n")

        # Get detailed info for first post
        if posts:
            post = await service.get_post(posts[0].id)
            user = await service.get_user(post.userId)
            print("📝 First post details:")
            print(f"  Title: {post.title}")
            print(f"  Author: {user.name} ({user.email})")


# Main entry point
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run CLI test
        @inject
        async def run_test(service: BlogService):
            await test_api(5, service)

        app.run(run_test)
    else:
        # Run ASGI server
        print("🌐 Starting Blog API server on http://localhost:8000")
        print("📚 Try these endpoints:")
        print("  GET  /posts")
        print("  GET  /posts/1")
        print("  POST /posts")
        print("\n💡 Run with 'test' argument to test the API client")

        app.run_asgi(port=8000)
