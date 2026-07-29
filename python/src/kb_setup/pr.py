"""Ship and land a pull request for THIS repo.

Sized for what this repo actually is: no ``.github/workflows/`` and no
container, so there is no main-CI run to watch and nothing to re-validate
locally after a merge. A PR flow that waited on either would be a gate with
nothing to watch.

What it does keep is the part that carries the safety:

* ``ship`` refuses a commit with no `kb-review` receipt — checked before the
  gates and again immediately before the push. **That is this module's strongest
  behaviour**, because CodeRabbit is advisory here, so the local review is the
  only review;
* ``ship`` then runs every gate in :data:`GATES` (``kb-scan-range``, ``lint``,
  ``test``, ``brain-audit``, ``eval``) BEFORE the branch is pushed, so a red
  branch never becomes a PR. ``kb-scan-range`` is the only one that asks about
  the COMMIT RANGE rather than the working tree — the push sends every commit on
  the branch, and nothing else here reads the intermediate ones (#67);
* the push is pinned to the SHA the receipt was validated against
  (``<sha>:refs/heads/<branch>``), so HEAD moving during the gates cannot slip an
  unreviewed commit onto the remote;
* ``land`` re-reads the checks and pins the merge to the head SHA it verified
  (``gh pr merge --match-head-commit``), so a commit pushed between the check
  and the merge cannot ride in unverified.

This docstring said "``lint`` + ``test``" and never mentioned the receipt until
the standards lane pointed out that `mise.toml` and `CLAUDE.md` had both been
synced while the doc closest to the code had not.

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

#: Checks that are ADVISORY here: reported, never blocking, in any bucket —
#: including "pending". CodeRabbit returned `pass — Review rate limited` on 4 of
#: 5 PRs, and a doc-only commit once sat blocked on its quota queue with nothing
#: wrong. A reviewer that is usually rate-limited is a delay, not a gate.
#:
#: This does NOT mean the review went away. It moved on-machine: `kb-review`
#: runs four local lenses and `ship_main` refuses to push without its receipt.
#: Relaxing the remote gate and adding the local one are one change, not two —
#: dropping only the first would leave the repo with no review at all.
_ADVISORY_CHECKS = frozenset({"CodeRabbit"})

#: How long `land` gives the checks to reach a terminal state before treating
#: the delay as QUOTA rather than review.
#:
#: The distinction is the whole point. "Never blocking" is not "never looking":
#: a CodeRabbit verdict that lands ten seconds after the merge was never read,
#: and reading it costs nothing. What must never happen is waiting on someone
#: else's rate limit — which is why this is bounded and why expiry proceeds
#: rather than refuses.
_TERMINAL_WAIT = 180


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


#: The local gates every PR must pass before it is pushed. `eval` is tiers 1+2 —
#: reachability probes plus the guard fixture table, offline and fast only, so it
#: costs nothing here. Its two opt-in halves run on demand: `-- --live` for the
#: lane doctor (one API call per installed lane) and `-- --slow` for the golden
#: retrieval set (~3 min, advisory — it reports recall@k, it does not gate).
#:
#: NOT EVERY OFFLINE CASE IS BINDING, and this comment used to imply otherwise by
#: scoping "advisory" to the `--slow` half alone. `tier1.mise-redaction-legible`
#: is offline, runs on every ship, and is `gated=False`: it reports and never
#: reddens, because its only remedy is a user-level mise config `do-not.md` #11
#: forbids editing. So a green `eval` gate here means "nothing GATED failed", not
#: "every case passed" — read the case table, not the rc. `evals.render` prints
#: the true failed/unarmed counts precisely so that distinction survives.
#:
#: `kb-scan-range` is FIRST, and that ordering is load-bearing rather than
#: tidiness. `run_gates` returns on the first failure, so putting the cheapest
#: gate and the one with the worst failure mode (a credential reaching a public
#: remote) ahead of the minutes-long ones means a branch carrying a secret is
#: refused before anything else is spent on it.
#:
#: "Cheapest" is measured at **0.36s for a ONE-COMMIT range** — state the
#: condition, because the ordering claim is being made about branches of tens of
#: commits and that figure was not measured there. It scales with the bytes in
#: the range's diffs, and `scan._SCAN_TIMEOUT` is 600s precisely because the
#: upper bound is not known. What holds unconditionally is the ordering by
#: CONSEQUENCE, which is the actual argument. (Spec lane, round 1.)
#:
#: It is also the only gate here that asks about a COMMIT RANGE rather than the
#: working tree. hk's `gitleaks` step is handed `{{ files }}`, so a blob that
#: exists only in an intermediate commit is never opened — and `ship` pushes
#: every commit on the branch to a public remote. See `kb_setup.scan` and #67.
GATES = ("kb-scan-range", "lint", "test", "brain-audit", "eval")


def prepush_scan(repo_root: Path, sha: str) -> tuple[bool, str]:
    """Scan the range ending at ``sha`` — the commit about to be pushed.

    ``sha``, not ``HEAD``. The first version took no ref and let `scan_range`
    resolve `HEAD` itself, while the caller had captured a SHA specifically to
    pin the push — so a HEAD move between the two validated a different commit
    than the one published, reopening the very race the surrounding comments
    said this scan closed. All three non-spine lanes found it independently in
    round 2, and the commit message asserting otherwise was the worse half.

    A module-level seam, and public for the same reason :func:`run_gates` is:
    the ship tests that exercise CONTROL FLOW stub it. A local import inside
    `_validated_sha_for_push` could not be stubbed at all, so every such test
    would shell out to a real gitleaks against a fixture with no repository —
    failing closed, correctly, for a reason unrelated to what the test asks.
    """
    from kb_setup import scan

    return scan.scan_range(repo_root, head=sha)


def run_gates(repo_root: Path) -> bool:
    """Run every local gate in :data:`GATES`; True only if all of them pass."""
    for gate in GATES:
        print(f"==> gate: {gate}")
        rc = _stream(["mise", "run", gate], cwd=repo_root)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"{status}  gate {gate} rc={rc}")
        if rc != 0:
            return False
    return True


def checks_state(pr_number: int) -> tuple[bool, str]:
    """Return ``(green, summary)`` for a PR's checks.

    Green means every BINDING check reached a terminal, non-failing bucket.
    Checks in :data:`_ADVISORY_CHECKS` are reported and never counted, in any
    bucket including "pending". A PR with no checks at all is green — this repo
    has no CI, so "no checks" is normal here and must not deadlock the merge.
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
    # The container AND its element types. Checking only `isinstance(rows, list)`
    # left `r.get(...)` to raise AttributeError on a scalar row, out of a function
    # whose entire contract is to return a worded refusal — a crash is not a
    # verdict, and the comment above already promised strict parsing.
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return (
            False,
            f"unexpected checks payload — want a list of objects (rc={rc}): {out.strip()[:200]}",
        )

    if not rows:
        return True, "no checks configured"

    advisory = [r for r in rows if r.get("name") in _ADVISORY_CHECKS]
    binding = [r for r in rows if r.get("name") not in _ADVISORY_CHECKS]

    note = ""
    if advisory:
        note = " | advisory (not blocking): " + ", ".join(
            f"{r.get('name')}={r.get('bucket')}" for r in advisory
        )

    bad = [r for r in binding if r.get("bucket") not in _OK_BUCKETS]
    if bad:
        detail = ", ".join(f"{r.get('name')}={r.get('bucket')}" for r in bad)
        return False, f"{len(bad)} check(s) not green: {detail}{note}"
    if not binding:
        # Every row was advisory. That is the NORMAL path here (no CI, CodeRabbit
        # on every PR), and it must not read as "0 checks green" — nothing was
        # verified remotely, which is a different sentence from "verified clean".
        # The local `kb-review` receipt is what actually gates; see ship_main.
        return True, f"no binding checks — nothing verified remotely{note}"
    return True, f"{len(binding)} binding check(s) green{note}"


def await_terminal(pr_number: int, *, timeout: int = _TERMINAL_WAIT) -> str:
    """Give a PR's checks a BOUNDED chance to reach a terminal state.

    Uses `gh pr checks --watch` rather than a hand-rolled poll loop, per
    `gh-cli-watch.md`: the CLI already redraws, paces its own interval, and
    knows what terminal means. What it has no flag for is a *bound*, so the
    bound is applied from outside.

    Expiry is not a failure. Past the bound the remaining delay is a rate limit,
    not a review, and this repo's binding gates all ran locally before the push.
    Returns a note for the caller to print; never raises, never blocks a merge.
    """
    try:
        proc = subprocess.run(
            ["gh", "pr", "checks", str(pr_number), "--watch", "--interval", "10"],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"still pending after {timeout}s — treating as quota, not review; proceeding"
    except (OSError, subprocess.SubprocessError) as exc:
        # Could not ask. Say so rather than implying the checks settled.
        return f"could not watch checks ({exc}); reading whatever state exists"
    if proc.returncode != 0:
        # `gh pr checks` exits non-zero for FAILING checks (terminal, expected)
        # AND for "could not ask" (auth expiry, no such PR, a renamed flag), so
        # rc cannot discriminate between them. The old code therefore ignored it
        # and asserted "reached a terminal state" either way — a claim about a
        # question that may never have been asked. It now declines to assert and
        # reports what it saw; `checks_state` is the verdict regardless, so this
        # costs nothing and stops the note from over-claiming.
        detail = (proc.stderr or proc.stdout or "").strip()
        return f"watch exited rc={proc.returncode}; reading whatever state exists: {detail[:160]}"
    return "reached a terminal state"


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
    # `git rev-parse --abbrev-ref HEAD` returns the literal string "HEAD" when
    # detached, so a paused bisect, a stopped rebase, or a `git checkout <sha>`
    # arrives here looking like a branch named HEAD.
    #
    # This guard USED to be free: `git push -u origin HEAD` failed on its own
    # ("must fully qualify the ref"). Pinning the push to `<sha>:refs/heads/
    # <branch>` — the fix for the TOCTOU window — SUCCEEDS on that input and
    # creates a real remote branch literally called `HEAD`. The protection was
    # an accident of the old form, and removing an accident is still removing a
    # protection, so it is explicit now. Found by the cold and silent-failure
    # lanes on the very commit that introduced the refspec.
    if branch == "HEAD":
        print("ship: refusing — detached HEAD; check out a branch first")
        return None
    if not working_tree_clean(repo_root):
        print("ship: refusing — working tree is dirty; commit or stash first")
        return None
    return branch


def _pr_number_and_state(out: str) -> tuple[int | None, str]:
    """Parse `gh pr view --json number,state` output; ``(None, "")`` if unreadable.

    Strict, and fails closed: `_run` merges stdout and stderr, so anything gh
    prints alongside the JSON lands here. An unreadable answer is not "no PR".
    """
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None, ""
    if not isinstance(data, dict) or not isinstance(data.get("number"), int):
        return None, ""
    return data["number"], str(data.get("state") or "")


def _open_or_update_pr(repo_root: Path, branch: str, title: str | None) -> int:
    """Open a PR for ``branch`` (or report the existing one); return an exit code."""
    # `--json number,state`, not `--jq .number`: `gh pr view <branch>` resolves a
    # branch to its PR REGARDLESS OF STATE. Measured — `gh pr view
    # docs/clear-prep-sync --json number,state` → `{"number":52,"state":"MERGED"}`,
    # rc=0 — so asking only for the number made `ship` print
    # `OK — PR #52 updated, gates green` and exit 0 having opened nothing. That is
    # reachable today: `land` deletes the remote branch and leaves the local one,
    # and every PR in this repo is MERGED. A ship that reports success while doing
    # nothing is the failure this whole branch exists to remove.
    rc, out = _run(
        ["gh", "pr", "view", branch, "--json", "number,state"],
        cwd=repo_root,
        timeout=_GH_TIMEOUT,
    )
    if rc == 0:
        number, state = _pr_number_and_state(out)
        if number is None:
            print(f"ship: could not read the branch's PR state (rc=0)\n{out.strip()[:300]}")
            return 1
        if state == "OPEN":
            print(f"ship: OK — PR #{number} updated, gates green")
            return 0
        # MERGED or CLOSED is not something to "update" — the commits just pushed
        # need a new PR. Say which, so this does not look like a lost PR.
        print(f"ship: branch's PR #{number} is {state}; opening a new one")
    # rc != 0 is either "no PR yet" (create one) or "could not ask" (stop). Only
    # the literal gh phrase means the former; any other failure — auth expiry,
    # network, rate limit — is an unanswered question, and falling through to
    # `gh pr create` would turn it into a second PR.
    elif "no pull requests found" not in out.lower():
        print(f"ship: could not read the branch's PR state (rc={rc})\n{out.strip()[:300]}")
        return 1

    create = ["gh", "pr", "create", "--base", "main", "--head", branch]
    create += ["--title", title, "--body", ""] if title else ["--fill"]
    rc, out = _run(create, cwd=repo_root, timeout=_GH_TIMEOUT)
    if rc != 0:
        print(f"ship: PR create failed\n{out}")
        return 1
    print(out.strip())
    print("ship: OK — PR open, gates green")
    return 0


def _validated_sha_for_push(repo_root: Path, branch: str) -> str | None:
    """Return the SHA to push, or None (having said why) if the push must not happen.

    Re-checked immediately before the push, not only before the gates: the gates
    take minutes and nothing stops HEAD moving underneath them. The first check
    fails fast; THIS one guards the push.

    BOTH halves of the refspec are re-read here. Pinning the push to a post-gate
    `sha` while still using the pre-gate `branch` closed one half of the window
    and left the other open: a checkout during the gates would push the new
    branch's (separately reviewed, so passing) SHA onto the OLD branch's ref.
    """
    from kb_setup import review

    sha = review.head_sha(repo_root)
    if current_branch(repo_root) != branch:
        print(f"ship: refusing — branch changed during the gates (was '{branch}')")
        return None
    ok, summary = review.receipt_state(repo_root, sha, require_base="main")
    if not ok:
        print(f"ship: refusing — HEAD moved since the review ({summary})")
        return None

    # The secret scan is re-run HERE, pinned to `sha` — the exact object the
    # push will send — and not only as the first gate. Same reasoning as the
    # receipt check directly above, applied to the other thing that must be true
    # of the pushed bytes: `run_gates` scanned whatever HEAD was minutes ago,
    # and nothing stops HEAD moving underneath the gates.
    #
    # A moved HEAD does not always invalidate the receipt — `review.EXEMPT_PATHS`
    # lets an ancestor's receipt cover a delta of `graphify-out/memory/**`, which
    # is precisely the directory that carried three live credentials on
    # 2026-07-28. So the receipt check alone cannot stand in for this one.
    # (Cold lane and silent-failure lane, round 1, independently.)
    #
    # Cheap enough to repeat. The first run is what fails fast; THIS one is
    # what guarantees.
    scanned, scan_summary = prepush_scan(repo_root, sha)
    print(f"==> scan-range (pre-push): {scan_summary}")
    if not scanned:
        print("ship: refusing — the commit range did not pass the secret scan")
        return None
    return sha


def ship_main(repo_root: Path, *, title: str | None = None) -> int:
    """Gate, push, and open a PR for the current branch; return an exit code."""
    branch = _ship_preflight(repo_root)
    if branch is None:
        return 1

    # Checked BEFORE the gates, deliberately: a failing gate is fixed by an
    # amend, which moves the SHA and invalidates whatever receipt existed. Ask
    # the cheap question first rather than after four gate runs.
    from kb_setup import review

    ok, summary = review.receipt_state(repo_root, review.head_sha(repo_root), require_base="main")
    print(f"==> review: {summary}")
    if not ok:
        print("ship: refusing — not pushing an unreviewed commit")
        return 1

    if not run_gates(repo_root):
        print("ship: gates failed — not pushing")
        return 1

    sha = _validated_sha_for_push(repo_root, branch)
    if sha is None:
        return 1

    # Push the SHA that was just VALIDATED, not the branch name. Re-reading HEAD
    # and then pushing `branch` left the window open that the check above exists
    # to close: HEAD could move between the two calls and the push would send a
    # commit no lane ever read — the receipt would be honest and the pushed bytes
    # would not be the ones it is for. The refspec makes the validated commit and
    # the pushed commit the same object by construction.
    rc, out = _run(["git", "push", "origin", f"{sha}:refs/heads/{branch}"], cwd=repo_root)
    if rc != 0:
        print(f"ship: push failed\n{out}")
        return 1

    # `-u` cannot set tracking from a raw-SHA refspec — probed both arms: the
    # push succeeds and silently leaves no upstream — so set it explicitly.
    # Non-fatal on purpose, and NOT a swallowed error: the validated commit is
    # already on the remote and the PR path uses `--head <branch>` rather than
    # local tracking, so only a later bare `git push` would notice. Reported
    # rather than ignored, with the command that fixes it.
    rc_upstream, out_upstream = _run(
        ["git", "branch", "--set-upstream-to", f"origin/{branch}", branch],
        cwd=repo_root,
    )
    if rc_upstream != 0:
        print(
            f"ship: pushed {sha[:12]}, but could not set upstream tracking "
            f"(non-fatal; run `git branch -u origin/{branch}`): "
            f"{out_upstream.strip()[:200]}"
        )

    return _open_or_update_pr(repo_root, branch, title)


def land_main(repo_root: Path, pr_number: int) -> int:
    """Verify a PR's checks, squash-merge it pinned to that SHA, and sync main."""
    # Wait for a TERMINAL state, never for quota. Advisory checks still cannot
    # block the merge — but a verdict that arrives ten seconds later was never
    # read, and reading it is free.
    print(f"==> waiting for terminal check state: {await_terminal(pr_number)}")

    green, summary = checks_state(pr_number)
    print(f"==> checks: {summary}")
    if not green:
        print(f"land: refusing — PR #{pr_number} is not green")
        return 1

    oid = pr_head_oid(pr_number)
    if not oid:
        print(f"land: could not read head SHA for PR #{pr_number}")
        return 1

    # The PR head — not local HEAD. `ship` guards what IT pushes; a commit
    # pushed afterwards by any other route reaches the merge having been
    # reviewed by nothing. Receipts are machine-local, so this also means you
    # land from the machine you reviewed on; the message says so, because
    # otherwise the refusal looks like a bug rather than the design.
    from kb_setup import review

    # `require_base="main"` here as well as in `ship`. Without it `land` accepted a
    # receipt covering only a SUFFIX of the branch: `--fixed-point HEAD^` produces
    # a perfectly truthful receipt for one commit, and land merged all twelve.
    #
    # That is not reachable through `ship`, which refuses the same receipt — but
    # `gh pr create` is NOT guard-denied here (`mise.toml`, `mise-tasks-only.md`),
    # and this gate is documented as the backstop for exactly that bypass
    # (`kb-review/SKILL.md`, "closing the gap where a PR is pushed by one path and
    # merged by another"). A backstop that does not cover its own stated case is
    # the kind of untrue claim this module exists to refuse. Found by the cold
    # lane; the standards and spec lanes found the asymmetry and rated it lower.
    reviewed, detail = review.receipt_state(repo_root, oid, require_base="main")
    print(f"==> review: {detail}")
    if not reviewed:
        print(
            f"land: refusing — PR #{pr_number}'s head is unreviewed. Run the "
            f"`kb-review` skill against it, or land from the machine that did."
        )
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
