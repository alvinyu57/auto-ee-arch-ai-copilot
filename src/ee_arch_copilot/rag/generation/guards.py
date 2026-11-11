"""Conservative English checks, never semantic entailment or engineering validation."""

import re
from decimal import Decimal

from ee_arch_copilot.rag.models import Chunk

VERIFICATION_CLAIM = re.compile(
    r"\b(?:architecture|system|vehicle|design|checks?|validation)\b[^.!?\n]{0,120}"
    r"\b(?:pass(?:ed)?|compl(?:ies|iant)|meets?\s+(?:all\s+)?(?:\w+\s+){0,4}requirements?)\b"
    r"|\b(?:verified|validated|certified)\b[^.!?\n]{0,80}"
    r"\b(?:architecture|compliance|latency|requirements?)\b",
    re.I,
)
QUANTITY = re.compile(r"\b(\d+(?:\.\d+)?)\s*(ms|µs|us|ns|s|mbps|gbps|mhz|hz)\b", re.I)


def conflicting_source_indices(chunks: list[Chunk]) -> list[int]:
    """Flag equal statement templates with different quantities in equal units.

    This detects potential conflicts only; no unit conversion, negation, applicability,
    paraphrase or precedence reasoning is attempted. Distinct scopes stay distinct.
    """
    groups: dict[str, list[tuple[int, tuple[Decimal, ...]]]] = {}
    seen: set[tuple[str, str | None, str]] = set()
    for index, chunk in enumerate(chunks):
        identity = (chunk.document_id, chunk.requirement_id, chunk.original_text)
        if not chunk.requirement_id or identity in seen:
            continue
        seen.add(identity)
        text = chunk.original_text
        text = text.replace(chunk.requirement_id, "", 1).lstrip(" :*#-\n")
        values = tuple(Decimal(match.group(1)) for match in QUANTITY.finditer(text))
        if not values:
            continue
        template = QUANTITY.sub(lambda match: "<quantity> " + match.group(2).casefold(), text)
        template = " ".join(template.casefold().split())
        groups.setdefault(template, []).append((index, values))
    return sorted(
        {
            index
            for group in groups.values()
            if len({values for _, values in group}) > 1
            for index, _ in group
        }
    )
