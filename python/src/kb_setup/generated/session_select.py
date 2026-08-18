# Copyright (c) 2026 Raymond Manaloto
"""Generated session-selection models; edit the schema and rerun the generator."""

from enum import Enum
from typing import Annotated, Literal

from msgspec import UNSET, Meta, UnsetType
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


class ResolvedBy(Enum):
    """Generated source-group enumeration."""

    explicit = "explicit"
    graph_first_state = "graph-first-state"
    newest_birthtime = "newest-birthtime"
    window = "window"


class Window(Struct):
    """Generated source-group contract type."""

    since: str | None
    until: str | None


class TimeSource(Enum):
    """Generated source-group enumeration."""

    birthtime = "birthtime"
    content = "content"


class SessionRecord(Struct):
    """Generated source-group contract type."""

    path: Annotated[str, Meta(min_length=1)]
    session_id: Annotated[str, Meta(max_length=128, min_length=1)]
    started_at: Annotated[
        str, Meta(description="When the session STARTED, ISO 8601 UTC. Birthtime, not mtime.")
    ]
    last_written: Annotated[
        str, Meta(description="mtime, ISO 8601 UTC; beside started_at so a resume stays visible.")
    ]
    bytes: Annotated[int, Meta(ge=0)]
    time_source: Annotated[
        TimeSource,
        Meta(description="Which clock set started_at: the filesystem, or the file's own record."),
    ]


class SessionSelection(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    selector: Annotated[
        str,
        Meta(description="The selector as invoked, echoed verbatim.", max_length=256, min_length=1),
    ]
    window: Annotated[
        Window, Meta(description="Echoed even for a non-time selector, with null bounds.")
    ]
    resolved_by: Annotated[
        ResolvedBy,
        Meta(description="Which route produced this set; --current has two that can disagree."),
    ]
    sessions: Annotated[
        list[SessionRecord],
        Meta(
            description="Never empty; an empty resolution is a refusal, not an empty list.",
            min_length=1,
        ),
    ]
    caveat: (
        Annotated[
            str,
            Meta(
                description="The resolution is sound but contested; present means read it.",
                max_length=512,
            ),
        ]
        | UnsetType
    ) = UNSET
