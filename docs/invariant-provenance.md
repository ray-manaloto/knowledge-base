# Invariant provenance — the evidence behind `do-not.md`

Moved out of `.claude/rules/do-not.md` on 2026-09-03 (#697), which was at exactly
its 200-line ceiling. Every entry below is the *evidence* for an invariant, not
the invariant itself — the rule still carries the norm, and it is the rule that
binds. Nothing here was refuted; it was re-homed because a rule file is eager
context in every session and this detail is not.

**Why the corrections came with the detail they correct.** Several entries below
record that an earlier version of `do-not.md` said something wrong. A correction
is only load-bearing while the claim it corrects is still present — so detail and
correction moved together. What stayed in the rule is a one-line marker naming
the retraction, which is what stops a refuted ban being re-added.

## Entry 1 — `graphify install`

At the pinned 0.9.53, `dispatch_install_cli` resolves exactly **one** platform —
the CLI arg, or `claude` by default (`install.py:2066-2121`) — and
`_copy_skill_file` writes ONE destination plus ONE `.graphify_version` stamp
(`install.py:172-239`).

🔴 **A corrected claim.** An earlier version of this entry said there was a loop
spraying stamps into every installed platform. There is not. Do not reintroduce
that reading.

The default (`claude`) write is ~84 KB total: `skill.md` (~41 KB) plus its
`references/` sidecar (~43 KB, `install.py:187-190`), and it appends a
`# graphify` H1 to `~/.claude/CLAUDE.md`, creating the file if absent.
`CLAUDE_CONFIG_DIR` is irrelevant either way, since `--project` is denied
outright regardless of any env var.

The denial generalises to every platform subcommand: `graphify antigravity
install` and `graphify codex install --project` are both denied.

## Entry 2a — why `watch` was removed from the ban list

Narrowed 2026-08-01. The banned spelling `graphify --watch` **is not a real
invocation**: `--watch` occurs **0** times in the currently-pinned **0.9.53**
`cli.py` (re-verified 2026-09-03; originally cited against 0.9.31), against a
control arm of **9** occurrences of `--force`. So the probe discriminates, and
the flag genuinely does not exist.

The real form is the subcommand `graphify watch <path>`, whose effect is
repo-local (`<path>/graphify-out/`, never `~/`). The entry's stated rationale —
shared mutable machine state — never described it.

⚠️ **Do not re-add `watch` to entry 2's ban list.** It is still the wrong tool
here, but for a different reason, and that reason is stated in the rule: it
refreshes only that path's scoped sub-graph and cannot update the aggregate
graph. Use `mise run kb-watch`.

## Entry 2b — `hook install`, in full

`graphify.hooks.install()` (`hooks.py:754-763`) resolves the nearest git repo and
calls `_hooks_dir(root)`, which asks `git rev-parse --git-path hooks` and honours
`core.hooksPath` (`hooks.py:491-532`). On an ordinary repo it writes to that
repo's own `.git/hooks`, never `~/` — which is why the entry is partially
misfiled. When `core.hooksPath` names an absolute external directory (e.g.
`~/.githooks`, as Husky sets), `install()` writes THERE instead, which is
genuinely shared state and is the configuration the ban is for.

## Entry 4 — the headline that was wrong

`do-not.md` #4's headline read "any key-detected backend" until 2026-09-03.
That was wrong, and #685 tracks it: `ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL` are
intentionally KEPT (`graphify_env.py:21-24`), and `detect_backend`'s priority
tuple puts `"claude"` third (`llm.py:3547`) — so that one backend genuinely is
key-detected and genuinely is allowed to auto-select. The exception is
deliberate and test-locked; the headline now says so.

## See also

- `.claude/rules/do-not.md` — the invariants themselves.
- `docs/currency/design-notes.md` — the same treatment applied to `CLAUDE.md`'s
  tool-currency section in the same change.

## GitHub repos touched

_None._ Every line above was moved verbatim from this repo's own
`.claude/rules/do-not.md`.
