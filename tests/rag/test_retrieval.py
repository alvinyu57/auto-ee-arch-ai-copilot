import json
from pathlib import Path

import httpx
import pytest

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.embeddings.providers import CompatibleEmbeddingProvider
from ee_arch_copilot.rag.models import DocumentInput, RetrievalOptions, SearchFilter
from ee_arch_copilot.rag.retrieval.hybrid import fuse
from ee_arch_copilot.rag.retrieval.keyword import KeywordRetriever
from ee_arch_copilot.rag.service import KnowledgeService
from ee_arch_copilot.rag.tokenization import tokenize


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("REQ-ETH-001", "REQ-ETH-001"),
        ("req-soa-015", "REQ-SOA-015"),
        ("SOME/IP-SD", "REQ-SOA-015"),
        ("VLAN 100", "REQ-SOA-015"),
        ("0x1234", "REQ-SOA-015"),
        ("1000BASE-T1", "REQ-ETH-001"),
    ],
)
def test_exact_technical_retrieval(indexed: KnowledgeService, query: str, expected: str) -> None:
    assert (
        indexed.search(query, RetrievalOptions(method="keyword")).hits[0].chunk.requirement_id
        == expected
    )


def test_technical_tokenization() -> None:
    terms = tokenize("REQ-ETH-001 SOME/IP-SD IEEE 802.1Qbv VLAN 100 1000BASE-T1 0x1234")
    assert {
        "req-eth-001",
        "some/ip-sd",
        "ieee 802.1qbv",
        "vlan 100",
        "1000base-t1",
        "0x1234",
    } <= set(terms)


def test_semantic_retrieval_distinguishes_documents(indexed: KnowledgeService) -> None:
    hits = indexed.search(
        "Central Gateway Ethernet ADAS bandwidth", RetrievalOptions(method="semantic")
    ).hits
    assert hits[0].chunk.requirement_id == "REQ-ETH-001"
    assert hits[0].methods == ["semantic"]
    assert hits[0].ranking["semantic_score"] > 0.2


def test_hybrid_rrf_exact_math_and_dedup(indexed: KnowledgeService) -> None:
    chunks = indexed.store.chunks()
    first, second = chunks[:2]
    options = RetrievalOptions(rrf_constant=10)
    hits = fuse(
        {
            "keyword": [(first, 100), (second, 1), (first, 100)],
            "semantic": [(second, 0.9), (first, 0.8)],
        },
        options,
        "gateway",
    )
    assert len(hits) == 2
    assert hits[0].score == pytest.approx(1 / 11 + 1 / 12)
    assert hits[1].score == hits[0].score
    assert hits[0].chunk.chunk_id < hits[1].chunk.chunk_id
    assert hits[0].methods == ["keyword", "semantic"]


def test_deterministic_hybrid_and_rerank(indexed: KnowledgeService) -> None:
    options = RetrievalOptions(enable_reranking=True, final_top_k=2)
    first = indexed.search("Gateway 1000BASE-T1", options)
    assert first == indexed.search("Gateway 1000BASE-T1", options)
    assert first.hits[0].chunk.requirement_id == "REQ-ETH-001"
    assert all("reranker_overlap" in hit.ranking for hit in first.hits)
    assert [hit.rank for hit in first.hits] == list(range(1, len(first.hits) + 1))


def test_no_results_and_missing_identifiers(
    indexed: KnowledgeService, service: KnowledgeService
) -> None:
    assert service.search("REQ-MISSING-999").hits == []
    assert indexed.search("REQ-MISSING-999").hits == []
    assert indexed.search("the and").hits == []
    assert (
        indexed.search("lithium cathode electrolyte", RetrievalOptions(method="keyword")).hits == []
    )
    assert (
        indexed.search("gateway", RetrievalOptions(filters=SearchFilter(document_id="absent"))).hits
        == []
    )
    assert KeywordRetriever().search("gateway", [], 5) == []
    with pytest.raises(ValueError):
        indexed.search(" ")


def test_multiple_requirement_ids(indexed: KnowledgeService) -> None:
    hits = indexed.search("Compare REQ-ETH-001 and REQ-ETH-002").hits
    assert {hit.chunk.requirement_id for hit in hits} == {"REQ-ETH-001", "REQ-ETH-002"}


def test_semantic_adapter_retrieves_without_shared_terms(
    tmp_path: Path, source: DocumentInput
) -> None:
    # A controlled semantic provider encodes synonyms; verifies vector search independently
    # from BM25 and without pretending the hash baseline understands paraphrases.
    def handle(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": index,
                        "embedding": [
                            1.0 if ("1000BASE-T1" in text or "gigabit backbone" in text) else 0.0,
                            0.0 if ("1000BASE-T1" in text or "gigabit backbone" in text) else 1.0,
                        ]
                        + [0.0] * 30,
                    }
                    for index, text in enumerate(texts)
                ]
            },
        )

    settings = Settings(
        vector_db_path=tmp_path,
        embedding_provider="openai_compatible",
        embedding_model="controlled-semantic",
        embedding_dimension=32,
    )
    provider = CompatibleEmbeddingProvider(settings, httpx.MockTransport(handle))
    service = KnowledgeService(settings, embedding_provider=provider)
    service.ingest(source)
    assert service.search("gigabit backbone", RetrievalOptions(method="keyword")).hits == []
    hits = service.search("gigabit backbone", RetrievalOptions(method="semantic")).hits
    assert [hit.chunk.requirement_id for hit in hits] == ["REQ-ETH-001"]
    assert hits[0].score == pytest.approx(1)
