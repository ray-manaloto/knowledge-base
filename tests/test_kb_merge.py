"""Tests for `kb-merge` (`kb_setup.graphify_ops.merge_chunk`).

The defect these pin down was invisible for the same reason it was expensive:
`graph-prose.json` is derived from `graph.json`, `kb-build` re-derives it, and a
merge-only ingestion did not — so `kb-query --prose`, the arm this repo
*recommends* for a question about the documents, went on answering from the
corpus as it stood before the merge, and the next unrelated `kb-build` quietly
repaired it. Nothing failed; the answers were just older than the graph.

So the load-bearing test here is not "merge_chunk returns the subprocess rc".
It is :func:`test_a_successful_merge_re_derives_the_prose_graph` paired with
:func:`test_a_failed_merge_leaves_the_prose_graph_alone` — the second is the
control arm, and without it the first passes just as well for a `merge_chunk`
that derives unconditionally, which is a different and worse function.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

from kb_setup import graphify_ops, prose

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

#: What the stub writes as the merged graph: one AST node the derivation must
#: drop, and one prose node it must keep. Naming the merged node lets a test
#: assert the prose graph holds THIS merge rather than merely holding something.
_AST_NODE = {"id": "sym", "label": "sym", "_origin": "ast", "file_type": "code"}
_PROSE_NODE = {"id": "just_merged", "label": "just_merged", "file_type": "concept"}

_MERGED: dict[str, object] = {
    "graph": {"hyperedges": []},
    "nodes": [_AST_NODE, _PROSE_NODE],
    "links": [],
}

_PRE_MERGE: dict[str, object] = {
    "graph": {"hyperedges": []},
    "nodes": [{"id": "yesterday", "label": "yesterday", "file_type": "concept"}],
    "links": [],
}


def _repo(tmp_path: Path) -> Path:
    """A repo root with a pre-merge `graph.json` and a prose graph derived from it."""
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text(json.dumps(_PRE_MERGE), encoding="utf-8")
    prose.prose_graph_path(tmp_path).write_text(json.dumps(_PRE_MERGE), encoding="utf-8")
    return tmp_path


def _chunk(tmp_path: Path) -> str:
    """A chunk file on disk. Its CONTENT is irrelevant — the merge is stubbed."""
    path = tmp_path / "chunk.json"
    path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    return str(path)


def _stub_merge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    rc: int,
    writes: dict[str, object] | None = None,
) -> None:
    """Stand in for `_merge_docs.py` under graphify's interpreter.

    The real thing needs graphify's bundled environment, which a unit test has
    no business standing up. What the stub does reproduce is the part that
    matters to the caller: an rc, and whether `graph.json` changed.
    """

    def fake_run(cmd: Sequence[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        if writes is not None:
            (tmp_path / "graphify-out" / "graph.json").write_text(
                json.dumps(writes), encoding="utf-8"
            )
        return subprocess.CompletedProcess(list(cmd), rc)

    monkeypatch.setattr(graphify_ops, "graphify_python", lambda _root: "/nonexistent/python")
    monkeypatch.setattr(graphify_ops.subprocess, "run", fake_run)


def _prose_ids(repo_root: Path) -> list[str]:
    """Node ids in the derived prose graph."""
    data = json.loads(prose.prose_graph_path(repo_root).read_text(encoding="utf-8"))
    return [str(n["id"]) for n in cast("list[dict[str, object]]", data["nodes"])]


def test_a_successful_merge_re_derives_the_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The direction the fix exists for: `--prose` must see what was just merged.

    Asserting on the merged node's id, not on a count or an mtime: a count moves
    for a re-derivation of the OLD graph too, and an mtime moves for a file that
    was rewritten with identical content. The id is the only one of the three
    that cannot be satisfied by a derivation of the wrong corpus.
    """
    repo = _repo(tmp_path)
    _stub_merge(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 0
    assert _prose_ids(repo) == ["just_merged"]


def test_a_failed_merge_leaves_the_prose_graph_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the derivation is gated on the merge's rc, not unconditional.

    Without this, a `merge_chunk` that derives whatever the state of the world
    passes the test above just as happily — and would replace a valid prose
    graph off the back of a merge that failed, possibly half-written.
    """
    repo = _repo(tmp_path)
    _stub_merge(monkeypatch, tmp_path, rc=1)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1
    assert _prose_ids(repo) == ["yesterday"]


def test_a_merge_whose_derivation_fails_does_not_report_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The chunk landed, the `--prose` arm did not. rc=0 would say otherwise.

    `prose.derive` unlinks first, so this leaves NO prose graph — the right
    artifact state (a stale one is indistinguishable from a fresh one to every
    consumer) reached by a path the caller has to be told about, because the
    graph really did change underneath them.
    """
    repo = _repo(tmp_path)
    # An all-AST graph: nothing survives the drop rule, so `derive` refuses.
    _stub_merge(
        monkeypatch,
        tmp_path,
        rc=0,
        writes={"graph": {"hyperedges": []}, "nodes": [_AST_NODE], "links": []},
    )

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1
    assert not prose.prose_graph_path(repo).exists()
    assert "kb-prose" in capsys.readouterr().err


def test_a_missing_chunk_is_refused_before_anything_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing behaviour, pinned so the new tail cannot start reaching it."""
    repo = _repo(tmp_path)
    _stub_merge(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, str(tmp_path / "absent.json")) == 2
    assert _prose_ids(repo) == ["yesterday"]
