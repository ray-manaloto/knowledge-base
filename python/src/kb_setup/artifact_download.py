# Copyright (c) 2026 Raymond Manaloto
"""Provider-neutral immutable artifact planning and receipt publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SOURCE = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")
_DEFAULT_MAX_BYTES = 1 << 40
_CHUNK = 8 * 1024 * 1024
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")
_LICENSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,63}\Z")


@dataclass(frozen=True, slots=True)
class ArtifactFile:
    """One provider-declared immutable file."""

    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    """Resolved immutable metadata before payload transfer."""

    provider: str
    source: str
    revision: str
    license_id: str
    license_path: str
    files: tuple[ArtifactFile, ...]


@dataclass(frozen=True, slots=True)
class DownloadOptions:
    """Caller policy for one bounded provider-neutral transfer."""

    provider: str
    source: str
    revision: str
    destination: Path
    receipt: Path | None = None
    max_bytes: int = _DEFAULT_MAX_BYTES
    apply: bool = False
    destination_identity: str | None = None


class Provider(Protocol):
    """Existing provider adapter boundary; no transfer engine is implemented here."""

    name: str

    def plan(self, source: str, revision: str) -> DownloadPlan:
        """Resolve immutable metadata without transferring payload bytes."""
        ...

    def download(self, plan: DownloadPlan, destination: Path) -> None:
        """Transfer the already-reviewed plan into the destination."""
        ...

    def version(self) -> str:
        """Return the exact executing provider version."""
        ...


class ArtifactError(RuntimeError):
    """Bounded artifact refusal without provider body or secret values."""


def _sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_CHUNK):
            value.update(block)
    return value.hexdigest()


def _relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ArtifactError("provider file path is unsafe")
    return path


def _project_path(repo_root: Path, value: Path) -> Path:
    if value.is_absolute() or ".." in value.parts or not value.parts:
        raise ArtifactError("artifact output path must be project-local")
    root = repo_root.resolve()
    resolved = (root / value).resolve()
    if root not in resolved.parents:
        raise ArtifactError("artifact output path must be project-local")
    return resolved


def _validated_plan(options: DownloadOptions, plan: DownloadPlan) -> DownloadPlan:
    if plan.provider != options.provider or plan.source != options.source:
        raise ArtifactError("provider plan identity does not match request")
    if plan.revision != options.revision:
        raise ArtifactError("provider plan revision does not match immutable request")
    paths = [item.path for item in plan.files]
    if not paths or paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ArtifactError("provider file inventory is empty, duplicate, or unordered")
    total = 0
    for item in plan.files:
        _relative(item.path)
        if item.size < 0 or not re.fullmatch(r"[0-9a-f]{64}", item.sha256):
            raise ArtifactError("provider file metadata is invalid")
        total += item.size
    if not _LICENSE.fullmatch(plan.license_id) or plan.license_path not in paths:
        raise ArtifactError("provider license evidence is invalid or absent")
    if total > options.max_bytes:
        raise ArtifactError("provider plan exceeds the configured byte limit")
    return plan


def _provider_plan(options: DownloadOptions, provider: Provider) -> tuple[DownloadPlan, str]:
    """Call provider metadata seams without retaining provider bodies or exceptions."""
    try:
        plan = provider.plan(options.source, options.revision)
        version = provider.version()
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ArtifactError("provider adapter failed without retained provider output") from None
    return _validated_plan(options, plan), version


def _provider_download(provider: Provider, plan: DownloadPlan, staging: Path) -> None:
    """Call the byte-transfer seam without retaining provider bodies or exceptions."""
    try:
        provider.download(plan, staging)
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ArtifactError("provider adapter failed without retained provider output") from None


def _atomic_receipt(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    backup = path.parent / f".{path.name}.previous"
    installed = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _require_absent_backup(backup)
        if path.exists():
            path.replace(backup)
        Path(temporary).replace(path)
        installed = True
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError, ArtifactError:
        Path(temporary).unlink(missing_ok=True)
        if installed:
            path.unlink(missing_ok=True)
        if backup.exists():
            backup.replace(path)
        raise
    backup.unlink(missing_ok=True)


def _require_absent_backup(backup: Path) -> None:
    if backup.exists():
        raise ArtifactError("stale receipt recovery state exists")


def _receipt(options: DownloadOptions, plan: DownloadPlan, status: str) -> dict[str, object]:
    if options.destination_identity is None:
        raise ArtifactError("project-relative destination identity is required")
    destination_identity = _relative(options.destination_identity).as_posix()
    if destination_identity != options.destination_identity:
        raise ArtifactError("project-relative destination identity is not canonical")
    return {
        "schema_version": 1,
        "status": status,
        "provider": plan.provider,
        "provider_version": "unavailable",
        "source": plan.source,
        "revision": plan.revision,
        "license_id": plan.license_id,
        "license_path": plan.license_path,
        "destination_sha256": hashlib.sha256(destination_identity.encode()).hexdigest(),
        "bytes_total": sum(item.size for item in plan.files),
        "files": [asdict(item) for item in plan.files],
    }


def _verify(destination: Path, plan: DownloadPlan) -> None:
    root = destination.resolve()
    expected = {destination / _relative(item.path) for item in plan.files}
    observed: set[Path] = set()
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ArtifactError("downloaded artifact contains a symbolic link")
        if path.is_file():
            observed.add(path)
    if observed != expected:
        raise ArtifactError("downloaded artifact inventory does not match the plan")
    for item in plan.files:
        path = destination / _relative(item.path)
        if path.is_symlink() or root not in path.resolve().parents:
            raise ArtifactError("downloaded artifact escaped the destination")
        if not path.is_file() or path.stat().st_size != item.size or _sha(path) != item.sha256:
            raise ArtifactError("downloaded artifact bytes do not match the plan")


def _publish_download(destination: Path, staging: Path) -> Path | None:
    """Publish staging while retaining the prior tree for receipt commit."""
    parent = destination.parent
    backup = parent / f".{destination.name}.previous"
    if backup.exists():
        raise ArtifactError("stale artifact recovery state exists")
    had_destination = destination.exists()
    if had_destination:
        if destination.is_symlink():
            raise ArtifactError("artifact destination is a symbolic link")
        destination.replace(backup)
    try:
        staging.replace(destination)
        descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        if destination.exists():
            shutil.rmtree(destination)
        if had_destination and backup.exists():
            backup.replace(destination)
        raise
    return backup if had_destination else None


def _rollback_download(destination: Path, backup: Path | None) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    if backup is not None and backup.exists():
        backup.replace(destination)


def _finish_download(backup: Path | None) -> None:
    if backup is not None and backup.exists():
        shutil.rmtree(backup)


def _apply(
    options: DownloadOptions,
    provider: Provider,
    plan: DownloadPlan,
    planned: dict[str, object],
    receipt: Path,
) -> None:
    attempt_receipt = receipt.parent / f"{receipt.name}.attempt"
    _atomic_receipt(attempt_receipt, planned)
    options.destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{options.destination.name}.download-",
            dir=options.destination.parent,
        )
    )
    backup: Path | None = None
    published = False
    try:
        _provider_download(provider, plan, staging)
        _verify(staging, plan)
        backup = _publish_download(options.destination, staging)
        published = True
        _atomic_receipt(receipt, {**planned, "status": "complete"})
    except BaseException as error:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        if published:
            _rollback_download(options.destination, backup)
        _atomic_receipt(attempt_receipt, {**planned, "status": "failed"})
        raise
    _finish_download(backup)
    attempt_receipt.unlink(missing_ok=True)


def download(options: DownloadOptions, *, provider: Provider) -> int:
    """Plan by default; transfer only with explicit apply and publish atomic receipts."""
    if not _COMMIT.fullmatch(options.revision):
        raise ArtifactError("revision must be a full immutable commit")
    if not _SOURCE.fullmatch(options.source):
        raise ArtifactError("source must be a credential-free repository identifier")
    if not _TOKEN.fullmatch(options.provider):
        raise ArtifactError("provider identifier is invalid")
    if options.max_bytes < 0:
        raise ArtifactError("maximum byte limit is invalid")
    plan, provider_version = _provider_plan(options, provider)
    receipt = options.receipt or options.destination / ".artifact-receipt.json"
    try:
        receipt_relative = receipt.relative_to(options.destination).as_posix()
    except ValueError:
        receipt_relative = ""
    if receipt_relative in {item.path for item in plan.files}:
        raise ArtifactError("receipt path collides with the reviewed artifact inventory")
    planned = _receipt(options, plan, "planned")
    if not _TOKEN.fullmatch(provider_version):
        raise ArtifactError("provider version is invalid")
    planned["provider_version"] = provider_version
    if not options.apply:
        _atomic_receipt(receipt, planned)
        return 0
    _apply(options, provider, plan, planned, receipt)
    return 0


def main(repo_root: Path, argv: list[str], *, provider: Provider | None = None) -> int:
    """Public CLI; real providers remain unavailable until separately reviewed."""
    parser = argparse.ArgumentParser(prog="kb-setup artifact-download")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--max-bytes", type=int, default=_DEFAULT_MAX_BYTES)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if provider is None or provider.name != args.provider:
        print("artifact download refused: provider adapter is unavailable", file=sys.stderr)
        return 2
    try:
        destination = _project_path(repo_root, args.destination)
        receipt = _project_path(repo_root, args.receipt) if args.receipt is not None else None
        destination_identity = args.destination.as_posix()
        return download(
            DownloadOptions(
                args.provider,
                args.source,
                args.revision,
                destination,
                receipt,
                args.max_bytes,
                args.apply,
                destination_identity,
            ),
            provider=provider,
        )
    except ArtifactError as error:
        print(f"artifact download refused: {error}", file=sys.stderr)
        return 2
