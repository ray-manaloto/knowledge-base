# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.guard_inventory` — the G00 (#753) reconciler.

Each test asserts the EXPECTED DIAGNOSTIC, never merely "something failed". A
test that accepts any non-empty findings list passes when the reconciler dies
for an unrelated reason, which is Astra's green-and-useless failure mode #10 and
the difference between an armed gate and one that reddens for any cause at all.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from kb_setup import guard_inventory
from kb_setup.guard_inventory import (
    DEFAULT_INVENTORY_PATH,
    DO_NOT_PATH,
    SETTINGS_PATH,
    GuardInventoryError,
    dispatched_module_names,
    expand_scope_cases,
    invariant_digests,
    load_inventory,
    reconcile,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """A mutable copy of the four authorities the reconciler reads."""
    for rel in (SETTINGS_PATH, DO_NOT_PATH, DEFAULT_INVENTORY_PATH):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dest)
    guard_dir = tmp_path / "python" / "src" / "kb_setup"
    guard_dir.mkdir(parents=True, exist_ok=True)
    for src in (REPO / "python" / "src" / "kb_setup").glob("*.py"):
        shutil.copy(src, guard_dir / src.name)
    return tmp_path


def _verdicts(findings: list) -> list[str]:
    return [f.verdict for f in findings]


# --- the control arm, first ------------------------------------------------


def test_the_committed_inventory_reconciles_clean(repo_copy: Path) -> None:
    """THE CONTROL ARM. Everything below is void if this is not clean.

    A reconciler that reddens on an unmutated tree cannot discriminate, so every
    FAIL-direction test that follows would pass for the wrong reason.
    """
    inventory = load_inventory(repo_copy / DEFAULT_INVENTORY_PATH)
    assert reconcile(repo_copy, inventory) == []


# --- reachability: the membership rule the whole ticket turns on -----------


def test_reachability_finds_the_four_modules_a_name_pattern_misses() -> None:
    """The defect this inventory exists to close, as a test.

    `graph_first`, `destructive_git`, `codex_lane` and `inplace_edit` contain
    none of the tokens the programme report's `grep -Ei` alternation used, so it
    published 7 modules when there were 11. Reachability sees all four.
    """
    dispatched = dispatched_module_names(REPO)
    for missed in ("graph_first", "destructive_git", "codex_lane", "inplace_edit"):
        assert missed in dispatched, f"{missed} is dispatched but reachability missed it"


def test_reachability_excludes_hook_guards_own_redirect() -> None:
    """`_graphify_redirect` is hook_guard's own logic, not a separate module."""
    assert "graphify_redirect" not in dispatched_module_names(REPO)


def test_unreadable_hook_guard_yields_empty_not_a_false_clean(tmp_path: Path) -> None:
    """An empty set means NOT_RUN upstream, never "there are no guards".

    A parser that silently matches nothing would otherwise report a clean
    reconciliation against nothing at all.
    """
    assert dispatched_module_names(tmp_path) == frozenset()


# --- F3: every static import shape, not only `from kb_setup import X` -----


def _hook_guard_fixture(tmp_path: Path, body: str, extra_modules: tuple[str, ...] = ()) -> Path:
    """A minimal `hook_guard.py` plus stub sibling modules.

    The stubs are what `_module_stems` admits, so whatever import shape a test
    names must also appear as an actual file.
    """
    guard_dir = tmp_path / "python" / "src" / "kb_setup"
    guard_dir.mkdir(parents=True, exist_ok=True)
    (guard_dir / "hook_guard.py").write_text(body, encoding="utf-8")
    for name in extra_modules:
        (guard_dir / f"{name}.py").write_text("", encoding="utf-8")
    return tmp_path


def test_a_from_kb_setup_import_reaches_a_brand_new_guard(tmp_path: Path) -> None:
    root = _hook_guard_fixture(
        tmp_path, "from kb_setup import brandnew_guard\n", ("brandnew_guard",)
    )
    assert "brandnew_guard" in dispatched_module_names(root)


def test_a_bare_import_of_a_submodule_reaches_a_brand_new_guard(tmp_path: Path) -> None:
    """`import kb_setup.brandnew_guard` -- silently missed before this fix."""
    root = _hook_guard_fixture(tmp_path, "import kb_setup.brandnew_guard\n", ("brandnew_guard",))
    assert "brandnew_guard" in dispatched_module_names(root)


def test_a_relative_bare_import_reaches_a_brand_new_guard(tmp_path: Path) -> None:
    """`from . import brandnew_guard` -- silently missed before this fix."""
    root = _hook_guard_fixture(tmp_path, "from . import brandnew_guard\n", ("brandnew_guard",))
    assert "brandnew_guard" in dispatched_module_names(root)


def test_a_relative_submodule_import_reaches_a_brand_new_guard(tmp_path: Path) -> None:
    """`from .brandnew_guard import decide` -- silently missed before this fix."""
    root = _hook_guard_fixture(
        tmp_path, "from .brandnew_guard import decide\n", ("brandnew_guard",)
    )
    assert "brandnew_guard" in dispatched_module_names(root)


def test_a_dotted_from_import_reaches_the_named_submodule(tmp_path: Path) -> None:
    """`from kb_setup.stage_explicitly import decide` -- the victim-substitution arm."""
    root = _hook_guard_fixture(
        tmp_path, "from kb_setup.stage_explicitly import decide\n", ("stage_explicitly",)
    )
    assert "stage_explicitly" in dispatched_module_names(root)


def test_an_import_module_call_naming_kb_setup_fails_closed(tmp_path: Path) -> None:
    """A dynamic `importlib.import_module` call must NOT be silently omitted."""
    root = _hook_guard_fixture(
        tmp_path,
        'import importlib\nimportlib.import_module("kb_setup.brandnew_guard")\n',
        ("brandnew_guard",),
    )
    assert dispatched_module_names(root) == frozenset()


def test_a_bare_dunder_import_call_fails_closed(tmp_path: Path) -> None:
    root = _hook_guard_fixture(
        tmp_path, '__import__("kb_setup.brandnew_guard")\n', ("brandnew_guard",)
    )
    assert dispatched_module_names(root) == frozenset()


def test_a_getattr_on_kb_setup_fails_closed(tmp_path: Path) -> None:
    root = _hook_guard_fixture(
        tmp_path, "import kb_setup\ngetattr(kb_setup, 'brandnew_guard')\n", ("brandnew_guard",)
    )
    assert dispatched_module_names(root) == frozenset()


def test_a_getattr_unrelated_to_kb_setup_does_not_trip_the_backstop(tmp_path: Path) -> None:
    """The backstop is scoped to `kb_setup`; an ordinary getattr must still work."""
    root = _hook_guard_fixture(
        tmp_path,
        "from kb_setup import brandnew_guard\ngetattr(object(), 'x', None)\n",
        ("brandnew_guard",),
    )
    assert "brandnew_guard" in dispatched_module_names(root)


# --- the effective-case denominator ----------------------------------------


def test_an_if_condition_refines_the_matcher_to_one_tool() -> None:
    assert expand_scope_cases("Edit|Write", "Edit(CLAUDE.md)") == [("Edit", "CLAUDE.md")]


def test_a_bare_matcher_contributes_one_case_per_alternative() -> None:
    assert expand_scope_cases("Bash|Grep", "") == [("Bash", ""), ("Grep", "")]


def test_no_matcher_is_an_explicit_wildcard_case() -> None:
    assert expand_scope_cases("", "") == [("*", "")]


def test_an_unparsable_if_condition_is_never_silently_widened() -> None:
    """None, so the caller reports UNINTERPRETABLE_SCOPE.

    Widening it would silently GROW claimed coverage, which is worse than
    failing: the gate would report more protection than exists.
    """
    assert expand_scope_cases("Edit|Write", "this is not a condition") is None


def test_the_live_settings_expand_to_twenty_eight_effective_cases() -> None:
    """18 registrations, 28 effective cases — the real denominator.

    A migration graded against 18 can drop 10 cases and read complete.
    """
    settings = json.loads((REPO / SETTINGS_PATH).read_text(encoding="utf-8"))
    total = 0
    for groups in settings["hooks"].values():
        for group in groups:
            for hook in group.get("hooks", []):
                cases = expand_scope_cases(group.get("matcher") or "", hook.get("if") or "")
                assert cases is not None
                total += len(cases)
    assert total == 28


# --- the FAIL directions the ticket names ----------------------------------


def test_an_unclassified_live_hook_fails_with_that_verdict(repo_copy: Path) -> None:
    """The ticket's named FAIL arm: add a hook nobody classified."""
    path = repo_copy / SETTINGS_PATH
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"].append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo junk", "timeout": 5}]}
    )
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert "UNCLASSIFIED" in _verdicts(findings)


def test_a_removed_invariant_mapping_fails_with_orphan(repo_copy: Path) -> None:
    """The ticket's other named FAIL arm: drop an anchor from do-not.md."""
    path = repo_copy / DO_NOT_PATH
    text = path.read_text(encoding="utf-8")
    anchor = "<!-- guard-programme: do-not.default-branch -->\n"
    assert anchor in text
    path.write_text(text.replace(anchor, "", 1), encoding="utf-8")
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert "ORPHAN" in _verdicts(findings)


def test_renumbering_an_invariant_fails_with_locator_drift(repo_copy: Path) -> None:
    """Renumbering must NOT silently steal the next rule's disposition.

    This is why the ordinal is compared separately from the anchor: the anchor
    still identifies the rule, so the drift is reported rather than followed.
    """
    path = repo_copy / DO_NOT_PATH
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("7. **Do NOT commit onto the default branch", "8. **Do NOT commit onto"),
        encoding="utf-8",
    )
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert "LOCATOR_DRIFT" in _verdicts(findings)


def test_a_deleted_guard_module_fails_with_orphan(repo_copy: Path) -> None:
    (repo_copy / "python" / "src" / "kb_setup" / "stage_explicitly.py").unlink()
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert "ORPHAN" in _verdicts(findings)


# --- F1: direct-registration modules are now reconciled --------------------


def _drop_module_block(text: str, module_id: str) -> str:
    """Delete one `[[modules]]` block by id, from a copy of the inventory text."""
    pattern = re.compile(
        r'\[\[modules\]\]\nid = "' + re.escape(module_id) + r'"\n.*?(?=\n\[\[modules\]\]|\n# --- )',
        re.DOTALL,
    )
    new_text, n = pattern.subn("", text, count=1)
    assert n == 1, f"expected exactly one [[modules]] block for {module_id}"
    return new_text


def _add_pretool_hook(settings: dict, matcher: str, command: str, timeout: int = 30) -> None:
    settings["hooks"]["PreToolUse"].append(
        {"matcher": matcher, "hooks": [{"type": "command", "command": command, "timeout": timeout}]}
    )


def test_a_direct_registration_module_dropped_from_inventory_is_unclassified(
    repo_copy: Path,
) -> None:
    """`module.instruction-edit-guard` is `direct-registration`.

    Not `hook-guard-dispatch` -- the axis F1 adds a check for.
    """
    path = repo_copy / DEFAULT_INVENTORY_PATH
    path.write_text(
        _drop_module_block(path.read_text(encoding="utf-8"), "module.instruction-edit-guard"),
        encoding="utf-8",
    )
    findings = reconcile(repo_copy, load_inventory(path))
    assert "UNCLASSIFIED" in _verdicts(findings)


def test_the_dispatchers_own_module_row_dropped_is_unclassified(repo_copy: Path) -> None:
    """`module.hook-guard` is the dispatcher itself, also `direct-registration`."""
    path = repo_copy / DEFAULT_INVENTORY_PATH
    path.write_text(
        _drop_module_block(path.read_text(encoding="utf-8"), "module.hook-guard"), encoding="utf-8"
    )
    findings = reconcile(repo_copy, load_inventory(path))
    assert "UNCLASSIFIED" in _verdicts(findings)


def test_a_repointed_direct_module_path_fails_reconciliation(repo_copy: Path) -> None:
    """F1's own arm: repoint `module.hook-guard`'s path to another EXISTING file.

    Before F1 nothing checked a `direct-registration` module's route at all, so
    this mutation survived reconciliation entirely.
    """
    path = repo_copy / DEFAULT_INVENTORY_PATH
    text = path.read_text(encoding="utf-8")
    original = 'path = "python/src/kb_setup/hook_guard.py"'
    assert text.count(original) == 1
    path.write_text(
        text.replace(original, 'path = "python/src/kb_setup/check_first.py"', 1), encoding="utf-8"
    )
    findings = reconcile(repo_copy, load_inventory(path))
    assert findings, "repointing a direct-registration module's path must not reconcile clean"


def test_an_unrecognised_direct_command_shape_is_not_run(repo_copy: Path) -> None:
    """An unknown command shape must be NOT_RUN, never silently 'external'."""
    settings_path = repo_copy / SETTINGS_PATH
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    _add_pretool_hook(settings, "Bash", "./scripts/a-brand-new-guard.sh")
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert "NOT_RUN" in _verdicts(findings)


def test_an_unmapped_mise_task_direct_command_is_not_run(repo_copy: Path) -> None:
    """A `mise run` task this resolver has no entry for must be NOT_RUN too."""
    settings_path = repo_copy / SETTINGS_PATH
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    _add_pretool_hook(settings, "Bash", 'mise run -C "${CLAUDE_PROJECT_DIR:-.}" kb-brand-new-guard')
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert "NOT_RUN" in _verdicts(findings)


def test_a_registration_referencing_an_unknown_module_id_is_flagged(repo_copy: Path) -> None:
    """`module_ids` must resolve to a real inventory module -- blind spot 5's other half."""
    path = repo_copy / DEFAULT_INVENTORY_PATH
    text = path.read_text(encoding="utf-8")
    anchor = '  "module.hook-guard",\n'
    assert text.count(anchor) == 1
    path.write_text(
        text.replace(anchor, anchor + '  "module.does-not-exist",\n', 1), encoding="utf-8"
    )
    findings = reconcile(repo_copy, load_inventory(path))
    assert any("module.does-not-exist" in f.detail for f in findings)


# --- F1: the resolver itself -----------------------------------------------


def test_the_hookguard_command_resolves_to_hook_guard() -> None:
    recognised, module = guard_inventory._resolve_direct_command(
        'uv run --project "${CLAUDE_PROJECT_DIR:-.}/python" kb-setup hookguard'
    )
    assert (recognised, module) == (True, "hook_guard")


def test_the_instruction_edit_guard_mise_task_resolves_to_its_module() -> None:
    recognised, module = guard_inventory._resolve_direct_command(
        'mise run -C "${CLAUDE_PROJECT_DIR:-.}" kb-instruction-edit-guard'
    )
    assert (recognised, module) == (True, "instruction_edit_guard")


def test_the_instruction_shell_write_mise_task_resolves_to_its_module() -> None:
    recognised, module = guard_inventory._resolve_direct_command(
        'mise run -C "${CLAUDE_PROJECT_DIR:-.}" kb-instruction-shell-write'
    )
    assert (recognised, module) == (True, "instruction_shell_write")


def test_the_graphify_binary_read_and_search_resolve_to_external() -> None:
    for sub in ("read", "search"):
        recognised, module = guard_inventory._resolve_direct_command(
            f'"${{CLAUDE_PROJECT_DIR:-.}}/.venv/bin/graphify" hook-guard {sub}'
        )
        assert (recognised, module) == (True, None)


def test_an_unknown_graphify_hook_guard_subcommand_is_not_recognised() -> None:
    recognised, module = guard_inventory._resolve_direct_command(
        '"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/graphify" hook-guard bogus'
    )
    assert (recognised, module) == (False, None)


def test_an_unmapped_mise_task_is_not_recognised() -> None:
    recognised, module = guard_inventory._resolve_direct_command(
        'mise run -C "${CLAUDE_PROJECT_DIR:-.}" kb-brand-new-guard'
    )
    assert (recognised, module) == (False, None)


def test_a_wholly_unknown_command_shape_is_not_recognised() -> None:
    recognised, module = guard_inventory._resolve_direct_command("./scripts/a-brand-new-guard.sh")
    assert (recognised, module) == (False, None)


def test_an_unreadable_authority_is_not_run_not_a_pass(repo_copy: Path) -> None:
    """Inability to ask is never a pass — the repo's own Rc contract."""
    (repo_copy / SETTINGS_PATH).unlink()
    findings = reconcile(repo_copy, load_inventory(repo_copy / DEFAULT_INVENTORY_PATH))
    assert _verdicts(findings) == ["NOT_RUN"]


# --- the regression the control arm caught ---------------------------------


def test_a_subsection_without_an_ordinal_does_not_fabricate_drift(repo_copy: Path) -> None:
    """REGRESSION. A subsection has no ordinal in EITHER place.

    msgspec leaves the field UNSET while the parser yields None, and
    `UNSET != None`, so every subsection fabricated a permanent LOCATOR_DRIFT.
    Nothing but running the control arm would have found it — the call graph
    reads correctly.
    """
    inventory = load_inventory(repo_copy / DEFAULT_INVENTORY_PATH)
    subsections = [i for i in inventory.invariants if i.kind.value == "subsection"]
    assert subsections, "fixture must contain a subsection or this test cannot fail"
    drifted = {f.subject for f in reconcile(repo_copy, inventory) if f.verdict == "LOCATOR_DRIFT"}
    assert not ({i.id for i in subsections} & drifted)


# --- the closed set, which is why the models are generated ------------------


def test_an_unrecognised_disposition_is_rejected_at_decode(repo_copy: Path) -> None:
    """A bare `str` here cost this repo two full kb-build runs once already."""
    path = repo_copy / DEFAULT_INVENTORY_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'disposition = "function-hook"', 'disposition = "not-a-real-disposition"', 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(GuardInventoryError, match=r"guard-inventory\.schema\.json"):
        load_inventory(path)


def test_a_positional_id_is_rejected_by_the_semantic_id_pattern(repo_copy: Path) -> None:
    """`R00` is an index; an index re-points a disposition when rows shift."""
    path = repo_copy / DEFAULT_INVENTORY_PATH
    path.write_text(
        path.read_text(encoding="utf-8").replace('id = "module.hook-guard"', 'id = "R00"', 1),
        encoding="utf-8",
    )
    with pytest.raises(GuardInventoryError, match=r"guard-inventory\.schema\.json"):
        load_inventory(path)


# --- the anchors themselves -------------------------------------------------


def test_every_do_not_invariant_carries_an_anchor() -> None:
    """15 anchors: 13 numbered invariants + 2 non-'See also' subsections."""
    digests = invariant_digests(REPO)
    assert digests is not None
    assert len(digests) == 15
    assert sum(1 for ordinal, _ in digests.values() if ordinal is not None) == 13
