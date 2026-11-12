import asyncio
import json

import httpx
import pytest
from pydantic import JsonValue

from ee_arch_copilot.agent.models import AgentResponse, AnalyzeRequest
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.providers import CompatibleAgentProvider, ProviderReply
from ee_arch_copilot.agent.testing import Messages, ScriptedProvider, referenced_final, tool_reply
from ee_arch_copilot.agent.tools.adapters import EngineeringTools, TopologyArguments
from ee_arch_copilot.agent.tools.registry import ToolRegistry, json_bytes
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.main import create_app
from ee_arch_copilot.rag.errors import ConfigurationError, ProviderError
from ee_arch_copilot.rag.service import KnowledgeService
from tests.conftest import Payload

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "endpoint",
    [
        "file:///etc/passwd",
        "https://user:password@example.test/v1",
        "http://",
    ],
)
def test_invalid_configured_provider_urls(agent_settings: Settings, endpoint: str) -> None:
    settings = agent_settings.model_copy(
        update={
            "agent_provider": "openai_compatible",
            "agent_model": "test",
            "llm_base_url": endpoint,
        }
    )
    with pytest.raises(ConfigurationError):
        CompatibleAgentProvider(settings)


async def test_native_adapter_api_workflow_with_mock_http(
    payload: Payload,
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    replies = [
        tool_reply("search_requirements", {"query": "REQ-ETH-001"}, "s"),
        tool_reply(
            "find_physical_path", {"source_device_id": "a", "destination_device_id": "b"}, "p"
        ),
        tool_reply("validate_architecture", {}, "v"),
    ]
    calls = 0

    def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        messages = json.loads(request.content)["messages"]
        reply = replies[calls] if calls < len(replies) else referenced_final(messages)
        calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls" if reply.tool_calls else "stop",
                        "message": reply.message(),
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    settings = agent_settings.model_copy(
        update={"agent_provider": "openai_compatible", "agent_model": "mock-http"}
    )
    provider = CompatibleAgentProvider(settings, httpx.MockTransport(endpoint))
    app = create_app(settings, agent_knowledge, provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/v1/agent/analyze", json={"question": "Combined", "architecture": payload}
        )
        assert result.status_code == 200
        response = AgentResponse.model_validate(result.json())
    assert calls == 4 and response.status == "COMPLETED"
    assert response.citations and any(item.validation for item in response.findings)
    assert response.execution_metadata.input_tokens == 40


@pytest.mark.parametrize("timeout", [False, True])
async def test_provider_failure_http_status(
    agent_settings: Settings, timeout: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exercise provider failures independently of the time spent building tool schemas.
    monkeypatch.setattr("ee_arch_copilot.agent.observability.monotonic", lambda: 0.0)
    monkeypatch.setattr("ee_arch_copilot.agent.orchestrator.monotonic", lambda: 0.0)

    class FailedProvider:
        model = "failed-test"

        async def complete(
            self, messages: Messages, tools: list[dict[str, JsonValue]]
        ) -> ProviderReply:
            if timeout:
                await asyncio.sleep(1)
            raise RuntimeError("private provider error")

    settings = agent_settings.model_copy(update={"agent_timeout_seconds": 0.02})
    app = create_app(settings, agent_provider=FailedProvider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/api/v1/agent/analyze", json={"question": "Inspect"})
        assert result.status_code == (504 if timeout else 502)
        assert result.json()["status"] == "FAILED"
        assert result.json()["execution_metadata"]["stop_reason"] == (
            "provider_timeout" if timeout else "provider_error"
        )
        assert "private provider error" not in result.text


@pytest.mark.parametrize("phase", ["setup", "before_tool", "after_evidence"])
async def test_execution_timeout_http_status(
    agent_settings: Settings, phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 0.0
    monkeypatch.setattr("ee_arch_copilot.agent.observability.monotonic", lambda: now)
    monkeypatch.setattr("ee_arch_copilot.agent.orchestrator.monotonic", lambda: now)

    def expire(messages: Messages) -> ProviderReply:
        nonlocal now
        now = agent_settings.agent_timeout_seconds
        return tool_reply("get_architecture_topology", {}, "expired")

    if phase == "setup":
        specifications = ToolRegistry.specifications

        def expired_specifications(self: ToolRegistry) -> list[dict[str, JsonValue]]:
            nonlocal now
            result = specifications(self)
            now = agent_settings.agent_timeout_seconds
            return result

        monkeypatch.setattr(ToolRegistry, "specifications", expired_specifications)

    has_evidence = phase == "after_evidence"
    provider = ScriptedProvider(
        [tool_reply("get_architecture_topology", {}, "topology"), expire]
        if has_evidence
        else [expire]
    )
    app = create_app(agent_settings, agent_provider=provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/v1/agent/analyze",
            json={"question": "Inspect", "architecture": {"id": "empty", "name": "Empty"}},
        )
    assert result.status_code == (200 if has_evidence else 504)
    response = AgentResponse.model_validate(result.json())
    assert response.status == ("PARTIAL" if has_evidence else "FAILED")
    assert response.execution_metadata.stop_reason == "execution_timeout"
    expected_iterations = {"setup": 0, "before_tool": 1, "after_evidence": 2}[phase]
    assert response.execution_metadata.iterations == expected_iterations
    assert len(provider.histories) == response.execution_metadata.iterations
    assert response.execution_metadata.tool_calls == int(has_evidence)
    assert len(response.tool_executions) == int(has_evidence)
    assert bool(response.evidence) == has_evidence
    assert app.state.knowledge_service is None


async def test_complete_wire_envelope_size_is_enforced(
    agent_settings: Settings,
    agent_tools: EngineeringTools,
    agent_knowledge: KnowledgeService,
) -> None:
    raw = agent_tools.topology(TopologyArguments())
    settings = agent_settings.model_copy(
        update={
            "agent_max_tool_result_bytes": len(json_bytes(raw.model_dump(mode="json"))) + 1,
        }
    )
    provider = ScriptedProvider(
        [tool_reply("get_architecture_topology", {}, "t"), referenced_final]
    )
    result = await AgentOrchestrator(settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Inspect", architecture=agent_tools.context.architecture)
    )
    assert result.status == "PARTIAL" and not result.evidence
    assert result.tool_executions[0].error_code == "tool_result_size_limit"


async def test_topology_truncation_is_disclosed(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    provider = ScriptedProvider(
        [tool_reply("get_architecture_topology", {"max_nodes": 1}, "t"), referenced_final]
    )
    result = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Inspect", architecture=sample)
    )
    assert (
        result.status == "PARTIAL" and result.execution_metadata.stop_reason == "truncated_output"
    )
    assert any("truncated" in question for question in result.unresolved_questions)


@pytest.mark.parametrize("dependency", ["embedding", "vector"])
async def test_real_retrieval_dependency_failure_is_controlled(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    dependency: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed(*args: object, **kwargs: object) -> None:
        raise ProviderError("sensitive provider details")

    if dependency == "embedding":
        monkeypatch.setattr(agent_knowledge.embeddings, "embed_query", failed)
    else:
        monkeypatch.setattr(agent_knowledge.semantic, "search", failed)
    provider = ScriptedProvider(
        [tool_reply("search_requirements", {"query": "ADAS"}, "s"), referenced_final]
    )
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Find")
    )
    assert response.status == "PARTIAL" and response.tool_executions[0].error_code == "tool_failed"
    assert not response.evidence and "sensitive provider details" not in response.model_dump_json()


async def test_source_recheck_failure_is_explicit(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_recheck(self: EngineeringTools) -> bool:
        raise OSError("sensitive storage path")

    monkeypatch.setattr(EngineeringTools, "evidence_current", failed_recheck)
    provider = ScriptedProvider(
        [tool_reply("search_requirements", {"query": "ADAS"}, "s"), referenced_final]
    )
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Find")
    )
    assert response.status == "PARTIAL" and not response.citations
    assert response.execution_metadata.stop_reason == "source_freshness_unverified"
    assert "sensitive storage path" not in response.model_dump_json()
