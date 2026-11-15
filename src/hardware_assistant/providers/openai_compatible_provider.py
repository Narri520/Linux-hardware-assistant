"""Generic OpenAI-compatible inference provider (vLLM, llama.cpp, LiteLLM, Groq, OpenAI)."""

import json
import os
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

from hardware_assistant.providers.base import LLMProvider, ProviderResponse, ToolCall


class OpenAICompatibleProvider(LLMProvider):
    """Inference provider for any OpenAI-compatible API endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: Optional[str] = None,
        model: str = "default",
        timeout_sec: float = 60.0
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "dummy-key")
        self.model = model
        self.timeout_sec = timeout_sec

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        """Sends chat completion request to standard `/chat/completions`."""
        if requests is None:
            return ProviderResponse(
                content="Error: 'requests' package not installed. Install with `pip install requests` to use OpenAI-compatible provider."
            )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            content = message.get("content")
            tool_calls: List[ToolCall] = []

            raw_calls = message.get("tool_calls", [])
            for idx, call in enumerate(raw_calls):
                func = call.get("function", {})
                name = func.get("name")
                raw_args = func.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = raw_args
                call_id = call.get("id", f"call_{idx}")
                if name:
                    tool_calls.append(ToolCall(id=call_id, name=name, arguments=args))

            return ProviderResponse(content=content, tool_calls=tool_calls)

        except Exception as exc:
            return ProviderResponse(content=f"OpenAI-compatible inference error: {str(exc)}")

