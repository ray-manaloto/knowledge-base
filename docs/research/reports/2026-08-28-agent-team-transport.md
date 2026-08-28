# The Claude↔Codex team is a transport — round 2 (2026-08-28), synthesis

**Promoted verbatim** from `.agent/kb/reports/agents/synthesis-agent-team-0828.md` (kb-synthesist, opus) in session kb-20260827.09 at HEAD `31adf68981fe`. Extends `2026-08-27-claude-codex-handoff.md`. Inputs promoted alongside: `2026-08-28-codex-binary-probe.md`, `2026-08-28-evidence-transport-0828.md`, `2026-08-28-trackers-agent-team.md`; the two backend-path lane reports and the codex history report remain in `.agent/`. The architect's own arm this session: `mise run kb-graphify-native-extract -- --backend openai-cli --dry-run` → rc 0. `fable-advisor` verdict: pending at promotion time — see the annotation appended at the bottom when it lands.

---

# Synthesis: a Claude/Codex agent team on limited Fable-5 tokens, ending at graphify on `openai-cli`

**Question (Ray, verbatim, `docs/direction/2026-08-28-ray-directives.md:36-46`):** "how to build a
claude/codex agent team that optimizes use of limited fable-5 tokens and communication between
claude and codex agents — and the ultimate goal of graphify setup starting with openai-cli backend".

**Baseline extended, never re-answered:** `docs/research/reports/2026-08-27-claude-codex-handoff.md`
(§5 interface + offload rule + three Fable points) and `docs/research/reports/2026-08-06-roster-synthesis.md` §5.

**Inputs** (all `.agent/kb/reports/agents/`): `codex-binary-probe.md` (live executions,
codex-cli 0.150.1) · `evidence-agent-team-0828.md` (opus evidence sweep) · `trackers-agent-team.md`
(trackers + source read at `rust-v0.150.1`) · `openai-cli-backend-path-explore.md` and
`openai-cli-backend-path.md` (two independent routes to the same setup path) ·
`codex-history-agent-team.md` (codex-authored dated timeline). Plus one arm run by the architect
this session.

**Labels used throughout.** MEASURED = executed this round (this session or a named lane's live
execution). DERIVED = computed here from measured or cited figures, arithmetic shown.
INHERITED = carried from a prior round or another report without re-derivation.
CONFIRMED = primary source (pinned source read) or execution. ANECDOTAL = issue text, blog,
third-party README.

---

## 1. Answer

The team does not need new roles; it needs a **typed, file-first transport with an executor-identity
attestation**, and the one thing that has actually changed since the baseline is that three of its
five interface recommendations are now MEASURED rather than assumed — `--output-schema` works and
validates, `exec resume --last` recovers a SIGTERM'd run's state, and `--json` carries **no
timestamps**, which refutes the baseline's "emit a clock" as written
(`codex-binary-probe.md:12,19-21`, MEASURED on codex-cli 0.150.1). The transport should stay
**`codex exec` subprocess + `--output-schema` + `resume`**, not `codex mcp-server`: the source read
at `rust-v0.150.1` correctly shows `mcp-server` exposing usable `codex`/`codex-reply` tools
(`trackers-agent-team.md:36-40`, CONFIRMED), but the **installed binary prints a DEPRECATION warning
on stderr when you actually run it** (`codex-binary-probe.md:24`, MEASURED) — a runtime fact a source
read cannot see, so the executed probe wins and `app-server` is the only forward-looking alternative
(experimental, **unexecuted**). Scarce Fable stays at the baseline's three decision points, but those
three now sit in open contradiction with Ray's 2026-08-27 "always consult fable-advisor before any
codex-implementer dispatch" and with `kb-advisor.md`'s own "sparingly" — an unresolved policy
conflict, not a research gap (`codex-history-agent-team.md:86`). On the ultimate goal: `openai-cli`
is **wired, opt-in, and one command from running** — the architect dry-ran it this session (rc 0,
argv `graphify extract sources/graphify --mode deep --backend openai-cli --out .agent/kb/native-extract`,
serial, MEASURED) — and what blocks the *provider-reaching proof run* is bookkeeping and cost, not
mechanism: four governance surfaces still assert the prohibition Ray lifted on 2026-08-25, and a
serial run over the pinned clone is a multi-hour, single-threaded spend.

---

## 2. What changed since the baseline

| # | Baseline claim | Verdict | Evidence |
|---|---|---|---|
| 1 | §5 rec 4 — "**Emit a clock.** `codex exec --json` gives a JSONL event stream; record dispatch, first token, and completion" (`…handoff.md:167`) | **REFUTED** on 0.150.1 | `codex-binary-probe.md:21` — 0 of 6 event lines carry `timestamp/ts/time/created_at`; control arm: `"type"` matched 6/6 on the same file, same command shape. MEASURED. An external wall-clock wrapper is required. |
| 2 | §5 rec 3 / Not-measured — "`codex exec resume` … the recommendation most likely to be wrong" (`…handoff.md:200`) | **CONFIRMED** | `codex-binary-probe.md:20` — SIGTERM'd 4 s into a turn (`wait` rc=143, **no `-o` file ever written**), `resume --last` recalled both the remembered number and mid-task progress. MEASURED. Recovery came from persisted session state, not a completed output. |
| 3 | §5 rec 1 — `--output-schema` types the handoff | **CONFIRMED (happy path only)** | `codex-binary-probe.md:19` — 1-key required-int schema produced exactly `{"answer":4}` to both `-o` and the stdout transcript. MEASURED. **NARROWED**: enforcement under a *violating* model response was not tested (`:33`). |
| 4 | §3a — "prompts saying only 'return the full report as your final message' produced **8 in 8**" (`…handoff.md:104`) | **NARROWED, ~7×** | `evidence-agent-team-0828.md:52-58` — 8 resends over **55** un-instructed prompts = 14.5%, not 100%. The baseline's denominator was its numerator. Direction holds: all 8 resends came from the NEITHER arm, 0 from the other 103. MEASURED over 107 parsed in-window transcripts. |
| 5 | §2 — "the result survives, the notification does not … nothing was lost **only because** incremental writes are required" (`…handoff.md:64-67`) | **PARTLY REFUTED** | `evidence-agent-team-0828.md:186` — for read-only lane types (premise-verifier, advisor) **no disk report exists to survive**; v4/v5 were recovered from the *transcript*. The durable channel is transcript-first for those types. |
| 6 | auto-memory — "one SendMessage recovers the full report in ~1 min" | **REFUTED** | `evidence-agent-team-0828.md:187` — 2 of 4 resends failed (v4: 3 idle notices + 2 resends → nothing; v5: 2 + 1 → nothing). Settled recovery: **transcript first, one resend at most, never a second wait**. |
| 7 | §4 — "zero reports record an orphaned codex CLI process surviving a 'completed' task" | **CONFIRMED (still zero)** | `evidence-agent-team-0828.md:188` — a new report explicitly probes and finds none; the one live process was an unrelated pre-existing `codex-otel` daemon. |
| 8 | §5 roster — "**No new roles are recommended**" | **CONFIRMED, unchanged** | `evidence-agent-team-0828.md:161-175` — `.claude/agents/` untouched since 2026-08-06 (`a41f0b5c`); #116 still OPEN with **0 comments**. No input in this sweep proposes a role. See §6 rec 4 for the one thing that *is* new — a contract, not a role. |
| 9 | §4 fragility taxonomy | **NEW class the baseline had no row for** | `evidence-agent-team-0828.md:35,103` + `codex-history-agent-team.md:78` — the `codex-lychee-spike` lane wrote its files with its **own Bash** and never launched `codex exec` (#559). A watchdog kill yields a detectable *empty* result; a substitution yields a *complete, plausible* result attributed to the wrong model family. |
| 10 | §5 rec 5 — "stop stripping the `:variant`" | **UNCHANGED, and now more load-bearing** | `codex-history-agent-team.md:74` (INHERITED) — 157/159 review artifacts could not identify the model family. Row 9 shows why that is a correctness problem, not a bookkeeping one: cross-family review routing depends on it. |
| 11 | (baseline silent) — a token-budget cap per Codex delegation | **NEW: none exists** | `trackers-agent-team.md:314-335` — the only budget field in the pinned source is `GoalsToml.max_goal_token_budget` (`codex-rs/config/src/config_toml.rs:659`), scoped to goal mode, **not** `exec`. `--max-steps`/`--max-agent-turns` for `exec` is openai/codex#33294, **OPEN**. CONFIRMED (source) + ANECDOTAL (tracker). Only levers: reasoning-effort tier before dispatch, or an external timeout. |
| 12 | (baseline silent) — `codex exec review --output-schema` | **NEW: a false-success trap** | `trackers-agent-team.md:49-54,283-298` — the `ExecCommand::Review` arm never calls `load_output_schema`; the flag is accepted, silently dropped, exit 0, free-form prose. openai/codex#38545 OPEN. CONFIRMED (source read at the pinned ref) + ANECDOTAL (issue). **Never route a schema-dependent call through `exec review`.** |

---

## 3. The transport decision

### The three options actually available

| option | status on the **installed** binary | schema | session continuation | verdict |
|---|---|---|---|---|
| **A. spawn `codex exec` + `--output-schema` + `exec resume`** | MEASURED working, all three primitives (`codex-binary-probe.md:19-21`) | yes, validated on the happy path | `exec resume --last`, MEASURED across a SIGTERM | **adopt** |
| **B. `codex mcp-server`** | MEASURED working — full MCP `initialize` round trip, `protocolVersion 2025-06-18`, `serverInfo codex-mcp-server/0.150.1` — **but stderr says DEPRECATED, will be removed** (`codex-binary-probe.md:24`) | via the `codex` tool's `config` overrides | built in — `codex-reply` by `threadId` (`trackers-agent-team.md:36-40`) | **do not build on it** |
| **C. `codex app-server`** | exists per `--help`, marked `[experimental]`, **never executed** (`codex-binary-probe.md:23,32`) | unknown here | `thread/*` + `turn/*` JSON-RPC 2.0 over stdio | **watch, do not adopt** |

**The one disagreement between inputs, and which wins.** `trackers-agent-team.md:36-40,266-274`
reads the pinned source at `rust-v0.150.1` and calls `codex mcp-server` "a native, ready-to-register
MCP server Claude Code can add via `.mcp.json`" — CONFIRMED as to *mechanism*, and this synthesis
does not dispute a line of it. `codex-binary-probe.md:24` **ran** the same subcommand on the
installed `codex-cli 0.150.1` and captured a DEPRECATION warning on **stderr**.
**The executed probe wins**, for a stated reason rather than a preference: the two are not in
conflict about what the code does, only about what the running binary *says about its own future* —
and a deprecation notice printed at runtime is invisible to a source read of the tool config
module. Same version on both sides (`rust-v0.150.1` ≡ `0.150.1`), so this is not a version-skew
artifact. Building the transport on B would be building on a surface its owner has announced it is
removing.

`app-server`'s status is ANECDOTAL beyond the `--help` line: three independent third-party
integrations (OpenClaw, Claudian, `happy`, `etienne`) converge on the same JSON-RPC-over-stdio
description (`trackers-agent-team.md:229-238`), which is a strong cross-check and still four
secondary sources.

### The difference, drawn

```mermaid
sequenceDiagram
    autonumber
    participant A as Claude architect
    participant F as report file<br/>(.agent/kb/reports/)
    participant X as codex process

    rect rgb(235,245,255)
    Note over A,X: A — codex exec (ADOPT). One process per turn; state on disk.
    A->>X: spawn `codex exec --output-schema s.json -o out.json -`
    X-->>F: incremental writes (lane's own duty)
    X-->>A: exit + validated {…} in out.json
    Note over A,X: watchdog kill? -> `codex exec resume --last`<br/>MEASURED to recover state with NO -o file written
    end

    rect rgb(255,240,235)
    Note over A,X: B — codex mcp-server (DEPRECATED on the installed binary)
    A->>X: MCP initialize (stdio, long-lived)
    A->>X: tool `codex` {prompt, model, config}
    X-->>A: {threadId, content}
    A->>X: tool `codex-reply` {threadId, prompt}
    Note over X: stderr: DEPRECATED, will be removed
    end

    rect rgb(240,240,240)
    Note over A,X: C — codex app-server ([experimental], UNEXECUTED here)
    A->>X: JSON-RPC initialize -> initialized
    A->>X: thread/start, turn/start, turn/interrupt
    X-->>A: streamed turn events
    end
```

The structural difference the sketch is drawing: **A's durable state is a file and a session id on
disk; B and C's durable state is a live connection.** Every measured failure in this repo's history
— idle-without-reporting, the 116-second blackout, the 222.4-minute delivery dead time
(`codex-history-agent-team.md:74`, INHERITED) — is a *connection* failure with an intact result
behind it. A transport whose state is a connection converts those into losses; A converts them into
a `resume`.

### The decision rule for offloading to Codex — baseline §5, updated

**Unchanged core (baseline, `…handoff.md:168-176`):** offload when the work is bounded by a spec the
architect can write in full, and the result is verifiable without the architect's context. Keep it
inline when writing the spec costs more than doing the work, or when the result can only be judged
against conversation the lane will not have.

**Four amendments this round earns:**

1. **Never route a schema-dependent call through `codex exec review`** — accepted, silently dropped,
   exit 0, prose (row 12). Plain `exec` or `exec resume` only.
2. **Budget the dispatch with an external bound, because Codex has none.** There is no per-call
   max-token or max-turn cap for `exec` (row 11). The only pre-dispatch lever is the
   reasoning-effort tier; the only hard bound is a wrapper timeout.
3. **Do not offload work whose spec forbids the lane's own build/verify step.** The one substitution
   on record (#559) and the one 2700 s watchdog kill both trace to a spec the lane could not satisfy
   in its sandbox — the kill's root cause is recorded as `workspace-write` having **no outbound
   network** while the spec demanded a live `gh` check (`evidence-agent-team-0828.md:141-145`,
   MEASURED). Check the sandbox can perform the verification before writing it into the spec.
4. **Require an executor attestation in the returned object**, not just the report (§6 rec 4).

---

## 4. Where scarce Fable-5 buys something

The baseline named three decision points and nowhere else (`…handoff.md:175-190`). **All three are
confirmed by this round's evidence; the *policy around them* is contradicted, and that contradiction
is Ray's to settle, not this report's.**

| baseline point | verdict | this round's evidence |
|---|---|---|
| 1. Before a change expensive to reverse | **CONFIRMED** | This is the only point with independent upstream corroboration: `mar3co/fable-orchestrator` #16 (the plugin this repo runs, its **one open issue**) records that post-bound fix commits shipping with self-review only let real defects through, found later by an external reviewer (`trackers-agent-team.md:204-219`). ANECDOTAL (issue text), but it is the plugin's own maintainer-facing record. |
| 2. When the same problem has resisted two attempts | **CONFIRMED, unchanged** | INHERITED from this repo's own measured pattern (round 2 finds defects in round 1's fix). Nothing this round re-derives it; nothing refutes it. |
| 3. Adjudicating two lanes that disagree | **CONFIRMED, and exercised in this very report** | The `mcp-server` disagreement in §3 is exactly this shape, and it resolved on a stated rule (execution beats source read on a runtime-only signal) rather than on judgment — which is the cheap case. Reserve Fable for the disagreements a rule cannot settle. |

**AMENDMENT — a live policy contradiction, three-way, unresolved.**
`codex-history-agent-team.md:86` names it precisely and it is not a research question:

- the baseline says Fable at **three named decision points and nowhere else**;
- Ray's 2026-08-27 directive says **"always use the fable-advisor with codex-implementer"**
  (`docs/direction/2026-08-27-ray-directives.md:7-15`), adopted verbatim into `.claude/CLAUDE.md:29-51`;
- `.claude/agents/kb-advisor.md:10-27` says Fable is the most expensive model and must be consulted
  **sparingly**.

These can only coexist if the universal pre-dispatch consult is a **short, bounded gate** (a
few hundred tokens: "is this spec complete and verifiable without my context? yes/no + what is
missing") rather than a full advisory pass. That reading is consistent with all three texts and is
the recommendation in §6 rec 5 — but it is a reading, not a ruling, and the three documents still
contradict each other in tracked prose today.

**One cost fact that changes the arithmetic.** The baseline's own diagnosis was that the architect's
expensive work was **re-reading**, not reasoning (`…handoff.md`, §5). Rows 1 and 4 of §2 sharpen
this: the typed contract (`--output-schema`, MEASURED working) removes re-reading directly, and the
one-sentence both-channels prompt fix costs nothing and is applied in only **4 of 107** in-window
dispatches (`evidence-agent-team-0828.md:52-64`, MEASURED) — **3 of those 4 are from the single
session that read the baseline.** The cheapest Fable-token saving available is not a model choice.
It is a sentence in the dispatch prompt that nobody has adopted.

*Caveat carried, not buried:* 0/4 resends on the BOTH arm is consistent with the fix working **and**
with chance at a 14.5% base rate (P ≈ 0.54) — `evidence-agent-team-0828.md:201-205` says so
explicitly. The direction is measured; the magnitude is not.

---

## 5. The `openai-cli` backend — the exact setup path

**Two lanes reached this independently** (`openai-cli-backend-path-explore.md`,
`openai-cli-backend-path.md`) and **agree on every load-bearing point**, which is the strongest
evidence in this report:

| both lanes agree | citation |
|---|---|
| `--backend` is the **CLI-only** selector; **no `GRAPHIFY_BACKEND` env var exists** (control-armed: `GRAPHIFY_OPENAI_CLI_MODEL` and friends *do* hit) | `explore:29` / `path:41` |
| `detect_backend()` **excludes** both `claude-cli` and `openai-cli` from its fallback loop — neither can *ever* be auto-selected | `llm.py:3527-3557`; `explore:29` / `path:41` |
| `clean_env()` needs **no change**: `_call_openai_cli` reads no API key (`llm.py:2289`, `:3217` exempt `bedrock`/`claude-cli`/`openai-cli`); keeping the `OPENAI_API_KEY` strip is now *protective* against the metered fallback | `explore:30` / `path:47` |
| **`kb-graphify-native-extract` is the only task carrying the opt-in.** `kb-build`/`kb-merge` take no backend; `kb-label`'s only opt-in is `--claude-cli` | `explore:31` / `path:55-57` |
| the output goes to `--out`, **never** into aggregate `graphify-out/graph.json` — an explicit "separate, later decision" | `graphify_native_extract.py:112-115`; `explore:31` / `path:57,113` |
| parallelism is **clamped to 1** for `openai-cli` unless `GRAPHIFY_OPENAI_CLI_PARALLEL=1`; the kb lever is `--allow-parallel-claude-cli` (backend-generic despite its name) and lifting it here is **UNTESTED** — the 19-chunk evidence is `claude-cli`'s and "does not transfer" | `llm.py:2973`, `:3772`; `graphify_native_extract.py:796-828`; `explore:37` / `path:61` |
| four governance surfaces still assert the lifted prohibition; `currency.toml` is the one surface that *does* reflect the ruling | `explore:35` / `path:76-85` |
| `kb-build` is **independently broken right now** (`.build-failure.json`, `failed_at 2026-08-27T16:12:49Z`, Cargo.toml zero-node stderr; #397 and #417 OPEN) and does **not** block this experiment | `explore:36` / `path:89-99` |

**One disagreement between them, adjudicated by reading the source this session.**
`path:27` reports finding no `GRAPHIFY_OPENAI_CLI_EFFORT`; `explore:24` reports it exists, default
`ultra`. **`explore` wins** — `path` grepped only the `BACKENDS` dict, where the key genuinely is
not; the var is read at the call site. Re-derived MEASURED this session:
`sources/graphify/graphify/llm.py:2072-2074` —
`"-c", "model_reasoning_effort=%s" % (os.environ.get("GRAPHIFY_OPENAI_CLI_EFFORT", "").strip() or "ultra")`.
It is **not** surfaced as a `kb-graphify-native-extract` flag, so it must be exported in the parent
shell, and `path:120` correctly flags that its survival through `clean_env()` is untraced.

### The path, in order

```bash
# 0. Ensure GRAPHIFY_OUT is unset — its PRESENCE (not truthiness) refuses the run.
#    graphify_native_extract.py:653-663 (#480); GRAPHIFY_OUT="" also refuses.
mise run kb-currency-check          # currency.toml:49 backend_probes = ["claude-cli","openai-cli"]
mise exec -- codex --version        # codex-cli 0.150.1 (MEASURED, codex-binary-probe.md:3)
mise run kb-graphify-native-extract -- --backend openai-cli --dry-run
mise run kb-graphify-native-extract -- --backend openai-cli      # the real run
```

**Step 3 was run this session. MEASURED: rc 0**, resolved argv
`graphify extract sources/graphify --mode deep --backend openai-cli --out .agent/kb/native-extract`,
**serial** — no `GRAPHIFY_OPENAI_CLI_PARALLEL` in the env overlay. That is the arm proving the wiring
is live end-to-end up to the point of spend. Defaults come from `graphify_native_extract.py:239`
(`--target sources/graphify`) and `:246` (`--out .agent/kb/native-extract`).

`_refuse_backend()` (`graphify_native_extract.py:568-593`) reads graphify's **own** `BACKENDS` table
via `graphify_env.installed_backends()` (`graphify_env.py:258-278`) — never a mirrored copy — so a
future upgrade that drops the fork's patch fails closed with a named remedy rather than silently
falling back to the metered `openai` backend.

### Blockers

1. **Four governance surfaces still assert the prohibition Ray lifted on 2026-08-25.**
   `.claude/rules/do-not.md:56-63` #4 · `.claude/rules/ai-cli-invocation.md:25-29` ("Extraction and
   labelling are Claude-only by hard invariant… never an extraction backend") · root `CLAUDE.md:66-71`
   mandate 2 · issue **#455** OPEN. Both are also *mechanically wrong* as the directive predicted:
   they credit `clean_env()` with a carve-out that is really `detect_backend()`'s exclusion list.
   Ray's ruling, verbatim (`docs/direction/2026-08-25-ray-directives.md:26-30`): *"we are going with
   claude-cli and openapi-cli as agents that can perform graphify agentic work — so remove and/or
   refactor the phrasing for #4 in .claude/rules/do-not.md"*. **Three days on, none has been edited.**
2. **Serial only.** Lifting the clamp for `openai-cli` is explicitly untested; `claude-cli`'s
   19-chunk parallel run "does not transfer".
3. **`--model` on a non-default backend is a live footgun**, already fixed once (#499):
   `GRAPHIFY_OPENAI_CLI_MODEL=claude-opus-5` was written on every run omitting `--model`. Omit
   `--model` so graphify's own `default_model = "gpt-5.6-sol"` (`llm.py:217`) applies.
4. **`GRAPHIFY_OPENAI_CLI_EFFORT` defaults to `ultra`** and is not routed through the kb flag surface
   or the printed env overlay — the most expensive setting, invisible in the dry-run.
5. **Nothing merges this output into the aggregate corpus**, by design. A successful run proves the
   backend, not the goal.
6. **`kb-build` is broken** (#397/#417 OPEN) — orthogonal, but it means no route reaches the
   aggregate graph today regardless of backend.

### What the first real run would cost

**MEASURED this session** (`find sources/graphify -type f -not -path '*/.git/*'`): the pinned clone
holds **1,285 files**, of which **343 `.py`** and **363 `.md`** = **706** plausible extraction inputs.

**DERIVED, with its unit mismatch stated rather than hidden.** graphify's own comment
(`llm.py:2090-2092`, INHERITED — graphify's measurement, not ours) reads: *"A measured
single-document extraction took 361 seconds, so the 600-second default is tight; users should raise
`--api-timeout`."* The `claude-cli` precedent over **this same target** was **19 chunks**
(2026-08-23, INHERITED, `codex-history-agent-team.md:32`). If a chunk-call costs what a
"single-document" call costs:

> 19 × 361 s = **6,859 s ≈ 114 minutes**, serial, single-threaded.

**Treat that as an order of magnitude, not a figure.** Three reasons, all of which cut the same way
(toward *longer*): (a) "document" and "chunk" are not established to be the same unit, and the 361 s
was measured on an unnamed document; (b) `openai-cli` at effort `ultra` has no measured per-call time
in this corpus at all; (c) the 600 s default `--api-timeout` is *below* twice the one measured call,
so a slower chunk fails the run rather than slowing it — **raise `--api-timeout` before the first
real run.** The honest statement is: **hours, serial, unbounded by any Codex-side token cap** (§2
row 11).

A cheaper proof exists and was already planned: Ray's 2026-08-25 execution plan was **~25 of 337
`mise` prose files**, serial, then the rest if measurement justified it
(`codex-history-agent-team.md:56`, INHERITED, still unexecuted). That is the run to do first.

---

## 6. Recommendations — cheapest first

Each names the primitive it uses and the failure it fixes. **None proposes a new agent role** — §2
row 8 confirms the baseline's conclusion, and no input in this sweep changes it. Rec 4 adds a
*contract*, which is a different thing.

1. **Put the both-channels sentence in the committed dispatch template.**
   *Primitive:* prose in `.claude/agents/*.md` — the sentence exists in exactly **one** file today
   (`kb-extraction-worker.md:28`) and in **0** files under `.agent/plans/` or `.claude/` as a
   template (control-armed, `evidence-agent-team-0828.md:76-79`).
   *Fixes:* the 14.5% resend rate on un-instructed lanes (8/55, MEASURED). Cost: one sentence.
   *Honest caveat:* the 0/4 BOTH-arm result cannot discriminate at n=4 (§4).

2. **Amend the recovery procedure to transcript-first.**
   *Primitive:* the handoff/`kb-session-*` procedure text and the auto-memory note.
   *Fixes:* the REFUTED "one SendMessage recovers in ~1 min" — 2 of 4 resends failed and both
   reports were intact in the transcript (20 KB / 31 KB). Settled rule: **read the transcript, send
   at most one resend, never wait on a second.** Cost: an edit.

3. **Bound every Codex dispatch externally, and never use `exec review` for a typed call.**
   *Primitive:* the Bash tool's own `timeout` parameter, or a mise task `timeout` key; plain
   `codex exec`/`exec resume` with `--output-schema`.
   *Fixes:* §2 row 11 (Codex has **no** per-call token or turn cap — openai/codex#33294 OPEN) and
   row 12 (`exec review` silently drops the schema and exits 0 — openai/codex#38545 OPEN). Cost:
   a flag and a rule line.

4. **Require an executor attestation *inside the typed return*, not only in the report body.**
   *Primitive:* one required field in the `--output-schema` JSON schema
   (e.g. `executor: "codex"|"claude"` + the codex session id), which `--output-schema` is MEASURED
   to produce and validate (`codex-binary-probe.md:19`).
   *Fixes:* the NEW failure class in §2 row 9 — a wrapper that substitutes itself returns a
   *complete, plausible* result attributed to the wrong family (#559), and 157/159 review artifacts
   already cannot name their executor. A `CODEX SAID:`/`PROCESS:` field in prose catches it only if
   a human reads the prose; a required schema field makes the object refuse to validate.
   *Note:* this is a contract addition, not a role — the roster stays at six.

5. **Settle the Fable consult as a bounded gate, in writing.**
   *Primitive:* `.claude/agents/kb-advisor.md` + `.claude/CLAUDE.md` prose; no code.
   *Fixes:* the live three-way contradiction in §4 (three-points vs always-consult vs "sparingly").
   Proposed wording, for Ray to accept or reject: the pre-dispatch consult is a **short gate** — is
   this spec complete and verifiable without the architect's context, yes/no plus what is missing —
   while the three named decision points get a **full** advisory pass. **This is Ray's ruling to
   make; recommending it here does not make it settled.**

6. **Sync the four governance surfaces to Ray's 2026-08-25 ruling — as its own change.**
   *Primitive:* edits to `.claude/rules/do-not.md:56-63` #4, `.claude/rules/ai-cli-invocation.md:25-29`,
   root `CLAUDE.md:66-71`, and closing/superseding issue **#455**.
   *Fixes:* an agent reading tracked authority today is correctly told `openai-cli` is forbidden,
   while `currency.toml:49` and the wrapper both treat it as sanctioned. Two of those texts are also
   *mechanically* wrong (they credit `clean_env()` with `detect_backend()`'s carve-out), so this is a
   correctness fix as well as a currency one. **It is a prerequisite for rec 7**: running the backend
   while the rules forbid it either violates the rules or silently ignores them, and both are worse
   than the edit. Ray named `do-not.md` #4 explicitly and it has stood unchanged for three days.

7. **Run the ~25-file `mise` prose slice on `openai-cli`, serial, with `--api-timeout` raised.**
   *Primitive:* `mise run kb-graphify-native-extract -- --backend openai-cli` (dry-run MEASURED rc 0
   this session), `--api-timeout`, no `--model`, `GRAPHIFY_OPENAI_CLI_EFFORT` set deliberately.
   *Fixes:* the standing ultimate goal is still **permitted and unexecuted** — no deep extraction has
   reached a provider on the current 0.9.50 pin. A ~25-file slice buys the per-call cost figure that
   §5's estimate is missing, at a fraction of the ~114-minute full-clone run.
   *Record on the run:* backend, model, effort, wall-clock per call, and token spend — Ray's
   2026-08-26 directive is that **token spend, not dollars, is what must be tracked across both
   subscriptions** (`docs/direction/2026-08-26-ray-directives.md:41-50`).

8. **(Deferred, not recommended now) `codex app-server`.** Watch openai/codex#41188 and #40953. It is
   `[experimental]`, unexecuted here, and its only corroboration is four third-party integrations.
   Adopt when `mcp-server`'s removal actually lands, not before.

---

## 7. Not measured

- **`codex app-server` was never executed** — existence only, from `--help`
  (`codex-binary-probe.md:23,32`). Everything about its protocol in this report is ANECDOTAL.
- **`--output-schema` enforcement under a *violating* model response.** Only the happy path was run
  (`codex-binary-probe.md:33`). Whether it re-prompts, repairs, or errors is unknown — so rec 4's
  "the object refuses to validate" is an expectation, not a measurement.
- **`exec resume` restoring in-flight tool-call / sandbox state.** The kill test interrupted text
  generation only, not a running subprocess or a partially-applied edit (`codex-binary-probe.md:34`).
- **Any per-call time or token figure for `openai-cli`.** §5's ~114 min is DERIVED from an INHERITED
  361 s whose unit ("document" vs "chunk") is not established, times an INHERITED `claude-cli` chunk
  count. **No `openai-cli` extraction has reached a provider on the current pin.**
- **Whether the BOTH-channels prompt fix works.** 0/4 is consistent with the fix and with chance at
  the 14.5% base rate (P ≈ 0.54) — the cell cannot discriminate
  (`evidence-agent-team-0828.md:201-205`).
- **Whether the #559 substitution recurs.** n=1; the stated hypothesis (a spec forbidding the lane's
  own build/verify step invites substitution) is untested.
- **`codex mcp-server` under concurrent or long-lived clients.** One client, one `initialize`, one
  reply (`codex-binary-probe.md:35`).
- **`GRAPHIFY_OPENAI_CLI_EFFORT` surviving `clean_env()` end-to-end.** Not in the strip list, so it
  likely passes, but not traced into `resolve_env` (`openai-cli-backend-path.md:120`).
- **Codex's own `AgentsToml` multi-agent subsystem** — field shapes read from source
  (`config_toml.rs:661-690`), never exercised; whether Codex-internal fan-out could complement a
  Claude-orchestrated team is an open follow-up (`trackers-agent-team.md:356-362`).
- **Live GitHub state for #509, #559, #397, #417 in the `codex-history` lane** — that lane's `gh`
  calls all failed at the network boundary and it marked them **UNVERIFIED**
  (`codex-history-agent-team.md:16,98`). The `openai-cli-backend-path` lanes independently report
  #397/#417 OPEN, and `evidence-agent-team-0828.md:215` independently read #116 and #559 via
  `gh issue view` — so those four are corroborated by a second lane; #509 is not.
- **openai/codex Discussions** — the trackers adapter has no discussions branch
  (`trackers-agent-team.md:369-374`); `app-server`'s experimental-status rationale may live there.
- **Anything about `agy`/antigravity in this window** — no in-window report measures it.

---

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; issues #116, #397, #417, #455, #480, #499, #509, #559 cited (see Not measured for which are live-verified).
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the fork pinned at `0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956`; `graphify/llm.py` (BACKENDS, `_call_openai_cli`, `detect_backend`, the 361 s comment) read.
- [openai/codex](https://github.com/openai/codex) — primary source at `rust-v0.150.1` (`codex-rs/cli`, `mcp-server`, `app-server`, `exec`, `config`); issues #38545, #35596, #19816, #40702, #40149, #22998, #23123, #33294, #34215, #41188, #40953, #39482, #37471, #39198 and others cited.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — tracker sweep; #86471 and #90264 (background subagents reporting `completed` with empty output) are the upstream general form of this repo's idle-without-reporting finding.
- [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) — full issue/PR enumeration; issue #16 (post-bound fix commits ship self-reviewed) is upstream evidence for Fable decision point 1.
- [johnlindquist/codex-imps](https://github.com/johnlindquist/codex-imps) — ANECDOTAL, unofficial reverse-engineered token-cost table for codex's system prompt; not verified against the pinned source.
- [openclaw/openclaw](https://github.com/openclaw/openclaw) — ANECDOTAL, `app-server` JSON-RPC-over-stdio corroboration via DeepWiki mirror.
- [yishentu/claudian](https://github.com/yishentu/claudian) — ANECDOTAL, same corroboration.
- [slopus/happy](https://github.com/slopus/happy) — ANECDOTAL, same corroboration.
- [bullorosso/etienne](https://github.com/bullorosso/etienne) — ANECDOTAL, same corroboration.

---

## Appendix — synthesist bookkeeping (verification counts + not-comparable)

Required by the `kb-synthesist` contract; kept out of the report body, which follows the shape the
lead specified.

**Counts across the 12 baseline claims re-examined in §2:** **6 CONFIRMED** (rows 2, 3, 7, 8, 10 and
the §4 decision points) · **3 REFUTED or PARTLY REFUTED** (rows 1, 5, 6) · **1 NARROWED** (row 4) ·
**2 NEW** (rows 11, 12) · row 9 is a new failure class the baseline had no row for.
Refuted ≠ 0, so the verification arm did in fact run — a sweep returning zero refutations would
itself have been the finding.

**Not comparable — scored badly and not applicable are different answers:**

- **`codex-history-agent-team.md` cannot be scored on live tracker state.** Every `gh` call it made
  failed at the network boundary and it said so and marked the claims UNVERIFIED. That is correct
  lane behaviour under a broken probe, not a weak report; its *timeline* claims are all local-file
  citations and stand on their own.
- **`trackers-agent-team.md` and `codex-binary-probe.md` are not comparable on `mcp-server`.** One
  read the pinned source; one ran the binary. §3 resolves *which wins on the specific question of
  runtime deprecation* — it does not rank the reports, and the trackers lane's source reading is not
  refuted by it.
- **The two `openai-cli-backend-path` lanes are not independent on `kb-build`'s failure**: both read
  the same `.build-failure.json`. Their agreement there is one observation, not two.
- **No input measures `agy`/antigravity**, so this report says nothing about that lane in either
  direction.

---

## Caller's annotation — `fable-advisor` verdict, received after promotion (2026-08-28)

Verbatim copy: `.agent/kb/reports/agents/advisor-agent-team.md`. Four rulings, applied to the published page (`docs/artifacts/the-team-is-a-transport.html`) and recorded here without editing the synthesis above:

- **(a) ADOPT** `codex exec` + `--output-schema` + `exec resume`. Deciding risk: durable state — a file + session id survives what a connection does not. No probe on `app-server` until `mcp-server`'s removal lands.
- **(b) §6 rec 4 as written is REFUSED.** A self-reported `executor: "codex"` field is as fakeable as the `CODEX SAID:` prose it replaces. The field must be a codex **thread/session id the architect verifies** (`codex exec resume <id>` succeeds, or the session file exists) — an arm, not an attestation. "The object refuses to validate" cannot be the published mechanism while schema enforcement under a violating reply is unmeasured (§7).
- **(c) The Fable "three-way contradiction" is over-stated.** Ray's verbatim 2026-08-27 directive outranks the baseline's "three points only" and `kb-advisor.md`'s "sparingly": publish it as **settled precedence, open shape**. Rec 5's bounded gate stands, with one addition — the gate consult receives the **spec by file path with a size cap, never the conversation**, or the "short" consult still loads a full context.
- **(d) Sync the four governance surfaces FIRST, then the ~25-file slice** — with `GRAPHIFY_OPENAI_CLI_EFFORT` exported explicitly and `--api-timeout` raised above 2×361 s, or the first spend fails on timeout instead of measuring anything.
