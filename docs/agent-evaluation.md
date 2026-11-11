# Agent evaluation

Phase 3 has a checked-in dataset of 24 synthetic tasks in
`data/evaluation/agent_tasks.json`. The evaluator executes the real orchestrator,
registry, hybrid retrieval, physical topology/path service and deterministic validator.
It ingests the existing synthetic corpus plus explicit conflict/injection fixtures into
a temporary index. No production source records or architecture files are modified.

## Reproduce offline

```bash
uv run --locked python -m ee_arch_copilot.agent.evaluation \
  --output /tmp/agent-evaluation-scripted.json \
  --demo-output /tmp/agent-workflow-scripted.json
uv run --locked pytest tests/agent
```

Use `env -u PYTHONPATH` on Linux/macOS if shell tooling injects ROS packages. CI runs the
full tests, unchanged 90% coverage gate and explicit offline evaluation on its configured
Python 3.12/3.13 matrix. Local verification was performed on Python 3.12.16; this does not
claim that a remote CI run or local Python 3.13 execution occurred.

`ScriptedProvider` is injected through Python, never selectable by `AGENT_PROVIDER`.
Scripts request native tool calls and receive actual correlated tool results before
returning final JSON. They do not compute engineering results or call a replacement
hardcoded application workflow. The final fixture reads server-allocated evidence labels.
Gold tool sets, expected requirements/statuses and boundary outcomes are separate from
the script factory. Scoring uses active source records and fresh deterministic service
results, rather than trusting a script's answer text. Tests deliberately corrupt citations,
paths and engineering statuses and verify that scoring rejects them.

## Coverage

| Task IDs | Scenario |
| --- | --- |
| A01–A03 | ADAS/camera bandwidth requirements and TSN source lookup; no unrelated tools |
| B01–B04 | Camera–ADAS, cross-technology physical adjacency, disconnected ECU, parallel links and alternative paths |
| C01–C02 | Declared nominal budgets and explicit 105 Mbps demand on a 100 Mbps camera link |
| D01–D02 | Missing route and missing demand; authoritative NOT_EVALUATED evidence |
| E01–E02 | Combined source retrieval, topology, physical path and validation |
| F01–F02 | Absent requirement and absent architecture; evidence/clarification limitations |
| G01–G02 | Retrieved instruction injection, fabricated outcome text and attempted unauthorized shell tool |
| H01–H03 | Unknown tool, malformed tool arguments and unknown endpoint |
| I01–I02 | Tool-call budget and iteration exhaustion |
| J01 | Two source versions/origins with conflicting bandwidth quantities |
| K01 | Physical topology inspection |

Unit/integration tests additionally exercise strict schemas, result serialization,
scope narrowing, independent concurrent contexts, batch call correlation, invalid/reused
call IDs, provider/malformed-response failures, bounded repair, timeouts/cancellation,
request/context/argument/result limits, source replacement/uncheckable freshness,
embedding/vector failures, cost/usage availability and metadata-only logging. A combined
API test runs the actual compatible provider adapter against mocked native HTTP replies.
This verifies wire integration, not a real external model.

## Metric definitions

- **Tool selection accuracy:** fraction of tasks whose set of admitted attempted tool
  names equals one of the accepted sets. Order is ignored. For physical queries, both
  path-only and discovery-then-path are accepted; combined tasks permit topology discovery
  to be omitted when IDs are already known. Extra/unrelated tools are penalized. Unknown
  names are represented as `unregistered`; deliberately injected unknown-tool attempts
  remain selection errors even though successful rejection completes the security task.
- **Tool argument validity:** total admitted attempts with valid schemas and authorized
  arguments divided by all admitted attempts. Unknown tools, malformed arguments,
  denied document scopes and unknown endpoints are invalid. Missing architecture with
  otherwise valid empty arguments is a context failure. Calls after budget exhaustion
  are not admitted, executed or included in this denominator.
- **Task completion rate:** fraction meeting the dataset's expected supported outcome,
  agent status, required retrieved IDs, deterministic rule/status outcomes, path result,
  rejection/stop reason and budgets, with valid evidence/status preservation. For negative
  tasks this means correct refusal, missing information or enforced boundary, not a
  completed engineering analysis. Missing architecture can also be handled by a clear
  no-tool clarification where the task explicitly accepts that workflow.
- **Evidence integrity:** fraction with unique, resolvable evidence identities tied to
  successful executions; source chunks/citations match the active index, validation
  evidence matches deterministic results, and physical evidence matches the topology
  service. All returned statement references must resolve. Valid empty evidence is
  allowed for a correctly disclosed negative outcome. This measures provenance,
  not semantic entailment of generated prose.
- **Engineering status preservation:** fraction of applicable cases in which every
  returned validation record and finding exactly matches the deterministic oracle and
  each collected validation record survives in the response. Cases without
  returned validation evidence are excluded; their value is null, not an invented PASS.
  Required outcomes/coverage remain separate completion checks.
- **Conclusion integrity:** fraction whose headline matches the server rendering of the
  collected evidence and whose generated findings/recommendations obey the controlled
  narrative policy. This is scored separately from reference membership and exact
  validator-oracle preservation; all three are required for task completion. Tampered
  approval and measured-latency summaries fail even with valid citations/statuses.
- **Output rejection / fallback cases:** counts of tasks with rejected final attempts or
  fallback use, respectively. A repaired task still reports its rejection. The report also
  records provider/model/protocol and execution bounds without credentials.
- **Efficiency:** arithmetic means of provider iterations, admitted tool attempts and
  end-to-end request latency. Token totals/cost remain null when usage/pricing is missing.
  The report includes usage-observed case count and all individual case outcomes.

## Measured offline baseline

See [raw scripted evaluation](reviews/phase3-agent-evaluation-scripted.json) and the
[combined workflow evidence](reviews/phase3-workflow-scripted.json).

| Metric | Observed |
| --- | --- |
| Tasks meeting expected outcomes | 24/24 (100%) |
| Tool selection accuracy | 21/24 (87.50%) |
| Tool argument validity | 28/32 (87.50%) |
| Evidence integrity | 24/24 (100%) |
| Engineering status preservation | 6/6 applicable cases (100%) |
| Average iterations | 2.33 |
| Average admitted tool calls | 1.33 |
| Tokens and cost | Not available; null |

G02/H01 intentionally request unknown tools; F02 deliberately calls validation despite
missing architecture and is also counted as a selection error. G02/H01/H02/H03 contribute invalid
arguments. Their expected rejections succeed without recasting the model errors as
correct selections. Report latency is a local scripted-protocol measurement and varies
by machine/cache state. It is not a real-model latency or reasoning-quality benchmark.
No live and scripted results are combined.

## Phase 3 remediation verification

The independent audit's D-P3-001 (contradictory approval) and D-P3-002 (invented measured
latency) are reproduced in `tests/agent/test_response_integrity.py` through the public
REST path. Additional cases cover FAIL/NOT_EVALUATED presented as PASS, all-PASS production
approval, unsupported TSN/VLAN claims, invented rules/citations, mixed results, no validation,
bounded repeated rejection, retrieved injection, contradictions in recommendations and
questions, correctly scoped PASS, valid negated compliance language and foreign-request
evidence. They assert externally visible results and compare exact findings to the real
validator. Unknown prose is withheld; the tests do not claim arbitrary semantic entailment.

The original independent I33 scenario was rerun first, then all 33 original gold outcomes
were rerun unchanged: **33/33 passed**, compared with **32/33** before remediation.
Supplementary runs passed **35/35 boundaries**, **14/14 provenance/context/API** and
**3/3 controlled-clock** checks. The existing scripted evaluator still passes **24/24**,
with **24/24 conclusion integrity**. Detailed measured results, the pre-fix failures and
reproducibility evidence are in the [remediation report](reviews/phase3-remediation-report.md)
and [evidence record](reviews/phase3-remediation-evidence.json).

## Optional live evaluation

Configure a compatible function-calling/JSON-output model with `AGENT_PROVIDER`,
`AGENT_MODEL` (or `LLM_MODEL`), `LLM_BASE_URL` and any required `LLM_API_KEY`, then run:

```bash
uv run --locked python -m ee_arch_copilot.agent.evaluation --live \
  --output /tmp/agent-evaluation-live.json \
  --demo-output /tmp/agent-workflow-live.json
```

This explicitly enables provider calls and may incur costs. It uses an isolated hash
embedding index and the same outcome checks on 17 positive/missing-evidence/conflict
tasks. Seven scripted injection/invalid-protocol/budget cases are excluded because the
live model is not receiving those forced protocol replies. Live results are labeled
`mode=live`, saved separately, and must not be compared as the same 24-case denominator.
The command exits nonzero when an expected outcome is missing. Configure both explicit
token prices only if cost estimates for that configured model are desired.
The existing per-task iteration/call/output-token/deadline bounds apply to all 17 tasks
and the optional demonstration reuses an already collected response. The report records
the actual model and policy bounds plus tokens and estimated cost when available.
Conclusion integrity checks enforce the application policy; they do not establish live
selection quality or general natural-language reliability.

Current environment: **live tool-calling behavior NOT VERIFIED**. The initial verification
had no configured provider/model/credential. A later `gpt-6.1-terra` configuration passed
model metadata access, but generation returned OpenAI HTTP 429 `credit_balance_exhausted`.
See the [provider connectivity follow-up](reviews/agent-provider-connectivity-report.md).
Scripted evaluation and mock HTTP tests do not
establish actual LLM tool-selection quality, source sufficiency or interpretation
faithfulness. Before full end-to-end acceptance, run the combined workflow against a
real configured provider and review its findings, source relevance, unsupported
claims, boundaries and unresolved constraints separately.
