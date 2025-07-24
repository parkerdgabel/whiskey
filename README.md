# Whiskey >C

A next-generation dependency injection and IoC framework for Python AI applications.

## Features

- **AI-First Design**: Built specifically for AI workloads with native support for model management, token tracking, and conversation contexts
- **Zero-Config Magic**: Convention-over-configuration with intelligent defaults
- **Type-Safe**: Full type hints and runtime validation
- **Async-Native**: First-class support for async/await patterns
- **Framework Agnostic**: Works with FastAPI, Django, Flask, and pure Python

## Quick Start

```python
from whiskey import inject, provide, singleton
from whiskey.ai.context import AIContext

# Define services
@singleton
class ConfigService:
    def __init__(self):
        self.api_key = "your-api-key"

@provide
class AIService:
    def __init__(self, config: ConfigService):
        self.config = config
    
    async def process(self, prompt: str, context: AIContext):
        # Your AI logic here
        context.add_usage(prompt_tokens=10)
        return f"Processed: {prompt}"

# Use with automatic injection
@inject
async def handle_request(prompt: str, ai: AIService):
    context = AIContext()
    return await ai.process(prompt, context)

# Run it
result = await handle_request("Hello AI!")
```

## Core Concepts

### Scopes

Whiskey provides several built-in scopes:

- `singleton` - One instance for the entire application
- `transient` - New instance for each request
- `request` - One instance per HTTP request
- `session` - One instance per user session
- `conversation` - One instance per AI conversation
- `ai_context` - One instance per AI operation

### Decorators

- `@provide` - Register a class as an injectable service
- `@singleton` - Register as a singleton service
- `@inject` - Automatically inject dependencies into functions
- `@factory` - Register a factory function

### AI-Specific Features

- **AIContext**: Automatic tracking of token usage, costs, and conversation history
- **Model Registry**: Unified interface for different AI providers
- **Resource Management**: Token budgets, rate limiting, GPU memory management
- **Conversation Scopes**: Maintain state across multi-turn dialogues

## Installation

```bash
pip install whiskey
```

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format

# Lint
uv run ruff check
```

## License

MIT