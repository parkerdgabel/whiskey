"""Agent example using Whiskey AI extension."""

<<<<<<< HEAD
from whiskey import Whiskey, inject
from whiskey_ai import LLMClient, MockLLMClient, ai_extension
from whiskey_ai.agents import AnalysisAgent, CodingAgent, ResearchAgent
from whiskey_ai.tools import calculate, get_current_time, web_search
from whiskey_asgi import Request, asgi_extension

# Create application
app = Whiskey()
app.use(ai_extension)
app.use(asgi_extension)


=======
import json

from whiskey import Application, inject
from whiskey_ai import ai_extension, MockLLMClient, LLMClient
from whiskey_ai.agents import ResearchAgent, CodingAgent, AnalysisAgent
from whiskey_ai.tools import calculate, web_search, get_current_time
from whiskey_asgi import asgi_extension, Request


# Create application
app = Application()
app.use(ai_extension)
app.use(asgi_extension)

>>>>>>> origin/main
# Register mock model
@app.model("mock")
class MockModel(MockLLMClient):
    pass

<<<<<<< HEAD

app.configure_model("mock")


=======
app.configure_model("mock")

>>>>>>> origin/main
# Register built-in tools
@app.tool()
async def search_web(query: str, max_results: int = 5) -> list:
    """Search the web for information."""
    return await web_search(query, max_results)

<<<<<<< HEAD

=======
>>>>>>> origin/main
@app.tool()
def calculate_expression(expression: str) -> float:
    """Calculate a mathematical expression."""
    return calculate(expression)

<<<<<<< HEAD

=======
>>>>>>> origin/main
@app.tool()
def current_time(timezone: str = None) -> str:
    """Get the current time."""
    return get_current_time(timezone)

<<<<<<< HEAD

=======
>>>>>>> origin/main
# Register specialized agents
@app.agent("researcher")
class Researcher(ResearchAgent):
    pass

<<<<<<< HEAD

=======
>>>>>>> origin/main
@app.agent("coder")
class Coder(CodingAgent):
    pass

<<<<<<< HEAD

=======
>>>>>>> origin/main
@app.agent("analyst")
class Analyst(AnalysisAgent):
    pass

<<<<<<< HEAD

=======
>>>>>>> origin/main
# Custom agent
@app.agent("assistant")
@inject
class GeneralAssistant:
    """General purpose assistant agent."""
<<<<<<< HEAD

    def __init__(self, client: LLMClient, tools: "ToolManager", agents: "AgentManager"):
        from whiskey_ai.agents import LLMAgent

=======
    
    def __init__(self, client: LLMClient, tools: "ToolManager", agents: "AgentManager"):
        from whiskey_ai.agents import LLMAgent
        
>>>>>>> origin/main
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
<<<<<<< HEAD
            model="gpt-4",
        )

        # Store reference to other agents for delegation
        self.agents = agents

=======
            model="gpt-4"
        )
        
        # Store reference to other agents for delegation
        self.agents = agents
    
>>>>>>> origin/main
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
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
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
<<<<<<< HEAD

    agent = agents.get(agent_name)
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}, 404

    try:
        result = await agent.run(task)
        return {"agent": agent_name, "task": task, "result": result}
    except Exception as e:
        return {"agent": agent_name, "task": task, "error": str(e)}, 500
=======
    
    agent = agents.get(agent_name)
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}, 404
    
    try:
        result = await agent.run(task)
        return {
            "agent": agent_name,
            "task": task,
            "result": result
        }
    except Exception as e:
        return {
            "agent": agent_name,
            "task": task,
            "error": str(e)
        }, 500
>>>>>>> origin/main


@app.get("/agents")
@inject
async def list_agents(agents: "AgentManager"):
    """List available agents."""
    return {
        "agents": [
            {
                "name": name,
                "class": agent_class.__name__,
<<<<<<< HEAD
                "description": getattr(agent_class, "__doc__", "No description"),
=======
                "description": getattr(agent_class, "__doc__", "No description")
>>>>>>> origin/main
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
<<<<<<< HEAD

    result = await assistant.run(message)

    return {"message": message, "response": result}
=======
    
    result = await assistant.run(message)
    
    return {
        "message": message,
        "response": result
    }
>>>>>>> origin/main


# Tool execution endpoint
@app.post("/tools/{tool_name}")
@inject
async def execute_tool(tool_name: str, request: Request, tools: "ToolManager"):
    """Execute a specific tool."""
    data = await request.json()
<<<<<<< HEAD

    tool = tools.get(tool_name)
    if not tool:
        return {"error": f"Tool '{tool_name}' not found"}, 404

    try:
        import asyncio

=======
    
    tool = tools.get(tool_name)
    if not tool:
        return {"error": f"Tool '{tool_name}' not found"}, 404
    
    try:
        import asyncio
        
>>>>>>> origin/main
        if asyncio.iscoroutinefunction(tool):
            result = await tool(**data)
        else:
            result = tool(**data)
<<<<<<< HEAD

        return {"tool": tool_name, "arguments": data, "result": result}
    except Exception as e:
        return {"tool": tool_name, "arguments": data, "error": str(e)}, 500
=======
        
        return {
            "tool": tool_name,
            "arguments": data,
            "result": result
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "arguments": data,
            "error": str(e)
        }, 500
>>>>>>> origin/main


@app.get("/tools")
@inject
async def list_tools(tools: "ToolManager"):
    """List available tools."""
    return {
        "tools": [
            {
                "name": schema["function"]["name"],
                "description": schema["function"]["description"],
<<<<<<< HEAD
                "parameters": schema["function"]["parameters"],
=======
                "parameters": schema["function"]["parameters"]
>>>>>>> origin/main
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
<<<<<<< HEAD
            "POST /tools/{name}": "Execute a specific tool",
        },
        "agents": ["researcher", "coder", "analyst", "assistant"],
        "tools": ["search_web", "calculate_expression", "current_time"],
=======
            "POST /tools/{name}": "Execute a specific tool"
        },
        "agents": ["researcher", "coder", "analyst", "assistant"],
        "tools": ["search_web", "calculate_expression", "current_time"]
>>>>>>> origin/main
    }


if __name__ == "__main__":
    print("Starting Whiskey AI Agent Example...")
    print("API available at http://localhost:8000")
    print("\nExample requests:")
    print("\n1. List agents:")
    print("curl http://localhost:8000/agents")
    print("\n2. Chat with assistant:")
<<<<<<< HEAD
    print("curl -X POST http://localhost:8000/chat \\")
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "What is 25 * 4?"}\'')
    print("\n3. Run specific agent:")
    print("curl -X POST http://localhost:8000/agent/researcher \\")
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"task": "Find information about Python async programming"}\'')

    app.run_asgi(port=8000)
=======
    print('curl -X POST http://localhost:8000/chat \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "What is 25 * 4?"}\'')
    print("\n3. Run specific agent:")
    print('curl -X POST http://localhost:8000/agent/researcher \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"task": "Find information about Python async programming"}\'')
    
    app.run_asgi(port=8000)
>>>>>>> origin/main
