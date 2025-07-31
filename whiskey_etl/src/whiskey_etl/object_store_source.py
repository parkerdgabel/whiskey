"""Object store source implementations for cloud storage."""

from __future__ import annotations

import asyncio
import json
from abc import abstractmethod
from datetime import datetime
from typing import Any, AsyncIterator, Callable

from .errors import SourceError
from .sources import DataSource


class ObjectStoreSource(DataSource):
    """Base class for object store sources (S3, Azure Blob, GCS, etc.)."""

    def __init__(
        self,
        prefix: str = "",
        suffix: str = "",
        recursive: bool = True,
        modified_after: datetime | None = None,
        max_keys: int | None = None,
    ):
        """Initialize object store source.

        Args:
            prefix: Filter objects by prefix (e.g., "data/2024/")
            suffix: Filter objects by suffix (e.g., ".json", ".csv")
            recursive: Whether to list objects recursively
            modified_after: Only include objects modified after this time
            max_keys: Maximum number of objects to process
        """
        self.prefix = prefix
        self.suffix = suffix
        self.recursive = recursive
        self.modified_after = modified_after
        self.max_keys = max_keys

    @abstractmethod
    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """List objects in the bucket.

        Args:
            bucket: Bucket/container name
            prefix: Object prefix filter
            **kwargs: Additional provider-specific options

        Yields:
            Object metadata dictionaries with at least:
            - key: Object key/path
            - size: Object size in bytes
            - last_modified: Last modification time
        """
        pass

    @abstractmethod
    async def get_object(self, bucket: str, key: str) -> bytes:
        """Get object content.

        Args:
            bucket: Bucket/container name
            key: Object key/path

        Returns:
            Object content as bytes
        """
        pass

    @abstractmethod
    async def get_object_stream(
        self,
        bucket: str,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream object content in chunks.

        Args:
            bucket: Bucket/container name
            key: Object key/path
            chunk_size: Size of chunks to yield

        Yields:
            Chunks of object content
        """
        pass

    async def extract(
        self,
        bucket: str,
        processor: Callable[[str, bytes], AsyncIterator[dict]] | None = None,
        stream: bool = False,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """Extract data from object store.

        Args:
            bucket: Bucket/container name
            processor: Function to process object content into records
            stream: Whether to stream large objects
            **kwargs: Additional options

        Yields:
            Records extracted from objects
        """
        try:
            object_count = 0

            # List objects with filters
            async for obj in self.list_objects(bucket, self.prefix, **kwargs):
                # Apply filters
                if self.suffix and not obj["key"].endswith(self.suffix):
                    continue

                if self.modified_after and obj.get("last_modified"):
                    if obj["last_modified"] < self.modified_after:
                        continue

                # Check max keys limit
                if self.max_keys and object_count >= self.max_keys:
                    break

                object_count += 1

                # Get object content
                if stream and hasattr(self, "get_object_stream"):
                    # Stream large objects
                    content_stream = self.get_object_stream(bucket, obj["key"])
                    if processor:
                        async for record in processor(obj["key"], content_stream):
                            yield record
                    else:
                        # Default: yield object metadata with stream
                        yield {
                            "key": obj["key"],
                            "size": obj.get("size"),
                            "last_modified": obj.get("last_modified"),
                            "content_stream": content_stream,
                        }
                else:
                    # Load entire object
                    content = await self.get_object(bucket, obj["key"])

                    if processor:
                        # Process content into records
                        async for record in processor(obj["key"], content):
                            yield record
                    else:
                        # Default: yield object metadata with content
                        yield {
                            "key": obj["key"],
                            "size": obj.get("size"),
                            "last_modified": obj.get("last_modified"),
                            "content": content,
                        }

        except Exception as e:
            raise SourceError(
                self.__class__.__name__,
                f"Failed to extract from object store: {e}",
                details={"bucket": bucket, "prefix": self.prefix},
            ) from e


class S3Source(ObjectStoreSource):
    """AWS S3 source implementation."""

    def __init__(
        self,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
        endpoint_url: str | None = None,
        **kwargs,
    ):
        """Initialize S3 source.

        Args:
            aws_access_key_id: AWS access key (uses environment/IAM if not provided)
            aws_secret_access_key: AWS secret key
            region_name: AWS region
            endpoint_url: Custom endpoint (for S3-compatible services)
            **kwargs: Additional ObjectStoreSource parameters
        """
        super().__init__(**kwargs)
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self._client = None

    async def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            try:
                import aioboto3
            except ImportError as e:
                raise ImportError(
                    "aioboto3 required for S3Source. Install with: pip install aioboto3"
                ) from e

            session = aioboto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
            )
            self._client = session.client("s3", endpoint_url=self.endpoint_url)
        return self._client

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """List objects in S3 bucket."""
        client = await self._get_client()

        async with client as s3:
            paginator = s3.get_paginator("list_objects_v2")

            async for page in paginator.paginate(
                Bucket=bucket,
                Prefix=prefix or self.prefix,
                **kwargs,
            ):
                for obj in page.get("Contents", []):
                    yield {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj.get("ETag"),
                        "storage_class": obj.get("StorageClass"),
                    }

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Get object content from S3."""
        client = await self._get_client()

        async with client as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            return await response["Body"].read()

    async def get_object_stream(
        self,
        bucket: str,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream object content from S3."""
        client = await self._get_client()

        async with client as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)

            async for chunk in response["Body"].iter_chunks(chunk_size):
                yield chunk


class AzureBlobSource(ObjectStoreSource):
    """Azure Blob Storage source implementation."""

    def __init__(
        self,
        account_name: str,
        account_key: str | None = None,
        connection_string: str | None = None,
        **kwargs,
    ):
        """Initialize Azure Blob source.

        Args:
            account_name: Storage account name
            account_key: Storage account key
            connection_string: Full connection string (alternative to account_name/key)
            **kwargs: Additional ObjectStoreSource parameters
        """
        super().__init__(**kwargs)
        self.account_name = account_name
        self.account_key = account_key
        self.connection_string = connection_string
        self._client = None

    async def _get_client(self):
        """Get or create Azure Blob client."""
        if self._client is None:
            try:
                from azure.storage.blob.aio import BlobServiceClient
            except ImportError as e:
                raise ImportError(
                    "azure-storage-blob required for AzureBlobSource. "
                    "Install with: pip install azure-storage-blob"
                ) from e

            if self.connection_string:
                self._client = BlobServiceClient.from_connection_string(self.connection_string)
            else:
                self._client = BlobServiceClient(
                    account_url=f"https://{self.account_name}.blob.core.windows.net",
                    credential=self.account_key,
                )
        return self._client

    async def list_objects(
        self,
        bucket: str,  # container name in Azure
        prefix: str = "",
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """List blobs in Azure container."""
        client = await self._get_client()
        container_client = client.get_container_client(bucket)

        async for blob in container_client.list_blobs(
            name_starts_with=prefix or self.prefix,
            **kwargs,
        ):
            yield {
                "key": blob.name,
                "size": blob.size,
                "last_modified": blob.last_modified,
                "etag": blob.etag,
                "content_type": (
                    blob.content_settings.content_type if blob.content_settings else None
                ),
            }

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Get blob content from Azure."""
        client = await self._get_client()
        blob_client = client.get_blob_client(container=bucket, blob=key)

        return await blob_client.download_blob().readall()

    async def get_object_stream(
        self,
        bucket: str,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream blob content from Azure."""
        client = await self._get_client()
        blob_client = client.get_blob_client(container=bucket, blob=key)

        stream = await blob_client.download_blob()
        async for chunk in stream.chunks():
            yield chunk


class GCSSource(ObjectStoreSource):
    """Google Cloud Storage source implementation."""

    def __init__(
        self,
        project_id: str | None = None,
        credentials_path: str | None = None,
        **kwargs,
    ):
        """Initialize GCS source.

        Args:
            project_id: GCP project ID
            credentials_path: Path to service account JSON file
            **kwargs: Additional ObjectStoreSource parameters
        """
        super().__init__(**kwargs)
        self.project_id = project_id
        self.credentials_path = credentials_path
        self._client = None

    async def _get_client(self):
        """Get or create GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage
                from google.oauth2 import service_account
            except ImportError as e:
                raise ImportError(
                    "google-cloud-storage required for GCSSource. "
                    "Install with: pip install google-cloud-storage"
                ) from e

            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self._client = storage.Client(
                    project=self.project_id,
                    credentials=credentials,
                )
            else:
                self._client = storage.Client(project=self.project_id)
        return self._client

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """List objects in GCS bucket."""
        client = await self._get_client()
        bucket_obj = client.bucket(bucket)

        # GCS client is sync, so we run in executor
        loop = asyncio.get_event_loop()
        blobs = await loop.run_in_executor(
            None, lambda: list(bucket_obj.list_blobs(prefix=prefix or self.prefix, **kwargs))
        )

        for blob in blobs:
            yield {
                "key": blob.name,
                "size": blob.size,
                "last_modified": blob.updated,
                "etag": blob.etag,
                "content_type": blob.content_type,
                "storage_class": blob.storage_class,
            }

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Get object content from GCS."""
        client = await self._get_client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(key)

        # GCS client is sync, so we run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, blob.download_as_bytes)

    async def get_object_stream(
        self,
        bucket: str,
        key: str,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream object content from GCS."""
        # For now, GCS doesn't have great async streaming support
        # So we'll download and yield in chunks
        content = await self.get_object(bucket, key)

        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]


# Utility processors for common file formats
async def json_processor(key: str, content: bytes) -> AsyncIterator[dict]:
    """Process JSON content into records."""
    try:
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, list):
            for record in data:
                yield record
        else:
            yield data
    except json.JSONDecodeError as e:
        raise SourceError("json_processor", f"Invalid JSON in {key}: {e}") from e


async def jsonl_processor(key: str, content: bytes) -> AsyncIterator[dict]:
    """Process JSON Lines content into records."""
    for line_num, line in enumerate(content.decode("utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise SourceError(
                    "jsonl_processor", f"Invalid JSON on line {line_num} in {key}: {e}"
                ) from e


async def csv_processor(
    key: str,
    content: bytes,
    delimiter: str = ",",
    has_header: bool = True,
) -> AsyncIterator[dict]:
    """Process CSV content into records."""
    import csv
    import io

    text = content.decode("utf-8")
    reader = (
        csv.DictReader(
            io.StringIO(text),
            delimiter=delimiter,
        )
        if has_header
        else csv.reader(io.StringIO(text), delimiter=delimiter)
    )

    for row in reader:
        if has_header:
            yield row
        else:
            # For no header, create dict with column indices
            yield {f"col_{i}": val for i, val in enumerate(row)}
