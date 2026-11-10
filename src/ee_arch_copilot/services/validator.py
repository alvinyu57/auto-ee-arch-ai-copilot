"""Evidence-backed checks over declared structure, physical paths, and nominal link budgets."""

from decimal import Decimal
from enum import StrEnum

from pydantic import JsonValue, ValidationError

from ee_arch_copilot.domain.models import (
    Architecture,
    BandwidthConstraint,
    ConnectivityConstraint,
    NetworkLink,
    NetworkTechnology,
)
from ee_arch_copilot.domain.models.common import DomainModel
from ee_arch_copilot.services.topology import TopologyService


class FindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationFinding(DomainModel):
    rule_id: str
    requirement_id: str | None = None
    severity: Severity
    status: FindingStatus
    affected_components: list[str]
    explanation: str
    evidence: dict[str, JsonValue]


class ValidationReport(DomainModel):
    architecture_id: str
    status: FindingStatus
    findings: list[ValidationFinding]
    scope: str = "Structural consistency, physical connectivity, and declared nominal link budgets"


class ArchitectureValidator:
    def validate(self, architecture: Architecture) -> ValidationReport:
        try:
            checked = Architecture.model_validate(architecture.model_dump())
        except ValidationError as error:
            # API payloads are rejected with 422 before reaching here.
            # Revalidation also protects Python callers after model mutation.
            return ValidationReport(
                architecture_id=architecture.id,
                status=FindingStatus.FAIL,
                findings=[
                    ValidationFinding(
                        rule_id="structure.consistency",
                        severity=Severity.ERROR,
                        status=FindingStatus.FAIL,
                        affected_components=[],
                        explanation="Architecture structure is invalid.",
                        evidence={"errors": [entry["msg"] for entry in error.errors()]},
                    )
                ],
            )
        topology = TopologyService(checked)
        findings = [
            ValidationFinding(
                rule_id="structure.consistency",
                severity=Severity.INFO,
                status=FindingStatus.PASS,
                affected_components=[checked.id],
                explanation=(
                    "Schema, identifiers, references, interfaces, and declared routes are valid."
                ),
                evidence={
                    "device_count": len(checked.ecus) + len(checked.ethernet_switches),
                    "link_count": len(checked.links),
                    "service_count": len(checked.services),
                },
            )
        ]
        loads, incomplete, traffic_findings = self._traffic_loads(checked)
        findings.extend(traffic_findings)
        links = {link.id: link for link in checked.links}
        scoped_links: set[str] = set()
        for requirement in checked.requirements:
            constraint = requirement.constraints
            if isinstance(constraint, ConnectivityConstraint):
                path = topology.find_physical_path(
                    constraint.source_device_id, constraint.destination_device_id
                )
                findings.append(
                    ValidationFinding(
                        rule_id="connectivity.physical_path",
                        requirement_id=requirement.id,
                        severity=Severity.INFO if path.exists else Severity.ERROR,
                        status=FindingStatus.PASS if path.exists else FindingStatus.FAIL,
                        affected_components=[
                            constraint.source_device_id,
                            constraint.destination_device_id,
                        ],
                        explanation=(
                            "A physical path exists; VLAN and service reachability "
                            "are not established."
                            if path.exists
                            else "No physical path exists between the required devices."
                        ),
                        evidence={
                            "device_ids": list(path.device_ids),
                            "link_ids": list(path.link_ids),
                            "connectivity_scope": "physical",
                        },
                    )
                )
            elif isinstance(constraint, BandwidthConstraint):
                for link_id in constraint.link_ids:
                    scoped_links.add(link_id)
                    findings.append(
                        self._check_link(links[link_id], loads[link_id], incomplete, requirement.id)
                    )
            else:
                findings.append(
                    ValidationFinding(
                        rule_id="requirement.evaluability",
                        requirement_id=requirement.id,
                        severity=Severity.WARNING,
                        status=FindingStatus.NOT_EVALUATED,
                        affected_components=requirement.associated_components,
                        explanation=(
                            "Free-text requirements need a supported structured constraint."
                            if constraint is None
                            else "Network isolation requires a VLAN/forwarding policy engine; "
                            "physical topology alone cannot establish isolation."
                        ),
                        evidence={"requirement_type": requirement.requirement_type.value},
                    )
                )
        for link in checked.links:
            if link.id not in scoped_links:
                findings.append(self._check_link(link, loads[link.id], incomplete))
        statuses = {finding.status for finding in findings}
        status = (
            FindingStatus.FAIL
            if FindingStatus.FAIL in statuses
            else FindingStatus.NOT_EVALUATED
            if FindingStatus.NOT_EVALUATED in statuses
            else FindingStatus.PASS
        )
        return ValidationReport(architecture_id=checked.id, status=status, findings=findings)

    @staticmethod
    def _traffic_loads(
        architecture: Architecture,
    ) -> tuple[dict[str, dict[str, Decimal]], list[str], list[ValidationFinding]]:
        loads: dict[str, dict[str, Decimal]] = {link.id: {} for link in architecture.links}
        incomplete: list[str] = []
        findings: list[ValidationFinding] = []
        links = {link.id: link for link in architecture.links}
        for service in architecture.services:
            if not service.consumer_ecu_ids:
                continue
            routes = {route.consumer_ecu_id: route for route in service.traffic_routes}
            missing = []
            if service.bandwidth_requirement_mbps is None:
                missing.append(f"Service {service.id}: bandwidth demand is missing")
            missing.extend(
                f"Service {service.id}: route to {consumer} is missing"
                for consumer in service.consumer_ecu_ids
                if consumer not in routes
            )
            if missing:
                incomplete.extend(missing)
                findings.append(
                    ValidationFinding(
                        rule_id="bandwidth.traffic_evaluability",
                        severity=Severity.WARNING,
                        status=FindingStatus.NOT_EVALUATED,
                        affected_components=[
                            service.id,
                            service.provider_ecu_id,
                            *service.consumer_ecu_ids,
                        ],
                        explanation=(
                            "Declared service traffic cannot be fully assessed for nominal link "
                            "budgets without demand and explicit consumer routes."
                        ),
                        evidence={
                            "provider_ecu_id": service.provider_ecu_id,
                            "consumer_ecu_ids": list(service.consumer_ecu_ids),
                            "missing_information": list(missing),
                        },
                    )
                )
            if service.bandwidth_requirement_mbps is None:
                continue
            for consumer in service.consumer_ecu_ids:
                if consumer not in routes:
                    continue
                current = service.provider_ecu_id
                for link_id in routes[consumer].link_ids:
                    link = links[link_id]
                    destination = (
                        link.destination.device_id
                        if current == link.source.device_id
                        else link.source.device_id
                    )
                    direction = (
                        "shared"
                        if link.technology == NetworkTechnology.CAN
                        else f"{current}->{destination}"
                    )
                    loads[link_id][direction] = loads[link_id].get(direction, Decimal(0)) + Decimal(
                        str(service.bandwidth_requirement_mbps)
                    )
                    current = destination
        return loads, incomplete, findings

    @staticmethod
    def _check_link(
        link: NetworkLink,
        loads: dict[str, Decimal],
        incomplete: list[str],
        requirement_id: str | None = None,
    ) -> ValidationFinding:
        capacity = link.nominal_bandwidth_mbps
        overloaded = capacity is not None and any(
            demand > Decimal(str(capacity)) for demand in loads.values()
        )
        if overloaded:
            status, severity = FindingStatus.FAIL, Severity.ERROR
            explanation = "Declared routed demand exceeds the nominal link capacity budget."
        elif capacity is None or incomplete:
            status, severity = FindingStatus.NOT_EVALUATED, Severity.WARNING
            explanation = (
                "Insufficient capacity, traffic-demand, or routing data to assess this link."
            )
        else:
            status, severity = FindingStatus.PASS, Severity.INFO
            explanation = (
                "Declared routed demand fits the nominal link budget. This does not guarantee "
                "application throughput, delivery, or latency."
            )
        return ValidationFinding(
            rule_id="bandwidth.nominal_link_budget",
            requirement_id=requirement_id,
            severity=severity,
            status=status,
            affected_components=[link.id, link.source.device_id, link.destination.device_id],
            explanation=explanation,
            evidence={
                "nominal_capacity_mbps": capacity,
                "routed_demand_mbps": {direction: str(load) for direction, load in loads.items()},
                "missing_information": [
                    *incomplete,
                    *(["Link nominal capacity is missing"] if capacity is None else []),
                ],
                "budget_model": "shared"
                if link.technology == NetworkTechnology.CAN
                else "per_direction",
                "traffic_model": (
                    "declared provider-to-consumer unicast; no overhead or background traffic"
                ),
                "quantity_encoding": "routed demands are decimal strings in Mbps",
            },
        )
