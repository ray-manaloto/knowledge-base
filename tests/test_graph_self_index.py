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

Also covers `refresh_self` / `kb-watch` (#175): the single-N-ary-merge
restructure removed the base-snapshot/guard machinery `kb-watch` used to
restart from, and this file's compose-manifest + merge-ledger tests cover what
replaced it — recomposing from what `build()` actually recorded it composed,
refusing rather than guessing whenever a between-build `kb-merge` cannot be
verified against what is currently on disk. See `refresh_self`'s own docstring
in `graph.py` for the property this preserves and how.
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


def test_build_writes_a_compose_manifest(monkeypatch, tmp_path):
    """`build()` must record what it composed, or `kb-watch` can never recompose.

    Realistic break: deleting the `_write_compose_manifest` call from the end
    of `build()` — the same shape `test_the_self_subgraph_joins_the_one_corpus
    _merge_not_a_second_call` already guards for the merge itself, one step
    later in the function.
    """
    _run_build(monkeypatch, tmp_path)

    manifest = graph._read_compose_manifest(tmp_path)
    assert manifest is not None, "build() did not leave a readable compose manifest"
    joined = " ".join(manifest.corpus)
    assert "aaa-seed" in joined, f"corpus source missing from compose manifest: {manifest.corpus}"
    assert "zzz-merged" in joined, f"corpus source missing from compose manifest: {manifest.corpus}"
    assert manifest.self_graph == str(graph._self_subgraph(tmp_path).relative_to(tmp_path)), (
        f"the compose manifest recorded the wrong self sub-graph path: {manifest.self_graph!r}"
    )


def test_build_resets_the_merge_ledger(monkeypatch, tmp_path):
    """A fresh build subsumes every between-build merge — the ledger goes back to [].

    Without this, a chunk merged BEFORE this build would be replayed a SECOND
    time by a later `kb-watch`, on top of a corpus that already reflects it.
    """
    (tmp_path / "graphify-out").mkdir(parents=True, exist_ok=True)
    stale = tmp_path / "stale-chunk.json"
    stale.write_text("{}", encoding="utf-8")
    graph._write_merged_chunks(
        tmp_path, [graph.MergedChunkEntry(chunk=str(stale), sha256="deadbeef")]
    )

    _run_build(monkeypatch, tmp_path)

    assert graph._read_merged_chunks(tmp_path) == [], (
        "build() left stale ledger entries behind — a fresh build must subsume them"
    )


def _compose_repo(tmp_path: Path, *, corpus: list[str], chunks: list[str] | None = None) -> Path:
    """A repo root with a REAL compose manifest and real corpus-leaf files.

    Mirrors what `build()` itself would have written: one sub-graph file per
    named corpus source, and a compose manifest naming them (plus the fixed
    self-subgraph location) — everything `refresh_self` reads before it does
    any real work. Returns `tmp_path` itself, named for readability at call
    sites below.
    """
    (tmp_path / "graphify-out").mkdir(parents=True, exist_ok=True)
    corpus_rel: list[str] = []
    for name in corpus:
        sub = tmp_path / "sources" / name / "graphify-out" / "graph.json"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.write_text(f'{{"nodes": [], "edges": [], "from": "{name}"}}', encoding="utf-8")
        corpus_rel.append(str(sub.relative_to(tmp_path)))
    self_rel = str(graph._self_subgraph(tmp_path).relative_to(tmp_path))
    graph._write_compose_manifest(
        tmp_path, corpus=corpus_rel, self_graph=self_rel, chunks=chunks or []
    )
    return tmp_path


def _stub_recompose(monkeypatch, calls: list[list[str]]) -> None:
    """Stub every subprocess/IO surface `refresh_self` crosses, recording argv.

    Mirrors `_run_build`'s own stubbing (same reasons): `_run` is RECORDED
    rather than replaced with nothing, because the merge/replay argv IS the
    behaviour under test; `label`/`assert_composition` run against REAL
    graph.json content that `apply_merge`'s byte-concatenation stand-in does
    not produce.
    """
    monkeypatch.setattr(graph, "_run", merge_recorder(calls))
    monkeypatch.setattr(graph, "graphify_python", lambda _root: "python3")
    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph.graphify_ops, "label", lambda _root: 0)
    monkeypatch.setattr(graph.graph_checks, "assert_composition", lambda _path: None)


def _forbid_subprocesses(monkeypatch) -> None:
    """Make `refresh_self` fail FAST and CLEAN if it ever reaches a subprocess.

    Every refusal below is supposed to fire before `_extract_self` or
    `_merge_sources_into` ever runs. Without this, a regression that drops the
    refusal does not fail the test cleanly — it falls through to `_run`'s real
    `subprocess.run`, which shells out to the actually-installed `graphify`
    binary. That is slow, environment-dependent, and (measured directly: the
    FAIL-arm check for the sha256 comparison below hit exactly this) turns a
    clear "SystemExit was not raised" into a confusing `CalledProcessError`
    from a real extraction — still red, but for a much noisier reason than the
    regression itself.
    """

    def boom(argv: list[str], _root: Path) -> None:
        raise AssertionError(f"refresh_self must refuse before shelling out; got {argv}")

    monkeypatch.setattr(graph, "_run", boom)


def test_refresh_self_refuses_without_a_compose_manifest(monkeypatch, tmp_path):
    """No record of a prior build -> refuse, naming the fix.

    Unknown is not permission: a repo that has never been built (or whose
    record could not be read) has nothing safe for `kb-watch` to recompose FROM.
    """
    _forbid_subprocesses(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        graph.refresh_self(tmp_path)
    assert "kb-build" in str(exc.value), (
        f"the refusal must point at the real recovery path; it said {exc.value!r}"
    )


def test_refresh_self_refuses_when_a_corpus_leaf_is_gone(monkeypatch, tmp_path):
    """A recorded corpus leaf that vanished since the last build must refuse, NAMED.

    Realistic break: silently dropping a missing source from the recompose
    input list instead of refusing — that would recompose a SMALLER corpus
    than the last build produced, without anyone asking for that.
    """
    _forbid_subprocesses(monkeypatch)
    repo = _compose_repo(tmp_path, corpus=["aaa", "bbb"])
    (repo / "sources" / "bbb" / "graphify-out" / "graph.json").unlink()

    with pytest.raises(SystemExit) as exc:
        graph.refresh_self(repo)
    message = str(exc.value)
    assert "bbb" in message, f"the refusal must name the missing leaf; it said {message!r}"


def test_refresh_self_refuses_when_a_ledger_chunk_is_gone(monkeypatch, tmp_path):
    """A ledger entry whose file vanished must refuse, NAMING the entry.

    This is the exact silent-discard the ledger exists to prevent: recomposing
    without this chunk would produce a graph.json that quietly no longer
    reflects a merge everyone believed had landed.
    """
    _forbid_subprocesses(monkeypatch)
    repo = _compose_repo(tmp_path, corpus=["aaa"])
    missing = repo / "sources" / "extractions" / "gone-docs.json"
    graph._write_merged_chunks(
        repo, [graph.MergedChunkEntry(chunk=str(missing.relative_to(repo)), sha256="abc123")]
    )

    with pytest.raises(SystemExit) as exc:
        graph.refresh_self(repo)
    message = str(exc.value)
    assert "gone-docs.json" in message, (
        f"the refusal must name the missing chunk; it said {message!r}"
    )


def test_refresh_self_refuses_when_a_ledger_chunk_has_changed(monkeypatch, tmp_path):
    """A ledger entry whose sha256 no longer matches must refuse, NAMING the entry.

    Recomposing over silently-changed content would replay bytes different
    from whatever was actually verified and merged at `kb-merge` time.

    FAIL-ARM CHECKED (manually, not committed): disabling the `actual !=
    entry.sha256` comparison in `_verified_ledger_chunks` turns this test red
    — confirmed, then restored. Before `_forbid_subprocesses` existed, the
    mutated run fell through to a REAL `graphify extract` subprocess instead
    of failing cleanly on "SystemExit not raised"; that observation is what
    `_forbid_subprocesses` exists to fix, here and on every sibling refusal
    test above.
    """
    _forbid_subprocesses(monkeypatch)
    repo = _compose_repo(tmp_path, corpus=["aaa"])
    chunk = repo / "sources" / "extractions" / "changed-docs.json"
    chunk.parent.mkdir(parents=True, exist_ok=True)
    chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    stale_sha = graph._sha256_file(chunk)
    chunk.write_text('{"nodes": [], "edges": [], "edited": true}', encoding="utf-8")

    graph._write_merged_chunks(
        repo, [graph.MergedChunkEntry(chunk=str(chunk.relative_to(repo)), sha256=stale_sha)]
    )

    with pytest.raises(SystemExit) as exc:
        graph.refresh_self(repo)
    message = str(exc.value)
    assert "changed-docs.json" in message, (
        f"the refusal must name the changed chunk; it said {message!r}"
    )


def test_refresh_self_replays_a_valid_ledger_chunk_after_the_manifests(monkeypatch, tmp_path):
    """A verified ledger entry reaches `_MERGE_SCRIPT`, AFTER the manifest's own chunks.

    Asserted on the recorded argv, the same shape `test_the_self_subgraph_
    joins_the_one_corpus_merge_not_a_second_call` already uses for the corpus
    merge — the behaviour under test is which paths reach the subprocess and
    in what order, not the subprocess itself.
    """
    manifest_chunk_dir = tmp_path / "sources" / "extractions"
    manifest_chunk_dir.mkdir(parents=True, exist_ok=True)
    manifest_chunk = manifest_chunk_dir / "known-docs.json"
    manifest_chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    repo = _compose_repo(
        tmp_path, corpus=["aaa"], chunks=[str(manifest_chunk.relative_to(tmp_path))]
    )

    ledger_chunk = tmp_path / "ledger-chunk.json"
    ledger_chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    graph._write_merged_chunks(
        repo,
        [graph.MergedChunkEntry(chunk=str(ledger_chunk), sha256=graph._sha256_file(ledger_chunk))],
    )

    calls: list[list[str]] = []
    _stub_recompose(monkeypatch, calls)

    graph.refresh_self(repo)

    merge_argvs = [c for c in calls if str(graph._MERGE_SCRIPT) in c]
    # argv shape is [gpy, _MERGE_SCRIPT, chunk, root, out] — index 2 is the chunk.
    chunk_args = [c[2] for c in merge_argvs]
    assert chunk_args == [str(manifest_chunk), str(ledger_chunk)], (
        f"expected the manifest's chunk replayed before the ledger's; got {chunk_args}"
    )


def test_a_successful_refresh_resets_the_ledger_too(monkeypatch, tmp_path):
    """The ledger entries a refresh just replayed must not be replayed again next time.

    CONTROL for `test_build_resets_the_merge_ledger`'s sibling: `kb-watch`
    subsumes the same way a fresh `kb-build` does, or a second consecutive
    `kb-watch` would replay an already-replayed chunk on top of itself. The
    replayed chunk must also join the REWRITTEN compose manifest's `chunks`,
    since it is now part of what the graph durably reflects.
    """
    repo = _compose_repo(tmp_path, corpus=["aaa"])
    ledger_chunk = tmp_path / "ledger-chunk.json"
    ledger_chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    graph._write_merged_chunks(
        repo,
        [graph.MergedChunkEntry(chunk=str(ledger_chunk), sha256=graph._sha256_file(ledger_chunk))],
    )

    calls: list[list[str]] = []
    _stub_recompose(monkeypatch, calls)

    graph.refresh_self(repo)

    assert graph._read_merged_chunks(repo) == [], (
        "a successful refresh must reset the ledger — it subsumed every entry"
    )
    manifest = graph._read_compose_manifest(repo)
    assert manifest is not None
    assert str(ledger_chunk.relative_to(repo)) in manifest.chunks, (
        f"the replayed ledger chunk must join the rewritten compose manifest; "
        f"chunks were {manifest.chunks}"
    )


def test_a_recompose_failure_leaves_the_real_graph_untouched(monkeypatch, tmp_path):
    """Everything above the swap runs against the scratch file, never the real one.

    Realistic break: writing `_merge_sources_into`'s output straight to the
    real `graphify-out/graph.json` instead of a temp path — the shape this
    design specifically avoids, and this is the test that would catch it
    coming back.
    """
    repo = _compose_repo(tmp_path, corpus=["aaa"])
    real_out = repo / "graphify-out" / "graph.json"
    real_out.write_text('{"nodes": [], "UNTOUCHED": true}', encoding="utf-8")

    def boom(argv: list[str], _root: Path) -> None:
        if "merge-graphs" in argv:
            raise RuntimeError("simulated failure mid-recompose")
        # Self-extraction (and anything else that is not the corpus merge)
        # succeeds as a no-op, so the failure below is proven to land INSIDE
        # the scratch-file recompose, not before it is even reached.

    monkeypatch.setattr(graph, "_run", boom)
    monkeypatch.setattr(graph, "graphify_python", lambda _root: "python3")

    with pytest.raises(RuntimeError, match="simulated failure"):
        graph.refresh_self(repo)

    assert real_out.read_text(encoding="utf-8") == '{"nodes": [], "UNTOUCHED": true}', (
        "a failure during recomposition touched the real graph.json"
    )
    leftover = list((repo / "graphify-out").glob("graph.json.*.recompose.tmp"))
    assert leftover == [], f"a failed recomposition left its scratch file behind: {leftover}"
