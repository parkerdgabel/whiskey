"""Agent example using Whiskey AI extension."""

from whiskey import inject
from whiskey_ai import LLMClient, MockLLMClient, ai_extension
from whiskey_ai.agents import AnalysisAgent, CodingAgent, ResearchAgent
from whiskey_ai.tools import calculate, get_current_time, web_search
from whiskey_asgi import Request, asgi_extension

# Create application
app = Application()
app.use(ai_extension)
app.use(asgi_extension)


# Register mock model
@app.model("mock")
class MockModel(MockLLMClient):
    pass


app.configure_model("mock")


# Register built-in tools
@app.tool()
async def search_web(query: str, max_results: int = 5) -> list:
    """Search the web for information."""
    return await web_search(query, max_results)


@app.tool()
def calculate_expression(expression: str) -> float:
    """Calculate a mathematical expression."""
    return calculate(expression)


@app.tool()
def current_time(timezone: str = None) -> str:
    """Get the current time."""
    return get_current_time(timezone)


# Register specialized agents
@app.agent("researcher")
class Researcher(ResearchAgent):
    pass


@app.agent("coder")
class Coder(CodingAgent):
    pass


@app.agent("analyst")
class Analyst(AnalysisAgent):
    pass


# Custom agent
@app.agent("assistant")
@inject
class GeneralAssistant:
    """General purpose assistant agent."""

    def __init__(self, client: LLMClient, tools: "ToolManager", agents: "AgentManager"):
        from whiskey_ai.agents import LLMAgent

        self.agent = LLMAgent(
            name="General Assistant",
            description="A helpful assistant that can handle various tasks",
            client=client,
            tools=tools,
            system_prompt="""You are a helpful AI assistant. You can:
1. Answer questions and provide information
2. Perform calculations
3. Search the web for current information
4. Help with various tasks

Use the available tools when needed to provide accurate, up-to-date information.""",
            model="gpt-4",
        )

        # Store reference to other agents for delegation
        self.agents = agents

    async def run(self, task: str) -> str:
        """Run the assistant on a task."""
        # Check if we should delegate to a specialized agent
        if "research" in task.lower() or "search" in task.lower():
            researcher = self.agents.get("researcher")
            if researcher:
                return await researcher.run(task)
        elif "code" in task.lower() or "program" in task.lower():
            coder = self.agents.get("coder")
            if coder:
                return await coder.run(task)
        elif "analy" in task.lower() or "data" in task.lower():
            analyst = self.agents.get("analyst")
            if analyst:
                return await analyst.run(task)

        # Handle with general agent
        return await self.agent.run(task)


# Setup default client
@app.on_startup
async def setup():
    app.container[LLMClient] = app.get_model("mock")


# Agent endpoints
@app.post("/agent/{agent_name}")
@inject
async def run_agent(agent_name: str, request: Request, agents: "AgentManager"):
    """Run a specific agent."""
    data = await request.json()
    task = data.get("task", "")

    agent = agents.get(agent_name)
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}, 404

    try:
        result = await agent.run(task)
        return {"agent": agent_name, "task": task, "result": result}
    except Exception as e:
        return {"agent": agent_name, "task": task, "error": str(e)}, 500


@app.get("/agents")
@inject
async def list_agents(agents: "AgentManager"):
    """List available agents."""
    return {
        "agents": [
            {
                "name": name,
                "class": agent_class.__name__,
                "description": getattr(agent_class, "__doc__", "No description"),
            }
            for name, agent_class in agents.agents.items()
        ]
    }


# Chat with agent endpoint
@app.post("/chat")
@inject
async def chat_with_agent(request: Request, assistant: GeneralAssistant):
    """Chat with the general assistant."""
    data = await request.json()
    message = data.get("message", "")

    result = await assistant.run(message)

    return {"message": message, "response": result}


# Tool execution endpoint
@app.post("/tools/{tool_name}")
@inject
async def execute_tool(tool_name: str, request: Request, tools: "ToolManager"):
    """Execute a specific tool."""
    data = await request.json()

    tool = tools.get(tool_name)
    if not tool:
        return {"error": f"Tool '{tool_name}' not found"}, 404

    try:
        import asyncio

        if asyncio.iscoroutinefunction(tool):
            result = await tool(**data)
        else:
            result = tool(**data)

        return {"tool": tool_name, "arguments": data, "result": result}
    except Exception as e:
        return {"tool": tool_name, "arguments": data, "error": str(e)}, 500


@app.get("/tools")
@inject
async def list_tools(tools: "ToolManager"):
    """List available tools."""
    return {
        "tools": [
            {
                "name": schema["function"]["name"],
                "description": schema["function"]["description"],
                "parameters": schema["function"]["parameters"],
            }
            for schema in tools.all_schemas()
        ]
    }


# Home endpoint
@app.get("/")
async def index():
    """API information."""
    return {
        "name": "Whiskey AI Agent Example",
        "endpoints": {
            "GET /": "This page",
            "GET /agents": "List available agents",
            "POST /agent/{name}": "Run a specific agent",
            "POST /chat": "Chat with the general assistant",
            "GET /tools": "List available tools",
            "POST /tools/{name}": "Execute a specific tool",
        },
        "agents": ["researcher", "coder", "analyst", "assistant"],
        "tools": ["search_web", "calculate_expression", "current_time"],
    }


if __name__ == "__main__":
    print("Starting Whiskey AI Agent Example...")
    print("API available at http://localhost:8000")
    print("\nExample requests:")
    print("\n1. List agents:")
    print("curl http://localhost:8000/agents")
    print("\n2. Chat with assistant:")
    print("curl -X POST http://localhost:8000/chat \\")
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "What is 25 * 4?"}\'')
    print("\n3. Run specific agent:")
    print("curl -X POST http://localhost:8000/agent/researcher \\")
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"task": "Find information about Python async programming"}\'')

    app.run_asgi(port=8000)
