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
from kb_setup.currency import config, sync


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
        tmp_path,
        [graph.MergedChunkEntry(chunk=str(stale), sha256="deadbeef", root=str(tmp_path))],
    )

    _run_build(monkeypatch, tmp_path)

    assert graph._read_merged_chunks(tmp_path) == [], (
        "build() left stale ledger entries behind — a fresh build must subsume them"
    )


def _compose_repo(
    tmp_path: Path,
    *,
    corpus: list[str],
    chunks: list[str] | None = None,
    chunk_roots: dict[str, str] | None = None,
) -> Path:
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
        tmp_path,
        graph.ComposeManifest(
            corpus=tuple(corpus_rel),
            self_graph=self_rel,
            chunks=tuple(chunks or []),
            chunk_roots=chunk_roots or {},
        ),
    )
    return tmp_path


def _stub_recompose(monkeypatch, calls: list[list[str]]) -> None:
    """Stub every subprocess/IO surface `refresh_self` crosses, recording argv.

    Mirrors `_run_build`'s own stubbing (same reasons): `_run` is RECORDED
    rather than replaced with nothing, because the merge/replay argv IS the
    behaviour under test; `label`/`assert_composition` run against REAL
    graph.json content that `apply_merge`'s byte-concatenation stand-in does
    not produce. `_clear_stamp` accepts `**_` because `refresh_self` now calls
    it with `tag="kb-watch"` (#175 cold review, finding 9). `_restamp_self` is
    deliberately NOT stubbed here: none of these fixtures write a
    `currency.toml`, so `_currency_spec` resolves to `None` and it is already
    a no-op — restamping is exercised on purpose by
    `test_refresh_self_restamps_so_the_graph_stays_verifiable` and its
    siblings below, which DO set one up (`_stamped_repo`).
    """
    monkeypatch.setattr(graph, "_run", merge_recorder(calls))
    monkeypatch.setattr(graph, "graphify_python", lambda _root: "python3")
    monkeypatch.setattr(graph, "_clear_stamp", lambda _root, **_: None)
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
        repo,
        [
            graph.MergedChunkEntry(
                chunk=str(missing.relative_to(repo)), sha256="abc123", root=str(missing.parent)
            )
        ],
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
        repo,
        [
            graph.MergedChunkEntry(
                chunk=str(chunk.relative_to(repo)), sha256=stale_sha, root=str(chunk.parent)
            )
        ],
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
    in what order, not the subprocess itself. Also asserts the ROOT each
    replays with: the manifest chunk gets the naming-convention default
    (`sources/known`, from its `-docs` stem), the ledger chunk gets its OWN
    recorded root — never the same derivation (#175 cold review, finding 4b).
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
        [
            graph.MergedChunkEntry(
                chunk=str(ledger_chunk),
                sha256=graph._sha256_file(ledger_chunk),
                root=str(tmp_path),
            )
        ],
    )

    calls: list[list[str]] = []
    _stub_recompose(monkeypatch, calls)

    graph.refresh_self(repo)

    merge_argvs = [c for c in calls if str(graph._MERGE_SCRIPT) in c]
    # argv shape is [gpy, _MERGE_SCRIPT, chunk, root, out] — index 2 is the
    # chunk, index 3 is the root.
    chunk_args = [c[2] for c in merge_argvs]
    assert chunk_args == [str(manifest_chunk), str(ledger_chunk)], (
        f"expected the manifest's chunk replayed before the ledger's; got {chunk_args}"
    )
    root_args = [c[3] for c in merge_argvs]
    assert root_args == [str((tmp_path / "sources" / "known").resolve()), str(tmp_path)], (
        f"expected the manifest chunk's naming-convention root then the ledger "
        f"chunk's own recorded root; got {root_args}"
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
        [
            graph.MergedChunkEntry(
                chunk=str(ledger_chunk),
                sha256=graph._sha256_file(ledger_chunk),
                root=str(tmp_path),
            )
        ],
    )

    calls: list[list[str]] = []
    _stub_recompose(monkeypatch, calls)

    graph.refresh_self(repo)

    assert graph._read_merged_chunks(repo) == [], (
        "a successful refresh must reset the ledger — it subsumed every entry"
    )
    manifest = graph._read_compose_manifest(repo)
    assert manifest is not None
    promoted = str(ledger_chunk.relative_to(repo))
    assert promoted in manifest.chunks, (
        f"the replayed ledger chunk must join the rewritten compose manifest; "
        f"chunks were {manifest.chunks}"
    )
    assert manifest.chunk_roots.get(promoted) == str(tmp_path), (
        f"the promoted chunk's recorded root did not survive into the "
        f"rewritten manifest; chunk_roots were {manifest.chunk_roots}"
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


def test_recompose_swaps_in_a_world_readable_graph_json(monkeypatch, tmp_path):
    """The swapped-in graph.json must not silently inherit mkstemp's 0600.

    `tempfile.mkstemp` always creates its scratch file `0600`, and
    `Path.replace` is a rename — the surviving inode's permission bits are the
    TEMP file's, not `real_out`'s. Left unfixed, every `kb-watch` would
    silently tighten `graph.json` from world-readable to owner-only, and
    graphify's own `_atomic_replace` PRESERVES whatever mode is already
    there, so nothing downstream would ever repair it (#175 cold review,
    finding 5).
    """
    repo = _compose_repo(tmp_path, corpus=["aaa"])
    real_out = repo / "graphify-out" / "graph.json"
    real_out.write_text('{"nodes": []}', encoding="utf-8")
    real_out.chmod(0o644)

    _stub_recompose(monkeypatch, [])

    graph.refresh_self(repo)

    mode = real_out.stat().st_mode & 0o777
    assert mode == 0o644, f"graph.json's mode after refresh_self was {oct(mode)}, expected 0o644"


# --- restamp semantics (#175 cold review, finding 1) -------------------------


def _stamped_repo(tmp_path: Path) -> Path:
    """A repo with a currency pin and a compose manifest `refresh_self` can use.

    Combines what the deleted (pre-#175) `_stamped_repo` set up — the mise +
    `currency.toml` pin and an existing `graphify-out/graph.json` to
    fingerprint — with what `_compose_repo` sets up: the recorded composition
    `refresh_self` now reads back instead of a base snapshot.
    """
    (tmp_path / "mise.toml").write_text(
        '[tools]\n"pipx:graphifyy" = { version = "0.9.32", extras = ["all"] }\n', encoding="utf-8"
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n'
        # Matches the REAL currency.toml's `inputs` declaration — needed so a
        # regression that reintroduces `_input_fingerprints(repo_root)` in
        # `refresh_self` actually globs `sources/*.manifest` here too, rather
        # than the empty tuple a bare `[tool.graphify]` with no `inputs =`
        # line would produce (which returns `{}` regardless of what manifests
        # exist, masking finding 1's defect shape).
        'inputs = ["sources/*.manifest"]\n',
        encoding="utf-8",
    )
    repo = _compose_repo(tmp_path, corpus=["aaa"])
    (repo / "graphify-out" / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
    return repo


def test_refresh_self_restamps_so_the_graph_stays_verifiable(monkeypatch, tmp_path):
    """`kb-watch` must restamp, or currency step 1 goes permanently red.

    This asserts on the ARTIFACT, not on a recorded call to a helper being
    invoked — `stamped == observed` is a claim about the stamp file agreeing
    with graph.json, which is exactly what `kb-currency-check` compares.
    Asserting that some `_restamp_self` function was called would pass just as
    happily on a restamp that wrote the wrong bytes.

    Realistic break: revert `refresh_self`'s tail back to
    `_stamp_build(repo_root, inputs)` — this fix's own regression (#175 cold
    review, finding 1). `artifact_fingerprints` is `size:mtime_ns`, so ANY
    rewrite of graph.json moves it; without a restamp that carries the
    fingerprint forward, the very next session reports the graph as not
    verifiably built by the pin.
    """
    root = _stamped_repo(tmp_path)
    spec = config.load(root)[0]
    sync.write_stamp(root, spec, version="0.9.32", source_ref="", inputs=None)
    assert sync.stamped_fingerprints(sync.read_stamp(root, spec)) == sync.artifact_fingerprints(
        root, spec
    ), "fixture is wrong: the stamp must agree with the artifact BEFORE the refresh"

    def _fake_run(argv: list[str], _root: Path) -> None:
        # The merge really does rewrite the scratch file `--out` names — write
        # DIFFERENT bytes there so the fingerprint genuinely moves once the
        # swap lands. A stub that left it untouched would make the assertion
        # below pass whether or not restamping actually happened.
        a = [str(x) for x in argv]
        if "merge-graphs" in a and "--out" in a:
            Path(a[a.index("--out") + 1]).write_text(
                '{"nodes": [], "rebuilt": true}', encoding="utf-8"
            )

    monkeypatch.setattr(graph, "_run", _fake_run)
    monkeypatch.setattr(graph, "graphify_python", lambda _root: "python3")
    monkeypatch.setattr(graph, "_clear_stamp", lambda _root, **_: None)
    monkeypatch.setattr(graph.graphify_ops, "label", lambda _root: 0)
    monkeypatch.setattr(graph.graph_checks, "assert_composition", lambda _path: None)

    graph.refresh_self(root)

    assert sync.stamped_fingerprints(sync.read_stamp(root, spec)) == sync.artifact_fingerprints(
        root, spec
    ), (
        "refresh_self rewrote graph.json without restamping — kb-currency-check "
        "would report the graph as built by an unknown version every session after."
    )


def test_refresh_self_does_not_fingerprint_a_manifest_it_never_read(monkeypatch, tmp_path):
    """THE regression itself (#175 cold review, finding 1).

    `refresh_self` recomposes ONLY from the recorded compose manifest and the
    verified ledger — it deliberately never re-reads `sources/*.manifest` (see
    `refresh_self`'s own docstring). A manifest dropped in AFTER the last
    `kb-build` is therefore excluded from the graph a `kb-watch` produces, and
    the stamp must say so: recording a LIVE fingerprint over it anyway would
    make `kb-currency-check` report the corpus in sync with content the graph
    structurally does not contain.
    """
    root = _stamped_repo(tmp_path)
    spec = config.load(root)[0]
    old_manifest = root / "sources" / "old.manifest"
    old_manifest.parent.mkdir(parents=True, exist_ok=True)
    old_manifest.write_text("url = https://example.invalid/o/old\n", encoding="utf-8")
    # A stamp recording ONE input `kb-build` actually saw, matching a real
    # `_input_fingerprints` map's shape — not the `None` "never asked" case.
    sync.write_stamp(
        root,
        spec,
        version="0.9.32",
        source_ref="",
        inputs={"sources/old.manifest": sync.input_fingerprint(old_manifest)},
    )

    _stub_recompose(monkeypatch, [])

    # Dropped in AFTER the stamp — exactly the repro `refresh_self`'s
    # docstring names: a manifest `kb-build` never saw and `kb-watch` never
    # reads.
    (root / "sources" / "newthing.manifest").write_text(
        "url = https://example.invalid/o/newthing\n", encoding="utf-8"
    )

    graph.refresh_self(root)

    recorded = sync.stamped_input_fingerprints(sync.read_stamp(root, spec))
    assert recorded is not None
    assert "sources/newthing.manifest" not in recorded, (
        f"refresh_self fingerprinted a manifest it structurally never read: {recorded}"
    )
    assert "sources/old.manifest" in recorded, (
        f"the pre-existing input fingerprint must survive verbatim, not just "
        f"exclude the new one: {recorded}"
    )


# --- ledger promotion: dedup + root fidelity (#175 cold review, finding 4) --


def test_promoting_an_already_present_ledger_chunk_does_not_duplicate(monkeypatch, tmp_path):
    """A chunk already in `manifest.chunks` must not be appended a second time.

    The scenario the cold review found: a chunk lands in `manifest.chunks` (an
    earlier `kb-watch` already promoted it, or `build()`'s own glob already
    carried it) and is ALSO still named by a ledger entry (e.g. a `kb-merge`
    re-run against unchanged content). Without de-duplication the rewritten
    manifest would carry it TWICE, and every later recomposition would replay
    it twice — pure waste that compounds on every subsequent `kb-watch`.
    """
    ledger_chunk = tmp_path / "ledger-chunk.json"
    ledger_chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    already_promoted = str(ledger_chunk.relative_to(tmp_path))

    repo = _compose_repo(
        tmp_path,
        corpus=["aaa"],
        chunks=[already_promoted],
        chunk_roots={already_promoted: str(tmp_path)},
    )
    graph._write_merged_chunks(
        repo,
        [
            graph.MergedChunkEntry(
                chunk=already_promoted,
                sha256=graph._sha256_file(ledger_chunk),
                root=str(tmp_path),
            )
        ],
    )

    calls: list[list[str]] = []
    _stub_recompose(monkeypatch, calls)

    graph.refresh_self(repo)

    manifest = graph._read_compose_manifest(repo)
    assert manifest is not None
    assert manifest.chunks.count(already_promoted) == 1, (
        f"a chunk already in manifest.chunks was promoted again; chunks were {manifest.chunks}"
    )
    # And it must still only be REPLAYED once per recomposition — the waste
    # the dedup exists to stop, not merely a manifest-bookkeeping detail.
    merge_argvs = [c for c in calls if str(graph._MERGE_SCRIPT) in c]
    chunk_args = [c[2] for c in merge_argvs]
    assert chunk_args.count(str(ledger_chunk)) == 1, (
        f"the chunk was replayed more than once in a single recomposition; argv were {merge_argvs}"
    )


def test_a_ledger_chunk_replays_with_its_recorded_root_not_its_parent_directory(
    monkeypatch, tmp_path
):
    """A ledger chunk replays with the root `kb-merge` ACTUALLY used, not a guess.

    Before #175's cold-review fixes, a ledger chunk's replay root was always
    `c.resolve().parent` — the chunk file's own directory — which silently
    discarded a `kb-merge --root <custom>` invocation. This chunk's recorded
    root is deliberately DIFFERENT from its parent directory, so a replay
    using the old guess would send a different root than the one actually
    merged with.
    """
    custom_root = tmp_path / "a-totally-different-root"
    custom_root.mkdir()
    ledger_chunk = tmp_path / "somewhere-else" / "chunk.json"
    ledger_chunk.parent.mkdir(parents=True, exist_ok=True)
    ledger_chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    repo = _compose_repo(tmp_path, corpus=["aaa"])
    graph._write_merged_chunks(
        repo,
        [
            graph.MergedChunkEntry(
                chunk=str(ledger_chunk),
                sha256=graph._sha256_file(ledger_chunk),
                root=str(custom_root),
            )
        ],
    )

    calls: list[list[str]] = []
    _stub_recompose(monkeypatch, calls)

    graph.refresh_self(repo)

    merge_argvs = [c for c in calls if str(graph._MERGE_SCRIPT) in c]
    root_args = [c[3] for c in merge_argvs]
    assert root_args == [str(custom_root)], (
        f"the ledger chunk replayed with the wrong root; argv were {merge_argvs}"
    )


def test_a_promoted_ledger_chunks_root_survives_into_the_next_refresh(monkeypatch, tmp_path):
    """THE regression the cold review found (finding 4b), across TWO refreshes.

    A chunk under `sources/extractions/foo-docs.json`, merged with `kb-merge`'s
    own DEFAULT root (the chunk's parent directory, `sources/extractions` —
    NOT the naming-convention guess `sources/foo` the manifest-chunk fallback
    derives from its `-docs` stem), is promoted into `manifest.chunks` by the
    FIRST refresh. The SECOND refresh must still replay it with the ORIGINAL
    `sources/extractions` root: before this fix, `_replay_targets` re-derived
    a manifest chunk's root fresh on every call via the naming convention,
    with no way to tell this chunk apart from one `build()` itself discovered.
    """
    extractions = tmp_path / "sources" / "extractions"
    extractions.mkdir(parents=True, exist_ok=True)
    chunk = extractions / "foo-docs.json"
    chunk.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    default_root = str(extractions)  # kb-merge's own default: the chunk's parent dir

    repo = _compose_repo(tmp_path, corpus=["aaa"])
    graph._write_merged_chunks(
        repo,
        [
            graph.MergedChunkEntry(
                chunk=str(chunk), sha256=graph._sha256_file(chunk), root=default_root
            )
        ],
    )

    _stub_recompose(monkeypatch, [])
    graph.refresh_self(repo)

    manifest = graph._read_compose_manifest(repo)
    assert manifest is not None
    promoted_name = str(chunk.relative_to(repo))
    assert promoted_name in manifest.chunks
    assert manifest.chunk_roots.get(promoted_name) == default_root, (
        f"the promoted chunk's root was not recorded correctly: {manifest.chunk_roots}"
    )

    # SECOND refresh: the ledger is empty (the first refresh reset it), so
    # this chunk now replays purely from `manifest.chunks` — exactly the path
    # the naming-convention fallback (`sources/foo`, wrong) would otherwise
    # silently take over.
    second_calls: list[list[str]] = []
    _stub_recompose(monkeypatch, second_calls)
    graph.refresh_self(repo)

    merge_argvs = [c for c in second_calls if str(graph._MERGE_SCRIPT) in c]
    root_args = [c[3] for c in merge_argvs]
    assert root_args == [default_root], (
        f"the promoted chunk replayed with a re-derived root instead of its "
        f"recorded one; got {root_args}, expected [{default_root!r}]"
    )
