"""Parser for block storage and partition telemetry from lsblk JSON."""

import json
from typing import List, Optional, Dict, Any
from hardware_assistant.models import StorageDevice, StoragePartition
from hardware_assistant.parsers.memory_parser import format_bytes_human


def parse_lsblk_json(raw_json: str) -> List[StorageDevice]:
    """Parses output from `lsblk -J -b` into a structured list of StorageDevice models."""
    devices: List[StorageDevice] = []
    try:
        data = json.loads(raw_json)
        blockdevices = data.get("blockdevices", [])

        for dev_data in blockdevices:
            dev_type = dev_data.get("type", "disk")
            # We focus primarily on physical/logical disks and loop devices if specified
            if dev_type not in ("disk", "rom"):
                continue

            name = dev_data.get("name", "")
            path = dev_data.get("path", f"/dev/{name}")
            size_bytes = int(dev_data.get("size", 0))
            rota = bool(dev_data.get("rota", False))
            tran = dev_data.get("tran") or ("nvme" if name.startswith("nvme") else None)
            is_nvme = (tran == "nvme") or name.startswith("nvme")

            # Parse partitions / children
            partitions: List[StoragePartition] = []
            for child in dev_data.get("children", []):
                part_name = child.get("name", "")
                part_size = int(child.get("size", 0))
                partitions.append(
                    StoragePartition(
                        name=part_name,
                        size_bytes=part_size,
                        size_human=format_bytes_human(part_size),
                        fstype=child.get("fstype"),
                        mountpoint=child.get("mountpoint"),
                        label=child.get("label"),
                    )
                )

            devices.append(
                StorageDevice(
                    name=name,
                    path=path,
                    size_bytes=size_bytes,
                    size_human=format_bytes_human(size_bytes),
                    type=dev_type,
                    rotational=rota,
                    transport=tran,
                    is_nvme=is_nvme,
                    model=dev_data.get("model"),
                    vendor=dev_data.get("vendor"),
                    serial=dev_data.get("serial"),
                    partitions=partitions,
                )
            )
    except Exception:
        pass

    return devices

