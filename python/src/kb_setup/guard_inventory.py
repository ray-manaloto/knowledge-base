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


def dispatched_module_names(root: Path) -> frozenset[str]:
    """Every guard module `hook_guard` imports, by AST walk at ALL depths.

    The reachability half a filename pattern cannot reproduce, and the reason it
    is an AST walk rather than a regex over the dispatch tuple: **`hook_guard`
    imports only 2 of its 9 guards at module scope** (`graph_first` at `:27`);
    the other seven are FUNCTION-LOCAL imports inside their own wrappers around
    `:347-358`. A module-scope walk finds 2 of 9, and a regex over the tuple
    finds all 9 only because of the shape that code happens to have today.
    `ast.walk` visits every `ImportFrom` at every depth, so neither nesting nor a
    refactor of `hook_guard` can hide one.

    Returns EMPTY when the file cannot be read or parsed; the caller treats that
    as NOT_RUN. A parser that silently matches nothing would otherwise report a
    clean reconciliation against nothing at all.
    """
    try:
        source = (root / GUARD_DIR / "hook_guard.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
    except OSError, SyntaxError:
        return frozenset()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "kb_setup":
            names.update(alias.name for alias in node.names)
    return frozenset(names & _module_stems(root))


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


def _reconcile_modules(root: Path, inventory: GuardInventory) -> list[Finding]:
    findings: list[Finding] = []
    dispatched = dispatched_module_names(root)
    if not dispatched:
        return [
            Finding(
                "NOT_RUN",
                "hook_guard dispatch tuple",
                "could not read the guard tuple — the module enumeration never ran",
            )
        ]
    by_stem = {Path(m.path).stem: m for m in inventory.modules}
    findings.extend(
        Finding(
            "UNCLASSIFIED",
            f"{GUARD_DIR / name}.py",
            "reached by hook_guard dispatch but absent from the inventory",
        )
        for name in sorted(dispatched - by_stem.keys())
    )
    for name, module in sorted(by_stem.items()):
        path = root / module.path
        if not path.exists():
            findings.append(Finding("ORPHAN", module.id, f"{module.path} does not exist"))
            continue
        if module.reached_by.value == "hook-guard-dispatch" and name not in dispatched:
            findings.append(
                Finding("ORPHAN", module.id, "claims hook-guard-dispatch but is not in the tuple")
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
    findings.extend(_reconcile_modules(root, inventory))
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
