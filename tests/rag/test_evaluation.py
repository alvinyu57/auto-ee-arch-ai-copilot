import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.evaluation.metrics import answer_checks, retrieval_metrics
from ee_arch_copilot.rag.evaluation.run import EvaluationItem, evaluate, main
from ee_arch_copilot.rag.ingestion.loader import load_file
from ee_arch_copilot.rag.models import AskRequest, RetrievalOptions
from ee_arch_copilot.rag.service import KnowledgeService
from tests.rag.conftest import ControlledLLM

DATA = Path(__file__).resolve().parents[2] / "data"


def test_metrics_known_rankings() -> None:
    metrics = retrieval_metrics(["wrong", "a", "a", "b"], {"a", "b", "c"}, 3)
    assert metrics.recall_at_k == pytest.approx(2 / 3)
    assert metrics.precision_at_k == pytest.approx(2 / 3)
    assert metrics.mrr == 0.5
    assert retrieval_metrics([], {"a"}, 5).mrr == 0
    with pytest.raises(ValueError):
        retrieval_metrics([], set(), 5)
    with pytest.raises(ValueError):
        retrieval_metrics([], {"a"}, 0)


def test_golden_corpus_end_to_end(tmp_path: Path) -> None:
    service = KnowledgeService(Settings(vector_db_path=tmp_path), llm_provider=ControlledLLM())
    for path in sorted((DATA / "knowledge" / "synthetic").glob("*.md")):
        service.ingest(load_file(path, document_id=path.stem, version="1.0"))
    assert len(service.store.documents()) == 4
    items = [
        EvaluationItem.model_validate(item)
        for item in json.loads((DATA / "evaluation" / "retrieval_dataset.json").read_text())
    ]
    report = evaluate(service, items, RetrievalOptions())
    assert report.dataset_size >= 20
    assert report.metrics.recall_at_k >= 0.8
    assert report.metrics.mrr >= 0.8
    assert report.recall_at_1 <= report.recall_at_3 <= report.recall_at_5
    assert report.exact_id_queries == 5
    assert report.exact_requirement_id_hit_at_1 == 1
    assert report.no_answer_abstention_rate == 1
    for case in json.loads((DATA / "evaluation" / "qa_dataset.json").read_text()):
        answer = service.ask(AskRequest(question=case["question"]))
        if case["no_answer"]:
            assert answer.evidence_status == "insufficient"
        else:
            assert answer.evidence_status == "cited"
            assert set(answer.referenced_requirement_ids) <= set(case["expected_requirement_ids"])
            assert all(
                service.store.get_chunk(citation.chunk_id) is not None
                for citation in answer.citations
            )
    # Test provider merely quotes evidence. This does not score semantic faithfulness.


def test_evaluation_failure_and_abstention_paths(indexed: KnowledgeService) -> None:
    items = [
        EvaluationItem(
            query_id="missing",
            question="REQ-OTHER-001",
            expected_requirement_ids=["REQ-OTHER-001"],
            expected_source_documents=["other"],
        ),
        EvaluationItem(
            query_id="wrong-source",
            question="REQ-ETH-001",
            expected_requirement_ids=["REQ-ETH-001"],
            expected_source_documents=["other"],
        ),
        EvaluationItem(query_id="false-positive", question="gateway", no_answer=True),
    ]
    report = evaluate(indexed, items, RetrievalOptions())
    assert report.failed_queries == [item.query_id for item in items]
    assert report.metrics.recall_at_k == 0
    assert report.no_answer_abstention_rate == 0
    assert report.recall_at_1 == report.recall_at_3 == report.recall_at_5 == 0
    assert report.precision_at_3 == report.mrr_within_5 == 0
    with pytest.raises(ValueError):
        evaluate(indexed, [items[-1]], RetrievalOptions())
    chunk = indexed.store.chunks()[0]
    chunk_report = evaluate(
        indexed,
        [
            EvaluationItem(
                query_id="chunk",
                question=chunk.requirement_id or "gateway",
                expected_chunk_ids=[chunk.chunk_id],
                expected_source_documents=[chunk.document_id],
            )
        ],
        RetrievalOptions(),
    )
    assert chunk_report.metrics.recall_at_k == 1
    assert chunk_report.no_answer_abstention_rate is None
    with pytest.raises(ValidationError):
        EvaluationItem(query_id="bad", question="bad")


def test_answer_checks(indexed: KnowledgeService) -> None:
    answer = indexed.ask(AskRequest(question="REQ-ETH-001"))
    checks = answer_checks(
        answer, {chunk.chunk_id for chunk in indexed.store.chunks()}, {"REQ-ETH-001"}
    )
    assert checks["citation_validity"] and checks["referenced_requirements_correct"]
    assert not answer_checks(answer, set(), set())["citation_validity"]
    assert not answer_checks(answer, set(), set())["referenced_requirements_correct"]


def test_evaluation_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "evaluation.json"
    monkeypatch.setattr("sys.argv", ["evaluate", "--output", str(output)])
    main()
    assert json.loads(output.read_text())["dataset_size"] == 24


def test_typed_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVAL_TOP_K", "7")
    monkeypatch.setenv("ENABLE_RERANKING", "true")
    assert Settings().retrieval_options().final_top_k == 7
    assert Settings().enable_reranking
    with pytest.raises(ValidationError):
        Settings(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValidationError):
        Settings(requirement_id_pattern=".*")
