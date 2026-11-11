from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ee_arch_copilot.rag.models import RetrievalOptions

DEFAULT_REQUIREMENT_PATTERN = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    embedding_provider: Literal["hash", "openai_compatible"] = "hash"
    embedding_model: str = "hash-token-v1"
    embedding_dimension: int = Field(default=384, ge=32, le=8192)
    embedding_base_url: str = "http://localhost:11434/v1"
    embedding_api_key: SecretStr | None = Field(default=None, repr=False)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    vector_db_path: Path = Path("data/vector_db")
    llm_provider: Literal["none", "openai_compatible"] = "none"
    llm_model: str = ""
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    provider_timeout_seconds: float = Field(default=30, gt=0, le=300)
    retrieval_top_k: int = Field(default=5, ge=1, le=100)
    semantic_top_k: int = Field(default=12, ge=1, le=100)
    keyword_top_k: int = Field(default=12, ge=1, le=100)
    rrf_constant: int = Field(default=60, ge=1, le=1000)
    min_similarity: float = Field(default=0.15, ge=-1, le=1)
    enable_reranking: bool = False
    requirement_id_pattern: str = DEFAULT_REQUIREMENT_PATTERN
    chunk_size: int = Field(default=1000, ge=100, le=8000)
    chunk_overlap: int = Field(default=120, ge=0)
    max_request_bytes: int = Field(default=1_100_000, ge=1000, le=10_000_000)
    agent_provider: Literal["none", "openai_compatible"] = "none"
    agent_model: str = ""
    agent_max_iterations: int = Field(default=6, ge=1, le=20)
    agent_max_tool_calls: int = Field(default=10, ge=1, le=50)
    agent_timeout_seconds: float = Field(default=60, gt=0, le=300)
    agent_tool_timeout_seconds: float = Field(default=10, gt=0, le=60)
    agent_max_tool_result_bytes: int = Field(default=16_384, ge=512, le=65_536)
    agent_max_argument_bytes: int = Field(default=4096, ge=128, le=16_384)
    agent_max_context_bytes: int = Field(default=131_072, ge=4096, le=1_000_000)
    agent_max_provider_response_bytes: int = Field(default=262_144, ge=1024, le=1_000_000)
    agent_enable_tracing: bool = True
    agent_max_output_tokens: int = Field(default=2000, ge=1, le=16_000)
    agent_input_usd_per_million_tokens: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    agent_output_usd_per_million_tokens: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )

    @field_validator("requirement_id_pattern")
    @classmethod
    def valid_pattern(cls, value: str) -> str:
        pattern = re.compile(value)
        if pattern.match(""):
            raise ValueError("requirement pattern must not match empty text")
        return value

    @model_validator(mode="after")
    def chunk_bounds(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if (self.agent_input_usd_per_million_tokens is None) != (
            self.agent_output_usd_per_million_tokens is None
        ):
            raise ValueError("Configure both agent token prices or neither")
        return self

    def retrieval_options(self) -> RetrievalOptions:
        return RetrievalOptions(
            semantic_top_k=self.semantic_top_k,
            keyword_top_k=self.keyword_top_k,
            final_top_k=self.retrieval_top_k,
            rrf_constant=self.rrf_constant,
            min_similarity=self.min_similarity,
            enable_reranking=self.enable_reranking,
        )
