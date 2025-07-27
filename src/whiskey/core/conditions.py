"""Conditional registration support for Whiskey.

This module provides functionality for conditional component registration,
allowing components to be registered based on runtime conditions.
"""

from __future__ import annotations

import os
from typing import Callable

# Type alias for condition functions
Condition = Callable[[], bool]


def evaluate_condition(condition: Condition | bool | None) -> bool:
    """Evaluate a condition for component registration.

    Args:
        condition: A callable that returns bool, a bool value, or None

    Returns:
        True if the condition is met or None, False otherwise

    Examples:
        >>> evaluate_condition(lambda: os.getenv("DEBUG") == "true")
        False

        >>> evaluate_condition(True)
        True

        >>> evaluate_condition(None)  # No condition means always register
        True
    """
    if condition is None:
        return True

    if isinstance(condition, bool):
        return condition

    if callable(condition):
        try:
            return bool(condition())
        except Exception:
            # If condition evaluation fails, don't register
            return False

    # Unknown condition type, don't register
    return False


class ConditionalRegistry:
    """Registry that tracks conditions for components.

    This allows re-evaluation of conditions if needed, though
    by default conditions are evaluated at registration time.
    """

    def __init__(self):
        self._conditions: dict[tuple[type, str | None], Condition] = {}

    def set_condition(self, component_type: type, name: str | None, condition: Condition) -> None:
        """Store a condition for a component."""
        self._conditions[(component_type, name)] = condition

    def get_condition(self, component_type: type, name: str | None) -> Condition | None:
        """Get the condition for a component."""
        return self._conditions.get((component_type, name))

    def has_condition(self, component_type: type, name: str | None) -> bool:
        """Check if a component has a condition."""
        return (component_type, name) in self._conditions

    def evaluate(self, component_type: type, name: str | None) -> bool:
        """Evaluate the condition for a component."""
        condition = self.get_condition(component_type, name)
        return evaluate_condition(condition)

    def clear(self) -> None:
        """Clear all conditions."""
        self._conditions.clear()


# Common condition factories


def env_equals(var_name: str, expected_value: str) -> Condition:
    """Create a condition that checks if an environment variable equals a value.

    Args:
        var_name: Environment variable name
        expected_value: Expected value

    Returns:
        A condition function

    Example:
        >>> @provide(condition=env_equals("ENV", "development"))
        ... class DevService:
        ...     pass
    """
    return lambda: os.getenv(var_name) == expected_value


def env_exists(var_name: str) -> Condition:
    """Create a condition that checks if an environment variable exists.

    Args:
        var_name: Environment variable name

    Returns:
        A condition function

    Example:
        >>> @provide(condition=env_exists("DEBUG"))
        ... class DebugService:
        ...     pass
    """
    return lambda: os.getenv(var_name) is not None


def env_truthy(var_name: str) -> Condition:
    """Create a condition that checks if an environment variable is truthy.

    Args:
        var_name: Environment variable name

    Returns:
        A condition function that returns True for "true", "1", "yes", "on"

    Example:
        >>> @provide(condition=env_truthy("ENABLE_FEATURE"))
        ... class FeatureService:
        ...     pass
    """

    def check():
        value = os.getenv(var_name, "").lower()
        return value in ("true", "1", "yes", "on")

    return check


def all_conditions(*conditions: Condition) -> Condition:
    """Create a condition that requires all sub-conditions to be true.

    Args:
        *conditions: Variable number of conditions

    Returns:
        A condition function that ANDs all conditions

    Example:
        >>> @provide(condition=all_conditions(
        ...     env_exists("API_KEY"),
        ...     env_equals("ENV", "production")
        ... ))
        ... class ProductionAPIService:
        ...     pass
    """

    def check():
        return all(evaluate_condition(c) for c in conditions)

    return check


def any_conditions(*conditions: Condition) -> Condition:
    """Create a condition that requires any sub-condition to be true.

    Args:
        *conditions: Variable number of conditions

    Returns:
        A condition function that ORs all conditions

    Example:
        >>> @provide(condition=any_conditions(
        ...     env_equals("ENV", "development"),
        ...     env_exists("DEBUG")
        ... ))
        ... class DebugService:
        ...     pass
    """

    def check():
        return any(evaluate_condition(c) for c in conditions)

    return check


def not_condition(condition: Condition) -> Condition:
    """Create a condition that negates another condition.

    Args:
        condition: The condition to negate

    Returns:
        A condition function that returns the opposite

    Example:
        >>> @provide(condition=not_condition(env_equals("ENV", "production")))
        ... class NonProductionService:
        ...     pass
    """
    return lambda: not evaluate_condition(condition)
