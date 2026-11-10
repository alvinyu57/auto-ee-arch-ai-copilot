import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.main import create_app
from ee_arch_copilot.rag.errors import ConfigurationError, ProviderError
from ee_arch_copilot.rag.models import DocumentInput
from ee_arch_copilot.rag.service import KnowledgeService
from tests.rag.conftest import ControlledLLM

pytestmark = pytest.mark.anyio

SOURCE = {
    "document_id": "ethernet",
    "filename": "ethernet.md",
    "source_type": "markdown",
    "version": "1.0",
    "content": "# Ethernet\n\nREQ-ETH-001: Gateway shall use 1000BASE-T1 at 1000 Mbps.",
}


@pytest.fixture
def api_service(tmp_path: Path) -> KnowledgeService:
    return KnowledgeService(Settings(vector_db_path=tmp_path), llm_provider=ControlledLLM())


@pytest.fixture
async def knowledge_client(api_service: KnowledgeService) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=create_app(api_service.settings, api_service)),
        base_url="http://test",
    ) as client:
        yield client


async def test_api_lifecycle(knowledge_client: AsyncClient) -> None:
    client = knowledge_client
    assert (await client.get("/api/v1/knowledge/documents")).json() == []
    ingested = await client.post("/api/v1/knowledge/documents", json=SOURCE)
    assert ingested.status_code == 200
    assert ingested.json()["status"] == "created"
    assert (await client.post("/api/v1/knowledge/documents", json=SOURCE)).json()[
        "status"
    ] == "unchanged"
    assert len((await client.get("/api/v1/knowledge/documents")).json()) == 1
    assert (await client.get("/api/v1/knowledge/documents/ethernet")).json()["content"] == SOURCE[
        "content"
    ]
    search = await client.post("/api/v1/knowledge/search", json={"question": "REQ-ETH-001"})
    assert search.status_code == 200
    hit = search.json()["hits"][0]
    assert hit["chunk"]["requirement_id"] == "REQ-ETH-001"
    assert hit["methods"] == ["keyword", "semantic"]
    chunk_id = hit["chunk"]["chunk_id"]
    assert (await client.get(f"/api/v1/knowledge/chunks/{chunk_id}")).json() == hit["chunk"]
    answer = await client.post("/api/v1/knowledge/ask", json={"question": "REQ-ETH-001"})
    assert answer.status_code == 200
    assert answer.json()["evidence_status"] == "cited"
    assert answer.json()["citations"][0]["chunk_id"] == chunk_id
    assert (
        await client.post("/api/v1/knowledge/ask", json={"question": "REQ-MISSING-999"})
    ).json()["evidence_status"] == "insufficient"
    assert (await client.delete("/api/v1/knowledge/documents/ethernet")).status_code == 204
    assert (await client.get(f"/api/v1/knowledge/chunks/{chunk_id}")).status_code == 404
    assert (await client.post("/api/v1/knowledge/search", json={"question": "gateway"})).json()[
        "hits"
    ] == []


@pytest.mark.parametrize("method", ["get", "delete"])
async def test_missing_documents(knowledge_client: AsyncClient, method: str) -> None:
    assert (
        await knowledge_client.request(method, "/api/v1/knowledge/documents/missing")
    ).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": " "},
        {"question": "x" * 5001},
        {"question": "x", "options": {"final_top_k": 101}},
        {"question": "x", "options": {"min_similarity": float("inf")}},
    ],
)
async def test_invalid_search(knowledge_client: AsyncClient, body: dict[str, object]) -> None:
    # Send non-finite values as raw JSON to exercise the app's safe validation-error handler.
    import json

    response = await knowledge_client.post(
        "/api/v1/knowledge/search",
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"filename": "/etc/passwd"},
        {"source_type": "pdf"},
        {"source_type": "json", "content": "bad"},
        {"metadata": {"api_key": "test-only"}},
        {"path": "/etc/passwd"},
    ],
)
async def test_invalid_document(knowledge_client: AsyncClient, change: dict[str, object]) -> None:
    response = await knowledge_client.post("/api/v1/knowledge/documents", json=SOURCE | change)
    assert response.status_code == 422


async def test_missing_llm_and_lazy_service(tmp_path: Path) -> None:
    app = create_app(Settings(vector_db_path=tmp_path))
    assert app.state.knowledge_service is None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/v1/knowledge/search", json={"question": "gateway"})).json()[
            "hits"
        ] == []
        assert app.state.knowledge_service is not None
        assert (
            await client.post("/api/v1/knowledge/ask", json={"question": "gateway"})
        ).status_code == 503
        assert (await client.post("/api/v1/knowledge/documents", json=SOURCE)).status_code == 200
        assert (
            await client.post("/api/v1/knowledge/ask", json={"question": "gateway"})
        ).status_code == 503


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProviderError("secret"), 502),
        (ConfigurationError("secret"), 503),
        (sqlite3.OperationalError("secret"), 503),
        (OSError("secret"), 503),
    ],
)
async def test_safe_service_errors(
    knowledge_client: AsyncClient, error: Exception, status: int
) -> None:
    with patch.object(KnowledgeService, "search", side_effect=error):
        response = await knowledge_client.post(
            "/api/v1/knowledge/search", json={"question": "gateway"}
        )
    assert response.status_code == status
    assert "secret" not in response.text


async def test_bad_llm_response(
    knowledge_client: AsyncClient, api_service: KnowledgeService
) -> None:
    api_service.ingest(DocumentInput.model_validate(SOURCE))
    api_service.generator.provider = ControlledLLM("malformed")
    assert (
        await knowledge_client.post("/api/v1/knowledge/ask", json={"question": "gateway"})
    ).status_code == 502
    api_service.generator.provider = ControlledLLM(
        '{"answer":"invented [S99]","citation_ids":["S99"]}'
    )
    response = await knowledge_client.post("/api/v1/knowledge/ask", json={"question": "gateway"})
    assert response.status_code == 200
    assert response.json()["evidence_status"] == "invalid_citations"


async def test_streamed_size_limit(tmp_path: Path) -> None:
    app = create_app(Settings(vector_db_path=tmp_path, max_request_bytes=1000))

    async def oversized() -> AsyncIterator[bytes]:
        yield b"x" * 700
        yield b"x" * 700

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/knowledge/documents", content=oversized())
        assert response.status_code == 413
        assert app.state.knowledge_service is None
