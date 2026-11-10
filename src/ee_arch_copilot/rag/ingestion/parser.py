import json
import re
from typing import cast

from pydantic import JsonValue

from ee_arch_copilot.core.settings import DEFAULT_REQUIREMENT_PATTERN
from ee_arch_copilot.rag.models import Document, SourceLocation, SourceRecord


class RequirementParser:
    def __init__(self, requirement_pattern: str = DEFAULT_REQUIREMENT_PATTERN) -> None:
        self.pattern = re.compile(requirement_pattern)
        self.start_pattern = re.compile(
            r"^\s*(?:[-*+]\s+|#{1,6}\s+)?(?:\*\*)?(?P<id>" + requirement_pattern + r")(?=\s|:|\*|$)"
        )

    def parse(self, document: Document) -> list[SourceRecord]:
        if document.source_type == "json":
            return self._json(document.content)
        return self._text(document)

    def _json(self, content: str) -> list[SourceRecord]:
        data = json.loads(content)
        prefix = ""
        if isinstance(data, dict) and "requirements" in data:
            prefix = "/requirements"
            data = data["requirements"]
        if not isinstance(data, list) or not data:
            raise ValueError(
                "JSON must be a nonempty requirement array or object with requirements"
            )
        records: list[SourceRecord] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError("Each JSON requirement must be an object")
            field = next(
                (
                    key
                    for key in ("text", "description", "statement", "content")
                    if isinstance(item.get(key), str) and item[key].strip()
                ),
                None,
            )
            if field is None:
                raise ValueError("JSON requirement needs text, description, statement, or content")
            identifier = item.get("requirement_id", item.get("id"))
            if identifier is not None and (
                not isinstance(identifier, str) or not identifier.strip()
            ):
                raise ValueError("Requirement ID must be a nonempty string when present")
            section = item.get("section")
            records.append(
                SourceRecord(
                    requirement_id=identifier,
                    section=section if isinstance(section, str) else None,
                    text=item[field],
                    location=SourceLocation(json_pointer=f"{prefix}/{index}/{field}"),
                    structured_fields=cast(dict[str, JsonValue], item),
                )
            )
        return records

    def _text(self, document: Document) -> list[SourceRecord]:
        content = document.content
        lines = content.splitlines(keepends=True)
        records: list[SourceRecord] = []
        headings: dict[int, str] = {}
        section: str | None = None
        record_section: str | None = None
        requirement_id: str | None = None
        start: int | None = None
        offset = 0

        def flush(end: int) -> None:
            if start is None:
                return
            left = start
            while left < end and content[left].isspace():
                left += 1
            while end > left and content[end - 1].isspace():
                end -= 1
            if left == end:
                return
            records.append(
                SourceRecord(
                    requirement_id=requirement_id,
                    section=record_section,
                    text=content[left:end],
                    location=SourceLocation(
                        start_offset=left,
                        end_offset=end,
                        start_line=content.count("\n", 0, left) + 1,
                        end_line=content.count("\n", 0, end) + 1,
                        page=content.count("\f", 0, left) + 1
                        if document.source_type == "pdf"
                        else None,
                    ),
                )
            )

        for line in lines:
            match = self.start_pattern.match(line)
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if "\f" in line:
                flush(offset)
                start = None
                requirement_id = None
            elif match:
                flush(offset)
                start, requirement_id, record_section = offset, match.group("id"), section
            elif heading and document.source_type == "markdown":
                flush(offset)
                depth = len(heading.group(1))
                headings = {key: value for key, value in headings.items() if key < depth}
                headings[depth] = heading.group(2)
                section = " / ".join(headings.values())
                start, requirement_id = None, None
            elif not line.strip() and requirement_id is None:
                flush(offset)
                start = None
            elif start is None and line.strip():
                start, record_section = offset, section
            offset += len(line)
        flush(len(content))
        if not records:
            raise ValueError("Document contains no indexable text")
        return records
