#!/usr/bin/env python3
"""Automated demonstration of the Linux Hardware Q&A Assistant."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
except ImportError:
    import re
    STYLE_TAG_PATTERN = re.compile(r"\[/?(?:bold|italic|dim|cyan|yellow|green|white|red|blue|magenta)[^\]]*\]")
    class FallbackConsole:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            clean = STYLE_TAG_PATTERN.sub("", text)
            print(clean)
    class FallbackPanel:
        @staticmethod
        def fit(text, border_style=None):
            clean = STYLE_TAG_PATTERN.sub("", text)
            return f"============================================================\n{clean}\n============================================================"
    console = FallbackConsole()
    Panel = FallbackPanel

from hardware_assistant.collectors.base import MockLinuxRunner
from hardware_assistant.agent.tools import HardwareToolRegistry
from hardware_assistant.agent.engine import HardwareAgentEngine
from hardware_assistant.providers.mock_provider import MockLLMProvider


def run_demo():
    console.print(
        Panel.fit(
            "[bold green]Linux Laptop Hardware Assistant — Live Demonstration[/bold green]\n"
            "[italic]Safe Read-Only System Tool Calling, Telemetry Normalization & Multi-Turn Grounding[/italic]",
            border_style="green"
        )
    )

    runner = MockLinuxRunner()
    registry = HardwareToolRegistry(runner)
    provider = MockLLMProvider()
    engine = HardwareAgentEngine(registry=registry, provider=provider)

    test_queries = [
        "Can I add more RAM, and how much?",
        "and what about the GPU?",
        "Is my SSD NVMe?",
    ]

    for idx, query in enumerate(test_queries, 1):
        console.print(f"\n[bold yellow]Step {idx}: User Query[/bold yellow]")
        console.print(f"[bold white]> {query}[/bold white]")

        def on_tool_start(tool_name: str):
            console.print(f"  [cyan]⚡ Tool Triggered:[/cyan] [bold]{tool_name}()[/bold]")

        def on_tool_finish(tool_name: str, res):
            console.print(f"  [dim]✔ Normalized Payload: {len(str(res.data))} bytes | Source: {res.source}[/dim]")

        answer = engine.ask(
            query,
            on_tool_start=on_tool_start,
            on_tool_finish=on_tool_finish,
        )

        console.print(f"\n[bold green]Assistant Answer:[/bold green]\n{answer}")
        console.print("[dim]" + "─" * 60 + "[/dim]")

    console.print("\n[bold green]✔ Demonstration completed successfully![/bold green]\n")


if __name__ == "__main__":
    run_demo()

