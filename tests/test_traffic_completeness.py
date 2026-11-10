"""Regression coverage for D-001: incomplete traffic must survive absent links."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.main import create_app
from ee_arch_copilot.services.validator import ArchitectureValidator, FindingStatus
from tests.conftest import Payload


@pytest.mark.parametrize("has_links", [False, True])
@pytest.mark.parametrize("demand", [None, 0, 60])
def test_missing_traffic_has_independent_evidence(
    payload: Payload, has_links: bool, demand: float | None
) -> None:
    payload["requirements"] = []
    if not has_links:
        payload["links"] = []
    payload["services"][0].update(bandwidth_requirement_mbps=demand, traffic_routes=[])
    architecture = Architecture.model_validate(payload)
    before = architecture.model_dump_json()
    validator = ArchitectureValidator()
    report = validator.validate(architecture)

    assert report.status == FindingStatus.NOT_EVALUATED
    traffic = [item for item in report.findings if item.rule_id == "bandwidth.traffic_evaluability"]
    assert len(traffic) == 1
    finding = traffic[0]
    assert finding.status == FindingStatus.NOT_EVALUATED
    assert finding.severity == "WARNING"
    assert finding.requirement_id is None
    assert finding.affected_components == ["svc", "a", "b"]
    assert finding.explanation
    assert finding.evidence["provider_ecu_id"] == "a"
    assert finding.evidence["consumer_ecu_ids"] == ["b"]
    missing = ["Service svc: route to b is missing"]
    if demand is None:
        missing.insert(0, "Service svc: bandwidth demand is missing")
    assert finding.evidence["missing_information"] == missing
    assert not any(item.rule_id == "connectivity.physical_path" for item in report.findings)
    assert report.model_dump_json() == validator.validate(architecture).model_dump_json()
    assert architecture.model_dump_json() == before


def test_unknown_demand_with_explicit_route(payload: Payload) -> None:
    payload["services"][0].pop("bandwidth_requirement_mbps")
    report = ArchitectureValidator().validate(Architecture.model_validate(payload))
    finding = next(
        item for item in report.findings if item.rule_id == "bandwidth.traffic_evaluability"
    )
    assert finding.evidence["missing_information"] == ["Service svc: bandwidth demand is missing"]
    assert report.status == FindingStatus.NOT_EVALUATED


def test_each_incomplete_service_retains_its_endpoints(payload: Payload) -> None:
    payload.update(links=[], requirements=[])
    payload["services"][0]["traffic_routes"] = []
    second = deepcopy(payload["services"][0])
    second.update(id="second", consumer_ecu_ids=["b", "isolated"])
    payload["services"].append(second)
    report = ArchitectureValidator().validate(Architecture.model_validate(payload))
    traffic = [item for item in report.findings if item.rule_id == "bandwidth.traffic_evaluability"]
    assert [item.affected_components for item in traffic] == [
        ["svc", "a", "b"],
        ["second", "a", "b", "isolated"],
    ]
    assert traffic[1].evidence["missing_information"] == [
        "Service second: route to b is missing",
        "Service second: route to isolated is missing",
    ]


@pytest.mark.parametrize("failure", ["connectivity", "overload"])
def test_failure_takes_precedence_over_incomplete_traffic(payload: Payload, failure: str) -> None:
    if failure == "connectivity":
        payload["links"] = []
        payload["requirements"] = payload["requirements"][:1]
        payload["services"][0]["traffic_routes"] = []
    else:
        payload["services"][0]["bandwidth_requirement_mbps"] = 101
        extra = deepcopy(payload["services"][0])
        extra.update(id="unknown", bandwidth_requirement_mbps=None)
        payload["services"].append(extra)
    report = ArchitectureValidator().validate(Architecture.model_validate(payload))
    assert report.status == FindingStatus.FAIL
    assert any(item.status == FindingStatus.NOT_EVALUATED for item in report.findings)
    assert any(item.status == FindingStatus.FAIL for item in report.findings)


@pytest.mark.parametrize("inventory", ["empty", "no_services", "no_consumers"])
def test_no_communicating_traffic_can_pass_without_links(payload: Payload, inventory: str) -> None:
    payload.update(links=[], requirements=[])
    if inventory == "no_consumers":
        payload["services"][0].update(
            consumer_ecu_ids=[], traffic_routes=[], bandwidth_requirement_mbps=None
        )
    else:
        payload["services"] = []
        if inventory == "empty":
            payload["ecus"] = []
    report = ArchitectureValidator().validate(Architecture.model_validate(payload))
    assert report.status == FindingStatus.PASS
    assert [item.rule_id for item in report.findings] == ["structure.consistency"]


@pytest.mark.parametrize("demand", [None, 0, 60])
def test_api_zero_link_incomplete_traffic(payload: Payload, demand: float | None) -> None:
    payload.update(links=[], requirements=[])
    payload["services"][0].update(bandwidth_requirement_mbps=demand, traffic_routes=[])
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/architectures/validate", json=payload)
        assert response.status_code == 200
        report = response.json()
        assert report["status"] == "NOT_EVALUATED"
        finding = next(
            item
            for item in report["findings"]
            if item["rule_id"] == "bandwidth.traffic_evaluability"
        )
        assert finding["affected_components"] == ["svc", "a", "b"]
        assert finding["status"] == "NOT_EVALUATED"
        assert "Service svc: route to b is missing" in finding["evidence"]["missing_information"]
        assert (
            "Service svc: bandwidth demand is missing" in finding["evidence"]["missing_information"]
        ) is (demand is None)
        assert report == ArchitectureValidator().validate(
            Architecture.model_validate(payload)
        ).model_dump(mode="json")
