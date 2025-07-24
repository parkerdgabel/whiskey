"""Validators for prompt template variables."""

import re
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Pattern, Type, Union


class ValidationError(Exception):
    """Raised when validation fails."""
    
    def __init__(self, message: str, variable_name: str, value: Any):
        super().__init__(message)
        self.variable_name = variable_name
        self.value = value


class Validator(ABC):
    """Base class for validators."""
    
    @abstractmethod
    def validate(self, value: Any, variable_name: str) -> None:
        """Validate a value.
        
        Args:
            value: The value to validate
            variable_name: Name of the variable being validated
            
        Raises:
            ValidationError: If validation fails
        """
        pass


class TypeValidator(Validator):
    """Validates that a value is of a specific type."""
    
    def __init__(self, expected_types: Union[Type, List[Type]]):
        """Initialize type validator.
        
        Args:
            expected_types: Single type or list of allowed types
        """
        if isinstance(expected_types, type):
            self.expected_types = [expected_types]
        else:
            self.expected_types = expected_types
    
    def validate(self, value: Any, variable_name: str) -> None:
        """Validate type."""
        if not any(isinstance(value, t) for t in self.expected_types):
            type_names = ", ".join(t.__name__ for t in self.expected_types)
            raise ValidationError(
                f"Variable '{variable_name}' must be of type {type_names}, "
                f"got {type(value).__name__}",
                variable_name,
                value
            )


class LengthValidator(Validator):
    """Validates string length."""
    
    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ):
        """Initialize length validator.
        
        Args:
            min_length: Minimum allowed length
            max_length: Maximum allowed length
        """
        self.min_length = min_length
        self.max_length = max_length
    
    def validate(self, value: Any, variable_name: str) -> None:
        """Validate length."""
        if not isinstance(value, str):
            raise ValidationError(
                f"Variable '{variable_name}' must be a string for length validation",
                variable_name,
                value
            )
        
        length = len(value)
        
        if self.min_length is not None and length < self.min_length:
            raise ValidationError(
                f"Variable '{variable_name}' must be at least {self.min_length} "
                f"characters long, got {length}",
                variable_name,
                value
            )
        
        if self.max_length is not None and length > self.max_length:
            raise ValidationError(
                f"Variable '{variable_name}' must be at most {self.max_length} "
                f"characters long, got {length}",
                variable_name,
                value
            )


class PatternValidator(Validator):
    """Validates against a regex pattern."""
    
    def __init__(self, pattern: Union[str, Pattern], error_message: Optional[str] = None):
        """Initialize pattern validator.
        
        Args:
            pattern: Regex pattern to match
            error_message: Custom error message
        """
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern)
        else:
            self.pattern = pattern
        self.error_message = error_message
    
    def validate(self, value: Any, variable_name: str) -> None:
        """Validate pattern."""
        if not isinstance(value, str):
            raise ValidationError(
                f"Variable '{variable_name}' must be a string for pattern validation",
                variable_name,
                value
            )
        
        if not self.pattern.match(value):
            message = self.error_message or (
                f"Variable '{variable_name}' does not match required pattern"
            )
            raise ValidationError(message, variable_name, value)


class RangeValidator(Validator):
    """Validates numeric values are within a range."""
    
    def __init__(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ):
        """Initialize range validator.
        
        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
        """
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any, variable_name: str) -> None:
        """Validate range."""
        if not isinstance(value, (int, float)):
            raise ValidationError(
                f"Variable '{variable_name}' must be numeric for range validation",
                variable_name,
                value
            )
        
        if self.min_value is not None and value < self.min_value:
            raise ValidationError(
                f"Variable '{variable_name}' must be at least {self.min_value}, "
                f"got {value}",
                variable_name,
                value
            )
        
        if self.max_value is not None and value > self.max_value:
            raise ValidationError(
                f"Variable '{variable_name}' must be at most {self.max_value}, "
                f"got {value}",
                variable_name,
                value
            )