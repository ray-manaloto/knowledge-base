# Ray's directives — 2026-08-21 (c) — VERBATIM

Written the same day, mid-round, in the pin-sync session that followed the
`/clear` after `kb-20260821.03`. Session `11db65d3` (this one). This file is
separate from `2026-08-21-ray-directives.md` because that file carries two
addenda that exist only on `corpus-gate-bundle-0821`; appending a third here
on a branch cut from `main` would have made the two branches conflict on it.

## The round's opening instruction (`/kb-resume` args) — VERBATIM

> must do this also:
> update/graphifyresync:
> - mise.toml:
>   - codex: 0.149.0
>   - antigravity-cli: 1.1.17
> - pyproject.toml:
>   - ruff: v0.16.4

## On where the bumps go (AskUserQuestion) — decisions

Own pin-sync PR FIRST, on its own branch off `main` (`tool-sync-0821`), before
the small tooling PR and before round 3. Include the carried mise
2026.8.9 → 2026.8.10 sync. On `kb-build` being RED (#397), Ray — VERBATIM:

> just update all first level dependencies and graphify sources from mise.toml
> and pyproject.toml. if there are failures besides graphify on the rsync, that
> is ok for now as we just need the updates to in the proejct. but must fix
> test failures or anything that affects the project from working properly
> so these commands must not show anything outdated:
> - mise outdated --local -b -J
> - uv tree --outdated --show-sizes --all-groups --format json

## Mid-turn, after the session hand-edited the two files with `sed` — VERBATIM

> dont hand edit mise.toml and pyproject.toml
> - use their native commands
> - add this as a check in session-review for occurences this is being done
>   and how to prevent an agent from hand modifying these files

And, minutes later — VERBATIM:

> enforce with:
> - AGENTS.md/CLAUDE.md instructions
> - hooks and claude rules when those files are updated via path filter
> - anything else possible:
>   - hk linters/pre-commit/post-commit checks?

**What was done on the spot:** the hand edits were reverted (`git checkout`)
and redone through the owners — `mise use rumdl@0.2.58 gh@2.98.0 codex@0.149.0
antigravity-cli@1.1.17`, `mise config set min_version.hard|soft 2026.8.10`,
`uv add "anthropic>=1.0.0"`, `uv add --group dev "ruff==0.16.4"` — producing
byte-identical diffs to the reverted edits. `currency.toml` and the five
`sources/*.manifest` files stay hand-edited: no native command owns them, and
the directive names only the two files above.

**What the directive asks for beyond the spot fix** (the enforcement set, to be
built as one change): a CLAUDE.md/AGENTS.md instruction; a `.claude/rules/`
rule path-scoped to `mise.toml` + `pyproject.toml`; a PreToolUse DENY
(`Edit|Write|Bash`) on a direct write to either file, printing the native
command (`mise use` / `mise config set` / `uv add` / `uv remove` / `uv lock`);
hk steps that catch the RESULT of a hand edit — a lockfile that disagrees with
its manifest (`uv lock --check`; the mise-lock equivalent); and a
session-review lane that counts hand edits of those files across transcripts.

## At `/clear-prep` step 0 (AskUserQuestion), same session — VERBATIM

Asked how to treat Repowise's advisory code-health FAIL on PR #439 (its two
findings live only on a JS report page). Ray:

> do more research on getting this information
> i just setup repowise to index the project: https://www.repowise.dev/s/82747d64d7c1/overview
> they provide an mcp server we might be able to utilize:
> - claude mcp add --transport http repowise https://api.repowise.dev/mcp/ray-manaloto/knowledge-base \ --header "Authorization: Bearer rw_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
> - i added the api key under key name 'REPOWISE_KNOWLEDGE_BASE_API_KEY'
>   - use the fnox/doppler/macos keychain sync we've been using to get the keys as environment variables
>     - MAKE SURE TO NOT LEAK THE KEYS

**Decided in the same step:** the small tooling PR after #439 carries all six
items (#437, #428, #429, #430, #431, the /clear-prep context DENY guard), then
round 3; when `corpus-gate-bundle-0821` is rebased onto main, the two clear-prep
`SKILL.md` copies conflict and **main's version wins** (`0a88507f`+ supersedes
`842a1f9e`).

**Probe at the time (no secret printed):** the key was not yet in this session's
shell env (0 hits; the shell predates the key), `fnox get` resolved 0 bytes in
this process, `mcp2cli` is installed, and the MCP endpoint answers 405 to a
bare GET — live, and expecting the streamable-HTTP POST. Next session: fresh
shell → confirm the variable by COUNT only → `mcp2cli` against the endpoint with
the bearer taken from the environment → read PR #439's findings → decide on a
project-scoped `.mcp.json` entry whose header is `${REPOWISE_KNOWLEDGE_BASE_API_KEY}`
(never the literal; `research-doc-sources.md`: mcp2cli first, register when
frequent).
