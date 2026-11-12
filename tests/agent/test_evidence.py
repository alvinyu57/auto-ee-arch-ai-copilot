import json

import pytest

from ee_arch_copilot.agent.evidence import EvidenceStore
from ee_arch_copilot.agent.models import AnalyzeRequest, ModelFinal
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.testing import ScriptedProvider, referenced_final, tool_reply
from ee_arch_copilot.agent.tools.adapters import EngineeringTools, SearchArguments
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.models import DocumentInput
from ee_arch_copilot.rag.service import KnowledgeService

pytestmark = pytest.mark.anyio


def test_provenance_deduplication_and_citations(agent_tools: EngineeringTools) -> None:
    evidence = EvidenceStore()
    result = agent_tools.search(SearchArguments(query="REQ-ETH-001"))
    first = evidence.prepare("first", result)
    assert not evidence.records
    evidence.commit(first)
    result.hits[0].rank = 99
    result.hits[0].score = 0.1
    second = evidence.prepare("second", result)
    evidence.commit(second)
    assert len(evidence.records) == 1 and second[0].evidence_id == first[0].evidence_id
    record = next(iter(evidence.records.values()))
    assert record.document_version == "1.0" and record.execution_id == "first"
    cite = evidence.citations()[0]
    assert cite.citation_id == record.evidence_id and cite.chunk_id == record.chunk_id
    assert cite.quote == result.hits[0].chunk.text
    assert cite.location == result.hits[0].chunk.location


@pytest.mark.parametrize(
    "mutation", ["unknown_ref", "unknown_id", "wrong_source", "no_ref", "wrong_kind"]
)
def test_evidence_reference_validation(agent_tools: EngineeringTools, mutation: str) -> None:
    evidence = EvidenceStore()
    evidence.commit(evidence.prepare("s", agent_tools.search(SearchArguments(query="ADAS"))))
    draft = json.loads(str(referenced_final([]).content))
    draft["findings"] = [
        {
            "description": "Inspect the source.",
            "finding_type": "interpretation",
            "evidence_references": ["E1"],
        }
    ]
    if mutation == "unknown_ref":
        draft["findings"][0]["evidence_references"] = ["E999"]
    elif mutation == "unknown_id":
        draft["summary"] = "REQ-BOGUS-999 is described here."
    elif mutation == "wrong_source":
        other = next(record for record in evidence.records.values() if record.evidence_id != "E1")
        draft["findings"][0]["description"] = f"Inspect {other.requirement_id}."
    elif mutation == "no_ref":
        draft["findings"][0]["evidence_references"] = []
    else:
        draft["recommendations"][0]["finding_type"] = "assumption"
    with pytest.raises(ValueError):
        evidence.validate_final(
            ModelFinal.model_validate(draft),
            agent_tools.knowledge().settings.requirement_id_pattern,
        )


async def test_conflicting_requirements_keep_both_sources(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
) -> None:
    for name, value in [("first", 100), ("second", 1000)]:
        agent_knowledge.ingest(
            DocumentInput(
                document_id=name,
                filename=f"{name}.md",
                version=name,
                source_type="text",
                content=f"REQ-CONFLICT-001: The gateway bandwidth shall be {value} Mbps.",
            )
        )
    provider = ScriptedProvider(
        [tool_reply("search_requirements", {"query": "REQ-CONFLICT-001"}, "s"), referenced_final]
    )
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Compare conflicting bandwidth constraints")
    )
    assert response.status == "INSUFFICIENT_EVIDENCE"
    assert {cite.document_id for cite in response.citations} == {"first", "second"}
    assert {cite.document_version for cite in response.citations} == {"first", "second"}
    assert "conflicting" in response.summary
    assert any("precedence" in text for text in response.unresolved_questions)
    assert not any(item.validation for item in response.findings)
