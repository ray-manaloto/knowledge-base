# The Edit/Write hook surface — decision record

**Issue:** #700. **Decided:** 2026-09-03. **Status:** decided, not yet built.
**Advisor:** `kb-codex-advisor` (gpt-5.6-sol, xhigh) — verdict retained at
`.agent/kb/reports/agents/advisor-700-edit-write-surface.md`.

Ray's ruling (AskUserQuestion, 2026-09-03): **trim first, then guard**; this
record lives in `docs/`, not `.claude/rules/`, because it is a design record and
not a per-session instruction — a rule file is eager context in every session.

## The finding this answers

`.claude/settings.json` registers `PreToolUse` on `Bash|Grep` (twice) and
`Read|Glob`. There is **no `PostToolUse` block and no Edit/Write matcher at all**.
`.claude/settings.local.json` has no `hooks` key, so nothing overrides that —
control-armed, the asymmetry is real and unmasked.

Meanwhile `.codex/hooks.json` carries a `PostToolUse` `apply_patch` handler
running `kb-setup edit-check`. **On the surface where this repo does most of its
editing, the codex lane receives more edit-time feedback than Claude does.**

Caveat, so this is not read as "codex has it better": a codex hook is SKIPPED
SILENTLY until its exact hash is trusted (measured 2026-09-03: 3 trusted
`pre_tool_use`, **0** `post_tool_use`). "codex has more" is about what is
*registered*, not necessarily what *runs*.

## Decisions

### 1. Event — `PreToolUse` only

One handler does both jobs. `PostToolUse` would duplicate it.

- **Over budget** → `hookSpecificOutput.permissionDecision: "deny"` plus
  `permissionDecisionReason`, which Claude reads.
- **Within budget** → `hookSpecificOutput.additionalContext` carrying the
  projected headroom, and **no `permissionDecision` at all**.

Two contract details decide the shape, both read from
`sources/claude-code-docs/.../hooks.md` rather than assumed:

- 🔴 **`permissionDecisionReason` reaches Claude only on `"deny"`.** For
  `"allow"` and `"ask"` it is *"shown to the user but not Claude"*
  (`hooks.md:1745`). So headroom on a valid edit MUST travel in
  `additionalContext`, never the reason.
- 🔴 **`additionalContext` IS supported on `PreToolUse`** (`hooks.md:1747`, with
  the JSON example at `:1766`) — even though the decision-control summary table
  at `:1007` lists only `permissionDecision`/`permissionDecisionReason`. That
  table gives key fields *for the decision*, not the event's full field set. A
  design read off the summary alone splits this across two events and is wrong.

Omitting `permissionDecision` on the valid path is deliberate: returning
`"allow"` would additionally **skip the user's permission prompt**, a side effect
nobody asked for. `additionalContext` is ignored under `"defer"` (`:1747`), so
defer-plus-headroom discards the very thing it sends — the advisor's verdict
proposed exactly that and is corrected here.

### 2. Matcher — `Edit|Write`, plus one `if` rule per path class

`Edit|Write` is **already exact**. `hooks.md:289-293`: a matcher containing only
letters, digits, `_`, `-`, spaces, `,` and `|` is evaluated as an exact string or
list — verbatim, *"`Edit|Write` and `Edit, Write` each match either tool
exactly."* The `RegExp.prototype.test` substring semantics at `:295` (where
`Edit.*` also matches `NotebookEdit`) apply only to a matcher containing some
other character. **So `^(Edit|Write)$` is wrong** — the anchors would push an
already-exact matcher onto the regex path for nothing.

`MultiEdit` has **0** occurrences in the pinned docs; that tool no longer exists.
Do not name `NotebookEdit`: it writes `.ipynb`, not instruction markdown.

Filtering goes in the harness via `if`, not only in python, because a bare
matcher spawns a ~0.25 s process on **every** edit in the repo for a policy that
concerns a small minority of them. `if` holds **exactly one** permission rule
(`hooks.md:432`) — no `&&`, `||` or list — so each path class needs its own
handler. One `Edit(<glob>)` rule covers `Edit`, `Write` and `NotebookEdit`
(`tools-reference.md:85,368`). Python stays authoritative; `if` is cheap dispatch
only, since the docs call the filter best-effort (`hooks.md:448`).

### 3. Module — separate, not inside `hook_guard`

`hook_guard`'s whole interface is a shell-tokenised `command` from `Bash`/`Grep`;
an Edit payload has none of that. Mixing payload families would turn it into a
heterogeneous dispatcher where an instruction-policy failure could affect every
Bash and Grep call.

🔴 **And wiring `hook_guard`'s entry point on an Edit matcher today is a silent
no-op**: `hook_guard.py:279-280` returns `Ok(None)` immediately for any
`tool_name` outside `{"Bash", "Grep"}`.

So: a new `kb_setup` module, its own CLI entry, its own mise task, per
`zero-bash-logic.md`. It shares the **authoritative** `md_budget` sweep — never a
second per-file checker, which would be free to disagree with the gate — and
shares no shell tokeniser.

### 4. Errors — fail CLOSED for a matched candidate

`hook_guard` fails open deliberately: a crashed guard must not brick every Bash
call. That reasoning does **not** carry here. A silent internal failure defeats
exactly the policy the hook advertises, and the blast radius is one instruction
file rather than all shell access.

🔴 **The timeout path fails OPEN and cannot be leaned on.** `hooks.md:845`,
verbatim: *"A timed-out `command`, `http`, or `mcp_tool` hook doesn't block the
tool call. The call continues through the normal permission flow, so don't count
on a stalled hook to act as a gate."* Only an Agent SDK callback hook blocks on
timeout. Related: `hooks.md:836` — exit **1** is a non-blocking error and the
action proceeds; **exit 2** (or a JSON deny) is the enforcement code.

Fail-closed therefore has to be *implemented*, not inherited. The hk gate remains
the final authority either way.

### 5. No Claude mirror of `edit-check`

Claude already receives ty diagnostics after an Edit-tool edit via LSP (#671,
proven three-armed). A duplicate adds noise.

⚠️ **The shell-edit bypass is NOT fully closed, and I claimed it was.**
`inplace_edit.py:96-100` states its own blind spots verbatim, under the heading
*"SCOPE, stated so silence does not imply coverage"*: a heredoc (`cat > f.py`),
`tee`, a `python -c` that writes a file, and `find … -exec sed -i` /
`xargs sed -i`, where the command word is `find`/`xargs`. It sees `sed`/`perl` at
a command position only, and only for `.py`/`.pyi`. Those belong at the **Bash**
surface, not Edit/Write — closing them here would be the wrong tenant.

`Write` has not been probed for whether it delivers LSP feedback the way `Edit`
does. Probe it before assuming; if it does not, a narrow Write-only
`PostToolUse` tenant is justified and nothing else is.

### 6. Ordering — #697 before any denial

Five instruction files sat at **exactly** 100% of their line budget when this was
decided — `CLAUDE.md` (200/200), `.claude/rules/do-not.md` (200/200),
`.claude/rules/probes-need-a-control-arm.md` (200/200), and
`.claude/skills/clear-prep/SKILL.md` (500/500) in BOTH the `.claude/` and
`.agents/` trees. Re-derived twice independently on 2026-09-03; issue 697's prose
said seven, its own table said five, and five is right.

**How to re-derive it.** `md_budget.Report` exposes only an aggregate count, so
the per-file breakdown needs the classifier directly — the cold review of
`00d0b078` correctly labelled this claim `unverified` for want of exactly this
recipe:

```python
from pathlib import Path
from kb_setup import md_budget as m
root = Path(".")
for rel in m.tracked_files(root):
    f = root / rel
    if m.classify(rel) is None or not f.is_file():
        continue
    raw = f.read_text(errors="replace")
    cls = m._resolve_class(rel, raw, m.DEFAULT_EXCLUDED_PREFIXES)
    if cls is None:
        continue
    lines, _bytes, _unit = m._size_of(cls, f, raw, root)
    cap = m.BUDGETS[cls].max_lines
    print(f"{lines / cap:6.1%} {lines:>4}/{cap:<4} {rel}")
``` A deny shipped against that state makes every edit to
`CLAUDE.md` or `do-not.md` a trim-first operation, and **a guard that blocks
routinely gets switched off — a switched-off guard is worse than none.**

Issue 697 was landed first, in the same round as this record. Post-trim the
tightest files are `.claude/rules/long-running-command-hangs.md` (198/200) and
`.claude/rules/mise-tasks-only.md` (194/200) — same recipe as above — so the
ordering constraint is relieved but not eliminated.

(That paragraph opened with a bare `#697` until the cold review of `00d0b078`:
`mise run fmt` rewrote it to `# 697` at line start, making it an **H1** and
orphaning the rest of the sentence. `kb-review`'s own SKILL.md records the same
hazard. Never start a line with `#` followed by digits.)

## What this record does NOT do

No settings entry, no placeholder command, no dormant module. A registered
skeleton falsely advertises coverage and creates an interface before the
behaviour and its arms exist. **#698 is the first implementation tenant**, and it
owes a `kb-arms` spec proving both directions per
`probes-need-a-control-arm.md` — Edit and Write arms, matching and non-matching
paths.

Two holes in #698's proposal as filed, found reading `md_budget.py`:

1. `check()` walks `tracked_files()` (`git ls-files`) then skips anything where
   `not path.is_file()` (`md_budget.py:404-405`). A `Write` creating a **new**
   instruction file is invisible twice over — untracked and not yet on disk. An
   `overrides` map must be able to **inject** a path into the walk, not only
   substitute content for one already in it.
2. `_size_of()` for `eager_root`/`nested` calls `closure_size(path, root)`
   (`md_budget.py:329`), which re-reads every `@import`ed member from disk.
   Overriding only the top-level `read_text` leaves the closure counting stale
   bytes.

A third tenant exists and is unscoped: `.agents/skills/**` mirrors
`.claude/skills/**` byte-exactly, and editing one half obliges the other.
`skill_lint.mirror_drift` already covers it as a stable-state gate; #699 records
why it can never be a per-edit deny (a single-file `Edit` cannot update both
atomically).

## Measurements behind this record

- Full `md_budget` sweep: **0.24 / 0.28 / 0.29 s** (three runs, warm cache,
  `uv run` startup included) over **50** instruction files. A **cold**-cache
  figure was NOT measured, and sizing the hook's `timeout` needs one.
- Eager context at decision time: **162,581 bytes / ~40,645 tokens** per session,
  down from 168,087 / 42,021 before #697.
- "~5% of edits touch an instruction file" is the advisor's **estimate** and was
  not measured. Measure it before using it to justify the `if` dispatch.

## See also

- `.claude/rules/md-size-budgets.md` — the budgets this surface would enforce.
- `.claude/rules/zero-bash-logic.md` · `mise-tasks-only.md` — module + seam shape.
- `.claude/rules/probes-need-a-control-arm.md` — the arms #698 owes.
- `docs/invariant-provenance.md` · `docs/probe-failures.md` ·
  `docs/currency/design-notes.md` — the evidence re-homed by #697.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues #671, #697, #698, #699, #700.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — via the pinned docs clone `sources/claude-code-docs/`, for `hooks.md` and `tools-reference.md`.
```
