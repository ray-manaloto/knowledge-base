# Mise Tasks Only: No One-Off Commands for Canonical Workflows

Every recurring workflow in this repo has (or gets) a canonical mise
task. When a task exists, USE IT — never hand-roll the underlying
command sequence. When you build a new recurring workflow, ship its mise
task (wrapping a `kb_setup` module, per `zero-bash-logic.md`) in the same change.

## The canonical task map

| Instead of | Use |
|---|---|
| `hk run check --all` / `hk run pre-commit --all` | `mise run lint` (read-only, no silent rewriting); `mise run fmt` to apply fixes |
| bare `pytest` | `mise run test` (or `uv run pytest tests/path::test` for one test) |
| `agnix .` | `mise run lint-docs` (`--strict`, warnings-as-errors) |
| `graphify extract` / `clone` / `merge-graphs` | `mise run kb-build` |
| `graphify update` | `mise run kb-update -- <name>` |
| `graphify add <url>` | `mise run kb-add -- <url>` |
| `graphify query "…"` | `mise run kb-query -- "<question>"` (add `--prose` for a question about the DOCUMENTS) |
| `graphify query --graph …/graph-prose.json` | `mise run kb-query -- "<question>" --prose` |
| `graphify cluster` / `label` | `mise run kb-label` |
| `graphify save-result` | `mise run kb-remember -- --question Q --answer-file A.md --outcome useful` — now a `kb_setup` module, not a bare seam: it REFUSES `--outcome corrected` with no `--correction`/`--correction-file`, because that field is the only thing `reflect` renders and **21 of 32** recorded corrections reached `LESSONS.md` empty. `-- --audit` names the survivors |
| `graphify reflect` | `mise run kb-reflect` |
| the bundled interpreter / `_merge_docs.py` | `mise run kb-merge -- <chunk>` |
| `graphify transcribe` | `mise run kb-transcribe -- <audio>` |
| regenerating wiki/graphml/svg by hand | `mise run kb-artifacts` |
| `graphify install --project` (which regresses `.claude/settings.json` every run — #133), or copying the skill out of the pinned clone | `mise run kb-skill-refresh` — runs the GENERATOR (the skill tree is generated, never authored) via `kb_setup.currency.skill`, the SAME refresh a `currency apply` bump uses, then re-applies `currency.skill.ADDENDA` (this repo's local notes, which the installer wipes — it ate one on its first live run) and `fmt`s. Refuses a graphify that disagrees with the pin, and exits non-zero on a lost addendum |
| `gh pr create` (+ push + gates by hand) | `mise run kb-ship` |
| `gh pr merge` (+ watch + validate by hand) | `mise run kb-land -- <PR#>` |
| a manual version-drift check | `mise run kb-currency-check` (offline) / `mise run kb-currency` |
| hand-writing the same throwaway probe again, or eyeballing a transcript for "what should have been a task" | `mise run kb-distill` — proposes a `skill -> task -> module` triple for any script shape written twice (#219). The producing half of Ray's directive; `kb-skill-lint` is the policing half. Advisory, always rc 0, **never a gate** |
| judging a skill by eye, or a raw `plugin-eval score` | `mise run kb-skill-score [-- [--write] <skill>...]` — advisory on findings (a score never fails a gate) but **rc 2 on a malformed request**, e.g. a skill name matching nothing; names WHICH plugin-eval copy scored you, since two scorers are not comparable |
| eyeballing whether a skill got better, or diffing two transcripts | the committed baseline: `docs/skills/baseline.json` + `README.md`, written by `kb-skill-score -- --write` and shown as a Δ column on every later run |
| a hand-rolled pre-PR review, or waiting on CodeRabbit | the `kb-review` skill, then `mise run kb-review-receipt` — **both** `kb-ship` and `kb-land` refuse an unreviewed HEAD (one exception: a commit whose ENTIRE delta since the receipt is `graphify-out/memory/**` or `docs/goals/README.md`, so the round's own closing tasks can land — `kb_setup.review.EXEMPT_PATHS`, #66) |
| `mise run <task> &` (hand-detaching a local task) | the harness background run — a `&`-detached local task gets REAPED when the turn goes idle |
| `uv run ruff check <file> \| tail -3` (and the ty/pytest forms) — the dev loop | `mise run kb-check -- <paths>` — ruff + format + ty + the paths' own tests, real exit codes, no pipe. `check` is whole-repo and `kb-gates` runs the ship gates; **neither answered "are these two files clean?"**, and that vacuum was filled 35 times in one session by a pipe that discards the gate's rc (2026-08-08) |
| `<gate> 2>&1 \| tail -40` | `mise run kb-check` / `kb-gates` as above. The old advice here was `> /tmp/out.log 2>&1; echo "rc=$?"` — **shell logic, in the repo whose first invariant forbids it**, and unfollowable besides: `${PIPESTATUS[0]}` is a BASH array and this shell is zsh, where it expands to empty for a passing and a failing gate alike (armed both ways, zsh 5.9). If you must pipe, zsh spells it `${pipestatus[1]}` |
| `git status` + `git branch` + `git log` + `gh pr list`, reformatted by hand into a handoff | `mise run kb-session-state` — one task, already handoff-shaped (#144). `-- --no-pr` skips the network call. A failed `gh` lookup prints `COULD NOT ASK`, never `none`; the four raw commands stay fine for ordinary diagnostics. **To COPY the block, use `uv run kb-setup session-state`** — mise redaction mangles the branch, every SHA and every PR number, which is the one case in this table where the task is not the right transport |
| running the gates one at a time and retyping the exit codes into a handoff | `mise run kb-gates` — runs them and writes `.agent/kb/gates/gates-<sha>.json`, so the claim has a surviving artifact. The `/tmp` form above is still correct for a ONE-OFF gate; what it cannot do is outlive the session (#146) |
| `npx <tool>` | the mise-pinned binary directly |

Read-only introspection with **no task equivalent** stays direct and is
explicitly allowed by the guard: `graphify path`, `explain`, `god-nodes`,
`affected`, `diagnose`, `--help`, `--version`. So do ordinary diagnostics
(`git status`, `gh pr view`, a single-test `uv run pytest`).

## Enforcement layers

1. **PreToolUse hook (hard deny).** `.claude/settings.json` routes every Bash
   call through `kb_setup.hook_guard`. A raw `graphify <sub>` at a command
   position, or a call through graphify's bundled interpreter / `_merge_docs.py`
   / `import graphify`, is DENIED with the canonical task printed back
   (JSON `permissionDecision: "deny"` — deterministic, applies even in
   bypassPermissions mode). Tested in `tests/test_hook_guard.py`.
2. **hk step `skill_lint` (authoring-time deny).** `uv run kb-setup skill-lint`
   fails the lint if a `SKILL.md` instructs, inside a shell fence, a command a
   mise task already owns — printing the canonical task, not just a refusal.
   Closes #128, Ray's standing "skills call mise tasks that wrap the python
   library", which had lived only in prose here.

   **It shares ONE decision function with layer 1**:
   `kb_setup.skill_lint.check()` calls `hook_guard.decide()`, so the redirect
   table, the read-only allowlist and the remediation wording exist once and are
   enforced in both places. A redirect added to `_REDIRECT` is live at runtime
   AND at authoring time with no second table to drift; a test pins that shared
   identity. `decide` is an injectable parameter, so the walker is reusable for
   a different command family without forking it.

   Scope, stated because a gate's scope is what its green means: only
   `.claude/skills/*/SKILL.md`, only inside ```` ```bash ````-class fences
   (prose *describing* a tool is not an instruction), and the
   installer-generated `.claude/skills/graphify/**` is excluded on
   `md_budget`'s precedent. A glob matching nothing exits **`Rc.NOT_RUN` (127)**, not 0 — a gate
   that never asked the question is not a pass.
2b. **The SAME hook also denies a broad source search before any graph query**
   (`kb_setup.graph_first`, #253) — a second directive, one entry point, so
   `.claude/settings.json` matches `Bash|Grep` for this hook rather than `Bash`.
   It is here because it is the *second* measurement of this rule's thesis: the
   warning-only version of that directive was complied with **0 times out of
   19** in one session, while the DENY above took its own violations 62 → 0.
   See `research-doc-sources.md` step 0 for the scope.
3. **This rule + the skills.** `.claude/skills/kb-curator/SKILL.md` carries the
   MANDATE and the full ingestion workflow; markdown alone is "relying on the
   LLM", so it is never the only layer.
4. **`mise run kb-ship` gates.** The `kb-review` receipt, then `lint`, `test`,
   `brain-audit`, and `eval` all run before a PR is pushed, so a workflow that
   bypasses a task and breaks something fails at ship time rather than in review.

The hook **fails OPEN on its own errors** — a crashed guard must not brick
every Bash call. It is a *redirect* guard, not a sandbox: `$(…)` substitution,
`sh -c`, `eval`, and aliases all get through by design. That is the
precision-over-recall trade; measured evasion in the sibling repo's equivalent
guard is **zero**, while its only recorded defects were false positives.

**The guard allows anything containing `mise run kb-…`** — a task legitimately
shells out to graphify inside itself, and the guard only sees the command
Claude issues, not the task's children.

## What the guard does NOT cover here

Unlike the sibling dotfiles repo, this guard does **not** intercept
`gh pr create` / `gh pr merge`. Use `mise run kb-ship` / `mise run kb-land`
anyway — the gates only run if you go through them. (dotfiles' guard IS
repo-aware and will redirect a *knowledge-base* PR to `kb-ship`/`kb-land`;
that repo-awareness exists because an earlier unconditional rule denied KB PRs
and pointed at a dotfiles-only task, so two KB PRs had to be merged by hand.
**A guard whose redirect target cannot perform the redirected action is not
enforcement, it is an outage.**)

## Extending

A new redirect = a new `_REDIRECT` entry in `hook_guard.py` + a test + a row in
the table above, in the same change. Keep patterns narrow: a redirect that
misfires on legitimate read-only introspection erodes trust in the guard, and
that — not evasion — is the direction every measured defect has come from.

## See also

- `zero-bash-logic.md` — a task wraps a `kb_setup` module, never a shell script.
- `verify-before-advancing.md` — the gates `kb-ship`/`kb-land` encode.
- `long-running-command-hangs.md` — why the gate tasks, not raw hk.
- `do-not.md` — the graphify invariants the guard machine-enforces.
