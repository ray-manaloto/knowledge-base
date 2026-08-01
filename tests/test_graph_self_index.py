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


def _run_build(monkeypatch, tmp_path: Path) -> list[list[str]]:
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

    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph, "_extract_code", lambda _root, _name: True)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)
    monkeypatch.setattr(graph.shutil, "copy", lambda _src, _dst: None)
    monkeypatch.setattr(graph, "_run", lambda argv, _root: calls.append([str(a) for a in argv]))

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
