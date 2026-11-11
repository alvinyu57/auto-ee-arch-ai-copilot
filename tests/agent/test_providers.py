import json
from typing import Any

import httpx
import pytest
from pydantic import JsonValue, SecretStr

from ee_arch_copilot.agent.providers import CompatibleAgentProvider
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.errors import ConfigurationError, InvalidModelResponse, ProviderError

pytestmark = pytest.mark.anyio


def test_configuration_required(agent_settings: Settings) -> None:
    with pytest.raises(ConfigurationError):
        CompatibleAgentProvider(agent_settings)
    with pytest.raises(ConfigurationError):
        CompatibleAgentProvider(
            agent_settings.model_copy(update={"agent_provider": "openai_compatible"})
        )


async def test_native_protocol_and_credential_reuse(agent_settings: Settings) -> None:
    seen: list[dict[str, Any]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "configured-test-model"
        assert body["store"] is False and body["tool_choice"] == "auto"
        assert body["tools"][0]["type"] == "function"
        seen.append(body)
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "validate_architecture", "arguments": "{}"},
                }
            ],
        }
        if len(seen) == 2:
            assert body["messages"][-1]["tool_call_id"] == "call_123"
            message = {"role": "assistant", "content": '{"summary":"done"}'}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls" if len(seen) == 1 else "stop",
                        "message": message,
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    settings = agent_settings.model_copy(
        update={
            "agent_provider": "openai_compatible",
            "llm_model": "configured-test-model",
            "llm_api_key": SecretStr("test-key"),
        }
    )
    provider = CompatibleAgentProvider(settings, httpx.MockTransport(endpoint))
    definitions: list[dict[str, JsonValue]] = [
        {"type": "function", "function": {"name": "validate_architecture"}}
    ]
    reply = await provider.complete([{"role": "user", "content": "Check"}], definitions)
    assert reply.tool_calls[0].id == "call_123"
    assert reply.usage and reply.usage.input_tokens == 10
    second = await provider.complete(
        [
            reply.message(),
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "content": "{}",
            },
        ],
        definitions,
    )
    assert second.content == '{"summary":"done"}' and not second.tool_calls


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
        {"choices": [{"finish_reason": "stop", "message": []}]},
        {"choices": [{"finish_reason": "stop", "message": {"role": "user", "content": "{}"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": None}}]},
        {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {"role": "assistant", "tool_calls": [{"id": "bad"}]},
                }
            ]
        },
        {
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}
            ],
            "usage": {},
        },
        {
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}
            ],
            "usage": "bad",
        },
    ],
)
async def test_malformed_provider_replies(agent_settings: Settings, body: object) -> None:
    settings = agent_settings.model_copy(
        update={"agent_provider": "openai_compatible", "agent_model": "test"}
    )
    provider = CompatibleAgentProvider(
        settings, httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    with pytest.raises(ProviderError):
        await provider.complete([], [])


@pytest.mark.parametrize("failure", ["http", "invalid_json", "oversized", "timeout"])
async def test_http_failures_are_safe(agent_settings: Settings, failure: str) -> None:
    def endpoint(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("private server text")
        if failure == "http":
            return httpx.Response(401, text="private server text")
        return httpx.Response(
            200, content=b"private server text" if failure == "invalid_json" else b"x" * 1025
        )

    settings = agent_settings.model_copy(
        update={
            "agent_provider": "openai_compatible",
            "agent_model": "test",
            "agent_max_provider_response_bytes": 1024,
        }
    )
    provider = CompatibleAgentProvider(settings, httpx.MockTransport(endpoint))
    with pytest.raises(ProviderError) as raised:
        await provider.complete([], [])
    assert "private server text" not in str(raised.value)


async def test_without_usage(agent_settings: Settings) -> None:
    settings = agent_settings.model_copy(
        update={"agent_provider": "openai_compatible", "agent_model": "test"}
    )
    provider = CompatibleAgentProvider(
        settings,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}
                    ],
                },
            )
        ),
    )
    reply = await provider.complete([], [])
    assert reply.usage is None


async def test_script_exhaustion_is_explicit() -> None:
    from ee_arch_copilot.agent.testing import ScriptedProvider

    with pytest.raises(InvalidModelResponse):
        await ScriptedProvider([]).complete([], [])
