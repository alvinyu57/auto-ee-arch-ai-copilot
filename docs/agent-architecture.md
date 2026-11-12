# Phase 3 agent architecture

The application uses one request-scoped LLM orchestration loop with four explicitly
registered read-only tools. It reuses the deterministic Phase 1 services and the Phase 2
hybrid retrieval pipeline. There are no independent agents, agent frameworks, additional
provider SDKs, write tools, persistent conversations or background jobs.

```mermaid
flowchart TD
    Request[Validated question and optional full Architecture] --> Context[Owned request snapshot]
    Context --> Loop[Bounded native tool-calling loop]
    Loop <--> Provider[Configured compatible LLM or injected test provider]
    Loop --> Registry[Explicit typed read-only registry]
    Registry --> RAG[KnowledgeService.search: hybrid retrieval]
    Registry --> Topology[TopologyService: physical graph and path]
    Registry --> Validator[ArchitectureValidator: original engineering findings]
    Registry --> Evidence[Server-owned evidence IDs and provenance]
    Evidence --> Guard[Schema, reference, controlled narrative and freshness checks]
    Guard --> Summary[Server-rendered status and scope summary]
    Summary --> Response[Exact findings, review templates, citations and integrity metadata]
```

## Integration and authority

`agent/tools/adapters.py` is the only engineering integration layer. It calls Python
services directly. It does not duplicate graph algorithms, traffic assignment, budget
calculations, retrieval fusion, citation construction or conflict detection. The Phase 1
domain, validator and topology service retain their existing semantics. The existing
compatible-provider HTTP boundary gains a cancellable, response-bounded asynchronous
variant; the Phase 2 synchronous provider remains compatible.

`ModelFinal` retains its wire schema: a summary, labeled interpretations/assumptions,
recommendations, unresolved questions and an insufficient-evidence flag. It has no
validation object, status, source metadata or requirement-ID fields. The server copies
each collected `ValidationFinding` into `AgentFinding.validation` with its exact rule ID,
requirement ID, severity, PASS/FAIL/NOT_EVALUATED status, components, explanation and
evidence. It attaches these findings even when generation fails. Generated findings
have `interpretation_status=unverified`; server-copied validation entries use
`not_applicable` for that interpretation label.

The independent audit found that generated summaries bypassed the old English claim
patterns: D-P3-001 returned an overall approval beside real FAIL findings; D-P3-002
returned a fabricated latency measurement with only topology evidence. Structured
statuses were preserved in both cases. Bare summary text and phrase matching were the
root cause, rather than corruption of deterministic tools.

`EngineeringResponseVerifier` now owns the narrative contract on the actual orchestrator
and REST path. It checks references using the request-local `EvidenceStore` and admits
only exact controlled review templates. It does not classify arbitrary prose as true.
The public summary is always rendered server-side from committed validation findings,
with PASS/FAIL/NOT_EVALUATED counts, selected-scope omissions, physical/retrieval scope,
missing VLAN/TSN/latency analysis and the Phase 3 prohibition on architecture approval.
The model's summary is never copied to the public summary, including during recovery.

| Layer | Enforced boundary |
| --- | --- |
| Schema | Strict `ModelFinal`; generated validation/status/finding-ID/source fields are rejected |
| References | Current-request E labels; scoped requirement IDs; exact server-built citations |
| Deterministic findings | Original rule, status, finding identity, components and evidence copied by the server; the LLM cannot supply replacements |
| Conclusions | Server counts and scope; no autonomous approval, certification or production release |
| Narrative | Exact review templates in `agent/integrity.py`; arbitrary assertions are rejected in summary, findings, recommendations and questions |

The normal model summary template is “Collected engineering evidence is available for
review.” Findings use “Review source and computation evidence within its scope.”
Recommendations use “Review unsupported constraints and supply missing inputs.” The only
model clarification template is “Which source documents or architecture should be
supplied?” Lists may be empty. Findings must be interpretations with real references;
recommendations retain their recommendation label. Free-form assumptions and explanations
remain expressible by the wire schema for compatibility, but are withheld by this policy.
This deliberately narrows generated prose to enforce the integrity contract. The original
tool evidence and validator explanations remain available for engineering review.

Two additional exact summary inputs have deterministic preconditions: “All executed checks
passed; additional engineering validation may be required.” requires nonempty all-PASS
findings and all executed validation reports PASS. “The architecture is not compliant
because the bandwidth check failed.” requires an actual nominal-link-budget FAIL.
Neither input is copied into the headline. Other wording, even benign paraphrases, needs
repair; this is a controlled vocabulary, not keyword-based semantic verification.

On rejection, record a safe category and `integrity` trace event, allow one repair within
existing budgets, then return a server-rendered fallback with exact findings, valid
citations, limitations and unresolved checks. It is PARTIAL after useful tool execution,
or FAILED before useful execution. A successful repair can be COMPLETED while preserving
its rejection history. `evidence_integrity` exposes summary authority, narrative policy,
`approval=NOT_AUTHORIZED`, rejected attempt count, categories and fallback use. Rejected
prose is absent from responses and logs. No additional tool or verifier-model call is made.

Execution COMPLETED and individual rule PASS are distinct from full coverage and design
approval. FAIL never becomes PASS; NOT_EVALUATED always remains unresolved; retrieval and
physical adjacency do not establish compliance. Source truth, engineering applicability,
model tool selection and completeness of requested coverage still require human review.
The policy does not establish arbitrary natural-language factual correctness or certify
functional safety. See the [remediation report](reviews/phase3-remediation-report.md).

## Tool contracts

Every definition includes a unique name, description, Pydantic input/result types,
positive execution timeout and read-only classification. Duplicate names and write
definitions are rejected. Only explicit registrations are exposed as native function
definitions. No reflection, dynamic imports, eval, shell or HTTP endpoint dispatch is used.
Pydantic rejects extra arguments and validates tool JSON in strict mode. Provider
schemas set `strict=false`: optional defaults are accepted across compatible servers,
while the application performs its own strict validation.

| Tool | Input | Typed result and scope |
| --- | --- | --- |
| `search_requirements` | `query` (1–5000 characters), `top_k` (integer 1–10, default 5), optional `filters` with document ID, version or requirement ID | Phase 2 `SearchResponse`: exact IDs, versions, chunk/source locations, text, ranks, methods and ranking metadata; always hybrid, never answer generation |
| `get_architecture_topology` | `max_nodes`, `max_links` (integers 1–100, default 50 each) | Physical topology, node names/kinds, endpoint/link attributes, isolated nodes, connected components, original counts and explicit truncation flag |
| `find_physical_path` | Exact `source_device_id`, `destination_device_id` | Physical path existence, ordered nodes and link IDs, ordered link attributes, original physical limitations and representative-route warning |
| `validate_architecture` | Optional nonempty `rule_ids`, restricted to the five existing rule IDs | Existing validator report, exact selected findings, original overall report status, scope note and number of omitted findings |

Available rules are `structure.consistency`, `connectivity.physical_path`,
`bandwidth.traffic_evaluability`, `bandwidth.nominal_link_budget` and
`requirement.evaluability`. A rule filter limits the returned findings, not the
calculation or original report status. A PASS for one rule is never overall compliance.
Successful validation executions also expose `tool_executions[].validation_scope` with
architecture ID, original full-report status/scope, selected rules and omitted-finding
count. Filtered omissions are repeated in response limitations. These fields come from
the actual validator result, even when omitted findings are outside the selected scope.

Unknown endpoints are errors. Disconnected known endpoints produce `exists=false`.
The path service chooses a minimum-hop physical path and one lexicographically selected
parallel link per hop. Alternative paths can exist; the result never assigns service
traffic. Physical adjacency does not prove VLAN forwarding, IP routing, SOME/IP, TSN,
protocol translation or application reachability.

Topology output that omits nodes or links is explicitly truncated; component lists
are withheld rather than representing incomplete components as complete. Such execution
returns PARTIAL. Oversized results are rejected intact, with no evidence committed from
that result. Validation findings are never clipped or converted to generated estimates.
The model may retry with a supported narrower rule/query scope. Very large architectures
can remain incomplete; there is no topology/validation pagination in this MVP.

## Request context and access

`AnalyzeRequest.architecture` uses the complete existing Phase 1 `Architecture` model.
It is optional for retrieval-only questions. The application copies and revalidates the
submitted model, then binds adapters to that snapshot. Model arguments contain no file
paths, URLs or selectable architecture IDs. There is no sample-ID resolver; send the full
sample JSON. The initial prompt contains only the question, architecture-availability
flag and description of the current-request handle. Device details are disclosed through
tools. Concurrent requests have separate snapshots, evidence stores and histories.

Server code may inject an `AgentContext.document_scope` using the existing Phase 2
`SearchFilter`. Model filters must agree with every enforced scope field; omitted fields
inherit the scope and conflicting values are denied before retrieval. HTTP clients cannot
set the server scope. The deployed MVP inherits Phase 2's local single-user index and has
no authentication or tenant ACLs. A scope mechanism is not a complete authorization system.
Only `KnowledgeService.search` is exposed: ingestion, reindex, replacement and deletion
are unavailable to the model. Phase 2 service/index provisioning retains its existing
lazy initialization behavior; analysis does not write architecture or source records.

## Orchestration and failure behavior

1. Build a request snapshot, policy, trace and registry.
2. Send the role/policy, final-output schema, question and native tool definitions.
3. Check the total serialized context size before each provider call.
4. Parse tool calls, reject malformed protocol/duplicate call IDs, enforce the total budget.
5. Validate each tool's JSON arguments and execute through the registry.
6. Validate and size-check results, stage evidence, size-check the complete wire envelope,
   and commit evidence only if the result will actually be disclosed.
7. Return one native tool message per admitted call, correlated with `tool_call_id`.
8. Validate final JSON, current-run references and controlled narrative; allow one repair.
9. Recheck retrieved source revisions, copy deterministic findings and render the summary
   from committed evidence even if final generation failed.

Multiple calls in one model response execute sequentially. Admitted attempts consume the
budget even when arguments are invalid or the tool is denied. No further call executes
after exhaustion. Unknown tools, malformed arguments, missing architectures/endpoints,
storage or embedding errors, timeouts and oversized results return safe error codes.
Unrelated successful evidence survives. Provider failures stop the loop. Cancellation
propagates to the asynchronous provider and caller. Unexpected provider/tool exceptions
are sanitized; raw error strings never appear in traces or responses.

`asyncio.wait_for` bounds caller waits. Existing synchronous engineering/storage work
runs in a thread. Python cannot forcibly terminate an already running thread; a timed-out
read may finish in the background. Its late result is never committed. The standard
executor bounds active threads, but production concurrency/rate limiting and process
isolation for pathological CPU/storage work belong to later hardening.

## Evidence and provenance

Evidence labels (`E1`, `E2`, …) are allocated only by the server. Retrieval records retain
document ID/version, chunk ID, requirement ID, source location, original chunk and ranking
data. Identical chunks deduplicate even if a repeated query changes rank. Distinct
validator executions retain execution ID, finding ID, rule ID and component IDs. Path and
topology records contain actual typed tool results. Native result envelopes map evidence
labels to result indexes; the model cannot create new evidence objects.

Every generated statement's reference list must resolve within this execution.
Interpretations require a reference; assumptions and recommendations may explicitly
lack one. Requirement IDs mentioned within a statement must belong to its referenced
evidence, subject to the documented bounded identifier grammar. Citation objects are
constructed with the existing Phase 2 citation function, never model metadata.

Source revisions are captured under the existing store lock during search and rechecked
before returning. Replaced/deleted or uncheckable sources cause requirement citations
and generated prose to be withheld, while independent validation evidence remains.
The response discloses the freshness issue. The check is not a cross-process transaction
or a guarantee against changes after response generation. Equal statement templates
with different quantities reuse Phase 2's bounded conflict detector: both sources stay
traceable and the response requests an engineer's applicability/precedence decision.

## API and status semantics

`POST /api/v1/agent/analyze` is a single request/response operation documented in OpenAPI.
It accepts `question`, optional full `architecture`, and optional `options` with lower
iteration/call limits and `include_trace`. Requests cannot increase server limits.
The existing streaming body middleware limits bytes before JSON parsing for knowledge
and agent routes, including chunked requests.

| Agent status | Meaning |
| --- | --- |
| `COMPLETED` | Valid final response and supporting tool evidence, without execution errors or collected unresolved evaluations; does not imply design PASS |
| `INSUFFICIENT_EVIDENCE` | Execution finished but evidence is absent, model flags insufficiency, sources conflict, or collected validation findings include NOT_EVALUATED |
| `PARTIAL` | Execution was limited, a tool failed, topology was truncated, sources expired/could not be checked, or generation failed after useful execution |
| `FAILED` | Execution deadline expired or an unrecoverable provider, protocol or final-output error occurred before useful tool execution/evidence |

HTTP 200 carries completed, insufficient or partial analysis, including real engineering
FAIL findings. Input errors/raised request limits return 422, excessive bodies 413 and
missing/invalid provider configuration 503. Provider/protocol/final-output failures
without usable execution return a structured FAILED response with 502. Expiry of the
end-to-end execution deadline before usable execution returns FAILED with 504, including
expiry during request setup or while waiting for the provider. Partial results retain
HTTP 200 and explicit failed checks.

## Configuration and observability

The defaults and validated ranges are defined in `core/settings.py` and `.env.example`.
`AGENT_PROVIDER=none` disables production analysis until configured; `openai_compatible`
uses `AGENT_MODEL` with `LLM_MODEL` fallback and existing `LLM_BASE_URL`, `LLM_API_KEY` and
`PROVIDER_TIMEOUT_SECONDS`. URLs must be trusted HTTP(S) endpoints without embedded
credentials. No API keys are sent to the LLM as prompt content. HTTP redirects are disabled.
`AGENT_API_MODE=auto` selects `/responses` for the official `api.openai.com` host and
`/chat/completions` for other compatible endpoints. Explicit `responses` and
`chat_completions` values support proxies with either dialect. The Responses path uses
flat function definitions, strict final JSON Schema, `max_output_tokens`, and native
`function_call_output` items correlated by `call_id`. With `store=false`, native output
items, including encrypted reasoning and assistant phase metadata, are replayed in their
original order on subsequent calls. They remain internal to the bounded request history
and are not returned in response evidence or logs. The adapter has no shared conversation
cache, preserving request isolation. See [OpenAI reasoning continuation](https://developers.openai.com/api/docs/guides/reasoning).

The Chat Completions path retains `response_format=json_object` and `max_tokens` for
compatible local/third-party servers. Models such as
[`gpt-6.1-terra`](https://developers.openai.com/api/docs/models/gpt-6.1-terra) require Responses
for tool calling. Both modes use the same registry, policies, HTTP size/time limits,
credentials and token accounting. Phase 2 generation retains its existing separate
configuration. Restart the application after changing `.env`: settings are loaded at
startup relative to the working directory; Python reload watching does not normally
include dotenv files. Exported shell values override the file. No dotenv content or
secret values are included in configuration errors.

| Policy setting | Default | Trade-off |
| --- | --- | --- |
| `AGENT_API_MODE` | auto | Responses for official OpenAI; Chat Completions elsewhere, with explicit overrides for proxies |
| `AGENT_MAX_ITERATIONS` | 6 | More rounds permit discovery/refinement but increase latency and cost; output repair also consumes rounds |
| `AGENT_MAX_TOOL_CALLS` | 10 | Includes denied/invalid admitted calls; higher values permit more reads |
| `AGENT_TIMEOUT_SECONDS` | 60 | End-to-end caller deadline, including source recheck |
| `AGENT_TOOL_TIMEOUT_SECONDS` | 10 | Per-call wait, capped by remaining request time |
| `AGENT_MAX_TOOL_RESULT_BYTES` | 16384 | Complete JSON envelope limit; smaller values can reject otherwise valid large findings |
| `AGENT_MAX_ARGUMENT_BYTES` | 4096 | Bound individual argument JSON |
| `AGENT_MAX_CONTEXT_BYTES` | 131072 | Bound complete serialized messages and tool schemas; bytes are not tokenizer-specific tokens |
| `AGENT_MAX_PROVIDER_RESPONSE_BYTES` | 262144 | Bounded HTTP/model response parsing |
| `AGENT_MAX_OUTPUT_TOKENS` | 2000 | Provider output budget each round |
| `AGENT_ENABLE_TRACING` | true | Allows metadata-only logs and requested response traces |
| `MAX_REQUEST_BYTES` | 1100000 | Existing streamed request-body cap |

Traces include request/trace IDs, iterations, tool name/call ID, duration, execution
status, provider durations and token usage when available. Tool executions are always
in the response; `options.include_trace=true` includes detailed events when tracing is
enabled. The `ee_arch_copilot.agent.trace` Python logger emits structured `agent_trace`
metadata through logging `extra`; configure an application JSON formatter if desired.
There is no persistent trace store. Prompts, arguments, architecture payloads, document
contents, API keys and raw provider errors are excluded from logs. Exact prompt echoes
and configured credential strings in generated text are rejected as a bounded safeguard.

Token totals are null unless every LLM iteration reports usage. Cost is null unless
complete usage and both explicit USD-per-million input/output prices are configured.
Prices are administrator-provided estimates; there is no built-in price table or claim
of exact billing. Tracing can be disabled independently of usage aggregation.

`execution_metadata.provider_http_status` and `provider_error_code` preserve safe upstream
diagnostics for failed model calls. Only allowlisted codes (such as
`credit_balance_exhausted`, `insufficient_quota`, `model_not_found` and rate/spend-limit
codes) are returned; provider messages, prompts, body fields and arbitrary codes are
withheld. The async HTTP helper bounds error bodies before reading their code. A failed
upstream call still produces the existing FAILED/PARTIAL agent status and 502/200 HTTP
contract, with the original upstream status available separately in metadata.

## Security limits and Phase 4 extension points

The tool allowlist, typed arguments, request scope, enforced limits and server-owned
provenance are application controls; prompt-injection resistance does not rest on
instructions alone. A malicious document may still influence the model's choice among
approved reads. Arbitrary generated prose is withheld regardless of language, rather
than semantically verified. Arbitrary identifier grammars, source truth, engineering
applicability, completeness and general conflict reasoning remain unproven.
The MVP has no production authentication, tenant isolation, global rate limiting or
isolated worker termination. Keep proprietary sources within approved provider/data
handling boundaries. This assistant does not certify functional safety or compliance.

Phase 4 can consume `AgentResponse`, exact validator findings and evidence provenance
to render reviewed reports and measure interpretation quality. No report generator,
architecture mutation workflow, automatic approval, multi-agent system or new network
verification engine is implemented as part of Phase 3.
