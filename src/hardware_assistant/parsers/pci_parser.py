"""Parser for PCI bus devices from `lspci -vmm`."""

import re
from typing import List, Dict
from hardware_assistant.models import PCIDevice


def parse_lspci_vmm(raw_output: str) -> List[PCIDevice]:
    """Parses machine-readable key-value blocks from `lspci -vmm` into PCIDevice models."""
    devices: List[PCIDevice] = []
    if not raw_output.strip():
        return devices

    blocks = raw_output.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        fields: Dict[str, str] = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                fields[key.strip()] = val.strip()

        slot = fields.get("Slot", "")
        dev_class = fields.get("Class", "")
        vendor = fields.get("Vendor", "")
        dev_name = fields.get("Device", "")
        svendor = fields.get("SVendor")
        sdevice = fields.get("SDevice")
        driver = fields.get("Driver")

        if not slot or not dev_name:
            continue

        # Classify GPU
        is_gpu = False
        lower_class = dev_class.lower()
        if "vga" in lower_class or "3d" in lower_class or "display" in lower_class:
            is_gpu = True
        elif "graphics" in dev_name.lower() or "geforce" in dev_name.lower() or "radeon" in dev_name.lower():
            is_gpu = True

        devices.append(
            PCIDevice(
                slot=slot,
                device_class=dev_class,
                vendor=vendor,
                device_name=dev_name,
                subsystem_vendor=svendor,
                subsystem_device=sdevice,
                driver=driver,
                is_gpu=is_gpu,
            )
        )

    return devices

