"""#182 — does each derived view describe the graph that is on disk NOW?

`sync`'s fingerprint is `size:mtime_ns`, so it can only detect a declared output
that **moved**. A derived view that is stale precisely because nothing
regenerated it never moves, so it reads OK forever. Measured on the live corpus
immediately after a `kb-label` that relabelled 9,385 communities: all four rows
reported `recorded == live` while `graph.graphml` and `wiki/` described the
pre-label graph, ~11 hours behind it.

Two facts make that worse than it first looks. `kb-build` does not regenerate the
views — `artifacts.generate` has exactly one caller, the `kb-artifacts` task — so
a rebuild does not close the gap either; it re-stamps the stale views at their
unchanged fingerprints. And `graphify label` regenerates `GRAPH_REPORT.md` but
not `graphml`/`wiki`, so the documented merge -> label flow leaves two of the
three views behind every time.

## Why this compares provenance and not clocks

#182 proposed the ordering rule — a view older than the graph is stale by
construction — and it was implemented, run against the live corpus, and
**refuted by its own first output**:

    GRAPH_REPORT.md  2026-08-05 12:12:07     <- written by `graphify label`
    graph.json       2026-08-05 12:12:25     <- written by the SAME label, 18.7 s later
    graph.graphml    2026-08-05 01:13:00     <- genuinely 11 h behind

The report is 18.7 s "older" than the graph and describes it exactly; the rule
cannot tell that from `graphml`'s eleven hours, because a run writes its outputs
in some order and the primary is not always last. A tolerance window only moves
the boundary somewhere unprincipled — the gap grows with the corpus, so any
constant silently stops working — and a false positive is expensive here: the
remedy it prints costs minutes.

So the stamp records what actually happened instead, exactly as it already does
for the tool version (`sync.write_stamp`'s docstring: graphify stamps no version
into its own output, so the sidecar records the one that ACTUALLY RAN). Per view:
the graph fingerprint it was last observed to be generated FROM. Stale is then
an equality, with no clock anywhere in it — see `sync.view_records`.

## Why it reports separately

Under its OWN header and its own verdict vocabulary, for the same reason
`staleness` has them: `build-stamp`'s remedy line is "regenerate or rebuild", and
*rebuild* is the wrong fix here — `kb-build` genuinely cannot repair it.

**What this replaces is an accident, not a check.** Before #179, `graph.json`'s
moved fingerprint raised a drift line whose remedy text was "regenerate
(`mise run kb-artifacts`) or rebuild", and following it *would* have refreshed
the views. That line was a FALSE POSITIVE about `graph.json` doing accidental
duty as a TRUE reminder about `graphml`/`wiki`. #179 removed the false positive
and took the accidental reminder with it. A signal that only works by accident is
not a check — so the answer is a real one, not a restored false positive.

Silence has a named owner in every quiet state (:data:`NEVER_BUILT`,
:data:`NOT_GENERATED`), because this module deliberately does not restate a
condition another check already reports loudly in the same command's output.
Those hand-offs are asserted in `tests/test_currency_views.py`, so a later change
cannot leave a state with no reporter at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kb_setup.currency import sync

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from kb_setup.currency.config import ToolSpec

#: Nothing to compare — no primary artifact declared, no derived views declared,
#: no stamp configured, or the wrong host. Genuinely not-applicable rather than
#: not-checked.
SKIP = "skip"
#: There is no build to compare against. Silent HERE: `staleness.report` already
#: prints the fresh-clone "no graph has been built here yet" line, and two
#: headers saying the same thing is how a reader learns to skim past both.
NEVER_BUILT = "never-built"
#: A graph and a stamp exist, but no declared view does. Silent HERE: `sync`'s
#: build-stamp check already reports each one as DRIFT `(missing)` with the same
#: remedy. A distinct state rather than OK, because "every view is current" would
#: be a false pass over a set in which nothing exists.
NOT_GENERATED = "not-generated"
#: A view exists but its provenance is unknown — the stamp predates this check,
#: or the view has never been observed being generated. Nothing else covers this,
#: so it is loud. Never rendered as a pass.
NOT_VERIFIABLE = "not-verifiable"
#: Asked, and at least one view was generated from a graph that is no longer the
#: one on disk.
STALE = "stale"
#: Asked, and every view that exists was generated from the current graph.
OK = "ok"

_HEADER = "[views]"

#: How much of a `size:mtime_ns` fingerprint to show. The size is the legible
#: half — a reader recognises a graph by it — and the mtime tail is only there to
#: distinguish two rebuilds that happened to land on the same size.
_FP_TAIL = 4


@dataclass(frozen=True)
class ViewStatus:
    """One tool's derived-views-vs-graph verdict.

    `stale` is populated only for :data:`STALE` and `blind` only for
    :data:`NOT_VERIFIABLE`; each entry is a rendered line rather than a bare path,
    because WHICH graph a view was generated for is the first thing a reader needs
    and cannot be reconstructed from the path.
    """

    tool: str
    state: str
    detail: str = ""
    stale: tuple[str, ...] = ()
    blind: tuple[str, ...] = ()

    @property
    def quiet(self) -> bool:
        """True when this verdict prints nothing.

        Every quiet state other than OK/SKIP is quiet because another check owns
        its message — see :data:`NEVER_BUILT` and :data:`NOT_GENERATED`.
        """
        return self.state in (OK, SKIP, NEVER_BUILT, NOT_GENERATED)


def _short(fingerprint: str) -> str:
    """`498804246:1785949927017788379` -> `498804246:…8379`, or `?` when empty."""
    if not fingerprint:
        return "?"
    size, _, mtime = fingerprint.partition(":")
    return f"{size}:…{mtime[-_FP_TAIL:]}" if mtime else size


def check_views(repo_root: Path, spec: ToolSpec) -> ViewStatus:
    """Compare each declared derived view's recorded provenance against the graph.

    An equality, not an ordering: a view whose recorded `graph` fingerprint is not
    the graph's current fingerprint was generated from a graph that no longer
    exists. That is exact — it does not care which order a run wrote its outputs
    in, which is what sank the clock-based version (see the module docstring).
    """
    derived = [rel for rel in spec.artifacts if rel != spec.artifact]
    if not spec.artifact or not derived or not spec.stamp or not spec.applies_here():
        return ViewStatus(spec.name, SKIP)

    primary = repo_root / spec.artifact
    stamp = sync.read_stamp(repo_root, spec)
    if not primary.exists() or not stamp:
        # Either half alone is enough, and both mean the same thing here: there is
        # no build whose views could be out of date. Same reasoning as
        # `staleness._no_build_reason`, which this deliberately mirrors.
        return ViewStatus(spec.name, NEVER_BUILT, f"{spec.artifact} or its stamp is absent")

    recorded = sync.stamped_views(stamp)
    if recorded is None:
        return ViewStatus(
            spec.name,
            NOT_VERIFIABLE,
            # Covers BOTH ways `stamped_views` answers None — the key is absent
            # (a stamp written before #182) or present and corrupt (hand-edited,
            # half-written). The earlier wording said "predates view provenance",
            # which is a diagnosis rather than an observation and is simply wrong
            # for the second case. This states what was observed and what to run.
            f"{spec.stamp} carries no usable view provenance — "
            f"run `mise run kb-artifacts` to record it",
        )
    primary_fp = sync.artifact_fingerprint(primary)
    if not primary_fp:
        return ViewStatus(spec.name, NOT_VERIFIABLE, f"{spec.artifact} could not be read")

    return _verdict(spec.name, len(derived), _classify(repo_root, derived, recorded, primary_fp))


def _verdict(tool: str, declared: int, classified: tuple[list[str], list[str], int]) -> ViewStatus:
    """Turn the per-view split into one status. The ORDER of these branches is the design.

    STALE outranks NOT_VERIFIABLE: a view known to describe an earlier graph is a
    finding, and burying it under "some other view could not be aged" would let the
    weaker answer suppress the stronger. The blind list still rides along on the
    STALE status so it is reported rather than dropped.

    NOT_GENERATED comes last and only when NOTHING was compared, which is what
    stops the missing-view hand-off in `_classify` from becoming a false pass: with
    no views on disk there is nothing for OK to be true of.
    """
    stale, blind, present = classified
    if stale:
        return ViewStatus(
            tool,
            STALE,
            f"{len(stale)} of {present} present view(s) describe an earlier graph",
            tuple(stale),
            tuple(blind),
        )
    if blind:
        return ViewStatus(
            tool, NOT_VERIFIABLE, f"{len(blind)} view(s) of unknown provenance", (), tuple(blind)
        )
    if not present:
        return ViewStatus(tool, NOT_GENERATED, f"none of {declared} declared view(s) exist")
    return ViewStatus(tool, OK)


def _classify(
    repo_root: Path,
    derived: list[str],
    recorded: dict[str, dict[str, str]],
    primary_fp: str,
) -> tuple[list[str], list[str], int]:
    """Split the present views into `(stale, blind, present_count)`.

    A view that does not exist is counted in NEITHER list and not in `present`:
    `sync._check_artifact_identity` already reports it as DRIFT `(missing)`, with
    the same remedy, in the same command's output. Restating it here would put two
    loud lines on one condition, which is how a reader learns to skim past both.
    The count is what stops that hand-off becoming a false pass — see
    :data:`NOT_GENERATED`.
    """
    stale: list[str] = []
    blind: list[str] = []
    present = 0
    for rel in derived:
        if not (repo_root / rel).exists():
            continue
        present += 1
        generated_for = recorded.get(rel, {}).get("graph", "")
        if not generated_for:
            blind.append(f"{rel}  (never observed being generated — provenance unknown)")
        elif generated_for != primary_fp:
            stale.append(
                f"{rel}  (generated for graph {_short(generated_for)}; "
                f"on disk now is {_short(primary_fp)})"
            )
    return stale, blind, present


def report(statuses: Iterable[ViewStatus]) -> None:
    """Print the non-clean verdicts under `[views]`. Silent when everything agrees.

    STALE and NOT_VERIFIABLE print separately for the same reason `sync` keeps
    DRIFT and NOT-CHECKED apart: "this view describes an older graph" and "we could
    not ask" are different answers, and one header over both lets the weaker borrow
    the stronger's weight — or lets a real finding be dismissed as a flaky probe.

    The remedy is `mise run kb-artifacts` and NOT `kb-build`, deliberately.
    `artifacts.generate` has one caller and a rebuild does not reach it, so
    printing the build-stamp check's "or rebuild" here would hand the reader an
    instruction that cannot repair what it is reporting.
    """
    for status in statuses:
        if status.quiet:
            continue
        if status.stale:
            print(
                f"{_HEADER} derived views describe an earlier graph — run `mise run kb-artifacts`:"
            )
            for line in status.stale:
                print(f"{_HEADER}   {line}")
        if status.blind:
            print(f"{_HEADER} NOT CHECKED for staleness (this is not a pass):")
            for line in status.blind:
                print(f"{_HEADER}   {line}")
        elif status.state == NOT_VERIFIABLE and not status.stale:
            print(f"{_HEADER} NOT CHECKED for staleness (this is not a pass): {status.detail}")
