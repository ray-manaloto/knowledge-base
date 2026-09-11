# astra-function-hooks-programme — kb-codex-astra-advisor

**STATUS: COMPLETE.** Written incrementally throughout; the Astra lane returned
a full verdict and did NOT refuse. Raw verdict verbatim beside this file at
`.agent/kb/reports/agents/astra-function-hooks-verdict-raw.md`.

- Lane: `kb-codex-astra-advisor` (harness agent) driving `codex` on `gpt-6-astra`.
- Started: 2026-09-11.
- Repo HEAD at start: `cd3b07a6` on `chore/drift-sweep-and-fork-rebase-automation`.

## 🔴 Routing caveat, stated before anything else

My own agent definition (`.claude/agents/kb-codex-astra-advisor.md`) says to
REFUSE and hand back to `kb-codex-advisor` (Sol) for *"anything reading
`hook_guard.py`, `secret_guard.py`, `check_first.py`, `absent_binary.py` or
`stage_explicitly.py`"*, because Astra rejects some authorized security work
outright (five upstream reports recorded in
`.claude/skills/kb-review/SKILL.md:182-189`).

This programme IS that surface. I am running it anyway because Ray named this
lane explicitly and the team lead assigned it — but the refusal path is live:
if the Astra lane returns `invalid_prompt`, a usage-policy rejection, or an
empty result, that is reported VERBATIM here and the consult falls back to Sol.
A refusal is never reported as a verdict.

## Progress log

- [x] report file created
- [x] phase 0 `kb-recall-work` run
- [x] graph query run (control-armed below)
- [x] repo evidence gathered — see "What I measured here" below
- [x] Astra lane launched, ran ~9 min, returned 30,137 bytes
- [x] verdict persisted (raw + synthesised)

## Phase 0 — `mise run kb-recall-work -- "function hooks mods enforcement do-not.md migration"`

Seven probes, all `ran`. Counts as printed:

| probe | examined | matched |
|---|---:|---:|
| tracked_files | 3333 | 4 |
| artifact_pages | 136 | 0 |
| branches | 482 | 66 |
| worktrees | 2 | 0 |
| issues | 934 | **0** |
| plans | 204 | **0** |
| memory | 413 | 386 |

**There is NO tracked issue and NO plan for this programme.** That is the single
most decision-relevant phase-0 result: the programme is greenfield in the
tracker, so the ticket chain below is new, not a re-plan.

The four tracked-file matches, and what each is:

- `docs/direction/2026-09-10-ray-directives.md` — Ray's directive text.
- `docs/research/reports/2026-09-10-github-function-hooks-examples.md` — the
  prior research report. **This is the load-bearing prior art** and is read in
  full below.
- two dotfiles modernization-audit files (sibling repo, not this programme).

Report: `.agent/kb/recall/function-hooks-mods-enforcement-do-not-md-migration.md`

## Graph query — and its control arm

`mise run kb-query -- "what are the PreToolUse hook guards and how are they wired"`
returned **rc=3, TRUNCATED** — 49 of 157 nodes shown against a ~2000-token
budget. Per `kb-query rc 3 is a truncation guard`, that prefix is **not**
evidence of absence, and I did not treat it as an answer. What it did establish
is that the corpus holds `claude-code-docs` and `codex-rs` hook material, and
that the aggregate graph is at **472,069 nodes** (matching the branch's baseline).

The graph could not answer the programme question, which is expected: the
function-hooks surface is UNRELEASED (team lead's fact 12), so nothing about it
is in a pinned source. I therefore grounded on the repo's own files instead, and
say so rather than reporting a graph miss as an absence.

## 🔴 What I measured HERE, today — five facts the brief did not contain

All run in `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base` at
`cd3b07a6`. These change the plan, so they are stated before the verdict.

### M1. `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` is NOT set in tracked config

`grep -rn 'FUNCTION_HOOKS' .claude/` returns exactly ONE hit, and it is prose:
`.claude/rules/research-doc-sources.md:96`. The `env` block of
`.claude/settings.json` contains eight keys and that is not one of them:

```
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD, CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS,
CLAUDE_CODE_ENABLE_TELEMETRY, OTEL_LOG_USER_PROMPTS, OTEL_LOG_ASSISTANT_RESPONSES,
OTEL_LOG_TOOL_DETAILS, OTEL_LOG_TOOL_CONTENT, OTEL_LOG_RAW_API_BODIES
```

Control arm, same command shape: `grep -n 'ENABLE_TELEMETRY' .claude/settings.json`
→ `:5`, a hit. So the probe discriminates; the absence is real.

### M2. `.claude/mods/` is UNTRACKED and registered NOWHERE

`git status --short .claude/mods` → `?? .claude/mods/`;
`git ls-files .claude/mods` → **empty**; `git check-ignore` → rc 1 (not ignored,
just never added). Neither `.claude/settings.json` nor `.claude/settings.local.json`
names it in `extraKnownMarketplaces` (22 + 0 marketplace entries) or
`enabledPlugins` (22 + 4 entries, **0** matching `kb-`/`mod`/`guard`).

Whether `.claude/mods/**` is a directory Claude Code scans natively, with no
marketplace registration, is **UNVERIFIED by me**. The team lead reports a
three-armed live proof, which I take as given — but "it ran in a probe" and "it
is wired in tracked config" are different claims, and only the first is
evidenced on disk. **This is exactly this repo's recurring defect shape:
written is not running.**

### M3. There are 12 PreToolUse entries — and 18 hook entries in total

Enumerated from `.claude/settings.json` (`uv run python`, not a bare
interpreter — the guard denies that):

| event | matcher | command | count |
|---|---|---|---:|
| PreToolUse | `Bash\|Grep` | `.venv/bin/graphify hook-guard search` | 1 |
| PreToolUse | `Bash\|Grep` | `kb-setup hookguard` | 1 |
| PreToolUse | `Read\|Glob` | `.venv/bin/graphify hook-guard read` | 1 |
| PreToolUse | `Edit\|Write` | `mise run kb-instruction-edit-guard` | **8** |
| PreToolUse | `Bash` | `mise run kb-instruction-shell-write` | 1 |
| SessionStart | (4 entries) | currency-check, telemetry-prune, codex-config-check, env-refresh | 4 |
| SessionEnd | | brain-transcript-audit, kb-session-reflect | 2 |

**12 PreToolUse, 18 total.** The brief's "12 classic PreToolUse hooks" is
confirmed. Two things the count hides and the plan must not:

- **8 of the 12 are the SAME command** (`kb-instruction-edit-guard`) repeated
  across 8 matcher groups. That is 8 *registrations*, ONE *guard*. A migration
  planned as "12 tickets" would be planning 8 tickets for one module.
- **2 of the 12 are graphify's own** (`graphify hook-guard search|read`), owned
  by the pinned fork, not by `kb_setup`. Those cannot be migrated by editing
  this repo's python — they are a third party's binary. The programme must say
  what happens to them, or it silently drops 2 of its 12.

### M4. The codegen the reference implementation cites DOES NOT EXIST

`.claude/mods/kb-settings-guard/hooks/protected-paths.ts:1-15` declares itself
GENERATED and names a source of truth and two tasks:

> Source of truth: `kb_setup.settings_guard.PROTECTED_SUFFIXES`.
> Regenerate with `mise run kb-guard-codegen`; `mise run kb-guard-codegen-check`
> is the drift gate.

Measured: `python/src/kb_setup/settings_guard.py` → **No such file or directory**.
`grep -n 'kb-guard-codegen\|settings_guard' mise.toml` → **no output, no such
tasks**. `schemas/` holds 8 schema files and none is a guard schema.

So the file is a hand-written file *labelled* generated, whose drift gate does
not exist. Under this repo's standing rule that the generator owns every model
type, that header is currently a **false claim in a tracked-to-be file**, and
the "list of protected paths" has no single source of truth at all. This is a
ticket, and it is a prerequisite rather than a nicety.

### M5. The guard python surface is 7 modules, not 5

`ls python/src/kb_setup/ | grep -Ei 'guard|hook|check_first|absent|stage|instruction'`:

```
absent_binary.py  check_first.py  hook_guard.py  instruction_edit_guard.py
instruction_shell_write.py  secret_guard.py  stage_explicitly.py
```

The five named in my own agent definition's refusal rule are
`hook_guard`/`secret_guard`/`check_first`/`absent_binary`/`stage_explicitly`.
Two more exist — `instruction_edit_guard` and `instruction_shell_write` — and
they are the ones the 12 PreToolUse entries actually invoke most.

### M6. Guard surface size — 2,859 lines of Python across 7 modules

```
hook_guard.py              525
check_first.py             640
secret_guard.py            439
instruction_shell_write.py 401   (+ tests/test_instruction_shell_write.py 304)
absent_binary.py           386
instruction_edit_guard.py  342
stage_explicitly.py        126
                         -----
                         2,859
```

The brief's "401 lines + 304 test lines" for the shell parser is **confirmed
exactly**. But `instruction_shell_write.py` is only **14% of the guard Python**.
A programme framed as "migrate the guards to TS" is proposing to reimplement
2,859 lines of tested Python in a loader that forbids node builtins. That number
belongs in the plan, because it is the number that decides Q9 and probably more.

### M7. `do-not.md` has 13 numbered invariants — and 7 of them have NO machine enforcement today

`grep -c '^[0-9]\+\. \*\*' .claude/rules/do-not.md` → **13**. Classified by what
enforces them, per each entry's own text plus the probes below:

| # | invariant | enforced by | mechanically checkable? |
|---|---|---|---|
| 1 | no hand `graphify install` | `hook_guard` DENY | yes — command string |
| 2 | no `hook install` / `extract --global` / `global add` | `hook_guard` DENY | yes — command string |
| 3 | no hand graphify at all | `hook_guard` DENY | yes — command string |
| 4 | no non-Anthropic key-detected backend | `clean_env()` at runtime | partly — env, not a hook |
| 5 | don't commit `graphify-out/` beyond 2 subdirs | **nothing** (`stage_explicitly` is adjacent, not this) | yes — at stage time |
| 6 | don't ingest outside the `sources/` contract | **nothing** | **no** — intent, not a call |
| 7 | don't commit onto the default branch | ship-time only (`pr.py:405-411`); the rule SAYS so | yes — but at the wrong moment |
| 8 | no `.sh` / inline shell logic | **nothing** — the rule says *"Policy, not a hk gate today"* | yes — a file check |
| 9 | no inline lint suppression | `no_lint_skip` hk step, scoped to `python/src/`+`tests/` | yes |
| 10 | don't trust `gh run watch --exit-status` | **nothing** — probe: `grep -rn 'exit-status' python/src/kb_setup/` → **0 hits** | partly — command string |
| 11 | don't mutate user/global/system config | **nothing** — probe: no `~/.claude` / `.codex/config.toml` path check in `instruction_edit_guard.py` → **0 hits** | yes — a path check |
| 12 | don't combine `--sandbox` with `--dangerously-bypass-approvals-and-sandbox` | **nothing** enforcing (only prose in `codex_lane.py`/`codex_run.py`) | yes — flag pair |
| 13 | don't run a repo lane at `danger-full-access` | **nothing** enforcing | yes — flag value |

Control arm for the three zero-hit probes: `grep -rln 'graphify install'
python/src/kb_setup/` → 3 files. So the probe shape finds things when they are
there; the zeros are real.

**The decision-relevant reading:** of 13 invariants, **3 are already enforced by
a hook**, 2 by other mechanisms, **1 (#6) is not mechanically checkable at all**,
and **7 are prose-only but WOULD be checkable**. So Ray's "move do-not.md into
function hooks" has a real, bounded target of **7 new enforcements** — not 13 —
and the honest answer for #6 is "this one stays prose". A programme that plans
13 tickets is planning 6 it cannot deliver, and the two that would fail last are
the ones that look easiest on a list.

Also note #7: it IS enforced, but at ship time, and its own text says a commit
onto `main` still lands. Migrating it to a PreToolUse-class function hook is the
one entry where function hooks would be a genuine capability UPGRADE rather than
a port — it moves enforcement from "when you push" to "when you commit".

## Step zero (Ray's standing rule) — what ALREADY EXISTS, from the repo's own prior research

`docs/research/reports/2026-09-10-github-function-hooks-examples.md` is a
control-armed GitHub sweep across all four indexes, done for this exact topic on
2026-09-10. I read it in full rather than re-running the search. It already
answers most of "what exists", so the programme does not need to re-do it:

**ADOPT — `ray-amjad/awesome-claude-code-function-hooks`** (MIT, pinned
`b559942ec757e1f28b6a901ce1be79a23aa52c7d`). Not a link list: a working plugin
**marketplace** shipping two complete, tested function-hook plugins, one of which
(`secret-redactor`, `hooks/redact.ts`, 366 lines, with
`test/detect.test.mts`) **is a direct functional analogue of
`kb_setup.secret_guard`**. It is the only find that is complete, tested,
MIT-licensed, and demonstrates distribution. This is the borrow target.

**ADOPT AS PRIOR ART — `lossless-claude/lcm`** (`#376`/`#377`, both merged): a
real project that has **already completed** the classic→function-hooks migration
this programme is contemplating. 14 code hits, changesets, tests.

**READ BEFORE DESIGNING — `Monte9/claude-function-hooks` issues #1/#2/#3.** The
sharpest semantic critique found anywhere, and 🔴 **#3 asserts `deny` has no
engine meaning at all**, which if true qualifies the whole enforcement thesis.
The prior report explicitly did NOT adjudicate it. The team lead's fact 5
(`{deny}` blocks even under `--dangerously-skip-permissions`) is a live
measurement and I weight it above a third-party issue — but the issue is about
`tool.call`'s `deny`, and it deserves an arm rather than a shrug.

**REJECTED for this repo — the recommended enablement path.** That marketplace's
README documents USER-scope enablement (`~/.claude/settings.json` `env`) as the
recommended route. `do-not.md` #11 forbids writing `~/.claude`, so this repo
cannot follow it. The README neither confirms nor refutes project scope; the
team lead's fact 1 says project scope works, which is a measurement and wins.

### 🔴 Three findings from that report that change the plan

**(a) `.claude/mods/` is NOT the function-hook convention.** Measured there:
`path:.claude/mods` returns 5 hits and **all five are a false positive** (an
FFXIV roleplay project). The real on-disk shape is a plugin directory —
`.claude-plugin/plugin.json` + `hooks/hooks.json` + the TS module — which the
reference implementation DOES have. But the parent path buys nothing, and
combined with **M2** (untracked, registered nowhere) the honest status is: the
reference implementation has the right *shape* in a location nothing is known to
scan. **A ticket must establish HOW it is discovered, with an arm.**

**(b) 🔴 The liveness observable EXISTS and is better than anything invented.**
`anthropics/claude-code#92469` carries a verbatim runtime load line reproducible
via `claude --debug`, writing to `~/.claude/debug/<session>.txt`:

> `hooks module <name> loaded (worker, environment 1); events: tool.call,ui.render,…`

— **54 events named by the engine itself at load time.** This is a positive,
greppable, non-destructive proof-of-enablement. The settled ruling ("liveness:
both a SessionStart warning AND a `kb-gates` failure") now has a concrete
mechanism instead of a wish, and it is the ONLY signal that distinguishes
"loaded" from "silently failed to load" (team lead's fact 4). **Any liveness
ticket that does not read this line is inventing a weaker signal than the one
that exists.**

**(c) 🔴 The obvious migration lands exactly on the open isolation bug.** This
repo's guard stack is a `PreToolUse` matcher on `Bash|Grep`. `#92533` says
registering ANY `tool.call` hook on Bash — *"even a pure passthrough `next(e)`
with no logic"* — refuses every Bash call in an `Agent(isolation:"worktree")`
subagent, bisected headless with 6 failed retries. The team lead's fact 9 states
this. What the team lead's framing understates: the worktree-scoping ruling
means this programme is **actively steering lanes into worktrees**, so the
programme increases the exposure to the bug it is exposed to. Those two settled
decisions interact, and that interaction is where I would put the risk budget.

**(d) The type declarations must NOT be checked in.** That marketplace's README,
verbatim: *"The type declarations are not in git. Claude Code writes them, and
every release rewrites them, so a checked-in copy goes stale and lies to you."*
Regenerate with `/plugin-types`. This is in direct tension with this repo's
codegen convention (schema → generated, committed, drift-gated) and the tension
must be resolved explicitly in a ticket, not discovered later.

### 🔴 CORRECTION to the prior research report — the `deny` critique is about the WRONG ENGINE

The prior report flags `Monte9/claude-function-hooks#3` as *"directly relevant to
the prior report's enforcement thesis — it asserts `deny` is not an engine-level
primitive at all, which if true qualifies … 'returning `{deny: <reason>}` …
DENIES the event outright.'"* and says it *"belongs in front of whoever designs
the migration."*

I am that designer, so I went and read it. **It is about a different engine.**

`gh api repos/Monte9/claude-function-hooks` returns, verbatim in its own
`description` field:

> *"A reference implementation of the Function Hooks algebra **proposed for**
> Claude Code."*

`fork: false`, `parent: null`, `language: JavaScript`, 1 star, **no license**,
last pushed 2026-09-03. Its top-level tree is
`docs examples findings package.json src test`.

And the issue body's own decisive probe (`#3`, open, 2026-09-04, title
*"`deny` has no engine meaning, and `next()` twice runs the side effect twice"*):

> *"**What broke.** `grep -rn deny src/` is empty, so: `{deny: ""}`, `{deny: 0}`,
> `{deny: null}`, `{Deny: "x"}` all block the action (no `next`), but the caller's
> `if (r.deny)` says 'allowed'"*

`src/` is **Monte9's** source tree. The issue is a bug report filed against a
third party's independent JavaScript reimplementation — it is not an observation
about Anthropic's engine and never claimed to be. Its proposed fix is *"Make
`next` a single-use token the engine tracks per hook. Koa already does this."*
That is a design suggestion for Monte9's own code.

Control arm: issue `#1` in the same repo is *"Matchers bind once at dispatch
entry, and `e` is passed by reference"* — also an implementation-internals bug
report, same shape, same repo, so the probe is reading the issues correctly and
the classification is not a one-off.

**What this changes for the programme, in both directions:**

- **A risk is REMOVED.** The enforcement thesis is not qualified by this issue.
  The team lead's fact 5 — `{deny: "<reason>"}` blocks even under
  `--dangerously-skip-permissions`, measured live on 2.1.268 — stands
  unopposed. The programme does not need a ticket to adjudicate it.
- **A methodological lesson is CONFIRMED, and it is this repo's own rule.**
  `probes-need-a-control-arm.md` § *"Source beats issue tracker"*: a secondary
  artifact (a third party's issue about a third party's clone) was read as
  evidence about a primary one (the shipped engine). The prior report was
  careful — it said *"I did not adjudicate this"* — but it was passed forward as
  a live risk, and one `gh api` call settles it.

I am NOT downgrading the rest of that report. `#92533` (isolation) and `#92469`
(the debug load line) are issues on `anthropics/claude-code` itself and are
unaffected by this correction.

## 🔴 M8 — THE STRUCTURAL FINDING: codex cannot run a Claude function hook

`.codex/hooks.json` exists and carries **its own, separate** classic hook stack:

```
PreToolUse  matcher "Bash|Grep"  -> mise exec -- graphify hook-guard search   (timeout 15)
PreToolUse  matcher "Bash|Grep"  -> uv run kb-setup hookguard                 (timeout 20)
PostToolUse matcher "apply_patch"-> uv run kb-setup edit-check                (timeout 90)
SessionStart …
```

Function hooks are a **Claude Code** mechanism. Codex has no such surface — it
reads `.codex/hooks.json` and `AGENTS.md`. Ray's directive is *"so the agents in
both claude and codex know this is how we want to move forward"*, and the
settled ruling is prose in a rule file **plus `AGENTS.md`** precisely because
codex reads that.

So the programme's real shape is not "migrate 12 hooks". It is:

> **Every guard that must bind BOTH families needs an implementation codex can
> run. That implementation already exists and is Python.**

A TS reimplementation therefore does not REPLACE the Python — it **duplicates**
it, and the two must agree forever, across two languages, with no shared test.
That is the divergence class this repo has already been bitten by (a generated
table drifting from its generator; a summary table that was not the field set).

## 🔴 M9 — A hooks module has NO NODE, and the subprocess cost is the whole question

Two independent sources, both already in this repo's prior research:

1. `claude-code.d.ts:13-15`, quoted in
   `docs/research/reports/2026-09-10-github-function-hooks-examples.md:337`:
   *"A hooks module runs in an environment of its own: no DOM, no Node."*
2. `lossless-claude/lcm` — the one project that has ALREADY completed this
   migration — hit it in practice and had to keep a **daemon** and POST to it,
   verbatim: *"Chosen over a rewrite of the extractors because the module runs
   without Node or SQLite: the daemon has to write."*

And the capability that makes delegation possible does exist: **`$.process.run`**
is in the 66-name catalog (alongside `fs.*`, `http.fetch`, `mcp.call`,
`store.*`). So a function hook CAN shell out to `uv run kb-setup …`.

The prior report already drew the conclusion and I agree with it (`:337`,
verbatim): *"A function hook **cannot** call them in-process — it would need a
subprocess capability (`$.process.run`) or a daemon, which gives back much of the
cost the classic hook already pays. That is a real argument against migrating
this repo's guard stack."*

**UNVERIFIED by me**: `$.process.run`'s signature, whether it is sandboxed, and
its per-call latency. The name is from a catalog the prior report itself warns is
incomplete (`#92469` proves the d.ts omits real events). Do not plan around its
semantics without probing it.

## My independent read on Q9 — stated BEFORE the Astra verdict, so the two can be compared

Given M8 + M9, the question the team lead framed ("does the TS parser ship with
the reference implementation, or become its own ticket?") has a **third answer
that neither option contains**, and I think it is the right one:

> **Do not port `instruction_shell_write`'s parser to TypeScript at all.**
> Ship the function hook as a THIN policy shell that calls the existing Python
> through `$.process.run`. Q9's two options both assume a rewrite; the rewrite
> is the thing to question.

The risk that decides it: **codex still needs the Python** (M8). So a TS port
does not retire 401 lines + 304 tests — it adds a second implementation beside
them. Two parsers for one rule, in two languages, with the fail direction of a
shell-command parser being *silent under-matching* (a command slips through and
the guard says nothing). That is precisely a gate that is green while the thing
it guards is unguarded.

The cost of my recommendation, stated plainly: a subprocess per matched tool
call, which is what the classic hook already costs — so the migration buys
**flexibility** (bidirectional `next()` wrapping, `agentId` lane discrimination,
worktree scoping, `{deny}` reasons the model reads) and buys **no latency win**.
That is a fair trade, but it should be made with eyes open, not as a side effect
of a ruling that said "command parsing moves to TS".

I cannot overrule the prior ruling and I am not trying to. I am flagging that it
was made before M8 and M9 were on the table.

**If the ruling stands and the parser IS ported:** then it is unambiguously its
own ticket, not part of the reference implementation. The reference
implementation is a 91-line path-suffix match with no parsing at all; bolting a
shell parser onto it merges a proven, arm-able change with an unproven one and
loses the ability to say which half broke.

---

# THE ASTRA VERDICT

## Lane provenance — what actually ran

**The lane did NOT refuse.** It returned a complete verdict, 30,137 bytes,
after ~9 minutes wall clock.

Observables, in preference order:

- **The process arguments**, read live from `ps` while it ran (PID 6848):
  `codex exec --sandbox read-only --model gpt-6-astra -o
  /tmp/kb-codex-astra-advisor-verdict.md -c model_reasoning_effort=xhigh
  --dangerously-bypass-hook-trust -`. This is a stronger observable than the
  banner's `sandbox:` line, and far stronger than its `model:` line, which
  reports the SESSION model and has been measured to print identically for an
  Astra run, a Sol control and a bogus slug.
- codex-cli **0.154.0** (`npm-openai-codex/0.154.0`).
- `--timeout 1800` under `kb-codex`'s own 5400s ceiling; not reached.
- No `--ephemeral`, so the session persists and is reviewable via
  `mise run kb-session-search`.
- Raw verdict copied verbatim to
  `.agent/kb/reports/agents/astra-function-hooks-verdict-raw.md`.

**Its own stated limitation, verbatim:** *"The required graph query failed
because mise could not create a temporary file in this read-only session; graph
health remains **UNVERIFIED**. No repository files were changed."* That is
correct and expected — the graph work was done on this side (above), which is
what the lane's brief assumed.

## 🔴 The verdict, first line, unhedged

> **Q9 verdict: put the TypeScript shell parser in its own ticket; ship the
> settings guard first and retain the tested Python parser until a replacement
> proves equivalent behavior.**

And the reframing that matters more than the ticket boundary, verbatim:

> *"This revisits the earlier TS-port preference without overruling the settled
> function-hook mechanism: **the interception can move to TypeScript while the
> policy implementation remains Python**."*

**This converges with the independent read I wrote above BEFORE the lane
returned** (see "My independent read on Q9"). Two lanes, different evidence —
mine from `.codex/hooks.json` and the no-Node constraint, Astra's from
behaviour-preservation risk — reached the same place. That agreement is worth
more than either argument alone.

## The risk that decides Q9 (Astra's words)

> *"The decisive risk is **a migration that passes its new tests while silently
> dropping an existing write form**. A parser library reduces syntax work; it
> does not supply your repository's interpretation of writes."*

And the ordered decision procedure it gives for the parser ticket:

1. **Probe an official process capability** — whether this build permits a
   usable process call through `$`, with arguments, input, output, cancellation
   and timeout behaviour, is **UNVERIFIED**. Node's `child_process` is
   unavailable under the loader constraints.
2. If supported, prefer a **thin TS adapter invoking the existing Python through
   its mise task**. Pass the intercepted command as *data*; **do not execute it
   to analyse it**. Return a schema-defined decision and **distinguish analysis
   failure from permission to proceed**.
3. **Measure end-to-end overhead** against the classic hook. *"A function hook
   that still spawns Python does not remove the spawn cost."* Latency
   **UNVERIFIED**.
4. If the bridge is unavailable or too expensive, evaluate the vendored-parser
   route, preserving the Python behavioural cases **plus independently authored
   expected outcomes**.
5. **Until one route passes, retain the existing classic Bash enforcement under
   an explicit migration exception.**

Plus a trap I had not considered: *"Also probe whether invoking a process
**re-enters relevant hooks**. Do not introduce recursion or a persistent worker
merely to avoid measuring a straightforward bridge."* That is the shim-recursion
class this repo has already been bitten by once (the renovate `node-gyp` hang).

And: *"A timeout, malformed response, or loader error must never be relabeled as
'unsupported syntax' and quietly allowed."*

## Step zero — Astra's adoption matrix (condensed; full text in the raw file)

Its framing is the useful part: **distinguish a dependency usable by repository
tooling from one usable INSIDE the mod loader.** Node tools can run through mise
in development without being importable by a function hook.

| Candidate | Verdict |
|---|---|
| Anthropic's generated `claude-code.d.ts` + published built-in mods | **ADOPT as the runtime reference** — regenerate from the pinned executable, record version + declaration digest |
| Native `claude plugin validate` | **ADOPT for packaging validation** via a task — but it does not prove module execution or enforcement |
| Claude Agent SDK | **Consider as an external live-test driver**; prefer the real CLI if that avoids another integration |
| pytest (+ optional fast-check) | **Reuse pytest as coordinator**; dev deps are outside the restricted loader |
| A ready-made third-party mod framework/harness | **No recommendation — UNVERIFIED**, explicitly *not* a claim that none exists |
| **OPA/Rego** | **DO NOT ADOPT for the reference guard.** WASM runtime reachability inside the loader UNVERIFIED; running OPA externally adds a process/service without removing event extraction or path normalization |
| **Cedar** | **DEFER** — five protected paths do not justify another policy language |
| **Conftest** | **REJECT** unless inventory finds existing adoption; existing Python gates occupy this role |
| **CUE / Jsonnet** | **DO NOT** introduce a second source of truth beside the mandated JSON Schemas |
| **shell-quote** | Best small candidate to *investigate*; CommonJS so a bare import is forbidden; a pinned transformed relative `.ts` is plausible but UNVERIFIED — and it would not replace the write-destination semantics |
| **bash-parser** | **REJECT** for the reference implementation — substantial dependency graph |
| **tree-sitter-bash** | **DEFER** — needs a runtime, and does not identify which `tee`/`sed`/`python` args are writes |
| **mvdan/sh via WASM** (`sh-syntax`) | Strong parser candidate *outside* the reference implementation; WASM reachability UNVERIFIED |
| **nix-shell-parser** | UNVERIFIED — *"Do not select it from its name"* |
| **the existing Python parser** | **RETAIN as the production baseline** |

Its rule-shape recommendation, which lands exactly on this repo's codegen
convention: *"**Rules should be data where their semantics are simple.** Put
protected paths, rule IDs, tool selectors, scopes, dispositions, and exception
records in schema-governed inputs. Generate relative `.ts` imports containing
literals and generated types. Keep a small evaluator for those specific rule
kinds; **do not create a general policy language**."*

One important correction it makes to the brief's own premise: *"The import
restriction does **not** prove bundled dependencies are impossible. It proves
ordinary bare package imports are unavailable."*

## The subagent team — Astra's roster: Ray's six plus THREE added

| Role | Owns | Output | Objective check |
|---|---|---|---|
| **Tooling researcher** *(added)* | Existing-tool evaluation and capability evidence | Adoption/rejection matrix with versions, licenses, probes, unknowns | The selected dependency **loads through its intended path**; rejections have reproducible reasons |
| **Architect** | Runtime boundary, rule placement, scope, compatibility | ADR + decision tables | Every requirement maps to an **observable predicate** or an explicit limitation; no assumed capability lacks a probe |
| **Planner** | Ticket dependencies, ownership, acceptance commands, cutover order | Tracked dependency graph + per-ticket contracts | No orphan rule, circular dependency, undefined proving command, or **retirement without replacement evidence** |
| **Implementer** *(added)* | One bounded component or migration slice | Reviewable commit + local evidence | Focused checks pass; generated output reproduces |
| **Code-reviewer** | Cold review of correctness and maintainability | Findings **or an explicit no-findings verdict bound to that commit** | Findings name reproducible behaviour; a fix triggers a fresh review of changed scope |
| **QA** | Scenario matrix and expected outcomes | Positive, negative, boundary, startup, compatibility cases | **Independently authored** expected decisions cover every supported rule × tool × scope |
| **Verifier** | Execution evidence and **fail-arm validity** | Receipts with raw results, identities, counts, restoration evidence | Real tools execute; intended mutations produce the intended failure; restored production passes |
| **Reliability improver** | Bounded self-healing / optimisation | Diagnosis + **one** candidate repair | Candidate preserves coverage on independent cases; benefit is measured |
| **Release custodian** *(added)* | Activation, source identity, cutover, rollback, delivery | Loaded-version evidence, retirement ledger, remote-main receipt | **Tested bytes match deployed bytes**; supported cold launch succeeds; the commit is present on remote `main` |

The three added roles each close a specific hole: **tooling researcher** because
Ray's step-zero rule has no owner otherwise; **implementer** because the six
named roles are all planning/checking and none builds; **release custodian**
because M2 (untracked, unregistered) and fact 8 (plugins are COPIED to the cache)
mean "it works on disk" and "it is what runs" are different claims with no owner.

### The self-healing role, made concrete — this is the part Ray asked about

**What it MEASURES** — six metrics, and the fifth and sixth are what stop it
gaming the first:

- **Guard observation coverage** — matching opportunities seen by the guard ÷
  opportunities identified independently from tool traces.
- **Missed enforcement** — prohibited operations that actually executed.
- **False denials** — legitimate operations refused, *including worktree-authorized edits*.
- **Task completion** — whether agents can finish the intended work.
- **Operational health** — cold-start readiness, loader errors, source mismatch,
  unsupported parsing, latency.
- **Compliance** — with **raw numerators and denominators**, never a bare rate.

🔴 **Two anti-gaming rules stated outright:** *"Zero opportunities means **N/A**,
not 100% compliance. Missing guard telemetry is a **liveness failure**, not
evidence of zero violations."*

**What it may CHANGE:** implementation repairs, deployment repairs, clearer denial
guidance, measured efficiency improvements. **What it may NOT change** — and this
is the answer to "how do you stop it optimizing a metric while the guard rots":

> *"Changing protected paths, exclusions, expected outcomes, coverage
> definitions, or **DENY into WARN** is a **policy change**, outside autonomous
> optimization."*

**Stopping condition:** stop after **two** candidate attempts, any hard-invariant
regression, or an exhausted ticket budget — then escalate with evidence. Success
requires all independent correctness checks **plus** the claimed improvement.

And on this repo's own 0/19-vs-62→0 history, which I put in the prompt as the
available signal: *"Retain [it] as motivation, but **do not compare future rates
without preserving their opportunity counts and workload context**."* That is a
direct application of `probes-need-a-control-arm.md` rule 6.

Its final "would not": *"I would not let the self-improving role edit its own
success criteria."*

## The ticket chain — G00…G12, with a proving command and a FAIL arm each

Astra states plainly that the task identifiers are **proposed contracts, not
claims these tasks exist**, and that each ticket must deliver its named task as
Python under `python/src/kb_setup/` invoked through mise — *"record a narrow
language-policy exception for the settled TS mod surface"* (i.e. `zero-bash-logic`
gains a documented carve-out, it is not silently violated).

Its `--arms` contract, which every proving command must satisfy: run unmodified
successfully → apply **each** mutation separately in an isolated fixture → show
the check returning nonzero **for the expected invariant with the expected
diagnostic** → restore → rerun green → confirm restoration → and **return nonzero
for missing tools, unexecuted cases, malformed evidence, or missing controls**.
Explicitly: *"Neither a compiler failure nor an unrelated permission refusal
counts as a behavioral mutation being caught."*

| # | Delivers | Deps | Proving command | FAIL arm | Size |
|---|---|---|---|---|---|
| **G00** | Inventory + reuse decision: stable IDs mapping all 18 registrations, 7 modules, 13 invariants + 2 subsections to owners/scopes/evidence/dispositions | — | `mise run kb-guard-programme-check -- --phase inventory --arms` | Remove an invariant mapping, or add an unclassified hook registration | M 1–2d |
| **G01** | Runtime contract: locally regenerated declarations + live probes for event fields, imports, `$`, **process access**, fs, namespace bridging, tiers, the worktree bug | G00 | `mise run kb-mod-runtime-check -- --arms` | **Read `agent_id`** in the adapter → the real delegated-call assertion fails. Separately add a JSON import + illegal `$` binding → load failures must be **visible and fatal** | M 2–3d |
| **G02** | Genuine codegen: schema-owned policy data, generated models/enums + TS literals, **truthful provenance headers**, drift gate | G00 | `mise run kb-guard-codegen-check -- --arms` | Change a generated path, delete an output, change schema input without regenerating | M 1–2d |
| **G03** | Settings reference behaviour on generated policy + verified adapters | G01,G02 | `mise run kb-settings-guard-check -- --live --arms` | Replace DENY with continuation → prohibited delegated edits execute. Remove the worktree exception → authorized worktree edits fail their positive control | M 2–3d |
| **G04** 🔴 | Cold bootstrap + liveness: explicit activation, **the tracked flag**, independent SessionStart warning, session-bound readiness evidence, `kb-gates` integration. **This releases the reference guard.** | G03 | `mise run kb-guard-liveness-check -- --cold --arms` | Remove the flag; disable registration; corrupt the module; serve a **stale cached copy**; substitute an earlier session's receipt. Each warns AND fails the gate; **a warmed second launch cannot rescue a failed first session** | L 3–5d |
| **G05** | Enforce the direction: rule file + `AGENTS.md` + structural lint on new/broadened classic enforcement without a recorded exception | G00,G02 | `mise run kb-guard-direction-check -- --arms` | Add classic enforcement with no exception; then **broaden an excepted matcher beyond its recorded scope**. Both fail; the narrow form passes | S 1d |
| **G06** | Parser placement: the measured Python-bridge-vs-vendored-TS decision **and its implementation** | G01,G02,G04 | `mise run kb-shell-policy-check -- --live --differential --arms` | Break `cd` tracking and **each** supported write mechanism separately. **A bridge timeout must fail readiness and must not permit the operation** | L 3–6d |
| **G07** | Repo-owned file-tool migration incl. the 8 instruction-edit registrations, preserving complete effective coverage | G04,G05 | `mise run kb-file-policy-check -- --live --arms` | Drop one covered matcher/tool adapter/path case while leaving a happy path intact | M 2–3d |
| **G08** | Repo-owned command migration through G06's route + worktree-workflow compatibility | G05,G06 | `mise run kb-command-policy-check -- --live --arms` | Disable each migrated rule separately. **Enable the known-broken native isolation combination → compatibility validation fails BEFORE that workflow is advertised as supported** | L 3–5d |
| **G09** | Prose→enforcement for mechanically decidable clauses, with **explicit partial coverage** for the rest | G00,G02,G04,G05 | `mise run kb-do-not-check -- --live --arms` | Put derived output outside the two allowed dirs into the candidate index; omit ingestion evidence; attempt a prohibited config write | L 3–5d |
| **G10** | **Graphify-owned** migration: the two owner-side hooks through the fork's workflow, pin + skill update, effective-behaviour verification | G01,G04 | `mise run kb-guard-graphify-check -- --live --arms` | Disable each third-party guard, or substitute an older fork artifact | L 3–5d **+ external wait** |
| **G11** | Bounded improvement loop: role config, independent metrics, candidate evaluation, stopping rules | G04,G07 | `mise run kb-guard-improvement-check -- --arms` | Supply a candidate that improves compliance by **dropping observations, suppressing telemetry, converting DENY→WARN, or refusing all work**. Every one is rejected | M 2–3d |
| **G12** | Cutover: retire only proven replacements, account for residual exceptions, final review/gates, **delivery verified on remote `main`** | G05–G11 | `mise run kb-guard-delivery-check -- --remote origin --branch main --arms` | Remove a replacement but keep its retirement record; remove the liveness dependency from `kb-gates`; present another commit's evidence; present an unmerged branch | M 1–2d |

**Parallelism:** G01 ∥ G02 after G00. G05 runs alongside the reference work.
After G04: G06, G07, G09 and owner-side G10 proceed independently; **G08 waits
for G06**. Serialize edits to shared schemas/settings; run mutation arms in
separate fixtures.

🔴 **The ticket that blocks the most if it slips: G04.** *"Without a proven
loading and liveness path, every later port can be correct on disk and absent at
runtime."* G10 may be the longest external wait but **must not delay shipping the
settings reference**.

### Three acceptance details Astra says must be written INTO the tickets

- **G03's matrix** must include *"a worktree lane accidentally targeting the
  canonical checkout by absolute path"* — because **worktree authority applies to
  the DESTINATION inside that worktree, not to every destination merely because
  `.git` is a file.** 🔴 That is a live defect in the current reference
  implementation: `register.ts` derives the verdict from `$.session.cwd()` alone
  and never compares it to `e.file_path`, so a lane in a worktree writing an
  absolute path into the main checkout is ALLOWED.
- **G04's independence**: *"a missing mod cannot reliably warn about its own
  absence."* Use an **independent** SessionStart checker — possibly an existing
  classic lifecycle hook with a narrowly recorded reason. Before current-session
  evidence exists, report **"unproven", never "live"**. If all hooks are
  disabled, an in-session warning cannot be guaranteed; the launcher and the
  external gate must catch that.
- **G09's honesty**: inspect actual staged/candidate content for derived-output
  rules; for ingestion check manifests, provenance and receipts. *"Do not label
  semantic source suitability or human intent as fully enforced."* — which agrees
  with **M7**'s finding that `do-not.md` #6 is not mechanically checkable.

## Green-and-useless: 16 ranked failure modes (Astra's judgment, not a statistic)

Ranked most→least likely. The top five are the ones I would budget for.

| # | Failure | The observable that catches it |
|---|---|---|
| **1** | The mod is **untracked, unregistered, disabled, or relies on an absent flag** | Clean-checkout launch through the supported entry point; a real matching event and denial; effective-config ↔ tracked-file reconciliation |
| **2** | `agent_id` read from a function event → **every lane looks like the main thread** | A **real spawned lane** attempts the protected op; record the received discriminator. *"A synthetic object supplied by the implementation is insufficient"* |
| **3** | A **warm cache hides the first-session gap** | Start with an empty plugin cache; score the **first** usable session separately. *"Never average first-run failure with second-run success"* |
| **4** | Module compilation or capability errors stay **only in a debug log** | Capture loader diagnostics every live run; deliberately break imports and `$` |
| **5** | Tests exercise the **tracked source** while Claude executes a **cache copy** | Bind evidence to the resolved loaded artifact **and its digest**; intentionally make them differ |
| **6** | **Another** classic hook or an ordinary permission denial makes a **dead** function guard look effective | Attribute the denial to the expected rule; prove the tool **executes** when that guard is mutated away; include the bypass-permissions control |
| **7** | "Generated" output maintained **by hand**, or a drift check that misses deleted/untracked files | Regenerate from committed schema inputs into an isolated location; compare the **complete file set and bytes** |
| **8** | Eight registrations become **one hook with incomplete coverage** | Compare effective **rule × tool × scope** cases before/after. *"Raw registration counts are not the denominator"* |
| **9** | The gate validates **yesterday's receipt** while the current session is unguarded | Match session identity, run nonce, loaded-source digest, effective config, runtime version, commit |
| **10** | A mutation runner calls **any nonzero** result success, or leaves a mutation behind | Require the **expected diagnostic** + observed behaviour, then restored green + a final tree comparison |
| **11** | Event-**blob** matching blocks replies or quoted examples | A real outgoing message quotes a forbidden token and still succeeds |
| **12** | Worktree detection becomes an **unconditional exemption**, or session root is mistaken for the operation's **destination** | Test own-worktree writes, canonical-checkout destinations **from that lane**, subdirectory launches, relative paths |
| **13** | Python/TS "parity" = both implementations agreeing on the same **wrong** expectation | Retain **independently authored** outcomes and isolated filesystem results, not equality between implementations |
| **14** | Wrong event **namespace** or continuation routing skips enforcement | Exercise the selected event, any `classic.PreToolUse` bridge, and the installed composition. *"A registration log alone does not count"* |
| **15** | Enabling native worktree isolation later **breaks every Bash call** (`#92533`) | A live compatibility probe that rejects the combination while unsupported |
| **16** | Compliance rises because **opportunities disappear**, all work is denied, or hard cases become exclusions | Independent opportunity counts, positive controls, task-completion checks, reviewed coverage-inventory changes |

**#1 is already true today** — M1 (flag absent) and M2 (untracked, unregistered)
are that failure mode, measured, right now. **#7 is already true today** — M4,
the generated header with no generator. The programme's first ticket is
therefore not speculative risk management; it is fixing two live instances.

## What Astra would NOT do — including two objections to the SETTLED list

Flagged, not overruled, exactly as asked.

1. **"I would not treat the preview API as stable."** Mitigation: pin the
   executable, regenerate declarations, require live control arms before
   accepting a version change. (Ties to fact 12: zero CHANGELOG entries through
   2.1.268, and to the marketplace README's *"every release rewrites them, so a
   checked-in copy goes stale and lies to you."*)
2. **"I would not force all implementation logic into TypeScript."** Keep the
   interception in the settled mechanism; choose parser placement from measured
   compatibility, behaviour and cost.
3. **"I would not make the reference guard wait for an OPA integration, generic
   framework, or parser rewrite."** Its unresolved problems are activation,
   provenance, generation, scope and liveness — all of which M1/M2/M4 confirm.
4. 🔴 **OBJECTION TO A SETTLED RULING — "I would not promise that warning plus
   gate failure prevents every unguarded action."** The settled liveness design
   (SessionStart warning + `kb-gates` failure) **detects**, sometimes *after* a
   session has started. Cost: the cold-start gap (fact 7) is a real unguarded
   session that neither half prevents. Cheapest mitigation: *"a supported
   bootstrap/launch task that establishes readiness before handing over ordinary
   work, plus an explicit unproven state elsewhere."*
5. 🔴 **OBJECTION TO A SETTLED RULING — "I would not mistake the five-path list
   for protection of the whole enforcement system."** The mod itself, the schema,
   the generator and the liveness machinery all fall **outside** the five
   protected paths. Astra does **not** propose widening the list (that is Ray's
   call and it is settled); the cheapest mitigation is merge review plus
   mutation-tested gates.
6. **"I would not exempt a merge merely because its author worked in an
   authorized worktree."** Worktree authority *shifts* responsibility to the
   merge boundary; validate the resulting candidate tree and **refresh evidence
   after conflict resolution**.
7. **"I would not remove the two Graphify hooks by editing only KB settings."**
   Owner-side delivery + a verified pin transition; installation stays
   `mise run kb-skill-refresh`.
8. **"I would not count a recorded classic exception as completed migration."**
   Exceptions need exact scope, owner, reason, review trigger — and lifecycle
   hooks, temporary parser retention and third-party ownership are *different*
   reasons.
9. **"I would not expand this into shell-evasion work or a general security
   boundary."** Preserve the accepted `sh -c` / `eval` / substitution limits —
   *while distinguishing those limits from accidental loss of already-supported
   behaviour*.
10. **"I would not let the self-improving role edit its own success criteria."**

## What I could not verify

- **The graph could not answer the programme question.** `mise run kb-query`
  returned rc=3 TRUNCATED (49 of 157 nodes). Expected: the function-hooks surface
  is unreleased, so no pinned source carries it. Not reported as an absence.
- **Astra's own graph access failed** (read-only sandbox, mise could not create a
  temp file). It said so. All its repository facts come from my prompt, which is
  why every measured fact above is stated with its command.
- **Whether `.claude/mods/**` is scanned natively** with no marketplace
  registration — UNVERIFIED. M2 shows it is registered nowhere; the team lead
  reports a live three-armed proof. Both can be true only if the path is
  auto-scanned, and that has not been shown.
- **`$.process.run`'s signature, sandboxing and latency** — UNVERIFIED by both
  lanes. It is the pivot of Q9's implementation and needs G01's probe.
- **Whether `claude plugin validate` covers this preview's module constraints** —
  UNVERIFIED (Astra's own caveat).
- **The `fs.read`/`fs.readFile` naming discrepancy** between the 2.1.263 runtime
  load line and the 2.1.267 declarations — unresolved in the prior report, still
  unresolved. It matters because `register.ts` calls `$.fs.list`.
- **Astra's external links** (OPA WASM docs, Cedar, fast-check, shell-quote's
  `parse.js`, `sh-syntax`) were not fetched by me. Treat them as leads.
- **Latency of any bridge**, and **whether a spawned process re-enters hooks** —
  both flagged by Astra, neither measured.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issues #92533 (worktree isolation, OPEN, `bug`/`has repro`, 0 comments, no movement since 2026-09-06) and #92469 (the `/plugin-types` omission + the runtime hooks load line); `contents/mods` → `README.md diff sec-default telemetry`
- [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) — issues #1 and #3 read in full; its `description` field is what shows the `deny` critique is about its own engine
- [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) — via the prior report; the MIT marketplace with `secret-redactor`, the borrow target
- [lossless-claude/lcm](https://github.com/lossless-claude/lcm) — via the prior report; the project that already completed this migration and hit the no-Node wall
- [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) — via the prior report; the third-party copy of `claude-code.d.ts`. Regenerate with `/plugin-types`; do not cite a checked-in copy
- [ljharb/shell-quote](https://github.com/ljharb/shell-quote), [vorpaljs/bash-parser](https://github.com/vorpaljs/bash-parser), [tree-sitter/tree-sitter-bash](https://github.com/tree-sitter/tree-sitter-bash), [mvdan/sh](https://github.com/mvdan/sh) — parser candidates named by Astra; NOT fetched by me, leads only
- [anthropics/claude-agent-sdk-typescript](https://github.com/anthropics/claude-agent-sdk-typescript) — named by Astra as a possible live-test driver; not fetched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — owner of 2 of the 12 PreToolUse registrations (G10)

**STATUS: COMPLETE.**
