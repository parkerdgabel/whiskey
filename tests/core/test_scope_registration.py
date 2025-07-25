"""Tests for dynamic scope registration."""

import pytest

from whiskey import Container, ContextVarScope
from whiskey.core.exceptions import ScopeError


class TestDynamicScopeRegistration:
    """Test dynamic scope registration functionality."""
    
    @pytest.fixture
    def container(self):
        return Container()
    
    def test_register_custom_scope(self, container):
        """Test registering a custom scope."""
        # Create a custom scope
        class CustomScope(ContextVarScope):
            def __init__(self):
                super().__init__("custom")
        
        # Register it
        custom_scope = CustomScope()
        container.register_scope("custom", custom_scope)
        
        # Verify it's registered
        retrieved_scope = container.scope_manager.get_scope("custom")
        assert retrieved_scope is custom_scope
    
    def test_use_custom_scope_in_registration(self, container):
        """Test using a custom scope when registering services."""
        # Register custom scope
        class MyScope(ContextVarScope):
            def __init__(self):
                super().__init__("my_scope")
        
        container.register_scope("my_scope", MyScope())
        
        # Register a service with the custom scope
        class MyService:
            pass
        
        container.register(MyService, MyService, scope="my_scope")
        
        # Verify the service is registered with the custom scope
        descriptor = container.get_descriptor(MyService)
        assert descriptor is not None
        assert descriptor.scope == "my_scope"
    
    def test_duplicate_scope_registration_error(self, container):
        """Test that registering a duplicate scope raises an error."""
        # Register a scope
        class CustomScope(ContextVarScope):
            def __init__(self):
                super().__init__("duplicate")
        
        container.register_scope("duplicate", CustomScope())
        
        # Try to register again
        with pytest.raises(ScopeError, match="already registered"):
            container.register_scope("duplicate", CustomScope())
    
    def test_plugin_scope_registration(self):
        """Test that plugins can register scopes."""
        from whiskey import Application
        from whiskey.plugins import BasePlugin
        
        # Create a test plugin that registers a scope
        class TestPlugin(BasePlugin):
            def __init__(self):
                super().__init__("test-plugin", "1.0.0")
            
            def register(self, container: Container) -> None:
                class PluginScope(ContextVarScope):
                    def __init__(self):
                        super().__init__("plugin_scope")
                
                container.register_scope("plugin_scope", PluginScope())
        
        # Create app and manually register the plugin
        app = Application()
        plugin = TestPlugin()
        plugin.register(app.container)
        
        # Verify the scope is available
        scope = app.container.scope_manager.get_scope("plugin_scope")
        assert scope is not None
        assert scope.name == "plugin_scope"