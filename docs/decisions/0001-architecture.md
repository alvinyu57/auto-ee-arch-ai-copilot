# ADR 0001: A deterministic Python core with stateless HTTP adapters

Date: 2026-11-10

Status: Accepted

## Context

Automotive E/E analysis combines structural data, physical networks, protocol-specific
reachability, and engineering requirements. A useful proof of concept must expose
where evidence is sufficient and where analysis is incomplete. Phase 1 needs a working,
testable core that future retrieval and language-model features can call safely.

## Decision

Use a src-layout Python 3.12+ package managed by uv, with Pydantic v2 domain models,
NetworkX physical topology, deterministic application services, and a FastAPI adapter.
Dependencies point inward from the API to services and domain. Pydantic is a deliberate
domain dependency: shared typed schemas and cross-reference checks are more valuable
here than duplicating DTOs and hand-written domain validation.

Use `MultiGraph` to preserve parallel physical links. Keep endpoint identities and VLAN
membership in edge attributes, but state the physical scope in every topology response.
Do not infer VLAN forwarding, Ethernet/CAN translation, or application reachability.

Require explicit provider-to-consumer routes and demand to evaluate nominal link budgets.
Use per-direction Ethernet accounting and a local shared CAN budget. Missing information
produces `NOT_EVALUATED`; demonstrated overloads produce `FAIL`. Free text remains free
text, and isolation analysis remains unsupported in Phase 1. No shortest-path traffic
assignment, effective-throughput estimate, TSN analysis, or worst-case latency claim.

Reject invalid structures at model boundaries. Report engineering failures in a structured
result. Keep APIs stateless and copy/revalidate mutable domain inputs in analysis services.
Use ordinary constructors rather than a dependency injection framework. Do not create an
empty infrastructure package, unused ports, fake AI adapters, or placeholder integrations.

## Consequences

The implementation remains small, inspectable, and independently testable offline.
Future retrieval and model orchestration can call the same services and retain their
evidence. Schema validation has some automotive rules but is not a safety certification.

Pydantic couples the domain schemas to one validation library; that is accepted for this
phase. Domain collections remain mutable for engineering edits, so service entry points
pay for snapshot revalidation. Large models may eventually require immutable snapshots
or incremental validation, based on measured performance.

Missing traffic mapping conservatively prevents passing budgets even on unrelated links.
A future traffic-scope model could reduce that conservatism. Explicit routes still do
not establish forwarding; richer VLAN, gateway, and protocol models must remain separately
identified analyses. CAN multidrop contention requires a bus model beyond pairwise links.

CI checks locked installation, formatting, lint, strict types, coverage, and packaging.
The Docker runtime uses the same lockfile and runs as a non-root user. Deployment security
and external integrations remain out of scope until Phase 5.
