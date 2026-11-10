from fastapi import APIRouter, HTTPException

from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.domain.models.common import DomainModel, Identifier
from ee_arch_copilot.services.topology import (
    PhysicalPath,
    TopologyRepresentation,
    TopologyService,
    UnknownDeviceError,
)
from ee_arch_copilot.services.validator import ArchitectureValidator, ValidationReport

router = APIRouter(prefix="/api/v1/architectures", tags=["architectures"])


class PathRequest(DomainModel):
    architecture: Architecture
    source_device_id: Identifier
    destination_device_id: Identifier


@router.post("/validate", response_model=ValidationReport)
def validate_architecture(architecture: Architecture) -> ValidationReport:
    """Report deterministic findings. FAIL and NOT_EVALUATED findings still return HTTP 200."""
    return ArchitectureValidator().validate(architecture)


@router.post("/topology", response_model=TopologyRepresentation)
def architecture_topology(architecture: Architecture) -> TopologyRepresentation:
    """Export a physical multigraph, including endpoint VLAN annotations, without VLAN analysis."""
    return TopologyService(architecture).to_representation()


@router.post(
    "/path", response_model=PhysicalPath, responses={404: {"description": "Unknown device"}}
)
def architecture_path(request: PathRequest) -> PhysicalPath:
    """Find one unweighted physical path. This is not traffic routing or service reachability."""
    try:
        return TopologyService(request.architecture).find_physical_path(
            request.source_device_id, request.destination_device_id
        )
    except UnknownDeviceError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
