"""Parser for CPU information from lscpu JSON or /proc/cpuinfo."""

import json
import re
from typing import Optional, Dict, Any, List
from hardware_assistant.models import CPUSpec


def parse_lscpu_json(raw_json: str) -> Optional[CPUSpec]:
    """Parses output from `lscpu -J` into CPUSpec."""
    try:
        data = json.loads(raw_json)
        items = data.get("lscpu", [])
        mapping: Dict[str, str] = {}
        for entry in items:
            field = entry.get("field", "").rstrip(":")
            val = entry.get("data", "")
            mapping[field] = val

        arch = mapping.get("Architecture", "unknown")
        model = mapping.get("Model name", "Generic CPU")
        vendor = mapping.get("Vendor ID")
        sockets = int(mapping.get("Socket(s)", "1"))
        
        # Cores and Threads
        cores_per_socket = int(mapping.get("Core(s) per socket", "1"))
        threads_per_core = int(mapping.get("Thread(s) per core", "1"))
        physical_cores = int(mapping.get("CPU(s)", cores_per_socket * sockets))
        # If CPU(s) represents total logical, compute:
        logical_threads = int(mapping.get("CPU(s)", physical_cores))
        if "Core(s) per socket" in mapping:
            physical_cores = cores_per_socket * sockets

        max_mhz = None
        if "CPU max MHz" in mapping:
            try:
                max_mhz = float(mapping["CPU max MHz"])
            except ValueError:
                pass

        min_mhz = None
        if "CPU min MHz" in mapping:
            try:
                min_mhz = float(mapping["CPU min MHz"])
            except ValueError:
                pass

        virt = mapping.get("Virtualization")

        # Extract caches in KB
        l1d = _parse_cache_kb(mapping.get("L1d cache"))
        l1i = _parse_cache_kb(mapping.get("L1i cache"))
        l2 = _parse_cache_kb(mapping.get("L2 cache"))
        l3 = _parse_cache_kb(mapping.get("L3 cache"))

        # Notable flags
        raw_flags = mapping.get("Flags", "").split()
        notable = {"vmx", "svm", "avx", "avx2", "avx512f", "aes", "sse4_2"}
        filtered_flags = [f for f in raw_flags if f in notable]

        return CPUSpec(
            architecture=arch,
            model_name=model,
            vendor_id=vendor,
            sockets=sockets,
            physical_cores=physical_cores,
            logical_threads=logical_threads,
            max_mhz=max_mhz,
            min_mhz=min_mhz,
            l1d_cache_kb=l1d,
            l1i_cache_kb=l1i,
            l2_cache_kb=l2,
            l3_cache_kb=l3,
            virtualization=virt,
            flags=filtered_flags
        )
    except Exception:
        return None


def _parse_cache_kb(cache_str: Optional[str]) -> Optional[int]:
    """Helper to parse cache strings like '544 KiB', '11.5 MiB', or '24 MiB' into KB."""
    if not cache_str:
        return None
    match = re.search(r"([\d\.]+)\s*([KMG])i?B", cache_str, re.IGNORECASE)
    if not match:
        return None
    val = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "K":
        return int(val)
    elif unit == "M":
        return int(val * 1024)
    elif unit == "G":
        return int(val * 1024 * 1024)
    return int(val)

