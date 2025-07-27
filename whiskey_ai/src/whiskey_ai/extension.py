"""AI extension for Whiskey applications with OpenAI-compatible API."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Protocol,
    runtime_checkable,
)

from whiskey import Container
from whiskey.core.scopes import ContextVarScope

if TYPE_CHECKING:
    from whiskey import Whiskey


# OpenAI-compatible types
@dataclass
class Function:
    """OpenAI function definition."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


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
    content: str | None = None
    name: str | None = None
    function_call: FunctionCall | None = None
    tool_calls: list[ToolCall] | None = None


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
    finish_reason: str | None
    logprobs: Any | None = None


@dataclass
class ChatCompletion:
    """OpenAI-compatible chat completion response."""

    id: str
    model: str
    choices: list[Choice]
    usage: Usage
    object: str = "chat.completion"
    created: int = field(default_factory=lambda: int(time.time()))
    system_fingerprint: str | None = None


@dataclass
class Delta:
    """Streaming message delta."""

    content: str | None = None
    function_call: FunctionCall | None = None
    tool_calls: list[ToolCall] | None = None
    role: str | None = None


@dataclass
class StreamChoice:
    """Streaming completion choice."""

    index: int
    delta: Delta
    finish_reason: str | None = None
    logprobs: Any | None = None


@dataclass
class ChatCompletionChunk:
    """OpenAI-compatible streaming chunk."""

    id: str
    model: str
    choices: list[StreamChoice]
    object: str = "chat.completion.chunk"
    created: int = field(default_factory=lambda: int(time.time()))
    system_fingerprint: str | None = None


@dataclass
class Embedding:
    """Single embedding."""

    index: int
    embedding: list[float]
    object: str = "embedding"


@dataclass
class EmbeddingResponse:
    """OpenAI-compatible embedding response."""

    data: list[Embedding]
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
        messages: list[dict[str, Any]],
        temperature: float | None = 1.0,
        top_p: float | None = 1.0,
        n: int | None = 1,
        stream: bool | None = False,
        stop: str | list[str] | None = None,
        max_tokens: int | None = None,
        presence_penalty: float | None = 0.0,
        frequency_penalty: float | None = 0.0,
        logit_bias: dict[str, float] | None = None,
        user: str | None = None,
        functions: list[dict[str, Any]] | None = None,
        function_call: str | dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        seed: int | None = None,
        **kwargs: Any,
    ) -> ChatCompletion | AsyncIterator[ChatCompletionChunk]:
        """Create a chat completion."""
        ...


@runtime_checkable
class Embeddings(Protocol):
    """OpenAI-compatible embeddings interface."""

    async def create(
        self,
        *,
        model: str,
        input: str | list[str],
        encoding_format: Literal["float", "base64"] | None = "float",
        dimensions: int | None = None,
        user: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Create embeddings."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """OpenAI-compatible client interface."""

    chat: ChatCompletions
    embeddings: Embeddings


# Manager classes using Whiskey's dict-like patterns
class ModelManager:
    """Manages LLM model implementations using Whiskey's container patterns."""

    def __init__(self, container: Container = None):
        self.container = container or Container()
        # Use container's dict-like API for model classes
        self._model_classes: dict[str, type] = {}

    def register(self, name: str, model_class: type) -> None:
        """Register a model implementation."""
        self._model_classes[name] = model_class
        # Also register in container with tag for discoverability
        self.container[f"ai.model.{name}"] = model_class

    def get(self, name: str) -> LLMClient:
        """Get a configured model instance from the container."""
        key = f"ai.model.instance.{name}"
        if key not in self.container:
            raise ValueError(f"Model '{name}' not configured. Use configure() first.")
        return self.container[key]

    def configure(self, name: str, **kwargs) -> None:
        """Configure and instantiate a model."""
        if name not in self._model_classes:
            raise ValueError(f"Model '{name}' not registered")
        
        # Create instance and store in container
        instance = self._model_classes[name](**kwargs)
        self.container[f"ai.model.instance.{name}"] = instance
        
        # Also register as the default LLMClient if it's the first one
        if LLMClient not in self.container:
            self.container[LLMClient] = instance


class ToolManager:
    """Manages tools/functions for LLMs using container patterns."""

    def __init__(self, container: Container = None):
        self.container = container or Container()

    def register(self, tool: Callable, schema: dict[str, Any]) -> None:
        """Register a tool with its schema."""
        name = schema["function"]["name"]
        # Store tool and schema as raw values to avoid container resolution
        # We'll use a wrapper object to prevent the container from trying to call the function
        tool_wrapper = {"tool": tool, "is_ai_tool": True}
        schema_wrapper = {"schema": schema, "is_ai_tool_schema": True}
        self.container[f"ai.tool.{name}"] = tool_wrapper
        self.container[f"ai.tool.schema.{name}"] = schema_wrapper

    def get(self, name: str) -> Callable | None:
        """Get a tool by name."""
        key = f"ai.tool.{name}"
        if key in self.container:
            wrapper = self.container[key]
            return wrapper["tool"] if isinstance(wrapper, dict) and "tool" in wrapper else None
        return None

    def get_schema(self, name: str) -> dict[str, Any] | None:
        """Get a tool's schema."""
        key = f"ai.tool.schema.{name}"
        if key in self.container:
            wrapper = self.container[key]
            return wrapper["schema"] if isinstance(wrapper, dict) and "schema" in wrapper else None
        return None

    def all_schemas(self) -> list[dict[str, Any]]:
        """Get all tool schemas."""
        # Find all schema keys and return their values
        schemas = []
        for key, value in self.container.items():
            if isinstance(key, str) and key.startswith("ai.tool.schema.") and isinstance(value, dict) and "schema" in value:
                schemas.append(value["schema"])
        return schemas


class AgentManager:
    """Manages AI agents using Whiskey's container."""

    def __init__(self, container: Container = None):
        self.container = container or Container()

    def register(self, name: str, agent_class: type) -> None:
        """Register an agent class in the container."""
        # Store agent class with consistent key pattern
        self.container[f"ai.agent.{name}"] = agent_class
        # Also register by class type for injection
        self.container[agent_class] = agent_class

    def get(self, name: str) -> Any:
        """Get an agent class (not instance) by name."""
        key = f"ai.agent.{name}"
        return self.container[key] if key in self.container else None




class ConversationScope(ContextVarScope):
    """Scope for conversation/chat sessions - isolated per async context."""

    def __init__(self):
        super().__init__("conversation")


def ai_extension(app: Whiskey) -> None:
    """AI extension that adds LLM capabilities to Whiskey applications.

    This extension provides:
    - OpenAI-compatible LLM client abstraction
    - Model registration with @app.model decorator
    - Tool/function calling with @app.tool decorator
    - Agent framework with @app.agent decorator
    - Conversation management
    - Streaming support
    - CLI commands for AI development

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
    # Create managers using the app's container
    model_manager = ModelManager(app.container)
    tool_manager = ToolManager(app.container)
    agent_manager = AgentManager(app.container)

    # Store managers in app
    app.model_manager = model_manager
    app.tool_manager = tool_manager
    app.agent_manager = agent_manager

    # Register conversation scope as a singleton service
    # This allows it to be injected and used throughout the app
    conversation_scope = ConversationScope()
    app.singleton(conversation_scope, key="conversation_scope")
    app.singleton(conversation_scope, key=ConversationScope)

    # Register managers as singleton services using dict-like API
    app.container[ModelManager] = model_manager
    app.container[ToolManager] = tool_manager
    app.container[AgentManager] = agent_manager
    
    # Also register by string key for easier access
    app.container["model_manager"] = model_manager
    app.container["tool_manager"] = tool_manager
    app.container["agent_manager"] = agent_manager

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
    def tool(name: str | None = None, description: str | None = None):
        """Decorator to register a tool/function for LLMs.

        The decorated function should have type hints for parameters
        and can return any JSON-serializable value.
        """

        def decorator(func: Callable) -> Callable:
            import inspect

            # Generate OpenAI function schema from function signature
            sig = inspect.signature(func)
            parameters = {"type": "object", "properties": {}, "required": []}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Infer type from annotation
                param_type = "string"  # default
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation is int:
                        param_type = "integer"
                    elif param.annotation is float:
                        param_type = "number"
                    elif param.annotation is bool:
                        param_type = "boolean"
                    elif param.annotation is list:
                        param_type = "array"
                    elif param.annotation is dict:
                        param_type = "object"

                parameters["properties"][param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}",
                }

                if param.default == inspect.Parameter.empty:
                    parameters["required"].append(param_name)

            schema = {
                "type": "function",
                "function": {
                    "name": name or func.__name__,
                    "description": description or func.__doc__ or f"Function {func.__name__}",
                    "parameters": parameters,
                },
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
    
    # Register CLI commands if whiskey-cli is available
    try:
        from whiskey_cli import cli_extension
        # Check if CLI extension is loaded
        if hasattr(app, 'command'):
            from .cli import register_ai_cli_commands
            register_ai_cli_commands(app)
    except ImportError:
        # CLI extension not available, skip CLI registration
        pass
