# Copyright (c) 2026 Raymond Manaloto
"""Generated worktree-readiness models; edit the schema and rerun the generator."""

from enum import Enum
from typing import Annotated, Literal

from msgspec import UNSET, Meta, UnsetType
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


class WorktreeItemStatus(Enum):
    """Generated source-group enumeration."""

    created = "created"
    already_present = "already-present"
    skipped = "skipped"


class WorktreeItem(Struct):
    """Generated source-group contract type."""

    name: Annotated[
        str,
        Meta(
            description="The repo-relative path this row describes, e.g. sources/graphify.",
            min_length=1,
        ),
    ]
    status: WorktreeItemStatus
    detail: (
        Annotated[str, Meta(description="The copied clone's HEAD, or why it was skipped.")]
        | UnsetType
    ) = UNSET


class WorktreeReadyReport(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    target: Annotated[
        str,
        Meta(description="The worktree this run made ready, as an absolute path.", min_length=1),
    ]
    donor: Annotated[
        str,
        Meta(
            description="The main checkout the clones and graph files were copied from.",
            min_length=1,
        ),
    ]
    donor_graph: Annotated[
        str,
        Meta(
            description='The donor\'s graph.json identity (path, size, mtime), or "absent".',
            min_length=1,
        ),
    ]
    items: Annotated[
        list[WorktreeItem],
        Meta(description="One row per required clone and per required graph file."),
    ]
