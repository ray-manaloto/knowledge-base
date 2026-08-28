# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.plugin_validate` (`mise run kb-plugin-validate`).

Every test owns its environment (`probes-need-a-control-arm.md`): the network
fetch and the `claude` subprocess are both stubbed, so nothing here touches
schemastore or spawns `claude`. Each failure arm asserts the message NAMES the
file that failed, per the spec's own requirement.
"""

from __future__ import annotations

import json
import unicodedata
import warnings
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
            "name": "ray-manaloto",
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


_WARN_PREFIX = unicodedata.lookup("WARNING SIGN")  # the "Found N warning(s):" header
_PASS_PREFIX = unicodedata.lookup("HEAVY CHECK MARK")  # the final "Validation passed" line
_ARROW = unicodedata.lookup("RIGHTWARDS ARROW")  # inside a plugin.json field path
# Looked up BY NAME, not a literal glyph or a `chr(0x...)` magic number: ruff's
# RUF001 (ambiguous unicode) has nothing to flag, and a wrong hex digit can't
# hide the way it could with a bare number. These reproduce `claude plugin
# validate`'s EXACT non-ASCII output, verbatim, measured 2026-08-28 on both a
# marketplace root and a plugin dir (team-lead's respec), no `--strict`, rc 0.
_MARKETPLACE_OK_OUTPUT = "\n".join(
    [
        "Validating marketplace manifest: /path/.claude-plugin/marketplace.json",
        "",
        f"{_WARN_PREFIX} Found 1 warning:",
        "",
        (
            f"  {pv._FINDING_PREFIX} plugins[0] plugin.json {_ARROW} version: No version "
            'specified. Consider adding a version following semver (e.g., "1.0.0")'
        ),
        "",
        f"{_PASS_PREFIX} Validation passed with warnings",
        "",
    ]
)

_PLUGIN_DIR_OK_OUTPUT = "\n".join(
    [
        "Validating plugin manifest: /path/aggregated-research/.claude-plugin/plugin.json",
        "",
        f"{_WARN_PREFIX} Found 1 warning:",
        "",
        (
            f"  {pv._FINDING_PREFIX} version: No version specified. Consider adding a "
            'version following semver (e.g., "1.0.0")'
        ),
        "",
        f"{_PASS_PREFIX} Validation passed with warnings",
        "",
    ]
)


def _fake_runner(
    outputs: list[tuple[int, str]] | None = None,
) -> tuple[pv.Runner, list[tuple[str, ...]]]:
    """`outputs[i]` answers the i-th call; the last entry is reused past that.

    Default: a clean `(0, "")` for every call — `validate()` calls the runner
    once per target (root, then each local plugin dir), in that order.
    """
    calls: list[tuple[str, ...]] = []
    answers = outputs or [(0, "")]

    def _run(argv: tuple[str, ...]) -> tuple[int, str]:
        calls.append(argv)
        return answers[min(len(calls) - 1, len(answers) - 1)]

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


def test_the_measured_pass_output_passes(tmp_path: Path) -> None:
    """The verbatim measured output (version warning only) must not fail the run."""
    root = _good_marketplace_root(tmp_path)
    runner, _calls = _fake_runner([(0, _MARKETPLACE_OK_OUTPUT), (0, _PLUGIN_DIR_OK_OUTPUT)])

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


def test_claude_plugin_validate_x_line_fails_naming_the_file(tmp_path: Path) -> None:
    root = _good_marketplace_root(tmp_path)
    fail_line = f"{pv._FAIL_PREFIX} Validation failed"
    runner, _calls = _fake_runner([(1, fail_line)])

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(root) in result.message


def test_a_non_version_finding_fails_naming_the_file(tmp_path: Path) -> None:
    """The measured pass output, but with the finding changed to a real defect."""
    root = _good_marketplace_root(tmp_path)
    original_finding = (
        f"  {pv._FINDING_PREFIX} plugins[0] plugin.json {_ARROW} version: No version "
        'specified. Consider adding a version following semver (e.g., "1.0.0")'
    )
    changed = _MARKETPLACE_OK_OUTPUT.replace(
        original_finding, f"  {pv._FINDING_PREFIX} name: Missing required field"
    )
    runner, _calls = _fake_runner([(0, changed)])

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(root) in result.message
    assert "Missing required field" in result.message


def test_nonzero_rc_with_clean_text_still_fails(tmp_path: Path) -> None:
    """No finding line in the text, but a nonzero rc must still fail."""
    root = _good_marketplace_root(tmp_path)
    runner, _calls = _fake_runner([(1, f"{_PASS_PREFIX} Validation passed with warnings\n")])

    result = pv.validate(root, fetch_schema=_fake_fetch_schema(_SCHEMAS), runner=runner)

    assert isinstance(result, Err)
    assert str(root) in result.message
    assert "exited 1" in result.message


def test_schema_validation_raises_no_deprecation_warning() -> None:
    """Proof for the `RefResolver` removal: a DeprecationWarning cannot return silently."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert pv._schema_errors({"name": "x"}, PLUGIN_SCHEMA) == []

        lsp_schema = PLUGIN_SCHEMA["properties"]["lspServers"]["anyOf"][1]
        lsp_instance = {"ty": {"command": "x", "args": ["y"], "extensionToLanguage": {}}}
        assert pv._schema_errors(lsp_instance, lsp_schema, resolver_root=PLUGIN_SCHEMA) == []


def test_fetch_schema_refuses_file_url_before_opening() -> None:
    raised = None
    try:
        pv._default_fetch_schema("file:///etc/passwd")
    except ValueError as exc:
        raised = exc
    assert raised is not None
    assert "http/https only" in str(raised)


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
