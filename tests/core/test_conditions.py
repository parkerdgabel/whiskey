"""Tests for conditional registration functionality."""

import os
from unittest.mock import patch

from whiskey.core.conditions import (
    ConditionalRegistry,
    all_conditions,
    any_conditions,
    env_equals,
    env_exists,
    env_truthy,
    evaluate_condition,
    not_condition,
)


class TestEvaluateCondition:
    """Test the evaluate_condition function."""

    def test_evaluate_none_condition(self):
        """Test that None condition returns True."""
        assert evaluate_condition(None) is True

    def test_evaluate_bool_condition(self):
        """Test evaluating boolean conditions."""
        assert evaluate_condition(True) is True
        assert evaluate_condition(False) is False

    def test_evaluate_callable_condition(self):
        """Test evaluating callable conditions."""
        assert evaluate_condition(lambda: True) is True
        assert evaluate_condition(lambda: False) is False

    def test_evaluate_callable_with_exception(self):
        """Test that exceptions in conditions return False."""

        def failing_condition():
            raise ValueError("Test error")

        assert evaluate_condition(failing_condition) is False

    def test_evaluate_invalid_condition(self):
        """Test that invalid condition types return False."""
        assert evaluate_condition("not a valid condition") is False
        assert evaluate_condition(123) is False


class TestEnvironmentConditions:
    """Test environment-based condition functions."""

    def test_env_equals(self):
        """Test env_equals condition."""
        with patch.dict(os.environ, {"TEST_VAR": "expected"}):
            condition = env_equals("TEST_VAR", "expected")
            assert condition() is True

            condition = env_equals("TEST_VAR", "different")
            assert condition() is False

        # Missing variable
        condition = env_equals("MISSING_VAR", "value")
        assert condition() is False

    def test_env_exists(self):
        """Test env_exists condition."""
        with patch.dict(os.environ, {"PRESENT_VAR": "any_value"}):
            condition = env_exists("PRESENT_VAR")
            assert condition() is True

        condition = env_exists("MISSING_VAR")
        assert condition() is False

    def test_env_truthy(self):
        """Test env_truthy condition."""
        # Truthy values
        truthy_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES", "on", "On", "ON"]
        for value in truthy_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                condition = env_truthy("TEST_VAR")
                assert condition() is True, f"Failed for value: {value}"

        # Falsy values
        falsy_values = ["false", "False", "0", "no", "off", "", "anything_else"]
        for value in falsy_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                condition = env_truthy("TEST_VAR")
                assert condition() is False, f"Failed for value: {value}"

        # Missing variable
        condition = env_truthy("MISSING_VAR")
        assert condition() is False


class TestCombinationConditions:
    """Test condition combination functions."""

    def test_all_conditions(self):
        """Test all_conditions combinator."""
        # All true
        condition = all_conditions(lambda: True, lambda: True, lambda: True)
        assert condition() is True

        # One false
        condition = all_conditions(lambda: True, lambda: False, lambda: True)
        assert condition() is False

        # All false
        condition = all_conditions(lambda: False, lambda: False, lambda: False)
        assert condition() is False

        # Empty
        condition = all_conditions()
        assert condition() is True  # Empty all() returns True

    def test_any_conditions(self):
        """Test any_conditions combinator."""
        # All true
        condition = any_conditions(lambda: True, lambda: True, lambda: True)
        assert condition() is True

        # One true
        condition = any_conditions(lambda: False, lambda: True, lambda: False)
        assert condition() is True

        # All false
        condition = any_conditions(lambda: False, lambda: False, lambda: False)
        assert condition() is False

        # Empty
        condition = any_conditions()
        assert condition() is False  # Empty any() returns False

    def test_not_condition(self):
        """Test not_condition inverter."""
        condition = not_condition(lambda: True)
        assert condition() is False

        condition = not_condition(lambda: False)
        assert condition() is True

        # With exception
        def failing():
            raise ValueError("Test")

        condition = not_condition(failing)
        assert condition() is True  # Failure is treated as False, so not False is True


class TestConditionalRegistry:
    """Test the ConditionalRegistry class."""

    def test_registry_creation(self):
        """Test creating a ConditionalRegistry."""
        registry = ConditionalRegistry()
        assert registry is not None
        assert hasattr(registry, "_conditions")

    def test_set_and_get_condition(self):
        """Test setting and getting conditions."""
        registry = ConditionalRegistry()

        class TestService:
            pass

        # Set condition
        def condition():
            return True
        registry.set_condition(TestService, None, condition)

        # Get condition
        retrieved = registry.get_condition(TestService, None)
        assert retrieved is condition

        # Get non-existent condition
        assert registry.get_condition(str, None) is None

    def test_has_condition(self):
        """Test checking if condition exists."""
        registry = ConditionalRegistry()

        class TestService:
            pass

        # Initially no condition
        assert not registry.has_condition(TestService, None)

        # Set condition
        registry.set_condition(TestService, None, lambda: True)
        assert registry.has_condition(TestService, None)

        # With name
        registry.set_condition(TestService, "named", lambda: False)
        assert registry.has_condition(TestService, "named")
        assert not registry.has_condition(TestService, "other")

    def test_evaluate_condition(self):
        """Test evaluating conditions."""
        registry = ConditionalRegistry()

        class TestService:
            pass

        # No condition (should evaluate to True)
        assert registry.evaluate(TestService, None) is True

        # True condition
        registry.set_condition(TestService, None, lambda: True)
        assert registry.evaluate(TestService, None) is True

        # False condition
        registry.set_condition(TestService, "disabled", lambda: False)
        assert registry.evaluate(TestService, "disabled") is False

    def test_clear_conditions(self):
        """Test clearing all conditions."""
        registry = ConditionalRegistry()

        class TestService1:
            pass

        class TestService2:
            pass

        # Set multiple conditions
        registry.set_condition(TestService1, None, lambda: True)
        registry.set_condition(TestService2, None, lambda: False)
        registry.set_condition(TestService1, "named", lambda: True)

        assert registry.has_condition(TestService1, None)
        assert registry.has_condition(TestService2, None)
        assert registry.has_condition(TestService1, "named")

        # Clear all
        registry.clear()

        assert not registry.has_condition(TestService1, None)
        assert not registry.has_condition(TestService2, None)
        assert not registry.has_condition(TestService1, "named")
