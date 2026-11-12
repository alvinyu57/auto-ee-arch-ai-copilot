import json

import pytest
from pydantic import BaseModel

from ee_arch_copilot.agent.policies import AgentPolicy
from ee_arch_copilot.agent.tools.adapters import TopologyArguments, TopologyResult
from ee_arch_copilot.agent.tools.registry import ToolDefinition, ToolRegistry

pytestmark = pytest.mark.anyio


def test_allowlist_and_provider_schemas(registry: ToolRegistry) -> None:
    specs = registry.specifications()
    functions = [spec["function"] for spec in specs]
    assert all(isinstance(function, dict) for function in functions)
    assert {function["name"] for function in functions if isinstance(function, dict)} == {
        "search_requirements",
        "get_architecture_topology",
        "find_physical_path",
        "validate_architecture",
    }
    for spec in specs:
        assert spec["type"] == "function"
        function = spec["function"]
        assert isinstance(function, dict)
        schema = function["parameters"]
        assert isinstance(schema, dict)
        assert schema["additionalProperties"] is False
    assert json.loads(json.dumps(specs)) == specs


def test_duplicate_write_and_timeout_registration() -> None:
    registry = ToolRegistry()
    tool = ToolDefinition("test", "Test", BaseModel, BaseModel, lambda arg: arg, 1)
    registry.register(tool)
    with pytest.raises(ValueError):
        registry.register(tool)
    for readonly, timeout in [(False, 1), (True, 0)]:
        with pytest.raises(ValueError):
            registry.register(
                ToolDefinition(
                    "other", "Test", BaseModel, BaseModel, lambda arg: arg, timeout, readonly
                )
            )


@pytest.mark.parametrize(
    ("name", "arguments", "error"),
    [
        ("execute_shell", '{"command":"id"}', "unknown_tool"),
        ("find_physical_path", "not JSON", "invalid_arguments_or_result"),
        ("find_physical_path", '{"source_device_id":"a"}', "invalid_arguments_or_result"),
        (
            "get_architecture_topology",
            '{"architecture":"/etc/passwd"}',
            "invalid_arguments_or_result",
        ),
        ("validate_architecture", '{"rule_ids":["tsn.certify"]}', "invalid_arguments_or_result"),
        ("search_requirements", '{"query":"ADAS","top_k":100}', "invalid_arguments_or_result"),
        ("search_requirements", '{"query":"ADAS","top_k":"5"}', "invalid_arguments_or_result"),
        ("search_requirements", '{"query":" "}', "invalid_arguments_or_result"),
        ("validate_architecture", " " * 5000, "argument_size_limit"),
    ],
)
async def test_rejected_calls(
    registry: ToolRegistry,
    policy: AgentPolicy,
    name: str,
    arguments: str,
    error: str,
) -> None:
    outcome = await registry.execute(name, arguments, "call_1", policy, 5)
    assert outcome.execution.status == "REJECTED"
    assert outcome.execution.error_code == error
    assert outcome.payload is None
    assert outcome.execution.duration_ms >= 0


async def test_typed_result_roundtrip(registry: ToolRegistry, policy: AgentPolicy) -> None:
    outcome = await registry.execute("get_architecture_topology", "{}", "call_1", policy, 5)
    assert outcome.execution.status == "SUCCEEDED"
    assert isinstance(outcome.payload, TopologyResult)
    assert TopologyResult.model_validate_json(outcome.payload.model_dump_json()) == outcome.payload
    assert TopologyArguments.model_json_schema()["properties"]["max_nodes"]["maximum"] == 100
