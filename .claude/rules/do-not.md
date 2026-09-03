# Do Not — Project Invariants

The authoritative list of things agents (and humans) must not do in this repo.

1. **Do NOT run `graphify install` by hand — not even with `--project`.**
   `hook_guard.decide()` keys only on the SUBCOMMAND, never on flags
   (`hook_guard.py:141-147`), so `--project` is not a carve-out: both
   `graphify install --project` and bare `graphify install` are DENIED.
   Control-armed this round: `hg.decide("graphify install --project")` →
   denied, `hg.decide("mise run kb-build")` → `None`. **Use
   `mise run kb-skill-refresh`** instead — it runs the same installer, then
   repairs what the installer regresses (`.claude/settings.json`'s hook
   paths/timeouts, a stripped trailing newline — #133) and restores the local
   skill addenda the installer wipes. See `mise-tasks-only.md`.

   Bare `graphify install` (no `--project`) still additionally **mutates
   `~/.claude`**: at the pinned 0.9.53, `dispatch_install_cli` resolves
   exactly **one** platform — the CLI arg, or `claude` by default
   (`install.py:2066-2121`) — and `_copy_skill_file` writes ONE destination
   plus ONE `.graphify_version` stamp (`install.py:172-239`); there is no
   loop spraying stamps into every installed platform, an earlier version of
   this entry said there was and was wrong. Default (`claude`) write is
   ~84 KB total: `skill.md` (~41 KB) + its `references/` sidecar (~43 KB,
   `:187-190`), plus it **appends a `# graphify` H1 to `~/.claude/CLAUDE.md`**
   (creating it if absent). `CLAUDE_CONFIG_DIR` is irrelevant either way,
   since `--project` is denied outright regardless of any env var.

   **The denial generalises to every platform subcommand, not just
   `install`.** `graphify antigravity install` and `graphify codex install
   --project` are BOTH denied too. The old advice to run those "in a
   throwaway directory outside this repo" works only for a **human** typing
   directly in a terminal — the hook watches this session's Bash tool, not
   the target directory.

2. **Do NOT run `graphify hook install`, `graphify extract --global`, or
   `graphify global add`.** All three are hand-run graphify, already forbidden
   by entry 3 — but their REASONS differ:
   - `extract --global` / `global add` — genuinely shared, non-reproducible,
     collides across hosts. The graph lives in this repo's `graphify-out/`.
   - `hook install` — **MISFILED here, but only PARTIALLY.** `graphify.hooks.install()`
     (`hooks.py:754-763`) resolves the nearest git repo and calls
     `_hooks_dir(root)`, which asks `git rev-parse --git-path hooks` and
     honours `core.hooksPath` (`hooks.py:491-532`): on an ordinary repo it
     writes to **that repo's own `.git/hooks`**, never `~/`. But when
     `core.hooksPath` names an absolute external directory (e.g.
     `~/.githooks`, as Husky sets), `install()` writes THERE instead —
     genuinely shared state in that one configuration, banned for entry-2's
     own reason rather than entry-3's.

   **`watch` was in this list and never belonged to it** (narrowed 2026-08-01).
   The banned spelling `graphify --watch` is not a real invocation — `--watch`
   occurs **0** times in the currently-pinned **0.9.53** `cli.py`
   (re-verified this round; was cited against 0.9.31), against a control of
   **9** for `--force`. The real form is the subcommand `graphify watch
   <path>`, and its effect is repo-local (`<path>/graphify-out/`, never `~/`)
   — this entry's stated rationale never described it.

   It is still the wrong tool here, for a better reason: `watch` refreshes
   only that path's scoped sub-graph with no post-rebuild hook, so it cannot
   update the **aggregate** `graphify-out/graph.json`. Use
   **`mise run kb-watch`** (`kb_setup.graph.refresh_self`), which re-extracts
   `python/` + `tests/`, merges into the aggregate, re-derives the prose
   graph, and restamps. Running `watch` by hand also still fails rule 3.

3. **Do NOT run graphify by hand at all — drive it through a `kb-*` mise task.**
   Enforced by `kb_setup.hook_guard`, a PreToolUse deny — **best-effort, not
   a sandbox**: it FAILS OPEN on its own errors (`hook_guard.py:314`) and
   does not intercept `$(…)` substitution, `sh -c`, `eval`, or an alias.
   Read-only introspection is an EXPLICIT diagnostic allowlist
   (`hook_guard.py:91-100`), not "no task equivalent" —
   `path`/`explain`/`god-nodes`/`affected`/`diagnose`/`--help`/`-h`/`--version`;
   `affected` has its own `kb-affected` task and is still allowed direct,
   since the allowlist is a deliberate exception list. See `mise-tasks-only.md`.

4. **Do NOT let any NON-ANTHROPIC key-detected LLM backend touch the corpus —
   `ANTHROPIC_API_KEY` is the one deliberate, test-locked exception.** The
   headline used to say "any key-detected backend"; that is WRONG (#685).
   `ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL` are intentionally KEPT
   (`kb_setup/graphify_env.py:21-24`), and `detect_backend`'s own priority
   tuple puts `"claude"` third (`llm.py:3547`) — so it genuinely IS
   key-detected and genuinely IS allowed to auto-select. `[[ -v
   ANTHROPIC_API_KEY ]]` is ABSENT on this host, so the gap is latent and
   host-conditional, not a live leak — but live on any host that exports it.

   Two graphify agents are sanctioned — `claude-cli` and `openai-cli` (Ray,
   2026-08-25, `docs/direction/2026-08-25-ray-directives.md` §2; both
   subscription-billed, both `--backend`-explicit only). Every OTHER
   key-detected backend stays forbidden: `clean_env()` strips every
   non-Claude key trigger (Gemini/Google/OpenAI/Kimi/DeepSeek/Azure/
   **Bedrock via `AWS_REGION`**/Ollama) — `_STRIP_BACKEND_ENV`
   (`graphify_env.py:32+`). `detect_backend()` (`llm.py:3535`) never
   auto-selects `claude-cli`/`openai-cli` by name. Keep the `OPENAI_API_KEY`
   strip — without it the openai-cli route can fall through to the METERED
   API (`llm.py:2017-2022`). `extra` overrides in `clean_env({...})` apply
   AFTER the strips (`test_graphify_env.py::test_extra_still_wins`) — do not
   hand a stripped key back in through `extra`.

   🔴 **The compensating control this module cites is GONE.** The comment at
   `graphify_env.py:25-31` cites `graphify_semantic_slice.scrub_route_overrides`
   as removing the two Anthropic vars from this process's own environ before
   corpus entry points run. That module does not exist (removed with the
   2026-08-24 layer removal). No executable definition or call site survives
   anywhere in `python/` — `git grep -n scrub_route_overrides -- python/`
   finds only this same comment (a repo-wide grep also hits many `docs/`
   reports, frozen provenance of the removed layer, not live references).
   Filed as #686; do not assume this control runs.

5. **Do NOT commit `graphify-out/` beyond `memory/` and
   `graphify-semantic-slice/`.** Everything else is DERIVED and rebuilt by
   `kb-build` / `kb-artifacts`; at aggregate scale the graph exceeds
   git/GitHub limits. **`git ls-files graphify-out` returns TWO tracked
   subdirectories today, not one**: `memory/` (364 files) and
   `graphify-semantic-slice/` (5 files: four added 2026-08-14 in `cc6e226b`,
   the fifth — `provider-boundary-start.json` — added 2026-08-15 in
   `98b116fd`; `272d14bc` on 2026-08-22 only MODIFIED all five, per
   `git show --stat 272d14bc`, not "added" as an earlier version said).
   A THIRD, unrelated exception, `graphify-semantic-corpus-chunks/`, lived
   here 2026-08-23–24 and is correctly gone with the whole semantic-corpus
   layer (`docs/archive/README.md`) — don't confuse the removed
   `-corpus-chunks/` with the still-tracked `-semantic-slice/`.

6. **Do NOT ingest a source outside the `sources/` contract.** Every
   graph-ingested source is either a `sources/<name>.manifest`, vendored
   under `sources/media/`, or a committed extraction chunk under
   `sources/extractions/`. An ad-hoc `curl`/WebFetch that never reaches the
   graph produces knowledge no other session can see. `sources/*.pages.toml`
   (e.g. `sources/doppler-docs.pages.toml`) is a DIFFERENT thing — staged
   site-capture evidence, not yet an extraction.

7. **Do NOT commit onto the default branch — branch FIRST.** Create the branch
   *before* the commit, then `mise run kb-ship`. Enforced at SHIP time, not
   commit time — `kb-ship`'s preflight refuses to push from `main`
   (`pr.py:405-411`), but nothing stops the commit itself landing on `main`
   first. A sibling-repo session committed 34 files straight onto `main` and
   had to move them afterwards; recoverable only because nothing was pushed.

8. **Do NOT add a `.sh` script or inline decision logic to `hk.pkl`/
   `mise.toml`.** This repo has zero `.sh` files (`git ls-files '*.sh'` → 0);
   "inline shell logic" means multi-statement decision logic in those two
   files, not any string containing a shell command — a one-command task
   seam is fine. **Policy, not a hk gate today.** See `zero-bash-logic.md`.

9. **Do NOT add an inline lint suppression.** `noqa` / `type: ignore` /
   `ty: ignore` / `nosec` are rejected by the `no_lint_skip` hk step — but
   only inside `python/src/` and `tests/` (`lint_checks.py:31`'s
   `_SCAN_DIRS`; `find_inline_suppressions` is declared at `:34`, but the
   self-file exclusion it needs — it necessarily contains every marker
   literally — is implemented at `:40-47`, not `:34`). All suppressions live
   in the ONE root `pyproject.toml`. See `zero-skip-policy.md`.

10. **Do NOT trust `gh run watch --exit-status`.** It has reported 0
    prematurely. Cross-verify with `gh pr checks <n> --json name,state,bucket`
    or `gh run view <id> --json conclusion` — bare `--json` is a usage error.

11. **Do NOT intentionally MUTATE user, global, or system configuration as
    part of repository work — from an agent session, ever.** No writing to
    `~/.claude`, `~/.gemini`, `~/.codex/config.toml`, or any other
    global/system/user config. This repo edits PROJECT settings only. (Entry
    1's other-platform advice applies only to a human outside this session.)

## On MCP

Native MCP registration is **allowed** when a plugin/tool genuinely requires
it — Ray's ruling, replacing this section's prior project-only wording. See
`research-doc-sources.md` § "MCP registration is allowed when required" for
the policy plus Ray's condition: a check-before-registering step (user-global
or project config? same name elsewhere?), since `codex mcp add --url` once
broke codex by writing a USER-GLOBAL entry over this repo's own (`.codex/config.toml:122`).

## Two codex-sandbox invariants (missing until this round)

Verified against `sources/codex.manifest`'s `openai/codex@rust-v0.152.1`
(`5adb68a4`), agreeing with the installed `codex-cli` **0.152.1**.

12. **Do NOT combine `--sandbox <value>` with
    `--dangerously-bypass-approvals-and-sandbox`.** The bypass flag carries
    no `conflicts_with` (`shared_options.rs:52-59`) — unlike its sibling
    `--approve-for-me`, which DOES declare `conflicts_with_all = [...]` at
    `:44-50`, proving the rejection mechanism exists and simply wasn't
    applied here. So `-s read-only --dangerously-bypass-approvals-and-sandbox`
    is accepted and silently runs at **danger-full-access**
    (`cli/src/main.rs:2217-2221`).

13. **Do NOT run a repository lane at `--sandbox danger-full-access`.**
    `SandboxPolicy::DangerFullAccess` resolves to `unrestricted()`
    (`permissions.rs:1792`, `:580-586`) — an EMPTY filesystem-entries list —
    where `ReadOnly` builds a real restricted entry protecting the root
    (`:1794-1801`); `.git`/`.agents`/`.codex` lose their read-only
    protection. (Not `protocol.rs:1228` — a different function,
    `get_writable_roots_with_cwd`; its `DangerFullAccess` arm is `:1228`,
    `ReadOnly` is `:1230`, and both return `Vec::new()` there.)

## See also

- `mise-tasks-only.md` — canonical mise tasks over one-off commands (hook-enforced)
- `zero-skip-policy.md` — no warning/error shall be dismissed
- `verify-before-advancing.md` — every applicable check green before the next task
- `probes-need-a-control-arm.md` — a check that can only pass is not a check
- `clean-git-state.md` — stage all changes before validation
- `use-tool-builtins.md` — prefer tool builtins over homegrown logic
