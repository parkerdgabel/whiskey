"""Example demonstrating event-driven ML training with Whiskey."""

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


# Simple dataset implementation
class SimpleDataset(Dataset):
    """Simple synthetic dataset."""

    def __init__(self, n_samples: int = 1000):
        super().__init__()
        self.n_samples = n_samples
        self.data = None
        self.labels = None

    async def load(self):
        """Generate synthetic data."""
        self.data = np.random.randn(self.n_samples, 10)
        self.labels = (self.data[:, 0] + self.data[:, 1] > 0).astype(int)
        print(f"📊 Loaded dataset with {self.n_samples} samples")

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


# Simple model implementation
class SimpleModel(Model):
    """Simple linear model."""

    def __init__(self):
        super().__init__()
        self.weights = np.random.randn(10, 2) * 0.01
        self.bias = np.zeros(2)

    async def forward(self, inputs):
        """Forward pass."""
        X = inputs["data"]
        y = inputs.get("labels")

        # Linear transformation
        logits = X @ self.weights + self.bias

        # Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # Compute loss if labels provided
        loss = None
        if y is not None:
            # Cross entropy loss
            log_probs = np.log(probs + 1e-8)
            loss = -np.mean(log_probs[np.arange(len(y)), y])

            # Simple gradient descent update (for demo)
            self.weights -= 0.01 * X.T @ (probs - np.eye(2)[y])
            self.bias -= 0.01 * np.mean(probs - np.eye(2)[y], axis=0)

        return ModelOutput(predictions=probs, loss=loss)

    def get_parameters(self):
        return {"weights": self.weights, "bias": self.bias}

    def set_parameters(self, params):
        self.weights = params["weights"]
        self.bias = params["bias"]

    async def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, weights=self.weights, bias=self.bias)

    async def load(self, path):
        data = np.load(path)
        self.weights = data["weights"]
        self.bias = data["bias"]


async def main():
    """Run event-driven ML training example."""
    app = Whiskey()
    app.use(ml_extension)

    # Event tracking
    events_log = []

    # Register event handlers
    @app.on("ml.pipeline.started")
    async def on_pipeline_started(data):
        print(f"\n🚀 Pipeline started: {data['name']}")
        print(f"   Model: {data['config']['model']}")
        print(f"   Dataset: {data['config']['dataset']}")
        print(f"   Epochs: {data['config']['epochs']}")
        events_log.append(("started", data))

    @app.on("ml.pipeline.state_changed")
    async def on_state_changed(data):
        print(f"📍 State: {data['state']} (from {data['previous_state']})")
        events_log.append(("state_changed", data))

    @app.on("ml.training.metrics")
    async def on_metrics(data):
        epoch = data["epoch"]
        metrics = data["metrics"]
        metrics_str = ", ".join(f"{k}: {v:.4f}" for k, v in metrics.items())
        print(f"📈 Epoch {epoch + 1}: {metrics_str}")
        events_log.append(("metrics", data))

    @app.on("ml.pipeline.completed")
    async def on_pipeline_completed(data):
        print(f"\n✅ Pipeline completed: {data['name']}")
        print(f"   Epochs trained: {data['result']['epochs_trained']}")
        print(f"   Training time: {data['result']['training_time']:.2f}s")
        if data["result"]["test_metrics"]:
            print("   Test metrics:")
            for metric, value in data["result"]["test_metrics"].items():
                print(f"     - {metric}: {value:.4f}")
        events_log.append(("completed", data))

    @app.on("ml.pipeline.failed")
    async def on_pipeline_failed(data):
        print(f"\n❌ Pipeline failed: {data['name']}")
        print(f"   Error: {data['error']}")
        events_log.append(("failed", data))

    # Wildcard handler for all ML events
    @app.on("ml.*")
    async def on_any_ml_event(data):
        # Could log to file, send to monitoring service, etc.
        pass

    # Register components
    @app.ml_dataset("simple_dataset")
    class RegisteredDataset(SimpleDataset):
        pass

    @app.ml_model("simple_model")
    class RegisteredModel(SimpleModel):
        pass

    # Define pipeline with event emission
    @app.ml_pipeline("event_driven_pipeline")
    class EventDrivenPipeline(MLPipeline):
        dataset = "simple_dataset"
        model = "simple_model"
        epochs = 5
        batch_size = 32
        metrics = ["loss", "accuracy"]

        # Custom lifecycle hooks that work with events
        async def on_start(self):
            await super().on_start()
            print("\n" + "=" * 60)
            print("Event-Driven ML Training Example")
            print("=" * 60)

        async def on_complete(self, result):
            await super().on_complete(result)
            print("\n" + "=" * 60)
            print("Training Summary")
            print("=" * 60)
            print(f"Total events emitted: {len(events_log)}")

            # Count event types
            event_counts = {}
            for event_type, _ in events_log:
                event_counts[event_type] = event_counts.get(event_type, 0) + 1

            print("\nEvent counts:")
            for event_type, count in event_counts.items():
                print(f"  - {event_type}: {count}")

    # Run the pipeline
    async with app:
        await app.ml.run_pipeline("event_driven_pipeline")

        # Show how events can be used for monitoring
        print("\n" + "=" * 60)
        print("Event-Driven Monitoring Benefits:")
        print("=" * 60)
        print("✓ Real-time training progress tracking")
        print("✓ Automatic metric collection and logging")
        print("✓ Easy integration with monitoring tools")
        print("✓ Decoupled visualization and alerts")
        print("✓ Extensible event handling")


if __name__ == "__main__":
    asyncio.run(main())
