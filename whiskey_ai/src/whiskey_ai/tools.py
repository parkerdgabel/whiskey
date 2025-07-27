"""Built-in tools for AI agents."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from whiskey import inject

from .extension import LLMClient, ToolCall, ToolManager


class ToolExecutor:
    """Executes tool calls from LLM responses."""

    @inject
    def __init__(self, tools: ToolManager):
        self.tools = tools

    async def execute(self, tool_call: ToolCall) -> dict[str, Any]:
        """Execute a single tool call."""
        tool_name = tool_call.function.name
        tool = self.tools.get(tool_name)

        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.tools.tools.keys()),
            }

        try:
            # Parse arguments
            args = json.loads(tool_call.function.arguments)

            # Execute tool
            if asyncio.iscoroutinefunction(tool):
                result = await tool(**args)
            else:
                result = tool(**args)

            return {"tool_call_id": tool_call.id, "result": result}

        except json.JSONDecodeError as e:
            return {"tool_call_id": tool_call.id, "error": f"Invalid JSON arguments: {e}"}
        except Exception as e:
            return {"tool_call_id": tool_call.id, "error": f"Tool execution failed: {e}"}

    async def execute_all(self, tool_calls: list[ToolCall]) -> list[dict[str, Any]]:
        """Execute multiple tool calls concurrently."""
        tasks = [self.execute(call) for call in tool_calls]
        return await asyncio.gather(*tasks)


# Example built-in tools
def calculate(expression: str) -> float:
    """Safely evaluate a mathematical expression.

    Args:
        expression: Mathematical expression to evaluate

    Returns:
        The result of the calculation
    """
    # Safe evaluation of math expressions
    import ast
    import operator

    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def eval_expr(node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return ops[type(node.op)](eval_expr(node.left), eval_expr(node.right))
        elif isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](eval_expr(node.operand))
        else:
            raise TypeError(f"Unsupported operation: {node}")

    tree = ast.parse(expression, mode="eval")
    return eval_expr(tree.body)


async def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web for information.

    Args:
        query: Search query
        max_results: Maximum number of results to return

    Returns:
        List of search results with title, url, and snippet
    """
    # This is a mock implementation
    # In production, integrate with a real search API
    await asyncio.sleep(0.1)  # Simulate API call

    results = []
    for i in range(min(max_results, 3)):
        results.append(
            {
                "title": f"Result {i + 1} for '{query}'",
                "url": f"https://example.com/search?q={query}&page={i + 1}",
                "snippet": f"This is a snippet for search result {i + 1} about {query}...",
            }
        )

    return results


def get_current_time(timezone: str | None = None) -> str:
    """Get the current time.

    Args:
        timezone: Optional timezone name (e.g., 'America/New_York')

    Returns:
        Current time as ISO format string
    """
    from datetime import datetime

    import pytz

    if timezone:
        try:
            tz = pytz.timezone(timezone)
            dt = datetime.now(tz)
        except pytz.UnknownTimeZoneError:
            return f"Unknown timezone: {timezone}"
    else:
        dt = datetime.now()

    return dt.isoformat()


class ConversationTools:
    """Tools for managing conversations."""

    @inject
    def __init__(self, client: LLMClient):
        self.client = client

    async def summarize_conversation(
        self, messages: list[dict[str, str]], style: str = "concise"
    ) -> str:
        """Summarize a conversation.

        Args:
            messages: List of messages to summarize
            style: Style of summary (concise, detailed, bullet-points)

        Returns:
            Summary of the conversation
        """
        # Create summarization prompt
        conversation_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in messages)

        prompt = f"""Summarize the following conversation in {style} style:

{conversation_text}

Summary:"""

        response = await self.client.chat.create(
            model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], max_tokens=200
        )

        return response.choices[0].message.content

    async def extract_action_items(self, messages: list[dict[str, str]]) -> list[str]:
        """Extract action items from a conversation.

        Args:
            messages: List of messages to analyze

        Returns:
            List of action items
        """
        conversation_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in messages)

        prompt = f"""Extract all action items from this conversation.
Return them as a JSON array of strings.

{conversation_text}

Action items:"""

        response = await self.client.chat.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response.choices[0].message.content)
            return result.get("action_items", [])
        except (json.JSONDecodeError, AttributeError, KeyError):
            return []
