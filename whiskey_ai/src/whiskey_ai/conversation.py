"""Conversation and chat management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from whiskey import inject

from .extension import LLMClient, Message


@dataclass
class ConversationMetadata:
    """Metadata for a conversation."""

    id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    title: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Conversation:
    """Manages a conversation with an LLM."""

    def __init__(
        self, conversation_id: str, system_prompt: str | None = None, max_messages: int = 100
    ):
        self.metadata = ConversationMetadata(id=conversation_id)
        self.messages: list[Message] = []
        self.max_messages = max_messages

        if system_prompt:
            self.add_message("system", system_prompt)

    def add_message(self, role: str, content: str | None = None, **kwargs) -> Message:
        """Add a message to the conversation."""
        message = Message(role=role, content=content, **kwargs)
        self.messages.append(message)
        self.metadata.updated_at = time.time()

        # Trim old messages if needed
        if len(self.messages) > self.max_messages:
            # Keep system message if present
            if self.messages[0].role == "system":
                self.messages = [self.messages[0], *self.messages[-(self.max_messages - 1) :]]
            else:
                self.messages = self.messages[-self.max_messages :]

        return message

    def get_messages(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get messages in dict format for API calls."""
        messages = self.messages[-limit:] if limit else self.messages

        return [
            {
                k: v
                for k, v in {
                    "role": msg.role,
                    "content": msg.content,
                    "name": msg.name,
                    "tool_calls": msg.tool_calls,
                    "function_call": msg.function_call,
                }.items()
                if v is not None
            }
            for msg in messages
        ]

    def get_last_user_message(self) -> str | None:
        """Get the last user message."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None

    def get_last_assistant_message(self) -> str | None:
        """Get the last assistant message."""
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg.content
        return None

    def clear(self):
        """Clear all messages except system prompt."""
        system_msg = None
        if self.messages and self.messages[0].role == "system":
            system_msg = self.messages[0]

        self.messages.clear()
        if system_msg:
            self.messages.append(system_msg)

        self.metadata.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert conversation to dict."""
        return {
            "metadata": {
                "id": self.metadata.id,
                "created_at": self.metadata.created_at,
                "updated_at": self.metadata.updated_at,
                "title": self.metadata.title,
                "tags": self.metadata.tags,
                "metadata": self.metadata.metadata,
            },
            "messages": self.get_messages(),
        }


class ConversationManager:
    """Manages multiple conversations."""

    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def create(
        self, conversation_id: str, system_prompt: str | None = None, **kwargs
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(conversation_id, system_prompt=system_prompt, **kwargs)
        self.conversations[conversation_id] = conversation
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)

    def get_or_create(
        self, conversation_id: str, system_prompt: str | None = None, **kwargs
    ) -> Conversation:
        """Get or create a conversation."""
        conversation = self.get(conversation_id)
        if not conversation:
            conversation = self.create(conversation_id, system_prompt=system_prompt, **kwargs)
        return conversation

    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            return True
        return False

    def list_conversations(self) -> list[ConversationMetadata]:
        """List all conversation metadata."""
        return [conv.metadata for conv in self.conversations.values()]


class ChatSession:
    """High-level chat session with an LLM."""

    @inject
    def __init__(
        self,
        client: LLMClient,
        conversation: Conversation,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        self.client = client
        self.conversation = conversation
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def send_message(self, message: str, **kwargs) -> str:
        """Send a message and get a response."""
        # Add user message
        self.conversation.add_message("user", message)

        # Get response
        response = await self.client.chat.create(
            model=self.model,
            messages=self.conversation.get_messages(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs,
        )

        # Add assistant response
        assistant_message = response.choices[0].message
        self.conversation.add_message(
            "assistant",
            content=assistant_message.content,
            tool_calls=assistant_message.tool_calls,
            function_call=assistant_message.function_call,
        )

        return assistant_message.content

    async def stream_message(self, message: str, **kwargs):
        """Send a message and stream the response."""
        # Add user message
        self.conversation.add_message("user", message)

        # Stream response
        stream = await self.client.chat.create(
            model=self.model,
            messages=self.conversation.get_messages(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            **kwargs,
        )

        # Collect full response
        full_content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_content += content
                yield content

        # Add complete response to conversation
        self.conversation.add_message("assistant", full_content)

    def reset(self):
        """Reset the conversation."""
        self.conversation.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """Get conversation history."""
        return self.conversation.get_messages()
