"""Tool definitions and dispatcher for LLM agent function calling."""

import json
from typing import Dict, Any, List, Optional
from hardware_assistant.collectors.base import SystemRunner
from hardware_assistant.models import ToolExecutionResult
from hardware_assistant.parsers import (
    parse_lscpu_json,
    build_memory_spec,
    parse_lsblk_json,
    parse_lspci_vmm,
    build_system_spec,
)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_memory_info",
            "description": "Inspects system RAM usage and physical motherboard memory slots, capacity, and upgradeability.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cpu_info",
            "description": "Inspects processor specifications including architecture, core/thread count, frequencies, and virtualization.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_storage_info",
            "description": "Inspects storage disks and partitions, identifying SSD vs HDD, NVMe vs SATA, sizes, and mountpoints.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_gpu_and_pci_info",
            "description": "Inspects PCI bus devices focusing on integrated and discrete graphics cards (GPUs), network cards, etc.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_overview",
            "description": "Inspects laptop hardware model, manufacturer, BIOS version, OS distribution, kernel, and battery status.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


class HardwareToolRegistry:
    """Dispatches safe read-only tool calls to system collectors and parses results."""

    def __init__(self, runner: SystemRunner):
        self.runner = runner

    def get_memory_info(self) -> ToolExecutionResult:
        """Collects memory telemetry."""
        free_res = self.runner.run_command("free_bytes")
        dmi_res = self.runner.run_command("dmidecode_memory")
        
        dmi_out = dmi_res.stdout if dmi_res.is_success else None
        elevation_needed = False
        elevation_tip = None

        if not dmi_res.is_success:
            elevation_needed = True
            elevation_tip = (
                "Physical RAM slot details and maximum motherboard capacity require read access to DMI/SMBIOS tables. "
                "Configure safe sudoers with: scripts/install_sudoers.sh"
            )

        spec = build_memory_spec(free_res.stdout, dmi_out)
        if not spec:
            return ToolExecutionResult(
                tool_name="get_memory_info",
                success=False,
                error=f"Failed to inspect memory. stderr: {free_res.stderr}",
                source="mock" if self.runner.is_mock else "native"
            )

        return ToolExecutionResult(
            tool_name="get_memory_info",
            success=True,
            data=spec.model_dump(),
            requires_elevation=elevation_needed and not spec.has_elevated_data,
            elevation_tip=elevation_tip if (elevation_needed and not spec.has_elevated_data) else None,
            source="mock" if self.runner.is_mock else "native"
        )

    def get_cpu_info(self) -> ToolExecutionResult:
        """Collects CPU telemetry."""
        res = self.runner.run_command("lscpu_json")
        if not res.is_success:
            return ToolExecutionResult(
                tool_name="get_cpu_info",
                success=False,
                error=f"lscpu command failed: {res.stderr}",
                source="mock" if self.runner.is_mock else "native"
            )

        spec = parse_lscpu_json(res.stdout)
        if not spec:
            return ToolExecutionResult(
                tool_name="get_cpu_info",
                success=False,
                error="Could not parse lscpu output.",
                source="mock" if self.runner.is_mock else "native"
            )

        return ToolExecutionResult(
            tool_name="get_cpu_info",
            success=True,
            data=spec.model_dump(),
            source="mock" if self.runner.is_mock else "native"
        )

    def get_storage_info(self) -> ToolExecutionResult:
        """Collects block storage telemetry."""
        res = self.runner.run_command("lsblk_json")
        if not res.is_success:
            return ToolExecutionResult(
                tool_name="get_storage_info",
                success=False,
                error=f"lsblk command failed: {res.stderr}",
                source="mock" if self.runner.is_mock else "native"
            )

        devices = parse_lsblk_json(res.stdout)
        return ToolExecutionResult(
            tool_name="get_storage_info",
            success=True,
            data={"devices": [d.model_dump() for d in devices]},
            source="mock" if self.runner.is_mock else "native"
        )

    def get_gpu_and_pci_info(self) -> ToolExecutionResult:
        """Collects PCI bus and GPU telemetry."""
        res = self.runner.run_command("lspci_vmm")
        if not res.is_success:
            return ToolExecutionResult(
                tool_name="get_gpu_and_pci_info",
                success=False,
                error=f"lspci command failed: {res.stderr}",
                source="mock" if self.runner.is_mock else "native"
            )

        devices = parse_lspci_vmm(res.stdout)
        gpus = [d.model_dump() for d in devices if d.is_gpu]
        all_devs = [d.model_dump() for d in devices]

        return ToolExecutionResult(
            tool_name="get_gpu_and_pci_info",
            success=True,
            data={
                "gpus": gpus,
                "all_pci_devices": all_devs
            },
            source="mock" if self.runner.is_mock else "native"
        )

    def get_system_overview(self) -> ToolExecutionResult:
        """Collects overall machine and battery telemetry."""
        uname_res = self.runner.run_command("uname_all")
        os_rel = self.runner.read_sys_file("/etc/os-release")
        product = self.runner.read_sys_file("/sys/class/dmi/id/product_name")
        vendor = self.runner.read_sys_file("/sys/class/dmi/id/sys_vendor")
        bios_v = self.runner.read_sys_file("/sys/class/dmi/id/bios_version")
        bios_d = self.runner.read_sys_file("/sys/class/dmi/id/bios_date")
        chassis = self.runner.read_sys_file("/sys/class/dmi/id/chassis_type")

        # Battery
        bat_cap_str = self.runner.read_sys_file("/sys/class/power_supply/BAT0/capacity")
        bat_stat_str = self.runner.read_sys_file("/sys/class/power_supply/BAT0/status")
        bat_pct = int(bat_cap_str.strip()) if bat_cap_str and bat_cap_str.strip().isdigit() else None
        bat_stat = bat_stat_str.strip() if bat_stat_str else None

        spec = build_system_spec(
            os_release_text=os_rel,
            uname_text=uname_res.stdout if uname_res.is_success else None,
            product_name=product,
            sys_vendor=vendor,
            bios_version=bios_v,
            bios_date=bios_d,
            chassis_type_raw=chassis,
            battery_percentage=bat_pct,
            battery_status=bat_stat,
        )

        return ToolExecutionResult(
            tool_name="get_system_overview",
            success=True,
            data=spec.model_dump(),
            source="mock" if self.runner.is_mock else "native"
        )

    def execute_tool_by_name(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> ToolExecutionResult:
        """Executes a tool by string name."""
        dispatch = {
            "get_memory_info": self.get_memory_info,
            "get_cpu_info": self.get_cpu_info,
            "get_storage_info": self.get_storage_info,
            "get_gpu_and_pci_info": self.get_gpu_and_pci_info,
            "get_system_overview": self.get_system_overview,
        }

        if tool_name not in dispatch:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Unrecognized tool '{tool_name}'"
            )

        return dispatch[tool_name]()

