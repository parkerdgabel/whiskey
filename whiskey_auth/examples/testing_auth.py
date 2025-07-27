"""Example of testing authentication with Whiskey Auth testing utilities."""

import pytest
from dataclasses import dataclass

from whiskey import Whiskey, inject
from whiskey_auth import (
    auth_extension,
    AuthenticationError,
    AuthorizationError,
    CurrentUser,
    requires_auth,
    requires_permission,
    requires_role,
    # Testing utilities
    create_test_user,
    MockAuthProvider,
    AuthTestClient,
    AuthTestContainer,
)
from whiskey_auth.testing import (
    assert_authenticated,
    assert_not_authenticated,
    assert_has_permission,
    assert_lacks_permission,
    assert_has_role,
    assert_lacks_role,
)


# Example application code to test
app = Whiskey()
app.use(auth_extension)


@app.user_model
@dataclass
class User:
    id: int
    username: str
    email: str
    permissions: list[str] = None
    roles: list[str] = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
        if self.roles is None:
            self.roles = []


# Protected functions to test
@requires_auth
@inject
async def get_profile(user: CurrentUser) -> dict:
    """Get user profile - requires authentication."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email
    }


@requires_permission("write")
@inject
async def create_article(title: str, user: CurrentUser) -> dict:
    """Create article - requires write permission."""
    return {
        "title": title,
        "author": user.username,
        "created": True
    }


@requires_role("admin")
@inject
async def delete_user(user_id: int, user: CurrentUser) -> dict:
    """Delete user - requires admin role."""
    return {
        "deleted_user_id": user_id,
        "deleted_by": user.username
    }


@requires_permission("read", "write")
@inject
async def edit_article(article_id: int, user: CurrentUser) -> dict:
    """Edit article - requires read OR write permission."""
    return {
        "article_id": article_id,
        "edited_by": user.username
    }


# Test examples
class TestAuthenticationFlow:
    """Test authentication flows using testing utilities."""
    
    @pytest.fixture
    def users(self):
        """Create test users with different permissions."""
        return {
            "alice": create_test_user(
                id=1,
                username="alice",
                password="alice123",
                permissions=["read"],
                roles=["reader"]
            ),
            "bob": create_test_user(
                id=2,
                username="bob",
                password="bob123",
                permissions=["read", "write"],
                roles=["writer"]
            ),
            "charlie": create_test_user(
                id=3,
                username="charlie",
                password="charlie123",
                permissions=["read", "write", "delete", "admin"],
                roles=["admin"]
            ),
            "inactive": create_test_user(
                id=4,
                username="inactive",
                is_active=False
            )
        }
    
    @pytest.fixture
    def auth_provider(self, users):
        """Create mock auth provider with test users."""
        return MockAuthProvider(users=list(users.values()))
    
    @pytest.fixture
    def client(self):
        """Create auth test client."""
        return AuthTestClient()
    
    @pytest.mark.asyncio
    async def test_authentication_success(self, auth_provider, users):
        """Test successful authentication."""
        # Authenticate with correct credentials
        user = await auth_provider.authenticate(
            username="alice",
            password="password"  # Default test password
        )
        
        assert user is not None
        assert user.username == "alice"
        
        # Verify auth provider tracked the call
        assert len(auth_provider.authenticate_calls) == 1
        assert auth_provider.authenticate_calls[0]["username"] == "alice"
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, auth_provider):
        """Test failed authentication."""
        # Wrong username
        user = await auth_provider.authenticate(
            username="nonexistent",
            password="password"
        )
        assert user is None
        
        # Wrong password
        user = await auth_provider.authenticate(
            username="alice",
            password="wrongpassword"
        )
        assert user is None
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_auth(self, client, users):
        """Test accessing protected endpoint with authentication."""
        alice = users["alice"]
        
        # Set up authentication
        client.authenticate_as(alice)
        
        # Call protected function
        result = await client.call(get_profile)
        
        assert result["username"] == "alice"
        assert result["email"] == "alice@example.com"
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_auth(self, client):
        """Test accessing protected endpoint without authentication."""
        # No authentication set
        
        with pytest.raises(AuthenticationError):
            await client.call(get_profile)
    
    @pytest.mark.asyncio
    async def test_permission_requirements(self, client, users):
        """Test permission-based authorization."""
        alice = users["alice"]  # Has 'read' permission
        bob = users["bob"]      # Has 'read' and 'write' permissions
        
        # Alice can't create articles (no write permission)
        client.authenticate_as(alice)
        with pytest.raises(AuthorizationError):
            await client.call(create_article, "Test Article")
        
        # Bob can create articles
        client.authenticate_as(bob)
        result = await client.call(create_article, "Test Article")
        assert result["created"] is True
        assert result["author"] == "bob"
    
    @pytest.mark.asyncio
    async def test_role_requirements(self, client, users):
        """Test role-based authorization."""
        bob = users["bob"]        # writer role
        charlie = users["charlie"]  # admin role
        
        # Bob can't delete users (not admin)
        client.authenticate_as(bob)
        with pytest.raises(AuthorizationError):
            await client.call(delete_user, 999)
        
        # Charlie can delete users
        client.authenticate_as(charlie)
        result = await client.call(delete_user, 999)
        assert result["deleted_user_id"] == 999
        assert result["deleted_by"] == "charlie"
    
    @pytest.mark.asyncio
    async def test_dynamic_permission_addition(self, client, users):
        """Test adding permissions dynamically."""
        alice = users["alice"]
        
        # Initially Alice can't write
        client.authenticate_as(alice)
        with pytest.raises(AuthorizationError):
            await client.call(create_article, "Test")
        
        # Add write permission
        client.with_permissions("write")
        result = await client.call(create_article, "Test")
        assert result["created"] is True
    
    @pytest.mark.asyncio
    async def test_multiple_permission_options(self, client, users):
        """Test endpoints accepting multiple permissions."""
        alice = users["alice"]  # Has 'read' only
        
        client.authenticate_as(alice)
        
        # Alice can edit (has 'read' which is one of the accepted permissions)
        result = await client.call(edit_article, 123)
        assert result["article_id"] == 123
        assert result["edited_by"] == "alice"


class TestAuthContext:
    """Test auth context assertions."""
    
    def test_auth_context_assertions(self):
        """Test auth context assertion helpers."""
        from whiskey_auth.core import AuthContext
        
        # Create test user
        user = create_test_user(
            username="testuser",
            permissions=["read", "write"],
            roles=["editor"]
        )
        
        # Test authenticated context
        auth_context = AuthContext(user=user)
        assert_authenticated(auth_context, user)
        assert_has_permission(auth_context, "read")
        assert_has_permission(auth_context, "write")
        assert_lacks_permission(auth_context, "delete")
        assert_has_role(auth_context, "editor")
        assert_lacks_role(auth_context, "admin")
        
        # Test unauthenticated context
        empty_context = AuthContext()
        assert_not_authenticated(empty_context)


class TestContainerIntegration:
    """Test container integration for DI testing."""
    
    @pytest.mark.asyncio
    async def test_container_user_injection(self):
        """Test injecting test users via container."""
        # Create test container
        container = AuthTestContainer()
        
        # Create test user
        user = create_test_user(username="containeruser")
        container.set_test_user(user)
        
        # Resolve CurrentUser
        from whiskey_auth.core import User as UserType
        resolved_user = await container.resolve(UserType)
        
        assert resolved_user is not None
        assert resolved_user.username == "containeruser"
    
    @pytest.mark.asyncio
    async def test_container_auth_context(self):
        """Test auth context via container."""
        from whiskey_auth.core import AuthContext
        
        container = AuthTestContainer()
        
        # Set test user
        user = create_test_user(username="contextuser")
        container.set_test_user(user)
        
        # Resolve auth context
        auth_context = await container.resolve(AuthContext)
        
        assert auth_context.is_authenticated
        assert auth_context.user.username == "contextuser"


# Example of using in actual tests
def example_test_suite():
    """Example of how to structure auth tests in your application."""
    
    class TestMyApplication:
        """Test my application with auth."""
        
        @pytest.fixture
        def app(self):
            """Create application with test auth."""
            app = Whiskey()
            app.use(auth_extension)
            
            # Use mock provider
            mock_provider = MockAuthProvider([
                create_test_user(id=1, username="user1", permissions=["read"]),
                create_test_user(id=2, username="user2", permissions=["read", "write"]),
                create_test_user(id=3, username="admin", roles=["admin"]),
            ])
            
            app.container[MockAuthProvider] = mock_provider
            
            return app
        
        @pytest.fixture
        def client(self):
            """Create test client."""
            return AuthTestClient()
        
        @pytest.mark.asyncio
        async def test_my_endpoint(self, app, client):
            """Test my protected endpoint."""
            # Get a user from the app
            user = create_test_user(username="testuser", permissions=["required_permission"])
            
            # Authenticate as the user
            client.authenticate_as(user)
            
            # Test your endpoint
            @requires_permission("required_permission")
            async def my_endpoint(user: CurrentUser):
                return {"success": True, "user": user.username}
            
            result = await client.call(my_endpoint)
            assert result["success"] is True
            assert result["user"] == "testuser"


if __name__ == "__main__":
    # Run the example
    print("=== Whiskey Auth Testing Examples ===\n")
    
    # Example 1: Create test users
    print("1. Creating test users:")
    regular_user = create_test_user(username="regular", permissions=["read"])
    admin_user = create_test_user(username="admin", permissions=["read", "write", "admin"], roles=["admin"])
    
    print(f"  Regular user: {regular_user.username} with permissions: {regular_user.permissions}")
    print(f"  Admin user: {admin_user.username} with roles: {admin_user.roles}")
    
    # Example 2: Mock authentication
    print("\n2. Mock authentication:")
    mock_auth = MockAuthProvider(users=[regular_user, admin_user])
    
    import asyncio
    
    async def test_mock_auth():
        # Test successful auth
        user = await mock_auth.authenticate(username="regular", password="password")
        print(f"  ✅ Authenticated as: {user.username if user else 'None'}")
        
        # Test failed auth
        user = await mock_auth.authenticate(username="regular", password="wrong")
        print(f"  ❌ Failed auth: {user is None}")
        
        # Check tracked calls
        print(f"  Auth calls tracked: {len(mock_auth.authenticate_calls)}")
    
    asyncio.run(test_mock_auth())
    
    # Example 3: Test client usage
    print("\n3. Test client usage:")
    client = AuthTestClient()
    
    async def test_client():
        # Test without auth
        try:
            await client.call(get_profile)
        except AuthenticationError:
            print("  ❌ Correctly blocked without auth")
        
        # Test with auth
        client.authenticate_as(regular_user)
        profile = await client.call(get_profile)
        print(f"  ✅ Got profile: {profile}")
        
        # Test with added permissions
        client.with_permissions("write")
        article = await client.call(create_article, "Test Article")
        print(f"  ✅ Created article: {article}")
    
    asyncio.run(test_client())
    
    print("\n✅ Testing examples completed!")