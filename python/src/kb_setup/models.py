# Copyright (c) 2026 Raymond Manaloto
"""Shared registry, bounded catalog reads and launch-scoped model verdicts.

Feed acquisition is the only live boundary. ``evaluate`` is pure; unreadable
feeds never become a pass or a denial. Repository rendering is offline.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

import httpx2
import msgspec

from kb_setup import atomic
from kb_setup.generated.models_registry import Registry, Status
from kb_setup.generated.models_report import (
    FeedStatus,
    LaunchDecision,
    OverlayStatus,
    RegistryReport,
    TrustResult,
    TrustStatus,
    Vendor,
    VendorReport,
    Verdict,
)
from kb_setup.generated.vendor_feeds import CodexCatalog, Feeds, VendorFeed
from kb_setup.generated.vendor_feeds import FeedStatus as NativeFeedStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

OVERLAY_URL = (
    "https://raw.githubusercontent.com/ray-manaloto/knowledge-base/main/"
    "python/src/kb_setup/models.toml"
)
_CODEX_USER_CONFIG = Path.home() / ".codex/config.toml"
_CACHE = Path(".agent/state/models-verdict.json")
_RETIRE_WINDOW = timedelta(hours=72)
_AGY_COLUMNS = 2
_MIN_TIMEOUT_PREFIX = 2
_CD_TOKENS = 2
_PLUGIN_ID = "antigravity@antigravity-for-claude-code"
_PLUGIN_DEFAULTS = {
    "tier_flash": "Gemini 3.8 Flash (High)",
    "tier_flash_lo": "Gemini 3.8 Flash (Low)",
    "tier_pro": "Gemini 3.1 Pro (High)",
    "default_model": "Gemini 3.8 Flash (High)",
}
_PLUGIN_ROLES = {
    "tier_flash": "flash",
    "tier_flash_lo": "flash-lo",
    "tier_pro": "pro",
    "default_model": "flash",
}

type KnownSets = dict[str, set[str]]


def _resolved_data(data: dict) -> dict:
    """Derive dispatch slugs before decoding the generated resolved contract."""
    for vendor in ("codex", "agy"):
        block = data[vendor]
        roles = list(block["dispatch"].values())
        if vendor == "codex":
            roles.append(block["config_fallback"])
            for agent in block["agents"].values():
                agent.setdefault("authored", False)
                if agent["role"] not in block["pins"]:
                    raise ValueError(f"unknown codex agent role: {agent['role']}")
        for role in roles:
            role["slug"] = block["pins"][role["role"]]["slug"]
    return data


def load_registry(path: Path | None = None) -> Registry:
    """Decode package data or an explicit file, rejecting offline load errors."""
    resource = files("kb_setup").joinpath("models.toml") if path is None else path
    raw = resource.read_bytes()
    data = tomllib.loads(raw.decode())
    data["registry_source"] = (
        "package:kb_setup/models.toml" if path is None else str(path.resolve())
    )
    data["registry_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        registry = msgspec.convert(_resolved_data(data), type=Registry)
    except (KeyError, TypeError, msgspec.ValidationError) as exc:
        raise ValueError(f"model registry load failure: {exc}") from exc
    _check_adoption(registry)
    return registry


def _check_adoption(registry: Registry) -> None:
    if any(role not in registry.codex.pins for role in registry.codex.launch_agents.values()):
        raise ValueError("unknown codex launch agent role")
    for name, block in [("codex", registry.codex), ("agy", registry.agy)]:
        for pin in block.pins.values():
            known = block.known.get(pin.slug)
            if known is None or known.status != Status.ADOPTED:
                raise ValueError(f"{name} pin is not adopted: {pin.slug}")
    for value in registry.claude.api.values():
        for slug in [value] if isinstance(value, str) else value:
            known = registry.claude.known.get(slug)
            if known is None or known.status != Status.ADOPTED:
                raise ValueError(f"claude.api id is not adopted: {slug}")


@overload
def claude_api(key: Literal["graphify_native_extract"]) -> str: ...


@overload
def claude_api(key: Literal["model_limits"]) -> tuple[str, ...]: ...


@overload
def claude_api(key: str) -> str | tuple[str, ...]: ...


def claude_api(key: str) -> str | tuple[str, ...]:
    """Read a full SDK ID at runtime; Claude Code aliases are a separate role."""
    value = load_registry().claude.api[key]
    return value if isinstance(value, str) else tuple(value)


def agent_pair(file_stem: str, registry: Registry) -> tuple[str, str | None]:
    """Resolve exactly one stem rule, retaining Option C's model-only sentinel."""
    matches = [v for k, v in registry.codex.agents.items() if fnmatch.fnmatchcase(file_stem, k)]
    if len(matches) != 1:
        raise ValueError(f"agent stem {file_stem!r} matches {len(matches)} registry rules")
    entry = matches[0]
    return registry.codex.pins[entry.role].slug, None if entry.effort == "spawn" else entry.effort


def tracked_files(root: Path) -> list[str]:
    """Use Git's tracked inventory; ignored agent exports are not registry sites."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    return [name for name in result.stdout.decode().split("\0") if name]


def codex_trust(repo_root: Path, user_config: Path = _CODEX_USER_CONFIG) -> TrustResult:
    """Read only project trust, never print or write other user configuration."""
    repo = repo_root.resolve()
    fix = f'[projects.{msgspec.json.encode(str(repo)).decode()}]\ntrust_level = "trusted"'
    try:
        data = tomllib.loads(user_config.read_text(encoding="utf-8"))
        projects = data.get("projects", {})
        trusted = _trusted_project(repo, {"projects": projects})
    except OSError, ValueError, AttributeError, TypeError:
        return TrustResult(
            TrustStatus.UNREADABLE, str(user_config), "codex trust NOT CHECKED: unreadable config"
        )
    finding = (
        ""
        if trusted
        else (
            f"{user_config}: project .codex/ layers are ignored while untrusted; "
            "Trusted-parent/worktree semantics await V-TRUST-PARENT.\n"
            f"user-config fix:\n{fix}\n"
        )
    )
    return TrustResult(
        TrustStatus.TRUSTED if trusted else TrustStatus.UNTRUSTED, str(user_config), finding
    )


def _fetch(url: str, timeout_s: float) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("feed URLs must use https")
    with httpx2.Client(
        timeout=timeout_s, headers={"User-Agent": "kb-setup/models"}, follow_redirects=True
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def read_overlay(source: str, timeout_s: float = 5.0) -> KnownSets | None:
    """Overlay only known sets; upstream pins can never change package pins."""
    try:
        raw = Path(source).read_bytes() if Path(source).is_absolute() else _fetch(source, timeout_s)
        data = tomllib.loads(raw.decode())
        if data.get("schema_version") != 1:
            return None
        result = {}
        for vendor in ("codex", "agy", "claude"):
            entries = data[vendor]["known"]
            if not isinstance(entries, dict) or not all(isinstance(k, str) for k in entries):
                return None
            result[vendor] = set(entries)
    except OSError, ValueError, KeyError, TypeError, httpx2.HTTPError:
        return None
    return result


def _feed(status: NativeFeedStatus, finding: str = "") -> VendorFeed:
    return VendorFeed(
        status, [], [finding] if finding else [], {}, {}, {}, {}, 0.0, hidden_slugs=[]
    )


def _retirement_time(value: str) -> datetime:
    retirement = datetime.fromisoformat(value)
    if retirement.utcoffset() is None:
        raise ValueError("retirement_at requires a timezone")
    return retirement


def _retirement_shape_findings(feed: VendorFeed) -> list[str]:
    try:
        for retirement in feed.retirements.values():
            _retirement_time(retirement)
    except ValueError:
        return ["KEY-SHAPE FAIL: retirement_at"]
    return []


def parse_codex(payload: bytes, status: NativeFeedStatus = NativeFeedStatus.LIVE) -> VendorFeed:
    """Require every key we read, including nullable upgrade and effort objects."""
    try:
        catalog = msgspec.json.decode(payload, type=CodexCatalog)
    except msgspec.DecodeError as exc:
        return _feed(NativeFeedStatus.SHAPE_BROKEN, f"KEY-SHAPE FAIL: {exc}")
    result = _feed(status)
    for model in catalog.models:
        result.slugs.append(model.slug)
        if model.visibility == "hide":
            result.hidden_slugs.append(model.slug)
        result.efforts[model.slug] = [entry.effort for entry in model.supported_reasoning_levels]
        if model.upgrade is not None:
            try:
                _retirement_time(model.upgrade.retirement_at)
            except ValueError:
                return _feed(NativeFeedStatus.SHAPE_BROKEN, "KEY-SHAPE FAIL: retirement_at")
            result.upgrades[model.slug] = model.upgrade.model
            result.retirements[model.slug] = model.upgrade.retirement_at
    return result


def _native(argv: list[str], timeout_s: float) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, capture_output=True, timeout=timeout_s, check=False)


def _codex_feed() -> VendorFeed:
    deadline = time.monotonic() + 30.0
    errors = []
    for suffix in ([], ["--bundled"]):
        try:
            proc = _native(
                ["mise", "exec", "--", "codex", "debug", "models", *suffix],
                max(0.1, deadline - time.monotonic()),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"codex feed unreadable: {type(exc).__name__}")
            continue
        if proc.returncode:
            errors.append(
                f"codex feed rc={proc.returncode}: {proc.stderr.decode(errors='replace')}"
            )
            continue
        # N3: raw_model_catalog(OnlineIfUncached) returns its seed on refresh
        # failure, with rc 0 and no machine-readable freshness provenance.
        # Even a catalog differing from --bundled can be a stale cache. Until
        # the CLI attests freshness, use bundled-only availability semantics.
        result = parse_codex(proc.stdout, NativeFeedStatus.BUNDLED)
        if not suffix:
            result.findings.append(
                "unverified-live: codex debug models does not attest a fresh refresh; "
                "availability treated as bundled-only"
            )
        result.findings.extend(errors)
        if proc.stderr:
            result.findings.append(proc.stderr.decode(errors="replace"))
        return result
    return _feed(NativeFeedStatus.UNREADABLE, "\n".join(errors))


def parse_agy(payload: bytes) -> VendorFeed:
    """Parse the native two-column TSV, preserving IDs and display names."""
    result = _feed(NativeFeedStatus.LIVE)
    for line in payload.decode(errors="replace").splitlines():
        fields = line.split("\t")
        if len(fields) != _AGY_COLUMNS or not all(fields):
            return _feed(NativeFeedStatus.SHAPE_BROKEN, "KEY-SHAPE FAIL: agy TSV row (2 fields)")
        result.slugs.append(fields[0])
        result.display_names[fields[0]] = fields[1]
    return (
        result if result.slugs else _feed(NativeFeedStatus.SHAPE_BROKEN, "KEY-SHAPE FAIL: agy rows")
    )


def _agy_feed() -> VendorFeed:
    try:
        proc = _native([str(Path.home() / ".local/bin/agy"), "models"], 30.0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _feed(NativeFeedStatus.UNREADABLE, f"agy feed unreadable: {type(exc).__name__}")
    result = (
        parse_agy(proc.stdout)
        if proc.returncode == 0
        else _feed(NativeFeedStatus.UNREADABLE, f"agy feed rc={proc.returncode}")
    )
    if proc.stderr:
        result.findings.append(proc.stderr.decode(errors="replace"))
    return result


def parse_claude(payload: bytes) -> VendorFeed:
    """Scope models.dev to anthropic, failing loudly when its shape changes."""
    try:
        models = msgspec.json.decode(payload)["anthropic"]["models"]
    except (msgspec.DecodeError, KeyError, TypeError, ValueError) as exc:
        return _feed(NativeFeedStatus.SHAPE_BROKEN, f"KEY-SHAPE FAIL: {exc}")
    if not isinstance(models, dict) or not models:
        return _feed(NativeFeedStatus.SHAPE_BROKEN, "KEY-SHAPE FAIL: anthropic.models")
    if not all(
        isinstance(value, dict) and isinstance(value.get("id"), str) for value in models.values()
    ):
        return _feed(NativeFeedStatus.SHAPE_BROKEN, "KEY-SHAPE FAIL: anthropic.models[].id")
    result = _feed(NativeFeedStatus.LIVE)
    result.slugs = list(models)
    return result


def _claude_feed() -> VendorFeed:
    try:
        return parse_claude(_fetch("https://models.dev/api.json", 10.0))
    except (ValueError, httpx2.HTTPError) as exc:
        return _feed(NativeFeedStatus.UNREADABLE, f"models.dev unreadable: {type(exc).__name__}")


def _plugin_options() -> dict[str, str]:
    try:
        settings = msgspec.json.decode((Path.home() / ".claude/settings.json").read_bytes())
        options = settings.get("pluginConfigs", {}).get(_PLUGIN_ID, {}).get("options", {})
        return {key: str(options[key]) for key in _PLUGIN_ROLES if key in options}
    except OSError, msgspec.DecodeError, AttributeError, TypeError:
        return {}


def read_feeds(*, resolved_model: str | None, budget_s: float = 35.0) -> Feeds:
    """Collect concurrently; daemon workers cannot extend the caller's deadline."""
    completed: queue.Queue[tuple[str, VendorFeed]] = queue.Queue()
    deadline = time.monotonic() + budget_s

    def collect(name: str, reader: Callable[[], VendorFeed]) -> None:
        started = time.monotonic()
        feed = reader()
        feed.duration_s = time.monotonic() - started
        completed.put((name, feed))

    readers = {"codex": _codex_feed, "agy": _agy_feed, "claude": _claude_feed}
    for name, reader in readers.items():
        threading.Thread(target=collect, args=(name, reader), daemon=True).start()
    vendors = {}
    while len(vendors) < len(readers):
        try:
            name, feed = completed.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty:
            break
        vendors[name] = feed
    for name in readers.keys() - vendors.keys():
        vendors[name] = _feed(
            NativeFeedStatus.UNREADABLE, "NOT CHECKED (budget; this is not a pass)"
        )
    return Feeds(
        vendors, resolved_model, _plugin_options(), disabled_by_baseline=False, overrides=[]
    )


def _known(registry: Registry) -> KnownSets:
    return {
        "codex": set(registry.codex.known),
        "agy": set(registry.agy.known),
        "claude": set(registry.claude.known),
    }


def _pins(registry: Registry, vendor: Vendor) -> dict[str, str]:
    if vendor == Vendor.CODEX:
        return {key: value.slug for key, value in registry.codex.pins.items()}
    if vendor == Vendor.AGY:
        return {key: value.slug for key, value in registry.agy.pins.items()}
    return {}


def _retirements(report: VendorReport, feed: VendorFeed, now: datetime) -> None:
    for role, slug in report.current_pins.items():
        if feed.status == NativeFeedStatus.LIVE and slug not in feed.slugs:
            report.invalid_pins[role] = slug
            report.findings.append(f"MISSING pin {role}: {slug}")
        if slug in feed.retirements:
            retirement = _retirement_time(feed.retirements[slug])
            line = (
                f"{slug} upgrade to {feed.upgrades[slug]}; retirement_at={retirement.isoformat()}"
            )
            if now >= retirement - _RETIRE_WINDOW:
                report.invalid_pins[role] = slug
                report.findings.append(line)
            else:
                report.retiring.append(line)


def _claude_findings(registry: Registry, feeds: Feeds, known: set[str]) -> list[str]:
    findings = []
    if feeds.resolved_model is None:
        findings.append("resolved model NOT CHECKED (this is not a pass): absent")
    elif re.sub(r"\[[^\]]*\]$", "", feeds.resolved_model) not in known:
        findings.append(f"unknown resolved model: {feeds.resolved_model}")
    live = set(feeds.vendors["claude"].slugs)
    for value in registry.claude.api.values():
        findings.extend(
            f"claude.api missing from anthropic: {slug}"
            for slug in ([value] if isinstance(value, str) else value)
            if slug not in live
        )
    return findings


def _plugin_findings(registry: Registry, feeds: Feeds) -> list[str]:
    feed = feeds.vendors["agy"]
    reverse = {name: slug for slug, name in feed.display_names.items()}
    findings = []
    for key, role in _PLUGIN_ROLES.items():
        configured = feeds.plugin_options.get(key) or _PLUGIN_DEFAULTS[key]
        slug = reverse.get(configured, configured)
        if slug != registry.agy.pins[role].slug:
            findings.append(f"pluginConfigs[{_PLUGIN_ID}].options.{key} disagrees with pin {role}")
    return findings


def _effort_findings(registry: Registry, feed: VendorFeed) -> list[str]:
    pairs: list[tuple[str, str]] = [(p.slug, str(p.effort)) for p in registry.codex.pins.values()]
    pairs += [
        (registry.codex.pins[a.role].slug, str(a.effort))
        for a in registry.codex.agents.values()
        if a.effort != "spawn"
    ]
    pairs += [(r.slug, r.effort) for r in registry.codex.dispatch.values()]
    pairs.append((registry.codex.config_fallback.slug, registry.codex.config_fallback.effort))
    return [
        f"unsupported effort {effort} for {slug}"
        for slug, effort in sorted(set(pairs))
        if slug in feed.slugs and effort not in feed.efforts.get(slug, [])
    ]


def _vendor_report(
    registry: Registry, feeds: Feeds, overlay: KnownSets | None, vendor: Vendor, now: datetime
) -> VendorReport:
    feed = feeds.vendors[vendor.value]
    known = _known(registry)[vendor.value]
    visible = set(feed.slugs) - set(feed.hidden_slugs)
    unknown = visible - known
    status = OverlayStatus.NOT_NEEDED
    if unknown:
        status = OverlayStatus.UNREADABLE if overlay is None else OverlayStatus.READ
        known |= (overlay or {}).get(vendor.value, set())
    report = VendorReport(
        vendor,
        Verdict.OK,
        FeedStatus(feed.status.value),
        status,
        {},
        sorted(visible - known),
        [],
        list(feed.findings),
        _pins(registry, vendor),
        feed.display_names,
        {},
    )
    if vendor == Vendor.CODEX:
        report.agent_roles = dict(registry.codex.launch_agents)
    if feeds.disabled_by_baseline:
        report.verdict = Verdict.NOT_CHECKED
        report.findings.append("disabled_by_baseline")
        return report
    shape_findings = _retirement_shape_findings(feed)
    report.findings.extend(shape_findings)
    if shape_findings:
        report.feed = FeedStatus.SHAPE_BROKEN
    if report.feed in (FeedStatus.UNREADABLE, FeedStatus.SHAPE_BROKEN):
        report.verdict = Verdict.NOT_CHECKED
        report.findings.append("NOT CHECKED (this is not a pass)")
        return report
    if vendor != Vendor.CLAUDE:
        _retirements(report, feed, now)
    return _catalog_verdict(report, unknown, overlay)


def _catalog_verdict(
    report: VendorReport, unknown: set[str], overlay: KnownSets | None
) -> VendorReport:
    """Bundled reads cannot certify availability; positive markers can invalidate."""
    if report.invalid_pins:
        report.verdict = Verdict.INVALID
    elif report.feed == FeedStatus.BUNDLED:
        report.verdict = Verdict.NOT_CHECKED
        report.findings.append(
            "bundled-only catalog: availability NOT CHECKED (this is not a pass); "
            "bundled absence cannot retire a pin (openai/codex#47152)"
        )
    elif unknown and overlay is None:
        report.verdict = Verdict.NOT_CHECKED
        report.findings.append("overlay unreadable; NOT CHECKED (this is not a pass)")
    elif report.unknown_slugs:
        report.verdict = Verdict.DRIFT
    return report


def _add_drift(report: VendorReport, findings: list[str]) -> None:
    report.findings.extend(findings)
    if findings and report.verdict == Verdict.OK:
        report.verdict = Verdict.DRIFT


def _apply_overrides(vendors: list[VendorReport], overrides: list[str]) -> None:
    """Overrides remain visible even with enforcement disabled."""
    if not overrides:
        return
    for report in vendors:
        report.findings.append("OVERRIDE: " + ", ".join(overrides))
        if report.verdict == Verdict.OK:
            report.verdict = Verdict.DRIFT


def evaluate(
    registry: Registry,
    feeds: Feeds,
    overlay: KnownSets | None,
    trust: TrustResult,
    *,
    now: datetime,
) -> RegistryReport:
    """Pure verdicts; positive stale-pin evidence takes precedence over drift."""
    vendors = [_vendor_report(registry, feeds, overlay, vendor, now) for vendor in Vendor]
    codex, agy, claude = vendors
    if not feeds.disabled_by_baseline:
        if codex.verdict != Verdict.NOT_CHECKED:
            _add_drift(codex, _effort_findings(registry, feeds.vendors["codex"]))
            if trust.status == TrustStatus.UNREADABLE:
                codex.findings.append(trust.finding)
                if codex.verdict != Verdict.INVALID:
                    codex.verdict = Verdict.NOT_CHECKED
            elif trust.status == TrustStatus.UNTRUSTED:
                _add_drift(codex, [trust.finding])
        if agy.verdict != Verdict.NOT_CHECKED:
            _add_drift(agy, _plugin_findings(registry, feeds))
        if claude.verdict != Verdict.NOT_CHECKED:
            findings = _claude_findings(
                registry, feeds, _known(registry)["claude"] | (overlay or {}).get("claude", set())
            )
            _add_drift(claude, [f for f in findings if "NOT CHECKED" not in f])
            claude.findings.extend(f for f in findings if "NOT CHECKED" in f)
    _apply_overrides(vendors, feeds.overrides)
    return RegistryReport(
        vendors,
        registry.registry_source,
        registry.registry_sha256,
        feeds.resolved_model,
        feeds.disabled_by_baseline,
        now.isoformat(),
        feeds.overrides,
    )


def encode_report(report: RegistryReport) -> str:
    """Serialize through one typed codec boundary."""
    return msgspec.json.encode(report).decode()


def decode_report(raw: bytes) -> RegistryReport:
    """Decode against the generated report contract."""
    return msgspec.json.decode(raw, type=RegistryReport)


def cached_report(
    repo_root: Path, registry: Registry, *, max_age_s: int = 600
) -> RegistryReport | None:
    """An override, future timestamp or different package digest is never a hit."""
    try:
        report = decode_report((repo_root / _CACHE).read_bytes())
        age = (datetime.now(UTC) - datetime.fromisoformat(report.checked_at)).total_seconds()
    except OSError, ValueError, msgspec.DecodeError:
        return None
    if (
        report.overrides
        or report.registry_sha256 != registry.registry_sha256
        or not 0 <= age < max_age_s
    ):
        return None
    return report


def write_cache(repo_root: Path, report: RegistryReport) -> None:
    """Publish only unoverridden reports, atomically in repository state."""
    if report.overrides:
        return
    path = repo_root / _CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(path, encode_report(report) + "\n")


def _shell_stages(command: str) -> list[list[str]]:
    """Keep prefixes and parse failures for launch context; never expand shell."""
    command = command.replace("\\\n", "")
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = "#"
    stages: list[list[str]] = [[]]
    for token in lexer:
        if token and all(c in ";&|\n" for c in token):
            stages.append([])
        else:
            stages[-1].append(token)
    return [stage for stage in stages if stage]


def command_stages(command: str) -> list[list[str]]:
    """Return program stages for offline rendering; classification keeps errors."""
    try:
        return [_strip_prefix(stage) for stage in _shell_stages(command)]
    except ValueError:
        return []


def _strip_prefix(tokens: list[str]) -> list[str]:
    tokens = list(tokens)
    while tokens:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
            tokens = tokens[1:]
        elif tokens[0] == "env":
            tokens = tokens[1:]
            if tokens and tokens[0] == "-i":
                tokens = tokens[1:]
        elif tokens[0] == "timeout" and len(tokens) >= _MIN_TIMEOUT_PREFIX:
            tokens = tokens[2:]
        elif tokens[:3] in (["mise", "exec", "--"], ["mise", "x", "--"]):
            tokens = tokens[3:]
        elif tokens[0] == "command":
            tokens = tokens[1:]
        else:
            break
    return tokens


def _explicit_model(arguments: list[str]) -> str | None:
    for index, argument in enumerate(arguments):
        if argument in ("-m", "--model") and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument.startswith("--model="):
            return argument.partition("=")[2]
        if argument.startswith("-m") and argument != "-m":
            return argument[2:]
        if (
            argument == "-c"
            and index + 1 < len(arguments)
            and arguments[index + 1].startswith(("review_model=", "model="))
        ):
            return arguments[index + 1].partition("=")[2].strip("\"'")
    return None


@dataclass(frozen=True)
class _ResolvedModel:
    """A model identity and its provenance; None means resolution failed."""

    slug: str | None
    source: str


def _model_value(value: object, source: str) -> _ResolvedModel:
    # Do not echo shell expansions, malformed config values, or other keys.
    slug = value if isinstance(value, str) else ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", slug):
        return _ResolvedModel(None, f"{source}: model indeterminate")
    return _ResolvedModel(slug, source)


def _argument_values(arguments: list[str]) -> dict[str, str]:
    """Read model/profile flags and top-level -c keys on either side of exec."""
    values = {}
    names = {
        "-m": "model",
        "--model": "model",
        "-p": "profile",
        "--profile": "profile",
        "-C": "cd",
        "--cd": "cd",
    }
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in (*names, "-c", "--config"):
            index += 1
            value = arguments[index] if index < len(arguments) else ""
            key = names.get(argument, "config")
        elif argument.startswith(("--model=", "--profile=", "--config=", "--cd=")):
            key, _, value = argument[2:].partition("=")
        elif argument.startswith(("-m", "-c", "-C")):
            key = (
                "cd"
                if argument.startswith("-C")
                else ("model" if argument.startswith("-m") else "config")
            )
            value = argument[2:]
        else:
            index += 1
            continue
        if key == "config":
            name, separator, value = value.partition("=")
            if separator and name.strip() in ("model", "review_model"):
                values[f"config.{name.strip()}"] = value.strip().strip("\"'")
        else:
            values[key] = value
        index += 1
    return values


def _wrapper_name(tokens: list[str]) -> str:
    program = Path(tokens[0]).name
    return tokens[2] if program == "mise" and tokens[1:2] == ["run"] and tokens[2:3] else program


def _config_layer(path: Path, *, required: bool = False) -> dict:
    """Read TOML without surfacing decoder messages containing private values."""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if not required:
            return {}
        raise ValueError(f"{path.name}: unreadable profile; model indeterminate") from None
    except OSError, ValueError:
        raise ValueError(f"{path.name}: unreadable config; model indeterminate") from None


def _trust_roots(root: Path) -> tuple[Path, ...]:
    """Include filesystem ancestors and a linked worktree's main clone."""
    root = root.resolve()
    roots = (root, *root.parents)
    if not any((parent / ".git").exists() for parent in roots):
        return roots
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=root,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        raise ValueError("git common dir: trust indeterminate") from None
    if proc.returncode == 0:
        common = Path(proc.stdout.decode().strip()).resolve()
        if common.name == ".git":
            return (*roots, common.parent)
    # A plain .git placeholder has no linked-worktree identity to resolve.
    if any((parent / ".git").is_file() for parent in roots):
        raise ValueError("git common dir: trust indeterminate")
    return roots


def _trusted_project(root: Path, user: dict) -> bool:
    projects = user.get("projects", {})
    if not isinstance(projects, dict):
        raise TypeError("projects: trust indeterminate")
    # Match codex_trust's ANY trusted ancestor policy and the root Git project.
    # UNVERIFIED: V-TRUST-PARENT runtime parity is prohibited in this lane.
    return any(
        isinstance(entry := projects.get(str(parent)), dict)
        and entry.get("trust_level") == "trusted"
        for parent in _trust_roots(root)
    )


def _model_layers(root: Path, home: Path, values: dict[str, str]) -> Iterator[tuple[dict, str]]:
    """Read lower layers only when a higher model source has no applicable key."""
    user = _config_layer(home / "config.toml")
    if _trusted_project(root, user):
        for parent in (root, *root.parents):
            path = parent / ".codex/config.toml"
            yield _config_layer(path), f"project {path}"
            if (parent / ".git").exists():
                break
    if "profile" in values:
        profile = values["profile"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", profile):
            raise ValueError("--profile: profile indeterminate")
        path = home / f"{profile}.config.toml"
        yield _config_layer(path, required=True), f"profile {path.name}"
    yield user, "user config.toml"


def _configured_model(layers: Iterator[tuple[dict, str]], key: str) -> _ResolvedModel | None:
    for data, source in layers:
        if key in data:
            return _model_value(data[key], f"{source} {key}")
    return None


def _argv_model(values: dict[str, str], *, review: bool) -> _ResolvedModel | None:
    if review and "config.review_model" in values:
        return _model_value(values["config.review_model"], "-c review_model")
    explicit = next((key for key in ("model", "config.model") if key in values), None)
    if not review and explicit:
        return _model_value(values[explicit], "--model/-m" if explicit == "model" else "-c model")
    return None


def _config_model(
    root: Path, home: Path, values: dict[str, str], *, review: bool
) -> _ResolvedModel:
    if review and (
        configured := _configured_model(_model_layers(root, home, values), "review_model")
    ):
        return configured
    explicit = next((key for key in ("model", "config.model") if key in values), None)
    if explicit:
        return _model_value(values[explicit], "--model/-m" if explicit == "model" else "-c model")
    if configured := _configured_model(_model_layers(root, home, values), "model"):
        return configured
    return _ResolvedModel(None, "no model in argv, profile or config; model indeterminate")


def _resolve_codex_model(tokens: list[str], root: Path, home: Path | None = None) -> _ResolvedModel:
    """Resolve wrapper-emitted arguments before read-only configuration layers."""
    wrapper = _wrapper_name(tokens)
    known = ("codex", "kb-codex", "sdlc-team", "codex-lane")
    if wrapper not in known:
        return _ResolvedModel(None, "unknown codex wrapper: model indeterminate")
    values = _argument_values(tokens[1:])
    review = "review" in tokens[1:] or (wrapper == "kb-codex" and "--review" in tokens[1:])
    if wrapper != "codex":
        default = load_registry().codex.dispatch[wrapper.replace("-", "_")].slug
        return _model_value(
            values.get("model", default),
            f"{wrapper} wrapper-emitted "
            + ("-c review_model (--model)" if wrapper == "kb-codex" and review else "--model"),
        )
    if explicit := _argv_model(values, review=review):
        return explicit
    home = home or Path(os.environ.get("CODEX_HOME") or _CODEX_USER_CONFIG.parent).expanduser()
    if any(char in str(home) for char in ("$", "`")):
        return _ResolvedModel(None, "CODEX_HOME: model indeterminate")
    try:
        return _config_model(root.resolve(), home, values, review=review)
    except (ValueError, TypeError) as exc:
        return _ResolvedModel(None, str(exc))


def _launch_vendor(tokens: list[str]) -> Vendor | None:
    if not tokens:
        return None
    program = Path(tokens[0]).name
    wrapper = _wrapper_name(tokens)
    non_launchers = (
        "kb-codex-config-check",
        "codex-log-check",
        "codex-agent-parity",
        "codex-agent-validate",
        "codex-lane-mirror",
        "codex-schema-generate",
        "codex-schema-check",
    )
    if (
        program in ("sh", "bash", "eval")
        or wrapper in non_launchers
        or any(t in ("--help", "-h", "--version", "-V") for t in tokens[1:])
    ):
        return None
    if program == "codex" and any(t in ("exec", "e", "review") for t in tokens[1:]):
        return Vendor.CODEX
    if wrapper in ("kb-codex", "sdlc-team", "codex-lane") or wrapper.startswith(
        ("kb-codex-", "codex-")
    ):
        return Vendor.CODEX
    if program == "agy-delegate.sh" or (
        program == "agy" and any(t in ("--print", "-p") for t in tokens[1:])
    ):
        return Vendor.AGY
    return None


def _classify_stage(
    tokens: list[str],
    report: RegistryReport,
    root: Path,
    home: Path | None = None,
    context_error: str = "",
) -> LaunchDecision:
    vendor = _launch_vendor(tokens)
    row = next((v for v in report.vendors if v.vendor == vendor), None)
    if row is None or row.verdict != Verdict.INVALID:
        return LaunchDecision(allow=True, reason="")
    if vendor == Vendor.CODEX:
        resolved = (
            _ResolvedModel(None, context_error)
            if context_error
            else _resolve_codex_model(tokens, root, home)
        )
        if resolved.slug is None:
            return LaunchDecision(
                allow=False, reason=f"codex model indeterminate: {resolved.source}"
            )
        if resolved.slug not in row.invalid_pins.values():
            return LaunchDecision(allow=True, reason="")
        return LaunchDecision(
            allow=False,
            reason=f"codex stale pin launch: {resolved.slug} (resolved via {resolved.source})",
        )
    explicit = _explicit_model(tokens)
    if vendor == Vendor.AGY:
        current = {slug for role, slug in row.current_pins.items() if role not in row.invalid_pins}
        if explicit is not None and (
            explicit in current or explicit in {row.display_names.get(slug) for slug in current}
        ):
            return LaunchDecision(allow=True, reason="")
    return LaunchDecision(
        allow=False,
        reason=f"{vendor} stale pin launch: {', '.join(sorted(row.invalid_pins.values()))}",
    )


def _context_path(value: str, root: Path, source: str, *, must_exist: bool = False) -> Path:
    """Resolve literal command paths without executing expansions or cd."""
    if not value or any(char in value for char in ("$", "`")):
        raise ValueError(f"{source}: context indeterminate")
    path = Path(value).expanduser()
    path = path if path.is_absolute() else root / path
    try:
        path = path.resolve(strict=must_exist)
    except OSError, ValueError:
        raise ValueError(f"{source}: context indeterminate") from None
    if must_exist and not path.is_dir():
        raise ValueError(f"{source}: context indeterminate")
    return path


def _stage_context(raw: list[str], root: Path) -> tuple[Path, Path | None]:
    """Read launch-local prefixes before the program-only lexer strips them."""
    tokens = _strip_prefix(raw)
    prefix = raw[: len(raw) - len(tokens)]
    home = None
    for argument in prefix:
        if argument.startswith("CODEX_HOME="):
            home = _context_path(argument.partition("=")[2], root, "CODEX_HOME")
    values = _argument_values(tokens[1:])
    if "cd" in values:
        root = _context_path(values["cd"], root, "-C/--cd", must_exist=True)
    return root, home


def _cd_root(tokens: list[str], root: Path) -> Path:
    if len(tokens) != _CD_TOKENS:
        raise ValueError("cd: context indeterminate")
    return _context_path(tokens[1], root, "cd", must_exist=True)


def _classify_shell(command: str, report: RegistryReport, root: Path) -> LaunchDecision:
    try:
        stages = _shell_stages(command)
    except ValueError:
        codex_invalid = any(
            row.vendor == Vendor.CODEX and row.verdict == Verdict.INVALID for row in report.vendors
        )
        if codex_invalid and re.search(
            r"\b(?:codex(?:-[\w-]+)?|kb-codex(?:-[\w-]+)?|sdlc-team)\b", command
        ):
            return LaunchDecision(
                allow=False, reason="codex model indeterminate: shell parse failure"
            )
        return LaunchDecision(allow=True, reason="")
    context_error = ""
    for raw in stages:
        tokens = _strip_prefix(raw)
        try:
            if tokens and tokens[0] == "cd":
                root = _cd_root(tokens, root)
                continue
            if _launch_vendor(tokens) != Vendor.CODEX:
                decision = _classify_stage(tokens, report, root)
                if not decision.allow:
                    return decision
                continue
            launch_root, home = _stage_context(raw, root)
        except ValueError as exc:
            context_error = str(exc)
            launch_root, home = root, None
        decision = _classify_stage(tokens, report, launch_root, home, context_error)
        if not decision.allow:
            return decision
    return LaunchDecision(allow=True, reason="")


def classify_launch(
    *,
    tool: str,
    command: str | None,
    subagent_type: str | None,
    report: RegistryReport,
    root: Path | None = None,
) -> LaunchDecision:
    """Deny only a classified stale launch; repair and Claude tools always pass."""
    if report.disabled_by_baseline:
        return LaunchDecision(allow=True, reason="")
    if tool in ("Agent", "agent.spawn"):
        codex = next(v for v in report.vendors if v.vendor == Vendor.CODEX)
        roles = {
            r
            for stem, r in codex.agent_roles.items()
            if fnmatch.fnmatchcase(subagent_type or "", stem)
        }
        if codex.verdict == Verdict.INVALID and roles & codex.invalid_pins.keys():
            resolved = ", ".join(
                f"{codex.invalid_pins[role]} (launch_agents role {role})"
                for role in sorted(roles & codex.invalid_pins.keys())
            )
            return LaunchDecision(
                allow=False, reason=f"codex stale pin for agent {subagent_type}: {resolved}"
            )
    if tool == "Bash":
        return _classify_shell(command or "", report, root or Path.cwd())
    return LaunchDecision(allow=True, reason="")


def _catalog_disagreement(report: RegistryReport) -> bool:
    """Compare observed catalog contents with the reviewed feed inventory."""
    return any(
        row.invalid_pins
        or row.unknown_slugs
        or any("claude.api missing from anthropic:" in finding for finding in row.findings)
        for row in report.vendors
    )


def _openrouter_ids(payload: bytes) -> set[str]:
    """Decode the control feed without treating it as enforcement evidence."""
    data = msgspec.json.decode(payload)
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not all(
        isinstance(row, dict) and isinstance(row.get("id"), str) for row in rows
    ):
        raise ValueError("KEY-SHAPE FAIL: OpenRouter data[].id")
    return {row["id"] for row in rows}


def _control_findings(report: RegistryReport, remaining_s: float) -> list[str]:
    """Read OpenRouter only for catalog disagreement, within the wall budget."""
    if report.disabled_by_baseline or not _catalog_disagreement(report):
        return []
    if remaining_s <= 0:
        return ["OpenRouter control NOT CHECKED (budget; findings only)"]
    completed: queue.Queue[list[str]] = queue.Queue()

    def collect() -> None:
        try:
            ids = _openrouter_ids(_fetch("https://openrouter.ai/api/v1/models", remaining_s))
            findings = []
            for row in report.vendors:
                candidates = set(row.invalid_pins.values()) | set(row.unknown_slugs)
                candidates.update(
                    finding.removeprefix("claude.api missing from anthropic: ")
                    for finding in row.findings
                    if finding.startswith("claude.api missing from anthropic: ")
                )
                for slug in sorted(candidates):
                    present = any(identifier.rsplit("/", 1)[-1] == slug for identifier in ids)
                    state = "present" if present else "absent"
                    findings.append(f"OpenRouter control: {slug} {state} (findings only)")
            completed.put(findings)
        except (httpx2.HTTPError, msgspec.DecodeError, ValueError) as exc:
            completed.put([f"OpenRouter control NOT CHECKED: {exc} (findings only)"])

    threading.Thread(target=collect, daemon=True).start()
    try:
        return completed.get(timeout=remaining_s)
    except queue.Empty:
        return ["OpenRouter control NOT CHECKED (budget; findings only)"]


def _baseline_disabled(path: Path) -> bool:
    try:
        return (
            tomllib.loads(path.read_text(encoding="utf-8")).get("models", {}).get("enabled", True)
            is False
        )
    except OSError, ValueError:
        return False


def _overrides(args: argparse.Namespace) -> list[str]:
    return [key for key in ("registry", "overlay", "codex_user_config") if getattr(args, key)]


def _check(root: Path, args: argparse.Namespace) -> RegistryReport:
    registry = load_registry(Path(args.registry) if args.registry else None)
    started = time.monotonic()
    trust = codex_trust(
        root,
        Path(args.codex_user_config)
        if args.codex_user_config
        else Path.home() / ".codex/config.toml",
    )
    disabled = _baseline_disabled(root / args.baseline)
    feeds = (
        read_feeds(
            resolved_model=args.resolved_model, budget_s=max(0, 30 - (time.monotonic() - started))
        )
        if not disabled
        else Feeds(
            {v.value: _feed(NativeFeedStatus.UNREADABLE) for v in Vendor},
            args.resolved_model,
            {},
            disabled_by_baseline=True,
            overrides=[],
        )
    )
    feeds.disabled_by_baseline = disabled
    feeds.overrides = _overrides(args)
    overlay = None
    if any(
        set(feed.slugs) - set(feed.hidden_slugs) - _known(registry)[vendor]
        for vendor, feed in feeds.vendors.items()
    ):
        overlay = read_overlay(
            args.overlay or OVERLAY_URL,
            timeout_s=max(0.1, min(5.0, 35 - (time.monotonic() - started))),
        )
    report = evaluate(registry, feeds, overlay, trust, now=datetime.now(UTC))
    control = _control_findings(report, max(0, 35 - (time.monotonic() - started)))
    for row in report.vendors:
        row.findings.extend(control)
    write_cache(root, report)
    return report


def _ship_rc(report: RegistryReport) -> int:
    """A ship check needs at least one checked feed and no invalid pin (F10)."""
    if report.disabled_by_baseline:
        return 0
    return int(
        any(v.invalid_pins for v in report.vendors)
        or all(v.verdict == Verdict.NOT_CHECKED for v in report.vendors)
    )


def main(root: Path, argv: list[str]) -> int:
    """Identical baseline-aware CLI for both consumers of kb_setup."""
    parser = argparse.ArgumentParser(prog="kb-setup models")
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("check", "ship-check"):
        p = sub.add_parser(mode)
        p.add_argument("--json", action="store_true")
        p.add_argument("--resolved-model")
        p.add_argument("--registry", default=os.environ.get("KB_MODELS_REGISTRY"))
        p.add_argument("--overlay", default=os.environ.get("KB_MODELS_OVERLAY"))
        p.add_argument("--baseline", type=Path, default=Path("doctor.toml"))
        p.add_argument("--codex-user-config")
    p = sub.add_parser("classify-launch")
    p.add_argument("--report-json", type=Path, required=True)
    p.add_argument("--tool", required=True)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--command")
    group.add_argument("--subagent-type")
    args = parser.parse_args(argv)
    if args.mode == "classify-launch":
        report = decode_report(
            sys.stdin.buffer.read()
            if str(args.report_json) == "-"
            else args.report_json.read_bytes()
        )
        result = classify_launch(
            tool=args.tool,
            command=args.command,
            subagent_type=args.subagent_type,
            report=report,
            root=root,
        )
        print("ALLOW" if result.allow else f"DENY: {result.reason}")
        return 0
    report = _check(root, args)
    if report.disabled_by_baseline:
        print(
            "models gate DISABLED by doctor.toml",
            file=sys.stderr if args.json else sys.stdout,
        )
    if args.json:
        print(encode_report(report))
    else:
        suffix = " OVERRIDE" if report.overrides else ""
        for vendor in report.vendors:
            print(
                f"{vendor.vendor}: {vendor.verdict}{suffix} "
                f"feed={vendor.feed} overlay={vendor.overlay}"
            )
            for line in vendor.findings + vendor.retiring:
                print(f"  {line}{suffix}")
    return _ship_rc(report) if args.mode == "ship-check" else 0
