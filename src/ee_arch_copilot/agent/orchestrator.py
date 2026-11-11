"""One bounded native-tool-calling loop, with server-owned engineering evidence."""

import asyncio
import json
from collections.abc import Callable
from time import monotonic

from pydantic import JsonValue, ValidationError

from ee_arch_copilot.agent.context import AgentContext
from ee_arch_copilot.agent.evidence import EvidenceStore
from ee_arch_copilot.agent.integrity import (
    UNSUPPORTED_SCOPE,
    EngineeringResponseVerifier,
    ResponseIntegrityError,
)
from ee_arch_copilot.agent.models import (
    AgentResponse,
    AgentStatus,
    AnalyzeRequest,
    EvidenceIntegrity,
    ModelFinal,
    ValidationScope,
)
from ee_arch_copilot.agent.observability import AgentTrace
from ee_arch_copilot.agent.policies import AgentPolicy
from ee_arch_copilot.agent.prompts import SYSTEM_PROMPT
from ee_arch_copilot.agent.providers import AgentProvider
from ee_arch_copilot.agent.tools.adapters import EngineeringTools, TopologyResult, ValidationResult
from ee_arch_copilot.agent.tools.registry import ToolRegistry, engineering_registry, json_bytes
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.errors import ProviderError
from ee_arch_copilot.rag.service import KnowledgeService

LIMITATIONS = [
    "Physical connectivity does not establish VLAN, IP, SOME/IP, TSN or service reachability.",
    "Validation covers only supported structured constraints and declared nominal traffic; "
    "retrieved prose is not automatically verified or converted into approved constraints.",
    "Narrative fields use controlled review templates and server-rendered status summaries. "
    "Source text and engineering applicability still require human review.",
]


class AgentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        provider: AgentProvider,
        knowledge: Callable[[], KnowledgeService],
    ) -> None:
        self.settings, self.provider, self.knowledge = settings, provider, knowledge

    async def analyze(
        self,
        request: AnalyzeRequest,
        *,
        context: AgentContext | None = None,
        registry: ToolRegistry | None = None,
    ) -> AgentResponse:
        policy = AgentPolicy.build(self.settings, request.options)
        trace = AgentTrace(self.settings)
        deadline = trace.started + policy.timeout_seconds
        context = context or AgentContext.from_request(request)
        tools = EngineeringTools(context, self.knowledge)
        registry = registry or engineering_registry(tools, policy.tool_timeout_seconds)
        specifications = registry.specifications()
        evidence = EvidenceStore()
        verifier = EngineeringResponseVerifier(evidence)
        integrity_failures: list[str] = []
        messages: list[dict[str, JsonValue]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": request.question,
                        "architecture_available": context.architecture is not None,
                        "architecture_handle": "current_request_only",
                    }
                ),
            },
        ]
        executions = []
        seen_call_ids: set[str] = set()
        final: ModelFinal | None = None
        reason, iterations, calls, invalid_finals = "iteration_limit", 0, 0, 0
        truncated = False
        provider_error: ProviderError | None = None
        for iteration in range(1, policy.max_iterations + 1):
            remaining = deadline - monotonic()
            if remaining <= 0:
                reason = "execution_timeout"
                break
            if (
                len(json_bytes({"messages": messages, "tools": specifications}))
                > policy.max_context_bytes
            ):
                reason = "context_size_limit"
                break
            iterations = iteration
            started = monotonic()
            try:
                reply = await asyncio.wait_for(
                    self.provider.complete(messages, specifications), timeout=remaining
                )
            except TimeoutError:
                reason = "provider_timeout"
                trace.record("llm", iteration, (monotonic() - started) * 1000, "TIMEOUT")
                break
            except ProviderError as error:
                provider_error, reason = error, "provider_error"
                trace.record("llm", iteration, (monotonic() - started) * 1000, "ERROR")
                break
            except Exception:
                reason = "provider_error"
                trace.record("llm", iteration, (monotonic() - started) * 1000, "ERROR")
                break
            trace.record(
                "llm", iteration, (monotonic() - started) * 1000, "SUCCEEDED", usage=reply.usage
            )
            if (
                len(json_bytes(reply.model_dump(mode="json")))
                > self.settings.agent_max_provider_response_bytes
            ):
                reason = "provider_response_size_limit"
                break
            messages.append(reply.message())
            if reply.tool_calls:
                ids = [call.id for call in reply.tool_calls]
                if len(set(ids)) != len(ids) or seen_call_ids.intersection(ids):
                    reason = "invalid_tool_call_ids"
                    break
                seen_call_ids.update(ids)
                stopped = False
                for call in reply.tool_calls:
                    if calls >= policy.max_tool_calls:
                        reason, stopped = "tool_call_limit", True
                        break
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        reason, stopped = "execution_timeout", True
                        break
                    calls += 1
                    outcome = await registry.execute(
                        call.function.name, call.function.arguments, call.id, policy, remaining
                    )
                    execution = outcome.execution
                    wire: dict[str, JsonValue] = {
                        "execution_id": execution.execution_id,
                        "status": execution.status,
                        "error_code": execution.error_code,
                    }
                    if outcome.payload is not None:
                        prepared = evidence.prepare(execution.execution_id, outcome.payload)
                        wire["data"] = outcome.payload.model_dump(mode="json")
                        wire["evidence_references"] = [
                            {
                                "evidence_id": record.evidence_id,
                                "kind": record.kind,
                                "source_index": index,
                            }
                            for index, record in enumerate(prepared)
                        ]
                        size = len(json_bytes(wire))
                        if size > policy.max_tool_result_bytes:
                            execution.status, execution.error_code = (
                                "LIMIT",
                                "tool_result_size_limit",
                            )
                            wire = {"status": "LIMIT", "error_code": execution.error_code}
                        else:
                            evidence.commit(prepared)
                            execution.result_bytes = size
                            if isinstance(outcome.payload, ValidationResult):
                                result = outcome.payload
                                execution.validation_scope = ValidationScope.model_validate(
                                    {
                                        "architecture_id": result.report.architecture_id,
                                        "original_report_status": result.report.status,
                                        "scope": result.report.scope,
                                        "selected_rule_ids": result.selected_rule_ids,
                                        "omitted_findings": result.omitted_findings,
                                    }
                                )
                            truncated |= (
                                isinstance(outcome.payload, TopologyResult)
                                and outcome.payload.truncated
                            )
                    executions.append(execution)
                    trace.record(
                        "tool",
                        iteration,
                        execution.duration_ms,
                        execution.status,
                        execution.tool_name,
                        execution.tool_call_id,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json_bytes(wire).decode(),
                        }
                    )
                if stopped:
                    break
                continue
            try:
                if reply.content is None:
                    raise ValueError("Missing final content")
                final = ModelFinal.model_validate_json(reply.content, strict=True)
                generated = " ".join(
                    " ".join(
                        [
                            final.summary,
                            *final.unresolved_questions,
                            *(
                                item.description
                                for item in [*final.findings, *final.recommendations]
                            ),
                        ]
                    ).split()
                )
                protected = " ".join(SYSTEM_PROMPT.split())
                if any(
                    protected[index : index + 100] in generated
                    for index in range(0, len(protected) - 99, 50)
                ):
                    raise ValueError("System prompt disclosure")
                for secret in (self.settings.llm_api_key, self.settings.embedding_api_key):
                    if (
                        secret
                        and secret.get_secret_value()
                        and secret.get_secret_value() in generated
                    ):
                        raise ValueError("Credential disclosure")
                verifier.validate(final, executions, self.settings.requirement_id_pattern)
            except (ValidationError, ValueError) as error:
                final = None
                invalid_finals += 1
                category = (
                    str(error) if isinstance(error, ResponseIntegrityError) else "invalid_output"
                )
                integrity_failures.append(category)
                trace.record("integrity", iteration, 0, category)
                if invalid_finals >= 2:
                    reason = "invalid_final_response"
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": f"Final response rejected ({category}). Return all required "
                        "JSON fields and only collected evidence references. Use the exact "
                        "controlled narrative templates in the system policy, or empty lists. "
                        "One repair attempt remains. Server-rendered summary: "
                        + verifier.summary(executions),
                    }
                )
                reason = "invalid_final_response"
                continue
            reason = "final_response"
            break

        # The recheck is read-only and shares the remaining end-to-end deadline.
        # If it fails, retain independent validator evidence, withhold generated prose/citations.
        freshness_issue: str | None = None
        if evidence.chunks():
            freshness_reason = "stale_evidence"
            try:
                current = await asyncio.wait_for(
                    asyncio.to_thread(tools.evidence_current), max(0, deadline - monotonic())
                )
            except Exception:
                current = False
                freshness_reason = "source_freshness_unverified"
            if not current:
                freshness_issue = freshness_reason
                evidence.records = {
                    key: value
                    for key, value in evidence.records.items()
                    if value.kind != "requirement"
                }
                final = None
                if reason == "final_response":
                    reason = freshness_reason
        errors = [execution for execution in executions if execution.status != "SUCCEEDED"]
        if reason == "final_response" and (errors or truncated):
            reason = "tool_errors" if errors else "truncated_output"
        incomplete = reason != "final_response" or bool(errors) or truncated
        conflict_refs = evidence.conflict_references()
        unevaluated = [
            record
            for record in evidence.records.values()
            if record.kind == "validation" and record.data["status"] == "NOT_EVALUATED"
        ]
        has_evidence = bool(evidence.records)
        status: AgentStatus
        if incomplete:
            terminal_failure = reason in {
                "provider_error",
                "provider_timeout",
                "invalid_tool_call_ids",
                "invalid_final_response",
            }
            status = (
                "FAILED" if terminal_failure and not has_evidence and not executions else "PARTIAL"
            )
        elif (
            not has_evidence
            or (final is not None and final.insufficient_evidence)
            or conflict_refs
            or unevaluated
        ):
            status = "INSUFFICIENT_EVIDENCE"
        else:
            status = "COMPLETED"
        questions = list(final.unresolved_questions) if final else []
        if incomplete:
            questions.append(f"Analysis incomplete: {reason}.")
        if integrity_failures:
            questions.append(
                "Model output was rejected by response integrity validation; "
                "see evidence_integrity for safe failure categories."
            )
        if provider_error and provider_error.code:
            questions.append(
                f"Model provider rejected the request: {provider_error.code} "
                f"(HTTP {provider_error.http_status})."
            )
            if provider_error.code in {"credit_balance_exhausted", "insufficient_quota"}:
                questions.append(
                    "Check API billing and credits for the organization associated with this key."
                )
        if freshness_issue:
            questions.append(f"Requirement evidence withheld: {freshness_issue}.")
        for execution in errors:
            questions.append(f"Tool {execution.tool_name}: {execution.error_code}.")
        if truncated:
            questions.append("Topology output was truncated; full components were withheld.")
        if not has_evidence:
            questions.append(
                "No supporting tool evidence was collected for the requested analysis."
            )
        if conflict_refs:
            questions.append(
                "Potential conflicting quantities in sources "
                + ", ".join(conflict_refs)
                + "; an engineer must determine applicability and precedence."
            )
        for record in unevaluated:
            questions.append(
                f"Unevaluated check {record.rule_id} [{record.evidence_id}]: "
                + str(record.data["explanation"])
            )
        summary = verifier.summary(executions)
        questions.append(UNSUPPORTED_SCOPE)
        if incomplete:
            summary = "Analysis incomplete; review unresolved checks. " + summary
        if conflict_refs:
            summary = "Potential conflicting requirements require engineering review. " + summary
        trace.record("final", iterations, (monotonic() - trace.started) * 1000, status)
        limitations = list(LIMITATIONS)
        for execution in executions:
            scope = execution.validation_scope
            if scope and scope.omitted_findings:
                limitations.append(
                    f"Validation execution {execution.execution_id} returned selected rules "
                    f"{scope.selected_rule_ids}; {scope.omitted_findings} findings were omitted. "
                    "Its original_report_status refers to the full declared-model report, "
                    "not the selected rule subset."
                )
        metadata = trace.metadata(
            self.provider.model, iterations, calls, reason, request.options.include_trace
        )
        if provider_error:
            metadata.provider_error_code = provider_error.code
            metadata.provider_http_status = provider_error.http_status
        return AgentResponse(
            request_id=trace.request_id,
            status=status,
            summary=summary,
            findings=evidence.findings(final),
            recommendations=final.recommendations if final else [],
            unresolved_questions=list(dict.fromkeys(questions)),
            citations=evidence.citations(),
            evidence=list(evidence.records.values()),
            tool_executions=executions,
            execution_metadata=metadata,
            limitations=limitations,
            evidence_integrity=EvidenceIntegrity(
                rejected_final_attempts=invalid_finals,
                failure_categories=list(dict.fromkeys(integrity_failures)),
                fallback_used=final is None,
            ),
        )
