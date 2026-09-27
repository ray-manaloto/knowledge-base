# Copyright (c) 2026 Raymond Manaloto
"""Negative controls for the local dependency-updater evidence boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup.renovate_local import (
    emit_diagnostics,
    lookup_complete,
    renovate_environment,
    summarize_report,
)


def _report(*, remove_manager: str | None = None, skipped: bool = False) -> bytes:
    package_files = {
        manager: [
            {
                "packageFile": filename,
                "deps": [
                    {
                        "depName": name,
                        "currentValue": "1.0.0",
                        "skipReason": "no-token" if skipped else None,
                        "updates": [{"newValue": "1.0.1"}],
                    }
                ],
            }
        ]
        for manager, filename, name in (
            ("mise", "mise.toml", "node"),
            ("pep621", "pyproject.toml", "graphifyy"),
            ("github-actions", ".github/workflows/ci.yml", "actions/checkout"),
        )
    }
    if remove_manager:
        del package_files[remove_manager]
    return json.dumps({"repositories": {"local": {"packageFiles": package_files}}}).encode()


def test_report_counts_all_configured_managers_and_updates() -> None:
    summary = summarize_report(_report())
    assert summary["missing_managers"] == []
    assert summary["managers"] == {"mise": 1, "pep621": 1, "github-actions": 1}
    assert len(summary["updates"]) == 2
    assert [row["dependency"] for row in summary["manual_updates"]] == ["graphifyy"]
    assert summary["skipped_dependencies"] == []


def test_missing_manager_cannot_look_current() -> None:
    assert summarize_report(_report(remove_manager="pep621"))["missing_managers"] == ["pep621"]


def test_skipped_lookup_is_not_current() -> None:
    assert len(summarize_report(_report(skipped=True))["skipped_dependencies"]) == 3


def test_only_exact_reviewed_nonversion_skips_are_allowed() -> None:
    summary = summarize_report(_report())
    summary["skipped_dependencies"] = [
        {"file": "pyproject.toml", "dependency": "skillopt", "reason": "invalid-value"}
    ]
    assert lookup_complete(summary, token_present=True)
    summary["skipped_dependencies"][0]["reason"] = "no-token"
    assert not lookup_complete(summary, token_present=True)
    assert not lookup_complete(summary, token_present=False)


@pytest.mark.parametrize("raw", [b"{}", b'{"repositories":{"local":{}}}'])
def test_absent_report_data_is_refused(raw: bytes) -> None:
    with pytest.raises(TypeError, match="Renovate did not report"):
        summarize_report(raw)


def test_local_mode_and_token_are_forced_without_printing_secret(tmp_path: Path) -> None:
    sample = "fixture"
    child = renovate_environment(
        tmp_path / "report.json",
        {
            "GITHUB_COM_TOKEN": sample,
            "GITHUB_TOKEN": "secondary-fixture",
            "RENOVATE_GITHUB_COM_TOKEN": "third-fixture",
        },
    )
    assert child["GITHUB_COM_TOKEN"] == sample
    assert "RENOVATE_GITHUB_COM_TOKEN" not in child
    assert "GITHUB_TOKEN" not in child
    assert json.loads(child["RENOVATE_FORCE"]) == {"cloneSubmodules": False}
    assert child["RENOVATE_REPORT_TYPE"] == "file"


def test_lookup_diagnostics_are_retained_with_credential_redacted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample = "fixture-token"
    secondary = "secondary-fixture-token"
    emit_diagnostics(
        f"lookup ok {secondary}\n",
        f"warning for {sample}\n",
        tokens=[sample, secondary],
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "lookup ok [REDACTED_GITHUB_TOKEN]" in captured.err
    assert "warning for [REDACTED_GITHUB_TOKEN]" in captured.err
    assert sample not in captured.err
    assert secondary not in captured.err
