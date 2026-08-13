# Copyright (c) 2026 Raymond Manaloto
"""Contract tests for the public Graphify SDK boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from kb_setup import graphify_sdk


def test_graphify_0941_public_sdk_contract_is_current() -> None:
    assert graphify_sdk.contract_errors("0.9.41") == ()


def test_every_contract_symbol_is_public() -> None:
    assert all(
        all(not part.startswith("_") for part in symbol.dotted_name.split("."))
        for symbol in graphify_sdk._PUBLIC_SYMBOLS
    )


def test_signature_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    first = graphify_sdk._PUBLIC_SYMBOLS[0]
    mutant = replace(first, expected_signature="(silently_changed: 'bool') -> 'None'")
    monkeypatch.setattr(
        graphify_sdk,
        "_PUBLIC_SYMBOLS",
        (mutant, *graphify_sdk._PUBLIC_SYMBOLS[1:]),
    )

    with pytest.raises(RuntimeError, match="signature changed"):
        graphify_sdk.assert_public_sdk("0.9.41")


def test_sdk_version_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "0.9.42")

    with pytest.raises(RuntimeError, match=r"version 0\.9\.42"):
        graphify_sdk.assert_public_sdk("0.9.41")


def test_contract_main_checks_the_repository_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kb_setup import graphify_env

    calls: list[Path] = []
    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", calls.append)
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "0.9.41")

    assert graphify_sdk.contract_main(tmp_path) == 0
    assert calls == [tmp_path]
    assert "Graphify CLI/SDK contract PASS: 0.9.41" in capsys.readouterr().out
