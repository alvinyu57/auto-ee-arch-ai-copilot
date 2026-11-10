"""ASGI entry point: uvicorn ee_arch_copilot.main:app."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ee_arch_copilot import __version__
from ee_arch_copilot.api.routes import architecture, health


def create_app() -> FastAPI:
    application = FastAPI(
        title="Automotive E/E Architecture AI Copilot",
        version=__version__,
        description=(
            "Phase 1: deterministic architecture modeling, physical topology, and nominal link "
            "budget checks. Synthetic engineering proof of concept; no AI integration yet."
        ),
    )

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
    return application


app = create_app()
