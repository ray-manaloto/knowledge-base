"""Tests for `kb-setup query` — the kb-query task's `--prose` form.

What is actually under test is WHICH CORPUS ANSWERED. Everything else this
wrapper does is pass-through, and a wrapper that quietly resolved the wrong
graph would still print a plausible answer — which is the failure mode that
makes a scoped corpus worth having in the first place.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import graphify_ops, prose

if TYPE_CHECKING:
    import pytest


class _Recorder:
    """Stands in for `subprocess.run`, capturing the argv it was handed."""

    def __init__(self) -> None:
        self.argv: list[str] | None = None

    def __call__(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.argv = list(argv)
        return subprocess.CompletedProcess(argv, 0)


def _repo(tmp_path: Path, *, full: bool = True, prose_graph: bool = True) -> Path:
    """A repo root holding whichever of the two graphs the case needs."""
    out = tmp_path / "graphify-out"
    out.mkdir()
    if full:
        (out / "graph.json").write_text("{}")
    if prose_graph:
        (out / prose.PROSE_GRAPH_NAME).write_text("{}")
    return tmp_path


def _run(
    monkeypatch: pytest.MonkeyPatch, repo: Path, args: list[str]
) -> tuple[int, list[str] | None]:
    recorder = _Recorder()
    monkeypatch.setattr(graphify_ops.subprocess, "run", recorder)
    return graphify_ops.query(repo, args), recorder.argv


def test_the_default_form_pins_the_full_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Never left to the process cwd — graphify's default is cwd-relative.

    Invoked from the repo root it silently agrees; invoked from anywhere else it
    silently answers from another corpus.
    """
    repo = _repo(tmp_path)
    rc, argv = _run(monkeypatch, repo, ["a question"])
    assert rc == 0
    assert argv is not None
    assert argv[argv.index("--graph") + 1] == str(repo / "graphify-out" / "graph.json")


def test_the_prose_form_pins_the_derived_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CONTROL ARM for the above: the flag has to change the corpus.

    A wrapper that accepted `--prose` and queried the same graph would pass the
    default test and every smoke check, while answering from the corpus the flag
    exists to avoid.
    """
    repo = _repo(tmp_path)
    rc, argv = _run(monkeypatch, repo, ["a question", graphify_ops.PROSE_FLAG])
    assert rc == 0
    assert argv is not None
    assert argv[argv.index("--graph") + 1] == str(repo / "graphify-out" / prose.PROSE_GRAPH_NAME)


def test_the_prose_flag_is_not_forwarded_to_graphify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """It is this wrapper's flag; graphify has never heard of it."""
    _, argv = _run(monkeypatch, _repo(tmp_path), ["q", graphify_ops.PROSE_FLAG])
    assert argv is not None
    assert graphify_ops.PROSE_FLAG not in argv


def test_other_arguments_pass_through_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The wrapper adds a corpus; it is not a re-implementation of the CLI."""
    _, argv = _run(monkeypatch, _repo(tmp_path), ["q", "--budget", "8000", "--dfs"])
    assert argv is not None
    assert argv[:2] == ["graphify", "query"]
    assert argv[2:6] == ["q", "--budget", "8000", "--dfs"]


def test_an_explicit_graph_is_left_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A caller naming a corpus outranks the default, and is not doubled up."""
    _, argv = _run(monkeypatch, _repo(tmp_path), ["q", "--graph", "/elsewhere/graph.json"])
    assert argv is not None
    assert argv.count("--graph") == 1
    assert argv[argv.index("--graph") + 1] == "/elsewhere/graph.json"


def test_prose_and_an_explicit_graph_together_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two corpora named, no sensible winner — so neither one silently wins.

    A precedence rule here would mean the answer came from a corpus the caller
    did not choose, which is exactly the confusion the flag exists to remove.
    """
    rc, argv = _run(
        monkeypatch,
        _repo(tmp_path),
        ["q", graphify_ops.PROSE_FLAG, "--graph", "/elsewhere/graph.json"],
    )
    assert rc == 2
    assert argv is None, "graphify must not run when the corpus is ambiguous"


def test_a_missing_prose_graph_names_the_task_that_derives_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing corpus must name its fix — and the RIGHT one of the two tasks."""
    repo = _repo(tmp_path, prose_graph=False)
    rc, argv = _run(monkeypatch, repo, ["q", graphify_ops.PROSE_FLAG])
    assert rc == 2
    assert argv is None, "graphify must not run against a corpus that is not there"
    assert "kb-prose" in capsys.readouterr().err


def test_a_missing_full_graph_names_the_build_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTROL ARM: the two absences are different, and must not collapse.

    Pointing both at one task would send a reader who is missing the derived
    graph into a full rebuild, and a reader who is missing the built graph into
    a derivation that cannot run.
    """
    repo = _repo(tmp_path, full=False)
    rc, argv = _run(monkeypatch, repo, ["q"])
    assert rc == 2
    assert argv is None
    assert "kb-build" in capsys.readouterr().err
