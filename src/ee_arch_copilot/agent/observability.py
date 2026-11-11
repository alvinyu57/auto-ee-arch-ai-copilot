"""Metadata-only local traces. No prompts, arguments, tool payloads, or provider errors."""

import logging
from time import monotonic
from uuid import uuid4

from ee_arch_copilot.agent.models import ExecutionMetadata, TraceEvent
from ee_arch_copilot.agent.providers import TokenUsage
from ee_arch_copilot.core.settings import Settings

logger = logging.getLogger("ee_arch_copilot.agent.trace")


class AgentTrace:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.request_id, self.trace_id = uuid4().hex, uuid4().hex
        self.started = monotonic()
        self.events: list[TraceEvent] = []
        self.usages: list[TokenUsage | None] = []

    def record(
        self,
        event: str,
        iteration: int,
        duration_ms: float,
        status: str,
        tool_name: str | None = None,
        call_id: str | None = None,
        usage: TokenUsage | None = None,
    ) -> None:
        trace = TraceEvent.model_validate(
            {
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "event": event,
                "iteration": iteration,
                "duration_ms": duration_ms,
                "status": status,
                "tool_name": tool_name,
                "tool_call_id": call_id,
                "input_tokens": usage.input_tokens if usage else None,
                "output_tokens": usage.output_tokens if usage else None,
            }
        )
        if event == "llm":
            self.usages.append(usage)
        if self.settings.agent_enable_tracing:
            self.events.append(trace)
            logger.info("agent_event", extra={"agent_trace": trace.model_dump(mode="json")})

    def metadata(
        self, model: str, iterations: int, calls: int, reason: str, include_trace: bool
    ) -> ExecutionMetadata:
        complete = bool(self.usages) and all(usage is not None for usage in self.usages)
        inputs = sum(usage.input_tokens for usage in self.usages if usage) if complete else None
        outputs = sum(usage.output_tokens for usage in self.usages if usage) if complete else None
        cost = None
        if (
            inputs is not None
            and outputs is not None
            and self.settings.agent_input_usd_per_million_tokens is not None
            and self.settings.agent_output_usd_per_million_tokens is not None
        ):
            cost = (
                inputs * self.settings.agent_input_usd_per_million_tokens
                + outputs * self.settings.agent_output_usd_per_million_tokens
            ) / 1_000_000
        return ExecutionMetadata(
            trace_id=self.trace_id,
            provider_model=model,
            iterations=iterations,
            tool_calls=calls,
            duration_ms=(monotonic() - self.started) * 1000,
            input_tokens=inputs,
            output_tokens=outputs,
            usage_complete=complete,
            estimated_cost_usd=cost,
            stop_reason=reason,
            trace=list(self.events) if include_trace else [],
        )
