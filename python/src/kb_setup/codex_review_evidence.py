# Copyright (c) 2026 Raymond Manaloto
"""#750 Phase 1 — provenance evidence for a `codex review` attempt.

**Ray's ruling (2026-09-10, the scope that shipped): RECORD, DO NOT GATE.**
This module collects and stores evidence for any lane that CAN produce it,
and the receipt carries the evidence reference OR the honest label
`model-unverified`. Nothing here refuses a ship or a land — see
`docs/research/reports/2026-09-10-750-premise-verification.md` for why the
original wider (gating) design was refused before any code was written: the
`_all_reasons` enforcement point the issue proposed would have refused three
of the four cold review lanes, including the DEFAULT one, because only the
`codex review` invocation this module reads ever produces this evidence.
Gating is a later ticket, decided once real runs show which lanes can comply.

**Why the banner is NOT the observable.** `.claude/skills/kb-review/references/lanes.md`
already documents that the CLI banner's `model:` line names the PARENT session,
never the reviewer sub-agent it delegates to — for `codex review` the parent
thread takes no model turn at all. The real observable is the reviewer
sub-agent's OWN rollout file under `$CODEX_HOME/sessions/`, joined on BOTH
`session_meta.payload.source == {"subagent": "review"}` AND
`payload.parent_thread_id` equal to the banner's own `session id:` line —
measured live, 3 arms, 3-for-3, on codex-cli 0.154.0
(`docs/research/reports/2026-09-10-codex-model-provenance-advisor.md` F1-F8).

**Schema isolation — this is the ONE adapter that reads codex's own rollout
format.** Everything downstream (the receipt, `_all_reasons`, `kb-ship`/
`kb-land`) reads only the flattened, versioned `CodexReviewEvidence` record
this module writes to `.agent/kb/review/evidence/` — never `turn_context` or
`session_meta` directly. That keeps the dependency on codex's internal schema
at REVIEW time, where a failure is cheap (one attempt's evidence is
`model-unverified`), rather than at SHIP time, where it would be an outage.
`ADAPTER_VERSION` is bumped, and this module requalified against the
installed `codex-cli`, on any rollout-shape change — see
`schemas/codex-review-evidence.schema.json`'s own field comments for what was
actually measured on this host on 2026-09-10 versus what is inferred by
symmetry from the pinned Rust source.

**Result contract.** :func:`resolve_reviewer_model` returns a tagged union —
:class:`Resolved` | :class:`Unavailable` | :class:`Error` — never `None`,
never an empty list, never a default success. `Unavailable` means the
resolver looked properly and the evidence was not there (a data gap, not a
bug); `Error` means the resolver itself broke while looking. Under Phase 1
both are RECORDED outcomes, not failures: :func:`capture_and_persist` writes
a `CodexReviewEvidence` record for every one of the three, and
:func:`receipt_reference` reduces all but `resolved` to the honest label
`model-unverified`.

**Never substituted.** The requested model (`args.model`) and the banner's
own model are both recorded (`requested_model`, and the banner is what
produces `parent_session_id`), but `resolved_model` is set ONLY from a
matched child rollout's own `turn_context.model` — see
:func:`_resolve_child`. `turn_models` keeps EVERY model-bearing turn, not
just the first, so a later turn changing model is a recorded fact rather
than a silently dropped one.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import msgspec

from kb_setup.currency import sync
from kb_setup.generated.codex_review_evidence import (
    CodexReviewEvidence,
    ErrorKind,
    OutcomeKind,
    ReviewCompletion,
    UnavailableReason,
)
from kb_setup.review import RECEIPT_DIR

#: Bumped, and this adapter requalified against the installed codex-cli, on
#: any change to what it reads out of `session_meta`/`turn_context`/`event_msg`.
ADAPTER_VERSION = 1

SCHEMA_VERSION = 1

#: `.agent/kb/review/evidence/` — a sibling of `RECEIPT_DIR`'s own `reports/`,
#: machine-local for the same reason every other `.agent/kb/review/**` path is
#: (`agent-artifact-conventions.md`): it proves what THIS machine observed.
EVIDENCE_DIR = RECEIPT_DIR / "evidence"

#: Strips the bold/color escapes `_run_review`'s tee may have captured — the
#: banner is written with `.style(self.bold)` (`event_processor_with_human_output.rs`),
#: which emits ANSI when stdout is styled. Matching on the un-styled text only
#: would silently miss a styled run.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

#: `"{key}: {value}"`, one per line — `config_summary_entries` pushes
#: `("session id", session_id)` last and `print_config_summary` renders every
#: entry as `eprintln!("{key}: {value}")`
#: (`sources/codex/codex-rs/exec/src/event_processor_with_human_output.rs:219-221,469-471`).
#: A codex session id is a UUIDv7: 36 hex-and-hyphen characters.
_SESSION_ID_RE = re.compile(r"^session id:\s*([0-9a-fA-F-]{36})\s*$", re.MULTILINE)

#: Bounded retries against `$CODEX_HOME/sessions/` persistence lag — the
#: reviewer sub-agent's rollout can still be flushing when `_spawn` returns.
#: 6 * 0.5s = 3s added at most, negligible beside a review that runs minutes.
_RETRY_ATTEMPTS = 6
_RETRY_DELAY_SECONDS = 0.5

#: Diagnostics is a bounded free-text field (`schemas/codex-review-evidence.schema.json`);
#: this is the code-side half of that bound. MUST NOT carry prompt text or
#: credentials — only paths, counts, and short messages.
_MAX_DIAGNOSTICS = 4096


@dataclass(frozen=True)
class CodexAttempt:
    """What `_run_review` knows the moment `_spawn` returns, before resolution.

    Collection-time facts only — no read of codex's rollout schema happens to
    produce this; that is entirely :func:`resolve_reviewer_model`'s job, kept
    separate so a resolution failure never taints what was actually observed
    about the subprocess itself.
    """

    attempt_id: str
    codex_home: str
    cli_version: str
    requested_model: str | None
    requested_effort: str | None
    base_ref: str
    subprocess_rc: int
    timed_out: bool
    output_path: Path | None


def capture_attempt(
    *,
    requested_model: str | None,
    requested_effort: str | None,
    base_ref: str,
    subprocess_rc: int,
    timed_out: bool,
    output_path: Path | None,
) -> CodexAttempt:
    """Build a :class:`CodexAttempt` from what the caller already knows.

    `codex_home` reads `$CODEX_HOME` from the environment — NEVER hardcoded to
    `~/.codex` and never re-derived — because a subprocess spawned with
    `env=os.environ.copy()` (`codex_run.py:314`) sees whatever the PARENT's
    environment set, and this repo has already set `CODEX_HOME` for a
    subprocess elsewhere (`skillopt_reviewed.py:824`).

    `cli_version` reuses :func:`kb_setup.currency.sync.observed_version` rather
    than a second ad-hoc `subprocess.run(["codex", "--version"])` —
    `use-tool-builtins.md`: don't reimplement what this repo already has.
    """
    codex_home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    cli_version = sync.observed_version("codex") or "unknown"
    return CodexAttempt(
        attempt_id=str(uuid.uuid4()),
        codex_home=codex_home,
        cli_version=cli_version,
        requested_model=requested_model,
        requested_effort=requested_effort,
        base_ref=base_ref,
        subprocess_rc=subprocess_rc,
        timed_out=timed_out,
        output_path=output_path,
    )


@dataclass(frozen=True)
class Resolved:
    """A unique reviewer turn was found and its model read."""

    record: CodexReviewEvidence


@dataclass(frozen=True)
class Unavailable:
    """The resolver looked properly and the evidence was not there.

    A data gap, never a resolver bug — see :class:`Error` for that.
    """

    reason: UnavailableReason
    diagnostics: str


@dataclass(frozen=True)
class Error:
    """The resolver itself failed while trying to look."""

    kind: ErrorKind
    diagnostics: str


#: No `None`, no empty list, no default-success — every resolution names
#: exactly one of these three.
ReviewEvidenceResult = Resolved | Unavailable | Error


def _parse_banner_session_id(output_path: Path) -> str | None:
    """Return the banner's `session id:` value from a `--output` tee, or None.

    None means "the tee was READ and held no session id". **A read FAILURE
    raises `OSError`**, so the caller reports it as `Error` rather than folding
    it into `Unavailable`.

    🔴 THE FIRST VERSION FOLDED THEM and called the fold deliberate: *"an
    unreadable tee is `Unavailable`, not `Error`: the tee file existing (or not)
    is exactly the fact `--output` being omitted also produces"*. A cold
    antigravity review of `3cc9c93a` rejected that and was right — those are two
    different facts:

        --output never passed    -> we did not ASK. Nothing is wrong.
        --output passed, EACCES  -> we asked and the environment refused.

    Collapsing them records an environment fault as a non-fault, and Phase 1
    exists to record ACCURATELY so Phase 2 can decide what to gate on. A
    poisoned `Unavailable` count is exactly what makes that later decision wrong.

    The module already knew better sixty lines down: `_candidate_children` has an
    `os.scandir` preflight precisely so a permission failure at `sessions_root`
    cannot masquerade as "no children found". One module, one class, two answers
    — the comment defending the weaker one is what stopped it being re-read.
    """
    text = output_path.read_text(encoding="utf-8", errors="replace")
    text = _ANSI_RE.sub("", text)
    match = _SESSION_ID_RE.search(text)
    return match.group(1) if match else None


def _sessions_root(codex_home: str) -> Path:
    return Path(codex_home) / "sessions"


def _read_jsonl(path: Path) -> list[dict[str, Any]] | None:
    """Return every well-formed JSON line in `path`, or None if it is unreadable.

    A malformed or truncated LINE is skipped, not fatal — a rollout still being
    flushed can have a partial final line, and losing one line must not lose
    every line before it. An unreadable FILE (permissions, vanished mid-scan)
    is None, which the caller distinguishes from "read fine, found nothing".
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    records: list[dict[str, Any]] = []
    for raw_line in raw.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _candidate_children(sessions_root: Path, parent_session_id: str) -> list[Path]:
    """Every rollout under `sessions_root` whose FIRST line binds to `parent_session_id`.

    Binding is BOTH `payload.parent_thread_id == parent_session_id` AND
    `payload.source == {"subagent": "review"}` — measured live
    (`docs/research/reports/2026-09-10-codex-model-provenance-advisor.md` F4),
    not one or the other. Only the first line is read per candidate file
    (`session_meta` is always first), so this scan stays cheap even with years
    of history under `sessions/`.

    **Raises `OSError` on a permission failure at `sessions_root` ITSELF** —
    measured: `Path.rglob` silently SKIPS a nested directory it cannot list
    rather than raising, so a bare `rglob` here would turn "sessions/ itself
    is unreadable" into the same `[]` as "genuinely no rollout exists", and
    the caller could never distinguish `Unavailable` from `Error`. The
    explicit `os.scandir` preflight is what makes that distinction real.
    """
    if not sessions_root.is_dir():
        return []
    with os.scandir(sessions_root) as _preflight:
        next(_preflight, None)
    hits: list[Path] = []
    for path in sorted(sessions_root.rglob("rollout-*.jsonl")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
        except OSError as exc:
            # 🔴 NOT `continue`. A candidate we cannot READ is not a candidate
            # that failed to MATCH, and skipping it turns "the one matching child
            # is unreadable" into "zero children found" — an environment fault
            # reported as an ordinary absence. Same class as the `rglob` hazard
            # this function's own preflight exists for. Found by a cold
            # antigravity review of `3cc9c93a`.
            raise OSError(f"could not read candidate rollout {path}: {exc}") from exc
        first_line = first_line.strip()
        if not first_line:
            continue
        try:
            record = json.loads(first_line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "session_meta":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("parent_thread_id") != parent_session_id:
            continue
        if payload.get("source") != {"subagent": "review"}:
            continue
        hits.append(path)
    return hits


def _turn_models(records: list[dict[str, Any]]) -> list[str]:
    """Every non-empty `turn_context.model`, in file order — not just the first.

    A later turn changing model must be a recorded fact, not something a
    first-turn-only read silently drops (FAIL-arm "lane/model agreement" in
    the advisor's table).
    """
    models: list[str] = []
    for record in records:
        if record.get("type") != "turn_context":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        model = payload.get("model")
        if isinstance(model, str) and model:
            models.append(model)
    return models


def _completion(records: list[dict[str, Any]]) -> ReviewCompletion:
    """Return the LAST `task_complete` event's shape, or `unknown` if none exists.

    **Measured, not inferred**, against a real rollout on this host
    (2026-09-10): a review whose reviewer model was rejected by the API left
    exactly one `event_msg` of `payload.type == "task_complete"`, with
    `last_agent_message: null` and a populated `error` object. **The success
    shape is inferred by symmetry**, not independently measured this session:
    `sources/codex/codex-rs/core/src/tasks/review.rs:170-174` reads
    `task_complete.last_agent_message` to parse the review's own findings on
    the success path, which only makes sense if that field is populated then.
    A rollout with NO `task_complete` event at all — observed on a review that
    completed normally but whose child file this adapter read before the
    event flushed — is `unknown`, never silently read as `complete`.
    """
    outcome = ReviewCompletion.unknown
    for record in records:
        if record.get("type") != "event_msg":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "task_complete":
            continue
        has_error = bool(payload.get("error"))
        has_message = bool(payload.get("last_agent_message"))
        outcome = (
            ReviewCompletion.aborted if has_error or not has_message else ReviewCompletion.complete
        )
    return outcome


def _resolve_child(
    attempt: CodexAttempt, parent_session_id: str, child_path: Path
) -> ReviewEvidenceResult:
    records = _read_jsonl(child_path)
    if records is None:
        return Error(ErrorKind.resolver_io_error, f"could not read {child_path}"[:_MAX_DIAGNOSTICS])
    models = _turn_models(records)
    if not models:
        has_turn_context = any(r.get("type") == "turn_context" for r in records)
        if not has_turn_context:
            return Unavailable(
                UnavailableReason.no_turn_context,
                f"{child_path} has zero turn_context records"[:_MAX_DIAGNOSTICS],
            )
        return Unavailable(
            UnavailableReason.missing_model_field,
            f"{child_path}'s turn_context record(s) carry no model field"[:_MAX_DIAGNOSTICS],
        )
    resolved_model = models[-1]
    completion = _completion(records)
    record = CodexReviewEvidence(
        schema_version=SCHEMA_VERSION,
        adapter_version=ADAPTER_VERSION,
        attempt_id=attempt.attempt_id,
        codex_home=attempt.codex_home,
        cli_version=attempt.cli_version,
        requested_model=attempt.requested_model,
        requested_effort=attempt.requested_effort,
        base_ref=attempt.base_ref,
        subprocess_rc=attempt.subprocess_rc,
        timed_out=attempt.timed_out,
        output_path=str(attempt.output_path) if attempt.output_path else None,
        outcome=OutcomeKind.resolved,
        parent_session_id=parent_session_id,
        child_rollout_path=str(child_path),
        turn_models=models,
        resolved_model=resolved_model,
        review_completion=completion,
        unavailable_reason=None,
        error_kind=None,
        diagnostics=None,
    )
    return Resolved(record)


def resolve_reviewer_model(
    attempt: CodexAttempt,
    *,
    attempts: int = _RETRY_ATTEMPTS,
    delay: float = _RETRY_DELAY_SECONDS,
) -> ReviewEvidenceResult:
    """Resolve `attempt`'s reviewer sub-agent model, or say precisely why not.

    Reads ONLY `attempt.output_path` (the banner) and `$CODEX_HOME/sessions/`
    (the join target) — never the requested or banner model as a substitute,
    per the tagged-union contract this function exists to keep honest.
    """
    if attempt.output_path is None:
        return Unavailable(
            UnavailableReason.no_output_flag,
            "no --output flag; the banner (and its session id) was never captured",
        )
    try:
        parent_session_id = _parse_banner_session_id(attempt.output_path)
    except OSError as exc:
        # A tee we were TOLD to read and could not is the environment refusing,
        # not `--output` being omitted. See the function's docstring.
        return Error(
            ErrorKind.resolver_io_error,
            f"could not read the tee at {attempt.output_path}: {exc}"[:_MAX_DIAGNOSTICS],
        )
    if not parent_session_id:
        return Unavailable(
            UnavailableReason.banner_session_id_unavailable,
            f"no 'session id:' line found in {attempt.output_path}"[:_MAX_DIAGNOSTICS],
        )
    sessions_root = _sessions_root(attempt.codex_home)
    if not sessions_root.is_dir():
        return Unavailable(
            UnavailableReason.codex_home_unresolvable,
            f"{sessions_root} does not exist"[:_MAX_DIAGNOSTICS],
        )
    return _await_single_child(attempt, parent_session_id, sessions_root, attempts, delay)


def _await_single_child(
    attempt: CodexAttempt,
    parent_session_id: str,
    sessions_root: Path,
    attempts: int,
    delay: float,
) -> ReviewEvidenceResult:
    """Retry-scan `sessions_root` for exactly one bound child, then resolve it.

    Split out of :func:`resolve_reviewer_model` so its own early-return guards
    (no `--output`, no banner, no `$CODEX_HOME`) stay countable separately from
    this loop's three possible endings (resolved, ambiguous, exhausted).
    """
    last_io_error: str | None = None
    for attempt_index in range(max(1, attempts)):
        try:
            hits = _candidate_children(sessions_root, parent_session_id)
        except OSError as exc:
            last_io_error = str(exc)
            hits = []
        if len(hits) == 1:
            return _resolve_child(attempt, parent_session_id, hits[0])
        if len(hits) > 1:
            named = ", ".join(str(h) for h in hits)
            return Unavailable(
                UnavailableReason.ambiguous_child_rollout,
                f"{len(hits)} rollouts bind to parent {parent_session_id}: {named}"[
                    :_MAX_DIAGNOSTICS
                ],
            )
        if attempt_index < attempts - 1:
            time.sleep(delay)

    if last_io_error is not None:
        return Error(ErrorKind.resolver_io_error, last_io_error[:_MAX_DIAGNOSTICS])
    return Unavailable(
        UnavailableReason.no_matching_child_rollout,
        (
            f"no rollout under {sessions_root} bound to parent {parent_session_id} "
            f"after {attempts} attempt(s)"
        )[:_MAX_DIAGNOSTICS],
    )


def build_record(attempt: CodexAttempt, result: ReviewEvidenceResult) -> CodexReviewEvidence:
    """Merge `attempt` (collection) and `result` (resolution) into one record.

    The ONE place both halves combine. `Resolved` already carries a complete
    record from :func:`_resolve_child`; `Unavailable`/`Error` are flattened
    here rather than in the resolver, keeping :func:`resolve_reviewer_model`'s
    return type free of the on-disk schema's field names.
    """
    if isinstance(result, Resolved):
        return result.record
    outcome = OutcomeKind.unavailable if isinstance(result, Unavailable) else OutcomeKind.error
    return CodexReviewEvidence(
        schema_version=SCHEMA_VERSION,
        adapter_version=ADAPTER_VERSION,
        attempt_id=attempt.attempt_id,
        codex_home=attempt.codex_home,
        cli_version=attempt.cli_version,
        requested_model=attempt.requested_model,
        requested_effort=attempt.requested_effort,
        base_ref=attempt.base_ref,
        subprocess_rc=attempt.subprocess_rc,
        timed_out=attempt.timed_out,
        output_path=str(attempt.output_path) if attempt.output_path else None,
        outcome=outcome,
        parent_session_id=None,
        child_rollout_path=None,
        turn_models=[],
        resolved_model=None,
        review_completion=None,
        unavailable_reason=result.reason if isinstance(result, Unavailable) else None,
        error_kind=result.kind if isinstance(result, Error) else None,
        diagnostics=result.diagnostics[:_MAX_DIAGNOSTICS],
    )


def evidence_path(repo_root: Path, attempt_id: str) -> Path:
    """Where one attempt's record is written — keyed by `attempt_id` alone.

    Deliberately NOT keyed by commit SHA or receipt lane: collection happens
    inside `codex_run.py`, a general-purpose lane runner with no notion of
    `review.py`'s receipt vocabulary (#750 M4 named exactly this coupling
    risk). `cli.py`'s receipt writer, which DOES know sha/lane, references
    this file by the attempt id a human or orchestrating agent copies from
    `_run_review`'s own stderr line into `--evidence`.
    """
    safe_id = "".join(c for c in attempt_id if c.isalnum() or c == "-") or "unknown"
    return repo_root / EVIDENCE_DIR / f"evidence-{safe_id}.json"


def persist(repo_root: Path, record: CodexReviewEvidence) -> Path:
    """Write `record` to disk atomically and return its path.

    Write-to-temp-then-replace: a caller reading `evidence_path` mid-write
    must never see a half-written JSON file, since `Path.replace` is atomic on
    the same filesystem (POSIX `rename(2)`) — matching "publish evidence
    atomically" (advisor Q4 Recovery).
    """
    path = evidence_path(repo_root, record.attempt_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = msgspec.json.format(msgspec.json.encode(record).decode(), indent=2)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def receipt_reference(record: CodexReviewEvidence) -> str:
    """The string a receipt's `--evidence` flag should carry for `record`.

    `resolved` -> the attempt id (resolvable back to the persisted record via
    :func:`evidence_path`). Every other outcome -> the honest label
    `model-unverified` — retired as the FINAL remedy (the full design this
    module descends from), kept as the Phase 1 default for anything this
    adapter could not resolve.
    """
    if record.outcome is OutcomeKind.resolved:
        return record.attempt_id
    return "model-unverified"


def capture_and_persist(
    repo_root: Path,
    *,
    requested_model: str | None,
    requested_effort: str | None,
    base_ref: str,
    subprocess_rc: int,
    timed_out: bool,
    output_path: Path | None,
) -> CodexReviewEvidence | None:
    """Capture, resolve, and persist one attempt's evidence — best-effort.

    The ONE broad catch in this module (`pyproject.toml`'s BLE001 exemption
    names it): a Phase 1 provenance side-channel must never turn a working
    review into a broken one, so any unexpected failure here is reported to
    stderr and swallowed rather than propagated into `_run_review`'s own
    return value. Every function this calls already returns a typed
    `Unavailable`/`Error` for the failures it anticipates; this guard is only
    for what it does not.
    """
    try:
        attempt = capture_attempt(
            requested_model=requested_model,
            requested_effort=requested_effort,
            base_ref=base_ref,
            subprocess_rc=subprocess_rc,
            timed_out=timed_out,
            output_path=output_path,
        )
        result = resolve_reviewer_model(attempt)
        record = build_record(attempt, result)
        persist(repo_root, record)
    except Exception as exc:
        print(
            f"kb-codex --review: evidence capture failed unexpectedly: {exc}",
            file=sys.stderr,
        )
        return None
    print(
        f"kb-codex --review: evidence {record.outcome.value} — "
        f"reference {receipt_reference(record)!r} ({evidence_path(repo_root, record.attempt_id)})",
        file=sys.stderr,
    )
    return record


__all__ = [
    "ADAPTER_VERSION",
    "SCHEMA_VERSION",
    "CodexAttempt",
    "Error",
    "Resolved",
    "ReviewEvidenceResult",
    "Unavailable",
    "build_record",
    "capture_and_persist",
    "capture_attempt",
    "evidence_path",
    "persist",
    "receipt_reference",
    "resolve_reviewer_model",
]
