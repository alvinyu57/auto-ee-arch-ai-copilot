# Roadmap

This is a technical proof of concept using synthetic data. Phases 1 and 2 are implemented;
live external model quality and container runtime behavior remain separate verification work.

## Phase 1: Core Architecture Modeling & Deterministic Validation

- Typed ECU, interface, Ethernet switch, link, service, requirement, and architecture models.
- Structural invariants and explicit cross-reference validation.
- Physical multigraph, paths, neighbors, disconnected nodes, and components.
- Physical connectivity and declared routed-demand nominal link budgets.
- Structured findings with explicit incomplete and unsupported evaluations.
- Stateless REST APIs, synthetic examples, offline tests, developer tools, CI, and Docker.

## Phase 2: Requirements RAG Pipeline — implemented

- Ingest a bounded collection of synthetic engineering requirement documents.
- Preserve document IDs, versions, sections, page locations, and source excerpts.
- Add embeddings, retrieval, citations, and a retrieval evaluation dataset.
- Define ingestion/retrieval contracts alongside real adapters under `rag`.
- Keep retrieved engineering prose separate from reviewed structured constraints.
- Make data handling and retrieval configuration explicit; no hidden external uploads.
- Markdown/text/JSON and trusted local extractable-PDF loading; no OCR.
- Chroma vectors plus an authoritative SQLite evidence catalog, idempotent revision replacement.
- Independent BM25, semantic, and RRF retrieval; optional local reranking.
- Optional compatible HTTP generation, citation validation, and explicit missing-evidence responses.
- Four synthetic documents, 24 retrieval queries, six QA review cases, offline tests and HTTP probe.
- See [measured evaluation](rag-evaluation.md) and the [implementation report](reviews/phase2-implementation-report.md).

## Phase 3: LLM Agent with Tool Calling

- Expose typed deterministic topology and validation tools to a model orchestrator.
- Validate tool inputs and proposed architecture changes with the domain schemas.
- Preserve findings and citations independently of generated explanations.
- Require human review of generated engineering assumptions and constraints.
- Add bounded execution, provider adapters, and reproducible orchestration tests.

## Phase 4: Architecture Review Reports & AI Evaluation

- Render architecture reviews from structured findings and cited requirements.
- Track assumptions, missing evidence, review decisions, and report provenance.
- Evaluate retrieval quality, tool correctness, groundedness, and unsupported claims.
- Expand synthetic scenarios and regression datasets; distinguish deterministic test
  failures from model-quality evaluation results.

## Phase 5: Cloud Deployment, Observability, Security, and API Integration

- Add deployment configuration when a concrete hosting target is selected.
- Add authentication/authorization, secrets management, request controls, and audit trails.
- Instrument latency, errors, tool use, retrieval quality, and model cost.
- Add persistence and enterprise integrations through real adapters.
- Version API/schema contracts and define operational reliability requirements.

## Recommended next increment

Begin Phase 3 with read-only typed tools around `KnowledgeService`, `TopologyService`,
and `ArchitectureValidator`. Compare a learned embedding model against the checked-in
retrieval baseline, and run a separately labeled live LLM QA review before trusting
generated engineering summaries. Physical/VLAN/service analyses must retain distinct
semantics as engineering coverage grows. More detailed networking (VLAN forwarding,
shared CAN buses, multicast, overhead, scheduling, or latency bounds) needs explicit
models and evidence-backed rules, not assumptions derived from physical adjacency.
