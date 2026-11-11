from ee_arch_copilot.rag.models import AnswerResponse, RAGModel


class RetrievalMetrics(RAGModel):
    recall_at_k: float
    precision_at_k: float
    mrr: float


def retrieval_metrics(retrieved: list[str], relevant: set[str], k: int) -> RetrievalMetrics:
    """Unique requirement/chunk units. No-answer cases have a separate abstention measure."""
    if not relevant or k < 1:
        raise ValueError("Use answerable queries and k >= 1 for ranking metrics")
    ranked = list(dict.fromkeys(retrieved))[:k]
    matches = len(set(ranked) & relevant)
    reciprocal = next((1 / rank for rank, item in enumerate(ranked, 1) if item in relevant), 0.0)
    return RetrievalMetrics(
        recall_at_k=matches / len(relevant), precision_at_k=matches / k, mrr=reciprocal
    )


def answer_checks(
    answer: AnswerResponse, allowed_chunk_ids: set[str], expected_ids: set[str]
) -> dict[str, bool]:
    """Structural checks only. Unsupported natural-language claims need human adjudication."""
    return {
        "citation_validity": bool(answer.citations)
        and all(citation.chunk_id in allowed_chunk_ids for citation in answer.citations),
        "referenced_requirements_correct": set(answer.referenced_requirement_ids) <= expected_ids,
        "insufficient_evidence": answer.evidence_status == "insufficient",
    }
