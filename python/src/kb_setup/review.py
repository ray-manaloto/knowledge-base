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
from dataclasses import dataclass
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
_SKIP_JUSTIFICATIONS = (
    "not-applicable-",  # the lane cannot say anything about this diff
    "no-spec-available",  # spec lane, and only when there genuinely is no spec
)

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

    def as_payload(self) -> dict[str, Any]:
        """Return the JSON form written to disk."""
        return {
            "sha": self.sha,
            "written_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
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
    payload = receipt.as_payload()
    return _reject_reason(payload, receipt.sha) or _evidence_gap(repo_root, payload, receipt.sha)


def _evidence_gap(repo_root: Path, data: dict[str, Any], sha: str) -> str | None:
    """Return why the claimed lanes lack reports on disk, or None if they don't."""
    missing = _missing_reports(repo_root, data, sha)
    if missing:
        return (
            f"claims lane(s) {', '.join(missing)} ran, but no non-empty report is at "
            f"{REPORT_DIR}/review-{sha[:12]}…-<lane>.md — a lane that left no report "
            f"is a claim, not a review"
        )
    return None


def _safe(sha: str) -> str:
    """Return ``sha`` with anything that is not a commit character stripped.

    Defence in depth behind the CLI's refusal to take a `--sha`: a value with a
    path separator in it would otherwise steer a write out of the receipt dir.
    """
    return "".join(c for c in sha if c.isalnum())


def receipt_path(repo_root: Path, sha: str) -> Path:
    """Return the receipt path for ``sha`` (not necessarily existing)."""
    return repo_root / RECEIPT_DIR / f"receipt-{_safe(sha)}.json"


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
    except OSError, subprocess.SubprocessError:
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


def _unexplained_skips(data: dict[str, Any]) -> list[str]:
    """Return skipped-lane entries whose reason does not excuse the lane.

    Two ways to fail: no reason at all, or a reason that merely REPORTS the lane
    did not run. Only a justification — the lane had nothing to say about this
    diff — excuses it. `cold:not-yet-run` is a gap wearing a reason's clothes.
    """
    bad: list[str] = []
    for s in data.get("lanes_skipped", []):
        if not isinstance(s, str):
            bad.append(str(s))
            continue
        reason = s.partition(_SKIP_SEPARATOR)[2]
        if not reason or not reason.startswith(_SKIP_JUSTIFICATIONS):
            bad.append(s)
    return bad


def report_path(repo_root: Path, sha: str, lane: str) -> Path:
    """Return where ``lane``'s report for ``sha`` must be written."""
    return repo_root / REPORT_DIR / f"review-{_safe(sha)}-{_safe(lane)}.md"


def _missing_reports(repo_root: Path, data: dict[str, Any], sha: str) -> list[str]:
    """Return lanes claimed as RUN that have no non-empty report on disk."""
    missing = []
    for entry in data.get("lanes_ran") or []:
        lane = _lane_prefix(str(entry))
        path = report_path(repo_root, sha, lane)
        if not path.is_file() or not path.read_text(encoding="utf-8", errors="replace").strip():
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
    return None


def _check_lanes(data: dict[str, Any], _sha: str) -> str | None:
    """Reject a receipt whose lanes are unexplained, invented, or missing.

    All three are one defect wearing three hats: a receipt that claims more
    coverage than the review actually had.
    """
    unexplained = _unexplained_skips(data)
    if unexplained:
        return (
            f"skipped lane(s) not excused: {', '.join(unexplained)} — a skip must "
            f"justify itself with one of {', '.join(_SKIP_JUSTIFICATIONS)}; a lane "
            f"that merely did not run is a gap, not a skip"
        )

    ran = [str(s) for s in data.get("lanes_ran") or []]
    named = ran + [str(s) for s in data.get("lanes_skipped") or []]
    accounted = {_lane_prefix(e) for e in named}

    unknown = sorted(accounted - set(LANES))
    if unknown:
        return f"names unknown lane(s): {', '.join(unknown)} (known: {', '.join(LANES)})"

    missing = [lane for lane in LANES if lane not in accounted]
    if missing:
        return (
            f"lane(s) unaccounted for: {', '.join(missing)} — each must either run "
            f"or be skipped with a reason"
        )

    if not ran:
        return "records no lane that actually ran"
    return None


def _check_blocking(data: dict[str, Any], _sha: str) -> str | None:
    """Reject a receipt with unresolved blocking findings, or an unreadable count."""
    blocking = data.get("blocking")
    if not isinstance(blocking, int) or isinstance(blocking, bool):
        return "has no readable blocking count"
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

    reason = _reject_reason(data, sha) or _evidence_gap(repo_root, data, sha)
    if reason is not None:
        return False, f"receipt for {sha[:12]} {reason}"

    ran = data["lanes_ran"]
    skipped = data.get("lanes_skipped") or []
    detail = f"{len(ran)} lane(s): {', '.join(map(str, ran))}"
    if skipped:
        detail += f" | skipped: {', '.join(map(str, skipped))}"
    return True, detail
