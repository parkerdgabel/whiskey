"""Transform utilities and registry for ETL pipelines."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, TypeVar, Union

from .errors import TransformError

T = TypeVar("T")
Transform = Callable[..., Union[T, None]]


class TransformRegistry:
    """Registry for transform functions."""

    def __init__(self):
        self._transforms: dict[str, Transform] = {}

    def register(self, name: str, transform: Transform) -> None:
        """Register a transform function."""
        self._transforms[name] = transform

    def get(self, name: str) -> Transform | None:
        """Get transform by name."""
        return self._transforms.get(name)

    def list_transforms(self) -> list[str]:
        """List all registered transforms."""
        return list(self._transforms.keys())


# Built-in transform utilities
async def filter_transform(
    record: Any,
    predicate: Callable[[Any], bool],
) -> Any | None:
    """Filter records based on predicate.

    Args:
        record: Input record
        predicate: Function that returns True to keep record

    Returns:
        Record if predicate is True, None otherwise
    """
    if asyncio.iscoroutinefunction(predicate):
        keep = await predicate(record)
    else:
        keep = predicate(record)

    return record if keep else None


async def map_transform(
    record: dict[str, Any],
    mapping: dict[str, str | Callable],
) -> dict[str, Any]:
    """Map fields using mapping dictionary.

    Args:
        record: Input record
        mapping: Field mapping (new_field: old_field or callable)

    Returns:
        Transformed record
    """
    result = {}

    for new_field, source in mapping.items():
        if callable(source):
            # Apply function
            if asyncio.iscoroutinefunction(source):
                value = await source(record)
            else:
                value = source(record)
        elif isinstance(source, str):
            # Simple field mapping
            value = record.get(source)
        else:
            value = source

        result[new_field] = value

    return result


async def select_fields(
    record: dict[str, Any],
    fields: list[str],
    keep_missing: bool = False,
) -> dict[str, Any]:
    """Select specific fields from record.

    Args:
        record: Input record
        fields: Fields to keep
        keep_missing: Include fields even if missing (as None)

    Returns:
        Record with only selected fields
    """
    if keep_missing:
        return {field: record.get(field) for field in fields}
    else:
        return {field: record[field] for field in fields if field in record}


async def rename_fields(
    record: dict[str, Any],
    mapping: dict[str, str],
    remove_original: bool = True,
) -> dict[str, Any]:
    """Rename fields in record.

    Args:
        record: Input record
        mapping: Field renaming (old_name: new_name)
        remove_original: Remove original field names

    Returns:
        Record with renamed fields
    """
    result = record.copy()

    for old_name, new_name in mapping.items():
        if old_name in result:
            result[new_name] = result[old_name]
            if remove_original and old_name != new_name:
                del result[old_name]

    return result


async def add_fields(
    record: dict[str, Any],
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Add new fields to record.

    Args:
        record: Input record
        fields: Fields to add

    Returns:
        Record with additional fields
    """
    result = record.copy()
    result.update(fields)
    return result


async def remove_fields(
    record: dict[str, Any],
    fields: list[str],
) -> dict[str, Any]:
    """Remove fields from record.

    Args:
        record: Input record
        fields: Fields to remove

    Returns:
        Record without specified fields
    """
    return {k: v for k, v in record.items() if k not in fields}


async def type_cast(
    record: dict[str, Any],
    types: dict[str, type],
    strict: bool = False,
) -> dict[str, Any]:
    """Cast field types.

    Args:
        record: Input record
        types: Field type mapping (field: type)
        strict: Raise error on cast failure

    Returns:
        Record with type-cast fields
    """
    result = record.copy()

    for field, target_type in types.items():
        if field in result:
            try:
                result[field] = target_type(result[field])
            except (ValueError, TypeError) as e:
                if strict:
                    raise TransformError(
                        "type_cast",
                        f"Failed to cast {field} to {target_type.__name__}: {e}",
                        record=record,
                    ) from e
                # Keep original value if not strict

    return result


async def flatten_nested(
    record: dict[str, Any],
    separator: str = "_",
    max_depth: int | None = None,
) -> dict[str, Any]:
    """Flatten nested dictionaries.

    Args:
        record: Input record with nested dicts
        separator: Separator for flattened keys
        max_depth: Maximum depth to flatten

    Returns:
        Flattened record
    """

    def flatten(obj: Any, prefix: str = "", depth: int = 0) -> dict[str, Any]:
        if max_depth is not None and depth >= max_depth:
            return {prefix: obj} if prefix else {}

        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                new_key = f"{prefix}{separator}{key}" if prefix else key
                result.update(flatten(value, new_key, depth + 1))
            return result
        else:
            return {prefix: obj} if prefix else {}

    return flatten(record)


async def validate_required(
    record: dict[str, Any],
    required_fields: list[str],
) -> dict[str, Any]:
    """Validate required fields exist.

    Args:
        record: Input record
        required_fields: Fields that must exist

    Returns:
        Record if valid

    Raises:
        TransformError: If required fields missing
    """
    missing = [field for field in required_fields if field not in record]

    if missing:
        raise TransformError(
            "validate_required",
            f"Missing required fields: {missing}",
            record=record,
        )

    return record


async def clean_strings(
    record: dict[str, Any],
    fields: list[str] | None = None,
    operations: list[str] = None,
) -> dict[str, Any]:
    """Clean string fields.

    Args:
        record: Input record
        fields: Fields to clean (None for all strings)
        operations: List of operations (strip, lower, upper, title)

    Returns:
        Record with cleaned strings
    """
    if operations is None:
        operations = ["strip", "lower"]
    result = record.copy()

    # Determine fields to process
    if fields is None:
        fields = [k for k, v in result.items() if isinstance(v, str)]

    # Apply operations
    for field in fields:
        if field in result and isinstance(result[field], str):
            value = result[field]
            for op in operations:
                if op == "strip":
                    value = value.strip()
                elif op == "lower":
                    value = value.lower()
                elif op == "upper":
                    value = value.upper()
                elif op == "title":
                    value = value.title()
            result[field] = value

    return result


# Composite transform builder
class TransformChain:
    """Chain multiple transforms together."""

    def __init__(self):
        self.transforms: list[Transform] = []

    def add(self, transform: Transform) -> TransformChain:
        """Add transform to chain."""
        self.transforms.append(transform)
        return self

    def filter(self, predicate: Callable[[Any], bool]) -> TransformChain:
        """Add filter transform."""
        self.transforms.append(functools.partial(filter_transform, predicate=predicate))
        return self

    def map(self, mapping: dict[str, str | Callable]) -> TransformChain:
        """Add map transform."""
        self.transforms.append(functools.partial(map_transform, mapping=mapping))
        return self

    def select(self, fields: list[str], **kwargs) -> TransformChain:
        """Add select fields transform."""
        self.transforms.append(functools.partial(select_fields, fields=fields, **kwargs))
        return self

    def rename(self, mapping: dict[str, str], **kwargs) -> TransformChain:
        """Add rename fields transform."""
        self.transforms.append(functools.partial(rename_fields, mapping=mapping, **kwargs))
        return self

    async def apply(self, record: Any) -> Any | None:
        """Apply all transforms in chain."""
        result = record

        for transform in self.transforms:
            if result is None:
                return None

            if asyncio.iscoroutinefunction(transform):
                result = await transform(result)
            else:
                result = transform(result)

        return result

    def __call__(self, record: Any) -> Any | None:
        """Make chain callable."""
        # Return coroutine for async compatibility
        return self.apply(record)
