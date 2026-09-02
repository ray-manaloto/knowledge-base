# Copyright (c) 2026 Raymond Manaloto
"""Single-source graphify operations: merge a doc chunk, label, transcribe.

Each is wrapped by a mise task (kb-merge / kb-label / kb-transcribe) so NOTHING
calls graphify by hand — the PreToolUse guard (`kb_setup.hook_guard`) denies raw
`graphify …` / `_merge_docs.py` invocations and redirects here.

Every graphify subprocess runs under `graphify_env.clean_env()`, which strips
non-Claude provider keys — so labeling can only use the claude-cli backend (your
Claude Pro/Max subscription) or the deterministic no-LLM fallback, never an
auto-detected Gemini/OpenAI key.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import events, graphify_health, prose, stamps
from kb_setup.graphify_env import assert_pinned_graphify, clean_env, graphify_exe, graphify_python

if TYPE_CHECKING:
    from collections.abc import Sequence

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")


#: How many validation issues a refusal prints before truncating. A chunk with a
#: systematic fault (every node missing `_origin`) can produce hundreds; the
#: point of the message is to name the CLASS, and the full list is one
#: `mise run kb-validate-chunks` away.
_MAX_SHOWN_ISSUES = 10


def _committed_chunks(repo_root: Path) -> list[Path]:
    """Every chunk whose nodes are, or will be, in the graph — the collision set.

    The glob over `sources/extractions/*.json` answers "who else already claims a
    `source_file`" for everything committed, including a chunk added to the tree
    but not yet merged: it still owns its files the moment `kb-build` runs.

    **The glob alone was not the whole set.** `kb-merge` accepts a chunk from
    ANY path — `graph.append_merged_chunk` exists precisely to record one, so
    `kb-watch` can replay it — and an out-of-tree chunk's nodes are in the graph
    just as much as a committed one's. Excluding them meant a new chunk could
    claim a `source_file` an out-of-tree chunk already owned, pass the gate, and
    have `build_merge` delete its nodes: the gate's own subject, reachable
    through the one door it was not looking at. (Cold lane, round 1, P1.)

    Best-effort on the ledger half — an unreadable or absent ledger yields the
    glob rather than raising, because a collision check that refuses to run is
    worse than one with a known bound, and `build()` resets the ledger anyway.
    """
    from kb_setup import graph as _graph

    paths = sorted((repo_root / "sources" / "extractions").glob("*.json"))
    try:
        ledger = _graph.merged_chunk_paths(repo_root)
    except OSError, ValueError:
        ledger = None
    if ledger is None:
        # WARNING, and it was ALREADY on stderr — so the level matches the
        # stream the old code chose, and nothing moves. This is the shape R9 is
        # about: a gate that continues with reduced coverage and says so in a
        # line nobody greps. `coverage_reduced` is now a field.
        events.warn(
            "merge.ledger_unreadable",
            "[kb-merge] WARNING: the recomposition ledger is unreadable, so the "
            "collision check can only see committed chunks. A chunk merged from "
            "outside sources/extractions/ is INVISIBLE to it right now. "
            "`mise run kb-build` regenerates the ledger.",
            coverage_reduced=True,
        )
        return paths
    known = {p.resolve() for p in paths}
    return paths + [p for p in ledger if p.is_file() and p.resolve() not in known]


def _self_remerge(repo_root: Path, chunk_path: Path) -> bool:
    """True when re-merging this chunk can only replace its OWN prior nodes.

    Two conditions, both necessary. The chunk must be COMMITTED — an uncommitted
    one contributed nothing to the graph, so anything it replaces belongs to
    somebody else. And it must be the ONLY committed claimant of every
    `source_file` it names — otherwise the replacement is a cross-chunk
    supersession, which is #189's subject and must not be waved through as
    routine.

    This is what lets `_merge_docs._report` phrase the most common merge there is
    as EXPECTED rather than as a possible data loss. Measured 2026-08-06: a
    re-merge of `claude-commands-docs.json` reports `REPLACED 10` with the total
    unchanged — correct, and it happens on every single re-merge. A check that
    prints "the loss is real" on that is a check people learn to skip.

    It reads the corpus rather than trusting the path, so a chunk sitting in
    `sources/extractions/` that ALSO shares a file with a sibling still gets the
    unexpected-replacement wording.
    """
    from kb_setup import chunks as _chunks

    committed = _committed_chunks(repo_root)
    resolved = chunk_path.resolve()
    if resolved not in {p.resolve() for p in committed}:
        return False
    mine, _ = _chunks.chunk_claims(resolved)
    for other in committed:
        if other.resolve() == resolved:
            continue
        theirs, _ = _chunks.chunk_claims(other)
        if mine.keys() & theirs.keys():
            return False
    return True


def _refuse(chunk_name: str, what: str, issues: list[str]) -> int:
    """Print a bounded refusal and return the rc `kb-merge` exits with."""
    events.fail(
        "merge.refused",
        f"[kb-merge] {chunk_name} {what} — refusing:",
        chunk=chunk_name,
        reason=what,
        issues=len(issues),
    )
    for i in issues[:_MAX_SHOWN_ISSUES]:
        events.fail("merge.issue", f"  {i}", chunk=chunk_name, issue=i)
    if len(issues) > _MAX_SHOWN_ISSUES:
        # The display bound, as a field. A refusal listing 10 of 400 issues
        # reads as a 10-issue problem unless the bound travels with it.
        events.fail(
            "merge.issues_truncated",
            f"  … and {len(issues) - _MAX_SHOWN_ISSUES} more",
            shown=_MAX_SHOWN_ISSUES,
            omitted=len(issues) - _MAX_SHOWN_ISSUES,
        )
    return 2


def _preflight(repo_root: Path, chunk_path: Path) -> int | None:
    """Both pre-merge gates; an rc to return, or None meaning "go ahead".

    TWO checks, asking genuinely different questions, and the second cannot be
    folded into the first:

    - **Per-chunk schema/integrity** — the same gate `build()` applies, added
      after a chunk with a missing `_origin` marker merged happily and the damage
      surfaced later as a node that had quietly stopped being retrievable.
      `kb-merge` is the sharper of the two doors: it takes a FRESH extraction
      straight off an agent, the input least likely to be well-formed.
    - **Cross-chunk `source_file` ownership** against the COMMITTED corpus
      (#189). Invisible to the first: two chunks can each be perfectly
      well-formed and still name one `source_file`, which `build_merge` resolves
      by deleting the replay loser's nodes for it. That is exactly how a
      2026-08-06 chunk destroyed 72 nodes of an unrelated source with every gate
      green — the per-chunk validator said ✓, the cold review passed it as data,
      and `kb-build` exited 0.
    """
    from kb_setup import chunks as _chunks

    issues = _chunks.validate_files([chunk_path]).get(chunk_path) or []
    if issues:
        return _refuse(chunk_path.name, "failed validation", issues)
    collisions = _chunks.collision_issues(
        [chunk_path, *_committed_chunks(repo_root)], merging=chunk_path
    )
    if collisions:
        return _refuse(chunk_path.name, "collides with the committed corpus", collisions)
    return None


def _record_counts(repo_root: Path, graph_path: Path, handoff: Path, *, tag: str) -> None:
    """Move `_merge_docs.py`'s counts into the ledger, then remove the handoff.

    A file rather than a return value because the two halves run under DIFFERENT
    interpreters: `_merge_docs.py` imports graphify and cannot import `kb_setup`,
    so there is no in-process channel. Its stdout is deliberately not captured
    either — the merge line is the operator's live progress, and swallowing it to
    parse a number back out would trade a visible report for an invisible one.

    Removed unconditionally, including when the merge failed and wrote nothing:
    a stale handoff from an earlier run must never be read as this run's result.

    On the SUCCESS path `_derive_prose` records again a moment later and its
    record wins — same node/edge/hyperedge counts, no `members`, because
    `ProseStats` counts hyperedges rather than their members. This call is not
    therefore redundant: it is the record that survives when the prose derivation
    FAILS, which is precisely the run after which the next merge would otherwise
    have no baseline. Two writers, one of them a fallback, and the richer of the
    two is the one that can be lost.
    """
    from kb_setup import graph_counts

    try:
        counts = json.loads(handoff.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        counts = None
    finally:
        handoff.unlink(missing_ok=True)
    if isinstance(counts, dict):
        graph_counts.record(repo_root, graph_path, counts, tag=tag)


def merge_chunk(repo_root: Path, chunk: str, root: str | None = None) -> int:
    """Merge one host-agent extraction chunk into graphify-out/graph.json.

    Runs `_merge_docs.py` under graphify's bundled interpreter (it imports
    graphify) with a Gemini-free env. `root` is the source root for path
    relativization (defaults to the chunk's dir; moot for URL-sourced chunks).

    A successful merge then RE-DERIVES the prose graph, exactly as
    `graph.build()` does at its own last step. `graph-prose.json` is a pure
    function of `graph.json`, so a merge that does not refresh it leaves the
    corpus and its scoped view disagreeing — and `--prose` is the *recommended*
    arm for a question about the documents, while the `kb-curator` ingestion
    workflow is add -> merge -> label with no prose step. Measured 2026-07-30:
    after merging a 132-node chunk, `kb-query --prose` still reported the
    pre-merge 2,421 nodes and returned none of the just-merged material; the
    only thing that had ever fixed it was the next unrelated `kb-build`. So
    every merge-only ingestion had been silently answering document questions
    from an older corpus.
    """
    chunk_path = Path(chunk)
    if not chunk_path.is_file():
        events.fail("merge.no_chunk", f"[kb-merge] no such chunk: {chunk}", chunk=str(chunk))
        return 2

    # BOTH gates BEFORE MERGING — schema, then cross-chunk ownership. See
    # `_preflight` for what each catches and why neither subsumes the other.
    preflight_rc = _preflight(repo_root, chunk_path)
    if preflight_rc is not None:
        return preflight_rc
    out = repo_root / "graphify-out" / "graph.json"
    src_root = root or str(chunk_path.resolve().parent)
    gpy = graphify_python(repo_root)
    cmd = [gpy, str(_MERGE_SCRIPT), str(chunk_path), src_root, str(out)]

    # #191. `_merge_docs.py` knows what it ADDED and what the graph now HOLDS;
    # the one number it cannot obtain for free is what the graph held BEFORE,
    # because re-parsing several hundred MB to learn one integer is the most
    # expensive possible way to ask. The ledger answers it for nothing — and
    # answers `None` rather than a stale number whenever the graph moved outside
    # a tracked writer, so the merge line reports "not checked" instead of a
    # confident delta computed against fiction.
    from kb_setup import graph_counts

    prior = graph_counts.read(repo_root, out)
    if prior is not None and "nodes" in prior:
        cmd += ["--prior-nodes", str(prior["nodes"])]
    # #198 item 1. Passed INDEPENDENTLY of `--prior-nodes`, not inside the same
    # `if`: `graph_counts` records four fields but `_derive_prose` writes only
    # three (no `members`), so a ledger entry carrying one slot and not another is
    # a shape this repo already produces. Nesting these would let a missing
    # `nodes` silently suppress a hyperedge check that was perfectly available.
    if prior is not None and "hyperedges" in prior:
        cmd += ["--prior-hyperedges", str(prior["hyperedges"])]
    # CLEARED before launch, not merely consumed after. The path is fixed and
    # reused, and `_merge_docs.py` legitimately writes nothing for a 0-node chunk
    # or a refused export — so a leftover file from an interrupted earlier run
    # would be read as THIS run's counts and recorded against this run's graph.
    # (Cold lane, round 2, P2.)
    counts_out = out.with_name(".merge-counts.tmp.json")
    counts_out.unlink(missing_ok=True)
    cmd += ["--counts-out", str(counts_out)]
    if _self_remerge(repo_root, chunk_path):
        cmd.append("--self-remerge")

    # The echoed command, BEFORE the subprocess runs — this is the progressive
    # print that made `merge_chunk` undeferrable under recipe rule 3, and the
    # operator wants it first because the merge is the slow part.
    events.say("merge.command", f"  $ {' '.join(cmd)}", argv=list(cmd))
    rc = subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode
    _record_counts(repo_root, out, counts_out, tag="kb-merge")
    if rc != 0:
        # Gated on the merge's rc, not run unconditionally: a failed merge may
        # have left graph.json untouched or half-written, and deriving from
        # either would replace a valid prose graph with one nobody asked for.
        # The caller's job here is the failed merge, and this rc says so.
        return rc
    prose_rc = _derive_prose(repo_root, tag="kb-merge", did="the chunk merged")
    if prose_rc != 0:
        return prose_rc

    # Deferred import: `graph` imports THIS module at its own top level
    # (`from kb_setup import graph_checks, graphify_ops`), so a top-level
    # `from kb_setup import graph` here would be circular. By the time this
    # function actually RUNS both modules are already fully loaded, so this is
    # a plain sys.modules cache hit — it only has to be deferred, not avoided.
    from kb_setup import graph

    try:
        graph.append_merged_chunk(repo_root, chunk, src_root)
    except (OSError, ValueError) as exc:
        # NOT swallowed: the chunk really did merge and the prose graph really
        # did re-derive, but reporting rc=0 here would claim the operation is
        # fully durable when the one record `kb-watch` reads to recompose from
        # just failed to extend — the same silent-discard this whole ledger
        # exists to prevent, arriving through its own write path instead of
        # through recomposition. Same shape as `_derive_prose`'s own gate.
        events.fail(
            "merge.ledger_write_failed",
            f"[kb-merge] the chunk merged and the prose graph was re-derived, but "
            f"recording it in the recomposition ledger failed: {exc}\n"
            f"[kb-merge] a future `mise run kb-watch` will not replay this chunk "
            f"unless it is re-merged.",
            error=str(exc),
        )
        return 1
    # LAST, and only on the fully-successful path (#181). `_merge_docs.py` is the
    # last writer of `graph.json` here — `_derive_prose` writes `graph-prose.json`
    # and `append_merged_chunk` writes the ledger, neither of which `currency.toml`
    # declares — so the fingerprint this records is the merge's final bytes.
    #
    # This is the THIRD wholesale writer of `graph.json`, alongside `label` and
    # `artifacts.generate`; `stamps.py`'s docstring said "two callers" because
    # this one was deferred out of #179. Without it a merge-only run — the
    # `kb-curator` skill's own quick path, with no following `kb-label` — leaves
    # `kb-currency-check` reporting build-stamp drift until something else
    # rewrites and restamps the graph.
    #
    # The full restamp, not a narrowed one. Measured on a real merge rather than
    # inferred: of the four declared artifacts, ONLY `graph.json` moves — the
    # three derived views are byte-identical before and after, so re-fingerprinting
    # them records the value they already had and masks nothing. The narrowing
    # this ticket's body floated is byte-for-byte identical in outcome. What a
    # merge really does invalidate is the derived views' CONTENT, and no
    # `size:mtime_ns` was ever able to see that — which is why the signal that
    # covers it is `currency.views`, not a variant of this call.
    #
    # A failed ledger write returns above without reaching here, so the stamp
    # stays stale for a graph that really was rewritten. That is the honest
    # outcome: the drift line then reports, truthfully, that something rewrote
    # the graph outside a complete run.
    stamps.refresh_after_regen(repo_root, tag="kb-merge")
    return 0


def _derive_prose(repo_root: Path, *, tag: str, did: str) -> int:
    """Re-derive the prose graph, reporting a failure as a non-zero rc.

    The derivation's own failure modes raise, and all of them leave NO prose
    graph — `prose.derive` unlinks first precisely so an abort fails closed.
    That is the right artifact state and the wrong exit code: `graph.json` really
    did change, so returning 0 would report an operation whose `--prose` arm has
    just gone missing as an unqualified success.

    All THREE are caught, and the first draft caught two. `ValueError` covers
    nothing-survives and — since `json.JSONDecodeError` subclasses it — an
    unreadable `graph.json`; `SystemExit` covers no-built-graph. **`OSError` is
    the one that escaped**: a full disk, a vanished directory, a permissions
    change. It is not hypothetical — `tests/test_prose_rederivation.py` injects
    exactly that fault against `prose.derive`, so the module had a test for a
    failure this wrapper then let propagate as an unhandled traceback instead of
    the rc and the message below. (Cold lane, round 2.)

    `tag`/`did` name the CALLER, because this message is the only thing telling
    someone which of their two graphs is now absent — and "the chunk merged"
    printed after a `kb-label` run would send them looking at the wrong step.
    """
    try:
        stats = prose.derive_for(repo_root)
    except (OSError, ValueError, SystemExit) as exc:
        events.fail(
            "prose.derive_failed",
            f"[{tag}] {did}, but the prose graph could not be re-derived: "
            f"{exc}\n[{tag}] `kb-query --prose` has no corpus until "
            f"`mise run kb-prose` (or `mise run kb-build`) succeeds.",
            tag=tag,
            error=str(exc),
        )
        return 1
    # The prose derivation is the ONE parse of `graph.json` that happens after
    # every write on this path, and it already counts both sides. So the counts
    # ledger is refreshed from it for free (#191, cold lane round 1, P2).
    #
    # Without this the feature was largely dead in ordinary use: `kb-label`
    # rewrites `graph.json` and never recorded counts, the `kb-curator` workflow
    # is "always relabel after a merge", and the ledger is fingerprint-gated — so
    # the merge AFTER any prior ingestion's label pass found the fingerprint moved
    # and reported "arithmetic NOT checked". Correct, and useless: the check
    # existed and could almost never run.
    #
    # `members` is deliberately NOT recorded here — `ProseStats` counts
    # hyperedges, not their members, and inventing a zero would be worse than an
    # absent key. `graph_counts.read` returns only the fields present, and the
    # only field any consumer reads is `nodes`. `assert_composition` still
    # records members on the build path, where it has them for free.
    from kb_setup import graph_counts

    graph_counts.record(
        repo_root,
        repo_root / "graphify-out" / "graph.json",
        {"nodes": stats.nodes_in, "edges": stats.links_in, "hyperedges": stats.hyperedges_in},
        tag=tag,
    )
    return 0


def _unaccounted_label_stderr(stderr: bytes) -> str:
    """Label-pass stderr minus what Graphify narrates in the ordinary course.

    A separate function so the refusal stays ONE branch: this repo's required
    state — no LLM backend, per `do-not.md` #4, which `label`'s own comment
    calls "the clean default" — is narrated on stderr, and the blanket refusal
    failed a build for being configured correctly. Everything else still
    refuses, line by line, through the same filter the receipt path uses.
    """
    from kb_setup import graphify_health

    return graphify_health.strip_routine_narration(stderr.decode("utf-8", errors="replace")).strip()


def label(repo_root: Path, *, missing_only: bool = False, claude_cli: bool = False) -> int:
    """(Re)label communities WITHOUT Gemini.

    Default = graphify's deterministic, LLM-free hub-name labeler (names each
    community after its highest-degree member). Instant, no API, no Gemini.

    Why deterministic is the default (Ray, 2026-07-22, control-arm verified): the
    only LLM path that is NOT Gemini is graphify's `claude-cli` backend. Issue
    #2076 reported it BROKEN for labeling — the CLI returns prose-wrapped JSON
    ("Done — cluster names above …") that graphify cannot parse, so every batch
    fails and the run is slow + noisy for no gain.

    **Scope, corrected 2026-08-23.** A native `graphify extract --mode deep
    --backend claude-cli` run (see `graphify_native_extract.py`) confirmed the
    EXTRACTION path works cleanly at the pinned 0.9.48 — 19/19 chunks, no
    prose-wrapping, structured JSON throughout. That is a DIFFERENT code path
    from labeling (`cluster-only`'s LLM-naming call), which this session did NOT
    re-test. #2076's report is therefore still the last evidence for LABELING
    specifically — treat it as unconfirmed either way, not as refuted. Do not
    read the extraction result as evidence labeling now works too.

    `--claude-cli` still opts into the labeling path (falls back to deterministic
    on the inevitable failure, if #2076 still applies there), kept only so a
    future re-probe can go through the task rather than a hand-run `graphify
    label --claude-cli`. clean_env() strips GEMINI/GOOGLE either way, so Gemini
    can never be auto-selected.

    A successful label RE-DERIVES the prose graph, for the same reason `kb-merge`
    does. `graphify label` is not a sidecar-only write: verified in the installed
    0.9.30 — `graphify/cli.py:1546` selects `label`, and that branch runs unbroken
    (no intervening `elif cmd`) to `to_json(G, communities, str(out /
    "graph.json"), …)` at :1830 — so it rewrites `graph.json` outright. (:1836 is
    six lines further on and writes the LABELS SIDECAR; this docstring cited it by
    mistake until the cold lane caught it, which had the citation pointing at
    exactly the sidecar-only write the sentence exists to deny.) The
    documented ingestion order is merge -> label, so without this the merge's own
    re-derivation is undone by the very next step and `--prose` is stale again
    with nothing having failed. (Cold lane, round 1.)

    Hyperedges are graphify's own job here since 0.9.34: the label round-trip
    reads both graph.json slots and re-attaches survivors (#2485, verified on
    the installed binary, not the release notes), so the 0.9.33-era
    capture/reattach carry this function used to run was retired at that bump
    — `hyperedges.py`'s module docstring records the mechanism and the
    evidence. `prose.ProseStats`' hyperedge-retention report now describes
    what graphify itself preserved, which is the fact worth reporting.
    """
    # Gate on the binary we are ABOUT TO RUN, not on PATH. The old
    # `shutil.which("graphify")` check sat directly in front of a
    # PATH-independent invocation and could abort with `mise which` resolving
    # perfectly well — refusing to run a binary it had already found. A bare
    # name is `graphify_exe`'s last resort, and `Path("graphify").is_file()` is
    # False, so the genuinely-absent case still refuses.
    exe = graphify_exe(repo_root)
    if not Path(exe).is_file():
        events.fail(
            "label.no_graphify",
            "[kb-label] graphify not found — neither `mise which graphify` nor PATH "
            "resolved it. Run `mise install`.",
        )
        return 2

    # Snapshotted BEFORE anything runs, for the artifact this operation
    # can move: `graphify label` regenerates GRAPH_REPORT.md as well as the graph
    # (it prints "GRAPH_REPORT.md and graph.json updated"). Bracketing the run is
    # what lets the stamp certify the report against the graph this label just
    # wrote, while leaving graphml/wiki — which label does NOT touch — correctly
    # reported as describing an earlier one (#182).
    views_before = stamps.snapshot_views(repo_root)

    base = [exe, "label", "."]
    if missing_only:
        base.append("--missing-only")

    def _run(cmd: list[str], why: str) -> int:
        events.say("label.command", f"  $ {' '.join(cmd)}   # {why}", argv=list(cmd), why=why)
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            env=clean_env(),
            check=False,
            capture_output=True,
        )
        if result.stdout:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.buffer.flush()
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
            sys.stderr.buffer.flush()
        if result.returncode != 0:
            return result.returncode
        if result.stderr and _unaccounted_label_stderr(result.stderr):
            digest = hashlib.sha256(result.stderr).hexdigest()
            events.fail(
                "label.stderr",
                "[kb-label] refusing warning-bearing Graphify success "
                f"(stderr_bytes={len(result.stderr)}, stderr_sha256={digest})",
            )
            return 3
        return 0

    if not claude_cli:
        # No --backend + GEMINI/GOOGLE stripped -> auto-detect finds nothing ->
        # deterministic hub labeler. The clean default.
        return _labelled(
            repo_root,
            _run(base, "deterministic no-LLM hub labels (Gemini-free)"),
            views_before,
        )

    rc = _run(
        [*base, "--backend=claude-cli", "--max-concurrency=1"],
        "claude-cli backend (opt-in; broken #2076 — expect fallback)",
    )
    if rc == 0:
        return _labelled(repo_root, rc, views_before)
    # WARNING rather than ERROR: the run CONTINUES on the fallback, which is the
    # exact shape R9 names — a degraded path taken silently. It was already on
    # stderr, so nothing moves.
    events.warn(
        "label.claude_cli_failed",
        "[kb-label] claude-cli backend failed (#2076) — deterministic no-LLM fallback.",
        fallback="deterministic",
    )
    return _labelled(repo_root, _run(base, "deterministic fallback"), views_before)


def _labelled(
    repo_root: Path,
    rc: int,
    views_before: dict[str, dict[str, str]] | None = None,
) -> int:
    """Refresh the currency stamp, then re-derive the prose graph.

    Both are gated on `rc`, for the same reason `merge_chunk` gates: a labelling run that
    failed may have left `graph.json` in any state, and either restamping it
    or deriving from it would assert a fact ("the run succeeded") that is
    false. The failing rc is the caller's job, and returning it unchanged says so.

    Until the 0.9.34 bump a hyperedge reattach ran first, as the last writer
    of graph.json, so the stamp would fingerprint ITS bytes (#179). With the
    carry retired (`hyperedges.py`'s module docstring), graphify's own
    `to_json` is the last writer again and the stamp certifies exactly the
    bytes label wrote — one writer fewer between the run and its fingerprint.

    The restamp runs before `_derive_prose`, not after, because
    `graphify-out/graph-prose.json` is NOT in the stamped set —
    `currency.toml`'s `[tool.graphify]` declares `artifact =
    "graphify-out/graph.json"` and `artifacts = ["graphify-out/GRAPH_REPORT.md",
    "graphify-out/graph.graphml", "graphify-out/wiki"]`, neither of which is the
    prose graph. So a prose derivation that fails afterwards cannot invalidate a
    fingerprint that was never about it, and gating the restamp on the prose
    step's rc would only buy a permanent, meaningless currency red on a graph
    that was legitimately relabelled.

    One more thing worth saying plainly, so the next reader does not mistake it
    for a bug: `stamps.refresh_after_regen` re-fingerprints the WHOLE declared
    artifact set via `sync.restamp_artifacts`, so this restamp also touches
    `GRAPH_REPORT.md` / `graph.graphml` / `wiki` — none of which `label`
    regenerated. That is correct and deliberate; the stamp answers "has
    anything moved since we last looked", not "is every output mutually
    consistent", which is the same semantics `stamps.refresh_after_regen`
    already documents for a partial `kb-artifacts only=` run. It also carries
    the recorded INPUT fingerprints forward verbatim rather than re-observing
    `sources/`: `label` never reads `sources/`, so it has no standing to
    restate what the graph was built from — re-observing them would be drift
    laundering, which was a P1 in the last round's review.
    """
    if rc != 0:
        return rc
    stamps.refresh_after_regen(repo_root, tag="kb-label", views_before=views_before)
    return _derive_prose(repo_root, tag="kb-label", did="communities were relabelled")


#: The flag `kb-query` adds on top of `graphify query`. Not a graphify flag —
#: it resolves to graphify's own `--graph`, pointed at the derived prose graph.
PROSE_FLAG = "--prose"

#: Selects the BM25/IDF lexical scorer (`kb_setup.lexical`) instead of
#: `graphify query`. A THIRD retrieval path, not a replacement for `--prose`
#: (knowledge-base#12 P1): the golden set measures `unscoped` / `prose` /
#: `prose+idf` side by side, so the scorer's effect stays attributable to the
#: scorer. It reads the same derived prose graph `--prose` selects, so the two
#: together are redundant rather than contradictory and are allowed.
IDF_FLAG = "--idf"

#: The only flags the `--idf` path understands. Everything else is REJECTED
#: rather than ignored: this path never shells out to graphify, so a
#: graphify-only flag (`--budget`, `--depth`) alongside it would have no effect
#: whatsoever — and a flag that silently does nothing is worse than one that
#: errors, because the caller reads the answer as if the flag applied.
GRAPH_FLAG = "--graph"
_IDF_TOP = "--top"

#: How many ranked hits `--idf` prints. Chosen to sit just above the golden
#: set's `k=10` window so a human reading the output can see what fell just
#: outside it; the eval calls the library directly and is not affected.
IDF_DEFAULT_TOP = 20

#: The attached form of graphify's own flag, which graphify DOES NOT SUPPORT.
#: Probed 2026-07-25 from a scratch directory: `graphify query q
#: --graph=<abs path>` exits 1 with `graph file not found:
#: /private/tmp/graphify-out/graph.json` — it ignores the argument entirely and
#: falls back to the cwd-relative default. So the form can neither be forwarded
#: (graphify drops it) nor read as "the caller pinned a corpus" (they did not,
#: as far as graphify is concerned). It is rejected instead, because the
#: alternative is an answer from a corpus nobody chose — which is the one
#: failure this wrapper exists to prevent.
ATTACHED_GRAPH = "--graph="


def query(repo_root: Path, args: Sequence[str]) -> int:
    """`kb-query` — `graphify query`, with `--prose` selecting the prose-only graph.

    The graph is ALWAYS pinned with an explicit `--graph`, never left to resolve
    against the process cwd. graphify's default is `graphify-out/graph.json`
    *relative to where it runs*, which silently agrees when invoked from the repo
    root and silently answers from some other corpus when it is not — the same
    trap that was caught in review of the retrieval eval (knowledge-base#30).

    `--prose` alongside an explicit `--graph` is an error rather than a
    precedence rule: the whole point of the flag is which corpus answered, so
    "one of them quietly wins" is the one behaviour that must not exist.
    """
    rest = [a for a in args if a not in {PROSE_FLAG, IDF_FLAG}]
    wants_prose = PROSE_FLAG in args
    wants_idf = IDF_FLAG in args
    attached = [a for a in rest if a.startswith(ATTACHED_GRAPH)]
    if attached:
        events.fail(
            "query.attached_graph_form",
            f"[kb-query] graphify does not support the attached form "
            f"({attached[0]}) — it ignores the argument and answers from the "
            f"cwd-relative default instead. Use `--graph <path>`, or --prose.",
            argument=attached[0],
        )
        return 2
    if wants_prose and GRAPH_FLAG in rest:
        events.fail(
            "query.conflicting_corpora",
            f"[kb-query] {PROSE_FLAG} and --graph both given — they name different "
            f"corpora and there is no sensible winner. Pass one.",
        )
        return 2
    if wants_idf:
        return _idf_query(repo_root, rest)
    assert_pinned_graphify(repo_root)
    if GRAPH_FLAG not in rest:
        graph = prose.prose_graph_path(repo_root) if wants_prose else _full_graph(repo_root)
        if not graph.is_file():
            missing = "mise run kb-prose" if wants_prose else "mise run kb-build"
            events.fail(
                "query.no_graph",
                f"[kb-query] no graph at {graph} — run `{missing}` first",
                graph=str(graph),
            )
            return 2
        rest = [*rest, "--graph", str(graph)]
    return _run_graphify_query(repo_root, rest)


def _run_graphify_query(repo_root: Path, args: Sequence[str]) -> int:
    """Run a pinned query and refuse output that declares reduced coverage."""
    proc = subprocess.run(
        [graphify_exe(repo_root), "query", *args],
        cwd=repo_root,
        env=clean_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        return proc.returncode
    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.QUERY,
        graphify_health.GraphifyEvidence(
            observed=True,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        ),
    )
    if "truncated" in receipt.reasons:
        events.fail(
            "query.truncated",
            "[kb-query] Graphify returned an incomplete TRUNCATED result with rc=0. "
            "Narrow the query or raise --budget; this prefix is not evidence of absence.",
            coverage_reduced=True,
        )
        return 3
    if "stderr" in receipt.reasons:
        events.fail(
            "query.stderr_warning",
            "[kb-query] Graphify emitted stderr while returning rc=0. The warning/error "
            "must be investigated before this result can be used.",
            coverage_reduced=True,
        )
        return 3
    if receipt.state is not graphify_health.GraphifyState.COMPLETE:
        events.fail(
            "query.incomplete",
            "[kb-query] Graphify returned incomplete coverage with rc=0; this result "
            "cannot be used as evidence of absence.",
            coverage_reduced=True,
            reasons=list(receipt.reasons),
        )
        return 3
    return 0


def _full_graph(repo_root: Path) -> Path:
    """The unscoped graph — every node, code AST included."""
    return repo_root / "graphify-out" / "graph.json"


def affected(repo_root: Path, args: Sequence[str]) -> int:
    """`kb-affected` — `graphify affected`, the reverse-dependency question.

    `query` is a forward BFS from the terms you name, so "what calls this" is a
    question it structurally cannot answer. `affected` walks the edges backwards
    instead, which is the blast radius of a change: which callers and which
    tests move if this symbol does.

    Wired here rather than left to a bare `graphify affected` — which the guard
    does allow — because `graph.refresh_self` exists precisely so this question
    is answerable about OUR code, and a capability with no verb is one nobody
    reaches for. `--depth` defaults to 2 upstream; pass it through untouched.

    The graph is pinned explicitly for the same reason `query` pins it: the
    upstream default resolves `graphify-out/graph.json` against the process cwd,
    so it answers from a different corpus depending on where it was run. Callers
    may still pass their own `--graph <path>`, which wins.

    The ATTACHED spelling `--graph=<path>` is REFUSED, exactly as `query`
    refuses it and for the same measured reason (see :data:`ATTACHED_GRAPH`):
    graphify ignores that form entirely and falls back to its cwd-relative
    default. Accepting it here would silently discard the caller's choice and
    substitute our pin — benign today, since our pin is the graph they almost
    certainly wanted, but it makes the docstring above a lie for one spelling.
    A near-identical sibling hardened against an input while this one was not is
    the shape a cold review flagged; the fix is to make them agree.
    """
    if not args:
        events.fail(
            "affected.usage",
            '[kb-affected] usage: mise run kb-affected -- "<symbol>" [--depth N] [--relation R]...',
        )
        return 2
    if attached := [a for a in args if a.startswith(ATTACHED_GRAPH)]:
        events.fail(
            "affected.attached_graph_form",
            f"[kb-affected] graphify does not support the attached form "
            f"({attached[0]}) — it ignores the argument and answers from the "
            f"cwd-relative default instead. Use `--graph <path>`.",
            argument=attached[0],
        )
        return 2
    rest = list(args)
    if GRAPH_FLAG not in rest:
        graph = _full_graph(repo_root)
        if not graph.is_file():
            events.fail(
                "affected.no_graph",
                f"[kb-affected] no graph at {graph} — run `mise run kb-build` first",
                graph=str(graph),
            )
            return 2
        rest = [*rest, GRAPH_FLAG, str(graph)]
    return subprocess.run(
        [graphify_exe(repo_root), "affected", *rest], cwd=repo_root, env=clean_env(), check=False
    ).returncode


@dataclass(frozen=True)
class _IdfArgs:
    """A parsed `--idf` invocation: the question, the corpus, how many to show."""

    question: str
    graph: Path | None
    top: int


def _parse_idf_args(rest: Sequence[str]) -> _IdfArgs | str:
    """Parse `--idf`'s arguments, or return the error message to print.

    Split out of :func:`_idf_query` so each half does one thing: this one only
    reads arguments and never touches the filesystem or prints, which is what
    lets it be tested without a graph on disk.
    """
    words: list[str] = []
    graph: Path | None = None
    top = IDF_DEFAULT_TOP
    args = list(rest)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {GRAPH_FLAG, _IDF_TOP}:
            if i + 1 >= len(args):
                return f"{arg} needs a value"
            value = args[i + 1]
            i += 2
            if arg == GRAPH_FLAG:
                graph = Path(value)
                continue
            # Validated by the conversion itself, not by `isdigit()`: that
            # predicate accepts superscripts and other Numeric_Type=Digit
            # characters that `int()` then REJECTS, so `--top ²` would raise
            # instead of returning this message.
            try:
                parsed_top = int(value)
            except ValueError:
                return f"{_IDF_TOP} needs a positive integer, got {value!r}"
            if parsed_top < 1:
                return f"{_IDF_TOP} needs a positive integer, got {value!r}"
            top = parsed_top
            continue
        if arg.startswith("-"):
            return (
                f"{IDF_FLAG} does not understand {arg!r}. It runs our own scorer, "
                f"not `graphify query`, so a graphify flag would have no effect at "
                f"all — which is why this is an error and not a warning. "
                f"Supported: {GRAPH_FLAG} <path>, {_IDF_TOP} <n>."
            )
        words.append(arg)
        i += 1
    if not words:
        return f'{IDF_FLAG} needs a question, e.g. kb-query -- "…" {IDF_FLAG}'
    return _IdfArgs(question=" ".join(words), graph=graph, top=top)


def _idf_query(repo_root: Path, rest: Sequence[str]) -> int:
    """`kb-query --idf` — rank the prose graph with the BM25/IDF scorer.

    Never shells out to graphify: this is our own scorer over the same derived
    corpus (`kb_setup.lexical`). It therefore accepts only the flags it can
    honour and REJECTS everything else, rather than forwarding or ignoring it —
    a `--budget` silently doing nothing here would let a caller read the answer
    as if a budget had applied.
    """
    from kb_setup import lexical

    parsed = _parse_idf_args(rest)
    if isinstance(parsed, str):
        events.fail("query.bad_args", f"[kb-query] {parsed}", detail=parsed)
        return 2

    explicit = parsed.graph is not None
    graph = parsed.graph if explicit else prose.prose_graph_path(repo_root)
    if not graph.is_file():
        # Only the DEFAULT corpus has a task that creates it. Telling someone who
        # passed their own --graph to run `kb-prose` names a command that would
        # not produce the file they asked for.
        fix = "check the path" if explicit else "run `mise run kb-prose` first"
        events.fail("query.no_graph", f"[kb-query] no graph at {graph} — {fix}", graph=str(graph))
        return 2
    try:
        index = lexical.load_index(graph)
    except (OSError, ValueError) as exc:
        events.fail(
            "query.index_failed",
            f"[kb-query] could not index {graph}: {exc}",
            graph=str(graph),
            error=str(exc),
        )
        return 1

    hits = lexical.search(index, parsed.question)
    events.say(
        "query.idf_header",
        f"[kb-query] {IDF_FLAG}: {index.size:,} indexed node(s) from {graph.name}",
        indexed=index.size,
        graph=graph.name,
    )
    if not hits:
        # `truncated=False` is the machine-readable half of a sentence this repo
        # wrote deliberately: an empty result that IS an answer, versus one that
        # is a display bound. `probes-need-a-control-arm.md` is about telling
        # those apart, and a field says it where prose only asserts it.
        events.say(
            "query.no_hits",
            f"[kb-query] no node shares a term with {parsed.question!r} — that is a "
            f"real empty result, not a truncated one.",
            hits=0,
            truncated=False,
        )
        return 0
    for rank, hit in enumerate(hits[: parsed.top], start=1):
        events.say(
            "query.hit",
            f"{rank:>3}  {hit.score:6.2f}  {hit.label}  [src={hit.source_file}]",
            rank=rank,
            score=round(hit.score, 2),
            label=hit.label,
            source_file=hit.source_file,
        )
    if len(hits) > parsed.top:
        events.say(
            "query.hits_truncated",
            f"     … {len(hits) - parsed.top:,} more scoring above zero (raise {_IDF_TOP})",
            shown=parsed.top,
            omitted=len(hits) - parsed.top,
        )
    return 0


def transcribe(repo_root: Path, audio: str) -> int:
    """Transcribe a local audio file with graphify's bundled faster-whisper.

    Local, no API key, no LLM backend (e.g. a graphify-downloaded yt_*.m4a). Prints
    the transcript path. Extraction of the transcript into the graph is then the
    normal host-agent (Claude Code) step.
    """
    audio_path = Path(audio)
    if not audio_path.is_file():
        events.fail(
            "transcribe.no_audio",
            f"[kb-transcribe] no such audio file: {audio}",
            audio=str(audio),
        )
        return 2
    gpy = graphify_python(repo_root)
    code = (
        "from pathlib import Path\n"
        "from graphify.transcribe import transcribe\n"
        f"p = transcribe(Path({str(audio_path)!r}), output_dir=Path({str(audio_path.parent)!r}))\n"
        "print('[kb-transcribe] transcript ->', p)\n"
    )
    events.say(
        "transcribe.command",
        f"  $ {gpy} -c '<graphify.transcribe.transcribe {audio_path.name}>'",
        audio=audio_path.name,
    )
    return subprocess.run([gpy, "-c", code], cwd=repo_root, env=clean_env(), check=False).returncode
