import math
from collections import Counter

from ee_arch_copilot.rag.models import Chunk
from ee_arch_copilot.rag.tokenization import tokenize


def searchable_text(chunk: Chunk) -> str:
    return "\n".join(filter(None, (chunk.requirement_id, chunk.section, chunk.text)))


class KeywordRetriever:
    """BM25 over a bounded local corpus, with an exact requirement-ID boost."""

    def search(self, question: str, chunks: list[Chunk], top_k: int) -> list[tuple[Chunk, float]]:
        query = set(tokenize(question))
        if not query or not chunks:
            return []
        terms = [Counter(tokenize(searchable_text(chunk))) for chunk in chunks]
        frequencies = Counter(term for counts in terms for term in counts)
        average_length = sum(sum(counts.values()) for counts in terms) / len(chunks) or 1
        hits = []
        for chunk, counts in zip(chunks, terms, strict=True):
            length = sum(counts.values())
            score = 0.0
            for term in query.intersection(counts):
                idf = math.log(
                    1 + (len(chunks) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                tf = counts[term]
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / average_length))
            if chunk.requirement_id and chunk.requirement_id.casefold() in query:
                score += 100.0
            if score > 0:
                hits.append((chunk, score))
        return sorted(hits, key=lambda hit: (-hit[1], hit[0].chunk_id))[:top_k]
