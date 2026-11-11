import pytest

from ee_arch_copilot.rag.generation.citations import validate_answer
from ee_arch_copilot.rag.models import ModelAnswer
from ee_arch_copilot.rag.service import KnowledgeService


@pytest.mark.parametrize(
    ("answer", "labels", "ids"),
    [
        ("Fake [S99]", ["S99"], []),
        ("No citation", [], []),
        ("Mismatched [S2]", ["S1"], []),
        ("Missing inline", ["S1"], []),
        ("REQ-INVENTED-999 [S1]", ["S1"], ["REQ-INVENTED-999"]),
        ("Fabricated REQ-INVENTED-999 [S1]", ["S1"], []),
    ],
)
def test_reject_fabrication(
    indexed: KnowledgeService, answer: str, labels: list[str], ids: list[str]
) -> None:
    result = validate_answer(
        ModelAnswer(answer=answer, citation_ids=labels, referenced_requirement_ids=ids),
        indexed.store.chunks(),
        "test",
    )
    assert result.evidence_status == "invalid_citations"
    assert result.citations == [] and result.referenced_requirement_ids == []
    assert "Fake" not in result.answer


def test_declared_insufficient_drops_generated_claim(indexed: KnowledgeService) -> None:
    result = validate_answer(
        ModelAnswer(answer="Invented answer", citation_ids=["S99"], insufficient_evidence=True),
        indexed.store.chunks(),
        "test",
    )
    assert result.evidence_status == "insufficient"
    assert "Invented" not in result.answer and result.citations == []


def test_custom_requirement_pattern_and_duplicate_citations(indexed: KnowledgeService) -> None:
    chunk = indexed.store.chunks()[0].model_copy(update={"requirement_id": "CUSTOM_42"})
    good = ModelAnswer(answer="CUSTOM_42 [S1]", citation_ids=["S1", "S1"])
    result = validate_answer(good, [chunk], "test", r"CUSTOM_\d+")
    assert result.evidence_status == "cited" and len(result.citations) == 1
    assert result.referenced_requirement_ids == ["CUSTOM_42"]
    bad = good.model_copy(update={"answer": "CUSTOM_99 [S1]"})
    assert (
        validate_answer(bad, [chunk], "test", r"CUSTOM_\d+").evidence_status == "invalid_citations"
    )
