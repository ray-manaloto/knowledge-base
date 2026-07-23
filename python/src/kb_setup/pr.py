"""Ship and land a pull request for THIS repo.

Deliberately thinner than the dotfiles equivalent (``dotfiles_setup.pr``). That
one watches a main ``ci.yml`` run and then re-validates a devcontainer locally;
this repo has **neither** — no ``.github/workflows/``, no container — so copying
those steps would cargo-cult a gate with nothing to watch.

What survives the trim is the part that carries the safety:

* ``ship`` runs the same local gates CI would have run (``lint`` + ``test``)
  BEFORE the branch is pushed, so a red branch never becomes a PR;
* ``land`` re-reads the checks and pins the merge to the head SHA it verified
  (``gh pr merge --match-head-commit``), so a commit pushed between the check
  and the merge cannot ride in unverified.

Invoked via the ``kb-ship`` / ``kb-land`` mise tasks — never by hand.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

_GIT_TIMEOUT = 120
_GH_TIMEOUT = 120
_GATE_TIMEOUT = 1800

# `gh pr checks --json bucket` buckets that do NOT block a merge. "skipping" is a
# valid terminal state (a conditional job that correctly did not run); "pending"
# is deliberately absent — it means the answer is not in yet.
_OK_BUCKETS = frozenset({"pass", "skipping", "neutral"})


def _run(
    cmd: list[str], *, cwd: Path | None = None, timeout: int = _GIT_TIMEOUT
) -> tuple[int, str]:
    """Run ``cmd`` capturing output; return ``(returncode, stdout+stderr)``."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{cmd[0]}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _stream(cmd: list[str], *, cwd: Path | None = None, timeout: int = _GATE_TIMEOUT) -> int:
    """Run ``cmd`` with output streaming to the terminal; return its exit code."""
    try:
        return subprocess.run(cmd, cwd=cwd, check=False, timeout=timeout).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  {cmd[0]}: {exc}")
        return 1


def current_branch(repo_root: Path) -> str:
    """Return the checked-out branch name, or "" if it cannot be determined."""
    rc, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    return out.strip() if rc == 0 else ""


def working_tree_clean(repo_root: Path) -> bool:
    """Return True when nothing is staged, modified, or untracked-and-unignored."""
    rc, out = _run(["git", "status", "--porcelain"], cwd=repo_root)
    return rc == 0 and not out.strip()


def run_gates(repo_root: Path) -> bool:
    """Run the local gates (lint, test); return True only if every one passes."""
    for gate in ("lint", "test"):
        print(f"==> gate: {gate}")
        rc = _stream(["mise", "run", gate], cwd=repo_root)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"{status}  gate {gate} rc={rc}")
        if rc != 0:
            return False
    return True


def checks_state(pr_number: int) -> tuple[bool, str]:
    """Return ``(green, summary)`` for a PR's checks.

    Green means every check reached a terminal, non-failing bucket. A PR with no
    checks at all is green — this repo has no CI, so "no checks" is normal here
    and must not deadlock the merge.
    """
    rc, out = _run(
        ["gh", "pr", "checks", str(pr_number), "--json", "name,bucket"], timeout=_GH_TIMEOUT
    )
    # `gh pr checks` exits non-zero both when checks FAIL and (per its docs) when
    # none exist, so rc alone cannot discriminate — the JSON body is what does.
    # Parse strictly and FAIL CLOSED: output we cannot parse means we never got to
    # ask the question, which is not the same as "nothing is wrong" and must never
    # authorise a merge (`probes-need-a-control-arm.md`: a redirect/parse-error is
    # not a "no"). Only a well-formed empty array counts as "no checks".
    #
    # NOT verified against a real zero-check PR: every PR in this repo so far has
    # had CodeRabbit, so that arm could not be armed. If a genuinely check-less PR
    # ever reports non-JSON here, land will refuse and print the raw output —
    # noisy, but safe, and self-diagnosing.
    try:
        rows = json.loads(out)
    except json.JSONDecodeError:
        return False, f"could not read checks (rc={rc}): {out.strip()[:200]}"
    if not isinstance(rows, list):
        return False, f"unexpected checks payload (rc={rc}): {out.strip()[:200]}"

    if not rows:
        return True, "no checks configured"

    bad = [r for r in rows if r.get("bucket") not in _OK_BUCKETS]
    if bad:
        detail = ", ".join(f"{r.get('name')}={r.get('bucket')}" for r in bad)
        return False, f"{len(bad)} check(s) not green: {detail}"
    return True, f"{len(rows)} check(s) green"


def pr_head_oid(pr_number: int) -> str | None:
    """Return the PR's current head commit SHA, or None if it cannot be read."""
    rc, out = _run(
        ["gh", "pr", "view", str(pr_number), "--json", "headRefOid", "--jq", ".headRefOid"],
        timeout=_GH_TIMEOUT,
    )
    oid = out.strip()
    return oid if rc == 0 and oid else None


def _ship_preflight(repo_root: Path) -> str | None:
    """Return the branch to ship, or None (having explained why) if it must not."""
    branch = current_branch(repo_root)
    if not branch or branch == "main":
        print(f"ship: refusing — on '{branch or 'unknown'}'; create a branch first")
        return None
    if not working_tree_clean(repo_root):
        print("ship: refusing — working tree is dirty; commit or stash first")
        return None
    return branch


def _open_or_update_pr(repo_root: Path, branch: str, title: str | None) -> int:
    """Open a PR for ``branch`` (or report the existing one); return an exit code."""
    rc, out = _run(
        ["gh", "pr", "view", branch, "--json", "number", "--jq", ".number"], timeout=_GH_TIMEOUT
    )
    existing = out.strip()
    if rc == 0 and existing.isdigit():
        print(f"ship: OK — PR #{existing} updated, gates green")
        return 0

    create = ["gh", "pr", "create", "--base", "main", "--head", branch]
    create += ["--title", title, "--body", ""] if title else ["--fill"]
    rc, out = _run(create, cwd=repo_root, timeout=_GH_TIMEOUT)
    if rc != 0:
        print(f"ship: PR create failed\n{out}")
        return 1
    print(out.strip())
    print("ship: OK — PR open, gates green")
    return 0


def ship_main(repo_root: Path, *, title: str | None = None) -> int:
    """Gate, push, and open a PR for the current branch; return an exit code."""
    branch = _ship_preflight(repo_root)
    if branch is None:
        return 1

    if not run_gates(repo_root):
        print("ship: gates failed — not pushing")
        return 1

    rc, out = _run(["git", "push", "-u", "origin", branch], cwd=repo_root)
    if rc != 0:
        print(f"ship: push failed\n{out}")
        return 1

    return _open_or_update_pr(repo_root, branch, title)


def land_main(repo_root: Path, pr_number: int) -> int:
    """Verify a PR's checks, squash-merge it pinned to that SHA, and sync main."""
    green, summary = checks_state(pr_number)
    print(f"==> checks: {summary}")
    if not green:
        print(f"land: refusing — PR #{pr_number} is not green")
        return 1

    oid = pr_head_oid(pr_number)
    if not oid:
        print(f"land: could not read head SHA for PR #{pr_number}")
        return 1
    print(f"==> merging PR #{pr_number} pinned to {oid[:12]}")

    rc, out = _run(
        [
            "gh",
            "pr",
            "merge",
            str(pr_number),
            "--squash",
            "--delete-branch",
            "--match-head-commit",
            oid,
        ],
        cwd=repo_root,
        timeout=_GH_TIMEOUT,
    )
    if rc != 0:
        print(f"land: merge failed (head may have moved since the check)\n{out}")
        return 1

    for cmd in (["git", "checkout", "main"], ["git", "pull", "--ff-only"]):
        rc, out = _run(cmd, cwd=repo_root)
        if rc != 0:
            print(f"land: merged, but local sync failed at `{' '.join(cmd)}`\n{out}")
            return 1

    print(f"land: OK — PR #{pr_number} merged, main synced")
    return 0
