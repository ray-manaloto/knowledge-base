# Copyright (c) 2026 Raymond Manaloto
"""Durable record of whether the last `kb-build` RAN AND FAILED (#397).

The stamp answers "was a graph built, and by which version". It cannot answer
"why is there no stamp", and those two causes are not the same finding:

* **never run** — a fresh clone. A scheduling item. `mise run kb-build`.
* **ran and failed** — a DEFECT. `mise run kb-build` will fail again.

`kb-currency-check` reported *"artifacts have never been stamped — rebuild
pending"* for both, and several handoffs in a row carried the resulting defect
as a to-do, which is what #397 is about. This is the same class
`persistence-gate-retry.md` names: *a tool reporting an outage in the words of
an authoritative answer.*

The record lives beside the stamp under `graphify-out/` — machine-local and
gitignored, like the stamp, because it describes THIS host's last attempt and
nothing a fresh clone should inherit.

Two directions are deliberately asymmetric:

* Writing is **best-effort**. Recording a failure must never replace the
  failure being recorded, so `record_failure` swallows its own IO errors.
* Reading **fails closed**. A record that exists but cannot be parsed still
  means a build ran and failed; degrading it to "never run" would restore
  exactly the confusion this module removes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import msgspec

#: Beside `graphify-out/.currency-stamp.json`, for the same reason it is there.
RECORD_NAME = ".build-failure.json"

_SCHEMA_VERSION = 1

#: A failure summary is a rendered exception and can be a 900-character detect
#: dump per source. Bounded so a pathological run cannot leave an unreadable
#: record; the full text was already printed by the run that failed.
_MAX_SUMMARY = 2000


class BuildFailure(msgspec.Struct, frozen=True):
    """One recorded `kb-build` failure on this host."""

    #: `""` when the record was present but unparsable — see `describe`.
    failed_at: str = ""
    stage: str = ""
    summary: str = ""


def record_path(repo_root: Path) -> Path:
    """Where this host's last-failure record lives."""
    return repo_root / "graphify-out" / RECORD_NAME


def record_failure(repo_root: Path, stage: str, summary: str) -> None:
    """Best-effort. Never raises: the caller is already propagating a failure."""
    path = record_path(repo_root)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        # Timezone-aware, always. A naive timestamp compares against an aware
        # one by raising, so an offsetless string here would abort whichever
        # future reader tried to age this record.
        "failed_at": datetime.now(UTC).isoformat(),
        "stage": stage,
        "summary": summary[:_MAX_SUMMARY],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError:
        return


def clear(repo_root: Path) -> None:
    """Best-effort removal, called only after a build actually succeeded."""
    try:
        record_path(repo_root).unlink(missing_ok=True)
    except OSError:
        return


def read(repo_root: Path) -> BuildFailure | None:
    """The recorded failure, or None when no build has failed here.

    A present-but-unreadable record returns an EMPTY `BuildFailure` rather than
    None. The existence of the file is the load-bearing fact; its contents only
    sharpen the message.
    """
    path = record_path(repo_root)
    try:
        raw = path.read_text()
    except OSError:
        return None
    try:
        decoded = json.loads(raw)
    except ValueError:
        return BuildFailure()
    if not isinstance(decoded, dict):
        return BuildFailure()
    return BuildFailure(
        failed_at=str(decoded.get("failed_at", "")),
        stage=str(decoded.get("stage", "")),
        summary=str(decoded.get("summary", "")),
    )


def describe(repo_root: Path) -> str | None:
    """The reader-facing clause for "there is no stamp", or None if none failed.

    Callers append this to their own header so each keeps its own voice; what
    they must not do is render the no-stamp state without asking here first.
    """
    failure = read(repo_root)
    if failure is None:
        return None
    when = failure.failed_at or "an unrecorded time"
    stage = f" at {failure.stage}" if failure.stage else ""
    detail = f": {failure.summary.splitlines()[0]}" if failure.summary else ""
    return (
        f"a build RAN AND FAILED{stage} ({when}) — this is a DEFECT, not a pending "
        f"rebuild; re-running `mise run kb-build` will fail again{detail}"
    )
