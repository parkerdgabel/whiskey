"""SQL-based transform operations for ETL pipelines."""

from __future__ import annotations

from typing import Any, Callable

from whiskey_sql import SQL, Database

from .errors import TransformError


class SQLTransform:
    """Base class for SQL-based transformations.

    These transforms use SQL queries to enrich or validate records
    by joining with database tables or executing lookups.
    """

    def __init__(self, database: Database):
        """Initialize SQL transform.

        Args:
            database: Whiskey SQL Database instance
        """
        self.database = database

    async def transform(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Transform a single record.

        Args:
            record: Input record

        Returns:
            Transformed record or None to filter out
        """
        raise NotImplementedError("Subclasses must implement transform()")


class LookupTransform(SQLTransform):
    """Transform that enriches records with database lookups."""

    def __init__(
        self,
        database: Database,
        lookup_query: str | SQL,
        input_fields: list[str],
        output_fields: list[str] | None = None,
        on_missing: str = "keep",  # "keep", "drop", "error"
        cache_size: int = 1000,
    ):
        """Initialize lookup transform.

        Args:
            database: Database instance
            lookup_query: SQL query with parameters matching input_fields
            input_fields: Fields from record to use as lookup parameters
            output_fields: Fields to add from lookup result (None = all)
            on_missing: What to do when lookup returns no results
            cache_size: Number of lookups to cache (0 to disable)
        """
        super().__init__(database)
        self.lookup_query = SQL(lookup_query) if isinstance(lookup_query, str) else lookup_query
        self.input_fields = input_fields
        self.output_fields = output_fields
        self.on_missing = on_missing
        self.cache_size = cache_size
        self._cache: dict[tuple, dict[str, Any]] = {}

    async def transform(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Enrich record with database lookup.

        Args:
            record: Input record

        Returns:
            Enriched record or None if dropped
        """
        # Build lookup key from input fields
        try:
            params = {field: record.get(field) for field in self.input_fields}
            cache_key = tuple(params.values())
        except KeyError as e:
            raise TransformError(
                self.__class__.__name__,
                f"Missing required field for lookup: {e}",
                record=record,
            ) from e

        # Check cache
        if self.cache_size > 0 and cache_key in self._cache:
            lookup_result = self._cache[cache_key]
        else:
            # Execute lookup
            lookup_result = await self.database.fetch_one(self.lookup_query, params)

            # Cache result if enabled
            if self.cache_size > 0:
                self._cache[cache_key] = lookup_result
                # Simple LRU: remove oldest if cache is full
                if len(self._cache) > self.cache_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

        # Handle missing lookups
        if lookup_result is None:
            if self.on_missing == "drop":
                return None
            elif self.on_missing == "error":
                raise TransformError(
                    self.__class__.__name__,
                    "Lookup returned no results",
                    record=record,
                    details={"params": params},
                )
            # For "keep", continue with original record

        # Enrich record with lookup results
        enriched = record.copy()
        if lookup_result:
            if self.output_fields:
                # Only add specified fields
                for field in self.output_fields:
                    if field in lookup_result:
                        enriched[field] = lookup_result[field]
            else:
                # Add all fields from lookup
                enriched.update(lookup_result)

        return enriched


class JoinTransform(SQLTransform):
    """Transform that performs SQL joins with records."""

    def __init__(
        self,
        database: Database,
        join_table: str,
        join_keys: dict[str, str],  # {record_field: table_field}
        select_fields: list[str] | None = None,
        join_type: str = "LEFT",  # LEFT, INNER, RIGHT
        where: str | None = None,
    ):
        """Initialize join transform.

        Args:
            database: Database instance
            join_table: Table to join with
            join_keys: Mapping of record fields to table fields
            select_fields: Fields to select from join table
            join_type: Type of join (LEFT, INNER, RIGHT)
            where: Additional WHERE conditions
        """
        super().__init__(database)
        self.join_table = join_table
        self.join_keys = join_keys
        self.select_fields = select_fields
        self.join_type = join_type
        self.where = where

        # Build join query template
        self._build_query()

    def _build_query(self) -> None:
        """Build the join query template."""
        # Select clause
        if self.select_fields:
            select_clause = ", ".join(f"j.{field}" for field in self.select_fields)
        else:
            select_clause = "j.*"

        # Join conditions
        join_conditions = []
        for record_field, table_field in self.join_keys.items():
            join_conditions.append(f"j.{table_field} = :{record_field}")
        join_clause = " AND ".join(join_conditions)

        # Build query
        query = f"SELECT {select_clause} FROM {self.join_table} j WHERE {join_clause}"

        if self.where:
            query += f" AND ({self.where})"

        self.join_query = SQL(query)

    async def transform(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Join record with database table.

        Args:
            record: Input record

        Returns:
            Joined record or None for INNER join with no match
        """
        # Build join parameters
        params = {}
        for record_field in self.join_keys:
            if record_field not in record:
                raise TransformError(
                    self.__class__.__name__,
                    f"Missing join key field: {record_field}",
                    record=record,
                )
            params[record_field] = record[record_field]

        # Execute join
        join_result = await self.database.fetch_one(self.join_query, params)

        # Handle join results based on type
        if join_result is None and self.join_type == "INNER":
            # No match for INNER join - filter out record
            return None

        # Merge results
        result = record.copy()
        if join_result:
            # Prefix joined fields to avoid conflicts
            for key, value in join_result.items():
                result[f"{self.join_table}_{key}"] = value

        return result


class ValidateTransform(SQLTransform):
    """Transform that validates records against database constraints."""

    def __init__(
        self,
        database: Database,
        validation_query: str | SQL,
        validation_fields: list[str],
        on_invalid: str = "drop",  # "drop", "mark", "error"
        invalid_field: str = "_is_valid",
    ):
        """Initialize validation transform.

        Args:
            database: Database instance
            validation_query: Query that returns a result if record is valid
            validation_fields: Fields to use for validation
            on_invalid: What to do with invalid records
            invalid_field: Field to mark invalid records (for "mark" mode)
        """
        super().__init__(database)
        self.validation_query = (
            SQL(validation_query) if isinstance(validation_query, str) else validation_query
        )
        self.validation_fields = validation_fields
        self.on_invalid = on_invalid
        self.invalid_field = invalid_field

    async def transform(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Validate record against database.

        Args:
            record: Input record

        Returns:
            Record (possibly marked) or None if dropped
        """
        # Build validation parameters
        params = {field: record.get(field) for field in self.validation_fields}

        # Execute validation
        is_valid = await self.database.fetch_val(
            SQL("SELECT EXISTS(" + str(self.validation_query) + ")"), params
        )

        if not is_valid:
            if self.on_invalid == "drop":
                return None
            elif self.on_invalid == "error":
                raise TransformError(
                    self.__class__.__name__,
                    "Record failed validation",
                    record=record,
                    details={"params": params},
                )
            elif self.on_invalid == "mark":
                record = record.copy()
                record[self.invalid_field] = False
                return record

        # Valid record
        if self.on_invalid == "mark":
            record = record.copy()
            record[self.invalid_field] = True

        return record


class AggregateTransform(SQLTransform):
    """Transform that adds aggregated values from database."""

    def __init__(
        self,
        database: Database,
        aggregate_query: str | SQL,
        group_by_fields: list[str],
        aggregate_fields: list[str],
        cache_size: int = 100,
    ):
        """Initialize aggregate transform.

        Args:
            database: Database instance
            aggregate_query: Query that returns aggregated values
            group_by_fields: Fields to group by
            aggregate_fields: Names of aggregated fields to add
            cache_size: Number of aggregations to cache
        """
        super().__init__(database)
        self.aggregate_query = (
            SQL(aggregate_query) if isinstance(aggregate_query, str) else aggregate_query
        )
        self.group_by_fields = group_by_fields
        self.aggregate_fields = aggregate_fields
        self.cache_size = cache_size
        self._cache: dict[tuple, dict[str, Any]] = {}

    async def transform(self, record: dict[str, Any]) -> dict[str, Any]:
        """Add aggregated values to record.

        Args:
            record: Input record

        Returns:
            Record with aggregated values added
        """
        # Build group key
        params = {field: record.get(field) for field in self.group_by_fields}
        cache_key = tuple(params.values())

        # Check cache
        if self.cache_size > 0 and cache_key in self._cache:
            aggregates = self._cache[cache_key]
        else:
            # Execute aggregation
            result = await self.database.fetch_one(self.aggregate_query, params)
            aggregates = result if result else {}

            # Cache result
            if self.cache_size > 0:
                self._cache[cache_key] = aggregates
                if len(self._cache) > self.cache_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

        # Add aggregates to record
        enriched = record.copy()
        for field in self.aggregate_fields:
            if field in aggregates:
                enriched[f"agg_{field}"] = aggregates[field]

        return enriched


def create_sql_transform(
    transform_type: str,
    database: Database,
    **config,
) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Factory function to create SQL transforms.

    Args:
        transform_type: Type of transform (lookup, join, validate, aggregate)
        database: Database instance
        **config: Transform-specific configuration

    Returns:
        Async transform function
    """
    transform_classes = {
        "lookup": LookupTransform,
        "join": JoinTransform,
        "validate": ValidateTransform,
        "aggregate": AggregateTransform,
    }

    if transform_type not in transform_classes:
        raise ValueError(f"Unknown transform type: {transform_type}")

    transform_class = transform_classes[transform_type]
    transform = transform_class(database, **config)

    return transform.transform
