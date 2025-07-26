"""Tests for core auth functionality."""

import pytest
from dataclasses import dataclass

from whiskey import Whiskey
from whiskey_auth import (
    auth_extension,
    AuthenticationError,
    AuthorizationError,
    Permission,
    Role,
    PasswordHasher,
)
from whiskey_auth.core import AuthContext


@dataclass
class TestUser:
    id: int
    username: str
    is_active: bool = True
    permissions: list[str] = None
    roles: list[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
        if self.roles is None:
            self.roles = []


class TestAuthCore:
    """Test core authentication functionality."""
    
    def test_permission(self):
        """Test Permission class."""
        perm1 = Permission("read", "Can read resources")
        perm2 = Permission("read")
        perm3 = Permission("write")
        
        # Test equality
        assert perm1 == perm2
        assert perm1 == "read"
        assert perm1 != perm3
        assert perm1 != "write"
        
        # Test string representation
        assert str(perm1) == "read"
        
        # Test hashing
        assert hash(perm1) == hash(perm2)
        assert hash(perm1) != hash(perm3)
    
    def test_role(self):
        """Test Role class."""
        # Create permissions
        read_perm = Permission("read")
        write_perm = Permission("write")
        delete_perm = Permission("delete")
        
        # Create roles
        reader = Role("reader", permissions={read_perm})
        writer = Role("writer", permissions={read_perm, write_perm})
        admin = Role("admin", permissions={delete_perm}, inherits=[writer])
        
        # Test basic properties
        assert reader.name == "reader"
        assert len(reader.permissions) == 1
        
        # Test permission checking
        assert reader.has_permission("read")
        assert not reader.has_permission("write")
        
        # Test inheritance
        all_admin_perms = admin.get_all_permissions()
        assert len(all_admin_perms) == 3  # read, write, delete
        assert admin.has_permission("read")  # inherited
        assert admin.has_permission("write")  # inherited
        assert admin.has_permission("delete")  # direct
        
        # Test equality
        assert reader == "reader"
        assert reader == Role("reader")
        assert reader != writer
    
    def test_auth_context(self):
        """Test AuthContext class."""
        # Test unauthenticated context
        context = AuthContext()
        assert not context.is_authenticated
        assert not context.has_permission("read")
        assert not context.has_role("admin")
        
        # Test authenticated context
        user = TestUser(id=1, username="alice")
        context = AuthContext(user=user)
        assert context.is_authenticated
        
        # Test with inactive user
        inactive_user = TestUser(id=2, username="bob", is_active=False)
        context = AuthContext(user=inactive_user)
        assert not context.is_authenticated
        
        # Test permissions
        user_with_perms = TestUser(
            id=3,
            username="charlie",
            permissions=["read", "write"]
        )
        context = AuthContext(user=user_with_perms)
        assert context.has_permission("read")
        assert context.has_permission(Permission("write"))
        assert not context.has_permission("delete")
        
        # Test roles
        user_with_roles = TestUser(
            id=4,
            username="diana",
            roles=["admin", "moderator"]
        )
        context = AuthContext(user=user_with_roles)
        assert context.has_role("admin")
        assert context.has_role(Role("moderator"))
        assert not context.has_role("user")


class TestPasswordSecurity:
    """Test password hashing and validation."""
    
    @pytest.mark.asyncio
    async def test_password_hasher(self):
        """Test password hashing."""
        hasher = PasswordHasher()
        
        # Test hashing
        password = "MySecureP@ssw0rd"
        hash1 = await hasher.hash(password)
        hash2 = await hasher.hash(password)
        
        # Hashes should be different (due to random salt)
        assert hash1 != hash2
        
        # Both should verify correctly
        assert await hasher.verify(password, hash1)
        assert await hasher.verify(password, hash2)
        
        # Wrong password should fail
        assert not await hasher.verify("WrongPassword", hash1)
        
        # Test verify and update
        old_hasher = PasswordHasher(time_cost=1)  # Weak params
        old_hash = await old_hasher.hash(password)
        
        new_hasher = PasswordHasher(time_cost=2)  # Stronger params
        valid, new_hash = await new_hasher.verify_and_update(password, old_hash)
        
        assert valid
        assert new_hash is not None  # Should need rehashing
        assert new_hash != old_hash
    
    def test_password_validator(self):
        """Test password validation."""
        from whiskey_auth.password import PasswordValidator
        
        validator = PasswordValidator(
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special=True
        )
        
        # Test valid password
        assert validator.is_valid("ValidP@ss123")
        assert len(validator.validate("ValidP@ss123")) == 0
        
        # Test various invalid passwords
        test_cases = [
            ("short", ["at least 8 characters"]),
            ("alllowercase123!", ["uppercase"]),
            ("ALLUPPERCASE123!", ["lowercase"]),
            ("NoDigitsHere!", ["digit"]),
            ("NoSpecialChars123", ["special character"]),
            ("", ["at least 8 characters"]),
        ]
        
        for password, expected_errors in test_cases:
            errors = validator.validate(password)
            assert len(errors) > 0
            assert any(expected in error for error in errors for expected in expected_errors)


class TestWhiskeyIntegration:
    """Test integration with Whiskey framework."""
    
    def test_extension_setup(self):
        """Test auth extension setup."""
        app = Whiskey()
        app.use(auth_extension)
        
        # Check that methods are added
        assert hasattr(app, "user_model")
        assert hasattr(app, "auth_provider")
        assert hasattr(app, "permissions")
        assert hasattr(app, "role")
        assert hasattr(app, "requires_auth")
        assert hasattr(app, "requires_permission")
        assert hasattr(app, "requires_role")
    
    def test_user_model_registration(self):
        """Test user model registration."""
        app = Whiskey()
        app.use(auth_extension)
        
        @app.user_model
        class User:
            id: int
            username: str
        
        # Check that user model is stored
        assert app.container.get("__auth_user_model__") is User
    
    def test_permission_registration(self):
        """Test permission registration."""
        app = Whiskey()
        app.use(auth_extension)
        
        @app.permissions
        class Perms:
            READ = "read"
            WRITE = "write"
            ADMIN = Permission("admin", "Admin access")
        
        # Check that permissions are stored
        perms = app.container.get("__auth_permissions__")
        assert len(perms) == 3
        assert "READ" in perms
        assert isinstance(perms["READ"], Permission)
        assert perms["READ"].name == "read"
        
        # Check that they're available on class
        assert isinstance(Perms.READ, Permission)
        assert Perms.ADMIN.description == "Admin access"
    
    def test_role_registration(self):
        """Test role registration."""
        app = Whiskey()
        app.use(auth_extension)
        
        @app.role("admin")
        class AdminRole:
            permissions = ["read", "write", "delete"]
            description = "Administrator"
        
        # Check that role is stored
        roles = app.container.get("__auth_roles__")
        assert "admin" in roles
        assert isinstance(roles["admin"], Role)
        assert roles["admin"].name == "admin"
        assert len(roles["admin"].permissions) == 3