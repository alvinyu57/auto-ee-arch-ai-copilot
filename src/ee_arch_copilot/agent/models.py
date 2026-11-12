"""Public response contracts and the smaller, non-authoritative model output contract."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.domain.models.common import DomainModel
from ee_arch_copilot.rag.models import Citation
from ee_arch_copilot.services.validator import FindingStatus, ValidationFinding

Text = Annotated[str, Field(min_length=1, max_length=5000)]
Reference = Annotated[str, Field(pattern=r"^E[1-9][0-9]{0,5}$")]
AgentStatus = Literal["COMPLETED", "PARTIAL", "INSUFFICIENT_EVIDENCE", "FAILED"]
ToolStatus = Literal["SUCCEEDED", "REJECTED", "ERROR", "TIMEOUT", "LIMIT"]


class AgentOptions(DomainModel):
    max_iterations: int | None = Field(default=None, ge=1, le=20, strict=True)
    max_tool_calls: int | None = Field(default=None, ge=1, le=50, strict=True)
    include_trace: bool = False


class AnalyzeRequest(DomainModel):
    question: Text
    architecture: Architecture | None = None
    options: AgentOptions = Field(default_factory=AgentOptions)


class GeneratedStatement(DomainModel):
    description: Text
    finding_type: Literal["interpretation", "recommendation", "assumption"]
    evidence_references: list[Reference] = Field(max_length=100)


class ModelFinal(DomainModel):
    # No statuses, requirement IDs, source metadata, or validation objects from the LLM.
    summary: Text
    findings: list[GeneratedStatement] = Field(max_length=50)
    recommendations: list[GeneratedStatement] = Field(max_length=30)
    unresolved_questions: list[Text] = Field(max_length=30)
    insufficient_evidence: bool


class EvidenceRecord(DomainModel):
    evidence_id: str
    kind: Literal["requirement", "validation", "topology", "physical_path"]
    execution_id: str
    source_index: int
    document_id: str | None = None
    document_version: str | None = None
    chunk_id: str | None = None
    requirement_id: str | None = None
    rule_id: str | None = None
    finding_id: str | None = None
    component_ids: list[str] = Field(default_factory=list)
    data: dict[str, JsonValue]


class AgentFinding(DomainModel):
    finding_id: str
    description: str
    finding_type: Literal["validation", "interpretation", "recommendation", "assumption"]
    severity: str
    requirement_ids: list[str]
    validation_rule_ids: list[str]
    evidence_references: list[str]
    # This field is populated by the server from the original validator, never from ModelFinal.
    validation: ValidationFinding | None = None
    interpretation_status: Literal["unverified", "not_applicable"] = "unverified"


class ValidationScope(DomainModel):
    architecture_id: str
    original_report_status: FindingStatus
    scope: str
    selected_rule_ids: list[str] | None
    omitted_findings: int


class ToolExecution(DomainModel):
    execution_id: str
    tool_call_id: str
    tool_name: str
    status: ToolStatus
    duration_ms: float
    arguments_valid: bool = False
    error_code: str | None = None
    result_bytes: int = 0
    validation_scope: ValidationScope | None = None


class TraceEvent(DomainModel):
    request_id: str
    trace_id: str
    event: Literal["llm", "tool", "integrity", "final"]
    iteration: int
    duration_ms: float
    status: str
    tool_name: str | None = None
    tool_call_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class ExecutionMetadata(DomainModel):
    trace_id: str
    provider_model: str
    iterations: int
    tool_calls: int
    duration_ms: float
    input_tokens: int | None
    output_tokens: int | None
    usage_complete: bool
    estimated_cost_usd: float | None
    stop_reason: str
    provider_error_code: str | None = None
    provider_http_status: int | None = None
    trace: list[TraceEvent] = Field(default_factory=list)


class EvidenceIntegrity(DomainModel):
    summary_authority: Literal["server"] = "server"
    narrative_policy: Literal["controlled_templates"] = "controlled_templates"
    approval: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    rejected_final_attempts: int = 0
    failure_categories: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class AgentResponse(DomainModel):
    request_id: str
    status: AgentStatus
    summary: str
    findings: list[AgentFinding]
    recommendations: list[GeneratedStatement]
    unresolved_questions: list[str]
    citations: list[Citation]
    evidence: list[EvidenceRecord]
    tool_executions: list[ToolExecution]
    execution_metadata: ExecutionMetadata
    limitations: list[str]
    evidence_integrity: EvidenceIntegrity = Field(default_factory=EvidenceIntegrity)
