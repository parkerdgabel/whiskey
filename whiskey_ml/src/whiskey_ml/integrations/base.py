"""Base integration functionality."""

from __future__ import annotations

import importlib
from typing import Any, Dict, Optional

from whiskey import Container

from whiskey_ml.core.pipeline import MLContext


class ExtensionIntegration:
    """Detects and integrates with other Whiskey extensions."""
    
    def __init__(self, container: Container):
        """Initialize extension integration.
        
        Args:
            container: Whiskey container
        """
        self.container = container
        self._integrations = {}
        self._detect_extensions()
    
    def _detect_extensions(self) -> None:
        """Detect available extensions."""
        # Check for ETL extension
        self._integrations["etl"] = self._check_extension("whiskey_etl")
        if self._integrations["etl"]:
            self._setup_etl_integration()
        
        # Check for SQL extension
        self._integrations["sql"] = self._check_extension("whiskey_sql")
        if self._integrations["sql"]:
            self._setup_sql_integration()
        
        # Check for Jobs extension
        self._integrations["jobs"] = self._check_extension("whiskey_jobs")
        if self._integrations["jobs"]:
            self._setup_jobs_integration()
    
    def _check_extension(self, module_name: str) -> bool:
        """Check if an extension is available.
        
        Args:
            module_name: Module name to check
            
        Returns:
            True if module is available
        """
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False
    
    def _setup_etl_integration(self) -> None:
        """Set up ETL extension integration."""
        try:
            from whiskey_ml.integrations.etl import ETLIntegration
            self._etl_integration = ETLIntegration(self)
        except ImportError:
            # ETL integration module not available
            pass
    
    def _setup_sql_integration(self) -> None:
        """Set up SQL extension integration."""
        try:
            from whiskey_ml.integrations.sql import SQLIntegration
            self._sql_integration = SQLIntegration(self)
        except ImportError:
            # SQL integration module not available
            pass
    
    def _setup_jobs_integration(self) -> None:
        """Set up Jobs extension integration."""
        try:
            from whiskey_ml.integrations.jobs import JobsIntegration
            self._jobs_integration = JobsIntegration(self)
        except ImportError:
            # Jobs integration module not available
            pass
    
    @property
    def available_extensions(self) -> dict[str, bool]:
        """Get available extensions.
        
        Returns:
            Dictionary of extension name to availability
        """
        return self._integrations.copy()
    
    def has_extension(self, name: str) -> bool:
        """Check if extension is available.
        
        Args:
            name: Extension name
            
        Returns:
            True if extension is available
        """
        return self._integrations.get(name, False)
    
    def create_context(self) -> MLContext:
        """Create ML context with integrations.
        
        Returns:
            MLContext instance
        """
        return MLContext(
            container=self.container,
            integrations=self.available_extensions,
        )