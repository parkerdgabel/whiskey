"""Validation framework for ETL pipelines."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Union

from .errors import ValidationError
from .transforms import Transform


class ValidationMode(Enum):
    """Validation failure handling modes."""
    
    FAIL = "fail"  # Raise exception on first validation failure
    DROP = "drop"  # Drop invalid records silently
    MARK = "mark"  # Mark records as invalid but pass through
    COLLECT = "collect"  # Collect all errors before failing
    QUARANTINE = "quarantine"  # Send invalid records to quarantine


class Severity(Enum):
    """Validation error severity levels."""
    
    ERROR = "error"  # Validation failure
    WARNING = "warning"  # Validation concern but not failure
    INFO = "info"  # Informational validation note


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, field: str, message: str, value: Any = None) -> None:
        """Add validation error."""
        self.errors.append(ValidationError(
            field=field,
            message=message,
            value=value,
            severity=Severity.ERROR
        ))
        self.valid = False
    
    def add_warning(self, field: str, message: str, value: Any = None) -> None:
        """Add validation warning."""
        self.warnings.append(ValidationError(
            field=field,
            message=message,
            value=value,
            severity=Severity.WARNING
        ))
    
    def merge(self, other: ValidationResult) -> None:
        """Merge another validation result."""
        self.valid = self.valid and other.valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.metadata.update(other.metadata)


@dataclass
class ValidationError:
    """Individual validation error."""
    
    field: str
    message: str
    value: Any = None
    severity: Severity = Severity.ERROR
    rule: str | None = None
    
    def __str__(self) -> str:
        if self.value is not None:
            return f"{self.field}: {self.message} (value: {self.value})"
        return f"{self.field}: {self.message}"


class Validator(ABC):
    """Base validator interface."""
    
    def __init__(self, field: str | None = None, message: str | None = None):
        """Initialize validator.
        
        Args:
            field: Field to validate (None for record-level)
            message: Custom error message
        """
        self.field = field
        self.message = message
    
    @abstractmethod
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        """Validate a value.
        
        Args:
            value: Value to validate
            record: Full record (for cross-field validation)
            
        Returns:
            ValidationResult
        """
        pass
    
    def get_error_message(self, default: str) -> str:
        """Get error message."""
        return self.message or default


# Built-in validators

class RequiredValidator(Validator):
    """Validate field is present and not null."""
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(
                self.field or "value",
                self.get_error_message("Field is required"),
                value
            )
        
        return result


class TypeValidator(Validator):
    """Validate field type."""
    
    def __init__(self, expected_type: type | tuple[type, ...], **kwargs):
        super().__init__(**kwargs)
        self.expected_type = expected_type
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is not None and not isinstance(value, self.expected_type):
            type_name = (
                self.expected_type.__name__ 
                if hasattr(self.expected_type, '__name__')
                else str(self.expected_type)
            )
            result.add_error(
                self.field or "value",
                self.get_error_message(f"Expected type {type_name}, got {type(value).__name__}"),
                value
            )
        
        return result


class RangeValidator(Validator):
    """Validate numeric value is within range."""
    
    def __init__(
        self, 
        min_value: float | None = None,
        max_value: float | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None:
            return result
        
        try:
            num_value = float(value)
            
            if self.min_value is not None and num_value < self.min_value:
                result.add_error(
                    self.field or "value",
                    self.get_error_message(f"Value must be >= {self.min_value}"),
                    value
                )
            
            if self.max_value is not None and num_value > self.max_value:
                result.add_error(
                    self.field or "value",
                    self.get_error_message(f"Value must be <= {self.max_value}"),
                    value
                )
        
        except (ValueError, TypeError):
            result.add_error(
                self.field or "value",
                self.get_error_message("Value must be numeric"),
                value
            )
        
        return result


class LengthValidator(Validator):
    """Validate string/collection length."""
    
    def __init__(
        self,
        min_length: int | None = None,
        max_length: int | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None:
            return result
        
        try:
            length = len(value)
            
            if self.min_length is not None and length < self.min_length:
                result.add_error(
                    self.field or "value",
                    self.get_error_message(f"Length must be >= {self.min_length}"),
                    value
                )
            
            if self.max_length is not None and length > self.max_length:
                result.add_error(
                    self.field or "value",
                    self.get_error_message(f"Length must be <= {self.max_length}"),
                    value
                )
        
        except TypeError:
            result.add_error(
                self.field or "value",
                self.get_error_message("Value must have length"),
                value
            )
        
        return result


class PatternValidator(Validator):
    """Validate value matches regex pattern."""
    
    def __init__(self, pattern: str | Pattern, **kwargs):
        super().__init__(**kwargs)
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None:
            return result
        
        if not isinstance(value, str):
            result.add_error(
                self.field or "value",
                self.get_error_message("Value must be string for pattern matching"),
                value
            )
            return result
        
        if not self.pattern.match(value):
            result.add_error(
                self.field or "value",
                self.get_error_message(f"Value does not match pattern {self.pattern.pattern}"),
                value
            )
        
        return result


class ChoiceValidator(Validator):
    """Validate value is in allowed choices."""
    
    def __init__(self, choices: list[Any] | set[Any], **kwargs):
        super().__init__(**kwargs)
        self.choices = set(choices)
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is not None and value not in self.choices:
            result.add_error(
                self.field or "value",
                self.get_error_message(f"Value must be one of {sorted(self.choices)}"),
                value
            )
        
        return result


class EmailValidator(Validator):
    """Validate email address format."""
    
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None:
            return result
        
        if not isinstance(value, str):
            result.add_error(
                self.field or "value",
                self.get_error_message("Email must be string"),
                value
            )
            return result
        
        if not self.EMAIL_PATTERN.match(value):
            result.add_error(
                self.field or "value",
                self.get_error_message("Invalid email format"),
                value
            )
        
        return result


class DateValidator(Validator):
    """Validate date/datetime values."""
    
    def __init__(
        self,
        date_format: str | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.date_format = date_format
        self.min_date = min_date
        self.max_date = max_date
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None:
            return result
        
        # Parse date if string
        if isinstance(value, str):
            if self.date_format:
                try:
                    value = datetime.strptime(value, self.date_format)
                except ValueError:
                    result.add_error(
                        self.field or "value",
                        self.get_error_message(f"Invalid date format, expected {self.date_format}"),
                        value
                    )
                    return result
            else:
                # Try common formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        value = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    result.add_error(
                        self.field or "value",
                        self.get_error_message("Invalid date format"),
                        value
                    )
                    return result
        
        if not isinstance(value, datetime):
            result.add_error(
                self.field or "value",
                self.get_error_message("Value must be datetime"),
                value
            )
            return result
        
        # Check range
        if self.min_date and value < self.min_date:
            result.add_error(
                self.field or "value",
                self.get_error_message(f"Date must be >= {self.min_date}"),
                value
            )
        
        if self.max_date and value > self.max_date:
            result.add_error(
                self.field or "value",
                self.get_error_message(f"Date must be <= {self.max_date}"),
                value
            )
        
        return result


class UniqueValidator(Validator):
    """Validate field uniqueness across records."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen_values: set[Any] = set()
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        if value is None:
            return result
        
        if value in self.seen_values:
            result.add_error(
                self.field or "value",
                self.get_error_message(f"Duplicate value: {value}"),
                value
            )
        else:
            self.seen_values.add(value)
        
        return result


class CustomValidator(Validator):
    """Custom validation function wrapper."""
    
    def __init__(
        self,
        validate_func: Callable[[Any, dict[str, Any] | None], bool | ValidationResult],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.validate_func = validate_func
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        import asyncio
        
        if asyncio.iscoroutinefunction(self.validate_func):
            result = await self.validate_func(value, record)
        else:
            result = self.validate_func(value, record)
        
        if isinstance(result, bool):
            validation_result = ValidationResult(valid=result)
            if not result:
                validation_result.add_error(
                    self.field or "value",
                    self.get_error_message("Custom validation failed"),
                    value
                )
            return validation_result
        
        return result


class CompositeValidator(Validator):
    """Combine multiple validators."""
    
    def __init__(self, validators: list[Validator], require_all: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.validators = validators
        self.require_all = require_all
    
    async def validate(self, value: Any, record: dict[str, Any] | None = None) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        for validator in self.validators:
            sub_result = await validator.validate(value, record)
            
            if self.require_all:
                result.merge(sub_result)
            else:
                # ANY mode - pass if any validator passes
                if sub_result.valid:
                    return ValidationResult(valid=True)
                result.merge(sub_result)
        
        if not self.require_all and not result.valid:
            # None passed in ANY mode
            result.valid = False
        
        return result


class RecordValidator:
    """Validate entire records with multiple field validators."""
    
    def __init__(
        self,
        field_validators: dict[str, Validator | list[Validator]] | None = None,
        record_validators: list[Validator] | None = None,
        mode: ValidationMode = ValidationMode.FAIL,
        collect_stats: bool = False
    ):
        """Initialize record validator.
        
        Args:
            field_validators: Validators per field
            record_validators: Validators for entire record
            mode: How to handle validation failures
            collect_stats: Whether to collect validation statistics
        """
        self.field_validators = field_validators or {}
        self.record_validators = record_validators or []
        self.mode = mode
        self.collect_stats = collect_stats
        
        # Statistics
        self.stats = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "warnings": 0,
            "errors_by_field": defaultdict(int),
            "errors_by_type": defaultdict(int),
        }
    
    async def validate_record(self, record: dict[str, Any]) -> ValidationResult:
        """Validate a single record."""
        result = ValidationResult(valid=True)
        
        # Field-level validation
        for field, validators in self.field_validators.items():
            if not isinstance(validators, list):
                validators = [validators]
            
            value = record.get(field)
            
            for validator in validators:
                validator.field = validator.field or field
                field_result = await validator.validate(value, record)
                result.merge(field_result)
                
                # Update stats
                if self.collect_stats:
                    for error in field_result.errors:
                        self.stats["errors_by_field"][field] += 1
                        if error.rule:
                            self.stats["errors_by_type"][error.rule] += 1
        
        # Record-level validation
        for validator in self.record_validators:
            record_result = await validator.validate(record, record)
            result.merge(record_result)
        
        # Update stats
        if self.collect_stats:
            self.stats["total"] += 1
            if result.valid:
                self.stats["valid"] += 1
            else:
                self.stats["invalid"] += 1
            if result.warnings:
                self.stats["warnings"] += 1
        
        return result
    
    async def transform(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Transform function for pipeline integration."""
        result = await self.validate_record(record)
        
        if self.mode == ValidationMode.FAIL:
            if not result.valid:
                errors_str = "; ".join(str(e) for e in result.errors)
                raise ValidationError(
                    "RecordValidator",
                    f"Validation failed: {errors_str}",
                    record=record,
                    errors=result.errors
                )
            return record
        
        elif self.mode == ValidationMode.DROP:
            return record if result.valid else None
        
        elif self.mode == ValidationMode.MARK:
            record["_validation"] = {
                "valid": result.valid,
                "errors": [str(e) for e in result.errors],
                "warnings": [str(w) for w in result.warnings],
            }
            return record
        
        elif self.mode == ValidationMode.COLLECT:
            # Store errors but continue
            if not hasattr(self, "_collected_errors"):
                self._collected_errors = []
            if not result.valid:
                self._collected_errors.extend(result.errors)
            return record
        
        elif self.mode == ValidationMode.QUARANTINE:
            # Mark for quarantine
            if not result.valid:
                record["_quarantine"] = True
                record["_validation_errors"] = [str(e) for e in result.errors]
            return record
        
        return record
    
    def get_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self.stats = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "warnings": 0,
            "errors_by_field": defaultdict(int),
            "errors_by_type": defaultdict(int),
        }


# Validation builder for fluent API
class ValidationBuilder:
    """Builder for creating validation pipelines."""
    
    def __init__(self, mode: ValidationMode = ValidationMode.FAIL):
        self.field_validators: dict[str, list[Validator]] = defaultdict(list)
        self.record_validators: list[Validator] = []
        self.mode = mode
    
    def field(self, name: str) -> FieldValidationBuilder:
        """Start building validation for a field."""
        return FieldValidationBuilder(self, name)
    
    def record(self, validator: Validator) -> ValidationBuilder:
        """Add record-level validator."""
        self.record_validators.append(validator)
        return self
    
    def custom(self, func: Callable, message: str | None = None) -> ValidationBuilder:
        """Add custom record validator."""
        self.record_validators.append(CustomValidator(func, message=message))
        return self
    
    def build(self) -> RecordValidator:
        """Build the record validator."""
        return RecordValidator(
            field_validators=dict(self.field_validators),
            record_validators=self.record_validators,
            mode=self.mode
        )


class FieldValidationBuilder:
    """Builder for field-level validation."""
    
    def __init__(self, parent: ValidationBuilder, field: str):
        self.parent = parent
        self.field = field
    
    def required(self, message: str | None = None) -> FieldValidationBuilder:
        """Field is required."""
        self.parent.field_validators[self.field].append(
            RequiredValidator(field=self.field, message=message)
        )
        return self
    
    def type(self, expected_type: type, message: str | None = None) -> FieldValidationBuilder:
        """Field must be of type."""
        self.parent.field_validators[self.field].append(
            TypeValidator(expected_type, field=self.field, message=message)
        )
        return self
    
    def range(
        self,
        min_value: float | None = None,
        max_value: float | None = None,
        message: str | None = None
    ) -> FieldValidationBuilder:
        """Numeric range validation."""
        self.parent.field_validators[self.field].append(
            RangeValidator(min_value, max_value, field=self.field, message=message)
        )
        return self
    
    def length(
        self,
        min_length: int | None = None,
        max_length: int | None = None,
        message: str | None = None
    ) -> FieldValidationBuilder:
        """Length validation."""
        self.parent.field_validators[self.field].append(
            LengthValidator(min_length, max_length, field=self.field, message=message)
        )
        return self
    
    def pattern(self, pattern: str | Pattern, message: str | None = None) -> FieldValidationBuilder:
        """Pattern matching validation."""
        self.parent.field_validators[self.field].append(
            PatternValidator(pattern, field=self.field, message=message)
        )
        return self
    
    def choices(self, choices: list[Any], message: str | None = None) -> FieldValidationBuilder:
        """Choice validation."""
        self.parent.field_validators[self.field].append(
            ChoiceValidator(choices, field=self.field, message=message)
        )
        return self
    
    def email(self, message: str | None = None) -> FieldValidationBuilder:
        """Email validation."""
        self.parent.field_validators[self.field].append(
            EmailValidator(field=self.field, message=message)
        )
        return self
    
    def date(
        self,
        date_format: str | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
        message: str | None = None
    ) -> FieldValidationBuilder:
        """Date validation."""
        self.parent.field_validators[self.field].append(
            DateValidator(date_format, min_date, max_date, field=self.field, message=message)
        )
        return self
    
    def unique(self, message: str | None = None) -> FieldValidationBuilder:
        """Uniqueness validation."""
        self.parent.field_validators[self.field].append(
            UniqueValidator(field=self.field, message=message)
        )
        return self
    
    def custom(self, func: Callable, message: str | None = None) -> FieldValidationBuilder:
        """Custom validation."""
        self.parent.field_validators[self.field].append(
            CustomValidator(func, field=self.field, message=message)
        )
        return self
    
    def end_field(self) -> ValidationBuilder:
        """Return to parent builder."""
        return self.parent
    
    def build(self) -> RecordValidator:
        """Build the validator."""
        return self.parent.build()


# Helper functions for creating validation transforms

def create_validation_transform(
    validators: dict[str, Validator | list[Validator]] | None = None,
    record_validators: list[Validator] | None = None,
    mode: ValidationMode = ValidationMode.FAIL,
    collect_stats: bool = False
) -> Transform[dict[str, Any]]:
    """Create a validation transform function.
    
    Args:
        validators: Field validators
        record_validators: Record-level validators
        mode: Validation mode
        collect_stats: Whether to collect statistics
        
    Returns:
        Transform function
    """
    validator = RecordValidator(validators, record_validators, mode, collect_stats)
    return validator.transform


def validation_transform(mode: ValidationMode = ValidationMode.FAIL) -> ValidationBuilder:
    """Start building a validation transform.
    
    Example:
        transform = validation_transform(ValidationMode.DROP) \\
            .field("email").required().email() \\
            .field("age").type(int).range(0, 150) \\
            .field("status").choices(["active", "inactive"]) \\
            .build()
    """
    return ValidationBuilder(mode)