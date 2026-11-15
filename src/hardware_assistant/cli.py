"""Command Line Interface for the Linux Hardware Q&A Assistant."""

import argparse
import sys
import os
import re
from typing import Optional
from contextlib import contextmanager

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    STYLE_RE = re.compile(r"\[/?(?:bold|italic|dim|cyan|yellow|green|white|red|blue|magenta)[^\]]*\]")
    class FallbackConsole:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            clean = STYLE_RE.sub("", text)
            print(clean)
        def input(self, prompt=""):
            clean = STYLE_RE.sub("", prompt)
            return input(clean)
        @contextmanager
        def status(self, message="", spinner=None):
            clean = STYLE_RE.sub("", message)
            print(f"> {clean}")
            yield
        def print_json(self, data):
            import json
            print(json.dumps(data, indent=2))
    class FallbackPanel:
        def __init__(self, text, border_style=None, title=None, subtitle=None):
            self.text = text
            self.title = title
        def __str__(self):
            clean = STYLE_RE.sub("", str(self.text))
            sep = "=" * 60
            t_str = f" {self.title} " if self.title else ""
            return f"\n{sep}\n{t_str}\n{clean}\n{sep}\n"
    class FallbackText:
        def __init__(self, text=""):
            self.parts = [text] if text else []
        def append(self, text, style=None):
            self.parts.append(text)
        def __str__(self):
            return "".join(self.parts)
    class FallbackTable:
        def __init__(self, title=None, border_style=None):
            self.title = title
            self.rows = []
        def add_column(self, name, style=None):
            pass
        def add_row(self, *cols):
            self.rows.append(cols)
        def __str__(self):
            lines = [f"\n--- {self.title or 'Table'} ---"]
            for r in self.rows:
                lines.append("  " + " : ".join(r))
            return "\n".join(lines)
    console = FallbackConsole()
    Panel = FallbackPanel
    Text = FallbackText
    Table = FallbackTable

from hardware_assistant.collectors.base import NativeLinuxRunner, MockLinuxRunner
from hardware_assistant.agent.tools import HardwareToolRegistry
from hardware_assistant.agent.engine import HardwareAgentEngine
from hardware_assistant.providers.ollama_provider import OllamaProvider
from hardware_assistant.providers.openai_compatible_provider import OpenAICompatibleProvider
from hardware_assistant.providers.mock_provider import MockLLMProvider
from hardware_assistant.providers.base import LLMProvider


def create_provider(provider_type: str, model_name: str, base_url: Optional[str]) -> LLMProvider:
    """Factory creating the requested LLM inference provider."""
    if provider_type == "ollama":
        url = base_url or "http://localhost:11434"
        ollama = OllamaProvider(model=model_name, base_url=url)
        if not ollama.is_available():
            console.print(
                f"[yellow]Notice: Ollama server not detected at {url}. "
                "Falling back to built-in Mock provider for seamless demonstration.[/yellow]\n"
            )
            return MockLLMProvider()
        return ollama
    elif provider_type == "openai":
        url = base_url or "http://localhost:8000/v1"
        return OpenAICompatibleProvider(base_url=url, model=model_name)
    elif provider_type == "mock":
        return MockLLMProvider()
    else:
        console.print(f"[red]Unknown provider '{provider_type}'. Using mock.[/red]")
        return MockLLMProvider()


def print_banner(runner_type: str, provider_name: str, model_name: str):
    """Displays startup welcome banner and system diagnostics status."""
    banner_text = Text()
    banner_text.append("Linux Laptop Hardware Assistant\n", style="bold green")
    banner_text.append("Grounded Natural-Language Hardware Diagnostics & Tool-Calling\n\n", style="italic")
    banner_text.append(f"• Diagnostics Runner: ", style="bold white")
    banner_text.append(f"{runner_type}\n", style="cyan")
    banner_text.append(f"• LLM Provider:       ", style="bold white")
    banner_text.append(f"{provider_name} ({model_name})\n", style="cyan")
    banner_text.append("• Safety Sandbox:     ", style="bold white")
    banner_text.append("Strict Allowlist (Read-Only, Zero Shell Expansion)\n", style="green")
    banner_text.append("\nType your question in plain English (e.g. 'Can I add more RAM?'), or '/help' for commands.", style="dim")

    console.print(Panel(banner_text, border_style="green", title="[bold]Hardware Q&A Assistant[/bold]", subtitle="v0.1.0"))


def print_help():
    """Prints command cheat sheet."""
    table = Table(title="Available Interactive Commands", border_style="cyan")
    table.add_column("Command", style="bold yellow")
    table.add_column("Description", style="white")

    table.add_row("/help", "Show this help table")
    table.add_row("/tools", "List all safe diagnostic tools and their schemas")
    table.add_row("/inspect <tool>", "Directly run and view structured JSON payload of a tool")
    table.add_row("/clear", "Reset conversation memory and start fresh")
    table.add_row("/exit, /quit", "Exit the assistant")

    console.print(table)


def run_interactive_session(engine: HardwareAgentEngine, registry: HardwareToolRegistry):
    """Main interactive chat loop."""
    while True:
        try:
            user_input = console.input("\n[bold green]hardware>[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting Hardware Assistant. Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input in ("/exit", "/quit", "exit", "quit"):
            console.print("[dim]Goodbye![/dim]")
            break
        elif user_input in ("/help", "help"):
            print_help()
            continue
        elif user_input in ("/clear", "/reset"):
            engine.reset()
            console.print("[green]Conversation memory cleared.[/green]")
            continue
        elif user_input == "/tools":
            from hardware_assistant.agent.tools import TOOL_DEFINITIONS
            table = Table(title="Safe Diagnostic Tool Allowlist", border_style="blue")
            table.add_column("Tool Function", style="bold cyan")
            table.add_column("Description", style="white")
            for t in TOOL_DEFINITIONS:
                fn = t["function"]
                table.add_row(fn["name"], fn["description"])
            console.print(table)
            continue
        elif user_input.startswith("/inspect"):
            parts = user_input.split()
            if len(parts) < 2:
                console.print("[red]Usage: /inspect <tool_name>[/red]")
                continue
            t_name = parts[1]
            res = registry.execute_tool_by_name(t_name)
            console.print_json(data=res.model_dump())
            continue

        # Active tool callbacks for user visibility
        elevation_warning: Optional[str] = None

        def on_tool_start(tool_name: str):
            console.print(f"[dim] ⚙ Calling diagnostic tool: [bold cyan]{tool_name}[/bold cyan]...[/dim]")

        def on_tool_finish(tool_name: str, res):
            nonlocal elevation_warning
            if res.requires_elevation and res.elevation_tip:
                elevation_warning = res.elevation_tip

        # Query the engine with live status
        try:
            with console.status("[bold blue]Analyzing system hardware...[/bold blue]", spinner="dots"):
                answer = engine.ask(
                    user_input,
                    on_tool_start=on_tool_start,
                    on_tool_finish=on_tool_finish,
                )

            console.print(f"\n[bold green]Assistant:[/bold green] {answer}")

            if elevation_warning:
                console.print(
                    Panel(
                        f"[bold yellow]Privilege Note:[/bold yellow] {elevation_warning}",
                        border_style="yellow",
                    )
                )

        except Exception as exc:
            console.print(f"\n[bold red]Error:[/bold red] {str(exc)}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Grounded Linux Laptop Hardware Q&A Assistant")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use pre-recorded mock Linux laptop hardware fixtures (for non-Linux hosts or testing)",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai", "mock"],
        default="mock",
        help="LLM inference provider (default: mock for instant out-of-the-box demo)",
    )
    parser.add_argument(
        "--model",
        default="llama3.2:latest",
        help="Model name for Ollama or OpenAI-compatible provider",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Base URL for provider (e.g. http://localhost:11434 for Ollama)",
    )
    parser.add_argument(
        "--ask",
        type=str,
        help="Single-shot query mode. Runs question and exits immediately.",
    )

    args = parser.parse_args()

    # Determine whether to use native Linux runner or Mock fixtures
    is_linux = sys.platform.startswith("linux")
    if args.mock or not is_linux:
        runner = MockLinuxRunner()
        runner_label = "Mock Linux Laptop (Lenovo ThinkPad T14 Gen 3 / Ubuntu 22.04)"
    else:
        runner = NativeLinuxRunner()
        runner_label = "Native Host Linux Kernel"

    # Setup tool registry and provider
    registry = HardwareToolRegistry(runner)
    provider = create_provider(args.provider, args.model, args.url)
    engine = HardwareAgentEngine(registry=registry, provider=provider)

    # Single-shot non-interactive mode
    if args.ask:
        answer = engine.ask(args.ask)
        print(answer)
        return

    # Interactive session
    print_banner(runner_label, args.provider.upper(), args.model)
    run_interactive_session(engine, registry)


if __name__ == "__main__":
    main()

