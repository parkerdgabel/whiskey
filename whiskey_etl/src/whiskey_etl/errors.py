"""ETL-specific error types."""

from typing import Any, Dict, List, Optional


class ETLError(Exception):
    """Base exception for all ETL errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PipelineError(ETLError):
    """Error in pipeline execution."""
    
    def __init__(
        self, 
        pipeline_name: str, 
        message: str, 
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.pipeline_name = pipeline_name
        self.stage = stage


class SourceError(ETLError):
    """Error in data extraction."""
    
    def __init__(self, source_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.source_name = source_name


class TransformError(ETLError):
    """Error in data transformation."""
    
    def __init__(
        self, 
        transform_name: str, 
        message: str, 
        record: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.transform_name = transform_name
        self.record = record


class SinkError(ETLError):
    """Error in data loading."""
    
    def __init__(self, sink_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.sink_name = sink_name


class ValidationError(ETLError):
    """Data validation error."""
    
    def __init__(
        self, 
        message: str, 
        record: Optional[Any] = None,
        errors: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.record = record
        self.errors = errors or []


class SchemaError(ETLError):
    """Schema validation error."""
    
    def __init__(
        self, 
        schema_name: str, 
        message: str, 
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.schema_name = schema_name
        self.field = field