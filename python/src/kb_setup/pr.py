# Copyright (c) 2026 Raymond Manaloto
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
* ``ship`` then refuses a branch whose OWN handoff cites something that is not
  there (:func:`_handoff_holds`, #149) — and explicitly SKIPS, out loud, when the
  newest handoff under `.agent/plans/` does not record the current branch. Why
  the match matters, and why it is the NEWEST handoff rather than the newest
  matching one, is recorded once at `handoff.check_for_branch` with the
  measurement behind it; this module owns only the ship-time policy;
* ``ship`` then runs every gate in :data:`gates.GATE_TASKS` (``lint``, ``test``,
  ``brain-audit``, ``eval``) BEFORE the branch is pushed, so a red branch never
  becomes a PR — and RECORDS each result under `.agent/kb/gates/`, because the
  numbers it prints used to survive only as long as the terminal did (#146). The
  list, the runner and the record all live in `kb_setup.gates`; this module keeps
  the ship-specific policy and nothing else;
* the push is pinned to the SHA the receipt was validated against
  (``<sha>:refs/heads/<branch>``), so HEAD moving during the gates cannot slip an
  unreviewed commit onto the remote;
* ``land`` gives the checks a BOUNDED chance to reach a terminal state before
  reading them (:func:`await_terminal` — `gh pr checks --watch` has no timeout of
  its own), then refuses a PR head with no `kb-review` receipt covering the WHOLE
  branch, and pins the merge to the head SHA it verified
  (``gh pr merge --match-head-commit``), so a commit pushed between the check
  and the merge cannot ride in unverified.

This docstring said "``lint`` + ``test``" and never mentioned the receipt until
the standards lane pointed out that `mise.toml` and `CLAUDE.md` had both been
synced while the doc closest to the code had not. The ``land`` bullet then
repeated the shape one commit later — it described the check re-read and the
merge pin while omitting both the terminal wait and the receipt refusal, in the
very commit that congratulated itself for syncing the ``ship`` half. (#57)

Invoked via the ``kb-ship`` / ``kb-land`` mise tasks — never by hand.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from kb_setup import events

_GIT_TIMEOUT = 120
_GH_TIMEOUT = 120
# `_GATE_TIMEOUT` moved to `kb_setup.gates` with the runner it bounded (#146).
# Left behind here it would be dead config that reads as live — the next person
# raising a gate timeout would edit the copy nothing consults.

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
#: `Repowise / code health` joined 2026-08-17 on Ray's ruling, and it is a
#: DIFFERENT argument from CodeRabbit's — recorded because the two look alike and
#: are not. CodeRabbit is advisory because it is usually *unavailable*; Repowise
#: is advisory because of what it MEASURES. Its verdict on PR #336 was
#: "AI-authored files account for the larger share of this PR's regression (-0.5
#: vs -0.0 human)": a delta on a composite score, attributed by authorship rather
#: than by defect. That is a signal worth reading and not a statement that
#: anything is wrong, and a gate whose failure names no defect cannot be
#: actioned — only appeased.
#:
#: THE COST, stated rather than discovered later: no PR blocks on code health
#: again. A real complexity regression now has to be caught by review or by the
#: `C901`/`PLR0915` ruff rules, which are binding and did fire on this very round
#: (three times, each fixed by extraction rather than by raising a threshold).
#:
#: Its detail page needs a browser login — measured, 307 with a github.com
#: control at 200 — so the summary above is the whole of what an agent can read.
#: A blocking gate whose evidence is unreachable from here is one nobody can
#: discharge without a human, which is the practical half of the argument.
_ADVISORY_CHECKS = frozenset({"CodeRabbit", "Repowise / code health"})

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


def current_branch(repo_root: Path) -> str:
    """Return the checked-out branch name, or "" if it cannot be determined."""
    rc, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    return out.strip() if rc == 0 else ""


def working_tree_clean(repo_root: Path) -> bool:
    """Return True when nothing is staged, modified, or untracked-and-unignored."""
    rc, out = _run(["git", "status", "--porcelain"], cwd=repo_root)
    return rc == 0 and not out.strip()


def run_gates(repo_root: Path) -> bool:
    """Run every gate in :data:`gates.GATE_TASKS`; True only if all of them pass.

    The list, the runner and the record all live in `kb_setup.gates` now (#146).
    This function keeps only the ship path's two policy choices:

    * **stop at the first failure** — the refusal is already decided, so the
      remaining gates would cost minutes to tell us something that cannot change
      it. `kb-gates` chooses the opposite, which is why the flag exists;
    * **refuse before running** if the gate list names a task this repo does not
      declare, rather than letting `mise` fail three gates in.

    It delegates rather than keeping its own loop specifically so that the record
    and the push decision cannot disagree: they are now the same numbers, read
    once. A second loop here would be a second answer to "did the gates pass".
    """
    from kb_setup import gates

    # `run_and_record`, not the three calls open-coded. Doing the sequence by hand
    # here is what let this path skip the unreadable-HEAD refusal `gates.main`
    # makes, so a ship could write `gates-.json` with `"sha": ""` — a record that
    # names no commit, which is the artifact #146 exists to abolish. Both review
    # lanes found that independently; the duplication was the cause, so the
    # sequence has one owner now and this function keeps only the policy.
    gate_run, summary = gates.run_and_record(repo_root, gates.GATE_TASKS, stop_on_failure=True)
    if gate_run is None:
        events.say("ship.gates_unrunnable", f"ship: refusing — {summary}", refused=True)
        return False

    events.say("ship.gates", summary, all_passed=gate_run.all_passed)
    return gate_run.all_passed


def checks_state(pr_number: int, *, cwd: Path | None = None) -> tuple[bool, str]:
    """Return ``(green, summary)`` for a PR's checks.

    Green means every BINDING check reached a terminal, non-failing bucket.
    Checks in :data:`_ADVISORY_CHECKS` are reported and never counted, in any
    bucket including "pending". A PR with no checks at all is green — this repo
    has no CI, so "no checks" is normal here and must not deadlock the merge.

    ``cwd`` selects the repository `gh` resolves against, and defaults to None
    — the process's own directory, which is what every caller in this module
    relied on implicitly. It is explicit now because `kb_setup.session_state`
    takes a ``repo_root`` and passes it to every other read; this was the one
    call that silently ignored it, so a caller pointing the snapshot at another
    checkout would have got PR checks resolved against whatever directory the
    process happened to be in. Not reachable from the shipped task, where
    `cli.py` sets ``repo_root = Path.cwd()`` — a latent inconsistency, fixed
    additively so `ship`/`land` behaviour is unchanged. (Cold lane, P3.)
    """
    rc, out = _run(
        ["gh", "pr", "checks", str(pr_number), "--json", "name,bucket"],
        cwd=cwd,
        timeout=_GH_TIMEOUT,
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
        events.say(
            "ship.refused_branch",
            f"ship: refusing — on '{branch or 'unknown'}'; create a branch first",
            branch=branch,
            refused=True,
        )
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
        events.say(
            "ship.refused_detached",
            "ship: refusing — detached HEAD; check out a branch first",
            refused=True,
        )
        return None
    if not working_tree_clean(repo_root):
        events.say(
            "ship.refused_dirty",
            "ship: refusing — working tree is dirty; commit or stash first",
            refused=True,
        )
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
            events.say(
                "ship.pr_state_unreadable",
                f"ship: could not read the branch's PR state (rc=0)\n{out.strip()[:300]}",
                rc=0,
            )
            return 1
        if state == "OPEN":
            events.say(
                "ship.pr_updated",
                f"ship: OK — PR #{number} updated, gates green",
                pr=number,
            )
            return 0
        # MERGED or CLOSED is not something to "update" — the commits just pushed
        # need a new PR. Say which, so this does not look like a lost PR.
        events.say(
            "ship.pr_superseded",
            f"ship: branch's PR #{number} is {state}; opening a new one",
            pr=number,
            state=state,
        )
    # rc != 0 is either "no PR yet" (create one) or "could not ask" (stop). Only
    # the literal gh phrase means the former; any other failure — auth expiry,
    # network, rate limit — is an unanswered question, and falling through to
    # `gh pr create` would turn it into a second PR.
    elif "no pull requests found" not in out.lower():
        events.say(
            "ship.pr_state_unreadable",
            f"ship: could not read the branch's PR state (rc={rc})\n{out.strip()[:300]}",
            rc=rc,
        )
        return 1

    create = ["gh", "pr", "create", "--base", "main", "--head", branch]
    create += ["--title", title, "--body", ""] if title else ["--fill"]
    rc, out = _run(create, cwd=repo_root, timeout=_GH_TIMEOUT)
    if rc != 0:
        events.say("ship.pr_create_failed", f"ship: PR create failed\n{out}", rc=rc)
        return 1
    # `gh pr create` prints the PR URL and nothing else; it is the one line a
    # human actually wants from a ship, so it is carried as a field too.
    events.say("ship.pr_url", out.strip(), url=out.strip())
    events.say("ship.ok", "ship: OK — PR open, gates green")
    return 0


def _handoff_holds(repo_root: Path, branch: str) -> bool:
    """Print the handoff verdict for ``branch``; False only when it is BROKEN.

    Three outcomes and they are all REPORTED, which is the criterion this gate
    was specified against (#149): a skip that printed nothing would be
    indistinguishable from a handoff that was checked and held.

    * BROKEN — the handoff describing THIS branch cites something that is not
      there. Refuse, and print the findings so the fix does not need a second
      command.
    * OK — checked and it holds. Advisory findings are named in the summary and
      do not refuse; `kb_setup.handoff` already draws that line and drawing a
      second, stricter one here would make `mise run kb-handoff-check` disagree
      with the gate that consumes it.
    * SKIPPED — the newest handoff does not describe this branch. NOT a pass, and
      it is the normal case at ship time, because `/clear-prep` writes the
      handoff after the round rather than before it.

    The skip is what makes the gate safe rather than lenient, and the evidence
    for that — including why it is the NEWEST handoff and not the newest one that
    matches — lives at `handoff.check_for_branch` rather than being paraphrased
    here. One measured fact, one place to correct it.
    """
    from kb_setup import handoff

    result = handoff.check_for_branch(repo_root, branch)
    # `coverage` as a field is the row that matters most here: SKIPPED is not a
    # pass, and until now that distinction lived only inside a rendered summary
    # string a reader had to parse by eye.
    events.say(
        "ship.handoff",
        f"==> handoff: {result.summary}",
        coverage=result.coverage.name,
        source=str(result.source),
    )
    if result.coverage is not handoff.Coverage.BROKEN:
        return True
    events.say(
        "ship.handoff_findings",
        handoff.render(list(result.findings), source=result.source),
        findings=len(list(result.findings)),
    )
    events.say(
        "ship.refused_handoff",
        "ship: refusing — the handoff for this branch cites something that is not there",
        refused=True,
    )
    return False


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
        events.say(
            "ship.refused_branch_moved",
            f"ship: refusing — branch changed during the gates (was '{branch}')",
            expected=branch,
            refused=True,
        )
        return None
    ok, summary = review.receipt_state(repo_root, sha, require_base=review.DEFAULT_BASE_REF)
    if not ok:
        events.say(
            "ship.refused_head_moved",
            f"ship: refusing — HEAD moved since the review ({summary})",
            sha=sha,
            refused=True,
        )
        return None
    return sha


def _pre_push_checks(repo_root: Path, branch: str) -> bool:
    """Every refusal that must clear before anything leaves the machine.

    One function rather than three inline blocks because they are one policy —
    nothing is pushed unless the commit was reviewed, this branch's handoff
    holds, and every gate is green — and because :func:`ship_main`'s job is the
    SEQUENCE (preflight, checks, push, PR) rather than the individual verdicts.

    THE ORDER IS CHEAPEST-FIRST, and the first two are ahead of the gates
    deliberately. A failing gate is fixed by an amend, which moves the SHA and
    invalidates whatever receipt existed — so asking the cheap questions after
    four gate runs would spend minutes to learn something that was already
    decided. Neither cheap check has an ordering hazard of its own: `.agent/` is
    gitignored, so fixing a handoff writes no commit and cannot move the SHA the
    receipt is for.
    """
    from kb_setup import review

    ok, summary = review.receipt_state(
        repo_root, review.head_sha(repo_root), require_base=review.DEFAULT_BASE_REF
    )
    events.say("ship.review", f"==> review: {summary}", reviewed=ok)
    if not ok:
        events.say(
            "ship.refused_unreviewed",
            "ship: refusing — not pushing an unreviewed commit",
            refused=True,
        )
        return False

    if not _handoff_holds(repo_root, branch):
        return False

    if not run_gates(repo_root):
        events.say("ship.refused_gates", "ship: gates failed — not pushing", refused=True)
        return False
    return True


def ship_main(repo_root: Path, *, title: str | None = None) -> int:
    """Gate, push, and open a PR for the current branch; return an exit code."""
    branch = _ship_preflight(repo_root)
    if branch is None:
        return 1

    # `branch` is the name `_ship_preflight` already validated — not "", not
    # "main", not detached. Threading it through rather than re-reading HEAD is
    # what keeps `_handoff_holds` off `current_branch`, whose rc-only read
    # reports an UNBORN branch as unreadable (#144, found by the cold lane).
    if not _pre_push_checks(repo_root, branch):
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
        events.say("ship.push_failed", f"ship: push failed\n{out}", rc=rc, sha=sha, branch=branch)
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
        events.say(
            "ship.upstream_unset",
            f"ship: pushed {sha[:12]}, but could not set upstream tracking "
            f"(non-fatal; run `git branch -u origin/{branch}`): "
            f"{out_upstream.strip()[:200]}",
            sha=sha,
            branch=branch,
            fatal=False,
        )

    return _open_or_update_pr(repo_root, branch, title)


def land_main(repo_root: Path, pr_number: int) -> int:
    """Await terminal checks, refuse an unreviewed head, squash-merge pinned, sync main.

    Four steps, and the one-line version named only two. In order: give the
    checks a BOUNDED chance to reach a terminal state (:func:`await_terminal`);
    refuse unless every binding check is green; refuse a head with no
    `kb-review` receipt covering the whole branch (``require_base`` —
    `origin/main`, per :data:`review.DEFAULT_BASE_REF`); then squash-merge
    pinned to the SHA that was verified.

    The receipt refusal is the step worth naming here rather than leaving to the
    body comment: it is what makes `land` a backstop for a PR that reached the
    remote without going through `ship`, and a summary that omits a gate reads
    as a gate that does not exist. (#57)
    """
    # Wait for a TERMINAL state, never for quota. Advisory checks still cannot
    # block the merge — but a verdict that arrives ten seconds later was never
    # read, and reading it is free.
    # THE line §9d named as the cost of deferring this conversion: `kb-land`
    # would have gone silent through its entire check-wait. It stays first, and
    # it stays progressive.
    events.say(
        "land.await",
        f"==> waiting for terminal check state: {await_terminal(pr_number)}",
        pr=pr_number,
    )

    green, summary = checks_state(pr_number)
    events.say("land.checks", f"==> checks: {summary}", pr=pr_number, green=green)
    if not green:
        events.say(
            "land.refused_not_green",
            f"land: refusing — PR #{pr_number} is not green",
            pr=pr_number,
            refused=True,
        )
        return 1

    oid = pr_head_oid(pr_number)
    if not oid:
        events.say(
            "land.no_head_sha",
            f"land: could not read head SHA for PR #{pr_number}",
            pr=pr_number,
        )
        return 1

    # The PR head — not local HEAD. `ship` guards what IT pushes; a commit
    # pushed afterwards by any other route reaches the merge having been
    # reviewed by nothing. Receipts are machine-local, so this also means you
    # land from the machine you reviewed on; the message says so, because
    # otherwise the refusal looks like a bug rather than the design.
    from kb_setup import review

    # `require_base` here as well as in `ship`. Without it `land` accepted a
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
    reviewed, detail = review.receipt_state(repo_root, oid, require_base=review.DEFAULT_BASE_REF)
    events.say("land.review", f"==> review: {detail}", pr=pr_number, reviewed=reviewed, sha=oid)
    if not reviewed:
        events.say(
            "land.refused_unreviewed",
            f"land: refusing — PR #{pr_number}'s head is unreviewed. Run the "
            f"`kb-review` skill against it, or land from the machine that did.",
            pr=pr_number,
            sha=oid,
            refused=True,
        )
        return 1

    events.say(
        "land.merging",
        f"==> merging PR #{pr_number} pinned to {oid[:12]}",
        pr=pr_number,
        sha=oid,
    )

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
        events.say(
            "land.merge_failed",
            f"land: merge failed (head may have moved since the check)\n{out}",
            pr=pr_number,
            sha=oid,
            rc=rc,
        )
        return 1

    for cmd in (["git", "checkout", "main"], ["git", "pull", "--ff-only"]):
        rc, out = _run(cmd, cwd=repo_root)
        if rc != 0:
            # `merged=True` is the field that matters: the PR IS on main and only
            # the local sync failed, so a reader of the rc alone would draw the
            # opposite conclusion from the one the text states.
            events.say(
                "land.sync_failed",
                f"land: merged, but local sync failed at `{' '.join(cmd)}`\n{out}",
                pr=pr_number,
                merged=True,
                argv=list(cmd),
                rc=rc,
            )
            return 1

    events.say(
        "land.ok",
        f"land: OK — PR #{pr_number} merged, main synced",
        pr=pr_number,
        sha=oid,
    )
    return 0
