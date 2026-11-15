"""Integration tests for the hardware agent engine and multi-turn dialogs."""

from hardware_assistant.collectors.base import MockLinuxRunner
from hardware_assistant.agent.tools import HardwareToolRegistry
from hardware_assistant.agent.engine import HardwareAgentEngine
from hardware_assistant.providers.mock_provider import MockLLMProvider


def setup_engine() -> HardwareAgentEngine:
    runner = MockLinuxRunner()
    registry = HardwareToolRegistry(runner)
    provider = MockLLMProvider()
    return HardwareAgentEngine(registry=registry, provider=provider)


def test_core_example_flow_ram_upgrade():
    """Validates the exact example from the interview problem specification:
    
    User: "Can I add more RAM, and how much?"
    Expected: "You have 16 GB in 1 of 2 slots. The board supports up to 64 GB, so you can add a stick of up to 32 GB."
    """
    engine = setup_engine()
    answer = engine.ask("Can I add more RAM, and how much?")

    assert "16 GB" in answer
    assert "1 of 2 slots" in answer
    assert "64.0 GB" in answer or "64 GB" in answer
    assert "32 GB" in answer


def test_storage_nvme_question():
    """Validates SSD NVMe inspection query: 'Is my SSD NVMe?'"""
    engine = setup_engine()
    answer = engine.ask("Is my SSD NVMe?")

    assert "NVMe" in answer
    assert "nvme0n1" in answer
    assert "SAMSUNG" in answer


def test_multi_turn_follow_up():
    """Validates follow-up query context handling:
    Turn 1: "How much RAM do I have?"
    Turn 2: "and what about the GPU?"
    """
    engine = setup_engine()

    # Turn 1: RAM
    ans1 = engine.ask("How much RAM do I have?")
    assert "RAM" in ans1 or "15.4 GB" in ans1

    # Turn 2: Follow-up on GPU
    ans2 = engine.ask("and what about the GPU?")
    assert "graphics" in ans2.lower() or "gpu" in ans2.lower()
    assert "Intel" in ans2 or "NVIDIA" in ans2


def test_cpu_query():
    """Validates CPU inspection query."""
    engine = setup_engine()
    answer = engine.ask("What CPU do I have?")

    assert "i7-12700H" in answer
    assert "cores" in answer


def test_engine_reset():
    """Validates conversation reset restores system prompt state."""
    engine = setup_engine()
    engine.ask("How much RAM do I have?")
    assert len(engine.messages) > 1

    engine.reset()
    assert len(engine.messages) == 1
    assert engine.messages[0]["role"] == "system"

