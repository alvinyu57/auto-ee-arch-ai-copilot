import json
from pathlib import Path

import pytest

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.models import Chunk, DocumentInput, GenerationOptions
from ee_arch_copilot.rag.service import KnowledgeService


class ControlledLLM:
    model = "controlled-test-provider"

    def __init__(self, response: str | None = None) -> None:
        self.response = response
        self.calls = 0

    def generate(self, question: str, chunks: list[Chunk], options: GenerationOptions) -> str:
        self.calls += 1
        if self.response is not None:
            return self.response
        return json.dumps(
            {
                "answer": chunks[0].text + " [S1]",
                "citation_ids": ["S1"],
                "referenced_requirement_ids": [chunks[0].requirement_id]
                if chunks[0].requirement_id
                else [],
            }
        )


@pytest.fixture
def source() -> DocumentInput:
    return DocumentInput(
        document_id="ethernet",
        filename="ethernet.md",
        source_type="markdown",
        version="1.0",
        content=(
            "# Synthetic Ethernet\n\n## Gateway\n\nREQ-ETH-001:\n"
            "The Central Gateway shall use 1000BASE-T1 at 1000 Mbps to ADAS.\n\n"
            "REQ-ETH-002: Camera shall use 100BASE-T1 on VLAN 20.\n\n"
            "## Discovery\n\nREQ-SOA-015: SOME/IP-SD service 0x1234 shall use VLAN 100.\n"
        ),
    )


@pytest.fixture
def service(tmp_path: Path) -> KnowledgeService:
    return KnowledgeService(
        Settings(vector_db_path=tmp_path / "index"), llm_provider=ControlledLLM()
    )


@pytest.fixture
def indexed(service: KnowledgeService, source: DocumentInput) -> KnowledgeService:
    service.ingest(source)
    return service
