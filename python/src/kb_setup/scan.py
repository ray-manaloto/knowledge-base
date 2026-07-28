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

#: gitleaks reads the whole range's diffs. Generous, because the failure this
#: bounds is a wedge, not slowness: measured at ~0.36s for a one-commit range,
#: and a branch is tens of commits.
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

#: The fixed point the receipt uses, so the range scanned and the range reviewed
#: are the same range. `ship` passes `require_base="main"` to
#: `review.receipt_state` for the same reason.
DEFAULT_BASE = "main"


def config_path(repo_root: Path) -> Path:
    """Return the gitleaks config this scan must use."""
    return repo_root / ".gitleaks.toml"


def _git(repo_root: Path, *args: str) -> tuple[int, str]:
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
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def range_base(repo_root: Path, base: str = DEFAULT_BASE) -> str:
    """Return the merge-base of ``base`` and HEAD, or "" if it cannot be resolved.

    Merge-base, not ``base`` itself, so the range is what the branch ADDED —
    matching `review.base_sha` and the ``<base>...HEAD`` the lanes read.

    A STALE local ``main`` widens the range rather than narrowing it (the
    merge-base moves backwards), so the failure direction here is scanning
    commits that are already on the remote. That is noise, not blindness, and it
    is the direction to prefer.

    ``--`` terminates option parsing: a base spelled like a flag is otherwise
    read by git as an option, and the command silently answers a different
    question. Same guard, same reason, as `review.base_sha`.
    """
    rc, out = _git(repo_root, "merge-base", "--", base, "HEAD")
    return out.strip() if rc == 0 else ""


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
    if "--base" in args:
        index = args.index("--base")
        if index + 1 >= len(args):
            print("kb-setup scan-range [--base REF]")
            return 2
        base = args[index + 1]

    ok, summary = scan_range(repo_root, base)
    print(f"scan-range: {summary}")
    return 0 if ok else 1
