"""Configuration schema utilities using dataclasses."""

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


class ConfigurationError(Exception):
    """Configuration-related error."""

    pass


def is_dataclass_instance(obj: Any) -> bool:
    """Check if object is a dataclass instance."""
    return dataclasses.is_dataclass(obj) and not isinstance(obj, type)


def is_dataclass_type(obj: Any) -> bool:
    """Check if object is a dataclass type."""
    return dataclasses.is_dataclass(obj)


def convert_value(value: Any, target_type: type[T], path: str = "") -> T:
    """Convert a value to the target type.

    Args:
        value: Value to convert
        target_type: Target type to convert to
        path: Configuration path for error messages

    Returns:
        Converted value

    Raises:
        ConfigurationError: If conversion fails
    """
    # Handle None
    if value is None:
        return None

    # Already correct type (skip for generic types)
    if not hasattr(target_type, "__origin__") and isinstance(value, target_type):
        return value

    # Get origin type for generics
    origin = get_origin(target_type)

    # Handle Optional types
    if origin is Union:
        args = get_args(target_type)
        # Check if it's Optional (Union[X, None])
        if type(None) in args:
            other_types = [t for t in args if t is not type(None)]
            if len(other_types) == 1:
                return convert_value(value, other_types[0], path)

    # Handle dataclass types
    if is_dataclass_type(target_type):
        if isinstance(value, dict):
            return create_dataclass_from_dict(target_type, value, path)
        else:
            raise ConfigurationError(
                f"Cannot convert {type(value).__name__} to dataclass {target_type.__name__} at {path}"
            )

    # Handle basic type conversions
    try:
        if target_type is bool:
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1", "on")
            return bool(value)

        elif target_type is int:
            return int(value)

        elif target_type is float:
            return float(value)

        elif target_type is str:
            return str(value)

        # Handle list/List types
        elif origin in (list, type(Sequence)) or (
            hasattr(target_type, "__origin__") and target_type.__origin__ is list
        ):
            if isinstance(value, str):
                # Handle comma-separated strings
                value = [v.strip() for v in value.split(",")]

            if not isinstance(value, (list, tuple)):
                value = [value]

            # Get item type if available
            args = get_args(target_type)
            if args:
                item_type = args[0]
                return [
                    convert_value(item, item_type, f"{path}[{i}]") for i, item in enumerate(value)
                ]
            return list(value)

        # Handle dict/Dict types
        elif origin in (dict, type(Mapping)) or (
            hasattr(target_type, "__origin__") and target_type.__origin__ is dict
        ):
            if not isinstance(value, dict):
                raise ConfigurationError(f"Cannot convert {type(value).__name__} to dict at {path}")

            # Get key/value types if available
            args = get_args(target_type)
            if args and len(args) == 2:
                key_type, value_type = args
                return {
                    convert_value(k, key_type, f"{path}.{k}"): convert_value(
                        v, value_type, f"{path}.{k}"
                    )
                    for k, v in value.items()
                }
            return dict(value)

        # Try direct conversion
        return target_type(value)

    except (ValueError, TypeError) as e:
        raise ConfigurationError(
            f"Cannot convert {value!r} to {target_type.__name__} at {path}: {e}"
        ) from e


def create_dataclass_from_dict(dataclass_type: type[T], data: dict[str, Any], path: str = "") -> T:
    """Create a dataclass instance from a dictionary.

    Args:
        dataclass_type: Dataclass type to create
        data: Dictionary containing data
        path: Configuration path for error messages

    Returns:
        Dataclass instance

    Raises:
        ConfigurationError: If creation fails
    """
    if not is_dataclass_type(dataclass_type):
        raise ConfigurationError(f"{dataclass_type} is not a dataclass")

    # Get field types
    type_hints = get_type_hints(dataclass_type)
    fields = dataclasses.fields(dataclass_type)

    # Build kwargs for dataclass
    kwargs = {}

    for field in fields:
        field_path = f"{path}.{field.name}" if path else field.name

        if field.name in data:
            # Field is present in data
            value = data[field.name]
            field_type = type_hints.get(field.name, field.type)
            kwargs[field.name] = convert_value(value, field_type, field_path)
        elif field.default is not dataclasses.MISSING:
            # Use default value
            kwargs[field.name] = field.default
        elif field.default_factory is not dataclasses.MISSING:
            # Use default factory
            kwargs[field.name] = field.default_factory()
        else:
            # Required field is missing
            raise ConfigurationError(f"Required field '{field.name}' is missing at {path}")

    # Create instance
    try:
        return dataclass_type(**kwargs)
    except Exception as e:
        raise ConfigurationError(
            f"Failed to create {dataclass_type.__name__} at {path}: {e}"
        ) from e


def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two configuration dictionaries.

    Args:
        base: Base configuration
        override: Override configuration

    Returns:
        Merged configuration
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge dictionaries
            result[key] = merge_configs(result[key], value)
        else:
            # Override value
            result[key] = value

    return result


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass instance to a dictionary.

    Args:
        obj: Dataclass instance

    Returns:
        Dictionary representation
    """
    if not is_dataclass_instance(obj):
        return obj

    result = {}
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        if is_dataclass_instance(value):
            result[field.name] = dataclass_to_dict(value)
        elif isinstance(value, list):
            result[field.name] = [dataclass_to_dict(item) for item in value]
        elif isinstance(value, dict):
            result[field.name] = {k: dataclass_to_dict(v) for k, v in value.items()}
        else:
            result[field.name] = value

    return result


def get_value_at_path(config: Union[dict[str, Any], Any], path: str) -> Any:
    """Get a value from a configuration object using a dotted path.

    Args:
        config: Configuration object (dict or dataclass)
        path: Dotted path (e.g., "database.host")

    Returns:
        Value at path

    Raises:
        ConfigurationError: If path is invalid
    """
    if not path:
        return config

    parts = path.split(".")
    current = config

    for i, part in enumerate(parts):
        current_path = ".".join(parts[: i + 1])

        if is_dataclass_instance(current):
            # Handle dataclass
            if not hasattr(current, part):
                raise ConfigurationError(f"No attribute '{part}' at path '{current_path}'")
            current = getattr(current, part)
        elif isinstance(current, dict):
            # Handle dictionary
            if part not in current:
                raise ConfigurationError(f"No key '{part}' at path '{current_path}'")
            current = current[part]
        else:
            raise ConfigurationError(
                f"Cannot navigate into {type(current).__name__} at path '{current_path}'"
            )

    return current
