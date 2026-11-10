from ee_arch_copilot.rag.embeddings.base import EmbeddingProvider
from ee_arch_copilot.rag.models import Chunk, RetrievalOptions
from ee_arch_copilot.rag.storage.chroma_store import ChromaStore


class SemanticRetriever:
    def __init__(self, provider: EmbeddingProvider, store: ChromaStore) -> None:
        self.provider, self.store = provider, store

    def search(self, question: str, options: RetrievalOptions) -> list[tuple[Chunk, float]]:
        return self.store.search(
            self.provider.embed_query(question),
            options.semantic_top_k,
            options.filters,
            options.min_similarity,
        )
