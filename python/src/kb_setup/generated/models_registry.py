# Copyright (c) 2026 Raymond Manaloto
"""Generated model-registry contract; edit its schema and rerun kb-codegen."""

from enum import StrEnum
from typing import Annotated, Literal

from msgspec import Meta
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


class Status(StrEnum):
    """Generated source-group enumeration."""

    ADOPTED = "adopted"
    ACKNOWLEDGED = "acknowledged"


class Effort(StrEnum):
    """Generated source-group enumeration."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class AgentEffort(StrEnum):
    """Generated source-group enumeration."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    SPAWN = "spawn"


class Known(Struct):
    """Generated source-group contract type."""

    status: Status
    family: str
    reason: str


class Pin(Struct):
    """Generated source-group contract type."""

    slug: str
    effort: Effort


class Role(Struct):
    """Generated source-group contract type."""

    role: str
    effort: Effort
    slug: str


class Agent(Struct):
    """Generated source-group contract type."""

    role: str
    effort: AgentEffort
    authored: bool


class Codex(Struct):
    """Generated source-group contract type."""

    pins: dict[str, Pin]
    dispatch: dict[str, Role]
    agents: dict[str, Agent]
    config_fallback: Role
    launch_agents: Annotated[
        dict[str, str],
        Meta(description="Claude wrappers that launch Codex; separate from its TOML roster"),
    ]
    known: dict[str, Known]


class AgyPin(Struct):
    """Generated source-group contract type."""

    slug: str


class AgyRole(Struct):
    """Generated source-group contract type."""

    role: str
    slug: str


class Agy(Struct):
    """Generated source-group contract type."""

    pins: dict[str, AgyPin]
    dispatch: dict[str, AgyRole]
    known: dict[str, Known]


class Pins(Struct):
    """Generated source-group contract type."""

    fallback: list[str]
    subagent: list[str]


class Claude(Struct):
    """Generated source-group contract type."""

    aliases: list[str]
    pins: Pins
    api: dict[str, str | list[str]]
    known: dict[str, Known]


class Registry(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    codex: Codex
    agy: Agy
    claude: Claude
    registry_source: str
    registry_sha256: str
