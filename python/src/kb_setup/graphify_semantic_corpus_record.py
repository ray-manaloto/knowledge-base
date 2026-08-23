# Copyright (c) 2026 Raymond Manaloto
"""Review and atomically record semantic-corpus plan authority."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import NotRequired, Self, TypedDict, Unpack

import msgspec

from kb_setup import atomic, events, graphify_semantic_corpus_authority
from kb_setup.graphify_semantic_corpus import (
    AdvisoryCatalog,
    AuthorityRoots,
    ChunkLedger,
    CorpusExecutionConfig,
    ExclusionCatalog,
    PlanSourceOptions,
    PlanVerification,
    SourceInventory,
    SourcePin,
    admit_source,
    encode_canonical,
    plan_source,
    planned_max_output_tokens,
    sha256_path,
    verify_plan,
)

DECISION_DIGESTS = ("advisories_sha256", "exclusions_sha256")
IDENTITY_DIGESTS = ("plan_manifest_sha256", "execution_config_sha256")
PLAN_FILES = (
    "source-inventory.json",
    "advisories.json",
    "exclusions.json",
    "chunk-ledger.json",
    "execution-config.json",
    "manifest.json",
)

_DIGEST_FIELDS = (*IDENTITY_DIGESTS, *DECISION_DIGESTS)
_ALLOWED_CANDIDATE_REASONS = frozenset(
    {
        "plan-authority-mismatch",
        "plan-authority-unset",
        "cost-advisory-review-required",
        "provisional-input-decisions",
    }
)
_AUTHORITY_FILE = "graphify_semantic_corpus_authority.json"
_LEDGER = "docs/agents/graphify-semantic-corpus-authority-ledger.md"


class RecordReport(msgspec.Struct, frozen=True):
    """Complete review result for one candidate plan."""

    candidate: str
    staged: str
    canonical: str
    candidate_state: str
    candidate_reasons: tuple[str, ...]
    moved: tuple[str, ...]
    decision_moved: tuple[str, ...]
    recordable: bool
    accepted: bool
    authorized_after: bool | None
    digests_before: dict[str, str]
    digests_after: dict[str, str]
    delta: dict[str, object]
    superseded_dir: str | None
    ignored_extras: tuple[str, ...]


class _ReportBase(msgspec.Struct, frozen=True):
    candidate: str
    staged: str
    canonical: str
    candidate_state: str
    candidate_reasons: tuple[str, ...]
    moved: tuple[str, ...]
    decision_moved: tuple[str, ...]
    recordable: bool
    digests_before: dict[str, str]
    digests_after: dict[str, str]
    delta: dict[str, object]
    ignored_extras: tuple[str, ...]

    def finish(
        self,
        *,
        accepted: bool,
        authorized_after: bool | None,
        superseded_dir: str | None,
        reasons: tuple[str, ...] | None = None,
    ) -> RecordReport:
        return RecordReport(
            candidate=self.candidate,
            staged=self.staged,
            canonical=self.canonical,
            candidate_state=self.candidate_state,
            candidate_reasons=self.candidate_reasons if reasons is None else reasons,
            moved=self.moved,
            decision_moved=self.decision_moved,
            recordable=self.recordable,
            accepted=accepted,
            authorized_after=authorized_after,
            digests_before=self.digests_before,
            digests_after=self.digests_after,
            delta=self.delta,
            superseded_dir=superseded_dir,
            ignored_extras=self.ignored_extras,
        )


class _RecordContext(msgspec.Struct, frozen=True):
    repo_root: Path
    canonical_dir: Path
    authority_path: Path
    ledger_path: Path
    accept: bool
    accept_decision_change: frozenset[str]
    source_root: Path


class _LedgerInputs(msgspec.Struct, frozen=True):
    timestamp: str
    members: tuple[
        SourceInventory,
        AdvisoryCatalog,
        ExclusionCatalog,
        ChunkLedger,
        CorpusExecutionConfig,
    ]
    decision_moved: tuple[str, ...]
    before: dict[str, str]
    after: dict[str, str]
    head: str
    superseded: Path | None


class _RollbackState(msgspec.Struct, frozen=True):
    canonical_dir: Path
    superseded_dir: Path | None
    authority_path: Path
    authority_before: bytes
    ledger_path: Path
    ledger_before: bytes

    def restore(self) -> None:
        if self.superseded_dir is None:
            if self.canonical_dir.exists():
                shutil.rmtree(self.canonical_dir)
        elif self.superseded_dir.exists():
            if self.canonical_dir.exists():
                shutil.rmtree(self.canonical_dir)
            self.superseded_dir.replace(self.canonical_dir)
        atomic.write_text(self.authority_path, self.authority_before.decode("utf-8"))
        atomic.write_text(self.ledger_path, self.ledger_before.decode("utf-8"))


class _Transaction:
    def __init__(self, rollback: _RollbackState) -> None:
        self.rollback = rollback
        self.error: str | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, traceback
        if exc is None:
            return False
        self.rollback.restore()
        if not isinstance(exc, Exception):
            # KeyboardInterrupt / SystemExit: the state is restored, but the
            # interrupt is not this transaction's to swallow. Returning True here
            # would let a Ctrl-C mid-accept print a report and exit 1 as if the
            # run had merely failed (cold review, round 1).
            return False
        self.error = str(exc)
        return True


class _RecordPlanOptions(TypedDict):
    accept: NotRequired[bool]
    accept_decision_change: NotRequired[frozenset[str]]
    source_root: NotRequired[Path | None]


def _members(
    plan_dir: Path,
) -> tuple[
    SourceInventory,
    AdvisoryCatalog,
    ExclusionCatalog,
    ChunkLedger,
    CorpusExecutionConfig,
]:
    """Strictly decode the five typed plan members used by the delta."""
    inventory = msgspec.json.decode(
        (plan_dir / "source-inventory.json").read_bytes(),
        type=SourceInventory,
        strict=True,
    )
    advisories = msgspec.json.decode(
        (plan_dir / "advisories.json").read_bytes(),
        type=AdvisoryCatalog,
        strict=True,
    )
    exclusions = msgspec.json.decode(
        (plan_dir / "exclusions.json").read_bytes(),
        type=ExclusionCatalog,
        strict=True,
    )
    ledger = msgspec.json.decode(
        (plan_dir / "chunk-ledger.json").read_bytes(),
        type=ChunkLedger,
        strict=True,
    )
    config = msgspec.json.decode(
        (plan_dir / "execution-config.json").read_bytes(),
        type=CorpusExecutionConfig,
        strict=True,
    )
    return inventory, advisories, exclusions, ledger, config


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _authority(path: Path) -> AuthorityRoots:
    return msgspec.json.decode(path.read_bytes(), type=AuthorityRoots, strict=True)


def _authority_digests(authority: AuthorityRoots) -> dict[str, str]:
    return {name: getattr(authority, name) for name in _DIGEST_FIELDS}


def _plan_digests(plan_dir: Path) -> dict[str, str]:
    paths = {
        "plan_manifest_sha256": "manifest.json",
        "execution_config_sha256": "execution-config.json",
        "advisories_sha256": "advisories.json",
        "exclusions_sha256": "exclusions.json",
    }
    return {
        name: sha256_path(plan_dir / member) if (plan_dir / member).is_file() else "unavailable"
        for name, member in paths.items()
    }


def _member_view(
    members: tuple[
        SourceInventory,
        AdvisoryCatalog,
        ExclusionCatalog,
        ChunkLedger,
        CorpusExecutionConfig,
    ],
) -> dict[str, object]:
    inventory, _advisories, _exclusions, ledger, config = members
    return {
        "execution_config": {
            "claude_model": config.claude_model,
            "claude_version": config.claude_version,
            "deep_mode": config.deep_mode,
            "effort": config.effort,
            "graphify_commit": config.graphify_commit,
            "graphify_version": config.graphify_version,
            "max_total_cost_usd": config.max_total_cost_usd,
            "max_turns": config.max_turns,
            "resolved_model": config.resolved_model,
        },
        "chunk_ledger": {
            "chunk_count": len(ledger.chunks),
            "token_budget": ledger.token_budget,
            "unit_count": ledger.unit_count,
        },
        "source_inventory": {
            "admitted_estimated_tokens": inventory.admitted_estimated_tokens,
            "admitted_unit_count": inventory.admitted_unit_count,
            "duplicate_dropped_estimated_tokens": (inventory.duplicate_dropped_estimated_tokens),
            "duplicate_dropped_unit_count": inventory.duplicate_dropped_unit_count,
            "duplicate_groups": len(inventory.duplicate_groups),
            "source_commit": inventory.source_commit,
        },
    }


def _delta(candidate: Path, canonical: Path) -> dict[str, object]:
    try:
        candidate_view: object = _member_view(_members(candidate))
    except msgspec.DecodeError, OSError:
        candidate_view = "undecodable"
    if not canonical.exists():
        canonical_view: object = None
    else:
        try:
            canonical_view = _member_view(_members(canonical))
        except msgspec.DecodeError, OSError:
            canonical_view = "undecodable"
    return {"candidate": candidate_view, "canonical": canonical_view}


def _dedupe_summary(inventory: SourceInventory) -> str:
    groups = len(inventory.duplicate_groups)
    noun = "group" if groups == 1 else "groups"
    dropped_tokens = inventory.duplicate_dropped_estimated_tokens
    total_tokens = inventory.admitted_estimated_tokens + dropped_tokens
    ratio = dropped_tokens / total_tokens if total_tokens else 0.0
    return (
        f"duplicate-content: {groups} {noun} · "
        f"{inventory.duplicate_dropped_path_count} paths / "
        f"{inventory.duplicate_dropped_unit_count} units dropped · "
        f"{dropped_tokens:,} of {total_tokens:,} estimated tokens "
        f"({ratio:.1%}) not re-extracted · "
        f"admitted {inventory.admitted_unit_count} units / "
        f"{inventory.admitted_estimated_tokens:,} tokens"
    )


def _say_dedupe(plan_dir: Path) -> None:
    try:
        inventory = _members(plan_dir)[0]
    except msgspec.DecodeError, OSError:
        return
    events.say(
        "corpus_plan.dedupe",
        _dedupe_summary(inventory),
        groups=len(inventory.duplicate_groups),
        dropped_path_count=inventory.duplicate_dropped_path_count,
        dropped_units=inventory.duplicate_dropped_unit_count,
        dropped_tokens=inventory.duplicate_dropped_estimated_tokens,
        total_tokens=(
            inventory.admitted_estimated_tokens + inventory.duplicate_dropped_estimated_tokens
        ),
    )


def _copy_plan_members(source: Path, destination: Path) -> tuple[str, ...]:
    reasons: list[str] = []
    destination.mkdir(parents=True)
    for name in PLAN_FILES:
        path = source / name
        try:
            mode = path.lstat().st_mode
        except OSError:
            reasons.append(f"member-unavailable:{name}")
            continue
        if not stat.S_ISREG(mode) or path.is_symlink():
            reasons.append(f"member-not-regular:{name}")
            continue
        try:
            shutil.copyfile(path, destination / name)
        except OSError:
            reasons.append(f"member-unavailable:{name}")
    return tuple(reasons)


def _ledger_line(inputs: _LedgerInputs) -> str:
    inventory, _advisories, _exclusions, ledger, config = inputs.members
    decisions = (
        "unchanged" if not inputs.decision_moved else f"CHANGED: {','.join(inputs.decision_moved)}"
    )
    superseded_name = inputs.superseded.name if inputs.superseded is not None else "none"
    # Every hash is written IN FULL. A short hex prefix can contain an
    # English-looking bigram or trigram that the spell-checker reads as a word:
    # on the first real accept, hk's `typos --write-changes` commit hook flagged
    # the 12-char plan-manifest prefix and REWROTE the 8-char commit id (one
    # letter inserted) — a corrupted hash in an authorization ledger. Probed
    # 2026-08-23: every full 40/64-hex string passes typos' hex heuristic; 7-,
    # 8- and 12-char prefixes do not. (This comment deliberately does not quote
    # the offending prefixes — quoting them re-triggers the same check.)
    return (
        f"- **{inputs.timestamp}** — graphify {config.graphify_version} "
        f"({config.graphify_commit}) · claude {config.claude_version} · "
        f"effort {config.effort} · cap ${config.max_total_cost_usd} · "
        f"units {inventory.admitted_unit_count} / chunks {len(ledger.chunks)} · "
        f"decision digests: {decisions} · "
        f"plan_manifest {inputs.before['plan_manifest_sha256']}→"
        f"{inputs.after['plan_manifest_sha256']} · "
        f"execution_config {inputs.before['execution_config_sha256']}→"
        f"{inputs.after['execution_config_sha256']} · HEAD {inputs.head} · "
        f"superseded {superseded_name}"
    )


def _new_authority(digests: dict[str, str]) -> AuthorityRoots:
    return AuthorityRoots(
        advisories_sha256=digests["advisories_sha256"],
        exclusions_sha256=digests["exclusions_sha256"],
        execution_config_sha256=digests["execution_config_sha256"],
        plan_manifest_sha256=digests["plan_manifest_sha256"],
        schema_version=1,
    )


def _require_authorized(verification: PlanVerification) -> None:
    if verification.execution_authorized:
        return
    reasons = ",".join(verification.reasons) or "unauthorized"
    raise RuntimeError(f"post-record verification failed: {reasons}")


def _record_with_source(
    candidate: Path | None,
    *,
    context: _RecordContext,
    source_pin: SourcePin | None,
) -> RecordReport:
    now = datetime.now(tz=UTC)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    suffix = now.strftime("%Y%m%dT%H%M%SZ")
    if candidate is None:
        if source_pin is None:
            raise ValueError("fresh recording requires record to materialize the source")
        candidate = context.repo_root / ".agent/kb" / f"replan-{suffix}"
        plan_source(
            context.source_root,
            candidate,
            source=source_pin,
            max_output_tokens=planned_max_output_tokens(context.repo_root, os.environ),
            options=PlanSourceOptions(repo_root=context.repo_root),
        )
        _say_dedupe(candidate)
    try:
        ignored_extras = tuple(
            sorted(path.name for path in candidate.iterdir() if path.name not in PLAN_FILES)
        )
    except OSError:
        ignored_extras = ()
    with tempfile.TemporaryDirectory(prefix="kb-graphify-corpus-record-stage-") as raw_stage:
        staged = Path(raw_stage) / "plan"
        copy_reasons = _copy_plan_members(candidate, staged)
        verification = verify_plan(
            staged,
            context.source_root,
            authority_path=context.authority_path,
            repo_root=context.repo_root,
        )
        candidate_reasons = tuple(dict.fromkeys((*verification.reasons, *copy_reasons)))
        before = _authority_digests(_authority(context.authority_path))
        after = _plan_digests(staged)
        moved = tuple(name for name in _DIGEST_FIELDS if before[name] != after[name])
        decision_moved = tuple(name for name in DECISION_DIGESTS if name in moved)
        decision_names_match = context.accept_decision_change == frozenset(decision_moved)
        structural = verification.structural_complete and set(candidate_reasons).issubset(
            _ALLOWED_CANDIDATE_REASONS
        )
        recordable = structural and bool(moved) and decision_names_match
        base = _ReportBase(
            candidate=_display_path(candidate, context.repo_root),
            staged=_display_path(staged, context.repo_root),
            canonical=_display_path(context.canonical_dir, context.repo_root),
            candidate_state=verification.state,
            candidate_reasons=candidate_reasons,
            moved=moved,
            decision_moved=decision_moved,
            recordable=recordable,
            digests_before=before,
            digests_after=after,
            delta=_delta(staged, context.canonical_dir),
            ignored_extras=ignored_extras,
        )
        if not context.accept or not recordable:
            return base.finish(
                accepted=False,
                authorized_after=None,
                superseded_dir=None,
            )

        authority_before = context.authority_path.read_bytes()
        ledger_before = context.ledger_path.read_bytes()
        candidate_members = _members(staged)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=context.repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        superseded = context.canonical_dir.with_name(
            f"{context.canonical_dir.name}.superseded-{suffix}"
        )
        if superseded.exists():
            raise FileExistsError(f"superseded plan already exists: {superseded}")
        retained = superseded if context.canonical_dir.exists() else None
        authority_text = encode_canonical(_new_authority(after)).decode("utf-8")
        ledger_line = _ledger_line(
            _LedgerInputs(
                timestamp=timestamp,
                members=candidate_members,
                decision_moved=decision_moved,
                before=before,
                after=after,
                head=head,
                superseded=retained,
            )
        )
        ledger_text = ledger_before.decode("utf-8") + ledger_line + "\n"
        rollback = _RollbackState(
            canonical_dir=context.canonical_dir,
            superseded_dir=retained,
            authority_path=context.authority_path,
            authority_before=authority_before,
            ledger_path=context.ledger_path,
            ledger_before=ledger_before,
        )
        with _Transaction(rollback) as transaction:
            if retained is not None:
                context.canonical_dir.replace(retained)
            context.canonical_dir.mkdir(parents=True)
            for name in PLAN_FILES:
                shutil.copyfile(staged / name, context.canonical_dir / name)
            atomic.write_text(context.authority_path, authority_text)
            atomic.write_text(context.ledger_path, ledger_text)
            after_verification = verify_plan(
                context.canonical_dir,
                context.source_root,
                authority_path=context.authority_path,
                repo_root=context.repo_root,
            )
            _require_authorized(after_verification)
        if transaction.error is not None:
            return base.finish(
                accepted=False,
                authorized_after=False,
                superseded_dir=None,
                reasons=(*candidate_reasons, f"record-accept-failed:{transaction.error}"),
            )
        return base.finish(
            accepted=True,
            authorized_after=True,
            superseded_dir=(
                _display_path(retained, context.repo_root) if retained is not None else None
            ),
        )


def record_plan(
    candidate: Path | None,
    *,
    repo_root: Path,
    canonical_dir: Path,
    authority_path: Path,
    ledger_path: Path,
    **options: Unpack[_RecordPlanOptions],
) -> RecordReport:
    """Classify a plan and optionally record it as the canonical authority."""
    accept = options.get("accept", False)
    accept_decision_change = options.get("accept_decision_change", frozenset())
    source_root = options.get("source_root")
    if source_root is not None:
        return _record_with_source(
            candidate,
            context=_RecordContext(
                repo_root=repo_root,
                canonical_dir=canonical_dir,
                authority_path=authority_path,
                ledger_path=ledger_path,
                accept=accept,
                accept_decision_change=accept_decision_change,
                source_root=source_root,
            ),
            source_pin=None,
        )
    with tempfile.TemporaryDirectory(prefix="kb-graphify-corpus-record-source-") as raw_source:
        admitted_root = Path(raw_source) / "graphify"
        source_pin = admit_source(repo_root, admitted_root)
        return _record_with_source(
            candidate,
            context=_RecordContext(
                repo_root=repo_root,
                canonical_dir=canonical_dir,
                authority_path=authority_path,
                ledger_path=ledger_path,
                accept=accept,
                accept_decision_change=accept_decision_change,
                source_root=admitted_root,
            ),
            source_pin=source_pin,
        )


def _usage() -> int:
    events.say(
        "corpus_record.usage",
        "kb-setup graphify-semantic-corpus record [--plan-dir PATH] [--accept] "
        "[--accept-decision-change NAME[,NAME]]",
    )
    return 2


def _parse_args(args: list[str]) -> tuple[Path | None, bool, frozenset[str]] | None:
    candidate: Path | None = None
    accept = False
    decisions: frozenset[str] = frozenset()
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--accept" and not accept:
            accept = True
            index += 1
        elif arg == "--plan-dir" and candidate is None and index + 1 < len(args):
            candidate = Path(args[index + 1])
            index += 2
        elif arg == "--accept-decision-change" and not decisions and index + 1 < len(args):
            names = frozenset(args[index + 1].split(","))
            if not names or "" in names or not names.issubset(DECISION_DIGESTS):
                return None
            decisions = names
            index += 2
        else:
            return None
    return candidate, accept, decisions


def record_main(repo_root: Path, args: list[str]) -> int:
    """CLI boundary for review, recording, and rollback."""
    parsed = _parse_args(args)
    if parsed is None:
        return _usage()
    candidate, accept, decisions = parsed
    authority_path = Path(graphify_semantic_corpus_authority.__file__).with_name(_AUTHORITY_FILE)
    report = record_plan(
        candidate,
        repo_root=repo_root,
        canonical_dir=repo_root / "graphify-out/graphify-semantic-corpus",
        authority_path=authority_path,
        ledger_path=repo_root / _LEDGER,
        accept=accept,
        accept_decision_change=decisions,
    )
    events.say(
        "corpus_record.classification",
        f"corpus record: moved={','.join(report.moved) or 'none'}; "
        f"decision_moved={','.join(report.decision_moved) or 'none'}; "
        f"recordable={str(report.recordable).lower()}; accepted={str(report.accepted).lower()}",
        moved=report.moved,
        decision_moved=report.decision_moved,
        recordable=report.recordable,
        accepted=report.accepted,
    )
    if not report.moved:
        events.say("corpus_record.refused", "corpus record: nothing to record")
    elif decisions != frozenset(report.decision_moved):
        events.say(
            "corpus_record.refused",
            "corpus record: --accept-decision-change must name exactly the moved decision digests",
        )
    if report.candidate_reasons:
        events.say(
            "corpus_record.reasons",
            f"corpus record reasons: {', '.join(report.candidate_reasons)}",
            reasons=report.candidate_reasons,
        )
    events.say(
        "corpus_record.report",
        encode_canonical(report).decode("utf-8").rstrip(),
        accepted=report.accepted,
        authorized_after=report.authorized_after,
        recordable=report.recordable,
    )
    if report.accepted and report.authorized_after:
        return 0
    if accept and report.recordable and report.authorized_after is False:
        return 1
    return 0 if report.recordable else 2
