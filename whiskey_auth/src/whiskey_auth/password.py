"""Secure password hashing and verification."""

from __future__ import annotations

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHash, VerifyMismatchError


class PasswordHasher:
    """Secure password hashing using Argon2.

    Argon2 is the winner of the Password Hashing Competition and is
    recommended for new applications. It's resistant to GPU cracking
    attacks and side-channel attacks.
    """

    def __init__(
        self,
        time_cost: int = 2,  # Number of iterations
        memory_cost: int = 65536,  # Memory usage in kibibytes (64 MB)
        parallelism: int = 1,  # Number of parallel threads
        hash_len: int = 32,  # Length of the hash in bytes
        salt_len: int = 16,  # Length of random salt in bytes
    ):
        """Initialize password hasher with Argon2 parameters.

        Args:
            time_cost: Number of iterations (higher = slower but more secure)
            memory_cost: Memory usage in kibibytes (higher = more secure)
            parallelism: Number of parallel threads
            hash_len: Length of the hash in bytes
            salt_len: Length of random salt in bytes
        """
        self._hasher = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
        )

    async def hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: Plain text password

        Returns:
            Hashed password string including salt and parameters

        Example:
            >>> hasher = PasswordHasher()
            >>> hash = await hasher.hash("my_secure_password")
            >>> print(hash)
            $argon2id$v=19$m=65536,t=2,p=1$...
        """
        return self._hasher.hash(password)

    async def verify(self, password: str, hash: str) -> bool:  # noqa: A002
        """Verify a password against a hash.

        Args:
            password: Plain text password to verify
            hash: Previously hashed password

        Returns:
            True if password matches, False otherwise

        Note:
            This method also performs hash parameter checking and will
            rehash if the parameters have changed (when used with check_needs_rehash).
        """
        try:
            self._hasher.verify(hash, password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False

    async def verify_and_update(self, password: str, hash: str) -> tuple[bool, str | None]:  # noqa: A002
        """Verify password and return updated hash if needed.

        Args:
            password: Plain text password to verify
            hash: Previously hashed password

        Returns:
            Tuple of (is_valid, new_hash)
            new_hash is None if rehashing is not needed

        Example:
            >>> valid, new_hash = await hasher.verify_and_update(password, old_hash)
            >>> if valid and new_hash:
            >>>     # Update stored hash
            >>>     await db.execute("UPDATE users SET password = ? WHERE id = ?", new_hash, user_id)
        """
        try:
            self._hasher.verify(hash, password)

            # Check if rehashing is needed (parameters changed)
            if self.check_needs_rehash(hash):
                new_hash = await self.hash(password)
                return True, new_hash

            return True, None

        except (VerifyMismatchError, InvalidHash):
            return False, None

    def check_needs_rehash(self, hash: str) -> bool:  # noqa: A002
        """Check if a hash needs to be rehashed.

        Args:
            hash: Existing password hash

        Returns:
            True if hash should be updated with new parameters
        """
        return self._hasher.check_needs_rehash(hash)


class PasswordValidator:
    """Password strength validator."""

    def __init__(
        self,
        min_length: int = 8,
        max_length: int = 128,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
        special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?",
    ):
        """Initialize password validator.

        Args:
            min_length: Minimum password length
            max_length: Maximum password length
            require_uppercase: Require at least one uppercase letter
            require_lowercase: Require at least one lowercase letter
            require_digit: Require at least one digit
            require_special: Require at least one special character
            special_chars: String of allowed special characters
        """
        self.min_length = min_length
        self.max_length = max_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
        self.special_chars = special_chars

    def validate(self, password: str) -> list[str]:
        """Validate password strength.

        Args:
            password: Password to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")

        if len(password) > self.max_length:
            errors.append(f"Password must be at most {self.max_length} characters long")

        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if self.require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if self.require_special and not any(c in self.special_chars for c in password):
            errors.append(
                f"Password must contain at least one special character ({self.special_chars})"
            )

        return errors

    def is_valid(self, password: str) -> bool:
        """Check if password is valid.

        Args:
            password: Password to check

        Returns:
            True if password meets all requirements
        """
        return len(self.validate(password)) == 0
