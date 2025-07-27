"""ETL extension integration for ML pipelines."""

from __future__ import annotations

from typing import Any, Optional

from whiskey_ml.core.dataset import Dataset, DataLoader, StreamingDataset
from whiskey_ml.integrations.base import ExtensionIntegration


class ETLIntegration:
    """Enhances ML pipelines with ETL capabilities when available."""
    
    def __init__(self, integration: ExtensionIntegration):
        """Initialize ETL integration.
        
        Args:
            integration: Extension integration instance
        """
        self.integration = integration
        self.container = integration.container
        self._setup()
    
    def _setup(self) -> None:
        """Set up ETL integration."""
        # Import ETL components
        from whiskey_etl import DataSource, DataSink, Transform
        
        # Store references
        self.DataSource = DataSource
        self.DataSink = DataSink
        self.Transform = Transform
        
        # Enhance ML components
        self._enhance_dataset_class()
        self._register_etl_datasets()
        self._register_etl_transforms()
    
    def _enhance_dataset_class(self) -> None:
        """Add ETL capabilities to Dataset class."""
        # Monkey patch Dataset to support ETL sources
        original_init = Dataset.__init__
        
        def enhanced_init(self, config=None, etl_source=None, **kwargs):
            original_init(self, config, **kwargs)
            if etl_source:
                self.set_etl_source(etl_source)
        
        Dataset.__init__ = enhanced_init
    
    def _register_etl_datasets(self) -> None:
        """Register ETL-based datasets."""
        from whiskey import component
        
        @component
        class ETLDataset(Dataset):
            """Dataset that uses ETL data sources."""
            
            def __init__(self, source_name: str, config=None):
                super().__init__(config)
                # Resolve ETL source
                from whiskey_etl import get_source
                self._etl_source = get_source(source_name)
            
            async def load(self) -> None:
                """Load data using ETL source."""
                # ETL sources handle their own loading
                pass
            
            def get_splits(self) -> tuple[DataLoader, Optional[DataLoader], Optional[DataLoader]]:
                """Get data loaders using ETL source."""
                # Create ETL-based data loader
                train_loader = ETLDataLoader(
                    self._etl_source,
                    self.config.batch_size,
                    transforms=self._transforms,
                )
                
                # ETL typically provides streaming data, so no predefined splits
                return train_loader, None, None
            
            def __len__(self) -> int:
                """Return estimated size."""
                return -1  # Unknown for streaming
        
        # Register in container
        self.container["ETLDataset"] = ETLDataset
    
    def _register_etl_transforms(self) -> None:
        """Register ML transforms that use ETL."""
        from whiskey import component
        
        @component
        class ETLPreprocessor:
            """Preprocessor that uses ETL transforms."""
            
            def __init__(self, transform_names: list[str]):
                self.transform_names = transform_names
                self._transforms = []
                
                # Resolve ETL transforms
                from whiskey_etl import get_transform
                for name in transform_names:
                    transform = get_transform(name)
                    self._transforms.append(transform)
            
            async def process(self, data: Any) -> Any:
                """Apply ETL transforms to data."""
                result = data
                for transform in self._transforms:
                    result = await transform(result)
                return result
        
        self.container["ETLPreprocessor"] = ETLPreprocessor


class ETLDataLoader(DataLoader):
    """Data loader that uses ETL data source."""
    
    def __init__(
        self,
        etl_source: Any,
        batch_size: int = 32,
        transforms: list[Any] | None = None,
    ):
        """Initialize ETL data loader.
        
        Args:
            etl_source: ETL DataSource instance
            batch_size: Batch size
            transforms: Optional transforms to apply
        """
        self.etl_source = etl_source
        self.batch_size = batch_size
        self.transforms = transforms or []
    
    async def __aiter__(self):
        """Iterate over batches from ETL source."""
        # Use ETL source's extract method
        async for batch in self.etl_source.extract(batch_size=self.batch_size):
            # Apply transforms
            for transform in self.transforms:
                batch = await transform(batch)
            
            # Convert to ML format
            yield self._convert_batch(batch)
    
    def _convert_batch(self, batch: Any) -> dict[str, Any]:
        """Convert ETL batch to ML format.
        
        Args:
            batch: ETL batch (list of records)
            
        Returns:
            ML-formatted batch
        """
        if isinstance(batch, list) and batch and isinstance(batch[0], dict):
            # Convert list of dicts to dict of lists
            keys = batch[0].keys()
            result = {key: [record[key] for record in batch] for key in keys}
            
            # Extract features and labels if present
            if "features" in result and "label" in result:
                return {
                    "data": result["features"],
                    "labels": result["label"],
                    "batch_size": len(batch),
                }
            else:
                return {
                    "data": batch,
                    "batch_size": len(batch),
                }
        
        # Return as-is if not in expected format
        return {
            "data": batch,
            "batch_size": len(batch) if hasattr(batch, "__len__") else 1,
        }
    
    def __len__(self) -> int:
        """Return number of batches (unknown for streaming)."""
        return -1


def create_etl_dataset(
    source: str | Any,
    preprocessing: list[str] | None = None,
    batch_size: int = 32,
) -> Dataset:
    """Create a dataset that uses ETL sources.
    
    Args:
        source: ETL source name or instance
        preprocessing: List of ETL transform names
        batch_size: Batch size
        
    Returns:
        Dataset instance
    """
    from whiskey_etl import get_source, get_transform
    
    # Resolve source
    if isinstance(source, str):
        source = get_source(source)
    
    # Resolve transforms
    transforms = []
    if preprocessing:
        for name in preprocessing:
            transforms.append(get_transform(name))
    
    # Create streaming dataset with ETL source
    async def stream_fn():
        async for batch in source.extract(batch_size=batch_size):
            # Apply transforms
            for transform in transforms:
                batch = await transform(batch)
            yield batch
    
    return StreamingDataset(stream_fn)