import re
from pathlib import Path
from typing import Literal

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.embeddings.base import EmbeddingProvider
from ee_arch_copilot.rag.embeddings.providers import create_embedding_provider
from ee_arch_copilot.rag.errors import ConfigurationError, DocumentIdentityConflict
from ee_arch_copilot.rag.generation.answer_generator import (
    AnswerGenerator,
    CompatibleLLMProvider,
    LLMProvider,
)
from ee_arch_copilot.rag.ingestion.chunker import RequirementChunker
from ee_arch_copilot.rag.ingestion.loader import normalize_document
from ee_arch_copilot.rag.ingestion.parser import RequirementParser
from ee_arch_copilot.rag.models import (
    AnswerResponse,
    AskRequest,
    DocumentInput,
    IngestionResponse,
    RetrievalOptions,
    SearchResponse,
)
from ee_arch_copilot.rag.retrieval.hybrid import fuse
from ee_arch_copilot.rag.retrieval.keyword import KeywordRetriever, searchable_text
from ee_arch_copilot.rag.retrieval.reranker import Reranker, TokenOverlapReranker
from ee_arch_copilot.rag.retrieval.semantic import SemanticRetriever
from ee_arch_copilot.rag.storage.chroma_store import ChromaStore
from ee_arch_copilot.rag.tokenization import tokenize


class KnowledgeService:
    """Phase 3 callable boundary; no NetworkX, validator, or HTTP dependencies."""

    def __init__(
        self,
        settings: Settings,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        llm_provider: LLMProvider | None = None,
        store: ChromaStore | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.settings = settings
        self.embeddings = embedding_provider or create_embedding_provider(settings)
        self.store = store or ChromaStore(
            Path(settings.vector_db_path), self.embeddings.identity, self.embeddings.dimension
        )
        if (
            self.store.embedding_identity != self.embeddings.identity
            or self.store.dimension != self.embeddings.dimension
        ):
            raise ConfigurationError("Injected store and embedding provider identities must match")
        self.parser = RequirementParser(settings.requirement_id_pattern)
        self.chunker = RequirementChunker(settings.chunk_size, settings.chunk_overlap)
        self.keyword = KeywordRetriever()
        self.semantic = SemanticRetriever(self.embeddings, self.store)
        self.reranker = reranker or TokenOverlapReranker()
        self.generator = AnswerGenerator(llm_provider, settings.requirement_id_pattern)

    def ingest(self, source: DocumentInput, *, force: bool = False) -> IngestionResponse:
        document = normalize_document(source)
        chunks = self.chunker.chunk(document, self.parser.parse(document))
        revision = self.store.revision_for(document, chunks)
        with self.store.lock:
            if (
                source.document_id is None
                and self.store.get_document(document.document_id) is not None
                and not self.store.is_current(document.document_id, revision)
            ):
                raise DocumentIdentityConflict(
                    "Filename-derived document already exists with different content or metadata; "
                    "supply its document_id to replace it, or a distinct document_id "
                    "for another origin"
                )
            status: Literal["created", "unchanged", "replaced"]
            if not force and self.store.is_current(document.document_id, revision):
                status = "unchanged"
            else:
                vectors = self.embeddings.embed_documents(
                    [searchable_text(chunk) for chunk in chunks]
                )
                status = self.store.replace(document, chunks, vectors, revision)
            summary = next(
                item for item in self.store.documents() if item.document_id == document.document_id
            )
            return IngestionResponse(
                document=summary,
                status=status,
                extraction_warnings=list(
                    dict.fromkeys(
                        warning for chunk in chunks for warning in chunk.extraction_warnings
                    )
                ),
            )

    def reindex(self, document_id: str) -> IngestionResponse:
        document = self.store.get_document(document_id)
        if document is None:
            raise KeyError(document_id)
        return self.ingest(
            DocumentInput.model_validate(
                document.model_dump(exclude={"content_hash", "ingestion_timestamp"})
            ),
            force=True,
        )

    def search(self, question: str, options: RetrievalOptions | None = None) -> SearchResponse:
        if not question.strip() or len(question) > 5000:
            raise ValueError("Question must contain 1 to 5000 characters")
        options = options or self.settings.retrieval_options()
        with self.store.lock:
            chunks = self.store.chunks(options.filters)
            if not chunks or not tokenize(question):
                return SearchResponse(hits=[])
            requested_ids = {
                match.group(0).casefold()
                for match in re.finditer(self.settings.requirement_id_pattern, question, re.I)
            }
            if requested_ids:
                chunks = [
                    chunk
                    for chunk in chunks
                    if chunk.requirement_id and chunk.requirement_id.casefold() in requested_ids
                ]
                if not chunks:
                    return SearchResponse(hits=[])
            allowed = {chunk.chunk_id for chunk in chunks}
            rankings = {}
            if options.method in {"keyword", "hybrid"}:
                rankings["keyword"] = self.keyword.search(question, chunks, options.keyword_top_k)
            if options.method in {"semantic", "hybrid"}:
                rankings["semantic"] = [
                    (chunk, score)
                    for chunk, score in self.semantic.search(
                        question, options, allowed if requested_ids else None
                    )
                    if chunk.chunk_id in allowed
                ]
            return SearchResponse(hits=fuse(rankings, options, question, self.reranker))

    def ask(self, request: AskRequest) -> AnswerResponse:
        with self.store.lock:
            if (
                self.generator.provider is None
                and self.settings.llm_provider == "openai_compatible"
            ):
                self.generator.provider = CompatibleLLMProvider(self.settings)
            # Capture revisions and retrieval in the same critical section, then release
            # the lock for the slow provider call. Metadata-only edits matter too.
            hits = self.search(request.question, request.options).hits
            revisions = {
                hit.chunk.document_id: self.store.get_revision(hit.chunk.document_id)
                for hit in hits
            }
        answer = self.generator.answer(
            request.question, [hit.chunk for hit in hits], request.generation
        )
        with self.store.lock:
            if any(
                revision is None or not self.store.is_current(document_id, revision)
                for document_id, revision in revisions.items()
            ):
                return AnswerResponse(
                    answer="The source evidence expired during generation. Search and ask again.",
                    evidence_status="stale_evidence",
                    model=answer.model,
                    explanation=(
                        "Retrieved source revisions changed or were deleted during generation."
                    ),
                )
            return answer
