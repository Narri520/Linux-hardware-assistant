"""Base interfaces and runners for hardware diagnostic commands."""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from hardware_assistant.security import (
    CommandExecutionResult,
    execute_allowlisted_command,
    safe_read_sys_file,
)


class SystemRunner(ABC):
    """Abstract interface for running read-only diagnostic commands and inspecting /proc or /sys."""

    @abstractmethod
    def run_command(self, key: str) -> CommandExecutionResult:
        """Run an allowlisted diagnostic command."""
        pass

    @abstractmethod
    def read_sys_file(self, path: str) -> Optional[str]:
        """Read a diagnostic file from /sys or /proc."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Whether this runner is returning synthetic mock fixtures."""
        pass


class NativeLinuxRunner(SystemRunner):
    """Executes safe commands directly on the host Linux kernel."""

    def run_command(self, key: str) -> CommandExecutionResult:
        return execute_allowlisted_command(key)

    def read_sys_file(self, path: str) -> Optional[str]:
        return safe_read_sys_file(path)

    @property
    def is_mock(self) -> bool:
        return False


class MockLinuxRunner(SystemRunner):
    """Provides realistic diagnostic telemetry from pre-recorded Linux hardware dumps.
    
    Used for safe testing, CI environments, and demonstrations on non-Linux hosts.
    """

    def __init__(self, fixtures_dir: Optional[str] = None):
        if fixtures_dir:
            self.fixtures_path = Path(fixtures_dir)
        else:
            self.fixtures_path = Path(__file__).parent.parent / "mock_fixtures"

    def _read_fixture(self, filename: str) -> str:
        filepath = self.fixtures_path / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def run_command(self, key: str) -> CommandExecutionResult:
        if key == "lscpu_json":
            out = self._read_fixture("lscpu.json")
            return CommandExecutionResult(stdout=out, stderr="", returncode=0)
        elif key == "lsblk_json":
            out = self._read_fixture("lsblk.json")
            return CommandExecutionResult(stdout=out, stderr="", returncode=0)
        elif key == "free_bytes":
            out = self._read_fixture("free.txt")
            return CommandExecutionResult(stdout=out, stderr="", returncode=0)
        elif key == "dmidecode_memory":
            out = self._read_fixture("dmidecode_memory.txt")
            return CommandExecutionResult(stdout=out, stderr="", returncode=0)
        elif key == "lspci_vmm":
            out = self._read_fixture("lspci.txt")
            return CommandExecutionResult(stdout=out, stderr="", returncode=0)
        elif key == "uname_all":
            return CommandExecutionResult(
                stdout="Linux thinkpad-linux 6.5.0-28-generic #29~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 28 14:15:35 UTC 2 x86_64\n",
                stderr="",
                returncode=0
            )
        else:
            return CommandExecutionResult(
                stdout="",
                stderr=f"Unknown mock command key: {key}",
                returncode=1
            )

    def read_sys_file(self, path: str) -> Optional[str]:
        if path == "/etc/os-release":
            return self._read_fixture("os_release.txt")
        
        # Load dmi_sys mock
        dmi_str = self._read_fixture("dmi_sys.json")
        if dmi_str:
            dmi_data = json.loads(dmi_str)
            if "product_name" in path:
                return dmi_data.get("product_name", "")
            elif "sys_vendor" in path:
                return dmi_data.get("sys_vendor", "")
            elif "bios_version" in path:
                return dmi_data.get("bios_version", "")
            elif "chassis_type" in path:
                return dmi_data.get("chassis_type", "")
            elif "capacity" in path:
                return str(dmi_data.get("battery_percentage", 87))
            elif "status" in path:
                return dmi_data.get("battery_status", "Discharging")

        return None

    @property
    def is_mock(self) -> bool:
        return True

