"""Security and sandboxing module for Linux hardware diagnostic commands.

Guarantees:
- Strictly immutable allowlist of read-only diagnostic commands.
- Zero arbitrary shell execution: shell=True is forbidden; commands run as direct argument vectors.
- Subprocess isolation with timeouts and stripped environment variables.
- Sanitized input validation preventing path traversal and shell injection.
- Safe read-only inspections of /proc and /sys with directory confinement.
"""

import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple, Set

# Permitted command signatures (Executable + Exact fixed argument tuples)
# No command here writes to disk, alters kernel state, or modifies hardware settings.
COMMAND_ALLOWLIST: Dict[str, Tuple[str, ...]] = {
    "lscpu_json": ("lscpu", "-J"),
    "lsblk_json": ("lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,ROTA,TRAN,MOUNTPOINT,FSTYPE,MODEL,VENDOR,SERIAL"),
    "free_bytes": ("free", "-b"),
    "lspci_vmm": ("lspci", "-vmm"),
    "uname_all": ("uname", "-s", "-r", "-v", "-m", "-n"),
    "dmidecode_memory": ("dmidecode", "-t", "memory"),
    "dmidecode_system": ("dmidecode", "-t", "1,2,3"),
}

# Permitted paths in /proc and /sys for unprivileged direct reads
ALLOWED_SYS_PROC_PREFIXES: Tuple[str, ...] = (
    "/proc/cpuinfo",
    "/proc/meminfo",
    "/proc/version",
    "/etc/os-release",
    "/sys/class/dmi/id/",
    "/sys/class/power_supply/",
    "/sys/block/",
)

# Strict regex for any user-supplied identifiers (if ever parameterized)
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class SecurityViolationError(Exception):
    """Raised when an unauthorized command, argument, or path traversal is detected."""
    pass


class CommandExecutionResult:
    """Result of a strictly controlled system command execution."""
    def __init__(self, stdout: str, stderr: str, returncode: int, timed_out: bool = False):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.timed_out = timed_out

    @property
    def is_success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def sanitize_identifier(value: str) -> str:
    """Validates that a string contains only alphanumeric and safe identifier characters."""
    if not value or not SAFE_IDENTIFIER_PATTERN.match(value):
        raise SecurityViolationError(f"Rejected unsafe identifier: '{value}'")
    return value


def validate_sys_path(path: str) -> str:
    """Verifies that a filesystem path strictly resides within allowed /sys or /proc directories.
    
    Prevents directory traversal ('..') and unauthorized filesystem snooping.
    """
    # Normalize path and check against traversal
    normalized = os.path.normpath(path).replace("\\", "/")
    if ".." in normalized:
        raise SecurityViolationError(f"Directory traversal detected in path: '{path}'")
    
    # Verify the path starts with an allowed diagnostic prefix
    is_allowed = any(normalized.startswith(prefix) for prefix in ALLOWED_SYS_PROC_PREFIXES)
    if not is_allowed:
        raise SecurityViolationError(f"Access to path '{path}' is blocked by security policy.")
        
    return normalized


def safe_read_sys_file(path: str, max_bytes: int = 65536) -> Optional[str]:
    """Safely reads a pseudo-filesystem file (/proc or /sys) within security bounds."""
    try:
        valid_path = validate_sys_path(path)
        if not os.path.exists(valid_path) or not os.path.isfile(valid_path):
            return None
        with open(valid_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except (SecurityViolationError, PermissionError, OSError):
        return None


def execute_allowlisted_command(
    key: str,
    timeout_sec: float = 3.0,
    try_sudo_if_needed: bool = True
) -> CommandExecutionResult:
    """Executes a strictly allowlisted command without shell expansion.
    
    Args:
        key: The key in COMMAND_ALLOWLIST.
        timeout_sec: Maximum execution time before SIGKILL.
        try_sudo_if_needed: Whether to try sudo for commands known to need elevation (e.g. dmidecode).
        
    Returns:
        CommandExecutionResult containing output and status.
    """
    if key not in COMMAND_ALLOWLIST:
        raise SecurityViolationError(f"Command key '{key}' is not in the security allowlist.")

    cmd_tuple = COMMAND_ALLOWLIST[key]
    binary = cmd_tuple[0]

    # Verify binary exists on the system
    bin_path = shutil.which(binary)
    if not bin_path:
        return CommandExecutionResult(
            stdout="",
            stderr=f"Diagnostic binary '{binary}' not installed or not in PATH.",
            returncode=127
        )

    cmd_list: List[str] = list(cmd_tuple)
    cmd_list[0] = bin_path  # Use absolute path to prevent PATH hijacking

    # Check if elevated privilege is helpful (e.g. dmidecode) and user has configured sudo
    is_privileged_cmd = binary in ("dmidecode", "lshw")
    current_uid = getattr(os, "geteuid", lambda: 1000)()
    if is_privileged_cmd and current_uid != 0 and try_sudo_if_needed:
        # Check if sudo is available and passwordless for this binary
        sudo_bin = shutil.which("sudo")
        if sudo_bin:
            # We attempt running with -n (non-interactive, never hangs on password prompt)
            cmd_list = [sudo_bin, "-n"] + cmd_list

    # Execute in clean environment with zero shell expansion
    safe_env = {
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }

    try:
        proc = subprocess.run(
            cmd_list,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            shell=False,  # CRITICAL: shell=False prevents shell injection
            env=safe_env,
        )
        return CommandExecutionResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode
        )
    except subprocess.TimeoutExpired:
        return CommandExecutionResult(
            stdout="",
            stderr=f"Command timed out after {timeout_sec} seconds.",
            returncode=124,
            timed_out=True
        )
    except Exception as exc:
        return CommandExecutionResult(
            stdout="",
            stderr=f"Execution error: {str(exc)}",
            returncode=-1
        )
