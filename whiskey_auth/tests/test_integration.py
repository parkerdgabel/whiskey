"""Integration tests for whiskey_auth."""

from dataclasses import dataclass
from typing import ClassVar, Optional

import pytest

from whiskey import Whiskey, inject
from whiskey_auth import (
    AuthorizationError,
    AuthProvider,
    CurrentUser,
    PasswordHasher,
    User,
    auth_extension,
    create_test_user,
)


class TestFullIntegration:
    """Test full integration scenarios."""

    @pytest.fixture
    def app(self):
        """Create fully configured app."""
        app = Whiskey()
        app.use(auth_extension)
        return app

    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, app):
        """Test complete authentication flow."""

        # Define user model
        @app.user_model
        @dataclass
        class User:
            id: int
            username: str
            email: str
            password_hash: str
            permissions: list[str] = None
            roles: list[str] = None
            is_active: bool = True

            def __post_init__(self):
                if self.permissions is None:
                    self.permissions = []
                if self.roles is None:
                    self.roles = []

        # Define permissions
        @app.permissions
        class Permissions:
            READ = "read"
            WRITE = "write"
            ADMIN = "admin"

        # Define roles
        @app.role("reader")
        class ReaderRole:
            permissions: ClassVar[list] = [Permissions.READ]

        @app.role("admin")
        class AdminRole:
            permissions: ClassVar[list] = [Permissions.READ, Permissions.WRITE, Permissions.ADMIN]

        # Create in-memory user storage
        users_db = {}

        # Define auth provider
        @app.auth_provider("password")
        class InMemoryAuthProvider(AuthProvider):
            def __init__(self, hasher: PasswordHasher):
                self.hasher = hasher

            async def authenticate(self, username: str, password: str) -> User | None:
                user_data = users_db.get(username)
                if not user_data:
                    return None

                if not await self.hasher.verify(password, user_data["password_hash"]):
                    return None

                return User(**user_data)

            async def get_user(self, user_id: int) -> User | None:
                for user_data in users_db.values():
                    if user_data["id"] == user_id:
                        return User(**user_data)
                return None

        # Create service that uses auth
        @app.component
        class UserService:
            def __init__(self, hasher: PasswordHasher):
                self.hasher = hasher

            async def create_user(
                self, username: str, email: str, password: str, roles: Optional[list[str]] = None
            ) -> User:
                password_hash = await self.hasher.hash(password)

                user_data = {
                    "id": len(users_db) + 1,
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                    "permissions": [],
                    "roles": roles or [],
                    "is_active": True,
                }

                users_db[username] = user_data
                return User(**user_data)

        # Protected endpoints
        @app.requires_auth
        @inject
        async def get_profile(user: CurrentUser) -> dict:
            return {"id": user.id, "username": user.username, "email": user.email}

        @app.requires_permission(Permissions.WRITE)
        @inject
        async def create_post(title: str, user: CurrentUser) -> dict:
            return {"title": title, "author": user.username}

        @app.requires_role("admin")
        @inject
        async def admin_panel(user: CurrentUser) -> dict:
            return {"admin": user.username, "access": "granted"}

        # Test the flow
        async with app:
            # Get services
            user_service = await app.container.resolve(UserService)
            auth_provider = await app.container.resolve(InMemoryAuthProvider)

            # Create users
            reader = await user_service.create_user(
                "reader", "reader@example.com", "reader123", roles=["reader"]
            )

            admin = await user_service.create_user(
                "admin", "admin@example.com", "admin123", roles=["admin"]
            )

            # Test authentication
            authenticated = await auth_provider.authenticate("reader", "reader123")
            assert authenticated is not None
            assert authenticated.username == "reader"

            # Test authorization with auth context
            from whiskey_auth.core import AuthContext

            # Reader context
            reader_context = AuthContext(user=reader)
            reader_context.roles_cache = {app.container["__auth_roles__"]["reader"]}

            # Can access profile
            profile = await get_profile(__auth_context__=reader_context)
            assert profile["username"] == "reader"

            # Cannot create posts (no write permission)
            with pytest.raises(AuthorizationError):
                await create_post("Test", __auth_context__=reader_context)

            # Cannot access admin panel
            with pytest.raises(AuthorizationError):
                await admin_panel(__auth_context__=reader_context)

            # Admin context
            admin_context = AuthContext(user=admin)
            admin_context.roles_cache = {app.container["__auth_roles__"]["admin"]}

            # Admin can do everything
            profile = await get_profile(__auth_context__=admin_context)
            assert profile["username"] == "admin"

            post = await create_post("Admin Post", __auth_context__=admin_context)
            assert post["author"] == "admin"

            panel = await admin_panel(__auth_context__=admin_context)
            assert panel["access"] == "granted"

    @pytest.mark.asyncio
    async def test_multiple_providers(self, app):
        """Test using multiple auth providers."""
        # User storage
        users = {
            1: create_test_user(id=1, username="dbuser"),
            2: create_test_user(id=2, username="apiuser"),
        }

        @app.auth_provider("database")
        class DatabaseAuth(AuthProvider):
            async def authenticate(self, user_id: int) -> User | None:
                return users.get(user_id)

        @app.auth_provider("api_key")
        class APIKeyAuth(AuthProvider):
            async def authenticate(self, api_key: str) -> User | None:
                if api_key == "secret-key-1":
                    return users[1]
                elif api_key == "secret-key-2":
                    return users[2]
                return None

        async with app:
            # Get providers
            db_auth = await app.container.resolve((AuthProvider, "database"))
            api_auth = await app.container.resolve((AuthProvider, "api_key"))

            # Test database auth
            user = await db_auth.authenticate(user_id=1)
            assert user.username == "dbuser"

            # Test API key auth
            user = await api_auth.authenticate(api_key="secret-key-2")
            assert user.username == "apiuser"

    @pytest.mark.asyncio
    async def test_custom_user_injection(self, app):
        """Test custom user injection in services."""

        @app.user_model
        @dataclass
        class CustomUser:
            id: int
            name: str
            org_id: int

        # Service that depends on current user
        @app.component
        class OrgService:
            @inject
            async def get_org_data(self, user: CurrentUser) -> dict:
                return {
                    "user_id": user.id,
                    "org_id": user.org_id,
                    "data": f"Data for org {user.org_id}",
                }

        async with app:
            # Create auth context
            from whiskey_auth.core import AuthContext

            user = CustomUser(id=1, name="Test User", org_id=42)
            auth_context = AuthContext(user=user)

            # Store in container for CurrentUser resolution
            app.container[AuthContext] = auth_context

            # Get service and test
            service = await app.container.resolve(OrgService)
            data = await service.get_org_data()

            assert data["user_id"] == 1
            assert data["org_id"] == 42
