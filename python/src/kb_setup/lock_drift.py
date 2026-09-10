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

NATIVE FIRST, AND IT IS NATIVE — **`--json`, not the human report.** `mise lock
--dry-run` "writes lockfiles without installing tools" and previews what it would
change (`mise lock --help`, 2026.9.4); `--json` returns that preview as one
object per tool with `old_versions` and `new_versions`. This module does not
re-implement resolution; it runs that and reads what it says.

🔴 IT PARSED THE HUMAN REPORT UNTIL 2026-09-10 AND WAS BLIND TO AN ADDED TOOL.
A tool newly pinned in `mise.toml` and absent from `mise.lock` makes mise print
the `→ Dry run - would update:` HEADER plus per-platform `✓ node@24.0.0 for
linux-arm64` rows — and **nothing else**. Those rows are byte-identical in shape
to the resolution progress a fully-in-sync run prints, so the parser skipped them
(correctly, on the evidence it had) and reported `mise.lock agrees`. Armed three
ways against the real repo, cold review of `7b28f460`:

    clean                              -> "agrees"            rc=0   correct
    changed version (uv 0.12.8->.12)   -> "does not describe"  rc=1   correct
    ADDED tool (MISE_NODE_VERSION)     -> "agrees"            rc=0   *** WRONG ***

`mise lock --dry-run --json` answers all three unambiguously — `[]`,
`uv ['0.12.8'] -> ['0.12.12']`, `node [] -> ['24.0.0']` — because an addition is
`old_versions == []`, a fact the prose never states. The lesson is this module's
own subject one layer down: **the text report is a DERIVED VIEW, and a derived
view can drop a distinction the structured source keeps.** `use-tool-builtins.md`
does not stop at "ask the tool"; it means ask it for the answer, not the prose.

`--json` is present in `src/cli/lock.rs` at every `v2026.9.x` tag from **2026.9.0**
— this repo's `min_version.hard` floor — through 2026.9.4, checked against
GitHub with a bogus-tag 404 control arm. On a mise too old to know the flag the
run exits non-zero and this gate reports NOT_RUN, never a pass.

🔴 THE PART MISE DOES NOT DO IS THE EXIT CODE. Armed both directions on
2026-09-10 against the real repo:

    lock in sync (antigravity-cli 1.2.0)  -> 1 "would prune" line   rc=0
    lock at the shipped-broken 1.1.25     -> 2 "would prune" lines   rc=0

The OUTPUT discriminates; the exit code never does. That is this repo's most
familiar shape — `hk test` exits 0 when it runs nothing, `kb-currency` always
exits 0 — and it is why a gate here reads the report rather than the rc. A
version of this check that trusted `mise lock --dry-run`'s exit status would be
green on the exact commit that motivated it.

WHAT COUNTS AS DRIFT. Any tool whose previewed `old_versions` differ from its
`new_versions`: a stale version, a stale tool entry, an added one. mise emits an
entry only for a tool it would change, so a clean repo returns `[]` and there is
no narration left to filter — the whole class of "is this line a finding or is it
progress?" disappears with the text parse that raised it.

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

import json
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
#: `--json` is the second load-bearing flag, and the one a cold review of
#: `7b28f460` had to add: the human report cannot express "this tool has no lock
#: entry at all", so the check that read it was blind to an added pin. See the
#: module docstring's three arms.
_ARGV = ("mise", "lock", "--dry-run", "--json")

#: `--dry-run` is not bounded by mise itself and re-resolves every platform, so
#: it reaches the network. The task carries a `timeout` too; this is the inner
#: bound so a wedge is reported as a wedge rather than killed anonymously.
_TIMEOUT_S = 180


@dataclass(frozen=True, slots=True)
class Drift:
    """One tool whose lock entry mise would change."""

    name: str
    old: tuple[str, ...]
    new: tuple[str, ...]

    @property
    def verb(self) -> str:
        """`add` when the lock has no entry, `remove` when the config has none."""
        if not self.old:
            return "add"
        if not self.new:
            return "remove"
        return "update"

    def line(self) -> str:
        """The human row, rendered once so the report and the JSONL sink agree."""
        shown = " -> ".join(", ".join(v) or "(none)" for v in (self.old, self.new))
        return f"would {self.verb} {self.name}: {shown}"


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
    # STDOUT ONLY, now that the answer is JSON. The text version merged both
    # streams because it did not know which one carried the report; a JSON
    # document cannot survive having mise's warnings interleaved into it, and
    # merging them would turn every warning into a parse failure — i.e. into a
    # NOT_RUN on a run that answered perfectly well.
    return proc.stdout


def drift(output: str) -> list[Drift]:
    """Every tool whose lock entry mise's preview would change.

    Raises :class:`LockUnavailableError` when ``output`` is not the report. A
    run that printed something unparsable did not answer the question, and the
    empty list it would otherwise decay to is indistinguishable from a clean
    lockfile — the same collapse the exit code made before `36069fb0`, arriving
    by a different road.
    """
    try:
        entries = json.loads(output or "[]")
    except json.JSONDecodeError as exc:
        raise LockUnavailableError(
            f"`{' '.join(_ARGV)}` printed something that is not its JSON report: {exc}"
        ) from exc
    if not isinstance(entries, list):
        raise LockUnavailableError(
            f"`{' '.join(_ARGV)}` returned {type(entries).__name__}, not the expected list"
        )
    rows: list[Drift] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise LockUnavailableError(
                f"`{' '.join(_ARGV)}` returned a non-object entry: {entry!r}"
            )
        old = tuple(entry.get("old_versions") or ())
        new = tuple(entry.get("new_versions") or ())
        if old == new:
            # mise emits an entry only for a tool it would change, so this is
            # belt-and-braces — but a no-op entry reported as drift is how a
            # gate that fires always loses its readers, and the text parser this
            # replaced shipped exactly that bug once.
            continue
        rows.append(Drift(str(entry.get("name") or "?"), old, new))
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
        # drift() is INSIDE the try on purpose: an unparsable report is a
        # "could not ask", exactly like a crashed mise. Leaving it outside would
        # let a malformed answer raise past the handler and die as a traceback,
        # which in a gate run reads as the gate itself being broken.
        rows = drift(preview(repo_root))
    except LockUnavailableError as exc:
        events.warn("lock_drift.not_run", f"[lock-drift] COULD NOT ASK: {exc}", reason=str(exc))
        return Rc.NOT_RUN

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
