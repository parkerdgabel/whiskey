# Whiskey AI CLI Commands

The Whiskey AI extension provides a comprehensive set of CLI commands for managing AI applications. These commands are available when both `whiskey-ai` and `whiskey-cli` extensions are installed.

## Installation

```bash
pip install whiskey-ai[cli]
# or
pip install whiskey-ai whiskey-cli
```

## Available Commands

All AI commands are grouped under the `ai` command group.

### Model Management

#### List Models
```bash
whiskey ai models
```
Lists all registered AI models and their configuration status.

#### Model Information
```bash
whiskey ai model-info <model_name>
```
Shows detailed information about a specific model including its class, documentation, and configuration status.

### Prompt Management

#### List Prompts
```bash
whiskey ai prompts --list
```
Lists all available prompts in your application.

#### Create Prompt
```bash
whiskey ai prompts --create <prompt_name>
```
Creates a new prompt template file with boilerplate YAML structure.

#### Test Prompt
```bash
whiskey ai prompts --test <prompt_name>
```
Tests a prompt with its defined test cases.

#### Show Prompt Versions
```bash
whiskey ai prompts --version <prompt_name>
```
Shows the version history of a prompt.

### Agent Management

#### List Agents
```bash
whiskey ai agents
```
Lists all registered AI agents in your application.

#### Scaffold New Agent
```bash
whiskey ai agent-scaffold <agent_name> [options]
```

Options:
- `--tools, -t`: Tools to include in the agent (can be specified multiple times)
- `--template`: Template to use (`basic`, `research`, `conversational`)

Example:
```bash
whiskey ai agent-scaffold customer_support --tools calculator --tools web_search --template conversational
```

This creates:
- `agents/customer_support_agent.py` - The agent implementation
- `tests/test_customer_support_agent.py` - Test file for the agent

### Tool Management

#### List Tools
```bash
whiskey ai tools
```
Lists all registered tools with their descriptions and parameters.

#### Test Tool
```bash
whiskey ai tool-test <tool_name> --input <json_input>
```

Example:
```bash
whiskey ai tool-test calculator --input '{"expression": "2 + 2"}'
```

### Evaluation and Testing

#### Run Evaluations
```bash
whiskey ai eval <eval_suite> [options]
```

Options:
- `--model, -m`: Model to use for evaluation
- `--output, -o`: Output file for results
- `--verbose, -v`: Verbose output

Example:
```bash
whiskey ai eval accuracy_benchmark --model gpt-4 --output results.json --verbose
```

### Interactive Chat

#### Start Chat Session
```bash
whiskey ai chat [options]
```

Options:
- `--model, -m`: Model to use (default: "default")
- `--agent, -a`: Agent to use for chat
- `--tools, -t`: Enable tool usage

Examples:
```bash
# Basic chat
whiskey ai chat

# Chat with specific model
whiskey ai chat --model gpt-4

# Chat using an agent
whiskey ai chat --agent customer_support

# Chat with tools enabled
whiskey ai chat --tools
```

## Configuration

### Setting Default Model

You can set a default model in your application configuration:

```python
app = Whiskey()
app.config["ai.default_model"] = "gpt-4"
```

### Custom CLI Commands

You can add your own AI-related CLI commands:

```python
@app.command(name="train", group="ai", description="Train a model")
@app.option("--dataset", required=True, help="Training dataset")
@app.option("--epochs", type=int, default=10, help="Number of epochs")
async def train_model(dataset: str, epochs: int):
    """Train an AI model."""
    click.echo(f"Training on {dataset} for {epochs} epochs...")
    # Your training logic here
```

## Prompt File Format

When creating prompts with `--create`, the following YAML format is used:

```yaml
# Prompt: greeting
version: 1.0
description: "A friendly greeting prompt"

template: |
  You are a friendly assistant.
  
  User: {{user_name}}
  Message: {{message}}
  
  Greet the user warmly and address their message.

variables:
  - user_name
  - message

model_config:
  temperature: 0.7
  max_tokens: 150
  model: gpt-4

tests:
  - input:
      user_name: "Alice"
      message: "Hello!"
    expected_contains: ["hello", "Alice", "welcome"]
  - input:
      user_name: "Bob"
      message: "How are you?"
    expected_contains: ["Bob", "well", "fine"]
```

## Agent Templates

The scaffolding command supports different agent templates:

### Basic Template
- Simple agent with basic structure
- Includes memory management
- Tool support

### Research Template
- Designed for information gathering
- Includes web search and analysis tools
- Research context tracking

### Conversational Template
- Optimized for chat interactions
- Advanced memory management
- System prompt configuration
- Tool integration

## Best Practices

1. **Model Registration**: Always register and configure models before using them in CLI commands
2. **Tool Testing**: Test tools individually using `tool-test` before integrating them into agents
3. **Agent Development**: Use scaffolding to quickly create agents, then customize the generated code
4. **Prompt Versioning**: Track prompt changes using version numbers in the YAML files
5. **Evaluation**: Regularly run evaluation suites to ensure quality

## Troubleshooting

### "Model not configured" Error
Ensure the model is both registered and configured:
```python
@app.model("my-model")
class MyModel(LLMClient):
    pass

app.configure_model("my-model", api_key="...")
```

### "Agent not found" Error
Verify the agent is registered with the correct name:
```python
@app.agent("my-agent")
class MyAgent:
    pass
```

### Tool Execution Errors
Check that tool parameters match the expected types and that all required parameters are provided.

## Examples

See the `examples/cli_example.py` file for a complete working example of CLI integration.