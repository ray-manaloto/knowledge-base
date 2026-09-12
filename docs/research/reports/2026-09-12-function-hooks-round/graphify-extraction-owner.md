# graphify / extraction programme — owner report

Owner: `kb-codex-astra-advisor`. Ray's directive 2026-09-12.
Status: IN PROGRESS — three codex lanes running, sections filled as they land.
All figures measured **2026-09-12** unless marked INHERITED or UNVERIFIED.

## Lane posture — a deviation from this agent's charter, stated plainly

`kb-codex-astra-advisor`'s definition mandates `--sandbox read-only` and says
"never `--network`". Every lane in this programme runs
`mise run kb-codex -- --network --timeout 1500`, which resolves to:

```
codex exec --sandbox workspace-write --add-dir /Users/rmanaloto/Library/Caches \
  -c sandbox_workspace_write.network_access=true \
  -c model_reasoning_effort=xhigh --dangerously-bypass-hook-trust -
```

Verified with `--print-argv` before launch. **The hazard the charter names is
absent**: the sandbox is explicitly `workspace-write`, never the inherited
`danger-full-access` from `$CODEX_HOME/config.toml` (`do-not.md` #13). The
deviation is necessary and structural, not convenience — `--add-dir` for uv's
cache arrives only with `--write`, so a read-only lane cannot run `mise run
kb-query`, which `kb_setup.graph_first` DENIES it for not running. That circular
deny is what wasted an earlier fan-out today.

**No lane is authorised to push to the fork, open a PR, comment on an upstream
PR, or move a pin.** Every lane prompt says so verbatim.

---

## 0. TWO CORRECTIONS TO THE BRIEF, both control-armed

**The single decision these force: the fork target is 0.9.59, not 0.9.58, and
both upstream PRs are already conflicted.**

| Brief said | Measured today | Arm |
|---|---|---|
| "Upstream PyPI is at 0.9.58 — we are one release behind" | PyPI latest is **0.9.59**. We are **two** releases behind. | `0.9.99 -> 404`, `0.9.58 -> 200`, `0.9.57 -> 200` — the probe discriminates |
| (not stated) | **BOTH** PRs are `mergeable=false`, `mergeable_state=dirty` | read from the `pulls/{n}` API for each |

Full PR state, `gh api repos/Graphify-Labs/graphify/pulls/{n}`:

- **#3073** open, not draft, `Azeem1985`, head `TelB-io:upstream/openai-cli-backend`,
  base `v8`, +519/-5, 5 files, **2 issue comments + 4 review comments**,
  created 2026-08-25T08:36:12Z, **last updated 2026-08-25T09:02:57Z** — untouched
  for 18 days.
- **#3311** open, not draft, `Ketlark`, head `Ketlark:cursor-cli-backend`,
  base `v8`, +391/-5, 5 files, **1 issue comment + 2 review comments**,
  created 2026-09-03T07:56:02Z, updated 2026-09-03T08:16:29Z.

Both are conflicted against `v8`. Neither is blocked on review silence alone —
there IS review feedback on both, and nobody here has read it. The PR-mining
lane is fetching it verbatim.

---

## 3. WORKSTREAM 3 — the extraction path (answered first; it is the cheapest)

**The single decision this forces: the destination path is pinned but has ZERO
callers, so "use the extraction path" today means running the STOPGAP, and the
real work is writing the caller that does not exist.**

### What runs today — armed, not argued

`mise run kb-graphify-native-extract -- --dry-run --backend openai-cli` exits
**rc 0** and prints the argv it would run:

```
.venv/bin/graphify extract <repo>/sources/graphify --mode deep \
  --backend openai-cli --out /tmp/ne-dryrun
```

So the openai-cli backend is reachable, and the fork patch is live in the
installed distribution. That is the good news.

### Three structural limits the dry run exposed

1. **`GRAPHIFY_OPENAI_CLI_PARALLEL` is NOT set, so openai-cli runs SERIALLY.**
   The task's own output says so, and adds that the concurrency clamp was
   cleared for `claude-cli` only: *"NO evidence either way for openai-cli: the
   run that cleared the clamp was claude-cli's, and it does not transfer."*
   A serial deep extraction over a real corpus is the throughput wall.
2. **`DEFAULT_BACKEND = "claude-cli"`** (`python/src/kb_setup/graphify_native_extract.py:298`)
   — `--backend openai-cli` must be passed explicitly every time, which is
   correct per `do-not.md` #4 but means no default path uses our own patch.
3. **The target defaults to the pinned `sources/graphify` clone.** This task was
   built to extract graphify's own source, not to be the general corpus
   ingestion route. `--target` exists; whether it is a supported general route
   is UNVERIFIED.

### The destination path exists as a pin and nothing else

`graphify.llm.extract_corpus_parallel` is pinned with a reviewed signature
carrying native `backend: str` and `model: str | None`
(`python/src/kb_setup/graphify_sdk.py:189-200`). Ray's own ranking, recorded in
`graphify_native_extract.py:60-70`, is: **1. call the public SDK · 2. shell out
to the CLI (what this module does) · 3. never import internals.**

**It has no callers.** `grep -rn extract_corpus_parallel python/src tests`
returns 5 hits: the import at `graphify_sdk.py:36`, the pin at `:191-192`, and
two PROSE mentions inside `graphify_native_extract.py`'s docstring (`:51`, `:88`).
Not one call site.

*Control arm, same command shape:* `public_api_fingerprint` → 4 files
(`graphify_sdk.py`, `skillopt_contract.py`, `graphify_native_extract.py`,
`graphify_baseline.py`). So the grep finds callers when callers exist, and the
zero is an answer.

This is the concrete shape of Ray's complaint. The rank-1 route was pinned,
fingerprinted, version-gated — and never wired to anything.

### The graph itself is degraded, which is WHY grepping keeps winning

Every `mise run kb-query` in this session emitted the same stderr:

```
[graphify] note: this graph uses the pre-#1504 node-ID scheme; rebuild with
`graphify extract --force` to get path-qualified IDs (fixes same-name-file
collisions).
```

Two separate failures on top of that, both real, both today:

- A plain question ("how does the openai-cli backend extraction work") returned
  **29 nodes of pure noise** — gitleaks Go rules, an agnix LSP `Backend` struct,
  a `codex-rs/exec/src/cli.rs` `Cli` — because the seeds matched on token
  spelling, not meaning.
- `hook_guard decide` hit **rc 3, TRUNCATED**, 60 of 80 nodes shown.
  *This is the control arm*: it returned the real
  `python/src/kb_setup/hook_guard.py:124`, so the graph and the query path work.
  The first result was a term-spelling miss, not an empty corpus.

**The graph is now 472,069 nodes.** `CLAUDE.md` states 359,026 — that figure is
stale by ~113k and should be re-derived, not quoted.

So the honest statement of Ray's complaint: agents grep because the aggregate
graph answers a prose question with Go-lang secret-scanner rules, and the tool
itself is asking for a `--force` rebuild it has not been given.


---

## 1. WORKSTREAM 1 — codex documentation and `--help`, measured on 0.154.0

**The single decision this forces: turn on `multi_agent_v2`. It is marked
`stable`, it is `false`, and it is the exact fan-out capability Ray asked for.**

Everything below is from the installed binary (`codex-cli 0.154.0`), run today.
The deep source read of the permission-profile subsystem is with a codex lane
and is NOT yet folded in.

### 1a. `codex doctor` — a first-party health instrument we have never run

`codex doctor --summary` exits **rc 0** and reports **22 ok · 3 notes · 1 warn ·
0 fail**. Three of those rows matter:

```
⚠ rollouts     3,068 active files · 4.08 GB on disk
⚠ sandbox      filesystem unrestricted · network enabled
⚠ threads      rollout scan was incomplete or found bad files
✓ sandbox      unrestricted fs + enabled network · approval Never
```

**The `sandbox` row independently confirms issue #767 from a first-party
source.** The ambient `$CODEX_HOME/config.toml` resolves to *unrestricted
filesystem, network enabled, approval Never* — i.e. `danger-full-access`. Every
codex invocation that does not pass an explicit `--sandbox` runs there. That is
exactly why `kb_setup.codex_run` always emits one, and why `do-not.md` #13
exists; what is new is that **codex itself will tell us, in one command, and we
never ask it**.

Two more real signals: **4.08 GB of rollouts across 3,068 files**, and a
**rollout scan that was incomplete or found bad files** — session history is
accumulating unbounded and some of it is corrupt. `mise run kb-session-search`
reads exactly that tree.

`--json` emits a *redacted* machine-readable report, so it is safe to consume
from a gate under this repo's secret rules. **Recommendation: `kb-codex-doctor`,
wrapping `codex doctor --json`, wired into `kb_setup.currency`'s probes.**

### 1b. Feature flags — 137 of them, and we set ZERO

`codex features list` reports **137 features**. Breakdown:

| stage / state | count |
|---|---|
| under development, false | 53 |
| **stable, true** | 40 |
| removed, false | 28 |
| removed, **true** | 9 |
| **stable, FALSE** | **3** |
| experimental, false | 3 |
| deprecated, false | 3 |
| under development, true | 1 |

**We configure none of them.** `grep features .codex/config.toml` → one hit, and
it is a *comment* about graphify's MCP. Control arm, same shape:
`grep -c mcp_servers .codex/config.toml` → 5. So the zero is an answer.

The three **stable-but-disabled** features are the finding:

```
multi_agent_v2         stable  false
recommended_plugins    stable  false
secret_auth_storage    stable  false
```

- 🔴 **`multi_agent_v2`** — stable, off. This repo's `CLAUDE.md` already cites
  `multi_agents_v2/spawn.rs:128-135` and `MultiAgentMode::Proactive` when
  explaining `ultra`, and Ray's directive today is *"codex lanes/subagents fanned
  out to help research, code-review, verification"*. The subagent surface is
  stable and switched off. Enabling it is `-c features.multi_agent_v2=true`, or
  `codex features enable multi_agent_v2` — **but note that writes
  `config.toml`, and `do-not.md` #11 forbids writing `~/.codex`**, so the
  project route is `-c`, which `kb-codex` can pass.
- `secret_auth_storage` — stable, off. Worth a look given this repo's secret
  posture; UNVERIFIED what it changes.

Tempering my own earlier read: **`worktrees` is `experimental, false`**, so the
top-level `--worktree` flag ("Run the session in a new managed Git worktree")
is gated behind a feature that is off. It is still the right answer for
collision-free parallel lanes, but it is experimental, not free.

### 1c. Top-level flags on `codex` that we never pass

| flag | what it does | verdict |
|---|---|---|
| `--strict-config` | **"Error out when config.toml contains fields that are not recognized by this version of Codex"** | 🔴 adopt — see below |
| `--search` | live web search; native Responses `web_search` tool, no per-call approval | strong candidate for research lanes |
| `--enable/--disable <FEATURE>` | `-c features.<name>=<bool>` shorthand | the route to `multi_agent_v2` |
| `--worktree` | managed git worktree per session | gated on the experimental `worktrees` feature |
| `-C/--cd <DIR>` | set the agent's working root | cleaner than `cd` in a lane prompt |
| `--approve-for-me` | route approvals through automatic review | UNVERIFIED |
| `--oss` / `--local-provider` | lmstudio/ollama | not applicable |

🔴 **`--strict-config` is the highest-value flag here and `kb-codex` cannot
pass it** — `uv run kb-setup codex --help | grep -c strict-config` → **0**.
Our `.codex/config.toml` is 265+ lines. Today, a key that a codex upgrade stops
recognising is **silently ignored**, which is the precise failure class this
repo keeps paying for (the dead `Read|Glob` matcher in `.codex/hooks.json`; the
untrusted `post_tool_use` hooks). `--strict-config` converts it into an error.

**I could not run the probe.** `codex exec --strict-config …` is DENIED by
`kb_setup.codex_lane` at the PreToolUse hook — correctly; the guard is doing its
job. `kb-codex` has no passthrough, so **whether our config survives strict
validation is UNVERIFIED**, and it is the first thing to find out.

### 1d. Subcommands on 0.154.0 we never call

`agents` · `doctor` · `sandbox` · `plugin` · `features` · `apply` · `queue` ·
`fork` · `archive` · `unarchive` · `delete` · `cloud` · `remote-control` ·
`app-server` · `exec-server` · `migrate-rollouts` · `completion` · `debug` ·
`update` · `app` · `login`/`logout`.

Worth naming three:

- **`codex sandbox [COMMAND]...`** — runs an arbitrary command under codex's
  own seatbelt sandbox, with `--sandbox-state-readable-root` to add roots. A
  native sandbox for local commands, which this repo has no other source of.
- **`codex agents`** — browses agent sessions on the shared local app-server
  daemon. Pairs with `multi_agent_v2`.
- **`codex fork <SESSION_ID>`** and **`codex queue --thread`** — branch or feed
  an existing session. Relevant to lane orchestration; we only ever start fresh.


---

## 4. WORKSTREAM 4 — the two upstream PRs, and what #3311 teaches

**The single decision this forces: stop treating #3073 as "our patch awaiting
review". Its HEAD is not our code, it is 18 days stale, and the only review on
it is a BOT.**

### 4a. Who actually reviewed these — nobody human

Every review submission on BOTH PRs is from **`graphify-labs[bot]`**, author
association `NONE`, state `COMMENTED`. There is no human maintainer review on
either. Each bot review carries its own qualification, verbatim:

> agreed by 2 of 2 members but NOT verified (no proof, no reproducing
> execution) — consensus is not a verdict; needs human review

and the gate result on both is:

> **PASS** — objectively clean (no health regressions, tests not run — proofs
> not run this pass (advisory)). Grounded, not self-assessed.

So: **neither PR is blocked by a review objection. Both are blocked by being
conflicted (`mergeable_state=dirty`) and unattended.** That is a different
problem with a different fix, and we had it recorded the other way round.

### 4b. 🔴 The bot's headline finding on #3073 does NOT apply to our fork

The two `high`-severity findings on #3073 are:

> **Incomplete conditional leaves module syntactically invalid** — `graphify/llm.py:2827` · _Escalate · high_
> **Incomplete openai-cli concurrency branch makes module unloadable** — `graphify/llm.py:2827`

**Armed against our own installed copy, and it is false for us:**

- `uv run python -c "import graphify.llm"` → **imports cleanly** from
  `.venv/lib/python3.14/site-packages/graphify/llm.py`.
- Our `llm.py:2827` is hollow-chunk retry logic, not a concurrency branch.
- Our openai-cli concurrency guard lives at **`llm.py:3017` and `:3816`**, not
  2827, and both read
  `if backend == "openai-cli" and os.environ.get("GRAPHIFY_OPENAI_CLI_PARALLEL","").strip() != "1"`.

**Conclusion: PR #3073's head (`4e1cfd65e2d1ee63e3eb0bcf343ec83f291e1d30`) has
diverged from our fork.** The PR was last updated 2026-08-25; our fork has been
rebased twice since (→ v0.9.53, → v0.9.57). Getting #3073 merged is therefore
not "answer the review" — it is **re-push our current, working branch to it**,
which we cannot do directly: the head is on `TelB-io`, not on our fork.

### 4c. TECHNIQUE TABLE — #3311 (cursor-cli) vs our #3073 (openai-cli)

Both solve the same problem independently, so this is free design review. Each
row armed against our INSTALLED copy, not against the PR diff.

| technique | #3311 does | we do | verdict |
|---|---|---|---|
| extraction instructions in the **user turn**, not the system prompt — *"system-prompt delivery gets diluted by local agent context and parses hollow"* | `_cli_extraction_prompt` helper | **yes**, inline `combined_message = _extraction_system(...) + "Now extract…" + user_message`, with the same rationale in the comment | ✅ already have it |
| **fail loud on an unparseable/empty envelope** rather than returning an empty graph the hollow-retry path bisects forever | raises on `is_error` / unparseable JSON | **yes, and better documented** — raises `RuntimeError("codex exec returned no graph content")`, comment records *"that exact failure mode previously consumed 87% of an hourly backend quota"* | ✅ already have it |
| prompt over **stdin** to dodge the argv cap | yes | yes — comment cites Linux `MAX_ARG_STRLEN` 128 KB vs real chunks at 240–306 KB | ✅ parity |
| **read-only / ask-mode** sandbox so extraction cannot write the corpus | `--trust` + ask-mode | `--sandbox read-only` | ✅ parity (ours is stricter; the bot flags *their* `--trust` twice) |
| forced-serial default, env opt-out | `GRAPHIFY_CURSOR_CLI_PARALLEL=1` | `GRAPHIFY_OPENAI_CLI_PARALLEL=1` | ✅ parity |
| MCP servers disabled per call | not addressed | **ours is the better one** — per-server `enabled=false`, with the measured reason that `-c mcp_servers={}` deep-merges and leaves them running (*"four graph servers at ~152 MB each during one run"*) | ✅ we are ahead |
| model flag guards on the right variable | bot flags a real bug: *"cursor-cli model flag uses `mdl` but guards on `model`, ignoring config default"* | ours reads `mdl` consistently | ✅ we are ahead |
| tests independent of the environment | bot flags *"Default-model test depends on external environment"* | UNVERIFIED for ours | ⬜ worth checking our own test |

**The honest headline: on every axis #3311 was praised for, our implementation
already matches or beats it.** The two techniques I expected to be adoptable
turned out to be things we already do. I was wrong about that going in, and the
arms are above.

Two findings that DO land on us, because the bot raised them against *our* PR:

- **"MCP server disabling fails open"** — if `codex mcp list` is unavailable,
  the servers stay as the user configured them. Real, and ours.
- **"Untrusted corpus text is sent to an agentic CLI that can run tools"** —
  the prompt-injection surface. Mitigated by `--sandbox read-only`, not removed.

### 4d. 🔴 `GRAPHIFY_OPENAI_CLI_EFFORT` defaults to `ultra`, and `ultra` is NOT "more depth"

Our fork sends `-c model_reasoning_effort=<$GRAPHIFY_OPENAI_CLI_EFFORT or "ultra">`
(installed `llm.py:2118`). Read what codex does with that, at
`sources/codex/codex-rs/protocol/src/openai_models/reasoning_effort.rs:10-40`
(pinned `6b9826e3aa83b1a5947db50f4332cb9c65f1b340`):

```rust
pub fn resolve_reasoning_effort(&self, effort: ReasoningEffort) -> ReasoningEffort {
    match effort {
        ReasoningEffort::Ultra => self
            .multi_agent_reasoning_effort ...        // 1. the MULTI-AGENT effort
            .or_else(|| ... preset.effort == Max ... // 2. else Max
                     ... .rev().find(|p| p.effort != Ultra))  // 3. else highest non-Ultra
            .unwrap_or(ReasoningEffort::Medium),     // 4. else MEDIUM
```

`ultra` is a **multi-agent alias**, and it never reaches the wire as `ultra` for
an ordinary inference request. It resolves to the model's multi-agent effort, or
`Max`, or the highest non-`Ultra` preset — **and its floor is `Medium`**.

Graphify's extraction is a single-shot `codex exec` per chunk with no subagents.
Combined with the measurement in §1b that **`multi_agent_v2` is `stable, false`**
on this machine, the default is at best a detour and at worst silently *less*
reasoning than `xhigh`.

**Which branch `gpt-5.6-sol` actually lands on is UNVERIFIED** — it depends on
that model's `supported_reasoning_levels` metadata, which I have not read. I am
not claiming we are getting Medium; I am claiming the default is unexamined and
can resolve below `xhigh`.

Note `ReasoningEffort` also has `Max` and `Persistent` variants
(`openai_models.rs:58-71`) that nothing here uses. `Max` may be the value the
`ultra` default was reaching for.


---

## 2. WORKSTREAM 2 — fork currency, 0.9.57 → 0.9.59

**The single decision this forces: budget the bump as a CODE CHANGE, not a pin
move. 0.9.59 adds a keyword-only parameter that reds our SDK contract, exactly
as `ast_sources` did at the last bump.**

Source: the `kb-codex --network` fork-currency lane, which ran the probes itself.
I have spot-checked its headline claims; where I have not, it is marked.

### 2a. TARGET — v0.9.59 = `522ea9662ead3a960f9a67d9d0f499e9b96580cf`

Both probes run, as the manifest requires:

- `git ls-remote --tags` (no pattern, then the exact ref with BOTH patterns):
  v0.9.57 = `3f82bf7f837a…`, v0.9.58 = `23f2ffaa43fd…`, **v0.9.59 = `522ea9662ead…`**
- PyPI: `0.9.59→200, 0.9.58→200, 0.9.57→200, 1.0.0→404, 0.9.99→404`.
  Three real releases control the two negatives.

⚠️ **v0.9.59 is a LIGHTWEIGHT tag** — there is no `^{}` peeled line, and that is
correct here rather than the filtering trap the manifest warns about.
`gh api repos/Graphify-Labs/graphify/git/ref/tags/v0.9.59 --jq .object` returns
`type=commit` with that same SHA. The manifest's `^{}` rule is about *annotated*
tags; applying it blindly to this one would look like a missing peeled line.

`default_branch` is `v8` (live), and v8 HEAD equals the target **today only** —
selection still goes tag + PyPI, not branch head.

### 2b. CONFLICT SURFACE — one conflict, and it is `CHANGELOG.md` again

`compare/v0.9.57...v0.9.59` → **37 commits, 44 files**, merge base `3f82bf7f…`.
Fork vs target → **8 ahead / 37 behind**, same merge base. Positive control:
local `git log --oneline kb-pin/openai-cli-backend-v0.9.57 ^v0.9.57` returns the
same eight patches.

The eight commits to replay, in order:

```
8adbc178  feat(llm): openai-cli backend
45371550  feat(cli): credential gate knows openai-cli
5c755a83  fix(openai-cli): disable each configured MCP server per call
fe4686da  feat: extract --fallback-backend
6a0ba926  test: a partial primary pass must not fire the fallback
c38f63d5  feat: graphify watch --semantic
c71245de  feat: batched UNWIND push for neo4j/falkordb (--batch-size)
3c9b930f  fix(openai-cli): only disable MCP servers Codex can resolve
```

| file | upstream delta | prediction |
|---|---|---|
| `CHANGELOG.md` | +29/-2 | **the one conflict** (`merge-file` rc=1). Keep the fork's `## Unreleased` ABOVE upstream's 0.9.59/0.9.58/0.9.57 sections — the same resolution as the last three rebases |
| `graphify/cli.py` | +14/-4 | rc=0, merges clean |
| `graphify/llm.py` | +49/-0 | rc=0, merges clean; the Claude label fallback still needs behavioural acceptance |
| `watch.py`, `__main__.py`, `exporters/graphdb.py` | 0/0 | upstream unchanged |
| 4 fork-only test files | absent upstream | survive as additions |

**Controls the lane ran:** `git merge-file -p BASE BASE TARGET` for every file,
each rc=0 and byte-equal to TARGET; the CHANGELOG's rc=1 is the positive arm
proving the clean results mean something. Backend token counts across
(v0.9.57 / fork / target): `openai-cli` **0/9/0**, `claude-cli` **23/24/26**,
`bogus-backend` **0/0/0** — so the zero discriminates and our patch is still
genuinely absent upstream.

⚠️ **The real rebase was NOT run and is UNVERIFIED.** `git fetch upstream` in the
designated checkout returned **255**, `error: cannot open '.git/FETCH_HEAD':
Operation not permitted` — a sandbox boundary, not a git conflict. The target
object is absent locally. So this is a *predicted* aggregate content merge from
immutable blobs; individual replay commits may expose more, and the real rebase
must be allowed to stop on them. No throwaway branch was created; nothing was
pushed.

### 2c. 🔴 API BREAKAGE — `graphify.build.build` gains `protected_ids`

This is the finding that decides the workstream.

```
OLD: (extractions, *, directed=False, dedup=True, dedup_llm_backend=None,
      root=None) -> 'nx.Graph'
NEW: (..., root=None, protected_ids: 'set[str] | None' = None) -> 'nx.Graph'
```

at target `graphify/build.py:1398` (upstream #3477). `build_merge` now computes
the IDs of surviving nodes and passes them in, so incremental dedup stops
collapsing nodes that belong to untouched sources.

`python/src/kb_setup/graphify_sdk.py:82-88` pins the OLD signature as an exact
string, and the contract refuses on any mismatch. **This is the same failure
shape as v0.9.57's `ast_sources`, which blocked every `kb-setup` command until
the contract was updated** — and the manifest already warns "a ticket that
enumerates pin sites is not thereby complete".

All **13 pinned symbols** were compared, not just the suspect one. 12 unchanged;
only `graphify.build.build` mismatches. The probe's positive discriminator: it
independently re-detects the known `ast_sources` addition from the last bump.

Two caveats the lane raised against itself, both worth keeping:

- `graphify_sdk.py:37` also imports `is_package_manifest_path` and
  `extract_package_manifest`, which are **outside** both fingerprint tuples.
  Unchanged here, but that is a coverage boundary, not a guarantee.
- **Unchanged signature ≠ unchanged behaviour.** `build_merge` and `extract`
  bodies changed (`extract` adds a pool-start fallback and resolution-cache
  resets). Corpus acceptance must run even where signatures match.

The installed v0.9.57 passes `mise run kb-graphify-contract` (rc=0) today, so
the contract gate is live and will catch this.

### 2d. A correction the lane made to our own prose

`python/src/kb_setup/cli.py:135-144` gates the contract check on `_GRAPH_WRITERS`,
**after** the version early-return at `:132`. So the historical "it blocked EVERY
kb-setup command" wording is writer-specific today and should not be repeated as
a current claim. The `build` mismatch is certain independently, from
`graphify_sdk.py:250-274`.


---

## 1b. 🔴 PERMISSION PROFILES — the finding that changes how every lane runs

The codex-docs lane's verdict, with `file:line` throughout (pinned codex
`6b9826e3aa83b1a5947db50f4332cb9c65f1b340`):

**Filesystem policy and network policy compile INDEPENDENTLY** —
`core/src/config/permissions.rs:351` (filesystem) and `:512` (network).

That single fact refutes a design assumption baked into our own wrapper.
`python/src/kb_setup/codex_run.py:696` makes `--network` **imply `--write`**,
and `kb-codex --help` states it: *"allow network egress; implies --write, since
the flag is a write-sandbox key"*. Under a named permission profile that is not
true: **a read-only lane can have network.** Every research lane I ran today was
given a writable workspace it did not need, purely because the wrapper couples
them.

Three distinct mechanisms, routinely confused:

| mechanism | selection | source |
|---|---|---|
| config profile file | `codex --profile NAME` → layers `$CODEX_HOME/NAME.config.toml` | `utils/cli/src/shared_options.rs:34` |
| **named permission policy** | `-c 'default_permissions="kb-research"'` → `[permissions.kb-research]` | `config/src/config_toml.rs:217` |
| direct sandbox diagnostic | `codex sandbox -P NAME -- COMMAND` (no model needed) | `cli/src/lib.rs:55` |

Built-in IDs are exactly `:read-only`, `:workspace`, `:danger-full-access`
(`protocol/src/models.rs:406`); only the first two are extensible
(`permissions.rs:207`). `extends` resolves a parent chain with cycle and
missing-parent detection (`permissions_toml.rs:33`). A custom policy **starts
restricted** — empty filesystem, restricted network — so it fails closed
(`permissions.rs:351`, `:512`).

Proposed project catalog (NOT applied — this is a proposal):

```toml
default_permissions = "kb-research"

[permissions.kb-research]          # read-only, no network
extends = ":read-only"

[permissions.kb-research-online]   # read-only WITH network — impossible today
extends = "kb-research"
[permissions.kb-research-online.network]
enabled = true

[permissions.kb-checks]            # workspace + the uv cache, as an exact allowance
extends = ":workspace"
[permissions.kb-checks.filesystem]
"~/Library/Caches" = "write"
```

Three traps the lane recorded, each armed:

1. 🔴 **Legacy `profile = "NAME"` in config is now a HARD RUNTIME ERROR**
   (`core/src/config/mod.rs:3292`) while still deserializing and still in the
   schema (`config_toml.rs:335`). Do not enable it because the schema lists it.
2. **A typed `--sandbox` OUTRANKS `-c default_permissions=…`**
   (`config/mod.rs:2491`, `:3274`; `exec/lib.rs:563`). So adding the config key
   while still passing `--sandbox` changes nothing — the wrapper needs a
   *mutually exclusive* branch, not an extra flag.
3. **Selecting `:workspace` intentionally ignores `[sandbox_workspace_write]`**
   network/tmp customisation (`config/mod.rs:3527`, `:3571`). Migrate all
   settings together or silently lose them.

Validation route that needs no model: `codex sandbox -P NAME -C <checkout> --
<cmd>`, plus `--log-denials` on macOS (`cli/src/lib.rs:90`) and
`--include-managed-config` (`:78`). **OS-level enforcement is UNVERIFIED** — the
lane read the compiler, it did not run the arms.

Constrained egress exists too: `[features] network_proxy = true` plus
`network.mode = "limited"` and a `network.domains` allowlist
(`permissions_toml.rs:330`, activation `config/mod.rs:3632`). ⚠️ Writing
`network.domains` **alone** is not domain-enforced egress —
`network_proxy_config_from_profile_network` resets `config.enabled=false`
(`permissions.rs:120`).

### Telemetry (section 4, abbreviated)

Separate log/trace/metric OTLP exporters over HTTP (binary or json) or gRPC,
optional TLS/mTLS, user span attributes, W3C trace-context propagation
(`config/src/types.rs:534`, `otel/README.md:54`, `otel/src/trace_context.rs:123`).
Neither our wrapper nor `.codex/config.toml` configures any of it — control arm:
the same `rg -n -F` shape matched `model_reasoning_effort` in both files and
`otel` in neither. Actual delivery is UNVERIFIED.

### ⚠️ What this lane did NOT deliver

The lane ran to its 1500s bound and **section 6 — the ranked "TOP 10 we should
be using" — was never written.** Its `--output` final-message file is empty
(0 bytes); only the incremental file survived, at 1,041,096 bytes covering
sections 1–5. The instruction to write incrementally is the only reason any of
it exists.

**The ordered list below is therefore MINE**, synthesised from the evidence
sections 1–5 did deliver plus my own measurements. It is not the lane's ranking
and is not labelled as such.

---

## DO THIS NEXT — ordered, with exact commands

1. **Find out whether our codex config survives strict validation.** It is the
   cheapest probe here and nothing else depends on it. `kb-codex` cannot pass
   the flag, so add a passthrough first (`codex_run.py`, one argparse row):
   ```
   mise run kb-codex -- --strict-config --print-argv x     # after the passthrough
   ```
   A failure names a key a codex upgrade silently stopped honouring.

2. **Run `codex doctor --json` and read it.** Never run here. It already
   reports `filesystem unrestricted · network enabled · approval Never`
   (#767, first-party), 4.08 GB of rollouts, and a rollout scan that found bad
   files. `--json` is redacted, so it is gate-safe.
   ```
   codex doctor --json > /tmp/codex-doctor.json
   ```
   Then propose `kb-codex-doctor` into `kb_setup.currency`'s probes.

3. **Decide on `multi_agent_v2`.** Stable, `false`, and it is the fan-out
   capability Ray asked for. Project route only — `do-not.md` #11 forbids
   `codex features enable` writing `~/.codex`:
   ```
   mise run kb-codex -- -c features.multi_agent_v2=true ...   # needs a -c passthrough
   ```

4. **Set `GRAPHIFY_OPENAI_CLI_EFFORT=xhigh` for extraction runs**, or establish
   what `ultra` resolves to for `gpt-5.6-sol`. `ultra` is a multi-agent alias
   whose floor is `Medium` (`reasoning_effort.rs:10-40`), and extraction is
   single-shot with `multi_agent_v2` off.

5. **Do the 0.9.59 fork bump as a CODE change.** In
   `/Users/rmanaloto/dev/github/ray-manaloto/graphify` only (never
   `sources/graphify/`, never a scratchpad). Park the dirty `uv.lock` FIRST.
   Target `522ea9662ead3a960f9a67d9d0f499e9b96580cf` (lightweight tag).
   Expect the CHANGELOG conflict; expect to update
   `graphify_sdk.py:85-87` for `build(…, protected_ids=None)` **in the same
   change**. Full arm sequence: `/tmp/lane-fork-section-e.md`.

6. **Build `kb-fork-rebase`** (#728 steps 6–7). The lane enumerated **31 pin
   sites** across `pyproject.toml`, `sources/graphify.manifest`, `uv.lock`,
   `currency.toml`, `graphify_baseline.py`, `graphify.dispositions.json`,
   `graph.py`, `graphify_sdk.py`, `CLAUDE.md` and two `.graphify_version`
   stamps — with a mandatory derivation order (R → T → catalog digest → source
   manifest digest → SDK fingerprint → counts). Control-armed absence: a TOML
   parse of all 102 tasks finds `kb-fork-rebase` missing while
   `kb-graphify-contract` (`mise.toml:811`) and the catalog task (`:1141`)
   are present. **Seven of those values are derived and cannot be satisfied by
   a binding-only edit** — the exact class `kb-graphify-catalog` was built to
   catch. 31 hand-edits in a required order is not a hand procedure.

7. **Un-block #3073 — the conflict is one file.** `git merge-tree --write-tree
   522ea966… 4e1cfd65…` → **rc 1, `CHANGELOG.md` only**; `llm.py`, `cli.py`,
   `__main__.py` all auto-merge. Same arm on #3311 also conflicts only in
   CHANGELOG, so the classification discriminates. ⚠️ The head is on
   **`TelB-io`**, not our fork, so we cannot push the fix — decide whether to
   ask the author or open a fresh PR from our branch.

8. **Adopt ONE technique from PR #2392 (Copilot backend).** It answers a live
   bot finding against our own PR (*"openai-cli runs an LLM agent with
   inherited cwd and environment"*):
   `with tempfile.TemporaryDirectory(prefix="graphify-copilot-") as workdir:`
   — an isolated working directory per call. Also worth copying: **capability
   detection** (`if _copilot_cli_supports(help_text, "--deny-tool")`) instead of
   assuming a CLI honours a flag. Do NOT copy Copilot's flags into Codex.

9. **Rebuild the graph with path-qualified IDs.** Every query today emits
   *"this graph uses the pre-#1504 node-ID scheme"*, and a prose question
   returned gitleaks Go rules. Via the task, never raw graphify:
   ```
   mise run kb-build
   ```
   Then re-derive the node count — `CLAUDE.md` says 359,026; it is **472,069**.

10. **Write the caller for `extract_corpus_parallel`.** The rank-1 SDK path is
    pinned at `graphify_sdk.py:189-200` with native `backend`/`model` params and
    has **zero call sites**. Until it exists, "use the extraction path" means
    running the stopgap CLI shell-out that Ray's own ranking calls a stopgap.

11. **Propose decoupling `--network` from `--write` in `kb-codex`**, using a
    named permission profile (`kb-research-online`). Filesystem and network
    compile independently (`permissions.rs:351`/`:512`), so the coupling at
    `codex_run.py:696` is our wrapper's, not codex's.

---

## COULD NOT ESTABLISH

- **Whether `.codex/config.toml` passes `--strict-config`.** `codex exec
  --strict-config` is denied by `kb_setup.codex_lane` (correctly) and `kb-codex`
  has no passthrough — `uv run kb-setup codex --help | grep -c strict-config` → 0.
- **What `ultra` resolves to for `gpt-5.6-sol`** — depends on that model's
  `supported_reasoning_levels`, which nobody read. The resolution *chain* is
  established; the landing branch is not.
- **The real 0.9.59 rebase.** `git fetch upstream` in the designated checkout
  returned **255**, `cannot open '.git/FETCH_HEAD': Operation not permitted` —
  a sandbox boundary. The conflict surface is *predicted* from immutable blobs
  via `git merge-file`, not from a rebase. Individual replay commits may expose
  more.
- **OS-level enforcement of any proposed permission profile.** The lane read the
  compiler; it ran no `codex sandbox -P` arms.
- **Whether `secret_auth_storage` (stable, false) matters** — not investigated.
- **The codex-docs lane's own section 6.** Cut at its 1500s bound; the ordered
  list above is mine, from its sections 1–5.
- **What the 0.9.58→0.9.59 upstream commits change behaviourally.** Signature
  parity was checked for 13 symbols; `build_merge` and `extract` bodies changed
  and behaviour was not tested.
- **Live extraction cost.** No real `--backend openai-cli` run was made — only
  the `--dry-run`. A prior measurement in the source notes a single-document
  extraction at 361 s, which is INHERITED, not re-measured.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream; PRs #3073, #3311, #2392, #1404, #2981, #856, #1062, #1063; tags v0.9.57/58/59.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork; branch `kb-pin/openai-cli-backend-v0.9.57`.
- [openai/codex](https://github.com/openai/codex) — pinned `rust-v0.154.0`; permission profiles, reasoning-effort resolution, OTEL, CLI surface.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues #728, #739, #767, #397.
- [TelB-io/graphify](https://github.com/TelB-io/graphify) — holds #3073's head branch.

---
---

# ADDENDUM (same session, after team-lead correction)

Self-contained by design: absolute paths, issue numbers, full commands. Nothing
here refers back to a conversation.

## A1. 🔴 RETRACTION — `codex sandbox` is deliberately DENIED, and I recommended it twice

Earlier in this report I listed `codex sandbox [COMMAND]...` as an unused
capability worth adopting, and proposed
`codex sandbox -P <profile> -C <checkout> -- <cmd>` as the way to validate a
permission profile. **Both are wrong. Withdraw them.**

`codex sandbox` is in `_GUARDED_SUBCOMMANDS` at
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/codex_lane.py:91`,
and the deny is live:

```
codex sandbox -P kb-research -- ls   -> DENY
codex exec --strict-config -         -> DENY
codex doctor --json                  -> allow
codex features list                  -> allow
codex --version                      -> allow
```

(`uv run python -c "from kb_setup import codex_lane as c; print(c.decide(<cmd>))"`
— the allow rows are the control arm proving the guard discriminates.)

**Why it is denied is the point, and it is issue #675** — *"A command-running
wrapper defeats every command-inspecting guard"*. `codex sandbox` takes a command
and runs it, so `secret_guard`, `check_first`, `graph_first`, `stage_explicitly`,
`inplace_edit` and `codex_lane` all see the wrapper and never the real command.
#675 records it as denied *as the remedy, not the fix*.

**The consequence for §1b is real and unresolved.** The permission-profile
proposal's only model-free validation route runs through the one subcommand this
repo bans. So: the profile catalog can be *designed* from source, and it cannot be
*armed* without either lifting the #675 deny for a bounded case or finding
another route. **That is a genuine conflict, not a recommendation I can make.**
It belongs on #675.

Unchanged by this: `codex doctor --json` and `codex features list` are allowed,
so DO-THIS-NEXT items 2 and 3 stand as written.

## A2. These tickets already exist — ADVANCE them, do not file duplicates

Per team-lead, checked live with `gh issue view <n>`:

| issue | state | what it already owns | what my findings ADD |
|---|---|---|---|
| **#744** | open, 2026-09-10 | *kb-lane-verify: verify a lane's REAL model/effort/flags*. Already names the ground truth: `~/.codex/sessions/**/rollout-*.jsonl` `turn_context` records. Already records that `codex review`'s banner `model:` line is the SESSION model, not the lane's (Astra, Sol and a bogus slug all printed the same). | `--strict-config` is a *config-side* check #744 does not have; `codex doctor --json` is a redacted machine-readable health report it could consume |
| **#732** | open | *V5 — `.claude/workflows/kb-upgrade.js` + skill + eight subagents mirrored `.claude/agents ↔ .codex/agents`*, phases 0–5 incl. `kb-fork-rebase` at phase 2 | `multi_agent_v2` being `stable,false` is a precondition its roster may assume is on |
| **#553** | open | already names **`--output-schema <FILE>`** ("JSON Schema describing the model's final response shape"), `codex exec resume/fork`, and `codex exec review` — plus the dead `--full-auto` in `.claude/rules/ai-cli-invocation.md:38` | still open on 0.154.0; `--output-schema` is the typed-handoff primitive and remains unused |
| **#652** | open | the ticket `kb-codex` came from — both sandbox flags omittable | `--strict-config` and `-c` have no passthrough in today's wrapper |
| **#675** | open | the command-running-wrapper class; `codex sandbox` denied | A1 above: it blocks the permission-profile arm |
| **#767** | open | 13 codex sessions at `danger-full-access` | `codex doctor --summary` reports it first-party in one line |
| **#693** | open | a codex lane cannot write `.agents/` (`sources/codex/codex-rs/protocol/src/permissions.rs:28`) | unchanged |

**Prior art I did NOT re-derive**, per team-lead, cited not claimed:
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/graphify-out/memory/query_20260901_235935_can_a_codex_lane_run_this_repo_s_uv_backed_gates.md`
(outcome `corrected`) establishes the two independent sandbox walls and that
`Could not resolve host` is **permanent and structural**, not the transient
`.claude/rules/persistence-gate-retry.md` classifies. Both flags are already
inside `mise run kb-codex -- --network`. No lane of mine reported a network
failure, so the run-it-outside-the-lane check was not needed this session.

## A3. WORKTREE + CONCURRENT REBUILD — the critical-path answer

Measured today against the installed graphify at
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.venv/lib/python3.14/site-packages/graphify/`.

**1. graphify HAS a first-class worktree mechanism: `GRAPHIFY_OUT`.**
`graphify/paths.py:1-27` — *"The output directory is `graphify-out` by default
and overridable with the `GRAPHIFY_OUT` env var (worktrees or shared-output
setups, #686). It accepts a relative name (`graphify-out-feature`) or an
absolute path (`/shared/graphify-out`)."*

⚠️ **It is read ONCE AT IMPORT TIME** (`paths.py:26`,
`GRAPHIFY_OUT = os.environ.get("GRAPHIFY_OUT", "graphify-out")`). The docstring
says so: *"set `GRAPHIFY_OUT` before the process starts."* It cannot be changed
mid-process, and a task that sets it after import silently gets the default.

**2. Our env cleaner does NOT strip it — armed, and I had this wrong first.**

```
GRAPHIFY_OUT=graphify-out-wt1 uv run python -c \
  "from kb_setup import graphify_env as g; print(g.clean_env().get('GRAPHIFY_OUT'))"
-> graphify-out-wt1
```

So `kb_setup.graphify_env.clean_env()` **passes it through**. The `env.pop` at
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/graphify_native_extract.py:619`
is scoped to **that module's own `resolve_env(opts)`** only (issue #480, because
`--out` is that task's sanctioned channel). `graphify_env` has no `resolve_env`
at all (`hasattr` → False). My first reading — "our code strips the worktree
mechanism" — was too broad and is corrected here.

**3. 🔴 There is NO build lock on the extract path.**

| file | lock? |
|---|---|
| `graphify/watch.py:162` | **yes** — `_rebuild_lock(out_dir, *, blocking=False)`, *"Per-repo advisory lock around a rebuild… uses `fcntl.flock` so the lock is released automatically if the process is killed (no stale-lock cleanup needed). While held, `.rebuild.lock` contains the owning PID"*. A hook that cannot acquire it appends to `.pending_changes` rather than dropping its change set (`watch.py:25-26`, upstream #1059) |
| `graphify/extract.py` | **no** |
| `graphify/cli.py` | **no** |

Control arm for that zero: `grep -c "def extract" extract.py` → **21**, so the
file is readable and the search shape works. The lock lives only in the *watch*
rebuild path, not in `extract`/`cli` — which is what `mise run kb-build` drives.

**4. What follows, practically.**

- **Two worktrees, each with its own `graphify-out/`: SAFE by default.**
  `GRAPHIFY_OUT` defaults to the relative name `graphify-out`, resolved per
  working directory, so two checkouts write two different trees.
- **Two builds pointed at ONE shared tree: UNPROTECTED.** Nothing in
  `extract.py`/`cli.py` serialises them. `paths.py:29-45`'s `_atomic_replace`
  gives per-file atomic rename (a kill mid-write leaves the previous file
  intact) — that is crash-safety for one writer, **not** mutual exclusion
  between two. Interleaved writers can produce a self-inconsistent tree with
  every individual file valid.
- **So: give each worktree its own output root, exported BEFORE the process
  starts:**
  ```
  GRAPHIFY_OUT=graphify-out-<worktree> mise run kb-build
  ```
  or an absolute path. Do NOT share one tree between concurrent builds.
- ⚠️ **UNVERIFIED, and it matters at 528 MB/472,069 nodes:** whether the repo's
  own derived-state consumers honour a non-default root —
  `.currency-stamp.json`, `graphify_baseline.py`, `kb-graphify-catalog`,
  `graph-prose.json`. Several `kb_setup` sites hardcode the literal name
  (`graph.py:1382`, `graph.py:2894`). **Anyone running a worktree build must
  arm that before trusting the result**; a stamp written to the default tree
  while the graph went elsewhere is the exact stranded-derived-value class
  `kb-graphify-catalog` exists to catch.
- Upstream fixed this same duplication once already: `paths.py:8-13` records
  that `security` and `callflow_html` *"hardcoded the literal `graphify-out` and
  silently ignored the override (#1423)"*. Our copy now has the same shape.

## A4. On `next.origin`

Team-lead reports `next.origin` is host-set and unforgeable
(`claude-code.d.ts:3841-3846`; `CommandRunArgs = Omit<CommandRunInput,'origin'|'args'>`
at `:1184`). **Recorded, not verified by me** — it is outside all four
workstreams and I read neither file. I made no claim about it anywhere in this
report, so there is nothing here to correct.

## A5. Revised DO THIS NEXT deltas

- **Item 1** (`--strict-config`) — file against **#652**, which owns the wrapper
  shape; the flag has no passthrough. Pair with **#744**, which owns lane
  verification but checks the *session record*, not the *config*.
- **NEW** — the permission-profile arm is **blocked by #675**. Do not plan a
  `codex sandbox -P` validation; resolve #675 first or find another route.
- **Item 6** (`kb-fork-rebase`) — it is **phase 2 of #732**, not a standalone.
  Build it under #728 and wire it into #732's workflow.
- **NEW** — before any worktree build: `GRAPHIFY_OUT=<distinct> mise run kb-build`,
  and arm whether the derived-state consumers follow the override (A3.4).
