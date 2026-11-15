"""Multi-turn conversation engine orchestrating LLM tool calling and grounding."""

import json
from typing import List, Dict, Any, Optional, Callable
from hardware_assistant.agent.prompts import SYSTEM_PROMPT
from hardware_assistant.agent.tools import HardwareToolRegistry, TOOL_DEFINITIONS
from hardware_assistant.models import ToolExecutionResult
from hardware_assistant.providers.base import LLMProvider, ToolCall


class HardwareAgentEngine:
    """Manages the agentic loop, multi-turn conversation memory, and tool execution."""

    def __init__(
        self,
        registry: HardwareToolRegistry,
        provider: LLMProvider,
        max_tool_iterations: int = 5
    ):
        self.registry = registry
        self.provider = provider
        self.max_tool_iterations = max_tool_iterations
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset(self) -> None:
        """Resets conversation history back to initial system prompt."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def ask(
        self,
        query: str,
        on_tool_start: Optional[Callable[[str], None]] = None,
        on_tool_finish: Optional[Callable[[str, ToolExecutionResult], None]] = None,
    ) -> str:
        """Processes a natural language query, calling diagnostic tools as needed.
        
        Args:
            query: User's question (e.g. "Can I add more RAM?").
            on_tool_start: Optional callback hook when a tool starts execution.
            on_tool_finish: Optional callback hook when a tool completes.
            
        Returns:
            The final grounded response in plain English.
        """
        self.messages.append({"role": "user", "content": query})

        iterations = 0
        while iterations < self.max_tool_iterations:
            iterations += 1

            # Request completion with tool schemas
            response = self.provider.generate(
                messages=self.messages,
                tools=TOOL_DEFINITIONS
            )

            # If the model requested one or more tool calls
            if response.tool_calls:
                # Store the assistant's tool call invocation in history
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)
                            }
                        }
                        for tc in response.tool_calls
                    ]
                }
                self.messages.append(assistant_msg)

                # Execute each tool call through the safe registry
                for tc in response.tool_calls:
                    if on_tool_start:
                        on_tool_start(tc.name)

                    tool_res = self.registry.execute_tool_by_name(tc.name, tc.arguments)

                    if on_tool_finish:
                        on_tool_finish(tc.name, tool_res)

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(tool_res.model_dump())
                    }
                    self.messages.append(tool_msg)

                # Continue loop so model digests the tool output and replies
                continue

            # If the model produced a final answer
            answer = response.content or "I could not retrieve an answer for that query."
            self.messages.append({"role": "assistant", "content": answer})
            return answer

        return "Reached maximum diagnostic iterations without resolving the query."

