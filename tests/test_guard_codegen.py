# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.guard_codegen` — G02 (#755), the settings-guard's schema.

The control arm (`test_the_committed_tree_reconciles_clean`) runs FIRST and
every FAIL-direction test below mutates a `tmp_path` COPY of the tree rather
than the real one, restoring nothing because nothing real is ever touched.
"""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

import pytest
from kb_setup import guard_codegen
from kb_setup.generated.guard_policy import ProtectedPathSuffix
from kb_setup.result import Rc

REPO = Path(__file__).resolve().parents[1]


#: Directories `guard_codegen.check` never reads, and which dominate this
#: repo's size: gitignored derived/vendored trees (`.venv` excluded from the
#: COPY, not from the test — it is symlinked back in below, since `uv run
#: --project` needs a real, already-synced environment matching `uv.lock` to
#: run fast and offline) plus session scratch (`.agent`) and clones/graphs
#: this check has no reason to touch.
_HEAVY_DIRS = (".venv", ".git", ".agent", ".self-graph", "graphify-out", "sources", "raw")


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """A mutable copy of everything `guard_codegen.check` reads.

    Minus the heavy trees in `_HEAVY_DIRS` — a full copy of this repo is tens
    of gigabytes and would dominate every test's runtime for nothing this
    check reads. `.venv` is symlinked back in so the native `datamodel-codegen`
    subprocess runs against the SAME already-synced environment rather than
    resolving a fresh one per test.
    """
    shutil.copytree(REPO, tmp_path, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*_HEAVY_DIRS))
    (tmp_path / ".venv").symlink_to(REPO / ".venv")
    return tmp_path


# --- the control arm, first ------------------------------------------------


def test_the_committed_tree_reconciles_clean(repo_copy: Path) -> None:
    """THE CONTROL ARM. Everything below is void if this is not clean."""
    assert guard_codegen.check(repo_copy) == Rc.OK


# --- render_typescript ------------------------------------------------------


def test_render_typescript_matches_the_committed_artifact() -> None:
    """The committed `.ts` file is exactly what the schema renders TODAY."""
    rendered = guard_codegen.render_typescript(REPO / guard_codegen.SCHEMA_PATH)
    committed = (REPO / guard_codegen.TS_OUTPUT_PATH).read_text(encoding="utf-8")
    assert rendered == committed


def test_rendered_typescript_keeps_the_loader_safe_shape() -> None:
    """No TS `enum`, `as const`, default export, or type-only export (spec §3)."""
    rendered = guard_codegen.render_typescript(REPO / guard_codegen.SCHEMA_PATH)
    assert "export const PROTECTED_SUFFIXES: readonly string[] = [" in rendered
    assert "enum " not in rendered
    assert "as const" not in rendered
    assert "export default" not in rendered
    assert "export type" not in rendered


def test_rendered_typescript_carries_every_schema_value_in_order() -> None:
    schema = json.loads((REPO / guard_codegen.SCHEMA_PATH).read_text(encoding="utf-8"))
    rendered = guard_codegen.render_typescript(REPO / guard_codegen.SCHEMA_PATH)
    values_in_rendered_order = [
        line.strip().strip(",").strip('"')
        for line in rendered.splitlines()
        if line.strip().startswith('"')
    ]
    assert values_in_rendered_order == schema["enum"]


def test_rendered_typescript_embeds_no_absolute_path(tmp_path: Path) -> None:
    """The header names the schema's REPO-RELATIVE path, never the caller's.

    Two different absolute locations for an identical schema must render
    BYTE-IDENTICAL output, or the drift gate becomes a false positive on every
    other checkout (premise E).
    """
    schema_path = REPO / guard_codegen.SCHEMA_PATH
    copy_path = tmp_path / "guard-policy.schema.json"
    copy_path.write_text(schema_path.read_text(encoding="utf-8"), encoding="utf-8")
    assert guard_codegen.render_typescript(schema_path) == guard_codegen.render_typescript(
        copy_path
    )
    rendered = guard_codegen.render_typescript(schema_path)
    assert str(tmp_path) not in rendered
    assert str(REPO) not in rendered


def test_rendered_typescript_is_lint_clean_bytes() -> None:
    """No trailing whitespace, LF-only, ends with exactly one final newline (C11).

    hk lints `.claude/mods/**` — `proseExclude` does not cover it — so a
    fix-direction builtin rewriting the generated file would make it differ
    from what the generator produces, redenning this module's own gate on the
    very next run. This is the regression arm for that trap.
    """
    rendered = guard_codegen.render_typescript(REPO / guard_codegen.SCHEMA_PATH)
    assert "\r" not in rendered
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    for line in rendered.splitlines():
        assert line == line.rstrip(), f"trailing whitespace: {line!r}"


# --- the generated Python enum: mangling is survivable, not silent --------


def test_enum_values_round_trip_byte_exact_and_nothing_collides() -> None:
    schema = json.loads((REPO / guard_codegen.SCHEMA_PATH).read_text(encoding="utf-8"))
    values = [m.value for m in ProtectedPathSuffix]
    assert values == schema["enum"]
    assert len(values) == len(set(values))


def test_generated_enum_does_not_ship_the_shared_templates_false_docstring() -> None:
    """C10: the false 'source-group enumeration' fallback must not survive."""
    text = (REPO / "python/src/kb_setup/generated/guard_policy.py").read_text(encoding="utf-8")
    assert "source-group enumeration" not in text
    assert ProtectedPathSuffix.__doc__ is not None
    assert "protected-path" in ProtectedPathSuffix.__doc__.lower()


# --- C3: expected outputs come from the job table, not a second list -------


def test_expected_generated_outputs_are_derived_from_pyproject_not_hard_coded() -> None:
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    jobs = pyproject["tool"]["datamodel-codegen"]["jobs"]
    expected_from_table = {
        (REPO / job["output"]).resolve() for job in jobs.values() if "output" in job
    }
    assert guard_codegen._expected_generated_outputs(REPO) == expected_from_table
    assert (REPO / guard_codegen.GENERATED_DIR / "guard_policy.py").resolve() in expected_from_table


# --- check(): all three drift shapes, each independently armed ------------


def test_a_modified_ts_artifact_is_detected(repo_copy: Path) -> None:
    ts_path = repo_copy / guard_codegen.TS_OUTPUT_PATH
    ts_path.write_text(ts_path.read_text(encoding="utf-8") + "// tamper\n", encoding="utf-8")
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_a_deleted_generated_python_file_is_caught_by_the_native_check(
    repo_copy: Path,
) -> None:
    """Deferred to native `datamodel-codegen --all-jobs --check` (spec §5 row 2)."""
    (repo_copy / guard_codegen.GENERATED_DIR / "guard_policy.py").unlink()
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_a_stale_extra_generated_file_is_caught_where_native_check_misses_it(
    repo_copy: Path,
) -> None:
    """The THIRD drift shape (spec §5 row 3) — native `--check` returns 0 on this."""
    orphan = repo_copy / guard_codegen.GENERATED_DIR / "orphan_stale.py"
    orphan.write_text(
        '# Copyright (c) 2026 Raymond Manaloto\n"""Generated orphan enum; stale."""\n',
        encoding="utf-8",
    )
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_a_non_generated_extra_file_in_the_generated_dir_is_not_flagged(
    repo_copy: Path,
) -> None:
    """Only the generated-provenance MARKER trips staleness — not any extra file.

    `__init__.py` and `__pycache__` legitimately live in `GENERATED_DIR`; a
    check keyed on "any file present that no job names" would flag them too.
    """
    (repo_copy / guard_codegen.GENERATED_DIR / "not_generated_at_all.py").write_text(
        "# just a stray file, never claiming to be generated\nX = 1\n", encoding="utf-8"
    )
    assert guard_codegen.check(repo_copy) == Rc.OK
