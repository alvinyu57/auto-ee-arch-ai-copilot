from pathlib import Path

import pytest

from ee_arch_copilot.agent.context import AgentContext
from ee_arch_copilot.agent.models import AnalyzeRequest
from ee_arch_copilot.agent.policies import AgentPolicy
from ee_arch_copilot.agent.tools.adapters import EngineeringTools
from ee_arch_copilot.agent.tools.registry import ToolRegistry, engineering_registry
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.rag.models import DocumentInput
from ee_arch_copilot.rag.service import KnowledgeService


@pytest.fixture
def agent_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, vector_db_path=tmp_path / "index")


@pytest.fixture
def agent_knowledge(agent_settings: Settings) -> KnowledgeService:
    service = KnowledgeService(agent_settings)
    service.ingest(
        DocumentInput(
            document_id="ethernet",
            filename="ethernet.md",
            version="1.0",
            source_type="markdown",
            content="REQ-ETH-001: The ADAS Controller shall support "
            "100 Mbps Ethernet bandwidth.\n\n"
            "REQ-ETH-002: The Central Gateway shall communicate with the ADAS Controller.\n",
        )
    )
    return service


@pytest.fixture
def agent_tools(payload: dict[str, object], agent_knowledge: KnowledgeService) -> EngineeringTools:
    return EngineeringTools(
        AgentContext.from_request(
            AnalyzeRequest(
                question="Inspect the architecture",
                architecture=Architecture.model_validate(payload),
            )
        ),
        lambda: agent_knowledge,
    )


@pytest.fixture
def registry(agent_tools: EngineeringTools) -> ToolRegistry:
    return engineering_registry(agent_tools, 5)


@pytest.fixture
def policy(agent_settings: Settings) -> AgentPolicy:
    return AgentPolicy.build(agent_settings, AnalyzeRequest(question="Inspect").options)
