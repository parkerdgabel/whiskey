"""Environment variable configuration source."""

import os
from typing import Any, Dict, Optional


from .base import ConfigurationSource


class EnvironmentSource(ConfigurationSource):
    """Configuration source that reads from environment variables."""
    
    def __init__(self, prefix: str = "", delimiter: str = "_"):
        """Initialize environment source.
        
        Args:
            prefix: Prefix for environment variables (e.g., "MYAPP_")
            delimiter: Delimiter for nested keys (default: "_")
        """
        super().__init__(f"ENV:{prefix}")
        self.prefix = prefix.upper()
        self.delimiter = delimiter
    
    async def load(self) -> Dict[str, Any]:
        """Load configuration from environment variables.
        
        Returns:
            Dictionary containing configuration from environment
        """
        config = {}
        
        for key, value in os.environ.items():
            # Skip if doesn't match prefix
            if self.prefix and not key.startswith(self.prefix):
                continue
            
            # Remove prefix
            if self.prefix:
                key = key[len(self.prefix):]
            
            # Skip empty keys
            if not key:
                continue
            
            # Convert to lowercase and split by delimiter
            parts = key.lower().split(self.delimiter)
            
            # Build nested dictionary
            current = config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value, attempting type conversion
            current[parts[-1]] = self._convert_value(value)
        
        return config
    
    def can_reload(self) -> bool:
        """Environment variables can be reloaded."""
        return True
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type.
        
        Args:
            value: String value from environment
            
        Returns:
            Converted value
        """
        # Handle empty strings
        if not value:
            return value
        
        # Try boolean
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try list (comma-separated)
        if "," in value:
            return [item.strip() for item in value.split(",")]
        
        # Return as string
        return value