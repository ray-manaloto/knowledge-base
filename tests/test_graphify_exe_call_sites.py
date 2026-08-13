# Copyright (c) 2026 Raymond Manaloto
"""Every corpus-affecting call site must actually REACH `graphify_exe`.

This file exists because the #40 fix shipped without it, and a cold reviewer
proved the gap the only way that counts: it reverted `graphify_exe(repo_root)`
back to a bare `"graphify"` in all four modules — undoing the entire fix — and
the full suite still passed, rc=0, zero failures.

`tests/test_graphify_env.py` tests the resolver in isolation; nothing tested
that a caller uses it. And the one assertion edited for the change,
`Path(argv[0]).name == "graphify"`, is true of the bare name too, so it could
not have caught the revert either.

So the sentinel here is deliberately a path whose BASENAME IS STILL "graphify"
(`…/SENTINEL/graphify`). A test asserting only the basename would pass against
the bare name; asserting the whole argv[0] is what discriminates. Each test
below fails if its call site stops going through the resolver.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import artifacts, graph, graphify_ops, graphify_sdk, stamps

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest


def _sentinel(tmp_path: Path) -> str:
    """An executable-looking path that a bare "graphify" can never equal."""
    exe = tmp_path / "SENTINEL" / "graphify"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    return str(exe)


class _Recorder:
    """Captures argv[0] of every subprocess.run, and never runs anything."""

    def __init__(self) -> None:
        self.argv0: list[str] = []

    def __call__(
        self, cmd: Sequence[str], *_a: object, **_k: object
    ) -> subprocess.CompletedProcess[str]:
        if cmd:
            self.argv0.append(str(cmd[0]))
        return subprocess.CompletedProcess(args=list(cmd), returncode=0, stdout="", stderr="")


def test_extract_code_runs_the_resolved_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """kb-build's AST pass — the one that produces the corpus."""
    exe = _sentinel(tmp_path)
    rec = _Recorder()
    subgraph = tmp_path / "sources" / "somesource" / "graphify-out" / "graph.json"
    subgraph.parent.mkdir(parents=True)
    subgraph.write_text('{"nodes": [{"id": "one"}], "links": []}', encoding="utf-8")
    monkeypatch.setattr(graph, "graphify_exe", lambda _root: exe)
    monkeypatch.setattr(graphify_sdk, "detect_checked", lambda _root: ({}, object()))
    monkeypatch.setattr(graph.subprocess, "run", rec)

    graph._extract_code(tmp_path, "somesource")

    assert rec.argv0 == [exe], f"extract ran {rec.argv0}, not the resolved binary"


#: Modules whose graphify invocations are OPERATIONAL — they read or write the
#: corpus, so the binary must follow the pin, not PATH order.
_OPERATIONAL = ("graph.py", "graphify_ops.py", "artifacts.py", "brain.py")

#: Modules that deliberately keep a bare `graphify`. Not an oversight: they
#: MEASURE the binary a session actually resolves, and `_corpus_stamp` records
#: which one that was. Pinning them would turn an ecological measurement into a
#: hypothetical one. Listed here so the contract below cannot quietly grow to
#: cover them, and so removing one is a visible diff.
_MEASUREMENT = ("evals.py", "eval_cases.py")


def test_no_operational_module_hard_codes_a_bare_graphify() -> None:
    """The contract that survives what a behavioural test cannot reach.

    `build()` and `update()` clone repos and hit the network, so exercising
    their merge/update steps in a unit test would mock away the very argv under
    test — which is exactly the shape of the two tests this replaces: they
    constructed `[graphify_exe(...), "merge-graphs"]` themselves and would have
    passed against a fully reverted module.

    This asserts on the source instead, and it is aimed precisely at the
    mutation the reviewer used: `sed 's/graphify_exe(repo_root)/"graphify"/'`.
    """
    src = Path(__file__).resolve().parents[1] / "python" / "src" / "kb_setup"
    offenders = [
        f"{name}:{n}"
        for name in _OPERATIONAL
        for n, line in enumerate((src / name).read_text(encoding="utf-8").splitlines(), 1)
        if '"graphify",' in line or line.strip() == '"graphify",'
    ]
    assert not offenders, (
        f"bare `graphify` argv[0] in an operational module: {offenders}. "
        f"Use graphify_env.graphify_exe(repo_root) — see #40."
    )


def test_the_measurement_modules_still_do_hard_code_it() -> None:
    """CONTROL ARM, and the one that makes the contract above discriminating.

    If this fails, either the exclusion was silently dropped (the evals stopped
    measuring what a session really resolves) or the detection string no longer
    matches anything — in which case the test above is vacuous and has been
    passing for free. Both are worth failing over.
    """
    src = Path(__file__).resolve().parents[1] / "python" / "src" / "kb_setup"
    found = [
        name
        for name in _MEASUREMENT
        if any(
            '"graphify",' in line for line in (src / name).read_text(encoding="utf-8").splitlines()
        )
    ]
    assert sorted(found) == sorted(_MEASUREMENT), (
        f"expected a deliberate bare `graphify` in {_MEASUREMENT}, found it in {found}"
    )


def test_label_runs_the_resolved_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """kb-label — and its gate must not refuse the binary it just resolved."""
    exe = _sentinel(tmp_path)
    rec = _Recorder()
    # A successful label now re-derives the prose graph, which needs a built
    # graph to derive FROM. Completing the fixture rather than relaxing the
    # assertion: the rc this test reads is still the one the PATH gate produces,
    # and `graphify label` cannot succeed against a repo with no graph anyway.
    (tmp_path / "graphify-out").mkdir(exist_ok=True)
    (tmp_path / "graphify-out" / "graph.json").write_text(
        '{"nodes": [{"id": "doc", "label": "doc"}], "links": [], "graph": {"hyperedges": []}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _root: exe)
    monkeypatch.setattr(graphify_ops.subprocess, "run", rec)

    rc = graphify_ops.label(tmp_path)

    assert rc == 0, "the PATH gate refused a binary that resolved fine"
    assert rec.argv0 == [exe]


def test_label_still_refuses_when_nothing_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the gate must still fire when the binary genuinely is absent.

    Without this, the test above is satisfied by deleting the gate entirely.
    `graphify_exe`'s last resort is the bare name, which is not a file.
    """
    rec = _Recorder()
    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _root: "graphify")
    monkeypatch.setattr(graphify_ops.subprocess, "run", rec)

    assert graphify_ops.label(tmp_path) == 2
    assert rec.argv0 == [], "it ran something despite refusing"


def test_artifacts_run_the_resolved_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """kb-artifacts — every derived view, one resolve hoisted out of the loop."""
    exe = _sentinel(tmp_path)
    rec = _Recorder()
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")

    monkeypatch.setattr(artifacts, "graphify_exe", lambda _root: exe)
    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _root: [])
    monkeypatch.setattr(stamps, "refresh_after_regen", lambda _root, **_kwargs: None)
    monkeypatch.setattr(artifacts.subprocess, "run", rec)

    artifacts.generate(tmp_path, only=["wiki", "graphml"])

    assert rec.argv0 == [exe, exe], f"artifacts ran {rec.argv0}"
