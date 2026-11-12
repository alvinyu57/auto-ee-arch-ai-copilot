from dataclasses import replace
from time import sleep

import pytest

from ee_arch_copilot.agent.policies import AgentPolicy
from ee_arch_copilot.agent.tools.adapters import (
    EngineeringTools,
    PathArguments,
    PathResult,
    SearchArguments,
    TopologyArguments,
    ValidationArguments,
)
from ee_arch_copilot.agent.tools.registry import ToolDefinition, ToolRegistry
from ee_arch_copilot.domain.models.common import DomainModel
from ee_arch_copilot.services.topology import UnknownDeviceError
from ee_arch_copilot.services.validator import ArchitectureValidator

pytestmark = pytest.mark.anyio


def test_search_is_hybrid_and_does_not_generate(agent_tools: EngineeringTools) -> None:
    results = agent_tools.search(SearchArguments(query="REQ-ETH-001"))
    assert len(results.hits) == 1
    hit = results.hits[0]
    assert hit.chunk.requirement_id == "REQ-ETH-001"
    assert hit.chunk.document_id == "ethernet" and hit.chunk.document_version == "1.0"
    assert hit.chunk.location.start_line is not None
    assert set(hit.methods) == {"semantic", "keyword"}
    assert set(hit.ranking) == {"keyword_score", "keyword_rank", "semantic_score", "semantic_rank"}
    assert not agent_tools.search(SearchArguments(query="REQ-UNKNOWN-999")).hits


def test_topology_and_paths(agent_tools: EngineeringTools) -> None:
    topology = agent_tools.topology(TopologyArguments())
    assert topology.topology.connected_components == [["a", "b"], ["isolated"]]
    assert topology.topology.isolated_device_ids == ["isolated"]
    path = agent_tools.path(PathArguments(source_device_id="a", destination_device_id="b"))
    assert path.path.exists and path.path.link_ids == ["ab"]
    assert path.links[0].nominal_bandwidth_mbps == 100
    assert "VLAN" in path.path.limitations and "traffic route" in path.route_note
    assert not agent_tools.path(
        PathArguments(
            source_device_id="a",
            destination_device_id="isolated",
        )
    ).path.exists
    with pytest.raises(UnknownDeviceError):
        agent_tools.path(PathArguments(source_device_id="private", destination_device_id="b"))
    small = agent_tools.topology(TopologyArguments(max_nodes=1, max_links=1))
    assert small.truncated and small.total_nodes == 3 and small.total_links == 1
    assert small.topology.connected_components == [] and small.topology.edges == []


def test_validation_preserves_exact_report(agent_tools: EngineeringTools) -> None:
    output = agent_tools.validate(ValidationArguments())
    assert output.report == ArchitectureValidator().validate(
        agent_tools.context.require_architecture()
    )
    selected = agent_tools.validate(ValidationArguments(rule_ids=["bandwidth.nominal_link_budget"]))
    assert selected.report.status == output.report.status
    assert selected.omitted_findings == len(output.report.findings) - 1
    assert selected.report.findings == [output.report.findings[-1]]


async def test_registry_safe_errors(registry: ToolRegistry, policy: AgentPolicy) -> None:
    missing = await registry.execute(
        "find_physical_path",
        '{"source_device_id":"private","destination_device_id":"b"}',
        "id",
        policy,
        5,
    )
    assert missing.execution.error_code == "unknown_device"
    large = await registry.execute(
        "get_architecture_topology", "{}", "id", replace(policy, max_tool_result_bytes=512), 5
    )
    assert large.execution.status == "LIMIT" and large.payload is None


async def test_tool_timeout_and_unexpected_error(policy: AgentPolicy) -> None:
    def slow(args: DomainModel) -> DomainModel:
        sleep(0.02)
        return args

    def failed(args: DomainModel) -> DomainModel:
        raise RuntimeError("API key secret and proprietary document must not be exposed")

    def bad_value(args: DomainModel) -> DomainModel:
        raise ValueError("private filesystem path")

    registry = ToolRegistry()
    for name, handler in [("slow", slow), ("failed", failed), ("bad", bad_value)]:
        registry.register(ToolDefinition(name, name, DomainModel, DomainModel, handler, 0.001))
    timed = await registry.execute("slow", "{}", "id", policy, 5)
    assert timed.execution.status == "TIMEOUT"
    for name in ("failed", "bad"):
        failed_result = await registry.execute(name, "{}", "id", policy, 5)
        assert failed_result.execution.error_code == "tool_failed"
        assert "secret" not in failed_result.execution.model_dump_json()


async def test_result_schema_is_checked(policy: AgentPolicy) -> None:
    registry = ToolRegistry()

    # The return annotation cannot make malformed implementation output trustworthy.
    def wrong(args: PathArguments) -> PathResult:
        return PathResult.model_construct()  # type: ignore[call-arg]

    registry.register(ToolDefinition("wrong", "wrong", PathArguments, PathResult, wrong, 5))
    result = await registry.execute(
        "wrong", '{"source_device_id":"a","destination_device_id":"b"}', "id", policy, 5
    )
    assert result.payload is None and result.execution.arguments_valid
    assert result.execution.error_code == "invalid_arguments_or_result"
