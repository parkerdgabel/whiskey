"""Simple chat application using Whiskey AI extension."""

from whiskey import inject
from whiskey_ai import LLMClient, MockLLMClient, ai_extension
from whiskey_asgi import Request, asgi_extension

# Create application
app = Application()
app.use(ai_extension)
app.use(asgi_extension)


# Register mock LLM client as the model
@app.model("mock")
class MockModel(MockLLMClient):
    pass


# Configure the model
app.configure_model("mock")


# Set as default LLM client
@app.on_startup
async def setup():
    app.container[LLMClient] = app.get_model("mock")


# Simple chat endpoint
@app.post("/chat")
@inject
async def chat(request: Request, client: LLMClient):
    """Simple chat endpoint."""
    data = await request.json()

    # Create chat completion
    response = await client.chat.create(model="gpt-4", messages=data.get("messages", []))

    return {
        "response": response.choices[0].message.content,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


# Streaming chat endpoint
@app.post("/chat/stream")
@inject
async def stream_chat(request: Request, client: LLMClient):
    """Streaming chat endpoint."""
    import json

    data = await request.json()

    async def generate():
        # Stream response
        stream = await client.chat.create(
            model="gpt-4", messages=data.get("messages", []), stream=True
        )

        async for chunk in stream:
            # Send as Server-Sent Events
            yield f"data: {json.dumps(chunk.model_dump())}\n\n"

        yield "data: [DONE]\n\n"

    # Return streaming response
    from whiskey_asgi.extension import StreamingResponse

    return StreamingResponse(generate(), media_type="text/event-stream")


# Chat with tools
@app.tool("get_weather")
def get_weather(location: str, unit: str = "celsius") -> dict:
    """Get the current weather for a location."""
    # Mock weather data
    return {
        "location": location,
        "temperature": 22 if unit == "celsius" else 72,
        "unit": unit,
        "conditions": "Partly cloudy",
    }


@app.post("/chat/tools")
@inject
async def chat_with_tools(request: Request, client: LLMClient, tools: "ToolManager"):
    """Chat endpoint with tool support."""
    from whiskey_ai.tools import ToolExecutor

    data = await request.json()

    # Get tool schemas
    tool_schemas = tools.all_schemas()

    # Create chat completion with tools
    response = await client.chat.create(
        model="gpt-4", messages=data.get("messages", []), tools=tool_schemas, tool_choice="auto"
    )

    message = response.choices[0].message

    # Handle tool calls
    if message.tool_calls:
        # Execute tools
        executor = ToolExecutor(tools)
        tool_results = await executor.execute_all(message.tool_calls)

        # Add tool results to messages
        messages = data.get("messages", [])
        messages.append(
            {"role": "assistant", "content": message.content, "tool_calls": message.tool_calls}
        )

        for result in tool_results:
            messages.append(
                {
                    "role": "tool",
                    "content": json.dumps(result.get("result", result)),
                    "tool_call_id": result.get("tool_call_id"),
                }
            )

        # Get final response
        response = await client.chat.create(model="gpt-4", messages=messages)

        message = response.choices[0].message

    return {"response": message.content, "tool_calls": message.tool_calls}


# Health check
@app.get("/")
async def index():
    """API information."""
    return {
        "name": "Whiskey AI Chat Example",
        "endpoints": {
            "POST /chat": "Simple chat completion",
            "POST /chat/stream": "Streaming chat completion",
            "POST /chat/tools": "Chat with tool/function calling",
        },
        "model": "mock (for testing)",
    }


if __name__ == "__main__":
    print("Starting Whiskey AI Chat Example...")
    print("API available at http://localhost:8000")
    print("\nExample request:")
    print("curl -X POST http://localhost:8000/chat \\")
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"messages": [{"role": "user", "content": "Hello!"}]}\'')

    app.run_asgi(port=8000)
