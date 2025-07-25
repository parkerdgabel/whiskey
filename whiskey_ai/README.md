# Whiskey AI Plugin

AI/LLM integration plugin for the Whiskey framework.

## Installation

```bash
pip install whiskey[ai]
```

## Features

- **AI Context Management**: Track token usage, costs, and conversation history
- **Model Protocols**: Standardized interfaces for chat, completion, and embedding models
- **Prompt Templates**: Manage and validate prompt templates with variable substitution
- **Resource Management**: Token bucket rate limiting and resource allocation
- **Observability**: Events and metrics for AI operations
- **Streaming Support**: Handle streaming responses from LLMs

## Quick Start

```python
from whiskey import Application
from whiskey_ai import AIContext, ChatCompletionModel, Message

app = Application()

@app.service
class MyAIService:
    def __init__(self, ai_context: AIContext, chat_model: ChatCompletionModel):
        self.context = ai_context
        self.model = chat_model
    
    async def chat(self, message: str) -> str:
        messages = [Message(role="user", content=message)]
        
        response = await self.model.complete(
            messages=messages,
            temperature=0.7,
        )
        
        # Context automatically tracks usage
        return response.choices[0].message.content

# Run the app
if __name__ == "__main__":
    app.run()
```

## Components

### AI Context

Manages conversation state and tracks resource usage:

```python
@inject
async def my_handler(ai_context: AIContext):
    # Get current conversation
    messages = ai_context.get_messages()
    
    # Add assistant response
    ai_context.add_message(Message(
        role="assistant",
        content="Hello! How can I help?",
    ))
    
    # Track token usage
    ai_context.track_usage(Usage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    ))
```

### Model Protocols

Implement these protocols to integrate any LLM:

```python
from whiskey_ai import ChatCompletionModel, ChatCompletion

class MyLLMProvider(ChatCompletionModel):
    async def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ChatCompletion:
        # Your implementation
        pass
```

### Prompt Templates

Manage prompts with validation and variable substitution:

```python
from whiskey_ai import PromptRegistry, PromptTemplate

@inject
async def setup_prompts(registry: PromptRegistry):
    registry.register(
        "greeting",
        PromptTemplate(
            template="Hello {name}, welcome to {product}!",
            variables=[
                PromptVariable(name="name", required=True),
                PromptVariable(name="product", default="Whiskey"),
            ],
        ),
    )
    
    # Use the template
    prompt = registry.render("greeting", name="Alice")
    # "Hello Alice, welcome to Whiskey!"
```

### Resource Management

Control API usage with token buckets:

```python
from whiskey_ai import AIResourceManager

@inject
async def rate_limited_call(
    resource_manager: AIResourceManager,
    chat_model: ChatCompletionModel,
):
    # Acquire tokens before making API call
    async with resource_manager.acquire("api_calls", tokens=1):
        response = await chat_model.complete(messages)
    
    # Automatically released after use
```

## Events

The plugin emits events for observability:

- `AIRequestStarted`: Fired when an AI request begins
- `AIRequestCompleted`: Fired when an AI request completes successfully
- `AIRequestFailed`: Fired when an AI request fails
- `AIStreamChunkReceived`: Fired for each streaming chunk
- `AIStreamCompleted`: Fired when streaming completes

## Configuration

Configure via environment variables:

```bash
# Resource limits
AI_MAX_REQUESTS_PER_MINUTE=60
AI_MAX_TOKENS_PER_MINUTE=10000

# Model settings
AI_DEFAULT_MODEL=gpt-4
AI_DEFAULT_TEMPERATURE=0.7
```

## Testing

The plugin includes mock implementations for testing:

```python
from whiskey_ai import MockChatModel

@app.service
class TestService:
    def __init__(self):
        # Use mock in tests
        self.model = MockChatModel(
            response="Test response",
            usage=Usage(prompt_tokens=5, completion_tokens=10),
        )
```

## License

Same as Whiskey framework.