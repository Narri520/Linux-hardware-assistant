"""Parser for system host, motherboard, OS, and battery specifications."""

import re
from typing import Optional, Dict
from hardware_assistant.models import SystemSpec


def parse_os_release(content: str) -> Dict[str, str]:
    """Parses /etc/os-release key-value pairs."""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip("\"'")
        result[key] = val
    return result


def parse_uname(content: str) -> Dict[str, str]:
    """Parses `uname -s -r -v -m -n`."""
    parts = content.strip().split()
    if len(parts) >= 3:
        return {
            "kernel_name": parts[0],
            "hostname": parts[1],
            "kernel_release": parts[2],
            "architecture": parts[-1] if len(parts) > 3 else "unknown"
        }
    return {}


def build_system_spec(
    os_release_text: Optional[str] = None,
    uname_text: Optional[str] = None,
    product_name: Optional[str] = None,
    sys_vendor: Optional[str] = None,
    bios_version: Optional[str] = None,
    bios_date: Optional[str] = None,
    chassis_type_raw: Optional[str] = None,
    battery_percentage: Optional[int] = None,
    battery_status: Optional[str] = None,
) -> SystemSpec:
    """Builds unified SystemSpec from /sys files and system outputs."""
    os_info = parse_os_release(os_release_text) if os_release_text else {}
    uname_info = parse_uname(uname_text) if uname_text else {}

    hostname = uname_info.get("hostname", "localhost")
    os_name = os_info.get("NAME", "Linux")
    os_version = os_info.get("VERSION", os_info.get("PRETTY_NAME", "Unknown"))
    kernel = uname_info.get("kernel_release", "Unknown")

    # Decode chassis type number if string is numeric (SMBIOS specification)
    chassis_map = {
        "8": "Portable",
        "9": "Laptop",
        "10": "Notebook",
        "11": "Hand Held",
        "14": "Sub Notebook",
        "30": "Tablet",
        "31": "Convertible",
        "32": "Detachable",
    }
    chassis_desc = chassis_map.get(chassis_type_raw.strip(), "Laptop/Notebook") if chassis_type_raw else None

    battery_present = battery_percentage is not None

    return SystemSpec(
        hostname=hostname,
        os_name=os_name,
        os_version=os_version,
        kernel_release=kernel,
        hardware_model=product_name.strip() if product_name else None,
        hardware_vendor=sys_vendor.strip() if sys_vendor else None,
        bios_version=bios_version.strip() if bios_version else None,
        bios_date=bios_date.strip() if bios_date else None,
        chassis_type=chassis_desc,
        battery_present=battery_present,
        battery_percentage=battery_percentage,
        battery_status=battery_status,
    )

