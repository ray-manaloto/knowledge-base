# Copyright (c) 2026 Raymond Manaloto
"""Generated model-registry contract; edit its schema and rerun kb-codegen."""

from enum import StrEnum

from msgspec import Struct as _Struct


class Struct(_Struct):
    """Generated source-group contract type."""


class FeedStatus(StrEnum):
    """Generated source-group enumeration."""

    LIVE = "live"
    BUNDLED = "bundled"
    UNREADABLE = "unreadable"
    SHAPE_BROKEN = "shape_broken"


class VendorFeed(Struct):
    """Generated source-group contract type."""

    status: FeedStatus
    slugs: list[str]
    findings: list[str]
    efforts: dict[str, list[str]]
    retirements: dict[str, str]
    upgrades: dict[str, str]
    display_names: dict[str, str]
    duration_s: float
    hidden_slugs: list[str]


class ReasoningLevel(Struct):
    """Generated source-group contract type."""

    effort: str


class Upgrade(Struct):
    """Generated source-group contract type."""

    model: str
    retirement_at: str


class CodexModel(Struct):
    """Generated source-group contract type."""

    slug: str
    visibility: str
    upgrade: Upgrade | None
    supported_reasoning_levels: list[ReasoningLevel]


class CodexCatalog(Struct):
    """Generated source-group contract type."""

    models: list[CodexModel]


class Feeds(Struct):
    """Generated source-group contract type."""

    vendors: dict[str, VendorFeed]
    resolved_model: str | None
    plugin_options: dict[str, str]
    disabled_by_baseline: bool
    overrides: list[str]
