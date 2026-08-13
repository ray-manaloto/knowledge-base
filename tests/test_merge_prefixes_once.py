# Copyright (c) 2026 Raymond Manaloto
"""Every merged source's node ids carry EXACTLY ONE `repo::` prefix (#120).

Why this exists, measured on the 2026-08-03 aggregate before the fix:

    node ids scanned                    218,243
      1 '::' separator                    9,645   (4.4%)
     10 '::' separators                  90,795
     22 '::' separators                  11,932

    id-bearing bytes (id/source/target/_src/_tgt)
      as written                    296,904,672
      with repeats collapsed        112,626,720
      waste                         184,277,952   (33% of the WHOLE file)

That is what took `graphify-out/graph.json` to 532.1 MiB, past graphify's
512 MiB read cap — and the cap is enforced on READ, so the failure was not a
slow graph but an aggregate that `query`, `explain` and `path` all refused to
open. Collapsing the repeats alone returns it to ~356 MiB, under the stock
default.

The cause is a two-part fit, neither half a bug on its own:
`prefix_graph_for_global` (`build.py:1449`) prefixes every input
unconditionally, with no already-prefixed guard; and `build()` used to merge
PAIRWISE, feeding `graph.json` back in as an input once per source. graphify's
`merge-graphs` accepts N paths in one call, which prefixes each exactly once.

Two levels, because either alone is insufficient. The unit arm catches "someone
restored the loop" without needing a binary. The integration arm is the only one
that can catch graphify itself changing under us — a unit test asserting we
issue one call proves nothing about what that call does.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import merge_recorder
from kb_setup import graph
from kb_setup.graphify_env import clean_env, graphify_exe

_TIMEOUT = 300


def _manifest(tmp_path: Path, name: str) -> None:
    src = tmp_path / "sources"
    (src / name).mkdir(parents=True, exist_ok=True)
    (src / f"{name}.manifest").write_text(
        "url = https://example.invalid/o/x\n"
        "ref = main\n"
        "commit = 03853a019423ffb5c5082e24c39ac20e38a7cfb1\n"
        "kind = code\n",
        encoding="utf-8",
    )
    sub = src / name / "graphify-out" / "graph.json"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text(f'{{"nodes": [], "edges": [], "from": "{name}"}}', encoding="utf-8")


def test_build_composes_every_corpus_source_in_one_merge(monkeypatch, tmp_path):
    """One `merge-graphs` call for the whole corpus AND our own code.

    Never one per source, and never a second call for self (#175).

    Realistic break: restoring the seed-plus-loop. That is not a hypothetical
    mutation, it is the code this replaced, and it is the shape someone reaches
    for again when adding a per-source step (a filter, a progress line, a retry)
    — the loop looks like the natural place to put it. Reintroducing a SEPARATE
    self-merge call is the same defect one call later (#175's own restructure) —
    both feed an already-merged `out` back into `merge-graphs` as an input.

    Asserting on the COUNT and not merely on "the sources appear somewhere" is
    the whole point: a pairwise loop mentions every source too, and passes any
    membership assertion, while writing 33% duplicated prefix.
    """
    for name in ("aaa", "mmm", "zzz"):
        _manifest(tmp_path, name)
    (tmp_path / "sources" / "extractions").mkdir(parents=True, exist_ok=True)

    calls: list[list[str]] = []
    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph, "_detect_preflight", lambda _manifests: None)
    monkeypatch.setattr(graph, "_extract_code", lambda _root, _name: True)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph.graphify_ops, "label", lambda _root: 0)
    monkeypatch.setattr(graph.graph_checks, "assert_composition", lambda _path, **_kw: None)
    monkeypatch.setattr(graph, "_run", merge_recorder(calls))

    graph.build(tmp_path)

    out = str(tmp_path / "graphify-out" / "graph.json")
    self_sub = str(graph._self_subgraph(tmp_path))
    # Since #175 the self sub-graph is an ORDINARY input to this same call, not
    # excluded from it — there is no second merge left to exclude by name.
    corpus_merges = [c for c in calls if "merge-graphs" in c and c[-1] == out]

    assert len(corpus_merges) == 1, (
        f"expected ONE merge composing all 3 corpus sources plus self; got "
        f"{len(corpus_merges)}. A per-source loop (or a second self-merge call) "
        f"re-prefixes the accumulator every iteration — 33% of the 2026-08-03 "
        f"graph.json was duplicated `repo::` prefix. argv were {corpus_merges}"
    )
    argv = corpus_merges[0]
    for name in ("aaa", "mmm", "zzz"):
        assert any(f"/{name}/graphify-out/graph.json" in a for a in argv), (
            f"corpus source {name!r} is not among the merge inputs; argv was {argv}"
        )
    assert self_sub in argv, (
        f"the self sub-graph must join this ONE merge as an ordinary input "
        f"(#175), not a second call; argv was {argv}"
    )
    assert out not in argv[: argv.index("--out")], (
        f"graph.json was fed back in as an INPUT to its own composition — that is "
        f"the accumulator re-prefix defect itself; argv was {argv}"
    )


#: The repo root, so `graphify_exe` answers from THIS repo's pin.
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _graphify() -> str:
    """The PINNED graphify, resolved through mise — never `shutil.which`.

    Not interchangeable. `command -v graphify` on this host resolves to
    `~/.local/share/mise/installs/pipx-graphifyy/<ver>/bin/graphify` — a raw
    install dir ahead of the shims — and more than one version is installed. An
    integration arm that runs whichever binary PATH happens to reach is not
    evidence about the version this repo builds its corpus with, which is the
    only version the claim is about. `graphify_exe` answers from mise's config
    for `_REPO_ROOT`, so it follows the pin by construction.
    """
    exe = graphify_exe(_REPO_ROOT)
    if not Path(exe).is_file():
        pytest.skip(f"graphify is not installed at {exe!r} — run `mise install`")
    return exe


def _repo_graph(root: Path, tag: str, ids: list[str]) -> Path:
    """A minimal node_link graph at `<root>/<tag>/graphify-out/graph.json`.

    The nesting is not decoration: `distinct_repo_tags` derives each input's
    prefix from `path.parent.parent.name`, so a flat layout would tag every
    input with the same directory and the test would measure a collision instead
    of a prefix.
    """
    p = root / tag / "graphify-out" / "graph.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "directed": False,
                "multigraph": False,
                "graph": {},
                "nodes": [{"id": i, "label": i, "file_type": "code"} for i in ids],
                "links": [{"source": ids[0], "target": ids[1]}] if len(ids) > 1 else [],
            }
        ),
        encoding="utf-8",
    )
    return p


def _depths(merged: Path) -> list[int]:
    data = json.loads(merged.read_text(encoding="utf-8"))
    return [str(n["id"]).count("::") for n in data["nodes"]]


def test_an_n_ary_merge_prefixes_each_input_exactly_once(tmp_path):
    """The tool-level claim the unit arm above rests on but cannot check.

    If graphify ever changed `merge-graphs` to prefix differently, the unit test
    would stay green while the aggregate silently regrew — which is precisely how
    this defect survived two prior sessions that both wrote workarounds for its
    symptom (`STUDY_GRAPH_NAME`'s partition, and the #101 namespace note).
    """
    exe = _graphify()
    inputs = [
        _repo_graph(tmp_path, "alpha", ["a_one", "a_two"]),
        _repo_graph(tmp_path, "beta", ["b_one", "b_two"]),
        _repo_graph(tmp_path, "gamma", ["g_one", "g_two"]),
    ]
    out = tmp_path / "merged.json"
    subprocess.run(
        [exe, "merge-graphs", *[str(p) for p in inputs], "--out", str(out)],
        check=True,
        timeout=_TIMEOUT,
        capture_output=True,
        env=clean_env(),
    )

    depths = _depths(out)
    assert len(depths) == 6, f"expected all 6 nodes to survive the merge; got {len(depths)}"
    assert set(depths) == {1}, (
        f"an N-ary merge did not prefix each input exactly once — id depths were "
        f"{sorted(set(depths))}. `_merge_sources_into` assumes it does; if graphify "
        f"changed, that assumption is now silently wrong."
    )


def test_the_pairwise_loop_really_does_accumulate_prefixes(tmp_path):
    """CONTROL ARM — without it the test above is a coin with one face.

    It reproduces the OLD shape against the SAME binary and the same fixtures. If
    this does not accumulate, then the assertion above passes for some reason
    other than the one claimed, and the whole diagnosis is wrong.

    This is also the one place the pre-fix behaviour stays executable, which is
    what stops "33% of the file was duplicated prefix" from decaying into an
    inherited number nobody can re-derive.
    """
    exe = _graphify()
    inputs = [
        _repo_graph(tmp_path, "alpha", ["a_one", "a_two"]),
        _repo_graph(tmp_path, "beta", ["b_one", "b_two"]),
        _repo_graph(tmp_path, "gamma", ["g_one", "g_two"]),
    ]
    acc = tmp_path / "acc" / "graphify-out" / "graph.json"
    acc.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(inputs[0], acc)
    for sub in inputs[1:]:
        subprocess.run(
            [exe, "merge-graphs", str(acc), str(sub), "--out", str(acc)],
            check=True,
            timeout=_TIMEOUT,
            capture_output=True,
            env=clean_env(),
        )

    depths = _depths(acc)
    assert max(depths) > 1, (
        f"the pairwise loop did NOT accumulate prefixes (depths {sorted(set(depths))}), "
        f"so the N-ary assertion above is not evidence of anything and #120's "
        f"diagnosis needs redoing against this binary."
    )
