"""Tests for the CLI extension."""

<<<<<<< HEAD
from click.testing import CliRunner

from whiskey import inject
=======
import pytest
from click.testing import CliRunner

from whiskey import Application, inject
>>>>>>> origin/main
from whiskey_cli import cli_extension


class TestCLIExtension:
    """Test CLI extension functionality."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_extension_adds_decorators(self):
        """Test that extension adds command and group decorators."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

        # Check decorators were added
        assert hasattr(app, "command")
        assert hasattr(app, "group")
        assert hasattr(app, "run_cli")
        assert hasattr(app, "cli")
        assert hasattr(app, "cli_manager")

=======
        
        # Check decorators were added
        assert hasattr(app, 'command')
        assert hasattr(app, 'group')
        assert hasattr(app, 'run_cli')
        assert hasattr(app, 'cli')
        assert hasattr(app, 'cli_manager')
    
>>>>>>> origin/main
    def test_simple_command(self):
        """Test registering a simple command."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command()
        def hello():
            """Say hello."""
            print("Hello, World!")
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, ["hello"])

        assert result.exit_code == 0
        assert "Hello, World!" in result.output

=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, ['hello'])
        
        assert result.exit_code == 0
        assert "Hello, World!" in result.output
    
>>>>>>> origin/main
    def test_command_with_arguments(self):
        """Test command with arguments."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command()
        def greet(name: str):
            """Greet someone."""
            print(f"Hello, {name}!")
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, ["greet", "Alice"])

        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output

=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, ['greet', 'Alice'])
        
        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output
    
>>>>>>> origin/main
    def test_command_with_injection(self):
        """Test command with dependency injection."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

        class GreetingService:
            def greet(self, name: str) -> str:
                return f"Greetings, {name}!"

        app.container[GreetingService] = GreetingService()

=======
        
        class GreetingService:
            def greet(self, name: str) -> str:
                return f"Greetings, {name}!"
        
        app.container[GreetingService] = GreetingService()
        
>>>>>>> origin/main
        @app.command()
        @inject
        def greet(name: str, service: GreetingService):
            """Greet with service."""
            message = service.greet(name)
            print(message)
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, ["greet", "Bob"])

        assert result.exit_code == 0
        assert "Greetings, Bob!" in result.output

=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, ['greet', 'Bob'])
        
        assert result.exit_code == 0
        assert "Greetings, Bob!" in result.output
    
>>>>>>> origin/main
    def test_async_command(self):
        """Test async command execution."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command()
        async def async_hello():
            """Async hello."""
            print("Async Hello!")
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, ["async-hello"])

        assert result.exit_code == 0
        assert "Async Hello!" in result.output

=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, ['async-hello'])
        
        assert result.exit_code == 0
        assert "Async Hello!" in result.output
    
>>>>>>> origin/main
    def test_command_groups(self):
        """Test command groups."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

        db_group = app.group("db")

=======
        
        db_group = app.group("db")
        
>>>>>>> origin/main
        @db_group.command()
        def migrate():
            """Run migrations."""
            print("Running migrations...")
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @db_group.command()
        def backup():
            """Backup database."""
            print("Backing up...")
<<<<<<< HEAD

        runner = CliRunner()

        # Test group commands
        result = runner.invoke(app.cli, ["db", "migrate"])
        assert result.exit_code == 0
        assert "Running migrations..." in result.output

        result = runner.invoke(app.cli, ["db", "backup"])
        assert result.exit_code == 0
        assert "Backing up..." in result.output

=======
        
        runner = CliRunner()
        
        # Test group commands
        result = runner.invoke(app.cli, ['db', 'migrate'])
        assert result.exit_code == 0
        assert "Running migrations..." in result.output
        
        result = runner.invoke(app.cli, ['db', 'backup'])
        assert result.exit_code == 0
        assert "Backing up..." in result.output
    
>>>>>>> origin/main
    def test_command_in_group_decorator(self):
        """Test adding command to group via decorator."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command(group="admin")
        def users():
            """List users."""
            print("Listing users...")
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command(group="admin")
        def roles():
            """List roles."""
            print("Listing roles...")
<<<<<<< HEAD

        runner = CliRunner()

        result = runner.invoke(app.cli, ["admin", "users"])
        assert result.exit_code == 0
        assert "Listing users..." in result.output

=======
        
        runner = CliRunner()
        
        result = runner.invoke(app.cli, ['admin', 'users'])
        assert result.exit_code == 0
        assert "Listing users..." in result.output
    
>>>>>>> origin/main
    def test_app_info_command(self):
        """Test built-in app-info command."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Register a component
        @app.component
        class TestService:
            pass
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, ["app-info"])

        assert result.exit_code == 0
        assert "Application:" in result.output
        assert "TestService" in result.output

=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, ['app-info'])
        
        assert result.exit_code == 0
        assert "Application:" in result.output
        assert "TestService" in result.output
    
>>>>>>> origin/main
    def test_custom_command_name(self):
        """Test custom command name."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command(name="say-hello")
        def hello_cmd():
            """Custom named command."""
            print("Hello!")
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, ["say-hello"])

        assert result.exit_code == 0
        assert "Hello!" in result.output

=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, ['say-hello'])
        
        assert result.exit_code == 0
        assert "Hello!" in result.output
    
>>>>>>> origin/main
    def test_run_cli_without_args(self):
        """Test run_cli shows help."""
        app = Application()
        app.use(cli_extension)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        @app.command()
        def test():
            """Test command."""
            pass
<<<<<<< HEAD

        runner = CliRunner()
        result = runner.invoke(app.cli, [])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "test" in result.output
=======
        
        runner = CliRunner()
        result = runner.invoke(app.cli, [])
        
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "test" in result.output
>>>>>>> origin/main
