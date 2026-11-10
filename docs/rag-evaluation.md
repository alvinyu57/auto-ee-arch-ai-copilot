# Requirements RAG evaluation

Measured on 2026-11-10 using Python 3.12.16, Chroma 1.5.9, and the checked-in
synthetic corpus. No external embedding or LLM API was used.

## Retrieval dataset and procedure

[The golden dataset](../data/evaluation/retrieval_dataset.json) contains **24 queries**:
22 answerable and two explicitly labeled no-evidence cases. Queries cover exact IDs,
natural-language engineering questions, SOME/IP-SD, IEEE 802.1AS/802.1Qbv, Ethernet PHY
names, VLAN numbers, hexadecimal identifiers, and evidence spanning requirements and
documents. Each item carries expected requirement/chunk IDs and expected source IDs.

The CLI creates a temporary database, ingests all four version-1.0 Markdown sources,
and calls retrieval without generation. The resulting corpus has **34 chunks**, of
which 30 have requirement IDs and four preserve document introductory text. Document
content hashes are recorded in each report. No tuning was performed to eliminate
the observed failed query.

Metrics use unique requirement IDs, or chunk IDs when explicitly labeled. Repeated
fragments of one requirement cannot earn repeated credit. Matches from an unexpected
source document do not count as relevant. Non-requirement chunks remain ranked
nonrelevant units. For each answerable query:

- Recall@K = retrieved relevant units / all expected relevant units.
- Precision@K = retrieved relevant units / K, including when fewer than K are returned.
- MRR = reciprocal rank of the first expected relevant unit, or zero if absent within K.

Reported values are macro averages over answerable queries. No-evidence cases are
excluded from these metrics and scored by **retrieval abstention rate**: the fraction
returning zero hits. A false positive returns nonempty retrieval for a no-evidence
case. This is not an evaluation of a model's no-answer judgment or a calibrated
confidence threshold. The evaluator also records missing expected source documents.

## Actual results

Configuration: `hash:hash-token-v1:384`, 1,000-character chunks, 120-character overlap,
semantic candidates 12, keyword candidates 12, final K 5, RRF constant 60,
minimum cosine similarity 0.15, reranking disabled, no metadata filters.

| Retrieval method | Recall@5 | Precision@5 | MRR within 5 | No-evidence abstention |
| --- | ---: | ---: | ---: | ---: |
| Keyword BM25 | 0.977273 | 0.281818 | 1.000000 | 2/2 (1.000000) |
| Semantic interface with hash vectors | 0.977273 | 0.281818 | 1.000000 | 2/2 (1.000000) |
| Hybrid RRF | 0.977273 | 0.281818 | 1.000000 | 2/2 (1.000000) |

These identical aggregate values do not establish a hybrid improvement. Hash vectors
share token features with BM25 and are not a learned semantic model. Precision is
also bounded by label sparsity and the fixed K denominator: an exact-ID query with
one expected result receives Precision@5 = 0.2 even when its only hit is correct.
Do not interpret MRR 1.0 as a complete retrieval or answer-quality score.

Raw reports: [keyword](reviews/phase2-retrieval-keyword.json),
[semantic](reviews/phase2-retrieval-semantic.json),
[hybrid](reviews/phase2-retrieval-hybrid.json).

All three methods missed one expected requirement for **q09**, “Which requirements
specify VLAN separation between camera and infotainment?” They ranked `REQ-ETH-008`
first but did not return `REQ-ISO-001` within five results. Per-query Recall@5 was 0.5,
Precision@5 0.2, and reciprocal rank 1.0. Other returned IDs were `REQ-ETH-007`,
`REQ-ETH-005`, `SYS-REQ-102`, and `REQ-SOA-015`. This is a useful cross-document
isolation-requirement miss to address when comparing learned embeddings or rerankers.

Run from the repository root:

```bash
uv run --locked python -m ee_arch_copilot.rag.evaluation.run --method hybrid --output /tmp/rag-hybrid.json
uv run --locked python -m ee_arch_copilot.rag.evaluation.run --method keyword --output /tmp/rag-keyword.json
uv run --locked python -m ee_arch_copilot.rag.evaluation.run --method semantic --output /tmp/rag-semantic.json
```

Environment settings select the embedding provider and ranking parameters; `--method`
overrides only the strategy. LLM generation is disabled in this CLI. Reports include
dataset size, active options, embedding identity, corpus hashes, aggregate/per-query
metrics, failed IDs, expected-document misses, abstention, and limitations.

## Answer evaluation

[The QA review dataset](../data/evaluation/qa_dataset.json) contains six cases: four
answerable and two no-evidence cases. Each defines expected IDs/documents, facts to
check, and examples of unsupported claims to reject. It distinguishes a nominal
bandwidth constraint, service identifier, proposed latency, and unevaluated isolation
from statements of actual verification or measured performance.

Offline tests use a controlled provider that assembles a source excerpt and citation,
and controlled adversarial responses for malformed JSON, fabricated citation labels,
invented requirement IDs, mismatched inline labels, and insufficient evidence.
`answer_checks` measures structural citation membership and referenced-ID correctness.
The full corpus test checks cited IDs against QA labels, while the HTTP acceptance
probe uses the actual HTTP LLM adapter with a controlled transport. None of these
results measures natural-language generation quality or proves absence of unsupported
claims. Prompt requirements alone do not establish semantic faithfulness.

The [captured HTTP workflow](reviews/phase2-workflow.json) records the test model as
`controlled-e2e-llm`, explicitly marks `live_llm_tested: false`, and preserves actual
search/answer responses, source metadata, and verification outcomes. A missing-evidence
question skipped generation. Production contains no controlled-provider fallback.

For an optional live assessment, configure an actual compatible LLM and embedding
endpoint, index the same versioned corpus in a separate database, and submit each QA
question through `ask`. Save the exact provider/model identity, temperature, max tokens,
retrieval settings, context chunk IDs, answers, and review date. Check citation
resolution automatically, then have an engineer judge every factual claim against the
quoted evidence, identifier/unit accuracy, completeness, requirement-versus-verification
language, abstention, and document-injection handling. Record unsupported claims
explicitly; do not derive a hallucination rate from citation validity. No live results
are claimed for this implementation.

## Limits and next experiment

The corpus is small, synthetic, English-only, and intentionally internally consistent.
Relevance labels are selective, not exhaustive judgments of every possible helpful
chunk. The two no-answer cases provide very limited evidence about abstention. Hash
collisions, token overlap, approximate-vector boundaries, and fixed thresholds can
produce false positives or misses. Real PDFs and supplier terminology need a larger
reviewed corpus. Compare a learned embedding model against this baseline, expand
negative and cross-document cases, test q09 explicitly, and evaluate reranking on a
held-out dataset before selecting production settings.
