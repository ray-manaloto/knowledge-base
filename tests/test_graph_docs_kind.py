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
        commit=_NEW,
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


def _report(monkeypatch, tmp_path: Path, completed: _Completed) -> str:
    m = _manifest(tmp_path, kind="docs")
    monkeypatch.setattr(graph.subprocess, "run", lambda *_a, **_k: completed)
    graph._report_doc_changes(m, _OLD, _NEW)
    return ""


def test_changed_pages_are_named_one_per_line(monkeypatch, tmp_path, capsys):
    """The worklist is the deliverable: which pages to re-extract, by path."""
    out = "docs/claude-code/goal.md\ndocs/codex/hooks.md\n"
    _report(monkeypatch, tmp_path, _Completed(0, out=out))
    printed = capsys.readouterr().out

    assert "2 file(s) changed" in printed
    assert "docs/claude-code/goal.md" in printed
    assert "docs/codex/hooks.md" in printed


def test_empty_diff_reports_zero_changed(monkeypatch, tmp_path, capsys):
    """A real, successful 'nothing moved' — distinct from the failure below."""
    _report(monkeypatch, tmp_path, _Completed(0, out=""))
    printed = capsys.readouterr().out

    assert "0 files changed" in printed
    assert "UNKNOWN" not in printed


def test_failed_diff_is_unknown_never_zero(monkeypatch, tmp_path, capsys):
    """THE ONE THAT MATTERS. A diff that errored did not answer 'nothing changed'.

    Realistic break it guards: dropping the `returncode` check makes a failed
    `git diff` fall through to an empty stdout and print '0 files changed' — a
    green worklist for a corpus nobody looked at.
    """
    _report(monkeypatch, tmp_path, _Completed(128, err="fatal: bad object"))
    printed = capsys.readouterr().out

    assert "UNKNOWN" in printed, "a failed diff must not be reported as an empty one"
    assert "0 files changed" not in printed
    assert "fatal: bad object" in printed, "the operator needs the real git error"
