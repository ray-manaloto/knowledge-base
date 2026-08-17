# Copyright (c) 2026 Raymond Manaloto
"""Resolve a Claude model's output ceiling instead of hardcoding it.

`graphify_semantic_slice.CORPUS_PROFILE` carried `max_output_tokens = "8192"` as
a literal. Against a **measured 31,887-token need** that truncated every corpus
extraction before a single chunk finished, and the API said so in its own words:

    Claude's response exceeded the 8192 output token maximum.

The number was never the model's. Claude Opus 5's real ceiling is **128,000**
output tokens. A literal cannot know that, cannot follow a model change, and
goes stale silently — the same failure this repo already measured on graphify's
version string, where `0.9.31` has 332 hits against the live pin's 161
(`docs/direction/2026-08-17-ray-directives.md` §3).

## Three sources, in order

**1. Models API `GET /v1/models/{id}`**, through the official `anthropic` SDK —
authoritative typed JSON, and it *is* the runtime, so it cannot be stale. It is
also the only source that reports `max_input_tokens` and the RESOLVED id behind
an alias (`claude-haiku-4-5` -> `claude-haiku-4-5-20251001`).

A **subscription-minted `CLAUDE_CODE_OAUTH_TOKEN`** (from `claude setup-token`)
authorizes it — verified 2026-08-17: a real model returned 200 while a bogus
model id returned 404, so the probe discriminates. Recorded because an earlier
run of the same probe returned **401 for both** and was read as "this credential
type cannot reach the endpoint". That was wrong: the token had a typo. A
malformed credential and an unauthorized one are indistinguishable from outside,
and only the 404 settles it.

**2. Docs `.md`** — credential-free, for hosts with no token (HTTP 200; a bogus
path returns 404, so the probe discriminates). But the table is **transposed** —
models are columns, `Max output` is a row — so the parse is column-positional
and breaks if the layout moves.

**3. Committed snapshot** — offline, reproducible, diffable in review. But it is
a *record of a past observation*, only as current as its last write.

The order is authoritative → live → recorded. Each step down trades currency for
availability, and the resolved value carries which one answered, so a caller can
tell "the runtime told us" from "a file remembers".

**There is no fourth step, and specifically no literal.** When all three yield
nothing this module raises. A hardcoded default here would be the exact defect
it exists to remove — and a wrong ceiling is worse than none, because a too-low
one truncates a paid call while a too-high one removes the only bound on a
runaway generation.

## The parse fails loudly, by construction

A column-positional parse of someone else's table is a probe with a spelling
bound (`.claude/rules/probes-need-a-control-arm.md` rule 3). If the docs
re-order their columns, a lenient parse returns *a* number for *a* model —
plausibly the wrong one, and nothing downstream could tell. So the structure is
validated before any value is read: the header row must open with `Feature`, the
alias and max-output rows must both exist, and all three must have the same cell
count. Any mismatch raises `LayoutChangedError` rather than returning a guess.

`max_input_tokens` is deliberately **optional**. Its cell is wrapped in
`<Tooltip …>` markup a plain table parse cannot read, and inventing a value
would smuggle a guess into a module whose point is refusing to guess. It
resolves to `None` — the third state, not a zero.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

DOCS_URL = "https://platform.claude.com/docs/en/about-claude/models/overview.md"
"""The credential-free source. Verified 2026-08-17: HTTP 200, 28,879 bytes."""

SNAPSHOT_PATH = Path("docs/model-limits/snapshot.json")
"""Committed record, relative to the repo root. Written by ``--write``."""

_FETCH_TIMEOUT_SECONDS = 30

_HEADER_LABEL = "Feature"
_ALIAS_LABEL = "Claude API alias"
_MAX_OUTPUT_LABEL = "Max output"

# "128k tokens" / "64K tokens" / "1M tokens". The unit is required: a bare
# integer here would mean the cell changed meaning, which is a layout change and
# not a number to trust.
_TOKENS_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([kKmM])\s*tokens?$")
_UNIT_SCALE = {"k": 1_000, "m": 1_000_000}
_MIN_TABLE_COLUMNS = 2
# `| a | b |` splits to 4 parts, two of them the empty outer edges. Fewer than
# that is not a pipe-delimited row at all.
_MIN_SPLIT_PARTS = 3


class LayoutChangedError(Exception):
    """The upstream table no longer has the shape this parser validated.

    Raised instead of returning a value, because a column-positional parse that
    keeps going after the columns moved reports a confident wrong number.
    """


class UnresolvableError(Exception):
    """No source could answer. Deliberately fatal — see the module docstring."""


class ModelLimits(msgspec.Struct, frozen=True):
    """One model's ceilings, and which source said so."""

    model: str
    max_output_tokens: int
    source: str
    max_input_tokens: int | None = None


def _strip_cell(cell: str) -> str:
    """Drop markdown emphasis and whitespace from one table cell."""
    return cell.strip().strip("*").strip()


def _split_row(line: str) -> list[str]:
    """Split a markdown table row into cells, dropping the outer pipes."""
    cells = line.split("|")
    if len(cells) >= _MIN_SPLIT_PARTS and not cells[0].strip() and not cells[-1].strip():
        cells = cells[1:-1]
    return [_strip_cell(cell) for cell in cells]


def parse_tokens(cell: str) -> int:
    """Turn a ``128k tokens`` cell into ``128000``.

    Raises `LayoutChangedError` on anything else, including a bare integer — the
    unit is what proves this is still the cell the parser thinks it is.
    """
    match = _TOKENS_RE.match(cell.strip())
    if match is None:
        raise LayoutChangedError(f"cell is not a token count: {cell!r}")
    amount, unit = match.groups()
    return int(float(amount) * _UNIT_SCALE[unit.lower()])


def _find_rows(markdown: str) -> tuple[list[str], list[str], list[str]]:
    """Locate the three load-bearing rows, or raise naming the missing one."""
    found: dict[str, list[str]] = {}
    for line in markdown.splitlines():
        if "|" not in line:
            continue
        cells = _split_row(line)
        if not cells:
            continue
        label = cells[0]
        if label == _HEADER_LABEL and _HEADER_LABEL not in found:
            found[_HEADER_LABEL] = cells
        elif _HEADER_LABEL in found and label in {_ALIAS_LABEL, _MAX_OUTPUT_LABEL}:
            found.setdefault(label, cells)
    for label in (_HEADER_LABEL, _ALIAS_LABEL, _MAX_OUTPUT_LABEL):
        if label not in found:
            raise LayoutChangedError(f"no {label!r} row in the comparison table")
    return found[_HEADER_LABEL], found[_ALIAS_LABEL], found[_MAX_OUTPUT_LABEL]


def _validate_shape(header: list[str], aliases: list[str], max_output: list[str]) -> None:
    """Refuse to zip rows that cannot correspond column-for-column."""
    widths = {len(header), len(aliases), len(max_output)}
    if len(widths) != 1:
        raise LayoutChangedError(
            f"row widths disagree: header={len(header)} "
            f"alias={len(aliases)} max_output={len(max_output)}"
        )
    if len(header) < _MIN_TABLE_COLUMNS:
        raise LayoutChangedError(f"table has no model columns: {header!r}")


def parse_docs_table(markdown: str) -> dict[str, ModelLimits]:
    """Read the transposed comparison table into per-alias limits."""
    header, aliases, max_output = _find_rows(markdown)
    _validate_shape(header, aliases, max_output)

    limits: dict[str, ModelLimits] = {}
    for alias, cell in zip(aliases[1:], max_output[1:], strict=True):
        if not alias:
            raise LayoutChangedError("an alias column is empty")
        limits[alias] = ModelLimits(
            model=alias,
            max_output_tokens=parse_tokens(cell),
            source="docs",
        )
    return limits


def _read_url(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kb-setup/model-limits"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_docs(
    *,
    url: str = DOCS_URL,
    opener: Callable[[str, int], bytes] | None = None,
) -> dict[str, ModelLimits] | None:
    """Fetch and parse the live docs table. ``None`` when unreachable.

    Unreachable is not the same as wrong: a network failure returns ``None`` so
    the chain falls through to the snapshot, while a reachable page whose layout
    moved raises `LayoutChangedError` and stops everything. Keeping those two
    apart is the point (`.claude/rules/persistence-gate-retry.md`).
    """
    read = opener if opener is not None else _read_url
    try:
        body = read(url, _FETCH_TIMEOUT_SECONDS)
    except urllib.error.URLError, TimeoutError, OSError:
        return None
    return parse_docs_table(body.decode("utf-8", errors="replace"))


def read_snapshot(repo_root: Path) -> dict[str, ModelLimits] | None:
    """Read the committed snapshot. ``None`` when it does not exist yet."""
    path = repo_root / SNAPSHOT_PATH
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    models = payload.get("models")
    if not isinstance(models, dict) or not models:
        raise LayoutChangedError(f"{SNAPSHOT_PATH} has no usable 'models' mapping")
    # `resolved_id` round-trips into `model`; without that a re-read would
    # report `resolved_id claude-haiku-4-5-20251001 -> claude-haiku-4-5` as a
    # change on every write — a delta that cries wolf gets ignored.
    return {
        alias: ModelLimits(
            model=str(entry.get("resolved_id", alias)),
            max_output_tokens=int(entry["max_output_tokens"]),
            source="snapshot",
            max_input_tokens=entry.get("max_input_tokens"),
        )
        for alias, entry in models.items()
    }


DEFAULT_ALIASES = ("claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-fable-5")
"""Asked of the Models API when the caller names none.

The endpoint answers per-id, so something has to supply the list. Reading it off
the docs first would defeat the point of preferring the API, so this is a
literal — and it is one the module can afford, because it names *which questions
to ask*, never an answer. A model missing from here is absent from the result,
which the chain then reports rather than inventing.
"""

_OAUTH_BETA_HEADER = "oauth-2025-04-20"
"""Required alongside a `Bearer` token; an API key does not need it.

Sending it unconditionally is harmless and keeps one code path.
"""


def _requested_aliases(environment: Mapping[str, str]) -> tuple[str, ...]:
    """Which aliases to ask about — `KB_MODEL_LIMITS_ALIASES`, else the default set."""
    raw = environment.get("KB_MODEL_LIMITS_ALIASES", "")
    named = tuple(alias.strip() for alias in raw.split(",") if alias.strip())
    return named or DEFAULT_ALIASES


def _sdk_caller(token: str) -> Callable[[str], object]:
    """Bind the official SDK's `models.retrieve` to one credential.

    The SDK rather than hand-rolled HTTP because it is the vendor's own typed
    client for this endpoint (`use-tool-builtins.md`): `ModelInfo` already
    carries `max_tokens`, `max_input_tokens` and `capabilities`, so the only
    thing left to write is which models to ask about.
    """
    import anthropic

    client = anthropic.Anthropic(
        auth_token=token,
        default_headers={"anthropic-beta": _OAUTH_BETA_HEADER},
    )
    return client.models.retrieve


def fetch_models_api(
    environment: Mapping[str, str],
    *,
    caller: Callable[[str], object] | None = None,
) -> dict[str, ModelLimits] | None:
    """The authoritative source, when a credential exists.

    Returns ``None`` — never raises — when no credential is present or the call
    fails, because an absent or rejected credential must fall through to the
    docs rather than failing the run.

    **A subscription-minted `CLAUDE_CODE_OAUTH_TOKEN` does authorize this
    endpoint** — verified 2026-08-17: `GET /v1/models/claude-opus-5` → 200 while
    a bogus model id → 404, so the probe discriminates. An earlier run of the
    same probe returned 401 for *both*, which read as "this credential type is
    not authorized" and was wrong: the token had a typo. A malformed credential
    and an unauthorized one are indistinguishable from the outside, and only the
    404 settles it.
    """
    token = (
        environment.get("ANTHROPIC_API_KEY")
        or environment.get("ANTHROPIC_AUTH_TOKEN")
        or environment.get("CLAUDE_CODE_OAUTH_TOKEN")
    )
    if not token:
        return None
    retrieve = caller if caller is not None else _sdk_caller(token)
    limits: dict[str, ModelLimits] = {}
    for alias in _requested_aliases(environment):
        try:
            info = retrieve(alias)
        except Exception:
            # Any SDK failure — auth, network, an unknown id — falls through to
            # the docs. Narrowing this would turn a transient into a hard stop
            # for a resolver whose whole design is layered fallback.
            return None
        max_output = getattr(info, "max_tokens", None)
        if not isinstance(max_output, int):
            continue
        max_input = getattr(info, "max_input_tokens", None)
        # `id` is the RESOLVED id, which differs from the alias for dated
        # snapshots (`claude-haiku-4-5` -> `claude-haiku-4-5-20251001`). Key by
        # the alias the caller asked for, and record the resolution.
        limits[alias] = ModelLimits(
            model=str(getattr(info, "id", alias)),
            max_output_tokens=max_output,
            source="models-api",
            max_input_tokens=max_input if isinstance(max_input, int) else None,
        )
    return limits or None


def resolve_all(
    repo_root: Path,
    environment: Mapping[str, str],
    *,
    sources: Sequence[Callable[[], dict[str, ModelLimits] | None]] | None = None,
) -> dict[str, ModelLimits]:
    """Walk the chain and return the first source that answered.

    `sources` is injectable so a test can drive every branch without a network
    call — the shape `skill_lint.check(root, *, decide)` already uses.
    """
    chain = sources
    if chain is None:
        chain = (
            lambda: fetch_models_api(environment),
            fetch_docs,
            lambda: read_snapshot(repo_root),
        )
    for source in chain:
        limits = source()
        if limits:
            return limits
    raise UnresolvableError(
        "no source could report model limits: the Models API needs a credential, "
        f"{DOCS_URL} was unreachable, and {SNAPSHOT_PATH} is absent or empty. "
        "Refusing to fall back to a literal."
    )


def resolve(
    model: str,
    repo_root: Path,
    environment: Mapping[str, str],
    *,
    sources: Sequence[Callable[[], dict[str, ModelLimits] | None]] | None = None,
) -> ModelLimits:
    """Resolve one model, failing closed when the chain cannot name it."""
    limits = resolve_all(repo_root, environment, sources=sources)
    found = limits.get(model)
    if found is None:
        known = ", ".join(sorted(limits)) or "nothing"
        raise UnresolvableError(f"{model!r} is not in the resolved set (knows: {known})")
    return found


def _snapshot_entry(alias: str, entry: ModelLimits) -> dict[str, int | str]:
    """Serialise one model, omitting fields the answering source could not know.

    `resolved_id` is written only when it differs from the alias, because only
    the Models API can report it (`claude-haiku-4-5` -> the dated snapshot) and
    writing `alias == alias` for every docs-sourced entry would be noise that
    later reads as a fact the docs supplied.
    """
    payload: dict[str, int | str] = {"max_output_tokens": entry.max_output_tokens}
    if entry.max_input_tokens is not None:
        payload["max_input_tokens"] = entry.max_input_tokens
    if entry.model != alias:
        payload["resolved_id"] = entry.model
    return payload


def write_snapshot(repo_root: Path, limits: Mapping[str, ModelLimits], observed_at: str) -> str:
    """Record the resolved set, returning the human-readable delta.

    The delta is the point, not the file: a snapshot nobody compares against is
    a number that ages silently, which is the defect this module exists to fix
    one layer up. `observed_at` is a parameter rather than a clock read, so the
    caller owns the timestamp and a test can pin it.
    """
    previous = read_snapshot(repo_root) or {}
    path = repo_root / SNAPSHOT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "observed_at": observed_at,
        "source": next(iter(limits.values())).source,
        "models": {alias: _snapshot_entry(alias, entry) for alias, entry in sorted(limits.items())},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return _render_delta(previous, limits)


def _changed_fields(old: ModelLimits, new: ModelLimits) -> list[str]:
    """Every recorded field that moved, not just the output ceiling.

    Reporting only `max_output_tokens` was this function's own first defect: the
    switch from the docs to the Models API filled in `max_input_tokens` on all
    four models and the delta printed *(no change)*. A record whose diff cannot
    see a change is the silent-ageing failure this module exists to prevent, one
    level down.
    """
    changes: list[str] = []
    if old.max_output_tokens != new.max_output_tokens:
        changes.append(f"max_output {old.max_output_tokens} -> {new.max_output_tokens}")
    if old.max_input_tokens != new.max_input_tokens:
        changes.append(f"max_input {old.max_input_tokens} -> {new.max_input_tokens}")
    if old.model != new.model:
        changes.append(f"resolved_id {old.model} -> {new.model}")
    return changes


def _render_delta(before: Mapping[str, ModelLimits], after: Mapping[str, ModelLimits]) -> str:
    """One line per model that appeared, vanished, or moved in any field."""
    lines: list[str] = []
    for alias in sorted(set(before) | set(after)):
        old = before.get(alias)
        new = after.get(alias)
        if old is None and new is not None:
            lines.append(f"  + {alias}: max_output {new.max_output_tokens}")
        elif new is None and old is not None:
            lines.append(f"  - {alias}: was max_output {old.max_output_tokens}")
        elif old is not None and new is not None:
            changes = _changed_fields(old, new)
            if changes:
                lines.append(f"  ~ {alias}: {', '.join(changes)}")
    return "\n".join(lines) if lines else "  (no change)"


class _Request(msgspec.Struct, frozen=True):
    """A parsed command line, or the message explaining why it is not one."""

    write: bool = False
    observed_at: str = ""
    wanted: tuple[str, ...] = ()
    error: str = ""


def _parse_argv(argv: Sequence[str]) -> _Request:
    """Split the flags from the model names, failing on anything unrecognised."""
    args = list(argv)
    write = "--write" in args
    if write:
        args.remove("--write")
    observed_at = ""
    if "--observed-at" in args:
        index = args.index("--observed-at")
        if index + 1 >= len(args):
            return _Request(error="--observed-at needs a value")
        observed_at = args[index + 1]
        del args[index : index + 2]
    unknown = [arg for arg in args if arg.startswith("-")]
    if unknown:
        return _Request(error=f"unknown flag(s): {', '.join(unknown)}")
    if write and not observed_at:
        return _Request(error="--write needs --observed-at DATE")
    return _Request(write=write, observed_at=observed_at, wanted=tuple(args))


def main(repo_root: Path, argv: Sequence[str], environment: Mapping[str, str]) -> int:
    """`kb-setup model-limits [--write] [--observed-at DATE] [model...]`.

    Reports on content and exits `BAD_REQUEST` on a malformed ask — the shape
    `kb-skill-score` established, where a name matching nothing exits 2 rather
    than reporting an empty corpus as clean.
    """
    from kb_setup.result import Rc

    request = _parse_argv(argv)
    if request.error:
        print(f"model-limits: {request.error}")
        return int(Rc.BAD_REQUEST)

    try:
        limits = resolve_all(repo_root, environment)
    except (UnresolvableError, LayoutChangedError) as exc:
        print(f"model-limits: {exc}")
        return int(Rc.NOT_RUN)

    if request.wanted:
        missing = [alias for alias in request.wanted if alias not in limits]
        if missing:
            known = ", ".join(sorted(limits))
            print(f"model-limits: unknown model(s): {', '.join(missing)} (knows: {known})")
            return int(Rc.BAD_REQUEST)
        limits = {alias: limits[alias] for alias in request.wanted}

    source = next(iter(limits.values())).source
    print(f"model-limits: {len(limits)} model(s), source={source}")
    for alias, entry in sorted(limits.items()):
        context = "unknown" if entry.max_input_tokens is None else str(entry.max_input_tokens)
        print(f"  {alias:<20} max_output={entry.max_output_tokens:>7}  max_input={context}")

    if request.write:
        print(f"\nsnapshot delta ({SNAPSHOT_PATH}):")
        print(write_snapshot(repo_root, limits, request.observed_at))
    return int(Rc.OK)
