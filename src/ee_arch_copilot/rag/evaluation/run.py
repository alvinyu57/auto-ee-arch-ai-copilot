"""uv run python -m ee_arch_copilot.rag.evaluation.run --output /tmp/rag-evaluation.json"""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from pydantic import Field, model_validator

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.evaluation.metrics import RetrievalMetrics, retrieval_metrics
from ee_arch_copilot.rag.ingestion.loader import load_file
from ee_arch_copilot.rag.models import RAGModel, RetrievalOptions
from ee_arch_copilot.rag.service import KnowledgeService


class EvaluationItem(RAGModel):
    query_id: str
    question: str
    expected_requirement_ids: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_source_documents: list[str] = Field(default_factory=list)
    no_answer: bool = False

    @model_validator(mode="after")
    def label_consistency(self) -> "EvaluationItem":
        has_evidence = bool(self.expected_requirement_ids or self.expected_chunk_ids)
        if has_evidence == self.no_answer or (has_evidence and not self.expected_source_documents):
            raise ValueError(
                "Answerable queries need IDs and documents; no-answer queries need none"
            )
        return self


class QueryResult(RAGModel):
    query_id: str
    retrieved_ids: list[str]
    retrieved_documents: list[str]
    metrics: RetrievalMetrics | None = None
    abstained: bool | None = None
    missing_expected_documents: list[str] = Field(default_factory=list)


class EvaluationReport(RAGModel):
    dataset_sha256: str | None = None
    dataset_size: int
    answerable_queries: int
    no_answer_queries: int
    options: RetrievalOptions
    embedding_provider: str
    corpus_hashes: dict[str, str]
    metrics: RetrievalMetrics
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_3: float
    mrr_within_5: float
    exact_id_queries: int
    exact_requirement_id_hit_at_1: float | None
    no_answer_abstention_rate: float | None
    results: list[QueryResult]
    failed_queries: list[str]
    limitations: list[str]


def evaluate(
    service: KnowledgeService, items: list[EvaluationItem], options: RetrievalOptions
) -> EvaluationReport:
    results = []
    failures = []
    fixed_metrics: dict[int, list[RetrievalMetrics]] = {1: [], 3: [], 5: []}
    exact_hits: list[bool] = []
    for item in items:
        hits = service.search(item.question, options).hits
        retrieved = list(
            dict.fromkeys(
                (
                    hit.chunk.chunk_id
                    if item.expected_chunk_ids
                    else hit.chunk.requirement_id or hit.chunk.chunk_id
                )
                for hit in hits
            )
        )
        documents = sorted({hit.chunk.document_id for hit in hits})
        result = QueryResult(
            query_id=item.query_id, retrieved_ids=retrieved, retrieved_documents=documents
        )
        if item.no_answer:
            result.abstained = not hits
            if hits:
                failures.append(item.query_id)
        else:
            expected = set(item.expected_chunk_ids or item.expected_requirement_ids)
            # Wrong-source matches do not earn relevance credit even if an ID was reused.
            ranked = list(
                dict.fromkeys(
                    (
                        (
                            hit.chunk.chunk_id
                            if item.expected_chunk_ids
                            else hit.chunk.requirement_id or hit.chunk.chunk_id
                        )
                        if hit.chunk.document_id in item.expected_source_documents
                        else f"wrong-source:{hit.chunk.chunk_id}"
                    )
                    for hit in hits
                )
            )
            result.metrics = retrieval_metrics(ranked, expected, options.final_top_k)
            for cutoff in fixed_metrics:
                fixed_metrics[cutoff].append(retrieval_metrics(ranked, expected, cutoff))
            if re.fullmatch(service.settings.requirement_id_pattern, item.question.strip(), re.I):
                exact_hits.append(bool(ranked) and ranked[0] in expected)
            result.missing_expected_documents = sorted(
                set(item.expected_source_documents) - set(documents)
            )
            if result.metrics.recall_at_k < 1 or result.missing_expected_documents:
                failures.append(item.query_id)
        results.append(result)
    metrics = [result.metrics for result in results if result.metrics is not None]
    if not metrics:
        raise ValueError("Evaluation requires at least one answerable query")
    no_answers = [result.abstained for result in results if result.abstained is not None]
    return EvaluationReport(
        dataset_size=len(items),
        answerable_queries=len(metrics),
        no_answer_queries=len(no_answers),
        options=options,
        embedding_provider=service.embeddings.identity,
        corpus_hashes={
            document.document_id: document.content_hash for document in service.store.documents()
        },
        metrics=RetrievalMetrics(
            recall_at_k=sum(item.recall_at_k for item in metrics) / len(metrics),
            precision_at_k=sum(item.precision_at_k for item in metrics) / len(metrics),
            mrr=sum(item.mrr for item in metrics) / len(metrics),
        ),
        recall_at_1=sum(item.recall_at_k for item in fixed_metrics[1]) / len(metrics),
        recall_at_3=sum(item.recall_at_k for item in fixed_metrics[3]) / len(metrics),
        recall_at_5=sum(item.recall_at_k for item in fixed_metrics[5]) / len(metrics),
        precision_at_3=sum(item.precision_at_k for item in fixed_metrics[3]) / len(metrics),
        mrr_within_5=sum(item.mrr for item in fixed_metrics[5]) / len(metrics),
        exact_id_queries=len(exact_hits),
        exact_requirement_id_hit_at_1=sum(exact_hits) / len(exact_hits) if exact_hits else None,
        no_answer_abstention_rate=sum(no_answers) / len(no_answers) if no_answers else None,
        results=results,
        failed_queries=failures,
        limitations=[
            "Small synthetic corpus; scores do not establish production retrieval quality.",
            "Hash embeddings are a lexical vector baseline, not learned semantic understanding.",
            "No-answer abstention depends on thresholds; similarity is not answer confidence.",
            "Citation checks do not measure unsupported claims or semantic faithfulness.",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic requirements retrieval without LLM calls"
    )
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/rag-evaluation.json"))
    parser.add_argument("--method", choices=["semantic", "keyword", "hybrid"], default="hybrid")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ee-rag-eval-") as directory:
        settings = Settings(vector_db_path=Path(directory), llm_provider="none")
        service = KnowledgeService(settings)
        for path in sorted((args.data / "knowledge" / "synthetic").glob("*.md")):
            service.ingest(load_file(path, document_id=path.stem, version="1.0"))
        dataset = (args.data / "evaluation" / "retrieval_dataset.json").read_bytes()
        items = [EvaluationItem.model_validate(item) for item in json.loads(dataset)]
        options = settings.retrieval_options().model_copy(update={"method": args.method})
        report = evaluate(service, items, options)
        report.dataset_sha256 = hashlib.sha256(dataset).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.model_dump_json(indent=2) + "\n")
        print(report.metrics.model_dump_json())
        print(
            f"Queries: {report.dataset_size}; "
            f"no-answer abstention: {report.no_answer_abstention_rate}"
        )
        print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
