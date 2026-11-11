import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ee_arch_copilot.rag.ingestion.loader import load_file, normalize_document
from ee_arch_copilot.rag.ingestion.parser import RequirementParser
from ee_arch_copilot.rag.models import DocumentInput
from ee_arch_copilot.rag.service import KnowledgeService


def test_markdown_preserves_sections_and_source(source: DocumentInput) -> None:
    document = normalize_document(source)
    records = RequirementParser().parse(document)
    assert [record.requirement_id for record in records] == [
        "REQ-ETH-001",
        "REQ-ETH-002",
        "REQ-SOA-015",
    ]
    assert document.title == "Synthetic Ethernet"
    assert records[0].section == "Synthetic Ethernet / Gateway"
    for record in records:
        assert (
            document.content[record.location.start_offset : record.location.end_offset]
            == record.text
        )
        assert record.location.start_line is not None
    assert records[-1].section == "Synthetic Ethernet / Discovery"


def test_json_fields_and_pointer() -> None:
    raw = {
        "title": "Structured",
        "version": 2,
        "requirements": [
            {
                "id": "custom:007",
                "description": "Gateway shall connect.",
                "components": ["gateway"],
                "constraints": {"bandwidth": 1000},
                "section": "Ethernet",
            },
            {"text": "No explicit ID is provided."},
        ],
    }
    document = normalize_document(
        DocumentInput(filename="req.json", source_type="json", content=json.dumps(raw))
    )
    records = RequirementParser().parse(document)
    assert document.title == "Structured" and document.version == "2"
    assert records[0].requirement_id == "custom:007"
    assert records[0].structured_fields["constraints"] == {"bandwidth": 1000}
    assert records[0].structured_fields["components"] == ["gateway"]
    assert records[0].location.json_pointer == "/requirements/0/description"
    assert records[1].requirement_id is None
    array = document.model_copy(update={"content": '[{"statement":"standalone array"}]'})
    assert RequirementParser().parse(array)[0].location.json_pointer == "/0/statement"


def test_duplicate_update_and_reindex(indexed: KnowledgeService, source: DocumentInput) -> None:
    chunks = indexed.store.chunks()
    timestamp = indexed.store.documents()[0].ingestion_timestamp
    assert indexed.ingest(source).status == "unchanged"
    assert indexed.store.documents()[0].ingestion_timestamp == timestamp
    assert indexed.store.collection.count() == len(chunks) == 3
    updated = source.model_copy(
        update={"version": "2.0", "content": "REQ-ETH-003: Radar interface 100BASE-T1."}
    )
    assert indexed.ingest(updated).status == "replaced"
    assert indexed.store.collection.count() == 1
    assert indexed.store.get_chunk(chunks[0].chunk_id) is None
    assert indexed.reindex("ethernet").status == "replaced"
    assert indexed.store.collection.count() == 1
    with pytest.raises(KeyError):
        indexed.reindex("missing")


@pytest.mark.parametrize(
    "content", ["{", "{}", "[]", '["text"]', '[{"id": 2,"text":"x"}]', '[{"id":"x"}]']
)
def test_invalid_json_rejected(service: KnowledgeService, content: str) -> None:
    with pytest.raises(ValueError):
        service.ingest(DocumentInput(filename="bad.json", source_type="json", content=content))
    assert service.store.documents() == []


@pytest.mark.parametrize(
    "filename", ["/etc/passwd", "../r.md", "C:\\secret.txt", "..", "file\x00.md"]
)
def test_no_paths(filename: str) -> None:
    with pytest.raises(ValidationError):
        DocumentInput(filename=filename, source_type="text", content="text")


@pytest.mark.parametrize("content", ["", "  \n"])
def test_empty_content(content: str) -> None:
    with pytest.raises(ValidationError):
        DocumentInput(filename="empty.txt", source_type="text", content=content)


def test_no_metadata_credentials() -> None:
    with pytest.raises(ValidationError, match="credentials"):
        DocumentInput(
            filename="x.txt",
            source_type="text",
            content="x",
            metadata={"nested": [{"api_key": "not-a-real-key"}]},
        )


def test_plain_text_and_configurable_ids() -> None:
    document = normalize_document(
        DocumentInput(
            filename="x.txt",
            source_type="text",
            content="Context.\r\n\r\nENG_42: Requirement.\r\n",
        )
    )
    records = RequirementParser(r"ENG_\d+").parse(document)
    assert records[0].requirement_id is None and records[0].text == "Context."
    assert records[1].requirement_id == "ENG_42"
    assert "\r" not in document.content
    assert not document.document_id.startswith("/")


def test_local_loader_and_pdf(tmp_path: Path) -> None:
    text_path = tmp_path / "source.txt"
    text_path.write_text("Local source.")
    assert load_file(text_path).content == "Local source."
    unsupported = tmp_path / "x.csv"
    with pytest.raises(ValueError, match="Supported formats"):
        load_file(unsupported)
    large = tmp_path / "large.txt"
    with large.open("wb") as handle:
        handle.truncate(10_000_001)
    with pytest.raises(ValueError, match="10 MB"):
        load_file(large)
    pdf = tmp_path / "source.pdf"
    writer = PdfWriter()
    for number in (1, 2):
        page = writer.add_blank_page(width=300, height=300)
        stream = DecodedStreamObject()
        stream.set_data(
            f"BT /F1 12 Tf 30 200 Td (REQ-PDF-00{number}: Gateway text.) Tj ET".encode()
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        )
                    }
                )
            }
        )
    writer.write(pdf)
    document = normalize_document(load_file(pdf))
    assert [record.location.page for record in RequirementParser().parse(document)] == [1, 2]
    blank = PdfWriter()
    blank.add_blank_page(width=300, height=300)
    blank.write(pdf)
    with pytest.raises(ValueError, match="OCR"):
        load_file(pdf)
    pdf.write_bytes(b"not a PDF")
    with pytest.raises(ValueError, match="cannot be read"):
        load_file(pdf)


def test_heading_only_rejected(service: KnowledgeService) -> None:
    with pytest.raises(ValueError, match="no indexable"):
        service.ingest(DocumentInput(filename="x.md", source_type="markdown", content="# Title"))
