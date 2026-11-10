"""Public domain model exports."""

from ee_arch_copilot.domain.models.architecture import Architecture
from ee_arch_copilot.domain.models.ecu import ECU, ECUType
from ee_arch_copilot.domain.models.network import (
    EthernetSwitch,
    LinkEndpoint,
    NetworkInterface,
    NetworkLink,
    NetworkTechnology,
)
from ee_arch_copilot.domain.models.requirement import (
    BandwidthConstraint,
    ConnectivityConstraint,
    IsolationConstraint,
    Requirement,
    RequirementType,
)
from ee_arch_copilot.domain.models.service import CommunicationProtocol, Service, TrafficRoute

__all__ = [
    "ECU",
    "Architecture",
    "BandwidthConstraint",
    "CommunicationProtocol",
    "ConnectivityConstraint",
    "ECUType",
    "EthernetSwitch",
    "IsolationConstraint",
    "LinkEndpoint",
    "NetworkInterface",
    "NetworkLink",
    "NetworkTechnology",
    "Requirement",
    "RequirementType",
    "Service",
    "TrafficRoute",
]
