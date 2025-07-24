"""Tests for prompt validators."""

import pytest

from whiskey.ai.prompts.validators import (
    LengthValidator,
    PatternValidator,
    RangeValidator,
    TypeValidator,
    ValidationError,
)


@pytest.mark.unit
class TestTypeValidator:
    """Test type validator."""
    
    def test_single_type_validation(self):
        """Test validation with single type."""
        validator = TypeValidator(str)
        
        # Should pass
        validator.validate("hello", "test_var")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate(123, "test_var")
        assert "must be of type str" in str(exc.value)
        assert exc.value.variable_name == "test_var"
        assert exc.value.value == 123
    
    def test_multiple_types_validation(self):
        """Test validation with multiple types."""
        validator = TypeValidator([str, int])
        
        # Should pass
        validator.validate("hello", "test_var")
        validator.validate(123, "test_var")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate(3.14, "test_var")
        assert "must be of type str, int" in str(exc.value)


@pytest.mark.unit
class TestLengthValidator:
    """Test length validator."""
    
    def test_min_length_validation(self):
        """Test minimum length validation."""
        validator = LengthValidator(min_length=5)
        
        # Should pass
        validator.validate("hello", "test_var")
        validator.validate("hello world", "test_var")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate("hi", "test_var")
        assert "at least 5 characters" in str(exc.value)
    
    def test_max_length_validation(self):
        """Test maximum length validation."""
        validator = LengthValidator(max_length=10)
        
        # Should pass
        validator.validate("hello", "test_var")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate("hello world!", "test_var")
        assert "at most 10 characters" in str(exc.value)
    
    def test_min_max_length_validation(self):
        """Test min and max length validation."""
        validator = LengthValidator(min_length=3, max_length=10)
        
        # Should pass
        validator.validate("hello", "test_var")
        
        # Should fail - too short
        with pytest.raises(ValidationError):
            validator.validate("hi", "test_var")
        
        # Should fail - too long
        with pytest.raises(ValidationError):
            validator.validate("hello world!", "test_var")
    
    def test_non_string_validation(self):
        """Test validation with non-string value."""
        validator = LengthValidator(min_length=5)
        
        with pytest.raises(ValidationError) as exc:
            validator.validate(123, "test_var")
        assert "must be a string" in str(exc.value)


@pytest.mark.unit
class TestPatternValidator:
    """Test pattern validator."""
    
    def test_pattern_validation(self):
        """Test regex pattern validation."""
        # Email pattern
        validator = PatternValidator(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        
        # Should pass
        validator.validate("user@example.com", "email")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate("not-an-email", "email")
        assert "does not match required pattern" in str(exc.value)
    
    def test_custom_error_message(self):
        """Test custom error message."""
        validator = PatternValidator(
            r"^\d{3}-\d{3}-\d{4}$",
            error_message="Phone number must be in format XXX-XXX-XXXX"
        )
        
        with pytest.raises(ValidationError) as exc:
            validator.validate("1234567890", "phone")
        assert "Phone number must be in format" in str(exc.value)
    
    def test_compiled_pattern(self):
        """Test with pre-compiled pattern."""
        import re
        pattern = re.compile(r"^[A-Z]{2,}$")
        validator = PatternValidator(pattern)
        
        # Should pass
        validator.validate("ABC", "code")
        
        # Should fail
        with pytest.raises(ValidationError):
            validator.validate("abc", "code")


@pytest.mark.unit
class TestRangeValidator:
    """Test range validator."""
    
    def test_min_value_validation(self):
        """Test minimum value validation."""
        validator = RangeValidator(min_value=0)
        
        # Should pass
        validator.validate(0, "test_var")
        validator.validate(10, "test_var")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate(-5, "test_var")
        assert "must be at least 0" in str(exc.value)
    
    def test_max_value_validation(self):
        """Test maximum value validation."""
        validator = RangeValidator(max_value=100)
        
        # Should pass
        validator.validate(50, "test_var")
        validator.validate(100, "test_var")
        
        # Should fail
        with pytest.raises(ValidationError) as exc:
            validator.validate(150, "test_var")
        assert "must be at most 100" in str(exc.value)
    
    def test_float_validation(self):
        """Test validation with float values."""
        validator = RangeValidator(min_value=0.0, max_value=1.0)
        
        # Should pass
        validator.validate(0.5, "probability")
        
        # Should fail
        with pytest.raises(ValidationError):
            validator.validate(1.5, "probability")
    
    def test_non_numeric_validation(self):
        """Test validation with non-numeric value."""
        validator = RangeValidator(min_value=0)
        
        with pytest.raises(ValidationError) as exc:
            validator.validate("abc", "test_var")
        assert "must be numeric" in str(exc.value)