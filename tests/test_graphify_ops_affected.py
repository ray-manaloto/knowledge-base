"""`kb-affected` — the reverse-dependency verb (`graphify_ops.affected`).

Each refusal test is paired with a control arm, because a function that returns
2 unconditionally satisfies every refusal test for free and breaks the feature.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class _OK:
    returncode = 0


def _graph(repo_root: Path) -> Path:
    """Write a minimal `graphify-out/graph.json` so the is-file gate passes."""
    out = repo_root / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "graph.json"
    p.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    return p


def test_no_symbol_returns_2_without_spawning(monkeypatch, tmp_path: Path) -> None:
    """A bare `mise run kb-affected` must print usage, not shell out to graphify.

    `graphify affected` with no argument prints its own usage and exits non-zero,
    so this could have been left to it. It is caught here because the message a
    user needs names the TASK (`mise run kb-affected -- "<symbol>"`), and the
    guard denies the raw command it would otherwise be told to run.

    THE GRAPH IS WRITTEN FIRST, and that is the whole test. Without it this
    passed for the wrong reason: with the empty-args guard deleted, execution
    fell through to the missing-graph refusal, which also returns 2 and also
    never spawns — so a mutation arm that removed the guard SURVIVED. One
    refusal masking another is indistinguishable from coverage until something
    tries to break it.
    """
    from kb_setup import graphify_ops

    _graph(tmp_path)

    def _must_not_spawn(*_a: object, **_k: object) -> None:
        pytest.fail("affected() spawned graphify with no symbol")

    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(graphify_ops.subprocess, "run", _must_not_spawn)
    assert graphify_ops.affected(tmp_path, []) == 2


def test_missing_graph_returns_2_without_spawning(monkeypatch, tmp_path: Path) -> None:
    """No graph on disk is a refusal, not a run against graphify's cwd default.

    This is the failure the explicit `--graph` pin exists to prevent: unpinned,
    graphify resolves `graphify-out/graph.json` relative to the process cwd, so
    a repo with no graph silently answers from whatever corpus sits under it.
    """
    from kb_setup import graphify_ops

    def _must_not_spawn(*_a: object, **_k: object) -> None:
        pytest.fail("affected() spawned graphify with no graph on disk")

    monkeypatch.setattr(graphify_ops.subprocess, "run", _must_not_spawn)
    assert graphify_ops.affected(tmp_path, ["some_symbol"]) == 2


def test_pins_the_unscoped_graph(monkeypatch, tmp_path: Path) -> None:
    """CONTROL ARM for both refusals, and the assertion that carries the design.

    Two things are checked together on purpose: that a well-formed call REACHES
    graphify at all (without which the refusals above pass trivially), and that
    the argv it reaches with carries `--graph <the unscoped graph>` — the pin,
    not the cwd default. Asserting the path is the point: the prose graph would
    be the wrong corpus for a code question, and no pin at all is the bug.
    """
    from kb_setup import graphify_ops

    graph = _graph(tmp_path)
    seen: list[list[str]] = []

    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        graphify_ops.subprocess, "run", lambda argv, **_k: (seen.append(argv), _OK())[1]
    )

    assert graphify_ops.affected(tmp_path, ["build_from_json"]) == 0
    assert len(seen) == 1
    argv = seen[0]
    assert argv[1] == "affected"
    assert "build_from_json" in argv
    assert argv[argv.index("--graph") + 1] == str(graph)


def test_an_explicit_graph_wins(monkeypatch, tmp_path: Path) -> None:
    """A caller's own `--graph` is passed through, and is NOT double-pinned.

    Appending our pin unconditionally would put two `--graph` flags in one argv,
    where which corpus answered depends on graphify's arg-parsing order rather
    than on what the caller asked for. That is exactly the "one of them quietly
    wins" behaviour `query` refuses for `--prose`.
    """
    from kb_setup import graphify_ops

    _graph(tmp_path)
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    seen: list[list[str]] = []

    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        graphify_ops.subprocess, "run", lambda argv, **_k: (seen.append(argv), _OK())[1]
    )

    graphify_ops.affected(tmp_path, ["sym", "--graph", str(other)])
    argv = seen[0]
    assert argv.count("--graph") == 1
    assert argv[argv.index("--graph") + 1] == str(other)


def test_the_attached_graph_form_is_refused(monkeypatch, tmp_path: Path) -> None:
    """`--graph=<path>` is rejected, not silently swapped for our pin.

    graphify ignores the attached spelling entirely and falls back to its
    cwd-relative default (`ATTACHED_GRAPH`'s note records the probe). Accepting
    it would discard the caller's corpus and substitute ours — benign in outcome
    but a lie in the docstring, and `query` already refuses it. A cold review
    found the two near-identical functions disagreeing on this input.
    """
    from kb_setup import graphify_ops

    _graph(tmp_path)

    def _must_not_spawn(*_a: object, **_k: object) -> None:
        pytest.fail("affected() spawned graphify for the unsupported attached form")

    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(graphify_ops.subprocess, "run", _must_not_spawn)
    assert graphify_ops.affected(tmp_path, ["sym", "--graph=/tmp/other.json"]) == 2


def test_flags_reach_graphify_untouched(monkeypatch, tmp_path: Path) -> None:
    """`--depth` / `--relation` are graphify's, and this wrapper must not eat them.

    A wrapper that silently dropped them would still pass every test above while
    making the depth argument a no-op — the quiet failure mode a pass-through
    seam is most prone to.
    """
    from kb_setup import graphify_ops

    _graph(tmp_path)
    seen: list[list[str]] = []

    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        graphify_ops.subprocess, "run", lambda argv, **_k: (seen.append(argv), _OK())[1]
    )

    graphify_ops.affected(tmp_path, ["sym", "--depth", "3", "--relation", "calls"])
    argv = seen[0]
    assert argv[argv.index("--depth") + 1] == "3"
    assert argv[argv.index("--relation") + 1] == "calls"


def test_the_cli_dispatches_affected(monkeypatch, tmp_path: Path) -> None:
    """The wiring, not the function — `uv run kb-setup affected` must REACH it.

    `mise-tasks-only.md` makes the task the only supported entry point, so a
    correct `affected()` that no dispatch branch calls is a feature nobody can
    run. This is the realistic break: deleting the dispatch line, not renaming
    the function.
    """
    from kb_setup import cli, graphify_ops

    called: list[tuple[Path, list[str]]] = []
    monkeypatch.setattr(
        graphify_ops, "affected", lambda root, rest: (called.append((root, list(rest))), 0)[1]
    )
    monkeypatch.chdir(tmp_path)

    assert cli.main(["affected", "sym", "--depth", "3"]) == 0
    assert len(called) == 1
    assert called[0][1] == ["sym", "--depth", "3"]
