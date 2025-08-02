"""Metrics abstractions for ML pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class MetricMode(Enum):
    """How metrics should be optimized."""

    MIN = "min"  # Lower is better (e.g., loss, error)
    MAX = "max"  # Higher is better (e.g., accuracy, F1)


@dataclass
class MetricResult:
    """Result from metric computation."""

    name: str
    value: float
    mode: MetricMode = MetricMode.MAX
    confidence_interval: tuple[float, float] | None = None
    metadata: dict[str, Any] | None = None

    def is_better_than(self, other: MetricResult) -> bool:
        """Check if this result is better than another."""
        if self.mode == MetricMode.MAX:
            return self.value > other.value
        else:
            return self.value < other.value


class Metric(ABC):
    """Base metric abstraction."""

    def __init__(
        self,
        name: str,
        mode: MetricMode = MetricMode.MAX,
        compute_on_step: bool = True,
    ):
        """Initialize metric.

        Args:
            name: Metric name
            mode: Optimization mode
            compute_on_step: Whether to compute metric on each step
        """
        self.name = name
        self.mode = mode
        self.compute_on_step = compute_on_step
        self.reset()

    @abstractmethod
    def update(self, predictions: Any, targets: Any) -> None:
        """Update metric state with new predictions and targets.

        Args:
            predictions: Model predictions
            targets: Ground truth targets
        """
        pass

    @abstractmethod
    def compute(self) -> float:
        """Compute the metric value.

        Returns:
            Metric value
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset metric state."""
        pass

    def __call__(self, predictions: Any, targets: Any) -> float | None:
        """Update and optionally compute metric.

        Args:
            predictions: Model predictions
            targets: Ground truth targets

        Returns:
            Metric value if compute_on_step, else None
        """
        self.update(predictions, targets)

        if self.compute_on_step:
            return self.compute()
        return None


class Accuracy(Metric):
    """Accuracy metric for classification."""

    def __init__(
        self,
        threshold: float = 0.5,
        top_k: int | None = None,
        name: str = "accuracy",
    ):
        """Initialize accuracy metric.

        Args:
            threshold: Threshold for binary classification
            top_k: Top-k accuracy (e.g., top_k=5 for top-5 accuracy)
            name: Metric name
        """
        super().__init__(name, MetricMode.MAX)
        self.threshold = threshold
        self.top_k = top_k
        self.correct = 0
        self.total = 0

    def update(self, predictions: Any, targets: Any) -> None:
        """Update accuracy state."""
        predictions = np.array(predictions)
        targets = np.array(targets)

        if predictions.ndim == 1 or predictions.shape[1] == 1:
            # Binary classification
            if predictions.ndim == 2:
                predictions = predictions.squeeze()
            pred_labels = (predictions > self.threshold).astype(int)
        else:
            # Multi-class classification
            if self.top_k:
                # Top-k accuracy
                top_k_preds = np.argsort(predictions, axis=1)[:, -self.top_k :]
                correct = np.any(top_k_preds == targets[:, None], axis=1)
                self.correct += np.sum(correct)
            else:
                # Standard accuracy
                pred_labels = np.argmax(predictions, axis=1)
                self.correct += np.sum(pred_labels == targets)

            self.total += len(targets)
            return

        self.correct += np.sum(pred_labels == targets)
        self.total += len(targets)

    def compute(self) -> float:
        """Compute accuracy."""
        if self.total == 0:
            return 0.0
        return self.correct / self.total

    def reset(self) -> None:
        """Reset state."""
        self.correct = 0
        self.total = 0


class Loss(Metric):
    """Loss metric (tracks average loss)."""

    def __init__(self, name: str = "loss"):
        """Initialize loss metric."""
        super().__init__(name, MetricMode.MIN)
        self.sum_loss = 0.0
        self.count = 0

    def update(self, predictions: Any, targets: Any = None) -> None:
        """Update loss state.

        Note: For loss, predictions is actually the loss value
        """
        if isinstance(predictions, list | np.ndarray):
            self.sum_loss += np.sum(predictions)
            self.count += len(predictions)
        else:
            self.sum_loss += float(predictions)
            self.count += 1

    def compute(self) -> float:
        """Compute average loss."""
        if self.count == 0:
            return 0.0
        return self.sum_loss / self.count

    def reset(self) -> None:
        """Reset state."""
        self.sum_loss = 0.0
        self.count = 0


class F1Score(Metric):
    """F1 score for classification."""

    def __init__(
        self,
        average: str = "binary",
        threshold: float = 0.5,
        name: str = "f1",
    ):
        """Initialize F1 score.

        Args:
            average: Averaging method (binary, micro, macro, weighted)
            threshold: Threshold for binary classification
            name: Metric name
        """
        super().__init__(name, MetricMode.MAX)
        self.average = average
        self.threshold = threshold
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0
        self.class_scores = {}

    def update(self, predictions: Any, targets: Any) -> None:
        """Update F1 state."""
        predictions = np.array(predictions)
        targets = np.array(targets)

        if self.average == "binary":
            # Binary classification
            if predictions.ndim == 2:
                predictions = predictions[:, 1]  # Assume positive class
            pred_labels = (predictions > self.threshold).astype(int)

            self.true_positives += np.sum((pred_labels == 1) & (targets == 1))
            self.false_positives += np.sum((pred_labels == 1) & (targets == 0))
            self.false_negatives += np.sum((pred_labels == 0) & (targets == 1))
        else:
            # Multi-class - store for later computation
            pred_labels = predictions if predictions.ndim == 1 else np.argmax(predictions, axis=1)

            for i in range(len(targets)):
                key = (pred_labels[i], targets[i])
                self.class_scores[key] = self.class_scores.get(key, 0) + 1

    def compute(self) -> float:
        """Compute F1 score."""
        if self.average == "binary":
            precision = self.true_positives / (self.true_positives + self.false_positives + 1e-8)
            recall = self.true_positives / (self.true_positives + self.false_negatives + 1e-8)
            f1 = 2 * (precision * recall) / (precision + recall + 1e-8)
            return f1
        else:
            # Implement macro/micro/weighted averaging
            # This is a simplified version
            return 0.0  # Placeholder

    def reset(self) -> None:
        """Reset state."""
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0
        self.class_scores = {}


class MeanSquaredError(Metric):
    """Mean squared error for regression."""

    def __init__(self, name: str = "mse"):
        """Initialize MSE metric."""
        super().__init__(name, MetricMode.MIN)
        self.sum_squared_error = 0.0
        self.count = 0

    def update(self, predictions: Any, targets: Any) -> None:
        """Update MSE state."""
        predictions = np.array(predictions)
        targets = np.array(targets)

        squared_errors = (predictions - targets) ** 2
        self.sum_squared_error += np.sum(squared_errors)
        self.count += len(targets)

    def compute(self) -> float:
        """Compute MSE."""
        if self.count == 0:
            return 0.0
        return self.sum_squared_error / self.count

    def reset(self) -> None:
        """Reset state."""
        self.sum_squared_error = 0.0
        self.count = 0


class MetricCollection:
    """Collection of metrics."""

    def __init__(self, metrics: list[Metric] | None = None):
        """Initialize metric collection.

        Args:
            metrics: List of metrics
        """
        self.metrics = {}
        if metrics:
            for metric in metrics:
                self.add(metric)

    def add(self, metric: Metric) -> None:
        """Add a metric to the collection.

        Args:
            metric: Metric to add
        """
        self.metrics[metric.name] = metric

    def update(self, predictions: Any, targets: Any, loss: float | None = None) -> dict[str, float]:
        """Update all metrics.

        Args:
            predictions: Model predictions
            targets: Ground truth targets
            loss: Optional loss value

        Returns:
            Dictionary of metric values
        """
        results = {}

        # Update regular metrics
        for name, metric in self.metrics.items():
            if name != "loss":
                value = metric(predictions, targets)
                if value is not None:
                    results[name] = value

        # Update loss if provided
        if loss is not None and "loss" in self.metrics:
            loss_metric = self.metrics["loss"]
            loss_metric.update(loss)
            results["loss"] = loss_metric.compute()

        return results

    def compute(self) -> dict[str, float]:
        """Compute all metrics.

        Returns:
            Dictionary of metric values
        """
        results = {}
        for name, metric in self.metrics.items():
            results[name] = metric.compute()
        return results

    def reset(self) -> None:
        """Reset all metrics."""
        for metric in self.metrics.values():
            metric.reset()

    def __getitem__(self, name: str) -> Metric:
        """Get metric by name."""
        return self.metrics[name]

    def __contains__(self, name: str) -> bool:
        """Check if metric exists."""
        return name in self.metrics

    @classmethod
    def from_names(cls, names: list[str]) -> MetricCollection:
        """Create collection from metric names.

        Args:
            names: List of metric names

        Returns:
            MetricCollection with requested metrics
        """
        metrics = []

        for name in names:
            if name == "accuracy":
                metrics.append(Accuracy())
            elif name == "loss":
                metrics.append(Loss())
            elif name == "f1":
                metrics.append(F1Score())
            elif name == "mse":
                metrics.append(MeanSquaredError())
            elif name.startswith("top"):
                # e.g., top5_accuracy
                k = int(name.split("_")[0][3:])
                metrics.append(Accuracy(top_k=k, name=name))
            else:
                raise ValueError(f"Unknown metric: {name}")

        return cls(metrics)
