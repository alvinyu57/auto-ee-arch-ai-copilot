# Phase 2 independent verification report

Audit date: **2026-11-10 (Europe/Berlin)**. Audited commit: **89d804d** (`Phase2: draft`), compared with Phase 1 commit **2795a54**. This is an acceptance audit, not implementation or remediation. Only this report was created in the repository. No source, test, golden label, dependency, configuration or user index was changed.

## 1. Executive Summary

**NO-GO for Phase 2 acceptance and unrestricted Phase 3 integration.** The core local pipeline operates and all existing tests pass. A confirmed **HIGH** defect lets generation return an already unresolvable citation after its source changes during the provider call. This violates a primary acceptance condition even within one shared service/process. Other confirmed limitations concern inline requirement boundaries, identifier validation, implicit document identity, exact-ID semantic candidates and generation support checks.

Across the 27 traceability rows: **16 PASS, 8 PARTIAL, 3 FAIL, 0 NOT VERIFIED, 0 NOT APPLICABLE**. Row status aggregates tested behavior and limitations; individual capabilities below can be NOT VERIFIED even when their encompassing requirement is PARTIAL/PASS. Defects: **0 CRITICAL, 1 HIGH, 5 MEDIUM, 0 LOW**. No confirmed persistent-vector corruption, confidential-document exposure or Phase 1 regression was observed.

**215/215 existing tests passed**, including **108 Phase 1** and **107 Phase 2** tests. Measured configured coverage: **99.10%**, 1,437 statements, seven missed statements, 344 branches and nine partial branches. Ruff lint, formatting check and strict source mypy passed.

Independent retrieval evaluation: **28 fixed queries**, 24 answerable and four no-evidence cases, against **18 independently authored requirements**. Keyword/hybrid Recall@5 = **1.000000**; hash-vector semantic Recall@5 = **0.958333**. Exact-ID Hit@1 = **6/6** for each mode. Retrieval abstention on negatives = **2/4** for each mode. These are small synthetic/offline results, not production semantic or answer quality evidence. The repository's original 24-query metrics reproduced unchanged.

Phase 3 structure: **READY WITH MINOR CHANGES**. Existing typed Python boundaries support tools without a major architectural rewrite. This structural assessment does not override the NO-GO acceptance decision: current-source citation integrity must be corrected and reverified first.

Evidence provenance: repository documentation, all Phase 2 modules/tests, supplied synthetic documents and datasets, and independently executed temporary probes. No separate original Phase 2 specification was found among tracked/hidden project files; the supplied acceptance request, roadmap and ADR 0002 form the available requirements basis. The implementation report and saved JSON were treated as prior claims, not independent execution evidence. No live embedding or LLM APIs were called. The main independent core/API probes blocked real HTTP transport and used injected providers/MockTransport only; supplementary probes used local hash embeddings and storage only.

## 2. Requirement Traceability Matrix

Path convention: `ingestion/`, `embeddings/`, `storage/`, `retrieval/`, `generation/`, `evaluation/` and unqualified RAG module filenames are relative to `src/ee_arch_copilot/rag/`. `api/`, `core/`, `domain/`, `services/` and `main.py` are relative to `src/ee_arch_copilot/`. Paths beginning `tests/`, `data/`, `docs/`, plus root configuration files, are repository relative. Numbers after colons are source lines at the audited commit. PASS requires execution evidence; PARTIAL explicitly includes material limits. Optional PDF and reranking are implemented and assessed rather than marked NOT APPLICABLE.

| ID | Requirement | Implementation location | Execution/test evidence | Status | Comments/limitations |
| --- | --- | --- | --- | --- | --- |
| P2-001 | Markdown/TXT/JSON ingestion | `ingestion/loader.py:12,47; ingestion/parser.py:18` | Existing ingestion tests; independent canonical Markdown, Unicode TXT and structured JSON ingestion; API validation. | **PASS** | Required formats work; JSON requires the documented array/envelope schema. |
| P2-002 | Document identity and metadata | `ingestion/loader.py:31; models.py:18,60` | Independent duplicate, Unicode, inherited JSON version, metadata-override and same-filename probes. | **PARTIAL** | Stable explicit IDs and provenance; implicit basename identity overwrites distinct origins (D-004). |
| P2-003 | Requirement extraction | `ingestion/parser.py:14,103; service.py:99` | Canonical three IDs pass; same-line second ID cannot be searched; variants/tables retain text without IDs. | **FAIL** | Silent extraction incompleteness violates the requested boundary/limitation contract (D-003). |
| P2-004 | Requirement-aware chunking | `ingestion/chunker.py:13; ingestion/parser.py:109` | Existing chunk tests; independent canonical offsets and 30 long fragments. | **PARTIAL** | Correct for extracted records; cannot recover silently merged requirements (D-003). |
| P2-005 | Stable chunk identifiers | `ingestion/chunker.py:33` | Existing deterministic/long-JSON tests; repeated canonical ingestion has identical IDs and three vectors. | **PASS** | Content/version/locations determine identity; metadata-only changes can preserve IDs. |
| P2-006 | Embedding provider abstraction | `embeddings/base.py:7; embeddings/providers.py:35` | Existing MockTransport batching/order/auth tests, dimension errors and injected-provider retrieval. | **PASS** | Document/query interfaces and real HTTP adapter verified offline; live service NOT VERIFIED. |
| P2-007 | Offline embedding test provider | `embeddings/providers.py:14` | Independent repeated/distinct/empty vectors; existing normalized-vector tests. | **PASS** | Meaningful lexical variation, deterministic; no learned semantic claim. |
| P2-008 | Persistent vector storage | `storage/chroma_store.py:30,85,184` | Existing persistence/staging tests; independent reopen in a separate interpreter and filtered search. | **PASS** | Persistent Chroma plus authoritative catalog works for documented single-service scope. |
| P2-009 | Idempotent ingestion | `service.py:62; storage/chroma_store.py:70` | Independent unchanged ingestion, stable timestamp/IDs/vector count; existing duplicate/reindex tests. | **PASS** | Identical envelopes skip embedding and create no extra active chunks. |
| P2-010 | Document update and deletion | `storage/chroma_store.py:85,219` | Independent content/version replacement, stale IDs absent, three search modes after deletion; existing staging failure tests. | **PASS** | Sequential lifecycle passes; in-flight generation freshness is separately failed under P2-015/018. |
| P2-011 | Keyword retrieval | `retrieval/keyword.py:15; tokenization.py:40` | Independent seven requested technical identifiers, 28-query evaluation and query-embedding trap. | **PASS** | Ranked BM25 works without LLM/query embeddings; exact matches lead the tested technical queries. |
| P2-012 | Semantic retrieval | `retrieval/semantic.py:10; service.py:115` | Independent hash search/evaluation, explicit-ID shadowing; existing controlled synonym adapter test. | **PARTIAL** | Interface operational; candidate filtering loses exact-ID evidence (D-005); learned quality NOT VERIFIED. |
| P2-013 | Hybrid retrieval | `retrieval/hybrid.py:5` | Independent known-list RRF arithmetic, missing branch, stable ranking and measured method comparison; existing dedup/tie test. | **PASS** | Correct RRF and provenance; no universal hybrid-superiority claim. |
| P2-014 | Optional reranking | `retrieval/reranker.py:7; retrieval/hybrid.py:28` | Existing deterministic reranking test and default-off evaluation. | **PASS** | Local token-overlap implementation is optional. No external reranker/fallback policy is implemented or claimed. |
| P2-015 | Retrieval metadata and citations | `service.py:123; generation/citations.py:24,41` | Independent canonical source offsets/resolution; delete/update during generation; TestClient returns citation 404 immediately. | **FAIL** | Snapshot provenance survives, but current source resolvability can fail before the answer returns (D-001). |
| P2-016 | Grounded LLM generation | `generation/answer_generator.py:63; generation/prompts.py:5` | Injected supported/unsupported/conflict/injection outputs; real HTTP adapter exercised by MockTransport tests. | **PARTIAL** | Contract works; unsupported engineering claims and suppressed conflicts still receive cited status (D-006). |
| P2-017 | Insufficient-evidence behavior | `generation/answer_generator.py:69; generation/citations.py:7` | Empty/missing-ID cases skip configured provider; explicit insufficient flag tests; independent negatives abstain 2/4 in each retrieval mode. | **PARTIAL** | Empty evidence is handled; sufficiency for nonempty context depends on provider judgment (D-006). |
| P2-018 | Citation validation | `generation/citations.py:24,30; service.py:130` | Fake S99/uppercase ID rejected; lowercase/custom prose fabrication accepted; deleted/updated snapshots accepted. | **FAIL** | Context membership is insufficient for current-record integrity and supported-ID grammar coverage (D-001/002). |
| P2-019 | RAG evaluation framework | `evaluation/metrics.py:10,22; evaluation/run.py:58` | Existing known-rank/source-filter metric tests; three CLI reruns; independent arithmetic outside production metric functions. | **PASS** | Ranking evaluation works; answer checks intentionally structural, no faithfulness measurement. |
| P2-020 | Golden evaluation dataset | `data/evaluation/retrieval_dataset.json:1; data/evaluation/qa_dataset.json:1` | Read all labels; reran 24-query dataset for all methods; six QA cases execute in existing suite. | **PASS** | Synthetic/selective labels and sparse negatives limit generalization; QA facts are not automatically adjudicated. |
| P2-021 | REST API integration | `api/routes/knowledge.py:18; main.py:39; api/limits.py:11` | 20 existing knowledge API tests plus independent TestClient lifecycle/errors/OpenAPI/body limits/Phase 1 probe. | **PASS** | Expected endpoints and schemas work; citation content defects are recorded under P2-015/018. |
| P2-022 | Synthetic automotive knowledge base | `data/knowledge/synthetic/{ethernet,soa,tsn,overview}.md` | Read all four documents; rerun corpus ingestion yields 34 chunks, 30 requirement-bearing. | **PASS** | Explicitly synthetic constraints, units, source IDs and Phase 1 links are present. |
| P2-023 | Configuration and secrets handling | `core/settings.py:15; models.py:41; providers.py:19; main.py:61` | Existing settings/HTTP error/auth tests; independent nested-secret rejection, safe errors, path rejection, 401/timeout. | **PASS** | No tested credential reflection; content is not redacted. No enterprise authorization assurance. |
| P2-024 | Automated testing | `tests/rag/; tests/test_knowledge_api.py; pyproject.toml:54` | 215 tests pass; 99.10% branch-aware combined coverage; new audit probes reproduce missed defects. | **PARTIAL** | Strong execution coverage does not cover all acceptance boundaries; retain D-001 through D-006 regressions. |
| P2-025 | Documentation | `docs/rag-architecture.md:59,102,150; README.md:194; docs/reviews/phase2-implementation-report.md:26` | Compared documentation against code, rerun metrics and independent probes. | **PARTIAL** | Good scope/quality caveats; universal boundary/reference claims need qualification for D-001/002/003. |
| P2-026 | Phase 1 backward compatibility | `domain/models/; services/; api/routes/architecture.py` | 108 Phase 1 tests pass within full suite; unchanged domain/services versus 2795a54; unusable-storage API probe. | **PASS** | No credentials, vector initialization or network needed for deterministic validation. |
| P2-027 | Phase 3 extensibility | `service.py:33,91,123; generation/answer_generator.py:57` | Independent typed search and generation injection; Phase 1 direct services and lazy API storage verified. | **PARTIAL** | READY WITH MINOR CHANGES structurally; citation acceptance blocker must close before Phase 3 integration. |

## 3. Architecture Assessment

| Responsibility | Actual component and source line | Assessment |
| --- | --- | --- |
| Local loading / normalization | `rag/ingestion/loader.py:12,47` | Basename envelopes, LF normalization, hashes, optional inherited JSON title/version; trusted local PDF adapter. |
| Parsing / extraction | `rag/ingestion/parser.py:18,23,64` | JSON records or heuristic line-start definitions; no extraction warning model. |
| Chunking | `rag/ingestion/chunker.py:13` | Per-record character windows, original text, locations, deterministic hashes. |
| Embeddings | `rag/embeddings/base.py:7`; `rag/embeddings/providers.py:14,35` | Replaceable protocol, local hash baseline and compatible HTTP provider. |
| Vector/catalog persistence | `rag/storage/chroma_store.py:22` | Concrete Chroma adapter with SQLite authoritative source catalog; revision staging. |
| Keyword / semantic / hybrid | `rag/retrieval/{keyword,semantic,hybrid}.py:15,10,5` | BM25, explicit vector queries, RRF respectively. |
| Reranking | `rag/retrieval/reranker.py:7,11` | Optional protocol plus local overlap heuristic. |
| Generation | `rag/generation/answer_generator.py:14,21,57` | Separate provider protocol, HTTP adapter and generation service. |
| Citation validation | `rag/generation/citations.py:16` | Snapshot labels and requirement-ID membership; does not query storage. |
| Evaluation | `rag/evaluation/metrics.py:10,22`; `rag/evaluation/run.py:58` | Retrieval ranking metrics plus limited structural answer checks. |
| HTTP integration | `api/routes/knowledge.py:29,42,97,103`; `main.py:19` | Lazy service, explicit Pydantic request/response schemas, safe error mappings. |

`KnowledgeService.search` executes without an LLM. A probe made `embed_query` raise if invoked and confirmed keyword search still worked. Embedding document/query providers and the generation provider can be injected independently. `AnswerGenerator.answer(question, chunks, options)` permits generation with previously retrieved evidence independently of search. Generation receives copies of evidence data, not the Phase 1 validator.

The storage boundary is **partially abstracted**: it accepts an injected store, but annotations use concrete `ChromaStore` (`service.py:42`, `retrieval/semantic.py:7`), and the service relies on its lock, revision, catalog and vector operations. Existing tests use isolated real Chroma; no store protocol/in-memory adapter exists. This is sufficient for current tests, but replacing the backend would require matching that concrete contract. It does not require a major rewrite for read-only Phase 3 tools.

Domain models use Pydantic and have no AI provider SDK, Chroma, FastAPI or HTTPX dependency. RAG does not import or modify Phase 1 topology/validation results. Diffing Phase 1 domain/services against 2795a54 showed no changes. No circular import was identified: settings depends on RAG DTOs, but those DTOs do not depend on settings. That direction couples configuration to retrieval options, not automotive domain models to providers.

Mutable state is owned by application/service objects: app state holds settings, a lazy knowledge service and a lock; a service holds embeddings, retrievers, generator and store. There is no global mutable evidence list. `main.py:81` constructs a global ASGI app and validates settings at import, but does not initialize a vector database. Chroma is an eager import dependency of the application (`main.py:6`), so runtime distribution still requires RAG packages even for Phase 1 HTTP use. Direct Phase 1 domain/services remain independent.

`RLock` protects ingestion/search on one store object. It does **not** protect evidence across an LLM call or coordinate separate store objects/processes. The documented one-service/one-process limit is material; multiple writer processes are unsupported. No explicit store `close()` or ASGI lifespan cleanup exists for the catalog/client; HTTP provider clients do use context managers (`rag/providers.py:21`). This is an operational limit, not evidence of corrupted data.

Dependency inspection found Phase 2 added Chroma, pydantic-settings and pypdf, and moved HTTPX into runtime dependencies. Chroma contributes a substantial transitive dependency set; no additional LangChain/agent framework or provider SDK abstraction was introduced. No unused framework was identified that blocks acceptance.

## 4. Document Ingestion Assessment

| Required scenario | Observed result | Status |
| --- | --- | --- |
| A. Valid Markdown engineering specification | Supplied three-requirement example ingested as three chunks; exact IDs, heading ancestry, offsets and independent retrieval preserved. | PASS |
| B. Valid JSON requirements | Object/array parsing, `custom:007`, original fields and `/requirements/0/text` or appropriate field pointer retained; inherited title and version `2`. | PASS |
| C. Plain text | Multiline `REQ-TXT-001` with engineering symbols ingested and persisted. | PASS |
| D. Empty/blank document | Pydantic ValidationError; HTTP 422. Heading-only Markdown raises no-indexable-text error; HTTP parser errors are sanitized 422. | PASS |
| E. Unsupported type | `.csv` loader raises supported-format ValueError; HTTP unsupported `source_type` gives 422. | PASS |
| F. Malformed JSON | Invalid JSON rejected before storing source records; HTTP 422. Existing tests cover empty/wrong-shape arrays and malformed records. | PASS |
| G. Identical reingestion | `unchanged`, original ingestion timestamp, same chunk IDs and vector count; canonical source remains exactly three chunks. | PASS |
| H. Changed source | `replaced`; old IDs disappear; old requirement search is empty; only new version filter matches. Forced reindex has no duplicates. | PASS for sequential lifecycle |
| I. Two origins, same filename | Explicit `a`/`b` IDs preserve both. Without explicit IDs, two `collision.md` sources share an ID; second replaces first and first requirement disappears. | PARTIAL, D-004 |
| J. Unicode/engineering symbols | `Überwachung`, `Δt ≤ 1 µs`, `125 °C` preserved in TXT/JSON source content. | PASS |

Document IDs are stable under the documented explicit-ID/basename policy, not unique per origin by default. LF-normalized content is stored with SHA-256, filename, title, source type, timestamp, metadata and version. JSON document versions are inherited; Markdown `Version: 1.0` text is not parsed into version metadata unless supplied by the caller. This matches the detailed documentation. Only the active version is retained; no archival version store or historical citation endpoint is promised.

Deleting one source left unrelated Unicode TXT/JSON documents intact and removed its evidence from keyword, semantic and hybrid searches. Update invalidated all old content/version chunk IDs. Metadata/title-only updates can preserve chunk IDs because chunk identity excludes those fields; revision fingerprints and returned titles do change. Blanket documentation that every replacement invalidates every old URL should be narrowed to content/version/identity changes (`README.md:194`, `docs/rag-architecture.md:102` versus `:69`).

Optional PDF: the executed existing `test_local_loader_and_pdf` constructs a real two-page text PDF and verifies page locations `[1, 2]`, then checks a blank page's OCR rejection and invalid-PDF rejection (`tests/rag/test_ingestion.py:129`). No OCR was used. Supplier layouts, cross-page requirement continuity and complex table extraction remain **NOT VERIFIED**; no claim of layout-aware parsing is warranted.

## 5. Requirement Extraction and Chunking Assessment

The exact supplied Ethernet example passes: `REQ-ETH-001`, `REQ-ETH-002`, `REQ-SEC-003` are separate, verbatim IDs. Sections include `Ethernet Architecture Requirements / Central Gateway` and `/ Network Segmentation`. Every canonical chunk text equals its normalized-content slice. Exact searches return each corresponding requirement independently.

| Additional case | Executed observation |
| --- | --- |
| Multiple requirements on one line | `REQ-ETH-010: Gateway shall connect. REQ-ETH-011: Camera shall connect.` becomes **one** record labeled 010. Query 011 returns **zero** hits; its text is present but its identity is unavailable (D-003). |
| Different naming conventions | Default parser preserves `SYS-REQ-014`; underscore `REQ_ETH_012` and lowercase `req-eth-013` stay as unassigned text. Existing custom `ENG_42` pattern test passes. |
| Requirement across lines | Canonical line-separated IDs/statements retain all multiline text until the next recognized boundary. |
| Heading without IDs | Contextual paragraph retained with `requirement_id=null`; headings alone are rejected as no indexable text. |
| Markdown table | Table text survives with `requirement_id=null`; structured requirement-table extraction is not implemented. Exact-ID service prefilter can make a table-only ID unsearchable. |
| Repeated ID in distinct documents/versions | Both independent conflict documents are retrievable; version/source locations distinguish citations. Updating one document keeps only its active revision. |
| Very long requirement | Independent 150-character/25-overlap run produced **30 distinct fragments**, all retaining `REQ-LONG-001`, complete original text and correct source slices. Existing long-JSON fragments also have unique IDs/pointers. |
| No ID | Null ID retained; no fabricated identifier was observed in ingestion. |

Stable chunk IDs hash source identity/content/version, section, requirement ID, source location and fragment text (`chunker.py:33`). Identical source/configuration produces identical IDs. Changing document content changes all its chunk IDs, including unchanged statements; this is a deliberate revision policy.

Overlap is confined to a source record, so it does not cross correctly recognized requirement boundaries. Fragments of the same long requirement can occupy multiple search slots and produce multiple valid, overlapping citations; deduplication is by chunk ID, not requirement ID. Citation labels deduplicate repeated labels only. Consumers must not count overlap as independent corroboration. The source text is preserved on failed extraction, but there is **no per-document extraction diagnostic** reporting unrecognized/merged IDs. This is the substantive gap in the requested fallback contract, beyond merely supporting a configurable regex.

## 6. Embedding and Vector Store Assessment

`EmbeddingProvider` has `embed_documents`, `embed_query`, `identity` and `dimension`. Hash outputs are repeatable, normalized for meaningful tokens, differ for distinct input and need no downloads. Empty/stopword input returns a zero vector at provider level; store validation rejects zero vectors. The public search service short-circuits empty meaningful token queries. Direct malformed Python calls are outside the typed provider contract.

The compatible HTTP adapter supports batching, restores input order by validated indices, validates counts/dimensions/finite nonzero values and records endpoint fingerprint, model and dimension in identity. Existing MockTransport tests exercise auth and malformed responses. Independent invalid-dimension, zero and NaN vectors raised ProviderError. An existing index rejected a changed model identity and a changed dimension with ConfigurationError; no silent model reuse was observed. An upstream endpoint silently changing weights under an unchanged name cannot be detected by this scheme.

Missing API keys are not universally configuration errors: compatible local servers may legitimately require no key. A controlled 401 yielded a safe ProviderError, not a fabricated result. Missing model configuration is checked. Actual remote credentials, learned embeddings and real provider timeouts remain **NOT VERIFIED**; simulated timeout handling passed.

Chroma uses `PersistentClient`, cosine HNSW, explicitly supplied embeddings, no implicit embedding function and telemetry disabled (`storage/chroma_store.py:35`). Collection metadata records model identity/dimension/schema. SQLite stores authoritative full documents/chunks. Chroma scalar metadata includes document ID, requirement ID, version, revision, chunk ID and filename. Section/source-location fields reside in catalog payloads, not Chroma scalars; retrieval rehydrates the complete catalog chunk, preserving them.

Creation, add, search, metadata filters, empty collection, replacement, identical reingestion, forced reindex, deletion and reopen passed. Reopen was also verified in a **separate Python interpreter** returning `REQ-ETH-001`. Existing tests verify failed staging leaves active records intact and inactive orphan vectors are excluded. Sequential vector/catalog operations do not expose stale active revisions. Keyword retrieval scans the active catalog, so it stays synchronized with ordinary updates/deletions without a second persistent lexical index.

Writes stage vectors before committing the catalog and prune old vectors afterward. Inactive disk remnants after crashes and non-atomic failures across the two backends remain documented operational limits; crash recovery, disk exhaustion and multiprocess contention were not fault-injected. Those are **NOT VERIFIED**, rather than inferred guarantees. D-001 is distinct: valid retrieval snapshots can become outdated while generation runs.

## 7. Keyword, Semantic, and Hybrid Retrieval Assessment

Independent top-one checks succeeded for all seven requested identifier forms: `REQ-ETH-001`, `REQ-SOA-015`, `SOME/IP-SD`, `IEEE 802.1Qbv`, `1000BASE-T1`, `VLAN 100`, `0x1234`. Matching and distracting requirements were present. Case-folded exact queries preserve the source's original ID. Technical whole tokens and components are indexed; BM25 uses term frequency, document frequency and length normalization, plus a 100-point exact requirement-ID boost (`keyword.py:19,26,32`). Results sort by descending score and stable chunk ID.

Semantic search is functionally real vector retrieval and returns structured metadata. Existing controlled HTTP vectors retrieve `gigabit backbone` without shared lexical tokens, proving the adapter/search interface can use semantics supplied by a model. It does not demonstrate learned semantics from the default hash provider. Fixed-condition repeated rankings were stable; final Top-K=1 never exceeded one in the independent dataset. No confidence calibration is claimed: response `score_note` explicitly distinguishes ranking scores from answer confidence.

**D-005:** explicit-ID eligibility is applied after Chroma candidate truncation. One actual `REQ-TARGET-001` and 13 different requirement records repeatedly mentioning that ID caused default semantic search for the exact ID to return **[]**, while keyword/hybrid returned the target. Adding an explicit `requirement_id` metadata filter made semantic search return the target. The source exists; post-truncation filtering is the cause, not insufficient evidence.

Independent RRF input: keyword ranks `[A, B]`, semantic ranks `[B, C]`, constant 10. Observed scores: B = `1/12 + 1/11 = 0.17424242424242425`; A = `1/11 = 0.09090909090909091`; C = `1/12 = 0.08333333333333333`. B correctly ranks first and has both method contributions. An empty keyword branch with one semantic hit works. Existing tests additionally verify stable chunk deduplication, duplicate entries, tie-breaking and metadata retention (`tests/rag/test_retrieval.py:63`).

The optional local token-overlap reranker preserves source chunks/citations, exposes its signal separately and can be disabled. Its executed deterministic test passes. No external reranker is present, so an external failure/fallback policy is **NOT APPLICABLE to the implemented adapter**, not an untested promised feature. Failure behavior for future injected arbitrary rerankers is not specified; the current call propagates their exceptions.

Measured comparison appears in section 9. Hybrid improved MRR over keyword slightly on this sample and recovered the hash paraphrase miss; it did not improve Recall@5 over keyword. The saved repository dataset produces identical aggregate scores across all three modes. Neither result supports universal hybrid superiority.

## 8. Citation and Grounded Generation Assessment

Citation **existence**, correct source **identity/location**, and claim-level **support** were assessed separately. Structured citations are built from retrieved chunk objects; the model cannot supply document IDs/quotes/locations in the output schema. Unknown fields such as model-supplied `document_id` raise InvalidModelResponse. Invented IDs inside ordinary prose are a different validation problem.

| Scenario | Actual controlled behavior | Assessment |
| --- | --- | --- |
| Supported excerpt and `[S1]` | `cited`; quote, exact source ID/version/location agree with indexed record; URL resolves. | PASS |
| Empty evidence / missing requirement | Fixed insufficient response, zero citations and no provider call with a configured provider. | PASS |
| Explicit provider insufficient flag | Generated claims discarded for fixed insufficient response (existing test). | PASS |
| Fake context label `[S99]` | `invalid_citations`, generated claims suppressed. | PASS |
| Invented uppercase `REQ-ETH-999 [S1]` | Rejected against cited requirement IDs. | PASS |
| Invented lowercase `req-eth-999 [S1]` | Accepted as `cited`; response's structured list instead contains real `REQ-ETH-001`. | FAIL, D-002 |
| JSON source `custom:007`, model prose `custom:999 [S1]` | Accepted as `cited` under default pattern. | FAIL, D-002 |
| Invented prose document `invented-doc-999` plus valid label | Accepted prose; structured citation still correctly identifies the real document. | PARTIAL support checking, D-006 |
| Source deleted or updated inside provider call | Old text/citation returned as `cited`; catalog cannot resolve old chunk. API `/ask` = 200 followed immediately by citation GET = 404. | FAIL, D-001 |
| Two conflict sources, two cited labels | Controlled response preserves 5 ms versus 10 ms and both real sources. | PASS for transport/citation contract |
| Same conflict context, provider silently selects one | Unqualified one-source answer accepted as `cited`. | PARTIAL conflict handling, D-006 |
| Provider claims TSN compliance with interface-only evidence | “The architecture meets all TSN latency requirements and all architecture checks passed. [S1]” accepted. Explanation says semantic support is not proven. | PARTIAL engineering-grounding capability, D-006 |
| Injected document says ignore instructions / claim checks passed | Context is serialized as untrusted evidence; a controlled provider returning “All architecture checks passed. [S1]” is still accepted. | Prompt separation PASS; behavioral resistance NOT VERIFIED; no deterministic support barrier |
| Missing provider/model | Controlled configuration exception; HTTP 503, no substitute answer. | PASS |
| Timeout / 401 / malformed output | Safe ProviderError/InvalidModelResponse; malformed output HTTP 502. Existing tests also cover 429/500 and invalid JSON. | PASS for controlled errors |

Provider request construction includes the question, retrieved excerpts, exact IDs/versions and generation settings. The system prompt explicitly requires evidence-only answers, units/IDs unchanged, no engineering validation inference, insufficient-evidence handling and treating the question/documents as untrusted (`generation/prompts.py:5`). Actual HTTP payload contract is exercised with MockTransport (`tests/rag/test_generation.py:38`). Controlled output tests demonstrate what the application accepts; they do **not** prove a real LLM follows or violates those instructions.

For the five independently controlled invalid-reference/schema cases (S99, uppercase invented requirement, lowercase invented requirement, custom invented requirement, extra structured document ID), **2/5** were accepted. This is a narrow case-level acceptance fraction, not a production hallucination rate; both accepted cases were prose requirement references, not fabricated structured source records. For the two separate lifecycle cases, **2/2** returned nonresolving citations before return. Ordinary sequential resolution passed. The requested zero invalid-reference/current-source target is therefore not met.

Citation validation is context scoped: labels map only to chunks supplied for that answer. It does not reread active catalog state after generation, detect arbitrary prose IDs outside the configured regex, enforce claim entailment, preserve conflicts or verify units. Its own explanation accurately warns about semantic support. Existing documentation recognizes the semantic limit; that caveat does not establish engineering-grounding acceptance or repair D-001/002.

## 9. Independent RAG Evaluation

The following corpus and labels were written to a temporary dataset **before any independent retrieval execution**. They were not copied from, or adjusted to match, observed search output. The repository golden datasets were unchanged. Evaluation used independent set/rank arithmetic, not `rag.evaluation.metrics` or `evaluate`.

Configuration: provider **`hash:hash-token-v1:384`**, Chroma 1.5.9 cosine; 1,000-character chunks, overlap 120; semantic/keyword candidate K=12, final K=5; RRF constant 60; minimum similarity 0.15; reranking off, no metadata filters. There were 18 short requirements/chunks across four documents, each in version `1`; each source was `# {document_id}

` followed by `ID: statement` records separated by blank lines. Source envelopes used explicit document IDs and filename `audit.md`, which also exercises distinct documents with equal filenames. No LLM was called during retrieval evaluation.

Relevance unit: **unique requirement ID**; all corpus IDs are unique, one chunk per requirement. Deduplicate IDs in returned order. Macro Recall@K = `|ranked[:K] ∩ expected| / |expected|`; Precision@3 uses fixed denominator 3; MRR is reciprocal first relevant rank within returned five, zero if absent. Ranking averages exclude all four negative queries. Exact-ID Hit@1 covers the six exact-ID questions, including one lowercase query. Negative retrieval abstention is reported separately; related documents can still be useful for explaining that a fact is absent, so retrieval abstention alone is not generation sufficiency or faithfulness.

| Method | Recall@1 | Recall@3 | Recall@5 | Precision@3 | MRR within 5 | Exact-ID Hit@1 | Negative retrieval abstention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| keyword | 0.895833 | 1.000000 | 1.000000 | 0.375000 | 0.972222 | 1.000000 (6/6) | 0.500000 (2/4) |
| semantic | 0.916667 | 0.958333 | 0.958333 | 0.347222 | 0.958333 | 1.000000 (6/6) | 0.500000 (2/4) |
| hybrid | 0.895833 | 1.000000 | 1.000000 | 0.375000 | 0.979167 | 1.000000 (6/6) | 0.500000 (2/4) |

All methods meet the provisional 95% exact-ID, 90% Recall@5 and 0.85 MRR targets **on this small offline dataset**. Learned semantic/production targets remain NOT VERIFIED. The separate exact-ID shadowing probe in section 7 shows why 6/6 should not be generalized. Negative cases i27/i28 return nonempty results in all modes. The empty/missing-ID generation contract passes, but nonempty-context sufficiency is not enforced and live-model abstention is NOT VERIFIED.

Failed Recall@5 queries: **semantic i24 only**, returning no hits for the gigabit/central-compute paraphrase; keyword and hybrid return both expected requirements. Top-one ranking miss: i15 (service discovery) is rank 3 for keyword, rank 2 for hybrid, rank 1 for semantic; it explains the MRR difference. Multiple-relevance questions naturally limit Recall@1. All 28 rankings per method repeated identically under the fixed conditions. No tuning or golden-answer changes were performed.

Independent corpus (complete; all synthetic):

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

Fixed independent queries and judgments (complete). `—` means no supporting evidence for the requested fact. In the result column K/S/H are the **first relevant rank** for keyword/semantic/hybrid, not just the rank of the first arbitrary hit. For negative queries the column records abstention or a false positive. Full expected sets make Recall metrics independently recomputable.

| Query | Category | Question | Expected requirement IDs | K / S / H first relevant rank or negative outcome |
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

To preserve actual rank evidence after temporary-file cleanup, all returned requirement sequences are recorded below. IDs use their full original spelling; negative rows are included. Arrays are ordered Top-5 results.

```json
{
  "keyword": {
    "i01": [
      "REQ-ETH-001"
    ],
    "i02": [
      "REQ-SOA-015"
    ],
    "i03": [
      "REQ-TSN-008"
    ],
    "i04": [
      "REQ-SEC-003"
    ],
    "i05": [
      "REQ-SOA-016"
    ],
    "i06": [
      "REQ-TSN-011"
    ],
    "i07": [
      "REQ-ETH-001",
      "REQ-ETH-004",
      "REQ-ETH-003"
    ],
    "i08": [
      "REQ-SOA-015",
      "REQ-SOA-016",
      "REQ-SOA-017"
    ],
    "i09": [
      "REQ-TSN-008",
      "REQ-TSN-001"
    ],
    "i10": [
      "REQ-SEC-004",
      "REQ-ETH-005",
      "REQ-SEC-005",
      "REQ-SOA-015"
    ],
    "i11": [
      "REQ-SOA-016"
    ],
    "i12": [
      "REQ-TSN-001",
      "REQ-TSN-008"
    ],
    "i13": [
      "REQ-ETH-002",
      "REQ-ETH-001",
      "REQ-ETH-003",
      "REQ-SEC-003",
      "REQ-TSN-001"
    ],
    "i14": [
      "REQ-SEC-003",
      "REQ-ETH-005",
      "REQ-TSN-008",
      "REQ-SEC-005",
      "REQ-SEC-004"
    ],
    "i15": [
      "REQ-SOA-016",
      "REQ-SOA-017",
      "REQ-SOA-015",
      "REQ-SOA-018"
    ],
    "i16": [
      "REQ-TSN-001",
      "REQ-TSN-008",
      "REQ-TSN-002",
      "REQ-TSN-011",
      "REQ-ETH-004"
    ],
    "i17": [
      "REQ-ETH-003",
      "REQ-ETH-004",
      "REQ-ETH-001",
      "REQ-SOA-018",
      "REQ-TSN-009"
    ],
    "i18": [
      "REQ-ETH-004",
      "REQ-ETH-003",
      "REQ-TSN-009",
      "REQ-TSN-001",
      "REQ-ETH-001"
    ],
    "i19": [
      "REQ-TSN-010",
      "REQ-SOA-018",
      "REQ-TSN-009",
      "REQ-TSN-002",
      "REQ-SOA-016"
    ],
    "i20": [
      "REQ-SOA-018",
      "REQ-SOA-015",
      "REQ-SOA-016",
      "REQ-SOA-017",
      "REQ-TSN-009"
    ],
    "i21": [
      "REQ-TSN-011",
      "REQ-TSN-002",
      "REQ-TSN-001"
    ],
    "i22": [
      "REQ-SEC-004",
      "REQ-SEC-005",
      "REQ-SEC-003",
      "REQ-ETH-005",
      "REQ-TSN-008"
    ],
    "i23": [
      "REQ-TSN-009",
      "REQ-SOA-018",
      "REQ-TSN-002",
      "REQ-SOA-016",
      "REQ-TSN-011"
    ],
    "i24": [
      "REQ-ETH-001",
      "REQ-ETH-002"
    ],
    "i25": [],
    "i26": [],
    "i27": [
      "REQ-TSN-010",
      "REQ-SOA-018",
      "REQ-TSN-009",
      "REQ-TSN-002",
      "REQ-SOA-016"
    ],
    "i28": [
      "REQ-SEC-005",
      "REQ-SEC-004",
      "REQ-SEC-003",
      "REQ-SOA-015",
      "REQ-TSN-008"
    ]
  },
  "semantic": {
    "i01": [
      "REQ-ETH-001"
    ],
    "i02": [
      "REQ-SOA-015"
    ],
    "i03": [
      "REQ-TSN-008"
    ],
    "i04": [
      "REQ-SEC-003"
    ],
    "i05": [
      "REQ-SOA-016"
    ],
    "i06": [
      "REQ-TSN-011"
    ],
    "i07": [
      "REQ-ETH-001"
    ],
    "i08": [
      "REQ-SOA-015",
      "REQ-SOA-016",
      "REQ-SOA-017"
    ],
    "i09": [
      "REQ-TSN-008",
      "REQ-TSN-001",
      "REQ-ETH-001"
    ],
    "i10": [
      "REQ-SEC-004"
    ],
    "i11": [
      "REQ-SOA-016"
    ],
    "i12": [
      "REQ-TSN-001",
      "REQ-TSN-008",
      "REQ-ETH-001"
    ],
    "i13": [
      "REQ-ETH-002",
      "REQ-ETH-001",
      "REQ-ETH-003"
    ],
    "i14": [
      "REQ-SEC-003",
      "REQ-TSN-008"
    ],
    "i15": [
      "REQ-SOA-015",
      "REQ-SOA-016",
      "REQ-SOA-017"
    ],
    "i16": [
      "REQ-TSN-001",
      "REQ-ETH-004",
      "REQ-ETH-001",
      "REQ-ETH-002",
      "REQ-ETH-003"
    ],
    "i17": [
      "REQ-ETH-003"
    ],
    "i18": [
      "REQ-ETH-004",
      "REQ-ETH-003",
      "REQ-SOA-016"
    ],
    "i19": [
      "REQ-TSN-010"
    ],
    "i20": [
      "REQ-SOA-018",
      "REQ-SOA-015",
      "REQ-SOA-016"
    ],
    "i21": [
      "REQ-TSN-011"
    ],
    "i22": [
      "REQ-SEC-005",
      "REQ-SEC-004",
      "REQ-SEC-003"
    ],
    "i23": [
      "REQ-TSN-009"
    ],
    "i24": [],
    "i25": [],
    "i26": [],
    "i27": [
      "REQ-TSN-010"
    ],
    "i28": [
      "REQ-SEC-003",
      "REQ-SEC-005",
      "REQ-SEC-004",
      "REQ-TSN-002"
    ]
  },
  "hybrid": {
    "i01": [
      "REQ-ETH-001"
    ],
    "i02": [
      "REQ-SOA-015"
    ],
    "i03": [
      "REQ-TSN-008"
    ],
    "i04": [
      "REQ-SEC-003"
    ],
    "i05": [
      "REQ-SOA-016"
    ],
    "i06": [
      "REQ-TSN-011"
    ],
    "i07": [
      "REQ-ETH-001",
      "REQ-ETH-004",
      "REQ-ETH-003"
    ],
    "i08": [
      "REQ-SOA-015",
      "REQ-SOA-016",
      "REQ-SOA-017"
    ],
    "i09": [
      "REQ-TSN-008",
      "REQ-TSN-001",
      "REQ-ETH-001"
    ],
    "i10": [
      "REQ-SEC-004",
      "REQ-ETH-005",
      "REQ-SEC-005",
      "REQ-SOA-015"
    ],
    "i11": [
      "REQ-SOA-016"
    ],
    "i12": [
      "REQ-TSN-001",
      "REQ-TSN-008",
      "REQ-ETH-001"
    ],
    "i13": [
      "REQ-ETH-002",
      "REQ-ETH-001",
      "REQ-ETH-003",
      "REQ-SEC-003",
      "REQ-TSN-001"
    ],
    "i14": [
      "REQ-SEC-003",
      "REQ-TSN-008",
      "REQ-ETH-005",
      "REQ-SEC-005",
      "REQ-SEC-004"
    ],
    "i15": [
      "REQ-SOA-016",
      "REQ-SOA-015",
      "REQ-SOA-017",
      "REQ-SOA-018"
    ],
    "i16": [
      "REQ-TSN-001",
      "REQ-ETH-004",
      "REQ-ETH-001",
      "REQ-ETH-002",
      "REQ-ETH-003"
    ],
    "i17": [
      "REQ-ETH-003",
      "REQ-ETH-004",
      "REQ-ETH-001",
      "REQ-SOA-018",
      "REQ-TSN-009"
    ],
    "i18": [
      "REQ-ETH-004",
      "REQ-ETH-003",
      "REQ-SOA-016",
      "REQ-TSN-009",
      "REQ-TSN-001"
    ],
    "i19": [
      "REQ-TSN-010",
      "REQ-SOA-018",
      "REQ-TSN-009",
      "REQ-TSN-002",
      "REQ-SOA-016"
    ],
    "i20": [
      "REQ-SOA-018",
      "REQ-SOA-015",
      "REQ-SOA-016",
      "REQ-SOA-017",
      "REQ-TSN-009"
    ],
    "i21": [
      "REQ-TSN-011",
      "REQ-TSN-002",
      "REQ-TSN-001"
    ],
    "i22": [
      "REQ-SEC-005",
      "REQ-SEC-004",
      "REQ-SEC-003",
      "REQ-ETH-005",
      "REQ-TSN-008"
    ],
    "i23": [
      "REQ-TSN-009",
      "REQ-SOA-018",
      "REQ-TSN-002",
      "REQ-SOA-016",
      "REQ-TSN-011"
    ],
    "i24": [
      "REQ-ETH-001",
      "REQ-ETH-002"
    ],
    "i25": [],
    "i26": [],
    "i27": [
      "REQ-TSN-010",
      "REQ-SOA-018",
      "REQ-TSN-009",
      "REQ-TSN-002",
      "REQ-SOA-016"
    ],
    "i28": [
      "REQ-SEC-005",
      "REQ-SEC-003",
      "REQ-SEC-004",
      "REQ-TSN-002",
      "REQ-SOA-015"
    ]
  }
}
```

Independent calculation sketch, operating on those recorded rankings and the fixed expected sets above:

```python
def score(ranked, expected, k):
    ranked = list(dict.fromkeys(ranked))[:k]
    hits = len(set(ranked) & set(expected))
    rr = next((1 / i for i, item in enumerate(ranked, 1) if item in expected), 0)
    return hits / len(expected), hits / k, rr


# Macro-average over 24 answerable queries; use k=1,3,5 for recall,
# k=3 for precision and k=5 for reciprocal rank. Score negatives separately.
```

The original repository evaluator was also rerun, separately, against its unchanged 24 queries, four sources and 34 chunks. All three modes reproduced **Recall@5 0.977273, Precision@5 0.281818, MRR 1.000000, negative abstention 2/2**. Each still misses `REQ-ISO-001` on q09 (retrieving `REQ-ETH-008`), with per-query Recall@5 0.5. The original saved metrics agree with execution. Identical aggregates do not establish hybrid improvement. QA fixtures contain six useful review cases, but their `expected_facts`/`unsupported_claims_to_reject` are not automatically semantically scored by the existing tests; those tests quote a controlled excerpt and check IDs/citations.

Limitations: small English synthetic corpora, no provider/model selection experiment, no learned embeddings, no supplier PDFs, sparse exact-ID sample, selective relevance judgments and no blinded human answer scoring. No confidence interval or production semantic/faithfulness claim is justified.

## 10. REST API Assessment

All five expected endpoint paths are implemented as requested; additional GET document/chunk endpoints expose evidence independently of generated text. Tests used the existing async ASGI tests and an independent synchronous FastAPI/Starlette **TestClient**. OpenAPI returned **3.1.0**, with all Phase 1 and knowledge paths and explicit Pydantic request/response models. No path discrepancy was found.

| Independent request | Actual HTTP behavior |
| --- | --- |
| Valid ingestion / duplicate / listing | 200 `created`; 200 `unchanged`; 200 list with one source and three chunks. |
| Exact keyword/semantic/hybrid search | All 200; real `REQ-ETH-001` first with matching source location. |
| Controlled ask / unknown-ID ask | 200 `cited`; 200 `insufficient` with no citation. |
| Basename path, unknown `path` field, blank content, malformed source JSON, unsupported source type, nested credential metadata | Each 422. No file content returned. |
| 1,000,001-character content within body limit | 422 schema limit. |
| 1,100,001-byte body | 413 before parsing; existing streaming test also checks chunked oversize. |
| Malformed JSON request | 422. |
| final_top_k = 0, -1, 101 | Each 422. Other candidate limits are schema bounded 1–100. |
| Malformed provider response / unconfigured generation | 502 / 503 with sanitized generic detail. |
| Delete / retrieval afterward / repeat delete | 204 / 200 empty hits / 404. |
| Citation deleted during generation | Ask 200 `cited`, immediately followed by GET chunk 404 (D-001). |
| Phase 1 example validation | 200 `NOT_EVALUATED`; lazy knowledge storage stays uninitialized in the independent unusable-path test. |

Provider 401/429/500, storage exceptions and validation-error sanitization are exercised by existing tests. No secret was observed in tested responses. The HTTP API never reads a user-supplied filesystem path; trusted local loading is intentionally separate. This verifies API integration and tested bounds, not complete penetration resistance or tenancy.

## 11. Phase 1 Regression Results

The complete existing suite ran and passed. Phase 1 modules account for **108 tests**: API 25, models 41, topology 8, traffic completeness 16, validator 18. They cover model/reference invariants, NetworkX physical topology, connectivity, declared-demand bandwidth rules, evidence schemas, health/OpenAPI and original REST behavior. Phase 2 domain/services changes versus 2795a54 were empty. The original OpenAPI regression changed from path-set equality to a superset assertion to allow new endpoints (`tests/test_api.py:17`); old paths remain required.

The independent sample API validation remains `NOT_EVALUATED`, without promoting prose or RAG results into engineering PASS. A new app with its vector path nested beneath a deliberately ordinary file still validates the Phase 1 sample with HTTP 200 and `knowledge_service is None`. Thus deterministic validation needs no vector initialization, embedding call, LLM credentials or external network. Invalid global RAG environment syntax can still fail `Settings()` when importing the shared HTTP app; direct domain/services do not read those settings. This coupling is a configuration boundary, not an observed regression under valid defaults.

## 12. Engineering Quality and Security

The existing Python 3.12 virtual environment was usable. `uv` was available at `/tmp/ee-arch-uv/bin/uv`, not on PATH. The lockfile contains 110 package entries; every installed package overlapping the lock matched its locked version. The only absent entries were platform-inapplicable `colorama` (Windows) and `httpx2-jsfetch` (Emscripten). Relevant versions: Python 3.12.16, Chroma 1.5.9, FastAPI 0.162.3, Pydantic 2.14.3, HTTPX 0.28.1, pypdf 6.21.4, pytest 9.2.0, pytest-cov 7.1.0, Ruff 0.17.4, mypy 1.20.2.

`uv sync --locked --all-groups` was deliberately **not run**, because the existing environment already supported all checks and synchronization could mutate it/download packages. `uv.lock` and dependency files were unchanged. Tests/probes used isolated paths beneath `/tmp/phase2-audit-4cph9f`; no default `data/vector_db` was initialized by audit code. Audit artifacts were transcribed into this report and removed afterward, including temporary indexes, script files, coverage and evaluation JSON. No results depend on retaining those temporary paths.

| Executed check | Result |
| --- | --- |
| `uv run --no-sync ruff check . --no-cache` | PASS, all checks passed. |
| `uv run --no-sync ruff format --check . --no-cache` | PASS, **80 files already formatted**. |
| `uv run --no-sync mypy src --cache-dir <temporary>/mypy` | PASS, **48 source files**, no issues. |
| `uv run --no-sync pytest -p no:cacheprovider --basetemp=<temporary>/pytest-outside --cov-report=term-missing --cov-report=xml:<temporary>/coverage.xml` | PASS, **215 tests in 8.65 seconds**, **99.10%** configured combined statement/branch coverage. `COVERAGE_FILE` also pointed outside the repo. |
| Three `python -m ee_arch_copilot.rag.evaluation.run --method ... --output <temporary>/...json` runs | PASS, reproduced original ranking metrics for keyword, semantic, hybrid. |
| Independent offline core, extras and TestClient scripts | Completed; numerical results and reproduced defects recorded in sections 4–10/13. |

All commands used the existing virtual environment, disabled Python bytecode writes, and removed inherited PYTHONPATH. Ruff caching was disabled; mypy/uv/pytest/coverage paths were redirected outside the repo. The first full pytest run stalled in sandboxed API tests and was interrupted; it is **not** counted as a successful full run. The authorized outside-sandbox rerun above completed. The independent TestClient run likewise timed out after 20 seconds inside the sandbox, then completed outside it with real HTTP transport blocked. Neither stall is attributed to an implementation failure. Packaging, Docker runtime, Python 3.13+, live providers, remote CI, load tests, crash recovery and production security scanning were **NOT VERIFIED** in this audit.

Type safety and ordinary error handling are strong: strict mypy passes; settings validate size/ranking/chunk bounds; safe errors avoid echoing raw requests or provider bodies. HTTPX clients close per request. The catalog/client lack an explicit lifecycle close hook. There is no application logging of document excerpts in the inspected code; dependency logs were not exhaustively audited. Sanitizing metadata key names is not confidential-content redaction and cannot guarantee no secret exists in uploaded prose or innocently named metadata.

User metadata cannot overwrite generated identity: independent metadata containing `document_id`, `chunk_id` and `requirement_id` did not override actual chunk fields. JSON item metadata is preserved under `structured_fields`. Document filters and per-source deletion provide meaningful local source boundaries; no authentication, authorization or tenant boundary exists, as explicitly documented. Anyone with API access can list/read/delete sources. Enterprise hosting would need access-scoped retrieval/filtering, authenticated source IDs and storage/configuration controls. This is not treated as missing Phase 2 multi-tenancy.

Uploads are bounded by character and streamed byte limits; regex configuration and provider URLs are trusted settings. Retrieved text/questions are untrusted input to generation. The system has no tool execution from retrieved instructions, but prompt-only protection does not enforce truthful output (D-006). Ordinary replaced/deleted sources leave search; in-flight generation can still publish their snapshots (D-001). No confidential corpus or real keys were used or printed.

## 13. Defect List

Ordered by severity. Recommendations are proposals only; no correction was applied.

### D-001 — HIGH — Generation can publish already deleted/outdated citations

- **Requirements:** P2-015, P2-018; lifecycle implication for P2-010 and Phase 3 evidence consumers.
- **Affected source:** `src/ee_arch_copilot/rag/service.py:123` (search at 130, generator call at 131); `src/ee_arch_copilot/rag/generation/citations.py:24` and `:41`; resolution at `src/ee_arch_copilot/api/routes/knowledge.py:79`.
- **Reproduction:** Ingest `REQ-RACE-001: Gateway shall connect.`. Inject a provider whose `generate()` deletes that document, then returns the previously supplied chunk text with `[S1]`. Call `ask`. A second probe replaces the source with version 2 “Gateway shall disconnect.” instead of deleting it. This deterministically simulates another request completing a mutation while a model call is in flight; it does not require multiple services/processes.
- **Expected:** Reject/retrieve again, report expired evidence, or return an explicitly versioned archival citation that still resolves. An already inactive chunk must not be represented as current validated evidence.
- **Actual:** Both probes return `evidence_status="cited"`, old text/version and a chunk missing from the active catalog. Independent TestClient confirms ask HTTP **200**, immediately followed by citation GET HTTP **404**.
- **Root-cause hypothesis:** `ask` releases the search lock before generation. `validate_answer` trusts passed chunk snapshots and never rechecks active source identity/revision after the provider returns. One writer process still permits concurrent requests/reads and writes.
- **Recommended correction:** Carry immutable revision identities through retrieval and revalidate under the store lock before returning; reject/retry expired snapshots or implement explicit resolvable archival citations with a current/expired distinction. Add delete/update-during-generation API regressions. Holding the lock for an entire network call would serialize ingestion and needs a deliberate latency/concurrency policy.

Minimal offline reproduction shape (use a temporary directory and default hash settings):

```python
class DeleteDuringGeneration:
    model = "controlled-audit"

    def generate(self, question, chunks, options):
        service.store.delete("race")
        return json.dumps({"answer": chunks[0].text + " [S1]", "citation_ids": ["S1"]})


service.ingest(
    DocumentInput(
        document_id="race",
        filename="race.txt",
        source_type="text",
        content="REQ-RACE-001: Gateway shall connect.",
    )
)
service.generator.provider = DeleteDuringGeneration()
answer = service.ask(AskRequest(question="REQ-RACE-001"))
assert answer.evidence_status == "cited"  # observed
assert service.store.get_chunk(answer.citations[0].chunk_id) is None
```

### D-002 — MEDIUM — Mentioned-ID validation can miss fabricated requirement references

- **Requirements:** P2-018, P2-016, P2-023.
- **Affected source:** `src/ee_arch_copilot/rag/generation/citations.py:30`; default pattern `src/ee_arch_copilot/core/settings.py:12`; broad JSON ID acceptance `src/ee_arch_copilot/rag/ingestion/parser.py:47`.
- **Reproduction:** Retrieve real `REQ-ETH-001`; controlled output is `{"answer":"req-eth-999 [S1]","citation_ids":["S1"]}` with no structured requirement list. Separately ingest JSON ID `custom:007` and validate prose `custom:999 ... [S1]` against that context under the default pattern.
- **Expected:** Reject or flag absent requirement references, or explicitly signal that those grammars cannot be checked. Preserve original known identifiers exactly.
- **Actual:** Both outputs are `cited`; structured referenced IDs are populated from the real cited source, hiding the discrepancy with prose. Uppercase `REQ-ETH-999` is correctly rejected.
- **Root-cause hypothesis:** Mention extraction is case-sensitive and limited to the configured regex; JSON permits a broader ID grammar. There is no coverage check for identifier-like references outside that regex.
- **Recommended correction:** Align source-ID and mention grammars, detect case variants without silently rewriting source spelling, and explicitly reject/flag unsupported ID-like output. Test JSON custom IDs and undeclared prose IDs. Do not represent regex membership checking as unrestricted fabricated-reference detection.

### D-003 — MEDIUM — Same-paragraph requirements silently lose independent identity

- **Requirements:** P2-003, P2-004, P2-025.
- **Affected source:** `src/ee_arch_copilot/rag/ingestion/parser.py:14,103,109`; exact-ID filtering `src/ee_arch_copilot/rag/service.py:99`.
- **Reproduction:** Ingest `REQ-ETH-010: Gateway shall connect. REQ-ETH-011: Camera shall connect.` as Markdown/text. Inspect records/chunks and query `REQ-ETH-011`.
- **Expected:** Preserve two definitions independently, or preserve text and return an explicit extraction limitation requiring review. Do not invent IDs or indiscriminately treat sentence references as definitions.
- **Actual:** One record labeled `REQ-ETH-010` contains both statements. Query 011 returns **[]** because the service restricts chunks by extracted metadata, even though 011 remains in the text. No warning is returned. Tables/default-unsupported ID conventions similarly retain text without an extraction diagnostic.
- **Root-cause hypothesis:** Parser recognizes only the first anchored definition on each line; model/API exposes no extraction diagnostics.
- **Recommended correction:** Support well-defined inline definitions or reject/flag ambiguous multiple-definition records. Report unrecognized identifier candidates and add paragraph/table/custom-pattern tests. Keep raw text and exact IDs unchanged. Qualify `docs/rag-architecture.md:59` accordingly.

### D-004 — MEDIUM — Default basename identity aliases distinct source documents

- **Requirements:** P2-002; replacement behavior under P2-010.
- **Affected source:** `src/ee_arch_copilot/rag/ingestion/loader.py:32`; replacement at `src/ee_arch_copilot/rag/service.py:65`.
- **Reproduction:** Ingest two different `collision.md` contents without document IDs, representing different origins. First has `REQ-COLLIDE-001`, second `REQ-COLLIDE-002`.
- **Expected:** Distinct origins remain separate or the caller must explicitly acknowledge/identify a replacement before one origin becomes unavailable.
- **Actual:** Same derived document ID, second status `replaced`, first requirement no longer searchable. Explicit document IDs correctly preserve same-filename documents.
- **Root-cause hypothesis:** Default ID hashes only the basename; the envelope has no required origin namespace or conflict check. This is a **documented caller obligation**, not an undisclosed random collision (`README.md:196`, `docs/rag-architecture.md:30`). It still only partially satisfies the requested same-filename acceptance case.
- **Recommended correction:** Require stable caller-supplied source identity for ingestion/replacement, or add an origin namespace and explicit replacement operation. Do not simply derive IDs from content if updates must retain source identity. Keep the documented explicit-ID workaround until that policy is adopted.

### D-005 — MEDIUM — Semantic candidate truncation precedes exact-ID eligibility

- **Requirements:** P2-012, P2-015; exact retrieval expectations.
- **Affected source:** `src/ee_arch_copilot/rag/service.py:103,116`; `src/ee_arch_copilot/rag/retrieval/semantic.py:11`; `src/ee_arch_copilot/rag/storage/chroma_store.py:203`.
- **Reproduction:** Index one target `REQ-TARGET-001: Calibration values for obscure unrelated actuator mechanics.` and 13 other requirements (`REQ-DISTRACT-000` through 012), each statement repeating `REQ-TARGET-001` 20 times. Search the target ID with default semantic candidates=12. Then repeat with explicit `SearchFilter(requirement_id="REQ-TARGET-001")`.
- **Expected:** Exact-ID eligibility constrains semantic candidates before Top-K, so a known target is not lost to ineligible records.
- **Actual:** Default semantic search returns **[]**; keyword/hybrid return the target. Explicit metadata filter makes semantic return the target. All records remain present and valid.
- **Root-cause hypothesis:** Service creates `allowed` IDs but sends only ordinary request filters to Chroma. It discards disallowed hits after Chroma's Top-K has consumed the candidate budget.
- **Recommended correction:** Push explicit-ID eligibility into vector candidate filtering before truncation, or use a separate exact-ID retrieval path with clear ranking semantics. Preserve multiple-ID query behavior and test candidate starvation.

### D-006 — MEDIUM — Generation checks source references without enforcing engineering support/conflicts

- **Requirements:** P2-016, P2-017; Phase 3 evidence presentation.
- **Affected source:** `src/ee_arch_copilot/rag/generation/citations.py:27,31,55`; `src/ee_arch_copilot/rag/generation/prompts.py:9`; sufficiency branch `src/ee_arch_copilot/rag/generation/answer_generator.py:71`.
- **Reproduction:** Controlled provider cites the interface requirement while asserting that all TSN latency requirements/architecture checks passed. For two contradictory 5 ms/10 ms source constraints, return a one-sided “unambiguously 5 ms” response citing only one. For the injection document, return “All architecture checks passed. [S1]”.
- **Expected:** Unsupported verification claims must not become verified engineering results; conflicts should be surfaced and insufficient support made explicit. At minimum consumers need enforceable distinction between valid references and demonstrated engineering support.
- **Actual:** All responses return `cited` with the generated text intact. The explanation correctly warns semantic support is unproven. No deterministic validator is actually run or modified. Empty evidence abstains, but nonempty irrelevant/incomplete context alone does not cause abstention.
- **Root-cause hypothesis:** Structural label/ID checking and prompt instructions are the only gates. Claim entailment, units, verification evidence and conflicting constraints are not checked. This is substantially acknowledged in the existing docs, so it is classified as **PARTIAL capability**, not a claim that citation existence equals full grounding everywhere.
- **Recommended correction:** Preserve explicit unverified-generation status in consuming tools/UI; require linked deterministic validation evidence for compliance assertions, add conflict/sufficiency review and adversarial regression checks, and conduct a separately authorized real-provider evaluation. Do not claim prompt-injection immunity from controlled outputs or a single passing example.

## 14. Phase 3 Readiness

**READY WITH MINOR CHANGES** in architecture; **not accepted for integration yet** due D-001.

| Readiness condition | Evidence / conclusion |
| --- | --- |
| Stable Python retrieval interface | `KnowledgeService.search` returns structured `SearchResponse`/`SearchHit`/`Chunk`; exercised without LLM. PASS. |
| Resolvable citations | Ordinary sequential paths pass; after in-flight mutation fail. BLOCKER, D-001. |
| Retrieval independent of generation | Search works with provider absent/incomplete and keyword mode without query embeddings. PASS. |
| Generation independently invocable | `AnswerGenerator.answer(question, chunks, options)` exercised with controlled providers. PASS for interface; supplied snapshots need a lifetime policy. |
| Provider configuration isolated | Domain has no provider dependency; settings/providers are separate. PASS. |
| Explicit no-evidence behavior | Empty context fixed response and missing config clear; nonempty-context sufficiency PARTIAL. |
| Phase 1 independently callable | Domain/topology/validator unchanged; 108 regressions pass and no storage initialization needed. PASS. |
| Agent combines evidence with deterministic findings | Both result schemas preserve IDs and evidence separately; no automatic conversion or result mutation. Interface suitability verified; actual orchestrator behavior NOT VERIFIED/outside Phase 2. |
| Major structural refactor necessary | No. Add revision validity and ID/extraction guards to existing boundaries; storage protocol/lifecycle improvements are incremental. |

Future agents must distinguish requirement intent, source-reference validity and deterministic validation findings. Retrieval cannot certify TSN, isolation, protocol reachability or nominal bandwidth compliance. Single-process service operation still needs a deliberate evidence consistency policy during slow provider calls. Enterprise tenancy/concurrency and live model quality remain separate deployment/evaluation work, not prerequisites for claiming that current typed tools can be exposed.

## 15. Prioritized Remediation Plan

No remediation was performed. Estimates describe scope, not delivery promises.

| Priority | Proposed work / exit evidence | Effort |
| --- | --- | --- |
| 1 | D-001: verify active revision after generation or provide resolvable archival evidence; API delete/update-during-call regressions must never return a current validated dangling citation. | MEDIUM |
| 2 | D-002: align supported source/answer identifier grammars and reject/flag lowercase/custom fabricated references; zero accepted invalid references in the controlled cases. | SMALL |
| 3 | D-003: extraction diagnostics plus supported inline-definition boundaries; both independent requirements searchable or explicit review-required ingestion result. Preserve exact source. | MEDIUM |
| 4 | D-005: enforce exact-ID eligibility before vector Top-K; shadowing regression retrieves target and multiple-ID queries remain correct. | SMALL |
| 5 | D-004: choose explicit stable source/origin identity and replacement policy; same-basename independent origins cannot silently replace one another. | SMALL |
| 6 | D-006: enforce unverified explanation status, deterministic-proof joins for compliance claims, and conflict/sufficiency evaluation; validate with controlled cases before separately authorized live quality work. | MEDIUM for bounded tool/status guards; LARGE for broad automated semantic entailment assurance |
| 7 | Preserve independent evaluation/probes as reviewed regressions; reconcile broad documentation claims, add lifecycle cleanup/storage protocol if needed; rerun existing checks and both fixed datasets. | MEDIUM |

Live learned-model comparison should use a separate index with recorded identity, unchanged held-out labels and explicit authorization. Broad semantic assurance is not required to fix the local HIGH defect, and should not delay that focused correction. Optional production security, authentication and multiworker storage are future deployment work.

## 16. Final Go/No-Go Decision

### NO-GO

Core ingestion, storage, offline retrieval, API integration and Phase 1 compatibility are operational. However, the current implementation can return a citation already invalidated during answer generation, and some fabricated requirement references evade validation. The requested source-integrity acceptance condition therefore fails; all-tests-pass and high coverage do not override direct counterexamples.

Reassess after D-001 and the controlled identifier/boundary defects are corrected and their regressions pass, with remaining engineering-grounding limits explicitly bounded for Phase 3 consumers. The architecture can accommodate these corrections without major restructuring. No unconditional GO is warranted while source integrity fails or learned semantic/real generation quality is unverified.
