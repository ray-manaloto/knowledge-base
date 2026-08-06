"""Tests for `kind = docs` manifests — the docs-mirror ingestion path.

TWO BEHAVIOURS, and both exist because a wrong answer here is SILENT.

1. `build()` must not run the AST pass over a docs manifest. graphify defines
   `--code-only` as "index code … and skip doc/paper/image files", so the pass is
   guaranteed empty over a markdown mirror. The waste is the small half; the real
   defect is that a docs manifest which was never asked and a code repo that was
   asked and answered "nothing" used to print the SAME `[skip] … no code nodes`
   line — collapsing not-applicable into could-not-check, which is the exact
   distinction `currency`'s DRIFT/SKIP/OK keeps apart everywhere else.

2. `_report_doc_changes` must never render a FAILED diff as "nothing changed".
   A `git diff` that errored did not ask the question. This is the whole reason
   the docs pin exists: knowledge-base#76 was opened on three moved sha256 values
   with no way to read the delta, so a mechanism that can quietly report an empty
   worklist would reproduce that failure with more machinery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import graph
from kb_setup import manifest as mf

_OLD = "03853a019423ffb5c5082e24c39ac20e38a7cfb1"
_NEW = "bb1e5f2c9d4a7e6031f8a2c4d5e6b7a8c9d0e1f2"


def _manifest(tmp_path: Path, *, kind: str, name: str = "demo") -> mf.Manifest:
    src = tmp_path / "sources"
    (src / name).mkdir(parents=True, exist_ok=True)
    m = mf.Manifest(
        name=name,
        path=src / f"{name}.manifest",
        url="https://example.invalid/o/demo",
        ref="main",
        commit=_OLD,
        kind=kind,
    )
    m.path.write_text(
        f"url = {m.url}\nref = {m.ref}\ncommit = {m.commit}\nkind = {kind}\n",
        encoding="utf-8",
    )
    return m


class _Completed:
    def __init__(self, rc: int, out: str = "", err: str = "") -> None:
        self.returncode = rc
        self.stdout = out
        self.stderr = err


# --------------------------------------------------------------------------
# 1. build(): a docs manifest is never handed to the AST pass
# --------------------------------------------------------------------------


def _build_with(monkeypatch, tmp_path: Path, kind: str) -> list[str]:
    """Run `build()` over ONE manifest of `kind`; return the names AST-extracted.

    One manifest is deliberate: with nothing code-bearing, `build()` raises
    SystemExit before reaching any merge machinery, so the partition decision is
    observable without stubbing half the module. The SystemExit is the expected
    terminus of both arms, which is why the assertion is on the CALL LIST and not
    on the exit — an rc-only assertion here would pass for either behaviour.
    """
    asked: list[str] = []
    _manifest(tmp_path, kind=kind)
    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)

    def fake_extract(_root: Path, name: str) -> bool:
        asked.append(name)
        return False  # no code nodes either way — the arms differ only in being ASKED

    monkeypatch.setattr(graph, "_extract_code", fake_extract)
    with pytest.raises(SystemExit):
        graph.build(tmp_path)
    return asked


def test_docs_manifest_is_never_ast_extracted(monkeypatch, tmp_path):
    """`kind = docs` -> the AST pass is not even attempted."""
    assert _build_with(monkeypatch, tmp_path, "docs") == []


def test_code_manifest_is_still_ast_extracted(monkeypatch, tmp_path):
    """CONTROL ARM for the test above.

    Without it, a helper that never called `_extract_code` at all would satisfy
    `== []` — i.e. a change disabling extraction for EVERY source would pass.
    """
    assert _build_with(monkeypatch, tmp_path, "code") == ["demo"]


def test_docs_skip_is_reported_distinctly_from_no_code_nodes(monkeypatch, tmp_path, capsys):
    """The two outcomes must not print the same line — that conflation IS the bug."""
    _build_with(monkeypatch, tmp_path, "docs")
    docs_line = capsys.readouterr().out
    _build_with(monkeypatch, tmp_path, "code")
    code_line = capsys.readouterr().out

    assert "[docs]" in docs_line
    assert "kind=docs" in docs_line
    assert "[skip]" in code_line
    assert "no code nodes" in code_line
    assert "[skip]" not in docs_line, "a declared docs source must not read as a failed probe"


# --------------------------------------------------------------------------
# 2. _report_doc_changes(): the worklist, and the three answers it can give
# --------------------------------------------------------------------------


def _advance(monkeypatch, tmp_path: Path, completed: _Completed) -> list[str]:
    """Run `_advance_docs_pin`; return the manifest's `commit =` lines after it."""
    m = _manifest(tmp_path, kind="docs")
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph.subprocess, "run", lambda *_a, **_k: completed)
    graph._advance_docs_pin(m, _NEW)
    return [ln for ln in m.path.read_text(encoding="utf-8").splitlines() if ln.startswith("commit")]


def test_changed_pages_are_named_with_their_action(monkeypatch, tmp_path, capsys):
    """The worklist is the deliverable, and it must say what to DO with each path."""
    out = "M\tdocs/claude-code/goal.md\nD\tdocs/codex/gone.md\nA\tdocs/codex/hooks.md\n"
    _advance(monkeypatch, tmp_path, _Completed(0, out=out))
    printed = capsys.readouterr().out

    assert "re-extract  docs/claude-code/goal.md" in printed
    assert "re-extract  docs/codex/hooks.md" in printed
    assert "REMOVE stale extraction for  docs/codex/gone.md" in printed
    assert "re-extract  docs/codex/gone.md" not in printed, "a deletion is not a page to read"


def test_a_rename_is_both_jobs(monkeypatch, tmp_path, capsys):
    """A rename produces work at the new path AND a stale extraction at the old one."""
    _advance(monkeypatch, tmp_path, _Completed(0, out="R096\tdocs/a/old.md\tdocs/a/new.md\n"))
    printed = capsys.readouterr().out

    assert "re-extract  docs/a/new.md" in printed
    assert "REMOVE stale extraction for  docs/a/old.md" in printed


def test_non_document_churn_is_not_extraction_work(monkeypatch, tmp_path, capsys):
    """A mirror is a git repo: its own metadata moves on syncs that touched no docs.

    Reporting `docs_manifest.json` as a page to read spends host-agent tokens on a
    build script — the realistic cost of the unfiltered first version.
    """
    out = "M\tdocs_manifest.json\nM\t.github/workflows/update-docs.yml\n"
    _advance(monkeypatch, tmp_path, _Completed(0, out=out))
    printed = capsys.readouterr().out

    assert "no document changes" in printed
    assert "2 non-document file(s) changed" in printed
    assert "re-extract" not in printed


def test_failed_diff_leaves_the_pin_exactly_where_it_was(monkeypatch, tmp_path, capsys):
    """THE ONE THAT MATTERS, and the defect a cold review caught.

    The first version wrote the pin and THEN diffed, so a failed diff printed
    "UNKNOWN — re-run" while the re-run hit `latest == m.commit` and reported
    "already at latest — nothing to do". The worklist was not merely unreported,
    it was unrecoverable, and the message pointed at a retry that could not work.

    Realistic break: move `mf.write_commit` back above the diff. The pin then
    reads `_NEW` here and the promised retry is dead.
    """
    commit_lines = _advance(monkeypatch, tmp_path, _Completed(128, err="fatal: bad object"))
    printed = capsys.readouterr().out

    assert commit_lines == [f"commit = {_OLD}"], (
        f"a failed diff must leave the pin at {_OLD[:10]}, saw {commit_lines}"
    )
    assert "UNKNOWN" in printed, "a failed diff must not be reported as an empty one"
    assert "NOT advanced" in printed
    assert "fatal: bad object" in printed, "the operator needs the real git error"


def test_successful_diff_does_advance_the_pin(monkeypatch, tmp_path):
    """CONTROL ARM for the test above: the happy path must still write the pin.

    Without it, code that never advanced the pin at all would satisfy the
    failed-diff test and the mechanism would simply never move.
    """
    commit_lines = _advance(monkeypatch, tmp_path, _Completed(0, out="M\tdocs/a.md\n"))
    assert commit_lines == [f"commit = {_NEW}"]


# --------------------------------------------------------------------------
# 3. update_all(): the bulk path must reach docs mirrors
# --------------------------------------------------------------------------


def test_a_copy_does_not_make_the_original_stale(monkeypatch, tmp_path, capsys):
    """`C###` is a COPY: the original still exists, so it is not stale.

    Treating it like `R###` queued a live page's extraction for removal. The
    worklist is advisory, so the blast radius is a host agent sent to delete
    something real — bounded, but wrong. (Cold lane round 2, P2.)
    """
    _advance(monkeypatch, tmp_path, _Completed(0, out="C085\tdocs/a/src.md\tdocs/a/copy.md\n"))
    printed = capsys.readouterr().out

    assert "re-extract  docs/a/copy.md" in printed
    assert "REMOVE" not in printed, "a copy leaves the original in place"


def test_a_failed_docs_diff_returns_a_nonzero_rc(monkeypatch, tmp_path):
    """The failure path must be visible to anything reading an exit code.

    Round 1 stopped the pin from advancing past a lost worklist; the rc stayed 0,
    so automation could not see it. Realistic break: return 0 from the failure
    branch, or drop the `return` in the CLI dispatch. (Cold lane round 2, P2.)
    """
    m = _manifest(tmp_path, kind="docs")
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph.subprocess, "run", lambda *_a, **_k: _Completed(128, err="boom"))
    assert graph._advance_docs_pin(m, _NEW) == 1


def test_a_successful_docs_diff_returns_zero(monkeypatch, tmp_path):
    """CONTROL ARM: without it, always-return-1 would satisfy the test above."""
    m = _manifest(tmp_path, kind="docs")
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    ok = _Completed(0, out="M\tdocs/a.md\n")
    monkeypatch.setattr(graph.subprocess, "run", lambda *_a, **_k: ok)
    assert graph._advance_docs_pin(m, _NEW) == 0


def test_update_all_reports_the_worst_rc_not_the_last(monkeypatch, tmp_path):
    """One failing source must not be masked by a later passing one."""
    _manifest(tmp_path, kind="docs", name="aaa-fails")
    _manifest(tmp_path, kind="code", name="zzz-passes")
    monkeypatch.setattr(graph, "update", lambda _root, name: 1 if "fails" in name else 0)
    assert graph.update_all(tmp_path) == 1


def test_update_all_includes_docs_manifests(monkeypatch, tmp_path):
    """A bare `mise run kb-update` must not silently skip every docs mirror.

    This filtered to `kind == "code"` back when `code` was the only kind, so
    adding the docs kind excluded mirrors from the bulk path — the changed-page
    worklist would then appear ONLY when a human named the source by hand, which
    is a check that exists and never runs. (Cold lane, P2.)
    """
    _manifest(tmp_path, kind="docs", name="mirror")
    _manifest(tmp_path, kind="code", name="repo")
    seen: list[str] = []
    monkeypatch.setattr(graph, "update", lambda _root, name: seen.append(name) or 0)
    graph.update_all(tmp_path)

    assert sorted(seen) == ["mirror", "repo"], f"docs manifest must be updated too, saw {seen}"


# --------------------------------------------------------------------------
# 3. update(): the writer version gate sits on the CODE branch only
# --------------------------------------------------------------------------
#
# The gate moved here from the dispatch layer (cold lane round 2, P2): a docs
# pin advance is pure git and must never be blocked by a stale graphify it
# does not run, while the code branch hands the artifact straight to the
# binary and must refuse a stale one BEFORE it runs.


def test_a_docs_update_never_pays_the_writer_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    m = _manifest(tmp_path, kind="docs")
    monkeypatch.setattr(graph.mf, "load", lambda _p: m)
    monkeypatch.setattr(graph.mf, "latest_commit", lambda _m: _NEW)
    monkeypatch.setattr(graph, "_advance_docs_pin", lambda _m, _l: 0)

    def boom(_root: object) -> None:
        raise AssertionError("a docs pin advance was blocked by the version gate")

    monkeypatch.setattr(graph, "assert_pinned_graphify", boom)

    assert graph.update(tmp_path, "demo") == 0


def test_a_code_update_pays_the_gate_before_any_graphify_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The tripwire raises BEFORE write_commit/clone/_run.

    A stale binary must not advance the pin either, or a retry after
    `mise install` would report "already at latest" and skip the re-extract
    it never did.
    """
    m = _manifest(tmp_path, kind="code")
    monkeypatch.setattr(graph.mf, "load", lambda _p: m)
    monkeypatch.setattr(graph.mf, "latest_commit", lambda _m: _NEW)

    def untouched(*_a: object, **_k: object) -> None:
        raise AssertionError("the code path ran past the version gate")

    monkeypatch.setattr(graph.mf, "write_commit", untouched)
    monkeypatch.setattr(graph, "_ensure_clone", untouched)
    monkeypatch.setattr(graph, "_run", untouched)

    def tripwire(_root: object) -> None:
        raise SystemExit("gate fired")

    monkeypatch.setattr(graph, "assert_pinned_graphify", tripwire)

    with pytest.raises(SystemExit, match="gate fired"):
        graph.update(tmp_path, "demo")
