# Copyright (c) 2026 Raymond Manaloto
"""The graph-size gate: is `graph.json` still small enough for graphify to READ?

`kb_setup.insights` has computed this number for a while and only printed it.
Printing is not a gate — the figure sat in a report nobody runs on the way to a
merge, while the graph climbed to roughly three quarters of its ceiling. This
module is the same measurement with a verdict attached, and Ray's ruling
(2026-08-17) is to gate it now, at the ceiling this repo currently sets.

WHOSE NUMBER IS WHOSE, because that distinction is what makes the verdict
readable:

* **512 MiB is graphify's**, the stock `_MAX_GRAPH_FILE_BYTES` in its
  `security.py`. Above it, graphify REFUSES to read the file — the corpus stops
  being queryable, which is why this is a hard ceiling and not a style rule.
* **1 GiB is OURS**, set by `GRAPHIFY_MAX_GRAPH_BYTES` in `mise.toml`, and
  `mise.toml` says plainly why that raise is a ratchet rather than a fix: the
  aggregate is inflated by a duplicated `repo::` prefix (#120), and the durable
  answer is federation across per-source graphs (#130). Both issues are still
  open.
* **The 80% warning line is ours too**, and it is the only number here that was
  chosen rather than inherited. It exists because a gate that fires only AT the
  ceiling fires when the graph is already unreadable, which forces the decision
  at the worst possible moment. 80% of 1 GiB leaves roughly 215 MiB of headroom
  — more than the last two ingestion rounds added together — so it should
  arrive as a prompt to federate, not as an emergency.

WHAT HAPPENS AT THE CEILING, said in code rather than left to a reader: the gate
FAILS. It does not fail at the warning line. The cap's job at 80% is to force the
trimming/federation decision; its job at 100% is to stop a merge that would leave
the corpus unqueryable for everyone who consumes it.

The effective ceiling is read from **graphify's own resolver**, not re-parsed
here. Its suffix semantics are a trap worth not re-implementing: `GB` means
**GiB** (1024³) and `MB` means MiB, so a hand-written parser that reads them as
powers of ten agrees on the string and disagrees on the number by 7%.
"""

from __future__ import annotations

from pathlib import Path

import msgspec

from kb_setup import events
from kb_setup.result import Rc

#: Fraction of the effective ceiling above which the gate WARNS but still passes.
#: Ours, chosen — see the module docstring.
WARN_AT = 0.80

_GRAPH = "graph.json"
#: Written by `kb-build`, recording the graphify version that ACTUALLY RAN. Read
#: here only for its EXISTENCE, as evidence that this machine has ever built —
#: which is what separates "nothing to gate" from "the artifact went missing".
_STAMP = ".currency-stamp.json"
_MIB = 1024 * 1024


class SizeVerdict(msgspec.Struct, frozen=True):
    """One measurement of `graph.json` against the ceiling that governs it."""

    state: str
    size_bytes: int
    cap_bytes: int
    note: str

    @property
    def ratio(self) -> float:
        """Fraction of the ceiling consumed, or 0.0 for an absent cap."""
        return self.size_bytes / self.cap_bytes if self.cap_bytes else 0.0

    @property
    def headroom_bytes(self) -> int:
        """Bytes still available before graphify refuses to read the file."""
        return max(self.cap_bytes - self.size_bytes, 0)


def effective_cap_bytes() -> int:
    """Return the cap graphify will ACTUALLY apply, resolved by graphify itself.

    Imported inside the function rather than at module scope so this module stays
    importable — and its tests runnable — on a machine where graphify is not
    installed. The name is private to graphify, which is a real risk and the
    lesser one: the alternative is a second parser for a suffix convention where
    `GB` means GiB, and a shadow implementation that disagrees by 7% would report
    headroom this repo does not have. `test_the_gate_reads_graphifys_own_cap`
    fails loudly if the name moves, which is the trade being made explicit.
    """
    from graphify import security

    # The SLF001 suppression for this line lives in the ONE root `pyproject.toml`
    # as a per-file-ignore, never inline — `do-not.md` #9, enforced by the
    # `no_lint_skip` hk step. That step caught an inline suppression here and then
    # caught this comment NAMING one, because it is a substring scan: the token
    # cannot appear in this file at all, not even while explaining its absence.
    # Suppressions are reviewable precisely because they are all in one place.
    return security._max_graph_file_bytes()


def measure(repo_root: Path) -> SizeVerdict:
    """Measure the built graph against the effective ceiling.

    A `stat`, never a read: this must stay cheap enough to run on every gate
    invocation against a file measured in hundreds of megabytes.

    An ABSENT graph is never `ok`, and it is two different states rather than
    one — `missing` when this machine's build stamp says a graph should be here,
    `unbuilt` when nothing has ever been built. See `main` for why they carry
    different exit codes; the short version is that only one of them means the
    gate could not ask its question.
    """
    out = repo_root / "graphify-out"
    graph = out / _GRAPH
    cap = effective_cap_bytes()
    if not graph.is_file():
        # TWO states, not one, and collapsing them is what a cold lane flagged:
        # "the gate can pass on an absent graph". It can, and on a machine that
        # has never built there is genuinely nothing to gate — failing there
        # would make a fresh clone unshippable and train people to skip this.
        #
        # But a machine that HAS built and no longer has the artifact is an
        # anomaly, and reporting that as a pass is the "gate that never asked the
        # question" this repo refuses elsewhere. The build stamp is the existing
        # artifact that tells them apart: `kb-build` writes it, so its presence
        # beside a missing graph means the graph was deleted or a build was
        # interrupted. That case is `Rc.NOT_RUN`, on `skill_lint`'s precedent.
        stamped = (out / _STAMP).is_file()
        return SizeVerdict(
            state="missing" if stamped else "unbuilt",
            size_bytes=0,
            cap_bytes=cap,
            note=(
                f"{_STAMP} says this machine has built, but {_GRAPH} is gone — "
                "the gate could not ask its question. Rebuild with `mise run kb-build`."
                if stamped
                else f"no graphify-out/{_GRAPH} here yet — run `mise run kb-build`. "
                "Nothing has been built on this machine, so there is nothing to gate."
            ),
        )
    size = graph.stat().st_size
    verdict = SizeVerdict(state="ok", size_bytes=size, cap_bytes=cap, note="")
    if size > cap:
        return msgspec.structs.replace(
            verdict,
            state="over",
            note=(
                "graphify REFUSES to read a graph this large, so the corpus is "
                "unqueryable for every consumer. Federate across per-source graphs "
                "(#130) or fix the duplicated `repo::` prefix (#120); raising "
                "GRAPHIFY_MAX_GRAPH_BYTES again is a ratchet, not a fix."
            ),
        )
    if verdict.ratio >= WARN_AT:
        return msgspec.structs.replace(
            verdict,
            state="near",
            note=(
                f"past {WARN_AT:.0%} of the ceiling. This is the prompt to federate "
                "(#130) or de-duplicate (#120) while there is still headroom — at "
                "the ceiling itself the decision is forced with none."
            ),
        )
    return verdict


def render(verdict: SizeVerdict) -> str:
    """One line of size, ceiling, headroom and verdict.

    Headroom is printed on EVERY run, including the passing ones, because the
    number that matters is the trend: a gate first heard from at the ceiling has
    told nobody anything they could act on.
    """
    return (
        f"graph size: {verdict.size_bytes / _MIB:,.1f} MiB of "
        f"{verdict.cap_bytes / _MIB:,.0f} MiB ({verdict.ratio:.0%}), "
        f"{verdict.headroom_bytes / _MIB:,.1f} MiB headroom — {verdict.state.upper()}"
        + (f"\n  {verdict.note}" if verdict.note else "")
    )


def main(repo_root: Path) -> int:
    """CLI boundary: 0 when the graph is within its ceiling, 1 when it is not.

    Three non-OK states, three different exit codes, because they are three
    different facts:

    * `over` — checked, and the graph is past the ceiling. **1.**
    * `missing` — this machine has built (the stamp is there) and the graph is
      not. The gate could not ask its question, which by
      `probes-need-a-control-arm.md` is not a pass. **`Rc.NOT_RUN`**, the same
      code `skill_lint` returns when its glob matches nothing.
    * `unbuilt` — nothing has ever been built here, so there is nothing to gate.
      **0**, deliberately: failing every gate run on a fresh clone would make the
      repo unshippable until a multi-minute build ran, and would train people to
      skip this gate. The state is NAMED rather than rendered `OK`, so a reader
      can tell "checked and fine" from "nothing to check".

    The middle state is the one a cold lane asked for, and it is the whole of
    what that finding was right about: "the gate can pass on an absent graph" is
    true, and only harmless when the absence means the work never happened.
    """
    verdict = measure(repo_root)
    events.say("graph.size", render(verdict))
    if verdict.state == "over":
        return int(Rc.FINDINGS)
    return int(Rc.NOT_RUN) if verdict.state == "missing" else int(Rc.OK)
