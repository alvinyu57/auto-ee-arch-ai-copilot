"""Service declarations and optional explicitly engineered physical traffic routes."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from ee_arch_copilot.domain.models.common import (
    DomainModel,
    Identifier,
    Name,
    NonNegativeMbps,
    ensure_unique,
)


class CommunicationProtocol(StrEnum):
    SOME_IP = "SOME/IP"
    DDS = "DDS"
    MQTT = "MQTT"
    REST = "REST"
    OTHER = "OTHER"


class TrafficRoute(DomainModel):
    """Ordered links from the provider to one consumer; never inferred from shortest paths."""

    consumer_ecu_id: Identifier
    link_ids: list[Identifier] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_links(self) -> Self:
        ensure_unique(self.link_ids, "route link IDs")
        return self


class Service(DomainModel):
    id: Identifier
    name: Name
    provider_ecu_id: Identifier
    consumer_ecu_ids: list[Identifier] = Field(default_factory=list)
    protocol: CommunicationProtocol
    bandwidth_requirement_mbps: NonNegativeMbps | None = None
    traffic_routes: list[TrafficRoute] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consumers(self) -> Self:
        ensure_unique(self.consumer_ecu_ids, f"consumer IDs for service {self.id}")
        ensure_unique(
            (route.consumer_ecu_id for route in self.traffic_routes),
            f"routed consumer IDs for service {self.id}",
        )
        for route in self.traffic_routes:
            if route.consumer_ecu_id not in self.consumer_ecu_ids:
                raise ValueError(
                    f"Route consumer {route.consumer_ecu_id} is not a service consumer"
                )
        return self
