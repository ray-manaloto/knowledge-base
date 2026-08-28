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
(spec M-5); then `claude plugin validate --strict` over the marketplace root
and over each local-source plugin dir.

`fetch_schema` and `runner` are injected so tests own their environment
(`probes-need-a-control-arm.md`) — no test here touches the network or spawns
`claude`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kb_setup.result import Err, Ok, Rc, Result, exit_code

MARKETPLACE_REL = Path(".claude-plugin/marketplace.json")
PLUGIN_MANIFEST_REL = Path(".claude-plugin/plugin.json")
LSP_REL = Path(".lsp.json")

SchemaFetcher = Callable[[str], dict[str, Any]]
Runner = Callable[[tuple[str, ...]], int]


def _default_fetch_schema(url: str) -> dict[str, Any]:
    """The real network boundary — GET `url`, follow redirects, parse JSON.

    Same shape as `fetch.http_fetcher`: a scheme-restricted opener built from
    only the http/https handlers, so `file:` cannot be opened. Redirects are
    handled by urllib's default `HTTPRedirectHandler`, which `build_opener`
    always includes — load-bearing here because schemastore's own `.json` URLs
    301 to `www.schemastore.org` (measured this session).
    """
    import urllib.request

    if not url.startswith(("http:", "https:")):
        msg = f"{url}: refused (http/https only)"
        raise ValueError(msg)
    opener = urllib.request.build_opener(urllib.request.HTTPHandler, urllib.request.HTTPSHandler)
    opener.addheaders = [("User-Agent", "kb-setup-plugin-validate")]
    with opener.open(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _default_runner(argv: tuple[str, ...]) -> int:
    """`claude plugin validate`, stdio inherited so its own diagnostics show."""
    return subprocess.run(argv, check=False).returncode


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None


def _schema_errors(
    instance: dict[str, Any],
    schema: dict[str, Any],
    *,
    resolver_root: dict[str, Any] | None = None,
) -> list[str]:
    """Validation errors for `instance` against `schema`, as short messages.

    `resolver_root` lets a SUBSCHEMA (the `.lsp.json` case) resolve `$ref`s
    relative to the schema it was cut from, rather than to itself.
    """
    import jsonschema

    resolver = jsonschema.RefResolver.from_schema(resolver_root or schema)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, resolver=resolver)
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
    except KeyError, IndexError:
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
    """`claude plugin validate --strict` over each target, appending to `checked`."""
    for target in targets:
        argv = ("claude", "plugin", "validate", "--strict", str(target))
        rc = runner(argv)
        if rc != 0:
            return f"claude plugin validate --strict {target}: exited {rc}"
        checked.append(f"claude plugin validate --strict {target}")
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
