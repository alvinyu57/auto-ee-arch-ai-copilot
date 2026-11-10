import re

from ee_arch_copilot.core.settings import DEFAULT_REQUIREMENT_PATTERN
from ee_arch_copilot.rag.models import AnswerResponse, Chunk, Citation, ModelAnswer


def insufficient_response(model: str | None = None) -> AnswerResponse:
    return AnswerResponse(
        answer="The answer cannot be determined from the indexed documents.",
        evidence_status="insufficient",
        explanation="No sufficient retrieved evidence supports an answer.",
        model=model,
    )


def validate_answer(
    response: ModelAnswer,
    chunks: list[Chunk],
    model: str,
    requirement_pattern: str = DEFAULT_REQUIREMENT_PATTERN,
) -> AnswerResponse:
    if response.insufficient_evidence:
        return insufficient_response(model)
    sources = {f"S{index}": chunk for index, chunk in enumerate(chunks, 1)}
    labels = list(dict.fromkeys(response.citation_ids))
    inline = re.findall(r"\[(S[^\]\s]*)\]", response.answer)
    valid_labels = bool(labels) and set(labels) <= sources.keys() and set(inline) == set(labels)
    cited = [sources[label] for label in labels if label in sources]
    actual_ids = {chunk.requirement_id for chunk in cited if chunk.requirement_id}
    mentioned_ids = {match.group(0) for match in re.finditer(requirement_pattern, response.answer)}
    valid_ids = (
        set(response.referenced_requirement_ids) <= actual_ids and mentioned_ids <= actual_ids
    )
    if not valid_labels or not valid_ids:
        return AnswerResponse(
            answer="The generated answer was rejected because citation validation failed.",
            evidence_status="invalid_citations",
            model=model,
            explanation="Citations and requirement references must resolve to retrieved chunks.",
        )
    citations = [
        Citation(
            citation_id=label,
            chunk_id=sources[label].chunk_id,
            document_id=sources[label].document_id,
            filename=sources[label].filename,
            document_version=sources[label].document_version,
            requirement_id=sources[label].requirement_id,
            section=sources[label].section,
            location=sources[label].location,
            quote=sources[label].text,
        )
        for label in labels
    ]
    return AnswerResponse(
        answer=response.answer,
        citations=citations,
        referenced_requirement_ids=sorted(actual_ids),
        evidence_status="cited",
        model=model,
        explanation="Source references validated; semantic support of every claim is not proven.",
    )
