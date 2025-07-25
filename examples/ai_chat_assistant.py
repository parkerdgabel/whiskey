"""Example: AI Chat Assistant using Whiskey's AI features.

This example demonstrates:
- Prompt templates with validation
- Resource management (rate limiting, token tracking)
- Streaming responses with real-time processing
- Observability with metrics collection
- Integration with DI container
"""

import asyncio
import json
from typing import AsyncIterator

from whiskey import Application, inject

# Note: This example requires the AI plugin to be installed:
# pip install whiskey[ai]
from whiskey_ai import (
    AIContext,
    AIMetricsCollector,
    AIResourceManager,
    ChatCompletionChunk,
    MockChatModel,
    PromptRegistry,
    PromptTemplate,
    PromptVariable,
    StreamProcessor,
)
from whiskey_ai.prompts import LengthValidator, TypeValidator
from whiskey_ai.resources.manager import ResourceConfig


# Create the application
app = Application()


# Define custom services
@app.service
class ChatAssistant:
    """AI-powered chat assistant with resource management."""
    
    def __init__(
        self,
        model: MockChatModel,
        prompt_registry: PromptRegistry,
        resource_manager: AIResourceManager,
        stream_processor: StreamProcessor,
        metrics: AIMetricsCollector
    ):
        self.model = model
        self.prompts = prompt_registry
        self.resources = resource_manager
        self.processor = stream_processor
        self.metrics = metrics
        
        # Configure resources
        asyncio.create_task(self._configure_resources())
    
    async def _configure_resources(self):
        """Configure resource limits."""
        await self.resources.configure_model(
            "mock-gpt-4",
            ResourceConfig(
                max_tokens_per_minute=10000,
                max_requests_per_minute=60,
                max_cost_per_hour=10.0
            )
        )
    
    async def chat(
        self,
        user_input: str,
        context: AIContext,
        stream: bool = True
    ) -> str:
        """Process a chat message."""
        # Check rate limits
        if not await self.resources.check_rate_limit("mock-gpt-4"):
            raise Exception("Rate limit exceeded")
        
        # Acquire request slot
        if not await self.resources.acquire_request_slot("mock-gpt-4"):
            raise Exception("Too many concurrent requests")
        
        # Get and render prompt
        template = self.prompts.get_required("chat")
        prompt = template.render(user_input=user_input)
        
        # Estimate tokens and acquire them
        estimated_tokens = len(prompt.split()) * 2  # Simple estimation
        token_leases = await self.resources.acquire_tokens(
            "mock-gpt-4",
            estimated_tokens
        )
        
        if not token_leases:
            raise Exception("Insufficient token quota")
        
        try:
            # Create messages for the model
            from whiskey_ai import Message
            messages = [
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content=prompt)
            ]
            
            if stream:
                # Stream response
                response_stream = await self.model.create(
                    messages=messages,
                    model="mock-gpt-4",
                    stream=True
                )
                
                # Process stream with callbacks
                collected_content = []
                
                def on_chunk(content: str, index: int):
                    print(f"[Chunk {index}] {content}", end="", flush=True)
                    collected_content.append(content)
                
                content, stats = await self.processor.process_stream(
                    response_stream,
                    on_chunk=on_chunk
                )
                
                print()  # New line after streaming
                print(f"\n📊 Stream stats: {stats.total_chunks} chunks, "
                      f"{stats.total_tokens} tokens, {stats.duration_ms:.0f}ms")
                
                return content
            else:
                # Non-streaming response
                response = await self.model.create(
                    messages=messages,
                    model="mock-gpt-4",
                    stream=False
                )
                
                # Update context with usage
                if response.usage:
                    context.add_usage(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens
                    )
                
                return response.choices[0].message.content
                
        finally:
            # Release tokens
            for lease in token_leases:
                await lease.release()


# Initialize prompt templates
@app.on_startup
async def setup_prompts(prompt_registry: PromptRegistry):
    """Set up prompt templates."""
    # Chat prompt with validation
    chat_template = PromptTemplate(
        template="User: {user_input}\nAssistant:",
        variables=[
            PromptVariable(
                name="user_input",
                description="The user's chat message",
                required=True,
                validators=[
                    TypeValidator(str),
                    LengthValidator(min_length=1, max_length=1000)
                ]
            )
        ]
    )
    
    prompt_registry.register("chat", chat_template)
    
    # System prompt for different personas
    system_template = PromptTemplate(
        template="You are a {persona}. {instructions}",
        variables=[
            PromptVariable(
                name="persona",
                description="Assistant persona",
                default="helpful AI assistant",
                required=False
            ),
            PromptVariable(
                name="instructions",
                description="Additional instructions",
                default="Be concise and friendly.",
                required=False
            )
        ]
    )
    
    prompt_registry.register("system", system_template)
    
    print("✅ Prompt templates initialized")


# Metrics reporting
@app.task(interval=30)  # Every 30 seconds
async def report_metrics(metrics: AIMetricsCollector):
    """Report AI metrics periodically."""
    all_metrics = metrics.get_all_metrics()
    
    if all_metrics:
        print("\n📊 AI Metrics Report:")
        for model, model_metrics in all_metrics.items():
            print(f"\n  Model: {model}")
            print(f"    Requests: {model_metrics['requests']['total']} "
                  f"(success: {model_metrics['requests']['success_rate']:.1%})")
            print(f"    Tokens: {model_metrics['tokens']['total']} "
                  f"(avg: {model_metrics['tokens']['average_per_request']:.1f})")
            print(f"    Cost: ${model_metrics['cost']['total']:.4f}")
            print(f"    Latency: {model_metrics['duration']['average_ms']:.0f}ms "
                  f"(p95: {model_metrics['duration']['p95_ms']:.0f}ms)")


# Example usage with dependency injection
@inject
async def process_message(
    message: str,
    assistant: ChatAssistant,
    context_factory: AIContext = None  # Will be injected
) -> str:
    """Process a chat message with automatic dependency injection."""
    # Create a new context for this conversation
    context = context_factory or AIContext()
    
    try:
        print(f"\n💬 User: {message}")
        response = await assistant.chat(message, context, stream=True)
        
        # Show context info
        print(f"\n📈 Usage: {context.total_tokens} tokens, "
              f"${context.total_cost:.4f}")
        
        return response
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


# Main application
async def main():
    """Run the chat assistant example."""
    print("🤖 Whiskey AI Chat Assistant Example")
    print("=" * 50)
    
    # Start the application
    await app.start()
    
    try:
        # Example conversations
        messages = [
            "Hello! How are you today?",
            "What's the weather like?",
            "Tell me a short joke.",
            "What are the benefits of dependency injection?",
        ]
        
        for msg in messages:
            await process_message(msg)
            await asyncio.sleep(1)  # Pause between messages
        
        # Show final metrics
        await asyncio.sleep(2)
        
        # Get resource availability
        manager = await app.container.resolve(AIResourceManager)
        availability = await manager.get_token_availability("mock-gpt-4")
        print(f"\n🔋 Token availability: {availability}")
        
    finally:
        # Shutdown
        await app.stop()
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())