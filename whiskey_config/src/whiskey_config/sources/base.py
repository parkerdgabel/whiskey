"""Base configuration source interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ConfigurationSource(ABC):
    """Abstract base class for configuration sources."""
    
    def __init__(self, name: str):
        """Initialize configuration source.
        
        Args:
            name: Name of the configuration source
        """
        self.name = name
    
    @abstractmethod
    async def load(self) -> Dict[str, Any]:
        """Load configuration from the source.
        
        Returns:
            Dictionary containing configuration data
        """
        pass
    
    @abstractmethod
    def can_reload(self) -> bool:
        """Check if this source supports reloading.
        
        Returns:
            True if source can be reloaded, False otherwise
        """
        pass
    
    async def reload(self) -> Optional[Dict[str, Any]]:
        """Reload configuration from the source.
        
        Returns:
            Updated configuration if changed, None otherwise
        """
        if not self.can_reload():
            return None
        return await self.load()
    
    def __repr__(self) -> str:
        """String representation of the source."""
        return f"{self.__class__.__name__}(name='{self.name}')"