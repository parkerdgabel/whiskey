"""Object store sink implementations for cloud storage."""

from __future__ import annotations

import asyncio
import json
from abc import abstractmethod
from datetime import datetime
from typing import Any, AsyncIterator

from .errors import SinkError
from .sinks import DataSink


class ObjectStoreSink(DataSink):
    """Base class for object store sinks (S3, Azure Blob, GCS, etc.)."""

    def __init__(
        self,
        key_template: str = "{timestamp}/{batch_id}.json",
        partition_by: list[str] | None = None,
        format: str = "json",  # json, jsonl, csv, parquet
        compression: str | None = None,  # gzip, snappy, etc.
        metadata: dict[str, str] | None = None,
    ):
        """Initialize object store sink.

        Args:
            key_template: Template for object keys (supports {timestamp}, {batch_id}, {partition})
            partition_by: Fields to partition data by (creates separate objects)
            format: Output format
            compression: Compression type
            metadata: Object metadata to add
        """
        self.key_template = key_template
        self.partition_by = partition_by or []
        self.format = format
        self.compression = compression
        self.metadata = metadata or {}
        self._batch_id = 0

    @abstractmethod
    async def put_object(
        self,
        bucket: str,
        key: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Put object to store.

        Args:
            bucket: Bucket/container name
            key: Object key/path
            content: Object content
            metadata: Object metadata
        """
        pass

    @abstractmethod
    async def put_object_stream(
        self,
        bucket: str,
        key: str,
        content_generator: AsyncIterator[bytes],
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Stream object to store.

        Args:
            bucket: Bucket/container name
            key: Object key/path
            content_generator: Async generator of content chunks
            metadata: Object metadata
        """
        pass

    def _generate_key(self, partition: str | None = None) -> str:
        """Generate object key from template."""
        self._batch_id += 1
        return self.key_template.format(
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            batch_id=self._batch_id,
            partition=partition or "default",
        )

    def _partition_records(self, records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Partition records by specified fields."""
        if not self.partition_by:
            return {"default": records}

        partitions = {}
        for record in records:
            # Create partition key from field values
            partition_values = []
            for field in self.partition_by:
                value = record.get(field, "null")
                partition_values.append(f"{field}={value}")

            partition_key = "/".join(partition_values)
            if partition_key not in partitions:
                partitions[partition_key] = []
            partitions[partition_key].append(record)

        return partitions

    async def _serialize_records(self, records: list[dict[str, Any]]) -> bytes:
        """Serialize records to bytes based on format."""
        if self.format == "json":
            content = json.dumps(records, indent=2, default=str).encode("utf-8")
        elif self.format == "jsonl":
            lines = [json.dumps(record, default=str) for record in records]
            content = "\n".join(lines).encode("utf-8")
        elif self.format == "csv":
            import csv
            import io

            if not records:
                return b""

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
            content = output.getvalue().encode("utf-8")
        elif self.format == "parquet":
            try:
                import io

                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError as e:
                raise ImportError(
                    "pyarrow required for parquet format. Install with: pip install pyarrow"
                ) from e

            # Convert to Arrow table
            table = pa.Table.from_pylist(records)

            # Write to bytes
            buf = io.BytesIO()
            pq.write_table(table, buf)
            content = buf.getvalue()
        else:
            raise ValueError(f"Unsupported format: {self.format}")

        # Apply compression if specified
        if self.compression:
            content = await self._compress(content)

        return content

    async def _compress(self, content: bytes) -> bytes:
        """Compress content."""
        if self.compression == "gzip":
            import gzip

            return gzip.compress(content)
        elif self.compression == "snappy":
            try:
                import snappy
            except ImportError as e:
                raise ImportError(
                    "python-snappy required for snappy compression. "
                    "Install with: pip install python-snappy"
                ) from e
            return snappy.compress(content)
        else:
            raise ValueError(f"Unsupported compression: {self.compression}")

    async def load(
        self,
        records: list[dict[str, Any]],
        bucket: str,
        **kwargs,
    ) -> None:
        """Load records to object store.

        Args:
            records: Records to store
            bucket: Bucket/container name
            **kwargs: Additional options
        """
        if not records:
            return

        try:
            # Partition records if specified
            partitions = self._partition_records(records)

            # Write each partition
            tasks = []
            for partition_key, partition_records in partitions.items():
                # Generate key for this partition
                key = self._generate_key(partition_key)

                # Serialize records
                content = await self._serialize_records(partition_records)

                # Prepare metadata
                metadata = self.metadata.copy()
                metadata.update(
                    {
                        "record_count": str(len(partition_records)),
                        "format": self.format,
                        "partition": partition_key,
                    }
                )
                if self.compression:
                    metadata["compression"] = self.compression

                # Upload object
                task = self.put_object(bucket, key, content, metadata)
                tasks.append(task)

            # Execute all uploads concurrently
            await asyncio.gather(*tasks)

        except Exception as e:
            raise SinkError(
                self.__class__.__name__,
                f"Failed to load to object store: {e}",
                details={
                    "bucket": bucket,
                    "records": len(records),
                    "format": self.format,
                },
            ) from e


class S3Sink(ObjectStoreSink):
    """AWS S3 sink implementation."""

    def __init__(
        self,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
        endpoint_url: str | None = None,
        storage_class: str = "STANDARD",
        server_side_encryption: str | None = None,
        **kwargs,
    ):
        """Initialize S3 sink.

        Args:
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            region_name: AWS region
            endpoint_url: Custom endpoint
            storage_class: S3 storage class
            server_side_encryption: Server-side encryption method
            **kwargs: Additional ObjectStoreSink parameters
        """
        super().__init__(**kwargs)
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.storage_class = storage_class
        self.server_side_encryption = server_side_encryption
        self._client = None

    async def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            try:
                import aioboto3
            except ImportError as e:
                raise ImportError(
                    "aioboto3 required for S3Sink. Install with: pip install aioboto3"
                ) from e

            session = aioboto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
            )
            self._client = session.client("s3", endpoint_url=self.endpoint_url)
        return self._client

    async def put_object(
        self,
        bucket: str,
        key: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Put object to S3."""
        client = await self._get_client()

        async with client as s3:
            put_args = {
                "Bucket": bucket,
                "Key": key,
                "Body": content,
                "StorageClass": self.storage_class,
            }

            if metadata:
                put_args["Metadata"] = metadata

            if self.server_side_encryption:
                put_args["ServerSideEncryption"] = self.server_side_encryption

            await s3.put_object(**put_args)

    async def put_object_stream(
        self,
        bucket: str,
        key: str,
        content_generator: AsyncIterator[bytes],
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Stream object to S3 using multipart upload."""
        client = await self._get_client()

        async with client as s3:
            # Initialize multipart upload
            create_args = {
                "Bucket": bucket,
                "Key": key,
                "StorageClass": self.storage_class,
            }

            if metadata:
                create_args["Metadata"] = metadata

            if self.server_side_encryption:
                create_args["ServerSideEncryption"] = self.server_side_encryption

            response = await s3.create_multipart_upload(**create_args)
            upload_id = response["UploadId"]

            try:
                parts = []
                part_number = 1

                async for chunk in content_generator:
                    part = await s3.upload_part(
                        Bucket=bucket,
                        Key=key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk,
                    )

                    parts.append(
                        {
                            "ETag": part["ETag"],
                            "PartNumber": part_number,
                        }
                    )
                    part_number += 1

                # Complete multipart upload
                await s3.complete_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )

            except Exception:
                # Abort upload on error
                await s3.abort_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                )
                raise


class AzureBlobSink(ObjectStoreSink):
    """Azure Blob Storage sink implementation."""

    def __init__(
        self,
        account_name: str,
        account_key: str | None = None,
        connection_string: str | None = None,
        blob_type: str = "BlockBlob",
        tier: str | None = None,
        **kwargs,
    ):
        """Initialize Azure Blob sink.

        Args:
            account_name: Storage account name
            account_key: Storage account key
            connection_string: Full connection string
            blob_type: Type of blob (BlockBlob, PageBlob, AppendBlob)
            tier: Access tier (Hot, Cool, Archive)
            **kwargs: Additional ObjectStoreSink parameters
        """
        super().__init__(**kwargs)
        self.account_name = account_name
        self.account_key = account_key
        self.connection_string = connection_string
        self.blob_type = blob_type
        self.tier = tier
        self._client = None

    async def _get_client(self):
        """Get or create Azure Blob client."""
        if self._client is None:
            try:
                from azure.storage.blob.aio import BlobServiceClient
            except ImportError as e:
                raise ImportError(
                    "azure-storage-blob required for AzureBlobSink. "
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

    async def put_object(
        self,
        bucket: str,
        key: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Put blob to Azure."""
        client = await self._get_client()
        blob_client = client.get_blob_client(container=bucket, blob=key)

        await blob_client.upload_blob(
            content,
            blob_type=self.blob_type,
            metadata=metadata,
            overwrite=True,
            standard_blob_tier=self.tier,
        )

    async def put_object_stream(
        self,
        bucket: str,
        key: str,
        content_generator: AsyncIterator[bytes],
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Stream blob to Azure."""
        client = await self._get_client()
        blob_client = client.get_blob_client(container=bucket, blob=key)

        # Collect chunks (Azure SDK doesn't support true streaming yet)
        chunks = []
        async for chunk in content_generator:
            chunks.append(chunk)

        content = b"".join(chunks)

        await blob_client.upload_blob(
            content,
            blob_type=self.blob_type,
            metadata=metadata,
            overwrite=True,
            standard_blob_tier=self.tier,
        )


class GCSSink(ObjectStoreSink):
    """Google Cloud Storage sink implementation."""

    def __init__(
        self,
        project_id: str | None = None,
        credentials_path: str | None = None,
        storage_class: str = "STANDARD",
        **kwargs,
    ):
        """Initialize GCS sink.

        Args:
            project_id: GCP project ID
            credentials_path: Path to service account JSON
            storage_class: Storage class
            **kwargs: Additional ObjectStoreSink parameters
        """
        super().__init__(**kwargs)
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.storage_class = storage_class
        self._client = None

    async def _get_client(self):
        """Get or create GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage
                from google.oauth2 import service_account
            except ImportError as e:
                raise ImportError(
                    "google-cloud-storage required for GCSSink. "
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

    async def put_object(
        self,
        bucket: str,
        key: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Put object to GCS."""
        client = await self._get_client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(key)

        if metadata:
            blob.metadata = metadata

        # GCS client is sync, so run in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(content),
        )

        # Set storage class if different from default
        if self.storage_class != "STANDARD":
            await loop.run_in_executor(
                None,
                lambda: blob.update_storage_class(self.storage_class),
            )

    async def put_object_stream(
        self,
        bucket: str,
        key: str,
        content_generator: AsyncIterator[bytes],
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Stream object to GCS."""
        # GCS doesn't have great async streaming support
        # Collect chunks and upload
        chunks = []
        async for chunk in content_generator:
            chunks.append(chunk)

        content = b"".join(chunks)
        await self.put_object(bucket, key, content, metadata)
