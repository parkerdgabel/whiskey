"""Prompt template implementation."""

import re
from dataclasses import dataclass, field
from string import Template
from typing import Any, Dict, List, Optional, Set

from whiskey.core.decorators import provide

from .validators import ValidationError, Validator


@dataclass
class PromptVariable:
    """Definition of a prompt template variable."""
    
    name: str
    description: str = ""
    default: Any = None
    required: bool = True
    validators: List[Validator] = field(default_factory=list)
    
    def validate(self, value: Any) -> None:
        """Validate a value against all validators.
        
        Args:
            value: The value to validate
            
        Raises:
            ValidationError: If validation fails
        """
        for validator in self.validators:
            validator.validate(value, self.name)


@provide
class PromptTemplate:
    """A template for generating prompts with variable substitution."""
    
    def __init__(
        self,
        template: str,
        variables: Optional[List[PromptVariable]] = None,
        strict: bool = True
    ):
        """Initialize prompt template.
        
        Args:
            template: Template string with {variable} placeholders
            variables: List of variable definitions
            strict: If True, all variables must be defined
        """
        self.template = template
        self.variables = variables or []
        self.strict = strict
        
        # Create variable lookup
        self._variable_map = {var.name: var for var in self.variables}
        
        # Extract variables from template
        self._template_vars = self._extract_variables()
        
        # Validate template if strict mode
        if self.strict:
            self._validate_template()
    
    def _extract_variables(self) -> Set[str]:
        """Extract variable names from template."""
        # Match {variable_name} pattern
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, self.template)
        return set(matches)
    
    def _validate_template(self) -> None:
        """Validate template consistency."""
        defined_vars = set(self._variable_map.keys())
        
        # Check for undefined variables in template
        undefined = self._template_vars - defined_vars
        if undefined:
            raise ValueError(
                f"Template contains undefined variables: {', '.join(undefined)}"
            )
        
        # Check for required variables not in template
        for var in self.variables:
            if var.required and var.name not in self._template_vars:
                raise ValueError(
                    f"Required variable '{var.name}' not used in template"
                )
    
    def render(self, **kwargs: Any) -> str:
        """Render the template with provided variables.
        
        Args:
            **kwargs: Variable values
            
        Returns:
            Rendered prompt string
            
        Raises:
            ValidationError: If validation fails
            ValueError: If required variables are missing
        """
        # Build final variable set
        values = {}
        
        # Apply defaults
        for var in self.variables:
            if var.default is not None:
                values[var.name] = var.default
        
        # Apply provided values
        values.update(kwargs)
        
        # Check required variables
        for var in self.variables:
            if var.required and var.name not in values:
                raise ValueError(f"Required variable '{var.name}' not provided")
        
        # Validate all values
        for name, value in values.items():
            if name in self._variable_map:
                self._variable_map[name].validate(value)
        
        # Render template using string format
        try:
            return self.template.format(**values)
        except KeyError as e:
            raise ValueError(f"Template variable {e} not provided")
    
    def partial(self, **kwargs: Any) -> "PromptTemplate":
        """Create a new template with some variables pre-filled.
        
        Args:
            **kwargs: Variable values to pre-fill
            
        Returns:
            New PromptTemplate with partial values applied
        """
        # Render with partial values
        partial_template = self.template
        for name, value in kwargs.items():
            if name in self._variable_map:
                self._variable_map[name].validate(value)
                # Replace this variable in template
                partial_template = partial_template.replace(
                    f"{{{name}}}",
                    str(value)
                )
        
        # Create new variable list without pre-filled ones
        remaining_vars = [
            var for var in self.variables 
            if var.name not in kwargs
        ]
        
        return PromptTemplate(
            template=partial_template,
            variables=remaining_vars,
            strict=self.strict
        )
    
    def get_variables(self) -> List[PromptVariable]:
        """Get list of template variables."""
        return self.variables.copy()
    
    def get_required_variables(self) -> List[str]:
        """Get list of required variable names."""
        return [var.name for var in self.variables if var.required]
    
    def format_variables_info(self) -> str:
        """Format information about template variables."""
        if not self.variables:
            return "No variables defined"
        
        lines = ["Template Variables:"]
        for var in self.variables:
            status = "required" if var.required else "optional"
            default = f" (default: {var.default})" if var.default is not None else ""
            desc = f" - {var.description}" if var.description else ""
            lines.append(f"  - {var.name} [{status}]{default}{desc}")
        
        return "\n".join(lines)