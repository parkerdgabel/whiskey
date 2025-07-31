"""Tests for object store ETL components."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Check for optional dependencies
try:
    import aioboto3  # noqa: F401

    HAS_AIOBOTO3 = True
except ImportError:
    HAS_AIOBOTO3 = False

from whiskey_etl import (
    ObjectStoreSink,
    ObjectStoreSource,
    S3Sink,
    S3Source,
    csv_processor,
    json_processor,
    jsonl_processor,
)
from whiskey_etl.errors import SourceError


class TestObjectStoreSource:
    """Test object store source base functionality."""

    async def test_list_objects_filter(self):
        """Test object listing with filters."""

        class TestSource(ObjectStoreSource):
            async def list_objects(self, bucket, prefix="", **kwargs):
                # Mock objects
                objects = [
                    {
                        "key": "data/2024/01/file1.json",
                        "size": 1000,
                        "last_modified": datetime(2024, 1, 1),
                    },
                    {
                        "key": "data/2024/01/file2.csv",
                        "size": 2000,
                        "last_modified": datetime(2024, 1, 2),
                    },
                    {
                        "key": "data/2024/02/file3.json",
                        "size": 3000,
                        "last_modified": datetime(2024, 2, 1),
                    },
                ]
                for obj in objects:
                    if obj["key"].startswith(prefix):
                        yield obj

            async def get_object(self, bucket, key):
                return b'{"test": "data"}'

            async def get_object_stream(self, bucket, key, chunk_size=8192):
                yield b'{"test": "data"}'

        # Test with suffix filter
        source = TestSource(suffix=".json")
        records = []
        async for record in source.extract("test-bucket"):
            records.append(record)

        assert len(records) == 2
        assert all(r["key"].endswith(".json") for r in records)

        # Test with modified_after filter
        source = TestSource(modified_after=datetime(2024, 1, 15))
        records = []
        async for record in source.extract("test-bucket"):
            records.append(record)

        assert len(records) == 1
        assert records[0]["key"] == "data/2024/02/file3.json"

    async def test_extract_with_processor(self):
        """Test extraction with custom processor."""

        class TestSource(ObjectStoreSource):
            async def list_objects(self, bucket, prefix="", **kwargs):
                yield {"key": "test.json", "size": 100}

            async def get_object(self, bucket, key):
                return b'[{"id": 1}, {"id": 2}]'

            async def get_object_stream(self, bucket, key, chunk_size=8192):
                yield b'[{"id": 1}, {"id": 2}]'

        source = TestSource()
        records = []
        async for record in source.extract("test-bucket", processor=json_processor):
            records.append(record)

        assert len(records) == 2
        assert records[0]["id"] == 1
        assert records[1]["id"] == 2

    async def test_max_keys_limit(self):
        """Test max_keys limitation."""

        class TestSource(ObjectStoreSource):
            async def list_objects(self, bucket, prefix="", **kwargs):
                for i in range(10):
                    yield {"key": f"file{i}.json", "size": 100}

            async def get_object(self, bucket, key):
                return b"{}"

            async def get_object_stream(self, bucket, key, chunk_size=8192):
                yield b"{}"

        source = TestSource(max_keys=3)
        records = []
        async for record in source.extract("test-bucket"):
            records.append(record)

        assert len(records) == 3


class TestS3Source:
    """Test S3 source implementation."""

    @pytest.mark.skipif(not HAS_AIOBOTO3, reason="aioboto3 not installed")
    @patch("aioboto3.Session")
    async def test_s3_source_list_objects(self, mock_session_class):
        """Test S3 object listing."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock paginator
        mock_paginator = AsyncMock()
        mock_client.__aenter__.return_value.get_paginator.return_value = mock_paginator

        # Mock pages
        async def mock_pages():
            yield {
                "Contents": [
                    {
                        "Key": "data/file1.json",
                        "Size": 1000,
                        "LastModified": datetime(2024, 1, 1),
                        "ETag": '"abc123"',
                        "StorageClass": "STANDARD",
                    }
                ]
            }

        mock_paginator.paginate.return_value = mock_pages()

        # Test listing
        source = S3Source()
        objects = []
        async for obj in source.list_objects("test-bucket"):
            objects.append(obj)

        assert len(objects) == 1
        assert objects[0]["key"] == "data/file1.json"
        assert objects[0]["size"] == 1000

    @pytest.mark.skipif(not HAS_AIOBOTO3, reason="aioboto3 not installed")
    @patch("aioboto3.Session")
    async def test_s3_source_get_object(self, mock_session_class):
        """Test S3 object retrieval."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock response
        mock_response = {"Body": AsyncMock()}
        mock_response["Body"].read.return_value = b'{"test": "data"}'
        mock_client.__aenter__.return_value.get_object.return_value = mock_response

        # Test get object
        source = S3Source()
        content = await source.get_object("test-bucket", "test.json")

        assert content == b'{"test": "data"}'


class TestObjectStoreSink:
    """Test object store sink base functionality."""

    async def test_partition_records(self):
        """Test record partitioning."""

        class TestSink(ObjectStoreSink):
            async def put_object(self, bucket, key, content, metadata=None):
                pass

            async def put_object_stream(self, bucket, key, content_generator, metadata=None):
                pass

        sink = TestSink(partition_by=["country", "year"])

        records = [
            {"id": 1, "country": "US", "year": 2024},
            {"id": 2, "country": "US", "year": 2024},
            {"id": 3, "country": "UK", "year": 2024},
            {"id": 4, "country": "US", "year": 2023},
        ]

        partitions = sink._partition_records(records)

        assert len(partitions) == 3
        assert "country=US/year=2024" in partitions
        assert len(partitions["country=US/year=2024"]) == 2

    async def test_serialize_json(self):
        """Test JSON serialization."""

        class TestSink(ObjectStoreSink):
            async def put_object(self, bucket, key, content, metadata=None):
                pass

            async def put_object_stream(self, bucket, key, content_generator, metadata=None):
                pass

        sink = TestSink(format="json")
        records = [{"id": 1, "name": "test"}]

        content = await sink._serialize_records(records)
        data = json.loads(content.decode("utf-8"))

        assert isinstance(data, list)
        assert data[0]["id"] == 1

    async def test_serialize_jsonl(self):
        """Test JSONL serialization."""

        class TestSink(ObjectStoreSink):
            async def put_object(self, bucket, key, content, metadata=None):
                pass

            async def put_object_stream(self, bucket, key, content_generator, metadata=None):
                pass

        sink = TestSink(format="jsonl")
        records = [{"id": 1}, {"id": 2}]

        content = await sink._serialize_records(records)
        lines = content.decode("utf-8").strip().split("\n")

        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == 1
        assert json.loads(lines[1])["id"] == 2

    async def test_serialize_csv(self):
        """Test CSV serialization."""

        class TestSink(ObjectStoreSink):
            async def put_object(self, bucket, key, content, metadata=None):
                pass

            async def put_object_stream(self, bucket, key, content_generator, metadata=None):
                pass

        sink = TestSink(format="csv")
        records = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

        content = await sink._serialize_records(records)
        text = content.decode("utf-8")
        # Handle different line endings
        lines = [line.strip() for line in text.strip().split("\n")]

        assert lines[0] == "id,name"  # Header
        assert lines[1] == "1,Alice"
        assert lines[2] == "2,Bob"

    async def test_compression(self):
        """Test content compression."""

        class TestSink(ObjectStoreSink):
            async def put_object(self, bucket, key, content, metadata=None):
                pass

            async def put_object_stream(self, bucket, key, content_generator, metadata=None):
                pass

        sink = TestSink(format="json", compression="gzip")
        records = [{"id": i} for i in range(100)]

        content = await sink._serialize_records(records)

        # Compressed content should be smaller
        uncompressed = json.dumps(records).encode("utf-8")
        assert len(content) < len(uncompressed)

    async def test_load_with_partitions(self):
        """Test loading with partitions."""
        put_calls = []

        class TestSink(ObjectStoreSink):
            async def put_object(self, bucket, key, content, metadata=None):
                put_calls.append((bucket, key, len(content), metadata))

            async def put_object_stream(self, bucket, key, content_generator, metadata=None):
                pass

        sink = TestSink(
            key_template="data/{partition}/{batch_id}.json",
            partition_by=["type"],
            format="json",
        )

        records = [
            {"id": 1, "type": "A"},
            {"id": 2, "type": "A"},
            {"id": 3, "type": "B"},
        ]

        await sink.load(records, "test-bucket")

        assert len(put_calls) == 2
        # Check that partitions were created
        keys = [call[1] for call in put_calls]
        assert any("type=A" in key for key in keys)
        assert any("type=B" in key for key in keys)


class TestS3Sink:
    """Test S3 sink implementation."""

    @pytest.mark.skipif(not HAS_AIOBOTO3, reason="aioboto3 not installed")
    @patch("aioboto3.Session")
    async def test_s3_sink_put_object(self, mock_session_class):
        """Test S3 object upload."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        mock_s3 = AsyncMock()
        mock_client.__aenter__.return_value = mock_s3

        # Test put object
        sink = S3Sink(storage_class="GLACIER")
        await sink.put_object(
            "test-bucket", "test.json", b'{"test": "data"}', {"custom": "metadata"}
        )

        # Verify call
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args[1]
        assert call_args["Bucket"] == "test-bucket"
        assert call_args["Key"] == "test.json"
        assert call_args["Body"] == b'{"test": "data"}'
        assert call_args["StorageClass"] == "GLACIER"
        assert call_args["Metadata"] == {"custom": "metadata"}


class TestProcessors:
    """Test content processors."""

    async def test_json_processor(self):
        """Test JSON processor."""
        # Process array
        records = []
        async for record in json_processor("test.json", b'[{"id": 1}, {"id": 2}]'):
            records.append(record)

        assert len(records) == 2
        assert records[0]["id"] == 1

        # Process single object
        records = []
        async for record in json_processor("test.json", b'{"id": 1, "name": "test"}'):
            records.append(record)

        assert len(records) == 1
        assert records[0]["name"] == "test"

        # Invalid JSON
        with pytest.raises(SourceError):
            async for record in json_processor("test.json", b"invalid json"):
                pass

    async def test_jsonl_processor(self):
        """Test JSONL processor."""
        content = b'{"id": 1}\n{"id": 2}\n\n{"id": 3}'

        records = []
        async for record in jsonl_processor("test.jsonl", content):
            records.append(record)

        assert len(records) == 3
        assert records[2]["id"] == 3

        # Invalid line
        with pytest.raises(SourceError) as exc_info:
            content = b'{"id": 1}\ninvalid\n{"id": 3}'
            async for record in jsonl_processor("test.jsonl", content):
                pass

        assert "line 2" in str(exc_info.value)

    async def test_csv_processor(self):
        """Test CSV processor."""
        # With header
        content = b"id,name\n1,Alice\n2,Bob"

        records = []
        async for record in csv_processor("test.csv", content):
            records.append(record)

        assert len(records) == 2
        assert records[0]["name"] == "Alice"

        # Without header
        content = b"1,Alice\n2,Bob"

        records = []
        async for record in csv_processor("test.csv", content, has_header=False):
            records.append(record)

        assert len(records) == 2
        assert records[0]["col_0"] == "1"
        assert records[0]["col_1"] == "Alice"
