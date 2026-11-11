import json
from typing import Any

import httpx
import pytest
from pydantic import JsonValue

from ee_arch_copilot.agent.models import AgentResponse
from ee_arch_copilot.agent.providers import CompatibleAgentProvider
from ee_arch_copilot.agent.testing import referenced_final
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.main import create_app
from ee_arch_copilot.rag.errors import InvalidModelResponse
from ee_arch_copilot.rag.service import KnowledgeService
from tests.conftest import Payload

pytestmark = pytest.mark.anyio


def response_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "agent_provider": "openai_compatible",
            "agent_model": "gpt-6.1-terra",
            "llm_base_url": "https://api.openai.com/v1",
        }
    )


def test_api_mode_selection_and_override(agent_settings: Settings) -> None:
    assert CompatibleAgentProvider(response_settings(agent_settings)).api_mode == "responses"
    local = response_settings(agent_settings).model_copy(
        update={"llm_base_url": "http://localhost:11434/v1"}
    )
    assert CompatibleAgentProvider(local).api_mode == "chat_completions"
    assert (
        CompatibleAgentProvider(local.model_copy(update={"agent_api_mode": "responses"})).api_mode
        == "responses"
    )
    explicit = response_settings(agent_settings).model_copy(
        update={"agent_api_mode": "chat_completions"}
    )
    assert CompatibleAgentProvider(explicit).api_mode == "chat_completions"


async def test_native_items_and_call_ids_replayed_in_order(agent_settings: Settings) -> None:
    output = [
        {
            "type": "reasoning",
            "id": "rs_first",
            "summary": [],
            "encrypted_content": "opaque_reasoning",
        },
        {
            "type": "function_call",
            "id": "fc_item_1",
            "call_id": "call_first",
            "name": "validate_architecture",
            "arguments": "{}",
            "status": "completed",
        },
        {
            "type": "function_call",
            "id": "fc_item_2",
            "call_id": "call_second",
            "name": "get_architecture_topology",
            "arguments": "{}",
            "status": "completed",
        },
    ]
    requests: list[dict[str, Any]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        assert body["model"] == "gpt-6.1-terra" and body["store"] is False
        assert body["max_output_tokens"] == agent_settings.agent_max_output_tokens
        assert not {"messages", "max_tokens", "response_format"}.intersection(body)
        assert body["tools"][0] == {
            "type": "function",
            "name": "validate_architecture",
            "parameters": {"type": "object", "properties": {}},
            "strict": False,
        }
        assert body["text"]["format"]["type"] == "json_schema"
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": output,
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )
        assert body["input"][1:4] == output
        assert body["input"][-2:] == [
            {
                "type": "function_call_output",
                "call_id": "call_first",
                "output": '{"status":"SUCCEEDED"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_second",
                "output": '{"status":"SUCCEEDED"}',
            },
        ]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_final",
                        "role": "assistant",
                        "phase": "final_answer",
                        "content": [{"type": "output_text", "text": "{}", "annotations": []}],
                    }
                ],
            },
        )

    provider = CompatibleAgentProvider(
        response_settings(agent_settings), httpx.MockTransport(endpoint)
    )
    definitions: list[dict[str, JsonValue]] = [
        {
            "type": "function",
            "function": {
                "name": "validate_architecture",
                "parameters": {"type": "object", "properties": {}},
                "strict": False,
            },
        }
    ]
    messages: list[dict[str, JsonValue]] = [{"role": "user", "content": "Check JSON"}]
    first = await provider.complete(messages, definitions)
    assert [call.id for call in first.tool_calls] == ["call_first", "call_second"]
    assert first.usage and first.usage.input_tokens == 10
    messages.extend(
        [
            first.message(),
            {"role": "tool", "tool_call_id": "call_first", "content": '{"status":"SUCCEEDED"}'},
            {"role": "tool", "tool_call_id": "call_second", "content": '{"status":"SUCCEEDED"}'},
        ]
    )
    final = await provider.complete(messages, definitions)
    assert final.content == "{}" and final.usage is None
    assert final.message()["response_output"] == final.native_output


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "incomplete", "output": []},
        {"status": "failed", "output": []},
        {"status": "completed", "output": {}},
        {"status": "completed", "output": [42]},
        {"status": "completed", "output": []},
        {"status": "completed", "output": [{"type": "reasoning", "summary": []}]},
        {
            "status": "completed",
            "output": [{"type": "function_call", "name": "validate_architecture"}],
        },
        {"status": "completed", "output": [{"type": "function_call", "status": "in_progress"}]},
        {"status": "completed", "output": [{"type": "web_search_call"}]},
        {"status": "completed", "output": [{"type": "message", "role": "user", "content": []}]},
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "refusal", "refusal": "No"}],
                }
            ],
        },
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": 123}],
                }
            ],
        },
        {
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_valid",
                    "name": "validate_architecture",
                    "arguments": "{}",
                }
            ],
            "usage": "bad",
        },
        {
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_valid",
                    "name": "validate_architecture",
                    "arguments": "{}",
                }
            ],
            "usage": {"input_tokens": -1, "output_tokens": 0},
        },
    ],
)
async def test_malformed_responses_are_controlled(agent_settings: Settings, body: object) -> None:
    provider = CompatibleAgentProvider(
        response_settings(agent_settings),
        httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    with pytest.raises(InvalidModelResponse):
        await provider.complete([], [])


def test_history_conversion_validates_native_items() -> None:
    invalid_items: list[JsonValue] = ["invalid", [5]]
    for native in invalid_items:
        with pytest.raises(InvalidModelResponse):
            CompatibleAgentProvider._response_input(
                [{"role": "assistant", "response_output": native}]
            )
    with pytest.raises(InvalidModelResponse):
        CompatibleAgentProvider._response_input([{"role": "assistant", "tool_calls": "bad"}])
    converted = CompatibleAgentProvider._response_input(
        [
            {
                "role": "assistant",
                "content": "Inspecting.",
                "tool_calls": [
                    {
                        "type": "function",
                        "id": "call_1",
                        "function": {"name": "validate_architecture", "arguments": "{}"},
                    }
                ],
            }
        ]
    )
    assert converted == [
        {"role": "assistant", "content": "Inspecting."},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "validate_architecture",
            "arguments": "{}",
        },
    ]


async def test_unapproved_tool_specs_rejected(agent_settings: Settings) -> None:
    provider = CompatibleAgentProvider(response_settings(agent_settings))
    definitions: list[dict[str, JsonValue]] = [
        {"type": "web_search"},
        {"type": "function", "function": "bad"},
    ]
    for definition in definitions:
        with pytest.raises(InvalidModelResponse):
            await provider.complete([], [definition])


async def test_responses_adapter_api_combined_workflow(
    payload: Payload,
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    script = [
        ("search_requirements", {"query": "REQ-ETH-001"}),
        ("find_physical_path", {"source_device_id": "a", "destination_device_id": "b"}),
        ("validate_architecture", {}),
    ]
    requests: list[dict[str, Any]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        index = len(requests)
        requests.append(body)
        if index < len(script):
            name, args = script[index]
            output = [
                {"type": "reasoning", "summary": [], "encrypted_content": "opaque_reasoning"},
                {
                    "type": "function_call",
                    "id": f"fc_{index}",
                    "call_id": f"call_{index}",
                    "name": name,
                    "arguments": json.dumps(args),
                    "status": "completed",
                },
            ]
        else:
            messages = [
                {"role": "tool", "content": item["output"]}
                for item in body["input"]
                if item.get("type") == "function_call_output"
            ]
            final = referenced_final(messages)
            output = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": final.content}],
                }
            ]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": output,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = CompatibleAgentProvider(
        response_settings(agent_settings), httpx.MockTransport(endpoint)
    )
    app = create_app(agent_settings, agent_knowledge, provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/api/v1/agent/analyze",
            json={
                "question": "Inspect requirements, path and supported budgets",
                "architecture": payload,
                "options": {"include_trace": True},
            },
        )
    assert result.status_code == 200
    response = AgentResponse.model_validate(result.json())
    assert response.status == "COMPLETED" and response.citations
    assert any(finding.validation for finding in response.findings)
    assert len(response.tool_executions) == 3 and response.execution_metadata.input_tokens == 40
    assert "opaque_reasoning" not in result.text and "encrypted_content" not in result.text
