from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ee_arch_copilot import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__
    phase: Literal[1] = 1


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
