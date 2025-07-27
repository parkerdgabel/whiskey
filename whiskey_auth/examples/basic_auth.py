"""Basic password authentication example."""

from dataclasses import dataclass
from typing import ClassVar, Optional

from whiskey import Whiskey, inject
from whiskey_auth import (
    CurrentUser,
    PasswordHasher,
    auth_extension,
    requires_auth,
    requires_permission,
    requires_role,
)
from whiskey_auth.providers import PasswordAuthProvider
from whiskey_sql import SQL, Database, sql_extension

# Create application
app = Whiskey()
app.use(auth_extension)
app.use(sql_extension)

# Configure database
app.configure_database(url="sqlite://:memory:")


# Define user model
@app.user_model
@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    is_active: bool = True
    permissions: list[str] = None
    roles: list[str] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
        if self.roles is None:
            self.roles = []


# Define permissions
@app.permissions
class Permissions:
    READ_POSTS = "read_posts"
    WRITE_POSTS = "write_posts"
    DELETE_POSTS = "delete_posts"
    ADMIN = "admin"


# Define roles
@app.role("reader")
class ReaderRole:
    permissions: ClassVar[list[str]] = [Permissions.READ_POSTS]
    description: ClassVar[str] = "Can read posts"


@app.role("writer")
class WriterRole:
    permissions: ClassVar[list[str]] = [Permissions.READ_POSTS, Permissions.WRITE_POSTS]
    inherits: ClassVar[list] = [ReaderRole]
    description: ClassVar[str] = "Can read and write posts"


@app.role("admin")
class AdminRole:
    permissions: ClassVar[list[str]] = [Permissions.ADMIN]
    inherits: ClassVar[list] = [WriterRole]
    description: ClassVar[str] = "Full admin access"


# SQL queries
@app.sql("users")
class UserQueries:
    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            permissions TEXT,
            roles TEXT
        )
    """)

    get_by_username = SQL("""
        SELECT * FROM users WHERE username = :username
    """)

    create = SQL("""
        INSERT INTO users (username, email, password_hash, permissions, roles)
        VALUES (:username, :email, :password_hash, :permissions, :roles)
    """)

    get_by_id = SQL("""
        SELECT * FROM users WHERE id = :id
    """)


# Custom password auth provider
@app.auth_provider("password")
class DatabasePasswordAuth(PasswordAuthProvider):
    def __init__(self, db: Database, queries: UserQueries):
        super().__init__()
        self.db = db
        self.queries = queries

    async def get_user_by_username(self, username: str) -> User | None:
        row = await self.db.fetch_one(self.queries.get_by_username, {"username": username})
        if not row:
            return None

        # Parse permissions and roles from comma-separated strings
        permissions = row["permissions"].split(",") if row["permissions"] else []
        roles = row["roles"].split(",") if row["roles"] else []

        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"]),
            permissions=permissions,
            roles=roles,
        )

    async def get_password_hash(self, user: User) -> str:
        return user.password_hash

    async def get_user(self, user_id: int) -> User | None:
        row = await self.db.fetch_one(self.queries.get_by_id, {"id": user_id})
        if not row:
            return None

        permissions = row["permissions"].split(",") if row["permissions"] else []
        roles = row["roles"].split(",") if row["roles"] else []

        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"]),
            permissions=permissions,
            roles=roles,
        )


# Service layer
@app.component
class UserService:
    def __init__(self, db: Database, queries: UserQueries, hasher: PasswordHasher):
        self.db = db
        self.queries = queries
        self.hasher = hasher

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        permissions: Optional[list[str]] = None,
        roles: Optional[list[str]] = None,
    ) -> User:
        """Create a new user."""
        # Hash password
        password_hash = await self.hasher.hash(password)

        # Store permissions and roles as comma-separated
        perms_str = ",".join(permissions) if permissions else ""
        roles_str = ",".join(roles) if roles else ""

        # Create user
        await self.db.execute(
            self.queries.create,
            {
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "permissions": perms_str,
                "roles": roles_str,
            },
        )

        # Get created user
        return await self.db.fetch_one(self.queries.get_by_username, {"username": username})


# Protected endpoints
@requires_auth
@inject
async def get_profile(user: CurrentUser):
    """Get current user profile - requires authentication."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": user.roles,
        "permissions": user.permissions,
    }


@requires_permission(Permissions.WRITE_POSTS)
@inject
async def create_post(title: str, content: str, user: CurrentUser):
    """Create a post - requires WRITE_POSTS permission."""
    return {"title": title, "content": content, "author": user.username, "created": True}


@requires_role("admin")
@inject
async def admin_action(user: CurrentUser):
    """Admin only action - requires admin role."""
    return {"message": f"Admin action performed by {user.username}", "admin": True}


# Demo application
@app.main
@inject
async def main(
    auth: DatabasePasswordAuth, user_service: UserService, db: Database, queries: UserQueries
):
    """Demonstrate authentication features."""

    print("=== Whiskey Auth Example ===\n")

    # Initialize database
    await db.execute(queries.create_table)

    # Create test users
    print("Creating test users...")

    # Reader user
    reader = await user_service.create_user(
        "reader", "reader@example.com", "reader123", roles=["reader"]
    )
    print(f"✅ Created reader user: {reader.username}")

    # Writer user
    writer = await user_service.create_user(
        "writer", "writer@example.com", "writer123", roles=["writer"]
    )
    print(f"✅ Created writer user: {writer.username}")

    # Admin user
    admin = await user_service.create_user(
        "admin", "admin@example.com", "admin123", permissions=[Permissions.ADMIN], roles=["admin"]
    )
    print(f"✅ Created admin user: {admin.username}")

    # Test authentication
    print("\n--- Testing Authentication ---")

    # Valid login
    authenticated = await auth.authenticate(username="reader", password="reader123")
    if authenticated:
        print(f"✅ Successfully authenticated as {authenticated.username}")

    # Invalid password
    failed_auth = await auth.authenticate(username="reader", password="wrong")
    print(f"❌ Failed authentication with wrong password: {failed_auth is None}")

    # Test authorization
    print("\n--- Testing Authorization ---")

    # Simulate different users
    for test_user in [reader, writer, admin]:
        print(f"\nTesting as {test_user.username} (roles: {test_user.roles}):")

        # Inject user into context (normally done by middleware)
        from whiskey_auth.core import AuthContext

        auth_context = AuthContext(user=test_user)

        # Test profile access (requires auth)
        try:
            profile = await get_profile(__auth_context__=auth_context)
            print(f"  ✅ Can access profile: {profile['username']}")
        except Exception as e:
            print(f"  ❌ Cannot access profile: {e}")

        # Test post creation (requires WRITE_POSTS)
        try:
            await create_post("Test Post", "Content", __auth_context__=auth_context)
            print("  ✅ Can create posts")
        except Exception as e:
            print(f"  ❌ Cannot create posts: {type(e).__name__}")

        # Test admin action (requires admin role)
        try:
            await admin_action(__auth_context__=auth_context)
            print("  ✅ Can perform admin actions")
        except Exception as e:
            print(f"  ❌ Cannot perform admin actions: {type(e).__name__}")

    # Test password validation
    print("\n--- Testing Password Validation ---")
    from whiskey_auth.password import PasswordValidator

    validator = PasswordValidator(
        min_length=8,
        require_uppercase=True,
        require_lowercase=True,
        require_digit=True,
        require_special=True,
    )

    test_passwords = [
        ("weak", "Too weak"),
        ("StrongP@ss123", "Strong password"),
        ("no_uppercase123!", "Missing uppercase"),
        ("NO_LOWERCASE123!", "Missing lowercase"),
        ("NoDigits!", "Missing digits"),
        ("NoSpecial123", "Missing special chars"),
    ]

    for password, description in test_passwords:
        errors = validator.validate(password)
        if errors:
            print(f"❌ {description}: {errors[0]}")
        else:
            print(f"✅ {description}: Valid")

    print("\n✅ Demo completed!")


if __name__ == "__main__":
    app.run()
