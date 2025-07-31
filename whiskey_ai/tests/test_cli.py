"""Tests for Whiskey AI CLI commands."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from whiskey import Whiskey
from whiskey_ai import MockLLMClient, ai_extension
from whiskey_cli import cli_extension


@pytest.fixture
def app():
    """Create test application with AI and CLI extensions."""
    app = Whiskey()
    app.use(cli_extension)
    app.use(ai_extension)

    # Register test model
    @app.model("test-model")
    class TestModel(MockLLMClient):
        pass

    app.configure_model("test-model")

    # Register test tool
    @app.tool(name="test_tool")
    def test_tool(x: int) -> int:
        """Test tool that doubles input."""
        return x * 2

    # Register test agent
    @app.agent("test-agent")
    class TestAgent:
        async def run(self, task: str) -> str:
            return f"Processed: {task}"

    return app


@pytest.mark.unit
class TestAICLICommands:
    """Test AI CLI commands."""

    def test_list_models_command(self, app):
        """Test listing models via CLI."""
        runner = CliRunner()

        # Get the CLI group
        cli = app.container["cli_manager"].cli_group

        # Run the command
        result = runner.invoke(cli, ["ai", "models"])

        assert result.exit_code == 0
        assert "Available AI Models:" in result.output
        assert "test-model" in result.output
        assert "✓ Configured" in result.output

    def test_model_info_command(self, app):
        """Test model info command."""
        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "model-info", "test-model"])

        assert result.exit_code == 0
        assert "Model: test-model" in result.output
        assert "Status:" in result.output

    def test_model_info_not_found(self, app):
        """Test model info with non-existent model."""
        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "model-info", "non-existent"])

        assert result.exit_code == 1
        assert "Error: Model 'non-existent' not found" in result.output

    def test_list_agents_command(self, app):
        """Test listing agents."""
        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "agents"])

        assert result.exit_code == 0
        assert "Available AI Agents:" in result.output
        assert "test-agent" in result.output

    def test_list_tools_command(self, app):
        """Test listing tools."""
        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "tools"])

        assert result.exit_code == 0
        assert "Available AI Tools:" in result.output
        assert "test_tool" in result.output
        assert "Test tool that doubles input" in result.output

    def test_tool_test_command(self, app):
        """Test tool execution."""
        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "tool-test", "test_tool", "--input", '{"x": 5}'])

        assert result.exit_code == 0
        assert "Result: 10" in result.output

    def test_tool_test_invalid_json(self, app):
        """Test tool test with invalid JSON."""
        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "tool-test", "test_tool", "--input", "invalid json"])

        assert result.exit_code == 1
        assert "Error: Invalid JSON input" in result.output

    def test_agent_scaffold_command(self, app, tmp_path, monkeypatch):
        """Test agent scaffolding."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(
            cli,
            ["ai", "agent-scaffold", "test_agent", "--tools", "calculator", "--template", "basic"],
            input="n\n",  # Don't overwrite if exists
        )

        assert result.exit_code == 0

        # Check files were created
        agent_file = tmp_path / "agents" / "test_agent_agent.py"
        test_file = tmp_path / "tests" / "test_test_agent_agent.py"

        assert agent_file.exists()
        assert test_file.exists()

        # Check content
        agent_content = agent_file.read_text()
        assert "class TestAgent(Agent):" in agent_content
        assert "from whiskey_ai.tools import calculator" in agent_content

    def test_prompts_create_command(self, app, tmp_path, monkeypatch):
        """Test prompt creation."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "prompts", "--create", "greeting"])

        assert result.exit_code == 0

        # Check file was created
        prompt_file = tmp_path / "prompts" / "greeting.yaml"
        assert prompt_file.exists()

        # Check content
        content = prompt_file.read_text()
        assert "# Prompt: greeting" in content
        assert "version: 1.0" in content
        assert "template:" in content

    @patch("click.prompt")
    def test_chat_command_exit(self, mock_prompt, app):
        """Test chat command with exit."""
        mock_prompt.return_value = "exit"

        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        result = runner.invoke(cli, ["ai", "chat", "--model", "test-model"])

        assert result.exit_code == 0
        assert "Starting AI chat session" in result.output
        assert "Goodbye!" in result.output

    def test_eval_command(self, app, tmp_path, monkeypatch):
        """Test evaluation command."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        cli = app.container["cli_manager"].cli_group

        output_file = tmp_path / "results.json"
        result = runner.invoke(
            cli,
            [
                "ai",
                "eval",
                "test_suite",
                "--model",
                "test-model",
                "--output",
                str(output_file),
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        assert "Running evaluation suite: test_suite" in result.output
        assert output_file.exists()

        # Check output content
        results = json.loads(output_file.read_text())
        assert results["suite"] == "test_suite"
        assert results["model"] == "test-model"
        assert "results" in results


@pytest.mark.unit
class TestCLIIntegration:
    """Test CLI integration with AI extension."""

    def test_cli_commands_registered(self, app):
        """Test that CLI commands are registered when both extensions are loaded."""
        cli_manager = app.container.get("cli_manager")
        assert cli_manager is not None

        # Check AI group exists
        assert "ai" in cli_manager.groups

        # Check commands are registered
        ai_group = cli_manager.groups["ai"]
        command_names = [cmd.name for cmd in ai_group.commands.values()]

        expected_commands = [
            "models",
            "model-info",
            "agents",
            "agent-scaffold",
            "tools",
            "tool-test",
            "prompts",
            "eval",
            "chat",
        ]

        for cmd in expected_commands:
            assert cmd in command_names

    def test_cli_not_loaded(self):
        """Test that AI extension works without CLI extension."""
        app = Whiskey()
        app.use(ai_extension)  # Only AI, no CLI

        # Should not have CLI commands
        assert not hasattr(app, "command")
        assert "cli_manager" not in app.container

        # But AI functionality should still work
        @app.model("test")
        class TestModel(MockLLMClient):
            pass

        app.configure_model("test")
        model = app.get_model("test")
        assert model is not None
