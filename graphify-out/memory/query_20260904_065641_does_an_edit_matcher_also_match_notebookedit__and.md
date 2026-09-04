---
type: "query"
date: "2026-09-04T06:56:41.578142+00:00"
question: "Does an Edit matcher also match NotebookEdit, and is the #671 shell-edit hole closed?"
contributor: "graphify"
outcome: "corrected"
correction: "Two claims I stated as measured this round were wrong, and both were caught by a\ncodex advisor lane reading the same pinned source I had.\n\n1. I reported a matcher trap that does not exist: \"`Edit` also matches\n   `NotebookEdit`, so use `^(Edit|Write)$`\". I quoted `hooks.md:295` without the\n   TABLE directly above it at `:289-293`, which says a matcher of only letters,\n   digits, `_`, `-`, spaces, `,` and `|` is evaluated as an EXACT string or list\n   — verbatim, \"`Edit|Write` and `Edit, Write` each match either tool exactly\".\n   The regex sentence I quoted governs the OTHER row of that table. My proposed\n   anchors would have pushed an already-exact matcher onto the regex path.\n\n2. I reported \"the #671 shell-edit hole is already closed, so question E answers\n   itself\". `inplace_edit.py:96-100` states its own blind spots under a heading\n   that reads \"SCOPE, stated so silence does not imply coverage\": heredoc\n   `cat > f.py`, `tee`, `python -c`, `find -exec sed -i`, `xargs sed -i` are all\n   NOT denied. I read the module's header and stopped before the paragraph that\n   contradicted me.\n\nTHE PATTERN, and it is the same one both times: I read the part of a document\nthat answered my question and stopped, without reading the part that qualified\nit. Once that was a summary table above the sentence I quoted; once it was a\nscope paragraph below the docstring I quoted. In both cases the qualifying text\nwas in the SAME FILE, within 10 lines, and free to read.\n\nThe habit that would have caught both: when a document gives you the answer you\ncame for, read the surrounding section before quoting it — a summary table lists\nkey fields for one purpose and is not the field set, and a module's header is\nnot its scope statement. This is `probes-need-a-control-arm.md` rule 3's BOUND\nwearing a third hat: the bound was where I stopped reading.\n\nA third, smaller one: I nearly reported `edit_check.py:128`'s\n`except OSError, subprocess.SubprocessError:` as a Python-2 syntax error. It is\nvalid under PEP 758 on Python 3.14.7. Arming it (ast.parse + a live try/except)\ntook ten seconds and stopped a false bug report.\n"
---

# Q: Does an Edit matcher also match NotebookEdit, and is the #671 shell-edit hole closed?

## Answer

# Round 2026-09-04a — #697 headroom + #700 Edit/Write surface

## What was asked

Phase U step 0's enforcement half. Ray picked #700, #702, #698 in that order
(AskUserQuestion, 2026-09-03). #700 asks: decide the Edit/Write hook surface
deliberately, once, rather than bolting on one guard at a time.

## What was found

`.claude/settings.json` registers PreToolUse on `Bash|Grep` (twice) and
`Read|Glob` and nothing else — no PostToolUse block, no Edit/Write matcher.
`.claude/settings.local.json` has no `hooks` key, so nothing masks that.
`.codex/hooks.json` HAS a PostToolUse `apply_patch` handler running
`kb-setup edit-check`. On the surface where this repo does most of its editing,
the codex lane is the better-instrumented client.

Five contract facts decided the design, each read from the pinned
`sources/claude-code-docs/.../hooks.md`:

1. `permissionDecisionReason` reaches Claude ONLY on `"deny"` (`hooks.md:1746`);
   on allow/ask it goes to the user. Headroom must ride in `additionalContext`.
2. `additionalContext` IS supported on PreToolUse (`hooks.md:1747`, example at
   `:1768`) even though the decision-control summary table at `:1013` omits it.
   The table lists key fields FOR THE DECISION, not the event's field set.
3. `Edit|Write` is already an EXACT matcher (`hooks.md:289-293`). The
   `RegExp.prototype.test` substring semantics apply only to a matcher
   containing a character outside `[A-Za-z0-9_\- ,|]`.
4. A timed-out command hook does NOT block (`hooks.md:846`). Fail-closed must be
   implemented, not inherited. Exit 1 is non-blocking; exit 2 enforces (`:836`).
5. `hook_guard.py:279-280` returns `Ok(None)` for any tool outside
   `{Bash, Grep}` — wiring that entry point on an Edit matcher is a SILENT NO-OP.

## What shipped

- `docs/design/edit-write-hook-surface.md` — the #700 decision record, in `docs/`
  per Ray's ruling (a rule file is eager context; this is a design record).
  Six decisions; NO settings entry and no dormant module.
- #697 cleared: all five zero-headroom instruction files, nothing deleted.
  CLAUDE.md 200->170, do-not.md 200->169, probes-need-a-control-arm.md 200->186,
  clear-prep/SKILL.md 500->483 in both trees. Eager context
  168,087 B / 42,021 tok -> 162,581 B / 40,645 tok.

## The method that made #697 non-destructive

Three levers, in preference order:

1. DE-DUPLICATE. CLAUDE.md's `## Tool currency` restated five bullets from
   `.claude/rules/tool-currency-and-native-first.md`. Both unscoped, so both
   eager — the corpus paid for those facts twice every session.
2. RE-HOME EVIDENCE, KEEP THE NORM. Detail and its correction move TOGETHER: a
   correction is only load-bearing while the claim it corrects is present. The
   rule keeps a one-line "do not re-add it" marker; the evidence goes to
   `docs/invariant-provenance.md` / `docs/probe-failures.md` /
   `docs/currency/design-notes.md`.
3. PROGRESSIVE DISCLOSURE. `md_budget._SKILL_RE` matches `SKILL.md` only, so a
   `references/` sidecar is unbudgeted. `skill_lint.mirror_drift` globs
   `*/SKILL.md` only, so sidecars are not mirror-compared.

## Two holes in #698 as filed, found reading md_budget.py

1. `check()` walks `git ls-files` then skips `not path.is_file()`
   (`md_budget.py:404-405`), so a `Write` CREATING an instruction file is
   invisible twice over. An `overrides` map must INJECT a path, not only
   substitute content.
2. `_size_of()` for eager_root/nested calls `closure_size()`
   (`md_budget.py:329`), re-reading every `@import` member from disk. Overriding
   the top-level read leaves the closure counting stale bytes.

## Gates

lint rc=0 · test rc=0 · skill-lint rc=0 · funnel CLEAN · mirrors byte-identical.


## Outcome

- Signal: corrected
- Correction: Two claims I stated as measured this round were wrong, and both were caught by a
codex advisor lane reading the same pinned source I had.

1. I reported a matcher trap that does not exist: "`Edit` also matches
   `NotebookEdit`, so use `^(Edit|Write)$`". I quoted `hooks.md:295` without the
   TABLE directly above it at `:289-293`, which says a matcher of only letters,
   digits, `_`, `-`, spaces, `,` and `|` is evaluated as an EXACT string or list
   — verbatim, "`Edit|Write` and `Edit, Write` each match either tool exactly".
   The regex sentence I quoted governs the OTHER row of that table. My proposed
   anchors would have pushed an already-exact matcher onto the regex path.

2. I reported "the #671 shell-edit hole is already closed, so question E answers
   itself". `inplace_edit.py:96-100` states its own blind spots under a heading
   that reads "SCOPE, stated so silence does not imply coverage": heredoc
   `cat > f.py`, `tee`, `python -c`, `find -exec sed -i`, `xargs sed -i` are all
   NOT denied. I read the module's header and stopped before the paragraph that
   contradicted me.

THE PATTERN, and it is the same one both times: I read the part of a document
that answered my question and stopped, without reading the part that qualified
it. Once that was a summary table above the sentence I quoted; once it was a
scope paragraph below the docstring I quoted. In both cases the qualifying text
was in the SAME FILE, within 10 lines, and free to read.

The habit that would have caught both: when a document gives you the answer you
came for, read the surrounding section before quoting it — a summary table lists
key fields for one purpose and is not the field set, and a module's header is
not its scope statement. This is `probes-need-a-control-arm.md` rule 3's BOUND
wearing a third hat: the bound was where I stopped reading.

A third, smaller one: I nearly reported `edit_check.py:128`'s
`except OSError, subprocess.SubprocessError:` as a Python-2 syntax error. It is
valid under PEP 758 on Python 3.14.7. Arming it (ast.parse + a live try/except)
took ten seconds and stopped a false bug report.
