# Do Not — Project Invariants

The authoritative list of things agents (and humans) must not do in this repo.

1. **Do NOT run bare `graphify install` — always pass `--project`.** One flag
   separates safe from destructive (verified in the installed `install.py`):
   - `graphify claude install` → **project only** (`./CLAUDE.md` +
     `./.claude/settings.json`).
   - `graphify install --project` → **project only** (adds
     `./.claude/skills/graphify/**` + a block in `./.claude/CLAUDE.md`).
   - ⚠️ `graphify install` **without** `--project` → **mutates `~/.claude`**:
     ~43 KB of skill files, **appends a `# graphify` H1 to `~/.claude/CLAUDE.md`**
     (creating it if absent), and sprays `.graphify_version` stamps into every
     other installed platform's user skill dir.

   Control arm on the safe claim: all **18** `Path.home()` call sites in
   `install.py` sit on `project=False` branches; the project-scoped call chain
   contains none. **`CLAUDE_CONFIG_DIR` is NOT containment** — it redirects the
   skill dir only, while the `~/.claude/CLAUDE.md` write is hardcoded.

   This generalises to EVERY platform. Run any `graphify <platform> install` in
   a **throwaway directory outside this repo**, never here: `graphify
   antigravity install` without `--project` writes to
   `~/.gemini/config/skills/graphify/SKILL.md`, and `graphify codex install`
   appends a `## graphify` block to `AGENTS.md` **with or without** `--project`.

2. **Do NOT run `graphify hook install`, `graphify extract --global`, or
   `graphify global add`.** Shared mutable machine state is non-reproducible and
   collides across hosts. The graph lives in this repo's `graphify-out/`.

   **`watch` was in this list and never belonged to it** (narrowed 2026-08-01).
   Two separate errors. The banned spelling `graphify --watch` is not a real
   invocation at all — `--watch` occurs **0** times in the **pinned 0.9.31**
   `cli.py`, against a control of **7** for `--force`, so the probe
   discriminates; the real form is the subcommand `graphify watch <path>`. And
   its effect is repo-local — it writes `<path>/graphify-out/`, never `~/` — so
   this entry's own stated rationale never described it. A ban filed under a
   reason that does not apply is one nobody can reason about later.

   It is still the wrong tool here, for a better reason: `watch` refreshes only
   that path's **scoped** sub-graph and exposes no post-rebuild hook, so it
   cannot update the **aggregate** `graphify-out/graph.json` that both `affected`
   and `currency.toml`'s `artifact` read. Use **`mise run kb-watch`**
   (`kb_setup.graph.refresh_self`), which re-extracts `python/` + `tests/`,
   merges them into the aggregate, re-derives the prose graph, and restamps.
   Pointing `watch` at the repo root is the actively bad case — it attempts to
   overwrite the merged graph with a root-only extraction, which graphify's
   `_check_shrink` refuses rather than obeys. Running it by hand also still
   fails rule 3, which is where a graphify-by-hand ban correctly lives.

3. **Do NOT run graphify by hand at all — drive it through a `kb-*` mise task.**
   Machine-enforced by `kb_setup.hook_guard` (PreToolUse deny). Read-only
   introspection with no task equivalent (`path`/`explain`/`god-nodes`/
   `affected`/`diagnose`) is allowed. See `mise-tasks-only.md`.

4. **Do NOT let any KEY-DETECTED LLM backend touch the corpus.** Two graphify
   agents are sanctioned — `claude-cli` and `openai-cli` (Ray, 2026-08-25,
   `docs/direction/2026-08-25-ray-directives.md` §2; both subscription-billed,
   both `--backend`-explicit only). What stays forbidden is any backend an API
   KEY selects: a global `GEMINI_API_KEY` exists on this machine, so
   `kb_setup.graphify_env.clean_env()` strips every key trigger (Gemini/Google/
   OpenAI/Kimi/DeepSeek/Azure/**Bedrock via `AWS_REGION`**/Ollama) from every
   graphify subprocess. The CLI carve-out is graphify's own, not `clean_env()`'s:
   `detect_backend()` (`sources/graphify/graphify/llm.py:3527`) never auto-selects
   `claude-cli` or `openai-cli`. Keep the `OPENAI_API_KEY` strip — without it the
   openai-cli route can fall through to the METERED API (`llm.py:1870-1874`).
   Never re-introduce a key var into a graphify call path, and never
   "temporarily" unset the cleaner to make something work.

5. **Do NOT commit `graphify-out/` beyond `memory/`.** Everything else is
   DERIVED and rebuilt by `kb-build` / `kb-artifacts`; at aggregate scale the
   graph exceeds git/GitHub limits. Consumers query via `kb-serve` MCP or a
   pushed graph DB, never a git blob.

   **A second exception, `graphify-semantic-corpus-chunks/`, lived here from
   2026-08-23 to 2026-08-24.** Ray settled #317 in favour of TRACKING that
   retained provider evidence, then ruled the whole semantic-corpus layer
   removed the next day — its evidence tree went with it (`docs/archive/README.md`).
   The rule is back to one exception. This is recorded because the prior
   two-exception wording drifted stale for a day between the settling and the
   rewrite once already (an agent following it literally would have UNTRACKED
   105 files it should have kept), which is the shape this note exists to
   prevent: a decision that lands in the repo but not in the instruction that
   governs it.

6. **Do NOT ingest a source outside the `sources/` contract.** Every source is
   either a `sources/<name>.manifest` pinned to an upstream commit, vendored
   under `sources/media/`, or a committed extraction chunk under
   `sources/extractions/`. An ad-hoc `curl`/WebFetch that never reaches the
   graph produces knowledge no other session can see.

7. **Do NOT commit onto the default branch — branch FIRST.** Create the branch
   *before* the commit, then `mise run kb-ship`. A session in the sibling repo
   committed 34 files straight onto `main` and had to move them afterwards; it
   was recoverable only because nothing had been pushed.

8. **Do NOT add a `.sh` script or inline shell logic.** This repo has zero.
   See `zero-bash-logic.md`.

9. **Do NOT add an inline lint suppression.** `noqa` / `type: ignore` /
   `ty: ignore` / `nosec` are rejected by the `no_lint_skip` hk step. All
   suppressions live in the ONE root `pyproject.toml` as per-file-ignores,
   visible and reviewable in one place. See `zero-skip-policy.md`.

10. **Do NOT trust `gh run watch --exit-status`.** It has reported 0
    prematurely. Cross-verify with `gh pr checks <n> --json` or
    `gh run view <id> --json conclusion`.

11. **Do NOT edit anything outside this project.** No `~/.claude`, no
    `~/.gemini`, no global/system/user config, ever. This repo edits PROJECT
    settings only — which is what makes invariant 1 above load-bearing rather
    than a style preference.

## On MCP

Native MCP registration is **allowed** when a plugin or tool requires it.
`mcp2cli` (process-spawn, no per-conversation schema-injection tax) stays the
*preferred* path for one-off doc/tool calls — a preference, not a gate. See
`research-doc-sources.md`.

## See also

- `mise-tasks-only.md` — canonical mise tasks over one-off commands (hook-enforced)
- `zero-skip-policy.md` — no warning/error shall be dismissed
- `verify-before-advancing.md` — every applicable check green before the next task
- `probes-need-a-control-arm.md` — a check that can only pass is not a check
- `clean-git-state.md` — stage all changes before validation
- `use-tool-builtins.md` — prefer tool builtins over homegrown logic
