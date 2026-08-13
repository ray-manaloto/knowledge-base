# Copyright (c) 2026 Raymond Manaloto
"""Download large immutable artifacts through pluggable upstream engines."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from kb_setup.atomic import write_text

_COMMIT = re.compile(r"[0-9a-f]{40}")
_HF_SOURCE = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?")
_MIB = 1024 * 1024
_PS_FIELD_COUNT = 2


@dataclass(frozen=True)
class ArtifactFile:
    """One expected file from immutable provider metadata."""

    path: str
    size: int
    sha256: str | None


@dataclass(frozen=True)
class DownloadPlan:
    """A resolved download plan before any payload transfer."""

    provider: str
    source: str
    requested_revision: str
    resolved_revision: str
    files: tuple[ArtifactFile, ...]
    bytes_total: int
    bytes_present: int
    bytes_needed: int


@dataclass(frozen=True)
class DownloadOptions:
    """User-controlled policy around an immutable provider request."""

    provider_name: str
    source: str
    revision: str
    destination: Path
    includes: tuple[str, ...] = ()
    headroom_gib: int = 20
    max_workers: int = 8
    verify_sha256: bool = False
    receipt: Path | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class ProcessSnapshot:
    """Stable-enough identity and state for one POSIX process."""

    pid: int
    pgid: int
    start_token: str
    command_sha256: str
    state: str


class Provider(Protocol):
    """Boundary implemented by an existing transfer SDK."""

    name: str

    def plan(
        self, source: str, revision: str, destination: Path, includes: tuple[str, ...]
    ) -> DownloadPlan:
        """Resolve immutable provider metadata without downloading payload bytes."""
        ...

    def download(
        self,
        plan: DownloadPlan,
        destination: Path,
        includes: tuple[str, ...],
        max_workers: int,
    ) -> Path:
        """Transfer or resume the planned files into ``destination``."""
        ...

    def versions(self) -> dict[str, str]:
        """Return versions of the provider packages that actually execute."""
        ...


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"provider returned unsafe artifact path: {value!r}")
    return path


def _matches(path: str, includes: tuple[str, ...]) -> bool:
    return not includes or any(fnmatch.fnmatch(path, pattern) for pattern in includes)


def _expected_sha(sibling: object) -> str | None:
    lfs = getattr(sibling, "lfs", None)
    value = getattr(lfs, "sha256", None)
    return str(value) if value else None


class HuggingFaceXetProvider:
    """Use Hugging Face's supported SDK and Xet transfer engine."""

    name = "hf-xet"

    def __init__(self) -> None:
        """Import the SDK only after profile environment variables are set."""
        self._hub = importlib.import_module("huggingface_hub")

    def plan(
        self, source: str, revision: str, destination: Path, includes: tuple[str, ...]
    ) -> DownloadPlan:
        """Resolve a model snapshot and its expected file metadata."""
        info = self._hub.model_info(source, revision=revision, files_metadata=True)
        resolved = str(info.sha)
        if resolved != revision:
            raise ValueError(f"provider resolved {revision} to unexpected revision {resolved}")
        siblings = info.siblings or ()
        files = tuple(
            ArtifactFile(
                path=str(sibling.rfilename),
                size=int(sibling.size or 0),
                sha256=_expected_sha(sibling),
            )
            for sibling in siblings
            if _matches(str(sibling.rfilename), includes)
        )
        if not files:
            raise ValueError("include patterns selected no artifact files")
        for item in files:
            _safe_relative(item.path)
        present = sum(
            item.size
            for item in files
            if (destination / _safe_relative(item.path)).is_file()
            and (destination / _safe_relative(item.path)).stat().st_size == item.size
        )
        total = sum(item.size for item in files)
        return DownloadPlan(
            self.name, source, revision, resolved, files, total, present, total - present
        )

    def download(
        self,
        plan: DownloadPlan,
        destination: Path,
        includes: tuple[str, ...],
        max_workers: int,
    ) -> Path:
        """Delegate transfer and resume behavior to ``snapshot_download``."""
        result = self._hub.snapshot_download(
            repo_id=plan.source,
            revision=plan.resolved_revision,
            local_dir=destination,
            allow_patterns=list(includes) or None,
            max_workers=max_workers,
        )
        return Path(result).resolve()

    def versions(self) -> dict[str, str]:
        """Report the exact locked Hugging Face transfer packages."""
        return {name: importlib.metadata.version(name) for name in ("huggingface-hub", "hf-xet")}


_PROVIDERS: dict[str, type[Provider]] = {"hf-xet": HuggingFaceXetProvider}


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * _MIB):
            digest.update(block)
    return digest.hexdigest()


def _verify(plan: DownloadPlan, destination: Path, *, sha256: bool) -> list[str]:
    failures: list[str] = []
    for item in plan.files:
        path = destination / _safe_relative(item.path)
        if not path.is_file():
            failures.append(f"missing:{item.path}")
            continue
        if path.stat().st_size != item.size:
            failures.append(f"size:{item.path}")
            continue
        if sha256 and item.sha256 and _stream_sha256(path) != item.sha256:
            failures.append(f"sha256:{item.path}")
    return failures


def _receipt_path(destination: Path, explicit: Path | None) -> Path:
    return explicit or destination / ".artifact-download.json"


def _existing_ancestor(path: Path) -> Path:
    """Return the nearest existing path so disk checks use the target filesystem."""
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise OSError(f"no existing ancestor for destination: {path}")
        candidate = parent
    return candidate


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _ps_value(pid: int, field: str) -> str:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", f"{field}="],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise ProcessLookupError(f"process {pid} is not running")
    return value


def _process_snapshot(pid: int) -> ProcessSnapshot:
    """Read a PID identity that detects ordinary PID reuse before signaling."""
    command = _ps_value(pid, "command")
    return ProcessSnapshot(
        pid=pid,
        pgid=int(_ps_value(pid, "pgid")),
        start_token=_ps_value(pid, "lstart"),
        command_sha256=hashlib.sha256(command.encode()).hexdigest(),
        state=_ps_value(pid, "stat"),
    )


def _process_record() -> dict[str, object]:
    process = _process_snapshot(os.getpid())
    leader = _process_snapshot(process.pgid)
    return {
        "pid": process.pid,
        "pgid": process.pgid,
        "start_token": process.start_token,
        "command_sha256": process.command_sha256,
        "group_leader_start_token": leader.start_token,
        "group_leader_command_sha256": leader.command_sha256,
        "tmux_pane": os.environ.get("TMUX_PANE"),
    }


def _process_is_stopped(pid: int) -> bool:
    return "T" in _process_snapshot(pid).state


def _wait_for_process_state(pid: int, *, stopped: bool) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if _process_is_stopped(pid) is stopped:
            return
        time.sleep(0.05)
    expected = "stopped" if stopped else "running"
    raise RuntimeError(f"process {pid} did not become {expected}")


def _tmux_pane_pgid(pane: str) -> int:
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane, "#{pane_pid} #{pane_dead}"],
        check=False,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.split()
    if result.returncode != 0 or len(fields) != _PS_FIELD_COUNT or fields[1] != "0":
        raise RuntimeError(f"tmux pane {pane!r} is not live")
    return int(fields[0])


def _recorded_int(process: dict[str, object], key: str) -> int:
    value = process.get(key)
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"receipt has invalid process.{key}")
    return value


def _recorded_str(process: dict[str, object], key: str) -> str:
    value = process.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"receipt has invalid process.{key}")
    return value


def _validate_control_target(payload: dict[str, object]) -> tuple[int, int, bool]:
    process = payload.get("process")
    if not isinstance(process, dict):
        raise TypeError("receipt predates process control; restart it once to enable pause")
    pid = _recorded_int(process, "pid")
    pgid = _recorded_int(process, "pgid")
    current = _process_snapshot(pid)
    leader = _process_snapshot(pgid)
    identity = (
        current.pgid == pgid
        and current.start_token == _recorded_str(process, "start_token")
        and current.command_sha256 == _recorded_str(process, "command_sha256")
        and leader.pid == pgid
        and leader.pgid == pgid
        and leader.start_token == _recorded_str(process, "group_leader_start_token")
        and leader.command_sha256 == _recorded_str(process, "group_leader_command_sha256")
    )
    if not identity:
        raise RuntimeError("recorded process identity no longer matches; refusing to signal")
    pane = _recorded_str(process, "tmux_pane")
    if _tmux_pane_pgid(pane) != pgid:
        raise RuntimeError("recorded tmux pane no longer owns the process group")
    return pid, pgid, _process_is_stopped(pid)


def _append_control_event(payload: dict[str, object], action: str) -> None:
    events = payload.setdefault("control_events", [])
    if not isinstance(events, list):
        raise TypeError("receipt control_events must be a list")
    events.append({"action": action, "at": datetime.now(UTC).isoformat(), "same_process": True})


def _pause(
    payload: dict[str, object], receipt: Path, pid: int, *, stopped: bool
) -> dict[str, object]:
    if stopped and payload.get("status") == "paused":
        return payload
    if not stopped:
        os.kill(pid, signal.SIGSTOP)
        _wait_for_process_state(pid, stopped=True)
    payload["status"] = "paused"
    _append_control_event(payload, "pause")
    _write_receipt(receipt, payload)
    return payload


def _resume(
    payload: dict[str, object], receipt: Path, pid: int, *, stopped: bool
) -> dict[str, object]:
    if not stopped and payload.get("status") == "downloading":
        return payload
    if not stopped:
        payload["status"] = "downloading"
        _write_receipt(receipt, payload)
        return payload
    previous = dict(payload)
    payload["status"] = "downloading"
    _append_control_event(payload, "resume")
    _write_receipt(receipt, payload)
    try:
        os.kill(pid, signal.SIGCONT)
        _wait_for_process_state(pid, stopped=False)
    except BaseException:
        _write_receipt(receipt, previous)
        raise
    return payload


def control(receipt: Path, action: str) -> dict[str, object]:
    """Pause, resume, or inspect one validated detached download process group."""
    if action not in {"pause", "resume", "status"}:
        raise ValueError(f"unsupported control action: {action}")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != "artifact-download-v1":
        raise ValueError("not an artifact-download-v1 receipt")
    pid, pgid, stopped = _validate_control_target(payload)
    if action == "status":
        process = payload["process"]
        if not isinstance(process, dict):
            raise TypeError("receipt process identity must be an object")
        return {
            "status": payload.get("status"),
            "process_state": "stopped" if stopped else "running",
            "pid": process["pid"],
            "pgid": pgid,
        }
    payload["pause_method"] = "posix-sigstop-process"
    if action == "pause":
        return _pause(payload, receipt, pid, stopped=stopped)
    return _resume(payload, receipt, pid, stopped=stopped)


def _last_progress(log: Path) -> str | None:
    """Return the latest rendered progress update from a bounded log tail."""
    try:
        with log.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 64 * 1024))
            tail = handle.read().decode(errors="replace")
    except OSError:
        return None
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    return lines[-1] if lines else None


def _control_summary(
    payload: dict[str, object], receipt: Path, log: Path | None
) -> dict[str, object]:
    process = payload.get("process")
    summary: dict[str, object] = {
        "status": payload.get("status"),
        "receipt": str(receipt),
    }
    if isinstance(process, dict):
        summary.update(pid=process.get("pid"), pgid=process.get("pgid"))
    else:
        summary.update(pid=payload.get("pid"), pgid=payload.get("pgid"))
    if "process_state" in payload:
        summary["process_state"] = payload["process_state"]
    if log is not None:
        summary["log"] = str(log)
        summary["last_progress"] = _last_progress(log)
    return summary


def _preserve_control_events(base: dict[str, object], receipt: Path) -> None:
    try:
        current = json.loads(receipt.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return
    for key in ("control_events", "pause_method"):
        if key in current:
            base[key] = current[key]


def _validate_result(actual: Path, destination: Path, plan: DownloadPlan, *, sha256: bool) -> None:
    if actual != destination:
        raise RuntimeError(f"provider returned unexpected destination {actual}")
    failures = _verify(plan, destination, sha256=sha256)
    if failures:
        raise RuntimeError(f"artifact verification failed: {', '.join(failures)}")


def download(options: DownloadOptions, *, provider: Provider | None = None) -> int:
    """Plan, transfer, and attest one immutable artifact set."""
    if not _COMMIT.fullmatch(options.revision):
        raise ValueError("revision must be an immutable 40-character lowercase commit SHA")
    if options.provider_name == "hf-xet" and not _HF_SOURCE.fullmatch(options.source):
        raise ValueError("Hugging Face source must be a repository identifier")
    if options.headroom_gib < 0 or options.max_workers < 1:
        raise ValueError("headroom must be non-negative and max-workers must be positive")
    implementation = provider or _PROVIDERS[options.provider_name]()
    destination = options.destination.resolve()
    plan = implementation.plan(options.source, options.revision, destination, options.includes)
    free = shutil.disk_usage(_existing_ancestor(destination.parent)).free
    required = plan.bytes_needed + options.headroom_gib * 1024**3
    if free < required:
        raise OSError(f"insufficient disk: need {required:,} bytes, have {free:,}")
    receipt_path = _receipt_path(destination, options.receipt)
    base: dict[str, object] = {
        "schema": "artifact-download-v1",
        "status": "planned" if options.dry_run else "downloading",
        "provider": plan.provider,
        "provider_versions": implementation.versions(),
        "source": plan.source,
        "requested_revision": plan.requested_revision,
        "resolved_revision": plan.resolved_revision,
        "destination": str(destination),
        "includes": list(options.includes),
        "files": [asdict(item) for item in plan.files],
        "bytes_total": plan.bytes_total,
        "bytes_present": plan.bytes_present,
        "bytes_needed": plan.bytes_needed,
        "disk_free_before": free,
        "headroom_gib": options.headroom_gib,
        "max_workers": options.max_workers,
        "verify_sha256": options.verify_sha256,
        "started_at": datetime.now(UTC).isoformat(),
        "process": _process_record(),
    }
    _write_receipt(receipt_path, base)
    if options.dry_run:
        print(json.dumps(base, indent=2, sort_keys=True))
        return 0
    started = time.monotonic()
    try:
        destination.mkdir(parents=True, exist_ok=True)
        actual = implementation.download(plan, destination, options.includes, options.max_workers)
        _validate_result(actual, destination, plan, sha256=options.verify_sha256)
    except Exception as exc:
        base.update(
            status="failed",
            error_type=type(exc).__name__,
            elapsed_seconds=time.monotonic() - started,
        )
        _preserve_control_events(base, receipt_path)
        _write_receipt(receipt_path, base)
        raise
    elapsed = time.monotonic() - started
    base.update(
        status="complete",
        elapsed_seconds=elapsed,
        average_bytes_per_second=plan.bytes_needed / elapsed if elapsed else None,
        completed_at=datetime.now(UTC).isoformat(),
        integrity=(
            "size+provider-sha256" if options.verify_sha256 else "size+immutable-provider-metadata"
        ),
    )
    _preserve_control_events(base, receipt_path)
    _write_receipt(receipt_path, base)
    print(json.dumps(base, indent=2, sort_keys=True))
    return 0


def main(_repo_root: Path, args: list[str]) -> int:
    """CLI adapter for the mise task."""
    parser = argparse.ArgumentParser(prog="kb-setup artifact-download")
    parser.add_argument("--provider", choices=sorted(_PROVIDERS), default="hf-xet")
    parser.add_argument("--source", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--headroom-gib", type=int, default=20)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--range-gets", type=int)
    parser.add_argument("--profile", choices=("balanced", "high-performance"), default="balanced")
    parser.add_argument("--verify-sha256", action="store_true")
    parser.add_argument("--receipt", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    options = parser.parse_args(args)
    if options.profile == "high-performance":
        os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
    if options.range_gets is not None:
        if options.range_gets < 1:
            parser.error("--range-gets must be positive")
        os.environ["HF_XET_NUM_CONCURRENT_RANGE_GETS"] = str(options.range_gets)
    return download(
        DownloadOptions(
            provider_name=options.provider,
            source=options.source,
            revision=options.revision,
            destination=options.destination,
            includes=tuple(options.include),
            headroom_gib=options.headroom_gib,
            max_workers=options.max_workers,
            verify_sha256=options.verify_sha256,
            receipt=options.receipt,
            dry_run=not options.apply,
        )
    )


def control_main(_repo_root: Path, args: list[str]) -> int:
    """CLI adapter for same-process artifact pause/resume control."""
    parser = argparse.ArgumentParser(prog="kb-setup artifact-download-control")
    parser.add_argument("action", choices=("pause", "resume", "status"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--log", type=Path)
    options = parser.parse_args(args)
    receipt = options.receipt.resolve()
    result = control(receipt, options.action)
    log = options.log.resolve() if options.log else None
    print(json.dumps(_control_summary(result, receipt, log), indent=2, sort_keys=True))
    return 0
