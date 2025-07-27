"""Example of using Whiskey AI CLI commands."""

from whiskey import Whiskey
from whiskey_ai import ai_extension, MockLLMClient
from whiskey_cli import cli_extension


def create_app():
    """Create a Whiskey app with AI and CLI extensions."""
    app = Whiskey()
    
    # Load extensions
    app.use(cli_extension)
    app.use(ai_extension)
    
    # Register a mock model for demonstration
    @app.model("mock")
    class MockModel(MockLLMClient):
        """Mock LLM for testing."""
        pass
    
    # Configure the model
    app.configure_model("mock")
    
    # Register some example tools
    @app.tool(name="calculator")
    def calculate(expression: str) -> float:
        """Evaluate a mathematical expression."""
        try:
            # Simple eval for demo - use proper parser in production
            return eval(expression)
        except:
            return 0.0
    
    @app.tool(name="get_time")
    def get_current_time() -> str:
        """Get the current time."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Register an example agent
    @app.agent("helper")
    class HelperAgent:
        """A helpful AI assistant."""
        def __init__(self):
            self.name = "Helper"
            self.description = "I'm here to help!"
        
        async def run(self, task: str) -> str:
            """Process a task."""
            return f"I'll help you with: {task}"
    
    return app


if __name__ == "__main__":
    # Create the app
    app = create_app()
    
    # Run the CLI
    # This makes the following commands available:
    #
    # AI Model Commands:
    #   whiskey ai models              - List available AI models
    #   whiskey ai model-info mock     - Show detailed model information
    #
    # Prompt Management:
    #   whiskey ai prompts --list      - List all prompts
    #   whiskey ai prompts --create greeting - Create a new prompt
    #   whiskey ai prompts --test greeting   - Test a prompt
    #   whiskey ai prompts --version greeting - Show prompt versions
    #
    # Agent Commands:
    #   whiskey ai agents              - List available AI agents
    #   whiskey ai agent-scaffold customer_support --tools calculator,get_time
    #                                  - Scaffold a new agent with tools
    #
    # Tool Commands:
    #   whiskey ai tools               - List available AI tools
    #   whiskey ai tool-test calculator --input '{"expression": "2 + 2"}'
    #                                  - Test a tool with inputs
    #
    # Evaluation:
    #   whiskey ai eval benchmark_suite --model mock --verbose
    #                                  - Run evaluation suite
    #
    # Interactive Chat:
    #   whiskey ai chat                - Start interactive chat
    #   whiskey ai chat --agent helper - Chat using a specific agent
    #   whiskey ai chat --tools        - Enable tool usage in chat
    
    app.run_cli()