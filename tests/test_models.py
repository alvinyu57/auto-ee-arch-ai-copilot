import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from ee_arch_copilot.domain.models import Architecture, Requirement
from tests.conftest import EXAMPLES, Payload


def test_synthetic_sample_and_requirements_load(sample: Architecture) -> None:
    assert len(sample.ecus) == 6
    assert len(sample.ethernet_switches) == 1
    requirements = TypeAdapter(list[Requirement]).validate_json(
        (EXAMPLES / "requirements.json").read_text()
    )
    assert requirements == sample.requirements
    assert Architecture.model_validate_json(sample.model_dump_json()) == sample
    assert "synthetic" in sample.description.lower()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p["ecus"].append(deepcopy(p["ecus"][0])), "Duplicate device IDs"),
        (lambda p: p["links"].append(deepcopy(p["links"][0])), "Duplicate link IDs"),
        (lambda p: p["services"].append(deepcopy(p["services"][0])), "Duplicate service IDs"),
        (
            lambda p: p["requirements"].append(deepcopy(p["requirements"][0])),
            "Duplicate requirement IDs",
        ),
        (
            lambda p: p["ecus"][0]["interfaces"].append(deepcopy(p["ecus"][0]["interfaces"][0])),
            "Duplicate interface IDs",
        ),
        (lambda p: p["links"][0]["destination"].update(device_id="missing"), "unknown device"),
        (
            lambda p: p["links"][0]["destination"].update(interface_id="missing"),
            "unknown interface/port",
        ),
        (lambda p: p["links"][0].update(technology="can"), "technology mismatch"),
        (
            lambda p: p["links"][0].update(nominal_bandwidth_mbps=101),
            "exceeds endpoint nominal speed",
        ),
        (lambda p: p["links"][0].update(nominal_bandwidth_mbps=-1), "greater than 0"),
        (
            lambda p: p["services"][0].update(bandwidth_requirement_mbps=-1),
            "greater than or equal to 0",
        ),
        (lambda p: p["services"][0].update(provider_ecu_id="missing"), "unknown provider ECU"),
        (
            lambda p: p["services"][0].update(consumer_ecu_ids=["missing"], traffic_routes=[]),
            "unknown consumer ECU",
        ),
        (lambda p: p["services"][0].update(consumer_ecu_ids=["b", "b"]), "Duplicate consumer IDs"),
        (
            lambda p: p["services"][0]["traffic_routes"][0].update(consumer_ecu_id="isolated"),
            "not a service consumer",
        ),
        (
            lambda p: p["services"][0]["traffic_routes"][0].update(link_ids=["missing"]),
            "unknown link",
        ),
        (
            lambda p: p["services"][0]["traffic_routes"][0].update(link_ids=["ab", "ab"]),
            "Duplicate route link IDs",
        ),
        (lambda p: p["services"][0].update(provider_ecu_id="isolated"), "not contiguous"),
        (
            lambda p: p["services"][0].update(
                consumer_ecu_ids=["isolated"],
                traffic_routes=[{"consumer_ecu_id": "isolated", "link_ids": ["ab"]}],
            ),
            "does not end",
        ),
        (
            lambda p: p["requirements"][0]["constraints"].update(destination_device_id="missing"),
            "unknown device",
        ),
        (
            lambda p: p["requirements"][0].update(associated_components=["missing"]),
            "unknown component",
        ),
        (lambda p: p["requirements"][0].update(requirement_type="bandwidth"), "must match"),
        (
            lambda p: p["requirements"][1]["constraints"].update(link_ids=["missing"]),
            "unknown link",
        ),
        (
            lambda p: p["requirements"][1]["constraints"].update(link_ids=["ab", "ab"]),
            "Duplicate bandwidth",
        ),
        (
            lambda p: p["ecus"][0]["interfaces"][0].update(vlan_ids=[0]),
            "greater than or equal to 1",
        ),
        (
            lambda p: p["ecus"][0]["interfaces"][0].update(vlan_ids=[4095]),
            "less than or equal to 4094",
        ),
        (lambda p: p["ecus"][0]["interfaces"][0].update(vlan_ids=[10, 10]), "Duplicate VLAN IDs"),
        (
            lambda p: p["ecus"][0]["interfaces"][0].update(technology="can", vlan_ids=[10]),
            "CAN interfaces",
        ),
        (lambda p: p["links"][0]["destination"].update(device_id="a"), "two different devices"),
        (lambda p: p.update(name="  "), "at least 1 character"),
        (lambda p: p.update(typo="unknown"), "Extra inputs"),
    ],
)
def test_invalid_structures_rejected(
    payload: Payload, mutate: Callable[[Payload], Any], message: str
) -> None:
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        Architecture.model_validate(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_demands_rejected(payload: Payload, value: float) -> None:
    payload["services"][0]["bandwidth_requirement_mbps"] = value
    with pytest.raises(ValidationError):
        Architecture.model_validate(payload)


def test_duplicate_across_ecus_and_switches(sample_payload: Payload) -> None:
    sample_payload["ethernet_switches"][0]["id"] = "gateway"
    with pytest.raises(ValidationError, match="Duplicate device IDs"):
        Architecture.model_validate(sample_payload)


def test_ethernet_port_cannot_be_reused(payload: Payload) -> None:
    extra = deepcopy(payload["links"][0])
    extra.update(id="extra", destination={"device_id": "isolated", "interface_id": "eth0"})
    payload["links"].append(extra)
    with pytest.raises(ValidationError, match="multiple physical links"):
        Architecture.model_validate(payload)


@pytest.mark.parametrize("invalid", ["duplicate", "can"])
def test_switch_port_validation(sample_payload: Payload, invalid: str) -> None:
    ports = sample_payload["ethernet_switches"][0]["ports"]
    if invalid == "duplicate":
        ports.append(deepcopy(ports[0]))
    else:
        ports[0].update(technology="can", vlan_ids=[])
    with pytest.raises(ValidationError, match=r"Duplicate port IDs|only Ethernet ports"):
        Architecture.model_validate(sample_payload)


def test_route_cycles_rejected(payload: Payload) -> None:
    for ecu in payload["ecus"][:2]:
        ecu["interfaces"].append({"id": "eth1", "technology": "ethernet"})
    extra = deepcopy(payload["links"][0])
    extra.update(id="ab2")
    extra["source"]["interface_id"] = "eth1"
    extra["destination"]["interface_id"] = "eth1"
    payload["links"].append(extra)
    payload["services"][0]["traffic_routes"][0]["link_ids"] = ["ab", "ab2"]
    with pytest.raises(ValidationError, match="cycles"):
        Architecture.model_validate(payload)


def test_example_is_standard_json() -> None:
    # Ensure the shipped example is ordinary JSON, including finite numeric quantities.
    parsed = json.loads((EXAMPLES / "centralized_architecture.json").read_text())
    json.dumps(parsed, allow_nan=False)
