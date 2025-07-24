"""Registry for managing prompt templates."""

from typing import Dict, List, Optional

from whiskey.core.decorators import provide, singleton

from .template import PromptTemplate


@singleton
class PromptRegistry:
    """Central registry for prompt templates."""
    
    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(
        self,
        name: str,
        template: PromptTemplate,
        category: Optional[str] = None,
        overwrite: bool = False
    ) -> None:
        """Register a prompt template.
        
        Args:
            name: Unique name for the template
            template: The prompt template
            category: Optional category for organization
            overwrite: Whether to overwrite existing template
            
        Raises:
            ValueError: If template already exists and overwrite=False
        """
        if name in self._templates and not overwrite:
            raise ValueError(f"Template '{name}' already registered")
        
        self._templates[name] = template
        
        # Add to category if specified
        if category:
            if category not in self._categories:
                self._categories[category] = []
            if name not in self._categories[category]:
                self._categories[category].append(name)
    
    def get(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name.
        
        Args:
            name: Template name
            
        Returns:
            PromptTemplate if found, None otherwise
        """
        return self._templates.get(name)
    
    def get_required(self, name: str) -> PromptTemplate:
        """Get a template by name, raising if not found.
        
        Args:
            name: Template name
            
        Returns:
            PromptTemplate
            
        Raises:
            KeyError: If template not found
        """
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found in registry")
        return self._templates[name]
    
    def list_templates(self, category: Optional[str] = None) -> List[str]:
        """List all template names.
        
        Args:
            category: Filter by category if specified
            
        Returns:
            List of template names
        """
        if category:
            return self._categories.get(category, []).copy()
        return list(self._templates.keys())
    
    def list_categories(self) -> List[str]:
        """List all categories."""
        return list(self._categories.keys())
    
    def remove(self, name: str) -> bool:
        """Remove a template.
        
        Args:
            name: Template name
            
        Returns:
            True if removed, False if not found
        """
        if name in self._templates:
            del self._templates[name]
            
            # Remove from categories
            for category_templates in self._categories.values():
                if name in category_templates:
                    category_templates.remove(name)
            
            return True
        return False
    
    def clear(self, category: Optional[str] = None) -> None:
        """Clear templates.
        
        Args:
            category: Clear only specific category if provided
        """
        if category:
            # Clear specific category
            template_names = self._categories.get(category, [])
            for name in template_names:
                self._templates.pop(name, None)
            self._categories.pop(category, None)
        else:
            # Clear everything
            self._templates.clear()
            self._categories.clear()
    
    def create_from_string(
        self,
        name: str,
        template_string: str,
        category: Optional[str] = None,
        **kwargs
    ) -> PromptTemplate:
        """Create and register a template from a string.
        
        Args:
            name: Template name
            template_string: Template content
            category: Optional category
            **kwargs: Additional arguments for PromptTemplate
            
        Returns:
            Created PromptTemplate
        """
        template = PromptTemplate(template_string, **kwargs)
        self.register(name, template, category)
        return template