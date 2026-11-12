"""Controlled narrative contract, not a general natural-language truth classifier.

Only exact templates can reach the response's narrative fields. Status summaries are
always rendered from committed tool evidence. Changing a word list cannot grant a
model-generated engineering assertion authority.
"""

from collections import Counter

from ee_arch_copilot.agent.evidence import EvidenceStore
from ee_arch_copilot.agent.models import ModelFinal, ToolExecution

NEUTRAL_SUMMARY = "Collected engineering evidence is available for review."
REVIEW_STATEMENT = "Review source and computation evidence within its scope."
RECOMMENDATION = "Review unsupported constraints and supply missing inputs."
CLARIFICATION = "Which source documents or architecture should be supplied?"
ALL_PASS = "All executed checks passed; additional engineering validation may be required."
BANDWIDTH_FAILED = "The architecture is not compliant because the bandwidth check failed."
APPROVAL_POLICY = "Architecture approval is not authorized in Phase 3."
UNSUPPORTED_SCOPE = (
    "VLAN isolation, TSN scheduling and latency compliance were not evaluated by these tools."
)


class ResponseIntegrityError(ValueError):
    """Safe category only; never include the rejected model text in diagnostics."""


class EngineeringResponseVerifier:
    def __init__(self, evidence: EvidenceStore) -> None:
        self.evidence = evidence

    def summary(self, executions: list[ToolExecution]) -> str:
        counts = Counter(
            str(record.data["status"])
            for record in self.evidence.records.values()
            if record.kind == "validation"
        )
        if counts:
            headline = (
                "Executed validation findings: "
                f"PASS={counts['PASS']}, FAIL={counts['FAIL']}, "
                f"NOT_EVALUATED={counts['NOT_EVALUATED']}."
            )
        else:
            headline = "No deterministic architecture validation findings were collected."
        if any(e.validation_scope and e.validation_scope.omitted_findings for e in executions):
            headline += " Only selected findings are shown; see validation scopes for omissions."
        if any(r.kind in {"physical_path", "topology"} for r in self.evidence.records.values()):
            headline += " Physical topology/path evidence is available within its stated scope."
        if any(r.kind == "requirement" for r in self.evidence.records.values()):
            headline += " Retrieved requirements are source evidence, not proof of compliance."
        return f"{headline} {UNSUPPORTED_SCOPE} {APPROVAL_POLICY}"

    def validate(
        self, final: ModelFinal, executions: list[ToolExecution], requirement_pattern: str
    ) -> None:
        # Reference checks apply to all fields, including ones that will not be copied.
        # Claim-word heuristics are deliberately not used to admit/reject templates.
        try:
            self.evidence.validate_final(final, requirement_pattern)
        except ValueError as error:
            raise ResponseIntegrityError("evidence_reference_invalid") from error

        allowed = {NEUTRAL_SUMMARY, self.summary(executions)}
        validation = [r for r in self.evidence.records.values() if r.kind == "validation"]
        if (
            validation
            and all(r.data["status"] == "PASS" for r in validation)
            and all(
                e.validation_scope.original_report_status == "PASS"
                for e in executions
                if e.validation_scope
            )
        ):
            allowed.add(ALL_PASS)
        if any(
            r.rule_id == "bandwidth.nominal_link_budget" and r.data["status"] == "FAIL"
            for r in validation
        ):
            # A narrowly defined negative statement has a deterministic precondition;
            # it must not be rejected simply for containing the word "compliant".
            allowed.add(BANDWIDTH_FAILED)
        if final.summary not in allowed:
            raise ResponseIntegrityError("uncontrolled_summary")
        for item in final.findings:
            if item.finding_type != "interpretation" or item.description != REVIEW_STATEMENT:
                raise ResponseIntegrityError("uncontrolled_interpretation")
        for item in final.recommendations:
            if item.description != RECOMMENDATION:
                raise ResponseIntegrityError("uncontrolled_recommendation")
        if any(question != CLARIFICATION for question in final.unresolved_questions):
            raise ResponseIntegrityError("uncontrolled_question")
