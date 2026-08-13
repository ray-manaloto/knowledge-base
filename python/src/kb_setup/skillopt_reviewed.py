# Copyright (c) 2026 Raymond Manaloto
"""Reviewed, redacted SkillOpt adapter with a content-addressed trust anchor."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from skillopt_sleep.tasks_file import load_tasks_file
from skillopt_sleep.types import TaskRecord

from kb_setup.result import Rc
from kb_setup.skillopt_contract import assert_public_contract

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}\Z")
_SEGMENT = re.compile(r"\.(\d{4})\.json\Z")
_TARGET = re.compile(r"\.(?:claude|agents)/skills/[a-z0-9][a-z0-9_-]*/SKILL\.md\Z")
_SAFE_TEXT = re.compile(r"[\x20-\x7e\n]{1,1000}\Z")
_PRIVATE_TEXT = re.compile(
    r"(?:data:|file:|https?://|[\\/]|\.\.|~|sk-[a-z0-9_-]{8}|ghp_[a-z0-9]{8}|"
    r"AKIA[A-Z0-9]{8})",
    re.IGNORECASE,
)
_STATUSES = frozenset({"open", "satisfied", "withdrawn", "contradicted"})
_KINDS = frozenset({"requirement", "promise"})
_PROVENANCE = frozenset({"native_root_user", "paired_form_answer"})
_BACKENDS = frozenset({"mock", "handoff"})
_TRAIN_CUTOFF = 60
_VAL_CUTOFF = 80
_HANDOFF_PENDING = 3
_CLI_ARG_COUNT = 8
_TIMEOUT_SECONDS = 120


class ReviewedLedgerError(ValueError):
    """A bounded, operator-safe validation error."""


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Relative artifact path and exact byte digest."""

    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ReviewedClaim:
    """Redacted claim identity retained for cross-binding only."""

    claim_id_sha256: str
    statement_sha256: str
    claim_kind: str
    status: str
    root_session_digest: str


@dataclass(frozen=True, slots=True)
class ReviewedSkillTask:
    """Human-reviewed optimizer input with no transcript content."""

    task_id: str
    task_family: str
    root_session_digest: str
    instruction: str
    success_rubric: str
    sources: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ReviewedCorpus:
    """Cross-bound claims, tasks, and review receipt."""

    packet_sha256: str
    receipt_sha256: str
    claims: tuple[ReviewedClaim, ...]
    tasks: tuple[ReviewedSkillTask, ...]


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    """Content-addressed project skill target."""

    target_id: str
    relative_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class SplitReceipt:
    """Counts and ID manifests for all immutable splits."""

    train_count: int
    val_count: int
    test_count: int
    train_sha256: str
    val_sha256: str
    test_sha256: str


@dataclass(frozen=True, slots=True)
class AdapterReceipt:
    """Execution receipt that explicitly certifies no improvement or adoption."""

    schema_version: int
    run_id: str
    backend: str
    status: str
    certification: str
    packet_sha256: str
    review_receipt_sha256: str
    target_sha256: str
    optimizer_tasks_sha256: str
    heldout_tasks_sha256: str
    split: SplitReceipt
    returncode: int
    stdout: ArtifactRef
    stderr: ArtifactRef


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest(values: list[str]) -> str:
    return _sha(("\n".join(values) + "\n").encode())


def _object(value: object, *, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ReviewedLedgerError(f"{label} has a forbidden or missing field")
    return {str(key): item for key, item in value.items()}


def _read(path: Path, *, label: str) -> tuple[bytes, dict[str, Any]]:
    if path.suffix == ".jsonl":
        raise ReviewedLedgerError(f"{label} raw JSONL is forbidden")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise ReviewedLedgerError(f"{label} is missing or invalid JSON") from exc
    if not isinstance(value, dict):
        raise ReviewedLedgerError(f"{label} must be a JSON object")
    return raw, {str(key): item for key, item in value.items()}


def _text(value: object, *, label: str, pattern: re.Pattern[str] = _ID) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ReviewedLedgerError(f"{label} is invalid")
    return value


def _bounded(value: object, *, label: str) -> str:
    text = _text(value, label=label, pattern=_SAFE_TEXT)
    if _PRIVATE_TEXT.search(text):
        raise ReviewedLedgerError(f"{label} contains a forbidden path, URL, or data payload")
    return text


def _ref(base: Path, value: object, *, label: str) -> tuple[ArtifactRef, Path]:
    row = _object(value, label=label, keys={"path", "sha256"})
    relative = _text(row["path"], label=f"{label} path", pattern=re.compile(r"[^\x00]+"))
    expected = _text(row["sha256"], label=f"{label} sha256", pattern=_SHA)
    path = (base / relative).resolve()
    root = base.resolve()
    valid = (
        not Path(relative).is_absolute()
        and not relative.endswith(".jsonl")
        and root in path.parents
        and path.suffix == ".json"
    )
    if not valid:
        raise ReviewedLedgerError(f"{label} is not an allowed relative JSON artifact")
    try:
        actual = _sha(path.read_bytes())
    except OSError as exc:
        raise ReviewedLedgerError(f"{label} is missing") from exc
    if actual != expected:
        raise ReviewedLedgerError(f"{label} content hash does not match")
    return ArtifactRef(relative, expected), path


def _refs(index: dict[str, Any], noun: str) -> list[dict[str, Any]]:
    values = index["segments"]
    if not isinstance(values, list) or not values:
        raise ReviewedLedgerError(f"{noun} index has no segments")
    rows: list[dict[str, Any]] = []
    hashes: list[str] = []
    for position, value in enumerate(values, 1):
        row = _object(
            value,
            label=f"{noun} segment reference",
            keys={"suffix", "sha256", f"{noun}_count"},
        )
        suffix = _text(row["suffix"], label="segment suffix", pattern=_SEGMENT)
        match = _SEGMENT.fullmatch(suffix)
        if match is None or int(match.group(1)) != position:
            raise ReviewedLedgerError(f"{noun} segment sequence is not canonical")
        digest = _text(row["sha256"], label="segment sha256", pattern=_SHA)
        count = row[f"{noun}_count"]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReviewedLedgerError(f"{noun} segment count is invalid")
        hashes.append(digest)
        rows.append(row)
    if index["segment_sha256_manifest"] != _manifest(hashes):
        raise ReviewedLedgerError(f"{noun} segment manifest does not match")
    return rows


def _iteration(path: Path) -> tuple[str, str, frozenset[str], frozenset[str]]:
    _, value = _read(path, label="iteration")
    row = _object(
        value,
        label="iteration",
        keys={
            "format",
            "manifest_sha256",
            "root_session_digest",
            "unreviewed_requirement_ids",
            "unreviewed_promise_ids",
            "open_requirement_id_sha256s",
            "open_promise_id_sha256s",
        },
    )
    if row["format"] != "kb.session-review.redacted-iteration.v1":
        raise ReviewedLedgerError("iteration format is unknown")
    if row["unreviewed_requirement_ids"] != [] or row["unreviewed_promise_ids"] != []:
        raise ReviewedLedgerError("iteration contains unreviewed claims")
    for key in ("open_requirement_id_sha256s", "open_promise_id_sha256s"):
        values = row[key]
        if not isinstance(values, list) or values != sorted(set(values)):
            raise ReviewedLedgerError("iteration OPEN IDs are not unique and canonical")
        for digest in values:
            _text(digest, label="OPEN claim digest", pattern=_SHA)
    return (
        _text(row["manifest_sha256"], label="iteration manifest", pattern=_SHA),
        _text(row["root_session_digest"], label="root session digest", pattern=_SHA),
        frozenset(row["open_requirement_id_sha256s"]),
        frozenset(row["open_promise_id_sha256s"]),
    )


def _claim(value: object, root_digest: str) -> ReviewedClaim:
    row = _object(
        value,
        label="claim",
        keys={"claim_id", "claim_kind", "provenance", "status", "statement_sha256"},
    )
    claim_id = _text(row["claim_id"], label="claim ID")
    kind = _text(row["claim_kind"], label="claim kind")
    provenance = _text(row["provenance"], label="claim provenance")
    status = _text(row["status"], label="claim status")
    if kind not in _KINDS or provenance not in _PROVENANCE or status not in _STATUSES:
        raise ReviewedLedgerError("claim kind, provenance, or status is not authoritative")
    return ReviewedClaim(
        _sha(claim_id.encode()),
        _text(row["statement_sha256"], label="statement sha256", pattern=_SHA),
        kind,
        status,
        root_digest,
    )


def _claims(index_path: Path, iteration_hash: str, root_digest: str) -> list[ReviewedClaim]:
    _, value = _read(index_path, label="claims index")
    index = _object(
        value,
        label="claims index",
        keys={
            "format",
            "iteration_manifest_sha256",
            "claim_count",
            "segment_count",
            "segment_sha256_manifest",
            "segments",
        },
    )
    if (
        index["format"] != "kb.session-review.redacted-claim-index.v1"
        or index["iteration_manifest_sha256"] != iteration_hash
    ):
        raise ReviewedLedgerError("claims index identity does not match")
    refs = _refs(index, "claim")
    if index["segment_count"] != len(refs):
        raise ReviewedLedgerError("claims index count does not match")
    claims: list[ReviewedClaim] = []
    for position, ref in enumerate(refs, 1):
        path = Path(f"{index_path}{ref['suffix']}")
        try:
            raw = path.read_bytes()
            segment_value = json.loads(raw)
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            raise ReviewedLedgerError("claim segment is missing or invalid") from exc
        if _sha(raw) != ref["sha256"]:
            raise ReviewedLedgerError("claim segment content hash does not match")
        segment = _object(
            segment_value,
            label="claim segment",
            keys={
                "format",
                "iteration_manifest_sha256",
                "segment_index",
                "claim_count",
                "claims",
            },
        )
        values = segment["claims"]
        valid = (
            segment["format"] == "kb.session-review.redacted-claim-segment.v1"
            and segment["iteration_manifest_sha256"] == iteration_hash
            and segment["segment_index"] == position
            and isinstance(values, list)
            and segment["claim_count"] == len(values)
            and ref["claim_count"] == len(values)
        )
        if not valid:
            raise ReviewedLedgerError("claim segment identity or count does not match")
        claims.extend(_claim(value, root_digest) for value in values)
    if index["claim_count"] != len(claims):
        raise ReviewedLedgerError("claims index total does not match")
    identities = [claim.claim_id_sha256 for claim in claims]
    if len(identities) != len(set(identities)):
        raise ReviewedLedgerError("claim identity is duplicated")
    return claims


def _dispositions(index_path: Path, iteration_hash: str) -> dict[str, str]:
    _, value = _read(index_path, label="dispositions index")
    index = _object(
        value,
        label="dispositions index",
        keys={
            "format",
            "iteration_manifest_sha256",
            "disposition_count",
            "segment_count",
            "segment_sha256_manifest",
            "segments",
        },
    )
    if (
        index["format"] != "kb.session-review.redacted-disposition-index.v1"
        or index["iteration_manifest_sha256"] != iteration_hash
    ):
        raise ReviewedLedgerError("dispositions index identity does not match")
    refs = _refs(index, "disposition")
    dispositions: dict[str, str] = {}
    for position, ref in enumerate(refs, 1):
        path = Path(f"{index_path}{ref['suffix']}")
        try:
            raw = path.read_bytes()
            segment_value = json.loads(raw)
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            raise ReviewedLedgerError("disposition segment is missing or invalid") from exc
        if _sha(raw) != ref["sha256"]:
            raise ReviewedLedgerError("disposition segment content hash does not match")
        segment = _object(
            segment_value,
            label="disposition segment",
            keys={
                "format",
                "iteration_manifest_sha256",
                "segment_index",
                "disposition_count",
                "dispositions",
            },
        )
        values = segment["dispositions"]
        valid = (
            segment["format"] == "kb.session-review.redacted-disposition-segment.v1"
            and segment["iteration_manifest_sha256"] == iteration_hash
            and segment["segment_index"] == position
            and isinstance(values, list)
            and segment["disposition_count"] == len(values)
            and ref["disposition_count"] == len(values)
        )
        if not valid:
            raise ReviewedLedgerError("disposition segment identity or count does not match")
        for value in values:
            row = _object(value, label="disposition", keys={"claim_id_sha256", "status"})
            claim_digest = _text(row["claim_id_sha256"], label="claim ID sha256", pattern=_SHA)
            status = _text(row["status"], label="disposition status")
            if status not in _STATUSES or claim_digest in dispositions:
                raise ReviewedLedgerError("disposition is unknown or duplicated")
            dispositions[claim_digest] = status
    if index["disposition_count"] != len(dispositions) or index["segment_count"] != len(refs):
        raise ReviewedLedgerError("dispositions index total does not match")
    return dispositions


def _reviewed_tasks(path: Path) -> list[ReviewedSkillTask]:
    _, value = _read(path, label="reviewed skill tasks")
    manifest = _object(
        value,
        label="reviewed skill tasks",
        keys={"format", "task_count", "tasks"},
    )
    if manifest["format"] != "kb.skillopt.reviewed-tasks.v1" or not isinstance(
        manifest["tasks"], list
    ):
        raise ReviewedLedgerError("reviewed skill task format is invalid")
    tasks: list[ReviewedSkillTask] = []
    for value in manifest["tasks"]:
        row = _object(
            value,
            label="reviewed skill task",
            keys={
                "task_id",
                "task_family",
                "root_session_digest",
                "instruction",
                "success_rubric",
                "sources",
            },
        )
        if not isinstance(row["sources"], list) or not row["sources"]:
            raise ReviewedLedgerError("reviewed skill task has no sources")
        sources: list[tuple[str, str]] = []
        for source_value in row["sources"]:
            source = _object(
                source_value,
                label="reviewed task source",
                keys={"claim_id_sha256", "statement_sha256"},
            )
            sources.append(
                (
                    _text(source["claim_id_sha256"], label="claim ID sha256", pattern=_SHA),
                    _text(source["statement_sha256"], label="statement sha256", pattern=_SHA),
                )
            )
        if len(sources) != len(set(sources)):
            raise ReviewedLedgerError("reviewed skill task source is duplicated")
        tasks.append(
            ReviewedSkillTask(
                _text(row["task_id"], label="task ID"),
                _text(row["task_family"], label="task family"),
                _text(row["root_session_digest"], label="root session digest", pattern=_SHA),
                _bounded(row["instruction"], label="instruction"),
                _bounded(row["success_rubric"], label="success rubric"),
                tuple(sources),
            )
        )
    if manifest["task_count"] != len(tasks) or len({task.task_id for task in tasks}) != len(tasks):
        raise ReviewedLedgerError("reviewed skill task total or identity does not match")
    return tasks


def load_reviewed_corpus(path: Path, expected_receipt_sha256: str) -> ReviewedCorpus:
    """Cross-bind all reviewed artifacts to an explicit, out-of-band digest."""
    expected = _text(expected_receipt_sha256, label="review receipt sha256", pattern=_SHA)
    raw, value = _read(path, label="reviewed packet")
    packet = _object(
        value,
        label="reviewed packet",
        keys={"format", "bundles", "reviewed_tasks", "review_receipt"},
    )
    if packet["format"] != "kb.skillopt.reviewed-packet.v1" or not isinstance(
        packet["bundles"], list
    ):
        raise ReviewedLedgerError("reviewed packet format is invalid")
    tasks_ref, tasks_path = _ref(path.parent, packet["reviewed_tasks"], label="reviewed tasks")
    receipt_ref, receipt_path = _ref(path.parent, packet["review_receipt"], label="review receipt")
    if receipt_ref.sha256 != expected:
        raise ReviewedLedgerError("review receipt does not match the trusted invocation digest")
    claims: list[ReviewedClaim] = []
    bundle_hashes: list[str] = []
    roots: set[str] = set()
    for value in packet["bundles"]:
        bundle = _object(
            value,
            label="review bundle",
            keys={"claims_index", "iteration", "dispositions_index"},
        )
        claim_ref, claim_path = _ref(path.parent, bundle["claims_index"], label="claims index")
        iteration_ref, iteration_path = _ref(path.parent, bundle["iteration"], label="iteration")
        disp_ref, disp_path = _ref(
            path.parent, bundle["dispositions_index"], label="dispositions index"
        )
        iteration_hash, root_digest, open_requirements, open_promises = _iteration(iteration_path)
        if root_digest in roots:
            raise ReviewedLedgerError("root session appears in more than one review bundle")
        roots.add(root_digest)
        bundle_claims = _claims(claim_path, iteration_hash, root_digest)
        dispositions = _dispositions(disp_path, iteration_hash)
        if {claim.claim_id_sha256 for claim in bundle_claims} != set(dispositions):
            raise ReviewedLedgerError("claims and dispositions do not cover the same IDs")
        if any(dispositions[claim.claim_id_sha256] != claim.status for claim in bundle_claims):
            raise ReviewedLedgerError("claim and disposition status does not match")
        expected_open_requirements = {
            claim.claim_id_sha256
            for claim in bundle_claims
            if claim.claim_kind == "requirement" and claim.status == "open"
        }
        expected_open_promises = {
            claim.claim_id_sha256
            for claim in bundle_claims
            if claim.claim_kind == "promise" and claim.status == "open"
        }
        if (
            open_requirements != expected_open_requirements
            or open_promises != expected_open_promises
        ):
            raise ReviewedLedgerError("iteration OPEN identities do not match claims")
        claims.extend(bundle_claims)
        bundle_hashes.append(_manifest([claim_ref.sha256, iteration_ref.sha256, disp_ref.sha256]))
    tasks = _reviewed_tasks(tasks_path)
    claim_sources = {
        (claim.claim_id_sha256, claim.statement_sha256, claim.root_session_digest)
        for claim in claims
    }
    task_sources = [
        (claim_id, statement, task.root_session_digest)
        for task in tasks
        for claim_id, statement in task.sources
    ]
    if len(task_sources) != len(set(task_sources)) or set(task_sources) != claim_sources:
        raise ReviewedLedgerError("reviewed tasks do not cover every claim exactly once")
    _, receipt_value = _read(receipt_path, label="review receipt")
    receipt = _object(
        receipt_value,
        label="review receipt",
        keys={"format", "authority", "bundle_sha256_manifest", "reviewed_tasks_sha256"},
    )
    valid_receipt = (
        receipt["format"] == "kb.skillopt.review-receipt.v1"
        and receipt["authority"] == "native_root_user"
        and receipt["bundle_sha256_manifest"] == _manifest(bundle_hashes)
        and receipt["reviewed_tasks_sha256"] == tasks_ref.sha256
    )
    if not valid_receipt:
        raise ReviewedLedgerError("review receipt does not bind the reviewed artifacts")
    return ReviewedCorpus(_sha(raw), expected, tuple(claims), tuple(tasks))


def load_target_descriptor(repo_root: Path, path: Path) -> TargetDescriptor:
    """Resolve one allowlisted project skill without granting write authority."""
    _, value = _read(path, label="target descriptor")
    row = _object(
        value,
        label="target descriptor",
        keys={"format", "target_id", "relative_path", "sha256"},
    )
    if row["format"] != "kb.skillopt.target.v1":
        raise ReviewedLedgerError("target descriptor format is invalid")
    relative = _text(row["relative_path"], label="target path", pattern=_TARGET)
    expected = _text(row["sha256"], label="target sha256", pattern=_SHA)
    target = (repo_root / relative).resolve()
    if repo_root.resolve() not in target.parents:
        raise ReviewedLedgerError("target path escapes the project")
    try:
        actual = _sha(target.read_bytes())
    except OSError as exc:
        raise ReviewedLedgerError("target is missing") from exc
    if actual != expected:
        raise ReviewedLedgerError("target content hash does not match")
    return TargetDescriptor(_text(row["target_id"], label="target ID"), relative, expected)


def _bucket(root_digest: str) -> str:
    value = int(root_digest[:8], 16) % 100
    return "train" if value < _TRAIN_CUTOFF else "val" if value < _VAL_CUTOFF else "test"


def reviewed_tasks(corpus: ReviewedCorpus) -> tuple[TaskRecord, ...]:
    """Map reviewed task descriptors to upstream records without native IDs."""
    tasks = tuple(
        TaskRecord(
            id="reviewed-" + _sha(task.task_id.encode())[:24],
            project="reviewed-ledger",
            intent=task.instruction,
            context_excerpt="",
            outcome="unknown",
            reference_kind="rubric",
            reference=task.success_rubric,
            source_sessions=[task.root_session_digest],
            split=_bucket(task.root_session_digest),
            tags=["reviewed-ledger", task.task_family],
        )
        for task in corpus.tasks
    )
    if {task.split for task in tasks} != {"train", "val", "test"}:
        raise ReviewedLedgerError(
            "root-session split lacks train, val, or test; borrowing is forbidden"
        )
    roots_by_split = {
        split: {task.source_sessions[0] for task in tasks if task.split == split}
        for split in ("train", "val", "test")
    }
    if any(
        roots_by_split[left] & roots_by_split[right]
        for left, right in (("train", "val"), ("train", "test"), ("val", "test"))
    ):
        raise ReviewedLedgerError("root session crosses split boundaries")
    split_by_task_id = {task.id: task.split for task in tasks}
    families: dict[str, set[str]] = {}
    content: dict[str, set[str]] = {}
    for reviewed in corpus.tasks:
        upstream_id = "reviewed-" + _sha(reviewed.task_id.encode())[:24]
        split = split_by_task_id[upstream_id]
        families.setdefault(reviewed.task_family, set()).add(split)
        normalized = " ".join(
            f"{reviewed.instruction}\n{reviewed.success_rubric}".casefold().split()
        )
        content.setdefault(_sha(normalized.encode()), set()).add(split)
    if any(len(splits) != 1 for splits in (*families.values(), *content.values())):
        raise ReviewedLedgerError("task family or normalized content crosses split boundaries")
    return tuple(sorted(tasks, key=lambda task: task.id))


def _payload(tasks: tuple[TaskRecord, ...]) -> dict[str, object]:
    return {
        "format": "skillopt_sleep.tasks.v1",
        "project": "reviewed-ledger",
        "transcript_source": "",
        "n_sessions": len({task.source_sessions[0] for task in tasks}),
        "target_skill_path": "",
        "reviewed": True,
        "tasks": [task.to_dict() for task in tasks],
    }


def _split_receipt(tasks: tuple[TaskRecord, ...]) -> SplitReceipt:
    values = {
        split: [task.id for task in tasks if task.split == split]
        for split in ("train", "val", "test")
    }
    return SplitReceipt(
        len(values["train"]),
        len(values["val"]),
        len(values["test"]),
        _manifest(values["train"]),
        _manifest(values["val"]),
        _manifest(values["test"]),
    )


_AUDITED = r"""
import os
import runpy
import sys
from pathlib import Path
allowed = Path(os.environ["KB_SKILLOPT_ALLOWED_ROOT"]).resolve()
def deny(candidate):
    if isinstance(candidate, (str, bytes, os.PathLike)):
        target = Path(os.fsdecode(candidate)).resolve()
        if target != allowed and allowed not in target.parents:
            raise PermissionError("SkillOpt attempted a write outside the current run")
def audit(event, args):
    if event == "open" and args:
        mode = args[1] if len(args) > 1 else "r"
        flags = args[2] if len(args) > 2 else 0
        if any(token in str(mode) for token in "wax+") or bool(flags & 0x3):
            deny(args[0])
    elif event in {
        "os.mkdir", "os.remove", "os.rmdir", "os.unlink", "os.chmod",
        "os.truncate", "os.utime", "os.chown", "os.setxattr", "os.removexattr",
    }:
        deny(args[0] if args else None)
    elif event in {"os.rename", "os.replace", "os.link", "os.symlink"}:
        deny(args[0] if args else None)
        deny(args[1] if len(args) > 1 else None)
sys.addaudithook(audit)
sys.argv = ["skillopt-sleep", *sys.argv[1:]]
runpy.run_module("skillopt_sleep", run_name="__main__")
"""


def _write_json(path: Path, value: object) -> bytes:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _artifact(run_root: Path, path: Path) -> ArtifactRef:
    return ArtifactRef(path.relative_to(run_root).as_posix(), _sha(path.read_bytes()))


def _redact_retained_paths(run_root: Path, repo_root: Path) -> None:
    replacements = (
        (str(run_root.resolve()).encode(), b"$RUN"),
        (str(repo_root.resolve()).encode(), b"$REPO"),
    )
    for path in run_root.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        redacted = data
        for source, replacement in replacements:
            redacted = redacted.replace(source, replacement)
        if redacted != data:
            path.write_bytes(redacted)


def _claim_run(repo_root: Path, run_id: str) -> Path:
    run_root = repo_root.resolve() / ".agent" / "skillopt" / "runs" / run_id
    try:
        run_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ReviewedLedgerError(
            "content-addressed run already exists; stale state reuse is forbidden"
        ) from exc
    except OSError as exc:
        raise ReviewedLedgerError("content-addressed run could not be claimed") from exc
    return run_root


def _mock_result(stdout: bytes, run_root: Path) -> bytes | None:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError, UnicodeError:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("staging_dir"), str):
        return None
    staging = Path(value["staging_dir"]).resolve()
    if run_root.resolve() not in staging.parents:
        return None
    report_path = staging / "report.json"
    try:
        report = json.loads(report_path.read_bytes())
    except OSError, json.JSONDecodeError, UnicodeError:
        return None
    valid = (
        value.get("tasks_reviewed") is True
        and isinstance(value.get("accepted"), bool)
        and isinstance(value.get("gate_action"), str)
        and isinstance(report, dict)
        and report.get("holdout_leaked") is False
    )
    if not valid:
        return None
    bounded = {
        "accepted": value["accepted"],
        "gate_action": value["gate_action"],
        "holdout_leaked": False,
        "n_tasks": value.get("n_tasks", 0),
        "staging_report_path": report_path.relative_to(run_root).as_posix(),
        "staging_report_sha256": _sha(report_path.read_bytes()),
        "tasks_reviewed": True,
    }
    return (json.dumps(bounded, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _handoff_result(stdout: bytes) -> bytes | None:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError, UnicodeError:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("handoff_pending"), int):
        return None
    return (
        json.dumps(
            {"handoff_pending": value["handoff_pending"]},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def run_reviewed_adapter(
    repo_root: Path,
    packet_path: Path,
    descriptor_path: Path,
    backend: str,
    review_receipt_sha256: str,
) -> AdapterReceipt:
    """Run only a confined mock/handoff workflow and retain every diagnostic byte."""
    if backend not in _BACKENDS:
        raise ReviewedLedgerError("only mock and handoff backends are supported")
    assert_public_contract()
    corpus = load_reviewed_corpus(packet_path, review_receipt_sha256)
    target = load_target_descriptor(repo_root, descriptor_path)
    tasks = reviewed_tasks(corpus)
    optimizer = tuple(task for task in tasks if task.split != "test")
    heldout = tuple(task for task in tasks if task.split == "test")
    run_id = _sha(f"{corpus.packet_sha256}\0{target.sha256}\0{backend}".encode())[:24]
    run_root = _claim_run(repo_root, run_id)
    sandbox = run_root / "project"
    target_copy = sandbox / target.relative_path
    target_copy.parent.mkdir(parents=True)
    target_copy.write_bytes((repo_root / target.relative_path).read_bytes())
    optimizer_path = run_root / "optimizer-tasks.json"
    heldout_path = run_root / "heldout-test-tasks.json"
    optimizer_data = _write_json(optimizer_path, _payload(optimizer))
    heldout_data = (
        json.dumps(_payload(heldout), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    loaded, metadata = load_tasks_file(str(optimizer_path))
    if metadata.get("reviewed") is not True or [task.id for task in loaded] != [
        task.id for task in optimizer
    ]:
        raise ReviewedLedgerError("upstream task loader changed reviewed optimizer identity")
    config_dir = run_root / "home" / ".skillopt-sleep"
    _write_json(
        config_dir / "config.json",
        {
            "state_dir": str(run_root / "state"),
            "target_skill_path": str(target_copy),
            "auto_adopt": False,
            "evidence_log": False,
            "gate_mode": "on",
            "evolve_memory": False,
            "evolve_skill": True,
            "dream_enabled": False,
            "recall_enabled": False,
        },
    )
    env = {
        "PATH": "",
        "HOME": str(run_root / "home"),
        "XDG_CONFIG_HOME": str(run_root / "xdg-config"),
        "XDG_CACHE_HOME": str(run_root / "xdg-cache"),
        "XDG_DATA_HOME": str(run_root / "xdg-data"),
        "CLAUDE_CONFIG_DIR": str(run_root / "claude"),
        "CODEX_HOME": str(run_root / "codex"),
        "SKILLOPT_SLEEP_HANDOFF_DIR": str(run_root / "handoff"),
        "KB_SKILLOPT_ALLOWED_ROOT": str(run_root),
        "PYTHONUTF8": "1",
    }
    command = [
        sys.executable,
        "-c",
        _AUDITED,
        "run",
        "--project",
        str(sandbox),
        "--backend",
        backend,
        "--tasks-file",
        str(optimizer_path),
        "--target-skill-path",
        str(target_copy),
        "--claude-home",
        str(run_root / "claude"),
        "--codex-home",
        str(run_root / "codex"),
        "--json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env=env,
            capture_output=True,
            check=False,
            timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(
            command, Rc.NOT_RUN, exc.stdout or b"", exc.stderr or b""
        )
    sanitized_stdout = (
        _mock_result(completed.stdout, run_root)
        if backend == "mock"
        else _handoff_result(completed.stdout)
    )
    stdout_path = run_root / "stdout.json"
    stderr_path = run_root / "stderr.bin"
    stdout_path.write_bytes(sanitized_stdout or b"{}\n")
    stderr_path.write_bytes(completed.stderr)
    heldout_path.write_bytes(heldout_data)
    _redact_retained_paths(run_root, repo_root)
    if backend == "mock":
        success = (
            completed.returncode == 0 and not completed.stderr and sanitized_stdout is not None
        )
        status = "staged_unverified" if success else "failed"
    else:
        success = (
            completed.returncode == _HANDOFF_PENDING
            and not completed.stderr
            and sanitized_stdout is not None
        )
        status = "handoff_pending" if success else "failed"
    split = _split_receipt(tasks)
    receipt = AdapterReceipt(
        schema_version=1,
        run_id=run_id,
        backend=backend,
        status=status,
        certification="none_no_adoption_or_heldout_claim",
        packet_sha256=corpus.packet_sha256,
        review_receipt_sha256=corpus.receipt_sha256,
        target_sha256=target.sha256,
        optimizer_tasks_sha256=_sha(optimizer_data),
        heldout_tasks_sha256=_sha(heldout_data),
        split=split,
        returncode=completed.returncode,
        stdout=_artifact(run_root, stdout_path),
        stderr=_artifact(run_root, stderr_path),
    )
    receipt_data = _write_json(run_root / "receipt.json", asdict(receipt))
    global_receipt = repo_root / ".agent" / "skillopt" / "receipts" / f"{_sha(receipt_data)}.json"
    _write_json(global_receipt, asdict(receipt))
    if not success:
        raise ReviewedLedgerError(
            "SkillOpt did not produce the required warning-free structural result; "
            "diagnostics retained"
        )
    return receipt


def reviewed_main(repo_root: Path, argv: list[str]) -> int:
    """CLI boundary with an explicit out-of-band review receipt digest."""
    valid = (
        len(argv) == _CLI_ARG_COUNT
        and argv[0] == "--packet"
        and argv[2] == "--target"
        and argv[4] == "--backend"
        and argv[6] == "--review-receipt-sha256"
    )
    if not valid:
        print(
            "usage: kb-setup skillopt-reviewed --packet P.json --target T.json "
            "--backend mock|handoff --review-receipt-sha256 SHA256",
            file=sys.stderr,
        )
        return Rc.BAD_REQUEST
    try:
        receipt = run_reviewed_adapter(repo_root, Path(argv[1]), Path(argv[3]), argv[5], argv[7])
    except (ReviewedLedgerError, RuntimeError) as exc:
        print(f"skillopt-reviewed: {exc}", file=sys.stderr)
        return Rc.BAD_REQUEST
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")))
    return Rc.OK
