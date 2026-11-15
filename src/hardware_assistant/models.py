"""Structured data schemas for Linux hardware telemetry."""

from typing import List, Optional, Dict, Any

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Graceful zero-dependency fallback for environments without pydantic
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self) -> Dict[str, Any]:
            res = {}
            for k, v in self.__dict__.items():
                if isinstance(v, list):
                    res[k] = [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
                elif hasattr(v, "model_dump"):
                    res[k] = v.model_dump()
                else:
                    res[k] = v
            return res
        def __repr__(self):
            return f"{self.__class__.__name__}({self.model_dump()})"

    def Field(default=None, default_factory=None, description=""):
        return default_factory() if default_factory else (default if default is not Ellipsis else None)



class CPUSpec(BaseModel):
    """Normalized CPU hardware specification."""
    architecture: str = Field(..., description="CPU architecture, e.g., x86_64, aarch64")
    model_name: str = Field(..., description="Full CPU model branding string")
    vendor_id: Optional[str] = Field(None, description="CPU vendor ID, e.g., GenuineIntel, AuthenticAMD")
    sockets: int = Field(1, description="Number of CPU sockets")
    physical_cores: int = Field(..., description="Physical core count")
    logical_threads: int = Field(..., description="Logical thread (vCPU) count")
    max_mhz: Optional[float] = Field(None, description="Maximum CPU frequency in MHz")
    min_mhz: Optional[float] = Field(None, description="Minimum CPU frequency in MHz")
    l1d_cache_kb: Optional[int] = Field(None, description="L1 Data cache size in KB")
    l1i_cache_kb: Optional[int] = Field(None, description="L1 Instruction cache size in KB")
    l2_cache_kb: Optional[int] = Field(None, description="L2 cache size in KB")
    l3_cache_kb: Optional[int] = Field(None, description="L3 cache size in KB")
    virtualization: Optional[str] = Field(None, description="Virtualization support (e.g. VT-x, AMD-V)")
    flags: List[str] = Field(default_factory=list, description="Notable instruction flags")


class MemorySlot(BaseModel):
    """Specification of an individual physical RAM slot."""
    locator: str = Field(..., description="Physical slot label, e.g., DIMM 0, Controller0-ChannelA")
    installed: bool = Field(..., description="Whether a RAM stick is currently installed in this slot")
    size_bytes: Optional[int] = Field(None, description="Installed module capacity in bytes")
    size_human: Optional[str] = Field(None, description="Installed module capacity human-readable (e.g., 16 GB)")
    memory_type: Optional[str] = Field(None, description="RAM standard, e.g., DDR4, DDR5, LPDDR5")
    speed_mts: Optional[int] = Field(None, description="Configured speed in MT/s or MHz")
    form_factor: Optional[str] = Field(None, description="Form factor, e.g., SODIMM, DIMM, Soldered")
    manufacturer: Optional[str] = Field(None, description="Memory manufacturer")
    part_number: Optional[str] = Field(None, description="Memory part number")


class MemorySpec(BaseModel):
    """Normalized Memory specification (combining runtime usage and physical slots)."""
    total_bytes: int = Field(..., description="Total available physical RAM in bytes")
    total_human: str = Field(..., description="Total physical RAM in human-readable units (e.g., 15.4 GB)")
    used_bytes: int = Field(..., description="Currently used RAM in bytes")
    available_bytes: int = Field(..., description="Currently available RAM in bytes")
    free_bytes: int = Field(..., description="Unused RAM in bytes")
    swap_total_bytes: int = Field(0, description="Total swap space in bytes")
    swap_free_bytes: int = Field(0, description="Free swap space in bytes")
    
    # Physical upgrade telemetry (from dmidecode if accessible)
    slots_total: Optional[int] = Field(None, description="Total physical RAM slots supported by motherboard")
    slots_used: Optional[int] = Field(None, description="Number of currently populated RAM slots")
    max_capacity_bytes: Optional[int] = Field(None, description="Maximum motherboard supported RAM capacity in bytes")
    max_capacity_human: Optional[str] = Field(None, description="Maximum motherboard supported capacity (e.g., 64 GB)")
    slots: List[MemorySlot] = Field(default_factory=list, description="Detailed slot breakdown")
    has_elevated_data: bool = Field(False, description="Whether physical slot data was obtained via dmidecode")


class StoragePartition(BaseModel):
    """Specification of a disk partition."""
    name: str = Field(..., description="Partition device name (e.g., nvme0n1p1)")
    size_bytes: int = Field(..., description="Partition size in bytes")
    size_human: str = Field(..., description="Human readable size")
    fstype: Optional[str] = Field(None, description="Filesystem type (e.g., ext4, btrfs, vfat)")
    mountpoint: Optional[str] = Field(None, description="Mount path (e.g., /, /boot/efi)")
    label: Optional[str] = Field(None, description="Partition label")


class StorageDevice(BaseModel):
    """Specification of a physical or logical storage disk."""
    name: str = Field(..., description="Device name (e.g. nvme0n1, sda)")
    path: str = Field(..., description="Device path (e.g. /dev/nvme0n1)")
    size_bytes: int = Field(..., description="Disk size in bytes")
    size_human: str = Field(..., description="Human-readable disk size")
    type: str = Field(..., description="Device type: disk, loop, rom")
    rotational: bool = Field(..., description="True if HDD (spinning platter), False if SSD/NVMe")
    transport: Optional[str] = Field(None, description="Bus type: nvme, sata, usb, scsi, mmc")
    is_nvme: bool = Field(False, description="True if disk operates over NVMe protocol")
    model: Optional[str] = Field(None, description="Disk model string")
    vendor: Optional[str] = Field(None, description="Disk manufacturer/vendor")
    serial: Optional[str] = Field(None, description="Serial number if permitted")
    partitions: List[StoragePartition] = Field(default_factory=list, description="Child partitions")


class PCIDevice(BaseModel):
    """Specification of a PCI bus device (e.g. GPU, Network controller, Sound card)."""
    slot: str = Field(..., description="PCI bus slot identifier, e.g., 00:02.0")
    device_class: str = Field(..., description="Device class name (e.g. VGA compatible controller, 3D controller)")
    vendor: str = Field(..., description="Vendor name, e.g. Intel Corporation, NVIDIA Corporation")
    device_name: str = Field(..., description="Device model string")
    subsystem_vendor: Optional[str] = Field(None, description="Subsystem vendor (e.g. Lenovo, Dell)")
    subsystem_device: Optional[str] = Field(None, description="Subsystem device name")
    driver: Optional[str] = Field(None, description="Kernel driver in use")
    is_gpu: bool = Field(False, description="True if device is an integrated or discrete graphics accelerator")


class SystemSpec(BaseModel):
    """System motherboard, chassis, OS, and battery specification."""
    hostname: str = Field(..., description="Machine network hostname")
    os_name: str = Field(..., description="Linux distribution name")
    os_version: str = Field(..., description="Distribution release version")
    kernel_release: str = Field(..., description="Linux kernel release string")
    hardware_model: Optional[str] = Field(None, description="Laptop or motherboard model (e.g., ThinkPad T14 Gen 3)")
    hardware_vendor: Optional[str] = Field(None, description="System manufacturer (e.g., LENOVO, Dell Inc.)")
    bios_version: Optional[str] = Field(None, description="BIOS firmware release version")
    bios_date: Optional[str] = Field(None, description="BIOS release date")
    chassis_type: Optional[str] = Field(None, description="Chassis type (Notebook, Laptop, Desktop)")
    battery_present: bool = Field(False, description="Whether a laptop battery is installed")
    battery_percentage: Optional[int] = Field(None, description="Current battery charge percentage")
    battery_status: Optional[str] = Field(None, description="Battery state: Charging, Discharging, Full")


class ToolExecutionResult(BaseModel):
    """Standardized output wrapper for all hardware diagnostic collector tools."""
    tool_name: str = Field(..., description="Name of the diagnostic tool called")
    success: bool = Field(..., description="Whether the tool execution and parsing succeeded")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured parsed telemetry payload")
    error: Optional[str] = Field(None, description="Error message or permission warning if unsuccessful")
    source: str = Field("native", description="'native' or 'mock'")
    requires_elevation: bool = Field(False, description="True if data was incomplete due to lack of root privileges")
    elevation_tip: Optional[str] = Field(None, description="Actionable command/sudoers tip to grant safe read access")
