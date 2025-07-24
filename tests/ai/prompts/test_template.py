"""Tests for prompt templates."""

import pytest

from whiskey.ai.prompts import (
    LengthValidator,
    PromptTemplate,
    PromptVariable,
    TypeValidator,
    ValidationError,
)


@pytest.mark.unit
class TestPromptVariable:
    """Test prompt variable."""
    
    def test_basic_variable(self):
        """Test basic variable creation."""
        var = PromptVariable(
            name="username",
            description="User's name",
            required=True
        )
        
        assert var.name == "username"
        assert var.description == "User's name"
        assert var.required is True
        assert var.default is None
    
    def test_variable_with_validators(self):
        """Test variable with validators."""
        var = PromptVariable(
            name="age",
            validators=[
                TypeValidator(int),
                RangeValidator(min_value=0, max_value=150)
            ]
        )
        
        # Should pass
        var.validate(25)
        
        # Should fail - wrong type
        with pytest.raises(ValidationError):
            var.validate("twenty-five")
        
        # Should fail - out of range
        with pytest.raises(ValidationError):
            var.validate(200)


@pytest.mark.unit
class TestPromptTemplate:
    """Test prompt template."""
    
    def test_basic_template(self):
        """Test basic template rendering."""
        template = PromptTemplate(
            template="Hello, {name}! Welcome to {place}.",
            variables=[
                PromptVariable(name="name", required=True),
                PromptVariable(name="place", required=True)
            ]
        )
        
        result = template.render(name="Alice", place="Wonderland")
        assert result == "Hello, Alice! Welcome to Wonderland."
    
    def test_template_with_defaults(self):
        """Test template with default values."""
        template = PromptTemplate(
            template="Hello, {name}! You are {role}.",
            variables=[
                PromptVariable(name="name", required=True),
                PromptVariable(name="role", default="a user", required=False)
            ]
        )
        
        # With all values
        result = template.render(name="Bob", role="an admin")
        assert result == "Hello, Bob! You are an admin."
        
        # Using default
        result = template.render(name="Bob")
        assert result == "Hello, Bob! You are a user."
    
    def test_missing_required_variable(self):
        """Test error on missing required variable."""
        template = PromptTemplate(
            template="Hello, {name}!",
            variables=[
                PromptVariable(name="name", required=True)
            ]
        )
        
        with pytest.raises(ValueError) as exc:
            template.render()
        assert "Required variable 'name' not provided" in str(exc.value)
    
    def test_validation(self):
        """Test variable validation."""
        template = PromptTemplate(
            template="User {username} (age: {age})",
            variables=[
                PromptVariable(
                    name="username",
                    validators=[
                        TypeValidator(str),
                        LengthValidator(min_length=3, max_length=20)
                    ]
                ),
                PromptVariable(
                    name="age",
                    validators=[TypeValidator(int)]
                )
            ]
        )
        
        # Should pass
        result = template.render(username="alice", age=25)
        assert "User alice (age: 25)" in result
        
        # Should fail - username too short
        with pytest.raises(ValidationError):
            template.render(username="ab", age=25)
        
        # Should fail - age wrong type
        with pytest.raises(ValidationError):
            template.render(username="alice", age="twenty-five")
    
    def test_partial_template(self):
        """Test partial template creation."""
        template = PromptTemplate(
            template="System: {system_prompt}\nUser: {user_input}",
            variables=[
                PromptVariable(name="system_prompt", required=True),
                PromptVariable(name="user_input", required=True)
            ]
        )
        
        # Create partial with system prompt filled
        partial = template.partial(system_prompt="You are a helpful assistant.")
        
        # Partial should only need user_input
        assert len(partial.get_required_variables()) == 1
        assert "user_input" in partial.get_required_variables()
        
        # Render partial
        result = partial.render(user_input="What is 2+2?")
        assert result == "System: You are a helpful assistant.\nUser: What is 2+2?"
    
    def test_strict_mode(self):
        """Test strict mode validation."""
        # Should fail - template has undefined variable
        with pytest.raises(ValueError) as exc:
            PromptTemplate(
                template="Hello, {name}! Your ID is {id}.",
                variables=[
                    PromptVariable(name="name")
                ],
                strict=True
            )
        assert "undefined variables: id" in str(exc.value)
        
        # Should pass in non-strict mode
        template = PromptTemplate(
            template="Hello, {name}! Your ID is {id}.",
            variables=[
                PromptVariable(name="name")
            ],
            strict=False
        )
        assert template is not None
    
    def test_extract_variables(self):
        """Test variable extraction from template."""
        template = PromptTemplate(
            template="Hello {name}, your balance is ${amount}.",
            strict=False
        )
        
        vars = template._extract_variables()
        assert vars == {"name", "amount"}
    
    def test_format_variables_info(self):
        """Test formatting variable information."""
        template = PromptTemplate(
            template="{greeting} {name}!",
            variables=[
                PromptVariable(
                    name="greeting",
                    description="The greeting to use",
                    default="Hello",
                    required=False
                ),
                PromptVariable(
                    name="name",
                    description="Person's name",
                    required=True
                )
            ]
        )
        
        info = template.format_variables_info()
        assert "greeting [optional] (default: Hello) - The greeting to use" in info
        assert "name [required] - Person's name" in info


from whiskey.ai.prompts.validators import RangeValidator  # Import here to avoid circular