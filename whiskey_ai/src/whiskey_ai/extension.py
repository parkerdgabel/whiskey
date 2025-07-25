"""AI extension for Whiskey applications with OpenAI-compatible API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import (
    Any, AsyncIterator, Callable, Dict, List, Literal, Optional, Protocol,
    Union, runtime_checkable
)

from whiskey import Application


# OpenAI-compatible types
@dataclass
class Function:
    """OpenAI function definition."""
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


@dataclass
class Tool:
    """OpenAI tool definition."""
    type: Literal["function"]
    function: Function


@dataclass
class FunctionCall:
    """Function call in a message."""
    name: str
    arguments: str


@dataclass
class ToolCall:
    """Tool call in a message."""
    id: str
    type: Literal["function"]
    function: FunctionCall


@dataclass
class ResponseFormat:
    """Response format specification."""
    type: Literal["text", "json_object"]


@dataclass
class Message:
    """OpenAI-compatible message."""
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None


@dataclass
class Usage:
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class Choice:
    """Completion choice."""
    index: int
    message: Message
    finish_reason: Optional[str]
    logprobs: Optional[Any] = None


@dataclass
class ChatCompletion:
    """OpenAI-compatible chat completion response."""
    id: str
    model: str
    choices: List[Choice]
    usage: Usage
    object: str = "chat.completion"
    created: int = field(default_factory=lambda: int(time.time()))
    system_fingerprint: Optional[str] = None


@dataclass
class Delta:
    """Streaming message delta."""
    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None
    role: Optional[str] = None


@dataclass
class StreamChoice:
    """Streaming completion choice."""
    index: int
    delta: Delta
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


@dataclass
class ChatCompletionChunk:
    """OpenAI-compatible streaming chunk."""
    id: str
    model: str
    choices: List[StreamChoice]
    object: str = "chat.completion.chunk"
    created: int = field(default_factory=lambda: int(time.time()))
    system_fingerprint: Optional[str] = None


@dataclass
class Embedding:
    """Single embedding."""
    index: int
    embedding: List[float]
    object: str = "embedding"


@dataclass
class EmbeddingResponse:
    """OpenAI-compatible embedding response."""
    data: List[Embedding]
    model: str
    usage: Usage
    object: str = "list"


# Protocol definitions for OpenAI-compatible interfaces
@runtime_checkable
class ChatCompletions(Protocol):
    """OpenAI-compatible chat completions interface."""
    
    async def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = 1.0,
        top_p: Optional[float] = 1.0,
        n: Optional[int] = 1,
        stream: Optional[bool] = False,
        stop: Optional[Union[str, List[str]]] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = 0.0,
        frequency_penalty: Optional[float] = 0.0,
        logit_bias: Optional[Dict[str, float]] = None,
        user: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[Union[str, Dict[str, Any]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
        **kwargs
    ) -> Union[ChatCompletion, AsyncIterator[ChatCompletionChunk]]:
        """Create a chat completion."""
        ...


@runtime_checkable
class Embeddings(Protocol):
    """OpenAI-compatible embeddings interface."""
    
    async def create(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        encoding_format: Optional[Literal["float", "base64"]] = "float",
        dimensions: Optional[int] = None,
        user: Optional[str] = None,
        **kwargs
    ) -> EmbeddingResponse:
        """Create embeddings."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """OpenAI-compatible client interface."""
    chat: ChatCompletions
    embeddings: Embeddings


# Manager classes
class ModelManager:
    """Manages LLM model implementations."""
    
    def __init__(self):
        self.models: Dict[str, type] = {}
        self.instances: Dict[str, LLMClient] = {}
    
    def register(self, name: str, model_class: type) -> None:
        """Register a model implementation."""
        self.models[name] = model_class
    
    def get(self, name: str) -> LLMClient:
        """Get a model instance."""
        if name not in self.instances:
            raise ValueError(f"Model '{name}' not configured")
        return self.instances[name]
    
    def configure(self, name: str, **kwargs) -> None:
        """Configure a model instance."""
        if name not in self.models:
            raise ValueError(f"Model '{name}' not registered")
        self.instances[name] = self.models[name](**kwargs)


class ToolManager:
    """Manages tools/functions for LLMs."""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}
    
    def register(self, tool: Callable, schema: Dict[str, Any]) -> None:
        """Register a tool with its schema."""
        name = schema["function"]["name"]
        self.tools[name] = tool
        self.schemas[name] = schema
    
    def get(self, name: str) -> Optional[Callable]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a tool's schema."""
        return self.schemas.get(name)
    
    def all_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas."""
        return list(self.schemas.values())


class AgentManager:
    """Manages AI agents."""
    
    def __init__(self):
        self.agents: Dict[str, type] = {}
        self.instances: Dict[str, Any] = {}
    
    def register(self, name: str, agent_class: type) -> None:
        """Register an agent class."""
        self.agents[name] = agent_class
    
    def get(self, name: str) -> Any:
        """Get an agent instance."""
        return self.instances.get(name)


# Conversation scope
from whiskey.core.scopes import ContextVarScope


class ConversationScope(ContextVarScope):
    """Scope for conversation/chat sessions - isolated per async context."""
    
    def __init__(self):
        super().__init__("conversation")


def ai_extension(app: Application) -> None:
    """AI extension that adds LLM capabilities to Whiskey applications.
    
    This extension provides:
    - OpenAI-compatible LLM client abstraction
    - Model registration with @app.model decorator
    - Tool/function calling with @app.tool decorator
    - Agent framework with @app.agent decorator
    - Conversation management
    - Streaming support
    
    Example:
        app = Application()
        app.use(ai_extension)
        
        # Register a model
        @app.model("openai")
        class OpenAIModel:
            def __init__(self, api_key: str):
                self.client = AsyncOpenAI(api_key=api_key)
            
            @property
            def chat(self):
                return self.client.chat.completions
            
            @property
            def embeddings(self):
                return self.client.embeddings
        
        # Configure the model
        app.configure_model("openai", api_key=os.getenv("OPENAI_API_KEY"))
        
        # Use in a route
        @app.post("/chat")
        @inject
        async def chat(request: Request, client: LLMClient):
            data = await request.json()
            response = await client.chat.create(
                model="gpt-4",
                messages=data["messages"]
            )
            return response.model_dump()
    """
    # Create managers
    model_manager = ModelManager()
    tool_manager = ToolManager()
    agent_manager = AgentManager()
    
    # Store managers in app
    app.model_manager = model_manager
    app.tool_manager = tool_manager
    app.agent_manager = agent_manager
    
    # Add conversation scope
    app.add_scope("conversation", ConversationScope)
    
    # Register managers as services
    app.container[ModelManager] = model_manager
    app.container[ToolManager] = tool_manager
    app.container[AgentManager] = agent_manager
    
    # Model decorator
    def model(name: str):
        """Decorator to register an LLM model implementation.
        
        The decorated class should implement the LLMClient protocol
        with OpenAI-compatible chat and embeddings interfaces.
        """
        def decorator(cls: type) -> type:
            model_manager.register(name, cls)
            return cls
        return decorator
    
    app.add_decorator("model", model)
    
    # Tool decorator
    def tool(name: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a tool/function for LLMs.
        
        The decorated function should have type hints for parameters
        and can return any JSON-serializable value.
        """
        def decorator(func: Callable) -> Callable:
            import inspect
            
            # Generate OpenAI function schema from function signature
            sig = inspect.signature(func)
            parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                    
                # Infer type from annotation
                param_type = "string"  # default
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == list or param.annotation == List:
                        param_type = "array"
                    elif param.annotation == dict or param.annotation == Dict:
                        param_type = "object"
                
                parameters["properties"][param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}"
                }
                
                if param.default == inspect.Parameter.empty:
                    parameters["required"].append(param_name)
            
            schema = {
                "type": "function",
                "function": {
                    "name": name or func.__name__,
                    "description": description or func.__doc__ or f"Function {func.__name__}",
                    "parameters": parameters
                }
            }
            
            tool_manager.register(func, schema)
            return func
        return decorator
    
    app.add_decorator("tool", tool)
    
    # Agent decorator
    def agent(name: str):
        """Decorator to register an AI agent.
        
        Agents are classes that can be injected and perform
        complex tasks using LLMs and tools.
        """
        def decorator(cls: type) -> type:
            agent_manager.register(name, cls)
            # Register the agent class in the container
            app.container[cls] = cls
            return cls
        return decorator
    
    app.add_decorator("agent", agent)
    
    # Model configuration method
    def configure_model(name: str, **kwargs) -> None:
        """Configure a model instance with the given parameters."""
        model_manager.configure(name, **kwargs)
    
    app.configure_model = configure_model
    
    # Get model method
    def get_model(name: str) -> LLMClient:
        """Get a configured model instance."""
        return model_manager.get(name)
    
    app.get_model = get_model
    
    # Default LLMClient injection
    @app.on_startup
    async def setup_default_client():
        """Set up default LLM client if configured."""
        # Check if a default model is configured
        if hasattr(app, "config") and app.config.get("ai.default_model"):
            default_model = app.config.get("ai.default_model")
            if default_model in model_manager.instances:
                app.container[LLMClient] = model_manager.instances[default_model]