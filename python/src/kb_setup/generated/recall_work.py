# Copyright (c) 2026 Raymond Manaloto
"""Generated recall-work models; edit the schema and rerun the generator."""

from enum import Enum
from typing import Annotated, Literal

from msgspec import UNSET, Meta, UnsetType
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


type Stem = Annotated[str, Meta(min_length=1)]


class ProbeName(Enum):
    """Generated source-group enumeration."""

    tracked_files = "tracked_files"
    artifact_pages = "artifact_pages"
    branches = "branches"
    worktrees = "worktrees"
    issues = "issues"
    plans = "plans"
    memory = "memory"


class ProbeStatus(Enum):
    """Generated source-group enumeration."""

    ran = "ran"
    could_not_ask = "could_not_ask"
    skipped = "skipped"


class Where(Enum):
    """Generated source-group enumeration."""

    local = "local"
    remote = "remote"
    both = "both"


class Verdict(Enum):
    """Generated source-group enumeration."""

    merged = "merged"
    live = "live"
    unverified = "unverified"
    current = "current"


class Repo(Struct):
    """Generated source-group contract type."""

    name: Annotated[str, Meta(min_length=1)]
    path: Annotated[str, Meta(min_length=1)]
    base: Annotated[
        str,
        Meta(
            description="Measured against origin/HEAD, else origin/main, else main.", min_length=1
        ),
    ]
    slug: (
        Annotated[str, Meta(description="owner/repo from the origin URL; null when not GitHub.")]
        | None
    )


class Hit(Struct):
    """Generated source-group contract type."""

    ref: Annotated[
        str,
        Meta(description="A path, a branch name, an issue number, or a memory file.", min_length=1),
    ]
    summary: str
    repo: str | UnsetType = UNSET
    state: str | UnsetType = UNSET
    date: str | UnsetType = UNSET
    score: float | UnsetType = UNSET


class Branch(Struct):
    """Generated source-group contract type."""

    repo: Annotated[str, Meta(min_length=1)]
    name: Annotated[str, Meta(min_length=1)]
    where: Where
    tip: Annotated[str, Meta(min_length=1)]
    date: str
    subject: str
    ahead: Annotated[int, Meta(ge=0)]
    behind: Annotated[int, Meta(ge=0)]
    verdict: Verdict
    topic_match: bool
    merged_pr: (
        Annotated[int, Meta(description="The merged PR whose head was this branch, if any.", ge=1)]
        | UnsetType
    ) = UNSET


class Probe(Struct):
    """Generated source-group contract type."""

    name: ProbeName
    status: ProbeStatus
    examined: Annotated[
        int, Meta(description="How many items were looked at: the denominator.", ge=0)
    ]
    matched: Annotated[int, Meta(ge=0)]
    detail: Annotated[
        str, Meta(description="The bound the probe ran under, or why it could not ask.")
    ]
    hits: list[Hit]


class RecallWork(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    topic: Annotated[
        str,
        Meta(description="The topic as invoked, echoed verbatim.", max_length=512, min_length=1),
    ]
    stems: Annotated[
        list[Stem], Meta(description="The prefix stems searched for; a spelling is a bound.")
    ]
    generated_at: Annotated[str, Meta(description="When the run happened, ISO 8601 UTC.")]
    repos: Annotated[
        list[Repo],
        Meta(description="Every checkout examined; an unmeasurable one is absent.", min_length=1),
    ]
    probes: Annotated[list[Probe], Meta(min_length=1)]
    branches: Annotated[
        list[Branch], Meta(description="Every branch measured, topic-matching or not.")
    ]
    matched_total: Annotated[int, Meta(description="Topic matches over the probes that ran.", ge=0)]
    report_path: Annotated[
        str, Meta(description="Where the markdown report was written.", min_length=1)
    ]
