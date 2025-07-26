# Whiskey AI Extension 🤖

Build intelligent applications with Whiskey's AI/LLM integration. This extension provides specialized scopes, dependency injection patterns, and utilities designed specifically for AI-powered applications.

## Why Whiskey AI?

While you can use any LLM library with Whiskey, this extension provides:

- **AI-Specific Scopes**: `conversation`, `session`, and `ai_context` scopes for managing state
- **Agent Framework**: Build complex AI agents with dependency injection
- **LLM Abstraction**: Swap between OpenAI, Anthropic, or custom models seamlessly
- **Conversation Management**: Automatic conversation history and context tracking
- **Tool Integration**: Function calling with automatic DI
- **Event-Driven AI**: React to AI events throughout your application

## Installation

```bash
pip install whiskey[ai]  # Includes whiskey-ai
# or
pip install whiskey-ai
```

## Quick Start

```python
from whiskey import Application, inject
from whiskey_ai import ai_extension

# Create app with AI extension
app = Application()
app.use(ai_extension)

# Configure your LLM
app.configure_llm(
    provider="openai",
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4"
)

# Define an AI agent
@app.agent("assistant")
class AssistantAgent:
    """A helpful AI assistant."""
    
    def __init__(self):
        self.system_prompt = """You are a helpful AI assistant. 
        Be concise, accurate, and friendly."""
    
    @inject
    async def process(
        self,
        message: str,
        llm: LLMClient,
        context: ConversationContext
    ) -> str:
        # Add user message to context
        context.add_message("user", message)
        
        # Get LLM response
        response = await llm.complete(
            messages=context.messages,
            system=self.system_prompt
        )
        
        # Save and return response
        context.add_message("assistant", response)
        return response

# Use the agent
@app.main
@inject
async def main():
    agent = await app.container.resolve(AssistantAgent)
    response = await agent.process("What is dependency injection?")
    print(response)

if __name__ == "__main__":
    app.run()
```

## Core Features

### 1. AI-Specific Scopes

Manage state at different levels of your AI application:

```python
# Session scope - persists across conversations
@scoped("session")
class UserPreferences:
    def __init__(self):
        self.language = "en"
        self.style = "professional"
        self.history = []

# Conversation scope - single conversation
@scoped("conversation")
class ConversationContext:
    def __init__(self):
        self.messages = []
        self.metadata = {}
        self.start_time = time.time()
    
    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

# AI context scope - single AI operation
@scoped("ai_context")
class TokenTracker:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0
```

### 2. Agent Framework

Build sophisticated AI agents with full DI support:

```python
@app.agent("researcher")
class ResearchAgent:
    """An agent that researches topics using multiple sources."""
    
    def __init__(self):
        self.tools = ["web_search", "arxiv", "wikipedia"]
    
    @inject
    async def research(
        self,
        topic: str,
        llm: LLMClient,
        search: SearchService
    ) -> dict:
        # Search for information
        results = await search.query(topic, sources=self.tools)
        
        # Synthesize with LLM
        synthesis = await llm.complete(
            f"Synthesize these research results about {topic}: {results}",
            max_tokens=1000
        )
        
        return {
            "topic": topic,
            "sources": results,
            "synthesis": synthesis
        }

# Compose agents
@app.agent("writer")
class WriterAgent:
    @inject
    async def write_article(
        self,
        topic: str,
        researcher: ResearchAgent,
        llm: LLMClient
    ) -> str:
        # Use another agent
        research = await researcher.research(topic)
        
        # Write article based on research
        article = await llm.complete(
            f"Write an article about {topic} using: {research['synthesis']}",
            max_tokens=2000
        )
        
        return article
```

### 3. LLM Abstraction

Swap LLM providers without changing your code:

```python
# Configure different providers
app.configure_llm(
    provider="openai",  # or "anthropic", "cohere", "local"
    api_key=os.getenv("API_KEY"),
    model="gpt-4",
    temperature=0.7
)

# Use consistently across your app
@inject
async def generate_response(
    prompt: str,
    llm: Annotated[LLMClient, Inject()]
) -> str:
    # Works with any configured provider
    return await llm.complete(prompt)

# Custom LLM implementation
@app.component
class CustomLLM(LLMClient):
    async def complete(self, prompt: str, **kwargs) -> str:
        # Your custom implementation
        return await self.model.generate(prompt)
```

### 4. Tool Integration

Enable function calling with automatic dependency injection:

```python
@app.tool("get_weather", description="Get current weather for a location")
@inject
async def get_weather(
    location: str,
    weather_api: Annotated[WeatherService, Inject()]
) -> dict:
    """Get weather data for the specified location."""
    return await weather_api.get_current(location)

@app.tool("send_email", description="Send an email")
@inject
async def send_email(
    to: str,
    subject: str,
    body: str,
    email_service: Annotated[EmailService, Inject()]
) -> dict:
    """Send an email to the specified recipient."""
    await email_service.send(to=to, subject=subject, body=body)
    return {"status": "sent", "to": to}

# Agent with tools
@app.agent("assistant")
class ToolUsingAssistant:
    def __init__(self):
        self.tools = ["get_weather", "send_email"]
    
    @inject
    async def process(
        self,
        message: str,
        llm: Annotated[LLMClient, Inject()],
        tool_registry: Annotated[ToolRegistry, Inject()]
    ) -> str:
        # LLM decides which tools to use
        response = await llm.complete(
            message,
            tools=tool_registry.get_tools(self.tools),
            tool_choice="auto"
        )
        
        # Execute any tool calls
        if response.tool_calls:
            for call in response.tool_calls:
                result = await tool_registry.execute(
                    call.name,
                    call.arguments
                )
                # Process tool results...
        
        return response.content
```

### 5. Conversation Management

Automatic conversation history and context:

```python
@app.component
class ChatService:
    @inject
    async def chat(
        self,
        message: str,
        context: Annotated[ConversationContext, Inject()],
        llm: Annotated[LLMClient, Inject()],
        preferences: Annotated[UserPreferences, Inject()]
    ) -> str:
        # Add user message
        context.add_message("user", message)
        
        # Include system prompt based on preferences
        system_prompt = f"""
        Language: {preferences.language}
        Style: {preferences.style}
        """
        
        # Get response with full context
        response = await llm.complete(
            messages=context.messages,
            system=system_prompt
        )
        
        # Save response
        context.add_message("assistant", response)
        
        # Emit event for analytics
        await app.emit("chat.message", {
            "user_message": message,
            "assistant_response": response,
            "conversation_length": len(context.messages)
        })
        
        return response
```

### 6. Streaming Support

Handle streaming responses with backpressure:

```python
@app.get("/chat/stream")
@inject
async def stream_chat(
    message: str,
    llm: Annotated[LLMClient, Inject()],
    context: Annotated[ConversationContext, Inject()]
):
    context.add_message("user", message)
    
    # Stream response
    async def generate():
        stream = await llm.stream(
            messages=context.messages,
            temperature=0.7
        )
        
        full_response = ""
        async for chunk in stream:
            full_response += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        
        # Save complete response
        context.add_message("assistant", full_response)
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### 7. Memory Systems

Implement various memory patterns:

```python
# Short-term memory (conversation scope)
@scoped("conversation")
class ShortTermMemory:
    def __init__(self):
        self.facts = []
        self.topics = set()
    
    def remember(self, fact: str, topic: str):
        self.facts.append(fact)
        self.topics.add(topic)

# Long-term memory (singleton with vector store)
@singleton
class LongTermMemory:
    def __init__(self):
        self.vector_store = ChromaDB()
    
    async def store(self, text: str, metadata: dict):
        embedding = await self.embed(text)
        await self.vector_store.add(embedding, metadata)
    
    async def recall(self, query: str, k: int = 5):
        embedding = await self.embed(query)
        return await self.vector_store.search(embedding, k)

# Episodic memory
@app.component
class EpisodicMemory:
    @inject
    async def remember_interaction(
        self,
        interaction: dict,
        short_term: Annotated[ShortTermMemory, Inject()],
        long_term: Annotated[LongTermMemory, Inject()]
    ):
        # Store in short-term
        short_term.remember(
            interaction["summary"],
            interaction["topic"]
        )
        
        # Store important things in long-term
        if interaction["importance"] > 0.7:
            await long_term.store(
                interaction["content"],
                {"timestamp": time.time(), **interaction}
            )
```

## Advanced Patterns

### Multi-Agent Systems

```python
@app.component
class OrchestratorAgent:
    @inject
    async def solve_complex_task(
        self,
        task: str,
        researcher: Annotated[ResearchAgent, Inject()],
        analyst: Annotated[AnalystAgent, Inject()],
        writer: Annotated[WriterAgent, Inject()]
    ) -> dict:
        # Break down the task
        subtasks = await self.decompose_task(task)
        
        # Assign to specialized agents
        research_results = await researcher.research(subtasks["research"])
        analysis = await analyst.analyze(research_results)
        report = await writer.write_report(analysis)
        
        return {
            "task": task,
            "research": research_results,
            "analysis": analysis,
            "report": report
        }
```

### RAG (Retrieval Augmented Generation)

```python
@app.component
class RAGService:
    @inject
    async def answer_with_context(
        self,
        question: str,
        retriever: Annotated[DocumentRetriever, Inject()],
        llm: Annotated[LLMClient, Inject()]
    ) -> str:
        # Retrieve relevant documents
        docs = await retriever.search(question, k=5)
        
        # Build context
        context = "\n\n".join([
            f"Document {i+1}: {doc.content}"
            for i, doc in enumerate(docs)
        ])
        
        # Generate answer with context
        prompt = f"""
        Context:
        {context}
        
        Question: {question}
        
        Answer based on the context provided.
        """
        
        return await llm.complete(prompt)
```

### Chain of Thought

```python
@app.agent("reasoner")
class ReasoningAgent:
    @inject
    async def reason_through(
        self,
        problem: str,
        llm: Annotated[LLMClient, Inject()]
    ) -> dict:
        # Step 1: Understand the problem
        understanding = await llm.complete(
            f"Break down this problem: {problem}"
        )
        
        # Step 2: Generate approach
        approach = await llm.complete(
            f"Given this understanding: {understanding}, "
            f"what's the best approach?"
        )
        
        # Step 3: Execute step by step
        steps = []
        for step in approach.split("\n"):
            result = await llm.complete(
                f"Execute this step: {step}"
            )
            steps.append({"step": step, "result": result})
        
        # Step 4: Synthesize
        conclusion = await llm.complete(
            f"Synthesize these results: {steps}"
        )
        
        return {
            "problem": problem,
            "reasoning_chain": steps,
            "conclusion": conclusion
        }
```

## Testing AI Applications

```python
import pytest
from whiskey.testing import create_test_container

@pytest.fixture
def test_container():
    container = create_test_container()
    
    # Mock LLM for testing
    container[LLMClient] = MockLLM(
        responses={
            "test prompt": "test response",
            "weather": "sunny and 72°F"
        }
    )
    
    return container

@pytest.mark.asyncio
async def test_agent(test_container):
    agent = await test_container.resolve(AssistantAgent)
    response = await agent.process("test prompt")
    assert response == "test response"

@pytest.mark.asyncio
async def test_conversation_context(test_container):
    async with test_container.scope("conversation"):
        context = await test_container.resolve(ConversationContext)
        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there!")
        
        assert len(context.messages) == 2
        assert context.messages[0]["role"] == "user"
```

## Configuration

### Environment Variables

```bash
# LLM Configuration
AI_PROVIDER=openai              # openai, anthropic, cohere, local
AI_API_KEY=your-api-key
AI_MODEL=gpt-4
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000

# Memory Configuration
AI_MEMORY_TYPE=chroma          # chroma, pinecone, weaviate
AI_MEMORY_COLLECTION=whiskey

# Rate Limiting
AI_RATE_LIMIT_REQUESTS=60      # per minute
AI_RATE_LIMIT_TOKENS=100000    # per minute

# Monitoring
AI_ENABLE_MONITORING=true
AI_LOG_PROMPTS=false           # PII consideration
```

### Programmatic Configuration

```python
from whiskey_config import config_extension

app.use(config_extension)

@dataclass
class AIConfig:
    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = 0.7
    max_retries: int = 3
    timeout: int = 30

app.configure_config(
    schema=AIConfig,
    sources=["ai_config.yaml", "ENV"],
    env_prefix="AI_"
)
```

## Best Practices

### 1. Use Appropriate Scopes

```python
# ✅ Session scope for user preferences
@scoped("session")
class UserProfile:
    def __init__(self):
        self.preferences = {}

# ✅ Conversation scope for chat history  
@scoped("conversation")
class ChatHistory:
    def __init__(self):
        self.messages = []

# ❌ Don't use singleton for user-specific data
@singleton  
class UserData:  # Wrong - shared across all users!
    pass
```

### 2. Handle Errors Gracefully

```python
@app.agent("safe_assistant")
class SafeAssistant:
    @inject
    async def process(
        self,
        message: str,
        llm: Annotated[LLMClient, Inject()]
    ) -> str:
        try:
            return await llm.complete(message)
        except RateLimitError:
            return "I'm currently busy. Please try again in a moment."
        except APIError as e:
            await app.emit("ai.error", {"error": str(e)})
            return "I encountered an error. Please try again."
```

### 3. Monitor Token Usage

```python
@app.on("ai.completion")
async def track_usage(event_data):
    tokens = event_data["usage"]["total_tokens"]
    cost = calculate_cost(tokens, event_data["model"])
    
    await metrics.increment(
        "ai.tokens.used",
        tokens,
        tags={"model": event_data["model"]}
    )
```

## Examples

See the `examples/` directory for complete examples:
- `chatbot.py` - Simple chatbot with memory
- `agent_system.py` - Multi-agent research system  
- `rag_app.py` - RAG application with vector store
- `streaming_chat.py` - Streaming chat with WebSockets

## Contributing

We welcome contributions! See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.