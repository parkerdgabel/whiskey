"""Model abstractions for ML pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class ModelType(Enum):
    """Types of ML models."""

    CLASSIFIER = "classifier"
    REGRESSOR = "regressor"
    GENERATOR = "generator"
    ENCODER = "encoder"
    DECODER = "decoder"
    TRANSFORMER = "transformer"
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    """Configuration for models."""

    # Model architecture
    model_type: ModelType = ModelType.CUSTOM
    input_shape: tuple[int, ...] | None = None
    output_shape: tuple[int, ...] | None = None
    hidden_sizes: list[int] | None = None

    # Training configuration
    learning_rate: float = 0.001
    weight_decay: float = 0.0
    dropout: float = 0.0

    # Optimization
    optimizer: str = "adam"
    scheduler: str | None = None
    gradient_clip: float | None = None

    # Device configuration
    device: str = "auto"  # auto, cpu, cuda, mps, tpu
    mixed_precision: bool = False
    compile_model: bool = False

    # Checkpointing
    checkpoint_dir: str | Path | None = None
    save_every_n_steps: int | None = None
    keep_last_n_checkpoints: int = 3


@dataclass
class ModelOutput:
    """Standard output from model forward pass."""

    predictions: Any  # Model predictions (logits, probabilities, etc.)
    loss: float | None = None  # Loss value if computed
    metrics: dict[str, float] | None = None  # Additional metrics
    hidden_states: Any | None = None  # Hidden representations
    attention_weights: Any | None = None  # Attention weights (if applicable)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "predictions": self.predictions,
            "loss": self.loss,
            "metrics": self.metrics or {},
        }


class Model(ABC):
    """Base model abstraction - framework agnostic."""

    def __init__(self, config: ModelConfig | None = None):
        """Initialize model.

        Args:
            config: Model configuration
        """
        self.config = config or ModelConfig()
        self._device = None
        self._compiled = False
        self._framework = None  # Set by framework adapter

    @abstractmethod
    async def forward(self, inputs: dict[str, Any]) -> ModelOutput:
        """Forward pass through the model.

        Args:
            inputs: Input batch dictionary

        Returns:
            ModelOutput with predictions and optional loss/metrics
        """
        pass

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        """Get model parameters.

        Returns:
            Dictionary of parameter name to parameter
        """
        pass

    @abstractmethod
    def set_parameters(self, parameters: dict[str, Any]) -> None:
        """Set model parameters.

        Args:
            parameters: Dictionary of parameter name to parameter
        """
        pass

    @abstractmethod
    async def save(self, path: str | Path) -> None:
        """Save model to disk.

        Args:
            path: Path to save model
        """
        pass

    @abstractmethod
    async def load(self, path: str | Path) -> None:
        """Load model from disk.

        Args:
            path: Path to load model from
        """
        pass

    def to_device(self, device: str) -> Model:
        """Move model to device.

        Args:
            device: Device name (cpu, cuda, mps, tpu)

        Returns:
            Self for chaining
        """
        self._device = device
        return self

    def compile(self) -> Model:
        """Compile model for faster execution.

        Returns:
            Self for chaining
        """
        self._compiled = True
        return self

    def count_parameters(self) -> int:
        """Count total number of parameters.

        Returns:
            Total parameter count
        """
        total = 0
        for param in self.get_parameters().values():
            if hasattr(param, "numel"):
                total += param.numel()
            elif isinstance(param, np.ndarray):
                total += param.size
            else:
                # Fallback for other frameworks
                total += 1
        return total

    def summary(self) -> str:
        """Get model summary.

        Returns:
            String summary of model architecture
        """
        return (
            f"{self.__class__.__name__}(\n"
            f"  parameters: {self.count_parameters():,}\n"
            f"  device: {self._device or 'cpu'}\n"
            f"  compiled: {self._compiled}\n"
            f")"
        )


class FrameworkModel(Model):
    """Wrapper for framework-specific models."""

    def __init__(
        self,
        model: Any,
        framework: str,
        config: ModelConfig | None = None,
    ):
        """Initialize framework model wrapper.

        Args:
            model: Framework-specific model instance
            framework: Framework name (pytorch, tensorflow, jax, etc.)
            config: Model configuration
        """
        super().__init__(config)
        self.model = model
        self._framework = framework

    async def forward(self, inputs: dict[str, Any]) -> ModelOutput:
        """Forward pass using framework model."""
        # Framework-specific forward implementation
        if self._framework == "pytorch":
            return await self._pytorch_forward(inputs)
        elif self._framework == "tensorflow":
            return await self._tensorflow_forward(inputs)
        elif self._framework == "jax":
            return await self._jax_forward(inputs)
        else:
            raise ValueError(f"Unsupported framework: {self._framework}")

    async def _pytorch_forward(self, inputs: dict[str, Any]) -> ModelOutput:
        """PyTorch forward pass."""
        import torch

        # Move inputs to device
        if self._device:
            inputs = {
                k: v.to(self._device) if isinstance(v, torch.Tensor) else v
                for k, v in inputs.items()
            }

        # Forward pass
        with torch.no_grad() if not self.model.training else torch.enable_grad():
            outputs = self.model(**inputs)

        # Handle different output types
        if isinstance(outputs, dict):
            return ModelOutput(
                predictions=outputs.get("logits", outputs.get("predictions")),
                loss=outputs.get("loss"),
                hidden_states=outputs.get("hidden_states"),
                attention_weights=outputs.get("attentions"),
            )
        elif isinstance(outputs, tuple):
            return ModelOutput(
                predictions=outputs[0], loss=outputs[1] if len(outputs) > 1 else None
            )
        else:
            return ModelOutput(predictions=outputs)

    async def _tensorflow_forward(self, inputs: dict[str, Any]) -> ModelOutput:
        """TensorFlow forward pass."""

        # Forward pass
        outputs = self.model(inputs, training=False)

        return ModelOutput(predictions=outputs)

    async def _jax_forward(self, inputs: dict[str, Any]) -> ModelOutput:
        """JAX forward pass."""

        # Forward pass
        outputs = self.model.apply(self.model.params, inputs)

        return ModelOutput(predictions=outputs)

    def get_parameters(self) -> dict[str, Any]:
        """Get model parameters based on framework."""
        if self._framework == "pytorch":
            return dict(self.model.named_parameters())
        elif self._framework == "tensorflow":
            return {var.name: var for var in self.model.trainable_variables}
        elif self._framework == "jax":
            return self.model.params
        else:
            return {}

    def set_parameters(self, parameters: dict[str, Any]) -> None:
        """Set model parameters based on framework."""
        if self._framework == "pytorch":
            self.model.load_state_dict(parameters)
        elif self._framework == "tensorflow":
            for var in self.model.trainable_variables:
                if var.name in parameters:
                    var.assign(parameters[var.name])
        elif self._framework == "jax":
            self.model.params = parameters

    async def save(self, path: str | Path) -> None:
        """Save model based on framework."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self._framework == "pytorch":
            import torch

            torch.save(self.model.state_dict(), path)
        elif self._framework == "tensorflow":
            self.model.save(path)
        elif self._framework == "jax":
            import pickle

            with open(path, "wb") as f:
                pickle.dump(self.model.params, f)

    async def load(self, path: str | Path) -> None:
        """Load model based on framework."""
        path = Path(path)

        if self._framework == "pytorch":
            import torch

            self.model.load_state_dict(torch.load(path))
        elif self._framework == "tensorflow":
            import tensorflow as tf

            self.model = tf.keras.models.load_model(path)
        elif self._framework == "jax":
            import pickle

            with open(path, "rb") as f:
                self.model.params = pickle.load(f)


class EnsembleModel(Model):
    """Ensemble of multiple models."""

    def __init__(
        self,
        models: list[Model],
        aggregation: str = "mean",
        weights: list[float] | None = None,
        config: ModelConfig | None = None,
    ):
        """Initialize ensemble model.

        Args:
            models: List of models to ensemble
            aggregation: Aggregation method (mean, weighted, vote)
            weights: Optional weights for weighted aggregation
            config: Model configuration
        """
        super().__init__(config)
        self.models = models
        self.aggregation = aggregation
        self.weights = weights or [1.0 / len(models)] * len(models)

    async def forward(self, inputs: dict[str, Any]) -> ModelOutput:
        """Forward pass through all models and aggregate."""
        outputs = []

        # Get predictions from all models
        for model in self.models:
            output = await model.forward(inputs)
            outputs.append(output)

        # Aggregate predictions
        if self.aggregation == "mean":
            predictions = np.mean([o.predictions for o in outputs], axis=0)
        elif self.aggregation == "weighted":
            predictions = np.average([o.predictions for o in outputs], weights=self.weights, axis=0)
        elif self.aggregation == "vote":
            # For classification - majority vote
            predictions = np.array([o.predictions for o in outputs])
            predictions = np.argmax(np.sum(predictions, axis=0), axis=-1)
        else:
            raise ValueError(f"Unknown aggregation: {self.aggregation}")

        return ModelOutput(predictions=predictions)

    def get_parameters(self) -> dict[str, Any]:
        """Get all model parameters."""
        params = {}
        for i, model in enumerate(self.models):
            for name, param in model.get_parameters().items():
                params[f"model_{i}_{name}"] = param
        return params

    def set_parameters(self, parameters: dict[str, Any]) -> None:
        """Set all model parameters."""
        for i, model in enumerate(self.models):
            model_params = {}
            prefix = f"model_{i}_"
            for name, param in parameters.items():
                if name.startswith(prefix):
                    model_params[name[len(prefix) :]] = param
            model.set_parameters(model_params)

    async def save(self, path: str | Path) -> None:
        """Save all models."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        for i, model in enumerate(self.models):
            await model.save(path / f"model_{i}")

    async def load(self, path: str | Path) -> None:
        """Load all models."""
        path = Path(path)

        for i, model in enumerate(self.models):
            await model.load(path / f"model_{i}")
