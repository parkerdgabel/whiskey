#!/usr/bin/env python3
"""Working demo of Whiskey CLI extension."""

from whiskey import Whiskey
from whiskey_cli import cli_extension
from datetime import datetime
import json
import random


# Create app
app = Whiskey()
app.use(cli_extension)


# Basic commands that work
@app.command()
def hello():
    """Say hello to the world."""
    print("Hello, World! 👋")
    print("Welcome to Whiskey CLI Extension!")


@app.command()
def greet(name: str):
    """Greet someone by name."""
    greetings = ["Hello", "Hi", "Hey", "Greetings", "Welcome"]
    greeting = random.choice(greetings)
    print(f"{greeting}, {name}! 🎉")


@app.command()
def echo(message: str):
    """Echo a message back."""
    print(f"You said: {message}")


@app.command()
def now():
    """Show current date and time."""
    current = datetime.now()
    print(f"📅 Date: {current.strftime('%Y-%m-%d')}")
    print(f"🕐 Time: {current.strftime('%H:%M:%S')}")
    print(f"📍 Timezone: {current.strftime('%Z')}")


@app.command()
def version():
    """Show version information."""
    print("Whiskey CLI Demo")
    print("Version: 1.0.0")
    print("Built with: Whiskey Framework + CLI Extension")


# Math commands group
math_group = app.group("math", description="Mathematical operations")


@math_group.command("add")
def math_add(a: str, b: str):
    """Add two numbers."""
    try:
        result = float(a) + float(b)
        print(f"{a} + {b} = {result}")
    except ValueError:
        print("Error: Please provide valid numbers")


@math_group.command("multiply")
def math_multiply(a: str, b: str):
    """Multiply two numbers."""
    try:
        result = float(a) * float(b)
        print(f"{a} × {b} = {result}")
    except ValueError:
        print("Error: Please provide valid numbers")


@math_group.command("power")
def math_power(base: str, exponent: str):
    """Calculate base to the power of exponent."""
    try:
        result = float(base) ** float(exponent)
        print(f"{base}^{exponent} = {result}")
    except ValueError:
        print("Error: Please provide valid numbers")


# Text manipulation group
text_group = app.group("text", description="Text manipulation commands")


@text_group.command("upper")
def text_upper(text: str):
    """Convert text to uppercase."""
    print(text.upper())


@text_group.command("lower")
def text_lower(text: str):
    """Convert text to lowercase."""
    print(text.lower())


@text_group.command("reverse")
def text_reverse(text: str):
    """Reverse the text."""
    print(text[::-1])


@text_group.command("count")
def text_count(text: str):
    """Count characters, words, and lines."""
    chars = len(text)
    words = len(text.split())
    lines = text.count('\n') + 1
    
    print(f"Characters: {chars}")
    print(f"Words: {words}")
    print(f"Lines: {lines}")


# JSON commands
json_group = app.group("json", description="JSON processing commands")


@json_group.command("pretty")
def json_pretty(json_string: str):
    """Pretty print JSON."""
    try:
        data = json.loads(json_string)
        print(json.dumps(data, indent=2, sort_keys=True))
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")


@json_group.command("minify")
def json_minify(json_string: str):
    """Minify JSON (remove whitespace)."""
    try:
        data = json.loads(json_string)
        print(json.dumps(data, separators=(',', ':')))
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")


# Fun commands
@app.command()
def fortune():
    """Get a random fortune."""
    fortunes = [
        "Your code will compile on the first try today! 🎯",
        "A bug you've been hunting will reveal itself soon. 🐛",
        "Documentation you write today will save hours tomorrow. 📚",
        "Your next commit will get many ⭐ on GitHub.",
        "Coffee levels optimal. Productivity increasing. ☕",
        "The algorithm you seek is hidden in plain sight. 🔍",
        "Your tests will all pass... eventually. ✅",
        "Beware of premature optimization today. ⚡",
        "A helpful Stack Overflow answer awaits you. 💡",
        "Your pull request will be approved without changes! 🎉"
    ]
    print(f"\n🔮 {random.choice(fortunes)}\n")


@app.command()
def motivate():
    """Get programming motivation."""
    quotes = [
        '"Any fool can write code that a computer can understand. Good programmers write code that humans can understand." - Martin Fowler',
        '"First, solve the problem. Then, write the code." - John Johnson',
        '"Code is like humor. When you have to explain it, it\'s bad." - Cory House',
        '"Fix the cause, not the symptom." - Steve Maguire',
        '"Simplicity is the soul of efficiency." - Austin Freeman',
        '"Before software can be reusable it first has to be usable." - Ralph Johnson',
        '"Make it work, make it right, make it fast." - Kent Beck',
        '"Clean code always looks like it was written by someone who cares." - Robert C. Martin',
        '"Programming isn\'t about what you know; it\'s about what you can figure out." - Chris Pine',
        '"The best error message is the one that never shows up." - Thomas Fuchs'
    ]
    print(f"\n💪 {random.choice(quotes)}\n")


# Demo command to show various features
@app.command()
def demo():
    """Run a demo of various commands."""
    print("🎭 Whiskey CLI Extension Demo\n")
    
    print("1️⃣ Basic Commands:")
    print("   Try: demo_app.py hello")
    print("   Try: demo_app.py greet YourName")
    print("   Try: demo_app.py echo 'Hello World'")
    print()
    
    print("2️⃣ Command Groups:")
    print("   Math operations:")
    print("     demo_app.py math add 10 20")
    print("     demo_app.py math multiply 3 7")
    print("     demo_app.py math power 2 8")
    print()
    
    print("   Text manipulation:")
    print("     demo_app.py text upper 'hello world'")
    print("     demo_app.py text reverse 'hello'")
    print("     demo_app.py text count 'Count this text'")
    print()
    
    print("   JSON processing:")
    print("     demo_app.py json pretty '{\"name\":\"test\",\"value\":123}'")
    print("     demo_app.py json minify '{ \"formatted\" : true }'")
    print()
    
    print("3️⃣ Fun Commands:")
    print("   demo_app.py fortune")
    print("   demo_app.py motivate")
    print()
    
    print("4️⃣ Other Commands:")
    print("   demo_app.py now")
    print("   demo_app.py version")
    print("   demo_app.py app-info")
    print()
    
    print("📖 Use --help on any command for more info!")


if __name__ == "__main__":
    app.run_cli()