# Function-hook setup coverage — kb-codex-astra-advisor

**Status: IN PROGRESS.** This file is written incrementally. If it ends here, the
lane was killed before the verdict; everything above this line is still real.

- Started: 2026-09-11
- Commit under review: `175144add286` (local, unpushed) on `chore/drift-sweep-and-fork-rebase-automation`
- Lane: `gpt-6-astra` / `xhigh` / `--sandbox read-only`, via `mise run kb-codex`
- Question: is `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` reliably ON in every execution
  context this repo uses (main session, subagents, codex lanes, worktrees, `-p`,
  agent teams), and what is the plan to make it provably always-on?

## Phase 0 — evidence gathered locally (graph + repo reads)

### P0-1 — the `env` key has its OWN trust rule, and it is NOT the one the task assumed

`sources/claude-code-docs/content/en/docs/claude-code/settings-reference.md:2670-2674`,
§ "When Claude Code applies `env` values", verbatim:

> * From user settings, `--settings`, and managed settings: at startup, and again in the
>   running session when a saved change alters the merged `env`.
> * **From project and local settings: after you trust the workspace, or at startup in
>   `-p` mode, which never shows the trust dialog**, and again when a saved change alters
>   the merged `env`.
> * **Variables Claude Code classifies as safe, such as model selection, timeouts and
>   limits, feature toggles, and telemetry settings: at startup from every settings
>   file**, apart from the variables project and local settings can't set.

Three consequences the brief's premise did not have:

1. The `settings-reference.md:4443` citation in the task is about
   **`extraKnownMarketplaces`** (actually `:4283`), not about `env`. Marketplaces are
   ignored in an untrusted folder *including a `-p` run there*; `env` is explicitly the
   opposite for `-p`. **Two different rules, and the repo needs both** — the flag comes
   from `env`, the guard module will come from a marketplace/plugin registration.
2. **`-p` mode gets the project `env` block** even with no trust dialog. So headless runs
   are covered for the FLAG.
3. 🔴 **UNVERIFIED and decision-deciding**: `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` is, in
   plain reading, a **feature toggle** — the third bullet's category. If the classifier
   counts it safe, the flag applies **at startup from every settings file regardless of
   trust**, and the worktree-trust worry is void for the flag (but NOT for registration).
   "such as" is a non-exhaustive list and the classifier's contents are not in the docs.
   This is cheaply probeable and is the first thing to measure.

### P0-2 — an adjacent live defect found while reading the same section

`settings-reference.md:2681-2683` lists the variables **project and local settings
cannot set**, and it explicitly names:

> Variables that export session content: **`OTEL_LOG_RAW_API_BODIES`** and the detailed
> beta tracing pair …

This repo sets `"OTEL_LOG_RAW_API_BODIES": "file:.agent/telemetry/"` in the **project**
`.claude/settings.json:10`. Per the doc, Claude Code **drops it and logs a warning**
visible only with `claude --debug`. Not this consult's question, but it is the same
failure class (a tracked env key that looks set and is not), it is in the same block as
the function-hooks flag, and it should be a ticket.

### P0-3 🔴 THE VERDICT-DECIDING FACT — the flag travels, the guard does not

`sources/claude-code-docs/content/en/docs/claude-code/permissions.md:631-636`, the table
"What runs before you trust a folder". Its two columns are the two untrusted situations:
*you trusted only a parent folder*, and *`claude -p`/SDK, folder never trusted*.

| repository content | parent-trusted | `-p`/SDK untrusted |
|---|---|---|
| Hooks in settings files, **the `env` block**, helper commands, project skill hooks (`:633`) | **Used** | **Used** |
| `permissions.allow`, `additionalDirectories` (`:634`) | Not used | Not used, warns on stderr |
| Subagent frontmatter hooks, `@skills-dir` plugins, **`extraKnownMarketplaces` from the repository or an `--add-dir` dir** (`:635`) | **Not used, and no dialog is offered** | **Not used** |

**So the two halves of this setup have OPPOSITE trust behaviour:**

- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` arrives via the **`env` block** → row `:633` →
  **Used in both untrusted situations.** The worktree-trust worry in the brief does not
  apply to the flag. Trust does not have to be solved for the flag to be on.
- The guard module will arrive via **`extraKnownMarketplaces` + `enabledPlugins`** (that
  is how `.claude/mods/kb-settings-guard/` gets registered) → row `:635` →
  **not used, and in the parent-trusted case NO DIALOG IS EVEN OFFERED.**

**The resulting failure mode is exactly the one G04 (#757) exists to prevent, and it is
structural rather than the cold-cache race already recorded**: in an untrusted folder —
which every freshly created `git worktree add` path is — **function hooks are ON and the
guard is silently ABSENT.** The engine reports itself healthy; the policy is missing.
A `-p` run in a worktree is the same, with no dialog in either case.

Two more contexts with the same signature, from the same page:

- `permissions.md:645`: **`--bare`** — "Claude Code reads no hooks, skills, custom
  commands, subagents, plugins, or `.mcp.json` servers from the project. **The project's
  `env` block … still apply.**" Flag ON, every module OFF. Same silent shape.
- `permissions.md:646`: a repository's **project settings take precedence** over user
  settings for `disableAllHooks`, so a project file can set it back to `false` — the
  converse also holds: nothing in *user* settings can be relied on to keep our hooks on.

**The remedy the docs name is one we are not allowed to apply.** `permissions.md:640`:
set `projects["<path>"].hasTrustDialogAccepted` to `true` in **`~/.claude.json`**. That
is user-global config, which `.claude/rules/do-not.md` #11 forbids an agent session from
writing. So trusting a new worktree is **Ray's action by hand, or an interactive dialog**
— it can never be automated from inside a session here. Any plan that assumes we can
pre-trust a worktree is unimplementable in this repo.

### P0-4 — the trust store, measured on this machine 2026-09-11

`~/.claude.json` `projects` map (read-only, via `uv run python`):

- **39 project entries; 18 with `hasTrustDialogAccepted: true`, 21 not.**
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base` → **trusted**.
- **A live worktree exists right now and has NO trust entry at all**:
  `git worktree list` shows
  `/private/tmp/claude-501/…/281f4093…/scratchpad/verify-worktree 175144ad (detached HEAD)`,
  and that path is absent from the `projects` map. Absent = untrusted.

So the worktree case is not hypothetical here; it is the current state of this checkout.
Trust is keyed by **absolute path**, so **every** `git worktree add` produces a new,
untrusted path — including worktrees created under the repo tree.

### P0-5 — subagents

`sub-agents.md:265`: subagents "receive only this system prompt plus basic environment
details like the working directory". They are in-process, and `settings-reference.md:2644`
says `env` sets variables "for every session **and for the subprocesses Claude Code
starts from it**" — so an in-process subagent is inside the same process env by
construction. **The flag reaches in-process subagents: VERIFIED by mechanism, not by a
live arm.**

Two carve-outs that are NOT covered:

- `sub-agents.md:693`: a **project** subagent's frontmatter hooks need the trust dialog
  for the folder containing the agent file; `--add-dir` folders "don't inherit the
  workspace's grant" (`:497`). This repo runs with two extra directories (`dotfiles`,
  `claude-code-marketplace`) — neither inherits trust.
- **codex-backed lanes have no function-hook surface at all.** `codex exec` is a
  different binary; `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` means nothing to it. Codex has
  its own hook system with per-hash trust (`.claude/rules/ai-cli-invocation.md`), and
  `--dangerously-bypass-hook-trust` is the only lever this repo owns. Any plan that says
  "function hooks enforce X for all lanes" is **false for every codex lane** — that is a
  KNOWN-NOT, not an unknown.

### P0-6 — two more launch contexts found in this repo's own code

- **`mise run cc` → `python/src/kb_setup/launch.py`** launches an interactive Claude Code
  session in tmux with a **deliberately cleaned environment** (`:1-30` documents three
  ways PATH lies, and `:401` refuses when `claude` does not resolve). The flag is
  unaffected — it comes from the project settings file, not the shell — but this is the
  repo's *canonical* session launcher and is therefore the right place to hang a
  readiness check. It already refuses rather than launching when the environment is
  wrong, so the precedent for "refuse, don't warn" exists in this exact module.
- **`python/src/kb_setup/skillopt_reviewed.py:817-825`** launches a claude with
  `CLAUDE_CONFIG_DIR`, `HOME`, and `XDG_*` all redirected into a throwaway run root, and
  a separate `--project` sandbox. That session reads a **different project directory**,
  so it gets no function hooks and no guard — correctly. It is deliberate isolation, not
  a gap, and a coverage gate must EXEMPT it by name or it will red on a design feature.

### P0-7 — the local settings file cannot be relied on as a second belt

Measured: `.claude/settings.local.json` has an **empty `env` block and no
`extraKnownMarketplaces`**. Everything — the flag and all 11 marketplaces — lives in the
tracked `.claude/settings.json`. That is the right place (it is what makes the flag
travel with a clone and with a worktree checkout), but it means there is exactly ONE
file whose corruption or reversion turns the whole mechanism off, and it is a file a
delegated lane can edit. That is precisely what `.claude/mods/kb-settings-guard/` was
built to prevent — and it is not registered yet, so the window is open right now.

### Lane hygiene — a stale-verdict trap, caught before it bit

`/tmp/kb-codex-astra-advisor-verdict.md` already existed when this lane launched, and
`md5` proves it is **byte-identical to the PREVIOUS round's committed verdict**
(`09966c5832d57c0a2bf86ddd8ae4ac5f` == `docs/research/reports/2026-09-11-function-hooks-astra-verdict-raw.md`).
That earlier verdict answers a different question (tooling/team/shell-parser choice), not
this one. Polling that path naively would have reported it as this consult's answer —
a probe that could only "succeed".

**Discriminator in force for the rest of this run:** the verdict is mine only if the md5
differs from `09966c58…`. Recorded here so a successor can check it too.

Lane verified running from `ps` argv (not the banner, which reports the session model and
is not a valid observable): `uv run kb-setup codex --model gpt-6-astra --effort xhigh
--sandbox read-only --timeout 1800`.

### P0-8 🔴 THE SIMPLEST FAILURE, AND IT IS TRUE RIGHT NOW — a new worktree has no flag AT ALL

Trust is not the first thing that breaks. **The file is.**

- `worktrees.md:144`: "New worktrees **branch from the repository's default branch**, so
  most sessions don't need this setting." (`worktree.baseRef` changes it.)
- Measured just now: `git show origin/main:.claude/settings.json | grep -c
  CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` → **0**. Local `main` → **0**. `HEAD` → **1**.

The flag exists only on the unpushed feature branch `chore/drift-sweep-and-fork-rebase-automation`.
So **today, `claude --worktree <name>` creates a checkout of `main`, where the flag is not
in the file at all** — function hooks are OFF, no trust question is even reached, and the
only observable is a debug-log seat line nobody is reading.

This generalises past the current branch state and is the durable form:

> **The flag is a TRACKED FILE, so its presence is a property of the COMMIT a context has
> checked out — not of the repository.** Any worktree, any `git worktree add` at an older
> base, any PR worktree (`--worktree '#123'`, `worktrees.md:165`), and any bisect
> checkout predating the merge has no flag. "Always enabled" cannot be delivered by a
> tracked file alone, because a tracked file is only present on commits that contain it.

**Consequence for the plan**: a readiness check that runs *in the session* is necessary
but not sufficient — it can only report the absence. If "always on" is the requirement,
the flag needs a source that is not commit-scoped (user settings, or managed settings),
with the tracked project file kept as the belt that makes it travel to a fresh clone.
That is a decision only Ray can make, because `do-not.md` #11 forbids us writing
`~/.claude/settings.json` ourselves.

### P0-9 — how a worktree session actually behaves, from the worktree docs

- `worktrees.md:29` — **interactive `--worktree` FAILS LOUD on an untrusted dir**: "if you
  haven't run Claude in the directory before, run `claude` once there to accept the trust
  dialog, or `--worktree` exits with an error prompting you to. **Non-interactive runs
  with `-p` skip the trust check, so `claude -p --worktree` proceeds without it.**"
  So the dangerous path is specifically `-p --worktree`: it proceeds untrusted and
  silent. Interactive is safe by refusal.
- `worktrees.md:43` — `EnterWorktree` to a path outside `.claude/worktrees/` prompts,
  "because the move takes the session's working directory, write access, and **project
  configuration such as `CLAUDE.md` and settings** to that location". So entering a
  worktree **relocates which project settings apply** — the `/cd` behaviour at
  `settings-reference.md:2674`. A session that starts flagged and enters a worktree
  checked out before the flag landed is UNVERIFIED as to whether the flag survives the
  move (`env` is applied at startup; the `/cd` bullet says new values layer "on top of
  the previous directory's", which suggests it does survive — but that is a reading, not
  an arm).
- `worktrees.md:228` — permission approvals from a worktree save to the **main
  checkout's** `.claude/settings.local.json`. So `settings.local.json` is shared across
  worktrees via the repo root, while `settings.json` is per-checkout. **The two halves of
  the settings pair have different scoping in a worktree**, which is a trap for any plan
  that puts the flag in one and the guard in the other.

### P0-10 🔴 the flag is COMPLETELY UNDOCUMENTED — control-armed

`grep -rn "FUNCTION_HOOKS" sources/claude-code-docs/` → **0 hits across the entire
ingested Claude Code docs corpus.**

**Control arm** (`probes-need-a-control-arm.md` rule 1): the same grep shape for
`CLAUDE_CODE_SUBAGENT_MODEL` in `env-vars.md` → **1 hit**. The probe discriminates, so
the zero is real and not a broken grep.

Combined with the given fact that function hooks have zero CHANGELOG entries through
2.1.268, the flag has **no published compatibility contract at all**. Two consequences
that bear directly on "always enabled":

1. **It can be renamed or removed in any release, silently.** The seat line is the only
   observable, and a removed variable and a disabled feature look identical in it.
2. 🔴 **The growthbook term cuts the wrong way.** The gate is
   `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS ?? growthbook("tengu_plugin_hooks_modules")`.
   If Anthropic ever flips that flag ON by default, the mechanism keeps working **with
   the env var doing nothing** — so a liveness check that only asserts "hooks are seated"
   would stay green through the var's removal, and the repo would discover it only when
   the remote default is later turned back off. A check that proves the FEATURE is on
   does not prove OUR CONFIGURATION is what turned it on. To catch that, the check needs
   an arm that removes the var and confirms the feature goes OFF — which is exactly the
   `env -u CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` arm already run once, and which therefore
   has to be RE-RUN periodically, not once.

### P0-11 — agent teams (this session is one)

`agent-teams.md:104` and `:111`: the default mode is **`"in-process"`** — "all teammates
run inside your main terminal", one process, so teammates share the parent's applied
`env` by construction. `"tmux"`/`"auto"` split-pane mode instead starts **separate
sessions** in new panes; those are new `claude` processes in the same cwd, so they read
the same project settings file and get the flag from there — but they are separate
startups, and each pays the cold-cache plugin-loading behaviour independently.
**UNVERIFIED**: whether a split-pane teammate's plugin load races the same way a cold
clone does.

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set in the same tracked `env` block, so it
carries exactly the same commit-scoped and trust properties as the function-hooks flag —
whatever fixes one fixes both.

### P0-12 🔴 the pre-warmed worker — a process that existed BEFORE your settings did

`agent-view.md:672`, verbatim:

> The supervisor keeps **one pre-warmed worker process** ready so a dispatch from agent
> view or `claude --bg` starts without the delay of a cold launch. When you dispatch, the
> supervisor assigns the pre-warmed worker to your session, **applies that session's
> directory, settings, and credentials to it**, and then starts a replacement.

Set that against the given enable-gate observable, whose wording is process-scoped:
`sec-default@builtin not seated: **hooks modules are off in this process**`.

**The risk**: the pre-warmed worker was launched before the dispatch, therefore before
this session's project `env` was known. If the four-term gate is evaluated at process
start — which "off in this process" strongly suggests — a `--bg` or agent-view session
handed a pre-warmed worker could run with hooks modules off **even though its settings
say to enable them**, and the settings-application step would not retroactively seat
them. `agent-view.md:563` says a background session does read `env` values from project
settings, so the two statements are in tension and only a live arm resolves which wins.

**UNVERIFIED, and it is the highest-value cheap probe available** — higher than the
safe-variable classification, because unlike that one it has a plausible mechanism for a
SILENT wrong answer in a context this repo uses routinely (`--bg`, agent view, `/loop`).
The arm: dispatch `claude --bg` with `--debug-file`, read the seat line, and compare
against a cold-launched foreground session in the same directory. If the pre-warmed
worker seats hooks, this is closed; if not, every background session in this repo is
unguarded and no amount of tracked settings fixes it.

Note the shape: this is the **same class** as the already-recorded cold-plugin-cache race
(marketplace installs after the plugin-loading pass), and both are "the process was
already past the decision point". A readiness check that runs inside the session catches
both, and a check that only inspects files on disk catches neither.

### P0-13 — where a gate would go

`python/src/kb_setup/gates.py:173-181`: `GATE_TASKS` is currently
`("lint", "test", "brain-audit", "eval", "graph-size", "hk-test", "funnel",
"kb-manifest-audit")` — eight ship gates, each a mise task, results written to
`.agent/kb/gates/gates-<sha>.json`. A function-hooks readiness gate added here inherits
the artifact and the "a gate the run never reached is `rc: null`, not a pass" semantics
for free. The comment at `:207` already states the house rule a new gate must satisfy:
*"we did not check" is not "it is safe"*.

**But note what a `kb-gates` entry can and cannot do.** `kb-gates` runs in a *subprocess
of a session that already started*. It can prove the repo's FILES are right; it cannot
prove THIS session seated its hook modules, because the gate process is not that process.
The only in-process evidence is the debug seat line, which requires `--debug-file` at
launch. So readiness (G04) genuinely needs the launcher (`kb_setup.launch`), not just a
gate — which is why `mise run cc` is the right hook point (P0-6).

### P0-14 🔴 starting Claude in a SUBDIRECTORY silently loses the flag

`sources/claude-code-docs/content/en/docs/claude-code/settings.md`, § "Where Claude Code
keeps the local file in a git repository", verbatim:

> Claude Code reads the shared `.claude/settings.json` from the session's **primary
> working directory**, so **to use a file committed at the repository root, start Claude
> Code there.**

and, separately, for the *local* file only:

> If you start Claude Code in a subdirectory of a git repository, it reads and writes
> **that** file at the repository root … **In a worktree, it uses the file at the main
> checkout's root.**

**The two files resolve differently, and the one carrying the flag is the worse of the
two.** `settings.local.json` is found from the repo root (and, in a worktree, from the
*main checkout's* root). `settings.json` — which holds
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` and all 11 marketplaces — is read **only from the
primary working directory**. So:

- `cd python && claude` → **no flag, no marketplaces, no guard.** Silent.
- Any session started from a subdirectory of this repo is unguarded by construction.

This repo's own launcher already knows the adjacent version of this hazard —
`python/src/kb_setup/launch.py:407-413` refuses when `repo_root` has no `mise.toml`, with
the comment *"inside a mise task the CWD is wherever mise was invoked from, NOT the
repo… a wrong root would find no pin, skip the version check, and launch — passing for
the one reason that should refuse hardest."* **That is exactly this failure, one layer
down.** The precedent and the refusal mechanism both already exist in the right module.

**This also reframes the worktree question.** A worktree gets `settings.local.json` from
the main checkout (so anything put *there* does travel), but `settings.json` from its own
checkout (so the flag does not, unless that commit has it — P0-8). Putting the flag in
`settings.local.json` would make it travel to every worktree — **but that file is
gitignored and per-machine, so it would not travel to a fresh clone.** The two properties
are in direct conflict and cannot both be had from project-scoped files. That is the
trade-off the plan has to resolve, and it is the reason user or managed settings keep
coming up as the only complete answer.


---

# PART 2 — THE ASTRA VERDICT (gpt-6-astra, xhigh, read-only, rc 0)

**Lane succeeded.** Not a refusal, not a timeout, not a capacity error.
Verified from `ps` argv, and verified NEW by checksum: the verdict file went from
`09966c5832d57c0a2bf86ddd8ae4ac5f` (stale prior round) to
`d40c1aa3450f5619e59e3c4b2c45558d`, 164 lines.

The raw verdict follows VERBATIM, unedited, per `agent-report-persistence.md` rule 2.

## Headline

> **No — the project setting does not prove "always enabled" across these contexts, and
> Claude function hooks cannot enforce policy inside Codex.** A defensible requirement is:
> *each supported Claude session must demonstrate guard enforcement in its actual worktree
> before receiving protected work, with explicit invalidation conditions.*
>
> The literal requirement remains impossible under the stated constraints: repository
> configuration cannot prevent every alternate launch, higher-priority disable switch, or
> different runtime.

## The deciding risk (Astra's words)

> **The deciding risk is admitting a session as guarded without proving its subagent
> denial path.** A missing module and a broken `agentId` discriminator can both produce
> successful, unguarded operations. Neither flag presence nor a module-load message
> detects both failures.

## On my P0 reading (section B of the prompt)

> **Yes: B establishes the trust asymmetry that makes your failure mode possible.** …
>
> Two qualifications matter:
> - Ignoring `extraKnownMarketplaces` does **not, by itself, prove the guard is absent**.
>   Your excerpts do not settle whether an already-known marketplace, installed cache
>   entry, and effective plugin enablement can supply it. That behavior is **UNVERIFIED**
>   and needs a warm-cache worktree test.
> - "Every untrusted interactive worktree has hooks on" is too strong. A and F leave both
>   pre-trust variable application and effective hook availability unresolved for that case.
>
> The planning conclusion survives both qualifications: **root trust, root registration,
> and root liveness cannot admit a different worktree.**

## Scope caveat Astra attached to its own verdict

> I have not independently verified anything here. **VERIFIED** below means established by
> your supplied measurements; **UNVERIFIED** includes predictions supported only by the
> excerpts.

**No—the project setting does not prove “always enabled” across these contexts, and Claude function hooks cannot enforce policy inside Codex.** A defensible requirement is: *each supported Claude session must demonstrate guard enforcement in its actual worktree before receiving protected work, with explicit invalidation conditions.*

The literal requirement remains impossible under the stated constraints: repository configuration cannot prevent every alternate launch, higher-priority disable switch, or different runtime.

I have not independently verified anything here. **VERIFIED** below means established by your supplied measurements; **UNVERIFIED** includes predictions supported only by the excerpts.

**The deciding risk is admitting a session as guarded without proving its subagent denial path.** A missing module and a broken `agentId` discriminator can both produce successful, unguarded operations. Neither flag presence nor a module-load message detects both failures.

### Coverage

Currently, your guard’s coverage through repository registration is **KNOWN-NOT everywhere**, because registration is deliberately absent. The enforcement column below describes the position **after registration**, without assuming registration resolves the remaining problems.

| Execution context | Flag delivery | Guard enforcement after registration | Reason |
|---|---|---|---|
| Exact in-repo launch used in your successful probe | **VERIFIED** | **UNVERIFIED** for deployed configuration | The armed probe establishes that launch path; production registration remains outstanding. |
| Other fresh, trusted-root interactive launches | **UNVERIFIED** | **UNVERIFIED** | Expected settings behavior, but launch arguments, merged settings, and loader state still matter. |
| Trusted-root `-p` or SDK launches beyond the measured invocation | **UNVERIFIED** | **UNVERIFIED** | Documented delivery does not certify each launcher or its plugin loading. |
| Already-running session when settings change | **UNVERIFIED** | **UNVERIFIED** | Updating process environment does not establish that module loading and seating rerun successfully. |
| Fresh Claude process in an explicitly trusted worktree | **UNVERIFIED** | **UNVERIFIED** | Requires that worktree’s settings/revision, resolved plugin artifact, and effective configuration. Root success is insufficient. |
| Fresh worktree with only ancestor trust | **UNVERIFIED**; `env` documented as used | **UNVERIFIED**, with a documented registration gap | Repository marketplace declarations are ignored despite settings hooks and `env` being used. |
| Never-trusted worktree under `-p`/SDK | **UNVERIFIED**; `env` documented as used | **UNVERIFIED**, with the same gap | Headless operation does not grant repository marketplace trust. |
| Interactive worktree with neither explicit nor qualifying ancestor trust | **UNVERIFIED** | **UNVERIFIED** | Safe-variable classification and the broader hook trust gate prevent asserting “hooks on.” |
| Ordinary in-process Claude subagent | Shares the verified host’s process flag | **UNVERIFIED** | It does not perform a separate process-environment inheritance step. Actual callback delivery and lane classification still need proof. |
| `Agent(isolation:"worktree")` | **UNVERIFIED** | **KNOWN-NOT** for reliable Bash operation under the measured regression | Treat as unsupported while #92533 remains applicable. You report no current use. |
| External/nested Claude process launched by a lane | **UNVERIFIED** | **UNVERIFIED** | This is another startup boundary: environment filtering, cwd, settings, trust, and cache apply again. |
| Codex-backed lane | Raw variable inheritance **UNVERIFIED**; Claude semantics **KNOWN-NOT** | **KNOWN-NOT** | Claude hooks do not receive Codex’s internal tool events. |
| Claude launched with `--bare` | **UNVERIFIED**; project `env` documented as applying | **KNOWN-NOT** for the project module | Flag delivery cannot overcome deliberate exclusion of project plugins. |
| Effective `disableAllHooks` or customization disablement | Raw flag may remain present | **KNOWN-NOT** when the corresponding gate disables hooks | Flag delivery and effective hook availability are different claims. Managed-only operation likewise excludes this repository guard. |
| Session moved with `/cd` | **UNVERIFIED** | **UNVERIFIED** | Environment overlays do not prove that trust, plugin loading, and worktree scope move together. |
| Agents/plugins sourced from the two `--add-dir` directories | **UNVERIFIED** for relevant directory settings | **UNVERIFIED** | Those directories do not inherit the workspace’s trust grant. Test their actual use separately. |
| Direct terminal, CI, or other launcher without a verified Claude parent | **UNVERIFIED** | **UNVERIFIED** for Claude; **KNOWN-NOT** outside Claude | These are additional boundary cases to inventory, not claims that the repo currently uses all of them. |

A resumed session started in a **new process** belongs in the fresh-launch rows. Resuming conversation history does not establish runtime readiness.

### Your P0 reading

**Yes: B establishes the trust asymmetry that makes your failure mode possible.** In the ancestor-trusted and never-trusted headless cases, `env` can apply while repository marketplace declarations are ignored.

Two qualifications matter:

- Ignoring `extraKnownMarketplaces` does **not, by itself, prove the guard is absent**. Your excerpts do not settle whether an already-known marketplace, installed cache entry, and effective plugin enablement can supply it. That behavior is **UNVERIFIED** and needs a warm-cache worktree test.
- “Every untrusted interactive worktree has hooks on” is too strong. A and F leave both pre-trust variable application and effective hook availability unresolved for that case.

The planning conclusion survives both qualifications: **root trust, root registration, and root liveness cannot admit a different worktree.** A new, absent absolute path needs its own trust handling and behavioral evidence. The owner must perform any required trust action; no session should edit the trust store.

### The safe-variable probe

**It merits one bounded investigation, but should not block G04.** Even a positive classification does not make repository marketplace declarations usable before their trust requirements are satisfied.

The cheapest *direct* check is a targeted inspection of the exact binary’s safe-environment predicate **and its project-settings call path**, if identifiable. Record the binary hash and predicate evidence. Whether that predicate is readily identifiable is **UNVERIFIED**; do not replace evidence with a string-presence search.

A cheap behavioral experiment uses three otherwise equivalent, fully untrusted **interactive** launches, observed before accepting trust:

1. No flag from any effective source.
2. Flag supplied only by project `env`.
3. Flag supplied through `--settings`, whose startup application is documented.

Use the existing debug seat observable. A baseline OFF, project ON, explicit-settings ON result establishes pre-trust project delivery for that build and setup. A `-p` experiment cannot distinguish safe classification because ordinary project `env` already applies there.

Crucially:

- **Project OFF, explicit-settings ON:** evidence against project delivery in that tested pre-trust state, assuming the effective inputs were controlled.
- **Both OFF:** inconclusive about classification; another gate may mask both.
- **Baseline ON:** also inconclusive; another source or the fallback may already enable hooks.
- A negative classifier result would **not** refute delivery after trust or in `-p`, nor the successful measurement you already have.

A seat-line experiment measures effective availability; it does not necessarily reveal the internal classifier’s answer.

### Cheapest checks for realistic failures

| Failure | Cheapest meaningful check | Required realistic FAIL arm |
|---|---|---|
| Old worktree revision, missing flag, or changed registration | Parse that worktree’s files and bind evidence to their content hashes | Worktree containing the preceding settings revision |
| Effective override or another enable-gate term disables hooks | Fresh debug seat observation plus behavioral liveness | Launch with documented `--settings '{"disableAllHooks":true}'` |
| Trust/cache causes module absence | Real canary in the exact path and cache state | Never-trusted path; separately, your measured cold-cache first launch |
| Loader rejects the module | Loader diagnostics plus a demonstrably attempted canary | Invalid `.json` import in a disposable module fixture |
| `agentId` contract breaks | Real in-process subagent attempts a valid, guard-prohibited operation | Fixture guard reads `agent_id`; operation must then escape enforcement and make the checker fail |
| Another permission layer creates a misleading denial | Identify this guard’s denial and run the same operation without it | Guard-disabled control must actually complete the operation |
| Preview version changes | Bind readiness to executable identity and rerun the behavioral contract | Upgrade/change the executable; old evidence must be rejected |
| `/cd`, effective settings, or plugin state changes | Invalidate the current session’s readiness evidence | Change a bound input; the workflow must refuse reuse |
| Probe cannot authenticate, trigger the tool, or obtain usable evidence | Explicit execution/evidence accounting | Suppress the actual trigger: result must be `NOT_RUN`, never PASS |

Missing enforcement **after a confirmed valid trigger** is FAIL. Inability to establish that the trigger occurred is `NOT_RUN`/127.

### Ordered setup plan

The commands below are **proposed interfaces**, not existing or executed commands. They should be mise tasks backed by Python under `python/src/kb_setup/`.

1. **G04/#757 — Define and characterize the supported context matrix.**  
   Record executable identity, startup mode, cwd/worktree, settings sources, trust state, and plugin source. Include the bounded safe-variable investigation.

   Proving command:  
   `mise run kb-function-hooks-probe -- characterize`

   Its report must preserve UNKNOWN/UNVERIFIED results. The untrusted-path and explicit-disable arms must prevent an unconditional green result.

2. **G04/#757 — Build the independent checker before relying on registration.**  
   It must observe real Claude operations and distinguish load, invocation, correct subagent classification, and policy denial. Use disposable fixtures containing valid operations, so ordinary tool errors cannot impersonate enforcement.

   Proving command:  
   `mise run kb-function-hooks-probe -- controls`

   Require main-thread permitted behavior, subagent denial, guard-disabled success, and wrong-field failure. The checker must live outside the module whose absence it detects.

3. **G04/#757 — Add tracked registration, then validate worktree resolution.**  
   Check marketplace/plugin consistency and the resolved module hash. Verify that policy applies to the current worktree’s paths; a cached module resolving against the canonical checkout would violate the chosen scope.

   Proving command:  
   `mise run kb-function-hooks-probe -- registration`

   FAIL arm: omit registration or resolve the wrong artifact in a disposable fixture. Do not silently propagate edits into protected, dirty worktrees.

4. **G04/#757 — Establish owner-performed trust and bootstrap, then prove liveness.**  
   The owner accepts trust for each required absolute path and handles any bootstrap operation that would violate #11 if performed by the agent. Where cold-cache installation requires a first session, classify it as bootstrap and assign no protected work to it.

   Proving command:  
   `mise run kb-function-hooks-probe -- liveness --context-matrix`

   Test warm and cold cache, trusted root, trusted worktree, untrusted headless worktree, and ordinary subagents. The observed cold first session must fail admission; a subsequent successful session cannot retroactively certify it.

5. **NEW ticket — Enforce admission in supported Claude launch/worktree workflows.**  
   Registration and a diagnostic command do not ensure that recurring launchers use them. Add Python/mise integration that withholds the work assignment until the **actual launched session** satisfies the challenge.

   Proving command:  
   `mise run kb-claude --verify-admission`

   Test a missing guard and `--bare`: neither may receive the protected assignment. **Same-process interactive admission feasibility is UNVERIFIED.** Demonstrate it before promising coverage; a successful probe subprocess cannot certify another main session.

   This is workflow enforcement, not a guarantee against arbitrary direct launches. Later runtime changes also require explicit invalidation; periodic checking is detection, not uninterrupted prevention.

6. **G05/#758 — Encode the direction rule using demonstrated capabilities.**  
   Require the supported admission path, define worktree scope, reject unsupported isolation, and distinguish Claude protection from Codex protection. Include agents originating in the extra directories.

   Proving command:  
   `mise run kb-function-hooks-probe -- routing-contract`

   FAIL arms must exercise actual routing through unsupported or unready contexts. A rule-text search is insufficient proof.

7. **NEW ticket — Establish equivalent enforcement for Codex lanes.**  
   Your conclusion is correct: Claude function hooks cannot enforce Codex’s internal operations. They can constrain the **outer launch**, which is a useful but different boundary.

   Proving command, once a Codex-native mechanism is selected:  
   `mise run kb-codex-guard-probe -- controls`

   Its minimum control changes a trusted hook’s content/hash and verifies that silent skipping cannot result in admission. Owner-managed trust remains an option; agent-written global trust does not. Until demonstrated, equivalent Codex coverage stays **UNVERIFIED**, while Claude-hook coverage of Codex stays **KNOWN-NOT**.

8. **NEW ticket — Resolve the telemetry configuration discrepancy separately.**  
   Your excerpts establish that project settings are not an effective source for `OTEL_LOG_RAW_API_BODIES`. The running value and warning are **UNVERIFIED**: another permitted source could supply it.

   Proving command:  
   `mise run kb-telemetry-config-check`

   The prohibited project placement should fail the configuration check. Do not make function-hook readiness depend on raw API logging or `$.ui.log` under `-p`.

For delivery, integrate the relevant checks into existing `mise run check` and `mise run kb-gates`. Extend the gate evidence with context-specific results: **a SHA-only receipt cannot certify different worktrees, binaries, trust states, or live processes.**

### What I would not do

- **Register the plugin and call the requirement complete.** That leaves the measured cold-start gap and unresolved worktree behavior.
- **Use an environment echo, seating message, firing counter, or telemetry event as enforcement proof.** None establishes the subagent denial path.
- **Automate trust-store edits or agent acceptance of the owner’s trust decision.** That contradicts your constraint.
- **Default to `--dangerously-bypass-hook-trust`.** It removes a Codex trust boundary; it does not prove the intended hook ran correctly.
- **Use `Agent(isolation:"worktree")` while the supplied regression applies.**
- **Make safe-variable classification or raw API telemetry a prerequisite for registration/readiness work.** Neither resolves guard admission.
- **Claim continuous enforcement from startup tests.** With mutable settings and an unreleased loader, that stronger guarantee needs an independent enforcement boundary or a narrower requirement.
---

# PART 3 — SYNTHESIS, LIMITS, AND WHAT ASTRA NEVER SAW

## 🔴 The most important limit of this consult

**The Astra prompt was sealed after P0-7. Findings P0-8 through P0-14 were made while the
lane was already running, so Astra never saw them and its verdict does not account for
them.** Specifically unreviewed by the lane:

| finding | why it matters that Astra did not see it |
|---|---|
| **P0-8** the flag is absent from `main`, so every new worktree lacks the FILE | Astra's worktree rows all reason about *trust*; the live failure today is simpler and upstream of trust. Its plan step 3 ("validate worktree resolution") is still right, but its premise is incomplete. |
| **P0-12** the pre-warmed supervisor worker (`agent-view.md:672`) | A process that existed before the session's settings did. Astra has no row for it; its matrix has no "background/agent-view session" line at all. |
| **P0-14** `settings.json` resolves from the **primary working directory**, not the repo root | Astra's "Other fresh, trusted-root interactive launches" row assumes root launches. A subdirectory launch is a silent total loss and is not in its matrix. |
| **P0-10** the flag is wholly undocumented + the growthbook masking argument | Astra's step 7 mentions preview version changes, but not that a remote default flip would keep a naive liveness check green while our config stopped mattering. |

Treat Astra's coverage table as **sound on trust and enforcement semantics, and incomplete
on delivery**. The two halves compose; neither is the whole answer.

## Where Astra corrected ME — accept both

1. **"Ignoring `extraKnownMarketplaces` does not, by itself, prove the guard is absent."**
   Correct, and I overstated it in P0-3. A warm plugin cache may already hold the
   marketplace from a previous trusted session, in which case the plugin can still load.
   The honest statement is *registration is not delivered by the repository in an
   untrusted folder*, not *the guard is absent*. **Needs a warm-cache worktree test.**
2. **"Every untrusted interactive worktree has hooks on" is too strong.** Also correct:
   the `env` row being "Used" establishes delivery, not that the other three terms of the
   enable gate hold. I conflated delivery with effectiveness.

Both corrections make the picture *less* certain, not more — which is the right direction
for an unreleased feature.

## Where I would go further than Astra

Astra says the literal "always enabled" requirement is impossible. I agree, and the
**reason is sharper than it states**: the flag is a tracked file (P0-8) read from the
primary working directory (P0-14), so its presence is a property of *the commit and the
cwd of each context*, not of the repository. No in-session check can fix that; it can only
report it. If Ray wants "always", the flag needs a non-commit-scoped source — user or
managed settings — with the tracked file kept as the belt that makes it travel to a fresh
clone. **`do-not.md` #11 means only Ray can make that change.** That is the one question
that should go back to him.

## What I could NOT verify

- **The codex call itself: SUCCEEDED.** rc 0, new checksum, 164 lines, not a refusal.
  Astra's own caveat stands: it verified nothing independently and reasoned only from the
  excerpts I pasted, because the lane was `--sandbox read-only` with no repo access.
- **The safe-variable classification** (`settings-reference.md:2672`, third bullet) —
  UNVERIFIED. Astra rates it worth one bounded investigation but says it must not block
  G04, and warns a seat-line experiment measures *effective availability*, not the
  classifier's answer. I agree and did not run it.
- **The pre-warmed worker hypothesis (P0-12)** — UNVERIFIED, no arm run.
- **Whether the flag survives `EnterWorktree` / `/cd`** — UNVERIFIED, reasoning only.
- **Whether a split-pane agent-teams teammate races the cold plugin cache** — UNVERIFIED.
- **Whether `OTEL_LOG_RAW_API_BODIES` is actually being dropped here** — I read the doc
  (`:2681-2683`) but did NOT run `claude --debug` to see the warning. Astra flags the same
  gap: "The running value and warning are UNVERIFIED: another permitted source could
  supply it."
- **I ran no live Claude launches at all.** Every context grade in Part 1 is from the
  ingested docs plus repo state, not from an armed session. The one armed measurement in
  play is the team lead's pre-existing `env -u` probe.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — the ingested
  documentation corpus under `sources/claude-code-docs/` supplied every doc citation in
  Part 1; issue #92533 was supplied to me as a given and not re-read.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this
  repo: `.claude/settings.json`, `.claude/mods/kb-settings-guard/`,
  `python/src/kb_setup/launch.py`, `gates.py`, `skillopt_reviewed.py`, and issue #757.

_Report complete. Lane: gpt-6-astra/xhigh via `mise run kb-codex`, rc 0._
