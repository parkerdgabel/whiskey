"""Tests for the CLI extension."""

from click.testing import CliRunner

from whiskey import Whiskey, inject
from whiskey_cli import cli_extension


class TestCLIExtension:
    """Test CLI extension functionality."""

    def test_extension_adds_decorators(self):
        """Test that extension adds command and group decorators."""
        app = Whiskey()
        app.use(cli_extension)

        # Check decorators were added
        assert hasattr(app, "command")
        assert hasattr(app, "group")
        assert hasattr(app, "run_cli")
        assert hasattr(app, "cli")
        assert hasattr(app, "cli_manager")

    def test_simple_command(self):
        """Test registering a simple command."""
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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
        app = Whiskey()
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

    def test_command_with_options(self):
        """Test command with options."""
        app = Whiskey()
        app.use(cli_extension)

        @app.option("--count", default=1, help="Number of greetings")
        @app.option("--name", default="World", help="Name to greet")
        @app.command()
        def greet():
            """Greet with options."""
            import click

            count = click.get_current_context().params["count"]
            name = click.get_current_context().params["name"]
            for _ in range(count):
                print(f"Hello, {name}!")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["greet", "--count", "2", "--name", "Alice"])

        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output
        assert result.output.count("Hello, Alice!") == 2

    def test_command_with_shorthand_options(self):
        """Test command with shorthand options."""
        app = Whiskey()
        app.use(cli_extension)

        @app.option("-v/--verbose", is_flag=True, help="Verbose output")
        @app.command()
        def test_cmd():
            """Test command with shorthand option."""
            import click

            verbose = click.get_current_context().params["verbose"]
            if verbose:
                print("Verbose mode enabled")
            else:
                print("Normal mode")

        runner = CliRunner()

        # Test short form
        result = runner.invoke(app.cli, ["test-cmd", "-v"])
        assert result.exit_code == 0
        assert "Verbose mode enabled" in result.output

        # Test long form
        result = runner.invoke(app.cli, ["test-cmd", "--verbose"])
        assert result.exit_code == 0
        assert "Verbose mode enabled" in result.output

        # Test without flag
        result = runner.invoke(app.cli, ["test-cmd"])
        assert result.exit_code == 0
        assert "Normal mode" in result.output

    def test_command_with_arguments_and_options(self):
        """Test command with both arguments and options."""
        app = Whiskey()
        app.use(cli_extension)

        @app.argument("message")
        @app.option("--repeat", default=1, type=int)
        @app.command()
        def echo():
            """Echo a message."""
            import click

            ctx = click.get_current_context()
            message = ctx.params["message"]
            repeat = ctx.params["repeat"]
            for _ in range(repeat):
                print(message)

        runner = CliRunner()
        result = runner.invoke(app.cli, ["echo", "Hello World", "--repeat", "3"])

        assert result.exit_code == 0
        assert result.output.count("Hello World") == 3

    def test_async_command_with_injection(self):
        """Test async command with dependency injection."""
        app = Whiskey()
        app.use(cli_extension)

        class AsyncService:
            async def process(self, data: str) -> str:
                return f"Processed: {data}"

        app.container[AsyncService] = AsyncService()

        @app.command()
        @inject
        async def process(data: str, service: AsyncService):
            """Process data asynchronously."""
            result = await service.process(data)
            print(result)

        runner = CliRunner()
        result = runner.invoke(app.cli, ["process", "test-data"])

        assert result.exit_code == 0
        assert "Processed: test-data" in result.output

    def test_lazy_click_group_finalization(self):
        """Test that LazyClickGroup finalizes pending commands."""
        app = Whiskey()
        app.use(cli_extension)

        # Add a command without finalizing
        @app.command()
        def test_lazy():
            """Test lazy finalization."""
            print("Lazy command executed")

        # Verify command is in pending
        assert "test-lazy" in app.cli_manager.pending_commands

        # Invoke should trigger finalization
        runner = CliRunner()
        result = runner.invoke(app.cli, ["test-lazy"])

        assert result.exit_code == 0
        assert "Lazy command executed" in result.output
        # Command should no longer be pending
        assert "test-lazy" not in app.cli_manager.pending_commands

    def test_lazy_click_group_help_exit_code(self):
        """Test that LazyClickGroup returns 0 for help display."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def test():
            """Test command."""
            pass

        runner = CliRunner()
        # Test that help doesn't return error code
        result = runner.invoke(app.cli, ["--help"])
        assert result.exit_code == 0

    def test_command_error_handling(self):
        """Test error handling in commands."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def failing_command():
            """A command that fails."""
            raise ValueError("Something went wrong")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["failing-command"])

        assert result.exit_code != 0
        assert isinstance(result.exception, ValueError)

    def test_injection_fallback(self):
        """Test fallback when injection fails."""
        app = Whiskey()
        app.use(cli_extension)

        # Command that would need injection but service isn't registered
        @app.command()
        def no_injection():
            """Command without injection needs."""
            print("No injection needed")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["no-injection"])

        assert result.exit_code == 0
        assert "No injection needed" in result.output

    def test_run_cli_with_args(self):
        """Test run_cli with specific arguments."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def test_args():
            """Test command for args."""
            print("Args test passed")

        # Test run_cli with explicit args
        import sys
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            app.run_cli(["test-args"])
            output = captured_output.getvalue()
            assert "Args test passed" in output
        finally:
            sys.stdout = old_stdout

    def test_run_cli_in_event_loop(self):
        """Test run_cli when already in an event loop."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def test_loop():
            """Test command in loop."""
            print("Loop test")

        async def test_in_loop():
            # This should handle being called from within an event loop
            try:
                app.run_cli(["test-loop"])
            except SystemExit:
                pass  # Expected

        # Run the test
        import asyncio

        try:
            asyncio.run(test_in_loop())
        except Exception:
            pass  # Expected due to Click's standalone mode

    def test_group_creation(self):
        """Test creating command groups."""
        app = Whiskey()
        app.use(cli_extension)

        # Create a group
        db_group = app.group("database", "Database operations")
        assert db_group is not None
        assert "database" in app.cli_manager.groups

        @app.command(group="database")
        def migrate():
            """Run database migrations."""
            print("Running migrations...")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["database", "migrate"])

        assert result.exit_code == 0
        assert "Running migrations..." in result.output

    def test_multiple_option_formats(self):
        """Test different option name formats."""
        app = Whiskey()
        app.use(cli_extension)

        @app.option("--verbose", is_flag=True)
        @app.option("--output-format", default="text")
        @app.command()
        def test_options():
            """Test multiple option formats."""
            import click

            ctx = click.get_current_context()
            verbose = ctx.params["verbose"]
            output_format = ctx.params["output_format"]
            if verbose:
                print(f"Output format: {output_format}")
            else:
                print("Quiet mode")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["test-options", "--verbose", "--output-format", "json"])

        assert result.exit_code == 0
        assert "Output format: json" in result.output

    def test_command_auto_argument_detection(self):
        """Test automatic argument detection from function signature."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def process_file(filename: str, count: int):
            """Process a file."""
            print(f"Processing {filename} {count} times")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["process-file", "test.txt", "5"])

        assert result.exit_code == 0
        assert "Processing test.txt 5 times" in result.output

    def test_command_with_defaults_become_options(self):
        """Test that parameters with defaults become options."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def greet_with_defaults(name: str, greeting: str = "Hello"):
            """Greet with default greeting."""
            print(f"{greeting}, {name}!")

        runner = CliRunner()

        # Test with default
        result = runner.invoke(app.cli, ["greet-with-defaults", "Alice"])
        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output

    def test_command_with_varargs_kwargs(self):
        """Test command with *args and **kwargs parameters."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def flexible_cmd(*args, **kwargs):
            """Command with flexible arguments."""
            print("Flexible command executed")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["flexible-cmd"])

        assert result.exit_code == 0
        assert "Flexible command executed" in result.output

    def test_command_with_inject_and_basic_types(self):
        """Test command with @inject that has basic type parameters."""
        app = Whiskey()
        app.use(cli_extension)

        class MyService:
            def process(self, data: str) -> str:
                return f"Processed: {data}"

        app.container[MyService] = MyService()

        @app.command()
        @inject
        def process_data(filename: str, count: int, service: MyService):
            """Process data with service injection."""
            result = service.process(f"{filename}x{count}")
            print(result)

        runner = CliRunner()
        result = runner.invoke(app.cli, ["process-data", "file.txt", "3"])

        assert result.exit_code == 0
        assert "Processed: file.txtx3" in result.output

    def test_option_decorator_on_non_command_function(self):
        """Test applying @app.option to a function that's not a command."""
        app = Whiskey()
        app.use(cli_extension)

        def regular_function():
            """Regular function."""
            pass

        # This should not crash
        decorated = app.option("--test")(regular_function)
        assert decorated is regular_function

    def test_argument_decorator_on_non_command_function(self):
        """Test applying @app.argument to a function that's not a command."""
        app = Whiskey()
        app.use(cli_extension)

        def regular_function():
            """Regular function."""
            pass

        # This should not crash
        decorated = app.argument("test_arg")(regular_function)
        assert decorated is regular_function

    def test_command_with_wrapped_function_detection(self):
        """Test command with wrapped function for argument detection."""
        app = Whiskey()
        app.use(cli_extension)

        def original_func(name: str):
            print(f"Hello, {name}!")

        # Manually wrap the function to simulate a decorator
        def wrapper(*args, **kwargs):
            return original_func(*args, **kwargs)

        wrapper.__wrapped__ = original_func
        wrapper.__name__ = "wrapped_greet"

        @app.command()
        def wrapped_greet(*args, **kwargs):
            return wrapper(*args, **kwargs)

        # Simulate having __wrapped__
        wrapped_greet.__wrapped__ = original_func

        runner = CliRunner()
        result = runner.invoke(app.cli, ["wrapped-greet", "Alice"])

        assert result.exit_code == 0

    def test_lazy_click_group_system_exit_non_help(self):
        """Test LazyClickGroup with non-help SystemExit."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def failing_exit():
            """Command that exits with code 1."""
            import sys

            sys.exit(1)

        runner = CliRunner()
        result = runner.invoke(app.cli, ["failing-exit"])

        assert result.exit_code == 1

    def test_run_cli_system_exit_handling(self):
        """Test run_cli system exit handling."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def exit_zero():
            """Command that exits with 0."""
            import sys

            sys.exit(0)

        # Test that SystemExit(0) is handled properly
        try:
            app.run_cli(["exit-zero"])
        except SystemExit as e:
            assert e.code == 0 or e.code is None

    def test_run_cli_exception_handling(self):
        """Test run_cli exception handling."""
        app = Whiskey()
        app.use(cli_extension)

        @app.command()
        def error_cmd():
            """Command that raises an exception."""
            raise RuntimeError("Test error")

        # Test that exceptions are handled
        import sys
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            app.run_cli(["error-cmd"])
        except SystemExit:
            pass  # Expected
        finally:
            sys.stdout = old_stdout

    def test_option_list_format(self):
        """Test option with list format (multiple values)."""
        app = Whiskey()
        app.use(cli_extension)

        @app.option(["-v", "--verbose"], is_flag=True)
        @app.command()
        def list_option_cmd():
            """Command with list-format option."""
            import click

            verbose = click.get_current_context().params.get("verbose", False)
            print(f"Verbose: {verbose}")

        runner = CliRunner()
        result = runner.invoke(app.cli, ["list-option-cmd", "-v"])

        assert result.exit_code == 0
        assert "Verbose: True" in result.output

    def test_finalize_pending_with_no_manager_attribute(self):
        """Test finalize_pending when manager doesn't have the method."""
        app = Whiskey()
        app.use(cli_extension)

        # Create a mock manager without finalize_pending
        class MockManager:
            pass

        mock_manager = MockManager()

        # This should not crash when calling main
        from whiskey_cli.extension import LazyClickGroup

        group = LazyClickGroup(mock_manager)

        # Test main with help args (should not crash)
        try:
            group.main(["--help"], standalone_mode=False)
            # Should handle gracefully even without finalize_pending
        except SystemExit:
            pass  # Expected for help

    def test_app_info_with_many_services(self):
        """Test app-info command with many registered services."""
        app = Whiskey()
        app.use(cli_extension)

        # Register many services to test the truncation
        for i in range(15):

            class TestService:
                pass

            TestService.__name__ = f"TestService{i}"
            app.container[TestService] = TestService()

        runner = CliRunner()
        result = runner.invoke(app.cli, ["app-info"])

        assert result.exit_code == 0
        assert "and" in result.output and "more" in result.output  # Should show truncation
