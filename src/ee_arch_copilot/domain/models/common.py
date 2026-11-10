"""Shared schema policies, identifiers, and explicit Mbps quantities."""

from collections import Counter
from collections.abc import Iterable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identifier = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
]
Name = Annotated[str, StringConstraints(min_length=1, max_length=256)]
NonNegativeMbps = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveMbps = Annotated[float, Field(gt=0, allow_inf_nan=False)]
VlanId = Annotated[int, Field(strict=True, ge=1, le=4094)]


class DomainModel(BaseModel):
    """Reject unknown fields, nonfinite numbers, and whitespace-only names."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False, validate_default=True
    )


def ensure_unique(values: Iterable[str | int], label: str) -> None:
    duplicates = sorted(str(value) for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate {label}: {', '.join(duplicates)}")
