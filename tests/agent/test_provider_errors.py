import httpx
import pytest

from ee_arch_copilot.agent.providers import CompatibleAgentProvider
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.main import create_app
from ee_arch_copilot.rag.errors import ProviderError

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "code",
    ["credit_balance_exhausted", "insufficient_quota", "rate_limit_exceeded", "model_not_found"],
)
async def test_safe_upstream_error_reaches_agent_metadata(
    agent_settings: Settings, code: str
) -> None:
    settings = agent_settings.model_copy(
        update={
            "agent_provider": "openai_compatible",
            "agent_model": "gpt-6.1-terra",
            "agent_api_mode": "responses",
        }
    )
    provider = CompatibleAgentProvider(
        settings,
        httpx.MockTransport(
            lambda request: httpx.Response(
                429,
                json={
                    "error": {
                        "code": code,
                        "type": "insufficient_quota",
                        "message": "private provider message and credentials",
                    },
                },
            )
        ),
    )
    app = create_app(settings, agent_provider=provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/agent/analyze", json={"question": "Inspect"})
    assert response.status_code == 502
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["execution_metadata"]["provider_error_code"] == code
    assert data["execution_metadata"]["provider_http_status"] == 429
    assert not data["tool_executions"]
    assert "private provider message" not in response.text
    if code in {"credit_balance_exhausted", "insufficient_quota"}:
        assert any("billing and credits" in question for question in data["unresolved_questions"])


@pytest.mark.parametrize(
    "body",
    [
        b"not JSON with sensitive text",
        b'{"error":{"code":"private-secret-code","message":"sensitive text"}}',
        b'{"error":[]}',
        b"[]",
    ],
)
async def test_unknown_provider_errors_do_not_leak(agent_settings: Settings, body: bytes) -> None:
    settings = agent_settings.model_copy(
        update={
            "agent_provider": "openai_compatible",
            "agent_model": "test",
            "agent_api_mode": "responses",
        }
    )
    provider = CompatibleAgentProvider(
        settings, httpx.MockTransport(lambda request: httpx.Response(401, content=body))
    )
    with pytest.raises(ProviderError) as raised:
        await provider.complete([], [])
    assert raised.value.http_status == 401 and raised.value.code is None
    assert "sensitive" not in str(raised.value) and "private-secret-code" not in str(raised.value)
