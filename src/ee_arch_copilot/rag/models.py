"""Public provenance, retrieval, and generation contracts."""

import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
NonBlank = Annotated[str, Field(min_length=1, max_length=5000)]
SourceType = Literal["markdown", "text", "json", "pdf"]


class RAGModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DocumentInput(RAGModel):
    document_id: Identifier | None = None
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    source_type: SourceType
    title: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    version: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    content: Annotated[str, Field(min_length=1, max_length=1_000_000)]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("filename")
    @classmethod
    def basename_only(cls, value: str) -> str:
        if value in {".", ".."} or any(c in value for c in ("/", "\\", "\x00", ":")):
            raise ValueError("filename must be a basename, not a filesystem path")
        return value

    @field_validator("content", "title", "version")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("metadata")
    @classmethod
    def no_credentials(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        def inspect(item: JsonValue) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if re.search(
                        r"api.?key|password|secret|authorization|access.?token", key, re.I
                    ):
                        raise ValueError("credentials must not be stored in document metadata")
                    inspect(child)
            elif isinstance(item, list):
                for child in item:
                    inspect(child)

        inspect(value)
        return value


class Document(RAGModel):
    document_id: Identifier
    filename: str
    source_type: SourceType
    title: str
    version: str | None = None
    content: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str


class DocumentSummary(RAGModel):
    document_id: str
    filename: str
    title: str
    source_type: SourceType
    version: str | None
    metadata: dict[str, JsonValue]
    ingestion_timestamp: datetime
    content_hash: str
    chunk_count: int


class SourceLocation(RAGModel):
    """Character offsets are half-open in normalized content; JSON uses a JSON pointer."""

    start_offset: int | None = None
    end_offset: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    page: int | None = None
    json_pointer: str | None = None
    text_start_offset: int | None = None
    text_end_offset: int | None = None


class SourceRecord(RAGModel):
    requirement_id: str | None = None
    section: str | None = None
    text: str
    location: SourceLocation
    structured_fields: dict[str, JsonValue] = Field(default_factory=dict)
    extraction_warnings: list[str] = Field(default_factory=list)


class Chunk(RAGModel):
    chunk_id: str
    document_id: str
    filename: str
    document_title: str
    document_version: str | None
    requirement_id: str | None
    section: str | None
    text: str
    original_text: str
    location: SourceLocation
    structured_fields: dict[str, JsonValue] = Field(default_factory=dict)
    extraction_warnings: list[str] = Field(default_factory=list)


class SearchFilter(RAGModel):
    document_id: Identifier | None = None
    requirement_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    version: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class RetrievalOptions(RAGModel):
    method: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    semantic_top_k: int = Field(default=12, ge=1, le=100)
    keyword_top_k: int = Field(default=12, ge=1, le=100)
    final_top_k: int = Field(default=5, ge=1, le=100)
    rrf_constant: int = Field(default=60, ge=1, le=1000)
    min_similarity: float = Field(default=0.15, ge=-1, le=1)
    filters: SearchFilter = Field(default_factory=SearchFilter)
    enable_reranking: bool = False


class SearchRequest(RAGModel):
    question: NonBlank
    options: RetrievalOptions | None = None

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class SearchHit(RAGModel):
    chunk: Chunk
    score: float
    rank: int
    methods: list[str]
    ranking: dict[str, float] = Field(default_factory=dict)


class SearchResponse(RAGModel):
    hits: list[SearchHit]
    score_note: str = "Ranking scores and cosine similarity are not calibrated answer confidence."


class IngestionResponse(RAGModel):
    document: DocumentSummary
    status: Literal["created", "unchanged", "replaced"]
    extraction_warnings: list[str] = Field(default_factory=list)


class GenerationOptions(RAGModel):
    temperature: float = Field(default=0, ge=0, le=2)
    max_tokens: int = Field(default=1000, ge=1, le=4000)


class AskRequest(SearchRequest):
    generation: GenerationOptions = Field(default_factory=GenerationOptions)


class Citation(RAGModel):
    citation_id: str
    chunk_id: str
    document_id: str
    filename: str
    document_version: str | None
    requirement_id: str | None
    section: str | None
    location: SourceLocation
    quote: str


class AnswerResponse(RAGModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    referenced_requirement_ids: list[str] = Field(default_factory=list)
    evidence_status: Literal[
        "cited",
        "insufficient",
        "invalid_citations",
        "stale_evidence",
        "unsupported_claims",
        "conflicting_evidence",
    ]
    claim_status: Literal["unverified"] = "unverified"
    engineering_validation: Literal["not_performed"] = "not_performed"
    reference_validation: Literal["bounded", "unsupported_identifier_grammar"] = "bounded"
    explanation: str | None = None
    model: str | None = None


class ModelAnswer(RAGModel):
    """Provider output uses context labels, never provider-supplied source metadata."""

    answer: Annotated[str, Field(min_length=1, max_length=20_000)]
    citation_ids: list[str] = Field(max_length=100)
    referenced_requirement_ids: list[str] = Field(default_factory=list, max_length=100)
    insufficient_evidence: bool = False
