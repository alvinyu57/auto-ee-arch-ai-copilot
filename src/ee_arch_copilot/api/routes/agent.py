"""Synchronous HTTP contract over a cancellable, bounded asynchronous orchestration loop."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ee_arch_copilot.agent.models import AgentResponse, AnalyzeRequest
from ee_arch_copilot.agent.orchestrator import AgentOrchestrator
from ee_arch_copilot.agent.providers import AgentProvider, CompatibleAgentProvider
from ee_arch_copilot.api.routes.knowledge import get_knowledge_service
from ee_arch_copilot.rag.errors import ConfigurationError

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["agent"],
    responses={
        413: {"description": "Request body exceeds configured size limit"},
        503: {"description": "Configure AGENT_PROVIDER and AGENT_MODEL / LLM_MODEL"},
        502: {"description": "Provider failed before any usable evidence was collected"},
        504: {"description": "Provider execution deadline exceeded without usable evidence"},
    },
)


def get_agent_provider(request: Request) -> AgentProvider:
    injected: AgentProvider | None = request.app.state.agent_provider
    if injected is not None:
        return injected
    try:
        return CompatibleAgentProvider(request.app.state.settings)
    except ConfigurationError as error:
        raise HTTPException(503, f"Agent unavailable: {error}") from error


@router.post("/analyze", response_model=AgentResponse)
async def analyze(
    body: AnalyzeRequest,
    request: Request,
    response: Response,
    provider: Annotated[AgentProvider, Depends(get_agent_provider)],
) -> AgentResponse:
    """Read-only analysis. COMPLETED describes execution, never design approval.

    Partial analyses retain independent findings with HTTP 200. Provider failures with
    no usable evidence return a structured FAILED result and 502/504. Invalid input is 422.
    Submit a complete Phase 1 architecture, or omit it for requirements-only questions.
    """
    orchestrator = AgentOrchestrator(
        request.app.state.settings, provider, lambda: get_knowledge_service(request)
    )
    try:
        result = await orchestrator.analyze(body)
        if result.status == "FAILED":
            response.status_code = (
                504 if result.execution_metadata.stop_reason == "provider_timeout" else 502
            )
        return result
    except ValueError as error:
        raise HTTPException(422, "Agent options exceed configured server limits") from error
