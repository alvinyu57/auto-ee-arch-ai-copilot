import logging

import pytest

from ee_arch_copilot.agent.models import AgentOptions, AnalyzeRequest
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.providers import ProviderReply, TokenUsage
from ee_arch_copilot.agent.testing import Messages, ScriptedProvider, referenced_final, tool_reply
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.service import KnowledgeService

pytestmark = pytest.mark.anyio


async def test_metadata_only_trace_and_explicit_cost(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    usage = TokenUsage(input_tokens=100, output_tokens=20)

    def finish(messages: Messages) -> ProviderReply:
        return referenced_final(messages).model_copy(update={"usage": usage})

    first = tool_reply("search_requirements", {"query": "REQ-ETH-001"}, "s")
    first.usage = usage
    settings = agent_settings.model_copy(
        update={
            "agent_input_usd_per_million_tokens": 2.0,
            "agent_output_usd_per_million_tokens": 4.0,
        }
    )
    with caplog.at_level(logging.INFO, logger="ee_arch_copilot.agent.trace"):
        response = await AgentOrchestrator(
            settings, ScriptedProvider([first, finish]), lambda: agent_knowledge
        ).analyze(
            AnalyzeRequest(
                question="Confidential question", options=AgentOptions(include_trace=True)
            )
        )
    metadata = response.execution_metadata
    assert metadata.usage_complete and metadata.input_tokens == 200 and metadata.output_tokens == 40
    assert metadata.estimated_cost_usd == pytest.approx(0.00056)
    assert len(metadata.trace) == 4
    assert all(
        event.request_id == response.request_id and event.trace_id == metadata.trace_id
        for event in metadata.trace
    )
    logs = str([getattr(record, "agent_trace", None) for record in caplog.records])
    assert "Confidential question" not in logs and "100 Mbps Ethernet" not in logs
    assert metadata.trace_id in logs


async def test_unknown_usage_and_disabled_tracing(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    for enabled, include in [(False, True), (True, False)]:
        provider = ScriptedProvider([referenced_final])
        response = await AgentOrchestrator(
            agent_settings.model_copy(update={"agent_enable_tracing": enabled}),
            provider,
            lambda: agent_knowledge,
        ).analyze(
            AnalyzeRequest(question="No evidence", options=AgentOptions(include_trace=include))
        )
        metadata = response.execution_metadata
        assert not metadata.trace and not metadata.usage_complete
        assert metadata.input_tokens is None and metadata.output_tokens is None
        assert metadata.estimated_cost_usd is None
