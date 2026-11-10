from copy import deepcopy

import pytest

from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.services.validator import (
    ArchitectureValidator,
    FindingStatus,
    ValidationFinding,
    ValidationReport,
)
from tests.conftest import Payload


def validate(payload: Payload) -> ValidationReport:
    return ArchitectureValidator().validate(Architecture.model_validate(payload))


def bandwidth(report: ValidationReport) -> ValidationFinding:
    return next(item for item in report.findings if item.rule_id == "bandwidth.nominal_link_budget")


def test_structural_and_requirements_pass(payload: Payload) -> None:
    report = validate(payload)
    assert report.status == FindingStatus.PASS
    assert len(report.findings) == 3
    assert all(item.status == FindingStatus.PASS for item in report.findings)
    finding = bandwidth(report)
    assert finding.requirement_id == "REQ-BW"
    assert finding.evidence["routed_demand_mbps"] == {"a->b": "40.0"}


def test_missing_connectivity_is_a_finding(payload: Payload) -> None:
    payload["requirements"][0]["constraints"]["destination_device_id"] = "isolated"
    report = validate(payload)
    finding = next(item for item in report.findings if item.requirement_id == "REQ-CONN")
    assert finding.status == FindingStatus.FAIL
    assert finding.evidence["device_ids"] == []
    assert report.status == FindingStatus.FAIL


@pytest.mark.parametrize(("demand", "expected"), [(0, "PASS"), (100, "PASS"), (101, "FAIL")])
def test_nominal_budget_boundaries(payload: Payload, demand: float, expected: str) -> None:
    payload["services"][0]["bandwidth_requirement_mbps"] = demand
    finding = bandwidth(validate(payload))
    assert finding.status == expected
    assert finding.evidence["nominal_capacity_mbps"] == 100


def test_demands_are_aggregated(payload: Payload) -> None:
    extra = deepcopy(payload["services"][0])
    extra.update(id="svc2", bandwidth_requirement_mbps=70)
    payload["services"].append(extra)
    assert bandwidth(validate(payload)).status == FindingStatus.FAIL


def test_decimal_budget_boundary(payload: Payload) -> None:
    payload["links"][0]["nominal_bandwidth_mbps"] = 0.3
    payload["services"][0]["bandwidth_requirement_mbps"] = 0.1
    extra = deepcopy(payload["services"][0])
    extra.update(id="svc2", bandwidth_requirement_mbps=0.2)
    payload["services"].append(extra)
    assert bandwidth(validate(payload)).status == FindingStatus.PASS


@pytest.mark.parametrize("missing", ["demand", "route", "capacity", "partial_route"])
def test_missing_information_not_evaluated(payload: Payload, missing: str) -> None:
    if missing == "demand":
        payload["services"][0].pop("bandwidth_requirement_mbps")
    elif missing == "route":
        payload["services"][0]["traffic_routes"] = []
    elif missing == "partial_route":
        payload["services"][0]["consumer_ecu_ids"].append("isolated")
    else:
        payload["links"][0].pop("nominal_bandwidth_mbps")
    report = validate(payload)
    finding = bandwidth(report)
    assert finding.status == FindingStatus.NOT_EVALUATED
    assert finding.evidence["missing_information"]
    assert report.status == FindingStatus.NOT_EVALUATED


def test_proven_overload_still_fails_with_other_missing_traffic(payload: Payload) -> None:
    payload["services"][0]["bandwidth_requirement_mbps"] = 101
    extra = deepcopy(payload["services"][0])
    extra.update(id="unknown", bandwidth_requirement_mbps=None)
    payload["services"].append(extra)
    finding = bandwidth(validate(payload))
    assert finding.status == FindingStatus.FAIL
    assert finding.evidence["missing_information"]


@pytest.mark.parametrize("technology", ["ethernet", "can"])
def test_ethernet_directional_and_can_shared_budget(payload: Payload, technology: str) -> None:
    for ecu in payload["ecus"]:
        ecu["interfaces"][0]["technology"] = technology
    payload["links"][0]["technology"] = technology
    payload["services"][0]["bandwidth_requirement_mbps"] = 60
    reverse = deepcopy(payload["services"][0])
    reverse.update(
        id="reverse",
        provider_ecu_id="b",
        consumer_ecu_ids=["a"],
        traffic_routes=[{"consumer_ecu_id": "a", "link_ids": ["ab"]}],
    )
    payload["services"].append(reverse)
    finding = bandwidth(validate(payload))
    assert finding.status == ("PASS" if technology == "ethernet" else "FAIL")


def test_bandwidth_checks_without_requirement(payload: Payload) -> None:
    payload["requirements"] = []
    assert bandwidth(validate(payload)).requirement_id is None


def test_service_without_consumers_adds_no_traffic(payload: Payload) -> None:
    payload["services"][0].update(
        consumer_ecu_ids=[], traffic_routes=[], bandwidth_requirement_mbps=None
    )
    finding = bandwidth(validate(payload))
    assert finding.status == FindingStatus.PASS
    assert finding.evidence["routed_demand_mbps"] == {}


def test_sample_does_not_claim_isolation_or_latency(sample: Architecture) -> None:
    report = ArchitectureValidator().validate(sample)
    assert report.status == FindingStatus.NOT_EVALUATED
    findings = {item.requirement_id: item for item in report.findings if item.requirement_id}
    assert findings["REQ-ISO-001"].status == FindingStatus.NOT_EVALUATED
    assert findings["REQ-TEXT-001"].status == FindingStatus.NOT_EVALUATED
    budgets = [item for item in report.findings if item.rule_id == "bandwidth.nominal_link_budget"]
    assert len(budgets) == 6
    assert all(item.status == FindingStatus.PASS for item in budgets)


def test_mutated_python_model_cannot_bypass_structure(payload: Payload) -> None:
    architecture = Architecture.model_validate(payload)
    architecture.services[0].provider_ecu_id = "missing"
    report = ArchitectureValidator().validate(architecture)
    assert report.status == FindingStatus.FAIL
    assert len(report.findings) == 1
    assert report.findings[0].rule_id == "structure.consistency"
    assert "unknown provider" in str(report.findings[0].evidence)
