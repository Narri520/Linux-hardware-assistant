"""Hardware telemetry parsers package."""

from hardware_assistant.parsers.cpu_parser import parse_lscpu_json
from hardware_assistant.parsers.memory_parser import (
    parse_free_bytes,
    parse_dmidecode_memory,
    build_memory_spec,
    format_bytes_human,
)
from hardware_assistant.parsers.storage_parser import parse_lsblk_json
from hardware_assistant.parsers.pci_parser import parse_lspci_vmm
from hardware_assistant.parsers.system_parser import build_system_spec

__all__ = [
    "parse_lscpu_json",
    "parse_free_bytes",
    "parse_dmidecode_memory",
    "build_memory_spec",
    "format_bytes_human",
    "parse_lsblk_json",
    "parse_lspci_vmm",
    "build_system_spec",
]

