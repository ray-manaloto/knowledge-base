# Copyright (c) 2026 Raymond Manaloto
"""Generated codex-review-evidence models; edit the schema and rerun the generator."""

from enum import Enum
from typing import Annotated, Literal

from msgspec import Meta
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


type TurnModel = Annotated[str, Meta(max_length=128)]


class OutcomeKind(Enum):
    """Generated source-group enumeration."""

    resolved = "resolved"
    unavailable = "unavailable"
    error = "error"


class ReviewCompletion(Enum):
    """Generated source-group enumeration."""

    complete = "complete"
    aborted = "aborted"
    unknown = "unknown"


class UnavailableReason(Enum):
    """Generated source-group enumeration."""

    no_output_flag = "no-output-flag"
    banner_session_id_unavailable = "banner-session-id-unavailable"
    codex_home_unresolvable = "codex-home-unresolvable"
    no_matching_child_rollout = "no-matching-child-rollout"
    ambiguous_child_rollout = "ambiguous-child-rollout"
    no_turn_context = "no-turn-context"
    missing_model_field = "missing-model-field"
    unsupported_schema_version = "unsupported-schema-version"


class ErrorKind(Enum):
    """Generated source-group enumeration."""

    resolver_io_error = "resolver-io-error"
    resolver_crashed = "resolver-crashed"


class CodexReviewEvidence(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    adapter_version: Literal[1]
    attempt_id: Annotated[str, Meta(max_length=64, min_length=1)]
    codex_home: Annotated[str, Meta(max_length=1024, min_length=1)]
    cli_version: Annotated[str, Meta(max_length=64)]
    requested_model: Annotated[str, Meta(max_length=128)] | None
    requested_effort: Annotated[str, Meta(max_length=64)] | None
    base_ref: Annotated[str, Meta(max_length=256, min_length=1)]
    subprocess_rc: int
    timed_out: bool
    output_path: Annotated[str, Meta(max_length=4096)] | None
    outcome: OutcomeKind
    parent_session_id: Annotated[str, Meta(max_length=64)] | None
    child_rollout_path: Annotated[str, Meta(max_length=4096)] | None
    turn_models: list[TurnModel]
    resolved_model: Annotated[str, Meta(max_length=128)] | None
    review_completion: ReviewCompletion | None
    unavailable_reason: UnavailableReason | None
    error_kind: ErrorKind | None
    diagnostics: Annotated[str, Meta(max_length=4096)] | None
