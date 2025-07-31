"""Example demonstrating ML training with real-time visualization."""

import asyncio
from pathlib import Path

import numpy as np
from whiskey import Whiskey

from whiskey_ml import (
    Dataset,
    MLPipeline,
    Model,
    ModelOutput,
    ml_extension,
)
from whiskey_ml.core.dataset import ArrayDataLoader
from whiskey_ml.visualization import (
    ConsoleMetricsHandler,
    MetricsTracker,
    RichProgressHandler,
    TensorBoardHandler,
)


# Reuse simple implementations from previous examples
class SimpleDataset(Dataset):
    """Simple synthetic dataset."""

    def __init__(self, n_samples: int = 1000):
        super().__init__()
        self.n_samples = n_samples
        self.data = None
        self.labels = None

    async def load(self):
        """Generate synthetic data."""
        # Create a more interesting dataset with some structure
        self.data = np.random.randn(self.n_samples, 10)
        # Create labels based on a nonlinear combination
        decision = (
            0.5 * self.data[:, 0]
            + 0.3 * self.data[:, 1] ** 2
            + 0.2 * np.sin(self.data[:, 2])
            + 0.1 * np.random.randn(self.n_samples)
        )
        self.labels = (decision > 0).astype(int)

    def get_splits(self):
        """Create train/val/test splits."""
        n_train = int(0.7 * self.n_samples)
        n_val = int(0.15 * self.n_samples)

        train_loader = ArrayDataLoader(self.data[:n_train], self.labels[:n_train], batch_size=32)
        val_loader = ArrayDataLoader(
            self.data[n_train : n_train + n_val],
            self.labels[n_train : n_train + n_val],
            batch_size=32,
        )
        test_loader = ArrayDataLoader(
            self.data[n_train + n_val :], self.labels[n_train + n_val :], batch_size=32
        )

        return train_loader, val_loader, test_loader

    def __len__(self):
        return self.n_samples


class ImprovedModel(Model):
    """Slightly better model with momentum."""

    def __init__(self):
        super().__init__()
        # Two-layer network
        self.w1 = np.random.randn(10, 20) * 0.1
        self.b1 = np.zeros(20)
        self.w2 = np.random.randn(20, 2) * 0.1
        self.b2 = np.zeros(2)

        # Momentum terms
        self.vw1 = np.zeros_like(self.w1)
        self.vb1 = np.zeros_like(self.b1)
        self.vw2 = np.zeros_like(self.w2)
        self.vb2 = np.zeros_like(self.b2)

        self.learning_rate = 0.01
        self.momentum = 0.9

    async def forward(self, inputs):
        """Forward pass with ReLU activation."""
        X = inputs["data"]
        y = inputs.get("labels")

        # First layer with ReLU
        z1 = X @ self.w1 + self.b1
        a1 = np.maximum(0, z1)  # ReLU

        # Output layer
        logits = a1 @ self.w2 + self.b2

        # Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # Compute loss and gradients if labels provided
        loss = None
        accuracy = None
        if y is not None:
            # Cross entropy loss
            log_probs = np.log(probs + 1e-8)
            loss = -np.mean(log_probs[np.arange(len(y)), y])

            # Accuracy
            predictions = np.argmax(probs, axis=1)
            accuracy = np.mean(predictions == y)

            # Backpropagation
            batch_size = X.shape[0]

            # Output layer gradients
            dlogits = probs.copy()
            dlogits[np.arange(batch_size), y] -= 1
            dlogits /= batch_size

            dw2 = a1.T @ dlogits
            db2 = np.sum(dlogits, axis=0)

            # Hidden layer gradients
            da1 = dlogits @ self.w2.T
            dz1 = da1 * (z1 > 0)  # ReLU derivative

            dw1 = X.T @ dz1
            db1 = np.sum(dz1, axis=0)

            # Update with momentum
            self.vw1 = self.momentum * self.vw1 - self.learning_rate * dw1
            self.vb1 = self.momentum * self.vb1 - self.learning_rate * db1
            self.vw2 = self.momentum * self.vw2 - self.learning_rate * dw2
            self.vb2 = self.momentum * self.vb2 - self.learning_rate * db2

            self.w1 += self.vw1
            self.b1 += self.vb1
            self.w2 += self.vw2
            self.b2 += self.vb2

        output = ModelOutput(predictions=probs, loss=loss)
        if accuracy is not None:
            output.metrics = {"accuracy": accuracy}

        return output

    def get_parameters(self):
        return {"w1": self.w1, "b1": self.b1, "w2": self.w2, "b2": self.b2}

    def set_parameters(self, params):
        self.w1 = params["w1"]
        self.b1 = params["b1"]
        self.w2 = params["w2"]
        self.b2 = params["b2"]

    async def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, **self.get_parameters())

    async def load(self, path):
        data = np.load(path)
        self.set_parameters({k: data[k] for k in data.files})


async def main():
    """Run ML training with visualization."""
    app = Whiskey()
    app.use(ml_extension)

    # Set up metrics tracking
    metrics_tracker = MetricsTracker()

    # Add multiple visualization handlers
    console_handler = ConsoleMetricsHandler(verbose=True)
    metrics_tracker.add_handler(console_handler)

    # Add TensorBoard handler
    tensorboard_handler = TensorBoardHandler(log_dir="./ml_logs/tensorboard")
    metrics_tracker.add_handler(tensorboard_handler)

    # Try to add rich progress (optional)
    try:
        progress_handler = RichProgressHandler()
        metrics_tracker.add_handler(progress_handler)
    except Exception:
        print("Rich progress not available, using console only")

    # Register metrics tracker with app
    await metrics_tracker.register_with_app(app)

    # Register components
    app.singleton(metrics_tracker)

    @app.ml_dataset("synthetic_dataset")
    class RegisteredDataset(SimpleDataset):
        pass

    @app.ml_model("improved_model")
    class RegisteredModel(ImprovedModel):
        pass

    # Define pipeline with extended training
    @app.ml_pipeline("visualized_pipeline")
    class VisualizedPipeline(MLPipeline):
        dataset = "synthetic_dataset"
        model = "improved_model"
        epochs = 20  # More epochs to see progress
        batch_size = 32
        metrics = ["loss", "accuracy"]

        def __init__(self, context):
            super().__init__(context)
            self.best_val_loss = float("inf")
            self.patience_counter = 0
            self.early_stopping_patience = 5

        async def on_epoch_end(self, epoch: int, metrics: dict[str, float]) -> None:
            """Custom epoch handling with validation."""
            # Simulate validation metrics (in real scenario, would compute on val set)
            val_loss = metrics.get("loss", 0) + 0.1 * np.random.randn()
            val_accuracy = metrics.get("accuracy", 0) - 0.05 + 0.02 * np.random.randn()

            val_metrics = {"loss": max(0, val_loss), "accuracy": min(1.0, max(0, val_accuracy))}

            # Emit validation metrics
            if hasattr(self.context, "app"):
                await self.context.app.emit(
                    "ml.validation.metrics",
                    {
                        "pipeline": self.config.name,
                        "epoch": epoch,
                        "metrics": val_metrics,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            # Early stopping check
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                print(f"   💾 New best model (val_loss: {val_loss:.4f})")
            else:
                self.patience_counter += 1
                if self.patience_counter >= self.early_stopping_patience:
                    print("   🛑 Early stopping triggered")
                    # Would normally stop training here

    # Additional event handlers for custom visualization
    @app.on("ml.validation.metrics")
    async def on_validation_metrics(data):
        # Could update a live dashboard here
        pass

    # Run the pipeline
    print("\n" + "=" * 80)
    print("ML Training with Real-time Visualization")
    print("=" * 80)
    print("\nVisualization features:")
    print("  ✓ Console output with progress tracking")
    print("  ✓ TensorBoard logging (if available)")
    print("  ✓ Rich progress bars (if available)")
    print("  ✓ Real-time metrics updates")
    print("  ✓ Validation tracking")
    print("  ✓ Early stopping monitoring")
    print("\n" + "=" * 80)

    async with app:
        # Run training
        result = await app.ml.run_pipeline("visualized_pipeline")

        # Get final metrics from tracker
        final_metrics = metrics_tracker.get_latest_metrics("visualized_pipeline")
        if final_metrics:
            print(f"\n📊 Final metrics: {final_metrics}")

        # Show how to plot metrics
        print("\n📈 Generating metrics plot...")
        metrics_tracker.plot_metrics("visualized_pipeline", ["loss", "accuracy"])

        print("\n" + "=" * 80)
        print("Visualization Summary")
        print("=" * 80)
        print(f"✓ Training completed with {result.epochs_trained} epochs")
        print("✓ Metrics logged to: ./ml_logs/tensorboard")
        print("✓ Run 'tensorboard --logdir ./ml_logs/tensorboard' to view")
        print(f"✓ Total training time: {result.training_time:.2f}s")


if __name__ == "__main__":
    # Ensure we have required imports
    from datetime import datetime

    asyncio.run(main())
