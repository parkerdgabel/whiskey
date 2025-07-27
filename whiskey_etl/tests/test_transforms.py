"""Tests for transform utilities."""

import pytest

from whiskey_etl.transforms import (
    TransformRegistry,
    filter_transform,
    map_transform,
    select_fields,
    rename_fields,
    add_fields,
    remove_fields,
    type_cast,
    flatten_nested,
    validate_required,
    clean_strings,
    TransformChain,
)
from whiskey_etl.errors import TransformError


@pytest.mark.asyncio
async def test_transform_registry():
    """Test transform registry functionality."""
    registry = TransformRegistry()
    
    # Register transform
    async def test_transform(record):
        return record
    
    registry.register("test", test_transform)
    
    # Get transform
    assert registry.get("test") is test_transform
    assert registry.get("nonexistent") is None
    
    # List transforms
    registry.register("another", lambda x: x)
    transforms = registry.list_transforms()
    assert "test" in transforms
    assert "another" in transforms


@pytest.mark.asyncio
async def test_filter_transform():
    """Test filter transform."""
    # Keep records with value > 10
    record1 = {"value": 15}
    record2 = {"value": 5}
    
    result1 = await filter_transform(record1, lambda r: r["value"] > 10)
    result2 = await filter_transform(record2, lambda r: r["value"] > 10)
    
    assert result1 == record1
    assert result2 is None
    
    # Test with async predicate
    async def async_predicate(record):
        return record["value"] > 10
    
    result = await filter_transform(record1, async_predicate)
    assert result == record1


@pytest.mark.asyncio
async def test_map_transform():
    """Test map transform."""
    record = {"first_name": "John", "last_name": "Doe", "age": 30}
    
    # Simple field mapping
    mapping = {
        "name": lambda r: f"{r['first_name']} {r['last_name']}",
        "age_group": lambda r: "adult" if r["age"] >= 18 else "minor",
        "original_age": "age",  # Direct field reference
    }
    
    result = await map_transform(record, mapping)
    
    assert result["name"] == "John Doe"
    assert result["age_group"] == "adult"
    assert result["original_age"] == 30


@pytest.mark.asyncio
async def test_select_fields():
    """Test select fields transform."""
    record = {"id": 1, "name": "Alice", "age": 30, "city": "NYC"}
    
    # Select specific fields
    result = await select_fields(record, ["id", "name"])
    assert result == {"id": 1, "name": "Alice"}
    
    # With missing fields
    result = await select_fields(record, ["id", "country"], keep_missing=True)
    assert result == {"id": 1, "country": None}
    
    # Without keep_missing
    result = await select_fields(record, ["id", "country"], keep_missing=False)
    assert result == {"id": 1}


@pytest.mark.asyncio
async def test_rename_fields():
    """Test rename fields transform."""
    record = {"id": 1, "name": "Alice", "age": 30}
    
    # Rename fields
    mapping = {"id": "user_id", "name": "full_name"}
    result = await rename_fields(record, mapping)
    
    assert "user_id" in result
    assert "full_name" in result
    assert "id" not in result
    assert "name" not in result
    assert result["age"] == 30
    
    # Keep original fields
    result = await rename_fields(record, mapping, remove_original=False)
    assert "id" in result
    assert "user_id" in result


@pytest.mark.asyncio
async def test_add_fields():
    """Test add fields transform."""
    record = {"id": 1, "name": "Alice"}
    
    new_fields = {"status": "active", "created": "2024-01-01"}
    result = await add_fields(record, new_fields)
    
    assert result["id"] == 1
    assert result["name"] == "Alice"
    assert result["status"] == "active"
    assert result["created"] == "2024-01-01"


@pytest.mark.asyncio
async def test_remove_fields():
    """Test remove fields transform."""
    record = {"id": 1, "name": "Alice", "password": "secret", "token": "xyz"}
    
    result = await remove_fields(record, ["password", "token"])
    
    assert result == {"id": 1, "name": "Alice"}
    assert "password" not in result
    assert "token" not in result


@pytest.mark.asyncio
async def test_type_cast():
    """Test type cast transform."""
    record = {"id": "1", "age": "30", "score": "95.5", "active": "true"}
    
    types = {
        "id": int,
        "age": int,
        "score": float,
        "active": lambda x: x.lower() == "true",
    }
    
    result = await type_cast(record, types)
    
    assert result["id"] == 1
    assert result["age"] == 30
    assert result["score"] == 95.5
    assert result["active"] is True
    
    # Test strict mode with invalid cast
    bad_record = {"id": "abc"}
    with pytest.raises(TransformError):
        await type_cast(bad_record, {"id": int}, strict=True)
    
    # Non-strict mode keeps original
    result = await type_cast(bad_record, {"id": int}, strict=False)
    assert result["id"] == "abc"


@pytest.mark.asyncio
async def test_flatten_nested():
    """Test flatten nested dictionaries."""
    record = {
        "id": 1,
        "user": {
            "name": "Alice",
            "contact": {
                "email": "alice@example.com",
                "phone": "123-456-7890"
            }
        }
    }
    
    result = await flatten_nested(record)
    
    assert result["id"] == 1
    assert result["user_name"] == "Alice"
    assert result["user_contact_email"] == "alice@example.com"
    assert result["user_contact_phone"] == "123-456-7890"
    
    # Test with max depth
    result = await flatten_nested(record, max_depth=1)
    assert result["id"] == 1
    assert result["user_name"] == "Alice"
    assert isinstance(result["user_contact"], dict)


@pytest.mark.asyncio
async def test_validate_required():
    """Test validate required fields."""
    record = {"id": 1, "name": "Alice"}
    
    # Valid record
    result = await validate_required(record, ["id", "name"])
    assert result == record
    
    # Missing required field
    with pytest.raises(TransformError) as exc_info:
        await validate_required(record, ["id", "name", "email"])
    
    assert "Missing required fields" in str(exc_info.value)
    assert "email" in str(exc_info.value)


@pytest.mark.asyncio
async def test_clean_strings():
    """Test clean strings transform."""
    record = {
        "name": "  Alice  ",
        "email": " ALICE@EXAMPLE.COM ",
        "city": "new york",
        "age": 30,
    }
    
    # Default cleaning (strip + lower)
    result = await clean_strings(record)
    
    assert result["name"] == "alice"
    assert result["email"] == "alice@example.com"
    assert result["city"] == "new york"
    assert result["age"] == 30  # Non-string unchanged
    
    # Custom operations
    result = await clean_strings(
        record,
        fields=["city"],
        operations=["strip", "title"]
    )
    assert result["city"] == "New York"


@pytest.mark.asyncio
async def test_transform_chain():
    """Test transform chain."""
    chain = TransformChain()
    
    # Build chain
    chain.select(["id", "name", "email", "age"]) \
         .rename({"id": "user_id"}) \
         .filter(lambda r: r["age"] >= 18) \
         .map({
             "user_id": "user_id",
             "name": "name",
             "email": lambda r: r["email"].lower(),
             "is_adult": lambda r: True
         })
    
    # Test with valid record
    record = {
        "id": 1,
        "name": "Alice",
        "email": "ALICE@EXAMPLE.COM",
        "age": 25,
        "extra": "ignored"
    }
    
    result = await chain.apply(record)
    
    assert result["user_id"] == 1
    assert result["name"] == "Alice"
    assert result["email"] == "alice@example.com"
    assert result["is_adult"] is True
    assert "extra" not in result
    
    # Test with filtered record
    young_record = {**record, "age": 16}
    result = await chain.apply(young_record)
    assert result is None