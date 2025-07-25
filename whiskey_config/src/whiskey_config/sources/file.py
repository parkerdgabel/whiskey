"""File-based configuration sources."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ConfigurationSource


class FileSource(ConfigurationSource):
    """Configuration source that reads from files."""
    
    def __init__(self, path: str, format: Optional[str] = None):
        """Initialize file source.
        
        Args:
            path: Path to configuration file
            format: File format (json, yaml, toml). Auto-detected if None
        """
        super().__init__(f"File:{path}")
        self.path = Path(path)
        self.format = format or self._detect_format()
        self._last_modified: Optional[float] = None
    
    def _detect_format(self) -> str:
        """Detect file format from extension."""
        suffix = self.path.suffix.lower()
        if suffix == ".json":
            return "json"
        elif suffix in (".yaml", ".yml"):
            return "yaml"
        elif suffix == ".toml":
            return "toml"
        else:
            raise ValueError(f"Unknown file format for {self.path}")
    
    async def load(self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            Dictionary containing configuration data
        """
        if not self.path.exists():
            return {}
        
        # Update last modified time
        self._last_modified = os.path.getmtime(self.path)
        
        # Read file content
        content = self.path.read_text()
        
        # Parse based on format
        if self.format == "json":
            return json.loads(content)
        elif self.format == "yaml":
            try:
                import yaml
                return yaml.safe_load(content) or {}
            except ImportError:
                raise ImportError(
                    "YAML support requires PyYAML. Install with: pip install whiskey-config[yaml]"
                )
        elif self.format == "toml":
            try:
                import tomli
                return tomli.loads(content)
            except ImportError:
                try:
                    import tomllib  # Python 3.11+
                    return tomllib.loads(content)
                except ImportError:
                    raise ImportError(
                        "TOML support requires tomli. Install with: pip install whiskey-config[toml]"
                    )
        else:
            raise ValueError(f"Unsupported format: {self.format}")
    
    def can_reload(self) -> bool:
        """File sources can be reloaded."""
        return True
    
    async def reload(self) -> Optional[Dict[str, Any]]:
        """Reload configuration if file has changed.
        
        Returns:
            Updated configuration if changed, None otherwise
        """
        if not self.path.exists():
            if self._last_modified is not None:
                # File was deleted
                self._last_modified = None
                return {}
            return None
        
        current_modified = os.path.getmtime(self.path)
        if self._last_modified is None or current_modified > self._last_modified:
            return await self.load()
        
        return None