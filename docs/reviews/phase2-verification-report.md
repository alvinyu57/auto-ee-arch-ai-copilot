# Phase 2 independent verification report — repeat acceptance audit

Audit date: **2026-11-11 (Europe/Berlin)**. Audited commit: **62d4ede** (`Phase2: fix`). Previous audited implementation: **89d804d**; Phase 1 baseline: **2795a54**. This report supersedes the 2026-11-10 acceptance conclusions for the current implementation. The previous report remains recoverable from Git. Only this report was updated during this audit; application code, tests, datasets, dependency files, configuration and user indexes were not modified.

## 1. Executive Summary

**CONDITIONAL GO for reviewed Phase 3 integration.** The prior HIGH citation-freshness defect no longer reproduces. Known invalid numeric/case-variant requirement references are rejected; implicit filename replacement is blocked; exact-ID semantic candidate starvation is corrected. The original period-separated inline requirement case is fixed. A narrower unsupported-boundary diagnostic gap remains, and full semantic grounding/sufficiency remains deferred.

Traceability totals: **22 PASS, 5 PARTIAL, 0 FAIL, 0 NOT VERIFIED, 0 NOT APPLICABLE** across 27 requirements. Component-level unknowns are recorded explicitly even where their parent requirement passes its bounded contract. Active findings: **0 CRITICAL, 0 HIGH, 2 MEDIUM, 0 LOW**. Four prior findings are closed in their tested contracts (D-001, D-002, D-004, D-005); D-003 and D-006 are partially resolved, as detailed below. This is more qualified than the remediation report's claim of five fully fixed findings: its D-003 original reproduction passes, but a separate fallback/diagnostic counterexample remains.

**243/243 tests passed**, including **108 Phase 1** and **135 Phase 2** cases. Measured configured statement/branch coverage: **99.16%**, with 1,531 statements, seven missed statements, 374 branches and nine partial branches. Ruff lint, formatting and strict source mypy passed. The offline remediation evaluation and full controlled HTTP workflow also passed.

The original independent **28-query/18-requirement** dataset was reconstructed verbatim from the previous report before retrieval. No labels were altered. All **84 ordered result lists** match the previous run and repeat stably. Keyword/hybrid Recall@5 = **1.000000**; hash-vector semantic Recall@5 = **0.958333**; exact-ID Hit@1 = **6/6** each. Negative retrieval abstention remains **2/4** per mode. The unchanged repository dataset retains Recall@5 **0.977273**, MRR **1.0**, with q09 still missing one relevant requirement.

Phase 3 structure: **READY WITH MINOR CHANGES**. Typed retrieval, generation, citation, topology and validation interfaces are usable without a major rewrite. Approval applies to human-reviewed tools over the documented source grammar, with unverified generated text kept separate from deterministic findings. Learned semantic quality, real LLM behavior and broad engineering entailment remain **NOT VERIFIED**. No live embedding or LLM API was called.

Source basis: README, architecture/roadmap/RAG documents, ADRs, implementation/remediation reports and saved evidence, pyproject/lockfile, relevant source/tests, supplied synthetic documents and the original acceptance request. No separate original Phase 2 specification was found. Remediation claims were treated as hypotheses and tested. Independent core/API probes blocked live HTTP transport and used hash embeddings plus controlled providers/MockTransport. All persistent test stores and outputs were isolated outside the repository and removed after report validation.

## 2. Requirement Traceability Matrix

Source paths below are relative to `src/ee_arch_copilot/` unless they start with `tests/`, `data/`, `docs/`, or name a root configuration file. `:N` identifies source lines at 62d4ede. PASS describes verified behavior within the stated contract, not production or live-model certification. Optional PDF/reranking are implemented and assessed, rather than dismissed as NOT APPLICABLE.

| ID | Requirement | Implementation location | Execution/test evidence | Status | Comments/limits |
| --- | --- | --- | --- | --- | --- |
| P2-001 | Markdown/TXT/JSON ingestion | `rag/ingestion/loader.py:12,47; rag/ingestion/parser.py:24` | Independent canonical Markdown, structured JSON with inherited version and Unicode TXT; existing ingestion tests. | **PASS** | Required formats and error contracts work. |
| P2-002 | Document identity and metadata | `rag/ingestion/loader.py:31; rag/service.py:67` | Implicit duplicate unchanged, changed implicit source rejected, first source preserved; explicit same-filename origins; API 409. | **PASS** | D-004 closed; explicit ID now required for replacement. |
| P2-003 | Requirement extraction | `rag/ingestion/parser.py:18,28,142` | Canonical three IDs pass; period-separated inline definitions split; tables/unknown conventions warn. Comma/mixed-case probes still merge silently. | **PARTIAL** | Original D-003 reproduction fixed; residual diagnostics gap remains. |
| P2-004 | Requirement-aware chunking | `rag/ingestion/chunker.py:13; rag/ingestion/parser.py:118` | Independent canonical source slices, 30 unique long fragments and inline identity; existing JSON/overlap tests. | **PARTIAL** | Correct per recognized record; still inherits missed boundaries from residual D-003. |
| P2-005 | Stable chunk identifiers | `rag/ingestion/chunker.py:33; rag/storage/chroma_store.py:70` | Independent identical ingestion, stable canonical chunks/three vectors; long fragments unique; legacy fingerprint regression. | **PASS** | Content/version identity retained; metadata-only edits may preserve chunk IDs. |
| P2-006 | Embedding provider abstraction | `rag/embeddings/base.py:7; rag/embeddings/providers.py:35` | Executed mock HTTP batch/auth/order tests and controlled synonym retrieval; independent vector validation. | **PASS** | Document/query interfaces and HTTP adapter verified offline; live provider operation NOT VERIFIED. |
| P2-007 | Offline embedding test provider | `rag/embeddings/providers.py:14` | Independent repeatability/distinct-input/empty-vector checks; existing vector normalization tests. | **PASS** | Hash vectors provide lexical variation, not learned semantic evidence. |
| P2-008 | Persistent vector storage | `rag/storage/chroma_store.py:30,94,194` | Independent creation, reopen including separate interpreter, metadata filters, update/delete; existing staging and legacy catalog tests. | **PASS** | Single shared service/process only; crash recovery and multiple writers NOT VERIFIED. |
| P2-009 | Idempotent ingestion | `rag/service.py:78; rag/storage/chroma_store.py:70` | Independent unchanged envelope/vector count; original/inline/legacy regression tests and HTTP workflow. | **PASS** | Duplicates skip embeddings; no unintended active duplicate chunks observed. |
| P2-010 | Document update and deletion | `rag/storage/chroma_store.py:94,237; rag/service.py:98` | Explicit update, version filters, old chunk disappearance, forced reindex, deletion in all modes, unrelated sources preserved. | **PASS** | Content/version revisions replace active evidence; archival retention is outside current scope. |
| P2-011 | Keyword retrieval | `rag/retrieval/keyword.py:15; rag/tokenization.py:40` | Seven required technical identifier forms top-one; fixed 28-query rerun; injected query-embedding trap. | **PASS** | Ranked BM25 works independently of LLM/query embedding. |
| P2-012 | Semantic retrieval | `rag/retrieval/semantic.py:10; rag/storage/chroma_store.py:215` | Original shadowing probe now returns exact target; existing synonym mock test; independent metrics/stability/Top-K tests. | **PARTIAL** | D-005 closed; learned semantic relevance and production quality remain NOT VERIFIED. |
| P2-013 | Hybrid retrieval | `rag/retrieval/hybrid.py:5` | Independent known RRF scores, repeated rankings; existing dedup/tie/missing-branch tests and evaluation. | **PASS** | Correct RRF; no blanket superiority over keyword/semantic claimed. |
| P2-014 | Optional reranking | `rag/retrieval/reranker.py:7; rag/retrieval/hybrid.py:28` | Existing deterministic optional-reranking test; default-off evaluations. | **PASS** | Local overlap heuristic; no external reranker or promised fallback policy. |
| P2-015 | Retrieval metadata and citations | `rag/service.py:143; rag/generation/citations.py:97` | Independent valid citation resolution, deletion/content/metadata mutations and true concurrent update; API stale response. | **PASS** | D-001 closed within documented service-return freshness boundary. |
| P2-016 | Grounded LLM generation | `rag/generation/answer_generator.py:63; rag/generation/citations.py:63; rag/models.py:190` | Controlled supported output, compliance suppression, injection, conflict; unrelated measured-latency claim still accepted as unverified. | **PARTIAL** | D-006 partially mitigated; full claim support remains unimplemented. |
| P2-017 | Insufficient-evidence behavior | `rag/generation/answer_generator.py:69; rag/generation/citations.py:9` | Empty evidence skips provider; repository negatives 6/6; independent negatives 2/4 under excerpt-only instrument. | **PARTIAL** | Nonempty-context sufficiency requires provider judgment and review, not similarity alone. |
| P2-018 | Citation validation | `rag/generation/citations.py:46,52; rag/identifiers.py:8; rag/service.py:160` | Fake S99, uppercase/lowercase/custom numeric invented IDs rejected; structured extra document ID rejected; freshness checked. | **PASS** | D-002 original cases closed; unsupported arbitrary grammar explicitly flagged, not certified. |
| P2-019 | RAG evaluation framework | `rag/evaluation/metrics.py:10; rag/evaluation/run.py:68` | Known-ranking/source tests; rerun remediation evaluator; independent arithmetic and preserved 84 rankings. | **PASS** | Fixed cutoffs use returned window; require final K >=5 for @5 comparison. Answer checks are structural. |
| P2-020 | Golden evaluation dataset | `data/evaluation/retrieval_dataset.json:1; data/evaluation/qa_dataset.json:1` | Original 24 queries/six QA cases rerun; exact-byte hashes and baseline unchanged. | **PASS** | Synthetic/selective relevance; no automatic semantic adjudication of all QA facts. |
| P2-021 | REST API integration | `api/routes/knowledge.py:43,104,110; main.py:39; api/limits.py:11` | Existing API tests plus independent TestClient lifecycle, 409, status fields, size/input/provider errors and resolution. | **PASS** | Routes preserved; enum additions and implicit replacement policy are intentional contract changes. |
| P2-022 | Synthetic automotive knowledge base | `data/knowledge/synthetic/{ethernet,soa,tsn,overview}.md` | Four sources ingested; 34 chunks/30 identified requirements; original corpus unchanged. | **PASS** | Explicitly synthetic design intent, not production verification evidence. |
| P2-023 | Configuration and secrets handling | `core/settings.py:15; rag/models.py:41; rag/providers.py:19; main.py:61` | Nested credential/path rejection, safe HTTP errors, mock 401/timeout; runtime/model mismatch checks. | **PASS** | No tested secret reflection; prose redaction and enterprise authorization are not provided. |
| P2-024 | Automated testing | `tests/rag/test_remediation.py; tests/rag/; tests/test_knowledge_api.py` | 243 tests pass, including 28 remediation cases; 99.16% coverage; independent residual probes supplement suite. | **PASS** | Passing coverage does not prove exhaustive behavior; residual D-003/D-006 need further tests. |
| P2-025 | Documentation | `README.md:192; docs/rag-architecture.md:28; docs/rag-evaluation.md:6; docs/decisions/0002-requirements-rag.md:56` | Read remediation report/docs and compare source changes/executed results. Baseline claims and new statuses reconciled here. | **PASS** | Bounded grammars/guards and single-process limits documented. D-003 not fully closed under broader acceptance fallback. |
| P2-026 | Phase 1 backward compatibility | `domain/models/; services/; api/routes/architecture.py` | All 108 Phase 1 tests pass; unchanged domain/services/original tests versus prior Phase 2; unusable vector path probe. | **PASS** | Deterministic validation requires no LLM/embedding call or initialized vector database. |
| P2-027 | Phase 3 extensibility | `rag/service.py:33,109,143; rag/generation/answer_generator.py:57` | Typed search/generation, stale/conflict/unverified statuses and independent deterministic services exercised. | **PASS** | READY WITH MINOR CHANGES for reviewed tools; consumers must preserve evidence/verification distinctions. |

## 3. Architecture Assessment

| Responsibility | Actual component (under `src/ee_arch_copilot/`) | Verification |
| --- | --- | --- |
| Loading / normalization | `rag/ingestion/loader.py:12,47` | Bounded content envelopes, trusted file/PDF loader, normalized content and identity. |
| Parsing / extraction | `rag/ingestion/parser.py:24,39,80` | JSON fields/pointers; heading-aware text definitions and bounded inline starts; warnings. |
| Requirement chunking | `rag/ingestion/chunker.py:13` | Per-record bounded windows, original statement, overlap and deterministic locations/IDs. |
| Embeddings | `rag/embeddings/base.py:7`; `rag/embeddings/providers.py:14,35` | Independent provider protocol, deterministic hash and compatible HTTP adapter. |
| Persistence | `rag/storage/chroma_store.py:22` | Persistent Chroma cosine vectors plus authoritative SQLite source/chunk/revision catalog. |
| Keyword / semantic / hybrid | `rag/retrieval/keyword.py:15`, `semantic.py:10`, `hybrid.py:5` | BM25, explicit vector query and RRF; exact-ID eligibility before vector Top-K. |
| Reranking | `rag/retrieval/reranker.py:7,11` | Optional local overlap implementation behind a small protocol. |
| Generation | `rag/generation/answer_generator.py:14,21,57` | Independent provider/HTTP adapter; question, chunks and options are explicit. |
| Citation / claim guards | `rag/generation/citations.py:18,97`; `guards.py:8,18`; `rag/identifiers.py:8` | Bounded label/ID validation, heuristics, structured unverified status. |
| Evaluation | `rag/evaluation/metrics.py:10,22`; `run.py:68` | Source-aware ranking evaluation, fixed cutoffs and structural answer checks. |
| REST | `api/routes/knowledge.py:30`; `main.py:19` | Lazy service construction and typed routes with controlled errors. |

Retrieval runs without an LLM; independent keyword search still succeeded with `embed_query` forced to raise. Embeddings and generation can be injected independently. `AnswerGenerator.answer(question, chunks, options)` can consume evidence separately from retrieval, but it accepts caller-owned snapshots and has no storage freshness check. Current-evidence users must call `KnowledgeService.ask` or impose their own revision policy.

`ask` now captures retrieval and active document revisions under the store lock, releases it for the provider call, and checks all retrieved source revisions again before returning (`rag/service.py:143`). Deletion, content/version replacement and metadata-only replacement suppress generated content with `stale_evidence`. A true two-thread probe verified a write completes while the provider waits, followed by a stale response. This fixes the previously observed return-time defect; it does not promise that a citation URL remains active after future edits.

Storage remains **concrete rather than fully abstract**: constructor injection accepts `ChromaStore`, and the service uses its lock/catalog/revision operations. Tests use isolated real Chroma, not an in-memory repository protocol. This is workable for this PoC and read-only agent tools; a backend swap would need a compatible interface. No circular import or global mutable evidence collection was identified. Settings depend on retrieval DTOs, not automotive domain models on AI SDKs. ASGI app state owns a lazy knowledge service; the module-level app initializes settings but not vector storage.

RAG does not import or change Phase 1 domain/topology/validator results. Direct domain/services remain independently callable. The shared app imports Chroma and validates all settings, so its installed distribution includes RAG dependencies and invalid RAG environment syntax can affect app startup; this does not force vector initialization or credentials for valid Phase 1 requests.

Persistence supports one shared service/store in one process, not independent writer processes. The RLock is object-local. HTTP clients use context managers; the store still has no explicit close/lifespan resource hook. Catalog scans rebuild lexical statistics per query. These are bounded-corpus operational limits; no corruption, circular imports or unneeded orchestration framework was observed. Chroma adds substantial transitive dependencies, but no LangChain/agent framework was introduced. Domain models have no provider SDK coupling.

## 4. Document Ingestion Assessment

| Scenario | Actual rerun behavior | Status |
| --- | --- | --- |
| A. Valid Markdown | Exact supplied Ethernet example creates three records with correct IDs, heading ancestry and source slices. | PASS |
| B. Valid JSON | Requirements object/array supported; custom ID, section/structured fields and JSON pointer retained; title/version inherited. | PASS |
| C. Plain text | Multiline requirement and engineering symbols persist. | PASS |
| D. Empty/blank | ValidationError and HTTP 422; heading-only source raises no-indexable-text error. | PASS |
| E. Unsupported format | `.csv` local loader raises supported-format ValueError; HTTP unsupported source type 422. | PASS |
| F. Malformed JSON | Parse error without new source insertion; HTTP 422. Existing tests cover wrong shapes/empty arrays and malformed records. | PASS |
| G. Identical ingestion | `unchanged`, same source timestamp/chunks, three canonical vectors; no embedding duplication. | PASS |
| H. Updated document | Explicit-ID update `replaced`; old IDs gone, previous requirement absent, version 1 filter empty/version 2 matches; forced reindex works. | PASS |
| I. Equal filenames | Different implicit content now raises DocumentIdentityConflict/HTTP 409 and preserves first source. Distinct explicit IDs preserve both origins; intentional explicit replacement remains possible. | PASS |
| J. Non-ASCII / symbols | `Überwachung`, `Δt ≤ 1 µs`, `125 °C` remain in TXT/JSON text. | PASS |

IDs are stable under the explicit-ID/basename policy. There is still no origin inference: callers retain the returned ID for changes and supply distinct IDs for different origins. Newlines normalize to LF, and offsets refer to normalized source text. JSON source title/version can be inherited; Markdown versions must be supplied by the caller. Source metadata is kept separately from trusted generated identifiers. The unchanged credential-key validation and explicit chunk-field construction prevent metadata keys from overriding trusted chunk identities.

Content/version replacement invalidates previous chunk IDs and keeps only the active version. Metadata-only updates may retain IDs but change revision fingerprints; the new freshness check covers those edits. Deletion removes catalog/vector evidence in all three retrieval modes while unrelated TXT/JSON sources remain. Historical revision retention is not implemented.

The executed `tests/rag/test_ingestion.py:129` constructs a real two-page text PDF, checks page `[1,2]` attribution, rejects a blank page with an OCR limitation, and rejects malformed PDF bytes. HTTP PDF envelopes remain intentionally rejected; local loading is trusted-only. No OCR was used. Supplier PDFs, complicated layouts and cross-page requirement continuity remain NOT VERIFIED. Local size limit is 10 MB; content/HTTP bounds are separately tested below.

## 5. Requirement Extraction and Chunking Assessment

The original supplied `REQ-ETH-001`, `REQ-ETH-002`, `REQ-SEC-003` document again produces exactly three independently retrievable records. Statements do not merge, source IDs are exact, heading ancestry is retained, all text slices match normalized offsets, identical ingestion has stable chunks and embedded/stored metadata survives.

| Edge case | Actual observation |
| --- | --- |
| Original same-line period-separated definitions | `REQ-ETH-010: Gateway shall connect. REQ-ETH-011: Camera shall connect.` now produces two chunks; query 011 returns its own record. |
| Comma-separated definitions | Changing the delimiter to a comma produces one 010 record containing both definitions, **no warning**, and query 011 returns **[]** (residual D-003). |
| Mixed naming in an assigned record | Uppercase 010 followed by lowercase `req-eth-011:` likewise merges without warning. |
| Unsupported IDs in unassigned text | `REQ_ETH_012`, lowercase `req-eth-013` remain verbatim with persisted extraction warnings; `SYS-REQ-014` remains identified. Existing custom `ENG_` pattern tests pass. |
| Table requirement | Table source preserved, ID null, warning returned on ingestion and stored chunk. No structured table parser is claimed. |
| Multiline requirement / ordinary sentence reference | Text remains intact; existing tests show references without a supported definition delimiter do not split records. |
| Headings / absent IDs | Context paragraphs remain with null ID and section; headings alone reject as nonindexable. No source ID is invented. |
| Repeated ID in two sources/versions | Both source records retrievable with distinct document/version/location identities; same-document update keeps active revision. |
| Very long requirement | Independent 150-character/25-overlap test creates **30 unique fragments**, each with exact ID, complete original text and correct source slices. Existing long JSON pointer/fragment tests pass. |

Chunk hashing still includes source identity/content/version, requirement ID, section, location and fragment. Content changes can invalidate even unchanged statements in the same document. Overlap stays within recognized records. Multiple fragments of one requirement can occupy Top-K slots and produce overlapping valid citations; fusion deduplicates chunk IDs, not requirement IDs. Consumers must not count that as independent evidence. Requirement-level evaluation deduplicates IDs to avoid extra credit.

The parser explicitly supports inline `ID:` after `. ; ! ?` plus whitespace; it does not promise general inline grammar. The remaining acceptance gap is **diagnostic fallback**, not a demand to interpret commas as definite new requirements: warnings are only added for records with `requirement_id is None` (`parser.py:29`), so an extra unsupported definition inside an already assigned record stays silent. Human source review or an explicit warning is still needed for these cases. This makes P2-003/004 PARTIAL rather than retaining the previous FAIL or treating the whole gap as fully closed.

## 6. Embedding and Vector Store Assessment

The document/query embedding protocol, batch HTTP adapter and offline hash provider remain separate and usable. Independent checks show repeated text is identical, distinct text varies, and empty text produces a zero hash vector. Store validation rejects wrong dimensions, zero vectors and NaN with ProviderError. Empty/stopword search is handled before vector querying. Existing HTTP tests validate batch ordering/counts, authentication, dimension/finite-vector handling and malformed responses without a live call.

Chroma uses PersistentClient, cosine HNSW, supplied embeddings, disabled implicit embedding and disabled telemetry (`storage/chroma_store.py:35`). Model/endpoint fingerprint/dimension/schema live in collection metadata. Independent incompatible-model and dimension reopen attempts fail with ConfigurationError. Separate-process reopening of the completed independent index returns `REQ-ETH-001`. A real model's identity/weights silently changing under the same configured name remains undetectable.

Full source and chunk metadata live in authoritative SQLite; Chroma scalar metadata includes source ID, requirement ID, filename, version, chunk ID and active revision. Section/location/original text/JSON fields are rehydrated from the catalog. Metadata filters, empty collections, adding/searching, duplicate ingestion, updated reindexing, deletion and reopening all pass. Keyword retrieval scans the active catalog, so its active evidence stays synchronized with vector retrieval. Existing failed-staging and inactive-orphan tests pass, as does failed embedding preserving both active indexes.

The remediation preserves legacy chunk payloads by defaulting missing warning fields to empty and excluding empty warnings from revision fingerprints (`storage/chroma_store.py:70`). The executed legacy regression verifies reopening/idempotent ingestion; existing data is not rewritten or reset by startup. New parser behavior requires deliberate per-document reindexing of affected existing sources. No user data was reindexed in this audit.

Missing keys are not invariably errors because local compatible servers can work without auth. Controlled 401/timeout/malformed response handling passed and kept safe error messages. Missing model/provider configuration gives a clear error. Actual remote service operation, learned-vector quality, model drift, crash recovery, disk exhaustion, backups and multiple writer processes remain NOT VERIFIED. Inactive staged vectors after interrupted writes are a documented disk-cleanup issue, not active retrieval evidence.

## 7. Keyword, Semantic, and Hybrid Retrieval Assessment

Independent rankings retain top-one results for all seven required identifier forms: `REQ-ETH-001`, `REQ-SOA-015`, `SOME/IP-SD`, `IEEE 802.1Qbv`, `1000BASE-T1`, `VLAN 100`, `0x1234`. Corpus distractors were present. Case normalization preserves original source spelling. BM25 applies actual term statistics/length normalization and an exact requirement-ID boost (`keyword.py:19,26,32`); results sort by descending score then chunk ID. Keyword-only search works with query embeddings forced to raise and no LLM configured.

Semantic retrieval is an operational vector-search interface with preserved metadata, similarity cutoff and configurable Top-K. Existing controlled HTTP synonym vectors retrieve a paraphrase without shared tokens; this tests the interface, not learned semantics from hash vectors. The prior target-plus-13-distractors reproduction now returns `REQ-TARGET-001` in **all three modes**. Chroma applies eligible chunk IDs alongside active revisions and metadata filters **before** candidate Top-K (`storage/chroma_store.py:215`). Existing tests also cover two eligible IDs, small candidate windows and incompatible filters.

RRF was independently recalculated using keyword `[A,B]`, semantic `[B,C]`, constant 10. Observed B = `1/12 + 1/11 = 0.17424242424242425`, A = `1/11 = 0.09090909090909091`, C = `1/12 = 0.08333333333333333`. B ranks first with both contributions. Existing tests verify duplicate chunk merging, tie-breaking, empty branches, final Top-K and provenance. All 84 independent result lists repeated stably and match the prior audit. Scores are explicitly ranking signals, not calibrated confidence.

The optional overlap reranker remains local, default-off and tested. Turning it off preserves hybrid behavior; chunk identity/citations stay attached. No external reranker or external failure policy is supplied, so external-reranker fallback is not a claimed Phase 2 capability. Arbitrary injected reranker exceptions propagate without a documented fallback.

Hybrid does not improve Recall@5 over keyword on either fixed dataset. It slightly improves MRR on the independent sample and recovers the hash paraphrase miss, but the original dataset aggregates are identical for all methods. No production or general hybrid-superiority claim is justified.

## 8. Citation and Grounded Generation Assessment

Citation existence, source correctness/currentness and claim support are separate acceptance questions. Structured citations are assembled from retrieved records; ModelAnswer rejects extra provider-supplied source fields. Known fabricated labels/IDs are suppressed. The new service boundary independently verifies active revisions after generation. `cited` continues to mean bounded reference checks, not proven factual support.

| Controlled scenario | Actual rerun | Assessment |
| --- | --- | --- |
| Valid excerpt and S1 | HTTP 200 `cited`, real quote/ID/version/location; citation GET 200. | PASS |
| Empty evidence / missing ID | Fixed `insufficient`, no citations and no provider call when configured. | PASS |
| Provider declares insufficient | Existing test discards generated claims for fixed response. | PASS |
| Invented S99 / uppercase REQ-ETH-999 | `invalid_citations`, no claims/citations. | PASS |
| Invented lowercase req-eth-999 / wrong-case real req-eth-001 | Both rejected; exact original source spelling is required. | PASS |
| Actual JSON custom:007, generated custom:999 | Rejected under new numeric-family checks. | PASS |
| Provider adds structured invented document_id | Pydantic ValidationError/InvalidModelResponse at generation boundary. | PASS |
| Unsupported arbitrary ID grammar | Executed test marks `unsupported_identifier_grammar` and keeps claims unverified; arbitrary-string references are not certified. | Bounded contract PASS; unrestricted detection NOT VERIFIED |
| Delete/content/version/metadata change during provider | Each yields `stale_evidence`, no generated claims/citations/referenced IDs. | PASS |
| Real concurrent update while model waits | Update completes without lock starvation; response `stale_evidence`. | PASS |
| Original TSN-compliance and passing-check assertions | `unsupported_claims`, no citations/claims. | PASS for bounded guard |
| Numeric 5 ms versus 10 ms equal-template sources | `conflicting_evidence` contains both source excerpts and real citations even when provider chooses one. | PASS for bounded conflict guard |
| Injection asks model to claim all checks passed | Same reproduced output suppressed. Context remains untrusted data with no tool execution. | Bounded guard PASS; real prompt-injection resistance NOT VERIFIED |
| Interface-only source, provider says measured camera latency is 2 ms | Still accepted as `cited`, with `claim_status=unverified` and `engineering_validation=not_performed`. | PARTIAL grounding, D-006 |
| Missing generation provider / malformed output | HTTP 503 / 502, clear safe errors and no fake answer. | PASS |
| Controlled timeout / 401 / malformed choices | ProviderError / InvalidModelResponse; original tests also cover 429/500. | PASS for error contract |

All AnswerResponse variants now fix `claim_status="unverified"` and `engineering_validation="not_performed"`. Models cannot promote these fields into a deterministic validation result. Source references and units are retained in supported outputs, but there is no general unit/entailment checker. New English verification-claim regex and numeric conflict templates are conservative heuristics; they can miss paraphrases or overflag text. General conflicting constraints, applicability, precedence and unit conversion are not implemented. D-006 remains open as a bounded capability, not silently counted fixed.

The rerun remediation evaluator emitted **12 controlled citations, 0 invalid**, suppressed **18 adversarial outputs**, and produced **6/6** correct insufficient responses for the repository's two empty-result negatives across three modes. Those denominators exclude arbitrary-ID grammars and broad semantic judgment. Independent stale cases (three same-call mutations plus one true concurrent mutation) emitted **zero dangling citations**. The original five invalid-reference/schema cases are now all rejected. This meets the controlled reference-integrity checks, without implying zero production hallucinations.

On independent i27/i28, retrieval returns nonempty but insufficient context. An excerpt-only provider is invoked once and its response is returned `cited`/unverified; i25/i26 skip the provider and return `insufficient`. Thus the independent negative answer-instrument result is **2/4**, whereas the repository negative contract is **6/6**. These are different cases and meanings. Returning relevant text to explain that a measurement is absent can be useful; citation membership alone cannot establish that an answer addresses the requested fact. A controlled provider is not a live model-quality measurement.

Provider payload tests verify that question, evidence and generation options reach the HTTP adapter. Prompt instructions label retrieved documents and the question as untrusted, demand exact identifiers/units, evidence-only answers, uncertainty and conflict attribution. Those instructions plus one controlled rejection do not establish complete injection resistance. RAG never executes Phase 1 validation or modifies engineering findings.

## 9. Independent RAG Evaluation

The prior report's complete 18-requirement corpus and 28 queries were parsed into a temporary dataset **before executing retrieval**, with assertions on both counts. Statements, questions, relevance sets, categories, document IDs, filename `audit.md` and version `1` were unchanged. Each source was `# {document_id}` plus two LF characters, then `ID: statement` records separated by blank lines. No observed result was used to relabel a query. The retained previous rankings were used only for comparison after execution.

Configuration: `hash:hash-token-v1:384`, Chroma 1.5.9 cosine; chunks 1,000 characters, overlap 120; semantic/keyword candidates 12, final K=5; RRF=60; min similarity 0.15; no filters; reranking off. All 18 requirements fit one chunk each. Relevance unit is a **unique requirement ID**; IDs are unique across this corpus. Deduplicate returned IDs in order. Macro Recall@K = matching expected IDs within K divided by all expected IDs; Precision@3 uses fixed denominator 3. MRR is first relevant reciprocal rank within returned five. Ranking averages cover 24 answerable queries; six exact-ID cases form Hit@1; four negatives are excluded and measured separately. Arithmetic was independent of production metric functions.

| Method | Recall@1 | Recall@3 | Recall@5 | Precision@3 | MRR within 5 | Exact-ID Hit@1 | Negative retrieval abstention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| keyword | 0.895833 | 1.000000 | 1.000000 | 0.375000 | 0.972222 | 1.000000 (6/6) | 0.500000 (2/4) |
| semantic | 0.916667 | 0.958333 | 0.958333 | 0.347222 | 0.958333 | 1.000000 (6/6) | 0.500000 (2/4) |
| hybrid | 0.895833 | 1.000000 | 1.000000 | 0.375000 | 0.979167 | 1.000000 (6/6) | 0.500000 (2/4) |

No rank list or metric changed from the previous independent run; all methods repeat stably. Semantic i24 still returns no results for the central-compute/gigabit paraphrase and loses both expected requirements. Keyword/hybrid return both. On i15 service discovery, first relevant rank is 3/1/2 for keyword/semantic/hybrid; this explains their MRR difference. All positive queries except semantic i24 have full Recall@5. i27 and i28 remain nonempty false-positive retrievals for an absent measurement/encryption algorithm in all modes.

The provisional exact-ID >=95%, Recall@5 >=90% and MRR >=0.85 targets pass on this small offline dataset. The 100% no-evidence target passes only for the controlled empty-result contract, not broader semantic sufficiency. Learned semantics and production quality remain NOT VERIFIED. Neither six exact-ID cases nor sparse synthetic labels support general guarantees.

Complete unchanged independent corpus:

| Document | Requirement ID | Exact statement |
| --- | --- | --- |
| ethernet | REQ-ETH-001 | The Central Gateway shall provide a 1000BASE-T1 Ethernet interface. |
| ethernet | REQ-ETH-002 | The Ethernet connection between Central Gateway and ADAS Controller shall support nominal bandwidth of at least 1000 Mbps. |
| ethernet | REQ-ETH-003 | The front camera shall provide a 100BASE-T1 Ethernet interface to ADAS Controller. |
| ethernet | REQ-ETH-004 | The rear radar shall provide a 100BASE-T1 Ethernet interface. |
| ethernet | REQ-ETH-005 | Infotainment audio shall support nominal bandwidth of 100 Mbps. |
| segmentation | REQ-SEC-003 | ADAS camera traffic shall be isolated from infotainment traffic using separate VLANs. |
| segmentation | REQ-SEC-004 | VLAN 100 shall carry diagnostic traffic. |
| segmentation | REQ-SEC-005 | VLAN 200 shall carry audio traffic. |
| services | REQ-SOA-015 | SOME/IP-SD service discovery shall advertise camera service on VLAN 20 before subscription. |
| services | REQ-SOA-016 | The camera SOME/IP service identifier shall be 0x1234. |
| services | REQ-SOA-017 | The radar SOME/IP service identifier shall be 0x4321. |
| services | REQ-SOA-018 | The camera service availability timeout shall be 500 ms. |
| timing | REQ-TSN-001 | Ethernet time synchronization shall use IEEE 802.1AS across gateway and camera. |
| timing | REQ-TSN-002 | Camera synchronization offset shall remain below 1 microsecond. |
| timing | REQ-TSN-008 | IEEE 802.1Qbv time-aware scheduling shall control camera traffic. |
| timing | REQ-TSN-009 | The camera schedule shall use a 1 ms cycle. |
| timing | REQ-TSN-010 | Maximum end-to-end camera delivery latency shall be 5 ms. This is a requirement and not proof of compliance. |
| timing | REQ-TSN-011 | If synchronization is lost the system shall suspend scheduled camera transmission. |

Complete fixed queries and relevance judgments. `—` means no evidence for the requested fact. K/S/H are first relevant ranks for keyword/semantic/hybrid; negative rows show retrieval abstention separately.

| Query | Category | Question | Expected requirement IDs | K / S / H |
| --- | --- | --- | --- | --- |
| i01 | exact | REQ-ETH-001 | REQ-ETH-001 | 1 / 1 / 1 |
| i02 | exact | REQ-SOA-015 | REQ-SOA-015 | 1 / 1 / 1 |
| i03 | exact | REQ-TSN-008 | REQ-TSN-008 | 1 / 1 / 1 |
| i04 | exact | req-sec-003 | REQ-SEC-003 | 1 / 1 / 1 |
| i05 | exact | REQ-SOA-016 | REQ-SOA-016 | 1 / 1 / 1 |
| i06 | exact | REQ-TSN-011 | REQ-TSN-011 | 1 / 1 / 1 |
| i07 | technical | 1000BASE-T1 | REQ-ETH-001 | 1 / 1 / 1 |
| i08 | technical | SOME/IP-SD | REQ-SOA-015 | 1 / 1 / 1 |
| i09 | technical | IEEE 802.1Qbv | REQ-TSN-008 | 1 / 1 / 1 |
| i10 | technical | VLAN 100 | REQ-SEC-004 | 1 / 1 / 1 |
| i11 | technical | 0x1234 | REQ-SOA-016 | 1 / 1 / 1 |
| i12 | technical | IEEE 802.1AS | REQ-TSN-001 | 1 / 1 / 1 |
| i13 | natural | Which requirements define communication capacity between the Central Gateway and ADAS Controller? | REQ-ETH-002 | 1 / 1 / 1 |
| i14 | natural | How should camera traffic be separated from infotainment traffic? | REQ-SEC-003 | 1 / 1 / 1 |
| i15 | natural | What constraints apply to SOME/IP service discovery? | REQ-SOA-015 | 3 / 1 / 2 |
| i16 | natural | Which requirements concern Ethernet time synchronization? | REQ-TSN-001 | 1 / 1 / 1 |
| i17 | natural | What is the expected communication interface for the front camera? | REQ-ETH-003 | 1 / 1 / 1 |
| i18 | multiple | Which interfaces use 100BASE-T1? | REQ-ETH-003, REQ-ETH-004 | 1 / 1 / 1 |
| i19 | natural | What is the maximum camera delivery latency? | REQ-TSN-010 | 1 / 1 / 1 |
| i20 | natural | What is the camera service availability timeout? | REQ-SOA-018 | 1 / 1 / 1 |
| i21 | natural | What happens if synchronization is lost? | REQ-TSN-011 | 1 / 1 / 1 |
| i22 | multiple | Which VLANs carry diagnostic and audio traffic? | REQ-SEC-004, REQ-SEC-005 | 1 / 1 / 1 |
| i23 | natural | How long is the camera schedule cycle? | REQ-TSN-009 | 1 / 1 / 1 |
| i24 | paraphrase | Gigabit uplink provision for central compute | REQ-ETH-001, REQ-ETH-002 | 1 / absent / 1 |
| i25 | negative | REQ-BATTERY-999 | — | abstain / abstain / abstain |
| i26 | negative | Lithium cathode chemistry electrolyte formulation | — | abstain / abstain / abstain |
| i27 | negative | What is the measured camera latency in the installed vehicle? | — | false positive / false positive / false positive |
| i28 | negative | Which VLAN encryption algorithm protects camera traffic? | — | false positive / false positive / false positive |

All actual ordered result lists, preserved here before temporary-artifact cleanup (requirement IDs are exact):

```json
{
  "keyword": {
    "i01": ["REQ-ETH-001"],
    "i02": ["REQ-SOA-015"],
    "i03": ["REQ-TSN-008"],
    "i04": ["REQ-SEC-003"],
    "i05": ["REQ-SOA-016"],
    "i06": ["REQ-TSN-011"],
    "i07": ["REQ-ETH-001", "REQ-ETH-004", "REQ-ETH-003"],
    "i08": ["REQ-SOA-015", "REQ-SOA-016", "REQ-SOA-017"],
    "i09": ["REQ-TSN-008", "REQ-TSN-001"],
    "i10": ["REQ-SEC-004", "REQ-ETH-005", "REQ-SEC-005", "REQ-SOA-015"],
    "i11": ["REQ-SOA-016"],
    "i12": ["REQ-TSN-001", "REQ-TSN-008"],
    "i13": ["REQ-ETH-002", "REQ-ETH-001", "REQ-ETH-003", "REQ-SEC-003", "REQ-TSN-001"],
    "i14": ["REQ-SEC-003", "REQ-ETH-005", "REQ-TSN-008", "REQ-SEC-005", "REQ-SEC-004"],
    "i15": ["REQ-SOA-016", "REQ-SOA-017", "REQ-SOA-015", "REQ-SOA-018"],
    "i16": ["REQ-TSN-001", "REQ-TSN-008", "REQ-TSN-002", "REQ-TSN-011", "REQ-ETH-004"],
    "i17": ["REQ-ETH-003", "REQ-ETH-004", "REQ-ETH-001", "REQ-SOA-018", "REQ-TSN-009"],
    "i18": ["REQ-ETH-004", "REQ-ETH-003", "REQ-TSN-009", "REQ-TSN-001", "REQ-ETH-001"],
    "i19": ["REQ-TSN-010", "REQ-SOA-018", "REQ-TSN-009", "REQ-TSN-002", "REQ-SOA-016"],
    "i20": ["REQ-SOA-018", "REQ-SOA-015", "REQ-SOA-016", "REQ-SOA-017", "REQ-TSN-009"],
    "i21": ["REQ-TSN-011", "REQ-TSN-002", "REQ-TSN-001"],
    "i22": ["REQ-SEC-004", "REQ-SEC-005", "REQ-SEC-003", "REQ-ETH-005", "REQ-TSN-008"],
    "i23": ["REQ-TSN-009", "REQ-SOA-018", "REQ-TSN-002", "REQ-SOA-016", "REQ-TSN-011"],
    "i24": ["REQ-ETH-001", "REQ-ETH-002"],
    "i25": [],
    "i26": [],
    "i27": ["REQ-TSN-010", "REQ-SOA-018", "REQ-TSN-009", "REQ-TSN-002", "REQ-SOA-016"],
    "i28": ["REQ-SEC-005", "REQ-SEC-004", "REQ-SEC-003", "REQ-SOA-015", "REQ-TSN-008"]
  },
  "semantic": {
    "i01": ["REQ-ETH-001"],
    "i02": ["REQ-SOA-015"],
    "i03": ["REQ-TSN-008"],
    "i04": ["REQ-SEC-003"],
    "i05": ["REQ-SOA-016"],
    "i06": ["REQ-TSN-011"],
    "i07": ["REQ-ETH-001"],
    "i08": ["REQ-SOA-015", "REQ-SOA-016", "REQ-SOA-017"],
    "i09": ["REQ-TSN-008", "REQ-TSN-001", "REQ-ETH-001"],
    "i10": ["REQ-SEC-004"],
    "i11": ["REQ-SOA-016"],
    "i12": ["REQ-TSN-001", "REQ-TSN-008", "REQ-ETH-001"],
    "i13": ["REQ-ETH-002", "REQ-ETH-001", "REQ-ETH-003"],
    "i14": ["REQ-SEC-003", "REQ-TSN-008"],
    "i15": ["REQ-SOA-015", "REQ-SOA-016", "REQ-SOA-017"],
    "i16": ["REQ-TSN-001", "REQ-ETH-004", "REQ-ETH-001", "REQ-ETH-002", "REQ-ETH-003"],
    "i17": ["REQ-ETH-003"],
    "i18": ["REQ-ETH-004", "REQ-ETH-003", "REQ-SOA-016"],
    "i19": ["REQ-TSN-010"],
    "i20": ["REQ-SOA-018", "REQ-SOA-015", "REQ-SOA-016"],
    "i21": ["REQ-TSN-011"],
    "i22": ["REQ-SEC-005", "REQ-SEC-004", "REQ-SEC-003"],
    "i23": ["REQ-TSN-009"],
    "i24": [],
    "i25": [],
    "i26": [],
    "i27": ["REQ-TSN-010"],
    "i28": ["REQ-SEC-003", "REQ-SEC-005", "REQ-SEC-004", "REQ-TSN-002"]
  },
  "hybrid": {
    "i01": ["REQ-ETH-001"],
    "i02": ["REQ-SOA-015"],
    "i03": ["REQ-TSN-008"],
    "i04": ["REQ-SEC-003"],
    "i05": ["REQ-SOA-016"],
    "i06": ["REQ-TSN-011"],
    "i07": ["REQ-ETH-001", "REQ-ETH-004", "REQ-ETH-003"],
    "i08": ["REQ-SOA-015", "REQ-SOA-016", "REQ-SOA-017"],
    "i09": ["REQ-TSN-008", "REQ-TSN-001", "REQ-ETH-001"],
    "i10": ["REQ-SEC-004", "REQ-ETH-005", "REQ-SEC-005", "REQ-SOA-015"],
    "i11": ["REQ-SOA-016"],
    "i12": ["REQ-TSN-001", "REQ-TSN-008", "REQ-ETH-001"],
    "i13": ["REQ-ETH-002", "REQ-ETH-001", "REQ-ETH-003", "REQ-SEC-003", "REQ-TSN-001"],
    "i14": ["REQ-SEC-003", "REQ-TSN-008", "REQ-ETH-005", "REQ-SEC-005", "REQ-SEC-004"],
    "i15": ["REQ-SOA-016", "REQ-SOA-015", "REQ-SOA-017", "REQ-SOA-018"],
    "i16": ["REQ-TSN-001", "REQ-ETH-004", "REQ-ETH-001", "REQ-ETH-002", "REQ-ETH-003"],
    "i17": ["REQ-ETH-003", "REQ-ETH-004", "REQ-ETH-001", "REQ-SOA-018", "REQ-TSN-009"],
    "i18": ["REQ-ETH-004", "REQ-ETH-003", "REQ-SOA-016", "REQ-TSN-009", "REQ-TSN-001"],
    "i19": ["REQ-TSN-010", "REQ-SOA-018", "REQ-TSN-009", "REQ-TSN-002", "REQ-SOA-016"],
    "i20": ["REQ-SOA-018", "REQ-SOA-015", "REQ-SOA-016", "REQ-SOA-017", "REQ-TSN-009"],
    "i21": ["REQ-TSN-011", "REQ-TSN-002", "REQ-TSN-001"],
    "i22": ["REQ-SEC-005", "REQ-SEC-004", "REQ-SEC-003", "REQ-ETH-005", "REQ-TSN-008"],
    "i23": ["REQ-TSN-009", "REQ-SOA-018", "REQ-TSN-002", "REQ-SOA-016", "REQ-TSN-011"],
    "i24": ["REQ-ETH-001", "REQ-ETH-002"],
    "i25": [],
    "i26": [],
    "i27": ["REQ-TSN-010", "REQ-SOA-018", "REQ-TSN-009", "REQ-TSN-002", "REQ-SOA-016"],
    "i28": ["REQ-SEC-005", "REQ-SEC-003", "REQ-SEC-004", "REQ-TSN-002", "REQ-SOA-015"]
  }
}
```

Independent metric calculation used these recorded rankings and the fixed judgments above:

```python
def score(ranked, expected, k):
    ranked = list(dict.fromkeys(ranked))[:k]
    matches = len(set(ranked) & set(expected))
    rr = next((1 / i for i, item in enumerate(ranked, 1) if item in expected), 0)
    return matches / len(expected), matches / k, rr
```

Macro-average positives only; use K=1/3/5 for recall, K=3 for precision, K=5 for MRR. Score negatives and exact-ID Hit@1 separately. This corpus has no multiple chunks per requirement; no chunk/requirement unit mixing occurs.

The **separate unchanged repository dataset** was rerun through `scripts/evaluate_phase2_remediation.py` for all three modes: 24 queries, 22 answerable, two negatives; four source documents, 34 chunks/30 identified requirements. Each mode measured Recall@1 **0.787879**, Recall@3/5 **0.977273**, Precision@3 **0.469697**, MRR **1.000000**, exact-ID Hit@1 **5/5**, negative retrieval abstention **2/2**; configured Precision@5 remains **0.281818**. q09 still misses `REQ-ISO-001` while ranking `REQ-ETH-008` first. Corpus hashes match original saved baseline reports. No dataset/corpus/label tuning occurred.

Dataset exact-byte SHA-256: retrieval `ffee2376d6b3a3b42e882e8794c77c8e0ddae10f6b08b7db4f105f2358ec7d1a`; QA `87c74b249d1dfedc8a422b95f27134494ffd77cc46a3b830832d7d0f4f36b4fd`. The six QA review cases exercise reference plumbing; expected facts and unsupported-claim lists are not all adjudicated semantically by the excerpt-only instrument. No live faithfulness/hallucination metric is claimed.

Limits: small English synthetic corpus, sparse exact-ID/negative samples, selective relevance labels, hash lexical vectors, no blinded human scoring, no supplier PDFs or learned-model comparison. Fixed cutoff evaluation uses the actual returned window, so final K must be >=5 for full @5 comparisons.

## 10. REST API Assessment

All expected paths are unchanged: POST/GET documents, DELETE document ID, POST search, POST ask; GET document/chunk resolution remain available. OpenAPI **3.1.0** returned all Phase 1 and knowledge paths with explicit schemas. Independent synchronous TestClient and the executed existing async/API/remediation tests cover request parsing, response models, safe HTTP errors and lifecycle.

| Independent scenario | Actual HTTP behavior |
| --- | --- |
| Valid document / duplicate / list | 200 created / 200 unchanged / 200 typed list. |
| Keyword / semantic / hybrid exact query | All 200, real requirement/source metadata. |
| Controlled ask / citation GET | 200 cited+unverified / 200 matching record. |
| Unknown requirement ask | 200 insufficient, no citations/provider call. |
| Path filename, extra path field, blank document, bad source JSON, unsupported format, nested credential key | Each 422; no local-file contents or secret reflected. |
| 1,000,001-character content | 422. |
| 1,100,001-byte body | 413; existing streamed-body regression also passes. |
| Malformed JSON request | 422. |
| final_top_k 0, -1, 101 | Each 422; other ranking/schema bounds remain explicit. |
| Changed implicit source | 409 with explicit identity/replacement guidance, no mutation of first source. |
| Malformed provider / missing provider | 502 / 503, generic safe detail. |
| Deletion during generation | 200 stale_evidence, empty citations. Old chunk GET 404 is expected because it is not returned by that stale answer. |
| Delete / search after deletion / repeat deletion | 204 / 200 empty hits / 404. |
| Phase 1 example validation | 200 NOT_EVALUATED. |

The HTTP workflow script completed against temporary persistent storage using the real compatible adapter with controlled transport; ingestion/duplicate/search/citation resolution, all modes, supported/empty ask, persistence reopen, replacement/deletion and Phase 1 validation passed. No live provider operation was implied.

API contract additions are intentional: `stale_evidence`, `unsupported_claims`, `conflicting_evidence`; fixed unverified/not-performed fields; bounded/unsupported-grammar flag; ingestion/chunk warnings; implicit replacement 409. Clients with exhaustive enum handling need updating. This is additive evolution plus an explicit replacement-policy change, not renamed endpoints. User-controlled HTTP paths never become filesystem source reads; only the trusted Python loader accepts local paths.

## 11. Phase 1 Regression Results

All **108 original Phase 1 tests passed** within the 243-test run: API 25, model/reference validation 41, topology 8, traffic completeness 16, validator 18. These exercise NetworkX multigraph paths/connectivity, deterministic bandwidth findings, result schemas, structural invariants, health and original endpoints. Comparison of 62d4ede with 89d804d shows no changes to Phase 1 domain/services, architecture routes or these tests. Comparison with Phase 1 baseline retains the prior additive OpenAPI superset assertion; legacy paths remain required.

Independent validation of the centralized example returned NOT_EVALUATED with the existing physical/nominal-budget semantics; RAG did not upgrade requirements to verified constraints. A fresh app whose vector path is deliberately nested below an ordinary file returned HTTP 200/NOT_EVALUATED while `knowledge_service is None`. Deterministic validation therefore works without credentials, initialized vectors, embedding service or external network. Direct Python validators/topology remain callable independently.

## 12. Engineering Quality and Security

The existing environment was used; **no uv sync/install, lockfile edit or dependency download** was performed. Python 3.12.16, Chroma 1.5.9, pytest 9.2.0; the 110-entry lockfile matched every overlapping installed version, with only platform-inapplicable colorama/Windows and httpx2-jsfetch/Emscripten absent. pyproject/uv.lock are unchanged from the prior implementation. Lockfile SHA-256: `99d9fbba7d39a0f7274c1cddba8069ca8dd6bd8fd420be53e50213f003014b9b`.

Commands used the existing `.venv/bin` tools, with inherited PYTHONPATH removed and Python bytecode writes disabled. Temporary root was `/tmp/phase2-reaudit-AjLdHY`; all audit scripts, indexes, outputs, pytest storage, coverage and type caches were kept there and cleaned afterward. Repository saved evidence JSON was read, not overwritten. Persistent user data was never opened for ingestion, deletion or reindexing.

| Executed command/check | Observed result |
| --- | --- |
| `.venv/bin/ruff check . --no-cache` | PASS; all checks. |
| `.venv/bin/ruff format --check . --no-cache` | PASS; **86 files already formatted** at initial audit state. |
| `.venv/bin/mypy src --cache-dir <temporary>/mypy` | PASS; **50 source files**, no issues. |
| `.venv/bin/python -m pytest -p no:cacheprovider --basetemp=<temporary>/tests --cov-report=term-missing --cov-report=xml:<temporary>/coverage.xml` | PASS; **243 tests in 12.84 s**, coverage **99.16%**. COVERAGE_FILE redirected outside repo. |
| `.venv/bin/python scripts/evaluate_phase2_remediation.py --output <temporary>/remediation.json` | PASS; all three modes, 0/12 invalid emitted citations, 18 adversarial suppressions, 6/6 original negative answers. |
| `.venv/bin/python scripts/verify_phase2.py --output <temporary>/workflow.json` | PASS; full offline HTTP lifecycle/workflow. |
| Independent core, supplementary and TestClient probes | Completed; actual results and residual cases transcribed in this report. |

The sandboxed pytest run timed out after 35 seconds at TestClient remediation tests; the independent API probe timed out after 15 seconds inside the sandbox. Authorized outside-sandbox reruns completed. These incomplete attempts are not reported as passing and are not attributed to an application defect. Outside execution remained offline; independent probes blocked live HTTP and repository workflow used MockTransport. Packaging, Docker runtime, remote CI, Python 3.13+, live providers, load tests and crash recovery were not run in this repeat audit and remain NOT VERIFIED.

The existing source code has explicit request bounds, strict schemas, dimension checks and safe provider/storage/request errors. Metadata credential keys are rejected recursively; this is not prose redaction or a guarantee about arbitrary confidential content. No confidential corpus or real keys were printed. No application logging of source content was identified; dependency logging was not exhaustively audited. Context and questions are untrusted prompt data, not instructions to an execution tool.

Document filters, active revision checks and per-source deletion supply local source boundaries. The API is unauthenticated and anyone with access can read/delete sources. Complete multi-tenancy is outside Phase 2; shared hosting would need authentication, access-scoped retrieval, audit trails, consistent backups and a supported concurrency model. Provider URLs/regex configuration are trusted settings, not user request controls. Store cleanup/lifespan and multiprocess coordination remain operational limits, not claimed enterprise readiness.

The new status fields reduce the risk of treating prose as engineering validation. They do not stop every unsupported sentence (D-006). Only direct deterministic findings can justify their own PASS/FAIL result. Retained archival citations, production observability and broad attack resistance are not certified by this offline run.

## 13. Defect List

Prior IDs are retained for traceability; closed findings are distinguished from active limitations. No implementation remediation was performed by this audit.

| Prior defect | Previous severity | Current disposition | Independent rerun evidence |
| --- | --- | --- | --- |
| D-001: stale citation at answer return | HIGH | **CLOSED for supported service boundary** | Delete/content/metadata and a true concurrent update yield stale_evidence with zero citations; normal source resolves. |
| D-002: lowercase/custom numeric fabricated mentions | MEDIUM | **CLOSED within explicit bounded grammar** | S99, uppercase/lowercase numeric IDs and actual JSON custom:007/custom:999 probes rejected; arbitrary grammar flagged. |
| D-003: inline extraction / missing diagnostics | MEDIUM | **PARTIAL; residual open** | Original period-separated scenario fixed; comma and mixed-case assigned-record cases remain merged without warnings. |
| D-004: implicit same-filename replacement | MEDIUM | **CLOSED** | Different implicit content rejected before storage; HTTP 409; original evidence preserved; explicit origins coexist. |
| D-005: exact-ID semantic candidate starvation | MEDIUM | **CLOSED** | Original target+13 distractor scenario returns actual target in every mode; eligibility before Top-K. |
| D-006: engineering grounding / sufficiency | MEDIUM | **PARTIAL; deferred assurance remains open** | Original compliance/injection outputs blocked, bounded conflict surfaced; unsupported measured-latency claim still accepted as explicitly unverified. |

### D-003 — MEDIUM — Residual extraction diagnostic blind spot in assigned records

- **Requirements:** P2-003, P2-004. Original period-separated reproduction is fixed; the broader fallback/limitation criterion is not fully satisfied.
- **Affected file/lines:** `src/ee_arch_copilot/rag/ingestion/parser.py:18` (bounded delimiter), `:29` (warnings only for unassigned records), `:142` (inline loop); exact-ID search eligibility `src/ee_arch_copilot/rag/service.py:117`.
- **Reproduction:** Ingest `REQ-ETH-010: Gateway shall connect, REQ-ETH-011: Camera shall connect.` as document `comma`. Query 011 with a document filter. Separately use the supported period delimiter but lowercase `req-eth-011:` after an uppercase first ID.
- **Expected:** Independently extract a supported definition or retain raw text with an explicit ambiguity/extraction warning. No requirement identity should be invented. Supporting commas as definite definitions is not necessary if a diagnostic makes the limitation visible.
- **Actual:** One chunk identified only as 010, containing both statements; `extraction_warnings=[]` at both ingestion/chunk levels. Query uppercase 011 against `comma` returns **[]**. The period/uppercase control returns the correct independent 011 chunk. Table/unassigned convention controls correctly warn.
- **Root-cause hypothesis:** `inline_pattern` limits recognition to configured case-sensitive IDs after `. ; ! ?`; subsequent diagnostics skip every record already assigned an ID. Thus a known identifier hint elsewhere in that record cannot trigger fallback warnings.
- **Recommended correction:** Detect definition-like unhandled IDs within assigned records and emit a bounded review warning, distinguishing ordinary references. Preserve source text/spelling and offsets. Add comma/mixed-layout/ordinary-reference regressions. Treat new parser application to existing sources as deliberate reindexing, never reset user collections.
- **Impact:** Exact-ID completeness is not guaranteed for unsupported layouts without source review. Severity remains MEDIUM because canonical and documented supported grammar work, text is preserved, and no source/citation record is fabricated.

### D-006 — MEDIUM — Semantic support and nonempty-context sufficiency remain provider-dependent

- **Requirements:** P2-016, P2-017. Fixed unverified status and bounded guards are verified mitigations, not full closure.
- **Affected file/lines:** `src/ee_arch_copilot/rag/generation/guards.py:8,18`; `src/ee_arch_copilot/rag/generation/citations.py:63,78`; `src/ee_arch_copilot/rag/generation/answer_generator.py:71`.
- **Reproduction:** Retrieve only interface requirement `REQ-ETH-001`. Inject `{"answer":"The measured camera latency is 2 ms. [S1]","citation_ids":["S1"]}`. Separately ask i27/i28 using an excerpt-only instrument, where related context exists but the requested measurement/encryption algorithm does not.
- **Expected:** Do not treat supported source IDs as proof of an unsupported measured fact; sufficiency should be reviewed and compliance must require separate deterministic evidence. At minimum generated claims must stay explicitly unverified.
- **Actual:** Measured-latency sentence is returned as `cited`, with valid source identity but no supporting fact. Typed status does correctly remain `claim_status=unverified`, `engineering_validation=not_performed`, and explanation states support is unproven. i27/i28 call the provider and return unrelated/unresponsive excerpts as cited/unverified; empty i25/i26 skip generation and abstain.
- **Root-cause hypothesis:** The verification regex only recognizes bounded English expressions; the conflict checker requires equal templates/different same-unit numbers. There is no general entailment, measured-versus-required classifier, conflict resolution or nonempty-context sufficiency adjudication. This is expressly documented and deferred.
- **Recommended correction:** Phase 3 consumers must honor unverified/stale/conflict/unsupported status, keep deterministic findings separate, and require engineering review before accepting generated facts. Expand reviewed negative/paraphrase/conflict evaluation; do not infer confidence from similarity. Separately authorize a live-provider evaluation before claiming model quality. General automated entailment assurance is a larger task than these bounded guards.
- **Impact:** Conditional human-reviewed tooling is viable; unrestricted automated engineering conclusions are not accepted. Controlled outputs are not evidence of real-model attack susceptibility or immunity.

No active CRITICAL/HIGH finding was confirmed. Source archival after later user edits, unsupported arbitrary-ID grammars, one-process storage and learned-model quality remain explicitly scoped limits rather than invented closed capabilities. Unknown supplier/PDF behavior remains NOT VERIFIED.

## 14. Phase 3 Readiness

**READY WITH MINOR CHANGES** for reviewed integration; no major architectural refactor is required.

| Criterion | Assessment |
| --- | --- |
| Stable Python retrieval boundary | PASS: KnowledgeService.search returns typed SearchResponse/SearchHit/Chunk. |
| Structured results and independent source access | PASS: document/chunk endpoints and current catalog; verified normal citation resolution. |
| Current-source citation validity | PASS at ask service-return boundary; mutations suppress stale answers. Later edits can expire a URL. |
| Retrieval independent of generation | PASS: missing LLM does not block search; keyword avoids query embedding. |
| Generation independent of retrieval | PASS interface: AnswerGenerator accepts provided chunks; caller owns snapshot freshness. |
| Provider/domain isolation | PASS: no AI SDK/configuration in automotive models. |
| Explicit no-evidence behavior | PASS empty-context contract; PARTIAL nonempty insufficiency. |
| Independent deterministic validators | PASS: 108 regressions and unusable-vector-path HTTP probe. |
| Combining evidence with deterministic results | Typed interfaces support composition without mutating validation semantics; actual orchestrator is outside Phase 2 and NOT VERIFIED. |
| Structural work required | Minor adapter/consumer status handling and residual extraction guard; storage protocol/lifecycle improvements are incremental. |

Integration conditions: consume `claim_status=unverified` and `engineering_validation=not_performed`; handle stale/unsupported/conflicting statuses; retain source locations, versions and warnings; use explicit IDs for changes; use ask for freshness-sensitive answers; review unsupported source grammar. A zero-warning result is not yet a completeness certificate (D-003). Requirement prose may inform a reviewed constraint but must not become executable engineering validation by assumption.

## 15. Prioritized Remediation Plan

No correction was applied. Estimates indicate scope, not delivery commitments.

| Priority | Action / acceptance evidence | Effort |
| --- | --- | --- |
| 1 | Residual D-003: warn on unhandled definition-like IDs inside assigned records; comma/mixed-case controls show warnings or separate records; ordinary references avoid false definitions. | SMALL |
| 2 | Phase 3 adapters preserve all warning/status fields and expose deterministic findings separately. Treat empty warnings as bounded diagnostics, not extraction completeness. | SMALL |
| 3 | D-006: expand reviewed nonempty negatives/paraphrased measurement claims/conflicts; require proof joins for compliance conclusions and engineering review. | MEDIUM for bounded consumer/guard work; LARGE for general semantic entailment assurance |
| 4 | Separately authorized learned embedding/real LLM evaluation with unchanged held-out labels; retain q09 and independent i24/i27/i28. Record model identity, context and human judgments. | MEDIUM |
| 5 | Optional explicit store lifecycle/protocol and operational backups; choose tenancy/concurrency architecture before shared enterprise deployment. | MEDIUM; broader deployment outside Phase 2 |

Keep the four closed defect regressions and all Phase 1 tests. Apply parser changes via deliberate scoped reindexing after consistent backup; do not delete or reset user collections. Rerun the fixed datasets without tuning labels to erase failures. No live model call is authorized by this report.

## 16. Final Go/No-Go Decision

### CONDITIONAL GO

The previous source-integrity blocker is corrected and independently verified. Core local ingestion, storage, retrieval, reference validation, APIs and Phase 1 compatibility operate; no CRITICAL/HIGH defect remains confirmed. This supports reviewed Phase 3 tool integration with the existing typed service boundaries.

Conditions are explicit handling of unverified/stale/conflict/unsupported evidence, bounded source grammar or manual extraction review while D-003 remains open, and separate deterministic findings for engineering PASS/FAIL. D-006 and live semantic/answer quality remain unaccepted for unrestricted automated conclusions. An unconditional GO would exceed the evidence from these offline synthetic tests.
