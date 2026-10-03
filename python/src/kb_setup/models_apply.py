# Copyright (c) 2026 Raymond Manaloto
"""Offline, tracked-file rendering and pin-site checks for both repositories."""

from __future__ import annotations

import argparse
import fnmatch
import re
import shlex
import subprocess
import tomllib
from dataclasses import dataclass, field
from importlib.resources import files
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import models

if TYPE_CHECKING:
    from collections.abc import Callable

    from kb_setup.generated.models_registry import Registry

_FENCE = re.compile(r"^\s*(?:<!--|#|//)\s*models-apply:\s*(off|on)(?:\s*-->)?\s*$")
_CANDIDATE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-\[\]]*$")
_PLUGIN = Path(".claude/skills/model-registry")
_MIN_COMMAND_TOKENS = 2
_SHELL_TOKEN = re.compile(r"""(?:'[^']*'|"(?:\\.|[^"\\])*"|\\[\s\S]|[^\s;&|'"\\])+|[;&|\n]+""")


@dataclass(frozen=True)
class ArgvSite:
    """An explicitly owned argument or complete command render."""

    glob: str
    anchor: str = ""
    flag: str = ""
    value: str = ""
    render: str = ""
    strict: bool = False


@dataclass(frozen=True)
class SitesConfig:
    """Reviewed inventory; all patterns resolve against Git's tracked files."""

    owned: tuple[str, ...] = ()
    derived: tuple[str, ...] = ()
    exempt: tuple[str, ...] = ()
    agent_pairs: tuple[str, ...] = ()
    argv_sites: tuple[ArgvSite, ...] = ()
    post_apply: tuple[str, ...] = ()
    effort_excluded: tuple[str, ...] = ()
    codex_config: tuple[str, ...] | None = None


def load_sites(path: Path) -> SitesConfig:
    """Read the shared sites format, retaining the optional D allowlist."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return SitesConfig(
        owned=tuple(row["glob"] for row in data.get("owned", [])),
        derived=tuple(row["glob"] for row in data.get("derived", [])),
        exempt=tuple(data.get("exempt", {}).get("globs", [])),
        agent_pairs=tuple(row["glob"] for row in data.get("agent_pairs", [])),
        argv_sites=tuple(ArgvSite(**row) for row in data.get("argv_site", [])),
        post_apply=tuple(row["task"] for row in data.get("post_apply", [])),
        effort_excluded=tuple(data.get("effort_excluded", {}).get("globs", [])),
        codex_config=tuple(data["codex_config"]["allow"]) if "codex_config" in data else None,
    )


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def _active(source: str, transform: Callable[[str], str]) -> str:
    """Transform complete active spans, leaving historical fences byte-exact."""
    output: list[str] = []
    span: list[str] = []
    enabled = True
    for line in source.splitlines(keepends=True):
        marker = _FENCE.fullmatch(line.rstrip("\r\n"))
        if marker:
            output.append(transform("".join(span)) if enabled else "".join(span))
            span = []
            target = marker[1] == "on"
            if target == enabled:
                raise ValueError("unbalanced models-apply fence")
            enabled = target
            output.append(line)
        else:
            span.append(line)
    if not enabled:
        raise ValueError("unterminated models-apply fence")
    output.append(transform("".join(span)))
    return "".join(output)


def active_text(source: str) -> str:
    """Return only active text, for checks that must ignore dated measurements."""
    parts: list[str] = []
    _active(source, lambda text: parts.append(text) or "")
    return "".join(parts)


def _slug_pattern(slug: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9_.-])" + re.escape(slug) + r"(?![A-Za-z0-9_.-])")


def _rewrite_slugs(text: str, registry: Registry) -> str:
    for block in (registry.codex, registry.agy):
        for slug, known in block.known.items():
            if known.family in block.pins:
                text = _slug_pattern(slug).sub(block.pins[known.family].slug, text)
    return text


def _set_key(text: str, key: str, value: str | None) -> str:
    pattern = re.compile(r"^" + re.escape(key) + r"\s*=.*\n?", re.MULTILINE)
    if value is None:
        return pattern.sub("", text)
    line = f'{key} = "{value}"\n'
    if pattern.search(text):
        return pattern.sub(lambda _: line, text)
    # Agent keys precede the instruction body; never insert into that string.
    boundary = re.search(r"^(?:developer_instructions\s*=|\[)", text, re.MULTILINE)
    index = boundary.start() if boundary else len(text)
    return text[:index] + line + text[index:]


def _config_pair(text: str, registry: Registry) -> str:
    pattern = re.compile(r"(^\[agents\]\n)(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
    pair = registry.codex.config_fallback

    def replace(match: re.Match[str]) -> str:
        body = _set_key(match[2], "default_subagent_model", pair.slug)
        return match[1] + _set_key(body, "default_subagent_reasoning_effort", pair.effort)

    if not pattern.search(text):
        text += "\n[agents]\n"
    return pattern.sub(replace, text)


def _command_spans(text: str, *, name: str = "") -> list[tuple[int, int, bool]]:
    """Select original offsets, so identical prose cannot become an argv site."""
    if name.endswith(".py"):
        return []  # Python argv builders are checked by their behavior tests.
    spans: list[tuple[int, int, bool]] = []
    in_block = False
    shell_block = False
    pending: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        start, offset = offset, offset + len(line)
        fence = re.match(r"^\s*(`{3,}|~{3,})([^\n]*)$", line)
        if fence:
            in_block = not in_block
            language = fence[2].strip().split(maxsplit=1)
            shell_block = in_block and (language[0] if language else "") in {
                "bash",
                "sh",
                "shell",
                "zsh",
                "",
            }
            continue
        if shell_block:
            if pending is None:
                pending = start
            if not line.rstrip().endswith("\\"):
                spans.append((pending, offset, False))
                pending = None
        elif not in_block:
            match = re.fullmatch(r"\s*(?:[-*]\s+)?`([^`\n]+)`\s*", line)
            if match:
                spans.append((start + match.start(1), start + match.end(1), True))
    return spans


def _commands(text: str, *, name: str = "") -> list[tuple[str, bool]]:
    """Find shell blocks and standalone command spans, excluding prose mentions."""
    return [
        (text[start:end].replace("\\\n", "").strip(), inline)
        for start, end, inline in _command_spans(text, name=name)
    ]


def _strict_needed(command: str, *, inline: bool) -> bool:
    if "…" in command:
        return False
    for stage in models.command_stages(command):
        if (
            len(stage) < _MIN_COMMAND_TOKENS
            or Path(stage[0]).name != "codex"
            or stage[1] not in {"exec", "review"}
        ):
            continue
        arguments = stage[2:]
        if (inline and not arguments) or any(
            arg in {"--help", "-h", "--version", "-V"} for arg in arguments
        ):
            continue
        if "--strict-config" not in arguments:
            return True
    return False


def _subcommand_end(stage: str, *, inline: bool) -> int | None:
    """Locate the actual program pair, never a quoted echo or assignment value."""
    if not _strict_needed(stage, inline=inline):
        return None
    argv = models.command_stages(stage)[0]
    words = [(shlex.split(match[0]), match.end()) for match in _SHELL_TOKEN.finditer(stage)]
    words = [word for word in words if word[0]]
    for current, following in pairwise(words):
        if current[0] == [argv[0]] and following[0] == [argv[1]]:
            return following[1]
    return None


def _strict_fragment(fragment: str, *, inline: bool) -> str:
    """Insert by original offsets, preserving shell quoting and stage boundaries."""
    separators = [
        match for match in _SHELL_TOKEN.finditer(fragment) if re.fullmatch(r"[;&|\n]+", match[0])
    ]
    start = 0
    insertions = []
    for end, next_start in [(m.start(), m.end()) for m in separators] + [(len(fragment), 0)]:
        position = _subcommand_end(fragment[start:end], inline=inline)
        if position is not None:
            insertions.append(start + position)
        start = next_start
    for position in reversed(insertions):
        fragment = fragment[:position] + " --strict-config" + fragment[position:]
    return fragment


def _strict_commands(text: str, *, name: str = "") -> str:
    """Render strict config only on actual documented exec/review invocations."""
    output = []
    previous = 0
    for start, end, inline in _command_spans(text, name=name):
        output.append(text[previous:start])
        output.append(_strict_fragment(text[start:end], inline=inline))
        previous = end
    output.append(text[previous:])
    return "".join(output)


def _value(template: str, name: str, registry: Registry) -> str:
    if template == "{by-agent-role}":
        return models.agent_pair(Path(name).stem, registry)[0]

    def lookup(match: re.Match[str]) -> str:
        obj: object = registry
        for key in match[1].split("."):
            obj = obj[key] if isinstance(obj, dict) else getattr(obj, key)
        return str(obj)

    return re.sub(r"\{([^{}]+)\}", lookup, template)


def _argv_render(text: str, site: ArgvSite, name: str, registry: Registry) -> str:
    if site.render:
        replacement = _value(site.render, name, registry)
        return re.sub(
            r"^.*" + re.escape(site.anchor) + r".*$",
            lambda _: replacement,
            text,
            flags=re.MULTILINE,
        )
    if site.flag:
        pattern = re.compile(re.escape(site.flag) + r"(?:\s+|=)(?:\"[^\"]*\"|'[^']*'|[^\s\\`]+)")
        replacement = f"{site.flag} {_value(site.value, name, registry)}"
        lines = text.splitlines(keepends=True)

        def rewrite(line: str) -> str:
            if site.anchor and site.anchor not in line:
                return line
            if pattern.search(line):
                return pattern.sub(lambda _: replacement, line)
            if site.anchor:
                return line.replace(site.anchor, f"{site.anchor} {replacement}")
            return line

        text = "".join(rewrite(line) for line in lines)
    return _strict_commands(text, name=name) if site.strict else text


def _lane_streams(line: str) -> tuple[str, bool]:
    """Log unredirected streams while preserving authored destinations."""
    log = r"[\"\']?\$(?:KB_LANE|\{KB_LANE\})/lane\.log[\"\']?"
    combined = rf"(?<![\d>])1?>\s*{log}\s+2>&1|&>\s*{log}"
    # Tokenize without changing quote spelling. Any existing redirect belongs
    # to the author; tee also owns its output. Never append a competing one.
    tokens = list(_SHELL_TOKEN.finditer(line))
    words = [match[0] for match in tokens]
    combined_redirect = any(
        first[0] == "&" and second[0].startswith(">") and first.end() == second.start()
        for first, second in pairwise(tokens)
    )
    redirects = [
        match
        for word in words
        if not word.startswith(("'", '"')) and (match := re.match(r"^(\d*)>", word))
    ]
    stdout = combined_redirect or any(match[1] in {"", "1"} for match in redirects)
    stderr = combined_redirect or any(match[1] == "2" for match in redirects)
    pipeline = "|" in words
    if not re.search(combined, line):
        if pipeline and not stderr:
            position = next(
                match.start() for match in _SHELL_TOKEN.finditer(line) if match[0] == "|"
            )
            line = line[:position].rstrip() + " 2>&1 " + line[position:]
        elif not stdout and not pipeline:
            line += ' > "$KB_LANE/lane.log"'
            if not stderr:
                line += " 2>&1"
        elif stdout and not stderr and not pipeline:
            if re.search(rf"1?>>?\s*{log}", line):
                line += " 2>&1"
            else:
                line += ' 2> "$KB_LANE/lane.log"'
    return line, pipeline


def _lane_launch_end(line: str) -> str:
    """Preserve redirects, wait for background lanes, and retain pipeline rc."""
    line = line.rstrip("\n")
    artifact = r'; (?:rc=\$\?; )?echo "rc=\$(?:\?|rc)" > "\$KB_LANE/lane\.rc"'
    record_rc = bool(re.search(artifact, line))
    line = re.sub(artifact, "", line)
    line = re.sub(r"; rc=\$\?$", "", line)
    line = re.sub(r' & wait "\$!"$', " &", line)
    background = line.rstrip().endswith("&") and not line.rstrip().endswith("&&")
    if background:
        line = line.rstrip()[:-1].rstrip()
    line, pipeline = _lane_streams(line)
    if pipeline and not line.startswith("set -o pipefail; "):
        line = "set -o pipefail; " + line
    if background:
        line += ' & wait "$!"'
    line += "; rc=$?"
    if record_rc:
        line += '; echo "rc=$rc" > "$KB_LANE/lane.rc"'
    return line + "\n"


def _wrapper_logs(text: str) -> str:
    """Bind every fenced KB wrapper to a retained stderr log and rolecheck rc."""
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    in_block = False
    launching = False
    checked_block = False
    for index, original_line in enumerate(lines):
        line = original_line
        if line.lstrip().startswith("```"):
            in_block = not in_block
            if not in_block and checked_block:
                output.append(line)
                note = "\nA non-zero `lane.log.rolecheck` is a FAIL; report the malformed role.\n"
                if note.strip() not in "".join(lines[index + 1 : index + 4]):
                    output.append(note)
                checked_block = False
                continue
        if in_block and "mise run codex-log-check" in line:
            checked_block = True
            line = (
                'mise run codex-log-check -- "$KB_LANE/lane.log"; '
                'echo "$?" > "$KB_LANE/lane.log.rolecheck"; exit "$rc"\n'
            )
        if in_block and "mise run kb-codex --" in line:
            launching = True
        if launching and not line.rstrip().endswith("\\"):
            line = _lane_launch_end(line)
            if index + 1 < len(lines) and "mise run codex-log-check" in lines[index + 1]:
                launching = False
            else:
                output.append(line)
                output.append(
                    'mise run codex-log-check -- "$KB_LANE/lane.log"; '
                    'echo "$?" > "$KB_LANE/lane.log.rolecheck"; exit "$rc"\n'
                )
                checked_block = True
                launching = False
                continue
        output.append(line)
    return "".join(output)


def render(name: str, source: str, sites: SitesConfig, registry: Registry) -> str:
    """Render one owned file, preserving every fenced span exactly."""

    def transform(text: str) -> str:
        text = _rewrite_slugs(text, registry)
        for site in sites.argv_sites:
            if fnmatch.fnmatchcase(name, site.glob):
                text = _argv_render(text, site, name, registry)
        text = _strict_commands(text, name=name)
        if name.startswith((".claude/agents/kb-codex-", ".codex/agents/kb-codex-")):
            text = _wrapper_logs(text)
        return text

    text = _active(source, transform)
    if _matches(name, sites.agent_pairs):
        model, effort = models.agent_pair(Path(name).stem, registry)
        boundary = re.search(r"^developer_instructions\s*=", text, re.MULTILINE)
        index = boundary.start() if boundary else len(text)
        header = _set_key(text[:index], "model", model)
        header = _set_key(header, "model_reasoning_effort", effort)
        text = header + text[index:]
    if name == ".codex/config.toml":
        text = _config_pair(text, registry)
    return text


def plugin_bytes() -> dict[str, bytes]:
    """The package is the sole source of the three rendered plugin artifacts."""
    root = files("kb_setup").joinpath("plugins/model-registry")
    names = (".claude-plugin/plugin.json", "hooks/hooks.json", "hooks/register.ts")
    return {name: root.joinpath(name).read_bytes() for name in names}


def _pin_candidates(name: str, text: str) -> list[str]:
    if name.endswith(".md") and "/agents/" in name:
        frontmatter = re.match(r"\A---\n(.*?)\n---", text, re.DOTALL)
        return (
            re.findall(r"^model:\s*(\S+)\s*$", frontmatter[1], re.MULTILINE) if frontmatter else []
        )
    if name.endswith((".js", ".ts")):
        return [m[2] for m in re.finditer(r"\bmodel:\s*(['\"])(.*?)\1", text)]
    if name == ".claude/settings.json":
        import json

        value = json.loads(text).get("fallbackModel", [])
        return [value] if isinstance(value, str) else value
    return []


def check_aliases_only(root: Path, sites: SitesConfig) -> list[str]:
    """Check literal Claude pin candidates, skipping expressions and descriptions."""
    aliases = models.load_registry().claude.aliases
    findings = []
    for name in models.tracked_files(root):
        if _matches(name, sites.exempt):
            continue
        if not name.endswith((".md", ".js", ".ts", ".json")):
            continue
        text = (root / name).read_text(encoding="utf-8")
        findings.extend(
            f"(e) {name}: Claude pin must be an alias: {candidate}"
            for candidate in _pin_candidates(name, text)
            if isinstance(candidate, str)
            and _CANDIDATE.fullmatch(candidate)
            and candidate not in aliases
        )
    return findings


def _slug_findings(name: str, text: str, sites: SitesConfig, registry: Registry) -> list[str]:
    declared = _matches(name, sites.owned + sites.derived)
    if not declared and _matches(name, sites.exempt):
        return []
    # r7.2: definitions cannot be pin sites, regardless of a consumer's inventory.
    if name == "python/src/kb_setup/models.toml" or Path(name).name == "models-sites.toml":
        return []
    findings = []
    for block in (registry.codex, registry.agy):
        for slug, known in block.known.items():
            if not _slug_pattern(slug).search(text):
                continue
            if not declared:
                findings.append(f"(d) {name}: undeclared model pin site: {slug}")
            elif known.family not in block.pins or slug != block.pins[known.family].slug:
                findings.append(f"(c) {name}: non-current pin: {slug}")
    return findings


def _argv_findings(name: str, text: str, sites: SitesConfig) -> list[str]:
    findings = []
    for site in sites.argv_sites:
        if not fnmatch.fnmatchcase(name, site.glob):
            continue
        if site.anchor and site.anchor not in text:
            findings.append(f"(b) {name}: argv anchor does not resolve: {site.anchor}")
        elif site.flag and not re.search(re.escape(site.flag) + r"(?:\s+|=)\S+", text):
            findings.append(f"(b) {name}: argv flag does not resolve: {site.flag}")
    return findings


def _pair_findings(name: str, source: str, registry: Registry) -> list[str]:
    expected = models.agent_pair(Path(name).stem, registry)
    data = tomllib.loads(source)
    actual = data.get("model"), data.get("model_reasoning_effort")
    if actual != expected or (expected[1] is None and "model_reasoning_effort" in data):
        return [f"(i) {name}: agent pair differs; expected {expected!r}"]
    return []


def _leaf_keys(data: dict, prefix: str = "") -> set[str]:
    result = set()
    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_leaf_keys(value, name))
        else:
            result.add(name)
    return result


def _settings_findings(root: Path, sites: SitesConfig, registry: Registry) -> list[str]:
    import json

    findings = []
    settings = root / ".claude/settings.json"
    data = json.loads(settings.read_text()) if settings.exists() else {}
    if "fallbackModel" not in data:
        print("INFO (f): fallbackModel absent; check skipped")
    elif data["fallbackModel"] != registry.claude.pins.fallback:
        findings.append("(f) .claude/settings.json: fallbackModel differs from registry")
    if sites.codex_config is not None:
        config = tomllib.loads((root / ".codex/config.toml").read_text())
        findings.extend(
            f"(k) .codex/config.toml: key not allowed: {key}"
            for key in sorted(_leaf_keys(config) - set(sites.codex_config))
        )
    return findings


def _file_findings(root: Path, name: str, sites: SitesConfig, registry: Registry) -> list[str]:
    if _matches(name, sites.exempt) and not _matches(name, sites.owned + sites.derived):
        return []
    try:
        source = (root / name).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []  # Binary artifacts cannot contain textual pin declarations.
    text = active_text(source)
    findings = _slug_findings(name, text, sites, registry)
    if _matches(name, sites.owned):
        if render(name, source, sites, registry) != source:
            findings.append(f"(a) {name}: differs from models-apply render")
        findings.extend(_argv_findings(name, text, sites))
    if _matches(name, sites.owned + sites.derived):
        findings.extend(
            f"(j) {name}: --strict-config missing: {command}"
            for command, inline in _commands(text, name=name)
            if _strict_needed(command, inline=inline)
        )
    if fnmatch.fnmatchcase(name, ".codex/agents/*.toml"):
        findings.extend(_pair_findings(name, source, registry))
    return findings


def check_pin_sites(root: Path, sites: SitesConfig, registry: Registry) -> list[str]:
    """Check all eleven offline classes; no feed, trust read or mirror subprocess."""
    names = models.tracked_files(root)
    findings = []
    for name in names:
        findings.extend(_file_findings(root, name, sites, registry))
    findings.extend(
        f"(b) argv glob does not resolve: {site.glob}"
        for site in sites.argv_sites
        if not any(fnmatch.fnmatchcase(name, site.glob) for name in names)
    )
    findings.extend(check_aliases_only(root, sites))
    findings.extend(_settings_findings(root, sites, registry))
    for name, content in plugin_bytes().items():
        path = root / _PLUGIN / name
        if not path.is_file() or path.read_bytes() != content:
            findings.append(f"(g) {_PLUGIN / name}: differs from package source")
    return findings


@dataclass
class ApplyResult:
    """Retain changed paths and each post-apply task's actual return code."""

    changed: list[str] = field(default_factory=list)
    post_rcs: dict[str, int] = field(default_factory=dict)


def apply(root: Path, sites: SitesConfig, registry: Registry) -> ApplyResult:
    """Render tracked owned files, then local mirrors in their authored order."""
    result = ApplyResult()
    for name in models.tracked_files(root):
        if not _matches(name, sites.owned):
            continue
        path = root / name
        source = path.read_text(encoding="utf-8")
        rendered = render(name, source, sites, registry)
        if rendered != source:
            path.write_text(rendered, encoding="utf-8")
            result.changed.append(name)
    for name, content in plugin_bytes().items():
        path = root / _PLUGIN / name
        if not path.is_file() or path.read_bytes() != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            result.changed.append(str(_PLUGIN / name))
    for task in sites.post_apply:
        child = subprocess.run(["mise", "run", task], cwd=root, check=False)
        result.post_rcs[task] = child.returncode
        if child.returncode:
            break
    return result


def main(root: Path, argv: list[str]) -> int:
    """Shared deterministic apply/check CLI; overrides never read live catalogs."""
    parser = argparse.ArgumentParser(prog="kb-setup models apply")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--sites", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        sites = load_sites(root / args.sites)
        registry = models.load_registry()
        if args.check:
            findings = check_pin_sites(root, sites, registry)
            for finding in findings:
                print(finding)
            return int(bool(findings))
        result = apply(root, sites, registry)
        for name in result.changed:
            print(f"models-apply: {name}")
        for task, rc in result.post_rcs.items():
            print(f"models-apply: post_apply {task}: rc={rc}")
        return int(any(result.post_rcs.values()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"(h) models-apply load/check failure: {exc}")
        return 1
