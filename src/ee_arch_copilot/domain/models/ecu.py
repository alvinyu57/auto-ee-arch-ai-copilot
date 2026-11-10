"""Electronic control units and their physical network interfaces."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from ee_arch_copilot.domain.models.common import DomainModel, Identifier, Name, ensure_unique
from ee_arch_copilot.domain.models.network import NetworkInterface


class ECUType(StrEnum):
    GATEWAY = "gateway"
    DOMAIN_CONTROLLER = "domain_controller"
    ZONAL_CONTROLLER = "zonal_controller"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    OTHER = "other"


class ECU(DomainModel):
    id: Identifier
    name: Name
    ecu_type: ECUType
    description: str = ""
    interfaces: list[NetworkInterface] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interfaces(self) -> Self:
        ensure_unique((item.id for item in self.interfaces), f"interface IDs on ECU {self.id}")
        return self
