"""Conversation management example using Whiskey AI extension."""

import uuid

from whiskey import Application, inject
from whiskey_ai import ai_extension, MockLLMClient, LLMClient
from whiskey_ai.conversation import ConversationManager, ChatSession
from whiskey_asgi import asgi_extension, Request


# Create application
app = Application()
app.use(ai_extension)
app.use(asgi_extension)

# Register mock model
@app.model("mock")
class MockModel(MockLLMClient):
    pass

app.configure_model("mock")

# Register conversation manager as singleton
app.container[ConversationManager] = ConversationManager()

# Setup default client
@app.on_startup
async def setup():
    app.container[LLMClient] = app.get_model("mock")


# Conversation endpoints
@app.post("/conversations")
@inject
async def create_conversation(request: Request, manager: ConversationManager):
    """Create a new conversation."""
    data = await request.json()
    
    conversation_id = data.get("id", str(uuid.uuid4()))
    system_prompt = data.get("system_prompt", "You are a helpful AI assistant.")
    
    conversation = manager.create(
        conversation_id=conversation_id,
        system_prompt=system_prompt
    )
    
    # Set optional metadata
    if "title" in data:
        conversation.metadata.title = data["title"]
    if "tags" in data:
        conversation.metadata.tags = data["tags"]
    
    return {
        "id": conversation_id,
        "created": True,
        "metadata": {
            "created_at": conversation.metadata.created_at,
            "title": conversation.metadata.title,
            "tags": conversation.metadata.tags
        }
    }


@app.get("/conversations")
@inject
async def list_conversations(manager: ConversationManager):
    """List all conversations."""
    conversations = manager.list_conversations()
    
    return {
        "conversations": [
            {
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "tags": conv.tags
            }
            for conv in conversations
        ],
        "count": len(conversations)
    }


@app.get("/conversations/{conversation_id}")
@inject
async def get_conversation(conversation_id: str, manager: ConversationManager):
    """Get a specific conversation."""
    conversation = manager.get(conversation_id)
    
    if not conversation:
        return {"error": "Conversation not found"}, 404
    
    return conversation.to_dict()


@app.delete("/conversations/{conversation_id}")
@inject
async def delete_conversation(conversation_id: str, manager: ConversationManager):
    """Delete a conversation."""
    deleted = manager.delete(conversation_id)
    
    if not deleted:
        return {"error": "Conversation not found"}, 404
    
    return {"deleted": True, "id": conversation_id}


@app.post("/conversations/{conversation_id}/messages")
@inject
async def send_message(
    conversation_id: str,
    request: Request,
    manager: ConversationManager,
    client: LLMClient
):
    """Send a message to a conversation."""
    data = await request.json()
    message = data.get("message", "")
    
    # Get or create conversation
    conversation = manager.get_or_create(conversation_id)
    
    # Create chat session
    session = ChatSession(
        client=client,
        conversation=conversation,
        model=data.get("model", "gpt-4"),
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens")
    )
    
    # Send message and get response
    response = await session.send_message(message)
    
    return {
        "conversation_id": conversation_id,
        "message": message,
        "response": response,
        "message_count": len(conversation.messages)
    }


@app.post("/conversations/{conversation_id}/messages/stream")
@inject
async def stream_message(
    conversation_id: str,
    request: Request,
    manager: ConversationManager,
    client: LLMClient
):
    """Stream a message response."""
    import json
    
    data = await request.json()
    message = data.get("message", "")
    
    # Get or create conversation
    conversation = manager.get_or_create(conversation_id)
    
    # Create chat session
    session = ChatSession(
        client=client,
        conversation=conversation,
        model=data.get("model", "gpt-4"),
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens")
    )
    
    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"
        
        async for chunk in session.stream_message(message):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done', 'message_count': len(conversation.messages)})}\n\n"
        yield "data: [DONE]\n\n"
    
    from whiskey_asgi.extension import StreamingResponse
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/conversations/{conversation_id}/summarize")
@inject
async def summarize_conversation(
    conversation_id: str,
    manager: ConversationManager,
    client: LLMClient
):
    """Summarize a conversation."""
    conversation = manager.get(conversation_id)
    
    if not conversation:
        return {"error": "Conversation not found"}, 404
    
    # Get conversation history
    messages = conversation.get_messages()
    
    if len(messages) < 2:
        return {"error": "Conversation too short to summarize"}, 400
    
    # Create summary prompt
    conversation_text = "\n".join(
        f"{msg['role']}: {msg['content']}" 
        for msg in messages 
        if msg.get('content')
    )
    
    summary_prompt = f"""Summarize the following conversation:

{conversation_text}

Summary:"""
    
    # Get summary
    response = await client.chat.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=200
    )
    
    summary = response.choices[0].message.content
    
    # Update conversation title if not set
    if not conversation.metadata.title:
        conversation.metadata.title = summary[:50] + "..."
    
    return {
        "conversation_id": conversation_id,
        "summary": summary,
        "message_count": len(messages)
    }


@app.post("/conversations/{conversation_id}/clear")
@inject
async def clear_conversation(conversation_id: str, manager: ConversationManager):
    """Clear conversation history."""
    conversation = manager.get(conversation_id)
    
    if not conversation:
        return {"error": "Conversation not found"}, 404
    
    conversation.clear()
    
    return {
        "conversation_id": conversation_id,
        "cleared": True,
        "message_count": len(conversation.messages)
    }


# Home endpoint
@app.get("/")
async def index():
    """API information."""
    return {
        "name": "Whiskey AI Conversation Example",
        "endpoints": {
            "GET /": "This page",
            "POST /conversations": "Create a new conversation",
            "GET /conversations": "List all conversations",
            "GET /conversations/{id}": "Get conversation details",
            "DELETE /conversations/{id}": "Delete a conversation",
            "POST /conversations/{id}/messages": "Send a message",
            "POST /conversations/{id}/messages/stream": "Stream a message response",
            "POST /conversations/{id}/summarize": "Summarize conversation",
            "POST /conversations/{id}/clear": "Clear conversation history"
        },
        "features": [
            "Multi-conversation management",
            "Message history tracking",
            "Streaming responses",
            "Conversation summarization",
            "Metadata and tagging"
        ]
    }


if __name__ == "__main__":
    print("Starting Whiskey AI Conversation Example...")
    print("API available at http://localhost:8000")
    print("\nExample requests:")
    print("\n1. Create conversation:")
    print('curl -X POST http://localhost:8000/conversations \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"title": "My Chat", "system_prompt": "You are a helpful assistant."}\'')
    print("\n2. Send message:")
    print('curl -X POST http://localhost:8000/conversations/{id}/messages \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "Hello!"}\'')
    print("\n3. List conversations:")
    print("curl http://localhost:8000/conversations")
    
    app.run_asgi(port=8000)