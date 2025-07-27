"""CLI commands for Whiskey AI extension."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import click
from whiskey import inject

if TYPE_CHECKING:
    from whiskey import Whiskey
    from whiskey_ai.extension import ModelManager, ToolManager, AgentManager


def register_ai_cli_commands(app: Whiskey) -> None:
    """Register AI-specific CLI commands."""
    
    # Model management commands
    @app.command(name="models", group="ai", description="List available AI models")
    @inject
    async def list_models(model_manager: ModelManager):
        """List all registered models."""
        click.echo("Available AI Models:")
        click.echo("=" * 50)
        
        if not model_manager._model_classes:
            click.echo("No models registered.")
            return
        
        for name, model_class in model_manager._model_classes.items():
            configured = f"ai.model.instance.{name}" in model_manager.container
            status = click.style("✓ Configured", fg="green") if configured else click.style("✗ Not configured", fg="yellow")
            click.echo(f"  {name}: {model_class.__name__} [{status}]")
    
    @app.command(name="model-info", group="ai", description="Show detailed model information")
    @app.argument("model_name")
    @inject
    async def model_info(model_name: str, model_manager: ModelManager):
        """Show detailed information about a model."""
        if model_name not in model_manager._model_classes:
            click.echo(f"Error: Model '{model_name}' not found.", err=True)
            sys.exit(1)
        
        model_class = model_manager._model_classes[model_name]
        click.echo(f"\nModel: {model_name}")
        click.echo(f"Class: {model_class.__module__}.{model_class.__name__}")
        click.echo(f"Docstring: {model_class.__doc__ or 'No documentation'}")
        
        # Check if configured
        if f"ai.model.instance.{model_name}" in model_manager.container:
            click.echo(f"Status: {click.style('Configured', fg='green')}")
            model = model_manager.get(model_name)
            if hasattr(model, 'model_info'):
                info = await model.model_info()
                click.echo(f"Model Info: {json.dumps(info, indent=2)}")
        else:
            click.echo(f"Status: {click.style('Not configured', fg='yellow')}")
    
    # Prompt management commands
    @app.command(name="prompts", group="ai", description="Manage prompts")
    @app.option("-l/--list", is_flag=True, help="List all prompts")
    @app.option("-c/--create", help="Create a new prompt")
    @app.option("-t/--test", help="Test a prompt")
    @app.option("-v/--version", help="Show prompt version history")
    @inject
    async def manage_prompts(
        list: bool,
        create: Optional[str],
        test: Optional[str],
        version: Optional[str]
    ):
        """Manage prompts in your AI application."""
        if list:
            await list_all_prompts()
        elif create:
            await create_prompt(create)
        elif test:
            await test_prompt(test)
        elif version:
            await show_prompt_versions(version)
        else:
            click.echo("Please specify an action: --list, --create, --test, or --version")
    
    # Agent management commands
    @app.command(name="agents", group="ai", description="List available AI agents")
    @inject
    async def list_agents(agent_manager: AgentManager):
        """List all registered agents."""
        click.echo("Available AI Agents:")
        click.echo("=" * 50)
        
        agent_count = 0
        for key in agent_manager.container.registry._descriptors:
            if isinstance(key, str) and key.startswith("ai.agent."):
                agent_name = key.replace("ai.agent.", "")
                agent_class = agent_manager.get(agent_name)
                if agent_class:
                    click.echo(f"  {agent_name}: {type(agent_class).__name__}")
                    agent_count += 1
        
        if agent_count == 0:
            click.echo("No agents registered.")
    
    @app.command(name="agent-scaffold", group="ai", description="Scaffold a new AI agent")
    @app.argument("agent_name")
    @app.option("-t/--tools", multiple=True, help="Tools to include in the agent")
    @app.option("--template", default="basic", help="Agent template to use")
    async def scaffold_agent(agent_name: str, tools: tuple, template: str):
        """Scaffold a new AI agent with boilerplate code."""
        # Convert agent name to PascalCase for class name
        class_name = ''.join(word.capitalize() for word in agent_name.split('_'))
        
        template_code = generate_agent_template(class_name, agent_name, tools, template)
        
        # Create agent file
        agent_file = Path(f"agents/{agent_name}_agent.py")
        agent_file.parent.mkdir(exist_ok=True)
        
        if agent_file.exists():
            if not click.confirm(f"Agent file {agent_file} already exists. Overwrite?"):
                return
        
        agent_file.write_text(template_code)
        click.echo(f"✓ Created agent at {agent_file}")
        
        # Create test file
        test_file = Path(f"tests/test_{agent_name}_agent.py")
        test_file.parent.mkdir(exist_ok=True)
        test_code = generate_agent_test_template(class_name, agent_name)
        test_file.write_text(test_code)
        click.echo(f"✓ Created test at {test_file}")
    
    # Tool management commands
    @app.command(name="tools", group="ai", description="List available AI tools")
    @inject
    async def list_tools(tool_manager: ToolManager):
        """List all registered tools."""
        click.echo("Available AI Tools:")
        click.echo("=" * 50)
        
        schemas = tool_manager.all_schemas()
        if not schemas:
            click.echo("No tools registered.")
            return
        
        for schema in schemas:
            func_info = schema["function"]
            click.echo(f"\n  {func_info['name']}:")
            click.echo(f"    Description: {func_info.get('description', 'No description')}")
            if func_info.get('parameters', {}).get('properties'):
                click.echo("    Parameters:")
                for param, info in func_info['parameters']['properties'].items():
                    required = param in func_info['parameters'].get('required', [])
                    req_marker = "*" if required else ""
                    click.echo(f"      - {param}{req_marker} ({info['type']}): {info.get('description', '')}")
    
    @app.command(name="tool-test", group="ai", description="Test a tool with sample inputs")
    @app.argument("tool_name")
    @app.option("-i/--input", help="JSON input for the tool")
    @inject
    async def test_tool(tool_name: str, input: Optional[str], tool_manager: ToolManager):
        """Test a tool with sample inputs."""
        tool = tool_manager.get(tool_name)
        if not tool:
            click.echo(f"Error: Tool '{tool_name}' not found.", err=True)
            sys.exit(1)
        
        # Parse input
        try:
            args = json.loads(input) if input else {}
        except json.JSONDecodeError:
            click.echo("Error: Invalid JSON input.", err=True)
            sys.exit(1)
        
        # Execute tool
        try:
            click.echo(f"Executing {tool_name} with args: {args}")
            result = await tool(**args) if asyncio.iscoroutinefunction(tool) else tool(**args)
            click.echo(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    # Evaluation and testing commands
    @app.command(name="eval", group="ai", description="Run AI evaluations")
    @app.argument("eval_suite")
    @app.option("-m/--model", help="Model to use for evaluation")
    @app.option("-o/--output", help="Output file for results")
    @app.option("-v/--verbose", is_flag=True, help="Verbose output")
    async def run_evaluations(
        eval_suite: str,
        model: Optional[str],
        output: Optional[str],
        verbose: bool
    ):
        """Run evaluation suite against AI models."""
        click.echo(f"Running evaluation suite: {eval_suite}")
        
        # TODO: Implement evaluation runner
        results = {
            "suite": eval_suite,
            "model": model or "default",
            "timestamp": datetime.now().isoformat(),
            "results": {
                "accuracy": 0.95,
                "latency_ms": 250,
                "cost_per_1k_tokens": 0.002
            }
        }
        
        if verbose:
            click.echo(json.dumps(results, indent=2))
        
        if output:
            Path(output).write_text(json.dumps(results, indent=2))
            click.echo(f"✓ Results saved to {output}")
    
    # Chat/Interactive commands
    @app.command(name="chat", group="ai", description="Start interactive chat session")
    @app.option("-m/--model", default="default", help="Model to use")
    @app.option("-a/--agent", help="Agent to use for chat")
    @app.option("-t/--tools", is_flag=True, help="Enable tool usage")
    @inject
    async def interactive_chat(
        model: str,
        agent: Optional[str],
        tools: bool,
        model_manager: ModelManager,
        agent_manager: AgentManager
    ):
        """Start an interactive chat session."""
        click.echo("Starting AI chat session...")
        click.echo("Type 'exit' or 'quit' to end the session.")
        click.echo("-" * 50)
        
        # Get model
        try:
            llm_client = model_manager.get(model)
        except ValueError:
            click.echo(f"Error: Model '{model}' not configured.", err=True)
            sys.exit(1)
        
        # Get agent if specified
        chat_agent = None
        if agent:
            chat_agent = agent_manager.get(agent)
            if not chat_agent:
                click.echo(f"Error: Agent '{agent}' not found.", err=True)
                sys.exit(1)
        
        # Chat loop
        messages = []
        while True:
            try:
                user_input = click.prompt("\nYou", type=str)
                
                if user_input.lower() in ['exit', 'quit']:
                    click.echo("Goodbye!")
                    break
                
                messages.append({"role": "user", "content": user_input})
                
                # Get response
                if chat_agent:
                    response = await chat_agent.run(user_input)
                else:
                    completion = await llm_client.chat.create(
                        model=model,
                        messages=messages,
                        tools=tool_manager.all_schemas() if tools else None
                    )
                    response = completion.choices[0].message.content
                
                messages.append({"role": "assistant", "content": response})
                click.echo(f"\nAssistant: {response}")
                
            except KeyboardInterrupt:
                click.echo("\nGoodbye!")
                break
            except Exception as e:
                click.echo(f"\nError: {e}", err=True)


def generate_agent_template(class_name: str, agent_name: str, tools: tuple, template: str) -> str:
    """Generate agent template code."""
    tools_imports = "\n".join(f"from whiskey_ai.tools import {tool}" for tool in tools)
    tools_list = ", ".join(tools) if tools else ""
    
    if template == "basic":
        return f"""\"\"\"AI Agent: {agent_name}\"\"\"

from typing import Any, List, Optional
from whiskey import inject
from whiskey_ai import Agent, LLMClient, ConversationMemory
{tools_imports if tools else ''}


class {class_name}(Agent):
    \"\"\"AI agent for {agent_name.replace('_', ' ')}.\"\"\"
    
    @inject
    def __init__(
        self,
        name: str = "{agent_name}",
        description: str = "AI agent for {agent_name.replace('_', ' ')}",
        client: LLMClient = None,
        tools: List[Any] = None
    ):
        super().__init__(name, description)
        self.client = client
        self.tools = tools or [{tools_list}]
        self.memory = ConversationMemory()
    
    async def run(self, task: str) -> str:
        \"\"\"Execute the agent task.\"\"\"
        # Add task to memory
        self.memory.add_message("user", task)
        
        # TODO: Implement agent logic
        response = "Agent implementation pending"
        
        # Add response to memory
        self.memory.add_message("assistant", response)
        
        return response
    
    async def plan(self, task: str) -> List[str]:
        \"\"\"Plan the steps to complete the task.\"\"\"
        # TODO: Implement planning logic
        return ["Step 1", "Step 2", "Step 3"]
    
    async def execute_step(self, step: str) -> Any:
        \"\"\"Execute a single step of the plan.\"\"\"
        # TODO: Implement step execution
        return f"Executed: {{step}}"
"""
    
    elif template == "research":
        return f"""\"\"\"Research Agent: {agent_name}\"\"\"

from typing import Any, List, Optional
from whiskey import inject
from whiskey_ai import Agent, LLMClient, ConversationMemory
from whiskey_ai.tools import web_search, calculate, get_current_time
{tools_imports if tools else ''}


class {class_name}(Agent):
    \"\"\"Research agent for {agent_name.replace('_', ' ')}.\"\"\"
    
    @inject
    def __init__(
        self,
        name: str = "{agent_name}",
        description: str = "Research agent for comprehensive information gathering",
        client: LLMClient = None
    ):
        super().__init__(name, description)
        self.client = client
        self.tools = [web_search, calculate, get_current_time{', ' + tools_list if tools else ''}]
        self.memory = ConversationMemory()
        self.research_context = {{}}
    
    async def run(self, task: str) -> str:
        \"\"\"Execute research task.\"\"\"
        # Plan research steps
        steps = await self.plan(task)
        
        # Execute each step
        results = []
        for step in steps:
            result = await self.execute_step(step)
            results.append(result)
            self.research_context[step] = result
        
        # Synthesize findings
        synthesis = await self.synthesize_research(results)
        
        return synthesis
    
    async def plan(self, task: str) -> List[str]:
        \"\"\"Plan research steps.\"\"\"
        prompt = f"Break down this research task into steps: {{task}}"
        # TODO: Use LLM to generate research plan
        return [
            "Gather initial information",
            "Verify sources",
            "Analyze findings",
            "Synthesize conclusions"
        ]
    
    async def execute_step(self, step: str) -> Any:
        \"\"\"Execute a research step.\"\"\"
        # TODO: Implement research logic with tools
        return f"Research data for: {{step}}"
    
    async def synthesize_research(self, results: List[Any]) -> str:
        \"\"\"Synthesize research findings.\"\"\"
        # TODO: Use LLM to synthesize findings
        return "Research synthesis pending implementation"
"""
    
    else:  # template == "conversational"
        return f"""\"\"\"Conversational Agent: {agent_name}\"\"\"

from typing import Any, List, Optional
from whiskey import inject
from whiskey_ai import Agent, LLMClient, ConversationMemory, ChatSession
{tools_imports if tools else ''}


class {class_name}(Agent):
    \"\"\"Conversational agent for {agent_name.replace('_', ' ')}.\"\"\"
    
    @inject
    def __init__(
        self,
        name: str = "{agent_name}",
        description: str = "Conversational AI assistant",
        client: LLMClient = None,
        system_prompt: Optional[str] = None
    ):
        super().__init__(name, description)
        self.client = client
        self.tools = [{tools_list}] if {bool(tools)} else []
        self.memory = ConversationMemory(max_messages=20)
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        # Initialize with system message
        self.memory.add_message("system", self.system_prompt)
    
    def _default_system_prompt(self) -> str:
        \"\"\"Get default system prompt.\"\"\"
        return f\"\"\"You are {{self.name}}, a helpful AI assistant.
        
Your capabilities:
- Engage in natural conversation
- Answer questions accurately
- Use available tools when needed
- Maintain context across the conversation

Be concise, helpful, and friendly.\"\"\"
    
    async def run(self, task: str) -> str:
        \"\"\"Process user message and generate response.\"\"\"
        # Add user message
        self.memory.add_message("user", task)
        
        # Generate response with tools if available
        messages = self.memory.get_messages()
        
        response = await self.client.chat.create(
            model="gpt-4",
            messages=messages,
            tools=self._get_tool_schemas() if self.tools else None,
            tool_choice="auto" if self.tools else None
        )
        
        # Handle tool calls if any
        message = response.choices[0].message
        if message.tool_calls:
            # Execute tools and get final response
            tool_results = await self._execute_tools(message.tool_calls)
            messages.append({{"role": "assistant", "tool_calls": message.tool_calls}})
            messages.extend(tool_results)
            
            # Get final response
            final_response = await self.client.chat.create(
                model="gpt-4",
                messages=messages
            )
            message = final_response.choices[0].message
        
        # Add to memory and return
        self.memory.add_message("assistant", message.content)
        return message.content
    
    def _get_tool_schemas(self) -> List[dict]:
        \"\"\"Get tool schemas for the LLM.\"\"\"
        # TODO: Convert tools to OpenAI function schemas
        return []
    
    async def _execute_tools(self, tool_calls: List[Any]) -> List[dict]:
        \"\"\"Execute tool calls and return results.\"\"\"
        # TODO: Implement tool execution
        return []
    
    async def clear_memory(self):
        \"\"\"Clear conversation memory.\"\"\"
        self.memory.clear()
        self.memory.add_message("system", self.system_prompt)
"""


def generate_agent_test_template(class_name: str, agent_name: str) -> str:
    """Generate test template for agent."""
    return f"""\"\"\"Tests for {class_name}.\"\"\"

import pytest
from whiskey import Whiskey
from whiskey_ai import ai_extension, MockLLMClient
from agents.{agent_name}_agent import {class_name}


@pytest.fixture
async def app():
    \"\"\"Create test application.\"\"\"
    app = Whiskey()
    app.use(ai_extension)
    
    # Register mock model
    @app.model("mock")
    class TestModel(MockLLMClient):
        pass
    
    app.configure_model("mock")
    
    async with app:
        yield app


@pytest.fixture
async def agent(app):
    \"\"\"Create test agent.\"\"\"
    return await app.resolve({class_name})


@pytest.mark.asyncio
class Test{class_name}:
    \"\"\"Test {class_name} functionality.\"\"\"
    
    async def test_agent_creation(self, agent):
        \"\"\"Test agent can be created.\"\"\"
        assert agent is not None
        assert agent.name == "{agent_name}"
    
    async def test_run_task(self, agent):
        \"\"\"Test agent can run a task.\"\"\"
        result = await agent.run("Test task")
        assert result is not None
        assert isinstance(result, str)
    
    async def test_planning(self, agent):
        \"\"\"Test agent planning capabilities.\"\"\"
        steps = await agent.plan("Complex task")
        assert isinstance(steps, list)
        assert len(steps) > 0
    
    async def test_memory_management(self, agent):
        \"\"\"Test agent memory management.\"\"\"
        # Run multiple tasks
        await agent.run("First task")
        await agent.run("Second task")
        
        # Check memory contains both
        messages = agent.memory.get_messages()
        assert len(messages) >= 4  # System + 2 user + 2 assistant
"""


async def list_all_prompts():
    """List all prompts in the system."""
    # TODO: Implement prompt listing from a prompt registry
    click.echo("No prompts found. Use --create to add a new prompt.")


async def create_prompt(name: str):
    """Create a new prompt template."""
    # Create prompt file
    prompt_file = Path(f"prompts/{name}.yaml")
    prompt_file.parent.mkdir(exist_ok=True)
    
    template = f"""# Prompt: {name}
version: 1.0
description: "Description of the prompt"

template: |
  You are a helpful AI assistant.
  
  User: {{{{user_input}}}}
  
  Please respond helpfully and concisely.

variables:
  - user_input

model_config:
  temperature: 0.7
  max_tokens: 150
  model: gpt-4

tests:
  - input:
      user_input: "Hello"
    expected_contains: ["hello", "hi", "greetings"]
  - input:
      user_input: "What is 2+2?"
    expected_contains: ["4", "four"]
"""
    
    prompt_file.write_text(template)
    click.echo(f"✓ Created prompt template at {prompt_file}")
    click.echo("Edit the file to customize your prompt.")


async def test_prompt(name: str):
    """Test a prompt with sample inputs."""
    prompt_file = Path(f"prompts/{name}.yaml")
    if not prompt_file.exists():
        click.echo(f"Error: Prompt '{name}' not found.", err=True)
        sys.exit(1)
    
    # TODO: Load and test prompt
    click.echo(f"Testing prompt: {name}")
    click.echo("Test implementation pending...")


async def show_prompt_versions(name: str):
    """Show version history for a prompt."""
    # TODO: Implement version tracking
    click.echo(f"Version history for prompt: {name}")
    click.echo("Version tracking not yet implemented.")


# Helper to ensure imports are available
import asyncio