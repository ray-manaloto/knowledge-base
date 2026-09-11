# Copyright (c) 2026 Raymond Manaloto
"""Generated guard-inventory models; edit the schema and rerun the generator."""

from enum import Enum
from typing import Annotated

from msgspec import UNSET, Meta, UnsetType
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


type SemanticId = Annotated[
    str,
    Meta(
        description="A readable, dotted, semantic identity — …",
        pattern="^[a-z][a-z0-9-]*(\\.[a-z0-9][a-z0-9-]*)+$",
        title="SemanticId",
    ),
]


class OwnerKind(Enum):
    """Generated source-group enumeration."""

    repository = "repository"
    external_tool = "external-tool"
    claude_code_runtime = "claude-code-runtime"


class CurrentSurface(Enum):
    """Generated source-group enumeration."""

    classic_hook = "classic-hook"
    function_hook = "function-hook"
    non_hook_control = "non-hook-control"
    prose_only = "prose-only"
    support_module = "support-module"


class Disposition(Enum):
    """Generated source-group enumeration."""

    function_hook = "function-hook"
    classic_hook = "classic-hook"
    external_classic_hook = "external-classic-hook"
    non_hook_control = "non-hook-control"
    prose_only = "prose-only"
    support_module = "support-module"


class EvidenceKind(Enum):
    """Generated source-group enumeration."""

    measured_this_session = "measured-this-session"
    read_from_source = "read-from-source"
    inherited_unverified = "inherited-unverified"


class ReachedBy(Enum):
    """Generated source-group enumeration."""

    direct_registration = "direct-registration"
    hook_guard_dispatch = "hook-guard-dispatch"


class InvariantKind(Enum):
    """Generated source-group enumeration."""

    numbered = "numbered"
    subsection = "subsection"


class ScopeCase(Struct):
    """Generated source-group contract type."""

    tool: str
    path_scope: str | UnsetType = UNSET


class RegistrationSource(Struct):
    """Generated source-group contract type."""

    path: Annotated[str, Meta(description="`.claude/settings.json`, or the mod's register.ts.")]
    event: str
    matcher: str | UnsetType = UNSET
    if_condition: str | UnsetType = UNSET
    command: str | UnsetType = UNSET
    reviewed_timeout_seconds: Annotated[int, Meta(ge=1)] | UnsetType = UNSET


class GuardModule(Struct):
    """Generated source-group contract type."""

    id: SemanticId
    path: str
    reached_by: ReachedBy
    current_surface: CurrentSurface
    disposition: Disposition
    owner_kind: OwnerKind
    evidence: EvidenceKind
    invariant_ids: (
        Annotated[list[SemanticId], Meta(description="Invariants this module enforces.")]
        | UnsetType
    ) = UNSET
    note: str | UnsetType = UNSET


class InvariantLocator(Struct):
    """Generated source-group contract type."""

    anchor: Annotated[str, Meta(description="The `<!-- guard-programme: <id> -->` comment's id.")]
    reviewed_ordinal: Annotated[int, Meta(ge=1)] | UnsetType = UNSET
    reviewed_digest: (
        Annotated[
            str, Meta(description="sha256 of the normalised invariant body, first 16 hex chars.")
        ]
        | UnsetType
    ) = UNSET


class Invariant(Struct):
    """Generated source-group contract type."""

    id: SemanticId
    kind: InvariantKind
    headline: str
    current_surface: CurrentSurface
    disposition: Disposition
    locator: InvariantLocator
    evidence: EvidenceKind
    enforced_by: (
        Annotated[list[SemanticId], Meta(description="Guard modules enforcing it.")] | UnsetType
    ) = UNSET
    rationale: str | UnsetType = UNSET
    note: str | UnsetType = UNSET


class RegistrationState(Enum):
    """Generated source-group enumeration."""

    declared = "declared"
    enabled = "enabled"
    installed = "installed"
    exercised = "exercised"


class Registration(Struct):
    """Generated source-group contract type."""

    id: SemanticId
    current_surface: CurrentSurface
    disposition: Disposition
    owner_kind: OwnerKind
    source: RegistrationSource
    evidence: EvidenceKind
    state: RegistrationState
    owner_ref: (
        Annotated[str, Meta(description="The module or binary that actually implements it.")]
        | UnsetType
    ) = UNSET
    module_ids: (
        Annotated[list[SemanticId], Meta(description="Guard modules this registration reaches.")]
        | UnsetType
    ) = UNSET
    reviewed_scope_cases: list[ScopeCase] | UnsetType = UNSET
    rationale: (
        Annotated[
            str,
            Meta(
                description="REQUIRED in spirit for classic-hook and prose-only dispositions: a …"
            ),
        ]
        | UnsetType
    ) = UNSET
    note: str | UnsetType = UNSET


class GuardInventory(Struct):
    """Generated source-group contract type."""

    registrations: list[Registration]
    modules: list[GuardModule]
    invariants: list[Invariant]
