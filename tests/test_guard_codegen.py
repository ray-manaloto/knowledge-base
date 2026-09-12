# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.guard_codegen` — G02 (#755), the settings-guard's schema.

The control arm (`test_the_committed_tree_reconciles_clean`) runs FIRST and
every FAIL-direction test below mutates a `tmp_path` COPY of the tree rather
than the real one, restoring nothing because nothing real is ever touched.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from kb_setup import guard_codegen, guard_inventory
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


def test_expected_generated_outputs_track_pyproject_when_it_changes(tmp_path: Path) -> None:
    """F8: PROVENANCE, not equality-with-today.

    Add a job to a COPIED `pyproject.toml` and assert
    `_expected_generated_outputs` follows it — a hardcoded set matching
    today's ten jobs cannot pass this, only a real derivation can.
    """
    pyproject_path = tmp_path / "pyproject.toml"
    original = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    extra_job = (
        "\n[tool.datamodel-codegen.jobs.new-fake-job-for-this-test]\n"
        'output = "python/src/kb_setup/generated/new_fake_job_for_this_test.py"\n'
    )
    pyproject_path.write_text(original + extra_job, encoding="utf-8")

    expected = guard_codegen._expected_generated_outputs(tmp_path)

    added = (tmp_path / "python/src/kb_setup/generated/new_fake_job_for_this_test.py").resolve()
    assert added in expected
    # And the existing jobs are still there too — this is additive tracking,
    # not a check that only sees the newest entry.
    assert (tmp_path / guard_codegen.GENERATED_DIR / "guard_policy.py").resolve() in expected


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


# --- F4: the stale-extra scan recurses ------------------------------------


def test_a_stale_file_in_a_subdirectory_is_caught(repo_copy: Path) -> None:
    """A non-recursive `glob("*.py")` used to miss this entirely."""
    nested = repo_copy / guard_codegen.GENERATED_DIR / "nested"
    nested.mkdir()
    orphan = nested / "orphan_nested.py"
    orphan.write_text(
        '# Copyright (c) 2026 Raymond Manaloto\n"""Generated orphan enum; stale."""\n',
        encoding="utf-8",
    )
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


# --- F5: the generated-provenance marker matches on TWO axes --------------


def test_a_stale_file_with_a_different_year_is_still_flagged(repo_copy: Path) -> None:
    """The marker cannot hardcode 2026 forever — any year must still match."""
    orphan = repo_copy / guard_codegen.GENERATED_DIR / "orphan_future_year.py"
    orphan.write_text(
        '# Copyright (c) 2031 Raymond Manaloto\n"""Generated orphan enum; stale."""\n',
        encoding="utf-8",
    )
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_a_schema_generated_init_shaped_file_is_never_flagged_regardless_of_year(
    repo_copy: Path,
) -> None:
    """The sole real near-miss: `generated/__init__.py`.

    It opens with `\"\"\"Schema-generated`, eight characters from the real
    `\"\"\"Generated` marker. A ONE-axis loosening (dropping the year, or
    matching any "generated" substring) would flag this file permanently —
    the exact failure class this repo calls "a check that can only pass" (F5).
    """
    near_miss = repo_copy / guard_codegen.GENERATED_DIR / "not_really_generated.py"
    near_miss.write_text(
        '# Copyright (c) 2026 Raymond Manaloto\n"""Schema-generated runtime contracts."""\n',
        encoding="utf-8",
    )
    assert guard_codegen.check(repo_copy) == Rc.OK


# --- F3: a launch failure must not be mislabelled as drift -----------------


def test_a_genuine_drift_report_is_findings_not_not_run(repo_copy: Path) -> None:
    """Control arm for F3: real drift (a unified diff) must still be FINDINGS."""
    (repo_copy / guard_codegen.GENERATED_DIR / "guard_policy.py").unlink()
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_a_native_launch_failure_is_reported_as_not_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F3: a launch failure must be `Rc.NOT_RUN`, never `Rc.FINDINGS`.

    No diff, no `MISSING:` line — mislabelling this as drift is the exact
    inversion the naive fix would cause.
    """

    def fake_run_native(repo_root: Path, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        del repo_root, extra_args
        return subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="",
            stderr="error: Project directory `/nonexistent-dir-xyz` does not exist\n",
        )

    schema_path = tmp_path / guard_codegen.SCHEMA_PATH
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        (REPO / guard_codegen.SCHEMA_PATH).read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(guard_codegen, "_run_native", fake_run_native)
    assert guard_codegen.check(tmp_path) == Rc.NOT_RUN


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("--- a/foo.py\n+++ b/foo.py (expected)\n@@ -1 +1 @@\n", True),
        ("MISSING: /repo/foo.py (file does not exist but should be generated)\n", True),
        ("error: Project directory `/nonexistent-dir-xyz` does not exist\n", False),
        ("", False),
    ],
)
def test_native_check_ran_discriminates_drift_from_launch_failure(output, expected) -> None:
    assert guard_codegen._native_check_ran(output) is expected


# --- F2: the schema's own floor --------------------------------------------


def test_an_emptied_schema_reports_below_the_floor(tmp_path: Path) -> None:
    """F2: an emptied policy must be a reported FINDING, not a silent clean.

    Checks 1-3 alone are internally consistent even with zero entries.
    `check()` reads the floor before touching the native subprocess or the TS
    artifact, so a bare schema file at the expected relative path is enough —
    no full repo copy needed.
    """
    empty_schema = json.loads((REPO / guard_codegen.SCHEMA_PATH).read_text(encoding="utf-8"))
    empty_schema["enum"] = []
    schema_path = tmp_path / guard_codegen.SCHEMA_PATH
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(empty_schema), encoding="utf-8")
    assert guard_codegen.check(tmp_path) == Rc.FINDINGS


def test_the_floor_constant_is_at_most_the_committed_enum_size() -> None:
    """Sanity: the floor must not itself be red against the committed schema."""
    schema = json.loads((REPO / guard_codegen.SCHEMA_PATH).read_text(encoding="utf-8"))
    assert len(schema["enum"]) >= guard_codegen._MINIMUM_PROTECTED_PATHS


# --- F6: the TS header's hardcoded rationale vs. the schema's description --


def test_ts_rationale_anchor_is_present_in_the_committed_schema() -> None:
    schema = json.loads((REPO / guard_codegen.SCHEMA_PATH).read_text(encoding="utf-8"))
    assert guard_codegen._ts_rationale_is_current(schema["description"])


def test_a_schema_description_that_drops_the_rationale_is_findings() -> None:
    assert not guard_codegen._ts_rationale_is_current("a description with no rationale at all")


def test_a_schema_whose_description_dropped_the_rationale_reports_findings(
    repo_copy: Path,
) -> None:
    """Integration-level arm for `_check_rationale`.

    The divergence must reach `check()`, not just the pure predicate above.
    Regenerates BOTH artifacts from the mutated schema first, so the native
    check and the TS-array check both agree with the new description — only
    `render_typescript`'s HARDCODED rationale comment (unrelated to the
    changed description, by construction) is left stale. Without the
    regenerate step, a schema-description edit alone also desyncs the
    generated Python docstring, and the native `--check` would report FINDINGS
    for that reason instead — passing this test for the wrong reason and
    hiding the very divergence `_check_rationale` exists to catch (measured:
    this was `A9`'s exact false SURVIVAL in the arm suite).
    """
    schema_path = repo_copy / guard_codegen.SCHEMA_PATH
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["description"] = "a description with no rationale at all"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    assert guard_codegen.regenerate(repo_copy) == Rc.OK
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


# --- F1: register.ts must both import AND use the generated policy --------


def test_register_ts_with_the_import_commented_out_has_no_live_consumer(
    repo_copy: Path,
) -> None:
    """Arm 1: a commented-out import.

    `register.ts` documents this as a SILENT loader failure, and a raw-text
    presence check would read the commented line and call it clean.
    """
    path = repo_copy / guard_inventory.FUNCTION_HOOK_SOURCE_PATH
    source = path.read_text(encoding="utf-8")
    tampered = source.replace(
        'import { PROTECTED_SUFFIXES } from "./protected-paths";',
        '// import { PROTECTED_SUFFIXES } from "./protected-paths";',
    )
    assert tampered != source
    path.write_text(tampered, encoding="utf-8")
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_register_ts_with_the_use_swapped_for_a_literal_has_no_live_consumer(
    repo_copy: Path,
) -> None:
    """Arm 2: the import stays, but the body of `isProtectedPath` is swapped.

    TypeScript tolerates the now-unused import, so an import-only check would
    pass over a guard that protects nothing the schema names.
    """
    path = repo_copy / guard_inventory.FUNCTION_HOOK_SOURCE_PATH
    source = path.read_text(encoding="utf-8")
    tampered = source.replace(
        "return PROTECTED_SUFFIXES.some(\n    (suffix) => normalized === suffix "
        '|| normalized.endsWith("/" + suffix),\n  );',
        'return ["README.md"].some((suffix) => normalized === suffix);',
    )
    assert tampered != source
    path.write_text(tampered, encoding="utf-8")
    assert guard_codegen.check(repo_copy) == Rc.FINDINGS


def test_register_ts_consumes_policy_on_the_committed_file() -> None:
    """Control arm: the real, unmutated `register.ts` must pass F1's check."""
    source = (REPO / guard_inventory.FUNCTION_HOOK_SOURCE_PATH).read_text(encoding="utf-8")
    assert guard_codegen._register_ts_consumes_policy(source)
