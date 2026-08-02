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
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import graph
from kb_setup import manifest as mf
from kb_setup.currency import config, sync

#: Imported rather than restated: a literal copy here would keep passing after a
#: rename, testing a filename nothing writes.
_BASE_NAME = graph.BASE_GRAPH_NAME


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


def _run_build(monkeypatch, tmp_path: Path, run=None) -> list[list[str]]:
    """Drive `build()` past its side effects; return every argv it shelled out.

    Everything stubbed here is I/O the assertion does not depend on (cloning,
    copying the seed graph, the doc-chunk replay, prose derivation, stamping).
    `_run` is captured rather than stubbed away because the merge argv IS the
    behaviour under test — asserting on a recorded call to a helper we are about
    to write would be tautological, while asserting that the self sub-graph
    reaches `merge-graphs` is a claim about the built artifact.
    """
    calls: list[list[str]] = []
    # TWO manifests deliberately: `build()` seeds graph.json from the first
    # code-bearing source and only `merge-graphs` the REST, so a single-manifest
    # fixture shells out to nothing and the control arm below would fail at HEAD
    # for a reason that has nothing to do with what it checks.
    _manifest(tmp_path, "aaa-seed")
    _manifest(tmp_path, "zzz-merged")
    (tmp_path / "sources" / "extractions").mkdir(parents=True, exist_ok=True)

    # The seed sub-graph is written for real and `shutil.copy` is NOT stubbed, so
    # graph.json and the base snapshot are actual files. That is what lets the
    # base-snapshot tests below assert on CONTENT rather than on "was copy called".
    seed_sub = tmp_path / "sources" / "aaa-seed" / "graphify-out" / "graph.json"
    seed_sub.parent.mkdir(parents=True, exist_ok=True)
    seed_sub.write_text('{"nodes": [], "edges": [], "seed": true}', encoding="utf-8")

    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph, "_extract_code", lambda _root, _name: True)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)
    monkeypatch.setattr(
        graph, "_run", run or (lambda argv, _root: calls.append([str(a) for a in argv]))
    )

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

    assert "python" in joined, (
        f"no self sub-graph reached merge-graphs; merge argv were {merged}. "
        "python/src/kb_setup is 0 of 37 files in the graph without it."
    )
    # `tests/` is a SEPARATE assertion, not an extension of the one above:
    # "which tests cover this symbol?" is the blast-radius question with the
    # most day-to-day value, and the 40 test files / 14,090 LOC that answer it
    # live outside `python/`. Ray widened P1 to include them (2026-07-31).
    assert "tests" in joined, (
        f"the test tree did not reach merge-graphs; merge argv were {merged}. "
        "Without it, `affected` cannot answer which tests cover a symbol."
    )


def _stamped_repo(tmp_path: Path) -> Path:
    """A repo root with a declared+stamped aggregate graph, per test_currency_sync."""
    (tmp_path / "mise.toml").write_text(
        '[tools]\n"pipx:graphifyy" = { version = "0.9.32", extras = ["all"] }\n', encoding="utf-8"
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    agg = tmp_path / "graphify-out" / "graph.json"
    agg.parent.mkdir(parents=True, exist_ok=True)
    agg.write_text('{"nodes": []}', encoding="utf-8")
    # `refresh_self` restarts from the base rather than appending to graph.json,
    # so a fixture without one is a repo that has never been built. Distinct
    # content from graph.json on purpose: identical bytes would let a refresh that
    # skipped the copy still look correct.
    (agg.parent / _BASE_NAME).write_text('{"nodes": [], "base": true}', encoding="utf-8")
    return tmp_path


def test_refresh_self_restamps_so_the_graph_stays_verifiable(monkeypatch, tmp_path):
    """`kb-watch` must restamp, or currency step 1 goes permanently red.

    This asserts on the ARTIFACT, not on a recorded call to the helper being
    written — `stamped == observed` is a claim about the stamp file agreeing with
    graph.json, which is exactly what `kb-currency-check` compares. Asserting that
    some `_restamp` function was invoked would pass just as happily on a restamp
    that wrote the wrong bytes.

    Realistic break: drop the restamp call. `artifact_fingerprints` is
    `size:mtime_ns`, so ANY rewrite of graph.json moves it; without the restamp
    the very next session reports the graph as not verifiably built by the pin.
    """
    root = _stamped_repo(tmp_path)
    spec = config.load(root)[0]
    sync.write_stamp(root, spec, version="0.9.32", source_ref="", inputs=None)
    assert sync.stamped_fingerprints(sync.read_stamp(root, spec)) == sync.artifact_fingerprints(
        root, spec
    ), "fixture is wrong: the stamp must agree with the artifact BEFORE the refresh"

    agg = root / "graphify-out" / "graph.json"

    def _fake_run(argv: list[str], _root: Path) -> None:
        # The merge really does rewrite graph.json; a stub that left the bytes
        # untouched would make the fingerprint agree for free and the assertion
        # below could never fail.
        if "merge-graphs" in [str(a) for a in argv]:
            agg.write_text(agg.read_text(encoding="utf-8") + " ", encoding="utf-8")

    monkeypatch.setattr(graph, "_run", _fake_run)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)

    graph.refresh_self(root)

    assert sync.stamped_fingerprints(sync.read_stamp(root, spec)) == sync.artifact_fingerprints(
        root, spec
    ), (
        "refresh_self rewrote graph.json without restamping — kb-currency-check "
        "would report the graph as built by an unknown version every session after."
    )


def test_refresh_self_merges_both_self_trees(monkeypatch, tmp_path):
    """CONTROL ARM for the test above: restamping alone is not a refresh.

    A `refresh_self` that only restamped would satisfy the fingerprint assertion
    trivially — it never rewrites graph.json, so the stamp and the artifact agree
    by doing nothing. That is the cheapest wrong implementation, so it gets an arm.
    """
    root = _stamped_repo(tmp_path)
    spec = config.load(root)[0]
    sync.write_stamp(root, spec, version="0.9.32", source_ref="", inputs=None)

    calls: list[list[str]] = []
    monkeypatch.setattr(graph, "_run", lambda argv, _r: calls.append([str(a) for a in argv]))
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)

    graph.refresh_self(root)

    merged = " ".join(a for c in calls if "merge-graphs" in c for a in c)
    assert "python" in merged, f"python/ never reached merge-graphs; argv were {calls}"
    assert "tests" in merged, f"tests/ never reached merge-graphs; argv were {calls}"


def test_build_snapshots_a_base_that_excludes_our_own_code(monkeypatch, tmp_path):
    """`build()` must leave a self-free base for `kb-watch` to restart from.

    MEASURED, which is why this exists: `merge-graphs` re-namespaces node ids on
    every merge, so merging our sub-graph into an aggregate that already holds it
    produces a SECOND copy with a distinct id — 0 duplicate ids, 2,080 nodes where
    1,040 belong, and `affected` back to "No unique node match". Since `build()`
    always merges our code in, every later refresh is a second merge by
    construction; there is no invocation order that avoids it. The fix is to keep
    a base that has never seen our code.

    Two claims, and the ORDER one is the load-bearing half: a snapshot taken after
    the self-merge would be a perfectly valid file that silently reintroduces the
    duplication it exists to prevent.
    """
    base = tmp_path / "graphify-out" / _BASE_NAME
    # Recorded PER CALL, because "the file exists when build() returns" is true of
    # a snapshot taken in the wrong place too. What has to hold is that the base
    # already existed at the first self merge and did NOT exist before it.
    existed_at: list[tuple[str, bool]] = []

    def _watch_run(argv: list[str], _root: Path) -> None:
        joined = " ".join(str(a) for a in argv)
        existed_at.append((joined, base.is_file()))

    monkeypatch.setattr(graph, "_run", _watch_run)
    _run_build(monkeypatch, tmp_path, run=_watch_run)

    assert base.is_file(), f"build() wrote no {_BASE_NAME}; kb-watch has nothing to restart from"

    self_merges = [
        i for i, (j, _) in enumerate(existed_at) if "merge-graphs" in j and "python" in j
    ]
    assert self_merges, "no self merge happened at all — the wrong test is failing"
    assert existed_at[self_merges[0]][1], (
        "the base snapshot did not exist yet when our code was merged — it was "
        "taken too late, so it would carry our nodes and kb-watch would double them"
    )
    # Split rather than `and`-ed so a failure says WHICH half broke: "no external
    # merge ran" is a broken fixture, "the base already existed" is a real defect.
    before = [ok for j, ok in existed_at[: self_merges[0]] if "merge-graphs" in j]
    assert before, "no external merge ran before ours — the fixture is not exercising the order"
    assert not any(before), (
        f"the base snapshot already existed during the EXTERNAL merges "
        f"({before}) — taken too early, so kb-watch would drop pinned sources"
    )


def test_refresh_self_restarts_from_the_base_snapshot(monkeypatch, tmp_path):
    """`kb-watch` must rebuild graph.json FROM the base, never append to itself.

    Artifact-level on purpose. With `_run` stubbed no merge writes anything, so a
    correct `refresh_self` leaves graph.json byte-identical to the base; an
    implementation that merges into the CURRENT graph leaves the stale marker
    behind. That distinction is invisible to any assertion about which functions
    were called.

    Realistic break: deleting the `shutil.copy(base, out)` line — which is
    precisely the pre-fix behaviour, not an invented mutation.
    """
    root = _stamped_repo(tmp_path)
    spec = config.load(root)[0]
    sync.write_stamp(root, spec, version="0.9.31", source_ref="", inputs=None)

    base = root / "graphify-out" / _BASE_NAME
    base.write_text('{"nodes": [], "base": true}', encoding="utf-8")
    out = root / "graphify-out" / "graph.json"
    # Stands in for a previous kb-watch's output: graph.json already carries our
    # merged code. Restarting from the base must discard it, not add to it.
    out.write_text('{"nodes": [], "base": true, "STALE_SELF_MERGE": true}', encoding="utf-8")

    monkeypatch.setattr(graph, "_run", lambda _argv, _r: None)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)

    graph.refresh_self(root)

    assert "STALE_SELF_MERGE" not in out.read_text(encoding="utf-8"), (
        "refresh_self merged into the existing graph instead of restarting from "
        "the base snapshot — this is how our nodes doubled to 2,080 and affected "
        "went back to 'No unique node match'."
    )


def test_refresh_self_refuses_when_another_writer_touched_the_graph(monkeypatch, tmp_path):
    """`kb-merge` between build and watch must not be silently reverted.

    THE DEFECT THIS EXISTS FOR, found by a cold review and invisible to every
    other test here: `.base-graph.json` is written only by `build()`, but it is
    not the only writer of `graph.json`. `kb-merge` folds in a doc chunk and
    `kb-label` rewrites the graph, both legitimate between builds. Restarting
    from the snapshot then discarded their work AND restamped the result as
    verified, so `kb-currency-check` reported clean. Silent data loss with a
    green light.

    None of the sibling tests could catch it because none models a SECOND WRITER
    touching graph.json between build and watch — the same blind spot that hid
    the node-duplication bug. That is the point of this fixture: it writes to
    graph.json behind refresh_self's back, which is precisely what a stub cannot
    do to itself.
    """
    root = _stamped_repo(tmp_path)
    out = root / "graphify-out" / "graph.json"
    graph._write_base_guard(root)

    # Stand in for `mise run kb-merge` — a legitimate third-party write.
    out.write_text('{"nodes": [], "MERGED_DOC_CHUNK": true}', encoding="utf-8")

    monkeypatch.setattr(graph, "_run", lambda _a, _r: None)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)

    with pytest.raises(SystemExit) as exc:
        graph.refresh_self(root)

    assert "has changed" in str(exc.value), (
        f"refresh_self did not refuse a graph another writer had touched; it said {exc.value!r}"
    )
    assert "MERGED_DOC_CHUNK" in out.read_text(encoding="utf-8"), (
        "refresh_self destroyed the other writer's content before refusing — "
        "refusing after the damage is not refusing"
    )


def test_refresh_self_leaves_the_graph_intact_when_a_merge_fails(monkeypatch, tmp_path):
    """A refresh that dies part-way must not leave graph.json worse than it found it.

    Before staging, `shutil.copy(base, out)` wiped every self node FIRST and the
    loop rebuilt them on disk, so a graphify crash or Ctrl-C left a graph with the
    corpus but none of our code — `affected` back to "No unique node match", with
    no rollback. Milder than the guard defect only because the stamp is not
    rewritten on that path.
    """
    root = _stamped_repo(tmp_path)
    out = root / "graphify-out" / "graph.json"
    out.write_text('{"nodes": [], "PRE_EXISTING": true}', encoding="utf-8")
    graph._write_base_guard(root)
    before = out.read_text(encoding="utf-8")

    def _boom(argv: list[str], _r: Path) -> None:
        if "merge-graphs" in [str(a) for a in argv]:
            raise RuntimeError("graphify crashed mid-merge")

    monkeypatch.setattr(graph, "_run", _boom)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)

    with pytest.raises(RuntimeError):
        graph.refresh_self(root)

    assert out.read_text(encoding="utf-8") == before, (
        "a failed refresh damaged graph.json; the rebuild must be staged and "
        "swapped atomically so a crash leaves the previous graph untouched"
    )


def test_refresh_self_uses_one_extraction_path(monkeypatch, tmp_path):
    """`graphify update` and `extract --force` are NOT interchangeable here.

    The first implementation branched — `update` when a sub-graph already existed,
    `extract` otherwise — under a comment claiming "the two paths differ in cost,
    not in result". Measured on the real binary, that was false: the SAME file
    came out as `source_file='src/kb_setup/graph.py'` down the update path and
    `'python/src/kb_setup/graph.py'` down the extract path, so the aggregate
    disagreed with itself about where our own code lives.

    This is deliberately a claim about the ARGV rather than about node counts.
    The argv is what differs between the two paths, and it is checkable without a
    real binary; the artifact-level consequence is verified out-of-band by
    rebuilding and re-running `affected`, which no stubbed test can do.

    Realistic break: someone reintroduces the `if sub.is_file(): update` branch
    as an optimisation, which is exactly how it got there the first time.
    """
    root = _stamped_repo(tmp_path)
    spec = config.load(root)[0]
    sync.write_stamp(root, spec, version="0.9.31", source_ref="", inputs=None)

    # The sub-graphs MUST already exist, or this arm is dead. The branch being
    # guarded against was `if sub.is_file(): update`, so a fixture without them
    # takes the extract path either way and the assertion passes against the very
    # mutation it exists to catch — verified: reintroducing the branch left the
    # suite green until these two files were added.
    for tree in graph._SELF_TREES:
        sub = root / tree / "graphify-out" / "graph.json"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    calls: list[list[str]] = []
    monkeypatch.setattr(graph, "_run", lambda argv, _r: calls.append([str(a) for a in argv]))
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)

    graph.refresh_self(root)

    subcommands = [c[1] for c in calls if len(c) > 1]
    assert "update" not in subcommands, (
        f"refresh_self reintroduced the `graphify update` branch; subcommands were "
        f"{subcommands}. update and extract disagree on source_file, so mixing them "
        f"puts two spellings of the same file in one graph."
    )
    assert subcommands.count("extract") == len(graph._SELF_TREES), (
        f"expected one `extract` per self tree; subcommands were {subcommands}"
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
