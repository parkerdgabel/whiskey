# Whiskey Auth Extension 🔐

Secure, flexible authentication and authorization for Whiskey applications with seamless dependency injection.

## Features

- **Multiple Auth Providers**: Password, JWT, Session, OAuth (coming soon)
- **Type-Safe CurrentUser Injection**: Automatically inject authenticated users
- **Role-Based Access Control**: Define roles with hierarchical permissions
- **Secure Password Hashing**: Argon2 by default with configurable parameters
- **Decorator-Based Protection**: Simple decorators for auth requirements
- **Middleware Integration**: Works seamlessly with whiskey_asgi
- **Testing Utilities**: Easy mocking and testing of auth flows

## Installation

```bash
pip install whiskey[auth]  # Includes whiskey-auth
# or
pip install whiskey-auth[redis]   # With Redis session support
pip install whiskey-auth[oauth]   # With OAuth providers
pip install whiskey-auth[totp]    # With 2FA support
pip install whiskey-auth[all]     # Everything
```

## Quick Start

```python
from whiskey import Whiskey, inject
from whiskey_auth import auth_extension, CurrentUser, requires_auth

# Create app with auth
app = Whiskey()
app.use(auth_extension)

# Define user model
@app.user_model
class User:
    id: int
    username: str
    email: str
    password_hash: str
    is_active: bool = True

# Create auth provider
@app.auth_provider
class MyAuthProvider(AuthProvider):
    async def authenticate(self, username: str, password: str) -> User | None:
        # Your auth logic here
        user = await get_user_by_username(username)
        if user and verify_password(password, user.password_hash):
            return user
        return None

# Protect endpoints
@requires_auth
@inject
async def profile(user: CurrentUser):
    return {"username": user.username, "email": user.email}

# Run the app
if __name__ == "__main__":
    app.run()
```

## Core Concepts

### 1. User Model

Define your user model with the `@app.user_model` decorator:

```python
@app.user_model
@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    is_active: bool = True
    permissions: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
```

The only requirement is that your user has an `id` attribute. Other attributes are optional but enhance functionality.

### 2. Authentication Providers

Create custom authentication providers by inheriting from `AuthProvider`:

```python
from whiskey_auth.providers import PasswordAuthProvider

@app.auth_provider("password")
class DatabasePasswordAuth(PasswordAuthProvider):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
    
    async def get_user_by_username(self, username: str) -> User | None:
        return await self.db.fetch_one(
            "SELECT * FROM users WHERE username = ?",
            username
        )
    
    async def get_password_hash(self, user: User) -> str:
        return user.password_hash
```

### 3. JWT Authentication

For stateless API authentication:

```python
from whiskey_auth.providers import JWTAuthProvider

@app.auth_provider("jwt")
class MyJWTAuth(JWTAuthProvider):
    def __init__(self, db: Database):
        super().__init__(
            secret="your-secret-key",
            algorithm="HS256",
            token_lifetime=timedelta(hours=1)
        )
        self.db = db
    
    async def get_user_by_id(self, user_id: str) -> User | None:
        return await self.db.fetch_one(
            "SELECT * FROM users WHERE id = ?",
            int(user_id)
        )

# Create tokens
jwt_auth = await app.container.resolve(MyJWTAuth)
token = jwt_auth.create_token(user)

# Verify tokens
user = await jwt_auth.authenticate(token=token)
```

### 4. Authorization

Define permissions and roles:

```python
# Define permissions
@app.permissions
class Permissions:
    READ_POSTS = "read_posts"
    WRITE_POSTS = "write_posts"
    DELETE_POSTS = "delete_posts"
    ADMIN = "admin"

# Define roles with permissions
@app.role("editor")
class EditorRole:
    permissions = [Permissions.READ_POSTS, Permissions.WRITE_POSTS]
    description = "Can read and write posts"

@app.role("admin")
class AdminRole:
    permissions = [Permissions.ADMIN]
    inherits = [EditorRole]  # Inherit editor permissions
    description = "Full admin access"

# Use in endpoints
@requires_permission(Permissions.WRITE_POSTS)
async def create_post(title: str, user: CurrentUser):
    # User must have WRITE_POSTS permission
    pass

@requires_role("admin")
async def admin_panel(user: CurrentUser):
    # User must have admin role
    pass
```

### 5. Password Security

Built-in password hashing with Argon2:

```python
from whiskey_auth import PasswordHasher, PasswordValidator

# Hash passwords
hasher = PasswordHasher()
password_hash = await hasher.hash("user_password")

# Verify passwords
is_valid = await hasher.verify("user_password", password_hash)

# Validate password strength
validator = PasswordValidator(
    min_length=8,
    require_uppercase=True,
    require_lowercase=True,
    require_digit=True,
    require_special=True
)

errors = validator.validate("weak")
if errors:
    raise ValueError(f"Password too weak: {', '.join(errors)}")
```

### 6. Decorators

Protect your endpoints with decorators:

```python
# Require authentication
@requires_auth
async def protected(user: CurrentUser):
    return f"Hello {user.username}"

# Require specific permission (ANY of the listed)
@requires_permission("read", "write")
async def content_access(user: CurrentUser):
    # User needs read OR write permission
    pass

# Require ALL permissions
@requires_all_permissions("read", "write", "delete")
async def full_access(user: CurrentUser):
    # User needs read AND write AND delete
    pass

# Require role
@requires_role("moderator", "admin")
async def moderate(user: CurrentUser):
    # User needs moderator OR admin role
    pass
```

### 7. Web Integration

When used with whiskey_asgi, authentication is handled automatically:

```python
from whiskey_asgi import asgi_extension

app = Whiskey()
app.use(auth_extension)
app.use(asgi_extension)

@app.post("/login")
async def login(request: Request, auth: PasswordAuthProvider):
    data = await request.json()
    user = await auth.authenticate(
        username=data["username"],
        password=data["password"]
    )
    
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    # Create session or JWT
    token = create_token(user)
    return {"access_token": token}

@app.get("/profile")
@requires_auth
async def profile(user: CurrentUser):
    # CurrentUser is automatically injected from request
    return {"user": user.username}
```

## Advanced Features

### Custom Authorization Rules

Create complex authorization logic:

```python
@app.authorize
async def can_edit_post(user: CurrentUser, post: Post) -> bool:
    # Owner can always edit
    if post.author_id == user.id:
        return True
    
    # Admins can edit anything
    if "admin" in user.roles:
        return True
    
    # Moderators can edit if post is flagged
    if "moderator" in user.roles and post.is_flagged:
        return True
    
    return False

@app.put("/posts/{post_id}")
@requires(can_edit_post)
async def edit_post(post_id: int, user: CurrentUser):
    post = await get_post(post_id)
    # Authorization check happens automatically
    ...
```

### Session Management (Coming Soon)

```python
# Configure sessions
app.configure_sessions(
    storage="redis",
    redis_url="redis://localhost",
    cookie_name="session_id",
    secure=True,
    httponly=True,
    max_age=86400
)

@app.auth_provider("session")
class SessionAuth:
    async def authenticate(self, session_id: str) -> User | None:
        session = await app.sessions.get(session_id)
        if session and session.user_id:
            return await get_user(session.user_id)
        return None
```

### OAuth Integration (Coming Soon)

```python
# Configure OAuth
app.configure_oauth(
    github=OAuthProvider(
        client_id="...",
        client_secret="...",
        redirect_uri="http://localhost:8000/auth/github/callback"
    )
)

@app.oauth_handler("github")
async def handle_github_auth(user_info: dict) -> User:
    # Create or update user from GitHub
    return await create_or_update_user(user_info)
```

## Testing

Whiskey Auth provides comprehensive testing utilities to make testing authentication flows easy and maintainable.

### Test User Creation

Create test users with sensible defaults:

```python
from whiskey_auth import create_test_user

# Basic user
user = create_test_user()  # id=1, username="testuser"

# Custom user
admin = create_test_user(
    id=2,
    username="admin",
    email="admin@example.com",
    password="secure123",  # Will be hashed
    permissions=["read", "write", "admin"],
    roles=["admin"],
    custom_field="value"  # Extra metadata
)
```

### Mock Authentication Provider

Test authentication without a real backend:

```python
from whiskey_auth import MockAuthProvider

# Create mock provider with test users
mock_auth = MockAuthProvider(users=[
    create_test_user(username="alice", password="alice123"),
    create_test_user(username="bob", password="bob123"),
])

# Test authentication
user = await mock_auth.authenticate(username="alice", password="alice123")
assert user.username == "alice"

# Track calls
assert len(mock_auth.authenticate_calls) == 1
```

### Auth Test Client

Test protected endpoints easily:

```python
from whiskey_auth import AuthTestClient

@pytest.fixture
def client():
    return AuthTestClient()

async def test_protected_endpoint(client):
    # Create test user
    user = create_test_user(username="testuser", permissions=["write"])
    
    # Authenticate as user
    client.authenticate_as(user)
    
    # Call protected function
    @requires_permission("write")
    async def create_post(title: str, user: CurrentUser):
        return {"title": title, "author": user.username}
    
    result = await client.call(create_post, "Test Post")
    assert result["author"] == "testuser"
    
    # Add permissions dynamically
    client.with_permissions("admin")
    
    # Add roles
    client.with_roles("moderator")
```

### Test Container

Inject test users via DI container:

```python
from whiskey_auth import AuthTestContainer

container = AuthTestContainer()

# Set test user for injection
user = create_test_user(username="injected")
container.set_test_user(user)

# Resolve CurrentUser anywhere
resolved_user = await container.resolve(CurrentUser)
assert resolved_user.username == "injected"
```

### Assertion Helpers

Use convenient assertion helpers:

```python
from whiskey_auth.testing import (
    assert_authenticated,
    assert_not_authenticated,
    assert_has_permission,
    assert_lacks_permission,
    assert_has_role,
    assert_lacks_role,
)

# Test auth context
auth_context = AuthContext(user=test_user)

assert_authenticated(auth_context, test_user)
assert_has_permission(auth_context, "read")
assert_lacks_permission(auth_context, "admin")
assert_has_role(auth_context, "editor")
assert_lacks_role(auth_context, "admin")
```

### Complete Test Example

```python
import pytest
from whiskey_auth import (
    AuthTestClient,
    create_test_user,
    requires_auth,
    requires_permission,
    AuthenticationError,
    AuthorizationError,
)

class TestMyApplication:
    @pytest.fixture
    def client(self):
        return AuthTestClient()
    
    @pytest.fixture
    def users(self):
        return {
            "reader": create_test_user(
                username="reader",
                permissions=["read"],
                roles=["reader"]
            ),
            "admin": create_test_user(
                username="admin", 
                permissions=["read", "write", "admin"],
                roles=["admin"]
            ),
        }
    
    @pytest.mark.asyncio
    async def test_authentication_required(self, client):
        """Test endpoint requires authentication."""
        @requires_auth
        async def protected(user: CurrentUser):
            return user.username
        
        # Without auth
        with pytest.raises(AuthenticationError):
            await client.call(protected)
        
        # With auth
        client.authenticate_as(create_test_user())
        result = await client.call(protected)
        assert result == "testuser"
    
    @pytest.mark.asyncio
    async def test_permission_based_access(self, client, users):
        """Test permission-based authorization."""
        @requires_permission("write")
        async def write_data(data: str, user: CurrentUser):
            return {"written_by": user.username, "data": data}
        
        # Reader can't write
        client.authenticate_as(users["reader"])
        with pytest.raises(AuthorizationError):
            await client.call(write_data, "content")
        
        # Admin can write
        client.authenticate_as(users["admin"])
        result = await client.call(write_data, "content")
        assert result["written_by"] == "admin"
```

## Security Best Practices

1. **Use Strong Secrets**: Generate cryptographically secure secrets for JWT signing
2. **HTTPS Only**: Always use HTTPS in production
3. **Secure Cookies**: Set secure, httponly, and samesite flags
4. **Rate Limiting**: Implement rate limiting on auth endpoints
5. **Password Requirements**: Enforce strong password policies
6. **Token Expiration**: Use short-lived access tokens with refresh tokens
7. **Audit Logging**: Log authentication events for security monitoring

## Examples

See the `examples/` directory for complete examples:
- `basic_auth.py` - Password authentication with roles and permissions
- `jwt_auth.py` - JWT-based API authentication
- `testing_auth.py` - Testing authentication flows with utilities
- `web_app.py` - Full web application with sessions (coming soon)
- `oauth_example.py` - Social login integration (coming soon)

## Contributing

We welcome contributions! See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.