# auto-ee-arch-ai-copilot

An Automotive E/E Architecture Design, Analysis, and Validation Assistant, starting
with a small, deterministic Python core. Phase 1 models ECUs, switches, interfaces,
links, services, and engineering requirements, then exposes physical topology and
validation through a stateless REST API.

**This project is an independent technical proof of concept and is not affiliated with any automotive OEM.**

All supplied architectures, requirements, speeds, and traffic demands are synthetic
engineering test data, not OEM production specifications. Phase 2 adds persistent
requirements retrieval and optional evidence-citing generation. Local retrieval and
all tests run without API keys or model downloads. Phase 3 adds a bounded, read-only
single agent with native tool calling. Deterministic validator findings remain authoritative;
generated interpretations are unverified. Live provider behavior is not yet verified.

## Executive Overview

Automotive Electrical/Electronic (E/E) architecture development is becoming increasingly complex as vehicles transition from distributed, ECU-centric architectures toward centralized computing, zonal architectures, and Software-Defined Vehicles (SDVs).

Traditional E/E architecture development relies heavily on manual requirements analysis, expert-driven design decisions, fragmented engineering tools, and repeated cross-functional reviews.

As vehicle functions, communication interfaces, and software dependencies increase, these conventional approaches face significant challenges in engineering efficiency, architecture consistency, change impact analysis, and requirements traceability.

The proposed Automotive E/E Architecture AI Copilot aims to address these challenges by combining three complementary capabilities:

- Retrieval-Augmented Generation (RAG): Retrieve relevant engineering requirements, design guidelines, and architecture documentation.
- LLM-powered reasoning and tool calling: Interpret engineering questions, coordinate analysis workflows, and explain technical findings.
- Deterministic architecture validation: Use structured E/E models and Python-based engineering tools to verify connectivity, bandwidth constraints, and architecture consistency.

The goal is not to replace automotive system architects, but to help them make faster, better-informed, and more traceable engineering decisions.

## Phase 1 features

- Pydantic v2 models with cross-reference validation and useful structural errors.
- Ethernet and CAN interfaces with explicit nominal Mbps quantities; Ethernet VLAN annotations.
- NetworkX physical multigraph, parallel links, paths, neighbors, isolated nodes, and components.
- Structured connectivity requirements and explicit routed-demand link budget checks.
- Evidence-backed `PASS`, `FAIL`, and `NOT_EVALUATED` findings.
- FastAPI endpoints and OpenAPI documentation, with no persistent state.
- Offline tests, coverage threshold, Ruff, strict mypy, pre-commit, CI, and Docker.

## Architecture

```text
HTTP / OpenAPI (api) → deterministic use cases (services) → validated data (domain)
                    → knowledge use cases (rag) → parsers / embeddings / Chroma + catalog
                                               → optional LLM / citation checks
```

`domain` has no FastAPI or NetworkX dependency. `services` uses domain models and
NetworkX. The HTTP adapter handles request parsing and status codes. There is no
coupling between deterministic validation and the knowledge pipeline. The `rag`
package contains the working source, storage, retrieval, and provider adapters.

See [architecture details](docs/architecture.md), the
[architecture decision](docs/decisions/0001-architecture.md), and the
[roadmap](docs/roadmap.md).

Phase 2 details: [RAG architecture](docs/rag-architecture.md),
[evaluation and measured results](docs/rag-evaluation.md),
[ADR 0002](docs/decisions/0002-requirements-rag.md), and
[implementation report](docs/reviews/phase2-implementation-report.md).

## Install

Use Python **3.12+** and [uv](https://docs.astral.sh/uv/getting-started/installation/).
The repository defaults to Python 3.12; uv can download it if needed.

```bash
cd auto-ee-arch-ai-copilot
uv sync --locked --all-groups
uv run --locked pre-commit install
```

`uv.lock` pins the resolved runtime and development dependencies. No credentials or
external services are needed to run the application or tests after installation.

## Run the API

```bash
uv run --locked uvicorn ee_arch_copilot.main:app --reload
```

Open <http://127.0.0.1:8000/docs> for interactive OpenAPI documentation.
The schema is at `/openapi.json`; ReDoc is at `/redoc`.

| Endpoint | Body | Result |
| --- | --- | --- |
| `GET /health` | None | Basic process health, version, and phase |
| `POST /api/v1/architectures/validate` | Architecture | Structured validation report |
| `POST /api/v1/architectures/topology` | Architecture | Physical nodes, edges, isolated nodes, components |
| `POST /api/v1/architectures/path` | Architecture and two device IDs | One unweighted physical path or `exists: false` |
| `POST /api/v1/knowledge/documents` | JSON document envelope | Created, unchanged, or replaced source revision |
| `GET /api/v1/knowledge/documents` | None | Indexed source summaries |
| `GET /api/v1/knowledge/documents/{id}` | None | Normalized indexed source |
| `GET /api/v1/knowledge/chunks/{id}` | None | Resolve an active citation |
| `DELETE /api/v1/knowledge/documents/{id}` | None | Delete source and vectors; 204 or 404 |
| `POST /api/v1/knowledge/search` | Question and optional retrieval options | Evidence without an LLM call |
| `POST /api/v1/knowledge/ask` | Question, retrieval and generation options | Cited answer or insufficient evidence; 503 if disabled |

Structural request errors return HTTP **422**. An unknown device in a path query
returns **404**. Valid analysis requests return **200**, including engineering
`FAIL` findings, incomplete evaluations, and the absence of a physical path.

### Example requests

Run these commands from the repository root in a second terminal:

```bash
curl --fail-with-body http://127.0.0.1:8000/health

curl --fail-with-body http://127.0.0.1:8000/api/v1/architectures/validate \
  -H 'Content-Type: application/json' \
  --data-binary @data/examples/centralized_architecture.json

curl --fail-with-body http://127.0.0.1:8000/api/v1/architectures/topology \
  -H 'Content-Type: application/json' \
  --data-binary @data/examples/centralized_architecture.json

uv run --locked python - <<'PY' > /tmp/ee-physical-path.json
import json
from pathlib import Path

architecture = json.loads(Path('data/examples/centralized_architecture.json').read_text())
print(json.dumps({
    'architecture': architecture,
    'source_device_id': 'front-camera',
    'destination_device_id': 'adas',
}))
PY

curl --fail-with-body http://127.0.0.1:8000/api/v1/architectures/path \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/ee-physical-path.json
```

The path result contains `front-camera → switch-core → adas` and
`link-camera`, `link-adas`. It explicitly reports `connectivity_scope: physical`.
The sample validation report has **9 PASS**, **2 NOT_EVALUATED**, and **0 FAIL**
findings: isolation and the free-text latency requirement remain unevaluated.
The overall status is therefore `NOT_EVALUATED`.

## Requirements knowledge pipeline (Phase 2)

Markdown, text, and JSON document content can be indexed through the API. Extractable
PDFs use `rag.ingestion.loader.load_file` from trusted Python code; pages without text
are rejected with an explicit OCR limitation. No HTTP request accepts a local path.

Ingest a minimal synthetic source:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/knowledge/documents \
  -H 'Content-Type: application/json' -d '{
    "document_id": "demo", "filename": "demo.md", "source_type": "markdown", "version": "1.0",
    "content": "# Synthetic gateway\n\nREQ-ETH-001: Gateway shall use 1000BASE-T1 at 1000 Mbps."
  }'
```

To load all four supplied specifications into the running API:

```bash
uv run --locked python - <<'PY'
from pathlib import Path
import httpx
from ee_arch_copilot.rag.ingestion.loader import load_file

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as api:
    for path in sorted(Path("data/knowledge/synthetic").glob("*.md")):
        source = load_file(path, document_id=path.stem, version="1.0")
        response = api.post("/api/v1/knowledge/documents", json=source.model_dump())
        response.raise_for_status()
        print(path.name, response.json()["status"])
PY
```

Search without an LLM:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' -d '{
    "question": "Which requirements define Ethernet bandwidth between the Central Gateway and ADAS controller?",
    "options": {"method": "hybrid", "semantic_top_k": 12, "keyword_top_k": 12,
                "final_top_k": 3, "rrf_constant": 60}
  }'
```

The response has `hits[].chunk` with the original requirement ID, source document ID,
filename, version, section, text, original text, source location, and stable chunk ID.
Each hit includes `score`, `rank`, `methods`, and component scores/ranks. These are
ranking signals, not probabilities that an answer is correct. See the actual captured
response in [the workflow evidence](docs/reviews/phase2-workflow.json).

Choose `keyword`, `semantic`, or `hybrid`; filters support `document_id`,
`requirement_id`, and `version`. Reranking is an optional local token-overlap heuristic.
Repeating the same envelope returns `unchanged`; reusing `document_id` with changed
content, metadata, or version replaces the active revision. Content/version changes
expire old chunk URLs; metadata-only edits may preserve chunk IDs. Omitting `document_id`
derives it from the basename, but changing that source without an explicit ID now returns
**409**. Use the returned ID for an intentional replacement, or another stable ID for a
different origin with the same filename. No requirement ID is invented. Ingestion and
chunk responses include `extraction_warnings` for detected unsupported ID/layout cases;
review those sources before depending on exact-ID retrieval.

The local default is deterministic hash embeddings. For learned semantic retrieval,
set `EMBEDDING_PROVIDER=openai_compatible`, `EMBEDDING_MODEL` to the server's embedding
model, `EMBEDDING_DIMENSION` to its output size, and `EMBEDDING_BASE_URL` to its `/v1`
endpoint. Set `EMBEDDING_API_KEY` only if needed. Model identity/dimension mismatches
reject index reuse: select a new `VECTOR_DB_PATH` and ingest the corpus again.

Copy `.env.example` to `.env` to configure providers. For generation, set
`LLM_PROVIDER=openai_compatible`, `LLM_MODEL`, `LLM_BASE_URL`, and optionally
`LLM_API_KEY`. The compatible server must support `/chat/completions` with JSON output.
Credentials stay in environment variables and are excluded from responses and metadata.
External providers receive the question and retrieved excerpts; embedding servers receive
indexed text. Use only endpoints suitable for the documents you intend to index.

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/knowledge/ask \
  -H 'Content-Type: application/json' -d '{
    "question": "REQ-ETH-002",
    "options": {"method": "hybrid", "final_top_k": 5},
    "generation": {"temperature": 0, "max_tokens": 1000}
  }'
```

`ask` returns `answer`, structured `citations`, `referenced_requirement_ids`, `model`,
and `evidence_status` (`cited`, `insufficient`, `invalid_citations`, `stale_evidence`,
`unsupported_claims`, or `conflicting_evidence`). Every answer carries
`claim_status="unverified"` and `engineering_validation="not_performed"`.
`reference_validation` flags unsupported prose ID grammars. `cited` means bounded
reference checks passed; it does not establish factual support. Sources changed during
generation suppress the answer and its citations; retry after `stale_evidence`.
Bounded guards withhold recognized compliance assertions and surface equal-template,
different-quantity requirements for review. Missing provider
configuration returns **503**; provider or malformed-response errors return **502**.
With a configured provider, empty retrieval returns a fixed insufficient-evidence
response without calling the model. Invalid citations suppress generated claims.
Citation checks establish source existence, not full semantic support. Retrieved documents
can contain prompt injections; the prompt treats them as untrusted data. Human review
remains necessary for engineering conclusions. Phase 2 does not run architecture validation.

Knowledge request bodies are bounded to 1,100,000 bytes by default; content is limited
to 1,000,000 characters and questions to 5,000. Invalid inputs return **422**,
oversized bodies **413**, and absent source/chunk IDs **404**. Settings are in
[settings.py](src/ee_arch_copilot/core/settings.py). The legacy `/health` response retains
`phase: 1` and version `0.1.0` for compatibility; OpenAPI documents the added capabilities.

Run the evaluation and independent offline acceptance probe:

```bash
uv run --locked python -m ee_arch_copilot.rag.evaluation.run --output /tmp/rag-evaluation.json
uv run --locked python scripts/verify_phase2.py --output /tmp/phase2-workflow.json
```

Both use temporary databases. The probe exercises real corpus ingestion through HTTP,
duplicate detection, persistent reopening, all search modes, citation resolution,
replacement/deletion, Phase 1 validation, and generation through a controlled HTTP
provider. It does not claim live LLM integration or answer quality.

## Architecture document format

The full, schema-valid example is
[centralized_architecture.json](data/examples/centralized_architecture.json).
[requirements.json](data/examples/requirements.json) is a standalone JSON array
of the same sample requirements; the API consumes requirements inside an architecture.

The following is a complete minimal synthetic document with one Ethernet link:

```json
{
  "id": "synthetic-minimal",
  "name": "Synthetic two-ECU architecture",
  "ecus": [
    {
      "id": "camera", "name": "Camera", "ecu_type": "sensor",
      "interfaces": [{"id": "eth0", "technology": "ethernet", "nominal_speed_mbps": 100, "vlan_ids": [20]}]
    },
    {
      "id": "adas", "name": "ADAS", "ecu_type": "domain_controller",
      "interfaces": [{"id": "eth0", "technology": "ethernet", "nominal_speed_mbps": 100, "vlan_ids": [20]}]
    }
  ],
  "links": [{
    "id": "camera-adas",
    "source": {"device_id": "camera", "interface_id": "eth0"},
    "destination": {"device_id": "adas", "interface_id": "eth0"},
    "technology": "ethernet",
    "nominal_bandwidth_mbps": 100
  }],
  "services": [{
    "id": "camera-stream", "name": "Camera stream",
    "provider_ecu_id": "camera", "consumer_ecu_ids": ["adas"], "protocol": "SOME/IP",
    "bandwidth_requirement_mbps": 60,
    "traffic_routes": [{"consumer_ecu_id": "adas", "link_ids": ["camera-adas"]}]
  }],
  "requirements": [{
    "id": "REQ-CONN", "description": "Synthetic physical connectivity requirement",
    "requirement_type": "connectivity",
    "constraints": {"kind": "connectivity", "source_device_id": "camera", "destination_device_id": "adas"}
  }]
}
```

Collections default to empty. Unknown fields are rejected. Device IDs are unique
across ECUs and switches; other entity IDs are unique in their collections. Interface
IDs are local to their device. Ethernet ports are point-to-point and cannot be reused
by multiple links. Parallel links use distinct physical interfaces.

Technology values are `ethernet` and `can`. Protocol labels are `SOME/IP`, `DDS`,
`MQTT`, `REST`, and `OTHER`. Labels declare intent; no protocol stack or transport
compatibility is inferred. VLAN IDs are integers from 1 to 4094; an empty list means
membership is unspecified, not that an access VLAN is inferred.

Structured constraints use a `kind` discriminator matching `requirement_type`:

- `connectivity`: `source_device_id`, `destination_device_id`; checks a physical path.
- `bandwidth`: `link_ids`; checks nominal budgets against declared service traffic.
- `isolation`: source and destination IDs; accepted but `NOT_EVALUATED` in Phase 1.
- Missing `constraints`: free-text requirement, always `NOT_EVALUATED`.

### Bandwidth interpretation

`bandwidth_requirement_mbps` is one provider-to-consumer unicast demand **per consumer**.
`traffic_routes` explicitly lists ordered link IDs from provider to each consumer.
The engine does not use a shortest path to assign traffic. It sums demands per
Ethernet direction, or into a shared budget for a CAN link. Missing link capacity is
not inferred from port speeds. Capacity cannot exceed a known endpoint speed.

If any communicating service lacks demand or a consumer route, link budget checks
remain `NOT_EVALUATED` unless the known traffic already proves an overload. Unknown
traffic might traverse any link, so this policy is deliberately conservative.
Each incomplete service also produces a `bandwidth.traffic_evaluability` finding
with its service/provider/consumer IDs and missing information, even when there are
no physical links. Missing demand and missing routes are reported together. The
overall result is `NOT_EVALUATED` unless another finding establishes `FAIL`.
No service consumers means no network demand. An empty service list means the
declared traffic inventory is empty; it makes no claim about real-world background traffic.

Findings include rule ID, optional requirement ID, severity, status, affected
components, explanation, and evidence. Routed demand values in evidence are decimal
strings in Mbps to keep the summation deterministic. The report status is `FAIL` if
any check fails, otherwise `NOT_EVALUATED` if any check is incomplete, otherwise `PASS`.
`PASS` is always limited to the declared model and the implemented rules.

## Test and development commands

```bash
uv run --locked ruff format .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
uv run --locked pre-commit run --all-files
uv build
```

Tests cover malformed documents, invalid references, duplicate IDs, disconnected
devices, parallel links, VLAN boundary limitations, incomplete traffic mappings,
aggregate overloads, Ethernet directionality, CAN budgets, REST status codes, and
statelessness. The coverage gate is **90%**, including branches, with terminal and XML
reports. Tests use in-process HTTP requests and require no network access or credentials.
If a ROS or other shell setup injects packages through `PYTHONPATH`, use a clean shell
or `env -u PYTHONPATH uv run --locked pytest` on Linux/macOS.

GitHub Actions installs the lockfile and runs formatting, lint, mypy, tests, and a
distribution build on Python 3.12 and 3.13. Local pre-commit hooks use the same locked
Ruff and mypy versions; `uv` must be on `PATH`.

## Docker

```bash
docker build -t auto-ee-arch-ai-copilot .
docker run --rm -p 127.0.0.1:8000:8000 -v ee-knowledge:/var/lib/ee-arch auto-ee-arch-ai-copilot
```

The image uses Python 3.12, locked runtime dependencies, a non-editable installation,
and an unprivileged user. A named volume persists Chroma and the evidence catalog;
it needs no companion container. Run one application worker against each local store.

## Known limitations

- A physical path does **not** establish VLAN connectivity or SOME/IP service reachability.
  A path through a gateway does not prove CAN/Ethernet translation or forwarding.
- VLAN membership is annotation only. No switch policy, tagging, routing, ACL, or isolation engine.
- Nominal link capacity is not guaranteed application throughput. Overhead, contention,
  loss, multicast, return traffic, background traffic, CAN bus arbitration, and switch
  fabric capacity are not modeled. Reverse traffic needs a separate declared service.
- CAN links represent physical adjacency and a local shared budget. A real multidrop
  bus and its bus-wide contention domain need a richer future model.
- No TSN scheduling, worst-case latency, functional safety, or cybersecurity certification analysis.
- Knowledge persistence is local and intended for one process; no authentication,
  tenant isolation, enterprise integrations, or proprietary-format importers.
- Hash embeddings provide a lexical baseline; configure a real embedding server for
  learned semantic retrieval. Live external embedding and LLM quality is not certified.
- Citation validity verifies references, not semantic faithfulness of every generated claim.
- Compliance and numeric-conflict guards are English heuristics; general entailment,
  sufficiency for nonempty context, arbitrary ID grammars, and conflict reasoning require review.
- No OCR, production TSN analysis, architecture modification, or automatic design approval.

## Roadmap and next step

See [the milestone roadmap](docs/roadmap.md). Phase 2 implements document ingestion,
requirements retrieval, source citations, and optional generation with a versioned
synthetic corpus and reproducible evaluation.
Retrieved text should remain separate from structured constraints until reviewed by
an engineer; deterministic findings remain the source of truth for implemented checks.
See the [Phase 2 remediation report](docs/reviews/phase2-remediation-report.md) for
corrected defects, compatibility changes, and the measured acceptance limits.

## Phase 3: read-only engineering agent

`POST /api/v1/agent/analyze` combines existing hybrid retrieval, physical topology,
path discovery, and deterministic validation through four approved Python tools.
It accepts `question`, optional `architecture` using the complete Phase 1 schema,
and `options` (`max_iterations`, `max_tool_calls`, `include_trace`). Omit architecture
for requirements lookup. There are no filesystem paths, sample-ID guesses, write tools,
background jobs, or persistent conversations in this API.

To use a real compatible provider, set `AGENT_PROVIDER=openai_compatible`, `AGENT_MODEL`
(or `LLM_MODEL`), `LLM_BASE_URL`, and, when required, `LLM_API_KEY` in your environment.
Use a model/server supporting native Chat Completions function calling and JSON output.
The existing HTTP infrastructure and credentials are reused; no provider SDK was added.
Ingest documents through the existing knowledge workflow before asking retrieval questions.
Keep provider URLs administrator-controlled. Retrieved text and relevant architecture
tool results are sent to that provider. Local hash embeddings remain the default.

With the server running, for example:

```bash
jq -n --slurpfile arch data/examples/centralized_architecture.json \
  '{question:"Retrieve REQ-ETH-002, find the physical path from gateway to adas, and validate supported constraints.", architecture:$arch[0], options:{include_trace:true}}' \
  | curl -sS http://127.0.0.1:8000/api/v1/agent/analyze \
      -H 'Content-Type: application/json' --data-binary @-
```

Without any LLM credentials, run the actual orchestration workflow with the injected
scripted test provider and an isolated synthetic index:

```bash
uv run --locked python -m ee_arch_copilot.agent.evaluation \
  --output /tmp/agent-evaluation-scripted.json \
  --demo-output /tmp/agent-workflow-scripted.json
```

This runs 24 tasks, including overload, missing routes, injection, invalid calls,
conflicting requirements, and budget exhaustion. Scripts simulate model messages;
the actual registry and Phase 1/2 tools run. Scripts are unavailable in production
configuration. CI runs this evaluation without paid calls. Optional live evaluation
uses `--live` and a separately named output file; it does not establish certification.

`COMPLETED` means orchestration finished with evidence, not that a design passed.
`INSUFFICIENT_EVIDENCE` includes empty retrieval, conflicting sources and collected
`NOT_EVALUATED` findings. `PARTIAL` discloses tool failures, limits or stale sources;
`FAILED` is an unrecoverable provider/protocol/final-output failure before useful execution.
Only server-copied `findings[].validation.status` supplies authoritative engineering
`PASS`, `FAIL` or `NOT_EVALUATED`. Citations and evidence identities are server-owned.

See [agent architecture](docs/agent-architecture.md), [evaluation definitions](docs/agent-evaluation.md),
and the [Phase 3 implementation report](docs/reviews/phase3-implementation-report.md)
for limits, observed results, API errors and remaining verification work.

Licensed under [Apache License 2.0](LICENSE).
