"""Root aggregate: cross-reference and physical route consistency validation."""

from typing import Self

from pydantic import Field, model_validator

from ee_arch_copilot.domain.models.common import DomainModel, Identifier, Name, ensure_unique
from ee_arch_copilot.domain.models.ecu import ECU
from ee_arch_copilot.domain.models.network import (
    EthernetSwitch,
    NetworkInterface,
    NetworkLink,
    NetworkTechnology,
)
from ee_arch_copilot.domain.models.requirement import (
    BandwidthConstraint,
    ConnectivityConstraint,
    IsolationConstraint,
    Requirement,
)
from ee_arch_copilot.domain.models.service import Service


class Architecture(DomainModel):
    id: Identifier
    name: Name
    description: str = ""
    ecus: list[ECU] = Field(default_factory=list)
    ethernet_switches: list[EthernetSwitch] = Field(default_factory=list)
    links: list[NetworkLink] = Field(default_factory=list)
    services: list[Service] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        device_ids = [ecu.id for ecu in self.ecus] + [
            switch.id for switch in self.ethernet_switches
        ]
        ensure_unique(device_ids, "device IDs")
        ensure_unique((link.id for link in self.links), "link IDs")
        ensure_unique((service.id for service in self.services), "service IDs")
        ensure_unique((requirement.id for requirement in self.requirements), "requirement IDs")
        interfaces = {
            **{ecu.id: {item.id: item for item in ecu.interfaces} for ecu in self.ecus},
            **{
                switch.id: {item.id: item for item in switch.ports}
                for switch in self.ethernet_switches
            },
        }
        self._validate_links(interfaces)
        self._validate_services({ecu.id for ecu in self.ecus})
        self._validate_requirements(set(interfaces))
        return self

    def _validate_links(self, interfaces: dict[str, dict[str, NetworkInterface]]) -> None:
        occupied: set[tuple[str, str]] = set()
        for link in self.links:
            for endpoint in (link.source, link.destination):
                if endpoint.device_id not in interfaces:
                    raise ValueError(f"Link {link.id}: unknown device {endpoint.device_id}")
                interface = interfaces[endpoint.device_id].get(endpoint.interface_id)
                if interface is None:
                    raise ValueError(
                        f"Link {link.id}: unknown interface/port "
                        f"{endpoint.device_id}/{endpoint.interface_id}"
                    )
                if interface.technology != link.technology:
                    raise ValueError(f"Link {link.id}: interface technology mismatch")
                if (
                    link.nominal_bandwidth_mbps is not None
                    and interface.nominal_speed_mbps is not None
                    and link.nominal_bandwidth_mbps > interface.nominal_speed_mbps
                ):
                    raise ValueError(f"Link {link.id}: bandwidth exceeds endpoint nominal speed")
                key = (endpoint.device_id, endpoint.interface_id)
                if link.technology == NetworkTechnology.ETHERNET:
                    if key in occupied:
                        raise ValueError(
                            f"Ethernet interface {key} is used by multiple physical links"
                        )
                    occupied.add(key)

    def _validate_services(self, ecu_ids: set[str]) -> None:
        links = {link.id: link for link in self.links}
        for service in self.services:
            if service.provider_ecu_id not in ecu_ids:
                raise ValueError(
                    f"Service {service.id}: unknown provider ECU {service.provider_ecu_id}"
                )
            for consumer in service.consumer_ecu_ids:
                if consumer not in ecu_ids:
                    raise ValueError(f"Service {service.id}: unknown consumer ECU {consumer}")
            for route in service.traffic_routes:
                current = service.provider_ecu_id
                visited = {current}
                for link_id in route.link_ids:
                    if link_id not in links:
                        raise ValueError(
                            f"Service {service.id}: route references unknown link {link_id}"
                        )
                    link = links[link_id]
                    if current == link.source.device_id:
                        current = link.destination.device_id
                    elif current == link.destination.device_id:
                        current = link.source.device_id
                    else:
                        raise ValueError(
                            f"Service {service.id}: route is not contiguous at {link_id}"
                        )
                    if current in visited:
                        raise ValueError(
                            f"Service {service.id}: traffic route must not contain cycles"
                        )
                    visited.add(current)
                if current != route.consumer_ecu_id:
                    raise ValueError(
                        f"Service {service.id}: route does not end at its consumer ECU"
                    )

    def _validate_requirements(self, device_ids: set[str]) -> None:
        link_ids = {link.id for link in self.links}
        components = device_ids | link_ids | {service.id for service in self.services}
        for requirement in self.requirements:
            for component in requirement.associated_components:
                if component not in components:
                    raise ValueError(f"Requirement {requirement.id}: unknown component {component}")
            constraint = requirement.constraints
            if isinstance(constraint, ConnectivityConstraint | IsolationConstraint):
                for device in (constraint.source_device_id, constraint.destination_device_id):
                    if device not in device_ids:
                        raise ValueError(f"Requirement {requirement.id}: unknown device {device}")
            elif isinstance(constraint, BandwidthConstraint):
                for link_id in constraint.link_ids:
                    if link_id not in link_ids:
                        raise ValueError(f"Requirement {requirement.id}: unknown link {link_id}")
