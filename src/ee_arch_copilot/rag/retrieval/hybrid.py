from ee_arch_copilot.rag.models import Chunk, RetrievalOptions, SearchHit
from ee_arch_copilot.rag.retrieval.reranker import Reranker


def fuse(
    rankings: dict[str, list[tuple[Chunk, float]]],
    options: RetrievalOptions,
    question: str,
    reranker: Reranker | None = None,
) -> list[SearchHit]:
    combined: dict[str, SearchHit] = {}
    hybrid = options.method == "hybrid"
    for method, candidates in rankings.items():
        seen: set[str] = set()
        for rank, (chunk, score) in enumerate(candidates, 1):
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            contribution = 1 / (options.rrf_constant + rank) if hybrid else score
            if chunk.chunk_id not in combined:
                combined[chunk.chunk_id] = SearchHit(chunk=chunk, score=0, rank=0, methods=[])
            hit = combined[chunk.chunk_id]
            hit.score += contribution
            hit.methods.append(method)
            hit.ranking[f"{method}_score"] = score
            hit.ranking[f"{method}_rank"] = float(rank)
    hits = sorted(combined.values(), key=lambda hit: (-hit.score, hit.chunk.chunk_id))
    if options.enable_reranking and reranker is not None:
        hits = reranker.rerank(question, hits)
    hits = hits[: options.final_top_k]
    for rank, hit in enumerate(hits, 1):
        hit.rank = rank
    return hits
