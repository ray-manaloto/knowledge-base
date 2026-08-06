"""Every writer of `graph.json` must re-derive `graph-prose.json`.

The defect these pin down was invisible for the same reason it was expensive:
`graph-prose.json` is derived from `graph.json`, `kb-build` re-derives it, and a
merge-only ingestion did not — so `kb-query --prose`, the arm this repo
*recommends* for a question about the documents, went on answering from the
corpus as it stood before the merge, and the next unrelated `kb-build` quietly
repaired it. Nothing failed; the answers were just older than the graph.

The file is named for the CONTRACT rather than for `kb-merge`, because there are
two writers and fixing one of them is not a fix. `graphify label` rewrites
`graph.json` outright (installed 0.9.30, `graphify/cli.py:1546` -> :1830), and the
documented ingestion order is merge -> label — so a `merge_chunk` that re-derives
while `label` does not is undone by the very next step of the workflow it fixes.
That gap survived the first round of this change and was found by the cold lane.

So the load-bearing tests here are not "the wrapper returns the subprocess rc".
They are the success/failure PAIRS: without the failure arm, a function that
derives unconditionally passes the success arm just as happily — and would
replace a valid prose graph off the back of an operation that failed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from kb_setup import graphify_ops, prose, stamps
from kb_setup.currency import config, sync

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def _stub_graphify(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    rc: int,
    writes: dict[str, object] | None = None,
) -> None:
    """Stand in for whatever graphify subprocess the wrapper is about to run.

    The real things need graphify's bundled environment, which a unit test has no
    business standing up. What the stub reproduces is the part that matters to
    the caller: an rc, and whether `graph.json` changed underneath it.

    `graphify_exe` is pointed at a file that EXISTS, because `label()` gates on
    `Path(exe).is_file()` and would otherwise refuse before running anything —
    a test that passes because the binary was missing has tested the guard, not
    the labelling.
    """

    def fake_run(cmd: Sequence[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        if writes is not None:
            (tmp_path / "graphify-out" / "graph.json").write_text(
                json.dumps(writes), encoding="utf-8"
            )
        return subprocess.CompletedProcess(list(cmd), rc)

    exe = tmp_path / "graphify"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(graphify_ops, "graphify_python", lambda _root: "/nonexistent/python")
    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _root: str(exe))
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
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 0
    assert _prose_ids(repo) == ["just_merged"]


def test_a_failed_merge_leaves_the_prose_graph_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the derivation is gated on the merge's rc, not unconditional.

    The failing merge WRITES graph.json before it fails, and that detail is the
    whole test. Its first version let the stub leave graph.json byte-identical to
    the pre-merge state, so an unconditional derivation would have re-derived the
    *same* corpus and the assertion below would have passed anyway — a control arm
    that could not produce the other answer. Proved by mutation in cold-lane round
    1: removing the `rc != 0` gate left this test green.

    A merge that mutated the graph and then failed is also the realistic shape of
    the thing the gate defends against, which is why it is what the stub does now.
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

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
    _stub_graphify(
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
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, str(tmp_path / "absent.json")) == 2
    assert _prose_ids(repo) == ["yesterday"]


# --- recomposition ledger (#175) --------------------------------------------


def test_a_successful_merge_appends_to_the_recomposition_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The OTHER thing a fully-successful merge must do: extend the ledger.

    `kb-watch` can only replay what this records. A merge that succeeds and
    re-derives the prose graph but never reaches the ledger would be invisible
    to a later recomposition — silently dropping its content the moment
    `kb-watch` next runs, which is the exact failure the ledger exists to rule
    out.

    The recorded `chunk` is asserted CANONICALIZED — repo-root-relative here,
    since the fixture chunk sits under `repo` — not the raw absolute string
    `merge_chunk` was called with. `append_merged_chunk` resolves and
    relativizes before storing (#175 cold review round 2, the round-1
    finding 8 secondary item), so a later `_verified_ledger_chunks` agrees
    regardless of the cwd at append time or at verify time.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)
    chunk = _chunk(tmp_path)

    assert graphify_ops.merge_chunk(repo, chunk) == 0

    entries = graph._read_merged_chunks(repo)
    assert entries is not None
    assert [e.chunk for e in entries] == ["chunk.json"]
    assert entries[0].sha256 == graph._sha256_file(Path(chunk))


def test_a_failed_merge_does_not_touch_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the ledger append is gated on rc, same as the prose re-derive.

    Without this gate, a failed merge that happened to leave a chunk file
    sitting on disk would still record a ledger entry for content that was
    never actually merged into graph.json.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)
    chunk = _chunk(tmp_path)

    assert graphify_ops.merge_chunk(repo, chunk) == 1

    assert graph._read_merged_chunks(repo) == []


def test_a_merge_whose_ledger_write_fails_does_not_report_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The chunk merged and the prose graph re-derived, but the ledger did not extend.

    `rc=0` here would tell a caller that everything about this merge is
    durably recorded, when the one artifact `kb-watch` reads to recompose from
    just failed to extend — the same class of lie `_derive_prose`'s own gate
    exists to prevent, one step further down the same function.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)
    chunk = _chunk(tmp_path)

    def boom(_repo_root: Path, _chunk: str, _root: str) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(graph, "append_merged_chunk", boom)

    assert graphify_ops.merge_chunk(repo, chunk) == 1
    assert "recomposition ledger" in capsys.readouterr().err


def test_a_successful_label_re_derives_the_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kb-label` is the OTHER writer of graph.json, and the next workflow step.

    `graphify label` does not only touch sidecars — it ends in
    `to_json(G, communities, str(out / "graph.json"), …)` (installed 0.9.30,
    `graphify/cli.py:1830`, reached from the `label` branch at :1546 with no
    intervening branch). The documented order is merge -> label, so fixing only
    the merge would have left the prose graph stale again one step later, which
    is the whole failure this change exists to end.
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.label(repo) == 0
    assert _prose_ids(repo) == ["just_merged"]


def test_a_failed_label_leaves_the_prose_graph_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM for the label path — same shape, same reason, same rc gate."""
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.label(repo) == 1
    assert _prose_ids(repo) == ["yesterday"]


# --- hyperedges: graphify's own job since 0.9.34 (the carry is retired) ------

_HYPEREDGE = {"id": "he1", "nodes": ["just_merged", "yesterday"]}

_PRE_LABEL_WITH_HYPEREDGE: dict[str, object] = {
    "graph": {"hyperedges": [_HYPEREDGE]},
    "nodes": [{"id": "yesterday", "label": "yesterday", "file_type": "concept"}],
    "links": [],
    "hyperedges": [_HYPEREDGE],
}


def test_label_leaves_graph_json_exactly_as_graphify_wrote_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing in `label()` rewrites the artifact — the carry is retired.

    Until the graphify 0.9.34 bump, `_labelled` was graph.json's LAST writer:
    it re-attached the pre-run hyperedge list over whatever the subprocess
    wrote, because 0.9.33's round-trip measurably destroyed the list
    (upstream #2484/#2485, fixed in 0.9.34 and verified on the installed
    binary — `hyperedges.py`'s module docstring). Restoring a list the
    subprocess dropped would now defeat upstream's member revalidation, so
    the pre-run state must NOT come back. Asserted as full-dict equality
    against the stub's exact output: this fails if kb_setup code touches ANY
    part of the file after the subprocess exits — which is precisely what a
    resurrected carry would look like.
    """
    repo = _repo(tmp_path)
    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps(_PRE_LABEL_WITH_HYPEREDGE), encoding="utf-8"
    )
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.label(repo) == 0

    on_disk = json.loads((repo / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    assert on_disk == _MERGED


# --- currency stamp refresh (#179) -------------------------------------------
#
# `label()` rewrites graph.json wholesale (see the module docstring for the
# installed-0.9.30 citation), which is a REGENERATION exactly like
# `artifacts.generate`'s `report` entry — so it needs the same
# `kb_setup.stamps.refresh_after_regen` call, or every manual `mise run
# kb-label`, including the documented merge -> label curator flow, leaves
# `mise run kb-currency-check` reporting build-stamp drift until the next full
# `kb-build` (the fingerprint is `size:mtime_ns`, so ANY rewrite moves it).


def _with_currency_stamp(repo_root: Path) -> None:
    """Add a currency.toml + an existing stamp to a repo `_repo` already built.

    `_repo` already wrote the declared artifact (the pre-merge `graph.json`),
    which a stamp must fingerprint something that exists.
    """
    (repo_root / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    spec = config.load(repo_root)[0]
    sync.write_stamp(repo_root, spec, version="0.9.32")


def test_a_successful_label_refreshes_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful `label()` must re-fingerprint graph.json, not leave it stale.

    Without this, `label()`'s rewrite moves the file's `size:mtime_ns` and step
    1 reports drift for a graph that was legitimately relabelled — the #179
    defect. Asserted as a real fingerprint comparison, not a spy, per the
    ticket's preference for a real assertion where the cost is affordable.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.label(repo) == 0

    after = sync.read_stamp(repo, spec)
    live_fp = sync.artifact_fingerprint(repo / "graphify-out" / "graph.json")
    before_fps = sync.stamped_fingerprints(before)
    after_fps = sync.stamped_fingerprints(after)
    assert after_fps["graphify-out/graph.json"] == live_fp
    assert before_fps["graphify-out/graph.json"] != after_fps["graphify-out/graph.json"]
    # version/source_ref are carried forward, not re-derived by a restamp —
    # `label()` never reads `sources/` and has no standing to restate them.
    assert after["version"] == before["version"] == "0.9.32"


def test_a_failed_label_does_not_refresh_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: a failed label run must restamp nothing.

    graph.json may be in any state after a failed run, and stamping it would
    assert "this is the artifact the pin built" — a claim the same `rc != 0`
    gate that protects the prose re-derivation (`_labelled`'s early
    `return rc`) also protects here.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.label(repo) == 1

    after = sync.read_stamp(repo, spec)
    assert after == before


def test_a_failed_prose_derivation_still_refreshes_the_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The restamp runs BEFORE `_derive_prose`, and does not gate on it.

    `graph-prose.json` is not in the stamped set (`currency.toml` declares
    `graph.json` plus the derived views), so a prose derivation that fails
    afterwards cannot invalidate a fingerprint that was never about it —
    gating the restamp on the prose rc would only buy a permanent,
    meaningless currency red on a graph that was legitimately relabelled
    (`_labelled`'s docstring). Proven by outcome, and the outcome DOES
    discriminate the order here: were the restamp placed after the prose step
    and gated on its rc, this run would leave the stamp reading `before`.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    def boom(_root: Path) -> prose.ProseStats:
        raise ValueError("no non-AST nodes")

    monkeypatch.setattr(prose, "derive_for", boom)

    assert graphify_ops.label(repo) == 1

    after = sync.read_stamp(repo, spec)
    live_fp = sync.artifact_fingerprint(repo / "graphify-out" / "graph.json")
    assert sync.stamped_fingerprints(after)["graphify-out/graph.json"] == live_fp
    assert after != before


# --- currency stamp refresh, the THIRD writer (#181) -------------------------
#
# `merge_chunk` runs `_merge_docs.py` against graph.json, so it is a wholesale
# rewrite exactly like `label` and `artifacts.generate`'s `report` entry — and it
# was the one #179 left out. Without a restamp, a merge-ONLY run (the kb-curator
# skill's own quick path, with no following `kb-label`) leaves
# `kb-currency-check` reporting build-stamp drift until something else rewrites
# and restamps the graph.
#
# Measured on a real merge rather than inferred, per the ticket: of the four
# declared artifacts only `graph.json` moves — the three derived views are
# byte-identical before and after — so the full restamp masks nothing at the
# fingerprint level. What a merge really invalidates is the views' CONTENT, and
# that is `currency.views`'s job, not a narrowed variant of this call.


def test_a_successful_merge_refreshes_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The #181 defect: a merge-only run must not leave the stamp behind.

    A real fingerprint comparison rather than a spy, matching the `label` pair
    above: the assertion is that the recorded fingerprint now EQUALS what is on
    disk and no longer equals what it was, which a spy on the call cannot show.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 0

    after = sync.read_stamp(repo, spec)
    live_fp = sync.artifact_fingerprint(repo / "graphify-out" / "graph.json")
    assert sync.stamped_fingerprints(after)["graphify-out/graph.json"] == live_fp
    assert (
        sync.stamped_fingerprints(before)["graphify-out/graph.json"]
        != sync.stamped_fingerprints(after)["graphify-out/graph.json"]
    )
    # Carried forward, not re-derived: a merge has no standing to restate which
    # graphify version built the graph. Same rule as the `label` restamp.
    assert after["version"] == before["version"] == "0.9.32"


def test_a_failed_merge_does_not_refresh_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: a failed merge restamps nothing.

    graph.json may be half-written after a failed merge, and stamping it would
    assert "this is the artifact the pin built" over bytes nobody vouched for —
    the same `rc != 0` gate that already protects the prose re-derivation and
    the ledger append.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1

    assert sync.read_stamp(repo, spec) == before


def test_a_merge_whose_ledger_write_fails_does_not_refresh_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the restamp sits BELOW the ledger gate, not above it.

    This is the arm that pins WHERE in `merge_chunk` the call goes. Placing the
    restamp before `append_merged_chunk` would satisfy the success test just as
    happily, and would then re-stamp on a run that reports rc=1 — claiming the
    artifact is fully accounted for by an operation that just told its caller it
    was not.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    def boom(_repo_root: Path, _chunk: str, _root: str) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(graph, "append_merged_chunk", boom)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1

    assert sync.read_stamp(repo, spec) == before


def test_merge_and_label_restamps_carry_their_own_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM on the tag: `[kb-merge]`, never the copied `[kb-label]`.

    The tag is the only thing telling someone which of their commands touched the
    stamp, and this call was written by copying the `label` one — the single most
    likely defect in it is a tag that came along for the ride. Both directions are
    asserted from one test so neither can be hardcoded and still pass.
    """
    tags: list[str] = []
    real_refresh = stamps.refresh_after_regen

    def spy(
        repo_root: Path, *, tag: str, views_before: dict[str, dict[str, str]] | None = None
    ) -> None:
        tags.append(tag)
        real_refresh(repo_root, tag=tag, views_before=views_before)

    monkeypatch.setattr(stamps, "refresh_after_regen", spy)

    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)
    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 0
    assert graphify_ops.label(repo) == 0

    assert tags == ["kb-merge", "kb-label"]


def test_an_interrupted_write_leaves_no_partial_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reader must never see a half-written prose graph, only present or absent.

    `kb-query --prose` checks `.is_file()` and hands the path to graphify, so a
    write that is visible before it is complete can be read mid-serialisation.
    Writing straight into the destination held that window open for as long as a
    full dump of the corpus, and this path is now reached on every merge and every
    label rather than only on a build. (Cold lane, round 1.)

    The failure is injected at `json.dump`, which is where a real interruption
    (disk full, SIGKILL, a broken pipe) lands — not at a wrapper that would prove
    only that the wrapper was called.
    """
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_MERGED), encoding="utf-8")
    out = tmp_path / prose.PROSE_GRAPH_NAME

    def boom(*_: object, **__: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(prose.json, "dump", boom)
    with pytest.raises(OSError, match="no space"):
        prose.derive(src, out)

    assert not out.exists(), "a partial write was left where a reader would find it"
    assert list(tmp_path.glob("*.tmp")) == [], "the temp file outlived the failure"


def test_a_write_failure_becomes_an_rc_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An `OSError` from the derivation must reach the caller as rc=1 and a message.

    The wrapper caught `ValueError` and `SystemExit` and not this — so a full disk
    during a `kb-merge` surfaced as an unhandled traceback rather than the line
    telling you `--prose` now has no corpus. The gap was visible from inside this
    very file, which already injects an `OSError` against `prose.derive` one test
    up. (Cold lane, round 2.)
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    def boom(*_: object, **__: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(prose.json, "dump", boom)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1
    assert "kb-prose" in capsys.readouterr().err


def test_a_derivation_does_not_clobber_another_ones_temp_file(tmp_path: Path) -> None:
    """Two concurrent derivations must not share one temp path.

    A temp name derived from `out_path` is the SAME path for every caller, so two
    derivations running at once write into one file and each `replace` a graph the
    other half-wrote — a torn WRITE in place of the torn read the temp file was
    added to prevent. (Cold lane, round 2.)

    Stated as the harm rather than as "mkstemp was called": the decoy stands in
    for another derivation's in-flight temp file, and a fixed-name implementation
    both overwrites it and then renames it away, so it fails on the read below
    rather than on an implementation detail it might satisfy some other way.
    """
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_MERGED), encoding="utf-8")
    out = tmp_path / prose.PROSE_GRAPH_NAME

    inflight = "another derivation is part-way through writing this"
    decoy = out.with_name(out.name + ".tmp")
    decoy.write_text(inflight, encoding="utf-8")

    prose.derive(src, out)

    assert decoy.exists(), "the other derivation's temp file was renamed away"
    assert decoy.read_text(encoding="utf-8") == inflight, "it was written over"
    derived = json.loads(out.read_text(encoding="utf-8"))
    ids = [str(n["id"]) for n in cast("list[dict[str, object]]", derived["nodes"])]
    assert ids == ["just_merged"], "the derivation itself did not land"
