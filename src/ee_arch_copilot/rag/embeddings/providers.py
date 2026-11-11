import hashlib
import math
from collections import Counter

import httpx

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.embeddings.base import EmbeddingProvider, validate_vectors
from ee_arch_copilot.rag.errors import ConfigurationError, ProviderError
from ee_arch_copilot.rag.providers import post_json
from ee_arch_copilot.rag.tokenization import tokenize


class HashEmbeddingProvider:
    """Offline signed token hashing baseline, not a learned semantic language model."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.identity = f"hash:hash-token-v1:{dimension}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token, count in Counter(tokenize(text)).items():
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4]) % self.dimension] += (1 if digest[4] % 2 else -1) * (
                1 + math.log(count)
            )
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class CompatibleEmbeddingProvider:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings, self.transport = settings, transport
        self.dimension = settings.embedding_dimension
        origin = hashlib.sha256(settings.embedding_base_url.encode()).hexdigest()[:16]
        self.identity = f"openai_compatible:{origin}:{settings.embedding_model}:{self.dimension}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        size = self.settings.embedding_batch_size
        for offset in range(0, len(texts), size):
            batch = texts[offset : offset + size]
            data = post_json(
                self.settings.embedding_base_url,
                "/embeddings",
                {"model": self.settings.embedding_model, "input": list(batch)},
                self.settings.embedding_api_key,
                self.settings.provider_timeout_seconds,
                self.transport,
            )
            try:
                items = data["data"]
                if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                    raise ValueError("Invalid data")
                rows = [item for item in items if isinstance(item, dict)]
                indices = [row["index"] for row in rows]
                if not all(isinstance(index, int) for index in indices):
                    raise ValueError("Invalid embedding index type")
                if sorted(index for index in indices if isinstance(index, int)) != list(
                    range(len(batch))
                ):
                    raise ValueError("Invalid embedding indices")
                ordered = sorted(rows, key=lambda row: int(str(row["index"])))
                batch_vectors = []
                for row in ordered:
                    values = row["embedding"]
                    if not isinstance(values, list):
                        raise ValueError("Invalid vector")
                    batch_vectors.append([float(str(value)) for value in values])
                validate_vectors(batch_vectors, len(batch), self.dimension)
                vectors.extend(batch_vectors)
            except (KeyError, ValueError, TypeError) as error:
                raise ProviderError("Embedding provider returned malformed vectors") from error
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "hash":
        if settings.embedding_model != "hash-token-v1":
            raise ConfigurationError("Hash provider requires EMBEDDING_MODEL=hash-token-v1")
        return HashEmbeddingProvider(settings.embedding_dimension)
    if not settings.embedding_model or settings.embedding_model == "hash-token-v1":
        raise ConfigurationError("Configure EMBEDDING_MODEL for the compatible embedding server")
    return CompatibleEmbeddingProvider(settings)
