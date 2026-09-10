# Copyright (c) 2026 Raymond Manaloto
"""Does `mise.lock` still describe what `mise.toml` pins? — `kb-setup lock-drift`.

WHY THIS EXISTS, and it is the most embarrassing possible reason. On 2026-09-10
this repo shipped `kb-graphify-catalog`, a gate whose entire subject is *a pin
move leaves its derived values behind*. **One commit later, in the same branch,
the `antigravity-cli` bump moved `mise.toml`, `currency.toml` and
`sources/antigravity-cli.manifest` and did not move `mise.lock`** — and all nine
gates, the new one included, went green over it and it merged (`6b3ab427`).

`mise.lock` is a derived value carried by nothing that checked it. So was the
catalog's `source_tree`. The class was not closed by naming it.

A SECOND drift was already there and had been for weeks: `mise.toml` pins
`"npm:@openai/codex" = "0.154.0"` while `mise.lock` carried
`[[tools.codex]] version = "0.149.1" backend = "aqua:openai/codex"` — an ORPHAN
from the backend change Ray ruled in #539, not merely a stale version. One
mechanism, two instances, zero gates.

NATIVE FIRST, AND IT IS NATIVE. `mise lock --dry-run` "writes lockfiles without
installing tools" and previews what it would change (`mise lock --help`,
2026.9.4). This module does not re-implement resolution; it runs that and reads
what it says. `use-tool-builtins.md` is satisfied by asking mise, and the custom
part is only the part mise does not do.

🔴 THE PART MISE DOES NOT DO IS THE EXIT CODE. Armed both directions on
2026-09-10 against the real repo:

    lock in sync (antigravity-cli 1.2.0)  -> 1 "would prune" line   rc=0
    lock at the shipped-broken 1.1.25     -> 2 "would prune" lines   rc=0

The OUTPUT discriminates; the exit code never does. That is this repo's most
familiar shape — `hk test` exits 0 when it runs nothing, `kb-currency` always
exits 0 — and it is why a gate here reads the report rather than the rc. A
version of this check that trusted `mise lock --dry-run`'s exit status would be
green on the exact commit that motivated it.

WHAT COUNTS AS DRIFT. Any previewed change to a tool ENTRY: a stale version, a
stale tool, an added one. A `--dry-run` line that mentions no tool is narration
and is ignored — mise prints per-platform resolution progress for every tool on
every run, and treating that as a finding would make the gate fire always, which
is how a gate loses its readers.

WHAT THIS CANNOT SEE, because a check that does not declare its blind spot gets
read as covering everything:

- **Checksums and URLs.** `mise lock` re-resolves them from the network; this
  gate runs `--dry-run` and reports what mise says, so a checksum mise cannot
  reach is a line this gate never receives rather than a mismatch it hides.
- **A lockfile that is wrong in the same way as the config.** It compares the
  two artifacts, never either against upstream. `kb-currency-check` owns that.
- **`uv.lock`.** Python's lock is `uv sync --locked`'s business and is checked
  by `[deps.uv]` at install time, not here.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import events
from kb_setup.result import Rc

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

#: The preview invocation. `--dry-run` is load-bearing: without it this WRITES
#: the lockfile, which would make the gate fix its own finding and report clean —
#: a check that repairs what it measures has measured nothing.
_ARGV = ("mise", "lock", "--dry-run")

#: A previewed change names a tool; narration does not. `prune` covers a stale
#: version and a stale tool, `add`/`update` the other direction.
#:
#: ANCHORED AT LINE START, after mise's `→ ` bullet. The first version said it was
#: "anchored on mise's own prefix" and used a bare `.search()` — true of the
#: STRING, false of the REGEX, so any line merely CONTAINING `Dry run - would`
#: matched. A cold review of `7f4035cd` read the comment against the line beneath
#: it and found they disagreed, which is the defect class this repo flags in
#: everyone else's code.
_CHANGE = re.compile(
    r"^\s*(?:→\s*)?Dry run - would (prune|add|update|remove)\b(?P<rest>.*)", re.IGNORECASE
)

#: `--dry-run` is not bounded by mise itself and re-resolves every platform, so
#: it reaches the network. The task carries a `timeout` too; this is the inner
#: bound so a wedge is reported as a wedge rather than killed anonymously.
_TIMEOUT_S = 180


@dataclass(frozen=True, slots=True)
class Drift:
    """One previewed change to a tool entry."""

    verb: str
    detail: str

    def line(self) -> str:
        """The human row, rendered once so the report and the JSONL sink agree."""
        return f"would {self.verb} {self.detail}"


class LockUnavailableError(Exception):
    """The question could not be asked — `Rc.NOT_RUN`, never a pass."""


def preview(repo_root: Path) -> str:
    """Run the native preview and return its merged output. Raises on NOT_RUN."""
    if not (repo_root / "mise.toml").is_file():
        raise LockUnavailableError("no mise.toml here")
    if not (repo_root / "mise.lock").is_file():
        # A missing lockfile is NOT drift — this repo could legitimately not
        # keep one. It is the absence of the thing being checked, so the honest
        # answer is "not run", not "clean" and not "everything drifted".
        raise LockUnavailableError("no mise.lock — nothing to compare the pins against")
    try:
        proc = subprocess.run(
            _ARGV,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LockUnavailableError(f"`{' '.join(_ARGV)}` did not complete: {exc}") from exc
    if proc.returncode != 0:
        # 🔴 THE THIRD STATE, and the first version of this module collapsed it
        # into "clean" — found by a cold review of `7f4035cd`.
        #
        # mise returns rc 0 whether the lock is in sync or five versions stale,
        # which is why the REPORT is the answer. But a mise that CRASHED — a bad
        # `mise.toml`, an unreachable backend, a wedged resolver — also prints no
        # "would" line, and the parser then sees zero changes and returns OK. A
        # broken environment would have read as perfectly in sync.
        #
        # "the rc cannot tell in-sync from stale" is TRUE and does not license
        # ignoring the rc. It is exactly `probes-need-a-control-arm.md` rule 4:
        # distinguish "answered no" from "never asked".
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "no output"
        raise LockUnavailableError(
            f"`{' '.join(_ARGV)}` exited {proc.returncode} — its report cannot be trusted: {tail}"
        )
    # stdout AND stderr: mise puts the dry-run report on one and its warnings on
    # the other, and which is which is not a contract worth depending on.
    return f"{proc.stdout}\n{proc.stderr}"


def drift(output: str) -> list[Drift]:
    """Every previewed tool-entry change in mise's report."""
    rows: list[Drift] = []
    for raw in output.splitlines():
        found = _CHANGE.search(raw)
        if not found:
            continue
        detail = found.group("rest").strip().removesuffix(":").strip()
        if not detail:
            # `→ Dry run - would update:` is a HEADER mise prints on every run,
            # followed by per-platform `✓ tool@version for <platform>` lines that
            # are resolution progress, not changes. Measured 2026-09-10: it
            # appears with the lockfile fully in sync. Counting it would make
            # this gate fire always, which is how a gate loses its readers — and
            # the first version of this parser did exactly that.
            continue
        rows.append(Drift(found.group(1).lower(), detail))
    return rows


def main(repo_root: Path, args: Sequence[str] | None = None) -> int:
    """0 clean, `Rc.FINDINGS` on drift, `Rc.NOT_RUN` when it could not look."""
    rest = list(args or [])
    if rest:
        events.fail(
            "lock_drift.bad_request",
            f"[lock-drift] unknown argument(s): {' '.join(rest)}",
            unknown=rest,
        )
        return Rc.BAD_REQUEST

    try:
        output = preview(repo_root)
    except LockUnavailableError as exc:
        events.warn("lock_drift.not_run", f"[lock-drift] COULD NOT ASK: {exc}", reason=str(exc))
        return Rc.NOT_RUN

    rows = drift(output)
    events.say(
        "lock_drift.examined",
        f"[lock-drift] mise previewed the lockfile — {len(rows)} tool entr(ies) would change",
        changes=len(rows),
    )
    for row in rows:
        events.warn("lock_drift.drift", f"[lock-drift] {row.line()}", verb=row.verb)
    if rows:
        events.fail(
            "lock_drift.findings",
            f"[lock-drift] mise.lock does not describe what mise.toml pins — "
            f"run `mise lock` and commit it ({len(rows)} entr(ies))",
            findings=len(rows),
        )
        return Rc.FINDINGS
    events.say("lock_drift.clean", "[lock-drift] mise.lock agrees with mise.toml")
    return Rc.OK
