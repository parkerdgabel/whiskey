"""Dataset abstractions for ML pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class DatasetConfig:
    """Configuration for datasets."""

    batch_size: int = 32
    shuffle: bool = True
    drop_last: bool = False
    num_workers: int = 0
    pin_memory: bool = True
    prefetch_factor: int = 2
    persistent_workers: bool = False

    # Data splitting
    train_split: float = 0.8
    val_split: float = 0.1
    test_split: float = 0.1

    # Preprocessing
    normalize: bool = True
    augment: bool = False
    cache: bool = False


class DataLoader(ABC):
    """Abstract data loader interface."""

    @abstractmethod
    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        """Iterate over batches asynchronously."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return number of batches."""
        pass


class Dataset(ABC):
    """Base dataset abstraction - framework agnostic."""

    def __init__(self, config: DatasetConfig | None = None):
        """Initialize dataset.

        Args:
            config: Dataset configuration
        """
        self.config = config or DatasetConfig()
        self._etl_source = None  # Set if ETL integration available
        self._cache = {} if self.config.cache else None

    @abstractmethod
    async def load(self) -> None:
        """Load dataset (async for large datasets)."""
        pass

    @abstractmethod
    def get_splits(self) -> tuple[DataLoader, DataLoader | None, DataLoader | None]:
        """Get train, validation, and test data loaders.

        Returns:
            Tuple of (train_loader, val_loader, test_loader)
            val_loader and test_loader may be None
        """
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return total number of samples."""
        pass

    def set_etl_source(self, source: Any) -> None:
        """Set ETL data source if available.

        Args:
            source: ETL DataSource instance
        """
        self._etl_source = source


class FileDataset(Dataset):
    """Dataset that loads from files."""

    def __init__(
        self,
        file_path: str | Path,
        config: DatasetConfig | None = None,
        format: str = "auto",
    ):
        """Initialize file dataset.

        Args:
            file_path: Path to data file(s)
            config: Dataset configuration
            format: File format (auto, csv, json, parquet, numpy)
        """
        super().__init__(config)
        self.file_path = Path(file_path)
        self.format = format
        self.data = None
        self.labels = None

    async def load(self) -> None:
        """Load data from file."""
        if self._etl_source:
            # Use ETL source if available
            self.data = []
            async for batch in self._etl_source.extract():
                self.data.extend(batch)
        else:
            # Load from file
            if self.format == "auto":
                self.format = self._detect_format()

            if self.format == "numpy":
                self.data = np.load(self.file_path)
            elif self.format == "csv":
                import pandas as pd

                df = pd.read_csv(self.file_path)
                self.data = df.values
            elif self.format == "json":
                import json

                with open(self.file_path) as f:
                    self.data = json.load(f)
            else:
                raise ValueError(f"Unsupported format: {self.format}")

    def _detect_format(self) -> str:
        """Detect file format from extension."""
        suffix = self.file_path.suffix.lower()
        if suffix in [".npy", ".npz"]:
            return "numpy"
        elif suffix == ".csv":
            return "csv"
        elif suffix == ".json":
            return "json"
        elif suffix == ".parquet":
            return "parquet"
        else:
            raise ValueError(f"Cannot detect format for {suffix}")

    def get_splits(self) -> tuple[DataLoader, DataLoader | None, DataLoader | None]:
        """Split data into train/val/test."""
        if self.data is None:
            raise RuntimeError("Dataset not loaded. Call load() first.")

        n_samples = len(self.data)
        n_train = int(n_samples * self.config.train_split)
        n_val = int(n_samples * self.config.val_split)

        # Shuffle if needed
        indices = np.arange(n_samples)
        if self.config.shuffle:
            np.random.shuffle(indices)

        # Split indices
        train_idx = indices[:n_train]
        val_idx = indices[n_train : n_train + n_val] if n_val > 0 else None
        test_idx = indices[n_train + n_val :] if n_samples > n_train + n_val else None

        # Create data loaders
        train_loader = ArrayDataLoader(
            self.data[train_idx],
            self.labels[train_idx] if self.labels is not None else None,
            self.config.batch_size,
            shuffle=self.config.shuffle,
        )

        val_loader = None
        if val_idx is not None:
            val_loader = ArrayDataLoader(
                self.data[val_idx],
                self.labels[val_idx] if self.labels is not None else None,
                self.config.batch_size,
                shuffle=False,
            )

        test_loader = None
        if test_idx is not None:
            test_loader = ArrayDataLoader(
                self.data[test_idx],
                self.labels[test_idx] if self.labels is not None else None,
                self.config.batch_size,
                shuffle=False,
            )

        return train_loader, val_loader, test_loader

    def __len__(self) -> int:
        """Return number of samples."""
        return len(self.data) if self.data is not None else 0


class ArrayDataLoader(DataLoader):
    """Simple data loader for numpy arrays."""

    def __init__(
        self,
        data: np.ndarray,
        labels: np.ndarray | None = None,
        batch_size: int = 32,
        shuffle: bool = True,
        drop_last: bool = False,
    ):
        """Initialize array data loader.

        Args:
            data: Input data array
            labels: Optional labels array
            batch_size: Batch size
            shuffle: Whether to shuffle data
            drop_last: Whether to drop last incomplete batch
        """
        self.data = data
        self.labels = labels
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.drop_last = drop_last

        self.n_samples = len(data)
        self.n_batches = self.n_samples // batch_size
        if not drop_last and self.n_samples % batch_size != 0:
            self.n_batches += 1

    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        """Iterate over batches."""
        indices = np.arange(self.n_samples)
        if self.shuffle:
            np.random.shuffle(indices)

        for i in range(self.n_batches):
            start_idx = i * self.batch_size
            end_idx = min((i + 1) * self.batch_size, self.n_samples)

            if self.drop_last and end_idx - start_idx < self.batch_size:
                break

            batch_indices = indices[start_idx:end_idx]

            batch = {
                "data": self.data[batch_indices],
                "batch_size": len(batch_indices),
            }

            if self.labels is not None:
                batch["labels"] = self.labels[batch_indices]

            yield batch

    def __len__(self) -> int:
        """Return number of batches."""
        return self.n_batches


class StreamingDataset(Dataset):
    """Dataset that streams data without loading all into memory."""

    def __init__(
        self,
        stream_fn: AsyncIterator[Any],
        config: DatasetConfig | None = None,
    ):
        """Initialize streaming dataset.

        Args:
            stream_fn: Async function that yields data
            config: Dataset configuration
        """
        super().__init__(config)
        self.stream_fn = stream_fn
        self._estimated_size = None

    async def load(self) -> None:
        """No-op for streaming dataset."""
        pass

    def get_splits(self) -> tuple[DataLoader, DataLoader | None, DataLoader | None]:
        """Return streaming data loaders."""
        # For streaming, we typically only have training data
        train_loader = StreamingDataLoader(
            self.stream_fn,
            self.config.batch_size,
        )

        return train_loader, None, None

    def __len__(self) -> int:
        """Return estimated size if available."""
        return self._estimated_size or -1


class StreamingDataLoader(DataLoader):
    """Data loader for streaming data."""

    def __init__(
        self,
        stream_fn: AsyncIterator[Any],
        batch_size: int = 32,
    ):
        """Initialize streaming data loader.

        Args:
            stream_fn: Async function that yields data
            batch_size: Batch size
        """
        self.stream_fn = stream_fn
        self.batch_size = batch_size

    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        """Stream batches."""
        batch = []

        async for item in self.stream_fn:
            batch.append(item)

            if len(batch) >= self.batch_size:
                yield {
                    "data": batch,
                    "batch_size": len(batch),
                }
                batch = []

        # Yield remaining items
        if batch:
            yield {
                "data": batch,
                "batch_size": len(batch),
            }

    def __len__(self) -> int:
        """Unknown length for streaming."""
        return -1
