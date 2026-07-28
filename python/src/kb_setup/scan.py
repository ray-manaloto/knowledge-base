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
_SCAN_ERROR_MARKERS = (" ERR ", " FTL ")

#: The fixed point the receipt uses, so the range scanned and the range reviewed
#: are the same range. `ship` passes `require_base="main"` to
#: `review.receipt_state` for the same reason.
DEFAULT_BASE = "main"

#: The only accepted argv shape: exactly ``--base <ref>``.
_BASE_ARGV_LEN = 2


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
    it, and the two failure paths that matter — a non-zero rc and an unparsable
    value — are both already handled as "could not ask".
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
        return 1, f"git: {exc}"
    return proc.returncode, proc.stdout or ""


def range_base(repo_root: Path, base: str = DEFAULT_BASE) -> str:
    """Return the cutoff commit for the scan, or "" if it cannot be resolved.

    The merge-base against ``base``, but resolved against ``origin/<base>``
    FIRST when that ref exists. The question this gate asks is "what will the
    push publish", and `ship` pushes `<sha>:refs/heads/<branch>` — a raw SHA,
    which carries its **entire ancestry**.

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
    for ref in (f"origin/{base}", base):
        rc, _ = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if rc != 0:
            continue
        rc, out = _git(repo_root, "merge-base", "--", ref, "HEAD")
        if rc == 0 and out.strip():
            return out.strip()
    return ""


def commits_in_range(repo_root: Path, base_sha: str) -> int:
    """Return how many commits ``base_sha..HEAD`` holds, or -1 if unreadable."""
    rc, out = _git(repo_root, "rev-list", "--count", f"{base_sha}..HEAD")
    if rc != 0:
        return -1
    try:
        return int(out.strip())
    except ValueError:
        return -1


def _gitleaks_cmd(repo_root: Path, base_sha: str) -> list[str]:
    """Build the gitleaks invocation for ``base_sha..HEAD``.

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
        f"{base_sha}..HEAD",
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
        # colours its log level even when stdout is a pipe (it does not
        # auto-detect), so the raw bytes are `\x1b[31mERR\x1b[0m` and a plain
        # `" ERR "` match finds nothing — a detector that could only ever say
        # "no error". Its own flag, rather than an ANSI-stripping regex here.
        "--no-color",
    ]


def _run_gitleaks(repo_root: Path, base_sha: str, span: str) -> tuple[bool, str]:
    """Run the scan over ``base_sha..HEAD`` and translate its exit code.

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
            _gitleaks_cmd(repo_root, base_sha),
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


def scan_range(repo_root: Path, base: str = DEFAULT_BASE) -> tuple[bool, str]:
    """Scan every commit in ``base..HEAD`` for secrets; return ``(ok, summary)``.

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

    base_sha = range_base(repo_root, base)
    if not base_sha:
        return False, f"could not resolve a merge-base against '{base}' — refusing to claim clean"

    count = commits_in_range(repo_root, base_sha)
    if count < 0:
        return False, f"could not count commits in {base_sha[:12]}..HEAD"
    if count == 0:
        return True, f"no commits in {base_sha[:12]}..HEAD — nothing to scan"

    # "a range of N commits", not "N commits scanned": gitleaks prints its own,
    # SMALLER count (it skips commits whose diff adds nothing — a pure deletion,
    # for instance), and two different numbers in one report read as a bug.
    # This one is the range size, which is the number the reader is choosing to
    # push.
    span = f"{base_sha[:12]}..HEAD (a range of {count} commit{'s' if count != 1 else ''})"
    return _run_gitleaks(repo_root, base_sha, span)


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
