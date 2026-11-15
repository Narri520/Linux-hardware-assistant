"""Base interface for LLM inference providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from hardware_assistant.models import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a tool call requested by an LLM."""
    id: str = Field(default="call_0")
    name: str = Field(..., description="Function name to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Parsed arguments")


class ProviderResponse(BaseModel):
    """Normalized response from an LLM inference provider."""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)


class LLMProvider(ABC):
    """Abstract interface for local or remote model backends."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        """Generates a completion or tool call request given conversation history."""
        pass

