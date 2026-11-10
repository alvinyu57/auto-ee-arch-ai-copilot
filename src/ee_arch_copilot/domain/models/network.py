"""Physical interfaces, switches, and links; speeds are nominal, not throughput."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from ee_arch_copilot.domain.models.common import (
    DomainModel,
    Identifier,
    Name,
    PositiveMbps,
    VlanId,
    ensure_unique,
)


class NetworkTechnology(StrEnum):
    ETHERNET = "ethernet"
    CAN = "can"


class NetworkInterface(DomainModel):
    id: Identifier
    technology: NetworkTechnology
    nominal_speed_mbps: PositiveMbps | None = None
    vlan_ids: list[VlanId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_vlans(self) -> Self:
        ensure_unique(self.vlan_ids, "VLAN IDs")
        if self.technology == NetworkTechnology.CAN and self.vlan_ids:
            raise ValueError("CAN interfaces cannot have Ethernet VLAN membership")
        return self


class EthernetSwitch(DomainModel):
    id: Identifier
    name: Name
    description: str = ""
    ports: list[NetworkInterface] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ports(self) -> Self:
        ensure_unique((port.id for port in self.ports), f"port IDs on switch {self.id}")
        if any(port.technology != NetworkTechnology.ETHERNET for port in self.ports):
            raise ValueError(f"Ethernet switch {self.id} supports only Ethernet ports")
        return self


class LinkEndpoint(DomainModel):
    device_id: Identifier
    interface_id: Identifier


class NetworkLink(DomainModel):
    id: Identifier
    source: LinkEndpoint
    destination: LinkEndpoint
    technology: NetworkTechnology
    nominal_bandwidth_mbps: PositiveMbps | None = None

    @model_validator(mode="after")
    def reject_self_link(self) -> Self:
        if self.source.device_id == self.destination.device_id:
            raise ValueError(f"Link {self.id} must connect two different devices")
        return self
