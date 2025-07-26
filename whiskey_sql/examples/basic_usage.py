"""Basic usage example for Whiskey SQL extension."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from whiskey import Whiskey, inject, singleton
from whiskey_sql import sql_extension, SQL, Database


# Define your data models
@dataclass
class User:
    id: int
    name: str
    email: str
    created_at: datetime


@dataclass
class Post:
    id: int
    user_id: int
    title: str
    content: str
    published: bool
    created_at: datetime


# Create application with SQL extension
app = Whiskey()
app.use(sql_extension)

# Configure database (uses DATABASE_URL env var by default)
app.configure_database(
    url="postgresql://localhost/whiskey_example",
    pool_size=10,
    echo_queries=True
)


# Define SQL queries
@app.sql("users")
class UserQueries:
    """SQL queries for user operations."""
    
    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    get_by_id = SQL("""
        SELECT id, name, email, created_at
        FROM users
        WHERE id = :id
    """)
    
    get_by_email = SQL("""
        SELECT id, name, email, created_at
        FROM users
        WHERE email = :email
    """)
    
    list_all = SQL("""
        SELECT id, name, email, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    
    create = SQL("""
        INSERT INTO users (name, email)
        VALUES (:name, :email)
        RETURNING id, name, email, created_at
    """)
    
    update = SQL("""
        UPDATE users
        SET name = :name
        WHERE id = :id
        RETURNING id, name, email, created_at
    """)
    
    delete = SQL("""
        DELETE FROM users
        WHERE id = :id
    """)


@app.sql("posts")
class PostQueries:
    """SQL queries for post operations."""
    
    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            published BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    get_user_posts = SQL("""
        SELECT id, user_id, title, content, published, created_at
        FROM posts
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """)
    
    create = SQL("""
        INSERT INTO posts (user_id, title, content, published)
        VALUES (:user_id, :title, :content, :published)
        RETURNING id, user_id, title, content, published, created_at
    """)


# Create service layer
@singleton
class UserService:
    """Service for user operations."""
    
    def __init__(self, db: Database, queries: UserQueries):
        self.db = db
        self.queries = queries
    
    async def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        # Check if email already exists
        existing = await self.db.fetch_one(
            self.queries.get_by_email,
            {"email": email}
        )
        if existing:
            raise ValueError(f"User with email {email} already exists")
        
        # Create user
        return await self.db.fetch_one(
            self.queries.create,
            {"name": name, "email": email},
            User
        )
    
    async def get_user(self, user_id: int) -> User | None:
        """Get user by ID."""
        return await self.db.fetch_one(
            self.queries.get_by_id,
            {"id": user_id},
            User
        )
    
    async def list_users(self, limit: int = 10, offset: int = 0) -> list[User]:
        """List all users with pagination."""
        return await self.db.fetch_all(
            self.queries.list_all,
            {"limit": limit, "offset": offset},
            User
        )
    
    async def update_user(self, user_id: int, name: str) -> User | None:
        """Update user name."""
        return await self.db.fetch_one(
            self.queries.update,
            {"id": user_id, "name": name},
            User
        )
    
    async def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        status = await self.db.execute(
            self.queries.delete,
            {"id": user_id}
        )
        return "DELETE 1" in status


@singleton
class PostService:
    """Service for post operations."""
    
    def __init__(self, db: Database, queries: PostQueries):
        self.db = db
        self.queries = queries
    
    async def create_post(
        self, 
        user_id: int, 
        title: str, 
        content: str,
        published: bool = False
    ) -> Post:
        """Create a new post."""
        return await self.db.fetch_one(
            self.queries.create,
            {
                "user_id": user_id,
                "title": title,
                "content": content,
                "published": published
            },
            Post
        )
    
    async def get_user_posts(self, user_id: int) -> list[Post]:
        """Get all posts for a user."""
        return await self.db.fetch_all(
            self.queries.get_user_posts,
            {"user_id": user_id},
            Post
        )


# Initialize database tables
@app.on_startup
async def init_database(db: Database, user_queries: UserQueries, post_queries: PostQueries):
    """Create database tables on startup."""
    print("🗄️  Initializing database tables...")
    
    await db.execute(user_queries.create_table)
    await db.execute(post_queries.create_table)
    
    print("✅ Database tables ready")


# Main application
@app.main
@inject
async def main(
    user_service: UserService,
    post_service: PostService,
    db: Database
):
    """Demonstrate SQL extension usage."""
    
    print("\n=== Whiskey SQL Extension Demo ===\n")
    
    # Create some users
    print("Creating users...")
    alice = await user_service.create_user("Alice", "alice@example.com")
    print(f"✅ Created user: {alice.name} (ID: {alice.id})")
    
    bob = await user_service.create_user("Bob", "bob@example.com")
    print(f"✅ Created user: {bob.name} (ID: {bob.id})")
    
    # List users
    print("\nListing all users:")
    users = await user_service.list_users()
    for user in users:
        print(f"  - {user.name} ({user.email})")
    
    # Create posts
    print(f"\nCreating posts for {alice.name}...")
    post1 = await post_service.create_post(
        alice.id,
        "Hello Whiskey SQL!",
        "This is my first post using Whiskey SQL extension.",
        published=True
    )
    print(f"✅ Created post: {post1.title}")
    
    post2 = await post_service.create_post(
        alice.id,
        "SQL Templates are Great",
        "Pure SQL with type safety - what's not to love?",
        published=True
    )
    print(f"✅ Created post: {post2.title}")
    
    # Get user's posts
    print(f"\nPosts by {alice.name}:")
    posts = await post_service.get_user_posts(alice.id)
    for post in posts:
        print(f"  - {post.title} (published: {post.published})")
    
    # Demonstrate transactions
    print("\nDemonstrating transactions...")
    try:
        async with db.transaction():
            # Create a user
            charlie = await db.fetch_one(
                SQL("INSERT INTO users (name, email) VALUES (:name, :email) RETURNING *"),
                {"name": "Charlie", "email": "charlie@example.com"},
                User
            )
            print(f"✅ Created user in transaction: {charlie.name}")
            
            # Force an error to rollback
            if charlie.name == "Charlie":
                raise ValueError("Simulating transaction rollback")
    except ValueError as e:
        print(f"❌ Transaction rolled back: {e}")
    
    # Verify Charlie was not created
    charlie_check = await user_service.get_user(3)
    print(f"Charlie exists: {charlie_check is not None}")
    
    # Use raw SQL
    print("\nUsing raw SQL queries...")
    user_count = await db.fetch_val(
        SQL("SELECT COUNT(*) FROM users")
    )
    print(f"Total users: {user_count}")
    
    # Get statistics
    stats = await db.fetch_row(
        SQL("SELECT COUNT(*) as user_count, MAX(id) as max_id FROM users")
    )
    if stats:
        count, max_id = stats
        print(f"Stats - Users: {count}, Max ID: {max_id}")
    
    print("\n✅ Demo completed!")


if __name__ == "__main__":
    # Run the application
    app.run()