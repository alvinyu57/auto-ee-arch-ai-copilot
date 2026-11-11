import re

from ee_arch_copilot.core.settings import DEFAULT_REQUIREMENT_PATTERN
from ee_arch_copilot.rag.generation.guards import VERIFICATION_CLAIM, conflicting_source_indices
from ee_arch_copilot.rag.identifiers import IDENTIFIER_HINT, mentioned_identifiers
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
    conflicts = conflicting_source_indices(chunks)
    if conflicts:
        conflicted_chunks = [chunks[index] for index in conflicts]
        return AnswerResponse(
            answer="Potentially conflicting requirements require engineering review:\n"
            + "\n".join(f"{chunks[index].text} [S{index + 1}]" for index in conflicts),
            citations=[citation(f"S{index + 1}", chunks[index]) for index in conflicts],
            referenced_requirement_ids=sorted(
                {
                    chunk.requirement_id
                    for chunk in conflicted_chunks
                    if chunk.requirement_id is not None
                }
            ),
            evidence_status="conflicting_evidence",
            model=model,
            explanation="Equal statement templates contain different quantities in equal units. "
            "Applicability and precedence require engineering review; general conflict detection "
            "is not implemented.",
        )
    if response.insufficient_evidence:
        return insufficient_response(model)
    sources = {f"S{index}": chunk for index, chunk in enumerate(chunks, 1)}
    labels = list(dict.fromkeys(response.citation_ids))
    inline = re.findall(r"\[(S[^\]\s]*)\]", response.answer)
    valid_labels = bool(labels) and set(labels) <= sources.keys() and set(inline) == set(labels)
    cited = [sources[label] for label in labels if label in sources]
    actual_ids = {chunk.requirement_id for chunk in cited if chunk.requirement_id}
    mentioned_ids = mentioned_identifiers(response.answer, requirement_pattern, actual_ids)
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
    if VERIFICATION_CLAIM.search(response.answer):
        return AnswerResponse(
            answer="Generated verification claims were withheld. Run the deterministic validation "
            "tools and review their findings separately.",
            evidence_status="unsupported_claims",
            model=model,
            explanation="Phase 2 has no deterministic validation evidence. Citation membership "
            "cannot establish architecture compliance or passing checks.",
        )
    citations = [citation(label, sources[label]) for label in labels]
    unsupported_grammar = any(
        not re.fullmatch(requirement_pattern, identifier)
        and not IDENTIFIER_HINT.fullmatch(identifier)
        for identifier in actual_ids
    )
    return AnswerResponse(
        answer=response.answer,
        citations=citations,
        referenced_requirement_ids=sorted(actual_ids),
        evidence_status="cited",
        model=model,
        reference_validation="unsupported_identifier_grammar" if unsupported_grammar else "bounded",
        explanation="Source references passed bounded identifier checks. Claims remain unverified; "
        "semantic support, evidence sufficiency, and general conflict detection are not proven. "
        "Engineering validation was not performed."
        + (
            " Some source IDs use unsupported prose identifier grammars; only known spellings "
            "and declared references can be checked for those IDs."
            if unsupported_grammar
            else ""
        ),
    )


def citation(label: str, chunk: Chunk) -> Citation:
    return Citation(
        citation_id=label,
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        filename=chunk.filename,
        document_version=chunk.document_version,
        requirement_id=chunk.requirement_id,
        section=chunk.section,
        location=chunk.location,
        quote=chunk.text,
    )
