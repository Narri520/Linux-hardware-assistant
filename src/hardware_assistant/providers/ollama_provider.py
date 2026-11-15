"""Ollama local model inference provider with native tool-calling support."""

import json
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

from hardware_assistant.providers.base import LLMProvider, ProviderResponse, ToolCall


class OllamaProvider(LLMProvider):
    """Inference provider connecting to a locally running Ollama instance (100% offline)."""

    def __init__(
        self,
        model: str = "llama3.2:latest",
        base_url: str = "http://localhost:11434",
        timeout_sec: float = 60.0
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def is_available(self) -> bool:
        """Checks if the local Ollama server is running and reachable."""
        if requests is None:
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        """Sends chat request to Ollama `/api/chat` with tool definitions."""
        if requests is None:
            return ProviderResponse(
                content="Error: 'requests' package not installed. Install with `pip install requests` to use Ollama."
            )
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {})

            # Extract text response
            content = message.get("content")

            # Extract tool calls if any
            tool_calls: List[ToolCall] = []
            raw_tool_calls = message.get("tool_calls", [])
            for idx, tc in enumerate(raw_tool_calls):
                func = tc.get("function", {})
                name = func.get("name")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if name:
                    tool_calls.append(ToolCall(id=f"call_{idx}", name=name, arguments=args))

            return ProviderResponse(content=content, tool_calls=tool_calls)

        except requests.exceptions.ConnectionError:
            return ProviderResponse(
                content="Error: Could not connect to local Ollama server at http://localhost:11434. "
                        "Please ensure Ollama is installed and running (`ollama serve`), "
                        "or run with `--provider mock` for offline simulation."
            )
        except Exception as exc:
            return ProviderResponse(content=f"Ollama inference error: {str(exc)}")

