"""Example application demonstrating Whiskey DI framework."""

import asyncio
from dataclasses import dataclass
from typing import List

from loguru import logger

from whiskey import Container, inject, provide, singleton
from whiskey.ai.context import AIContext
from whiskey.core.types import ScopeType


# Example service definitions

@dataclass
class Config:
    """Application configuration."""
    api_key: str = "test-key"
    model_name: str = "gpt-4"
    max_tokens: int = 1000


@singleton
class ConfigService:
    """Singleton configuration service."""
    
    def __init__(self):
        self.config = Config()
        logger.info("ConfigService initialized")

    def get_api_key(self) -> str:
        return self.config.api_key

    def get_model_name(self) -> str:
        return self.config.model_name


@provide
class TokenCounter:
    """Service for counting tokens."""
    
    def __init__(self, config: ConfigService):
        self.config = config
        self.total_tokens = 0
        logger.info(f"TokenCounter initialized with model: {config.get_model_name()}")

    def count(self, text: str) -> int:
        # Simple approximation: 1 token per 4 characters
        tokens = len(text) // 4
        self.total_tokens += tokens
        return tokens


@provide(scope=ScopeType.CONVERSATION)
class ConversationMemory:
    """Conversation-scoped memory service."""
    
    def __init__(self):
        self.messages: List[str] = []
        logger.info("ConversationMemory initialized")

    def add_message(self, message: str):
        self.messages.append(message)

    def get_history(self) -> List[str]:
        return self.messages.copy()


@provide
class AIService:
    """Main AI service using dependency injection."""
    
    def __init__(
        self,
        config: ConfigService,
        token_counter: TokenCounter,
        memory: ConversationMemory,
    ):
        self.config = config
        self.token_counter = token_counter
        self.memory = memory
        logger.info("AIService initialized")

    async def process(self, message: str, context: AIContext) -> str:
        # Add to memory
        self.memory.add_message(f"User: {message}")
        
        # Count tokens
        tokens = self.token_counter.count(message)
        context.add_usage(prompt_tokens=tokens)
        
        # Simulate AI response
        response = f"Echo from {self.config.get_model_name()}: {message}"
        self.memory.add_message(f"AI: {response}")
        
        # Update context
        response_tokens = self.token_counter.count(response)
        context.add_usage(completion_tokens=response_tokens)
        
        logger.info(
            f"Processed message. History: {len(self.memory.get_history())} messages, "
            f"Total tokens: {self.token_counter.total_tokens}"
        )
        
        return response


# Example usage with @inject decorator

@inject
async def chat_handler(message: str, ai_service: AIService) -> str:
    """Handler function with automatic dependency injection."""
    context = AIContext(model="gpt-4")
    return await ai_service.process(message, context)


# Factory example

from whiskey.core.decorators import factory


@factory(TokenCounter, scope=ScopeType.SINGLETON)
def create_special_counter(config: ConfigService) -> TokenCounter:
    """Factory for creating a special token counter."""
    counter = TokenCounter(config)
    counter.total_tokens = 100  # Start with 100 tokens
    return counter


async def main():
    """Demonstrate the DI framework."""
    # Set up container first, before imports
    from whiskey.core.decorators import get_default_container
    container = get_default_container()
    
    logger.info("Starting Whiskey example application")
    
    # Example 1: Direct resolution
    logger.info("\n=== Example 1: Direct Resolution ===")
    config_service = await container.resolve(ConfigService)
    logger.info(f"Resolved ConfigService: {config_service.get_model_name()}")
    
    # Example 2: Nested dependencies
    logger.info("\n=== Example 2: Nested Dependencies ===")
    ai_service = await container.resolve(AIService)
    context = AIContext()
    response = await ai_service.process("Hello, World!", context)
    logger.info(f"Response: {response}")
    logger.info(f"Context: {context.to_dict()}")
    
    # Example 3: Using @inject decorator
    logger.info("\n=== Example 3: @inject Decorator ===")
    response = await chat_handler("Test message")
    logger.info(f"Response from handler: {response}")
    
    # Example 4: Scoped services
    logger.info("\n=== Example 4: Scoped Services ===")
    
    # In same conversation scope
    memory1 = await container.resolve(ConversationMemory)
    memory1.add_message("Message 1")
    
    memory2 = await container.resolve(ConversationMemory)
    memory2.add_message("Message 2")
    
    logger.info(f"Same scope - Memory1 == Memory2: {memory1 is memory2}")
    logger.info(f"Messages: {memory2.get_history()}")
    
    # Example 5: Child containers
    logger.info("\n=== Example 5: Child Containers ===")
    child_container = container.create_child()
    
    # Override a service in child
    @dataclass
    class TestConfig(Config):
        api_key: str = "child-test-key"
        model_name: str = "gpt-3.5"
    
    child_container.register_singleton(ConfigService, instance=ConfigService())
    child_config = await child_container.resolve(ConfigService)
    child_config.config = TestConfig()
    
    child_ai = await child_container.resolve(AIService)
    logger.info(f"Child AI uses model: {child_ai.config.get_model_name()}")
    
    # Cleanup
    await container.dispose()
    logger.info("\nExample completed!")


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(msg),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    
    # Run example
    asyncio.run(main())