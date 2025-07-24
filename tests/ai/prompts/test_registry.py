"""Tests for prompt registry."""

import pytest

from whiskey.ai.prompts import PromptRegistry, PromptTemplate, PromptVariable
from whiskey.core.decorators import get_default_container


@pytest.mark.unit
class TestPromptRegistry:
    """Test prompt registry."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry."""
        return PromptRegistry()
    
    def test_register_and_get(self, registry):
        """Test registering and retrieving templates."""
        template = PromptTemplate(
            template="Hello, {name}!",
            variables=[PromptVariable(name="name")]
        )
        
        registry.register("greeting", template)
        
        # Should retrieve the same template
        retrieved = registry.get("greeting")
        assert retrieved is template
        
        # Should return None for non-existent
        assert registry.get("non-existent") is None
    
    def test_get_required(self, registry):
        """Test get_required method."""
        template = PromptTemplate(template="Test")
        registry.register("test", template)
        
        # Should return template
        assert registry.get_required("test") is template
        
        # Should raise for non-existent
        with pytest.raises(KeyError) as exc:
            registry.get_required("non-existent")
        assert "Template 'non-existent' not found" in str(exc.value)
    
    def test_overwrite_protection(self, registry):
        """Test overwrite protection."""
        template1 = PromptTemplate(template="First")
        template2 = PromptTemplate(template="Second")
        
        registry.register("test", template1)
        
        # Should fail without overwrite
        with pytest.raises(ValueError) as exc:
            registry.register("test", template2)
        assert "already registered" in str(exc.value)
        
        # Should succeed with overwrite
        registry.register("test", template2, overwrite=True)
        assert registry.get("test").template == "Second"
    
    def test_categories(self, registry):
        """Test category management."""
        template1 = PromptTemplate(template="Chat template")
        template2 = PromptTemplate(template="Email template")
        template3 = PromptTemplate(template="Another chat")
        
        registry.register("chat1", template1, category="chat")
        registry.register("email1", template2, category="email")
        registry.register("chat2", template3, category="chat")
        
        # List by category
        chat_templates = registry.list_templates(category="chat")
        assert set(chat_templates) == {"chat1", "chat2"}
        
        email_templates = registry.list_templates(category="email")
        assert email_templates == ["email1"]
        
        # List categories
        categories = registry.list_categories()
        assert set(categories) == {"chat", "email"}
    
    def test_list_all_templates(self, registry):
        """Test listing all templates."""
        registry.register("t1", PromptTemplate(template="1"))
        registry.register("t2", PromptTemplate(template="2"))
        registry.register("t3", PromptTemplate(template="3"))
        
        all_templates = registry.list_templates()
        assert set(all_templates) == {"t1", "t2", "t3"}
    
    def test_remove_template(self, registry):
        """Test removing templates."""
        template = PromptTemplate(template="Test")
        registry.register("test", template, category="testing")
        
        # Should remove successfully
        assert registry.remove("test") is True
        assert registry.get("test") is None
        
        # Should be removed from category too
        assert "test" not in registry.list_templates(category="testing")
        
        # Should return False for non-existent
        assert registry.remove("non-existent") is False
    
    def test_clear_category(self, registry):
        """Test clearing specific category."""
        registry.register("chat1", PromptTemplate(template="1"), category="chat")
        registry.register("chat2", PromptTemplate(template="2"), category="chat")
        registry.register("email1", PromptTemplate(template="3"), category="email")
        
        # Clear chat category
        registry.clear(category="chat")
        
        # Chat templates should be gone
        assert registry.get("chat1") is None
        assert registry.get("chat2") is None
        assert registry.list_templates(category="chat") == []
        
        # Email should remain
        assert registry.get("email1") is not None
    
    def test_clear_all(self, registry):
        """Test clearing all templates."""
        registry.register("t1", PromptTemplate(template="1"))
        registry.register("t2", PromptTemplate(template="2"))
        
        registry.clear()
        
        assert registry.list_templates() == []
        assert registry.list_categories() == []
    
    def test_create_from_string(self, registry):
        """Test creating template from string."""
        template = registry.create_from_string(
            name="simple",
            template_string="Hello, {name}!",
            category="greetings",
            strict=False  # Don't validate undefined variables
        )
        
        assert template.template == "Hello, {name}!"
        assert registry.get("simple") is template
        assert "simple" in registry.list_templates(category="greetings")
    
    def test_singleton_behavior(self):
        """Test that registry is a singleton."""
        container = get_default_container()
        
        registry1 = container.resolve_sync(PromptRegistry)
        registry2 = container.resolve_sync(PromptRegistry)
        
        assert registry1 is registry2