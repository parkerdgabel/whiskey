# Whiskey ML Extension

A declarative machine learning extension for the Whiskey dependency injection framework. Build ML pipelines with clean, composable abstractions that work with any ML framework.

## Features

- **Framework Agnostic**: Works with PyTorch, TensorFlow, JAX, scikit-learn, and more
- **Declarative Pipelines**: Define ML workflows as simple Python classes
- **Composable Design**: Works standalone or integrates with ETL, SQL, and other extensions
- **Type Safe**: Full typing support for better IDE experience
- **Production Ready**: Built-in experiment tracking, model registry, and deployment support

## Installation

```bash
# Basic installation
pip install whiskey-ml

# With specific ML frameworks
pip install whiskey-ml[pytorch]
pip install whiskey-ml[tensorflow]
pip install whiskey-ml[jax]

# With integrations
pip install whiskey-ml[etl]  # ETL pipeline integration
pip install whiskey-ml[sql]  # SQL feature engineering

# All features
pip install whiskey-ml[all]
```

## Quick Start

### Basic Classification Pipeline

```python
from whiskey import Whiskey
from whiskey_ml import ml_extension, MLPipeline

app = Whiskey()
app.use(ml_extension)

@app.ml_pipeline("iris_classifier")
class IrisClassifier(MLPipeline):
    # Data configuration
    dataset = "iris_dataset"
    batch_size = 32
    
    # Model configuration  
    model = "simple_mlp"
    learning_rate = 0.01
    
    # Training configuration
    epochs = 100
    metrics = ["accuracy", "f1"]

# Run the pipeline
async with app:
    result = await app.ml.run_pipeline("iris_classifier")
    print(f"Final accuracy: {result.test_metrics['accuracy']:.2%}")
```

### Custom Dataset

```python
@app.ml_dataset("custom_dataset")
class CustomDataset(Dataset):
    def __init__(self, data_path: str):
        super().__init__()
        self.data_path = data_path
    
    async def load(self):
        # Load your data
        self.data = np.load(self.data_path)
    
    def get_splits(self):
        # Return train, val, test loaders
        return self._create_loaders()
```

### Custom Model

```python
@app.ml_model("custom_model")
class CustomModel(Model):
    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
    
    async def forward(self, inputs):
        # Model forward pass
        predictions = self._forward_impl(inputs)
        return ModelOutput(predictions=predictions)
```

## Integration with ETL

When the ETL extension is available, ML pipelines can leverage data pipelines:

```python
from whiskey_etl import etl_extension

app = Whiskey()
app.use(etl_extension)
app.use(ml_extension)

@app.ml_pipeline("etl_ml_pipeline")
class ETLMLPipeline(MLPipeline):
    # Use ETL data source
    data_source = "s3_parquet"
    
    # ETL preprocessing
    preprocessing = [
        "validate_schema",
        "clean_outliers", 
        "normalize_features"
    ]
    
    # ML configuration
    model = "xgboost_classifier"
    
    # Save predictions with ETL
    prediction_sink = "postgres_predictions"
```

## LLM Support

```python
@app.ml_pipeline("llm_finetune")
class LLMFinetune(MLPipeline):
    # Base model
    model = "llama2_7b"
    
    # LoRA configuration
    lora_config = {
        "r": 16,
        "target_modules": ["q_proj", "v_proj"],
        "alpha": 32,
    }
    
    # Training
    dataset = "alpaca_clean"
    batch_size = 4
    gradient_accumulation = 8
    learning_rate = 2e-4
    epochs = 3
```

## Distributed Training

```python
@app.ml_pipeline("distributed_training")
class DistributedPipeline(MLPipeline):
    model = "large_transformer"
    
    # Distributed configuration
    trainer = "distributed"
    trainer_config = {
        "strategy": "ddp",  # or "fsdp", "horovod"
        "num_gpus": 4,
        "mixed_precision": True,
    }
```

## Hyperparameter Tuning

```python
@app.ml_pipeline("tuned_model")
class TunedModel(MLPipeline):
    model = "neural_network"
    
    # Define search space
    hyperparameters = {
        "learning_rate": tune.loguniform(1e-4, 1e-1),
        "hidden_size": tune.choice([128, 256, 512]),
        "dropout": tune.uniform(0.1, 0.5),
    }
    
    # Tuning configuration
    tuner = "optuna"
    n_trials = 100
    metric = "val_accuracy"
    mode = "max"
```

## Experiment Tracking

```python
@app.ml_pipeline("tracked_experiment")
class TrackedExperiment(MLPipeline):
    model = "resnet50"
    
    # Experiment configuration
    experiment_name = "image_classification"
    tags = {
        "dataset": "imagenet",
        "architecture": "resnet",
        "version": "v1.0"
    }
    
    # Callbacks for tracking
    async def on_epoch_end(self, epoch, metrics):
        # Custom logging
        await self.context.log_metrics({
            "epoch": epoch,
            **metrics
        })
```

## Model Registry

```python
# After training, register model
@app.ml_pipeline("production_model")
class ProductionModel(MLPipeline):
    model = "optimized_model"
    
    async def on_complete(self, result):
        # Register in model registry
        await self.context.register_model(
            name="sentiment_analyzer",
            version="1.0.0",
            metrics=result.test_metrics,
            artifacts={"model": self.model},
            tags={"production": "true"}
        )
```

## Testing

ML components are easily testable thanks to dependency injection:

```python
@pytest.fixture
async def test_app():
    app = Whiskey()
    app.use(ml_extension)
    return app

async def test_model_training(test_app):
    # Create test dataset
    @test_app.ml_dataset("test_data")
    class TestDataset(Dataset):
        async def load(self):
            self.data = np.random.randn(100, 10)
            self.labels = np.random.randint(0, 2, 100)
    
    # Define test pipeline
    @test_app.ml_pipeline("test_pipeline")
    class TestPipeline(MLPipeline):
        dataset = "test_data"
        model = "simple_mlp"
        epochs = 1
    
    # Run pipeline
    async with test_app:
        result = await test_app.ml.run_pipeline("test_pipeline")
        assert result.trainer_state == "completed"
        assert result.epochs_trained == 1
```

## Configuration

### Environment Variables

```bash
WHISKEY_ML_CACHE_DIR=/path/to/cache
WHISKEY_ML_DEVICE=cuda
WHISKEY_ML_MIXED_PRECISION=true
```

### Configuration File

```python
# ml_config.py
ML_CONFIG = {
    "default_device": "cuda",
    "enable_profiling": True,
    "checkpoint_dir": "./checkpoints",
    "experiment_tracking": {
        "backend": "mlflow",
        "uri": "http://localhost:5000"
    }
}

app.ml.configure(ML_CONFIG)
```

## Best Practices

1. **Use Type Hints**: Always type your pipeline components for better IDE support
2. **Leverage DI**: Use dependency injection for testable, modular components
3. **Compose Pipelines**: Build complex pipelines from simple, reusable parts
4. **Track Experiments**: Always use experiment tracking in production
5. **Version Models**: Use the model registry for deployment

## Advanced Topics

### Custom Trainers

```python
@app.ml_trainer("custom_trainer")
class CustomTrainer(Trainer):
    async def train_step(self, batch, step):
        # Custom training logic
        output = await self.model.forward(batch)
        
        # Custom loss computation
        loss = self.compute_custom_loss(output, batch)
        
        # Update model (framework specific)
        await self.optimizer_step(loss)
        
        return {"loss": loss.item()}
```

### Multi-Modal Models

```python
@app.ml_pipeline("multimodal")
class MultiModalPipeline(MLPipeline):
    # Multiple data sources
    datasets = {
        "image": "image_dataset",
        "text": "text_dataset",
        "tabular": "tabular_dataset"
    }
    
    # Fusion model
    model = "multimodal_fusion"
    
    # Custom data loading
    async def load_data(self):
        # Load and align multiple modalities
        return await self.fuse_modalities()
```

### AutoML

```python
@app.ml_pipeline("automl")
class AutoMLPipeline(MLPipeline):
    dataset = "tabular_data"
    
    # AutoML configuration
    automl_backend = "autogluon"
    time_limit = 3600  # 1 hour
    
    # Let AutoML choose model
    model = "auto"
```

## License

MIT