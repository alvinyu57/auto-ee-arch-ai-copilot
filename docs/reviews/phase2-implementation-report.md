# Phase 2 implementation report

Historical implementation evidence. The subsequent acceptance audit and corrections
are documented in the [verification report](phase2-verification-report.md) and
[remediation report](phase2-remediation-report.md); use the latter for current behavior
and acceptance status. Original measurements below are retained as the baseline.

Date: **2026-11-10 (Europe/Berlin)**. Repository: `auto-ee-arch-ai-copilot`.
Outcome: Phase 2 requirements retrieval, persistence, optional generation, REST APIs,
synthetic corpus, evaluation, and offline verification are implemented. Live external
model behavior and Docker execution have not been verified.

## Implemented features

- Normalized document envelopes with stable document IDs, source basename/type/title,
  optional version, original normalized content, metadata, hash, and UTC ingestion time.
- Markdown/text/JSON requirement extraction with configurable ID patterns, headings,
  source offsets/lines, JSON pointers, and preservation of structured fields. No invented IDs.
- Trusted local `pypdf` loading with page references and explicit rejection of pages
  without extractable text. HTTP supports content envelopes; no arbitrary filesystem paths.
- Requirement-aware chunks, controlled long-record overlap, complete original record
  text, fragment offsets, and deterministic chunk IDs, including repeated JSON fragments.
- A deterministic offline signed-hash embedding provider and a real compatible HTTP
  embedding adapter with batching, response-order validation, and dimension checks.
- Persistent Chroma cosine vectors plus an authoritative SQLite source/chunk catalog.
  Active revisions prevent partial staging from becoming retrievable. Duplicate ingestion
  skips embedding; updates replace active chunks. Filtering, deletion, persistent reopening,
  forced reindexing, and incompatible-model rejection are implemented and tested.
- Independent BM25 keyword search, semantic search, RRF fusion, stable deduplication,
  ranking details, and an optional local token-overlap reranker. Exact technical identifiers
  remain searchable. Scores are explicitly not calibrated answer confidence.
- Optional compatible HTTP LLM generation with evidence-only prompts, structured output,
  explicit insufficient evidence, untrusted-document instructions, and citation validation.
  Fabricated references suppress generated claims. Production contains no mock fallback.
- Versioned knowledge endpoints, typed request/response schemas, OpenAPI descriptions,
  bounded streamed input, source/chunk resolution, safe HTTP errors, and dependency injection.
- Four synthetic specifications with **30 identified requirements in 34 chunks**,
  **24 retrieval queries**, six QA review cases, and reproducible evaluation/probe commands.
- Typed environment settings, `.env.example`, a persistent Docker volume location,
  documentation, and ADR 0002.

## Final structure

Existing Phase 1 files remain in place. Relevant additions and integration points:

```text
src/ee_arch_copilot/
├── core/settings.py
├── api/
│   ├── limits.py
│   └── routes/knowledge.py
├── main.py                         # additive routing, DI, safe errors
└── rag/
    ├── models.py
    ├── errors.py
    ├── providers.py                # shared bounded HTTP request boundary
    ├── tokenization.py
    ├── service.py                  # Phase 3 callable boundary
    ├── ingestion/{loader,parser,chunker}.py
    ├── embeddings/{base,providers}.py
    ├── storage/chroma_store.py
    ├── retrieval/{keyword,semantic,hybrid,reranker}.py
    ├── generation/{prompts,answer_generator,citations}.py
    └── evaluation/{metrics,run}.py
data/
├── knowledge/synthetic/{ethernet,soa,tsn,overview}.md
└── evaluation/{retrieval_dataset,qa_dataset}.json
tests/
├── rag/test_{ingestion,chunking,embeddings,storage,retrieval,citations,generation,evaluation}.py
└── test_knowledge_api.py
scripts/verify_phase2.py
.env.example
docs/
├── rag-architecture.md
├── rag-evaluation.md
├── decisions/0002-requirements-rag.md
└── reviews/
    ├── phase2-implementation-report.md
    ├── phase2-retrieval-{keyword,semantic,hybrid}.json
    └── phase2-workflow.json
```

## Architectural decisions and integration boundaries

The existing monolith is retained. RAG owns its Pydantic contracts and concrete adapters;
it does not import NetworkX or the architecture validator. Phase 1 domain models,
topology algorithms, and validation rules are unchanged. Requirement IDs such as
`REQ-CONN-001`, `REQ-BW-001`, and `REQ-ISO-001` provide explicit links to the example
architecture without turning prose into reviewed constraints or validation results.

`KnowledgeService.search` returns machine-readable evidence without LLM calls.
Keyword-only queries also avoid the embedding provider. LLM setup is deferred to `ask`,
so incomplete generation configuration cannot block ingestion or retrieval. External
embedding and LLM protocols are separate and accept injected providers for offline tests.

Chroma stores supplied embeddings rather than invoking a default embedding function.
Collection metadata locks model identity and dimension; a different model requires a
new database directory and reingestion. The SQLite catalog commits active revisions
after vectors are staged. Both stores live under one volume directory. One service
and one process are supported; no distributed infrastructure was introduced.

The existing `/health` payload retains `phase: 1` and version `0.1.0` for compatibility.
Existing architecture endpoints and response semantics are preserved. The original
OpenAPI regression assertion now checks that all original paths are present, allowing
the new knowledge paths. All original Phase 1 tests still execute.

See [RAG architecture](../rag-architecture.md) and [ADR 0002](../decisions/0002-requirements-rag.md)
for persistence, provenance, ranking, trust boundaries, and tradeoffs.

## Local setup and execution

From the repository root, with Python 3.12+ and uv installed:

```bash
uv sync --locked --all-groups
cp .env.example .env
uv run --locked uvicorn ee_arch_copilot.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Offline defaults need no key or model download.
`VECTOR_DB_PATH` defaults to `data/vector_db`, excluded from Git and Docker context.
To use a learned embedding server, configure `EMBEDDING_PROVIDER=openai_compatible`,
the server's model name/output dimension/base URL, and an API key only if required.
To enable real answers, configure `LLM_PROVIDER=openai_compatible`, `LLM_MODEL`,
`LLM_BASE_URL`, and optionally `LLM_API_KEY`. A compatible `/chat/completions` endpoint
with JSON response support is required. Provider secrets never appear in API responses.

Docker configuration uses `/var/lib/ee-arch` for both stores:

```bash
docker build -t auto-ee-arch-ai-copilot .
docker run --rm -p 127.0.0.1:8000:8000 -v ee-knowledge:/var/lib/ee-arch auto-ee-arch-ai-copilot
```

These Docker commands are documented, not reported as executed. Run one Uvicorn worker
per database directory. Local development works without Docker.

## Example ingestion

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/knowledge/documents \
  -H 'Content-Type: application/json' -d '{
    "document_id": "demo", "filename": "demo.md", "source_type": "markdown",
    "version": "1.0",
    "content": "# Synthetic gateway\n\nREQ-ETH-001: Gateway shall use 1000BASE-T1 at 1000 Mbps."
  }'
```

The response contains a document summary, chunk count, and `status: created`.
Repeating the same envelope returns `unchanged`; changing it under the same ID returns
`replaced`. JSON sources use `source_type: json` with a JSON-encoded requirements
array in `content`. The [README](../../README.md#requirements-knowledge-pipeline-phase-2)
includes a Python/httpx loop that posts all four corpus files to the running API.

## Example hybrid search and actual result

After loading the supplied corpus:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' -d '{
    "question": "Which requirements define Ethernet bandwidth between the Central Gateway and ADAS controller?",
    "options": {"method": "hybrid", "final_top_k": 3}
  }'
```

The actual leading hit from the acceptance probe is summarized below. This is a
selected-field excerpt, not the entire HTTP response:

```json
{
  "chunk_id": "chk-684c8762d3ae09db2ab2fb3f2ccaedb5",
  "document_id": "ethernet",
  "filename": "ethernet.md",
  "document_version": "1.0",
  "requirement_id": "REQ-ETH-002",
  "start_line": 14,
  "end_line": 18,
  "score": 0.03278688524590164,
  "rank": 1,
  "methods": ["keyword", "semantic"]
}
```

The source text explicitly requires a switched gateway-to-ADAS path through
`switch-core`, `link-gateway`, and `link-adas`, each link at least 1000 Mbps using
1000BASE-T1. Second and third hits were `REQ-ETH-001` and `SYS-REQ-101`.
The [complete captured response](phase2-workflow.json) includes text/original text,
headings, offsets, component scores, and document metadata. Scores rank candidates;
they do not prove relevance, answer truth, or architecture compliance.

## Example grounded question answering

With a real provider configured:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/knowledge/ask \
  -H 'Content-Type: application/json' -d '{
    "question": "REQ-ETH-002",
    "options": {"method": "hybrid", "final_top_k": 5},
    "generation": {"temperature": 0, "max_tokens": 1000}
  }'
```

The return contract includes answer text, structured citations, requirement IDs,
evidence status, explanation, and model identity. Citation labels and inline references
must resolve to retrieved chunks. The offline HTTP probe returned `evidence_status:
cited`, referenced `REQ-ETH-002`, and resolved its citation to the actual indexed chunk.
Its model is explicitly recorded as `controlled-e2e-llm`; this is test evidence, not a
claim of live model output. A query for `REQ-BATTERY-999` returned the fixed insufficient
response and made no LLM call. With no configured provider, `ask` returns 503 even if
retrieval is empty. Malformed/provider failures return 502; fabricated references return
`invalid_citations` with generated claims removed.

## Actual verification results

All results below were executed against this implementation on Python **3.12.16**:

| Command | Actual result |
| --- | --- |
| `uv sync --locked --all-groups` | PASS; resolved 110 packages, checked 108 installed packages |
| `uv run --locked ruff check .` | PASS; all checks passed |
| `uv run --locked ruff format --check .` | PASS; 79 Python files formatted |
| `uv run --locked mypy src` | PASS; 48 source files |
| `uv run --locked mypy` | PASS; 66 configured source/test files |
| `uv run --locked pytest` | PASS; **215 tests in 9.04 s**, including all **108 original Phase 1 tests** and **107 added tests** |
| Coverage with existing 90% gate | **99.10%** statement/branch coverage; 1,437 statements, 344 branches |
| `uv build --offline` | PASS; source distribution and wheel built |
| Evaluation CLI, each of three methods | PASS; actual raw reports checked in |
| `uv run --locked python scripts/verify_phase2.py --output docs/reviews/phase2-workflow.json` | PASS; full synthetic HTTP acceptance workflow |

In this environment uv was found at `/tmp/ee-arch-uv/bin/uv` rather than on `PATH`.
Commands used that executable with `UV_CACHE_DIR=/tmp/ee-arch-uv-cache` and
`PYTHONPATH` removed. Dependency installation initially failed on sandbox DNS and
completed after network authorization. Offline ASGI tests also required execution
outside the sandbox: an existing health request stalled on asyncio thread wakeups
inside it, while the same API regression passed outside. Tests and the acceptance
probe made no external API calls and needed no API keys.

The final QA checks validate acceptable requirement references for all six QA cases.
The bandwidth case accepts both `REQ-ETH-001` and `REQ-ETH-002`, because both explicitly
specify link-gateway's nominal bandwidth. Adversarial controlled-response tests cover
malformed outputs, fabricated citations/IDs, missing evidence, and missing generation
configuration. A separate controlled semantic-provider test retrieves a paraphrase
with no shared lexical tokens, demonstrating that the semantic adapter is independent
of BM25 without claiming learned behavior from hash vectors.

## Actual retrieval evaluation

Dataset: **24 queries, 22 answerable, two no-evidence**. Corpus: four version-1.0
synthetic sources, 34 chunks. Provider: **`hash:hash-token-v1:384`**. Parameters:
semantic/keyword top K 12, final K 5, RRF 60, minimum similarity 0.15, reranking off.

| Method | Recall@5 | Precision@5 | MRR within 5 | No-evidence abstention |
| --- | ---: | ---: | ---: | ---: |
| Keyword | 0.977273 | 0.281818 | 1.000000 | 2/2 |
| Semantic interface with hash vectors | 0.977273 | 0.281818 | 1.000000 | 2/2 |
| Hybrid | 0.977273 | 0.281818 | 1.000000 | 2/2 |

One query, **q09** about VLAN separation between camera and infotainment, retrieved
`REQ-ETH-008` but missed `REQ-ISO-001` within five results. Its Recall@5 is 0.5.
The identical aggregate metrics do not show a hybrid improvement. Precision uses K
as the denominator even for exact-ID queries returning one relevant result. No-answer
queries are excluded from ranking averages and measured separately. Complete methodology,
per-query artifacts, and limitations are in [RAG evaluation](../rag-evaluation.md).

## End-to-end acceptance evidence

[phase2-workflow.json](phase2-workflow.json) records real in-process HTTP responses
from a temporary persistent database, not hand-written example output. It verifies:

1. All four real synthetic files ingested successfully; repeat ingestion was unchanged.
2. Natural-language gateway/ADAS search returned `REQ-ETH-002` first and retained source
   location, original text, version, and a resolvable chunk identifier.
3. Keyword, semantic, and hybrid endpoints each retrieved exact `REQ-SOA-015`.
4. Citation resolution returned the same indexed records as retrieval.
5. Generation through the actual compatible HTTP adapter accepted a controlled response
   with valid evidence; missing evidence skipped the provider.
6. A new service instance reopened persisted chunks and retrieved `REQ-TSN-008`.
7. Replacing Ethernet with version 1.1 removed old active chunk IDs; deletion removed
   its searchable evidence.
8. The Phase 1 example still returned `NOT_EVALUATED`, preserving deterministic semantics.

## Remaining limitations

- No live external embedding/LLM invocation or quality assessment was performed. HTTP
  protocol and generation behavior were verified with controlled transports/providers.
- Hash embeddings are a lexical vector baseline, not learned semantic understanding.
  The small synthetic dataset is not representative production evidence; q09 remains a
  documented retrieval miss. Similarity cutoffs do not guarantee relevance or abstention.
- Citation checks establish source-reference validity, not support for every factual
  claim, unit interpretation, or full prompt-injection resistance. Human review is needed.
- PDF extraction has no OCR, table/layout reasoning, or assurance on supplier PDFs.
  Markdown/text requirement extraction is heuristic, though original evidence is retained.
- Persistence supports one service/process. There is no authentication, tenant isolation,
  production audit trail, archival revision API, or backup automation. Interrupted staging
  can leave inactive vectors on disk; active citations expire on replacement/deletion.
- Docker configuration was updated and inspected but image build/runtime was not run.
  Python 3.13 and remote CI execution were not run in this session.
- Retrieval does not validate architecture, compute TSN latency, verify isolation,
  infer protocol reachability, or promote prose into executable constraints.

## Recommended Phase 3 work

Expose read-only typed retrieval, topology, and validation tools to a bounded orchestrator.
Preserve deterministic findings separately from generated explanations and reject invalid
tool inputs with the existing schemas. Require engineer approval before changing models
or interpreting new structured constraints. Compare a learned embedding model and
reranker against the saved baseline, expand negative and cross-document evaluation,
address q09, and conduct an explicitly labeled live QA/unsupported-claim review.
Select authentication, archival citations, and a concurrency model before shared hosting.
