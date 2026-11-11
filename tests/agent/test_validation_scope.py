import pytest

from ee_arch_copilot.agent.models import AnalyzeRequest
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.testing import ScriptedProvider, referenced_final, tool_reply
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.rag.service import KnowledgeService
from ee_arch_copilot.services.validator import ArchitectureValidator


@pytest.mark.anyio
async def test_filtered_validation_preserves_scope_and_original_status(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    provider = ScriptedProvider(
        [
            tool_reply(
                "validate_architecture", {"rule_ids": ["bandwidth.nominal_link_budget"]}, "v"
            ),
            referenced_final,
        ]
    )
    response = await AgentOrchestrator(agent_settings, provider, lambda: agent_knowledge).analyze(
        AnalyzeRequest(question="Check only declared link budgets", architecture=sample)
    )
    scope = response.tool_executions[0].validation_scope
    assert scope is not None
    oracle = ArchitectureValidator().validate(sample)
    assert scope.architecture_id == sample.id and scope.original_report_status == oracle.status
    assert scope.selected_rule_ids == ["bandwidth.nominal_link_budget"]
    assert scope.omitted_findings == len(oracle.findings) - sum(
        finding.rule_id == "bandwidth.nominal_link_budget" for finding in oracle.findings
    )
    assert scope.scope == oracle.scope
    assert all(
        item.validation.rule_id == "bandwidth.nominal_link_budget"
        for item in response.findings
        if item.validation
    )
    assert any("findings were omitted" in limitation for limitation in response.limitations)
