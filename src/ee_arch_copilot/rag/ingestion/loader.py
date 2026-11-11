import hashlib
import json
from pathlib import Path
from typing import cast

from pydantic import JsonValue
from pypdf import PdfReader

from ee_arch_copilot.rag.models import Document, DocumentInput, SourceType


def normalize_document(source: DocumentInput) -> Document:
    content = source.content.replace("\r\n", "\n").replace("\r", "\n")
    title = source.title
    version = source.version
    if source.source_type == "json":
        try:
            data = json.loads(content)
        except (ValueError, RecursionError) as error:
            raise ValueError("Invalid JSON document") from error
        if isinstance(data, dict):
            title = title or (data.get("title") if isinstance(data.get("title"), str) else None)
            version = version or (
                str(data["version"]) if isinstance(data.get("version"), (str, int)) else None
            )
    if not title and source.source_type == "markdown":
        title = next(
            (line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("# ")),
            None,
        )
    digest = hashlib.sha256(content.encode()).hexdigest()
    document_id = (
        source.document_id or "doc-" + hashlib.sha256(source.filename.encode()).hexdigest()[:24]
    )
    return Document(
        document_id=document_id,
        filename=source.filename,
        source_type=source.source_type,
        title=title or source.filename,
        version=version,
        content=content,
        metadata=source.metadata,
        content_hash=digest,
    )


def load_file(
    path: Path, *, document_id: str | None = None, version: str | None = None
) -> DocumentInput:
    """Trusted local caller only. No HTTP endpoint accepts a filesystem path.

    PDF offsets refer to extracted text. Reject any page without extractable text;
    partial ingestion would otherwise hide missing scanned requirements.
    """
    formats: dict[str, SourceType] = {
        ".md": "markdown",
        ".txt": "text",
        ".json": "json",
        ".pdf": "pdf",
    }
    if path.suffix.lower() not in formats:
        raise ValueError("Supported formats: .md, .txt, .json, .pdf")
    if path.stat().st_size > 10_000_000:
        raise ValueError("Local source exceeds 10 MB limit")
    kind = formats[path.suffix.lower()]
    metadata: dict[str, JsonValue] = {}
    if kind == "pdf":
        try:
            reader = PdfReader(path)
            texts = [page.extract_text() or "" for page in reader.pages]
        except Exception as error:
            raise ValueError("PDF cannot be read or is encrypted") from error
        if not texts or any(not text.strip() for text in texts):
            raise ValueError(
                "PDF has pages without extractable text; scanned PDFs need OCR (unsupported)"
            )
        content = "\n\f\n".join(texts)
        metadata["pdf_page_count"] = len(texts)
        metadata["pdf_offsets"] = cast(JsonValue, "extracted text; pages separated by form feed")
    else:
        content = path.read_text(encoding="utf-8")
    return DocumentInput(
        document_id=document_id,
        filename=path.name,
        source_type=kind,
        content=content,
        metadata=metadata,
        version=version,
    )
