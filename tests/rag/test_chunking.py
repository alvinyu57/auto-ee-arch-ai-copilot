import json

import pytest

from ee_arch_copilot.rag.ingestion.chunker import RequirementChunker
from ee_arch_copilot.rag.ingestion.loader import normalize_document
from ee_arch_copilot.rag.ingestion.parser import RequirementParser
from ee_arch_copilot.rag.models import DocumentInput


def test_short_requirements_independently_chunked(source: DocumentInput) -> None:
    document = normalize_document(source)
    records = RequirementParser().parse(document)
    chunks = RequirementChunker().chunk(document, records)
    assert len(chunks) == 3
    assert {chunk.requirement_id for chunk in chunks} == {
        "REQ-ETH-001",
        "REQ-ETH-002",
        "REQ-SOA-015",
    }
    assert chunks == RequirementChunker().chunk(document, records)
    assert all(chunk.text == chunk.original_text for chunk in chunks)


def test_long_requirement_overlap_and_offsets() -> None:
    content = "REQ-LONG-001:\n" + "A gateway interface shall preserve timing.\n" * 30
    document = normalize_document(
        DocumentInput(filename="long.txt", source_type="text", content=content)
    )
    parser = RequirementParser()
    chunks = RequirementChunker(150, 25).chunk(document, parser.parse(document))
    assert len(chunks) > 5
    for chunk in chunks:
        assert len(chunk.text) <= 150
        assert chunk.requirement_id == "REQ-LONG-001"
        assert chunk.original_text == content.rstrip()
        assert content[chunk.location.start_offset : chunk.location.end_offset] == chunk.text
    assert chunks[0].text[-25:] == chunks[1].text[:25]
    assert chunks[-1].location.end_offset == len(content.rstrip())
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    # Long unbroken text still makes progress and preserves every character.
    unbroken = document.model_copy(update={"content": "X" * 500})
    assert len(RequirementChunker(100, 0).chunk(unbroken, parser.parse(unbroken))) == 5


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (10, 10), (10, -1)])
def test_invalid_chunk_settings(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        RequirementChunker(size, overlap)


def test_long_json_repeated_text_has_unique_fragments() -> None:
    document = normalize_document(
        DocumentInput(
            filename="long.json",
            source_type="json",
            content=json.dumps([{"id": "REQ-JSON-001", "text": "Gateway interface. " * 100}]),
        )
    )
    chunks = RequirementChunker(150, 25).chunk(document, RequirementParser().parse(document))
    assert len(chunks) > 5
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    assert all(chunk.location.json_pointer == "/0/text" for chunk in chunks)
    assert chunks[0].location.text_end_offset is not None
    assert chunks[1].location.text_start_offset == chunks[0].location.text_end_offset - 25
