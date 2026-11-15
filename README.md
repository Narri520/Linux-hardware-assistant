# Linux Laptop Hardware Q&A Assistant

A grounded, secure, and privacy-preserving conversational assistant designed to run locally on a Linux laptop and answer hardware questions in clear, natural language.

---

## 🎯 Core Flow

```
[User Question]
       │
       ▼
[Agentic Loop] ──(Function Calling)──► [Security Sandbox & Allowlist]
       ▲                                              │
       │                                     (Read-Only Subprocess)
[Pydantic Normalized Data] ◄── [Structured Parsers] ◄─┘
       │                        (/proc, /sys, lscpu, lsblk, dmidecode, lspci)
       ▼
[Grounded Answer] (Plain English, Zero Hallucinations)
```

1. **Ask**: The user types a natural-language question (e.g., *"Can I add more RAM, and how much?"* or *"Is my SSD NVMe?"*).
2. **Gather**: The assistant determines which diagnostic tool it requires and invokes it via strict read-only execution vectors (`lscpu -J`, `lsblk -J -b`, `free -b`, `dmidecode -t memory`, `lspci -vmm`, `/sys`, `/proc`).
3. **Normalize**: Raw terminal strings and pseudo-filesystem tables are converted into strongly-typed Pydantic schemas, stripping redundant data to conserve context tokens.
4. **Answer**: The model digests the structured payload and turns it into a clear, accurate response without guessing specs.

---

## 🛡️ Architecture & Interview Design Highlights

### 1. Safety: Zero Arbitrary Shell Execution
- **Strict Immutable Allowlist**: Tools are defined as hardcoded tuples of fixed binaries and flags in `security.py`.
- **No `shell=True`**: All subprocess calls pass direct argument vectors (`subprocess.run(..., shell=False)`), rendering shell injection (`rm -rf`, `;`, `|`, `&`) impossible.
- **Path Traversal Guard**: Any pseudo-filesystem reads (`/sys`, `/proc`) pass through strict path canonicalization, rejecting directory traversal (`..`) or unauthorized paths.
- **Execution Confinement**: Stripped environment variables (`env={"LC_ALL": "C", ...}`) and process timeouts (3.0s) prevent hung processes.

### 2. Permissions: Least-Privilege & Graceful Degradation
- **The Problem**: Commands like `dmidecode` require elevated privileges (`CAP_SYS_RAWIO` or `root`) to read physical SMBIOS tables (motherboard slot counts, maximum RAM capacity). Running the entire assistant or Python as `root` is a dangerous anti-pattern.
- **The Solution**:
  1. **Least-Privilege Sudoers**: We provide `scripts/install_sudoers.sh`, which configures a minimal, non-interactive rule:
     ```sudoers
     username ALL=(ALL) NOPASSWD: /usr/sbin/dmidecode -t memory, /usr/sbin/dmidecode -t 1\,2\,3
     ```
  2. **Unprivileged Fallback**: If permissions are denied, the system falls back to unprivileged `/proc/meminfo` or `free -b`.
  3. **Explicit Transparency**: If slot details cannot be inspected due to permissions, the assistant never guesses. It reports current RAM and politely explains what privilege is needed to check slots.

### 3. Accuracy: Structured Parsing & Anti-Hallucination
- Raw terminal outputs are not dumped directly into context.
- Dedicated parsers (`src/hardware_assistant/parsers/`) normalize telemetry into Pydantic models:
  - `CPUSpec`: Architecture, physical cores, threads, clock frequencies, virtualization flags.
  - `MemorySpec`: Total/used/available RAM, swap, physical slots count, maximum supported capacity, installed module specs.
  - `StorageDevice`: Disks and partitions, protocol transport (`nvme` vs `sata`), rotational flag (`HDD` vs `SSD`), mountpoints.
  - `PCIDevice`: Discrete and integrated GPU classification.
- **Grounding Rule**: The system prompt strictly binds answers to tool data. If an inspection fails or a spec is missing, the model is instructed to reply: *"I don't know based on available system diagnostics."*

### 4. Portability & Missing Tools
- Commands check binary availability via `shutil.which`.
- Differences across distributions (Debian/Ubuntu, Fedora/RHEL, Arch) are normalized into unified schemas.
- Includes a **Mock Linux Runner** (`--mock`) loaded with realistic Lenovo ThinkPad / Ubuntu 22.04 hardware dumps, allowing automated testing and development on any operating system (Linux, macOS, Windows).

### 5. Privacy: 100% Offline Local Model
- Default integration with **Ollama** (`llama3.2`, `qwen2.5-coder`, `mistral`) running locally at `http://localhost:11434`.
- Zero hardware telemetry ever leaves the laptop.
- Also compatible with local OpenAI-compatible runtimes (vLLM, llama.cpp server, LiteLLM) and includes a deterministic mock provider for CI testing.

---

## 📂 Project Structure

```
├── pyproject.toml              # Project metadata & entrypoints
├── requirements.txt            # Python dependencies (pydantic, rich, requests, pytest)
├── README.md                   # System documentation & security design
├── scripts/
│   ├── install_sudoers.sh      # Least-privilege sudoers installer for dmidecode
│   └── run_demo.py             # Self-contained automated demonstration
├── src/
│   └── hardware_assistant/
│       ├── cli.py              # Rich terminal chat interface & interactive commands
│       ├── models.py           # Pydantic schemas (CPUSpec, MemorySpec, StorageDevice, etc.)
│       ├── security.py         # Command allowlist, subprocess sandbox & path validator
│       ├── collectors/         # System runners (NativeLinuxRunner, MockLinuxRunner)
│       ├── parsers/            # Output parsers (cpu, memory, storage, pci, system)
│       ├── agent/              # Function calling loop, prompts & tool registry
│       ├── providers/          # LLM backends (Ollama, OpenAI-compatible, MockLLM)
│       └── mock_fixtures/      # Real-world Linux hardware dumps (lscpu, lsblk, dmidecode, etc.)
└── tests/
    ├── test_security.py        # Sandboxing, injection rejection, and traversal tests
    ├── test_parsers.py         # Parsing validation for all hardware components
    └── test_agent.py           # Multi-turn conversation and grounding verification
```

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/your-org/hardware-assistant.git
cd hardware-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Optional: Configure Safe Least-Privilege Sudoers (Linux)

To inspect physical motherboard RAM slots and maximum supported memory without running the assistant as root:

```bash
sudo ./scripts/install_sudoers.sh
```

### 3. Run the Interactive Assistant

#### With Local Offline Ollama:
```bash
ollama run llama3.2
hw-assistant --provider ollama --model llama3.2
```

#### With the Built-in Mock Hardware / Test Mode (Instant Demo):
```bash
hw-assistant --mock --provider mock
```

#### Single-Shot Query Mode (CLI scripting):
```bash
hw-assistant --mock --provider mock --ask "Can I add more RAM, and how much?"
```

---

## 💬 Example Conversation Flow

```text
hardware> Can I add more RAM, and how much?
 ⚙ Calling diagnostic tool: get_memory_info()...
Assistant: You have 16 GB in 1 of 2 slots. The board supports up to 64.0 GB,
           so you can add a stick of up to 32 GB in the 1 empty slot.

hardware> and what about the GPU?
 ⚙ Calling diagnostic tool: get_gpu_and_pci_info()...
Assistant: Your laptop has 2 graphics controller(s):
           - Intel Corporation Alder Lake-P Integrated Graphics Controller
           - NVIDIA Corporation GA107M [GeForce RTX 3050 Mobile]

hardware> Is my SSD NVMe?
 ⚙ Calling diagnostic tool: get_storage_info()...
Assistant: Yes, your primary storage drive `nvme0n1` (1.0 TB) is a high-speed
           NVMe PCIe SSD (SAMSUNG MZVL21T0HCLR-00B00). You also have a secondary
           2.0 TB SATA drive (sda).
```

---

## 🧪 Running Automated Tests

```bash
pytest -v
```

All security checks (rejection of malicious inputs, path traversal detection, command allowlist isolation), parser validations, and multi-turn agent interactions pass completely offline.

