# graph-first as a Claude Code function hook — feasibility, design, and the honest verdict

**Lane:** `kb-codex-astra-advisor`. The empirical work below was run by the
Claude-side agent; the `gpt-6-astra` codex consult is recorded in §6, including
whether it ran at all.
**Date:** 2026-09-12.
**Subject:** Ray's directive, verbatim — *"have kb-codex-astra-advisor also research
how we can use claude function hooks to enforce graphify first as that is a great
candidate for this"*.

---

## THE HEADLINE, in one sentence

**VIABLE — and the blocker that was expected to kill it does not apply, because
`anthropics/claude-code#92533` is specific to the `tool.call` EVENT on Bash, not
to Bash hooks generally: a `tool.check` hook on Bash fires, denies with our own
reason text, and leaves `Agent(isolation: "worktree")` subagents working
normally — all three measured on 2.1.269 today.**

---

## Environment pinned (every claim below is against these exact artifacts)

| Artifact | Value | How established |
|---|---|---|
| Claude Code CLI | **2.1.269** | `claude --version` |
| Binary | `/Users/rmanaloto/.local/share/claude/versions/2.1.269`, Mach-O 64-bit arm64, 203150240 bytes, mtime Sep 11 14:29 | `file(1)` + `ls -la` |
| Type declarations | `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/types/claude-code.d.ts`, **9192 lines**, first line `// Written by Claude Code 2.1.269.` | `head -20`, `wc -l` |
| Guard under discussion | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/graph_first.py`, **460 lines** | `wc -l` |
| Existing mod | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/mods/kb-settings-guard/hooks/register.ts` | read in full |
| Upstream blocker | `anthropics/claude-code#92533`, **state `open`, 0 comments**, created 2026-09-06T18:56:14Z, labels `bug, has repro, platform:macos, area:bash, area:hooks, area:agents` | `gh api repos/anthropics/claude-code/issues/92533` |

The declarations file is the **same version as the installed binary** (2.1.269),
so it is not a stale artifact — but note it was generated on this machine and
generated declarations are environment-dependent.

### The function-hook flag is present in the installed binary — control-armed

```
grep -ac "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"   <binary> -> 4
grep -ac "CLAUDE_CODE_ENABLE_BOGUS_CONTROL_XYZ" <binary> -> 0      # control arm
grep -ac "isolation context for this agent was lost" <binary> -> 2
```

The bogus control returns 0 from the same command shape against the same file, so
the probe discriminates. The isolation-loss error string #92533 reports is **still
present in 2.1.269**.

`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS: "1"` is already set in
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/settings.json`.

---

## What `graph_first` is today, precisely

Wired in `.claude/settings.json` as the **second** `PreToolUse` entry matching
`Bash|Grep`:

```json
{ "matcher": "Bash|Grep",
  "hooks": [ { "type": "command",
               "command": "uv run --project \"${CLAUDE_PROJECT_DIR:-.}/python\" kb-setup hookguard",
               "timeout": 20 } ] }
```

🔴 **There is a FIRST `Bash|Grep` entry too** — graphify's own
`"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/graphify" hook-guard search`, timeout 15.
That is the *warning* layer whose 0-of-19 compliance bought the DENY, and it is
still live: its `MANDATORY … you MUST run graphify query` banner appeared on
essentially every Bash call made while producing this report. **Every Bash and
Grep call in this repo therefore pays TWO subprocess spawns today**, one of which
is a warning nobody acts on. That is a material input to the cost side of §4.

### Its session state — the part a function hook has to replace

`graph_first.py` keys the marker on the **session id from the PreToolUse payload**:

- `_state_path()` → `<repo>/.agent/state/graph-first/<session_id>.queried`
- `_SAFE_SESSION_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")` — validated before
  interpolation; an id that fails is treated as absent, which **allows**.
- `has_queried()` — *"Unreadable state means YES (allow)."*
- `note_query()` fires when the query is **issued**, not when it succeeds —
  deliberately optimistic.
- The session id **is** the invalidation rule; no TTL, by design.

What counts as the unblocking query (`_GRAPH_QUERY`):

```python
re.compile(r"\bmise\s+run\s+kb-query\b|\bgraphify\s+(?:explain|path|god-nodes)\b")
```

---

## 1. VIABLE OR NOT — the #92533 arms

### The harness

Throwaway repo at `<scratch>/fh/repo` (`git init` + one empty commit), minimal
plugins beside it, the issue's own prompt:

```
Do not modify files. Spawn ONE subagent via the Agent tool with isolation:
"worktree" and subagent_type general-purpose, with this prompt: "Run `pwd` once
via Bash. Report verbatim the output or the full error message. Do not retry."
Then paste the subagent report verbatim and stop.
```

```bash
claude -p "$P" --output-format json --allowedTools "Agent,Bash" \
  --plugin-dir "$S/plug-<arm>" \
  --settings '{"env":{"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS":"1"}}'
```

`$S` = `/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/3b921834-9839-450d-aee1-0b72d7549b50/scratchpad/fh`

### Round 1 — passthrough arms

| arm | registration | isolation-lost errors | worktree reached? |
|---|---|---|---|
| `none` | no plugin at all | 0 | **YES** — `worktrees/agent-a07179cd37a03f12f` |
| `bash` | `tool.call` on `Bash`, passthrough | **1** | **NO — refused** |
| `grep` | `tool.call` on `Grep`, passthrough | 0 | YES — `worktrees/agent-a5aad3d0b74cda8c7` |
| `start` | `session.start`, passthrough | 0 | YES |
| `result` | `tool.result` on `Bash` | 0 | **VOID — see below** |
| `check` | `tool.check` on `Bash`, passthrough | 0 | YES |

**#92533 still reproduces on 2.1.269.** The `bash` arm's refusal, verbatim from
the run's JSON:

> The working-directory isolation context for this agent was lost, so this
> command would run in the parent session's directory instead of this agent's
> worktree (`…/fh/repo/.claude/worktrees/agent-a157bdd35ffc2e982`). Refusing to
> run it. Retry the command; if this keeps failing, report that worktree
> isolation was lost.

The `none` arm is the positive control: an OK outcome is producible by this
probe, so a refusal elsewhere is a real difference.

### 🔴 Two probe failures caught before they reached a conclusion

**(a) The first pass of these arms never ran.** Four arms reported "rc=1" one
second apart. stderr:

```
error: unknown option '--plugin-dir /private/tmp/.../plug-bash'
```

The shell is **zsh, which does not word-split an unquoted variable**, so a `$PD`
holding `--plugin-dir <path>` arrived as one option *name*. Reported as-is that
would have read "the Bash arm fails" — a false confirmation pointing the same way
as the issue. Control arm on the flag itself: `--plugin-dir` is in `claude --help`
(*"Load a plugin from a directory or .zip … repeatable"*). The table above is the
corrected re-run.

**(b) The `result` arm is VOID and is discarded.** `tool.result` **is not a
declared event.** The declarations carry 74 event keys; the `tool.*` family is
`tool.call`, `tool.check`, `tool.describe`, `tool.list`, `tool.register` — no
`tool.result`. That hook never registered, so its "clean" reading measures
nothing. **A non-existent event and a safe event are indistinguishable to a
passthrough probe.** That is what forced round 2.

### Round 2 — proving the survivors actually FIRE

A passthrough that is clean may be clean because it never ran. So: denying
variants, armed on the main thread.

| arm | registration | outcome |
|---|---|---|
| **A** | `tool.check` on `Bash`, denies a sentinel command | **DENIED**, verbatim: `Permission to use Bash denied by plugin plug-checkdeny: KBPROBE_TOOLCHECK_FIRED: denied by the tool.check hook.` |
| **B** | `tool.call` on `Grep`, denies a sentinel pattern | **DENIED**, verbatim: `KBPROBE_GREPCALL_FIRED: denied by the tool.call hook on Grep.` |
| **C** | the SAME proven-live plugin from A + worktree subagent running `pwd` | **0 isolation-lost; subagent printed `…/repo/.claude/worktrees/agent-a655d95834dc2afc7`** |

Arm A proves the hook is live, that its verdict is honoured, and that **our own
reason text reaches the model**. Arm C then runs that same proven-live hook
against the worktree case and it is clean. C is the load-bearing arm: it is the
only one where "the hook fired" and "isolation survived" are true of the *same*
registration.

### 🔴 What this corrects in the repo's own written invariant

`.claude/mods/kb-settings-guard/hooks/register.ts` states:

> *"🔴 THE REAL `anthropics/claude-code#92533` INVARIANT IS "NEVER BASH", NOT
> "use literal matchers"."*

That is **broader than the evidence requires**. The measured invariant is
**"never `tool.call` on Bash"**. `tool.check` on Bash is a live, denying,
worktree-safe registration. The existing wording would forbid the one design that
works. (The mod's own `WRITE_TOOLS` never names Bash, so nothing about its
current behaviour is wrong — only the stated reason is over-broad.)

---

## 2. THE DESIGN

### The event: `tool.check`, matched per-tool on `Bash` and `Grep`

`claude-code.d.ts:2427-2438`:

> *"Fires when the engine decides whether a tool call may run, **after** the
> `tool.call` and PreToolUse hooks and before the mode settles an ask. `next(e)`
> resolves to the engine's verdict (rules, mode, the tool's own check,
> PreToolUse's decision); return any `{ decision }`."*

`ToolCheckResult` (~`:7220`):

> *"`allow` runs the tool; `ask` puts it to the mode's decider; **`deny` refuses
> it, the reason the model's error**."*

`ToolCheckInput` (`:7202`) carries what the guard needs:

- `tool: string` — *"As the model names it (`Bash`, `mcp__server__tool`); the key
  a matcher narrows on."*
- `input: unknown` — *"The tool's arguments as the permission decision reads them
  (`{ command }` for Bash, `{ file_path, … }` for the file tools)."*

That `{ command }` is the same string `graph_first.decide()` already parses, so
the port is a **transport change, not a logic change**.

### What it reads to decide "a graph query has run this session"

🔴 **`$.store` is the trap.** `claude-code.d.ts:2086-2109`:

> *"This plugin's own key-value store, **kept between sessions** and hot reloads;
> values are JSON data. A JSON file of the plugin's own under the user's Claude
> Code configuration directory."*
> *"Rejects a function, a cycle, or a store over 4 MiB of JSON text in all."*

The entire invalidation rule of `graph_first` is that **a new session starts
blocked again**. A naive `$.store.set("queried", true)` would unblock the check
**permanently, for every future session**, and the config directory may sync
across machines. Any `$.store` design MUST key on `$.session.id()`
(`claude-code.d.ts:4059`, `:4270`) and prune — and the pruning becomes
load-bearing against that 4 MiB cap.

Three candidate state mechanisms, with their failure directions:

| mechanism | on failure | verdict |
|---|---|---|
| `$.store` keyed by `$.session.id()` + prune | stale keys accumulate → 4 MiB cap → `set` rejects → hook throws → **SKIPPED = fail OPEN** | workable, but the pruning is safety-critical |
| module-level `Set<sessionId>` | hot reload drops it → session re-blocks → **fail CLOSED** | safest direction; costs one redundant query per reload |
| `$.fs` read of the existing `.agent/state/graph-first/<id>.queried` | shares state with the Python guard; no second source of truth | **the interesting middle path** — see §4 |

The third deserves emphasis: it keeps ONE state format and ONE definition of "has
queried", which is the same discipline `hook_guard.decide()` already uses by being
shared between the runtime guard and `skill_lint`.

### The deny text

The present `_REASON` is already well-formed and should port near-verbatim — it
names the measurement, the remedy, and the non-denied cases. The one thing a
function hook can do better: it has `e.input.command` in hand at compose time, so
it can interpolate a **topic-appropriate** query instead of a generic one. That
is the single genuine capability gain (see §4).

---

## 3. WHAT IT BUYS OVER THE PRESENT HOOK — the honest accounting

**What it genuinely buys:**

1. **Two subprocess spawns per Bash/Grep call become zero.** Today every such
   call pays `uv run …` (timeout 20) *plus* graphify's `.venv/bin/graphify`
   (timeout 15). In-process handlers remove both spawns from the hot path. This
   is the only *measurable* win, and I have **not** measured it — see §5.
2. **A contextual deny.** The hook sees the actual command and could name the
   query worth running rather than a generic `mise run kb-query -- "{question}"`.
   This is the part of Ray's framing that is real: the remedy can be *targeted*.
3. **`next.origin` is host-set and unforgeable**, so a future refinement ("lanes
   are held to this, the main thread is not", or the reverse) has a trustworthy
   basis that a subprocess hook reading JSON does not have.

**What it costs:**

1. **A second implementation of one policy.** 460 lines of tested Python with a
   documented ambiguity doctrine, re-expressed in a sandboxed TypeScript
   environment with no Node and no imports beyond relative paths. The parsing is
   the hard part and it is exactly the part with the measured false-positive
   history (`rg 'src/utils'`, `git commit -m "docs && rg decide"`).
2. **Silent skip on error.** The present hook's failure is a non-zero rc a human
   sees; a function hook that throws is **skipped and the tool runs**.
3. **An early-access API**, declared *"this surface may change between releases
   without notice"*, in a subsystem with a large open bug surface.
4. **`tool.check` has essentially no real-world usage.** GitHub code search for
   `on("tool.check"` → **2 total results**, one of which is this machine's own
   generated declarations file in `ray-manaloto/dotfiles`. Control arm:
   `"tool.call" language:typescript` → **29,248**, `incomplete_results: false`, so
   the index works and discriminates. We would be first users.

**My recommendation, stated plainly:** the strongest version of this is **not** a
rewrite. It is a **thin `tool.check` transport in front of the existing Python
decision**, or — better for the hot path — an in-process hook that answers the
*cheap* cases (is this even a tree-walking searcher? has this session already
queried?) and defers the ambiguous ones. The policy stays in one place, which is
where every false-positive lesson already lives. Rewriting the parser in TypeScript
would re-import a class of defect this repo has already paid for twice.

The one change I would make **regardless** of whether any of this is built: the
first `Bash|Grep` entry — graphify's warning-only hook — is measured at 0-of-19
compliance and costs a subprocess on every call. It is pure cost.

---

## 4. THE FAIL-OPEN AUDIT

A function hook that fails is **skipped**, not failed closed — quoted:

> *"At every one, a hook that fails (throws, overruns its budget, answers a wrong
> shape) is skipped: the hooks beneath and core run in its place, or its last
> `next` result stands; the failure is reported, naming it."*

Every way this could silently stop enforcing:

| # | Failure | Silent? | Detectable by |
|---|---|---|---|
| 1 | **The `agentId`/`agent_id` spelling class.** Any field read with the documented snake_case spelling is `undefined`; if absence means allow, the guard allows forever. | **Totally silent** | Only an end-to-end arm that dispatches a real lane and asserts the DENY. A unit test over the module proves nothing. |
| 2 | **A non-existent event name.** Measured today: `tool.result` registered cleanly and did nothing. | **Totally silent** | A liveness arm that asserts a real deny (round 2 above). This is why round 2 exists. |
| 3 | **Handler throws** (a bad `e.input` shape, an `$.store` rejection at the 4 MiB cap, an await that rejects). | Reported, but the tool RUNS | The failure is "reported, naming it" — but nothing gates on that report. Needs a session-bound readiness check. |
| 4 | **Module fails to load** (a `.json` import, reading `$` as a value, a non-top-level handler). Silent *unless* started with `--debug-file` — stated in the existing mod's own header. | **Silent by default** | `--debug-file`, or a positive liveness probe at session start. |
| 5 | **Matcher mismatch** — a tool renamed, or a new search tool added that the matcher does not name. | **Totally silent** | An inventory check that the matcher set still covers the tools that can walk a tree. |
| 6 | **State says "already queried" when it should not** — the `$.store` cross-session trap in §2; or a session-id collision; or a pruning bug. | **Totally silent** | Asserting a fresh session starts BLOCKED, as a real arm, not a unit test. |
| 7 | **The plugin is not installed on this machine.** Since Claude Code v2.1.195 an external-source plugin enabled only by PROJECT settings does not load until the user runs `claude plugin install` — so a `git clone` alone never arms it. (Recorded in the existing mod's header; **I did not re-verify that version claim** — see §5.) | **Totally silent** | An independent SessionStart warning that does not itself depend on the mod loading. |
| 8 | **`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` unset or `0`.** The issue's own bisection uses `"0"` as its control, so the whole mechanism is one env var away from off. | **Totally silent** | Same independent warning as #7. |
| 9 | **The early-access surface changes shape in a release.** A renamed field re-enters class #1 at any upgrade. | **Totally silent** | Re-running the liveness arms as a gate after every CLI bump. |

**The structural point:** items 1, 2, 5, 6, 7 and 8 all fail toward ALLOW and all
look identical to a correctly-working guard from inside the session. The present
Python hook shares some of these (7/8 have analogues), but it has one property
the function hook does not: **its failure is an exit code the host surfaces.**

The only real mitigation is the one the programme already identified as G04: a
**session-bound liveness receipt** — a positive assertion, each session, that the
hook is loaded and denying, produced by something that does not itself depend on
the hook loading. Without that, every row above is invisible.

---

## 5. COULD NOT ESTABLISH

- **The latency win is UNMEASURED.** I did not benchmark the present two
  subprocess hooks against an in-process handler. The claim "removes two spawns
  per call" is structural; the magnitude is not established.
- **Whether `tool.check` deny interacts correctly with permission modes.** I
  armed it only under the default mode in `claude -p`. Behaviour under
  `bypassPermissions`, under an `ask` the user already approved, and against the
  managed-settings hooks that *"run first"* is **not established**. Arm A shows
  the deny reaching the model in one mode; that is not the same as all modes.
- **Whether `tool.check` fires for a tool call made INSIDE a worktree-isolated
  subagent.** Arm C proves isolation survives, i.e. the subagent's Bash *works*.
  It does **not** prove the hook *evaluated* that subagent's call. Those are
  different questions and the second one decides whether lanes are covered at
  all. This is the single most important untested thing in this report.
- **Whether `--plugin-dir` and a real installed plugin behave identically.** All
  arms used `--plugin-dir`. A plugin loaded through `enabledPlugins` may differ.
- **The v2.1.195 plugin-install claim** in fail-open row 7 is inherited from the
  existing mod's header comment; I did not re-derive it.
- **Whether a `prompt.submit`-class event could carry this enforcement.**
  `prompt.submit` exists in the declarations (74 events). I did not probe it. It
  would be advisory-by-nature, and advisory is the thing measured at 0-of-19.
- **`$.store` behaviour under concurrent sessions** — two sessions writing the
  same plugin store. Not probed.

---

## 6. THE CODEX (gpt-6-astra) CONSULT

**RESULT: see ADDENDUM B at the end of this file — the lane RAN (rc 0), did not refuse, and its verdict is "keep the Python hook".**
Nothing in §1–§5 depends on it: every measurement above was made directly.


---

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issue #92533 (the blocker, repro re-run here), 292 open worktree/isolation/hook issues surveyed, the CLI binary and its generated type declarations.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/types/claude-code.d.ts`, the 2.1.269 declarations every quoted type fact comes from.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under discussion; `graph_first.py`, `.claude/settings.json`, `.claude/mods/kb-settings-guard/`.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — owner of the first, warning-only `Bash|Grep` PreToolUse hook discussed in §3.
- [pent0shi/clai](https://github.com/pent0shi/clai) — the only non-self GitHub code hit for `on("tool.check"`, cited solely as evidence that the event is essentially unused in the wild.

---

# ADDENDUM A — arm D: `tool.check` FIRES INSIDE A WORKTREE LANE (2026-09-12, after §5 was written)

§5 named this as *"the single most important untested thing in this report"*:
arm C proved worktree isolation SURVIVES a `tool.check` hook, but not that the
hook EVALUATED the subagent's own call. Those are different questions, and the
second decides whether delegated lanes are covered at all.

**Arm D settles it: they are covered.**

Same proven-live `plug-checkdeny` (a `tool.check` hook on Bash denying a sentinel
command), but the sentinel is run by the worktree-isolated SUBAGENT rather than
the main thread:

```bash
claude -p 'Do not modify files. Spawn ONE subagent via the Agent tool with
isolation: "worktree" and subagent_type general-purpose, with this prompt: "Run
exactly this via Bash, once: echo ZZSENTINELZZ — then report verbatim the output
OR the full error/denial message. Do not retry, do not work around it." Then
paste the subagent report verbatim and stop.' \
  --output-format json --allowedTools "Agent,Bash" \
  --plugin-dir "$S/plug-checkdeny" \
  --settings '{"env":{"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS":"1"}}'
```

The subagent reported, verbatim:

> ```
> Permission to use Bash denied by plugin plug-checkdeny: KBPROBE_TOOLCHECK_FIRED: denied by the tool.check hook.
> ```
> No stdout was produced — the `echo ZZSENTINELZZ` command never executed. The
> denial came from a plugin named `plug-checkdeny` via a `tool.check` hook, which
> intercepted the Bash tool call before execution.

Counts over that run's JSON: `KBPROBE_` → **1**, isolation-lost → **0**.

**So a `tool.check` hook on Bash is, all four at once:**

1. live on the main thread (arm A),
2. live **inside a worktree-isolated subagent** (arm D),
3. able to deny with our own reason text reaching the model (arms A and D),
4. harmless to worktree isolation (arm C).

That is the complete enforcement surface `graph_first` needs, on the one tool
`tool.call` cannot touch. **Strike the corresponding bullet from §5** — it is now
established, in the affirmative.

One nuance worth carrying: the subagent's Bash was denied by the hook while
`pwd` in arm C ran fine, on the same plugin. So the deny in arm D is OUR policy
firing, not isolation breaking — the two failure signatures are distinguishable
in the transcript, which is what makes this armable at all.

---

# ADDENDUM B — §6 THE CODEX (gpt-6-astra) CONSULT: it ran, and it says DON'T BUILD IT

**The lane ran and returned.** Observables from its own banner:
`OpenAI Codex v0.154.0` · `sandbox: read-only` · `reasoning effort: xhigh` ·
`approval: never` · session id `01a096cd-2e16-7f11-aed9-027a6065aa2d` · **rc 0**.
(The banner also prints `model: gpt-6-astra`, which is NOT a valid observable —
it reports the session model, not the lane's. I am not citing it as proof Astra
ran.)

Full verdict persisted **verbatim** at
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graph-first-hook-astra-verdict-raw.md`
(15,130 bytes). It did not refuse, did not time out, and was not empty.

**The lane could NOT reach the graph**, and said so plainly: *"The repository
graph lookup was unavailable: mise reported `tool purgatory cleanup failed:
Operation not permitted`, then failed creating a temporary file under version
`2026.9.5 macos-arm64`. No Graphify result or health evidence was produced; this
decision uses your supplied probes and declarations."* Expected for a read-only
sandbox; the graph reads were done on this side instead.

## Its verdict, first line, verbatim

> **Keep the Python hook; migrating now is not worth it because the deciding risk
> is unnoticed loss of enforcement across an immature hook lifecycle, while the
> only substantial benefit—lower latency—remains unmeasured.**

> *"Your probes establish that `tool.check` on Bash is a viable candidate. They do
> not establish that replacing the existing implementation is a good investment."*

And on the invariant: *"Narrow the written invariant to **'Never register
`tool.call` on Bash.'** Discard the `tool.result` arm completely, as you have
done."*

## 🔴 The design point I did NOT have, and would have got wrong

> *"In particular, **'graph-first has no objection' must mean 'preserve the
> verdict,' never 'return allow.'** Returning a fresh `allow` can discard an
> `ask`, another restriction, or accompanying result fields."*

Its prescribed handler shape: call `next(e)` exactly once; preserve an existing
`deny` including its reason; replace `allow`/`ask` with our `deny` only on a
positive identification; **otherwise return the complete original result
unchanged.** My §2 sketch would have returned a bare verdict and silently
discarded other hooks' restrictions. This is the most valuable thing the consult
produced.

It also rejects the split design I floated: *"Prefer one event for both tools if
`tool.check` on Grep passes those checks. Splitting Bash onto `tool.check` and
Grep onto `tool.call` introduces two ordering models without an established
benefit."*

On the sparse-usage evidence, it declines to over-read my own number: *"Its
sparse public usage is **a maturity signal, not a veto**. Two search results do
not measure total adoption, and 292 matching issues do not measure this event's
failure probability."* That is a fair correction to how I framed it.

On state: use `$.store`, *"explicitly namespaced by **policy schema, repository
scope, and session ID**"*, and **first establish that `$.session.id()` identifies
the same lifecycle as the current hook payload's `session_id`** — which I had
assumed rather than checked. It also flags that eviction under the 4 MiB cap is a
real semantic change from indefinitely-retained marker files.

And a warning against over-correcting the fail-open audit: *"Do not 'fix' this
audit by turning every exception into a deny. That would reverse your deliberate
ambiguity policy and recreate the defects you have actually measured."*

## 🔴 ONE CLAIM OF THE LANE'S THAT I CHECKED AND CAN REFUTE

The lane wrote:

> *"A thin function-hook transport to Python is **not available from the API
> surface you listed**: there is no declared subprocess facility."*

**A subprocess facility DOES exist** — `$.process.run`, at
`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/types/claude-code.d.ts:2170-2187`:

> *"Runs a command on the host by its argument vector (no shell) and resolves
> `{ exitCode, stdout, stderr }` once it exits, any exit code."*
> *"@param init `{ cwd, env, stdin, timeoutMs }` (cwd the session's by default;
> timeout 30 s by default, ten minutes at most)"*

**But the fault is MINE, not the lane's, and its conclusion survives.** It said
*"from the API surface you listed"* — and my prompt listed `$.store`,
`$.session.*`, `$.fs.*`, `$.clock.now()` and `$.ui.log`, and **omitted
`$.process`**. The lane was accurate about what it was given and hedged the
remainder correctly: *"If another supported host facility provides one, it
retains the subprocess cost."* That clause is right, and it is decisive — a
`tool.check` hook calling `$.process.run("uv run kb-setup hookguard")` still
spawns the subprocess, so the **thin-transport design buys nothing on latency**,
which was its only claimed benefit. The middle path I recommended in §3 is
therefore buildable and pointless. **§3's recommendation is superseded by this.**

## Its next steps, which I endorse

1. **Keep the Python deny and narrow the inaccurate Bash invariant** (the
   `register.ts` wording).
2. **Audit the second, warning-only `Bash|Grep` hook.** *"If its only contribution
   duplicates graph-first guidance, removing that redundant invocation is the
   first optimization to evaluate."*
3. **Measure the remaining hook's actual cost** before paying for a replacement.
   It explicitly cautions that *"The 20-second timeout is a ceiling, not evidence
   of typical overhead. Two spawned hooks also do not establish twice the
   wall-clock delay; execution may overlap."* — a fair hit on my §3 framing.
4. Revisit only if measured savings justify the acceptance-test burden.

---

# FINAL BOTTOM LINE

**Technically VIABLE — measured, not argued. Not worth building today.**

- `tool.check` on Bash is live on the main thread, live inside worktree lanes,
  denies with our own reason text, and does not break worktree isolation (arms
  A–D). The blocker everyone expected, #92533, is `tool.call`-specific.
- The repo's written invariant *"NEVER BASH"* is over-broad and should be narrowed
  to *"never `tool.call` on Bash"* — this is the one concrete change both I and
  the consult recommend, and it costs nothing.
- The migration itself buys one thing (removing subprocess spawns) whose
  magnitude **nobody has measured**, against a fail-open surface where six or
  more distinct failures all look identical to a working guard from inside the
  session.
- **The cheapest real win is not the migration at all**: there are two
  `Bash|Grep` PreToolUse subprocesses today, and the first is a warning layer
  measured at 0-of-19 compliance. Deleting it is free and halves the per-call
  hook cost.

## What I could not establish (final)

- **Latency**, still unmeasured on both sides. This is the number that would
  decide a future revisit, and neither I nor the lane has it.
- **Permission-mode behaviour of `tool.check`**: armed only under the default
  mode in `claude -p`. `bypassPermissions`, an already-approved `ask`, and the
  managed-settings hooks that *"run first"* are untested.
- **Whether `$.session.id()` is the same lifecycle** as the PreToolUse payload's
  `session_id`. Assumed by me; flagged as needing proof by the lane; unproven.
- **Whether `--plugin-dir` and a real `enabledPlugins` installation behave
  identically.** All arms used `--plugin-dir`.
- **`$.store` under concurrent sessions.** Not probed.
- The **v2.1.195 plugin-install claim** in fail-open row 7 is inherited from the
  existing mod's header comment and was not re-derived.
- **A process hazard, not a finding:** another lane overwrote my prompt file at
  the shared scratchpad path `scratchpad/astra-prompt.md` while my consult was
  running. My lane had already read it (its log echoes my prompt verbatim), so
  this consult is sound — but concurrent lanes are colliding on that directory,
  and the next one may not be so lucky.

---

# ADDENDUM C — 🔴 PRIOR-ART RECONCILIATION (added after the report was first published)

**Correction to how this round was run.** Ray's standing instruction is to run
`kb-recall-work` FIRST. I ran it once, with a SIX-WORD topic
(`"function hooks graph first enforcement"`), and then read **only the summary
counts** — never the report it wrote to
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/recall/function-hooks-graph-first-enforcement.md`.
`kb-recall-work` ANDs its stems, so the long topic narrowed tracked-file matches
to **85** where `"function hooks"` alone returns **410**. The probe ran and its
output went unread — the exact failure the team lead flagged.

Re-run narrow, and the reports read, the position is this.

## What was ALREADY ESTABLISHED — cite, do not claim

| Fact | Already in | Status there |
|---|---|---|
| **`tool.check` exists in 2.1.269 declarations (10 occurrences), and shipped in the window (2.1.267, 2.1.269]** | `.agent/kb/reports/agents/fh-synthesis.md` **C5**, lines 175-197 | Re-derived there **with a version table and a negative control** (`ZZQQXX_NOT_REAL` → 0/0; `tool.call` positive control 46→61). Explicitly listed at `:346` under *"Retired by this synthesis (do not carry forward as open)"*. |
| **Upstream staff already recommended `tool.check` as the surface for guards** | `.agent/kb/reports/agents/fh-source-sweep.md:1143-1146` | `poteat`, verbatim: *"Parallel **guards** should use a checking surface such as the proposed `tool.check`, because `tool.call`'s core is the actual execution."* (`91870-comments.md:3019–3039`) |
| **`$.tool.check` as a callable affordance** | `fh-source-sweep.md:616-618` (S9) | poteat's example: `const { decision } = await $.tool.check({ tool: "Read", input: { file_path: e.path } })` |
| **#92533 is about `tool.call` on Bash specifically** | `docs/research/reports/2026-09-11-function-hooks-enforcement-programme.md:316-318` | Stated correctly there: *"registering ANY `tool.call` hook on Bash — 'even a pure passthrough `next(e)` with no logic' — refuses every Bash call in an `Agent(isolation:"worktree")` subagent"* |
| **A live compatibility probe for that combination is required** | same report, risk **#15** (`:758`) | *"Enabling native worktree isolation later breaks every Bash call (`#92533`) — A live compatibility probe that rejects the combination while unsupported"* |
| **"A registration log alone does not count"** | same report, risk **#14** (`:757`) | Exactly the reason my round-2 denying arms exist |
| **`next.origin` unforgeability** | `fh-synthesis.md` C1 | Retired there; I restated it |

🔴 **So my framing to the team lead — that `tool.check` was an event "nobody has
named" — was WRONG, and I withdraw it.** It is named in three prior reports, it
was re-derived with controls yesterday, and the design direction came from
upstream staff, not from me. (The published report body never carried that
sentence; my prose to the lead did.)

**`register.ts`'s wording is still over-broad**, and that finding survives: the
programme report scoped #92533 correctly, but
`.claude/mods/kb-settings-guard/hooks/register.ts` states the invariant as
*"NEVER BASH"*. Narrowing it remains the cheap, correct change — it is a
docs-vs-docs inconsistency inside our own repo, not a new fact about the CLI.

## What this round GENUINELY adds

Every prior mention of `tool.check` marks its runtime contract **UNVERIFIED**,
and one of them says so as an instruction:

- `fh-source-sweep.md:1148` — *"**Do not convert this into a shipped `tool.check`
  guarantee.** … The pinned `sec-default` README names it as a pass-through
  event, but supplies no implementation or signature."*
- `fh-source-sweep.md:1225` — *"Staff's forthcoming checking surface; named in
  pinned README, unused by these implementations. **Full runtime contract
  UNVERIFIED.**"*
- `fh-source-sweep.md:916-917` — `sirmaelstrom`'s *"`tool.check` is NOT in 2.1.267
  declarations … so my S9 is weaker than I stated."*

**This round closes that named gap, by running it rather than reading it:**

1. **`tool.check` on Bash FIRES and its deny is honoured**, our reason text
   reaching the model verbatim (arm A). That is the runtime contract three
   reports marked UNVERIFIED.
2. **`tool.check` on Bash does NOT trigger #92533** (arm C) — the combination
   programme risk #15 asks for a live probe of. Nobody had run it.
3. **`tool.check` fires INSIDE a worktree-isolated subagent** (arm D) — programme
   risk #14's *"exercise the selected event … a registration log alone does not
   count"*, executed.
4. **`tool.call` on Grep alone is clean** (round 1) — so the bug is specific to
   the event-and-tool PAIR, not to either alone.
5. **#92533 still reproduces at 2.1.269**; the programme report described it from
   the issue at 2.1.263.
6. **`tool.result` is not a declared event** — a small negative, and the probe
   failure that forced the denying arms.
7. **`$.store` is cross-session**, which makes it a fail-open trap for a
   session-scoped marker.

Items 1–3 are the ones worth carrying. They convert a staff *suggestion* plus an
UNVERIFIED contract into a measured capability, and they retire programme risks
#14 and #15 for this event.

## Where this belongs in the programme

The G00–G12 chain (**#766**) already owns this work: **G01** is *"Runtime
contract: locally regenerated declarations + live probes for event fields,
imports, `$`, process access, fs, namespace bridging, tiers, **the worktree
bug**"*. Arms A–D are G01 evidence for `tool.check`, and should be filed there
rather than as a free-standing finding.

## Reports read for this reconciliation

- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-11-function-hooks-enforcement-programme.md` (847 lines)
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-function-hooks-research.md` (112 lines)
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-github-function-hooks-examples.md` (435 lines)
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-11-astra-function-hooks-setup-coverage.md` (653 lines)
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md` (502 lines)
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md` (1463 lines)

**Not read, and named as outstanding:** the nine further function-hooks reports in
`ray-manaloto/dotfiles`, and the cross-repo record `dotfiles#1020`. Any of them
may already contain items 1–3 above; I did not check, and I am not claiming
novelty against a corpus I did not open.

## Addendum C, closing the gap I named: the dotfiles reports, now read

I said above that I had not opened the sibling repo's function-hooks reports and
would not claim novelty against a corpus I had not read. I have now read the two
that mention the event:

- `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-upstream-91870.md` (308 lines)
- `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhook-harvest.md` (1099 lines)

Both treat `tool.check` as **prospective and not-yet-shipped**, on
`sirmaelstrom`'s 2.1.267 reading — `:244-247`: *"On concurrency / `tool.check` (a
**not-yet-shipped** event, per `sirmaelstrom` #158 who could not find it in
2.1.267's generated types): poteat describes it prospectively (#155)…"*.
Neither contains a probe, an arm, or any runtime result. So **items 1–3 are not
duplicated there**, and the narrow novelty claim stands.

Two things worth taking from them anyway:

- `:100-107` records poteat's own handler shape, and its return is
  `{ decision: 'deny', reason: 'destructive command' }` — **independent
  confirmation of the return shape I measured**, from upstream, on the same
  event. His pattern starts `next(e)` early for concurrency; Astra's advice
  (call `next(e)` exactly once, preserve its result) is compatible with it.
- `2026-09-11-fnhook-harvest.md:1041` already lists **`process.run`** among the
  surfaces. So `$.process.run` was in the corpus before today — which confirms
  ADDENDUM B's conclusion that omitting it from my consult prompt was my error
  alone, not a gap in what this project knew.
