# Phase 2 remediation report

Date: **2026-11-10 (Europe/Berlin)**. Base commit: **89d804d**. This report describes
the working-tree remediation of the [independent verification](phase2-verification-report.md).

## 1. Executive Summary

**CONDITIONALLY READY** for reviewed Phase 3 integration. The HIGH source-freshness
defect and four MEDIUM defects are fixed. The remaining MEDIUM engineering-grounding
capability is partially mitigated with typed unverified status, bounded claim guards,
and numeric-conflict surfacing; full semantic support/sufficiency verification remains
deferred. No CRITICAL or HIGH defect remains open.

| Classification | Count |
| --- | ---: |
| Defects reviewed | 6: 1 HIGH, 5 MEDIUM |
| Independently CONFIRMED | 6 |
| FIXED | 5 |
| DEFERRED, with bounded safeguards implemented | 1: D-006 |
| FALSE_POSITIVE / NOT_REPRODUCIBLE / INSUFFICIENT_EVIDENCE | 0 / 0 / 0 |
| Unresolved CRITICAL / HIGH | 0 / 0 |

The first independent regression run, before production changes, produced **20 failures
and one pass** across the six findings. Final verification: **243/243 tests passed**,
including all **108 Phase 1 tests**, with **99.16%** configured statement/branch coverage.
There are **28 new regression cases**, plus assertions strengthening evaluation tests.
Lint, formatting, strict typing, the distribution build, and controlled HTTP workflow pass.

On the unchanged original 24-query dataset, all three retrieval modes achieve
**Recall@5 0.977273, MRR 1.000000, exact-ID Hit@1 5/5**. Controlled generation emits
**0 invalid citations out of 12**, rejects **18 adversarial outputs**, and correctly
abstains on **6/6** original no-evidence cases across the three modes. These small
offline measurements do not establish learned semantic or live-generation quality.

The verification report was present. No separate original design specification was
found; README, roadmap, RAG architecture/evaluation documentation, ADR 0002, the supplied
requirements, implementation report, modules, lockfile, and tests formed the available
design basis. Findings were reproduced rather than accepted solely from the report.
Original golden labels, corpus, dependencies, and Phase 1 implementation/tests are unchanged.

Evidence artifacts:

- [Raw evaluation, baseline provenance, settings, hashes, and controlled responses](phase2-remediation-evaluation.json).
- [Controlled HTTP lifecycle and Phase 1 workflow](phase2-remediation-workflow.json).
- [Independent regression tests](../../tests/rag/test_remediation.py).
- [Reproducible offline evaluation script](../../scripts/evaluate_phase2_remediation.py).

## 2. Defect Resolution Matrix

Module paths below are relative to `src/ee_arch_copilot/`. Regression names refer to
`tests/rag/test_remediation.py` unless otherwise stated. All six classifications are
CONFIRMED; final disposition is recorded separately.

| Defect ID | Severity | Root Cause | Files Changed | Regression Test | Status |
| --- | --- | --- | --- | --- | --- |
| D-001 | HIGH | Generation validated snapshots without rechecking active revisions | `rag/service.py`, `rag/storage/chroma_store.py`, `rag/models.py` | `test_inflight_source_change_never_publishes_stale_citation` (delete/content/metadata); `test_generation_releases_store_lock_and_rechecks_after_concurrent_update` | FIXED |
| D-002 | MEDIUM | Case-sensitive configured mention regex missed lowercase/custom IDs; arbitrary JSON grammar was unmarked | `rag/identifiers.py`, `rag/generation/citations.py`, `rag/models.py` | `test_undeclared_prose_identifier_is_rejected`; `test_json_identifier_family_is_checked`; `test_unsupported_json_identifier_grammar_is_explicit` | FIXED within explicitly bounded grammar contract |
| D-003 | MEDIUM | Only anchored line starts defined records; unsupported extraction had no diagnostics | `rag/ingestion/{parser,chunker}.py`, `rag/models.py`, `rag/service.py`, `rag/storage/chroma_store.py` | `test_inline_definitions_preserve_independent_identity`; `test_custom_inline_pattern_and_sentence_reference`; `test_unsupported_extraction_is_visible`; canonical example | FIXED within documented extraction grammar |
| D-004 | MEDIUM | Basename-derived IDs allowed implicit destructive replacement of another origin | `rag/service.py`, `rag/errors.py`, `api/routes/knowledge.py` | `test_implicit_filename_collision_requires_explicit_replacement` | FIXED |
| D-005 | MEDIUM | Semantic Top-K ran before exact-ID eligibility filtering | `rag/service.py`, `rag/retrieval/semantic.py`, `rag/storage/chroma_store.py` | `test_semantic_exact_id_filter_precedes_top_k` (default and small candidate windows) | FIXED |
| D-006 | MEDIUM | Structural citation checks could not establish claim support, conflicts, or sufficiency | `rag/generation/{guards,citations,prompts}.py`, `rag/models.py` | Verification-claim, injection, conflict, unverified-status, and equal-value/distinct-scope regressions | DEFERRED for full semantic verification; bounded safeguards implemented |

Prioritization and dependencies: verify active source identity first (D-001/D-004),
then extraction and candidate eligibility (D-003/D-005), then output identity/grounding
(D-002/D-006), and finally retrieval evaluation and documentation. No unrelated
refactoring, public API renaming, new network validators, or Phase 3 orchestration was added.

## 3. Detailed Fixes

### D-001 — Current-source citations (P2-010, P2-015, P2-018)

Reproduction: ingest a requirement, then have an injected provider delete its source
or ingest a new content/version during `generate()`. Previously `ask` returned `cited`
with an unresolvable chunk. Metadata-only replacement also demonstrated that chunk-ID
existence alone cannot establish freshness.

`KnowledgeService.ask` now retrieves evidence and captures active document revision
fingerprints in one critical section. It releases the lock during the provider call
and rechecks **all retrieved document revisions** under the same lock afterward.
Changed/deleted evidence yields `stale_evidence` with no generated claims, citations,
or referenced requirement IDs. Clients can retry explicitly; provider calls are not
silently repeated. No archival store or long network lock was introduced.

The three API mutation regressions now return HTTP 200 with `stale_evidence`, rather
than a dangling validated citation. A separate two-thread test proves an update can
complete while generation waits, and the answer is rejected afterward. Unchanged
sources still produce resolvable citations. Freshness is checked at service return;
later edits can expire URLs. Direct snapshot-based `AnswerGenerator.answer` has no
storage boundary and remains caller-managed.

### D-002 — Requirement mention integrity (P2-016, P2-018, P2-023)

Reproduction: cite a real `REQ-ETH-001`, but return undeclared `req-eth-999`, a casing
change `req-eth-001`, or `custom:999` in prose. The old case-sensitive default regex
accepted these and substituted the real ID in structured output.

Mention detection now checks configured patterns case-insensitively, common numeric
hyphen/underscore/colon IDs, and escaped numeric families derived from actual JSON IDs.
Validation still requires exact source spelling; it never rewrites a generated variant
into a valid source ID. Structured references must also belong to cited records.
Invalid references suppress the generated answer and return `invalid_citations`.

JSON still preserves arbitrary existing IDs. When a cited source uses an unsupported
prose grammar, the response explicitly sets
`reference_validation="unsupported_identifier_grammar"` and explains the limitation.
For example `custom:alpha` cannot establish that arbitrary `custom:beta` prose is a
valid requirement reference; that limitation is now machine-readable and all claims
remain unverified. No universal arbitrary-string ID detector is claimed.

Numeric custom-ID, lowercase, undeclared-reference, duplicate-label, and original
technical-identifier tests pass. Correct source spellings remain accepted.

### D-003 — Independent inline requirements and diagnostics (P2-003, P2-004, P2-025)

Reproduction: `REQ-ETH-010: Gateway shall connect. REQ-ETH-011: Camera shall connect.`
was one record with ID 010, and querying 011 returned no hits. Table rows and default-
unsupported `ENG_42` records retained text without signaling the extraction limitation.

The existing parser now recognizes bounded inline `ID:` definitions after sentence
punctuation and whitespace. It flushes records using actual source offsets, preserving
exact text, section ancestry, multiline continuation, and configured ID patterns.
Ordinary sentence references without a definition delimiter do not split records.

Unassigned records containing detected requirement-like IDs now carry persisted
`extraction_warnings`, aggregated on ingestion responses and retained in chunks.
Tables and unsupported numeric ID conventions preserve original text and require
review instead of inventing identities. This remains a heuristic parser, not complete
layout or requirements-language understanding.

Inline requirements are independently retrievable; repeated ingestion preserves IDs
and exactly two vectors. The supplied canonical Ethernet example gives three distinct
requirements, exact IDs/offsets/headings, stable identity, and retained source metadata.
Custom inline patterns, long-record overlap, and JSON fragment/pointer tests pass.

### D-004 — Explicit source replacement (P2-002, P2-010)

Reproduction: ingest different documents named `collision.txt` without IDs. Previously
the second silently replaced the first because both hashed the same basename.

The stable default identity is preserved, but a changed implicit-ID envelope now raises
`DocumentIdentityConflict` before embedding or storage. HTTP maps this to **409** with
instructions to supply the existing ID for replacement or a distinct ID for another
origin. Identical implicit ingestion remains `unchanged` and creates no duplicate chunks.

The regression proves 409 leaves the first source searchable; a distinct explicit ID
preserves both same-filename sources, and the original explicit ID authorizes intentional
replacement. Existing explicit-ID lifecycle tests still pass. This intentionally changes
implicit replacement behavior; clients must retain returned IDs for subsequent updates.

### D-005 — Exact-ID semantic candidates (P2-012, P2-015)

Reproduction: one actual `REQ-TARGET-001` plus 13 other requirements repeating that ID
used up vector candidates. Post-query eligibility filtering returned no target evidence.

The existing semantic/store interfaces now accept an optional eligible chunk-ID set.
The Chroma query intersects that set with active revisions and metadata filters **before
Top-K**, then resolves results against the authoritative catalog. Existing signatures
remain callable without the new argument. No hardcoded evaluation answers or score
confidence interpretation was added.

Default semantic options and a two-candidate window retrieve the actual target. A
two-ID query preserves both target records, and incompatible document filters yield no
results. Existing learned-synonym MockTransport, RRF arithmetic/deduplication, keyword,
reranking, persistence, and metadata-filter tests pass.

### D-006 — Bounded safeguards; full support verification deferred (P2-016, P2-017)

Reproduction: controlled providers returned “All architecture checks passed” or claimed
TSN compliance with interface-only evidence. A provider silently selected 5 ms from
two otherwise equal 5 ms/10 ms constraints. Valid labels alone allowed these outputs.

Implemented safeguards:

- Every `AnswerResponse` fixes `claim_status="unverified"` and
  `engineering_validation="not_performed"`; the model cannot elevate either field.
- Recognized English verification/compliance assertions are withheld with
  `unsupported_claims`. Phase 2 has no linked deterministic proof to authorize them.
- Equal statement templates with different numeric quantities in equal units return
  `conflicting_evidence` with both original source excerpts and citations, overriding
  a one-sided model selection. Decimal-equivalent values and different statement scopes
  are covered by negative regressions.
- Prompt instructions explicitly require conflict attribution and prohibit deriving
  validation outcomes from retrieved prose. Evidence remains structured untrusted data
  with no tool execution capability.

These controls reject the reproduced compliance and injection outputs and surface the
controlled numeric conflict. They **do not** implement semantic entailment, all forms
of verification language, unit conversion, applicability/precedence, general conflicts,
or evidence sufficiency for nonempty retrieved context. Guards can have false positives
and false negatives. Full D-006 assurance is therefore **DEFERRED**, not counted as fixed.
Real-provider generation and broader reviewed negative/conflicting cases are still needed.

## 4. Data Integrity Verification

| Scenario | Executed evidence and result |
| --- | --- |
| Duplicate ingestion | Existing lifecycle, inline, canonical, and HTTP probes return `unchanged`; timestamps/IDs remain stable; no duplicate active vectors. |
| Source updates | Explicit-ID changes return `replaced`; old content/version chunk IDs disappear; old requirement searches are empty in all three modes. Metadata-only changes preserve permitted stable IDs but change revisions. |
| Deletion | Catalog records and vectors disappear; all search modes stop returning deleted requirements; unknown deletion is 404. Unrelated sources remain. |
| Same filename | Implicit changed-envelope collision returns 409 without mutation; distinct explicit IDs preserve two origins; intentional explicit replacement works. |
| Failed embedding | New regression forces embedding failure during replacement; original catalog and all three retrieval modes remain intact, vector count remains three. |
| Failed staging | Existing forced Chroma upsert failure preserves the active revision; orphan/inactive vectors remain ineligible. |
| Persistence | Existing reopen/filter tests and the controlled workflow read stored sources and vectors successfully. |
| Legacy catalog | A regression persists pre-remediation chunk JSON without warning fields and a legacy revision fingerprint; reopening and identical implicit ingestion skip embedding and retain retrieval. |
| Keyword/vector synchronization | BM25 rebuilds from active catalog chunks per search; vector queries use active revisions and eligible IDs. Update/delete/failure regressions cover both views. |
| Provenance | Exact IDs, normalized offsets/lines, headings, filenames, versions, JSON pointers/fields, and metadata pass original and canonical regressions. |

No existing user index was reset, deleted, or reindexed. Execution used isolated
temporary stores. There is no database schema change. Empty warning fields are excluded
from revision fingerprints to preserve the previous contract; old payloads default them
to empty. To apply new parsing/diagnostics to an affected existing document, explicitly
call `reindex(document_id)` after a consistent catalog/vector backup. No automatic
bulk migration is performed. One shared service/store in one process remains the
supported concurrency scope; crash recovery and multiple writer processes are not certified.

## 5. Retrieval Evaluation

Dataset version is its exact-byte SHA-256:

- Retrieval: `ffee2376d6b3a3b42e882e8794c77c8e0ddae10f6b08b7db4f105f2358ec7d1a`.
- QA: `87c74b249d1dfedc8a422b95f27134494ffd77cc46a3b830832d7d0f4f36b4fd`.

The unchanged original dataset has **24 queries: 22 answerable and two negative**.
Four version-1.0 synthetic documents produce **34 chunks, 30 requirement-bearing**.
All corpus hashes match the original saved retrieval reports. Configuration:
`hash:hash-token-v1:384`, Chroma cosine, 1,000-character chunks, overlap 120,
semantic/keyword candidates 12, final K 5, RRF constant 60, minimum similarity 0.15,
no metadata filters, reranking disabled. No learned embedding or live LLM was used.

| Method | Recall@1 | Recall@3 | Recall@5 | Precision@3 | MRR within 5 | Exact ID Hit@1 | Negative retrieval abstention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Keyword | 0.787879 | 0.977273 | 0.977273 | 0.469697 | 1.000000 | 1.000000 (5/5) | 2/2 |
| Semantic with hash vectors | 0.787879 | 0.977273 | 0.977273 | 0.469697 | 1.000000 | 1.000000 (5/5) | 2/2 |
| Hybrid | 0.787879 | 0.977273 | 0.977273 | 0.469697 | 1.000000 | 1.000000 (5/5) | 2/2 |

Metrics average unique requirement units over answerable queries; Precision@3 uses
fixed denominator three. Exact-ID Hit@1 includes q01–q05 only; q22 also contains prose.
The new evaluator retains source-aware relevance, configured-K metrics, and missing-source
failures while adding fixed cutoffs and dataset hash. Use final K >= 5 for @5 comparisons.

| Metric | Before | After | Target |
| --- | --- | --- | --- |
| Exact ID Hit@1 | 100% (5/5), recomputed from saved original rankings | 100% (5/5), all three modes | >=95% |
| Recall@5 | 97.7273%, original reports and reproduced audit baseline | 97.7273%, all three modes | >=90% |
| MRR | 1.000000, original reports and audit baseline | 1.000000, all three modes | >=0.85 |
| Invalid Citation Rate | Not quantified; audit reproduced accepted invalid/stale outputs | 0% (0/12 emitted controlled citations); 18 adversarial outputs suppressed | 0% controlled |
| No-Evidence Accuracy | Not quantified as an answer-level rate; golden retrieval abstention was 2/2 | 100% (6/6 controlled answers: two negatives times three modes) | 100% controlled |

Extra baseline Recall@1/3 and Precision@3 were independently recomputed from preserved
saved rankings; they match the after values. The verification report's **separate
28-query independent dataset** had keyword/hybrid Recall@5 1.0, semantic 0.958333,
and negative retrieval abstention **2/4**. Those are different corpus/query denominators
and must not be presented as an improvement to the original 24-query results. That
independent dataset was not reconstructed or modified for this run.

Remaining failed case: **q09** still misses `REQ-ISO-001` within five results, although
`REQ-ETH-008` ranks first. This cross-document isolation miss predates remediation and
does not lower the measured aggregates below provisional targets. No ranking tuning
or label changes were made to erase it. Shadowing is verified by the separate regression,
so unchanged golden aggregates do not imply the D-005 fix had no effect.

Controlled generation uses an explicitly labeled excerpt-only test instrument, not a
production fallback. Its 12 citations resolve to retrieved, active records with correct
documents, versions, requirement IDs, locations, and quotes. Its six abstentions cover
the original two negatives in each retrieval mode. It does not answer/adjudicate all
QA expected facts or measure entailment. Learned semantic quality and live-model
faithfulness/sufficiency remain **NOT VERIFIED**. All targets here are provisional
synthetic-PoC targets, not universal guarantees.

## 6. Citation and Grounding Assessment

Source labels remain context-scoped; public source metadata is constructed from
catalog-derived records, never trusted from provider output. Invalid labels/IDs suppress
claims. `ask` now additionally checks current revisions after generation, including
metadata-only edits. All emitted citations in the controlled workflow resolve programmatically.

`cited` means bounded reference checks passed, while `claim_status` and
`engineering_validation` explicitly prevent treating the response as a deterministic
verification result. `unsupported_identifier_grammar` requires source-reference review.
`conflicting_evidence` is a potential-conflict signal with both sources, not an engineering
resolution. Retrieved text remains untrusted and cannot invoke tools. No prompt-injection
immunity, unrestricted fabricated-reference detection, or full hallucination prevention
is claimed. D-006 remains open for general semantic support and sufficiency.

## 7. API Verification

Existing routes and schemas are preserved and extended with typed response fields.
Original knowledge API tests, new API regressions, and the controlled HTTP workflow pass.

| Endpoint / scenario | Verified behavior |
| --- | --- |
| POST `/api/v1/knowledge/documents` | 200 create/unchanged/explicit replacement; 409 changed implicit identity; malformed/empty/unsupported documents 422; body limits 413. |
| GET `/api/v1/knowledge/documents` | 200 typed summaries, correct metadata/version/counts. |
| GET documents/chunks by ID | 200 authoritative active record; unknown/deleted/expired IDs 404. |
| DELETE `/api/v1/knowledge/documents/{id}` | 204 successful deletion; 404 absent source; deleted evidence leaves retrieval. |
| POST `/api/v1/knowledge/search` | All three modes, typed metadata, Top-K, filters; invalid options/question 422; no LLM dependency. |
| POST `/api/v1/knowledge/ask` | Valid controlled citations or explicit insufficient response; absent LLM configuration 503; malformed/provider errors 502; in-flight mutations return 200 `stale_evidence` without claims/citations. |
| Storage/model configuration errors | Existing sanitized 503 paths pass; Phase 1 remains usable independently. |
| Injection/compliance/conflict | Typed `unsupported_claims` or `conflicting_evidence` is exercised through service tests; provider receives structured untrusted context and no validator tools. |

Intentional compatibility changes: implicit changed-envelope replacement now requires
an explicit ID; response status enums have three additional values; warning and verification
fields are additive. Clients doing exhaustive enum matching must update. Chunk-ID strategy
and existing endpoints were not renamed. Ordinary active-source URLs can still expire on
later deletion or content/version replacement.

## 8. Phase 1 Regression Results

All **108 original Phase 1 tests passed** in the full 243-test run:
25 API, 41 domain-model, eight topology, 16 traffic-completeness, and 18 validator tests.
Physical paths, NetworkX multigraph behavior, connectivity, nominal bandwidth budgets,
structural validation, original HTTP contracts, and incomplete/unsupported engineering
statuses remain deterministic. The HTTP workflow also validates the supplied centralized
architecture and retains `NOT_EVALUATED` for unsupported checks.

Git diff confirms no changes to Phase 1 domain/services, original routes, or these
original tests. No RAG/LLM dependency was introduced into automotive models, topology,
connectivity, bandwidth, or validation rules. Credentials and vector initialization are
not required for deterministic validation; existing lazy-resource API regressions pass.

## 9. Engineering Quality

Executed with Python **3.12.16**, Chroma **1.5.9**, pytest **9.2.0**. `uv` is available
at `/tmp/ee-arch-uv/bin/uv`, not the shell PATH. These are the exact command forms used:

```bash
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv sync --locked --all-groups
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv run --no-sync ruff check .
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv run --no-sync ruff format --check .
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv run --no-sync mypy src tests scripts/evaluate_phase2_remediation.py --cache-dir /tmp/phase2-remediation-mypy
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=/tmp/phase2-remediation.coverage UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv run --no-sync pytest --cov-report=xml:/tmp/phase2-remediation-coverage.xml --junitxml=/tmp/phase2-remediation-tests.xml
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv run --no-sync python scripts/evaluate_phase2_remediation.py --output docs/reviews/phase2-remediation-evaluation.json
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv run --no-sync python scripts/verify_phase2.py --output docs/reviews/phase2-remediation-workflow.json
env -u PYTHONPATH UV_CACHE_DIR=/tmp/phase2-remediation-uv /tmp/ee-arch-uv/bin/uv build
git diff --check
```

| Check | Outcome |
| --- | --- |
| Locked dependency sync | PASS: 110 resolved entries; 108 applicable installed packages checked; no lock/dependency edits. |
| Ruff lint | PASS: all checks. |
| Ruff format | PASS: repository formatting, including Markdown Python snippets. |
| Strict mypy | PASS: 70 source/test/script files checked. |
| Full pytest | PASS: **243 tests in 24.37 seconds**; **99.16%** coverage; 1,531 statements, 374 branches, seven missed statements, nine partial branches. |
| Controlled evaluation | PASS: three modes; unchanged golden labels; raw evidence saved. |
| Controlled HTTP workflow | PASS: lifecycle, citations, three retrieval modes, reopen, update/delete, and Phase 1 validation. |
| Distribution build | PASS: wheel and source archive generated. |
| Diff scope / whitespace | PASS: reviewed source/docs/tests/artifacts; corpus, labels, lockfile, dependencies and Phase 1 unchanged. |

Execution history is not hidden: sandboxed TestClient stalled and was interrupted;
authorized outside-sandbox test/workflow runs completed. The first build could not
resolve PyPI DNS inside the sandbox; an authorized rerun downloaded the isolated build
backend and passed. Initial lint/type errors in new code were corrected. A later legacy
test fixture initially fingerprinted catalog-ID order instead of original ingestion
order; the fixture was corrected without weakening its unchanged-ingestion or retrieval
assertions, and the final suite passed. The original audit report had two preexisting
Python code-fence formatting failures; only whitespace in those examples was normalized
for Ruff, with findings, measurements, and prose preserved. No checks were disabled.

## 10. Remaining Risks

- **D-006, MEDIUM, deferred:** arbitrary claim support, nonempty-context sufficiency,
  and general conflict detection remain unimplemented. Fixed unverified fields and
  bounded guards mitigate presentation risk but do not prove factual correctness.
- **Live models:** no learned embedding or live LLM evaluation. Hash-vector success
  cannot establish semantic generalization; controlled excerpts cannot establish answer quality.
- **q09:** original cross-document isolation retrieval miss remains despite passing
  aggregate PoC thresholds. Audit i27/i28 also illustrate nonempty insufficient contexts;
  this run makes no claim to solve those negative questions.
- **Bounded extraction/reference grammars:** unsupported source layouts/IDs require
  review or configured patterns; diagnostics cannot recognize every unknown convention.
- **Local persistence scope:** one shared service/process, no archival citations or
  multiprocess coordination. Inactive staging vectors can consume disk after failures;
  crash/disk-exhaustion recovery, production load, and Docker runtime remain unverified.
- **Integration:** consumers must honor status fields and keep deterministic findings
  separate. No authentication/tenant boundary or production-cloud infrastructure was added.

## 11. Phase 3 Readiness

Typed `KnowledgeService.search`, `ask`, `ingest`, and `reindex`, plus current catalog
resolution, remain usable service boundaries. Search is independent of LLM generation;
keyword retrieval avoids query embeddings. The provider/model identity checks and
optional reranker boundary remain intact. Existing deterministic tools can be called
independently without importing RAG into Phase 1 models or validation rules.

Reviewed Phase 3 integration can proceed subject to these explicit conditions:

1. Use `KnowledgeService.ask` for current evidence and handle stale/unsupported/conflict
   statuses; do not treat direct snapshot generation as a freshness check.
2. Preserve `claim_status=unverified`, `engineering_validation=not_performed`, source
   citations, extraction warnings, and unsupported-grammar signals. Engineering PASS/FAIL
   must come from separate deterministic findings, not model prose or citation existence.
3. Use explicit document IDs for changes and apply deliberate reindexing to affected
   existing sources; do not reset user collections to adopt parsing changes.
4. Before accepting live semantic/answer quality, evaluate configured learned embeddings
   and an actual LLM against reviewed negatives/conflicts, including nonempty insufficient
   contexts, and adjudicate factual support. This remains an acceptance blocker for
   unrestricted automated engineering conclusions.

## 12. Final Recommendation

**CONDITIONALLY READY.** All confirmed HIGH defects and four MEDIUM defects are closed;
the remaining MEDIUM grounding capability is explicitly deferred with tested bounded
mitigations. Local ingestion, identity, active retrieval, citation freshness, API behavior,
Phase 1 independence, automated quality checks, and original synthetic retrieval targets
are verified. Full semantic grounding and real-provider quality are not accepted by
these offline results. Phase 3 must preserve these limits and deterministic evidence boundaries.
