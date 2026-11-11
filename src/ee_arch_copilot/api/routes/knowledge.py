from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ee_arch_copilot.rag.errors import DocumentIdentityConflict
from ee_arch_copilot.rag.models import (
    AnswerResponse,
    AskRequest,
    Chunk,
    Document,
    DocumentInput,
    DocumentSummary,
    IngestionResponse,
    SearchRequest,
    SearchResponse,
)
from ee_arch_copilot.rag.service import KnowledgeService

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
    responses={
        503: {"description": "Knowledge provider or storage configuration unavailable"},
        502: {"description": "Provider request failed or model response malformed"},
        413: {"description": "Request body too large"},
    },
)


def get_knowledge_service(request: Request) -> KnowledgeService:
    # Lazy construction keeps existing Phase 1 routes independent of storage and providers.
    with request.app.state.knowledge_lock:
        service: KnowledgeService | None = request.app.state.knowledge_service
        if service is None:
            service = KnowledgeService(request.app.state.settings)
            request.app.state.knowledge_service = service
        return service


Service = Annotated[KnowledgeService, Depends(get_knowledge_service)]


@router.post(
    "/documents",
    response_model=IngestionResponse,
    responses={409: {"description": "Explicit document identity required for replacement"}},
)
def ingest_document(source: DocumentInput, service: Service) -> IngestionResponse:
    """JSON body: filename, source_type (markdown/text/json), content, optional ID/version/metadata.

    JSON document content is a JSON-encoded string containing a requirements array.
    Reuse document_id to replace the active version. PDF uses the trusted local loader.
    """
    if source.source_type == "pdf":
        raise HTTPException(422, "PDF ingestion requires the trusted local PDF loader")
    try:
        return service.ingest(source)
    except DocumentIdentityConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(
            422, "Document cannot be parsed into indexable source records"
        ) from error


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(service: Service) -> list[DocumentSummary]:
    return service.store.documents()


@router.get(
    "/documents/{document_id}",
    response_model=Document,
    responses={404: {"description": "Unknown document"}},
)
def get_document(document_id: str, service: Service) -> Document:
    document = service.store.get_document(document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.get(
    "/chunks/{chunk_id}", response_model=Chunk, responses={404: {"description": "Unknown chunk"}}
)
def get_chunk(chunk_id: str, service: Service) -> Chunk:
    chunk = service.store.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(404, "Chunk not found in the active indexed revision")
    return chunk


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    responses={404: {"description": "Unknown document"}},
)
def delete_document(document_id: str, service: Service) -> Response:
    if not service.store.delete(document_id):
        raise HTTPException(404, "Document not found")
    return Response(status_code=204)


@router.post("/search", response_model=SearchResponse)
def search_requirements(request: SearchRequest, service: Service) -> SearchResponse:
    """Retrieve evidence without invoking an LLM. Scores are ranking signals, not confidence."""
    return service.search(request.question, request.options)


@router.post("/ask", response_model=AnswerResponse)
def ask_requirements(request: AskRequest, service: Service) -> AnswerResponse:
    """Retrieve and cite evidence using a configured LLM; disabled generation returns 503."""
    return service.ask(request)
