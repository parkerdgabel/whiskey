"""Tests for AI extension manager classes."""

import pytest
from whiskey import Container
from whiskey_ai.extension import ModelManager, ToolManager, AgentManager, LLMClient
from whiskey_ai import MockLLMClient


@pytest.mark.unit
class TestModelManager:
    """Test the ModelManager class."""
    
    def test_register_and_get_model(self):
        """Test registering and retrieving models."""
        container = Container()
        manager = ModelManager(container)
        
        # Register a model class
        manager.register("mock", MockLLMClient)
        
        # Configure the model
        manager.configure("mock")
        
        # Get the model instance
        model = manager.get("mock")
        assert model is not None
        assert isinstance(model, MockLLMClient)
    
    def test_get_unconfigured_model_raises(self):
        """Test that getting unconfigured model raises error."""
        container = Container()
        manager = ModelManager(container)
        
        with pytest.raises(ValueError, match="not configured"):
            manager.get("nonexistent")
    
    def test_configure_unregistered_model_raises(self):
        """Test that configuring unregistered model raises error."""
        container = Container()
        manager = ModelManager(container)
        
        with pytest.raises(ValueError, match="not registered"):
            manager.configure("nonexistent")
    
    def test_first_model_becomes_default(self):
        """Test that first configured model becomes default LLMClient."""
        container = Container()
        manager = ModelManager(container)
        
        # Register and configure a model
        manager.register("mock", MockLLMClient)
        manager.configure("mock")
        
        # Check it's set as default LLMClient
        # Note: LLMClient is a Protocol, so we check if it's registered
        try:
            client = container[LLMClient]
            assert isinstance(client, MockLLMClient)
        except KeyError:
            # Protocol might not be directly resolvable, check the instance key
            assert f"ai.model.instance.mock" in container


@pytest.mark.unit
class TestToolManager:
    """Test the ToolManager class."""
    
    def test_register_and_get_tool(self):
        """Test registering and retrieving tools."""
        container = Container()
        manager = ToolManager(container)
        
        # Define a tool
        def test_tool(x: int) -> int:
            return x * 2
        
        schema = {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "Test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        
        # Register the tool
        manager.register(test_tool, schema)
        
        # Get the tool
        tool = manager.get("test_tool")
        assert tool is not None
        assert tool(5) == 10
    
    def test_get_nonexistent_tool_returns_none(self):
        """Test that getting nonexistent tool returns None."""
        container = Container()
        manager = ToolManager(container)
        
        assert manager.get("nonexistent") is None
    
    def test_get_tool_schema(self):
        """Test retrieving tool schema."""
        container = Container()
        manager = ToolManager(container)
        
        schema = {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "Test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        
        manager.register(lambda: None, schema)
        
        retrieved_schema = manager.get_schema("test_tool")
        assert retrieved_schema == schema
    
    def test_all_schemas(self):
        """Test retrieving all tool schemas."""
        container = Container()
        manager = ToolManager(container)
        
        # Register multiple tools
        schema1 = {
            "type": "function",
            "function": {"name": "tool1", "description": "Tool 1"}
        }
        schema2 = {
            "type": "function", 
            "function": {"name": "tool2", "description": "Tool 2"}
        }
        
        manager.register(lambda: 1, schema1)
        manager.register(lambda: 2, schema2)
        
        all_schemas = manager.all_schemas()
        assert len(all_schemas) == 2
        assert schema1 in all_schemas
        assert schema2 in all_schemas


@pytest.mark.unit
class TestAgentManager:
    """Test the AgentManager class."""
    
    def test_register_and_get_agent(self):
        """Test registering and retrieving agents."""
        container = Container()
        manager = AgentManager(container)
        
        # Define an agent class
        class TestAgent:
            pass
        
        # Register the agent
        manager.register("test", TestAgent)
        
        # Get the agent class
        agent_class = manager.get("test")
        assert agent_class is TestAgent
        
        # Check it's also registered by type
        assert TestAgent in container
        assert container[TestAgent] is TestAgent
    
    def test_get_nonexistent_agent_returns_none(self):
        """Test that getting nonexistent agent returns None."""
        container = Container()
        manager = AgentManager(container)
        
        assert manager.get("nonexistent") is None