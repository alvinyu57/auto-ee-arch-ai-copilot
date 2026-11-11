# ADR 0002: Requirements RAG in the existing monolith

Date: 2026-11-10. Status: accepted and implemented.

## Context

Engineering retrieval needs exact identifiers, semantic matching, resolvable source
evidence, and offline operation without changing deterministic architecture validation.
LLM generation must be optional and cannot become a source of validation results.

## Decision

Add a `rag` package with Pydantic evidence contracts and a directly callable
`KnowledgeService`. Implement requirement-aware Markdown/text/JSON parsing and a trusted
local PDF loader. Keep original text, source location, optional ID, version, and stable
chunk identity through retrieval. Configure ID extraction rather than inventing IDs.

Use explicit embedding providers and Chroma persistent cosine search. Include a
deterministic signed-hash baseline for offline development and a compatible HTTP adapter
for learned embeddings. Reject model/dimension/schema mismatches; migration reingests
the corpus into a new directory. Track active source revisions transactionally in a
small SQLite catalog so staging failures cannot expose partial evidence. Keep the
entire store in one mountable directory and support one writer process.

Implement BM25 directly to preserve engineering tokens without an additional framework.
Fuse independently ranked lexical and semantic results with RRF. Expose component ranks
and scores; do not label them answer confidence. Optional local reranking uses a small
protocol with a transparent token-overlap implementation.

Use a separate HTTP LLM adapter and generation service. Require structured output and
context-only citation labels; construct public citations from retrieved records. Missing
configuration is a 503, malformed provider output a 502, missing evidence a structured
abstention, and invalid references suppress generated claims. Treat documents as untrusted
data and give the model no engineering tools in Phase 2.

Do not introduce LangChain, agent orchestration, remote databases, or changes to
architecture models. Exact requirement IDs are the integration link to Phase 1 and
future typed Phase 3 tools. Preserve all existing Phase 1 route behavior and health
metadata; extend OpenAPI additively.

## Consequences

Retrieval works without any model API call when using the local baseline. Keyword-only
queries do not call external embeddings. Learned semantics and live generation require
an explicitly configured provider. Tests inject controlled providers; production has no
mock fallback. External embeddings receive indexed text; generation receives selected
excerpts. Secrets stay in environment settings and never become index metadata.

The local catalog, BM25 scan, and Chroma process are appropriate for a bounded corpus,
not multiworker production hosting. Catalog and vectors require consistent backups.
Inactive vectors may remain after interrupted staging, and old citations expire on
replacement/deletion. Citation checks prove reference validity, not semantic faithfulness
or resistance to all prompt injections. Learned model quality, retrieval thresholds,
and engineering conclusions require separate evaluation and human review.

## Remediation amendment — 2026-11-10

Keep the original storage and service boundaries. Preserve filename-derived IDs for
compatibility, but require an explicit ID for a changed envelope that would replace
an existing source; otherwise return 409 without modifying data. Existing explicit-ID
updates and identical implicit-ID ingestions keep their behavior.

Push exact-ID chunk eligibility into vector filtering before Top-K. Recognize bounded
inline definitions and expose extraction warnings while retaining source text. New
warning fields default to empty when reading old catalog payloads; empty warnings do
not change existing revision fingerprints. Apply parser changes to selected existing
documents through explicit `reindex`, without resetting collections.

Recheck retrieved source revisions after generation, under the same local store lock,
and suppress stale output. Release the lock during the provider call. Freshness is
checked at the service return boundary, not guaranteed indefinitely for later URL reads.
Direct snapshot generation remains caller-managed.

Extend the response contract with stale/unsupported/conflicting evidence statuses,
fixed unverified claim and not-performed validation fields, and an unsupported-ID-grammar
signal. Tighten mention checks for case variants and numeric custom IDs. Add conservative
English verification-claim suppression and equal-template numeric-conflict surfacing.
These are bounded controls rather than semantic entailment, general conflict reasoning,
or prompt-injection immunity. Clients with exhaustive status matching must update.
Phase 3 must retain separate deterministic findings and require engineering review.
