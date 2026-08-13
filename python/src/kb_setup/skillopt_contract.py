# Copyright (c) 2026 Raymond Manaloto
"""Strict provenance and public-surface contract for SkillOpt.

Upstream still reports version ``0.2.0`` on its moving ``main`` branch.  That
version is therefore descriptive, never identity: the VCS commit recorded by
``direct_url.json`` is the authority used by every check in this module.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import subprocess
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from skillopt_sleep.__main__ import main as sleep_main
from skillopt_sleep.cycle import run_sleep_cycle

SKILLOPT_COMMIT = "93bdf3d770b99128daf35278218e5a666fe392f3"
SKILLOPT_REPOSITORY = "https://github.com/microsoft/SkillOpt"
_EXPECTED_ENTRY_POINTS = {
    "skillopt-eval": "scripts.eval_only:main",
    "skillopt-sleep": "skillopt_sleep.__main__:main",
    "skillopt-train": "scripts.train:main",
}
_EXPECTED_HELP_SHA256 = {
    "skillopt-eval": "ebf79f8bf6965bd0012169cfa84d52ff09548d4bc8d1bbd4a7d7094d3e76aca2",
    "skillopt-sleep": "a1328faed317909735dc62829477fa533cef19cbf070d3d637e43356518a3f14",
    "skillopt-train": "6ac1202e271be60f61f07aaca331d23255ea625a9472979af645b345b2d36365",
}
_AUDITED_DRY_RUN = r"""
import os
import runpy
import sys
from pathlib import Path

allowed = Path(os.environ["SKILLOPT_CONTRACT_ROOT"]).resolve()

def audit(event, args):
    candidate = None
    writing = False
    if event == "open" and args:
        candidate = args[0]
        mode = args[1] if len(args) > 1 else "r"
        flags = args[2] if len(args) > 2 else 0
        writing = any(token in str(mode) for token in "wax+") or bool(flags & 0x3)
    elif event in {"os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.replace", "os.unlink"}:
        candidate = args[0] if args else None
        writing = True
    if writing and isinstance(candidate, (str, bytes, os.PathLike)):
        target = Path(os.fsdecode(candidate)).resolve()
        if target != allowed and allowed not in target.parents:
            raise PermissionError(f"SkillOpt attempted external write: {target}")

sys.addaudithook(audit)
sys.argv = ["skillopt-sleep", *sys.argv[1:]]
runpy.run_module("skillopt_sleep", run_name="__main__")
"""


@dataclass(frozen=True)
class PublicSymbol:
    """One reviewed public function and its runtime signature."""

    dotted_name: str
    function: Callable[..., object]
    expected_signature: str


_PUBLIC_SYMBOLS = (
    PublicSymbol("skillopt_sleep.__main__.main", sleep_main, "(argv=None) -> 'int'"),
    PublicSymbol(
        "skillopt_sleep.cycle.run_sleep_cycle",
        run_sleep_cycle,
        "(cfg: 'Optional[SleepConfig]' = None, *, seed_tasks: 'Optional[List[TaskRecord]]' = "
        "None, dry_run: 'bool' = False, clock: 'Optional[float]' = None, backend: "
        "'Optional[Backend]' = None) -> 'CycleOutcome'",
    ),
)


def installed_direct_url() -> dict[str, object]:
    """Return the installed distribution's PEP 610 provenance record."""
    raw = metadata.distribution("skillopt").read_text("direct_url.json")
    if raw is None:
        return {}
    payload = json.loads(raw)
    return {str(key): value for key, value in payload.items()} if isinstance(payload, dict) else {}


def installed_commit() -> str:
    """Return the exact installed VCS commit, or an empty string when unverifiable."""
    vcs_info = installed_direct_url().get("vcs_info", {})
    return str(vcs_info.get("commit_id") or "") if isinstance(vcs_info, dict) else ""


def public_api_fingerprint() -> tuple[tuple[str, str], ...]:
    """Return the deterministic reviewed function/signature fingerprint."""
    return tuple(
        (symbol.dotted_name, str(inspect.signature(symbol.function))) for symbol in _PUBLIC_SYMBOLS
    )


def console_entrypoint_fingerprint() -> tuple[tuple[str, str], ...]:
    """Return the installed SkillOpt console entry points in stable order."""
    found = {
        entry.name: entry.value
        for entry in metadata.distribution("skillopt").entry_points
        if entry.group == "console_scripts" and entry.name.startswith("skillopt-")
    }
    return tuple(sorted(found.items()))


def contract_errors() -> tuple[str, ...]:
    """Describe every provenance, entry-point, or public-signature mismatch."""
    errors: list[str] = []
    direct_url = installed_direct_url()
    if direct_url.get("url") != SKILLOPT_REPOSITORY:
        errors.append(
            f"skillopt direct_url is {direct_url.get('url')!r}, expected {SKILLOPT_REPOSITORY!r}"
        )
    commit = installed_commit()
    if commit != SKILLOPT_COMMIT:
        errors.append(f"skillopt installed commit {commit or 'UNKNOWN'} != {SKILLOPT_COMMIT}")
    expected_entrypoints = tuple(sorted(_EXPECTED_ENTRY_POINTS.items()))
    actual_entrypoints = console_entrypoint_fingerprint()
    if actual_entrypoints != expected_entrypoints:
        errors.append(
            f"skillopt console entry points changed: expected {expected_entrypoints}; "
            f"got {actual_entrypoints}"
        )
    for symbol in _PUBLIC_SYMBOLS:
        actual = str(inspect.signature(symbol.function))
        if actual != symbol.expected_signature:
            errors.append(
                f"{symbol.dotted_name} signature changed: expected "
                f"{symbol.expected_signature}; got {actual}"
            )
    return tuple(errors)


def assert_public_contract() -> None:
    """Fail closed unless installed SkillOpt matches the reviewed contract."""
    errors = contract_errors()
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(f"SkillOpt public contract failed:\n{details}")


def repository_contract_errors(repo_root: Path) -> tuple[str, ...]:
    """Cross-bind pyproject, uv lock, manifest, mise, and installed provenance."""
    errors: list[str] = []
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = _skillopt_requirements(pyproject)
    expected = f"skillopt @ git+{SKILLOPT_REPOSITORY}@{SKILLOPT_COMMIT}"
    if requirements != [expected]:
        errors.append(
            f"pyproject must declare exactly one SkillOpt requirement {expected!r}; "
            f"got {requirements!r}"
        )
    with (repo_root / "uv.lock").open("rb") as handle:
        locked = tomllib.load(handle)
    skillopt_packages = [
        package
        for package in locked.get("package", [])
        if isinstance(package, dict) and package.get("name") == "skillopt"
    ]
    expected_locked_url = f"{SKILLOPT_REPOSITORY}?rev={SKILLOPT_COMMIT}#{SKILLOPT_COMMIT}"
    locked_urls = [
        package.get("source", {}).get("git")
        for package in skillopt_packages
        if isinstance(package.get("source"), dict)
    ]
    if locked_urls != [expected_locked_url]:
        errors.append("uv.lock does not contain exactly one reviewed SkillOpt source revision")
    manifest = _read_manifest(repo_root / "sources" / "skillopt.manifest")
    if manifest.get("url") != SKILLOPT_REPOSITORY:
        errors.append("sources/skillopt.manifest origin does not match the reviewed repository")
    if manifest.get("commit") != SKILLOPT_COMMIT:
        errors.append("sources/skillopt.manifest commit does not match the reviewed revision")
    clone = repo_root / "sources" / "skillopt"
    clone_head = _git(clone, "rev-parse", "HEAD")
    if clone_head != SKILLOPT_COMMIT:
        errors.append(f"sources/skillopt clone HEAD is {clone_head or 'UNAVAILABLE'}")
    clone_status = _git(clone, "status", "--porcelain", "--untracked-files=no")
    if clone_status:
        errors.append("sources/skillopt clone has tracked modifications")
    mise = tomllib.loads((repo_root / "mise.toml").read_text(encoding="utf-8"))
    owners = _mise_skillopt_owners(mise.get("tools", {}))
    if owners:
        errors.append(f"mise duplicates SkillOpt dependency ownership: {owners}")
    settings = json.loads((repo_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    if any("skillopt" in str(name).lower() for name in settings.get("enabledPlugins", {})):
        errors.append("mutable SkillOpt marketplace plugin is enabled")
    if any("skillopt" in str(name).lower() for name in settings.get("extraKnownMarketplaces", {})):
        errors.append("mutable SkillOpt marketplace source remains configured")
    return tuple(errors)


def _skillopt_requirements(pyproject: dict[str, object]) -> list[str]:
    """Find SkillOpt across every installable PEP 508 dependency table."""
    candidates: list[object] = []
    project = pyproject.get("project", {})
    if isinstance(project, dict):
        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, list):
            candidates.extend(dependencies)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for values in optional.values():
                if isinstance(values, list):
                    candidates.extend(values)
    groups = pyproject.get("dependency-groups", {})
    if isinstance(groups, dict):
        for values in groups.values():
            if isinstance(values, list):
                candidates.extend(values)
    return [
        str(value)
        for value in candidates
        if re.match(r"^skillopt(?:\[|\s|@|=|<|>|!|~|$)", str(value), re.IGNORECASE)
    ]


def _mise_skillopt_owners(tools: object) -> list[str]:
    """Find SkillOpt in mise tool keys or nested backend/value declarations."""
    owners: list[str] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if "skillopt" in str(key).lower():
                    owners.append(child_path)
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif "skillopt" in str(value).lower():
            owners.append(path)

    visit(tools, "tools")
    return sorted(set(owners))


def _read_manifest(path: Path) -> dict[str, str]:
    """Parse the repository's simple unquoted source-manifest format."""
    fields: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
    return fields


def _git(repo: Path, *args: str) -> str:
    """Read one bounded local git fact without accepting stderr as evidence."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 and not result.stderr else ""


def cli_help_fingerprint(repo_root: Path) -> tuple[tuple[str, str], ...]:
    """Run every installed console entry point's help without user-global lookup."""
    bin_dir = repo_root / ".venv" / "bin"
    fingerprint: list[tuple[str, str]] = []
    for name in sorted(_EXPECTED_ENTRY_POINTS):
        executable = bin_dir / name
        if not executable.is_file():
            raise RuntimeError(f"SkillOpt CLI contract failed: missing {executable}")
        result = subprocess.run(
            [str(executable), "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0 or result.stderr:
            raise RuntimeError(
                f"SkillOpt CLI contract failed for {name}: rc={result.returncode}; "
                f"stderr={result.stderr!r}"
            )
        digest = hashlib.sha256(result.stdout.encode()).hexdigest()
        if digest != _EXPECTED_HELP_SHA256[name]:
            raise RuntimeError(
                f"SkillOpt CLI help changed for {name}: expected "
                f"{_EXPECTED_HELP_SHA256[name]}; got {digest}"
            )
        fingerprint.append((name, digest))
    return tuple(fingerprint)


def mock_dry_run_probe(repo_root: Path) -> None:
    """Run a fresh-process mock dry-run with every user-state root isolated."""
    with tempfile.TemporaryDirectory(prefix=".skillopt-contract-", dir=repo_root) as raw_root:
        root = Path(raw_root)
        project = root / "project"
        claude_home = root / "claude"
        codex_home = root / "codex"
        project.mkdir()
        claude_home.mkdir()
        codex_home.mkdir()
        argv = [
            str(repo_root / ".venv" / "bin" / "python"),
            "-c",
            _AUDITED_DRY_RUN,
            "dry-run",
            "--project",
            str(project),
            "--backend",
            "mock",
            "--claude-home",
            str(claude_home),
            "--codex-home",
            str(codex_home),
            "--max-sessions",
            "1",
            "--max-tasks",
            "1",
            "--json",
        ]
        isolated_home = root / "home"
        isolated_home.mkdir()
        config_dir = isolated_home / ".skillopt-sleep"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "state_dir": str(project / ".agent" / "skillopt-probe"),
                    "evidence_log": False,
                    "auto_adopt": False,
                    "target_skill_path": "",
                }
            ),
            encoding="utf-8",
        )
        env = {
            "HOME": str(isolated_home),
            "PATH": f"{repo_root / '.venv' / 'bin'}:/usr/bin:/bin",
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_STATE_HOME": str(root / "xdg-state"),
            "SKILLOPT_CONTRACT_CANARY": "contract-canary-must-not-escape",
            "SKILLOPT_CONTRACT_ROOT": str(project),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = subprocess.run(
            argv,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0 or result.stderr:
            raise RuntimeError(
                f"SkillOpt mock dry-run failed: rc={result.returncode}; stderr={result.stderr!r}"
            )
        canary = env["SKILLOPT_CONTRACT_CANARY"]
        if canary in result.stdout or any(
            canary in path.read_text(encoding="utf-8", errors="replace")
            for path in root.rglob("*")
            if path.is_file()
        ):
            raise RuntimeError("SkillOpt mock dry-run leaked the contract canary")


def locked_sync_is_stable(repo_root: Path) -> None:
    """Prove the reviewed lock resolves without changing a byte of it."""
    lock = repo_root / "uv.lock"
    before = lock.read_bytes()
    result = subprocess.run(
        ["uv", "sync", "--locked"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SkillOpt locked sync failed: rc={result.returncode}; stderr={result.stderr!r}"
        )
    if not _uv_progress_only(result.stderr):
        raise RuntimeError(f"SkillOpt locked sync emitted unexpected stderr: {result.stderr!r}")
    if lock.read_bytes() != before:
        raise RuntimeError("SkillOpt locked sync changed uv.lock bytes")


def _uv_progress_only(stderr: str) -> bool:
    """Accept only uv's status transport; warnings and unknown lines are failures."""
    allowed = (
        r"Resolved \d+ packages in .+",
        r"Audited \d+ packages in .+",
        r"Checked \d+ packages in .+",
    )
    return all(
        any(re.fullmatch(pattern, line) for pattern in allowed) for line in stderr.splitlines()
    )


def contract_main(repo_root: Path) -> int:
    """Verify provenance, public APIs, CLI help, lock stability, and mock isolation."""
    assert_public_contract()
    repository_errors = repository_contract_errors(repo_root)
    if repository_errors:
        details = "\n- ".join(repository_errors)
        raise RuntimeError(f"SkillOpt repository contract failed:\n- {details}")
    help_fingerprint = cli_help_fingerprint(repo_root)
    locked_sync_is_stable(repo_root)
    mock_dry_run_probe(repo_root)
    print(f"SkillOpt provenance/API contract PASS: {SKILLOPT_COMMIT}")
    for name, value in (*public_api_fingerprint(), *console_entrypoint_fingerprint()):
        print(f"  {name}: {value}")
    for name, digest in help_fingerprint:
        print(f"  {name} --help sha256:{digest}")
    return 0
