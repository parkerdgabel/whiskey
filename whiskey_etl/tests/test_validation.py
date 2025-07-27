"""Tests for validation framework."""

import re
from datetime import datetime, timedelta

import pytest

from whiskey_etl.validation import (
    ChoiceValidator,
    CompositeValidator,
    CustomValidator,
    DateValidator,
    EmailValidator,
    LengthValidator,
    PatternValidator,
    RangeValidator,
    RecordValidator,
    RequiredValidator,
    TypeValidator,
    UniqueValidator,
    ValidationBuilder,
    ValidationMode,
    ValidationResult,
    create_validation_transform,
    validation_transform,
)


class TestIndividualValidators:
    """Test individual validator implementations."""

    async def test_required_validator(self):
        """Test required field validation."""
        validator = RequiredValidator(field="name")
        
        # Valid cases
        result = await validator.validate("John")
        assert result.valid
        assert len(result.errors) == 0
        
        # Invalid cases
        result = await validator.validate(None)
        assert not result.valid
        assert len(result.errors) == 1
        assert "required" in result.errors[0].message.lower()
        
        result = await validator.validate("")
        assert not result.valid
        
        result = await validator.validate("   ")
        assert not result.valid

    async def test_type_validator(self):
        """Test type validation."""
        validator = TypeValidator(int, field="age")
        
        # Valid
        result = await validator.validate(25)
        assert result.valid
        
        result = await validator.validate(None)
        assert result.valid  # None is allowed
        
        # Invalid
        result = await validator.validate("25")
        assert not result.valid
        assert "int" in result.errors[0].message
        
        # Multiple types
        validator = TypeValidator((int, float), field="number")
        result = await validator.validate(25)
        assert result.valid
        result = await validator.validate(25.5)
        assert result.valid
        result = await validator.validate("25")
        assert not result.valid

    async def test_range_validator(self):
        """Test numeric range validation."""
        validator = RangeValidator(min_value=0, max_value=100, field="score")
        
        # Valid
        result = await validator.validate(50)
        assert result.valid
        
        result = await validator.validate(0)
        assert result.valid
        
        result = await validator.validate(100)
        assert result.valid
        
        # Invalid
        result = await validator.validate(-1)
        assert not result.valid
        assert ">= 0" in result.errors[0].message
        
        result = await validator.validate(101)
        assert not result.valid
        assert "<= 100" in result.errors[0].message
        
        # Non-numeric
        result = await validator.validate("fifty")
        assert not result.valid
        assert "numeric" in result.errors[0].message

    async def test_length_validator(self):
        """Test length validation."""
        validator = LengthValidator(min_length=3, max_length=10, field="username")
        
        # Valid
        result = await validator.validate("john")
        assert result.valid
        
        result = await validator.validate("abc")
        assert result.valid
        
        result = await validator.validate("1234567890")
        assert result.valid
        
        # Invalid
        result = await validator.validate("ab")
        assert not result.valid
        assert ">= 3" in result.errors[0].message
        
        result = await validator.validate("12345678901")
        assert not result.valid
        assert "<= 10" in result.errors[0].message
        
        # Lists
        result = await validator.validate([1, 2, 3, 4])
        assert result.valid
        
        result = await validator.validate([1, 2])
        assert not result.valid

    async def test_pattern_validator(self):
        """Test regex pattern validation."""
        validator = PatternValidator(r"^\d{3}-\d{3}-\d{4}$", field="phone")
        
        # Valid
        result = await validator.validate("123-456-7890")
        assert result.valid
        
        # Invalid
        result = await validator.validate("1234567890")
        assert not result.valid
        
        result = await validator.validate("123-45-6789")
        assert not result.valid
        
        # Compiled pattern
        validator = PatternValidator(re.compile(r"^[A-Z]{2}\d{4}$"), field="code")
        result = await validator.validate("AB1234")
        assert result.valid
        result = await validator.validate("ab1234")
        assert not result.valid

    async def test_choice_validator(self):
        """Test choice validation."""
        validator = ChoiceValidator(["active", "inactive", "pending"], field="status")
        
        # Valid
        result = await validator.validate("active")
        assert result.valid
        
        result = await validator.validate("inactive")
        assert result.valid
        
        # Invalid
        result = await validator.validate("deleted")
        assert not result.valid
        assert "one of" in result.errors[0].message
        
        # None is allowed
        result = await validator.validate(None)
        assert result.valid

    async def test_email_validator(self):
        """Test email validation."""
        validator = EmailValidator(field="email")
        
        # Valid
        valid_emails = [
            "user@example.com",
            "john.doe@company.co.uk",
            "test123@subdomain.example.com",
            "user+tag@example.com",
        ]
        
        for email in valid_emails:
            result = await validator.validate(email)
            assert result.valid, f"Email {email} should be valid"
        
        # Invalid
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
            "user @example.com",
            "user@exam ple.com",
        ]
        
        for email in invalid_emails:
            result = await validator.validate(email)
            assert not result.valid, f"Email {email} should be invalid"

    async def test_date_validator(self):
        """Test date validation."""
        # Basic date validation
        validator = DateValidator(field="birth_date")
        
        # Valid datetime
        result = await validator.validate(datetime.now())
        assert result.valid
        
        # Valid string formats
        result = await validator.validate("2024-01-15")
        assert result.valid
        
        result = await validator.validate("2024-01-15 10:30:00")
        assert result.valid
        
        # Invalid format
        result = await validator.validate("15/01/2024")
        assert not result.valid
        
        # With specific format
        validator = DateValidator(date_format="%d/%m/%Y", field="date")
        result = await validator.validate("15/01/2024")
        assert result.valid
        
        result = await validator.validate("2024-01-15")
        assert not result.valid
        
        # With date range
        min_date = datetime(2020, 1, 1)
        max_date = datetime(2025, 12, 31)
        validator = DateValidator(min_date=min_date, max_date=max_date, field="date")
        
        result = await validator.validate("2023-06-15")
        assert result.valid
        
        result = await validator.validate("2019-12-31")
        assert not result.valid
        
        result = await validator.validate("2026-01-01")
        assert not result.valid

    async def test_unique_validator(self):
        """Test uniqueness validation."""
        validator = UniqueValidator(field="id")
        
        # First occurrence is valid
        result = await validator.validate("user123")
        assert result.valid
        
        result = await validator.validate("user456")
        assert result.valid
        
        # Duplicate is invalid
        result = await validator.validate("user123")
        assert not result.valid
        assert "Duplicate" in result.errors[0].message

    async def test_custom_validator(self):
        """Test custom validation function."""
        # Simple boolean function
        def is_even(value, record):
            return value % 2 == 0
        
        validator = CustomValidator(is_even, field="number")
        
        result = await validator.validate(4)
        assert result.valid
        
        result = await validator.validate(3)
        assert not result.valid
        
        # Function returning ValidationResult
        def complex_validation(value, record):
            result = ValidationResult(valid=True)
            if value and len(value) < 5:
                result.add_error("password", "Password too short")
            if value and not any(c.isdigit() for c in value):
                result.add_warning("password", "Password should contain numbers")
            return result
        
        validator = CustomValidator(complex_validation, field="password")
        
        result = await validator.validate("abc")
        assert not result.valid
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        
        result = await validator.validate("abcdef123")
        assert result.valid
        assert len(result.warnings) == 0

    async def test_composite_validator(self):
        """Test combining multiple validators."""
        # ALL mode (default)
        validator = CompositeValidator([
            RequiredValidator(),
            TypeValidator(str),
            LengthValidator(min_length=3, max_length=10),
        ], field="username")
        
        result = await validator.validate("john")
        assert result.valid
        
        result = await validator.validate(None)
        assert not result.valid  # Fails required
        
        result = await validator.validate(123)
        assert not result.valid  # Fails type
        
        result = await validator.validate("ab")
        assert not result.valid  # Fails length
        
        # ANY mode
        validator = CompositeValidator([
            TypeValidator(int),
            PatternValidator(r"^\d+$"),  # String of digits
        ], require_all=False, field="id")
        
        result = await validator.validate(123)
        assert result.valid  # Passes first validator
        
        result = await validator.validate("456")
        assert result.valid  # Passes second validator
        
        result = await validator.validate("abc")
        assert not result.valid  # Fails both


class TestRecordValidator:
    """Test record-level validation."""

    async def test_field_validation(self):
        """Test validating multiple fields in a record."""
        validator = RecordValidator(
            field_validators={
                "name": RequiredValidator(),
                "age": [TypeValidator(int), RangeValidator(0, 150)],
                "email": EmailValidator(),
            }
        )
        
        # Valid record
        record = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
        result = await validator.validate_record(record)
        assert result.valid
        
        # Invalid record - missing required field
        record = {
            "age": 30,
            "email": "john@example.com"
        }
        result = await validator.validate_record(record)
        assert not result.valid
        assert any(e.field == "name" for e in result.errors)
        
        # Invalid record - wrong type
        record = {
            "name": "John",
            "age": "thirty",
            "email": "john@example.com"
        }
        result = await validator.validate_record(record)
        assert not result.valid
        assert any(e.field == "age" for e in result.errors)

    async def test_validation_modes(self):
        """Test different validation modes."""
        validator = RecordValidator(
            field_validators={"age": RangeValidator(0, 100)},
            mode=ValidationMode.DROP
        )
        
        # Valid record passes through
        result = await validator.transform({"age": 50})
        assert result == {"age": 50}
        
        # Invalid record is dropped
        result = await validator.transform({"age": 150})
        assert result is None
        
        # MARK mode
        validator.mode = ValidationMode.MARK
        result = await validator.transform({"age": 150})
        assert result is not None
        assert "_validation" in result
        assert not result["_validation"]["valid"]
        
        # QUARANTINE mode
        validator.mode = ValidationMode.QUARANTINE
        result = await validator.transform({"age": 150})
        assert result is not None
        assert "_quarantine" in result
        assert result["_quarantine"] is True

    async def test_validation_stats(self):
        """Test validation statistics collection."""
        validator = RecordValidator(
            field_validators={
                "email": EmailValidator(),
                "age": RangeValidator(0, 100),
            },
            collect_stats=True
        )
        
        records = [
            {"email": "valid@example.com", "age": 30},
            {"email": "invalid-email", "age": 50},
            {"email": "test@example.com", "age": 150},
            {"email": "another@example.com", "age": 40},
        ]
        
        for record in records:
            await validator.validate_record(record)
        
        stats = validator.get_stats()
        assert stats["total"] == 4
        assert stats["valid"] == 2
        assert stats["invalid"] == 2
        assert stats["errors_by_field"]["email"] == 1
        assert stats["errors_by_field"]["age"] == 1


class TestValidationBuilder:
    """Test fluent validation builder API."""

    async def test_builder_basic(self):
        """Test basic builder usage."""
        validator = (
            validation_transform(ValidationMode.FAIL)
            .field("name").required().end_field()
            .field("age").type(int).range(0, 150).end_field()
            .field("email").email().end_field()
            .build()
        )
        
        # Valid record
        record = {
            "name": "John",
            "age": 30,
            "email": "john@example.com"
        }
        result = await validator.validate_record(record)
        assert result.valid
        
        # Invalid record
        record = {
            "name": "",
            "age": 200,
            "email": "not-an-email"
        }
        result = await validator.validate_record(record)
        assert not result.valid
        assert len(result.errors) == 3

    async def test_builder_complex(self):
        """Test complex validation scenarios."""
        validator = (
            validation_transform()
            .field("username")
                .required()
                .type(str)
                .length(3, 20)
                .pattern(r"^[a-zA-Z0-9_]+$")
                .end_field()
            .field("password")
                .required()
                .length(min_length=8)
                .custom(lambda v, r: any(c.isupper() for c in v), "Must contain uppercase")
                .end_field()
            .field("email")
                .required()
                .email()
                .unique()
                .end_field()
            .field("age")
                .type(int)
                .range(13, 120)
                .end_field()
            .field("country")
                .choices(["US", "UK", "CA", "AU"])
                .end_field()
            .field("terms_accepted")
                .required()
                .type(bool)
                .custom(lambda v, r: v is True, "Must accept terms")
                .end_field()
            .build()
        )
        
        # First valid record
        record1 = {
            "username": "john_doe123",
            "password": "SecurePass123",
            "email": "john@example.com",
            "age": 25,
            "country": "US",
            "terms_accepted": True
        }
        result = await validator.validate_record(record1)
        assert result.valid
        
        # Second record with duplicate email
        record2 = {
            "username": "jane_doe",
            "password": "AnotherPass123",
            "email": "john@example.com",  # Duplicate
            "age": 30,
            "country": "UK",
            "terms_accepted": True
        }
        result = await validator.validate_record(record2)
        assert not result.valid
        assert any("Duplicate" in str(e) for e in result.errors)

    async def test_transform_function(self):
        """Test using validation as a transform."""
        transform = create_validation_transform(
            validators={
                "price": [RequiredValidator(), RangeValidator(0, None)],
                "quantity": [RequiredValidator(), TypeValidator(int), RangeValidator(1, None)],
            },
            mode=ValidationMode.DROP
        )
        
        # Valid record
        result = await transform({"price": 10.99, "quantity": 5})
        assert result == {"price": 10.99, "quantity": 5}
        
        # Invalid record (negative price)
        result = await transform({"price": -5, "quantity": 1})
        assert result is None
        
        # Invalid record (zero quantity)
        result = await transform({"price": 10, "quantity": 0})
        assert result is None


class TestValidationIntegration:
    """Test validation integration with pipelines."""

    async def test_pipeline_validation(self):
        """Test validation in pipeline context."""
        from whiskey_etl.transforms import filter_transform
        
        # Create validation transform
        validator = (
            validation_transform(ValidationMode.MARK)
            .field("user_id").required().type(str).end_field()
            .field("email").required().email().end_field()
            .field("age").type(int).range(13, None).end_field()
            .build()
        )
        
        # Sample records
        records = [
            {"user_id": "123", "email": "valid@example.com", "age": 25},
            {"user_id": "456", "email": "invalid-email", "age": 30},
            {"user_id": None, "email": "test@example.com", "age": 20},
            {"user_id": "789", "email": "another@example.com", "age": 10},
        ]
        
        # Process records
        validated_records = []
        for record in records:
            result = await validator.transform(record)
            if result:
                validated_records.append(result)
        
        assert len(validated_records) == 4  # All records pass (MARK mode)
        
        # Filter valid records
        valid_records = []
        for record in validated_records:
            result = await filter_transform(
                record,
                lambda r: r.get("_validation", {}).get("valid", True)
            )
            if result:
                valid_records.append(result)
        
        assert len(valid_records) == 1  # Only first record is valid

    async def test_cross_field_validation(self):
        """Test validation across multiple fields."""
        def validate_date_range(record, _):
            start = record.get("start_date")
            end = record.get("end_date")
            
            if start and end:
                # Assume they're already datetime objects or parseable strings
                if isinstance(start, str):
                    start = datetime.fromisoformat(start)
                if isinstance(end, str):
                    end = datetime.fromisoformat(end)
                
                if start > end:
                    result = ValidationResult(valid=False)
                    result.add_error("date_range", "Start date must be before end date")
                    return result
            
            return ValidationResult(valid=True)
        
        validator = RecordValidator(
            field_validators={
                "start_date": DateValidator(),
                "end_date": DateValidator(),
            },
            record_validators=[CustomValidator(validate_date_range)]
        )
        
        # Valid range
        record = {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
        result = await validator.validate_record(record)
        assert result.valid
        
        # Invalid range
        record = {
            "start_date": "2024-12-31",
            "end_date": "2024-01-01"
        }
        result = await validator.validate_record(record)
        assert not result.valid
        assert any("before end date" in str(e) for e in result.errors)