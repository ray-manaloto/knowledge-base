"""Verify a handoff's static claims — `mise run kb-handoff-check`.

WHAT THIS REPLACES. `/clear-prep` step 6 asks the agent to self-verify the
handoff it has just written, at the end of a long session, from memory: do the
cited paths exist, is every `file:line` real, is every named task real. That is
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

from kb_setup import citations, resolve


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
    """Every static claim in ``text``, checked against ``repo_root``.

    The authored-tree index is built ONCE here and threaded through every
    resolution: a handoff carries tens of citations, and rebuilding the walk per
    citation is the difference between one pass over the tree and one per claim.
    """
    index = resolve.build_index(repo_root)
    findings = [_check_path(repo_root, c, index) for c in citations.path_citations(text)]
    findings.extend(_check_line_ref(repo_root, c, index) for c in citations.line_citations(text))
    findings.extend(_check_tasks(repo_root, text))
    return findings


def _check_path(repo_root: Path, cite: citations.PathCitation, index: resolve.Index) -> Finding:
    got = resolve.resolve_path(repo_root, cite.text, index)
    if cite.marked_absent:
        return _check_absent_marker("path", cite.text, cite.line, got)
    return Finding("path", _VERDICT_OF[got.state], cite.text, cite.line, got.detail)


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


def _check_tasks(repo_root: Path, text: str) -> list[Finding]:
    declared = resolve.declared_tasks(repo_root)
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
    elif counts[Verdict.FAIL]:
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


def newest_handoff(repo_root: Path) -> Path | None:
    """The most recently modified `.agent/plans/session-*.md`, or None.

    Chosen by mtime rather than by filename. The names sort
    `session-2026-08-03-d.md` BEFORE `session-2026-08-03.md` (`-` < `.` in
    ASCII), so a lexicographic pick hands back the older of the two — and
    `.agent/` is gitignored and machine-local, so mtime here is authoring time
    rather than checkout time.
    """
    plans = sorted(
        (repo_root / ".agent" / "plans").glob("session-*.md"),
        key=lambda p: p.stat().st_mtime,
    )
    return plans[-1] if plans else None


def main(args: list[str], repo_root: Path) -> int:
    """`kb-handoff-check [<path>]` — 1 on a broken citation, 2 on a bad request."""
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
