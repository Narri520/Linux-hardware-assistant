"""Parser for system memory and physical RAM slots (free and dmidecode)."""

import re
from typing import Optional, List, Tuple
from hardware_assistant.models import MemorySpec, MemorySlot


def format_bytes_human(num_bytes: int) -> str:
    """Converts bytes to human readable format (e.g. 16.0 GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        num_bytes /= 1024.0
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
    return f"{num_bytes:.1f} PB"


def parse_free_bytes(raw_output: str) -> Optional[Tuple[int, int, int, int, int, int]]:
    """Parses output of `free -b`.
    
    Returns:
        (total, used, free, available, swap_total, swap_free)
    """
    try:
        lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]
        mem_line = None
        swap_line = None
        for line in lines:
            parts = line.split()
            if parts[0].startswith("Mem:"):
                mem_line = parts
            elif parts[0].startswith("Swap:"):
                swap_line = parts

        if not mem_line:
            return None

        total = int(mem_line[1])
        used = int(mem_line[2])
        free = int(mem_line[3])
        # In free -b, columns: total, used, free, shared, buff/cache, available
        available = int(mem_line[6]) if len(mem_line) > 6 else free

        swap_total = 0
        swap_free = 0
        if swap_line and len(swap_line) >= 4:
            swap_total = int(swap_line[1])
            swap_free = int(swap_line[3])

        return (total, used, free, available, swap_total, swap_free)
    except Exception:
        return None


def parse_dmidecode_memory(raw_output: str) -> Tuple[Optional[int], List[MemorySlot]]:
    """Parses `dmidecode -t memory` to extract max supported capacity and physical slots.
    
    Returns:
        (max_capacity_bytes, list_of_slots)
    """
    slots: List[MemorySlot] = []
    max_capacity_bytes = None

    if not raw_output or "Permission denied" in raw_output or "No SMBIOS" in raw_output:
        return None, slots

    # Parse Maximum Capacity
    max_cap_match = re.search(r"Maximum Capacity:\s*([\d\.]+)\s*([KMGTP]B)", raw_output, re.IGNORECASE)
    if max_cap_match:
        val = float(max_cap_match.group(1))
        unit = max_cap_match.group(2).upper()
        multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        max_capacity_bytes = int(val * multipliers.get(unit, 1024**3))

    # Parse Memory Device blocks
    blocks = raw_output.split("Memory Device\n")
    for block in blocks[1:]:
        locator_m = re.search(r"Locator:\s*([^\n]+)", block)
        size_m = re.search(r"Size:\s*([^\n]+)", block)
        type_m = re.search(r"Type:\s*([^\n]+)", block)
        speed_m = re.search(r"Speed:\s*(\d+)\s*(MT/s|MHz)?", block)
        form_m = re.search(r"Form Factor:\s*([^\n]+)", block)
        manuf_m = re.search(r"Manufacturer:\s*([^\n]+)", block)
        part_m = re.search(r"Part Number:\s*([^\n]+)", block)

        locator = locator_m.group(1).strip() if locator_m else "Unknown Slot"
        size_str = size_m.group(1).strip() if size_m else "Unknown"

        if "No Module Installed" in size_str or size_str == "0":
            slots.append(
                MemorySlot(
                    locator=locator,
                    installed=False,
                    form_factor=form_m.group(1).strip() if form_m else None,
                )
            )
        else:
            # Installed stick
            size_bytes = None
            size_bytes_m = re.search(r"(\d+)\s*([KMGTP]B)", size_str, re.IGNORECASE)
            if size_bytes_m:
                val = float(size_bytes_m.group(1))
                u = size_bytes_m.group(2).upper()
                mults = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                size_bytes = int(val * mults.get(u, 1024**3))

            speed_val = int(speed_m.group(1)) if speed_m else None
            mem_type = type_m.group(1).strip() if type_m and type_m.group(1).strip() != "Unknown" else None

            slots.append(
                MemorySlot(
                    locator=locator,
                    installed=True,
                    size_bytes=size_bytes,
                    size_human=size_str,
                    memory_type=mem_type,
                    speed_mts=speed_val,
                    form_factor=form_m.group(1).strip() if form_m else None,
                    manufacturer=manuf_m.group(1).strip() if manuf_m and manuf_m.group(1).strip() != "NO DIMM" else None,
                    part_number=part_m.group(1).strip() if part_m and part_m.group(1).strip() != "NO DIMM" else None,
                )
            )

    return max_capacity_bytes, slots


def build_memory_spec(free_output: str, dmi_output: Optional[str] = None) -> Optional[MemorySpec]:
    """Combines runtime OS memory telemetry with physical motherboard slot diagnostics."""
    usage = parse_free_bytes(free_output)
    if not usage:
        return None

    total, used, free, available, swap_tot, swap_free = usage
    max_cap = None
    slots: List[MemorySlot] = []
    has_elevated = False

    if dmi_output:
        max_cap, slots = parse_dmidecode_memory(dmi_output)
        if slots or max_cap is not None:
            has_elevated = True

    slots_total = len(slots) if slots else None
    slots_used = len([s for s in slots if s.installed]) if slots else None
    max_cap_human = format_bytes_human(max_cap) if max_cap else None

    return MemorySpec(
        total_bytes=total,
        total_human=format_bytes_human(total),
        used_bytes=used,
        available_bytes=available,
        free_bytes=free,
        swap_total_bytes=swap_tot,
        swap_free_bytes=swap_free,
        slots_total=slots_total,
        slots_used=slots_used,
        max_capacity_bytes=max_cap,
        max_capacity_human=max_cap_human,
        slots=slots,
        has_elevated_data=has_elevated,
    )

