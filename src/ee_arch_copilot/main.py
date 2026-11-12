"""ASGI entry point: uvicorn ee_arch_copilot.main:app."""

import sqlite3
from threading import RLock

from chromadb.errors import ChromaError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ee_arch_copilot import __version__
from ee_arch_copilot.agent.providers import AgentProvider
from ee_arch_copilot.api.limits import KnowledgeBodyLimit
from ee_arch_copilot.api.routes import agent, architecture, health, knowledge
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.errors import ConfigurationError, ProviderError
from ee_arch_copilot.rag.service import KnowledgeService


def create_app(
    settings: Settings | None = None,
    knowledge_service: KnowledgeService | None = None,
    agent_provider: AgentProvider | None = None,
) -> FastAPI:
    settings = settings or Settings()
    application = FastAPI(
        title="Automotive E/E Architecture AI Copilot",
        version=__version__,
        description=(
            "Phase 1: deterministic architecture modeling, physical topology, and nominal link "
            "budget checks. Phase 2: persistent requirements retrieval "
            "and optional cited generation. "
            "Phase 3: bounded read-only native tool-calling agent. "
            "Synthetic engineering proof of concept."
        ),
    )
    application.state.settings = settings
    application.state.knowledge_service = knowledge_service
    application.state.agent_provider = agent_provider
    application.state.knowledge_lock = RLock()
    application.add_middleware(KnowledgeBodyLimit, max_bytes=settings.max_request_bytes)

    @application.exception_handler(ConfigurationError)
    async def configuration_error(_request: Request, _error: ConfigurationError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Knowledge provider or index configuration unavailable; check settings"
            },
        )

    @application.exception_handler(ProviderError)
    async def provider_error(_request: Request, _error: ProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": "Knowledge provider failed or returned a malformed response"},
        )

    @application.exception_handler(sqlite3.Error)
    @application.exception_handler(ChromaError)
    @application.exception_handler(OSError)
    async def storage_error(_request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Knowledge storage unavailable"})

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, error: RequestValidationError) -> JSONResponse:
        # Raw inputs can contain NaN/Infinity, which cannot be encoded in a JSON error response.
        # Locations, messages, and error types provide useful diagnostics without echoing inputs.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(issue["loc"]), "msg": issue["msg"], "type": issue["type"]}
                    for issue in error.errors()
                ]
            },
        )

    application.include_router(health.router)
    application.include_router(architecture.router)
    application.include_router(knowledge.router)
    application.include_router(agent.router)
    return application


app = create_app()
