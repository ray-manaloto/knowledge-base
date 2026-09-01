# Copyright (c) 2026 Raymond Manaloto
"""Search what the agents actually did — `mise run kb-session-search`.

Ray, 2026-09-01, verbatim: *"i would like to get that setup so we can utilize
that for reviewing claude/codex sessions/telemetry"*.

WHY A TASK AND NOT A DOCUMENTED COMMAND. `agentsview`'s headline mode is
`agentsview serve`, a long-running local web UI — and a UI is the one shape this
repo cannot consume. `long-running-command-hangs.md` rule 2 forbids
`&`-detaching a local `mise run` (it gets reaped when the turn goes idle), and a
server gives an agent no bounded output to read. What an agent CAN consume is
the JSON surface beside it, which is what this wraps. The UI stays a plain
`agentsview serve` in `sources/REGISTRY.md`, deliberately un-wrapped.

THE GAP IT CLOSES. `kb-session-select` / `kb-session-review-archive` /
`kb-attribute-write` all read `~/.claude/projects/` and only that. Measured
2026-09-01 on this machine: 5,193 files there, against **2,658** under
`~/.codex/sessions/` and **978** under `~/.codex/archived_sessions/` that
nothing here has ever read. Since 2026-08-31 every lane in this repo runs on
codex, so the half of the evidence nobody could search was the half doing the
work.

WHAT THIS REFUSES TO DO, and it is the whole reason the module exists rather
than a `run =` line. `agentsview` reads a **mutable derived index**
(`~/.agentsview/sessions.db`), not the transcripts. So "0 results" has two
causes that look identical at the shell: the corpus genuinely lacks the term,
or the index was never built. The second one, reported as the first, is a false
evidentiary conclusion about a session — `probes-need-a-control-arm.md`'s exact
failure, with a database in the middle. Therefore:

* the sync runs FIRST, in the foreground, and a failing sync is `Rc.NOT_RUN`
  (127) — never an empty result list with rc 0;
* a zero-match search AFTER a green sync is `Rc.OK` with an explicit
  `"searched": true`, so a caller can tell "asked and got nothing" from "never
  asked".

`--reveal` IS REFUSED OUTRIGHT. `agentsview session search` redacts detected
secrets by default and `--reveal` unredacts them (probed against the installed
0.41.1). This repo denies credential-printing commands at the PreToolUse hook
(`secret_guard`, #441) precisely because a transcript is stored, searched and
fed onward; a task that could print one through a side door would be a hole in
that guard, not a feature.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from kb_setup.result import Rc

_BIN = "agentsview"

_FORCED_ENV = {
    # Anonymous daemon telemetry, opt-out only (its docs/configuration.md:1217).
    # Set HERE and not in the mise task, because enforcement must travel with
    # every repo-owned invocation — a task's `env` block protects exactly the
    # one call site that happens to go through it.
    "AGENTSVIEW_TELEMETRY_ENABLED": "0",
    # NOTE: `AGENTSVIEW_NO_DAEMON=1` was in this dict and has been REMOVED,
    # because the installed binary refutes the design it came from. Measured
    # 2026-09-01 against 0.41.1, each command's own argv, real exit codes:
    #
    #   usage daily --json              rc=0   direct SQLite
    #   session search <p> --json       rc=1   "daemon autostart is disabled"
    #   session list --limit 2 --json   rc=1   same
    #   stats / projects / health       rc=1   same
    #
    # Only `usage daily` reads SQLite directly. That contradicts the project's
    # own README, which annotates `session list` as *"read from the daemon if
    # warm, otherwise SQLite"* — so the doc is wrong, not this comment. The
    # daemon is therefore allowed to autostart; it is a local, loopback-bound
    # process the tool starts as an intrinsic consequence of the command the
    # user asked for. `agentsview daemon stop` ends it.
    #
    # The first probe of this LOOKED like it found four daemon-free commands.
    # It was broken: the classifier passed a whole command line through an
    # unquoted `$1`, and **zsh does not word-split unquoted parameters**, so
    # every multi-word case arrived as one argument and failed on flag parsing
    # rather than on the daemon — landing in the catch-all branch labelled
    # "DIRECT SQLITE". A probe whose negative and positive arms agree is broken.
    # Do not let it check for — or advertise — a newer version. `mise.toml`
    # owns this pin, and on 2026-09-01 BOTH `claude-code` and `mise` were found
    # to have self-updated out from under their pins on this machine. A pinned
    # tool that phones home about versions is one release away from joining
    # that list.
    "AGENTSVIEW_DISABLE_UPDATE_CHECK": "1",
}

_REFUSED_FLAGS = frozenset({"--reveal"})


def _env() -> dict[str, str]:
    """The parent environment plus the three settings a repo run must not lose."""
    return {**os.environ, **_FORCED_ENV}


_SYNC_TIMEOUT = 900
"""Seconds. `agentsview sync` walks every discovered session root.

Bounded because `long-running-command-hangs.md` requires it, and generously
because the first run is a cold index over what was measured on this machine as
**8,829** session files. A later run is incremental. A timeout here is reported
as `Rc.NOT_RUN`, exactly like a non-zero sync — an interrupted index is a stale
index, and this module's whole contract is that it never searches one silently.
"""

_SEARCH_TIMEOUT = 120
"""Seconds. A read against an already-built SQLite index."""


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[str] | None:
    """Run `args`, or return `None` if it exceeded `timeout`.

    `None` rather than a raised `TimeoutExpired` because every caller here
    treats a timeout and a failure the same way — refuse — and the distinction
    the module cares about is refuse-vs-answer, not how it failed.
    """
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            env=_env(),
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None


def _search_argv(binary: str, args: argparse.Namespace) -> list[str]:
    """Build the search argv.

    Split out of `main` because the filter list is the part that grows: every
    future flag is one more branch, and `main`'s job is the sync-then-search
    DECISION, not argument assembly.

    `--format json` is passed as two argv entries, which is not a detail worth
    losing: `agentsview` rejects `--format json` as a single argument with
    *"unknown flag: --format json"*, and one probe here did exactly that after
    zsh declined to word-split an unquoted variable.
    """
    argv = [binary, "session", "search", args.pattern, "--format", "json"]
    argv += ["--limit", str(args.limit)]
    for flag, value in (
        ("--agent", args.agent),
        ("--since", args.since),
        ("--project", args.project),
    ):
        if value:
            argv += [flag, value]
    if args.regex:
        argv.append("--regex")
    if args.include_children:
        argv.append("--include-children")
    return argv


def main(argv: list[str], repo_root: Path) -> int:
    """Sync the local index, then search it. Returns a `Rc`."""
    del repo_root  # reads only user-level session data; nothing repo-relative

    parser = argparse.ArgumentParser(
        prog="kb-session-search",
        description="Search Claude Code AND Codex session transcripts via agentsview.",
    )
    parser.add_argument("pattern", help="text or, with --regex, an RE2 pattern")
    parser.add_argument("--agent", help="filter by agent, e.g. claude or codex")
    parser.add_argument("--since", help="12h, 14d, 2w, 3m, 1y, or YYYY-MM-DD")
    parser.add_argument("--project", help="filter by project name")
    parser.add_argument("--limit", type=int, default=50, help="max results (max 500)")
    parser.add_argument("--regex", action="store_true", help="treat pattern as RE2")
    parser.add_argument(
        "--include-children",
        action="store_true",
        help="include subagent sessions (this repo's lanes ARE subagents)",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="search the index as-is; the result is then explicitly unfreshened",
    )
    args, extra = parser.parse_known_args(argv)

    refused = _REFUSED_FLAGS.intersection(extra)
    if refused:
        parser.error(
            f"refusing {' '.join(sorted(refused))}: it unredacts detected secrets, "
            "which `secret_guard` (#441) exists to prevent reaching a transcript"
        )

    binary = shutil.which(_BIN)
    if binary is None:
        print(
            f"{_BIN} is not on PATH. It is pinned in mise.toml; run:\n"
            f"  mise install 'github:kenn-io/agentsview@0.41.1'",
        )
        return Rc.NOT_RUN

    synced = False
    if not args.no_sync:
        sync = _run([binary, "sync"], _SYNC_TIMEOUT)
        if sync is None or sync.returncode != 0:
            # THE POINT OF THIS MODULE. A failed sync leaves a stale-or-absent
            # index, and searching it would return a number that reads as
            # evidence about a session. Refuse instead of answering.
            detail = (
                f"timed out after {_SYNC_TIMEOUT}s"
                if sync is None
                else f"rc={sync.returncode}\n{sync.stderr.strip()}"
            )
            print(
                "agentsview sync FAILED — refusing to search a stale or absent index, "
                "because an empty result would read as 'the sessions do not contain "
                f"this'.\n{detail}",
            )
            return Rc.NOT_RUN
        synced = True

    found = _run(_search_argv(binary, args), _SEARCH_TIMEOUT)
    if found is None or found.returncode != 0:
        detail = (
            f"timed out after {_SEARCH_TIMEOUT}s"
            if found is None
            else f"rc={found.returncode}\n{found.stderr.strip()}"
        )
        print(f"agentsview session search failed — {detail}")
        return Rc.NOT_RUN

    try:
        payload = json.loads(found.stdout or "null")
    except json.JSONDecodeError as exc:
        print(f"agentsview returned output that is not JSON: {exc}\n{found.stdout[:400]}")
        return Rc.NOT_RUN

    # `searched` is the field that makes a zero here readable. Without it a
    # caller cannot distinguish this from the two NOT_RUN paths above, which is
    # the entire distinction the module exists to preserve.
    print(
        json.dumps(
            {
                "searched": True,
                "synced": synced,
                "pattern": args.pattern,
                "results": payload,
            },
            indent=2,
        )
    )
    return Rc.OK
