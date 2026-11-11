"""Keep technical identifiers whole while also indexing their searchable components."""

import re

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "be",
        "for",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "with",
        "which",
        "what",
        "how",
        "find",
        "explain",
        "requirements",
        "requirement",
        "related",
        "define",
        "specify",
        "shall",
        "must",
        "support",
        "at",
        "least",
        "between",
    ]
)
TOKEN = re.compile(r"[\w]+(?:[./-][\w]+)*", re.UNICODE)


def tokenize(text: str) -> list[str]:
    words = TOKEN.findall(text.casefold())
    tokens: list[str] = []
    for word in words:
        if word not in STOPWORDS:
            tokens.append(word)
            parts = re.split(r"[./-]", word)
            if len(parts) > 1:
                tokens.extend(part for part in parts if part and part not in STOPWORDS)
    tokens.extend(
        match.group(0).casefold()
        for match in re.finditer(r"\b(?:IEEE\s+802\.\w+|VLAN\s+\d+)\b", text, re.I)
    )
    return tokens
