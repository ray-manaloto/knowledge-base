# Copyright (c) 2026 Raymond Manaloto
"""`mise run kb-plugin-validate` — Claude Code plugin marketplace schema check.

`mise run kb-plugin-validate -- <marketplace root>` — schema + `claude plugin
validate --strict` over a Claude Code plugin marketplace checkout.

Checks, in order, each naming the file it failed on: every `.claude-plugin/
marketplace.json` and `.claude-plugin/plugin.json` has a `$schema` and validates
against the schema it names (schemastore 301s `.json` URLs to
`www.schemastore.org` — `urllib` follows that by default); a plugin dir's
`.lsp.json`, if present, validates against the plugin schema's inline
`properties.lspServers.anyOf[1]` subschema — nothing else opens that file
(spec M-5); then `claude plugin validate` (no `--strict`) over the
marketplace root and over each local-source plugin dir. `--strict` turns
Ray's own ruling (no `version` field — commit-SHA versioning,
plugins-reference.md:1318) into a failure, since `claude plugin validate
--strict` exits 1 on both the root and every plugin dir with exactly one
warning, "No version specified. Consider adding a version following semver"
(measured 2026-08-28). Non-strict output has a fixed shape (measured, both
targets, rc 0): a "Validating ..." header line, a blank, a summary line
("Found N warning(s):", prefixed with a warning glyph), one indented FINDING
line per warning prefixed with an angle-arrow glyph, and a final "Validation
passed with warnings" line prefixed with a checkmark glyph.

So a FINDING line — the one whose first non-space character is the
angle-arrow glyph (`_FINDING_PREFIX` below) — fails unless it matches
`_ALLOWED_WARNINGS`; a line starting with the fail glyph (`_FAIL_PREFIX`)
always fails; the summary/header/blank lines carry no finding and are
ignored; and a nonzero exit code with no other finding still fails (belt
and suspenders against an output shape this hasn't seen).

`fetch_schema` and `runner` are injected so tests own their environment
(`probes-need-a-control-arm.md`) — no test here touches the network or spawns
`claude`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kb_setup.result import Err, Ok, Rc, Result, exit_code

MARKETPLACE_REL = Path(".claude-plugin/marketplace.json")
PLUGIN_MANIFEST_REL = Path(".claude-plugin/plugin.json")
LSP_REL = Path(".lsp.json")

SchemaFetcher = Callable[[str], dict[str, Any]]
Runner = Callable[[tuple[str, ...]], tuple[int, str]]

_FINDING_PREFIX = unicodedata.lookup("HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT")
_FAIL_PREFIX = unicodedata.lookup("HEAVY BALLOT X")  # `claude plugin validate`'s failure marker
# Looked up BY NAME rather than a literal glyph or a `chr(0x...)` magic number:
# ruff's RUF001 (ambiguous unicode) has no string literal to flag, and a wrong
# hex digit in a `chr()` call can't hide the way it could with a bare number.

_ALLOWED_WARNINGS = ("No version specified",)
"""Warning substrings `claude plugin validate` may emit without failing here.

Omitting `version` is Ray's ruling (commit-SHA versioning, per
plugins-reference.md:1318), and it is the ONLY warning the tool emits for
that — measured 2026-08-28 on both the marketplace root and a plugin dir.
"""


def _default_fetch_schema(url: str) -> dict[str, Any]:
    """The real network boundary — GET `url`, follow redirects, parse JSON.

    A `file:` URL is refused BEFORE any open, by an explicit scheme check —
    not by omitting `urllib.request.FileHandler` from the opener, which
    `build_opener` still adds by default (it appends any handler class not
    already present, regardless of which ones you pass). The opener here is
    built with ONLY the handlers this call needs — HTTP(S), the redirect
    handler schemastore's 301-to-`www.schemastore.org` needs (measured this
    session), and the two error handlers `urlopen`'s default opener carries —
    so nothing beyond that set is reachable even if the scheme check above
    were ever bypassed.
    """
    import urllib.request

    if not url.startswith(("http:", "https:")):
        msg = f"{url}: refused (http/https only)"
        raise ValueError(msg)
    opener = urllib.request.OpenerDirector()
    for handler_cls in (
        urllib.request.HTTPHandler,
        urllib.request.HTTPSHandler,
        urllib.request.HTTPRedirectHandler,
        urllib.request.HTTPDefaultErrorHandler,
        urllib.request.HTTPErrorProcessor,
    ):
        opener.add_handler(handler_cls())
    opener.addheaders = [("User-Agent", "kb-setup-plugin-validate")]
    with opener.open(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


_RUNNER_TIMEOUT_SECONDS = 120
"""Bound BELOW the `kb-plugin-validate` mise task's 5m, so a hung `claude`
process is killed here with a clear timeout rc rather than by the task's
own outer timeout with no diagnosis."""


def _default_runner(argv: tuple[str, ...]) -> tuple[int, str]:
    """`claude plugin validate`, stdout CAPTURED so the caller can scan it.

    Not inherited: the caller decides pass/fail from the text (a warning
    other than the allowlisted version one still fails), not solely from the
    exit code, which `--strict` would otherwise turn into a false positive.
    The rc is still returned and used as a belt-and-suspenders check.

    `encoding="utf-8", errors="replace"` rather than bare `text=True`: the
    latter decodes with the LOCALE encoding, which can raise on a stripped
    CI/container locale — a crash in the validator itself, not a validation
    finding. A timeout is a failure (nonzero rc), not an uncaught exception.
    """
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=_RUNNER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out_output = exc.stdout if isinstance(exc.stdout, str) else ""
        return 124, timed_out_output
    return completed.returncode, completed.stdout


def _validate_output_failure(output: str) -> str | None:
    """The first FINDING line in `output` that should fail the run, or `None`.

    A finding is a line whose first non-space character is `_FINDING_PREFIX`
    (indented under the "Found N warning(s):" summary header, which itself
    carries no finding and is ignored) or `_FAIL_PREFIX`. A `_FINDING_PREFIX`
    line fails unless it matches `_ALLOWED_WARNINGS` — today, only the
    missing-`version` warning; a `_FAIL_PREFIX` line always fails. Everything
    else ("Validating ...", the summary/pass lines, blanks) is not a finding
    and is ignored — deliberately NOT a case-insensitive "error" substring
    test, which would fail on a plugin legitimately named e.g. `error-handler`.
    """
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line[0] == _FAIL_PREFIX:
            return raw_line
        if line[0] == _FINDING_PREFIX and not any(allowed in line for allowed in _ALLOWED_WARNINGS):
            return raw_line
    return None


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError:
        return None


def _schema_errors(
    instance: dict[str, Any],
    schema: dict[str, Any],
    *,
    resolver_root: dict[str, Any] | None = None,
) -> list[str]:
    """Validation errors for `instance` against `schema`, as short messages.

    `resolver_root` lets a SUBSCHEMA (the `.lsp.json` case) resolve `$ref`s
    relative to the schema it was cut from, rather than to itself: the
    validator is built against `resolver_root` (its `$ref`-resolution base),
    then `.evolve(schema=...)` swaps in the subschema to validate against
    without swapping the base — no `RefResolver` needed, which is deprecated
    on the installed jsonschema 4.26.0.
    """
    import jsonschema

    root = resolver_root or schema
    validator_cls = jsonschema.validators.validator_for(root)
    validator_cls.check_schema(root)
    root_validator = validator_cls(root)
    validator = root_validator if resolver_root is None else root_validator.evolve(schema=schema)
    return [f"{err.json_path}: {err.message}" for err in validator.iter_errors(instance)]


def _validate_manifest(
    path: Path, data: dict[str, Any], fetch_schema: SchemaFetcher
) -> tuple[str | None, dict[str, Any] | None]:
    """Validate one manifest that must declare `$schema`. Returns (error, schema)."""
    schema_url = data.get("$schema")
    if not schema_url:
        return f'{path}: missing "$schema"', None
    schema = fetch_schema(schema_url)
    errors = _schema_errors(data, schema)
    if errors:
        return f"{path}: {errors[0]}", schema
    return None, schema


def _validate_lsp(path: Path, data: dict[str, Any], plugin_schema: dict[str, Any]) -> str | None:
    """Validate `.lsp.json` against the plugin schema's `lspServers` object form."""
    try:
        subschema = plugin_schema["properties"]["lspServers"]["anyOf"][1]
    except KeyError:
        return f"{path}: plugin schema has no properties.lspServers.anyOf[1] to validate against"
    except IndexError:
        return f"{path}: plugin schema has no properties.lspServers.anyOf[1] to validate against"
    errors = _schema_errors(data, subschema, resolver_root=plugin_schema)
    if errors:
        return f"{path}: {errors[0]}"
    return None


def _local_plugin_dirs(root: Path, marketplace: dict[str, Any]) -> list[Path]:
    """`root / source` for every plugin entry whose `source` is a local path."""
    dirs = []
    for plugin in marketplace.get("plugins", []):
        source = plugin.get("source")
        if isinstance(source, str) and source.startswith("./"):
            dirs.append(root / source)
    return dirs


def _validate_plugin_dir(
    plugin_dir: Path, fetch_schema: SchemaFetcher
) -> tuple[str | None, list[str]]:
    """Validate one local plugin dir's `plugin.json` and, if present, `.lsp.json`.

    Returns `(error, checked)`: `checked` names whatever passed before an error,
    if any — so a caller can still report partial progress.
    """
    checked: list[str] = []
    manifest_path = plugin_dir / PLUGIN_MANIFEST_REL
    plugin_data = _load_json(manifest_path)
    if plugin_data is None:
        return f"{manifest_path}: could not parse JSON", checked
    error, plugin_schema = _validate_manifest(manifest_path, plugin_data, fetch_schema)
    if error:
        return error, checked
    checked.append(str(manifest_path))

    lsp_path = plugin_dir / LSP_REL
    if lsp_path.is_file() and plugin_schema is not None:
        lsp_data = _load_json(lsp_path)
        if lsp_data is None:
            return f"{lsp_path}: could not parse JSON", checked
        error = _validate_lsp(lsp_path, lsp_data, plugin_schema)
        if error:
            return error, checked
        checked.append(str(lsp_path))
    return None, checked


def _run_claude_validate(
    targets: tuple[Path, ...], runner: Runner, checked: list[str]
) -> str | None:
    """`claude plugin validate` (no `--strict`) over each target; see module docstring."""
    for target in targets:
        argv = ("claude", "plugin", "validate", str(target))
        rc, output = runner(argv)
        failure = _validate_output_failure(output)
        if failure is None and rc != 0:
            failure = f"exited {rc}"
        if failure is not None:
            return f"claude plugin validate {target}: {failure.strip()}"
        checked.append(f"claude plugin validate {target}")
    return None


def validate(
    root: Path,
    *,
    fetch_schema: SchemaFetcher = _default_fetch_schema,
    runner: Runner = _default_runner,
) -> Result[list[str]]:
    """Validate the marketplace checkout at `root`. `Ok` carries every check that passed."""
    marketplace_path = root / MARKETPLACE_REL
    marketplace = _load_json(marketplace_path)
    if marketplace is None:
        return Err(f"{marketplace_path}: could not parse JSON")
    error, _schema = _validate_manifest(marketplace_path, marketplace, fetch_schema)
    if error:
        return Err(error)
    checked = [str(marketplace_path)]

    plugin_dirs = _local_plugin_dirs(root, marketplace)
    for plugin_dir in plugin_dirs:
        error, more = _validate_plugin_dir(plugin_dir, fetch_schema)
        checked.extend(more)
        if error:
            return Err(error)

    error = _run_claude_validate((root, *plugin_dirs), runner, checked)
    if error:
        return Err(error)
    return Ok(checked)


def main(repo_root: Path, args: list[str]) -> int:
    """Thin conversion from `Result` to a process exit code, and the only print."""
    positional = [a for a in args if not a.startswith("-")]
    if not positional:
        print("kb-setup: plugin-validate <marketplace root>", file=sys.stderr)
        return int(Rc.BAD_REQUEST)
    target = Path(positional[0])
    if not target.is_absolute():
        target = repo_root / target
    # `_default_fetch_schema`/`_default_runner` looked up here (not as `validate`'s
    # own bound-at-definition defaults) so a test can monkeypatch the module
    # attribute and have `main` pick it up.
    result = validate(target, fetch_schema=_default_fetch_schema, runner=_default_runner)
    match result:
        case Ok(checked, _):
            for c in checked:
                print(f"  ok    {c}")
        case Err(message, _):
            print(f"  FAIL  {message}")
    return exit_code(result)
