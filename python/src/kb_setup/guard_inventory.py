# Copyright (c) 2026 Raymond Manaloto
"""`kb-guard-inventory-check` — reconcile the G00 inventory against live state.

WHY THIS EXISTS, measured rather than argued. The function-hooks programme
(#766, tickets G00-G12) rests on an inventory of this repo's enforcement
surface. The report that preceded it derived its guard-module list from::

    ls python/src/kb_setup/ | grep -Ei 'guard|hook|check_first|absent|stage|instruction'

That bounds the NAME. Four guard modules contain none of those tokens --
``graph_first``, ``destructive_git``, ``codex_lane``, ``inplace_edit`` -- and
were invisible to it while reachable from ``hook_guard``; ``graph_first.py`` had
been there for a month. The
report published **7 modules / 2,859 lines**; the true figures are **11 /
4,024**. It was wrong when written, not stale.

Prose cannot be reconciled against a repo, so it drifts that way. This module is
what makes the inventory answerable.

THE MEMBERSHIP RULE IS REACHABILITY, and that is the whole design decision.
Both obvious shortcuts were probed and both are wrong:

* **filename pattern** -> 7. Misses the four above. This is the defect itself.
* **entry-point name** (``git grep -ln '^def decide'``) -> 10, wrong in BOTH
  directions: it admits ``currency/decide.py`` (the currency engine's six-gate
  bar, not a guard) and misses ``instruction_edit_guard`` /
  ``instruction_shell_write``, whose entry points are ``evaluate``/``render``/
  ``main``.

So a guard module is *a module a hook registration reaches, directly or through*
``hook_guard``'s *imports at any depth*. Only that makes the FAIL arm real: a new
guard must redden the gate, and neither shortcut can see one.

NO COUNT IS EVER COMPARED AGAINST A STORED COUNT. Line counts, effective-case
sets and invariant digests are re-derived on every run and checked against the
reviewed values. A stored census drifts in lockstep with itself and reads green
forever -- the failure ``kb_setup.currency.views`` was built to escape.

EXPLICITLY OUT OF SCOPE -- a check that does not declare its blind spot gets read
as covering everything:

1. **Whether a disposition is CORRECT.** This reconciles against what EXISTS. A
   wrong disposition passes every check here.
2. **Whether a guard WORKS.** Reachability is structural: a module can be
   reached, inventoried, and deny nothing.
3. **A registration's STATE past ``enabled``.** ``declared`` and ``enabled`` are
   determined statically here. ``installed`` and ``exercised`` cannot be: since
   v2.1.195 a project-enabled external plugin needs a per-machine
   ``claude plugin install``, and only a dispatched lane can observe a hook
   actually firing. Both belong to G04 (#757), and the reconciler REJECTS an
   inventory row claiming either.
4. **Invariant coverage.** An invariant with no enforcing module is DATA, never
   a failure: it is the programme's target list, and failing on it would redden
   the gate for the exact condition the programme exists to fix.
5. **A guard module that no registration reaches.** Unreachable-by-construction
   is a claim needing its own arm; this enumerates from registrations outward,
   so a module reached by nothing is invisible here BY DESIGN.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path

import msgspec

from kb_setup.generated.guard_inventory import (
    CurrentSurface,
    Disposition,
    GuardInventory,
    OwnerKind,
    Registration,
    RegistrationState,
)
from kb_setup.result import Rc

DEFAULT_INVENTORY_PATH = Path("docs/guards/inventory.toml")
SETTINGS_PATH = Path(".claude/settings.json")
GUARD_DIR = Path("python/src/kb_setup")
DO_NOT_PATH = Path(".claude/rules/do-not.md")

_ANCHOR = re.compile(r"^<!-- guard-programme: (?P<id>\S+) -->$")
_NUMBERED = re.compile(r"^(?P<n>\d+)\. \*\*")
_IF_CONDITION = re.compile(r"^(?P<tool>\w+)\((?P<scope>.+)\)$")


class GuardInventoryError(ValueError):
    """The inventory document violates its structural or semantic contract."""


@dataclass(frozen=True)
class Finding:
    """One typed reconciliation disagreement.

    The verdict vocabulary is deliberately narrow and each value names a
    DIFFERENT failure, because an arm that asserts only "nonzero" passes when
    the gate dies for an unrelated reason.
    """

    verdict: str
    subject: str
    detail: str


def load_inventory(path: Path) -> GuardInventory:
    """Decode and strictly validate the inventory TOML.

    Decoding through the generated msgspec model is what makes an unrecognised
    ``disposition`` a hard error rather than a silently-dropped row. Not
    hypothetical: this repo typed a closed set as a bare ``str`` once, its
    consumer dispatched with ``if``s and no ``else``, and an unrecognised value
    was dropped while the entry still looked reviewed -- two ``kb-build`` runs.
    """
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"inventory unreadable: {path}"
        raise GuardInventoryError(msg) from exc
    except tomllib.TOMLDecodeError as exc:
        msg = f"inventory is not valid TOML: {exc}"
        raise GuardInventoryError(msg) from exc
    try:
        return msgspec.convert(raw, GuardInventory, strict=True)
    except msgspec.ValidationError as exc:
        msg = f"inventory does not satisfy guard-inventory.schema.json: {exc}"
        raise GuardInventoryError(msg) from exc


#: Calls this walk treats as UNSUPPORTED INDIRECTION -- a dynamic import this
#: static AST walk cannot see past. Detecting one fails the whole enumeration
#: CLOSED (empty -> NOT_RUN upstream) rather than silently returning a set that
#: omits whatever the indirection hides.
_DYNAMIC_IMPORT_CALL_NAMES = frozenset({"__import__"})


def _dynamic_import_local_names(tree: ast.AST) -> frozenset[str]:
    """Local names bound to `importlib.import_module`, ALIASES INCLUDED.

    `from importlib import import_module as load` binds the dynamic importer to
    `load`, so a later `load("kb_setup.x")` is an `ast.Name` call the
    attribute-and-builtin checks below never see. That alias form is the common
    one, and a cold review measured it slipping past the backstop while the
    accompanying static import was still returned -- a silently short set rather
    than NOT_RUN, which is the precise failure the backstop exists to prevent.

    Scoped to `importlib` on purpose: an unrelated local called `load` is not
    evidence of indirection, and widening this to any short name would redden
    the gate on ordinary code.
    """
    # Named `aliases`, not `names`: a second `names: set[str] = set()` in this
    # file made the A0 control and the A2 reachability arm ambiguous, and
    # `kb-arms` refused both as PROBE BROKEN rather than mutating the wrong
    # occurrence. The reachability loop owns that spelling.
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "import_module"
            )
    return frozenset(aliases)


def _has_unsupported_indirection(tree: ast.AST) -> bool:
    """True when `hook_guard.py` reaches a guard through unsupported indirection.

    `importlib.import_module(...)` under any binding, `__import__(...)`, or a
    `getattr(...)` call whose target names `kb_setup`. None of these are used by
    `hook_guard.py` today -- this is a fail-closed backstop, not a reachability
    source in its own right.
    """
    aliased = _dynamic_import_local_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _DYNAMIC_IMPORT_CALL_NAMES | aliased:
            return True
        if isinstance(func, ast.Attribute) and func.attr == "import_module":
            return True
        if isinstance(func, ast.Name) and func.id == "getattr" and node.args:
            try:
                target_src = ast.unparse(node.args[0])
            except ValueError, TypeError:
                target_src = ""
            if "kb_setup" in target_src:
                return True
    return False


def dispatched_module_names(root: Path) -> frozenset[str]:
    """Every guard module reachable from `hook_guard.py`, by AST walk at ALL depths.

    Recognises every STATIC import shape the language offers for reaching a
    sibling module in the same package: `from kb_setup import X`,
    `from kb_setup.X import y`, `import kb_setup.X`, `from . import X`, and
    `from .X import y`.

    A PRIOR version of this walk recognised only the first of those five shapes
    -- it keyed on `node.module == "kb_setup"` alone, so `import kb_setup.X`,
    `from . import X` and `from .X import y` all passed through unseen. That is
    the reachability half a filename pattern cannot reproduce either way: it is
    an AST walk rather than a regex over the dispatch tuple because `hook_guard`
    imports exactly **one** of its eight guards at module scope
    (`graph_first`, `:27`) and reaches the other seven through FUNCTION-LOCAL
    imports inside their own wrappers -- state the MECHANISM, not a quoted pair
    of counts: this docstring previously said "2 of 9", which had already
    drifted by the time it was read. `ast.walk` visits every `ImportFrom` and
    `Import` at every depth, so neither nesting nor a refactor of `hook_guard`
    can hide a guard reached through one of the five supported shapes.

    FAILS CLOSED, not silently, on detected unsupported indirection --
    `importlib.import_module`, `__import__`, or a `getattr` call naming
    `kb_setup` -- by returning EMPTY, which the caller already treats as
    NOT_RUN. A dynamic import or a re-export is out of scope for a static walk
    by construction; narrowing the claim to what this function can actually see
    is the fix, not pretending it can see further.

    Returns EMPTY when the file cannot be read or parsed, or when unsupported
    indirection is detected; the caller treats that as NOT_RUN. A parser that
    silently matches nothing would otherwise report a clean reconciliation
    against nothing at all.
    """
    try:
        source = (root / GUARD_DIR / "hook_guard.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
    except OSError, SyntaxError:
        return frozenset()
    if _has_unsupported_indirection(tree):
        return frozenset()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(_import_from_targets(node))
        elif isinstance(node, ast.Import):
            names.update(
                alias.name.split(".")[1]
                for alias in node.names
                if alias.name.startswith("kb_setup.")
            )
    return frozenset(names & _module_stems(root))


def _import_from_targets(node: ast.ImportFrom) -> set[str]:
    """The sibling-module name(s) one `ImportFrom` node reaches, if any.

    Split out of `dispatched_module_names` purely to keep that walk's own
    branching within this repo's complexity budget. Covers four of the five
    shapes that function documents; the fifth, plain `import kb_setup.X`, is an
    `ast.Import` and handled by the caller.
    """
    if node.level == 0 and node.module == "kb_setup":
        return {alias.name for alias in node.names}
    if node.level == 0 and node.module is not None and node.module.startswith("kb_setup."):
        return {node.module.split(".")[1]}
    if node.level == 1 and node.module is None:
        return {alias.name for alias in node.names}
    if node.level == 1 and node.module is not None:
        return {node.module.split(".")[0]}
    return set()


def _module_stems(root: Path) -> frozenset[str]:
    """Module stems that exist in the package.

    Intersecting with this keeps a `from kb_setup import <helper>` that is not a
    module (or a module that has since been deleted) out of the reachable set,
    without reintroducing a NAME pattern: membership here is "the file exists",
    never "the file is called something guard-ish".
    """
    return frozenset(p.stem for p in (root / GUARD_DIR).glob("*.py"))


def live_registrations(root: Path) -> list[dict[str, object]] | None:
    """Every classic registration, as identity dicts. None when unreadable."""
    try:
        settings = json.loads((root / SETTINGS_PATH).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    return [
        {
            "event": event,
            "matcher": group.get("matcher") or "",
            "if_condition": hook.get("if") or "",
            "command": hook.get("command") or "",
            "timeout": hook.get("timeout"),
        }
        for event, groups in settings.get("hooks", {}).items()
        for group in groups
        for hook in group.get("hooks", [])
    ]


def expand_scope_cases(matcher: str, if_condition: str) -> list[tuple[str, str]] | None:
    """Derive the EFFECTIVE enforcement cases for one registration.

    This is the real coverage denominator: 18 registrations expand to 28
    effective cases, so a migration graded against 18 can drop 10 and read
    complete. An `if` refines the matcher to exactly one tool; a bare matcher
    contributes one case per alternative; no matcher is an explicit wildcard.

    Returns None for an `if` this cannot parse -- UNINTERPRETABLE SCOPE, which
    the caller reports rather than silently widening.
    """
    if if_condition:
        parsed = _IF_CONDITION.match(if_condition)
        if parsed is None:
            return None
        return [(parsed.group("tool"), parsed.group("scope"))]
    if matcher:
        return [(alt, "") for alt in matcher.split("|")]
    return [("*", "")]


def invariant_digests(root: Path) -> dict[str, tuple[int | None, str]] | None:
    """Anchor -> (ordinal, digest), parsed from `do-not.md`'s own anchors.

    The three-part identity is what makes renumbering detectable: the ANCHOR is
    semantic identity and survives both renumbering and rewording; the ORDINAL is
    compared separately, so 7 -> 8 reports LOCATOR_DRIFT rather than silently
    stealing #8's disposition; the DIGEST forces re-review when meaning changes.
    """
    try:
        lines = (root / DO_NOT_PATH).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    out: dict[str, tuple[int | None, str]] = {}
    current: str | None = None
    ordinal: int | None = None
    buf: list[str] = []

    def flush() -> None:
        if current is not None:
            body = re.sub(r"\s+", " ", "\n".join(buf).strip())
            out[current] = (ordinal, hashlib.sha256(body.encode()).hexdigest()[:16])

    for line in lines:
        anchor = _ANCHOR.match(line)
        if anchor:
            flush()
            current, buf, ordinal = anchor.group("id"), [], None
            continue
        if current is None:
            continue
        if ordinal is None and (numbered := _NUMBERED.match(line)):
            ordinal = int(numbered.group("n"))
        buf.append(line)
    flush()
    return out


def _registration_key(source: object) -> tuple[str, str, str, str]:
    """Identity tuple. `timeout` is EXCLUDED deliberately.

    Folding a timeout into identity makes a timeout change fabricate an ORPHAN
    plus an UNCLASSIFIED for what is one hook; it is compared as a reviewed
    ATTRIBUTE instead.
    """
    return (
        str(getattr(source, "event", "") or ""),
        str(getattr(source, "matcher", "") or ""),
        str(getattr(source, "if_condition", "") or ""),
        str(getattr(source, "command", "") or ""),
    )


def _reconcile_registrations(
    inventory: GuardInventory, live: list[dict[str, object]]
) -> list[Finding]:
    findings: list[Finding] = []
    classic = [r for r in inventory.registrations if r.source.path == str(SETTINGS_PATH)]

    reviewed: dict[tuple[str, str, str, str], list[Registration]] = {}
    for row in classic:
        reviewed.setdefault(_registration_key(row.source), []).append(row)
    for key, rows in reviewed.items():
        if len(rows) > 1:
            findings.append(
                Finding(
                    "AMBIGUOUS_IDENTITY",
                    ", ".join(r.id for r in rows),
                    f"{len(rows)} rows share identity {key}; ambiguous, never deduplicated",
                )
            )

    live_keys: dict[tuple[str, str, str, str], int] = {}
    for entry in live:
        key = (
            str(entry["event"]),
            str(entry["matcher"]),
            str(entry["if_condition"]),
            str(entry["command"]),
        )
        live_keys[key] = live_keys.get(key, 0) + 1

    for key, count in live_keys.items():
        if key not in reviewed:
            findings.append(
                Finding("UNCLASSIFIED", f"{key[0]} {key[1]} {key[2]}".strip(), key[3][:70])
            )
        elif count > 1:
            findings.append(
                Finding("AMBIGUOUS_IDENTITY", key[3][:70], f"{count} live hooks share one identity")
            )
    for key, rows in reviewed.items():
        if key not in live_keys:
            findings.append(
                Finding("ORPHAN", rows[0].id, "no live registration matches this identity")
            )

    findings.extend(_reconcile_scope_and_attributes(classic, live, reviewed))
    return findings


def _reconcile_scope_and_attributes(
    classic: list[Registration],
    live: list[dict[str, object]],
    reviewed: dict[tuple[str, str, str, str], list[Registration]],
) -> list[Finding]:
    findings: list[Finding] = []
    for entry in live:
        key = (
            str(entry["event"]),
            str(entry["matcher"]),
            str(entry["if_condition"]),
            str(entry["command"]),
        )
        rows = reviewed.get(key)
        if not rows:
            continue
        row = rows[0]
        derived = expand_scope_cases(str(entry["matcher"]), str(entry["if_condition"]))
        if derived is None:
            findings.append(
                Finding(
                    "UNINTERPRETABLE_SCOPE",
                    row.id,
                    f"cannot parse if-condition {entry['if_condition']!r} (never widened)",
                )
            )
            continue
        recorded = {(c.tool, c.path_scope or "") for c in (row.reviewed_scope_cases or [])}
        if recorded != set(derived):
            missing = sorted(set(derived) - recorded)
            added = sorted(recorded - set(derived))
            findings.append(Finding("SCOPE_DRIFT", row.id, f"missing={missing} added={added}"))
        if row.source.reviewed_timeout_seconds != entry["timeout"]:
            findings.append(
                Finding(
                    "ATTRIBUTE_DRIFT",
                    row.id,
                    f"timeout reviewed={row.source.reviewed_timeout_seconds} "
                    f"live={entry['timeout']}",
                )
            )
    _ = classic
    return findings


#: `kb-setup <cmd>` -> the repo module stem that command drives, for the
#: commands THIS repo's own `.claude/settings.json` and `mise.toml` name today.
#: A small explicit table rather than importing `cli.py` (which has no
#: importable dispatch table -- 84 `if cmd ==` branches with its own C901 etc.
#: suppressions, `cli.py:210` -- and would run import-time side effects to
#: resolve one string). Extending this table is how a NEW direct registration
#: becomes recognised; an entry absent here is UNRESOLVED, never silently
#: treated as external.
_DIRECT_MODULE_BY_KB_SETUP_CMD: dict[str, str] = {
    "hookguard": "hook_guard",
    "instruction-edit-guard": "instruction_edit_guard",
    "instruction-shell-write": "instruction_shell_write",
}

#: mise task name -> the `kb-setup <cmd>` it runs, taken from that task's own
#: `run =` line in `mise.toml` (`kb-instruction-edit-guard` ->
#: `uv run kb-setup instruction-edit-guard`, and the shell-write sibling). A
#: task name absent here is UNRESOLVED, not external -- see
#: `_resolve_direct_command`.
_MISE_TASK_KB_SETUP_CMD: dict[str, str] = {
    "kb-instruction-edit-guard": "instruction-edit-guard",
    "kb-instruction-shell-write": "instruction-shell-write",
}

#: graphify's own binary (`do-not.md`'s `external-classic-hook` disposition):
#: recognised and skipped, never treated as a repo module and never UNRESOLVED.
_EXTERNAL_HOOK_GUARD_SUBCOMMANDS = frozenset({"read", "search"})


def _resolve_direct_command(
    command: str, mise_cmds: dict[str, str] | None = None
) -> tuple[bool, str | None]:
    """Classify one live PreToolUse command's target.

    Returns `(recognised, module_stem)`. `module_stem` is a repo module id
    (e.g. `"hook_guard"`) when the command drives one; `None` when the command
    is a recognised EXTERNAL binary (graphify's own
    `.venv/bin/graphify hook-guard read|search`), which is not a repo module by
    disposition. `recognised` is `False` for ANY command shape this resolver
    does not know -- so the caller treats it as NOT_RUN rather than silently
    classifying an unknown command as external, which is the exact over-reach
    the ticket calls out.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False, None
    if not tokens:
        return False, None
    for resolver in (_resolve_graphify_binary, _resolve_kb_setup_cmd):
        result = resolver(tokens)
        if result is not None:
            return result
    # Called apart from the chain above because it alone needs the table parsed
    # from `mise.toml`, which only the caller (holding `root`) can read.
    mise_result = _resolve_mise_task(tokens, mise_cmds)
    if mise_result is not None:
        return mise_result
    return False, None


def _resolve_graphify_binary(tokens: list[str]) -> tuple[bool, str | None] | None:
    """`.venv/bin/graphify hook-guard read|search` — external, not a repo module.

    Returns `None` (try the next resolver) when the command is not this shape
    at all; `(False, None)` when it IS this shape but names an unrecognised
    `hook-guard` subcommand — that must stay NOT_RUN, never "external".
    """
    if not tokens[0].endswith("/graphify") or tokens[1:2] != ["hook-guard"]:
        return None
    if tokens[2:3] and tokens[2] in _EXTERNAL_HOOK_GUARD_SUBCOMMANDS:
        return True, None
    return False, None


def _resolve_kb_setup_cmd(tokens: list[str]) -> tuple[bool, str | None] | None:
    """`... kb-setup <cmd>` — direct at any position, per `hook.pretool.hookguard`."""
    if "kb-setup" not in tokens:
        return None
    idx = tokens.index("kb-setup")
    cmd = tokens[idx + 1] if idx + 1 < len(tokens) else None
    module = _DIRECT_MODULE_BY_KB_SETUP_CMD.get(cmd) if cmd else None
    return (True, module) if module else (False, None)


def _mise_task_kb_setup_cmds(root: Path) -> dict[str, str] | None:
    """Each mise task's `kb-setup <cmd>`, PARSED FROM `mise.toml` itself.

    This was a hand-maintained dict duplicating two `run =` lines, and a cold
    review measured the consequence: repointing `kb-instruction-edit-guard` in
    `mise.toml` produced ZERO reads of `mise.toml` and no finding, so the real
    task-to-module route could drift while the gate reported the old route as
    live. A gate that reconciles against a copy of its authority reconciles
    against itself.

    Returns None when `mise.toml` cannot be read or parsed -- the caller turns
    that into NOT_RUN rather than an empty map, which would silently make every
    mise-driven registration unrecognised.
    """
    try:
        tasks = tomllib.loads((root / "mise.toml").read_text(encoding="utf-8"))["tasks"]
    except OSError, tomllib.TOMLDecodeError, KeyError:
        return None
    found: dict[str, str] = {}
    for name, body in tasks.items():
        run = body.get("run") if isinstance(body, dict) else body
        if not isinstance(run, str):
            continue
        try:
            tokens = shlex.split(run)
        except ValueError:
            continue
        for i, word in enumerate(tokens):
            if word == "kb-setup" and tokens[i + 1 : i + 2]:
                found[name] = tokens[i + 1]
                break
    return found


def _resolve_mise_task(
    tokens: list[str], mise_cmds: dict[str, str] | None
) -> tuple[bool, str | None] | None:
    """`mise run [-C <dir>] <task>` — resolved via the task's own `run =` line.

    `mise_cmds` is the table parsed from `mise.toml` by the caller, which holds
    the root; None means it could not be read, and every mise-driven command is
    then UNRECOGNISED rather than silently unresolved.
    """
    if tokens[:2] != ["mise", "run"]:
        return None
    if mise_cmds is None:
        return False, None
    task = _mise_task_name(tokens[2:])
    kb_cmd = mise_cmds.get(task) if task else None
    module = _DIRECT_MODULE_BY_KB_SETUP_CMD.get(kb_cmd) if kb_cmd else None
    return (True, module) if module else (False, None)


def _mise_task_name(tokens: list[str]) -> str | None:
    """The task name in a `mise run [-C <dir>] <task>` argument tail.

    Skips `-C <dir>` (the only flag-with-value this resolver's known commands
    use) and any other `-`-prefixed flag, then returns the first bare token.
    """
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-C":
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok
    return None


def _direct_targets(
    live: list[dict[str, object]], mise_cmds: dict[str, str] | None
) -> tuple[set[str], str | None]:
    """Repo modules reached by a live registration CAPABLE OF BLOCKING A CALL.

    Membership is the capability, never the event name: a registration counts
    when it can synchronously prevent a tool call. `PreToolUse` is the classic
    instance; `SessionStart`/`SessionEnd` are excluded because they cannot stop
    anything, not because of what they are called. A future event with the same
    power is a member automatically, and a future lifecycle event never is.

    Returns `(targets, unresolved_command)`. A non-None second element is a
    command shape the resolver does not know, which the caller turns into
    NOT_RUN -- never silently classified as external, which would quietly shrink
    the reachable set.
    """
    targets: set[str] = set()
    for entry in live:
        if str(entry["event"]) not in _BLOCKING_EVENTS:
            continue
        recognised, module_stem = _resolve_direct_command(str(entry["command"]), mise_cmds)
        if not recognised:
            return targets, str(entry["command"])
        if module_stem is not None:
            targets.add(module_stem)
    return targets, None


def _reconcile_modules(
    root: Path, inventory: GuardInventory, live: list[dict[str, object]]
) -> list[Finding]:
    dispatched = dispatched_module_names(root)
    if not dispatched:
        return [
            Finding(
                "NOT_RUN",
                "hook_guard dispatch tuple",
                "could not read the guard tuple — the module enumeration never ran",
            )
        ]
    mise_cmds = _mise_task_kb_setup_cmds(root)
    if mise_cmds is None:
        return [
            Finding(
                "NOT_RUN",
                "mise.toml [tasks]",
                "could not read the task table — mise-driven routes were never resolved",
            )
        ]
    direct, unresolved = _direct_targets(live, mise_cmds)
    if unresolved is not None:
        return [
            Finding(
                "NOT_RUN",
                unresolved[:70],
                "unrecognised direct-registration command shape — enumeration never ran",
            )
        ]

    reachable = dispatched | direct
    present_stems = {Path(m.path).stem for m in inventory.modules}
    findings = [
        Finding(
            "UNCLASSIFIED",
            f"{GUARD_DIR / name}.py",
            "reached live but absent from the inventory",
        )
        for name in sorted(reachable - present_stems)
    ]
    for module in inventory.modules:
        path = root / module.path
        if not path.exists():
            findings.append(Finding("ORPHAN", module.id, f"{module.path} does not exist"))
            continue
        stem = path.stem
        if module.reached_by.value == "hook-guard-dispatch" and stem not in dispatched:
            findings.append(
                Finding(
                    "ROUTE_DRIFT",
                    module.id,
                    f"claims hook-guard-dispatch; {stem} is not reached that way",
                )
            )
        if module.reached_by.value == "direct-registration" and stem not in direct:
            findings.append(
                Finding(
                    "ROUTE_DRIFT",
                    module.id,
                    f"claims direct-registration; no live registration resolves to {stem}",
                )
            )
    findings.extend(_reconcile_module_ids(root, inventory))
    return findings


def _reconcile_module_ids(root: Path, inventory: GuardInventory) -> list[Finding]:
    """`module_ids` must resolve to a real module AND cover the route reached.

    Existence alone was not enough, and the gap was measured: deleting
    `module_ids` outright from a registration left the gate clean, because a
    check that only rejects references to NONEXISTENT modules has nothing to say
    about a reference that is missing. The schema defines these ids as the
    modules a registration reaches, so an empty list on a registration that
    demonstrably reaches one is a false statement about the route, not an
    abstention.

    Only the FORWARD direction is enforced -- the resolved module must appear.
    `hook.pretool.hookguard` legitimately lists the eight modules it dispatches
    to beside its own, so requiring an exact set would redden the gate on a row
    that is correct and more informative than the rule.
    """
    known = {m.id for m in inventory.modules}
    by_path = {m.path: m.id for m in inventory.modules}
    mise_cmds = _mise_task_kb_setup_cmds(root)
    findings: list[Finding] = []
    for reg in inventory.registrations:
        ids = reg.module_ids if isinstance(reg.module_ids, list) else []
        findings.extend(
            Finding("ORPHAN", reg.id, f"module_ids references unknown module {mid}")
            for mid in ids
            if mid not in known
        )
        recognised, stem = _resolve_direct_command(
            str(getattr(reg.source, "command", "") or ""), mise_cmds
        )
        # `(False, _)` is an unrecognised shape, already NOT_RUN upstream; a
        # recognised external binary yields `(True, None)` and owns no module.
        if not recognised or stem is None:
            continue
        expected = by_path.get(f"{GUARD_DIR}/{stem}.py")
        if expected is not None and expected not in ids:
            findings.append(
                Finding(
                    "ROUTE_DRIFT",
                    reg.id,
                    f"reaches {expected} but module_ids does not list it",
                )
            )
    return findings


def _reconcile_invariants(root: Path, inventory: GuardInventory) -> list[Finding]:
    findings: list[Finding] = []
    live = invariant_digests(root)
    if not live:
        return [Finding("NOT_RUN", str(DO_NOT_PATH), "parsed zero anchors — enumeration never ran")]
    reviewed = {i.locator.anchor: i for i in inventory.invariants}
    findings.extend(
        Finding("UNCLASSIFIED", anchor, "anchored in do-not.md, absent here")
        for anchor in sorted(live.keys() - reviewed.keys())
    )
    findings.extend(
        Finding("ORPHAN", anchor, "inventoried but no anchor in do-not.md")
        for anchor in sorted(reviewed.keys() - live.keys())
    )
    for anchor, row in sorted(reviewed.items()):
        if anchor not in live:
            continue
        ordinal, digest = live[anchor]
        # A subsection has no ordinal in EITHER place, but msgspec leaves the
        # field UNSET while the parser yields None, and UNSET != None. Without
        # this normalisation every subsection fabricates a LOCATOR_DRIFT --
        # found by the control arm, which is the only reason it was not shipped.
        reviewed_ordinal = getattr(row.locator, "reviewed_ordinal", None)
        if not isinstance(reviewed_ordinal, int):
            reviewed_ordinal = None
        if reviewed_ordinal != ordinal:
            findings.append(
                Finding(
                    "LOCATOR_DRIFT",
                    anchor,
                    f"ordinal reviewed={reviewed_ordinal} live={ordinal}",
                )
            )
        if row.locator.reviewed_digest and row.locator.reviewed_digest != digest:
            findings.append(
                Finding("ATTRIBUTE_DRIFT", anchor, "content changed since it was reviewed")
            )
    return findings


#: The mod's own hook source -- a SEPARATE authority from `.claude/settings.json`,
#: never mixed into `_reconcile_registrations`'s `classic` filter.
FUNCTION_HOOK_SOURCE_PATH = Path(".claude/mods/kb-settings-guard/hooks/register.ts")

#: The mod's manifest, whose `modules` array must name a tracked file for
#: `enabled` to be even POSSIBLE -- see `_function_hook_enabled_predicates`.
FUNCTION_HOOK_MANIFEST_PATH = Path(".claude/mods/kb-settings-guard/hooks/hooks.json")

#: The plugin's declared identity, as it appears (possibly with a
#: `@marketplace` suffix) in `enabledPlugins` / `extraKnownMarketplaces`.
_FUNCTION_HOOK_PLUGIN_NAME = "kb-settings-guard"

#: The runtime flag without which NO function hook loads, read from
#: `.claude/settings.json`'s `env` block. Tracked, so it is a legitimate static
#: predicate; `.claude/settings.local.json` is NOT tracked and is never read
#: here, or an untracked file would become ship-gate authority.
_FUNCTION_HOOK_ENV_FLAG = "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"

_TS_LINE_COMMENT = re.compile(r"//[^\n]*")
_TS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_WRITE_TOOLS_ARRAY = re.compile(
    r"const\s+WRITE_TOOLS\s*:\s*readonly\s+string\[\]\s*=\s*\[(?P<body>[^\]]*)\]\s*;"
)
_REGISTER_LOOP = re.compile(
    r"export\s+function\s+register\s*\([^)]*\)\s*:\s*void\s*\{\s*"
    r"for\s*\(\s*const\s+tool\s+of\s+WRITE_TOOLS\s*\)\s*\{\s*"
    r'on\s*\(\s*"tool\.call"\s*,\s*\{\s*tool\s*\}\s*,\s*\w+\s*\)\s*;?\s*'
    r"\}\s*\}"
)
_STRING_LITERAL = re.compile(r'"([^"\\]*)"')
_MATCHER_TOOL = re.compile(r'tool\s*:\s*"([^"]*)"')

#: The ONE function-hook event this reconciler derives from `register.ts`. A row
#: naming anything else is ROUTE_DRIFT, never grouped by its tool as if the
#: event matched -- `tool.result`, for one, cannot synchronously prevent a call
#: and so does not meet the membership capability at all.
_FUNCTION_HOOK_EVENT = "tool.call"

#: Events whose hooks can SYNCHRONOUSLY PREVENT A TOOL CALL. That capability --
#: not the event's name -- is what makes a registration a member of this
#: inventory, so a new event with the same power belongs here and a new
#: lifecycle event never does.
_BLOCKING_EVENTS = frozenset({"PreToolUse"})


def _strip_ts_comments(source: str) -> str:
    """Remove `//` and `/* */` comments before any structural match.

    Load-bearing: the module's only literal `{ tool: "Edit" }` sits inside a
    doc comment (`register.ts:68`), and the two CORRECT rows (`Write`,
    `NotebookEdit`) have ZERO literal hits in the source — a presence check
    over raw text is wrong in both directions.
    """
    return _TS_LINE_COMMENT.sub("", _TS_BLOCK_COMMENT.sub(" ", source))


def function_hook_write_tools(root: Path) -> frozenset[str] | None:
    """The tool set `register.ts`'s loop actually registers, comments stripped.

    Requires EXACTLY one top-level `WRITE_TOOLS` array and EXACTLY one
    supported registration loop over it — a duplicate or a rewritten loop shape
    this cannot verify returns `None`, same as a missing file. The caller
    treats `None` as NOT_RUN, never a silent skip: an anchored extractor that
    cannot see the current shape must say so, not report an empty tool set as
    if the loop legitimately registers nothing.
    """
    try:
        source = (root / FUNCTION_HOOK_SOURCE_PATH).read_text(encoding="utf-8")
    except OSError:
        return None
    stripped = _strip_ts_comments(source)
    arrays = list(_WRITE_TOOLS_ARRAY.finditer(stripped))
    if len(arrays) != 1:
        return None
    if len(list(_REGISTER_LOOP.finditer(stripped))) != 1:
        return None
    tools = _STRING_LITERAL.findall(arrays[0].group("body"))
    if not tools or len(set(tools)) != len(tools):
        return None
    return frozenset(tools)


def _reconcile_function_hooks(
    inventory: GuardInventory, tools: frozenset[str] | None
) -> list[Finding]:
    """Bidirectional reconciliation of `register.ts` against its inventory rows.

    Compares the derived `(path, tool.call, tool)` set from `register.ts`
    against the inventory rows sourced from that same path.
    """
    if tools is None:
        return [
            Finding(
                "NOT_RUN",
                str(FUNCTION_HOOK_SOURCE_PATH),
                "register.ts structure unsupported — enumeration never ran",
            )
        ]
    rows = [r for r in inventory.registrations if r.source.path == str(FUNCTION_HOOK_SOURCE_PATH)]

    # A row whose EVENT is not `tool.call` describes a different registration
    # than the one `register.ts` declares, and is reported as such rather than
    # grouped by its tool and silently matched. The extractor derives
    # `(path, "tool.call", tool)`; comparing the tool alone made the event half
    # of that triple unenforced, so a row could be repointed at `tool.result`
    # -- a hook that cannot block anything -- and the gate stayed green.
    findings: list[Finding] = [
        Finding(
            "ROUTE_DRIFT",
            row.id,
            f"event is {str(getattr(row.source, 'event', '') or '')!r}, not 'tool.call'",
        )
        for row in rows
        if str(getattr(row.source, "event", "") or "") != _FUNCTION_HOOK_EVENT
    ]
    rows = [
        row for row in rows if str(getattr(row.source, "event", "") or "") == _FUNCTION_HOOK_EVENT
    ]

    reviewed: dict[str, list[Registration]] = {}
    for row in rows:
        tool_match = _MATCHER_TOOL.search(str(getattr(row.source, "matcher", "") or ""))
        reviewed.setdefault(tool_match.group(1) if tool_match else "", []).append(row)

    findings.extend(
        Finding(
            "AMBIGUOUS_IDENTITY",
            ", ".join(r.id for r in group),
            f"{len(group)} rows registered for tool.call {tool!r}",
        )
        for tool, group in reviewed.items()
        if len(group) > 1
    )
    findings.extend(
        Finding(
            "UNCLASSIFIED",
            f"tool.call {tool}",
            f"{FUNCTION_HOOK_SOURCE_PATH} registers {tool} with no inventory row",
        )
        for tool in sorted(tools - reviewed.keys())
    )
    findings.extend(
        Finding("ORPHAN", group[0].id, f"no live tool.call registration for {tool!r}")
        for tool, group in reviewed.items()
        if tool not in tools
    )
    return findings


def _function_hook_enabled_predicates(root: Path) -> dict[str, bool]:
    """The three static predicates `enabled` requires, checked independently.

    G00 asserts only what is statically checkable: the mod's `hooks.json`
    validly names the tracked `register.ts`, the plugin appears TRUE in
    `enabledPlugins`, and the plugin's marketplace is declared in
    `extraKnownMarketplaces`. Installation, loading and dispatch are G04's
    (#757), never a tree read.
    """
    hooks_json_valid = False
    try:
        manifest = json.loads((root / FUNCTION_HOOK_MANIFEST_PATH).read_text(encoding="utf-8"))
        modules = manifest.get("modules", []) if isinstance(manifest, dict) else []
        target = (root / FUNCTION_HOOK_SOURCE_PATH).resolve()
        mod_dir = (root / FUNCTION_HOOK_MANIFEST_PATH).parent
        hooks_json_valid = any(
            isinstance(m, str) and (mod_dir / m).resolve() == target for m in modules
        )
    except OSError, json.JSONDecodeError:
        hooks_json_valid = False

    try:
        settings = json.loads((root / SETTINGS_PATH).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    enabled_plugins = settings.get("enabledPlugins", {})
    marketplaces = settings.get("extraKnownMarketplaces", {})
    env = settings.get("env", {})
    plugin_enabled = isinstance(enabled_plugins, dict) and any(
        key.split("@", 1)[0] == _FUNCTION_HOOK_PLUGIN_NAME and value is True
        for key, value in enabled_plugins.items()
    )

    # The OWNER half of `<plugin>@<owner>`, never the plugin name. An
    # `extraKnownMarketplaces` key is a marketplace name (`ray-manaloto`,
    # `astral-sh`), so comparing it to `kb-settings-guard` is unsatisfiable:
    # measured against all 11 live keys, every comparison was False, which made
    # `enabled` unreachable and the whole state check able to return only one
    # answer. A check that cannot produce its other verdict is not a check.
    owners = {
        key.split("@", 1)[1]
        for key, value in (enabled_plugins.items() if isinstance(enabled_plugins, dict) else ())
        if value is True and "@" in key and key.split("@", 1)[0] == _FUNCTION_HOOK_PLUGIN_NAME
    }
    marketplace_known = (
        isinstance(marketplaces, dict) and bool(owners) and owners <= set(marketplaces)
    )

    # The feature flag, which was named in the design and never read. It is a
    # TRACKED fact -- `.claude/settings.json` `env` -- so omitting it left a
    # predicate the docstring claimed and the code did not have. Function hooks
    # do not run at all without it, so no other predicate can substitute.
    function_hooks_enabled = isinstance(env, dict) and str(
        env.get(_FUNCTION_HOOK_ENV_FLAG, "")
    ).strip() not in ("", "0")
    return {
        "hooks_json_valid": hooks_json_valid,
        "plugin_enabled": plugin_enabled,
        "marketplace_known": marketplace_known,
        "function_hooks_enabled": function_hooks_enabled,
    }


def _reconcile_function_hook_state(root: Path, inventory: GuardInventory) -> list[Finding]:
    """Reject BOTH overstatement and understatement of a function-hook row's `state`.

    `enabled` requires every static predicate together; `enabledPlugins`
    presence alone is insufficient (a plugin can be enabled with no
    corresponding marketplace entry, or vice versa, and neither half makes it
    live). A row claiming `enabled` while any predicate fails is
    OVERSTATEMENT; a row left at `declared` while ALL predicates hold is
    UNDERSTATEMENT — both are a state contradicting the same static facts.
    """
    predicates = _function_hook_enabled_predicates(root)
    all_hold = all(predicates.values())
    findings: list[Finding] = []
    for reg in inventory.registrations:
        if reg.source.path != str(FUNCTION_HOOK_SOURCE_PATH):
            continue
        if reg.state is RegistrationState.enabled and not all_hold:
            failing = sorted(k for k, v in predicates.items() if not v)
            findings.append(
                Finding("CONTRADICTION", reg.id, f"state=enabled but {failing} do not hold")
            )
        elif reg.state is RegistrationState.declared and all_hold:
            findings.append(
                Finding(
                    "CONTRADICTION",
                    reg.id,
                    "state=declared but every static enablement predicate holds",
                )
            )
    return findings


def _reconcile_contradictions(inventory: GuardInventory) -> list[Finding]:
    """Dispositions that contradict their own owner or surface.

    The shape of error that reads as perfectly reasonable in a table.
    """
    foreign = {OwnerKind.external_tool, OwnerKind.claude_code_runtime}
    return [
        Finding(
            "CONTRADICTION",
            reg.id,
            f"owner_kind={reg.owner_kind.value} cannot be migrated from this repo",
        )
        for reg in inventory.registrations
        if reg.owner_kind in foreign and reg.disposition is Disposition.function_hook
    ] + [
        Finding(
            "CONTRADICTION",
            reg.id,
            f"state={reg.state.value} is not statically determinable; "
            "installed/exercised are G04's (#757), never a tree read",
        )
        for reg in inventory.registrations
        if reg.state in {RegistrationState.installed, RegistrationState.exercised}
    ]


def reconcile(root: Path, inventory: GuardInventory) -> list[Finding]:
    """Compare every row against live state, in BOTH directions.

    They fail differently and must not be conflated. An inventory row with no
    live counterpart is an ORPHAN -- it describes something deleted. A live
    object with no row is UNCLASSIFIED -- the direction the ticket's FAIL arm
    names, and how a guard gets added with nobody deciding its disposition.
    """
    live = live_registrations(root)
    if live is None:
        return [Finding("NOT_RUN", str(SETTINGS_PATH), "unreadable — reconciliation never ran")]
    findings = _reconcile_registrations(inventory, live)
    findings.extend(_reconcile_modules(root, inventory, live))
    findings.extend(_reconcile_invariants(root, inventory))
    findings.extend(_reconcile_contradictions(inventory))
    findings.extend(_reconcile_function_hooks(inventory, function_hook_write_tools(root)))
    findings.extend(_reconcile_function_hook_state(root, inventory))
    return findings


def render(root: Path, inventory: GuardInventory, findings: list[Finding]) -> str:
    """Report. Every count DERIVED here, never read from the inventory."""
    classic_cases = sum(
        len(r.reviewed_scope_cases or [])
        for r in inventory.registrations
        if r.state is not RegistrationState.declared
    )
    inert_cases = sum(
        len(r.reviewed_scope_cases or [])
        for r in inventory.registrations
        if r.state is RegistrationState.declared
    )
    module_lines = sum(
        len((root / m.path).read_text(encoding="utf-8").splitlines())
        for m in inventory.modules
        if (root / m.path).exists()
    )
    enabled = sum(1 for r in inventory.registrations if r.state is not RegistrationState.declared)
    lines = [
        "[guard-inventory] reconciling against live repo state",
        (
            f"  registrations : {len(inventory.registrations)} "
            f"({enabled} enabled, {len(inventory.registrations) - enabled} declared-only) "
            f"-> {classic_cases} effective cases (+{inert_cases} inert)"
        ),
        f"  modules       : {len(inventory.modules)} ({module_lines} lines, re-derived)",
        f"  invariants    : {len(inventory.invariants)}",
    ]
    new_enforcement = [
        i.id
        for i in inventory.invariants
        if i.disposition is Disposition.function_hook
        and not i.enforced_by
        and i.current_surface is CurrentSurface.prose_only
    ]
    upgrades = [
        i.id
        for i in inventory.invariants
        if i.disposition is Disposition.function_hook
        and i.current_surface is not CurrentSurface.prose_only
    ]
    lines.append(f"  new enforcements : {len(new_enforcement)} ({', '.join(new_enforcement)})")
    lines.append(f"  timing upgrades  : {len(upgrades)} ({', '.join(upgrades)})")
    if not findings:
        lines.append("  reconciliation: OK — every row matches live repo state")
        return "\n".join(lines)
    lines.append(f"  reconciliation: {len(findings)} finding(s)")
    lines.extend(f"    {f.verdict:22} {f.subject}: {f.detail}" for f in findings)
    return "\n".join(lines)


def main(root: Path) -> int:
    """Run the check. Returns a real exit code; nothing swallows it."""
    try:
        inventory = load_inventory(root / DEFAULT_INVENTORY_PATH)
    except GuardInventoryError as exc:
        print(f"[guard-inventory] {exc}")
        return int(Rc.NOT_RUN)
    findings = reconcile(root, inventory)
    print(render(root, inventory, findings))
    if any(f.verdict == "NOT_RUN" for f in findings):
        return int(Rc.NOT_RUN)
    return 1 if findings else 0


def cli() -> int:  # pragma: no cover - thin argv seam
    """Entry point for `uv run kb-setup guard-inventory-check`."""
    return main(Path.cwd())
