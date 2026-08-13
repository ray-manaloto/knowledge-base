# Copyright (c) 2026 Raymond Manaloto
"""Install one reviewed mise pin, lock it, and refresh its generated skills."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import graphify_env
from kb_setup.currency import config, skill, sync

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

_TIMEOUT = 600


def _run(argv: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Run one mise lifecycle step with its real exit code and bounded time."""
    return subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
    )


def _show_failure(label: str, result: subprocess.CompletedProcess[str]) -> int:
    """Render a failed lifecycle step without hiding its actual return code."""
    detail = (result.stderr or result.stdout or "no output").strip().splitlines()[-3:]
    print(f"[tool-sync] {label} FAILED rc={result.returncode}: {' / '.join(detail)}")
    return result.returncode


def _observed_via_mise(repo_root: Path, spec: ToolSpec) -> str:
    """Read the installed version through mise, independent of inherited PATH."""
    result = _run(["mise", "exec", "--", spec.binary, *spec.version_args], repo_root)
    if result.returncode != 0:
        return ""
    output = (result.stdout or result.stderr).strip()
    if spec.version_pattern:
        match = re.search(spec.version_pattern, output)
        return match.group(1).lstrip("v") if match else ""
    fields = output.split()
    return fields[-1].lstrip("v") if fields else ""


def _selection(repo_root: Path, args: list[str]) -> tuple[ToolSpec, str] | None:
    """Resolve a valid mise-managed tool and its exact reviewed pin."""
    if len(args) != 1:
        print("kb-setup tool-sync <currency-tool-name>")
        return None
    name = args[0]
    spec = next((item for item in config.load(repo_root) if item.name == name), None)
    if spec is None:
        print(f"[tool-sync] unknown tool {name!r}")
        return None
    if not spec.mise_key:
        print(f"[tool-sync] {name} is not installed from mise.toml")
        return None
    pinned, _extras = sync.pinned_version(repo_root, spec)
    if not pinned:
        print(f"[tool-sync] mise.toml has no exact pin for {spec.mise_key!r}")
        return None
    return spec, pinned


def _sync(repo_root: Path, spec: ToolSpec, pinned: str) -> int:
    """Run the ordered lock, install, skill, and executable-proof stages."""
    lock = _run(["mise", "lock", spec.mise_key], repo_root)
    if lock.returncode != 0:
        return _show_failure("lock", lock)
    install = _run(["mise", "install", spec.mise_key], repo_root)
    if install.returncode != 0:
        return _show_failure("install", install)

    observed = _observed_via_mise(repo_root, spec)
    if observed != pinned:
        print(
            f"[tool-sync] version mismatch after install: {spec.binary} reports "
            f"{observed or 'UNKNOWN'}, pin is {pinned}"
        )
        return 1
    if spec.name == "graphify":
        sdk = _run(
            [
                graphify_env.graphify_python(repo_root),
                "-c",
                (
                    "from pathlib import Path; from graphify.detect import detect; "
                    "r=detect(Path('.graphify-sdk-probe-missing')); "
                    "assert r['total_files'] == 0"
                ),
            ],
            repo_root,
        )
        if sdk.returncode != 0:
            return _show_failure("public SDK probe", sdk)
    if spec.skill_dir:
        refreshed = skill.refresh(repo_root, spec)
        if not refreshed.ran or refreshed.lost_addenda or refreshed.unrepaired:
            print(f"[tool-sync] skill refresh FAILED: {refreshed.note}")
            return 1
    print(f"[tool-sync] {spec.name} {pinned}: lock, install, and generated skills synchronized")
    return 0


def main(repo_root: Path, args: list[str]) -> int:
    """Synchronize one exact reviewed tool pin through mise and its skill generator."""
    selected = _selection(repo_root, args)
    return _sync(repo_root, *selected) if selected is not None else 2
