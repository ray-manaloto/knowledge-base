"""Scan the COMMIT RANGE a ship would push, not just the tree it would leave.

Every other secret check in this repo asks about the working tree. `hk`'s
`gitleaks` step is file-list-driven by design — it is handed `{{ files }}` — so
a blob that exists only in an intermediate commit is not a file it ever opens.
The review lanes have the same shape of hole from the other side: they read
``git diff <fixed-point>...HEAD``, an ENDPOINT diff, and
`review._delta_paths` compares two trees.

So a file added in one commit and deleted in a later one is invisible to the
lanes AND to the scanner, while `mise run kb-ship` pushes **every commit on the
branch** to a public remote. `kb-land` squash-merges, so `main` is safe; the
exposure is the pushed branch, and GitHub retains it after the branch is
deleted. That is #67, and this module is option (1) from it.

Not hypothetical. The round that filed #67 committed three live credentials
into a tracked file and caught them by REVIEW, before `ship` — no gate saw
them. Had the same content been added and reverted mid-branch, nothing would
have looked at it at all.

`gitleaks git --log-opts` is the built-in for exactly this (`use-tool-builtins.md`);
there is no hand-rolled range walk here and there must not be one.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_GIT_TIMEOUT = 30

#: gitleaks reads the whole range's diffs, so the cost scales with the bytes in
#: them, not the commit count. Generous because the failure this bounds is a
#: wedge rather than slowness, and because the upper bound is genuinely unknown:
#: the only measurement taken is **0.36s for a one-commit range**.
_SCAN_TIMEOUT = 600

#: gitleaks exits 0 when clean and `--exit-code` when it finds something. That
#: default is **1, which is also what it exits on a FATAL ERROR** — measured: a
#: missing config file fatals with rc=1, indistinguishable from a leak. The first
#: version of this module took the default and duly reported `SECRETS FOUND` for
#: a config that would not load. Its own test caught it.
#:
#: So the findings code is MOVED to 2 with the tool's own flag, and 1 rejoins the
#: "could not ask" class alongside 127 and a timeout. Three arms, all measured on
#: gitleaks 8.30.1: leaks → 2, clean → 0, missing config → 1. No string-matching
#: on gitleaks' output, which would be the hand-rolled alternative
#: (`use-tool-builtins.md`).
_CLEAN = 0
_LEAKS = 2

#: gitleaks' log levels for "something went wrong". Their presence means the
#: scan did not complete, REGARDLESS of the exit code.
#:
#: This is the blocking defect round 1 found, and it is the failure mode this
#: whole module claims to be immune to. `gitleaks git` shells out to `git log
#: -p`; when that fails it logs the error, reports **"0 commits scanned … no
#: leaks found"**, and exits **0**. Mapping rc=0 to "no secrets" therefore
#: turned any machine-local git misconfiguration into a permanently green,
#: permanently blind gate.
#:
#: Reproduced here, three arms, gitleaks 8.30.1, with a `.gitattributes`
#: `diff=` driver whose `textconv` command does not exist (the attribute must
#: be live across the WHOLE range — a first attempt that added it in a later
#: commit did not fire, and read as a refutation):
#:   * control, no driver         → rc=2, `1 commits scanned`, leak found
#:   * broken driver              → rc=0, `ERR [git] fatal: …`, `0 commits scanned`
#:   * deletion-only range, clean → rc=0, `0 commits scanned`, and NO `ERR`
#:
#: That third arm is why this matches the ERROR LINES and not the commit count.
#: The reviewer's proposed fix was to compare gitleaks' scanned count against
#: the range size — but a legitimate branch that only deletes files also scans
#: zero commits, so that check would refuse honest work. Right diagnosis, wrong
#: remedy; only the third arm separated them.
#:
#: KNOWN FALSE-POSITIVE SURFACE, recorded rather than discovered later: gitleaks
#: emits `ERR error="stderr is not empty"` for ANY output git writes to stderr,
#: so a benign advisory refuses the ship. That is the direction to prefer — it
#: reports too much rather than looking away — but it is a real cost, and the
#: remedy is to fix the advisory, never to narrow this tuple. It is not
#: env-defeatable in the other direction either: `GITLEAKS_LOG_LEVEL=fatal` and
#: friends still emit the ERR lines; only an explicit `-l fatal` suppresses
#: them, and `_gitleaks_cmd` never passes one. (Silent-failure lane, round 2.)
#:
#: What actually pins this tuple is the END-TO-END arm
#: (`tests/test_scan.py::test_a_failed_git_log_is_not_reported_as_clean`), not
#: the truthiness assertion beside it — narrowing it to `()` reddens that test.
#: Blind spots it does NOT cover, none of which log an error: an archive past
#: `--max-archive-depth`, a root `.gitleaksignore`, and honoured
#: `gitleaks:allow` comments.
_SCAN_ERROR_MARKERS = (" ERR ", " FTL ")

#: The same fixed point the receipt uses. The two ranges are RELATED, not
#: identical, and the difference is deliberate: `range_base` reduces the
#: ``origin/<base>`` and ``<base>`` merge-bases to their common ancestor while
#: `review.base_sha` resolves the literal ref, so whenever local ``main`` is
#: ahead of the remote the scan's range is strictly WIDER than the lanes'.
#:
#: That asymmetry is correct — the lanes review what the branch added, the
#: scanner must cover what the push publishes — but this comment used to claim
#: they were "the same range", which stopped being true the moment the remote
#: preference landed. (Standards lane, round 2: a claim carried without its
#: condition.)
DEFAULT_BASE = "main"

#: The only accepted argv shape: exactly ``--base <ref>``.
_BASE_ARGV_LEN = 2

#: `_git`'s rc when the SUBPROCESS ITSELF failed — outside git's exit-code space
#: on purpose, so "could not ask" can never be mistaken for one of git's
#: answers. See `_git`.
_GIT_EXEC_FAILED = -1

#: `git rev-parse --verify --quiet <ref>` exits 1, and ONLY 1, for "no such
#: ref". 128 is a real error and `_GIT_EXEC_FAILED` is a dead subprocess;
#: neither is an answer, and neither may be read as absence.
_GIT_REF_ABSENT = 1


def config_path(repo_root: Path) -> Path:
    """Return the gitleaks config this scan must use."""
    return repo_root / ".gitleaks.toml"


def _git(repo_root: Path, *args: str) -> tuple[int, str]:
    """Run a git command; return ``(rc, stdout)`` with stderr kept SEPARATE.

    Separate on purpose, unlike `pr._run` and `review._git` which merge the two.
    Every caller here consumes the output as DATA — a SHA, a count — and git
    writes advisories to stderr on commands that succeed (a detached-HEAD notice,
    a hint, a `core.hooksPath` warning). Merged, one of those is concatenated
    onto the SHA `range_base` returns; `commits_in_range` then fails to parse the
    result, returns -1, and the ship aborts on a false alarm. (Cold lane, round 1.)

    stderr is dropped rather than returned: no caller has anything to say about
    it, and the failure paths that matter are handled as "could not ask".

    A FAILED SUBPROCESS RETURNS :data:`_GIT_EXEC_FAILED`, not 1. It used to
    return 1 — which is also git's "the ref does not exist" *and* git's
    "not an ancestor", both of which are ANSWERS. So every caller that branched
    on rc==1 read a crashed subprocess as a definite reply, and the docstring
    here claimed those paths were "handled as could not ask" while they were
    handled as answers. Measured by the silent-failure lane in round 3: an
    injected `OSError` on the existence probe moved the cutoff forward and
    dropped an unpushed commit below it. A sentinel outside git's exit-code
    space makes the two distinguishable at every call site at once.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _GIT_EXEC_FAILED, f"git: {exc}"
    return proc.returncode, proc.stdout or ""


def range_base(repo_root: Path, base: str = DEFAULT_BASE, head: str = "HEAD") -> str:
    """Return the cutoff commit for the scan, or "" if it cannot be resolved.

    The merge-base against ``base`` AND against ``origin/<base>``, reduced to
    the single commit that is an ancestor of both. The question this gate asks
    is "what will the push publish", and `ship` pushes `<sha>:refs/heads/
    <branch>` — a raw SHA, which carries its **entire ancestry**.

    This paragraph used to say the cutoff was "resolved against ``origin/<base>``
    FIRST", which described neither the code that followed it nor the behaviour
    anyone wants. (Standards lane, round 3.)

    So a commit sitting on local ``main`` that has not reached the remote is
    published by that push while sitting BELOW a merge-base taken against local
    ``main`` — never scanned, and now public. Resolving against the
    remote-tracking ref moves the cutoff back past it.

    This docstring previously claimed the failure direction was safe, on the
    grounds that "a stale local main WIDENS the range". That is true only when
    local ``main`` is BEHIND the remote. The dangerous case is the opposite one
    — local ``main`` AHEAD, with unpushed commits — and the sentence was written
    as if only one direction existed. (Cold lane, round 1.)

    A stale remote-tracking ref (no recent `git fetch`) still errs wide: it can
    only be older than the real remote head, so the range grows. Scanning
    commits that are already public is noise; missing one that is not is the
    defect.

    ``--`` terminates option parsing: a base spelled like a flag is otherwise
    read by git as an option, and the command silently answers a different
    question. Same guard, same reason, as `review.base_sha`.
    """
    bases: list[str] = []
    for ref in (f"refs/remotes/origin/{base}", base):
        rc, _ = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if rc == _GIT_REF_ABSENT:
            continue  # genuinely no such ref here; the other one may exist.
        if rc != 0:
            # 128, or a dead subprocess. NOT an answer, and reading it as
            # "absent" silently narrows the cutoff — measured by injecting an
            # `OSError` on this call with local `main` one unpushed commit
            # ahead: the cutoff moved forward and dropped that commit below it,
            # while `ship` still publishes its whole ancestry. (Silent-failure
            # lane, round 3.)
            return ""
        rc, out = _git(repo_root, "merge-base", "--", ref, head)
        if rc != 0 or not out.strip():
            # The ref EXISTS and merge-base still failed — unrelated histories,
            # a corrupt object, a shallow clone. Refuse rather than falling
            # through to the local ref, which would NARROW the range.
            return ""
        bases.append(out.strip())

    if not bases:
        return ""
    if len(bases) == 1:
        return bases[0]

    # The merge-base OF THE CANDIDATES — an ancestor of both by construction,
    # hence the widest of the available cutoffs.
    #
    # This replaces a `--is-ancestor` loop that kept whichever candidate the
    # comparison endorsed. Two defects, both found in round 3 and one of them
    # OBSERVED LIVE: `--is-ancestor` exits 0/1/**128**, and `_git` used to map
    # its own exceptions onto 1, so "could not ask" was acted on as "no" and the
    # NEWER base survived. A test flaked exactly once at `d3e054b` on that path
    # and passed on three re-runs, which is the shape of defect that gets
    # re-run rather than read. The loop also assumed the two candidates were
    # comparable at all; nothing guaranteed it.
    #
    # One call, and its failure is a refusal rather than a silent preference.
    rc, out = _git(repo_root, "merge-base", "--", *bases)
    if rc != 0 or not out.strip():
        return ""
    return out.strip()


def commits_in_range(repo_root: Path, base_sha: str, head: str = "HEAD") -> int:
    """Return how many commits ``base_sha..head`` holds, or -1 if unreadable."""
    rc, out = _git(repo_root, "rev-list", "--count", f"{base_sha}..{head}")
    if rc != 0:
        return -1
    try:
        return int(out.strip())
    except ValueError:
        return -1


def _gitleaks_cmd(repo_root: Path, base_sha: str, head: str = "HEAD") -> list[str]:
    """Build the gitleaks invocation for ``base_sha..head``.

    ``--config`` is passed EXPLICITLY even though `mise.toml` exports
    ``GITLEAKS_CONFIG`` at the same path. Two reasons, both measured on
    gitleaks 8.30.1:

    * ``--config`` outranks the env var (arms: ``GITLEAKS_CONFIG=allow-all``
      plus ``-c allow-none`` → rc=1, i.e. allow-none won). So this pins the
      config regardless of what any ambient value says — including a value from
      a different repo, which is what `mise.toml`'s ``{{config_root}}`` would
      resolve to if this ever ran from elsewhere.
    * the handoff for this round recorded the opposite ("``GITLEAKS_CONFIG``
      OUTRANKS ``--config``"). It does not. What actually happened there is that
      **the mise SHIM re-applies mise's env**, so ``env -u GITLEAKS_CONFIG
      gitleaks …`` does not unset it and three probes silently ran the repo's
      own config. Control arm: the same command against ``$(mise which
      gitleaks)`` honours the prefix. Recorded because the wrong cause implies
      the wrong fix.

    ``--redact`` is not cosmetic. This gate exists because a credential reached
    a tracked file; a gate that then PRINTS that credential to the terminal
    writes it into the session transcript on disk, which is one of the two ways
    the original tokens were exposed. The finding's file, line, and rule id are
    what a human needs, and those are still printed.
    """
    return [
        "gitleaks",
        "git",
        str(repo_root),
        "--log-opts",
        # `--diff-merges=first-parent` closes an EVIL-MERGE hole, and it is #67's
        # own scenario surviving #67's own gate. `git log -p` emits no patch for
        # a merge commit, so content introduced by the merge RESOLUTION —
        # present in neither parent — is scanned by nothing, and gitleaks logs
        # no error, so the round-1 marker check does not fire either.
        #
        # Measured, and the first attempt at the repro did NOT fire: putting the
        # token on a side branch leaves it in an ordinary commit that is itself
        # in the range, which is caught. The real case needs a conflict resolved
        # by writing the token. With that:
        #   without the flag → rc=0, "3 commits scanned", NO LEAKS   ← the hole
        #   with the flag    → rc=2, "4 commits scanned", leak found
        # (Silent-failure lane, round 2.)
        #
        # KNOWN COST, recorded rather than left to be hit: when a branch merges
        # `origin/<base>` IN, that merge's first-parent diff is everything the
        # base brought — commits OUTSIDE the rev-list range, scanned anyway. So
        # a pre-existing secret on `main` blocks the ship with a message that
        # accuses the branch, and there is no branch-side remedy. Measured: a
        # secret present only in main's history goes rc=0/"no leaks" → rc=2.
        # Fail-closed, which is the direction to prefer, and `--diff-merges`
        # changes only whether merges emit a patch — never which commits are in
        # the range (that would be `--first-parent`, which this is not).
        # (Spec lane, round 3.)
        f"{base_sha}..{head} --diff-merges=first-parent",
        "--config",
        str(config_path(repo_root)),
        # See `_LEAKS`: this separates "found something" from "could not run",
        # which gitleaks' default of 1 for both does not.
        "--exit-code",
        str(_LEAKS),
        # `--redact` WITH `--verbose`, which is the pairing that makes this
        # usable. Verbose alone prints the secret; redact alone prints only
        # "leaks found: 1" with no file, line, or rule, so the summary's "see
        # the findings above" pointed at nothing — measured on the end-to-end
        # arm. Together they print the finding's location and rule id with the
        # value replaced by REDACTED. hk's own gitleaks builtin uses the same
        # pair.
        "--redact",
        "--verbose",
        "--no-banner",
        # REQUIRED for `_SCAN_ERROR_MARKERS` to work, not cosmetic. gitleaks
        # colours its log level even when the stream is a pipe rather than a
        # terminal, so the raw bytes are `\x1b[31mERR\x1b[0m` and a plain
        # `" ERR "` match finds nothing — a detector that could only ever say
        # "no error". Its own flag, rather than an ANSI-stripping regex here.
        #
        # "the stream", not "stdout": gitleaks writes its whole log to STDERR
        # (measured, piped: stdout 0 bytes, stderr 281). An earlier version of
        # this comment said stdout, which would have made the marker check work
        # only by the accident of `_run_gitleaks` merging both. It merges them
        # deliberately; the comment was the part that was wrong. (Spec lane,
        # round 2 — a stated condition that does not hold.)
        "--no-color",
    ]


def _run_gitleaks(
    repo_root: Path, base_sha: str, span: str, head: str = "HEAD"
) -> tuple[bool, str]:
    """Run the scan over ``base_sha..head`` and translate its exit code.

    The gitleaks binary is PINNED in `mise.toml`. It is therefore not allowed to
    be missing here, and a missing one is DRIFT rather than a skip — hence no
    "is it installed" early return, which would report green for a scan that
    never happened.

    ``GITLEAKS_CONFIG`` is stripped from the child env even though `--config` is
    passed. Redundant today, and deliberately so: if a future gitleaks release
    flips the documented precedence, the explicit flag and the absent env var
    agree rather than one silently overriding the other.
    """
    env = {k: v for k, v in os.environ.items() if k != "GITLEAKS_CONFIG"}
    try:
        proc = subprocess.run(
            _gitleaks_cmd(repo_root, base_sha, head),
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=_SCAN_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"gitleaks could not run ({exc}) — refusing to claim clean"

    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()

    # BEFORE the exit code, because rc=0 is exactly what this case returns. See
    # `_SCAN_ERROR_MARKERS`: gitleaks logs the failure of its own `git log -p`
    # and then exits clean, so trusting rc alone is what made the gate blind.
    #
    # Deliberately checked on the CLEAN path too rather than only when something
    # looks wrong — a scan that did not run cannot report a leak either, so an
    # error alongside rc=2 is still worth saying out loud.
    failed = [line for line in detail.splitlines() if any(m in line for m in _SCAN_ERROR_MARKERS)]
    if failed:
        reported = "\n".join(failed[:10])
        return False, (
            f"gitleaks reported an error while scanning {span} — refusing to claim clean "
            f"(it exits 0 after a failed `git log`, so rc={proc.returncode} means nothing here)"
            f"\n{reported}"
        )

    if proc.returncode == _CLEAN:
        return True, f"no secrets in {span}"
    if proc.returncode == _LEAKS:
        return False, f"SECRETS FOUND in {span} — see the findings above\n{detail}"
    return False, f"gitleaks exited rc={proc.returncode} — could not scan {span}\n{detail[:800]}"


def scan_range(repo_root: Path, base: str = DEFAULT_BASE, head: str = "HEAD") -> tuple[bool, str]:
    """Scan every commit in ``base..head`` for secrets; return ``(ok, summary)``.

    Fails CLOSED. An unresolvable base, an unreadable commit count, and a
    gitleaks exit code that is neither "clean" nor "leaks" all return False:
    each of them means the question was never answered, and "could not ask" is
    not "nothing is wrong" (`probes-need-a-control-arm.md`).

    An EMPTY range is a genuine pass, not a refusal — that is what shipping a
    branch with nothing new on it looks like, and gitleaks reports it honestly
    ("0 commits scanned"). Said explicitly in the summary so a zero-commit run
    can never be mistaken for a zero-finding one.
    """
    config = config_path(repo_root)
    if not config.is_file():
        # gitleaks fatals on this anyway, but with rc=1 — which used to be read
        # as "leaks found". Checked here so the message names the real cause
        # instead of accusing the branch of carrying a secret.
        return False, f"no gitleaks config at {config} — refusing to claim clean"

    base_sha = range_base(repo_root, base, head)
    if not base_sha:
        return False, f"could not resolve a merge-base against '{base}' — refusing to claim clean"

    count = commits_in_range(repo_root, base_sha, head)
    if count < 0:
        return False, f"could not count commits in {base_sha[:12]}..{head[:12]}"
    if count == 0:
        return True, f"no commits in {base_sha[:12]}..{head[:12]} — nothing to scan"

    # "a range of N commits", not "N commits scanned": gitleaks prints its own,
    # SMALLER count (it skips commits whose diff adds nothing — a pure deletion,
    # for instance), and two different numbers in one report read as a bug.
    # This one is the range size, which is the number the reader is choosing to
    # push.
    span = f"{base_sha[:12]}..{head[:12]} (a range of {count} commit{'s' if count != 1 else ''})"
    return _run_gitleaks(repo_root, base_sha, span, head)


def main(repo_root: Path, argv: list[str] | None = None) -> int:
    """`kb-scan-range` entry point: scan the range and return an exit code."""
    args = list(argv or [])
    base = DEFAULT_BASE
    if args:
        # REJECT anything not understood, rather than ignoring it. The first
        # version scanned for `--base` and silently dropped everything else, so
        # `-- --bas main` printed a green line having quietly scanned the
        # default — a fail-OPEN in the one module whose whole contract is
        # failing closed. (Spec lane, round 1.)
        if args[0] != "--base" or len(args) != _BASE_ARGV_LEN:
            print(f"kb-setup scan-range [--base REF] — unrecognised: {' '.join(args)}")
            return 2
        base = args[1]

    ok, summary = scan_range(repo_root, base)
    print(f"scan-range: {summary}")
    return 0 if ok else 1
