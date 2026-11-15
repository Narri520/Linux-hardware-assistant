#!/usr/bin/env python3
"""Root interactive chat entrypoint for the Linux Hardware Q&A Assistant."""

import sys
from pathlib import Path

# Automatically add src directory to sys.path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hardware_assistant.cli import main

if __name__ == "__main__":
    main()
