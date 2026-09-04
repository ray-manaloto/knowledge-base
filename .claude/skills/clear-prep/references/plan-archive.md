# Archiving the planning-with-files plan

Loaded on demand by `clear-prep` step 7. Split out of `SKILL.md` on
2026-09-03 (#697), which was at exactly its 500-line ceiling. Do this ONLY
after the user answers *"/clear now"*.

**One line is NOT a verbatim move**, flagged by the cold review of `00d0b078`:
the `PWF=` assignment below was rewritten from a `:-` default carrying a literal
plugin-cache path to the `:?` required-variable form. Two reasons, and neither is
cosmetic. agnix exempts a `SKILL.md` from its hard-coded-path rule but NOT a
`references/*.md` sidecar — measured three-armed — so that literal fails
`mise run lint` here while it passed there. And it pinned a plugin VERSION in
prose, which goes stale silently. `session-resume/SKILL.md` still carries the
literal path if you need it. Everything else below is verbatim.

**On *"/clear now"* — and only then — ARCHIVE the plan, but only if it is DONE:**

```bash
# CLAUDE_PLUGIN_ROOT is set when the plugin invokes this. Outside that, resolve
# it from the planning-with-files entry under the plugin cache — the literal
# path (with its pinned version) is in `session-resume/SKILL.md`.
PWF="${CLAUDE_PLUGIN_ROOT:?point this at the planning-with-files plugin root}"
sh "$PWF/scripts/check-complete.sh"   # phases still in_progress? then DO NOT archive
mkdir -p .planning/.archive && mv .planning/<id> .planning/.archive/<id>
grep -qx '<id>' .planning/.active_plan 2>/dev/null && rm .planning/.active_plan
```

**Archiving an UNFINISHED plan destroys the thing the plugin exists for** — its
`SessionStart` hook (matcher `startup|resume|clear|compact`) restores a live plan
after exactly the `/clear` you are preparing, and in gated mode the Stop hook is
still counting its phases. So check first — an incomplete plan is normal and stays.
The `.active_plan` guard matters: one global pointer a parallel `PLAN_ID` may hold.

Two details are load-bearing. Nothing creates `.archive/`, so without `mkdir -p`
the first archive fails and an `&&` chain silently leaves the plan selected. And
the leading dot matters because `resolve-plan-dir.sh` falls back to the newest
`.planning/<dir>/` by mtime while **skipping hidden dirs** (`.*) continue ;;`).

**Find the plan before you move it** — `resolve-plan-dir.sh` honours `PLAN_ID`
and `PWF_PLAN_ROOT`, and legacy mode keeps `task_plan.md` at the repo ROOT with
no `.planning/` at all. Archive rather than delete; `.planning/` is gitignored,
so none of it is corpus. After the answer, never before the ask. Then stop: next
is the user's `/clear`, then `/session-resume`.
