"""Simple example demonstrating ML training with proper scope management.

This example shows how to use Whiskey's built-in scope system for ML workflows:

1. Experiment scope for long-lived experiment tracking
2. Training scope for model and optimizer management  
3. Epoch scope for per-epoch resource management
4. Evaluation scope for validation isolation

The scope system ensures proper resource cleanup and isolation
between different phases of the ML workflow.
"""

import asyncio
import numpy as np
from pathlib import Path

from whiskey import Whiskey
from whiskey_ml import (
    MLPipeline,
    Model,
    ModelOutput,
    Dataset,
    ml_extension,
)
from whiskey_ml.core.dataset import ArrayDataLoader
from whiskey_ml.components.scoped_components import (
    ExperimentLogger,
    ModelCheckpointer,
    EpochMetricsCollector,
    ValidationRunner,
    register_all_scoped_components,
)


# Simple dataset and model
class SimpleDataset(Dataset):
    def __init__(self, n_samples: int = 1000):
        super().__init__()
        self.n_samples = n_samples
        self.data = None
        self.labels = None
    
    async def load(self):
        print("📂 Loading dataset...")
        self.data = np.random.randn(self.n_samples, 10)
        decision = (
            0.5 * self.data[:, 0] + 
            0.3 * self.data[:, 1]**2 + 
            0.2 * np.sin(self.data[:, 2])
        )
        self.labels = (decision > 0).astype(int)
        print(f"   Loaded {self.n_samples} samples")
    
    def get_splits(self):
        n_train = int(0.7 * self.n_samples)
        n_val = int(0.15 * self.n_samples)
        
        train_loader = ArrayDataLoader(
            self.data[:n_train],
            self.labels[:n_train],
            batch_size=32
        )
        val_loader = ArrayDataLoader(
            self.data[n_train:n_train + n_val],
            self.labels[n_train:n_train + n_val],
            batch_size=32
        )
        test_loader = ArrayDataLoader(
            self.data[n_train + n_val:],
            self.labels[n_train + n_val:],
            batch_size=32
        )
        
        return train_loader, val_loader, test_loader
    
    def __len__(self):
        return self.n_samples


class SimpleModel(Model):
    def __init__(self):
        super().__init__()
        print("🧠 Initializing model...")
        
        # Two-layer network
        self.w1 = np.random.randn(10, 20) * 0.1
        self.b1 = np.zeros(20)
        self.w2 = np.random.randn(20, 2) * 0.1
        self.b2 = np.zeros(2)
        
        self.learning_rate = 0.01
    
    async def forward(self, inputs):
        X = inputs["data"]
        y = inputs.get("labels")
        
        # First layer with ReLU
        z1 = X @ self.w1 + self.b1
        a1 = np.maximum(0, z1)
        
        # Output layer with softmax
        logits = a1 @ self.w2 + self.b2
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
            
            # Simple gradient descent
            self._update_weights(X, a1, z1, probs, y)
        
        output = ModelOutput(predictions=probs, loss=loss)
        if accuracy is not None:
            output.metrics = {"accuracy": accuracy}
        
        return output
    
    def _update_weights(self, X, a1, z1, probs, y):
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
        
        # Update weights
        self.w1 -= self.learning_rate * dw1
        self.b1 -= self.learning_rate * db1
        self.w2 -= self.learning_rate * dw2
        self.b2 -= self.learning_rate * db2
    
    async def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2)
        print(f"💾 Model saved to {path}")


class ScopedPipeline(MLPipeline):
    """Pipeline that demonstrates proper scope usage."""
    
    dataset = "simple_dataset"
    model = "simple_model"
    epochs = 6
    batch_size = 32
    metrics = ["loss", "accuracy"]
    
    def __init__(self, context):
        super().__init__(context)
        self.epoch_results = []
    
    async def on_epoch_end(self, epoch: int, metrics: dict[str, float]) -> None:
        """Custom epoch handling with scope-aware components."""
        print(f"\n🔄 Epoch {epoch} completed:")
        print(f"   Metrics: {metrics}")
        
        # Access scoped components
        try:
            # Try to get experiment logger (experiment scope)
            experiment_logger = await self.container.resolve(ExperimentLogger)
            await experiment_logger.log_run_result(
                f"{self.config.name}_epoch_{epoch}", 
                metrics
            )
            
            # Try to get model checkpointer (training scope)
            checkpointer = await self.container.resolve(ModelCheckpointer)
            checkpoint_path = await checkpointer.save_checkpoint(
                self._model, epoch, metrics
            )
            print(f"   Checkpoint saved: {checkpoint_path}")
            
            # Try to get epoch metrics collector (epoch scope)
            metrics_collector = await self.container.resolve(EpochMetricsCollector)
            # Simulate some batch metrics
            for i in range(5):
                metrics_collector.collect_batch_metrics(i, {
                    "loss": metrics.get("loss", 0) + np.random.normal(0, 0.1),
                    "accuracy": metrics.get("accuracy", 0) + np.random.normal(0, 0.05)
                })
            
            epoch_summary = metrics_collector.get_epoch_summary()
            print(f"   Epoch summary: {epoch_summary}")
            
        except Exception as e:
            print(f"   Note: Scoped components not available: {e}")
        
        self.epoch_results.append({
            "epoch": epoch,
            "metrics": metrics,
        })
        
        # Run validation every 2 epochs
        if epoch % 2 == 0:
            await self._run_scoped_validation(epoch)
    
    async def _run_scoped_validation(self, epoch: int) -> None:
        """Run validation using evaluation scope."""
        print(f"🔍 Running validation for epoch {epoch}")
        
        # Run validation in evaluation scope
        async with self.container.scope("evaluation"):
            try:
                validation_runner = await self.container.resolve(ValidationRunner)
                
                # Get validation data (mock)
                _, val_loader, _ = self._dataset.get_splits()
                val_results = await validation_runner.run_validation(
                    self._model, val_loader
                )
                
                print(f"   Validation results: {val_results}")
                
            except Exception as e:
                print(f"   Validation failed: {e}")


async def main():
    """Run simple scoped ML training example."""
    app = Whiskey()
    app.use(ml_extension)
    
    # Register all scoped components
    register_all_scoped_components(app)
    
    print("\n" + "=" * 60)
    print("Simple Scope-Aware ML Training")
    print("=" * 60)
    print("\nUsing Whiskey's built-in scope system:")
    print("  🔬 experiment scope: Long-lived experiment tracking")
    print("  🏋️  training scope: Model and checkpointing")
    print("  🔄 epoch scope: Per-epoch metrics collection")
    print("  🔍 evaluation scope: Validation isolation")
    print("=" * 60)
    
    # Register components
    @app.ml_dataset("simple_dataset")
    class RegisteredDataset(SimpleDataset):
        pass
    
    @app.ml_model("simple_model")
    class RegisteredModel(SimpleModel):
        pass
    
    @app.ml_pipeline("scoped_pipeline")
    class RegisteredPipeline(ScopedPipeline):
        pass
    
    async with app:
        print("\n🚀 Starting scoped training...")
        
        # The pipeline will automatically use scopes for resource management
        result = await app.ml.run_pipeline("scoped_pipeline")
        
        print("\n" + "=" * 60)
        print("Training Completed!")
        print("=" * 60)
        print(f"✓ Epochs trained: {result.epochs_trained}")
        print(f"✓ Training time: {result.training_time:.2f}s")
        print(f"✓ All scopes were properly managed and cleaned up")
        
        # Demonstrate manual scope usage
        print("\n🔧 Demonstrating manual scope usage...")
        
        # Use experiment scope directly
        async with app.container.scope("experiment"):
            print("   🔬 In experiment scope")
            exp_logger = await app.container.resolve(ExperimentLogger)
            await exp_logger.log_experiment_start({"manual": True, "demo": "scope_usage"})
            
            # Use training scope within experiment
            async with app.container.scope("training"):
                print("   🏋️ In training scope")
                checkpointer = await app.container.resolve(ModelCheckpointer)
                
                # Use epoch scope within training
                for epoch in range(2):
                    async with app.container.scope("epoch"):
                        print(f"      🔄 In epoch {epoch} scope")
                        metrics_collector = await app.container.resolve(EpochMetricsCollector)
                        
                        # Simulate batch processing
                        for batch_idx in range(3):
                            metrics_collector.collect_batch_metrics(
                                batch_idx, 
                                {"loss": 0.5 - (epoch * 0.1) + (batch_idx * 0.01)}
                            )
                        
                        # Get epoch summary
                        summary = metrics_collector.get_epoch_summary()
                        print(f"         📊 Epoch {epoch}: {summary}")
                
                print("      🏋️ Training scope cleanup...")
            print("   🔬 Experiment scope cleanup...")
        
        print("\n✅ Manual scope demonstration completed!")
        print("All resources were properly managed using Whiskey's scope system.")


if __name__ == "__main__":
    asyncio.run(main())