"""Free text requirements are distinct from discriminated machine-verifiable constraints."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ee_arch_copilot.domain.models.common import DomainModel, Identifier, Name, ensure_unique


class RequirementType(StrEnum):
    CONNECTIVITY = "connectivity"
    BANDWIDTH = "bandwidth"
    ISOLATION = "isolation"
    OTHER = "other"


class ConnectivityConstraint(DomainModel):
    kind: Literal["connectivity"] = "connectivity"
    source_device_id: Identifier
    destination_device_id: Identifier


class BandwidthConstraint(DomainModel):
    """Compare all declared routed traffic with nominal capacity on each listed link."""

    kind: Literal["bandwidth"] = "bandwidth"
    link_ids: list[Identifier] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_links(self) -> Self:
        ensure_unique(self.link_ids, "bandwidth constraint link IDs")
        return self


class IsolationConstraint(DomainModel):
    kind: Literal["isolation"] = "isolation"
    source_device_id: Identifier
    destination_device_id: Identifier


StructuredConstraint = Annotated[
    ConnectivityConstraint | BandwidthConstraint | IsolationConstraint, Field(discriminator="kind")
]


class Requirement(DomainModel):
    id: Identifier
    description: Name
    requirement_type: RequirementType
    associated_components: list[Identifier] = Field(default_factory=list)
    constraints: StructuredConstraint | None = None

    @model_validator(mode="after")
    def validate_constraint_type(self) -> Self:
        ensure_unique(
            self.associated_components, f"associated components for requirement {self.id}"
        )
        if self.constraints is not None and self.constraints.kind != self.requirement_type.value:
            raise ValueError("Requirement type must match structured constraint kind")
        return self
