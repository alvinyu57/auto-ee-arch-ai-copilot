import hashlib
import json

from ee_arch_copilot.rag.models import Chunk, Document, SourceRecord


class RequirementChunker:
    def __init__(self, max_chars: int = 1000, overlap: int = 120) -> None:
        if max_chars < 1 or overlap < 0 or overlap >= max_chars:
            raise ValueError("Require max_chars > overlap >= 0")
        self.max_chars, self.overlap = max_chars, overlap

    def chunk(self, document: Document, records: list[SourceRecord]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for record in records:
            start = 0
            while start < len(record.text):
                end = min(start + self.max_chars, len(record.text))
                if end < len(record.text):
                    boundary = record.text.rfind(" ", start + self.max_chars // 2, end)
                    if boundary > start:
                        end = boundary
                location = record.location.model_copy(deep=True)
                location.text_start_offset = start
                location.text_end_offset = end
                if location.start_offset is not None:
                    location.start_offset += start
                    location.end_offset = location.start_offset + end - start
                    location.start_line = document.content.count("\n", 0, location.start_offset) + 1
                    location.end_line = document.content.count("\n", 0, location.end_offset) + 1
                # The complete original requirement stays available even for long fragments.
                text = record.text[start:end]
                identity = json.dumps(
                    [
                        "chunk-v1",
                        document.document_id,
                        document.content_hash,
                        document.version,
                        record.requirement_id,
                        record.section,
                        location.model_dump(),
                        text,
                    ],
                    sort_keys=True,
                )
                chunks.append(
                    Chunk(
                        chunk_id="chk-" + hashlib.sha256(identity.encode()).hexdigest()[:32],
                        document_id=document.document_id,
                        filename=document.filename,
                        document_title=document.title,
                        document_version=document.version,
                        requirement_id=record.requirement_id,
                        section=record.section,
                        text=text,
                        original_text=record.text,
                        location=location,
                        structured_fields=record.structured_fields,
                        extraction_warnings=record.extraction_warnings,
                    )
                )
                if end == len(record.text):
                    break
                start = max(start + 1, end - self.overlap)
        return chunks
