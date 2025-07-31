"""Basic classification example using Whiskey ML extension."""

import asyncio
from pathlib import Path

import numpy as np
from whiskey import Whiskey

from whiskey_ml import (
    DataLoader,
    Dataset,
    MLPipeline,
    Model,
    ModelOutput,
    ml_extension,
)


# Create a simple dataset
class SimpleDataset(Dataset):
    """Simple synthetic dataset for demonstration."""

    def __init__(self, n_samples: int = 1000, n_features: int = 20, n_classes: int = 3):
        super().__init__()
        self.n_samples = n_samples
        self.n_features = n_features
        self.n_classes = n_classes
        self.X = None
        self.y = None

    async def load(self):
        """Generate synthetic data."""
        # Generate random features
        self.X = np.random.randn(self.n_samples, self.n_features)

        # Generate labels (simple linear classification)
        weights = np.random.randn(self.n_features, self.n_classes)
        logits = self.X @ weights
        self.y = np.argmax(logits + 0.1 * np.random.randn(*logits.shape), axis=1)

        print(f"Generated dataset with {self.n_samples} samples, {self.n_features} features")

    def get_splits(self):
        """Split into train/val/test."""
        n_train = int(0.7 * self.n_samples)
        n_val = int(0.15 * self.n_samples)

        # Create simple data loaders
        train_loader = SimpleDataLoader(
            self.X[:n_train], self.y[:n_train], batch_size=self.config.batch_size
        )

        val_loader = SimpleDataLoader(
            self.X[n_train : n_train + n_val],
            self.y[n_train : n_train + n_val],
            batch_size=self.config.batch_size,
        )

        test_loader = SimpleDataLoader(
            self.X[n_train + n_val :], self.y[n_train + n_val :], batch_size=self.config.batch_size
        )

        return train_loader, val_loader, test_loader

    def __len__(self):
        return self.n_samples


class SimpleDataLoader(DataLoader):
    """Simple data loader implementation."""

    def __init__(self, X, y, batch_size=32):
        self.X = X
        self.y = y
        self.batch_size = batch_size
        self.n_batches = len(X) // batch_size

    async def __aiter__(self):
        """Iterate over batches."""
        indices = np.arange(len(self.X))
        np.random.shuffle(indices)

        for i in range(self.n_batches):
            start = i * self.batch_size
            end = start + self.batch_size
            batch_idx = indices[start:end]

            yield {
                "data": self.X[batch_idx],
                "labels": self.y[batch_idx],
                "batch_size": len(batch_idx),
            }

    def __len__(self):
        return self.n_batches


# Create a simple model
class SimpleClassifier(Model):
    """Simple linear classifier."""

    def __init__(self, n_features: int = 20, n_classes: int = 3):
        super().__init__()
        self.n_features = n_features
        self.n_classes = n_classes

        # Initialize weights
        self.weights = np.random.randn(n_features, n_classes) * 0.01
        self.bias = np.zeros(n_classes)

    async def forward(self, inputs):
        """Forward pass."""
        X = inputs["data"]

        # Linear transformation
        logits = X @ self.weights + self.bias

        # Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # Compute loss if labels provided
        loss = None
        if "labels" in inputs:
            y = inputs["labels"]
            # Cross entropy loss
            log_probs = np.log(probs + 1e-8)
            loss = -np.mean(log_probs[np.arange(len(y)), y])

        return ModelOutput(predictions=probs, loss=loss)

    def get_parameters(self):
        """Get model parameters."""
        return {"weights": self.weights, "bias": self.bias}

    def set_parameters(self, parameters):
        """Set model parameters."""
        self.weights = parameters["weights"]
        self.bias = parameters["bias"]

    async def save(self, path):
        """Save model."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, weights=self.weights, bias=self.bias)

    async def load(self, path):
        """Load model."""
        data = np.load(path)
        self.weights = data["weights"]
        self.bias = data["bias"]


async def main():
    """Run basic classification example."""
    # Create Whiskey app
    app = Whiskey()
    app.use(ml_extension)

    # Register dataset
    @app.ml_dataset("synthetic_dataset")
    class SyntheticDataset(SimpleDataset):
        pass

    # Register model
    @app.ml_model("simple_classifier")
    class SimpleClassifierModel(SimpleClassifier):
        pass

    # Define ML pipeline
    @app.ml_pipeline("basic_classification")
    class BasicClassificationPipeline(MLPipeline):
        # Dataset configuration
        dataset = "synthetic_dataset"
        batch_size = 32

        # Model configuration
        model = "simple_classifier"
        learning_rate = 0.1

        # Training configuration
        epochs = 10
        metrics = ["loss", "accuracy"]

        # Optional: Custom initialization
        async def on_start(self):
            await super().on_start()
            print(f"\nStarting {self.config.name} pipeline")
            print(f"Model: {self.model}")
            print(f"Dataset: {self.dataset}")
            print(f"Epochs: {self.epochs}")
            print("-" * 50)

        async def on_epoch_end(self, epoch, metrics):
            """Log progress after each epoch."""
            print(f"Epoch {epoch + 1}/{self.epochs} - loss: {metrics.get('loss', 0):.4f}")

    # Run the pipeline
    async with app:
        print("Running basic classification pipeline...\n")

        # Execute pipeline
        result = await app.ml.run_pipeline("basic_classification")

        # Print results
        print("\n" + "=" * 50)
        print("Training Complete!")
        print("=" * 50)
        print(f"Final state: {result.trainer_state}")
        print(f"Epochs trained: {result.epochs_trained}")
        print(f"Training time: {result.training_time:.2f} seconds")

        if result.test_metrics:
            print("\nTest Metrics:")
            for metric, value in result.test_metrics.items():
                print(f"  {metric}: {value:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
