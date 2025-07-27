"""Simple chat application using Whiskey AI extension."""

from whiskey import Whiskey, inject
from whiskey_ai import LLMClient, MockLLMClient, ToolManager, ai_extension
from whiskey_asgi import Request, StreamingResponse, asgi_extension

# Create application
app = Whiskey()
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
            # Send as Server-Sent Event
            yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# Function calling example
@app.tool(name="get_weather", description="Get weather for a location")
def get_weather(location: str, unit: str = "celsius") -> dict:
    """Get weather information."""
    return {"location": location, "temperature": 22, "unit": unit, "condition": "sunny"}


@app.post("/chat/functions")
@inject
async def chat_with_functions(request: Request, client: LLMClient, tools: ToolManager):
    """Chat endpoint with function calling."""
    data = await request.json()

    # Get all tool schemas
    tool_schemas = tools.all_schemas()

    # Create chat completion with tools
    response = await client.chat.create(
        model="gpt-4", messages=data.get("messages", []), tools=tool_schemas
    )

    # Check if function was called
    if response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name

        # Execute the function
        if function := tools.get(function_name):
            import json

            args = json.loads(tool_call.function.arguments)
            result = function(**args)
            return {"function_called": function_name, "result": result}

    return {"response": response.choices[0].message.content}


# Health check
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "whiskey-ai-chat"}


if __name__ == "__main__":
    app.run()