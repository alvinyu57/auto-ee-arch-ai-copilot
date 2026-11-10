from typing import Protocol

from ee_arch_copilot.rag.models import SearchHit
from ee_arch_copilot.rag.tokenization import tokenize


class Reranker(Protocol):
    def rerank(self, question: str, hits: list[SearchHit]) -> list[SearchHit]: ...


class TokenOverlapReranker:
    """Optional offline lexical heuristic; not a learned relevance model."""

    def rerank(self, question: str, hits: list[SearchHit]) -> list[SearchHit]:
        query = set(tokenize(question))
        for hit in hits:
            overlap = len(query.intersection(tokenize(hit.chunk.text))) / max(1, len(query))
            hit.ranking["reranker_overlap"] = overlap
        return sorted(
            hits, key=lambda hit: (-hit.ranking["reranker_overlap"], -hit.score, hit.chunk.chunk_id)
        )
