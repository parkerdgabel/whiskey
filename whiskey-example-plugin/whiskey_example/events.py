"""Example events for the plugin."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ItemCreated:
    """Event fired when an item is created."""
    
    item_id: str
    name: str
    created_by: Optional[str] = None
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ItemDeleted:
    """Event fired when an item is deleted."""
    
    item_id: str
    deleted_by: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ItemUpdated:
    """Event fired when an item is updated."""
    
    item_id: str
    changes: Dict[str, Any]
    updated_by: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()