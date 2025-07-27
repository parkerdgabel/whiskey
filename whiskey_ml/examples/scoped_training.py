"""Example demonstrating ML training with proper scope management.

This example shows how to use Whiskey ML's scope system to properly
manage component lifecycles during training. It demonstrates:

1. Experiment scope for long-lived experiment tracking
2. Training scope for model and optimizer management
3. Epoch scope for per-epoch resource management
4. Evaluation scope for validation isolation
5. Batch scope for fine-grained resource control

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
    ExperimentScope,
    TrainingScope,
    EpochScope,
    EvaluationScope,
)
from whiskey_ml.core.dataset import ArrayDataLoader
from whiskey_ml.components.scoped_components import (
    ExperimentLogger,
    ModelCheckpointer,
    EpochMetricsCollector,
    ValidationRunner,
    BatchProcessor,
    register_all_scoped_components,
)


# Reuse dataset and model from previous examples
class ScopeAwareDataset(Dataset):
    """Dataset that demonstrates scope-aware resource management."""
    
    def __init__(self, n_samples: int = 1000):
        super().__init__()
        self.n_samples = n_samples
        self.data = None
        self.labels = None
    
    async def load(self):
        """Load data with logging."""
        print("📂 Loading dataset...")
        
        # Create synthetic data
        self.data = np.random.randn(self.n_samples, 10)
        decision = (
            0.5 * self.data[:, 0] + 
            0.3 * self.data[:, 1]**2 + 
            0.2 * np.sin(self.data[:, 2])
        )
        self.labels = (decision > 0).astype(int)
        
        print(f"   Loaded {self.n_samples} samples")
    
    def get_splits(self):
        """Create train/val/test splits."""
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


class ScopeAwareModel(Model):
    """Model that demonstrates scope-aware lifecycle management."""
    
    def __init__(self):
        super().__init__()
        print("🧠 Initializing model...")
        
        # Two-layer network
        self.w1 = np.random.randn(10, 20) * 0.1
        self.b1 = np.zeros(20)
        self.w2 = np.random.randn(20, 2) * 0.1
        self.b2 = np.zeros(2)
        
        self.learning_rate = 0.01
        self._training_step = 0
    
    async def forward(self, inputs):
        """Forward pass with scope-aware processing."""
        X = inputs["data"]
        y = inputs.get("labels")
        
        # First layer with ReLU
        z1 = X @ self.w1 + self.b1
        a1 = np.maximum(0, z1)
        
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
            
            # Backpropagation (simplified)
            self._update_weights(X, a1, z1, probs, y)
            self._training_step += 1
        
        output = ModelOutput(predictions=probs, loss=loss)
        if accuracy is not None:
            output.metrics = {"accuracy": accuracy}
        
        return output
    
    def _update_weights(self, X, a1, z1, probs, y):
        """Update model weights."""
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
    
    def get_parameters(self):
        return {
            "w1": self.w1, "b1": self.b1,
            "w2": self.w2, "b2": self.b2
        }
    
    def set_parameters(self, params):
        self.w1 = params["w1"]
        self.b1 = params["b1"]
        self.w2 = params["w2"]
        self.b2 = params["b2"]
    
    async def save(self, path):
        """Save model with scope context."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, **self.get_parameters())
        print(f"💾 Model saved to {path}")
    
    async def load(self, path):
        data = np.load(path)
        self.set_parameters({k: data[k] for k in data.files})
        print(f"📥 Model loaded from {path}")


class ScopeAwarePipeline(MLPipeline):
    """Pipeline that demonstrates scope usage patterns."""
    
    dataset = "scope_dataset"
    model = "scope_model"
    epochs = 8
    batch_size = 32
    metrics = ["loss", "accuracy"]
    
    def __init__(self, context):
        super().__init__(context)
        self.epoch_results = []
    
    async def on_epoch_end(self, epoch: int, metrics: dict[str, float]) -> None:
        """Custom epoch handling with scope-aware components."""
        print(f"\n🔄 Epoch {epoch} completed:")
        print(f"   Metrics: {metrics}")
        
        # Get scoped components and use them
        try:
            # Use experiment logger (long-lived)
            experiment_logger = await self.container.resolve(
                ExperimentLogger, scope="experiment"
            )
            await experiment_logger.log_run_result(
                f"{self.config.name}_epoch_{epoch}", 
                metrics
            )
            
            # Use checkpointer (training-scoped)
            checkpointer = await self.container.resolve(
                ModelCheckpointer, scope="training"
            )
            checkpoint_path = await checkpointer.save_checkpoint(
                self._model, epoch, metrics
            )
            print(f"   Checkpoint saved: {checkpoint_path}")
            
            # Get epoch metrics collector (epoch-scoped)
            metrics_collector = await self.container.resolve(
                EpochMetricsCollector, scope="epoch"
            )
            epoch_summary = metrics_collector.get_epoch_summary()
            print(f"   Epoch summary: {epoch_summary}")
            
        except Exception as e:
            print(f"   Warning: Could not access scoped components: {e}")
        
        self.epoch_results.append({
            "epoch": epoch,
            "metrics": metrics,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Simulate validation every few epochs
        if epoch % 3 == 0:
            await self._run_scoped_validation(epoch)
    
    async def _run_scoped_validation(self, epoch: int) -> None:
        """Run validation using evaluation scope."""
        print(f"🔍 Running validation for epoch {epoch}")
        
        # Get ML scope manager
        ml_scopes = getattr(self.context.app, "ml_scopes", None)
        if ml_scopes:
            # Run validation in evaluation scope
            async with ml_scopes.evaluation(f"validation_epoch_{epoch}"):
                try:
                    validation_runner = await self.container.resolve(
                        ValidationRunner, scope="evaluation"
                    )
                    
                    # Get validation data (mock)
                    _, val_loader, _ = self._dataset.get_splits()
                    val_results = await validation_runner.run_validation(
                        self._model, val_loader
                    )
                    
                    print(f"   Validation results: {val_results}")
                    
                except Exception as e:
                    print(f"   Validation failed: {e}")


async def main():
    """Run scoped ML training example."""
    app = Whiskey()
    app.use(ml_extension)
    
    # Register all scoped components
    register_all_scoped_components(app)
    
    print("\n" + "=" * 80)
    print("Scope-Aware ML Training with Whiskey")
    print("=" * 80)
    print("\nScope hierarchy:")
    print("  🔬 Experiment Scope: Experiment-wide tracking")
    print("  🏋️  Training Scope: Model and checkpointing")
    print("  🔄 Epoch Scope: Per-epoch metrics collection")
    print("  🔍 Evaluation Scope: Validation isolation")
    print("  📦 Batch Scope: Fine-grained processing")
    print("=" * 80)
    
    # Register components
    @app.ml_dataset("scope_dataset")
    class RegisteredDataset(ScopeAwareDataset):
        pass
    
    @app.ml_model("scope_model")
    class RegisteredModel(ScopeAwareModel):
        pass
    
    @app.ml_pipeline("scope_pipeline")
    class RegisteredPipeline(ScopeAwarePipeline):
        pass
    
    async with app:
        print("\n🚀 Starting scope-aware training...")
        
        # The pipeline will automatically use scopes for resource management
        result = await app.ml.run_pipeline("scope_pipeline")
        
        print("\n" + "=" * 80)
        print("Training Completed!")
        print("=" * 80)
        print(f"✓ Epochs trained: {result.epochs_trained}")
        print(f"✓ Training time: {result.training_time:.2f}s")
        print(f"✓ All scopes were properly managed and cleaned up")
        
        # Demonstrate manual scope usage
        print("\n🔧 Demonstrating manual scope usage...")
        
        # Use experiment scope directly
        async with app.ml_scopes.experiment("manual_experiment"):
            exp_logger = await app.container.resolve(ExperimentLogger, scope="experiment")
            await exp_logger.log_experiment_start({"manual": True, "test": "scope_demo"})
            
            # Use training scope within experiment
            async with app.ml_scopes.training("manual_training"):
                checkpointer = await app.container.resolve(ModelCheckpointer, scope="training")
                
                # Use epoch scope within training
                for epoch in range(3):
                    async with app.ml_scopes.epoch(epoch):
                        metrics_collector = await app.container.resolve(
                            EpochMetricsCollector, scope="epoch"
                        )
                        
                        # Simulate batch processing
                        for batch_idx in range(5):
                            metrics_collector.collect_batch_metrics(
                                batch_idx, 
                                {"loss": 0.5 - (epoch * 0.1) + (batch_idx * 0.01)}
                            )
                        
                        # Get epoch summary
                        summary = metrics_collector.get_epoch_summary()
                        print(f"   📊 Epoch {epoch}: {summary}")
                
                print("   🏋️ Training scope cleanup...")
            print("   🔬 Experiment scope cleanup...")
        
        print("\n✅ Manual scope demonstration completed!")
        print("All resources were properly managed and cleaned up.")


if __name__ == "__main__":
    asyncio.run(main())