"""Offline remediation evidence; controlled generation is not a production fallback.

uv run --no-sync python scripts/evaluate_phase2_remediation.py --output /tmp/remediation.json
"""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Literal

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.evaluation.run import EvaluationItem, evaluate
from ee_arch_copilot.rag.generation.citations import validate_answer
from ee_arch_copilot.rag.ingestion.loader import load_file
from ee_arch_copilot.rag.models import (
    AskRequest,
    Chunk,
    GenerationOptions,
    ModelAnswer,
    RetrievalOptions,
)
from ee_arch_copilot.rag.service import KnowledgeService


class ExcerptOnlyProvider:
    """Test instrument: quotes evidence without attempting to answer or judge claims."""

    model = "controlled-excerpt-only"

    def generate(self, question: str, chunks: list[Chunk], options: GenerationOptions) -> str:
        return json.dumps({"answer": chunks[0].text + " [S1]", "citation_ids": ["S1"]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/remediation.json"))
    args = parser.parse_args()
    dataset_path = Path("data/evaluation/retrieval_dataset.json")
    qa_path = Path("data/evaluation/qa_dataset.json")
    dataset_bytes = dataset_path.read_bytes()
    items = [EvaluationItem.model_validate(item) for item in json.loads(dataset_bytes)]
    qa_items = json.loads(qa_path.read_bytes())
    reports = {}
    baselines = {}
    cases = []
    rejected_cases = []
    emitted_citations = 0
    invalid_citations = 0
    no_evidence_correct = 0
    no_evidence_cases = 0
    with tempfile.TemporaryDirectory(prefix="ee-remediation-eval-") as directory:
        settings = Settings(
            vector_db_path=Path(directory),
            embedding_provider="hash",
            embedding_model="hash-token-v1",
            embedding_dimension=384,
            llm_provider="none",
        )
        service = KnowledgeService(settings, llm_provider=ExcerptOnlyProvider())
        for path in sorted(Path("data/knowledge/synthetic").glob("*.md")):
            service.ingest(load_file(path, document_id=path.stem, version="1.0"))
        methods: tuple[Literal["keyword", "semantic", "hybrid"], ...] = (
            "keyword",
            "semantic",
            "hybrid",
        )
        for method in methods:
            options = RetrievalOptions(method=method)
            report = evaluate(service, items, options)
            report.dataset_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
            reports[method] = report.model_dump(mode="json")
            baseline = json.loads(Path(f"docs/reviews/phase2-retrieval-{method}.json").read_text())
            assert baseline["corpus_hashes"] == report.corpus_hashes
            assert baseline["dataset_size"] == report.dataset_size
            baselines[method] = {
                "source": f"docs/reviews/phase2-retrieval-{method}.json",
                "metrics": baseline["metrics"],
                "no_answer_abstention_rate": baseline["no_answer_abstention_rate"],
                "corpus_hashes_match": True,
            }
            # Recompute extra baseline cutoffs from saved rankings independently
            # of the new metric functions. Golden corpus IDs are unique.
            saved = {entry["query_id"]: entry for entry in baseline["results"]}
            positives = [item for item in items if not item.no_answer]
            for cutoff in (1, 3, 5):
                baselines[method][f"recall_at_{cutoff}"] = sum(
                    len(
                        set(saved[item.query_id]["retrieved_ids"][:cutoff])
                        & set(item.expected_requirement_ids)
                    )
                    / len(item.expected_requirement_ids)
                    for item in positives
                ) / len(positives)
            baselines[method]["precision_at_3"] = sum(
                len(
                    set(saved[item.query_id]["retrieved_ids"][:3])
                    & set(item.expected_requirement_ids)
                )
                / 3
                for item in positives
            ) / len(positives)
            exact = [item for item in positives if item.question in item.expected_requirement_ids]
            baselines[method]["exact_id_queries"] = len(exact)
            baselines[method]["exact_requirement_id_hit_at_1"] = sum(
                bool(saved[item.query_id]["retrieved_ids"])
                and saved[item.query_id]["retrieved_ids"][0] in item.expected_requirement_ids
                for item in exact
            ) / len(exact)
            for case in qa_items:
                hits = service.search(case["question"], options).hits
                allowed = {hit.chunk.chunk_id for hit in hits}
                answer = service.ask(AskRequest(question=case["question"], options=options))
                if case["no_answer"]:
                    no_evidence_cases += 1
                    correct = answer.evidence_status == "insufficient" and not answer.citations
                    no_evidence_correct += correct
                    assert correct
                else:
                    assert answer.evidence_status == "cited"
                    assert set(answer.referenced_requirement_ids) <= set(
                        case["expected_requirement_ids"]
                    )
                for citation in answer.citations:
                    emitted_citations += 1
                    current = service.store.get_chunk(citation.chunk_id)
                    valid = (
                        current is not None
                        and current.chunk_id in allowed
                        and current.document_id == citation.document_id
                        and current.document_version == citation.document_version
                        and current.requirement_id == citation.requirement_id
                        and current.location == citation.location
                        and current.text == citation.quote
                    )
                    invalid_citations += not valid
                    assert valid
                cases.append(
                    {
                        "method": method,
                        "query_id": case["query_id"],
                        "context_chunk_ids": sorted(allowed),
                        "response": answer.model_dump(mode="json"),
                    }
                )
            context = [service.search("REQ-ETH-001", options).hits[0].chunk]
            for text, label, expected in (
                ("Invented [S99]", "S99", "invalid_citations"),
                ("REQ-FAKE-999 [S1]", "S1", "invalid_citations"),
                ("req-eth-999 [S1]", "S1", "invalid_citations"),
                ("custom:999 [S1]", "S1", "invalid_citations"),
                ("All architecture checks passed. [S1]", "S1", "unsupported_claims"),
                (
                    "The architecture meets all TSN latency requirements. [S1]",
                    "S1",
                    "unsupported_claims",
                ),
            ):
                answer = validate_answer(
                    ModelAnswer(answer=text, citation_ids=[label]),
                    context,
                    "controlled-adversarial",
                )
                assert answer.evidence_status == expected and not answer.citations
                rejected_cases.append(
                    {"method": method, "input": text, "response": answer.model_dump(mode="json")}
                )
        output = {
            "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "qa_dataset_sha256": hashlib.sha256(qa_path.read_bytes()).hexdigest(),
            "live_embedding_tested": False,
            "live_llm_tested": False,
            "baselines": baselines,
            "retrieval": reports,
            "controlled_generation": {
                "model": ExcerptOnlyProvider.model,
                "cases": cases,
                "rejected_cases": rejected_cases,
                "emitted_citations": emitted_citations,
                "invalid_citations": invalid_citations,
                "invalid_citation_rate": invalid_citations / emitted_citations,
                "no_evidence_cases": no_evidence_cases,
                "no_evidence_correct": no_evidence_correct,
                "no_evidence_accuracy": no_evidence_correct / no_evidence_cases,
                "limitations": [
                    "Excerpt-only provider tests source plumbing, "
                    "not answer quality or entailment.",
                    "No-evidence cases cover the two original golden negatives "
                    "in each retrieval mode.",
                    "Nonempty but insufficient evidence still requires "
                    "model judgment and human review.",
                ],
            },
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Saved remediation evidence: {args.output}")
    for method, result in reports.items():
        print(
            method,
            json.dumps(
                {
                    key: result[key]
                    for key in (
                        "recall_at_1",
                        "recall_at_3",
                        "recall_at_5",
                        "precision_at_3",
                        "mrr_within_5",
                        "exact_requirement_id_hit_at_1",
                        "failed_queries",
                    )
                }
            ),
        )
    print(
        f"Invalid citations: {invalid_citations}/{emitted_citations}; "
        f"no-evidence handling: {no_evidence_correct}/{no_evidence_cases}"
    )


if __name__ == "__main__":
    main()
