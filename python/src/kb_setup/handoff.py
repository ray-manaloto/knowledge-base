"""Verify a handoff's checkable claims — `mise run kb-handoff-check`.

FIVE CHECKS, AND THEY ARE NOT ALL STATIC. Four ask the filesystem: do the cited
paths exist (including whether a citation's EXTENSION is mistyped, #154), does
anything match a citation whose middle is ELIDED (`review-8a46d08…-cold.md`,
#148), is every `file:line` real, is every named task declared in `mise.toml`.
The fifth does not: a **gate claim** — `` `mise run lint` **rc=0** `` — is checked
against `.agent/kb/gates/gates-<sha>.json`, the record `mise run kb-gates` writes
(#147). That record is a machine-local artifact on disk rather than a fact about
the tree, which is why a claim can come back UNVERIFIABLE here and never can for
a path. This paragraph said "static claims" and enumerated only the first three
until #157; `mise.toml` and `.claude/skills/clear-prep/SKILL.md` had already been
corrected, so the source was the stale one — the worse direction. The count has
now gone stale twice, which is why it is spelled out rather than left as "the
checks below".

WHAT THIS REPLACES. `/clear-prep` step 6 asks the agent to self-verify the
handoff it has just written, at the end of a long session, from memory. That is
verification performed by the same context that produced the thing being
verified, and it has already failed in exactly the way that predicts — a line
number read off a `sed` window by eye, written as `:1836` when the real line was
`:1830`, which then propagated into three files before anyone noticed (#143).

STRICT ABOUT WRONGNESS, ADVISORY ABOUT AMBIGUITY. A broken path, a `file:line`
past the end of its file, or a task this repo does not declare exits 1. A bare
filename matching several files exits 0 — it is reported, because a reader may
want to disambiguate it, but it is not a defect and treating it as one is how a
checker teaches people to ignore it. A malformed request (a target that is not
there) exits 2, the same split `kb_setup.skill_eval` draws.

TWO CONSUMERS, ONE POLICY. `mise run kb-handoff-check` checks whatever handoff
you point it at; `mise run kb-ship` checks the NEWEST one, and only when that
handoff records the current branch, refusing the push if it is broken
(:func:`check_for_branch`, #149).
The strict/advisory split is written once, here, so the gate cannot disagree
with the command you would run to reproduce it. What the ship path adds is a
third outcome the CLI has no use for — SKIPPED, when nothing on disk describes
this branch — and skipping is what makes the gate safe rather than lenient.

THE COMPOSER OWNS NO PARSING. Every regex lives in `kb_setup.citations` and
every filesystem question in `kb_setup.resolve`; this module decides what a
verdict MEANS for a handoff. Keeping it that way is what lets the next checker —
a goal document, a research report — reuse the primitives instead of growing a
second copy (#143).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kb_setup import citations, gates, resolve, review

#: The checks a `` `path` (absent) `` marker can be written on. A gate claim
#: cannot, which is why `render` scopes its hint to these rather than to any
#: FAIL.
_PATH_CHECKS: frozenset[str] = frozenset({"path", "file-line", "elided"})


class Verdict(Enum):
    """Only FAIL fails the run; AMBIGUOUS and UNVERIFIABLE are reported at exit 0."""

    OK = "OK"
    AMBIGUOUS = "AMBIG"
    UNVERIFIABLE = "UNVER"
    FAIL = "FAIL"


#: How a resolution maps onto a verdict. Written as a table rather than a chain
#: of branches so that adding a state cannot silently default to FAIL — which is
#: the direction that produces false positives, the one failure mode #145 calls
#: fatal to the checker's credibility.
_VERDICT_OF: dict[resolve.State, Verdict] = {
    resolve.State.RESOLVED: Verdict.OK,
    resolve.State.AMBIGUOUS: Verdict.AMBIGUOUS,
    resolve.State.UNVERIFIABLE: Verdict.UNVERIFIABLE,
    resolve.State.MISSING: Verdict.FAIL,
}


@dataclass(frozen=True)
class Finding:
    """One checked claim.

    Carries all three things a reader needs to act without investigating: what
    was claimed, where in the handoff it was claimed, and what was found
    instead.
    """

    check: str
    verdict: Verdict
    claim: str
    line: int
    detail: str


def check(repo_root: Path, text: str) -> list[Finding]:
    """Every checkable claim in ``text``, checked against ``repo_root``.

    Paths, mistyped extensions, `file:line` references and task names are checked
    against the FILESYSTEM under ``repo_root``. Gate claims are not: they are
    checked against the record `mise run kb-gates` wrote under
    `.agent/kb/gates/`, which is machine-local and may simply be absent — hence
    UNVERIFIABLE, a verdict no path check can produce (#147, #157).

    The authored-tree index is built ONCE here and threaded through every
    resolution: a handoff carries tens of citations, and rebuilding the walk per
    citation is the difference between one pass over the tree and one per claim.
    """
    index = resolve.build_index(repo_root)
    # Read ONCE and threaded, for the same reason as ``index``: both the task
    # check and the gate check ask which tasks this repo declares, and letting
    # each parse `mise.toml` for itself is the drift this function's contract
    # already rules out for the tree walk. (Standards lane.)
    declared = resolve.declared_tasks(repo_root)
    findings = [_check_path(repo_root, c, index) for c in citations.path_citations(text)]
    findings.extend(_check_elided(repo_root, c, index) for c in citations.elided_citations(text))
    findings.extend(_check_extension_typos(repo_root, text, index))
    findings.extend(_check_line_ref(repo_root, c, index) for c in citations.line_citations(text))
    findings.extend(_check_tasks(text, declared))
    findings.extend(_check_gate_claims(repo_root, text, declared))
    return findings


def _check_path(repo_root: Path, cite: citations.PathCitation, index: resolve.Index) -> Finding:
    got = resolve.resolve_path(repo_root, cite.text, index)
    if cite.marked_absent:
        return _check_absent_marker("path", cite.text, cite.line, got)
    return Finding("path", _VERDICT_OF[got.state], cite.text, cite.line, got.detail)


def _check_elided(repo_root: Path, cite: citations.ElidedCitation, index: resolve.Index) -> Finding:
    """Adjudicate a citation whose middle is abbreviated — `review-8a46d08…-cold.md`.

    THE CHECK #148 IS ABOUT. A handoff names the reports its round produced, and
    it names many of them this way. Control-armed on 2026-08-05, the hole was
    total rather than partial — a concrete citation of a report that never existed
    came back FAIL, while the same citation with its sha elided produced no
    citation at all. So "the cold lane ran at a commit nothing was ever written
    for" was a sentence a handoff could make and pass.

    THE COUNT, WITH ITS CONDITION, because the first version of this paragraph
    carried one without. It claimed "21 report citations carry an elision", which
    was a PRE-IMPLEMENTATION count of report-directory tokens *including* the
    brace forms the extractor then excluded — a number invalidated by the very
    commit that wrote it, which `probes-need-a-control-arm.md` rule 6 warns reads
    as verified forever. Re-derived, the extractor returned **18**; normalising a
    leading elision then admitted 3 more, so it returns **21** over the 37 files
    in `.agent/plans/` today.

    That the wrong number and the right one coincide is a coincidence of two
    different quantities, and it is written down rather than tidied away: a
    reader seeing only the final figure would conclude the original claim had
    been right, when it counted a different set and was wrong about the set it
    named. `.agent/` is gitignored, so none of it is re-derivable on another
    clone; the durable facts are the mechanism and the control arm above.
    (Standards lane J3, spec lane F1.)

    WHY THE VARIANT IS STRIPPED FIRST. `kb_setup.review.report_path` removes a
    lane's `:variant` when it WRITES the report, so a handoff citing the lane as
    the receipt records it (`cold:codex`) names a file that cannot exist. Checking
    the written spelling literally would report a lane whose report is on disk as
    one that never ran. The repair is a spelling repair only — the repaired name
    still has to match something real, which
    `test_a_stripped_variant_does_not_excuse_a_lane_with_no_report` pins.

    The `(absent)` marker is adjudicated against the citation's OWN resolution,
    for the reason spelled out in :func:`_check_extension_typos`: routing a marked
    citation through a different question is what made the marker unfalsifiable
    there. Here both directions are live — a marked citation that MATCHES is a
    FAIL — so the marker cannot be pasted beside a report to silence it.
    """
    got = resolve.resolve_elided(repo_root, review.canonical_lane_report(cite.text), index)
    if cite.marked_absent:
        return _check_absent_marker("elided", cite.text, cite.line, got)
    return Finding("elided", _VERDICT_OF[got.state], cite.text, cite.line, got.detail)


def _check_extension_typos(repo_root: Path, text: str, index: resolve.Index) -> list[Finding]:
    """Findings for tokens whose EXTENSION looks mistyped — #154.

    Most candidates produce nothing. `resolve_extension_typo` returns None for
    every token it cannot positively identify as a typo, and None means the
    token never becomes a finding at all rather than becoming a quiet one: the
    allowlist's silence is the behaviour being preserved, and an OK finding would
    inflate the OK count with tokens nothing actually checked.

    Reported under the `path` check name rather than a new one. That is not
    cosmetic — `_PATH_CHECKS` scopes `render`'s `(absent)` hint, and this is the
    finding whose reader is most likely to have cited the token on purpose (a
    handoff quoting a typo as an example), so it is exactly the moment the hint
    exists for.
    """
    found: list[Finding] = []
    for cand in citations.typo_candidates(text):
        if cand.marked_absent:
            # Adjudicated against the token's OWN resolution, exactly as
            # `_check_path` does — never against the typo verdict.
            #
            # Routing it through `resolve_extension_typo` instead made the marker
            # UNFALSIFIABLE here, which is the one thing it must never be. That
            # function has two exits, None and MISSING, and `_check_absent_marker`
            # maps MISSING to OK — so for a marked candidate the entire input
            # space produced "no finding" or "OK" and no input could make the
            # marker fail. The comment that stood here argued the both-directions
            # rule was intact because "a token that RESOLVES never reaches this
            # function". True, and it was the defect: the token silently resolving
            # is precisely the case the marker is supposed to FAIL on.
            #
            # It mattered beyond the abstraction. `render` prints "the marker is
            # checked both ways, so it cannot hide a real miss" on any FAIL whose
            # check is in `_PATH_CHECKS`, and these are filed under `path` on
            # purpose — so the tool was printing that promise next to the one
            # check for which it was false. (Silent-failure lane, F1.)
            got = resolve.resolve_path(repo_root, cand.text, index)
            found.append(_check_absent_marker("path", cand.text, cand.line, got))
            continue
        got = resolve.resolve_extension_typo(repo_root, cand.text, cand.repairs, index)
        if got is None:
            continue
        found.append(Finding("path", _VERDICT_OF[got.state], cand.text, cand.line, got.detail))
    return found


def _check_absent_marker(
    check_name: str, claim: str, line: int, got: resolve.Resolution
) -> Finding:
    """Adjudicate a citation written as `` `path` (absent) ``.

    Checked in BOTH directions on purpose. A marker that could only suppress
    findings would be a mute button an author could paste beside anything;
    because a marked citation that RESOLVES is itself a failure, the marker can
    only be applied where the path really is missing — so it cannot hide a real
    miss. (This answers the case #145's acceptance criteria left open: a path
    cited precisely because it does not exist, such as the
    `docs/agents/issue-tracker.md` an external skill hardcodes and will not find.)
    """
    if got.state is resolve.State.MISSING:
        return Finding(check_name, Verdict.OK, claim, line, "marked `(absent)`, and absent")
    if got.state is resolve.State.UNVERIFIABLE:
        # We could not resolve it either way, so we cannot confirm the marker.
        # Reporting OK here would claim we had checked something we had not.
        return Finding(
            check_name,
            Verdict.UNVERIFIABLE,
            claim,
            line,
            f"marked `(absent)`, and unverifiable either way — {got.detail}",
        )
    # RESOLVED or AMBIGUOUS. AMBIGUOUS is the one that used to slip through as
    # "confirmed absent": several real files match, which is the opposite of
    # absent, and letting it pass turned the marker into the mute button the
    # both-directions rule exists to prevent.
    return Finding(
        check_name,
        Verdict.FAIL,
        claim,
        line,
        f"marked `(absent)` but it resolves — {got.detail}",
    )


def _check_line_ref(repo_root: Path, cite: citations.LineCitation, index: resolve.Index) -> Finding:
    got = resolve.resolve_path(repo_root, cite.path, index)
    claim = f"{cite.path}:{cite.start}" + (f"-{cite.end}" if cite.end != cite.start else "")
    if cite.start > cite.end:
        # Decidable without opening anything, and it is this tool's own subject:
        # `:20-10` is a transposed-digit typo. Both ends can sit inside the file,
        # so bounds checks alone accept the one arrangement that cannot describe
        # a real range.
        return Finding(
            "file-line",
            Verdict.FAIL,
            claim,
            cite.line,
            f"reversed line range — {cite.start} > {cite.end}",
        )
    if cite.marked_absent:
        return _check_absent_marker("file-line", claim, cite.line, got)
    if got.state is not resolve.State.RESOLVED or got.match is None:
        # The path could not be pinned down, so its line number cannot be
        # either. The path's own verdict carries through unchanged — inventing a
        # stricter one here would report one mistake as two different defects.
        return Finding("file-line", _VERDICT_OF[got.state], claim, cite.line, got.detail)
    total = resolve.line_count(got.match)
    if total is None:
        return Finding(
            "file-line",
            Verdict.AMBIGUOUS,
            claim,
            cite.line,
            f"could not read {got.detail} to count its lines",
        )
    if cite.start < 1 or cite.end > total:
        return Finding(
            "file-line",
            Verdict.FAIL,
            claim,
            cite.line,
            f"{got.detail} has {total} lines",
        )
    return Finding("file-line", Verdict.OK, claim, cite.line, f"{got.detail} has {total} lines")


def _check_tasks(text: str, declared: frozenset[str]) -> list[Finding]:
    findings: list[Finding] = []
    for cite in citations.task_citations(text):
        ok = cite.name in declared
        findings.append(
            Finding(
                "task",
                Verdict.OK if ok else Verdict.FAIL,
                cite.name,
                cite.line,
                "declared in mise.toml"
                if ok
                else f"not declared in mise.toml ({len(declared)} tasks declared)",
            )
        )
    return findings


def _check_gate_claims(repo_root: Path, text: str, declared: frozenset[str]) -> list[Finding]:
    """Every gate claim in ``text``, checked against the record #146 writes.

    Only claims naming a task THIS repo declares are checked. The parser cannot
    know which tokens are gates, so it hands back everything that preceded an
    `rc=` — `` `timeout 60 x` returns rc=127 `` yields a claim about `returns` —
    and reporting those would bury the real findings in prose.
    """
    return [
        _check_gate_claim(repo_root, c) for c in citations.gate_claims(text) if c.task in declared
    ]


def _gate_finding(claim: citations.GateClaim, verdict: Verdict, detail: str) -> Finding:
    return Finding("gate", verdict, f"{claim.task} rc={claim.rc}", claim.line, detail)


def _check_gate_claim(repo_root: Path, claim: citations.GateClaim) -> Finding:
    """Adjudicate one gate claim.

    THE SPLIT THAT MATTERS is FAIL versus UNVERIFIABLE, and it is not a style
    choice. FAIL means the record CONTRADICTS the claim. UNVERIFIABLE means no
    record can speak to it — there is none at that commit, none for that gate,
    or the claim named no commit to look one up by. `.agent/` is machine-local
    and dies with the clone, so anyone auditing someone else's handoff has no
    records at all; failing there would make the checker unusable in exactly the
    situation it was built for, and passing there would make a missing record
    read as a green one.
    """
    if not claim.shas:
        return _gate_finding(
            claim,
            Verdict.UNVERIFIABLE,
            "names no commit — put the sha in the same bullet as the claim "
            "(a sha in a neighbouring paragraph is not inherited, and a branch "
            "name is not a commit), or nothing can look the record up",
        )
    if len(claim.shas) > 1:
        return _gate_finding(
            claim,
            Verdict.AMBIGUOUS,
            f"its block names {len(claim.shas)} commits ({', '.join(claim.shas)}) — "
            f"which one did the gates run at?",
        )
    record, why = gates.find_record(repo_root, claim.sha)
    if record is None:
        return _gate_finding(claim, Verdict.UNVERIFIABLE, why)
    return _judge(claim, record)


def _judge(claim: citations.GateClaim, record: gates.Record) -> Finding:
    """Compare a claim to the rows that speak for it.

    A claim about the RUNNER (`mise run kb-gates`) is a claim about every row;
    a claim about one gate is a claim about its row. Both then face the same
    commit-binding and cleanliness questions, which is why the rows are chosen
    first and the checks that follow are written once.

    ``runner`` is decided HERE and passed down, rather than each step asking
    `claim.task == RUNNER_TASK` for itself. Two sites asking the same question
    of the same value is how the two halves drift apart. (Standards lane.)
    """
    runner = claim.task == gates.RUNNER_TASK
    at = record.sha[: gates.SHA_ABBREV]
    if runner:
        rows = list(record.gates)
        if not rows:
            return _gate_finding(claim, Verdict.UNVERIFIABLE, f"the record at {at} covers no gates")
    else:
        matched = record.rows_for(claim.task)
        if not matched:
            covered = ", ".join(r.task for r in record.gates) or "nothing"
            return _gate_finding(
                claim,
                Verdict.UNVERIFIABLE,
                f"the record at {at} covers {covered} — not {claim.task}",
            )
        if len(matched) > 1:
            # `kb-gates -- lint lint` is accepted, so one record really can hold
            # two rows for one task with different results. Picking the first
            # was silent, and silently picking the one that AGREES with the
            # claim is the failure this whole module exists to remove — so the
            # disagreement goes to the reader instead. (Cold lane.)
            said = ", ".join("rc=" + ("none" if r.rc is None else str(r.rc)) for r in matched)
            return _gate_finding(
                claim,
                Verdict.AMBIGUOUS,
                f"the record at {at} has {len(matched)} rows for {claim.task} ({said}) — "
                f"which one is the claim about?",
            )
        rows = list(matched)
    return _judge_rows(claim, record, rows, runner=runner)


def _judge_rows(
    claim: citations.GateClaim,
    record: gates.Record,
    rows: list[gates.RecordedGate],
    *,
    runner: bool,
) -> Finding:
    """The questions every claim faces once the rows that speak for it are known.

    Written once rather than per claim shape: a gate claim and a runner claim
    differ only in WHICH rows answer for them and in how their exit code is
    compared, and duplicating the commit-binding checks across the two is how
    one of them ends up hardened and the other not.
    """
    # Binding BEFORE the exit code, deliberately. A row that ran at another
    # commit has an exit code about code this one never contained, so reporting
    # "rc=1, not rc=0" would name the wrong defect and send the reader to fix a
    # gate that is fine.
    sha = claim.sha
    drifted = [r for r in rows if r.sha and not r.sha.lower().startswith(sha.lower())]
    if drifted:
        ran_at = ", ".join(sorted({r.sha[: gates.SHA_ABBREV] for r in drifted if r.sha}))
        return _gate_finding(
            claim,
            Verdict.FAIL,
            f"recorded against {ran_at}, not {sha} — HEAD moved during the run, so "
            f"that exit code is about code {sha} never contained "
            f"({', '.join(r.task for r in drifted)})",
        )

    mismatch = _rc_mismatch(claim, rows, record, runner=runner)
    if mismatch is not None:
        return _gate_finding(claim, Verdict.FAIL, mismatch)

    # `not r.sha`, not `r.sha is None`. `_parse` now normalises an empty row sha
    # to None, but this is the point of USE and it must not depend on that: an
    # empty string is FALSY, so the drift check above skips it, and it is not
    # None, so an identity test skipped it too — a row bound to no commit passed
    # in BOTH directions and confirmed a claim about any commit at all. Fixing
    # only the parser would leave the hole one constructor away. (Cold lane.)
    unbound = [r.task for r in rows if r.rc is not None and not r.sha]
    if unbound:
        return _gate_finding(
            claim,
            Verdict.UNVERIFIABLE,
            f"recorded, but bound to no commit — git was unreadable when "
            f"{', '.join(unbound)} ran, so nothing ties that result to {sha}",
        )

    # Only rows that RAN are asked about the tree. A row padded as "not run"
    # carries `dirty: null` because there was nothing to ask about, and reading
    # that as "could not tell whether the tree was clean" describes a gate that
    # never happened — true of the field, false about the world. Reachable on
    # any `--stop` record, which the ship path writes every time.
    ran = [r for r in rows if r.rc is not None]
    dirty = [r.task for r in ran if r.dirty]
    if dirty:
        return _gate_finding(
            claim,
            Verdict.AMBIGUOUS,
            f"recorded at {sha}, but the tree carried uncommitted changes when "
            f"{', '.join(dirty)} ran — the result describes that tree, not {sha}",
        )
    unknown = [r.task for r in ran if r.dirty is None]
    if unknown:
        return _gate_finding(
            claim,
            Verdict.AMBIGUOUS,
            f"recorded at {sha}, but whether the tree was clean when "
            f"{', '.join(unknown)} ran could not be read",
        )
    return _gate_finding(claim, Verdict.OK, f"recorded at {sha} in {record.path.name}")


def _rc_mismatch(
    claim: citations.GateClaim,
    rows: list[gates.RecordedGate],
    record: gates.Record,
    *,
    runner: bool,
) -> str | None:
    """Why the record contradicts ``claim``'s exit code, or None if it agrees.

    For a single gate the comparison is the exit code itself. For the runner it
    is `kb-gates`' own contract — 0 when every gate passed, non-zero otherwise —
    so a claim of rc=0 is checked against "nothing failed" rather than against a
    row that does not exist. A row with no result counts as not passed, which is
    what makes a `--stop` record unable to vouch for a green claim.
    """
    if runner:
        _, unpassed = record.summarise()
        # `kb-gates` exits 0 when every gate passed and 1 when one did not, so
        # the record implies ONE exit code and it is compared, not merely tested
        # for zeroness. The old form asked `(claim.rc == 0) == (unpassed == 0)`,
        # which made every non-zero claim equivalent — and 2 is not "a gate
        # failed", it is `kb-gates` REFUSING to run, which writes no record at
        # all. So a record confirming `rc=2` was confirming a run that, by the
        # runner's own contract, never happened. (Cold lane.)
        expected = 1 if unpassed else 0
        if claim.rc == expected:
            return None
        names = ", ".join(r.task for r in rows if r.rc != 0)
        if claim.rc not in {0, 1}:
            return (
                f"claims rc={claim.rc}, but {gates.RUNNER_TASK} exits only 0 or 1 once it "
                f"has run — {claim.rc} is a refused request, and a refusal writes no record"
            )
        return (
            f"claims rc={claim.rc}, but the record has {unpassed} gate(s) that "
            f"did not pass ({names})"
            if unpassed
            else f"claims rc={claim.rc}, but every gate in the record passed"
        )
    (row,) = rows
    if row.rc is None:
        # FAIL, not UNVERIFIABLE, and the choice is deliberate — no criterion
        # adjudicated it until a review lane asked, so it is written down here.
        # A `rc: null` row LOOKS like silence, which would argue for
        # UNVERIFIABLE. It is not: a record is a COMPLETE account of one run at
        # one commit (unreached gates are padded, never omitted) and it
        # OVERWRITES any earlier record for that commit, so it positively
        # asserts that the gate produced no result there. A claim that it exited
        # 0 is contradicted, not merely unsupported — and reading it as silence
        # would let the one artifact that knows better stay quiet at exit 0
        # about a green claim nothing backs. #146's `all_passed` and
        # `Record.summarise` both count a null as not-passed; this is the same
        # rule reaching the reader. (Spec lane, criterion 9.)
        return "no result was recorded for it — it never ran to completion, which is not a pass"
    if row.rc != claim.rc:
        return f"the record says rc={row.rc}"
    return None


def render(findings: list[Finding], *, source: str) -> str:
    """The report: every non-OK finding, then the counts.

    OK findings are counted but not listed. A report that prints one line per
    verified citation buries its few real findings in a few hundred passes,
    which is a different way of not being read.
    """
    counts = {v: sum(1 for f in findings if f.verdict is v) for v in Verdict}
    lines = [
        f"{f.verdict.value:<5} {f.check:<9} {source}:{f.line}  `{f.claim}` — {f.detail}"
        for f in findings
        if f.verdict is not Verdict.OK
    ]
    if not lines:
        lines.append(f"no broken citations in {source}")
    elif any(f.verdict is Verdict.FAIL and f.check in _PATH_CHECKS for f in findings):
        # Scoped to the checks the marker can actually be written on. The arm
        # used to fire on ANY failure, so once gate claims could fail, a run
        # whose only defect was `lint rc=0` advised the reader to write
        # `` `path` (absent) `` — advice that cannot be acted on, attached to a
        # finding it has nothing to do with. Its own comment claims the report
        # "teaches it at exactly that moment"; that moment had stopped being
        # this one. (Standards lane.)
        # The marker is useless if nobody discovers it, and the moment someone
        # needs it is the moment they are staring at a path they cited on
        # purpose. So the report teaches it at exactly that moment.
        lines.append("")
        lines.append(
            "  (a path cited BECAUSE it is absent: write `` `path` (absent) `` — "
            "the marker is checked both ways, so it cannot hide a real miss)"
        )
    lines.append("")
    # Every verdict appears in the count, including the two that do not fail.
    # A state absent from the summary is one a reader cannot tell from zero —
    # the same "could not check rendered as green" mistake these states exist
    # to prevent, arriving in the report instead of in the logic.
    lines.append(
        f"{counts[Verdict.OK]} OK, {counts[Verdict.AMBIGUOUS]} ambiguous, "
        f"{counts[Verdict.UNVERIFIABLE]} unverifiable, {counts[Verdict.FAIL]} broken"
        "   (only broken exits 1)"
    )
    return "\n".join(lines)


def handoffs(repo_root: Path) -> list[Path]:
    """Every `.agent/plans/session-*.md`, NEWEST FIRST.

    Ordered by mtime rather than by filename. The names sort
    `session-2026-08-03-d.md` BEFORE `session-2026-08-03.md` (`-` < `.` in
    ASCII), so a lexicographic pick hands back the older of the two — and
    `.agent/` is gitignored and machine-local, so mtime here is authoring time
    rather than checkout time.
    """
    return sorted(
        (repo_root / ".agent" / "plans").glob("session-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def newest_handoff(repo_root: Path) -> Path | None:
    """The most recently modified `.agent/plans/session-*.md`, or None."""
    found = handoffs(repo_root)
    return found[0] if found else None


def recorded_branch(text: str) -> str | None:
    """The branch this handoff says it is about, or None if it names none.

    The FIRST branch its lead mentions. First rather than "the only one" because
    a real handoff row reads ``| branch | `main` (the round's branch
    `feat/settled-claims` is merged) |`` — the coordinates come first and the
    commentary follows, which is how these documents are written.

    None is a real answer and the common one for older handoffs: 6 of the 35 in
    `.agent/plans/` on 2026-08-04 record no branch in their lead at all. It maps
    to a reported SKIP, never to a match — see :func:`check_for_branch`.
    Handoffs written from here on carry it by construction, because
    `mise run kb-session-state` emits `- **branch**: `<name>`` (#144).
    """
    mentions = citations.branch_mentions(citations.document_lead(text))
    return mentions[0].name if mentions else None


class Coverage(Enum):
    """Whether a handoff SPOKE for the current branch, and what it said.

    Three states rather than a bool, for the reason every other tri-state in
    this package exists: SKIPPED is not OK. A gate that had nothing to check and
    a gate that checked and found nothing are different sentences, and rendering
    the first as the second is the false green `kb-handoff-check` was built to
    remove — arriving in the gate that consumes it.
    """

    OK = "OK"
    BROKEN = "BROKEN"
    SKIPPED = "SKIP"


@dataclass(frozen=True)
class BranchHandoff:
    """What the handoff for one branch had to say.

    ``summary`` is always non-empty and always safe to print on its own — it is
    what `kb-ship` shows, and criterion 2 requires the skip case to be REPORTED
    rather than silent. ``source`` is the matched file's name, empty when
    nothing matched; ``findings`` is empty for the same reason, so a caller
    cannot accidentally report another branch's defects as this one's.
    """

    coverage: Coverage
    summary: str
    source: str = ""
    findings: tuple[Finding, ...] = ()


def _handoff_summary(name: str, branch: str, findings: list[Finding]) -> str:
    counts = {v: sum(1 for f in findings if f.verdict is v) for v in Verdict}
    advisory = counts[Verdict.AMBIGUOUS] + counts[Verdict.UNVERIFIABLE]
    tail = f" ({advisory} advisory — `mise run kb-handoff-check` for detail)" if advisory else ""
    return (
        f"`{name}` records branch `{branch}` — {counts[Verdict.FAIL]} broken, "
        f"{counts[Verdict.OK]} OK{tail}"
    )


def check_for_branch(repo_root: Path, branch: str | None) -> BranchHandoff:
    """Check the NEWEST handoff, and only if it records ``branch``.

    THE BRANCH MATCH IS THE POINT, not a nicety (#149). Measured on 2026-08-03:
    the newest handoff on disk pinned a commit six behind and asserted "no review
    receipt", because it described the session that STARTED the work rather than
    the one shipping it. Checking it would have blocked a healthy PR.

    NEWEST-ONLY, NOT "THE NEWEST THAT MATCHES". #149's acceptance criterion is
    worded the second way, and it was built that way first — scan every handoff
    newest-first and check the first one recording this branch. That reading is
    wrong, and measurably so. `.agent/plans/` is append-only and its handoffs
    cite paths, so an old handoff rots as unrelated commits delete what it named:
    over this repo's 35 handoffs, **8 of the 21 branches they record** come back
    BROKEN under the scan, every one of them on a handoff 1-7 days stale. Under
    newest-only all 8 SKIP. The scan does not remove the harm this ticket names —
    a healthy ship refused over another session's staleness — it relocates it one
    file back, and it grows monotonically. The criterion was amended on #149 to
    match; see the comment there for the measurement.

    What newest-only gives up is real and small: a session that switches branches
    and comes back finds its own handoff masked by whatever was written since,
    and skips. A skip is the safe direction, and this one is also self-correcting
    — the next `/clear-prep` writes a newer handoff for the branch you are on.

    So the two failure directions are not symmetric, and this function is biased
    accordingly. A handoff wrongly MATCHED refuses a push over another session's
    defects. A handoff wrongly SKIPPED loses one advisory check and says so out
    loud. Everything unreadable therefore skips: no branch, no handoff, a handoff
    naming no branch, a file that cannot be read.

    Only FAIL refuses. AMBIGUOUS and UNVERIFIABLE are reported in the summary and
    left advisory, which is `kb_setup.handoff`'s own split (`main` exits 0 for
    both) rather than a second, stricter policy invented at the gate.
    """
    if not branch:
        # None means git could not be asked (#144) — not "no branch". Either way
        # there is nothing to match a handoff against.
        return BranchHandoff(
            Coverage.SKIPPED,
            "SKIP — the current branch could not be read, so no handoff can be matched to it",
        )

    newest = newest_handoff(repo_root)
    if newest is None:
        return BranchHandoff(
            Coverage.SKIPPED,
            f"SKIP — no handoff under .agent/plans/ to check branch `{branch}` against",
        )
    try:
        text = newest.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # Reported, not silent, and not a refusal: a handoff we cannot open tells
        # us nothing about the branch, which is the skip case.
        return BranchHandoff(
            Coverage.SKIPPED,
            f"SKIP — the newest handoff {newest.name} could not be read: {exc}",
        )

    recorded = recorded_branch(text)
    if recorded != branch:
        # NAME what it recorded. "No handoff matched" alone cannot be told from
        # "the check is broken", and this is the branch of the gate a reader
        # meets most often — `/clear-prep` writes the handoff AFTER the round,
        # so at ship time the newest one usually describes the previous session.
        return BranchHandoff(
            Coverage.SKIPPED,
            f"SKIP — the newest handoff {newest.name} records "
            f"{'`' + recorded + '`' if recorded else 'no branch'}, not `{branch}`",
        )

    findings = check(repo_root, text)
    broken = any(f.verdict is Verdict.FAIL for f in findings)
    return BranchHandoff(
        Coverage.BROKEN if broken else Coverage.OK,
        _handoff_summary(newest.name, branch, findings),
        source=newest.name,
        findings=tuple(findings),
    )


def main(args: list[str], repo_root: Path) -> int:
    """`kb-handoff-check [<path>]` — 1 on a contradicted claim, 2 on a bad request.

    Exit 1 covers every FAIL, and a gate claim the record CONTRADICTS is one of
    them — it is not a citation, so "1 on a broken citation" understated it from
    #147 until #157. AMBIGUOUS and UNVERIFIABLE are reported at exit 0.
    """
    positional = [a for a in args if not a.startswith("-")]
    if positional:
        target = Path(positional[0])
        if not target.is_absolute():
            target = repo_root / target
        if not target.is_file():
            print(f"kb-handoff-check: no such file: {positional[0]}", file=sys.stderr)
            return 2
    else:
        found = newest_handoff(repo_root)
        if found is None:
            print(
                "kb-handoff-check: no handoff found under .agent/plans/ — pass a path explicitly",
                file=sys.stderr,
            )
            return 2
        target = found

    findings = check(repo_root, target.read_text(encoding="utf-8", errors="replace"))
    try:
        shown = str(target.relative_to(repo_root))
    except ValueError:
        shown = str(target)
    print(render(findings, source=shown))
    return 1 if any(f.verdict is Verdict.FAIL for f in findings) else 0
