"""Tests for the CLI extension."""

from click.testing import CliRunner

from whiskey import Application, inject
from whiskey_cli import cli_extension


class TestCLIExtension:
    """Test CLI extension functionality."""

    def test_extension_adds_decorators(self):
        """Test that extension adds command and group decorators."""
        app = Application()
        app.use(cli_extension)

        # Check decorators were added
        assert hasattr(app, "command")
        assert hasattr(app, "group")
        assert hasattr(app, "run_cli")
        assert hasattr(app, "cli")
        assert hasattr(app, "cli_manager")

    def test_simple_command(self):
        """Test registering a simple command."""
        app = Application()
        app.use(cli_extension)

        @app.command()
        def hello():
            """Say hello."""
            print("Hello, World!")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["hello"])

        assert result.exit_code == 0
        assert "Hello, World!" in result.output

    def test_command_with_arguments(self):
        """Test command with arguments."""
        app = Application()
        app.use(cli_extension)

        @app.command()
        def greet(name: str):
            """Greet someone."""
            print(f"Hello, {name}!")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["greet", "Alice"])

        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output

    def test_command_with_injection(self):
        """Test command with dependency injection."""
        app = Application()
        app.use(cli_extension)

        class GreetingService:
            def greet(self, name: str) -> str:
                return f"Greetings, {name}!"

        app.container[GreetingService] = GreetingService()

        @app.command()
        @inject
        def greet(name: str, service: GreetingService):
            """Greet with service."""
            message = service.greet(name)
            print(message)

        runner = CliRunner()
        result = runner.invoke(app.cli, ["greet", "Bob"])

        assert result.exit_code == 0
        assert "Greetings, Bob!" in result.output

    def test_async_command(self):
        """Test async command execution."""
        app = Application()
        app.use(cli_extension)

        @app.command()
        async def async_hello():
            """Async hello."""
            print("Async Hello!")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["async-hello"])

        assert result.exit_code == 0
        assert "Async Hello!" in result.output

    def test_command_groups(self):
        """Test command groups."""
        app = Application()
        app.use(cli_extension)

        db_group = app.group("db")

        @db_group.command()
        def migrate():
            """Run migrations."""
            print("Running migrations...")

        @db_group.command()
        def backup():
            """Backup database."""
            print("Backing up...")

        runner = CliRunner()

        # Test group commands
        result = runner.invoke(app.cli, ["db", "migrate"])
        assert result.exit_code == 0
        assert "Running migrations..." in result.output

        result = runner.invoke(app.cli, ["db", "backup"])
        assert result.exit_code == 0
        assert "Backing up..." in result.output

    def test_command_in_group_decorator(self):
        """Test adding command to group via decorator."""
        app = Application()
        app.use(cli_extension)

        @app.command(group="admin")
        def users():
            """List users."""
            print("Listing users...")

        @app.command(group="admin")
        def roles():
            """List roles."""
            print("Listing roles...")

        runner = CliRunner()

        result = runner.invoke(app.cli, ["admin", "users"])
        assert result.exit_code == 0
        assert "Listing users..." in result.output

    def test_app_info_command(self):
        """Test built-in app-info command."""
        app = Application()
        app.use(cli_extension)

        # Register a component
        @app.component
        class TestService:
            pass

        runner = CliRunner()
        result = runner.invoke(app.cli, ["app-info"])

        assert result.exit_code == 0
        assert "Application:" in result.output
        assert "TestService" in result.output

    def test_custom_command_name(self):
        """Test custom command name."""
        app = Application()
        app.use(cli_extension)

        @app.command(name="say-hello")
        def hello_cmd():
            """Custom named command."""
            print("Hello!")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["say-hello"])

        assert result.exit_code == 0
        assert "Hello!" in result.output

    def test_run_cli_without_args(self):
        """Test run_cli shows help."""
        app = Application()
        app.use(cli_extension)

        @app.command()
        def test():
            """Test command."""
            pass

        runner = CliRunner()
        result = runner.invoke(app.cli, [])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "test" in result.output
