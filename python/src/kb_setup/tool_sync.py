# Copyright (c) 2026 Raymond Manaloto
"""Synchronize one reviewed mise pin without leaving partial repository state."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup.currency import config, skill, sync
from kb_setup.graphify_env import clean_env

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

_TIMEOUT = 600
_WARNING = re.compile(r"\bwarn(?:ing)?\b", re.IGNORECASE)


@dataclass(frozen=True)
class _Snapshot:
    """A private copy of every repository path the lifecycle may rewrite."""

    backup_root: Path
    paths: tuple[Path, ...]
    present: tuple[bool, ...]


class ToolSyncError(RuntimeError):
    """A bounded public refusal; upstream output is represented only by a digest."""


def _diagnostic(proc: subprocess.CompletedProcess[str]) -> str:
    raw = proc.stdout.encode() + b"\0" + proc.stderr.encode()
    return f"bytes={len(raw) - 1} sha256={hashlib.sha256(raw).hexdigest()}"


def _run(argv: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Run one lifecycle command in the scrubbed project environment."""
    return subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
        env=clean_env(),
    )


def _mise_progress_only(stderr: str, spec: ToolSpec) -> bool:
    """Recognize only mise's bounded ordinary install-status lines."""
    lines = stderr.splitlines()
    pattern = re.compile(
        rf"^mise {re.escape(spec.mise_key)}@[^\s]+\s+⇢\s+"
        r"(?:already installed|installed)$"
    )
    return bool(lines) and all(pattern.fullmatch(line) is not None for line in lines)


def _checked(
    label: str,
    argv: list[str],
    repo_root: Path,
    *,
    progress_spec: ToolSpec | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = _run(argv, repo_root)
    stderr_refused = bool(proc.stderr) and not (
        progress_spec is not None and _mise_progress_only(proc.stderr, progress_spec)
    )
    warning = stderr_refused or _WARNING.search(proc.stdout) is not None
    if proc.returncode != 0 or warning:
        raise ToolSyncError(f"{label} refused: rc={proc.returncode}; {_diagnostic(proc)}")
    return proc


def _copy_path(source: Path, destination: Path) -> None:
    if source.is_symlink():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source.readlink())
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)


def _snapshot(paths: tuple[Path, ...]) -> _Snapshot:
    backup_root = Path(tempfile.mkdtemp(prefix="kb-tool-sync-"))
    present: list[bool] = []
    try:
        for index, path in enumerate(paths):
            exists = path.exists() or path.is_symlink()
            present.append(exists)
            if exists:
                _copy_path(path, backup_root / str(index))
    except BaseException:
        shutil.rmtree(backup_root, ignore_errors=True)
        raise
    return _Snapshot(backup_root, paths, tuple(present))


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _fsync_tree(path: Path) -> None:
    if path.is_file() and not path.is_symlink():
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    elif path.is_dir() and not path.is_symlink():
        for child in path.iterdir():
            _fsync_tree(child)
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _restore(snapshot: _Snapshot) -> None:
    """Restore bytes, links, modes, and absence, then durably sync parent directories."""
    failures = 0
    for index, (path, existed) in enumerate(zip(snapshot.paths, snapshot.present, strict=True)):
        try:
            _remove(path)
            if existed:
                _copy_path(snapshot.backup_root / str(index), path)
        except OSError:
            failures += 1
    for path, existed in zip(snapshot.paths, snapshot.present, strict=True):
        try:
            if existed:
                _fsync_tree(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            failures += 1
    if failures:
        raise ToolSyncError(
            f"rollback durability failed; recovery snapshot retained at {snapshot.backup_root}"
        )


def _close(snapshot: _Snapshot) -> None:
    shutil.rmtree(snapshot.backup_root, ignore_errors=True)


def _selection(repo_root: Path, args: list[str]) -> tuple[ToolSpec, str]:
    if len(args) != 1:
        raise ToolSyncError("usage: kb-setup tool-sync <currency-tool-name>")
    specs = config.load(repo_root)
    matches = [item for item in specs if item.name == args[0]]
    if len(matches) != 1:
        raise ToolSyncError("tool selection is unknown or duplicated")
    spec = matches[0]
    owners = [item for item in specs if item.mise_key and item.mise_key == spec.mise_key]
    if spec.python_package or spec.self_managed or spec.source_only or not spec.mise_key:
        raise ToolSyncError("tool is not solely owned by one mise pin")
    if len(owners) != 1:
        raise ToolSyncError("mise ownership is duplicated")
    distribution = spec.mise_key.split(":", 1)[-1].split("@", 1)[0]
    if _python_dependency_owns(repo_root, distribution):
        raise ToolSyncError("tool also has a Python dependency owner")
    if spec.manifest:
        raise ToolSyncError("manifest-bearing tools require the separate provenance workflow")
    if spec.skill_dir:
        raise ToolSyncError("generated-skill tools are outside this public mise-only workflow")
    skill_path = Path(spec.skill_dir or ".")
    if skill_path.is_absolute() or ".." in skill_path.parts:
        raise ToolSyncError("generated skill path must stay inside the repository")
    pinned, _extras = sync.pinned_version(repo_root, spec)
    if not re.fullmatch(r"v?\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?|[0-9a-f]{40}", pinned):
        raise ToolSyncError("mise pin is missing or not exact")
    return spec, pinned


def eligible_tools(repo_root: Path) -> tuple[str, ...]:
    """Current tools this deliberately narrow command can truthfully synchronize."""
    eligible: list[str] = []
    for spec in config.load(repo_root):
        try:
            selected, _pinned = _selection(repo_root, [spec.name])
        except ToolSyncError:
            continue
        eligible.append(selected.name)
    return tuple(eligible)


def _requirement_name(requirement: object) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", str(requirement))
    return re.sub(r"[-_.]+", "-", match.group(1)).lower() if match else ""


def _python_dependency_owns(repo_root: Path, tool: str) -> bool:
    """Whether an installable pyproject table also claims the selected distribution."""
    try:
        with (repo_root / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ToolSyncError("Python dependency ownership source is unreadable") from exc
    normalized = re.sub(r"[-_.]+", "-", tool).lower()
    values: list[object] = []
    project = data.get("project")
    if isinstance(project, dict):
        dependencies = project.get("dependencies")
        if isinstance(dependencies, list):
            values.extend(dependencies)
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    values.extend(group)
    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        for group in groups.values():
            if isinstance(group, list):
                values.extend(group)
    return any(_requirement_name(value) == normalized for value in values)


def _lock_converged(repo_root: Path, spec: ToolSpec, pinned: str) -> None:
    """Require mise's dry-run JSON to report no remaining version movement."""
    proc = _checked(
        "lock convergence",
        ["mise", "lock", spec.mise_key, "--dry-run", "--json"],
        repo_root,
    )
    if proc.stdout.strip() != "[]":
        raise ToolSyncError("selected lock did not converge to the reviewed pin")
    try:
        lock = tomllib.loads((repo_root / "mise.lock").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ToolSyncError("selected lock is unreadable") from exc
    tools = lock.get("tools")
    entries = tools.get(spec.mise_key) if isinstance(tools, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ToolSyncError("selected tool has no deterministic lock entry")
    versions = {str(entry.get("version") or "") for entry in entries if isinstance(entry, dict)}
    if versions != {pinned}:
        raise ToolSyncError("selected lock entry does not bind the reviewed pin")


def _observed(repo_root: Path, spec: ToolSpec) -> str:
    proc = _checked(
        "version probe",
        ["mise", "exec", "--", spec.binary, *spec.version_args],
        repo_root,
    )
    text = proc.stdout.strip()
    if spec.version_pattern:
        match = re.search(spec.version_pattern, text)
        return match.group(1).lstrip("v") if match else ""
    fields = text.split()
    return fields[-1].lstrip("v") if fields else ""


def _same_version(left: str, right: str) -> bool:
    match_left = re.fullmatch(r"v?(\d+(?:\.\d+)*)", left)
    match_right = re.fullmatch(r"v?(\d+(?:\.\d+)*)", right)
    if match_left is None or match_right is None:
        return left == right
    parts = []
    for match in (match_left, match_right):
        value = [int(piece) for piece in match.group(1).split(".")]
        while len(value) > 1 and value[-1] == 0:
            value.pop()
        parts.append(tuple(value))
    return parts[0] == parts[1]


def _validate_observed(observed: str, pinned: str) -> None:
    if not observed or not _same_version(observed, pinned):
        raise ToolSyncError("installed executable does not match the exact reviewed pin")


def _validate_skill(result: skill.SkillResult) -> None:
    if result.ran and not (result.process_warning or result.lost_addenda or result.unrepaired):
        return
    raise ToolSyncError(
        "generated skill refresh refused: "
        f"bytes={result.diagnostic_bytes} sha256={result.diagnostic_sha256 or 'none'}"
    )


def _sync(repo_root: Path, spec: ToolSpec, pinned: str) -> None:
    paths = (repo_root / "mise.lock", *skill.transaction_paths(repo_root, spec))
    resolved = tuple(path.resolve(strict=False) for path in paths)
    for index, path in enumerate(resolved):
        others = resolved[:index] + resolved[index + 1 :]
        if any(path == other or path in other.parents or other in path.parents for other in others):
            raise ToolSyncError("transaction paths overlap")
    snapshot = _snapshot(paths)
    try:
        _checked("lock", ["mise", "lock", spec.mise_key], repo_root)
        _lock_converged(repo_root, spec, pinned)
        _checked(
            "install",
            ["mise", "install", spec.mise_key],
            repo_root,
            progress_spec=spec,
        )
        observed = _observed(repo_root, spec)
        _validate_observed(observed, pinned)
        if spec.skill_dir:
            _validate_skill(skill.refresh(repo_root, spec))
        for path in paths:
            if path.exists() or path.is_symlink():
                _fsync_tree(path)
    except BaseException:
        _restore(snapshot)
        _close(snapshot)
        raise
    _close(snapshot)


def main(repo_root: Path, args: list[str]) -> int:
    """Lock, install, and version-verify one eligible exact mise-only pin."""
    try:
        spec, pinned = _selection(repo_root, args)
        _sync(repo_root, spec, pinned)
    except ToolSyncError as exc:
        print(f"[tool-sync] {exc}")
        return 1
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        token = hashlib.sha256(type(exc).__name__.encode()).hexdigest()
        print(f"[tool-sync] lifecycle failed: error_sha256={token}")
        return 1
    print(f"[tool-sync] {spec.name} {pinned}: lock, install, and version verified")
    return 0
