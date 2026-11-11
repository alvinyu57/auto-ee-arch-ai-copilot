import math
from typing import Protocol

from ee_arch_copilot.rag.errors import ProviderError


class EmbeddingProvider(Protocol):
    @property
    def identity(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def validate_vectors(vectors: list[list[float]], count: int, dimension: int) -> None:
    if len(vectors) != count:
        raise ProviderError("Embedding provider returned the wrong number of vectors")
    for vector in vectors:
        if (
            len(vector) != dimension
            or not all(math.isfinite(v) for v in vector)
            or sum(v * v for v in vector) == 0
        ):
            raise ProviderError("Embedding provider returned an invalid vector or dimension")
