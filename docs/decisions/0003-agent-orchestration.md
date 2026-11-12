# ADR 0003: One bounded agent with server-owned engineering evidence

Status: Accepted for the Phase 3 MVP; live provider behavior remains NOT VERIFIED.

## Context

Phase 1 provides typed architecture validation, physical topology/path discovery and
deterministic nominal link-budget checks. Phase 2 provides persistent hybrid retrieval
and source provenance. The assistant must combine them without treating retrieved
requirements or generated prose as computed engineering verification.

## Decision

Use a lightweight single-agent native function-calling loop and an explicit typed
read-only registry. Adapt `KnowledgeService.search`, `TopologyService` and
`ArchitectureValidator` directly. Reuse the compatible HTTP provider infrastructure and
credentials, extending it with cancellable bounded async HTTP. No new provider SDK,
agent framework or independent agent is needed for four local engineering tools.

Bind tools to a copied, validated architecture in the current request. Do not add file
paths, arbitrary URL fetching, architecture-ID discovery, write tools, durable sessions
or background jobs. Documents can narrow a server-supplied Phase 2 search scope.

Give the LLM progressive tool results, not the complete architecture/index initially.
Enforce schemas, allowed tools, time/call/iteration/context/result budgets in Python.
Support multiple calls per reply with exact call-ID correlation and one bounded final
JSON repair. Preserve useful evidence after unrelated failures.

The server allocates evidence identities and builds citation metadata. The model can
reference existing evidence and select controlled review interpretations/recommendations.
It cannot supply validation statuses or source objects. Copy original
validation findings independently of generation. Keep PASS, FAIL and NOT_EVALUATED
separate from agent execution status. Following D-P3-001/002, replace the Agent's English
claim-pattern gate with `EngineeringResponseVerifier`: render the public status/scope
summary from committed tool evidence and constrain every generated narrative field to
exact review templates. Reject arbitrary assertions in recommendations/questions too.
An individual PASS or an all-PASS report cannot authorize architecture approval.

Keep the existing final wire schema and add `evidence_integrity` to the public response.
Record safe rejection categories and metadata-only integrity events. Permit one bounded
repair; otherwise return the deterministic evidence/citation fallback, PARTIAL or FAILED
under existing execution semantics. Never echo rejected prose. The schema still accepts
the original field shapes, but free-form explanations/assumptions are deliberately
withheld. The prompt advertises the enforced templates; code is the authority.

Inject a scripted native-protocol provider only in tests/evaluation. Independently score
outcomes against active source records and deterministic services, including adversarial
failures. Keep live and scripted metrics separately labeled.

## Consequences

The implementation is small enough to inspect, deterministic tools stay authoritative,
and no engineering rule or retrieval algorithm is duplicated. Existing Phase 1/2 routes
and schemas remain compatible. A request can return useful findings and explicit partial
execution rather than losing successful work after a later error.

Limits can prevent a complete analysis, especially for large models. Timed-out synchronous
reads cannot be forcibly stopped in a Python thread, although late results are withheld.
Local source-revision checks are not distributed transactions. Source truth/applicability,
authentication, tenant ACLs, production concurrency and real-provider quality need further
verification/hardening. Phase 4 can consume the existing response/evidence contracts;
architecture changes and design approval remain outside this phase.
The narrative restriction sacrifices free-form explanatory output for a deterministic
engineering conclusion boundary. It does not prove all arbitrary natural-language claims
correct. See the [remediation report](../reviews/phase3-remediation-report.md).

See [agent architecture](../agent-architecture.md), [evaluation](../agent-evaluation.md)
and the [implementation report](../reviews/phase3-implementation-report.md).
