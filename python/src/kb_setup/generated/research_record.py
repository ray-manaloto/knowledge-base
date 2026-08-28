# Copyright (c) 2026 Raymond Manaloto
"""Generated research-record models; edit the schema and rerun the generator."""

from enum import StrEnum
from typing import Annotated

from msgspec import Meta
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


class Tier(StrEnum):
    """Generated source-group enumeration."""

    cheap = "cheap"
    expensive = "expensive"


class Kind(StrEnum):
    """Generated source-group enumeration."""

    issue = "issue"
    pr = "pr"


type UtcTimestamp = Annotated[
    str, Meta(pattern="^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
]


class Hit(Struct):
    """Generated source-group contract type."""

    url: Annotated[str, Meta(pattern="^https://")]
    title: Annotated[str, Meta(max_length=512, min_length=0)]
    snippet: Annotated[str, Meta(max_length=600, min_length=0)]
    date: UtcTimestamp
    kind: Kind


class Arm(Struct):
    """Generated source-group contract type."""

    kind: Kind
    command: Annotated[str, Meta(max_length=1024, min_length=1)]
    result: str
    discriminates: bool


class Null(Struct):
    """Generated source-group contract type."""

    arms: Annotated[list[Arm], Meta(max_length=2, min_length=1)]


class AdapterRecord(Struct):
    """Generated source-group contract type."""

    adapter: str
    tier: Tier
    question: Annotated[str, Meta(max_length=512, min_length=1)]
    command: Annotated[str, Meta(max_length=1024, min_length=1)]
    has_issues: bool
    has_discussions: bool
    ran_at: UtcTimestamp
    total_count: Annotated[int, Meta(ge=0)]
    hits: Annotated[list[Hit], Meta(max_length=60)]
    null_result: Null | None
