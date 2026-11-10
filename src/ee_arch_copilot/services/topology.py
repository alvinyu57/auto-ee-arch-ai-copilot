"""Physical topology only: edges do not imply VLAN, forwarding, or service reachability."""

from __future__ import annotations

from itertools import pairwise
from typing import Literal

import networkx as nx
from pydantic import Field

from ee_arch_copilot.domain.models import Architecture, ECUType, NetworkLink
from ee_arch_copilot.domain.models.common import DomainModel

PHYSICAL_LIMITATION = (
    "Physical connectivity only. Paths may cross technologies or VLAN boundaries and do not "
    "establish frame forwarding, VLAN connectivity, protocol compatibility, "
    "or service reachability."
)


class UnknownDeviceError(ValueError):
    """A topology query references a device outside the supplied architecture."""


class TopologyNode(DomainModel):
    id: str
    name: str
    kind: Literal["ecu", "ethernet_switch"]
    ecu_type: ECUType | None = None


class TopologyEdge(NetworkLink):
    source_vlan_ids: list[int] = Field(default_factory=list)
    destination_vlan_ids: list[int] = Field(default_factory=list)


class PhysicalPath(DomainModel):
    source_device_id: str
    destination_device_id: str
    exists: bool
    device_ids: list[str]
    link_ids: list[str]
    connectivity_scope: Literal["physical"] = "physical"
    limitations: str = PHYSICAL_LIMITATION


class TopologyRepresentation(DomainModel):
    architecture_id: str
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    isolated_device_ids: list[str]
    connected_components: list[list[str]]
    connectivity_scope: Literal["physical"] = "physical"
    limitations: str = PHYSICAL_LIMITATION


class TopologyService:
    def __init__(self, architecture: Architecture) -> None:
        # Copy and revalidate mutable models so prior caller mutations cannot bypass the schema.
        self.architecture = Architecture.model_validate(architecture.model_dump())
        self.graph = self._build_graph()

    def _build_graph(self) -> nx.MultiGraph[str]:
        graph: nx.MultiGraph[str] = nx.MultiGraph()
        interfaces = {
            **{
                ecu.id: {item.id: item for item in ecu.interfaces} for ecu in self.architecture.ecus
            },
            **{
                switch.id: {item.id: item for item in switch.ports}
                for switch in self.architecture.ethernet_switches
            },
        }
        for ecu in self.architecture.ecus:
            graph.add_node(ecu.id, name=ecu.name, kind="ecu", ecu_type=ecu.ecu_type)
        for switch in self.architecture.ethernet_switches:
            graph.add_node(switch.id, name=switch.name, kind="ethernet_switch", ecu_type=None)
        for link in self.architecture.links:
            edge = TopologyEdge(
                **link.model_dump(),
                source_vlan_ids=interfaces[link.source.device_id][
                    link.source.interface_id
                ].vlan_ids,
                destination_vlan_ids=interfaces[link.destination.device_id][
                    link.destination.interface_id
                ].vlan_ids,
            )
            graph.add_edge(
                link.source.device_id,
                link.destination.device_id,
                key=link.id,
                **edge.model_dump(mode="json"),
            )
        return graph

    def _require_device(self, device_id: str) -> None:
        if device_id not in self.graph:
            raise UnknownDeviceError(f"Unknown device: {device_id}")

    def find_physical_path(self, source: str, destination: str) -> PhysicalPath:
        self._require_device(source)
        self._require_device(destination)
        try:
            devices: list[str] = nx.shortest_path(self.graph, source, destination)
        except nx.NetworkXNoPath:
            devices = []
        # One representative link per hop. No capacity-based routing or traffic assignment.
        links = [min(self.graph[left][right]) for left, right in pairwise(devices)]
        return PhysicalPath(
            source_device_id=source,
            destination_device_id=destination,
            exists=bool(devices),
            device_ids=devices,
            link_ids=links,
        )

    def direct_neighbors(self, device_id: str) -> list[str]:
        self._require_device(device_id)
        return sorted(self.graph.neighbors(device_id))

    def disconnected_devices(self, reference_device_id: str | None = None) -> list[str]:
        """Return isolated nodes, or all nodes unreachable from an explicit reference device."""
        if reference_device_id is None:
            return sorted(nx.isolates(self.graph))
        self._require_device(reference_device_id)
        reachable = nx.node_connected_component(self.graph, reference_device_id)
        return sorted(set(self.graph) - reachable)

    def to_representation(self) -> TopologyRepresentation:
        return TopologyRepresentation(
            architecture_id=self.architecture.id,
            nodes=[TopologyNode(id=node, **data) for node, data in self.graph.nodes(data=True)],
            edges=[TopologyEdge.model_validate(data) for *_, data in self.graph.edges(data=True)],
            isolated_device_ids=self.disconnected_devices(),
            connected_components=sorted(
                sorted(group) for group in nx.connected_components(self.graph)
            ),
        )
