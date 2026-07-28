"""Receipts for the local cross-family review (`.claude/skills/kb-review`).

The review itself cannot live here. It spawns Claude agents, and only the model
can do that — a mise task is a shell command (`mise-tasks-only.md`,
`zero-bash-logic.md`). So the work splits: the *skill* runs the four lenses, and
this module records and enforces that it happened.

`kb-ship` calls :func:`receipt_state` and refuses to push a commit that has no
receipt. That inversion is the point — a gate the model can talk itself past is
not a gate, and CodeRabbit (advisory, rate-limited on 4 of 5 PRs here) is not
one either. The receipt is what makes the local review the real gate.

Receipts are gitignored: one proves that *this machine* reviewed *this commit*.
Committing them would make them stale on the first rebase, and a stale receipt
is worse than none — a green light nobody earned.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Where receipts land, relative to the repo root. Under `.agent/` because a
#: receipt is machine-local by design (`agent-artifact-conventions.md`).
RECEIPT_DIR = Path(".agent/kb/review")

#: Where each lane's report must be written, as `review-<sha>-<lane>.md`.
#:
#: This is what stops the receipt being pure honor-system. Without it,
#: `--lanes standards,spec,cold:codex,silent-failure --blocking 0` minted a
#: full-coverage receipt in one command with **zero evidence any lane ran** —
#: the widest version of a hole whose narrower forms this module had already
#: closed twice. Found by the spec lane, and `agent-report-persistence.md`
#: independently requires these reports on disk anyway.
#:
#: It raises the bar; it is not proof. A determined caller can write a stub
#: file. What it buys is that the honest path is the easy one and faking
#: coverage takes deliberate work — the same "strictly less than a signed
#: receipt" honesty the skill states about the whole mechanism.
REPORT_DIR = RECEIPT_DIR / "reports"

#: A skipped lane must say WHY, as `lane:reason`. A bare lane name is rejected:
#: "did not run" and "does not apply here" are different states, and collapsing
#: them is how a gap gets reported as coverage.
_SKIP_SEPARATOR = ":"

#: The ONLY reasons that excuse a lane. A skip must be a JUSTIFICATION — the
#: lane had nothing to say about this diff — not a report that it never ran.
#:
#: Accepting any non-empty reason was the second version of the same defect: the
#: reference docs already said "a lane that could not be spawned is
#: `not-yet-run`, never `not-applicable`", and then `cold:not-yet-run` sailed
#: through the gate. A doc and the code disagreeing is worse than either alone,
#: and here the code was the permissive one. Found by the cold lane on its
#: SECOND pass, over the commit that fixed its first finding.
#:
#: Reasons that excuse ANY lane: the lane genuinely had nothing to say here.
_SKIP_ANY_LANE = ("not-applicable-",)

#: Reasons that excuse ONE named lane, and no other. `no-spec-available` is the
#: spec lane's alone — a cold or silent-failure lane does not review against a
#: spec, so "there is no spec" cannot explain why it did not run.
#:
#: The THIRD instance of one hole. The reason was matched without ever looking
#: at the lane it was attached to, so `cold:no-spec-available` bought a pass for
#: a lane that never ran — after `--lanes placeholder` and `cold:not-yet-run`
#: had already been closed. The comment on the line right above it said "spec
#: lane, and only when there genuinely is no spec"; nothing enforced it. Found
#: by the cold lane, again, which is now three for three on this gate.
_SKIP_BY_LANE = {"spec": ("no-spec-available",)}

#: The four lenses. Every one must be ACCOUNTED FOR in a receipt — either it ran
#: or it was skipped with a reason. Without this list the gate accepted any
#: non-empty string, so `--lanes placeholder` satisfied it: a gate the model
#: could talk itself past, which is the exact thing this module exists to stop.
#: Found by the cold cross-family lane reviewing this module's own first draft.
#:
#: A lane entry may name a variant after a colon (`cold:codex`,
#: `cold:claude-fallback-SAME-FAMILY`) — the prefix is what must be known.
LANES = ("standards", "spec", "cold", "silent-failure")

_GIT_TIMEOUT = 30


def _lane_prefix(entry: str) -> str:
    """Return the lane an entry names, ignoring any `:variant` suffix."""
    return entry.partition(_SKIP_SEPARATOR)[0]


def _justifies(lane: str, reason: str) -> bool:
    """Return whether ``reason`` excuses ``lane`` — nothing else does.

    `not-applicable-` is a PREFIX and requires a non-empty why after it: a bare
    `not-applicable-` is the same empty claim as no reason at all, and
    `str.startswith` accepted it. Every other justification is matched EXACTLY,
    because `startswith` also accepted `no-spec-availablex` — a typo bought a
    pass for a lane that never ran. Both found by the cold lane.
    """
    for prefix in _SKIP_ANY_LANE:
        if reason.startswith(prefix) and len(reason) > len(prefix):
            return True
    return reason in _SKIP_BY_LANE.get(lane, ())


def _skip_reason_help() -> str:
    """Return a human summary of every accepted skip reason, with its scope."""
    scoped = ", ".join(
        f"{reason} ({lane} lane only)"
        for lane, reasons in _SKIP_BY_LANE.items()
        for reason in reasons
    )
    return ", ".join((*_SKIP_ANY_LANE, scoped))


@dataclass(frozen=True)
class Receipt:
    """One review of one commit, by the lanes named in it.

    A record rather than six loose parameters: the fields only ever travel
    together, and `lanes_ran` is meaningless without `lanes_skipped` beside it.
    """

    sha: str
    fixed_point: str
    #: The base RESOLVED to a commit. `fixed_point` alone is a movable name —
    #: `main` today is not `main` tomorrow — so it cannot say which base was
    #: actually reviewed. Recorded, not gated: the gate's question is "was THIS
    #: commit reviewed", and over-gating on a base that legitimately moves would
    #: invalidate honest receipts. (Cold lane, second pass.)
    fixed_point_sha: str
    lanes_ran: tuple[str, ...]
    lanes_skipped: tuple[str, ...]
    findings: int
    blocking: int
    #: Stamped ONCE, at construction. `as_payload()` used to call
    #: `datetime.now()` on every invocation, so `rejection()` validated a payload
    #: that differed from the one `write_receipt()` then wrote. Nothing gates on
    #: the timestamp, so it changed no verdict — but "the bytes we checked are
    #: the bytes we wrote" is the property this module sells, and it did not hold.
    written_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(timespec="seconds")
    )

    def as_payload(self) -> dict[str, Any]:
        """Return the JSON form written to disk."""
        return {
            "sha": self.sha,
            "written_at": self.written_at,
            "fixed_point": self.fixed_point,
            "fixed_point_sha": self.fixed_point_sha,
            "lanes_ran": list(self.lanes_ran),
            "lanes_skipped": list(self.lanes_skipped),
            "findings": self.findings,
            "blocking": self.blocking,
        }


def rejection(repo_root: Path, receipt: Receipt) -> str | None:
    """Return why ``receipt`` would be rejected, or None if it would pass.

    The same checks :func:`receipt_state` applies, reachable BEFORE the write so
    a bad receipt is refused rather than written and then reported as failing.
    One implementation, so the writer and the reader cannot drift apart.
    """
    return _all_reasons(repo_root, receipt.as_payload(), receipt.sha)


def _all_reasons(repo_root: Path, data: dict[str, Any], sha: str) -> str | None:
    """The complete verdict. ONE composition, called by both writer and reader.

    Composing `_reject_reason or _evidence_gap` independently in two places is
    how the writer and the reader drift back apart, which is the gap this
    module exists to close.
    """
    return _reject_reason(data, sha) or _evidence_gap(repo_root, data, sha)


def _evidence_gap(repo_root: Path, data: dict[str, Any], sha: str) -> str | None:
    """Return why the claimed lanes lack reports on disk, or None if they don't."""
    missing = _missing_reports(repo_root, data, sha)
    if missing:
        return (
            f"claims lane(s) {', '.join(missing)} ran, but no non-empty report is at "
            f"{REPORT_DIR}/review-{_safe_sha(sha)}-<lane>.md — a lane that left no "
            f"report is a claim, not a review"
        )
    return None


def _safe_sha(sha: str) -> str:
    """Return ``sha`` reduced to commit characters.

    Defence in depth behind the CLI's refusal to take a `--sha`: a value with a
    path separator in it would otherwise steer a write out of the receipt dir.
    """
    return "".join(c for c in sha if c.isalnum())


def _safe_lane(lane: str) -> str:
    """Return ``lane`` reduced to filename-safe characters, KEEPING hyphens.

    Hyphens are load-bearing: the lane is `silent-failure`, and stripping the
    hyphen made the gate hunt for `…-silentfailure.md` while every doc said
    `…-silent-failure.md`. Following the skill verbatim then failed the gate.

    The tests did not catch it because they built their fixture paths with
    :func:`report_path` and so inherited the same normalisation — a tautological
    probe (`probes-need-a-control-arm.md`). The test that guards this now spells
    the documented filename out literally.
    """
    return "".join(c for c in lane if c.isalnum() or c in "-_")


def receipt_path(repo_root: Path, sha: str) -> Path:
    """Return the receipt path for ``sha`` (not necessarily existing)."""
    return repo_root / RECEIPT_DIR / f"receipt-{_safe_sha(sha)}.json"


def _git(repo_root: Path, *args: str) -> str:
    """Return stripped stdout of `git *args`, or "" if it cannot be read."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        # Distinguished from a clean miss on purpose: a timeout means the
        # question was never answered, and a silent "" would read as an answer.
        print(f"  git {' '.join(args)}: timed out after {_GIT_TIMEOUT}s")
        return ""
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  git {' '.join(args)}: {exc}")
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def head_sha(repo_root: Path) -> str:
    """Return the full SHA at HEAD, or "" if git cannot be read."""
    return _git(repo_root, "rev-parse", "HEAD")


def base_sha(repo_root: Path, fixed_point: str) -> str:
    """Resolve ``fixed_point`` to the merge-base commit, or "" if unresolvable.

    Three-dot semantics, matching the `git diff <base>...HEAD` the review runs
    against: the question is what the branch added, not how the base has moved.
    """
    return _git(repo_root, "merge-base", fixed_point, "HEAD")


def write_receipt(repo_root: Path, receipt: Receipt) -> Path:
    """Write ``receipt`` under :data:`RECEIPT_DIR` and return its path."""
    path = receipt_path(repo_root, receipt.sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.as_payload(), indent=2) + "\n", encoding="utf-8")
    return path


def _unexplained_skips(skipped: list[str]) -> list[str]:
    """Return skipped-lane entries whose reason does not excuse THAT lane.

    Three ways to fail: no reason at all, a reason that merely REPORTS the lane
    did not run, or a reason that is only valid for a DIFFERENT lane.
    `cold:not-yet-run` is a gap wearing a reason's clothes; `cold:no-spec-available`
    is a gap wearing the spec lane's clothes.

    Takes the already-normalised list rather than re-reading ``data``. Reading
    one key through two idioms — `data.get(k, [])` here, `data.get(k) or []` in
    the caller — meant `"lanes_skipped": null` raised TypeError out of this
    function while the caller treated the same value as empty. A crash is not a
    verdict, and one key deserves one read.
    """
    bad: list[str] = []
    for entry in skipped:
        lane, _, reason = entry.partition(_SKIP_SEPARATOR)
        if not reason or not _justifies(lane, reason):
            bad.append(entry)
    return bad


def report_path(repo_root: Path, sha: str, lane: str) -> Path:
    """Return where ``lane``'s report for ``sha`` must be written."""
    return repo_root / REPORT_DIR / f"review-{_safe_sha(sha)}-{_safe_lane(lane)}.md"


def _missing_reports(repo_root: Path, data: dict[str, Any], sha: str) -> list[str]:
    """Return lanes claimed as RUN that have no non-empty report on disk."""
    # `data.get(k, [])`, matching `_check_lanes` — the THIRD idiom for one key
    # was here (`or []`), contradicting the "one key deserves one read" rule two
    # functions up. It is unreachable with a malformed value only because
    # `_all_reasons` runs `_reject_reason` first; that ordering is now stated
    # rather than relied on silently, and `or []` below is the belt to its braces.
    missing = []
    for entry in _as_entries(data.get("lanes_ran", [])) or []:
        lane = _lane_prefix(str(entry))
        path = report_path(repo_root, sha, lane)
        try:
            body = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        except OSError:
            # Unreadable is "could not check", which must refuse rather than
            # traceback out of the middle of `ship`.
            body = ""
        if not body.strip():
            missing.append(lane)
    return missing


def _check_identity(data: dict[str, Any], sha: str) -> str | None:
    """Reject a receipt that is not about this commit, or not about any range."""
    if data.get("sha") != sha:
        # A receipt filed under this SHA that records another is a copied file.
        return f"records a different SHA ({data.get('sha')})"
    if not str(data.get("fixed_point") or "").strip():
        # Without a base, the receipt says a review happened but not of WHAT.
        return "names no fixed point, so it does not say what was reviewed"
    if not str(data.get("fixed_point_sha") or "").strip():
        # An unresolvable fixed point (a typo, a deleted branch) recorded an
        # empty sha and sailed through, so the receipt claimed a base it never
        # resolved. Unresolvable is "could not check", never "clean".
        return "has an unresolved fixed point, so its comparison base is unknown"
    return None


def _as_entries(value: object) -> list[str] | None:
    """Return ``value`` as a list of strings, or None if it is not a list.

    A numeric `lanes_ran` is valid JSON and used to raise TypeError out of the
    validator, crashing `kb-ship` instead of refusing it. A crash is not a
    verdict — malformed input has to fail CLOSED with a reason.
    """
    if not isinstance(value, list):
        return None
    return [str(v) for v in value]


def _accounting_reason(ran: list[str], skipped: list[str], accounted: set[str]) -> str | None:
    """Return why the lane set is not fully and consistently accounted for.

    The three ways one receipt can misdescribe its own coverage: a lane claimed
    twice over, a lane that does not exist, and a lane nobody mentioned. Split
    out of :func:`_check_lanes` so each stays a named guard clause rather than
    being merged to satisfy a return-count limit — the limit is a signal to
    decompose, not to compress.
    """
    # A lane did one or the other. Listing it in both collapsed to a single set
    # entry, so `--lanes cold:codex --skipped cold:not-applicable-x` satisfied
    # "accounted for" twice over while saying two contradictory things about one
    # lane — and the skill's own worked example used to do exactly that.
    contradictory = sorted({_lane_prefix(e) for e in ran} & {_lane_prefix(e) for e in skipped})
    if contradictory:
        return (
            f"lists lane(s) as BOTH run and skipped: {', '.join(contradictory)} — a "
            f"lane did one or the other, and claiming both is not coverage"
        )

    unknown = sorted(accounted - set(LANES))
    if unknown:
        return f"names unknown lane(s): {', '.join(unknown)} (known: {', '.join(LANES)})"

    missing = [lane for lane in LANES if lane not in accounted]
    if missing:
        return (
            f"lane(s) unaccounted for: {', '.join(missing)} — each must either run "
            f"or be skipped with a reason"
        )
    return None


def _check_lanes(data: dict[str, Any], _sha: str) -> str | None:
    """Reject a receipt whose lanes are unexplained, invented, or missing.

    All three are one defect wearing three hats: a receipt that claims more
    coverage than the review actually had.
    """
    # `data.get(k, [])`, NOT `data.get(k) or []`: absent and present-but-null are
    # different states. Absent defaults to empty (a receipt with all four lanes
    # run legitimately has no skips); an explicit `null`, `0`, or `""` is a
    # MALFORMED array and must be refused, not quietly read as empty. `or []`
    # collapsed the two, which is the same "could not check rendered as clean"
    # this module refuses everywhere else.
    ran_raw = _as_entries(data.get("lanes_ran", []))
    skipped_raw = _as_entries(data.get("lanes_skipped", []))
    if ran_raw is None or skipped_raw is None:
        return "has a malformed lane list (lanes_ran/lanes_skipped must be arrays)"

    unexplained = _unexplained_skips(skipped_raw)
    if unexplained:
        return (
            f"skipped lane(s) not excused: {', '.join(unexplained)} — a skip must "
            f"justify itself with one of {_skip_reason_help()}; a lane that merely "
            f"did not run is a gap, not a skip"
        )

    ran = ran_raw
    named = ran + skipped_raw
    accounted = {_lane_prefix(e) for e in named}

    accounting = _accounting_reason(ran, skipped_raw, accounted)
    if accounting is not None:
        return accounting

    if not ran:
        return "records no lane that actually ran"
    return None


def _check_blocking(data: dict[str, Any], _sha: str) -> str | None:
    """Reject a receipt with unresolved blocking findings, or an unreadable count."""
    blocking = data.get("blocking")
    if not isinstance(blocking, int) or isinstance(blocking, bool):
        return "has no readable blocking count"
    # A negative count is malformed, not "fewer than zero blockers". Only
    # `> 0` was rejected, so a hand-authored `"blocking": -1` read as clean —
    # the same "unreadable rendered as green" this module refuses everywhere
    # else. The CLI cannot produce one; a hand-edited receipt can, which is
    # exactly the reader this check exists for.
    if blocking < 0:
        return f"has a negative blocking count ({blocking}) — that is malformed, not zero"
    if blocking > 0:
        return f"{blocking} blocking review finding(s) — resolve them or re-review"
    return None


#: Run in order; the first reason wins. Split into named checks rather than one
#: long branch so each is separately testable and the list reads as the contract.
_CHECKS = (_check_identity, _check_lanes, _check_blocking)


def _reject_reason(data: dict[str, Any], sha: str) -> str | None:
    """Return why ``data`` fails as a receipt for ``sha``, or None if it passes.

    Every check fails CLOSED: anything unreadable means the question was never
    answered, which is not the same as "nothing is wrong"
    (`probes-need-a-control-arm.md`).
    """
    for check in _CHECKS:
        reason = check(data, sha)
        if reason is not None:
            return reason
    return None


def receipt_state(repo_root: Path, sha: str) -> tuple[bool, str]:
    """Return ``(ok, summary)`` for ``sha``'s review receipt."""
    if not sha:
        return False, "could not read HEAD"

    path = receipt_path(repo_root, sha)
    if not path.is_file():
        return False, (
            f"no review receipt for {sha[:12]} — run the `kb-review` skill "
            f"(an amend or rebase moves the SHA and invalidates the old one)"
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"receipt for {sha[:12]} is unreadable: {exc}"
    if not isinstance(data, dict):
        return False, f"receipt for {sha[:12]} is not an object"

    reason = _all_reasons(repo_root, data, sha)
    if reason is not None:
        return False, f"receipt for {sha[:12]} {reason}"

    ran = data["lanes_ran"]
    skipped = data.get("lanes_skipped", [])
    detail = f"{len(ran)} lane(s): {', '.join(map(str, ran))}"
    if skipped:
        detail += f" | skipped: {', '.join(map(str, skipped))}"
    return True, detail
