import asyncio
import json

import pytest
from pydantic import JsonValue

from ee_arch_copilot.agent.models import AgentOptions, AnalyzeRequest
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.providers import ProviderReply
from ee_arch_copilot.agent.testing import (
    Messages,
    ScriptedProvider,
    ScriptStep,
    referenced_final,
    tool_reply,
)
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.rag.errors import ProviderError
from ee_arch_copilot.rag.models import DocumentInput
from ee_arch_copilot.rag.service import KnowledgeService
from ee_arch_copilot.services.validator import ArchitectureValidator
from tests.conftest import Payload

pytestmark = pytest.mark.anyio


async def test_combined_workflow(
    payload: Payload,
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    provider = ScriptedProvider(
        [
            tool_reply("search_requirements", {"query": "REQ-ETH-001"}, "search"),
            tool_reply("get_architecture_topology", {}, "topology"),
            tool_reply(
                "find_physical_path",
                {"source_device_id": "a", "destination_device_id": "b"},
                "path",
            ),
            tool_reply("validate_architecture", {}, "validate"),
            referenced_final,
        ]
    )
    architecture = Architecture.model_validate(payload)
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(
            question="Combined analysis",
            architecture=architecture,
            options=AgentOptions(include_trace=True),
        )
    )
    assert response.status == "COMPLETED"
    assert response.execution_metadata.iterations == 5
    assert len(response.tool_executions) == 4
    assert response.citations[0].requirement_id == "REQ-ETH-001"
    assert {record.kind for record in response.evidence} == {
        "requirement",
        "topology",
        "physical_path",
        "validation",
    }
    assert [item.validation for item in response.findings if item.validation] == (
        ArchitectureValidator().validate(architecture).findings
    )
    assert response.execution_metadata.trace[-1].status == "COMPLETED"
    initial = json.dumps(provider.histories[0])
    assert "eth0" not in initial and "Synthetic stream" not in initial
    results = [m for m in provider.histories[-1] if m["role"] == "tool"]
    assert [message["tool_call_id"] for message in results] == [
        "search",
        "topology",
        "path",
        "validate",
    ]
    assert all(
        item.result_bytes <= agent_settings.agent_max_tool_result_bytes
        for item in response.tool_executions
    )


@pytest.mark.parametrize(
    ("variant", "status", "agent_status"),
    [
        ("complete", "PASS", "COMPLETED"),
        ("overload", "FAIL", "COMPLETED"),
        ("missing", "NOT_EVALUATED", "INSUFFICIENT_EVIDENCE"),
    ],
)
async def test_engineering_status_preservation(
    payload: Payload,
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    variant: str,
    status: str,
    agent_status: str,
) -> None:
    if variant == "overload":
        payload["services"][0]["bandwidth_requirement_mbps"] = 105
    elif variant == "missing":
        payload["services"][0]["traffic_routes"] = []
    provider = ScriptedProvider([tool_reply("validate_architecture", {}, "v"), referenced_final])
    architecture = Architecture.model_validate(payload)
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Check bandwidth", architecture=architecture)
    )
    assert response.status == agent_status
    bandwidth = next(
        item.validation
        for item in response.findings
        if item.validation and item.validation.requirement_id == "REQ-BW"
    )
    assert bandwidth is not None and bandwidth.status == status
    assert "ab" in bandwidth.affected_components
    assert bandwidth == ArchitectureValidator().validate(architecture).findings[-1]
    if variant == "missing":
        assert any("Unevaluated check" in text for text in response.unresolved_questions)
    if variant == "overload":
        assert bandwidth.evidence["routed_demand_mbps"] == {"a->b": "105.0"}


async def test_multiple_calls_and_recoverable_errors(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    first = ProviderReply(
        tool_calls=[
            *tool_reply("execute_shell", {"command": "id"}, "bad").tool_calls,
            *tool_reply("validate_architecture", {}, "good").tool_calls,
        ]
    )
    provider = ScriptedProvider([first, referenced_final])
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Check", architecture=sample)
    )
    assert response.status == "PARTIAL"
    assert response.tool_executions[0].error_code == "unknown_tool"
    assert response.tool_executions[1].status == "SUCCEEDED"
    assert any(item.validation for item in response.findings)
    results = [m for m in provider.histories[1] if m["role"] == "tool"]
    assert [result["tool_call_id"] for result in results] == ["bad", "good"]


@pytest.mark.parametrize("budget", [1, 2])
async def test_tool_budget_stops_mid_batch(
    budget: int,
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    burst = ProviderReply(
        tool_calls=[
            call
            for index in range(4)
            for call in tool_reply("get_architecture_topology", {}, f"call_{index}").tool_calls
        ]
    )
    provider = ScriptedProvider([burst, referenced_final])
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(
            question="Check", architecture=sample, options=AgentOptions(max_tool_calls=budget)
        )
    )
    assert response.status == "PARTIAL"
    assert len(response.tool_executions) == budget
    assert response.execution_metadata.stop_reason == "tool_call_limit"
    assert len(provider.histories) == 1


async def test_iteration_context_and_result_limits(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    for settings, options, reason in [
        (agent_settings, AgentOptions(max_iterations=1), "iteration_limit"),
        (
            agent_settings.model_copy(update={"agent_max_context_bytes": 4096}),
            AgentOptions(),
            "context_size_limit",
        ),
    ]:
        provider = ScriptedProvider([tool_reply("get_architecture_topology", {}, "t")])
        response = await AgentOrchestrator(settings, provider, lambda: agent_knowledge).analyze(
            AnalyzeRequest(question="Check", architecture=sample, options=options)
        )
        assert response.status in {"PARTIAL", "FAILED"}
        assert response.execution_metadata.stop_reason == reason
    provider = ScriptedProvider([tool_reply("validate_architecture", {}, "v"), referenced_final])
    response = await AgentOrchestrator(
        agent_settings.model_copy(update={"agent_max_tool_result_bytes": 512}),
        provider,
        lambda: agent_knowledge,
    ).analyze(AnalyzeRequest(question="Check", architecture=sample))
    assert not response.evidence and response.status == "PARTIAL"
    assert response.tool_executions[0].error_code == "tool_result_size_limit"


async def test_duplicate_call_ids_are_blocked(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    reply = tool_reply("search_requirements", {"query": "ADAS"}, "repeated")
    for script in [[ProviderReply(tool_calls=reply.tool_calls * 2)], [reply, reply]]:
        response = await AgentOrchestrator(
            agent_settings, ScriptedProvider(script), lambda: agent_knowledge
        ).analyze(AnalyzeRequest(question="Find"))
        assert response.execution_metadata.stop_reason == "invalid_tool_call_ids"
        assert len(response.tool_executions) <= 1


async def test_unavailable_architecture_and_empty_search(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    for name, args, status in [
        ("validate_architecture", {}, "PARTIAL"),
        ("search_requirements", {"query": "REQ-UNKNOWN-999"}, "INSUFFICIENT_EVIDENCE"),
    ]:
        provider = ScriptedProvider([tool_reply(name, args, "call"), referenced_final])
        response = await AgentOrchestrator(
            agent_settings, provider, lambda: agent_knowledge
        ).analyze(AnalyzeRequest(question="Check"))
        assert response.status == status and not response.evidence
        assert not response.citations and response.unresolved_questions


async def test_final_repair_and_fail_closed(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    cases: list[tuple[ScriptStep, str]] = [
        (referenced_final, "COMPLETED"),
        (ProviderReply(content="{}"), "PARTIAL"),
    ]
    for second, expected in cases:
        provider = ScriptedProvider(
            [
                tool_reply("search_requirements", {"query": "REQ-ETH-001"}, "s"),
                ProviderReply(content="not JSON"),
                second,
            ]
        )
        response = await AgentOrchestrator(
            agent_settings, provider, lambda: agent_knowledge
        ).analyze(AnalyzeRequest(question="Find"))
        assert response.status == expected and len(provider.histories) == 3
        assert response.citations
        assert "not JSON" not in response.model_dump_json()


async def test_provider_failure_retains_independent_results(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    def fail(messages: Messages) -> ProviderReply:
        raise ProviderError("API key secret")

    cases: list[tuple[list[ScriptStep], str]] = [
        ([fail], "FAILED"),
        ([tool_reply("search_requirements", {"query": "ADAS"}, "s"), fail], "PARTIAL"),
    ]
    for script, expected in cases:
        response = await AgentOrchestrator(
            agent_settings, ScriptedProvider(script), lambda: agent_knowledge
        ).analyze(AnalyzeRequest(question="Find"))
        assert (
            response.status == expected
            and response.execution_metadata.stop_reason == "provider_error"
        )
        assert "API key secret" not in response.model_dump_json()


async def test_provider_timeout_and_cancellation(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    class SlowProvider:
        model = "slow-test"
        cancelled = False

        async def complete(
            self, messages: Messages, tools: list[dict[str, JsonValue]]
        ) -> ProviderReply:
            try:
                await asyncio.sleep(10)
            finally:
                self.cancelled = True
            return ProviderReply(content="{}")

    slow = SlowProvider()
    response = await AgentOrchestrator(
        agent_settings.model_copy(update={"agent_timeout_seconds": 0.02}),
        slow,
        lambda: agent_knowledge,
    ).analyze(AnalyzeRequest(question="Check"))
    assert response.status == "FAILED" and slow.cancelled
    task = asyncio.create_task(
        AgentOrchestrator(agent_settings, SlowProvider(), lambda: agent_knowledge).analyze(
            AnalyzeRequest(question="Check")
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_source_freshness(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    def replace_source(messages: Messages) -> ProviderReply:
        agent_knowledge.ingest(
            DocumentInput(
                document_id="ethernet",
                filename="ethernet.md",
                source_type="text",
                version="2",
                content="REQ-ETH-001: Revised source.",
            )
        )
        return referenced_final(messages)

    provider = ScriptedProvider(
        [
            tool_reply("search_requirements", {"query": "REQ-ETH-001"}, "s"),
            tool_reply("validate_architecture", {}, "v"),
            replace_source,
        ]
    )
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Combined", architecture=sample)
    )
    assert response.status == "PARTIAL" and not response.citations
    assert response.execution_metadata.stop_reason == "stale_evidence"
    assert any(item.validation for item in response.findings)
    assert all(record.kind != "requirement" for record in response.evidence)
