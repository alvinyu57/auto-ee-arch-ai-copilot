from pathlib import Path
from unittest.mock import patch

import pytest

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.embeddings.providers import HashEmbeddingProvider
from ee_arch_copilot.rag.errors import ConfigurationError
from ee_arch_copilot.rag.models import AskRequest, DocumentInput, RetrievalOptions, SearchFilter
from ee_arch_copilot.rag.service import KnowledgeService
from ee_arch_copilot.rag.storage.chroma_store import ChromaStore


def test_persistence_filters_and_delete(indexed: KnowledgeService) -> None:
    reopened = KnowledgeService(indexed.settings)
    assert len(reopened.store.chunks()) == 3
    hit = reopened.search("1000BASE-T1", RetrievalOptions(method="semantic")).hits[0]
    assert hit.chunk.requirement_id == "REQ-ETH-001"
    filters = SearchFilter(document_id="ethernet", requirement_id="REQ-ETH-002", version="1.0")
    assert [chunk.requirement_id for chunk in reopened.store.chunks(filters)] == ["REQ-ETH-002"]
    options = RetrievalOptions(method="semantic", filters=filters, min_similarity=-1)
    assert [hit.chunk.requirement_id for hit in reopened.search("camera", options).hits] == [
        "REQ-ETH-002"
    ]
    assert (
        reopened.search("camera", RetrievalOptions(filters=SearchFilter(version="missing"))).hits
        == []
    )
    assert reopened.store.get_document("missing") is None
    assert reopened.store.delete("ethernet")
    assert reopened.store.collection.count() == 0
    assert reopened.store.chunks() == []
    assert not reopened.store.delete("ethernet")


def test_model_mismatch(indexed: KnowledgeService) -> None:
    with pytest.raises(ConfigurationError, match="mismatch"):
        ChromaStore(indexed.settings.vector_db_path, "different-model", 384)
    with pytest.raises(ConfigurationError):
        ChromaStore(indexed.settings.vector_db_path, indexed.embeddings.identity, 32)


def test_atomic_replacement_staging_failure(
    indexed: KnowledgeService, source: DocumentInput
) -> None:
    original = indexed.store.chunks()
    updated = source.model_copy(update={"version": "2", "content": "REQ-NEW-001: New gateway."})
    collection_type = type(indexed.store.collection)
    with (
        patch.object(collection_type, "upsert", side_effect=RuntimeError("staging failed")),
        pytest.raises(RuntimeError, match="staging"),
    ):
        indexed.ingest(updated)
    assert indexed.store.chunks() == original
    assert indexed.search("REQ-ETH-001").hits[0].chunk.requirement_id == "REQ-ETH-001"


def test_inactive_orphan_vectors_excluded(indexed: KnowledgeService) -> None:
    indexed.store.collection.upsert(
        ids=["orphan"],
        embeddings=indexed.embeddings.embed_query("orphan"),
        documents=["orphan"],
        metadatas=[{"document_id": "ethernet", "revision": "not-active", "chunk_id": "fabricated"}],
    )
    assert all(hit.chunk.chunk_id != "fabricated" for hit in indexed.search("orphan").hits)


def test_metadata_update_and_content_change(
    indexed: KnowledgeService, source: DocumentInput
) -> None:
    original_ids = {chunk.chunk_id for chunk in indexed.store.chunks()}
    updated = source.model_copy(update={"metadata": {"reviewed": True}, "title": "Revised title"})
    assert indexed.ingest(updated).status == "replaced"
    assert indexed.store.collection.count() == 3
    assert all(chunk.document_title == "Revised title" for chunk in indexed.store.chunks())
    assert {chunk.chunk_id for chunk in indexed.store.chunks()} == original_ids
    changed = updated.model_copy(update={"content": "REQ-ETH-999: A new gateway requirement."})
    assert indexed.ingest(changed).status == "replaced"
    assert indexed.search("REQ-ETH-001").hits == []
    assert indexed.store.documents()[0].version == "1.0"


def test_empty_vector_write_rejected(tmp_path: Path) -> None:
    service = KnowledgeService(Settings(vector_db_path=tmp_path))
    from ee_arch_copilot.rag.ingestion.loader import normalize_document

    document = normalize_document(DocumentInput(filename="x.txt", source_type="text", content="x"))
    with pytest.raises(ValueError, match="indexable"):
        service.store.replace(document, [], [], "revision")


def test_injected_provider_cannot_mix_models(indexed: KnowledgeService) -> None:
    with pytest.raises(ConfigurationError, match="identities"):
        KnowledgeService(
            indexed.settings, store=indexed.store, embedding_provider=HashEmbeddingProvider(32)
        )


def test_generation_configuration_path(tmp_path: Path) -> None:
    service = KnowledgeService(
        Settings(vector_db_path=tmp_path, llm_provider="openai_compatible", llm_model="test")
    )
    assert service.ask(AskRequest(question="REQ-MISSING-999")).evidence_status == "insufficient"
    assert service.generator.provider is not None
    assert service.generator.provider.model == "test"


def test_bad_llm_settings_do_not_disable_retrieval(tmp_path: Path, source: DocumentInput) -> None:
    service = KnowledgeService(Settings(vector_db_path=tmp_path, llm_provider="openai_compatible"))
    service.ingest(source)
    assert service.search("REQ-ETH-001").hits[0].chunk.requirement_id == "REQ-ETH-001"
    with pytest.raises(ConfigurationError):
        service.ask(AskRequest(question="REQ-ETH-001"))
