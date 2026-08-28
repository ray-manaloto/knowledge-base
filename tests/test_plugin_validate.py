# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.plugin_validate` (`mise run kb-plugin-validate`).

Every test owns its environment (`probes-need-a-control-arm.md`): the network
fetch and the `claude` subprocess are both stubbed, so nothing here touches
schemastore or spawns `claude`. Each failure arm asserts the message NAMES the
file that failed, per the spec's own requirement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kb_setup import plugin_validate as pv
from kb_setup.result import Err, Ok

if TYPE_CHECKING:
    import pytest

MARKETPLACE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "owner", "plugins"],
    "properties": {
        "name": {"type": "string"},
        "owner": {"type": "object"},
        "plugins": {"type": "array"},
    },
}

PLUGIN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "lspServers": {
            "anyOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["command", "args", "extensionToLanguage"],
                    },
                },
            ]
        },
    },
}

_MARKETPLACE_SCHEMA_URL = "https://json.schemastore.org/claude-code-marketplace.json"
_PLUGIN_SCHEMA_URL = "https://json.schemastore.org/claude-code-plugin-manifest.json"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _good_marketplace_root(tmp_path: Path) -> Path:
    """A marketplace + one local plugin, all schema-valid, `.lsp.json` included."""
    root = tmp_path / "marketplace"
    _write(
        root / pv.MARKETPLACE_REL,
        {
            "$schema": _MARKETPLACE_SCHEMA_URL,
            "name": "claude-code-marketplace",
            "owner": {"name": "Raymond Manaloto"},
            "plugins": [{"name": "aggregated-research", "source": "./aggregated-research"}],
        },
    )
    _write(
        root / "aggregated-research" / pv.PLUGIN_MANIFEST_REL,
        {"$schema": _PLUGIN_SCHEMA_URL, "name": "aggregated-research"},
    )
    _write(
        root / "aggregated-research" / pv.LSP_REL,
        {"ty": {"command": "x", "args": ["server"], "extensionToLanguage": {".py": "python"}}},
    )
    return root


def _fake_fetch_schema(schemas: dict[str, dict[str, Any]]) -> pv.SchemaFetcher:
    def _fetch(url: str) -> dict[str, Any]:
        return schemas[url]

    return _fetch


_VERSION_WARNING = "⚠ version: No version specified. Consider adding a version following semver"


def _fake_runner(output: str = "") -> tuple[pv.Runner, list[tuple[str, ...]]]:
    calls: list[tuple[str, ...]] = []

    def _run(argv: tuple[str, ...]) -> str:
        calls.append(argv)
        return output

    return _run, calls


_SCHEMAS = {_MARKETPLACE_SCHEMA_URL: MARKETPLACE_SCHEMA, _PLUGIN_SCHEMA_URL: PLUGIN_SCHEMA}


def test_a_good_marketplace_passes(tmp_path: Path) -> None:
    root = _good_marketplace_root(tmp_path)
    runner, calls = _fake_runner()

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Ok)
    # marketplace.json, plugin.json, .lsp.json, then two `claude plugin validate` calls.
    assert len(result.value) == 5
    assert len(calls) == 2
    assert calls[0] == ("claude", "plugin", "validate", str(root))
    assert calls[1][-1] == str(root / "aggregated-research")


def test_the_no_version_warning_alone_passes(tmp_path: Path) -> None:
    """Ray's ruling (no `version`, commit-SHA versioning) must not fail the run."""
    root = _good_marketplace_root(tmp_path)
    runner, _calls = _fake_runner(output=_VERSION_WARNING)

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Ok)


def test_missing_name_in_plugin_json_fails_naming_the_file(tmp_path: Path) -> None:
    """CONTROL for the M-5 branch below: a plugin.json defect is caught FIRST."""
    root = _good_marketplace_root(tmp_path)
    manifest = root / "aggregated-research" / pv.PLUGIN_MANIFEST_REL
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["name"]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    runner, _calls = _fake_runner()

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(manifest) in result.message
    assert "name" in result.message


def test_manifest_with_no_schema_fails_naming_the_file(tmp_path: Path) -> None:
    root = _good_marketplace_root(tmp_path)
    marketplace_path = root / pv.MARKETPLACE_REL
    data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    del data["$schema"]
    marketplace_path.write_text(json.dumps(data), encoding="utf-8")
    runner, _calls = _fake_runner()

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(marketplace_path) in result.message
    assert "$schema" in result.message


def test_lsp_json_missing_extension_to_language_fails_naming_the_file(tmp_path: Path) -> None:
    """The M-5 branch: nothing else opens `.lsp.json`, so this exercises it directly."""
    root = _good_marketplace_root(tmp_path)
    lsp_path = root / "aggregated-research" / pv.LSP_REL
    _write(lsp_path, {"ty": {"command": "x", "args": ["server"]}})  # missing extensionToLanguage
    runner, _calls = _fake_runner()

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(lsp_path) in result.message


def test_claude_plugin_validate_failure_is_reported(tmp_path: Path) -> None:
    root = _good_marketplace_root(tmp_path)
    runner, _calls = _fake_runner(output="✘ plugin.json: something is wrong")

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(root) in result.message


def test_a_non_version_warning_fails_naming_the_file(tmp_path: Path) -> None:
    root = _good_marketplace_root(tmp_path)
    runner, _calls = _fake_runner(output="⚠ some other warning that is not about version")

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(root) in result.message


def test_main_returns_bad_request_with_no_args(tmp_path: Path) -> None:
    assert pv.main(tmp_path, []) == 2


def test_main_returns_ok_rc_for_a_good_marketplace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _good_marketplace_root(tmp_path)
    runner, _calls = _fake_runner()
    monkeypatch.setattr(pv, "_default_fetch_schema", _fake_fetch_schema(_SCHEMAS))
    monkeypatch.setattr(pv, "_default_runner", runner)

    assert pv.main(tmp_path, [str(root)]) == 0
