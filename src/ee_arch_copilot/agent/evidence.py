"""Server-owned provenance and fail-closed validation of model references."""

import re

from pydantic import BaseModel

from ee_arch_copilot.agent.models import AgentFinding, EvidenceRecord, ModelFinal
from ee_arch_copilot.agent.tools.adapters import PathResult, TopologyResult, ValidationResult
from ee_arch_copilot.rag.generation.citations import citation
from ee_arch_copilot.rag.generation.guards import VERIFICATION_CLAIM, conflicting_source_indices
from ee_arch_copilot.rag.identifiers import mentioned_identifiers
from ee_arch_copilot.rag.models import Chunk, Citation, SearchResponse
from ee_arch_copilot.services.validator import ValidationFinding

# Generated prose has no authority to issue verification outcomes, even if a model has
# seen a real PASS for an unrelated rule. Exact findings are copied independently below.
VERIFICATION_LANGUAGE = re.compile(
    r"\b(?:PASS|FAIL|NOT_EVALUATED)\b|\b(?:compliant|compliance|certified|certification)\b"
    r"|\b(?:satisf(?:y|ies|ied)|passed|verified|validated)\b"
    r"|\b(?:all|every)\s+(?:architecture\s+)?checks?\s+(?:have\s+)?pass",
    re.I,
)


class EvidenceStore:
    def __init__(self) -> None:
        self.records: dict[str, EvidenceRecord] = {}

    def prepare(self, execution_id: str, payload: BaseModel) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        if isinstance(payload, SearchResponse):
            for index, hit in enumerate(payload.hits):
                chunk = hit.chunk
                records.append(
                    EvidenceRecord(
                        evidence_id="pending",
                        kind="requirement",
                        execution_id=execution_id,
                        source_index=index,
                        document_id=chunk.document_id,
                        document_version=chunk.document_version,
                        chunk_id=chunk.chunk_id,
                        requirement_id=chunk.requirement_id,
                        data=hit.model_dump(mode="json"),
                    )
                )
        elif isinstance(payload, ValidationResult):
            for index, finding in enumerate(payload.report.findings):
                records.append(
                    EvidenceRecord(
                        evidence_id="pending",
                        kind="validation",
                        execution_id=execution_id,
                        source_index=index,
                        requirement_id=finding.requirement_id,
                        rule_id=finding.rule_id,
                        finding_id=f"V-{execution_id}-{index}",
                        component_ids=list(finding.affected_components),
                        data=finding.model_dump(mode="json"),
                    )
                )
        elif isinstance(payload, PathResult | TopologyResult):
            records.append(
                EvidenceRecord(
                    evidence_id="pending",
                    kind="physical_path" if isinstance(payload, PathResult) else "topology",
                    execution_id=execution_id,
                    source_index=0,
                    data=payload.model_dump(mode="json"),
                )
            )
        # Repeated retrievals deduplicate by exact evidence identity, including source version
        # and data. Distinct validator executions retain separate execution provenance.
        prepared: list[EvidenceRecord] = []
        next_id = len(self.records) + 1
        for record in records:
            duplicate = next(
                (
                    old
                    for old in self.records.values()
                    if record.kind == old.kind == "requirement"
                    and record.data["chunk"] == old.data["chunk"]
                ),
                None,
            )
            if duplicate is not None:
                prepared.append(duplicate)
            else:
                record.evidence_id = f"E{next_id}"
                next_id += 1
                prepared.append(record)
        return prepared

    def commit(self, records: list[EvidenceRecord]) -> None:
        self.records.update((record.evidence_id, record) for record in records)

    def chunks(self) -> list[Chunk]:
        return [
            Chunk.model_validate(record.data["chunk"])
            for record in self.records.values()
            if record.kind == "requirement"
        ]

    def citations(self) -> list[Citation]:
        return [
            citation(record.evidence_id, Chunk.model_validate(record.data["chunk"]))
            for record in self.records.values()
            if record.kind == "requirement"
        ]

    def conflict_references(self) -> list[str]:
        records = [record for record in self.records.values() if record.kind == "requirement"]
        return [records[index].evidence_id for index in conflicting_source_indices(self.chunks())]

    def validate_final(self, final: ModelFinal, requirement_pattern: str) -> None:
        identifiers = {r.requirement_id for r in self.records.values() if r.requirement_id}

        def check_text(text: str, allowed_ids: set[str], allowed_refs: set[str]) -> None:
            if VERIFICATION_LANGUAGE.search(text) or VERIFICATION_CLAIM.search(text):
                raise ValueError("Generated verification claims are not accepted")
            if not mentioned_identifiers(text, requirement_pattern, identifiers) <= allowed_ids:
                raise ValueError("Unresolved requirement identifier")
            if not set(re.findall(r"\bE[1-9][0-9]*\b", text)) <= allowed_refs:
                raise ValueError("Unresolved inline evidence reference")

        check_text(final.summary, identifiers, set(self.records))
        for question in final.unresolved_questions:
            check_text(question, identifiers, set(self.records))
        for statement in [*final.findings, *final.recommendations]:
            references = set(statement.evidence_references)
            if not references <= self.records.keys():
                raise ValueError("Unresolved evidence reference")
            if statement.finding_type == "interpretation" and not references:
                raise ValueError("Interpretations require collected evidence")
            scoped_ids = {self.records[ref].requirement_id for ref in references}
            check_text(
                statement.description,
                {identifier for identifier in scoped_ids if identifier},
                references,
            )
        if any(item.finding_type != "recommendation" for item in final.recommendations):
            raise ValueError("Recommendations must be marked as recommendations")

    def findings(self, final: ModelFinal | None) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for record in self.records.values():
            if record.kind != "validation":
                continue
            validation = ValidationFinding.model_validate(record.data)
            findings.append(
                AgentFinding(
                    finding_id=record.finding_id or record.evidence_id,
                    description=validation.explanation,
                    finding_type="validation",
                    severity=validation.severity,
                    requirement_ids=[validation.requirement_id]
                    if validation.requirement_id
                    else [],
                    validation_rule_ids=[validation.rule_id],
                    evidence_references=[record.evidence_id],
                    validation=validation,
                    interpretation_status="not_applicable",
                )
            )
        for index, statement in enumerate(final.findings if final else []):
            records = [self.records[ref] for ref in statement.evidence_references]
            findings.append(
                AgentFinding(
                    finding_id=f"I{index + 1}",
                    description=statement.description,
                    finding_type=statement.finding_type,
                    severity="INFO",
                    requirement_ids=sorted({r.requirement_id for r in records if r.requirement_id}),
                    validation_rule_ids=sorted({r.rule_id for r in records if r.rule_id}),
                    evidence_references=list(dict.fromkeys(statement.evidence_references)),
                )
            )
        return findings
