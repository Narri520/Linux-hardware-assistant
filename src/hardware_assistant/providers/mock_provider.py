"""Deterministic Mock LLM provider for testing, non-LLM demo mode, and offline CI."""

import json
from typing import List, Dict, Any, Optional
from hardware_assistant.providers.base import LLMProvider, ProviderResponse, ToolCall


class MockLLMProvider(LLMProvider):
    """Simulates an intelligent LLM that reliably generates tool calls and answers questions.
    
    Ensures tests and demonstrations run without external API keys or Ollama dependencies.
    """

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        # Find the most recent user message index
        last_user_idx = -1
        for idx in range(len(messages) - 1, -1, -1):
            if messages[idx].get("role") == "user":
                last_user_idx = idx
                break

        last_user_msg = messages[last_user_idx].get("content", "").lower() if last_user_idx != -1 else ""

        # Only check for tool results that belong to the current turn (after last_user_idx)
        last_tool_res = None
        tool_name = None
        if last_user_idx != -1:
            for msg in messages[last_user_idx + 1:]:
                if msg.get("role") == "tool":
                    content = msg.get("content", "{}")
                    try:
                        last_tool_res = json.loads(content)
                    except Exception:
                        last_tool_res = {}
                    tool_name = msg.get("name")

        # Phase 1: If we have not yet called a tool for this turn, emit the appropriate tool call
        if last_tool_res is None:
            if any(w in last_user_msg for w in ["ram", "memory", "dimm", "sodimm", "slot"]):
                return ProviderResponse(tool_calls=[ToolCall(name="get_memory_info")])
            elif any(w in last_user_msg for w in ["cpu", "processor", "core", "ghz", "mhz"]):
                return ProviderResponse(tool_calls=[ToolCall(name="get_cpu_info")])
            elif any(w in last_user_msg for w in ["ssd", "nvme", "disk", "storage", "drive", "hard drive", "hdd"]):
                return ProviderResponse(tool_calls=[ToolCall(name="get_storage_info")])
            elif any(w in last_user_msg for w in ["gpu", "graphics", "video", "nvidia", "radeon", "pci"]):
                return ProviderResponse(tool_calls=[ToolCall(name="get_gpu_and_pci_info")])
            elif any(w in last_user_msg for w in ["battery", "model", "laptop", "os", "kernel", "system", "bios", "specs"]):
                return ProviderResponse(tool_calls=[ToolCall(name="get_system_overview")])
            else:
                return ProviderResponse(
                    content="I can inspect your CPU, RAM, SSD/storage, GPU, battery, and system specifications. "
                            "What hardware component would you like to know about?"
                )

        # Phase 2: Formulate grounded answer from tool output
        data = last_tool_res.get("data", {})
        
        if tool_name == "get_memory_info":
            total = data.get("total_human", "Unknown")
            slots_used = data.get("slots_used")
            slots_total = data.get("slots_total")
            max_cap = data.get("max_capacity_human")

            if "add" in last_user_msg or "upgrade" in last_user_msg or "more" in last_user_msg or "slot" in last_user_msg:
                if slots_total and max_cap:
                    installed_stick = "16 GB"
                    for s in data.get("slots", []):
                        if s.get("installed") and s.get("size_human"):
                            installed_stick = s["size_human"]
                            break
                    free_slots = slots_total - (slots_used or 1)
                    return ProviderResponse(
                        content=f"You have {installed_stick} in {slots_used} of {slots_total} slots. "
                                f"The board supports up to {max_cap}, so you can add a stick of up to 32 GB in the {free_slots} empty slot."
                    )
                else:
                    return ProviderResponse(
                        content=f"You currently have {total} of RAM installed. Motherboard slot and upgrade information "
                                f"requires elevated permissions to read SMBIOS tables (`dmidecode`)."
                    )
            return ProviderResponse(
                content=f"You have {total} of total RAM ({data.get('used_bytes', 0) // (1024**3)} GB used, "
                        f"{data.get('available_bytes', 0) // (1024**3)} GB available)."
            )

        elif tool_name == "get_storage_info":
            devices = data.get("devices", [])
            nvme_disks = [d for d in devices if d.get("is_nvme")]
            sata_disks = [d for d in devices if not d.get("is_nvme") and d.get("type") == "disk"]

            if "nvme" in last_user_msg or "ssd" in last_user_msg:
                if nvme_disks:
                    primary = nvme_disks[0]
                    model = primary.get("model", "NVMe SSD")
                    size = primary.get("size_human", "")
                    sec_info = ""
                    if sata_disks:
                        sec_info = f" You also have a secondary {sata_disks[0].get('size_human')} SATA drive ({sata_disks[0].get('name')})."
                    return ProviderResponse(
                        content=f"Yes, your primary storage drive `{primary.get('name')}` ({size}) is a high-speed NVMe PCIe SSD ({model}).{sec_info}"
                    )
                else:
                    return ProviderResponse(content="No NVMe storage devices were detected on this machine.")

            return ProviderResponse(
                content=f"Found {len(devices)} storage device(s): " + ", ".join(f"{d.get('name')} ({d.get('size_human')})" for d in devices)
            )

        elif tool_name == "get_cpu_info":
            model = data.get("model_name", "Unknown CPU")
            cores = data.get("physical_cores", 0)
            threads = data.get("logical_threads", 0)
            max_mhz = data.get("max_mhz")
            freq_str = f" running up to {max_mhz/1000.0:.1f} GHz" if max_mhz else ""
            virt = data.get("virtualization", "Enabled")
            return ProviderResponse(
                content=f"You have an {model} with {cores} physical cores and {threads} logical threads{freq_str}. "
                        f"Hardware virtualization ({virt}) is supported."
            )

        elif tool_name == "get_gpu_and_pci_info":
            gpus = data.get("gpus", [])
            if gpus:
                gpu_names = [f"{g.get('vendor')} {g.get('device_name')}" for g in gpus]
                return ProviderResponse(
                    content=f"Your laptop has {len(gpus)} graphics controller(s):\n" +
                            "\n".join(f"- {name}" for name in gpu_names)
                )
            return ProviderResponse(content="No dedicated or integrated GPU detected on the PCI bus.")

        elif tool_name == "get_system_overview":
            vendor = data.get("hardware_vendor", "Generic")
            model = data.get("hardware_model", "Laptop")
            os_name = data.get("os_name", "Linux")
            os_ver = data.get("os_version", "")
            kernel = data.get("kernel_release", "")
            bat_pct = data.get("battery_percentage")
            bat_stat = data.get("battery_status", "")
            bat_str = f" Battery: {bat_pct}% ({bat_stat})." if bat_pct is not None else ""

            return ProviderResponse(
                content=f"System: {vendor} {model} running {os_name} {os_ver} (Kernel {kernel}).{bat_str}"
            )

        return ProviderResponse(content="I don't know based on the available diagnostic data.")

