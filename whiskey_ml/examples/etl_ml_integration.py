"""Example showing ML + ETL integration."""

import asyncio

import numpy as np
from whiskey import Whiskey

# This example shows how ML extension adapts when ETL is available
try:
    from whiskey_etl import Pipeline, ValidationMode, etl_extension, validation_transform

    HAS_ETL = True
except ImportError:
    HAS_ETL = False
    print("Note: ETL extension not available. Using standalone ML features.")

from whiskey_ml import MLPipeline, ml_extension


async def main():
    """Run ML pipeline with optional ETL integration."""
    app = Whiskey()

    # Register extensions
    if HAS_ETL:
        app.use(etl_extension)
    app.use(ml_extension)

    if HAS_ETL:
        # Create ETL pipeline for data preparation
        @app.pipeline("data_preparation")
        class DataPreparationPipeline(Pipeline):
            source = "csv_file"
            transforms = ["parse_csv", "clean_missing_values", "normalize_features"]
            sink = "memory"

        # Create validation transform
        validator = (
            validation_transform(ValidationMode.DROP)
            .field("age")
            .required()
            .type(int)
            .range(0, 120)
            .end_field()
            .field("income")
            .required()
            .type(float)
            .range(0, None)
            .end_field()
            .field("label")
            .required()
            .choices([0, 1])
            .end_field()
            .build()
        )

        @app.transform
        async def validate_ml_data(record):
            """Validate data for ML."""
            return await validator.transform(record)

    # Define ML pipeline that adapts based on available extensions
    @app.ml_pipeline("adaptive_ml_pipeline")
    class AdaptiveMLPipeline(MLPipeline):
        # Base configuration
        model = "logistic_regression"
        epochs = 50
        batch_size = 64
        metrics = ["accuracy", "f1", "loss"]

        def __init__(self, context):
            super().__init__(context)

            # Adapt based on available extensions
            if context.has_extension("etl"):
                print("ETL extension detected - using enhanced data pipeline")
                self.data_source = "csv_file"
                self.preprocessing = ["validate_ml_data", "feature_engineering"]
            else:
                print("Using standalone ML data loading")
                self.dataset = "file_dataset"

        async def on_start(self):
            await super().on_start()
            print("\nPipeline Configuration:")
            print(f"- ETL Available: {self.context.has_extension('etl')}")
            print(f"- SQL Available: {self.context.has_extension('sql')}")
            print(f"- Model: {self.model}")
            print(f"- Epochs: {self.epochs}")
            print("-" * 50)

    # Simulate some training data
    if HAS_ETL:
        # Register a CSV source with sample data
        @app.source("csv_file")
        class MockCSVSource:
            async def extract(self, **kwargs):
                """Generate mock CSV-like data."""
                for i in range(1000):
                    yield {
                        "id": i,
                        "age": np.random.randint(18, 80),
                        "income": np.random.uniform(20000, 200000),
                        "education_years": np.random.randint(8, 20),
                        "label": np.random.randint(0, 2),
                    }

        @app.transform
        async def feature_engineering(record):
            """Add engineered features."""
            record["income_bracket"] = "high" if record["income"] > 100000 else "low"
            record["age_group"] = "senior" if record["age"] > 65 else "adult"
            return record

    # Simple model that works with both approaches
    @app.ml_model("logistic_regression")
    class LogisticRegression:
        def __init__(self):
            self.weights = None
            self.bias = 0.0

        async def forward(self, inputs):
            """Simple forward pass."""
            from whiskey_ml import ModelOutput

            # Extract features
            if isinstance(inputs.get("data"), list):
                # From ETL pipeline
                X = np.array([[r.get("age", 0), r.get("income", 0)] for r in inputs["data"]])
                y = np.array([r.get("label", 0) for r in inputs["data"]])
            else:
                # From standard dataset
                X = inputs["data"]
                y = inputs.get("labels")

            # Initialize weights if needed
            if self.weights is None:
                self.weights = np.zeros(X.shape[1])

            # Compute predictions
            logits = X @ self.weights + self.bias
            probs = 1 / (1 + np.exp(-logits))

            # Compute loss
            loss = None
            if y is not None:
                loss = -np.mean(y * np.log(probs + 1e-8) + (1 - y) * np.log(1 - probs + 1e-8))

            return ModelOutput(predictions=probs, loss=loss)

        def get_parameters(self):
            return {"weights": self.weights, "bias": self.bias}

        def set_parameters(self, params):
            self.weights = params["weights"]
            self.bias = params["bias"]

        async def save(self, path):
            np.savez(path, weights=self.weights, bias=self.bias)

        async def load(self, path):
            data = np.load(path)
            self.weights = data["weights"]
            self.bias = data["bias"]

    # Fallback dataset if ETL not available
    @app.ml_dataset("file_dataset")
    class SimpleFileDataset:
        def __init__(self):
            self.data = None
            self.labels = None

        async def load(self):
            # Generate synthetic data
            n_samples = 1000
            self.data = np.random.randn(n_samples, 2)
            self.labels = (self.data[:, 0] + self.data[:, 1] > 0).astype(int)

        def get_splits(self):
            from whiskey_ml.core.dataset import ArrayDataLoader

            n = len(self.data)
            n_train = int(0.8 * n)

            train_loader = ArrayDataLoader(
                self.data[:n_train], self.labels[:n_train], batch_size=64
            )
            val_loader = ArrayDataLoader(self.data[n_train:], self.labels[n_train:], batch_size=64)
            return train_loader, val_loader, None

        def __len__(self):
            return len(self.data) if self.data is not None else 0

    # Run the pipeline
    async with app:
        print("=" * 70)
        print("ML Pipeline with Optional ETL Integration")
        print("=" * 70)

        # Run data preparation if ETL available
        if HAS_ETL:
            print("\nRunning ETL data preparation pipeline...")
            # This would normally run the ETL pipeline
            # await app.pipelines.run("data_preparation")

        # Run ML pipeline
        print("\nRunning ML training pipeline...")
        result = await app.ml.run_pipeline("adaptive_ml_pipeline")

        print("\nTraining completed!")
        print(f"- State: {result.trainer_state}")
        print(f"- Epochs: {result.epochs_trained}")
        print(f"- Time: {result.training_time:.2f}s")

        # Show how the pipeline adapted
        print("\nPipeline Adaptation Summary:")
        if HAS_ETL:
            print("✓ Used ETL data source for streaming data")
            print("✓ Applied ETL transforms for preprocessing")
            print("✓ Validated data quality with ETL validators")
        else:
            print("✓ Used standalone file dataset")
            print("✓ Applied basic preprocessing")
            print("✓ No external dependencies required")


if __name__ == "__main__":
    asyncio.run(main())
