"""`build()` must index THIS repo's own python library, not only its sources.

Why this exists. `graphify affected "<symbol>"` is the blast-radius question —
"what breaks if I change this?" — and it was unanswerable about our own code for
a reason that had nothing to do with graphify: `python/src/kb_setup/` was simply
never extracted. Measured at the commit before this test landed, over the built
`graphify-out/graph.json` and keyed on each node's `source_file`:

    graphify/extractors/   ->  429 nodes
    cognee/api/            ->  793 nodes
    zzz_bogus_path         ->    0 nodes   (the probe discriminates)
    python/src/kb_setup    ->    0 nodes   <- all 37 tracked files absent

So every `affected` query about our own library returned "No unique node match",
which is the SAME string it returns for a symbol that does not exist. A missing
index and a missing symbol were indistinguishable — a false negative that
announces nothing, which is why the fix needs a test rather than a one-off check.

`kb_setup` is not ordinary application code: dotfiles consumes it as a pinned
`uv` git dependency, so a change here has a blast radius that leaves the repo.

Also covers `refresh_self` (#175): the single-N-ary-merge restructure removed
the base-snapshot/guard machinery `kb-watch` used to restart from, so there is
no longer a separable "corpus without our own code" state to snapshot. The
function is now a loud, immediate refusal rather than a resurrection of that
machinery for a build shape it no longer matches — see `refresh_self`'s own
docstring in `graph.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import merge_recorder
from kb_setup import graph
from kb_setup import manifest as mf


def _manifest(tmp_path: Path, name: str = "demo") -> mf.Manifest:
    src = tmp_path / "sources"
    (src / name).mkdir(parents=True, exist_ok=True)
    m = mf.Manifest(
        name=name,
        path=src / f"{name}.manifest",
        url="https://example.invalid/o/demo",
        ref="main",
        commit="03853a019423ffb5c5082e24c39ac20e38a7cfb1",
        kind="code",
    )
    m.path.write_text(
        f"url = {m.url}\nref = {m.ref}\ncommit = {m.commit}\nkind = code\n", encoding="utf-8"
    )
    return m


def _run_build(monkeypatch, tmp_path: Path, run=None, assert_composition=None) -> list[list[str]]:
    """Drive `build()` past its side effects; return every argv it shelled out.

    Everything stubbed here is I/O the assertion does not depend on (cloning,
    stamping). `_run` is captured rather than stubbed away because the merge
    argv IS the behaviour under test — asserting on a recorded call to a
    helper we are about to write would be tautological, while asserting that
    the self sub-graph reaches `merge-graphs` is a claim about the built
    artifact.

    `graphify_ops.label` and `graph_checks.assert_composition` are stubbed for
    a different reason than the rest: both run against REAL graph.json content
    (a subprocess label pass; a `json.load` of the merged file), and
    `apply_merge`'s stand-in for `merge-graphs` concatenates each fixture's raw
    text — enough for an argv/substring assertion, not valid JSON either of
    these could run against. Composition correctness has its own fixture-driven
    suite in `tests/test_graph_checks.py`; this file is about the merge shape.
    """
    calls: list[list[str]] = []
    # TWO manifests deliberately. `_merge_sources_into` COPIES a lone input —
    # `merge-graphs` requires two paths — so a single-manifest fixture shells out
    # to nothing and the control arm below would fail at HEAD for a reason that
    # has nothing to do with what it checks. (Before #120 the same requirement
    # came from a different mechanism: the first source seeded and only the rest
    # were merged.)
    _manifest(tmp_path, "aaa-seed")
    _manifest(tmp_path, "zzz-merged")
    (tmp_path / "sources" / "extractions").mkdir(parents=True, exist_ok=True)

    # Both sub-graphs are written for real, with distinguishable bytes, and the
    # `_run` stub models `merge-graphs` on disk (`apply_merge`). That is what
    # lets the assertions below work on CONTENT rather than on "was copy called".
    for name, marker in (("aaa-seed", "seed"), ("zzz-merged", "merged")):
        sub = tmp_path / "sources" / name / "graphify-out" / "graph.json"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.write_text(f'{{"nodes": [], "edges": [], "{marker}": true}}', encoding="utf-8")

    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph, "_extract_code", lambda _root, _name: True)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph.graphify_ops, "label", lambda _root: 0)
    monkeypatch.setattr(
        graph.graph_checks, "assert_composition", assert_composition or (lambda _path: None)
    )
    monkeypatch.setattr(graph, "_run", run or merge_recorder(calls))

    graph.build(tmp_path)
    return calls


def test_our_own_library_reaches_the_aggregate_graph(monkeypatch, tmp_path):
    """The library must be merged in, or blast radius on our own code is a lie.

    Realistic break: delete the `_extract_self` call from `build()`. That is how
    this regresses — not by renaming anything, but by a later refactor dropping
    one line from the source list, which no other test would notice.
    """
    merged = [c for c in _run_build(monkeypatch, tmp_path) if "merge-graphs" in c]
    joined = " ".join(a for c in merged for a in c)

    # One root, so ONE sub-graph carries both trees (#101). This used to be two
    # assertions on the substrings "python" and "tests", which was right while
    # there were two runs and is a trap now: every tmp_path in this suite ends in
    # a directory whose name contains neither, but a real repo root path could
    # contain either by accident, so substring-matching tree names would pass
    # without the self sub-graph being merged at all.
    assert str(graph._self_subgraph(tmp_path)) in joined, (
        f"no self sub-graph reached merge-graphs; merge argv were {merged}. "
        "python/src/kb_setup is 0 of 37 files in the graph without it, and "
        "`affected` cannot answer which tests cover a symbol."
    )


def test_manifest_sources_are_still_merged(monkeypatch, tmp_path):
    """CONTROL ARM for the test above.

    Without it, a `build()` that merged ONLY our own library — dropping every
    pinned upstream source — would satisfy the assertion above while destroying
    the corpus. That is the cheapest wrong way to make this pass, so it gets its
    own arm rather than a comment.
    """
    merged = [c for c in _run_build(monkeypatch, tmp_path) if "merge-graphs" in c]
    joined = " ".join(a for c in merged for a in c)
    assert "zzz-merged" in joined, (
        f"the pinned upstream source stopped being merged; merge argv were {merged}"
    )


def test_the_self_subgraph_joins_the_one_corpus_merge_not_a_second_call(monkeypatch, tmp_path):
    """#175: the self sub-graph joins the single corpus merge, not a second call.

    It is now ONE input to that merge rather than a second `merge-graphs`
    call that feeds the just-merged aggregate back in as an input.

    Realistic break: restoring the old two-step shape (compose the corpus,
    THEN `merge-graphs(out, self_sub, --out=out)`) — exactly the code this
    replaces, and it re-prefixes every id already merged (#120's own defect,
    one call late instead of one loop late).
    """
    calls = _run_build(monkeypatch, tmp_path)
    out = str(tmp_path / "graphify-out" / "graph.json")
    merges_into_out = [c for c in calls if "merge-graphs" in c and c[-1] == out]

    assert len(merges_into_out) == 1, (
        f"expected ONE merge-graphs call composing the corpus AND self code; "
        f"got {len(merges_into_out)}. argv were {merges_into_out}"
    )
    assert str(graph._self_subgraph(tmp_path)) in merges_into_out[0], (
        f"the self sub-graph did not join the one corpus merge; argv was {merges_into_out[0]}"
    )
    # No merge-graphs call anywhere may feed the aggregate BACK IN as an input —
    # the standing invariant #120 fixed, restated for a world with no second
    # self-merge to name-exclude.
    for c in calls:
        if "merge-graphs" not in c or "--out" not in c:
            continue
        assert out not in c[: c.index("--out")], (
            f"graph.json was fed back into merge-graphs as an INPUT — that is "
            f"the accumulator re-prefix defect itself; argv was {c}"
        )


def test_build_calls_assert_composition_on_the_artifact_it_produced(monkeypatch, tmp_path):
    """The composition guard must actually run, not merely exist.

    Every other test in this file stubs `graph_checks.assert_composition` away
    as a no-op (it would otherwise `json.load` the fake concatenated content
    `apply_merge` produces) — which means none of them would notice if the
    call were deleted from `build()` entirely. This is the one that would:
    it replaces the no-op with a spy and asserts the call actually happened,
    against the exact path `build()` just finished writing.
    """
    seen: list[Path] = []
    _run_build(monkeypatch, tmp_path, assert_composition=seen.append)
    assert seen == [tmp_path / "graphify-out" / "graph.json"], (
        f"build() did not call assert_composition on the graph it just wrote; saw {seen}"
    )


def test_refresh_self_refuses_loudly(tmp_path):
    """`kb-watch` has no recomposition story under the single-merge build (#175).

    The base-snapshot/guard machinery this replaces existed only to make an
    incremental restart safe for a build with a SEPARABLE self-merge step; the
    single N-ary merge has no such step to restart from. Refusing is the
    honest answer until a real design lands, not a resurrection of machinery
    built for a shape `build()` no longer has.
    """
    with pytest.raises(SystemExit) as exc:
        graph.refresh_self(tmp_path)
    assert "not yet implemented" in str(exc.value), (
        f"the refusal must say WHY it refuses; it said {exc.value!r}"
    )
    assert "kb-build" in str(exc.value), (
        f"the refusal must point at the real recovery path; it said {exc.value!r}"
    )


def test_refresh_self_refuses_without_touching_anything(tmp_path):
    """CONTROL ARM: a refusal that already did partial work first is not a refusal.

    Without this, a `refresh_self` that clones, extracts, or merges before
    raising would satisfy the test above while still doing everything the stub
    exists NOT to do — network calls and a multi-minute extract+merge loop, for
    a function whose whole contract is now "refuse immediately".
    """
    out = tmp_path / "graphify-out" / "graph.json"
    out.parent.mkdir(parents=True)
    out.write_text('{"nodes": [], "UNTOUCHED": true}', encoding="utf-8")

    with pytest.raises(SystemExit):
        graph.refresh_self(tmp_path)

    assert out.read_text(encoding="utf-8") == '{"nodes": [], "UNTOUCHED": true}', (
        "refresh_self did work before refusing — a stub must refuse FIRST"
    )
