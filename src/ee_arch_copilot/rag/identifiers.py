"""Bounded identifier hints; these are diagnostics, not a universal ID grammar."""

import re

IDENTIFIER_HINT = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[-_:][A-Za-z0-9]+)*[-_:]\d+\b")


def mentioned_identifiers(text: str, pattern: str, known_ids: set[str]) -> set[str]:
    mentions = {match.group(0) for match in re.finditer(pattern, text, re.I)}
    mentions.update(IDENTIFIER_HINT.findall(text))
    # JSON allows arbitrary IDs. Recognize known spellings and numeric variants of
    # their family, escaping all punctuation rather than treating IDs as regexes.
    for identifier in known_ids:
        parts = re.split(r"(\d+)", identifier)
        family = "".join(r"\d+" if part.isdigit() else re.escape(part) for part in parts)
        mentions.update(
            match.group(0) for match in re.finditer(r"(?<!\w)(?:" + family + r")(?!\w)", text, re.I)
        )
    return mentions
