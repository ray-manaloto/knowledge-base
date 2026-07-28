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

#: A skipped lane must say WHY, as `lane:reason`. A bare lane name is rejected:
#: "did not run" and "does not apply here" are different states, and collapsing
#: them is how a gap gets reported as coverage.
_SKIP_SEPARATOR = ":"

_GIT_TIMEOUT = 30


@dataclass(frozen=True)
class Receipt:
    """One review of one commit, by the lanes named in it.

    A record rather than six loose parameters: the fields only ever travel
    together, and `lanes_ran` is meaningless without `lanes_skipped` beside it.
    """

    sha: str
    fixed_point: str
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
            "lanes_ran": list(self.lanes_ran),
            "lanes_skipped": list(self.lanes_skipped),
            "findings": self.findings,
            "blocking": self.blocking,
        }


def receipt_path(repo_root: Path, sha: str) -> Path:
    """Return the receipt path for ``sha`` (not necessarily existing)."""
    return repo_root / RECEIPT_DIR / f"receipt-{sha}.json"


def head_sha(repo_root: Path) -> str:
    """Return the full SHA at HEAD, or "" if git cannot be read."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except OSError, subprocess.SubprocessError:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def write_receipt(repo_root: Path, receipt: Receipt) -> Path:
    """Write ``receipt`` under :data:`RECEIPT_DIR` and return its path."""
    path = receipt_path(repo_root, receipt.sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.as_payload(), indent=2) + "\n", encoding="utf-8")
    return path


def _unexplained_skips(data: dict[str, Any]) -> list[str]:
    """Return skipped-lane entries that carry no reason."""
    return [
        str(s)
        for s in data.get("lanes_skipped", [])
        if not isinstance(s, str) or not s.partition(_SKIP_SEPARATOR)[2]
    ]


def _reject_reason(data: dict[str, Any], sha: str) -> str | None:
    """Return why ``data`` fails as a receipt for ``sha``, or None if it passes.

    One function so the checks read as a list. Every branch here fails CLOSED:
    anything unreadable means the question was never answered, which is not the
    same as "nothing is wrong" (`probes-need-a-control-arm.md`).
    """
    if data.get("sha") != sha:
        # A receipt filed under this SHA that records another is a copied file.
        return f"records a different SHA ({data.get('sha')})"

    unexplained = _unexplained_skips(data)
    if unexplained:
        return f"skipped lane(s) with no reason: {', '.join(unexplained)}"

    if not data.get("lanes_ran"):
        return "records no lane that actually ran"

    blocking = data.get("blocking")
    if not isinstance(blocking, int) or isinstance(blocking, bool):
        return "has no readable blocking count"
    if blocking > 0:
        return f"{blocking} blocking review finding(s) — resolve them or re-review"

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

    reason = _reject_reason(data, sha)
    if reason is not None:
        return False, f"receipt for {sha[:12]} {reason}"

    ran = data["lanes_ran"]
    skipped = data.get("lanes_skipped") or []
    detail = f"{len(ran)} lane(s): {', '.join(map(str, ran))}"
    if skipped:
        detail += f" | skipped: {', '.join(map(str, skipped))}"
    return True, detail
