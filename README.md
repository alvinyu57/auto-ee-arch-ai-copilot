# auto-ee-arch-ai-copilot

An Automotive E/E Architecture Design, Analysis, and Validation Assistant, starting
with a small, deterministic Python core. Phase 1 models ECUs, switches, interfaces,
links, services, and engineering requirements, then exposes physical topology and
validation through a stateless REST API.

**This project is an independent technical proof of concept and is not affiliated with any automotive OEM.**

All supplied architectures, requirements, speeds, and traffic demands are synthetic
engineering test data, not OEM production specifications. No LLM, RAG, vector database,
cloud integration, or multi-agent workflow is implemented in this phase.

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
```

`domain` has no FastAPI or NetworkX dependency. `services` uses domain models and
NetworkX. The HTTP adapter handles request parsing and status codes. There is no
infrastructure package yet because Phase 1 needs no external adapters. Future
document stores and model providers can be added there when they have real behavior.

See [architecture details](docs/architecture.md), the
[architecture decision](docs/decisions/0001-architecture.md), and the
[roadmap](docs/roadmap.md).

## Install

Use Python **3.12+** and [uv](https://docs.astral.sh/uv/getting-started/installation/).
The repository defaults to Python 3.12; uv can download it if needed.

```bash
cd auto-ee-arch-ai-copilot
uv sync --locked --dev
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
docker run --rm -p 127.0.0.1:8000:8000 auto-ee-arch-ai-copilot
```

The image uses Python 3.12, locked runtime dependencies, a non-editable installation,
and an unprivileged user. It needs no database or companion container.

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
- No persistence, authentication, quotas, importers for proprietary formats, or enterprise integrations.
- No LLM, RAG, embeddings, vector store, cloud infrastructure, or agent orchestration yet.

## Roadmap and next step

See [the milestone roadmap](docs/roadmap.md). Phase 2 adds document ingestion,
requirements retrieval, and source citations. Begin with a small, versioned set of
synthetic requirement documents and a citation-preserving ingestion/retrieval contract.
Retrieved text should remain separate from structured constraints until reviewed by
an engineer; deterministic findings remain the source of truth for implemented checks.

Licensed under [Apache License 2.0](LICENSE).
