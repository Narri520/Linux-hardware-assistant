"""Security and sandboxing test suite."""

try:
    import pytest
except ImportError:
    class PytestMock:
        class raises:
            def __init__(self, expected_exc, match=None):
                self.expected_exc = expected_exc
                self.match = match
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(f"Expected exception {self.expected_exc} was not raised")
                return issubclass(exc_type, self.expected_exc)
    pytest = PytestMock()
from hardware_assistant.security import (
    COMMAND_ALLOWLIST,
    SecurityViolationError,
    sanitize_identifier,
    validate_sys_path,
    execute_allowlisted_command,
)


def test_command_allowlist_is_immutable_and_safe():
    """Verify all allowlisted commands use safe argument vectors and read-only flags."""
    forbidden_substrings = [">", "<", "|", "&", ";", "rm", "dd", "mkfs", "sh", "bash"]
    for key, cmd_vector in COMMAND_ALLOWLIST.items():
        assert isinstance(cmd_vector, tuple)
        assert len(cmd_vector) >= 1
        for arg in cmd_vector:
            for forbidden in forbidden_substrings:
                assert forbidden not in arg.split()


def test_arbitrary_command_key_is_rejected():
    """Verify that unapproved command keys immediately raise SecurityViolationError."""
    with pytest.raises(SecurityViolationError, match="not in the security allowlist"):
        execute_allowlisted_command("arbitrary_bash_command")

    with pytest.raises(SecurityViolationError):
        execute_allowlisted_command("rm -rf /")


def test_path_traversal_detection():
    """Verify that directory traversal attempts in /sys or /proc are blocked."""
    with pytest.raises(SecurityViolationError, match="Directory traversal"):
        validate_sys_path("/sys/class/dmi/id/../../../../etc/shadow")

    with pytest.raises(SecurityViolationError, match="blocked by security policy"):
        validate_sys_path("/etc/shadow")

    with pytest.raises(SecurityViolationError, match="blocked by security policy"):
        validate_sys_path("/home/user/.ssh/id_rsa")


def test_allowed_sys_paths():
    """Verify valid /proc and /sys paths pass security checks."""
    assert validate_sys_path("/proc/cpuinfo") == "/proc/cpuinfo"
    assert validate_sys_path("/sys/class/dmi/id/product_name") == "/sys/class/dmi/id/product_name"
    assert validate_sys_path("/etc/os-release") == "/etc/os-release"


def test_identifier_sanitization():
    """Verify regex rejection of shell injection metacharacters."""
    assert sanitize_identifier("nvme0n1") == "nvme0n1"
    assert sanitize_identifier("sda1") == "sda1"

    # Malicious injection inputs must raise SecurityViolationError
    malicious_inputs = [
        "sda1; rm -rf /",
        "nvme0n1 | cat /etc/passwd",
        "$(whoami)",
        "`id`",
        "sda\nreboot",
        "../../etc/passwd",
    ]
    for bad_input in malicious_inputs:
        with pytest.raises(SecurityViolationError):
            sanitize_identifier(bad_input)

