"""JWT authentication example for APIs."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from whiskey import Whiskey, inject
from whiskey_auth import (
    auth_extension,
    CurrentUser,
    PasswordHasher,
    requires_auth,
    AuthenticationError,
)
from whiskey_auth.providers import JWTAuthProvider, PasswordAuthProvider
from whiskey_sql import sql_extension, SQL, Database


# Create application
app = Whiskey()
app.use(auth_extension)
app.use(sql_extension)

# Configure database
app.configure_database(url="sqlite://:memory:")

# JWT configuration
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)


# User model
@app.user_model
@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    is_active: bool = True


# SQL queries
@app.sql("users")
class UserQueries:
    create_table = SQL("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    """)
    
    get_by_username = SQL("""
        SELECT * FROM users WHERE username = :username
    """)
    
    get_by_id = SQL("""
        SELECT * FROM users WHERE id = :id
    """)
    
    create = SQL("""
        INSERT INTO users (username, email, password_hash)
        VALUES (:username, :email, :password_hash)
    """)


# Password auth for login
@app.auth_provider("password")
class DatabasePasswordAuth(PasswordAuthProvider):
    def __init__(self, db: Database, queries: UserQueries):
        super().__init__()
        self.db = db
        self.queries = queries
    
    async def get_user_by_username(self, username: str) -> User | None:
        row = await self.db.fetch_one(
            self.queries.get_by_username,
            {"username": username}
        )
        if not row:
            return None
        
        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"])
        )
    
    async def get_password_hash(self, user: User) -> str:
        return user.password_hash


# JWT auth for API access
@app.auth_provider("jwt")
class DatabaseJWTAuth(JWTAuthProvider):
    def __init__(self, db: Database, queries: UserQueries):
        super().__init__(
            secret=JWT_SECRET,
            algorithm=JWT_ALGORITHM,
            token_lifetime=ACCESS_TOKEN_EXPIRE,
            refresh_token_lifetime=REFRESH_TOKEN_EXPIRE,
            issuer="whiskey-auth-example",
            audience="whiskey-api"
        )
        self.db = db
        self.queries = queries
    
    async def get_user_by_id(self, user_id: int) -> User | None:
        row = await self.db.fetch_one(
            self.queries.get_by_id,
            {"id": int(user_id)}
        )
        if not row:
            return None
        
        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"])
        )


# Authentication service
@app.component
class AuthService:
    def __init__(
        self,
        password_auth: DatabasePasswordAuth,
        jwt_auth: DatabaseJWTAuth,
        hasher: PasswordHasher
    ):
        self.password_auth = password_auth
        self.jwt_auth = jwt_auth
        self.hasher = hasher
    
    async def register(self, username: str, email: str, password: str) -> User:
        """Register new user."""
        # Hash password
        password_hash = await self.hasher.hash(password)
        
        # Create user
        await self.password_auth.db.execute(
            self.password_auth.queries.create,
            {
                "username": username,
                "email": email,
                "password_hash": password_hash
            }
        )
        
        # Return created user
        return await self.password_auth.get_user_by_username(username)
    
    async def login(self, username: str, password: str) -> dict:
        """Login and return tokens."""
        # Authenticate with password
        user = await self.password_auth.authenticate(
            username=username,
            password=password
        )
        
        if not user:
            raise AuthenticationError("Invalid username or password")
        
        # Generate tokens
        access_token = self.jwt_auth.create_token(user, "access")
        refresh_token = self.jwt_auth.create_token(user, "refresh")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(ACCESS_TOKEN_EXPIRE.total_seconds())
        }
    
    async def refresh(self, refresh_token: str) -> dict:
        """Refresh access token."""
        tokens = self.jwt_auth.refresh_token(refresh_token)
        
        if not tokens:
            raise AuthenticationError("Invalid refresh token")
        
        access_token, new_refresh_token = tokens
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": int(ACCESS_TOKEN_EXPIRE.total_seconds())
        }
    
    async def verify_token(self, token: str) -> User | None:
        """Verify JWT token and return user."""
        return await self.jwt_auth.authenticate(token=token)


# Protected endpoints
@requires_auth
@inject
async def get_current_user(user: CurrentUser) -> dict:
    """Get current user info - requires valid JWT."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active
    }


@requires_auth
@inject
async def update_profile(email: str, user: CurrentUser, db: Database) -> dict:
    """Update user profile - requires valid JWT."""
    await db.execute(
        SQL("UPDATE users SET email = :email WHERE id = :id"),
        {"email": email, "id": user.id}
    )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": email,
        "updated": True
    }


# Demo API simulation
@app.main
@inject
async def main(
    auth_service: AuthService,
    jwt_auth: DatabaseJWTAuth,
    db: Database,
    queries: UserQueries
):
    """Demonstrate JWT authentication flow."""
    
    print("=== Whiskey JWT Auth Example ===\n")
    
    # Initialize database
    await db.execute(queries.create_table)
    
    # 1. Register users
    print("1. Registering users...")
    
    alice = await auth_service.register(
        "alice",
        "alice@example.com",
        "SecureP@ss123"
    )
    print(f"✅ Registered user: {alice.username}")
    
    bob = await auth_service.register(
        "bob",
        "bob@example.com",
        "AnotherP@ss456"
    )
    print(f"✅ Registered user: {bob.username}")
    
    # 2. Login flow
    print("\n2. Login flow...")
    
    # Successful login
    try:
        tokens = await auth_service.login("alice", "SecureP@ss123")
        print(f"✅ Login successful!")
        print(f"   Access token: {tokens['access_token'][:20]}...")
        print(f"   Refresh token: {tokens['refresh_token'][:20]}...")
        print(f"   Expires in: {tokens['expires_in']} seconds")
        
        alice_access_token = tokens['access_token']
        alice_refresh_token = tokens['refresh_token']
    except AuthenticationError as e:
        print(f"❌ Login failed: {e}")
    
    # Failed login
    try:
        await auth_service.login("alice", "WrongPassword")
    except AuthenticationError as e:
        print(f"❌ Login failed with wrong password: {e}")
    
    # 3. Token verification
    print("\n3. Token verification...")
    
    # Verify valid token
    verified_user = await auth_service.verify_token(alice_access_token)
    if verified_user:
        print(f"✅ Token valid for user: {verified_user.username}")
    
    # Verify invalid token
    invalid_user = await auth_service.verify_token("invalid.token.here")
    print(f"❌ Invalid token verified: {invalid_user is None}")
    
    # 4. Accessing protected endpoints
    print("\n4. Accessing protected endpoints...")
    
    # Simulate auth context (normally done by middleware)
    from whiskey_auth.core import AuthContext
    
    # With valid auth
    alice_context = AuthContext(user=alice)
    try:
        user_info = await get_current_user(__auth_context__=alice_context)
        print(f"✅ Protected endpoint access successful: {user_info}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Without auth
    no_auth_context = AuthContext(user=None)
    try:
        await get_current_user(__auth_context__=no_auth_context)
    except AuthenticationError as e:
        print(f"❌ Protected endpoint blocked without auth: {e}")
    
    # 5. Token refresh
    print("\n5. Token refresh flow...")
    
    try:
        new_tokens = await auth_service.refresh(alice_refresh_token)
        print(f"✅ Token refreshed successfully!")
        print(f"   New access token: {new_tokens['access_token'][:20]}...")
        print(f"   New refresh token: {new_tokens['refresh_token'][:20]}...")
    except AuthenticationError as e:
        print(f"❌ Refresh failed: {e}")
    
    # 6. Token introspection
    print("\n6. Token introspection...")
    
    decoded = jwt_auth.decode_token(alice_access_token)
    if decoded:
        print(f"✅ Token decoded:")
        print(f"   User ID: {decoded['sub']}")
        print(f"   Username: {decoded.get('username')}")
        print(f"   Email: {decoded.get('email')}")
        print(f"   Type: {decoded.get('type')}")
        print(f"   Issuer: {decoded.get('iss')}")
        print(f"   Audience: {decoded.get('aud')}")
    
    # 7. API usage example
    print("\n7. Simulating API request flow...")
    
    # Simulate API request with Authorization header
    api_headers = {
        "Authorization": f"Bearer {alice_access_token}"
    }
    
    print("→ Request: GET /api/profile")
    print(f"  Headers: {api_headers}")
    
    # In a real app, middleware would extract and verify the token
    # Here we simulate it manually
    auth_header = api_headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = await jwt_auth.authenticate(token=token)
        if user:
            auth_context = AuthContext(user=user)
            profile = await get_current_user(__auth_context__=auth_context)
            print(f"← Response: 200 OK")
            print(f"  Body: {profile}")
        else:
            print("← Response: 401 Unauthorized")
    
    print("\n✅ JWT authentication demo completed!")


if __name__ == "__main__":
    app.run()