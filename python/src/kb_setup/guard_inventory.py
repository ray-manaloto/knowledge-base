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


def _has_unsupported_indirection(tree: ast.AST) -> bool:
    """True when `hook_guard.py` reaches a guard through unsupported indirection.

    `importlib.import_module(...)`, `__import__(...)`, or a `getattr(...)` call
    whose target names `kb_setup`. None of these are used by `hook_guard.py`
    today -- this is a fail-closed backstop, not a reachability source in its
    own right.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _DYNAMIC_IMPORT_CALL_NAMES:
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


def _resolve_direct_command(command: str) -> tuple[bool, str | None]:
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
    for resolver in (_resolve_graphify_binary, _resolve_kb_setup_cmd, _resolve_mise_task):
        result = resolver(tokens)
        if result is not None:
            return result
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


def _resolve_mise_task(tokens: list[str]) -> tuple[bool, str | None] | None:
    """`mise run [-C <dir>] <task>` — resolved via the task's own `run =` line."""
    if tokens[:2] != ["mise", "run"]:
        return None
    task = _mise_task_name(tokens[2:])
    kb_cmd = _MISE_TASK_KB_SETUP_CMD.get(task) if task else None
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
    direct: set[str] = set()
    for entry in live:
        if str(entry["event"]) != "PreToolUse":
            continue
        recognised, module_stem = _resolve_direct_command(str(entry["command"]))
        if not recognised:
            return [
                Finding(
                    "NOT_RUN",
                    str(entry["command"])[:70],
                    "unrecognised direct-registration command shape — enumeration never ran",
                )
            ]
        if module_stem is not None:
            direct.add(module_stem)

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
    findings.extend(_reconcile_module_ids(inventory))
    return findings


def _reconcile_module_ids(inventory: GuardInventory) -> list[Finding]:
    """Every registration's `module_ids` must resolve to a real inventory module."""
    known = {m.id for m in inventory.modules}
    findings: list[Finding] = []
    for reg in inventory.registrations:
        ids = reg.module_ids if isinstance(reg.module_ids, list) else []
        findings.extend(
            Finding("ORPHAN", reg.id, f"module_ids references unknown module {mid}")
            for mid in ids
            if mid not in known
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
