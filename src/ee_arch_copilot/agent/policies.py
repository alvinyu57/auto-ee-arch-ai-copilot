"""Execution bounds are enforced by Python, independently of prompt instructions."""

from dataclasses import dataclass

from ee_arch_copilot.agent.models import AgentOptions
from ee_arch_copilot.core.settings import Settings


@dataclass(frozen=True)
class AgentPolicy:
    max_iterations: int
    max_tool_calls: int
    timeout_seconds: float
    tool_timeout_seconds: float
    max_tool_result_bytes: int
    max_argument_bytes: int
    max_context_bytes: int

    @classmethod
    def build(cls, settings: Settings, options: AgentOptions) -> "AgentPolicy":
        iterations = options.max_iterations or settings.agent_max_iterations
        calls = options.max_tool_calls or settings.agent_max_tool_calls
        if iterations > settings.agent_max_iterations or calls > settings.agent_max_tool_calls:
            raise ValueError("Request options may only reduce server execution limits")
        return cls(
            iterations,
            calls,
            settings.agent_timeout_seconds,
            settings.agent_tool_timeout_seconds,
            settings.agent_max_tool_result_bytes,
            settings.agent_max_argument_bytes,
            settings.agent_max_context_bytes,
        )
