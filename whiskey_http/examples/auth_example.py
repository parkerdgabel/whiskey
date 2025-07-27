"""Example demonstrating authentication patterns."""

import os

import httpx

from whiskey import Whiskey, inject
from whiskey_http import http_extension

app = Whiskey()
app.use(http_extension)


# Bearer token authentication
class BearerAuth(httpx.Auth):
    """Bearer token authentication."""

    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


# GitHub API client with authentication
@app.http_client(
    "github",
    base_url="https://api.github.com",
    headers={"Accept": "application/vnd.github.v3+json"},
    auth=BearerAuth(os.getenv("GITHUB_TOKEN", "fake-token")),
)
class GitHubClient:
    """GitHub API client with authentication."""

    pass


# OAuth2 client with dynamic token management
@app.http_client("oauth_api", base_url="https://api.example.com")
class OAuth2Client:
    """Client with OAuth2 authentication."""

    def __init__(self):
        self.access_token = None
        self.refresh_token = None

    async def authenticate(self, client_id: str, client_secret: str):
        """Authenticate and get tokens."""
        # In a real app, this would call the OAuth2 token endpoint
        self.access_token = "mock-access-token"
        self.refresh_token = "mock-refresh-token"

    @app.request_interceptor
    async def add_auth_header(self, request):
        """Add OAuth2 token to requests."""
        if self.access_token:
            request.headers["Authorization"] = f"Bearer {self.access_token}"
        return request

    @app.response_interceptor
    async def handle_auth_errors(self, response):
        """Handle 401 errors by refreshing token."""
        if response.status_code == 401 and self.refresh_token:
            # In a real app, refresh the token here
            print("🔄 Refreshing OAuth2 token...")
            self.access_token = "new-mock-access-token"

            # Retry the request with new token
            request = response.request
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            # Note: In production, you'd need proper retry logic here

        return response


# API key authentication via query parameter
@app.http_client(
    "api_key_service",
    base_url="https://api.example.com",
    params={"api_key": os.getenv("API_KEY", "demo-key")},
)
class APIKeyClient:
    """Client using API key in query parameters."""

    pass


@app.component
class AuthDemoService:
    def __init__(self, github: GitHubClient, oauth: OAuth2Client, api_key: APIKeyClient):
        self.github = github
        self.oauth = oauth
        self.api_key = api_key

    async def demo_github(self):
        """Demo GitHub API with bearer token."""
        print("🔐 Testing GitHub API with Bearer token...")

        try:
            # This will fail with fake token but demonstrates the auth
            response = await self.github.get("/user")
            user = response.json()
            print(f"✅ Authenticated as: {user['login']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                print("❌ Authentication failed (expected with fake token)")
            else:
                print(f"❌ Error: {e}")

    async def demo_oauth2(self):
        """Demo OAuth2 flow."""
        print("\n🔑 Testing OAuth2 authentication...")

        # Authenticate
        await self.oauth.authenticate("client-id", "client-secret")
        print("✅ Authenticated with OAuth2")

        # Make authenticated request
        try:
            await self.oauth.get("/protected-resource")
            print("✅ Accessed protected resource")
        except Exception as e:
            print(f"Info: Mock request (no real endpoint): {type(e).__name__}")

    async def demo_api_key(self):
        """Demo API key authentication."""
        print("\n🔑 Testing API key authentication...")

        try:
            # The API key is automatically included in query params
            await self.api_key.get("/data")
            print("✅ Request includes API key in params")
        except Exception as e:
            print(f"Info: Mock request (no real endpoint): {type(e).__name__}")


@inject
async def main(service: AuthDemoService):
    """Demonstrate various authentication patterns."""
    print("🔐 HTTP Client Authentication Examples\n")

    await service.demo_github()
    await service.demo_oauth2()
    await service.demo_api_key()


if __name__ == "__main__":
    app.run(main)
