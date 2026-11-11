import json
from collections.abc import AsyncIterator

import httpx
import pytest

from ee_arch_copilot.agent.models import AgentResponse
from ee_arch_copilot.agent.testing import ScriptedProvider, referenced_final, tool_reply
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.main import create_app
from ee_arch_copilot.rag.service import KnowledgeService

pytestmark = pytest.mark.anyio


async def test_endpoint_and_openapi(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    provider = ScriptedProvider(
        [
            tool_reply("search_requirements", {"query": "REQ-ETH-001"}, "s"),
            tool_reply("validate_architecture", {}, "v"),
            referenced_final,
        ]
    )
    app = create_app(agent_settings, agent_knowledge, provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/v1/agent/analyze",
            json={
                "question": "Inspect",
                "architecture": sample.model_dump(mode="json"),
                "options": {"include_trace": True},
            },
        )
        assert result.status_code == 200
        response = AgentResponse.model_validate(result.json())
        assert response.citations and response.tool_executions and response.execution_metadata.trace
        schema = (await client.get("/openapi.json")).json()
        operation = schema["paths"]["/api/v1/agent/analyze"]["post"]
        assert "422" in operation["responses"] and "503" in operation["responses"]
        assert (await client.get("/health")).status_code == 200


async def test_unconfigured_provider_is_503(agent_settings: Settings) -> None:
    app = create_app(agent_settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/api/v1/agent/analyze", json={"question": "Inspect"})
        assert result.status_code == 503 and "AGENT_PROVIDER" in result.text
    assert app.state.knowledge_service is None


@pytest.mark.parametrize(
    "body",
    [
        {"question": " "},
        {"question": "x" * 5001},
        {"question": "Inspect", "architecture": {"architecture_id": "sample"}},
        {"question": "Inspect", "architecture": "/etc/passwd"},
        {"question": "Inspect", "options": {"max_iterations": 7}},
        {"question": "Inspect", "options": {"max_tool_calls": 11}},
        {"question": "Inspect", "options": {"max_tool_calls": True}},
        {"question": "Inspect", "document_scope": {"document_id": "private"}},
    ],
)
async def test_api_rejects_invalid_input(agent_settings: Settings, body: object) -> None:
    provider = ScriptedProvider([referenced_final])
    app = create_app(agent_settings, agent_provider=provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/api/v1/agent/analyze", json=body)
        assert result.status_code == 422
    assert not provider.histories


async def test_streamed_body_limit(agent_settings: Settings) -> None:
    app = create_app(agent_settings.model_copy(update={"max_request_bytes": 1000}))

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"question":"'
        yield b"x" * 1001
        yield b'"}'

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/v1/agent/analyze", content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert result.status_code == 413
    assert app.state.knowledge_service is None


async def test_architecture_only_api_does_not_initialize_knowledge(
    agent_settings: Settings,
) -> None:
    app = create_app(
        agent_settings,
        agent_provider=ScriptedProvider(
            [
                tool_reply("get_architecture_topology", {}, "t"),
                referenced_final,
            ]
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/analyze",
            content=json.dumps(
                {
                    "question": "Inspect",
                    "architecture": {"id": "empty", "name": "Empty"},
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200 and response.json()["status"] == "COMPLETED"
    assert app.state.knowledge_service is None
