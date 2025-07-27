"""Basic HTTP client example using whiskey-http."""

from whiskey import Whiskey, inject
from whiskey_http import http_extension

# Create app and use HTTP extension
app = Whiskey()
app.use(http_extension)


# Register a simple HTTP client
@app.http_client("jsonplaceholder", base_url="https://jsonplaceholder.typicode.com")
class JSONPlaceholderClient:
    """Client for JSONPlaceholder API."""

    pass


# Service that uses the HTTP client
@app.component
class PostService:
    def __init__(self, client: JSONPlaceholderClient):
        self.client = client

    async def get_posts(self, limit: int = 10):
        """Get posts from the API."""
        response = await self.client.get("/posts", params={"_limit": limit})
        return response.json()

    async def get_post(self, post_id: int):
        """Get a single post."""
        response = await self.client.get(f"/posts/{post_id}")
        return response.json()

    async def create_post(self, title: str, body: str, user_id: int):
        """Create a new post."""
        response = await self.client.post(
            "/posts", json={"title": title, "body": body, "userId": user_id}
        )
        return response.json()


# Main function to demonstrate usage
@inject
async def main(service: PostService):
    """Main function demonstrating HTTP client usage."""
    # Get posts
    print("Fetching posts...")
    posts = await service.get_posts(5)
    for post in posts:
        print(f"- {post['title']}")

    print("\n" + "=" * 50 + "\n")

    # Get single post
    print("Fetching post #1...")
    post = await service.get_post(1)
    print(f"Title: {post['title']}")
    print(f"Body: {post['body']}")

    print("\n" + "=" * 50 + "\n")

    # Create a post
    print("Creating a new post...")
    new_post = await service.create_post(
        title="Hello from Whiskey HTTP!",
        body="This post was created using the whiskey-http extension.",
        user_id=1,
    )
    print(f"Created post with ID: {new_post['id']}")


if __name__ == "__main__":
    app.run(main)
