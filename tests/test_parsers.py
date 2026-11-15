"""Test suite for hardware telemetry output parsers."""

import json
from pathlib import Path
from hardware_assistant.parsers import (
    parse_lscpu_json,
    parse_free_bytes,
    parse_dmidecode_memory,
    build_memory_spec,
    parse_lsblk_json,
    parse_lspci_vmm,
    build_system_spec,
)

FIXTURES_DIR = Path(__file__).parent.parent / "src" / "hardware_assistant" / "mock_fixtures"


def test_cpu_parser():
    """Verify parsing lscpu JSON output."""
    raw_json = (FIXTURES_DIR / "lscpu.json").read_text(encoding="utf-8")
    cpu = parse_lscpu_json(raw_json)

    assert cpu is not None
    assert cpu.architecture == "x86_64"
    assert "i7-12700H" in cpu.model_name
    assert cpu.physical_cores == 14
    assert cpu.logical_threads == 16
    assert cpu.max_mhz == 4700.0
    assert cpu.virtualization == "VT-x"
    assert "avx2" in cpu.flags


def test_memory_parser_runtime_and_physical_slots():
    """Verify parsing free -b and dmidecode -t memory."""
    free_txt = (FIXTURES_DIR / "free.txt").read_text(encoding="utf-8")
    dmi_txt = (FIXTURES_DIR / "dmidecode_memory.txt").read_text(encoding="utf-8")

    mem_spec = build_memory_spec(free_txt, dmi_txt)
    assert mem_spec is not None
    assert mem_spec.total_bytes == 16489385984
    assert "15.4 GB" in mem_spec.total_human

    # Physical slot checks
    assert mem_spec.has_elevated_data is True
    assert mem_spec.slots_total == 2
    assert mem_spec.slots_used == 1
    assert mem_spec.max_capacity_bytes == 64 * 1024**3
    assert mem_spec.max_capacity_human == "64.0 GB"

    # Slot breakdown
    assert len(mem_spec.slots) == 2
    slot1, slot2 = mem_spec.slots
    assert slot1.installed is True
    assert slot1.size_human == "16 GB"
    assert slot1.memory_type == "DDR4"
    assert slot1.speed_mts == 3200

    assert slot2.installed is False


def test_storage_parser_nvme_and_sata():
    """Verify lsblk parser correctly differentiates NVMe SSD from SATA HDD."""
    raw_json = (FIXTURES_DIR / "lsblk.json").read_text(encoding="utf-8")
    devices = parse_lsblk_json(raw_json)

    assert len(devices) == 2
    nvme_dev = next(d for d in devices if d.name == "nvme0n1")
    sata_dev = next(d for d in devices if d.name == "sda")

    # NVMe checks
    assert nvme_dev.is_nvme is True
    assert nvme_dev.rotational is False  # Non-rotational = SSD
    assert nvme_dev.transport == "nvme"
    assert "SAMSUNG" in nvme_dev.model
    assert len(nvme_dev.partitions) == 2
    assert nvme_dev.partitions[1].mountpoint == "/"

    # SATA HDD checks
    assert sata_dev.is_nvme is False
    assert sata_dev.rotational is True  # Rotational = HDD
    assert sata_dev.transport == "sata"
    assert "Seagate" in sata_dev.vendor


def test_pci_parser_dual_gpu_detection():
    """Verify lspci parser identifies integrated Intel and discrete NVIDIA GPUs."""
    raw_txt = (FIXTURES_DIR / "lspci.txt").read_text(encoding="utf-8")
    devices = parse_lspci_vmm(raw_txt)

    gpus = [d for d in devices if d.is_gpu]
    assert len(gpus) == 2

    intel_gpu = next(g for g in gpus if "Intel" in g.vendor)
    nvidia_gpu = next(g for g in gpus if "NVIDIA" in g.vendor)

    assert "Integrated Graphics" in intel_gpu.device_name
    assert "RTX 3050" in nvidia_gpu.device_name


def test_system_spec_chassis_and_os():
    """Verify system parser decodes chassis number and OS release."""
    os_rel = (FIXTURES_DIR / "os_release.txt").read_text(encoding="utf-8")
    spec = build_system_spec(
        os_release_text=os_rel,
        uname_text="Linux thinkpad-linux 6.5.0-28-generic #29 x86_64",
        product_name="ThinkPad T14 Gen 3",
        sys_vendor="LENOVO",
        bios_version="N3MET08W (1.08 )",
        chassis_type_raw="10",
        battery_percentage=87,
        battery_status="Discharging",
    )

    assert spec.hostname == "thinkpad-linux"
    assert spec.os_name == "Ubuntu"
    assert spec.hardware_model == "ThinkPad T14 Gen 3"
    assert spec.chassis_type == "Notebook"
    assert spec.battery_present is True
    assert spec.battery_percentage == 87

