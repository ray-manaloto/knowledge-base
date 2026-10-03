# Copyright (c) 2026 Raymond Manaloto
"""Generated model-registry contract; edit its schema and rerun kb-codegen."""

from enum import StrEnum

from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


class Vendor(StrEnum):
    """Generated source-group enumeration."""

    CODEX = "codex"
    AGY = "agy"
    CLAUDE = "claude"


class Verdict(StrEnum):
    """Generated source-group enumeration."""

    OK = "ok"
    DRIFT = "drift"
    INVALID = "invalid"
    NOT_CHECKED = "not_checked"


class FeedStatus(StrEnum):
    """Generated source-group enumeration."""

    LIVE = "live"
    BUNDLED = "bundled"
    UNREADABLE = "unreadable"
    SHAPE_BROKEN = "shape_broken"


class OverlayStatus(StrEnum):
    """Generated source-group enumeration."""

    READ = "read"
    UNREADABLE = "unreadable"
    NOT_NEEDED = "not_needed"


class VendorReport(Struct):
    """Generated source-group contract type."""

    vendor: Vendor
    verdict: Verdict
    feed: FeedStatus
    overlay: OverlayStatus
    invalid_pins: dict[str, str]
    unknown_slugs: list[str]
    retiring: list[str]
    findings: list[str]
    current_pins: dict[str, str]
    display_names: dict[str, str]
    agent_roles: dict[str, str]


class TrustStatus(StrEnum):
    """Generated source-group enumeration."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNREADABLE = "unreadable"


class TrustResult(Struct):
    """Generated source-group contract type."""

    status: TrustStatus
    path: str
    finding: str


class LaunchDecision(Struct):
    """Generated source-group contract type."""

    allow: bool
    reason: str


class RegistryReport(Struct):
    """Generated source-group contract type."""

    vendors: list[VendorReport]
    registry_source: str
    registry_sha256: str
    resolved_model: str | None
    disabled_by_baseline: bool
    checked_at: str
    overrides: list[str]
