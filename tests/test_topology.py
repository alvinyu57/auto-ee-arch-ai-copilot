from copy import deepcopy

import networkx as nx
import pytest

from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.services.topology import TopologyService, UnknownDeviceError
from tests.conftest import Payload


def test_sample_graph_and_export(sample: Architecture) -> None:
    topology = TopologyService(sample)
    assert isinstance(topology.graph, nx.MultiGraph)
    assert topology.graph.number_of_nodes() == 7
    assert topology.graph.number_of_edges() == 6
    result = topology.to_representation()
    assert len(result.connected_components) == 1
    assert result.isolated_device_ids == []
    assert result.connectivity_scope == "physical"
    camera_edge = next(edge for edge in result.edges if edge.id == "link-camera")
    assert camera_edge.source.interface_id == "eth0"
    assert camera_edge.destination.interface_id == "p4"
    assert camera_edge.nominal_bandwidth_mbps == 100
    assert camera_edge.source_vlan_ids == [20]


def test_physical_path_and_neighbors(sample: Architecture) -> None:
    topology = TopologyService(sample)
    path = topology.find_physical_path("front-camera", "adas")
    assert path.exists
    assert path.device_ids == ["front-camera", "switch-core", "adas"]
    assert path.link_ids == ["link-camera", "link-adas"]
    assert topology.direct_neighbors("gateway") == ["body", "switch-core"]
    assert topology.find_physical_path("body", "adas").exists  # Crosses CAN/Ethernet physically.
    assert "service reachability" in path.limitations


def test_disconnected_and_self_paths(payload: Payload) -> None:
    topology = TopologyService(Architecture.model_validate(payload))
    assert topology.disconnected_devices() == ["isolated"]
    assert topology.disconnected_devices("isolated") == ["a", "b"]
    assert topology.disconnected_devices("a") == ["isolated"]
    path = topology.find_physical_path("a", "isolated")
    assert not path.exists and not path.device_ids and not path.link_ids
    assert topology.find_physical_path("a", "a").device_ids == ["a"]


@pytest.mark.parametrize("operation", ["path", "neighbors", "disconnected"])
def test_unknown_device(payload: Payload, operation: str) -> None:
    topology = TopologyService(Architecture.model_validate(payload))
    with pytest.raises(UnknownDeviceError, match="Unknown device"):
        if operation == "path":
            topology.find_physical_path("a", "missing")
        elif operation == "neighbors":
            topology.direct_neighbors("missing")
        else:
            topology.disconnected_devices("missing")


def test_parallel_links_preserved(payload: Payload) -> None:
    for ecu in payload["ecus"][:2]:
        ecu["interfaces"].append({"id": "eth1", "technology": "ethernet"})
    link = deepcopy(payload["links"][0])
    link.update(id="ab2")
    link["source"]["interface_id"] = "eth1"
    link["destination"]["interface_id"] = "eth1"
    payload["links"].append(link)
    topology = TopologyService(Architecture.model_validate(payload))
    assert topology.graph.number_of_edges("a", "b") == 2
    assert {edge.id for edge in topology.to_representation().edges} == {"ab", "ab2"}
    assert topology.find_physical_path("a", "b").link_ids == ["ab"]


def test_vlan_mismatch_is_not_service_reachability(payload: Payload) -> None:
    payload["ecus"][0]["interfaces"][0]["vlan_ids"] = [10]
    payload["ecus"][1]["interfaces"][0]["vlan_ids"] = [20]
    topology = TopologyService(Architecture.model_validate(payload))
    assert topology.find_physical_path("a", "b").exists
    edge = topology.to_representation().edges[0]
    assert edge.source_vlan_ids != edge.destination_vlan_ids
    assert "VLAN connectivity" in topology.to_representation().limitations
