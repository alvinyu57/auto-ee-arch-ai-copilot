# Phase 3 implementation report

Verification date: 2026-11-11 (Europe/Berlin).

## Executive Summary

Phase 3's read-only single-agent implementation is complete and verified offline.
The application now exposes `POST /api/v1/agent/analyze`, native compatible-provider
function calling, four typed engineering tools, request-scoped context, server-owned
evidence/citations, bounded execution, structured responses, safe errors and local traces.
Existing Phase 1/2 services are reused directly without duplicating their algorithms.

Final verification: **351 tests passed, 98.57% statement/branch combined coverage**;
Ruff lint/format, strict mypy, locked dependency synchronization, wheel and source
distribution builds passed. All **24/24 offline evaluation outcomes** passed.
The existing 90% coverage gate and earlier tests were retained.

**Live LLM tool-calling behavior: NOT VERIFIED.** The inspected configuration had
`AGENT_PROVIDER=none`, no agent/LLM model and no configured LLM credential. No paid
provider call was attempted. A real adapter is implemented and its native HTTP protocol
is tested with mocked transport, but that does not establish actual LLM selection quality.
Full live end-to-end acceptance remains pending a configured real-provider demonstration.

Follow-up: [provider connectivity diagnosis](agent-provider-connectivity-report.md) adds
Responses support for the subsequently configured `gpt-6.1-terra` model. Model metadata
access succeeded, but live generation is blocked by OpenAI `credit_balance_exhausted`.
That report contains the later 379-test regression results; the measurements below
remain the initial Phase 3 baseline.

## Architecture

The workflow is:

```text
Validated question + optional full Phase 1 Architecture
  -> owned request context + execution policy
  -> native LLM tool selection
  -> explicit typed read-only registry
  -> existing hybrid retrieval / topology / path / validator
  -> bounded results + server evidence identities
  -> correlated native tool messages + continuation
  -> final JSON validation, bounded repair, reference/source-freshness checks
  -> exact validator findings + unverified interpretations + citations + trace metadata
```

The implementation lives in `src/ee_arch_copilot/agent`, with the REST adapter in
`api/routes/agent.py`. Models, context, policies, evidence, prompts, provider interface,
observability and orchestration have separate small modules. The registry and four
adapters are under `agent/tools`. Scripted protocol fixtures live in `agent/testing.py`
and cannot be selected through production settings. `agent/evaluation.py` provides the
CLI, separate task golds and independent source/engineering outcome scoring.

`KnowledgeService.search` supplies hybrid retrieval without answer generation.
`TopologyService` supplies the graph and representative physical path.
`ArchitectureValidator` supplies authoritative engineering findings. The existing
compatible HTTP boundary gains asynchronous cancellable requests with response limits;
credentials, base URL and provider timeout are reused. No new dependency, provider SDK,
agent framework, multi-agent system or internal REST call was introduced.

Architecture tools bind to a copied, revalidated request model. The model receives an
availability flag initially and obtains details progressively. It cannot load an
architecture by guessing an ID, path or URL. Architecture and conversations are not
persisted. A server-injected document filter scope can only be narrowed by tool arguments;
the public request cannot set that scope. The MVP retains Phase 2's local single-user
access model and lazy knowledge-service/index initialization.

The model's final schema cannot supply validation statuses, source metadata or evidence
objects. The server copies original validator findings independently of generation and
derives requirement/rule references from collected evidence. Generated interpretations
remain explicitly unverified. Valid citation membership does not prove entailment.

See [agent architecture](../agent-architecture.md) and
[ADR 0003](../decisions/0003-agent-orchestration.md) for detailed contracts and trade-offs.

## Tool Registry

| Registered tool | Input contract | Result authority |
| --- | --- | --- |
| `search_requirements` | Nonblank query up to 5000 characters, integer top_k 1–10, optional existing document/version/requirement filters | Actual Phase 2 hybrid hits, exact requirement/document/version/chunk IDs, locations, text and ranking metadata |
| `get_architecture_topology` | Node/link bounds 1–100, defaults 50 | Existing physical topology, attributes and component summary; truncation explicit |
| `find_physical_path` | Exact source/destination device IDs from current architecture | Existing path existence, ordered devices/links and link attributes; physical-only and representative-path limitations |
| `validate_architecture` | Optional allowlisted existing rule IDs | Original report status and exact selected findings, components, evidence, explanations and omitted-findings scope |

Definitions include typed arguments/results, description, timeout and read-only flag.
Duplicate/write registrations are rejected. Every call uses strict Pydantic argument
validation; extra fields and arbitrary architecture/file/URL arguments are rejected.
Unknown tools are blocked and represented as `unregistered` in safe metadata.
Only the explicitly registered callbacks execute.

Successful validation execution metadata also preserves the original report status/scope,
selected rules and omitted-finding count in `validation_scope`. Filtered omissions are
explicit response limitations; scoped results cannot silently represent the full report.

Defaults are six model iterations, ten admitted tool attempts, 60 seconds analysis time,
ten seconds per tool wait, 16 KiB complete tool-result envelopes, 4 KiB arguments,
128 KiB serialized context, 256 KiB provider replies and 2000 output tokens per call.
The existing streamed HTTP request cap is 1,100,000 bytes. Request options may reduce,
never increase, server call/iteration budgets. Results that exceed their cap are rejected
intact; validation findings are not truncated into generated summaries. Topology
truncation is disclosed and returns PARTIAL.

## End-to-End Demonstration

The executed offline demonstration uses `data/examples/centralized_architecture.json`
and the existing synthetic Ethernet requirements, indexed in temporary storage.

Question: retrieve `REQ-ETH-002`, inspect topology, discover the physical path from
`gateway` to `adas`, and validate supported constraints while distinguishing unresolved
communication requirements.

Actual native-protocol sequence:

1. `search_requirements` retrieves `REQ-ETH-002` from `ethernet`, version `1.0`, with its
   exact chunk, source location and ranking metadata.
2. `get_architecture_topology` returns the actual physical devices, links and components.
3. `find_physical_path` returns `gateway -> switch-core -> adas`, using `link-gateway`
   and `link-adas`, with their attributes and physical-only limitations.
4. `validate_architecture` returns **11 unchanged deterministic findings: nine PASS and
   two NOT_EVALUATED**. The latter are `REQ-ISO-001` (unsupported VLAN/forwarding policy
   analysis) and `REQ-TEXT-001` (free-text requirement without a supported constraint).
5. Final generation references collected evidence; the server attaches the authoritative
   findings, source citation, two unresolved checks and ten metadata trace events.

The response is `INSUFFICIENT_EVIDENCE`, not overall design approval. It took five
scripted model rounds and four tool calls. The documented communication prose is not
silently promoted into a reviewed structured constraint. Physical connectivity does not
establish VLAN, IP, SOME/IP, TSN or service reachability.

The complete inspectable response is saved as
[phase3-workflow-scripted.json](phase3-workflow-scripted.json). A separate API integration
test exercises the actual compatible HTTP adapter with mocked native replies and real
retrieval/path/validation services. Neither demonstration is labeled as a live model run.

The evaluation also executes a 100 Mbps camera link with an explicitly routed 105 Mbps
demand: the original `bandwidth.nominal_link_budget` FAIL, affected link/components,
`REQ-BW-001` and demand evidence remain intact. Missing routes/demand produce original
NOT_EVALUATED findings and unresolved checks rather than generated estimates.

## Test Results

Commands below were actually executed from the repository. The tool binary was
`/tmp/ee-arch-uv/bin/uv` (0.13.7), with `UV_CACHE_DIR=/tmp/ee-arch-uv-cache` and, for sync,
`UV_PYTHON_INSTALL_DIR=/tmp/ee-arch-python`, `UV_LINK_MODE=copy`. `PYTHONPATH` was removed
to avoid shell-injected ROS pytest plugins. Python was 3.12.16.

| Executed command | Final outcome |
| --- | --- |
| `uv sync --locked --all-groups --offline` | PASS; 110 packages resolved, 108 checked; no lockfile/dependency changes |
| `uv run --no-sync ruff check .` | PASS |
| `uv run --no-sync ruff format --check .` | PASS; 119 files already formatted |
| `uv run --no-sync mypy` | PASS; 98 source/test files checked with strict configuration |
| `uv run --no-sync pytest --junitxml=/tmp/phase3-tests.xml` | PASS; **351 tests**, no warnings, 16.26 seconds; **98.57%** combined coverage, original 90% gate passed |
| `uv run --no-sync python -m ee_arch_copilot.agent.evaluation --output docs/reviews/phase3-agent-evaluation-scripted.json --demo-output docs/reviews/phase3-workflow-scripted.json` | PASS; all 24 expected outcomes; artifacts saved |
| `uv build --offline` | PASS; source archive and wheel built as version 0.1.0 |
| `git diff --check` | PASS |

The suite includes **108 new agent tests and all 243 existing regression tests**.
Coverage includes typed registration/schemas/results, actual adapters, parallel/disconnected
paths, request isolation, multiple calls and correlation, unknown/malformed calls,
denied scopes, source freshness, all engineering statuses, output repair, citation
validation, injection, invalid arguments, limits/timeouts/cancellation, actual retrieval
embedding/vector failures, native mocked HTTP, REST/OpenAPI errors, usage/cost and safe logs.
The evaluation scorer is tested against deliberately corrupted sources/paths/statuses.
No earlier tests or coverage thresholds were weakened.

Execution environment notes: the default uv cache was read-only and one prior temporary
cache lacked an offline build dependency; using the populated allowed `/tmp` cache
resolved synchronization. Sandboxed asynchronous thread wakeups reproduced the known
Phase 1/2 shutdown stall. Tests and asynchronous evaluation ran through the execution
tool's approved outside-sandbox mechanism. These runs remained offline with temporary
synthetic stores. No remote CI run, local Python 3.13 run or container runtime validation
is claimed; the existing CI matrix retains 3.12/3.13 and adds offline agent evaluation.

## Agent Evaluation

The independent 24-task dataset covers all requested scenarios A–J plus additional
topology/context cases. Gold outcomes are separate from protocol scripts. Accepted
tool sets ignore order and permit valid discovery alternatives. Evidence is checked
against current source records and freshly computed deterministic oracles.

| Metric | Measured offline result |
| --- | --- |
| Expected task/control outcomes | **24/24 (100%)** |
| Tool selection accuracy | **21/24 (87.50%)** |
| Tool argument validity | **28/32 (87.50%)** |
| Evidence integrity | **24/24 (100%)** |
| Engineering status preservation | **6/6 applicable cases (100%)** |
| Average model iterations | 2.3333 |
| Average admitted tool calls | 1.3333 |
| Average local scripted latency | 3.6595 ms in the saved run; machine/cache dependent |
| Provider tokens / estimated cost | Unavailable; null |

The three intentional selection errors are a validation attempt without architecture
and two unknown-tool attempts. The four invalid argument/tool attempts include unknown
tools, malformed arguments and an unknown endpoint. Correct rejection completes those
control scenarios without recasting model errors as correct selections. A valid empty
evidence response is not a fabricated engineering success. Cases without returned
validation evidence are excluded from status-preservation scoring; missing required
checks still fail task completion.

See [raw evaluation](phase3-agent-evaluation-scripted.json) and
[metric definitions/live commands](../agent-evaluation.md). Scripted protocol/control
metrics do not measure real LLM reasoning or selection quality. The optional `--live`
command uses separately labeled output and 17 applicable positive/missing/conflict tasks,
excluding forced scripted attack/protocol/budget replies. **No live result was produced.**

## Security Assessment

Application controls include explicit read-only registration, strict typed arguments and
results, request-bound architecture access, server-enforced document scope intersection,
streamed request limits, argument/context/result/provider response limits, call/iteration
and timeout budgets, exact call-ID correlation and safe error codes. Model arguments
cannot select arbitrary files, URLs, Python functions, shell commands, databases or
architecture identifiers. No write callback is registered.

Retrieved documents/tool payloads are lower-trust data. They cannot register tools,
increase limits or supply authoritative validation objects. Collected evidence is
staged and committed only after disclosure-size checks. Model references must resolve
within the current run; source revisions are checked again before return. Replaced,
deleted or uncheckable sources withhold requirement citations and generated prose,
preserving independent deterministic evidence and disclosing the freshness issue.

Structured tracing records metadata only. Prompts, full documents, architecture payloads,
credentials and raw provider/storage errors are excluded from logs. Generated exact
prompt echoes and configured credential strings are rejected as bounded safeguards.
Tokens/cost remain null when usage or explicit pricing is unavailable. HTTP provider
URLs are administrator-controlled, HTTP(S)-validated and redirect-disabled.

Remaining limits: no production authentication, tenant isolation, global rate limiting,
distributed source transaction or forcibly terminated synchronous worker. A timed-out
read may finish in a thread, but its late result is not committed. English claim/ID/conflict
checks are bounded heuristics; general semantic faithfulness, arbitrary identifier
grammars, multilingual interpretation and prompt-injection resistance beyond controlled
permissions are not proven. A malicious source may influence interpretations or choices
among approved reads. This implementation does not certify safety or compliance.

## Phase 1/2 Regression

All **108 Phase 1 tests** and **135 Phase 2 tests** passed in the final full run.
The Phase 1 domain models, topology algorithms, validator rules and original architecture
routes are unchanged. The Phase 2 ingestion, retrieval, source catalog, citation logic,
answer generation and existing knowledge routes retain their contracts.

Shared integration changes are additive settings, the new router/app provider injection,
streamed body-limit coverage for agent routes and an asynchronous HTTP helper alongside
the original synchronous helper. `pyproject.toml`, `uv.lock`, existing synthetic corpus,
retrieval evaluation labels and earlier verification artifacts were not changed.

## Known Limitations

- Real provider behavior/tool-selection quality is NOT VERIFIED; configure and review a
  real combined run before claiming full live acceptance.
- Retrieval remains the existing hash-embedding baseline by default. Learned semantic
  retrieval quality and real generation faithfulness remain separate verification work.
- Physical paths are representative adjacency only; no VLAN/forwarding, IP, SOME/IP,
  TSN scheduling, protocol translation, latency, safety or cybersecurity certification.
- Nominal budgets use declared traffic/routes and existing assumptions; no inferred routes,
  overhead, background traffic, multicast, arbitration or guaranteed throughput.
- Retrieved prose is not converted into approved structured constraints, and equal IDs do
  not establish applicability or requirement satisfaction.
- Large tool results can be rejected or topology explicitly truncated. No validation or
  topology pagination, streaming responses, background jobs or durable conversations.
- Provenance/reference integrity is not natural-language entailment. Output guards and
  numeric-template conflict detection remain bounded; interpretations need review.
- Local index/access/concurrency limits remain appropriate to a proof of concept, not a
  multi-tenant production service. Architecture writes and automatic approval are absent.

## Phase 4 Readiness

The structured response, exact deterministic findings, source citations, execution IDs,
unresolved checks and local metrics provide usable inputs for reviewed architecture
reports and more advanced evaluation. Readiness is conditional on real-provider quality
verification and explicit reporting of unsupported constraints. No Phase 4 report engine,
architecture modification workflow or automatic design-approval capability was implemented.

## Recommended Next Steps

1. Configure a real function-calling provider, execute the separately labeled live combined
   workflow/evaluation, and inspect selection, argument validity, source relevance and claims.
2. Evaluate learned embeddings and add human-reviewed interpretation/grounding golds;
   keep semantic quality separate from deterministic protocol/control verification.
3. Build Phase 4 report rendering from immutable evidence/finding contracts, retaining
   assumptions, unresolved constraints and human review decisions.
4. Before shared/network deployment, add authentication, tenant ACLs, operational
   concurrency/rate limits and appropriate worker/source-transaction hardening.
5. Extend network models/rules only with explicit engineering semantics and evidence;
   preserve the physical/VLAN/service distinction and existing NOT_EVALUATED behavior.
