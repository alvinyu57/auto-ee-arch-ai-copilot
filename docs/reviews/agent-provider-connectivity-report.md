# Agent provider connectivity follow-up

Date: 2026-11-11. This follows the initial [Phase 3 report](phase3-implementation-report.md).

## Diagnosis

The running development server returned configuration HTTP 503, while a fresh
`Settings()` from the same repository loaded `.env` and initialized its provider
successfully. The process working directory was correct and it had no exported
provider/model overrides. The application had retained its startup configuration;
dotenv edits alone do not normally trigger Uvicorn's Python-file reloader.

After a Python reload, a deliberately over-budget configuration probe returned the
expected HTTP 422 from execution-policy validation instead of the configuration 503.
This probe cannot invoke a model.

The configured model is `gpt-6.1-terra`. Its
[official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-terra)
requires Responses API tool calling; the original adapter only implemented Chat
Completions. A read-only model-metadata request returned HTTP 200 with the expected ID.

The live generation diagnostic reached `/v1/responses` and returned:

```json
{
  "http_status": 429,
  "error_code": "credit_balance_exhausted",
  "error_type": "insufficient_quota"
}
```

This remaining blocker requires API credits for the organization associated with the
key. The [official error guide](https://developers.openai.com/api/docs/guides/error-codes)
distinguishes exhausted credits from temporary request throttling; retrying does not
restore a credit balance. Successful real-model tool orchestration remains NOT VERIFIED.
No account billing changes were made. Credentials and the chosen model were preserved.

## Changes

- Added `AGENT_API_MODE=auto|responses|chat_completions`. Auto uses Responses for the
  official OpenAI host and preserves Chat Completions for other compatible endpoints.
- Responses uses native function calls/results, strict final JSON Schema, output-token
  bounds and stateless native-output replay, including encrypted reasoning in order.
- Added allowlisted upstream error codes and HTTP status to agent execution metadata;
  raw provider messages, credentials and arbitrary error codes remain withheld.
- Configuration 503 errors now retain the safe configuration-specific explanation.
- Documented startup dotenv loading, restart requirements and environment precedence.
- Isolated all unit tests from developer `.env` files and exported credentials.

## Verification

Executed from the repository with `PYTHONPATH` cleared for pytest:

| Command | Result |
| --- | --- |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/ruff format --check .` | PASS |
| `.venv/bin/mypy` | PASS; 100 source/test files |
| `.venv/bin/pytest --junitxml=/tmp/agent-responses-regressions.xml` | **379 passed**, no warnings, **98.64%** combined coverage; existing 90% gate retained |
| `.venv/bin/python -m ee_arch_copilot.agent.evaluation --output /tmp/agent-responses-evaluation-scripted.json` | **24/24 expected offline outcomes**, unchanged selection/argument metrics |
| `UV_CACHE_DIR=/tmp/ee-arch-uv-cache /tmp/ee-arch-uv/bin/uv build --offline` | PASS; source archive and wheel |
| `git diff --check` | PASS |

The 28 added tests cover Responses parsing, mode selection/overrides, multiple calls,
call-ID correlation, encrypted reasoning replay, malformed output, unknown tool specs,
full mocked API orchestration and safe credit/authentication error reporting. All
existing Phase 1/2/3 regressions pass. Mocked success is not live model verification.

After funding API credits, restart the server if `.env` changed and rerun the original
combined request. Request-scoped read-only tools and deterministic validation authority
are unchanged.
