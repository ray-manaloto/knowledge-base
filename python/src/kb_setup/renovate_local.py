# Copyright (c) 2026 Raymond Manaloto
"""Run the repository's pinned Renovate updater locally without writing PRs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RENOVATE_VERSION = "44.115.10"
EXPECTED_MANAGERS = frozenset({"mise", "pep621", "github-actions"})
MANUALLY_QUALIFIED = frozenset({"graphifyy"})
EXPECTED_SKIPS = frozenset(
    {
        (".github/workflows/graphify-live-receipt.yml", "ubuntu", "invalid-version"),
        ("pyproject.toml", "skillopt", "invalid-value"),
        ("pyproject.toml", "hatchling", "unspecified-version"),
    }
)
TOKEN_NAMES = ("GITHUB_COM_TOKEN", "RENOVATE_GITHUB_COM_TOKEN", "GITHUB_TOKEN")


def _token(env: dict[str, str]) -> str | None:
    return next((env[name] for name in TOKEN_NAMES if env.get(name)), None)


def _with_lookup_token(env: dict[str, str]) -> dict[str, str]:
    """Reuse a local GitHub CLI keyring when no token was explicitly supplied."""
    if _token(env):
        return env
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=False, timeout=10
        )
    except OSError, subprocess.TimeoutExpired:
        return env
    if result.returncode != 0 or not result.stdout.strip():
        return env
    return {**env, "GITHUB_COM_TOKEN": result.stdout.strip()}


def renovate_environment(report: Path, env: dict[str, str]) -> dict[str, str]:
    """Force local-only behavior after repository presets have been resolved."""
    child = dict(env)
    for name in TOKEN_NAMES:
        child.pop(name, None)
    child["RENOVATE_FORCE"] = json.dumps({"cloneSubmodules": False})
    child["RENOVATE_REPORT_TYPE"] = "file"
    child["RENOVATE_REPORT_PATH"] = str(report)
    if token := _token(env):
        child["GITHUB_COM_TOKEN"] = token
    return child


def _package_files(raw: bytes) -> tuple[dict[str, Any], list[Any]]:
    report = json.loads(raw)
    repositories = report.get("repositories")
    if not isinstance(repositories, dict) or not isinstance(repositories.get("local"), dict):
        raise TypeError("Renovate did not report a local repository")
    local = repositories["local"]
    files = local.get("packageFiles")
    if not isinstance(files, dict):
        raise TypeError("Renovate did not report package files")
    problems = local.get("problems") or []
    if not isinstance(problems, list):
        raise TypeError("Renovate problems field is malformed")
    return files, problems


def _dependencies(manager: str, files: object) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(files, list):
        raise TypeError(f"Renovate manager {manager} has invalid package files")
    found: list[tuple[str, dict[str, Any]]] = []
    for package_file in files:
        if not isinstance(package_file, dict) or not isinstance(package_file.get("deps"), list):
            raise TypeError(f"Renovate manager {manager} has invalid dependencies")
        for dependency in package_file["deps"]:
            if not isinstance(dependency, dict):
                raise TypeError(f"Renovate manager {manager} has an invalid dependency")
            found.append((str(package_file.get("packageFile", "")), dependency))
    return found


def summarize_report(raw: bytes) -> dict[str, Any]:
    """Require actual extraction by each configured manager before claiming coverage."""
    package_files, problems = _package_files(raw)
    counts: dict[str, int] = {}
    updates: list[dict[str, str]] = []
    manual_updates: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for manager, files in package_files.items():
        dependencies = _dependencies(manager, files)
        counts[manager] = len(dependencies)
        for filename, dependency in dependencies:
            if reason := dependency.get("skipReason"):
                skipped.append(
                    {
                        "manager": str(manager),
                        "file": filename,
                        "dependency": str(dependency.get("depName", "")),
                        "reason": str(reason),
                    }
                )
            for update in dependency.get("updates") or []:
                if not isinstance(update, dict):
                    raise TypeError("Renovate update is malformed")
                row = {
                    "manager": str(manager),
                    "file": filename,
                    "dependency": str(dependency.get("depName", "")),
                    "from": str(dependency.get("currentValue", "")),
                    "to": str(update.get("newValue", "")),
                }
                (manual_updates if row["dependency"] in MANUALLY_QUALIFIED else updates).append(row)
    missing = sorted(manager for manager in EXPECTED_MANAGERS if counts.get(manager, 0) == 0)
    return {
        "managers": counts,
        "missing_managers": missing,
        "skipped_dependencies": skipped,
        "updates": updates,
        "manual_updates": manual_updates,
        "problems": problems,
    }


def lookup_complete(summary: dict[str, Any], *, token_present: bool) -> bool:
    """Accept only observed managers and the three reviewed nonversion skips."""
    unresolved_skips = [
        row
        for row in summary["skipped_dependencies"]
        if (row["file"], row["dependency"], row["reason"]) not in EXPECTED_SKIPS
    ]
    return token_present and not (
        summary["missing_managers"] or unresolved_skips or summary["problems"]
    )


def _redact(value: str, tokens: Iterable[str]) -> str:
    for token in sorted({item for item in tokens if item}, key=len, reverse=True):
        value = value.replace(token, "[REDACTED_GITHUB_TOKEN]")
    return value


def emit_diagnostics(stdout: str, stderr: str, *, tokens: Iterable[str]) -> None:
    """Retain Renovate's own messages without disclosing its lookup credential."""
    secrets = tuple(tokens)
    for stream_name, output in (("stdout", stdout), ("stderr", stderr)):
        if output:
            safe = _redact(output, secrets)
            print(f"[renovate {stream_name}]\n{safe}", file=sys.stderr, end="\n")


def main(argv: list[str] | None = None) -> int:
    """Show pending updates, or fail a freshness check on drift/incomplete lookup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on pending updates")
    args = parser.parse_args(argv)
    env = _with_lookup_token(dict(os.environ))
    tokens = [env[name] for name in TOKEN_NAMES if env.get(name)]
    with tempfile.TemporaryDirectory(prefix="kb-renovate-") as tmp:
        report = Path(tmp) / "report.json"
        command = [
            "npm",
            "exec",
            "--yes",
            "--allow-scripts=re2",
            "--package",
            f"renovate@{RENOVATE_VERSION}",
            "--",
            "renovate",
            "--platform=local",
            "--dry-run=lookup",
        ]
        try:
            run = subprocess.run(
                command,
                env=renovate_environment(report, env),
                capture_output=True,
                text=True,
                check=False,
                timeout=900,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Renovate lookup did not finish: {type(exc).__name__}", file=sys.stderr)
            return 2
        # Keep the subprocess diagnostics in the caller's captured stream. Never
        # print the lookup credential even when Renovate echoes it unexpectedly.
        emit_diagnostics(run.stdout, run.stderr, tokens=tokens)
        if run.returncode != 0 or not report.is_file():
            print(
                f"Renovate lookup failed: rc={run.returncode}, report={report.is_file()}",
                file=sys.stderr,
            )
            return 2
        try:
            summary = summarize_report(report.read_bytes())
        except (OSError, ValueError, TypeError) as exc:
            print(f"Renovate report invalid: {exc}", file=sys.stderr)
            return 2
    complete = lookup_complete(summary, token_present=bool(_token(env)))
    summary["complete"] = complete
    summary["check"] = args.check
    print(_redact(json.dumps(summary, sort_keys=True, indent=2), tokens))
    if args.check and not complete:
        return 2
    return int(args.check and bool(summary["updates"]))


if __name__ == "__main__":
    raise SystemExit(main())
