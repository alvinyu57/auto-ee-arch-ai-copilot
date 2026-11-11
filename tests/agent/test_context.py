import asyncio

import pytest

from ee_arch_copilot.agent.context import AgentContext
from ee_arch_copilot.agent.models import AnalyzeRequest
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.testing import ScriptedProvider, referenced_final, tool_reply
from ee_arch_copilot.agent.tools.adapters import EngineeringTools, SearchArguments
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.rag.models import SearchFilter
from ee_arch_copilot.rag.service import KnowledgeService

pytestmark = pytest.mark.anyio


def test_context_owns_architecture_snapshot(sample: Architecture) -> None:
    request = AnalyzeRequest(question="Inspect", architecture=sample)
    context = AgentContext.from_request(request)
    sample.ecus[0].name = "changed"
    assert context.require_architecture().ecus[0].name != "changed"
    with pytest.raises(ValueError, match="architecture_unavailable"):
        AgentContext.from_request(AnalyzeRequest(question="Inspect")).require_architecture()


def test_scope_cannot_be_widened(agent_knowledge: KnowledgeService) -> None:
    scope = SearchFilter(document_id="ethernet", version="1.0", requirement_id="REQ-ETH-001")
    context = AgentContext.from_request(AnalyzeRequest(question="Find"), scope)
    assert context.filters(SearchFilter()) == scope
    scope.document_id = "changed"
    assert context.document_scope.document_id == "ethernet"
    tool = EngineeringTools(context, lambda: agent_knowledge)
    assert len(tool.search(SearchArguments(query="ADAS")).hits) == 1
    for proposed in [
        SearchFilter(document_id="private"),
        SearchFilter(version="2.0"),
        SearchFilter(requirement_id="REQ-ETH-002"),
    ]:
        with pytest.raises(ValueError, match="document_scope_denied"):
            context.filters(proposed)


async def test_concurrent_requests_are_isolated(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    async def run(architecture_id: str) -> str:
        provider = ScriptedProvider(
            [
                tool_reply("get_architecture_topology", {}, "topology"),
                referenced_final,
            ]
        )
        response = await AgentOrchestrator(
            agent_settings, provider, lambda: agent_knowledge
        ).analyze(
            AnalyzeRequest(
                question="Inspect", architecture=Architecture(id=architecture_id, name="Test")
            )
        )
        topology = response.evidence[0].data["topology"]
        assert isinstance(topology, dict)
        return str(topology["architecture_id"])

    first, second = await asyncio.gather(run("first"), run("second"))
    assert first == "first" and second == "second"
