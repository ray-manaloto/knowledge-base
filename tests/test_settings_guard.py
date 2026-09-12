# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.settings_guard` — the Python guard-policy consumer (G02, #755)."""

from __future__ import annotations

import enum
import json
from pathlib import Path

from kb_setup import guard_inventory, settings_guard
from kb_setup.generated.guard_policy import ProtectedPathSuffix

REPO = Path(__file__).resolve().parents[1]

SCHEMA_PATH = REPO / "schemas" / "guard-policy.schema.json"


def test_protected_suffixes_are_built_from_enum_values_not_names() -> None:
    """`PROTECTED_SUFFIXES` must be built from an enum's VALUES, never its NAMES.

    Tested by PROVENANCE, not by equality with today's list (F8). A
    hand-frozen tuple matching today's nine literal strings would pass a
    plain equality check even if the production code read `.name` instead of
    `.value` — the exact defect this test exists to catch, and the shape two
    prior versions of this test could not fail in (F8/M2). A hostile enum
    whose member NAMES and VALUES deliberately differ is what proves
    `_protected_suffixes_from` — the SAME function that builds the real
    `PROTECTED_SUFFIXES` — reads `.value`.
    """

    class _Hostile(enum.Enum):
        field_should_not_appear = "actual/value/one"
        another_mangled_name = "actual/value/two"

    built = settings_guard._protected_suffixes_from(_Hostile)
    assert built == ("actual/value/one", "actual/value/two")
    assert "field_should_not_appear" not in built
    assert "another_mangled_name" not in built

    # The production constant is built by that SAME function over the real
    # generated enum — not a separately hand-maintained tuple.
    assert (
        settings_guard._protected_suffixes_from(ProtectedPathSuffix)
        == settings_guard.PROTECTED_SUFFIXES
    )
    assert tuple(m.value for m in ProtectedPathSuffix) == settings_guard.PROTECTED_SUFFIXES
    assert ".claude/settings.json" in settings_guard.PROTECTED_SUFFIXES
    assert ".claude/settings.local.json" in settings_guard.PROTECTED_SUFFIXES
    assert "mise.toml" in settings_guard.PROTECTED_SUFFIXES
    assert "hk.pkl" in settings_guard.PROTECTED_SUFFIXES
    assert "python/src/kb_setup/hook_guard.py" in settings_guard.PROTECTED_SUFFIXES


def test_no_value_is_dropped_and_none_collide() -> None:
    """Every schema entry survives, none collide.

    The count is DERIVED from the schema, never hardcoded here (F2/M2: a
    hardcoded `5` — now stale at 9 — was the exact defect this ticket found in
    two places plus a docstring).
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    expected = len(schema["enum"])
    assert len(settings_guard.PROTECTED_SUFFIXES) == expected
    assert len(set(settings_guard.PROTECTED_SUFFIXES)) == expected


# --- is_protected_path: mirrors register.ts's isProtectedPath -------------


def test_exact_match_is_protected() -> None:
    assert settings_guard.is_protected_path(".claude/settings.json")
    assert settings_guard.is_protected_path("mise.toml")


def test_suffix_match_on_a_deeper_path_is_protected() -> None:
    assert settings_guard.is_protected_path("some/worktree/mise.toml")
    assert settings_guard.is_protected_path("a/b/c/.claude/settings.json")


def test_backslash_paths_are_normalised_before_matching() -> None:
    assert settings_guard.is_protected_path("some\\worktree\\mise.toml")


def test_a_substring_that_is_not_a_path_segment_is_not_protected() -> None:
    """The false-positive class `register.ts` documents avoiding.

    A name that merely CONTAINS a protected suffix as a substring, with no
    `/` boundary, must not match.
    """
    assert not settings_guard.is_protected_path("othermise.toml")
    assert not settings_guard.is_protected_path("hk.pkl.bak")


def test_an_unrelated_path_is_not_protected() -> None:
    assert not settings_guard.is_protected_path("README.md")
    assert not settings_guard.is_protected_path("")


# --- C1a: this module must stay UNWIRED -----------------------------------


def test_settings_guard_is_not_reachable_from_hook_guard() -> None:
    """`hook_guard.py` must not import `settings_guard` (C1a).

    Guard membership in `guard_inventory` is AST reachability from
    `hook_guard.py`; the moment `hook_guard` imports this module it becomes an
    undeclared guard and reds `kb-guard-inventory-check`. Wiring it up is a
    later ticket's job, with its own inventory update.
    """
    names = guard_inventory.dispatched_module_names(REPO)
    assert "settings_guard" not in names
