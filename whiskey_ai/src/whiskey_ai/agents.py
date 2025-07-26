"""Agent framework for building AI-powered assistants."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from whiskey import inject

from .extension import AgentManager, LLMClient, Message, ToolManager
from .tools import ToolExecutor


class Agent:
    """Base class for AI agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def run(self, task: str) -> str:
        """Run the agent on a task."""
        raise NotImplementedError("Agents must implement run()")


class ConversationMemory:
    """Manages conversation history for agents."""

    def __init__(self, max_messages: int = 20):
        self.messages: List[Message] = []
        self.max_messages = max_messages

    def add_message(self, role: str, content: str, **kwargs):
        """Add a message to history."""
        message = Message(role=role, content=content, **kwargs)
        self.messages.append(message)

        # Trim old messages
        if len(self.messages) > self.max_messages:
            # Keep system message if present
            if self.messages[0].role == "system":
                self.messages = [self.messages[0]] + self.messages[-(self.max_messages - 1) :]
            else:
                self.messages = self.messages[-self.max_messages :]

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get messages in dict format for API calls."""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "function_call": msg.function_call,
            }
            for msg in self.messages
        ]

    def clear(self):
        """Clear conversation history."""
        self.messages.clear()


class LLMAgent(Agent):
    """Agent powered by an LLM with tool support."""

    @inject
    def __init__(
        self,
        name: str,
        description: str,
        client: LLMClient,
        tools: ToolManager,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4",
    ):
        super().__init__(name, description)
        self.client = client
        self.tools = tools
        self.tool_executor = ToolExecutor(tools)
        self.model = model
        self.system_prompt = system_prompt or f"You are {name}. {description}"
        self.memory = ConversationMemory()

        # Add system message
        self.memory.add_message("system", self.system_prompt)

    async def run(self, task: str) -> str:
        """Run the agent on a task."""
        # Add user message
        self.memory.add_message("user", task)

        # Get tool schemas
        tool_schemas = self.tools.all_schemas()

        # Call LLM with tools
        response = await self.client.chat.create(
            model=self.model,
            messages=self.memory.get_messages(),
            tools=tool_schemas if tool_schemas else None,
            tool_choice="auto" if tool_schemas else None,
        )

        message = response.choices[0].message

        # Handle tool calls
        if message.tool_calls:
            # Add assistant message with tool calls
            self.memory.add_message(
                "assistant", content=message.content, tool_calls=message.tool_calls
            )

            # Execute tools
            tool_results = await self.tool_executor.execute_all(message.tool_calls)

            # Add tool results to conversation
            for result in tool_results:
                self.memory.add_message(
                    "tool",
                    content=json.dumps(result.get("result", result)),
                    name=result.get("tool_call_id"),
                )

            # Get final response
            response = await self.client.chat.create(
                model=self.model, messages=self.memory.get_messages()
            )

            message = response.choices[0].message

        # Add final response
        self.memory.add_message("assistant", message.content)

        return message.content


class MultiAgent(Agent):
    """Coordinator agent that delegates to other agents."""

    @inject
    def __init__(
        self,
        name: str,
        description: str,
        client: LLMClient,
        agents: AgentManager,
        model: str = "gpt-4",
    ):
        super().__init__(name, description)
        self.client = client
        self.agents = agents
        self.model = model

    async def run(self, task: str) -> str:
        """Delegate task to appropriate agent."""
        # Get available agents
        available_agents = list(self.agents.agents.keys())

        if not available_agents:
            return "No agents available to handle this task."

        # Decide which agent to use
        prompt = f"""Given this task: "{task}"

Which of these agents would be best suited to handle it?
{json.dumps(available_agents, indent=2)}

Respond with just the agent name."""

        response = await self.client.chat.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a task delegation assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=50,
        )

        agent_name = response.choices[0].message.content.strip()

        # Get the agent
        agent = self.agents.get(agent_name)
        if not agent:
            # Fallback to first available agent
            agent_name = available_agents[0]
            agent = self.agents.get(agent_name)

        # Delegate to chosen agent
        result = await agent.run(task)

        return f"[Delegated to {agent_name}]\n\n{result}"


# Example specialized agents
class ResearchAgent(LLMAgent):
    """Agent specialized in research tasks."""

    @inject
    def __init__(self, client: LLMClient, tools: ToolManager):
        super().__init__(
            name="Research Assistant",
            description="An agent that excels at researching topics and providing comprehensive information",
            client=client,
            tools=tools,
            system_prompt="""You are a research assistant. Your role is to:
1. Search for accurate, up-to-date information
2. Synthesize findings from multiple sources
3. Provide well-structured, informative responses
4. Cite sources when possible
5. Acknowledge limitations in available information

Use the available tools to gather information and provide comprehensive answers.""",
            model="gpt-4",
        )


class CodingAgent(LLMAgent):
    """Agent specialized in coding tasks."""

    @inject
    def __init__(self, client: LLMClient, tools: ToolManager):
        super().__init__(
            name="Coding Assistant",
            description="An agent that helps with programming tasks, code review, and debugging",
            client=client,
            tools=tools,
            system_prompt="""You are a coding assistant. Your role is to:
1. Write clean, efficient, and well-documented code
2. Follow best practices and design patterns
3. Provide clear explanations of code functionality
4. Help debug issues and suggest improvements
5. Consider security and performance implications

When writing code, always:
- Add appropriate comments
- Handle errors gracefully
- Follow the language's conventions
- Consider edge cases""",
            model="gpt-4",
        )


class AnalysisAgent(LLMAgent):
    """Agent specialized in data analysis."""

    @inject
    def __init__(self, client: LLMClient, tools: ToolManager):
        super().__init__(
            name="Analysis Assistant",
            description="An agent that analyzes data, identifies patterns, and provides insights",
            client=client,
            tools=tools,
            system_prompt="""You are a data analysis assistant. Your role is to:
1. Analyze provided data for patterns and insights
2. Perform calculations and statistical analysis
3. Create clear summaries and visualizations (describe them)
4. Identify trends and anomalies
5. Provide actionable recommendations

Use the calculate tool for mathematical operations and provide clear, data-driven insights.""",
            model="gpt-4",
        )
