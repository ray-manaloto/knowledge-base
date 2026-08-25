# Copyright (c) 2026 Raymond Manaloto
"""Durable record of whether the last `kb-build` RAN AND FAILED (#397).

The stamp answers "was a graph built, and by which version". It cannot answer
"why is there no stamp", and those two causes are not the same finding:

* **never run** — a fresh clone. A scheduling item. `mise run kb-build`.
* **ran and failed** — a DEFECT, until re-verified. The record does not
  re-test its own cause, so `describe()` no longer asserts the next attempt
  fails too — a code fix can land without the record knowing it.

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
* Every read and write names `encoding="utf-8"` explicitly. Left to the
  locale, a non-ASCII exception message could raise `UnicodeEncodeError` while
  recording, and undecodable bytes could raise `UnicodeDecodeError` while
  reading — and neither is an `OSError`, so both escaped the handlers below.

* Reading **fails closed**. A record that exists but cannot be READ OR parsed
  still means a build ran and failed; degrading it to "never run" would restore
  exactly the confusion this module removes. Only `FileNotFoundError` means
  absent — every other `OSError` (a `PermissionError`, a mode change, a
  directory in its place) is a record we could not read, not a record that
  is not there. The first version caught every `OSError` and returned None,
  which failed OPEN against its own stated contract. (Cold lane, P2.)

* A record present means the LAST BUILD ATTEMPT FAILED, whatever else is on
  disk. That is why both consumers ask here BEFORE they look at the stamp: a
  failing detect preflight aborts before `graph._clear_stamp` runs, so a
  machine that has ever built successfully keeps its old stamp through a
  failed rebuild — and a stamp-first reader then reports OK for a build that
  is broken. That is #397 itself, wearing a new coat, inside the fix for it.
  (Cold lane, P1, reproduced with a control arm.)
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import msgspec

#: Beside `graphify-out/.currency-stamp.json`, for the same reason it is there.
RECORD_NAME = ".build-failure.json"

_SCHEMA_VERSION = 1

#: The build did not fail — a person stopped it. Recorded, because an
#: interrupted build leaves no stamp either and calling that "never run" is the
#: same lie in a smaller hat; reported differently, because nothing about Ctrl-C
#: says the build is broken or that re-running it will fail again. (Cold lane, P2.)
INTERRUPTED = "interrupted"

#: An ordinary build failure — a defect. Not asserted to recur: see `describe`.
FAILED = "failed"

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
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        # Swallowed so the build's own failure still propagates — but NOT
        # silently. Without this line the durable record fails to write, every
        # later check says "never run", and nothing anywhere says why: the exact
        # ambiguity this module exists to remove, restored by its own error
        # path. stderr, so a piped stdout cannot lose it. (Cold lane, P2.)
        _warn(f"could not record the build failure at {path}: {exc}")
        return


def _warn(message: str) -> None:
    """Diagnostics must never become the failure they are describing.

    `print` to stderr can itself raise — a BrokenPipeError is an OSError — and
    this is called from inside an `except` while a build exception is already
    propagating. A raise here would REPLACE that exception with an unrelated IO
    one, hiding the real reason the build failed. (Cold lane round 2, P2.)
    """
    try:
        print(f"[kb-build] WARNING: {message}", file=sys.stderr)
    except OSError:
        return


def clear(repo_root: Path) -> None:
    """Remove the record after a build SUCCEEDS. Best-effort, but never silent.

    A surviving record now outranks the stamp, so a failure to remove one is a
    real consequence and not a shrug — it is why `describe` also accepts the
    stamp's `built_at` and supersedes the record independently of this.
    """
    try:
        record_path(repo_root).unlink(missing_ok=True)
    except OSError as exc:
        _warn(f"could not clear the stale build-failure record: {exc}")
        return


def read(repo_root: Path) -> BuildFailure | None:
    """The recorded failure, or None when no build has failed here.

    A present-but-unreadable record returns an EMPTY `BuildFailure` rather than
    None. The existence of the file is the load-bearing fact; its contents only
    sharpen the message.
    """
    path = record_path(repo_root)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # The ONLY OSError that means "no build has failed here".
        return None
    except OSError, UnicodeError:
        # Present but unreadable — a permission change, a directory in its
        # place, bytes that are not UTF-8. Fails CLOSED, per this contract.
        #
        # `UnicodeError` is listed explicitly because it is NOT an `OSError` —
        # it is a `ValueError` — so `except OSError` alone let a decode error
        # propagate out of `read()` and abort the whole currency check rather
        # than answer it. Reproduced: undecodable bytes in the record raised
        # `UnicodeDecodeError` straight through. Same class as the diagnostic
        # that could replace the build exception, through a door the first fix
        # did not close. (CodeRabbit, major.)
        return BuildFailure()
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


class Outcome(msgspec.Struct, frozen=True):
    """What a recorded build outcome MEANS, kept apart from how it reads.

    `kind` exists because the two are not the same verdict and a caller must not
    have to pattern-match on prose to tell them apart: a FAILURE is a defect and
    belongs in a drift bucket, an INTERRUPT is "nothing was verified" and belongs
    in a could-not-check one. The first version returned only the text, so both
    landed in DRIFT/BUILD_FAILED while the text said "not a defect" — the check
    contradicting itself in the same line. (Cold lane round 2, P2.)
    """

    kind: str
    text: str


def describe(repo_root: Path, *, stamp_built_at: str = "") -> Outcome | None:
    """The reader-facing verdict for a recorded outcome, or None if there is none.

    `stamp_built_at` is the successful build's own `built_at` from the stamp,
    when there is one. A record older than it has been SUPERSEDED: a build
    succeeded after that failure, so the failure is history.

    That parameter is the fix for the mirror of this module's first defect.
    `clear()` is best-effort, and once the record was made authoritative over the
    stamp, a `clear()` that failed left a successful build reporting a DEFECT
    forever, with no path back — reproduced by making `Path.unlink` raise.
    Comparing against the stamp SELF-HEALS: the next successful build supersedes
    the record whether or not the file could be removed.

    The comparison is deliberately STRICT (`>`), so an unparsable or
    same-second timestamp keeps REPORTING the failure. Note the CONDITION that
    follows: the stamp's `built_at` is written with `timespec="seconds"` and so
    truncates DOWN by up to a second, which means supersession needs about a
    second of real separation. Harmless for a build that takes minutes — and it
    is what a compressed same-second probe shows as "not superseded", which is
    the probe's artifact, not this function's defect. The two errors are not
    symmetric: wrongly ignoring a live failure reports OK for a broken build,
    which is #397 itself, while wrongly keeping a stale one reports a defect that
    a single successful build clears.

    The FAILED message itself does not claim to know the future. It used to
    read "re-running `mise run kb-build` will fail again" — a flat prediction
    from a note this function never re-tests. A record naming a file that no
    longer existed anywhere in the repo kept printing that exact sentence on
    every session start for three days, because nothing about reading a stale
    record on disk can know a fix landed since. The message now says the record
    does not re-test its own cause, and leaves the future to an actual re-run —
    still a DEFECT (a build genuinely failed, and this record still blocks until
    superseded), just not a promise about what has not been tried again.
    """
    failure = read(repo_root)
    if failure is None:
        return None
    if _superseded_by(failure, stamp_built_at):
        return None
    when = failure.failed_at or "an unrecorded time"
    detail = f": {failure.summary.splitlines()[0]}" if failure.summary else ""
    if failure.stage == INTERRUPTED:
        # Neither "DEFECT" nor "will fail again" follows from Ctrl-C, and
        # asserting them would make this module lie in the one direction it was
        # built to stop lying in. Still not "never run": no stamp was written.
        return Outcome(
            INTERRUPTED,
            f"a build was INTERRUPTED ({when}) and left no stamp — not a defect, "
            f"but nothing here was verified; re-run `mise run kb-build`{detail}",
        )
    stage = f" at {failure.stage}" if failure.stage else ""
    return Outcome(
        FAILED,
        f"a build RAN AND FAILED{stage} ({when}) — this is a DEFECT, not a pending "
        f"rebuild. This record does not re-test its own cause, so it is not a "
        f"guarantee the next attempt fails too — a fix can land without this "
        f"record knowing it. Only a fresh `mise run kb-build` can confirm whether "
        f"it still does{detail}",
    )


def _superseded_by(failure: BuildFailure, stamp_built_at: str) -> bool:
    """True iff a successful build was stamped strictly AFTER this failure."""
    if not stamp_built_at or not failure.failed_at:
        return False
    try:
        stamped = datetime.fromisoformat(stamp_built_at)
        failed = datetime.fromisoformat(failure.failed_at)
    except ValueError:
        return False
    # Both are written by this repo and both are tz-aware, but a hand-edited or
    # older stamp need not be — and `naive - aware` RAISES, which would abort the
    # whole check rather than answer it. Treat a naive value as unanswerable.
    if stamped.tzinfo is None or failed.tzinfo is None:
        return False
    return stamped > failed
