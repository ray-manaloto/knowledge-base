# Copyright (c) 2026 Raymond Manaloto
r"""Python consumer of the guard-policy schema (ticket G02, #755).

Re-exports the generated ``ProtectedPathSuffix`` enum's VALUES as
``PROTECTED_SUFFIXES`` and mirrors the TypeScript `isProtectedPath` predicate
(`.claude/mods/kb-settings-guard/hooks/register.ts`) as :func:`is_protected_path`:
exact match, or a `/`-prefixed suffix match, on a `\\` -> `/` normalised path.

🔴 **Iterates the enum's VALUES, never its member NAMES.** Measured this
session: `datamodel-codegen` mangles member names for identifier safety — a
leading dot becomes a `field_` prefix, so `.claude/settings.json` becomes
`field_claude_settings_json` — and two names that collide are silently
suffixed with no error and no warning. Values round-trip byte-exact and
nothing is dropped (every schema entry in, none dropped, none colliding — the
COUNT is derived from the schema at test time, never hardcoded here or in the
tests; a hardcoded number is the exact defect F2/M2 found and fixed), so the
schema keeps authority over the *values*, which is the security-relevant
half. A renamed member still fails LOUDLY at `ty check`
(`error[unresolved-attribute]`), which is what makes the mangling survivable
rather than dangerous — but there is no TypeScript type checker in this repo
at all, so the generated `.ts` array's correctness rests entirely on
`mise run kb-guard-codegen-check`.

🔴 **THIS MODULE IS DELIBERATELY UNWIRED.** Nothing in `kb_setup.hook_guard`
imports it, and nothing should, without also updating
`docs/guards/inventory.toml` — `kb_setup.guard_inventory` computes guard
membership by AST reachability from `hook_guard.py`, so importing this module
from there silently turns it into an undeclared guard and reds a gate that
shipped before this ticket. Wiring this module into an actual enforcement path
is a later ticket's job, with its own inventory update.
"""

from __future__ import annotations

from enum import Enum

from kb_setup.generated.guard_policy import ProtectedPathSuffix


def _protected_suffixes_from(enum_cls: type[Enum]) -> tuple[str, ...]:
    """Build a protected-suffix tuple from an enum's VALUES, never its NAMES.

    Factored out of the module-level assignment below so a test can feed it a
    hostile enum whose member names and values deliberately differ (F8) — that
    is what proves this reads `.value`, not `.name`, rather than merely
    matching today's five (now nine) literal strings.
    """
    return tuple(member.value for member in enum_cls)


PROTECTED_SUFFIXES: tuple[str, ...] = _protected_suffixes_from(ProtectedPathSuffix)
"""The settings-guard's protected-path policy, in schema order.

Built from `ProtectedPathSuffix.value`, never from a member's (mangled) name —
see the module docstring.
"""


def _normalize(path: str) -> str:
    r"""`\` -> `/`, then collapse `//`, `/./` and lexical `..` segments.

    🔴 **THIS IS A DELIBERATE DIVERGENCE FROM `register.ts`, AND IT IS FILED.**
    The round-2 cold lane on `c1932522` found the plain `\\`->`/` form fails
    OPEN on the equivalent spellings of a protected path: `.claude/./settings.json`
    and `.claude//settings.json` both returned False while `.claude/settings.json`
    and `/a/b/.claude/settings.json` returned True. Absence of a match is the
    ALLOW signal in this guard, so a spelling the matcher does not recognise is a
    hole, not a miss.

    `register.ts:87` still carries the unfixed form and is FROZEN for this ticket
    (`guard_inventory`'s anchored regexes parse it). So the two implementations
    are **no longer behaviourally identical**, which the docstring below used to
    claim outright. The TS half must land before #757 registers the mod — that is
    the point at which the hole becomes live — and it is recorded there.

    Lexical, never filesystem: no `resolve()`, no symlink following, no IO. That
    keeps it total and side-effect-free, and it is strictly more protective than
    not normalising. A symlinked alias reaching the same file is still unmatched,
    which `register.ts` already documents as a known limit.
    """
    parts: list[str] = []
    for segment in path.replace("\\", "/").split("/"):
        if segment in {"", "."}:
            continue
        if segment == ".." and parts and parts[-1] != "..":
            parts.pop()
            continue
        parts.append(segment)
    collapsed = "/".join(parts)
    return f"/{collapsed}" if path.startswith(("/", "\\")) else collapsed


def is_protected_path(path: str) -> bool:
    r"""Is `path` one of `PROTECTED_SUFFIXES`, exactly or as a path-segment suffix?

    Mirrors `isProtectedPath` in `register.ts` **except for normalisation**,
    which is stricter here — see `_normalize` above, which closes a fail-open the
    TypeScript side still has and which is filed against #757. Otherwise
    identical: a normalised path matches a suffix either exactly, or when it
    ends with `/` + that suffix. A bare substring match (no
    leading `/` and no exact-path check) is deliberately excluded, the same
    false-positive class `register.ts` already documents avoiding — matching
    `tool.call`'s serialized event text rather than a real path segment.
    """
    normalized = _normalize(path)
    return any(
        normalized == suffix or normalized.endswith(f"/{suffix}") for suffix in PROTECTED_SUFFIXES
    )
