---
type: "query"
date: "2026-09-04T14:08:29.573422+00:00"
question: "Does a Claude Code hook `if` filter of the form `Edit(<glob>)` also match a Write tool call?"
contributor: "graphify"
outcome: "corrected"
correction: "# A hook `if` filter matches on the ACTUAL TOOL NAME, not on a tool family\n\nBuilding the #698 Edit/Write instruction-budget guard, the first wiring in\n`.claude/settings.json` used four `PreToolUse` groups, each with an `if` rule of\nthe shape `Edit(<glob>)` — `Edit(CLAUDE.md)`, `Edit(.claude/rules/**)`, and so on\n— on the reading that `Edit(<glob>)` names a *path-matching predicate* that the\nwhole edit family (Edit, Write, NotebookEdit) is measured against. That reading is\nthe natural one, and `permissions.md:316` does not contradict it.\n\n**All 55 unit tests were green and the hook fired on nothing.**\n\nIt was found only by attempting a real over-budget `Write` to `.claude/rules/` and\nwatching the file reach disk. A green unit suite says the DECISION FUNCTION works;\nit says nothing about whether the settings file beside it ever routes a call into\nthat function. Those are two different questions and only one of them has tests.\n\nThe measurement, four rows, one variable each:\n\n| `if` rule | tool called | fired? |\n|---|---|---|\n| `Edit(.claude/rules/**)` | Edit | yes |\n| `Edit(.claude/rules/**)` | Write | **no** |\n| `Write(.claude/rules/**)` | Write | yes |\n| `Write(.claude/rules/**)` | Edit | **no** |\n\nSo the tool name inside `if` is the tool name, matched exactly. The fix was eight\ngroups rather than four — an `Edit(...)` and a `Write(...)` rule for each of the\nfour path classes. `docs/design/edit-write-hook-surface.md` carried the wrong\nclaim (\"one `Edit(<glob>)` rule covers Edit, Write and NotebookEdit\") and was\ncorrected with this table in the same change.\n\n**The transferable part**: a guard has two halves — the decision and the wiring —\nand the test suite can only see one of them. Before believing a new hook works,\nperform the ACTION it is supposed to block and confirm the block, once per tool\nname you claim to cover. `probes-need-a-control-arm.md` rule 2 applied to\nconfiguration rather than to code.\n\n**And a second one from the same change**: `no_lint_skip` matched the literal\nstring `ty: ignore` inside a DOCSTRING — the lint failed on prose describing a\nsuppression, not on a suppression. Same class as the agnix-keyed-on-filename trap:\na gate reads TEXT, not meaning.\n"
---

# Q: Does a Claude Code hook `if` filter of the form `Edit(<glob>)` also match a Write tool call?

## Answer

# A hook `if` filter matches on the ACTUAL TOOL NAME, not on a tool family

Building the #698 Edit/Write instruction-budget guard, the first wiring in
`.claude/settings.json` used four `PreToolUse` groups, each with an `if` rule of
the shape `Edit(<glob>)` — `Edit(CLAUDE.md)`, `Edit(.claude/rules/**)`, and so on
— on the reading that `Edit(<glob>)` names a *path-matching predicate* that the
whole edit family (Edit, Write, NotebookEdit) is measured against. That reading is
the natural one, and `permissions.md:316` does not contradict it.

**All 55 unit tests were green and the hook fired on nothing.**

It was found only by attempting a real over-budget `Write` to `.claude/rules/` and
watching the file reach disk. A green unit suite says the DECISION FUNCTION works;
it says nothing about whether the settings file beside it ever routes a call into
that function. Those are two different questions and only one of them has tests.

The measurement, four rows, one variable each:

| `if` rule | tool called | fired? |
|---|---|---|
| `Edit(.claude/rules/**)` | Edit | yes |
| `Edit(.claude/rules/**)` | Write | **no** |
| `Write(.claude/rules/**)` | Write | yes |
| `Write(.claude/rules/**)` | Edit | **no** |

So the tool name inside `if` is the tool name, matched exactly. The fix was eight
groups rather than four — an `Edit(...)` and a `Write(...)` rule for each of the
four path classes. `docs/design/edit-write-hook-surface.md` carried the wrong
claim ("one `Edit(<glob>)` rule covers Edit, Write and NotebookEdit") and was
corrected with this table in the same change.

**The transferable part**: a guard has two halves — the decision and the wiring —
and the test suite can only see one of them. Before believing a new hook works,
perform the ACTION it is supposed to block and confirm the block, once per tool
name you claim to cover. `probes-need-a-control-arm.md` rule 2 applied to
configuration rather than to code.

**And a second one from the same change**: `no_lint_skip` matched the literal
string `ty: ignore` inside a DOCSTRING — the lint failed on prose describing a
suppression, not on a suppression. Same class as the agnix-keyed-on-filename trap:
a gate reads TEXT, not meaning.


## Outcome

- Signal: corrected
- Correction: # A hook `if` filter matches on the ACTUAL TOOL NAME, not on a tool family

Building the #698 Edit/Write instruction-budget guard, the first wiring in
`.claude/settings.json` used four `PreToolUse` groups, each with an `if` rule of
the shape `Edit(<glob>)` — `Edit(CLAUDE.md)`, `Edit(.claude/rules/**)`, and so on
— on the reading that `Edit(<glob>)` names a *path-matching predicate* that the
whole edit family (Edit, Write, NotebookEdit) is measured against. That reading is
the natural one, and `permissions.md:316` does not contradict it.

**All 55 unit tests were green and the hook fired on nothing.**

It was found only by attempting a real over-budget `Write` to `.claude/rules/` and
watching the file reach disk. A green unit suite says the DECISION FUNCTION works;
it says nothing about whether the settings file beside it ever routes a call into
that function. Those are two different questions and only one of them has tests.

The measurement, four rows, one variable each:

| `if` rule | tool called | fired? |
|---|---|---|
| `Edit(.claude/rules/**)` | Edit | yes |
| `Edit(.claude/rules/**)` | Write | **no** |
| `Write(.claude/rules/**)` | Write | yes |
| `Write(.claude/rules/**)` | Edit | **no** |

So the tool name inside `if` is the tool name, matched exactly. The fix was eight
groups rather than four — an `Edit(...)` and a `Write(...)` rule for each of the
four path classes. `docs/design/edit-write-hook-surface.md` carried the wrong
claim ("one `Edit(<glob>)` rule covers Edit, Write and NotebookEdit") and was
corrected with this table in the same change.

**The transferable part**: a guard has two halves — the decision and the wiring —
and the test suite can only see one of them. Before believing a new hook works,
perform the ACTION it is supposed to block and confirm the block, once per tool
name you claim to cover. `probes-need-a-control-arm.md` rule 2 applied to
configuration rather than to code.

**And a second one from the same change**: `no_lint_skip` matched the literal
string `ty: ignore` inside a DOCSTRING — the lint failed on prose describing a
suppression, not on a suppression. Same class as the agnix-keyed-on-filename trap:
a gate reads TEXT, not meaning.
