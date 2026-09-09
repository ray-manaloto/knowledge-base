# Research: a GPT-6 Astra codex cold-review lane (xhigh effort)

Ray's directive (verbatim, relayed): *"research and add a new codex cold review
using the new codex GPT-6 Astra model on xhigh effort — we will have 2 types of
codex lanes — the astra model one is used when performing a complicated and
large review like this one — we should anticipate a very long review and adjust
timing expectations and adjust the codex lane and prompt to provide and codex
command line arguments and flags to use — would benefit from resynced codex
graphify sources and anything else found from research"*.

Written incrementally. Every claim is either `file:line`-cited against the
pinned source, a verbatim command + its output, or marked UNVERIFIED.

## 0. Environment facts (control data for everything below)

- `sources/codex.manifest`: pin is `ref = rust-v0.153.4`,
  `commit = 3d2ee51ca2d5db578f328aa75e20aa22c0197c9a`.
- `git -C sources/codex rev-parse --short=12 HEAD` → `3d2ee51ca2d5` — **matches
  the manifest**, and the commit date is `2026-09-04 15:41:04 -0700`.
- `mise exec -- codex --version` → `codex-cli 0.153.4` — **matches the pin**.
  So the pinned source tree IS the installed binary's source; findings below
  from `sources/codex/` describe the running CLI, not a different version.
- `sources/codex.manifest` also records: `build = skip` — this repo's
  `kb-build` does NOT currently extract `sources/codex/` into the graph
  (#417, a `Cargo.toml`-zero-nodes blocker unrelated to this task). **This is
  why the graph-first query below returned noise from unrelated repos instead
  of codex internals** — codex source is not indexed. Control arm confirming
  this is a real corpus gap and not a query-phrasing miss: see §0a.

### 0a. Graph-first probe (control-armed, negative confirmed structural)

Per this repo's PreToolUse guard, ran first:

```
mise run kb-query -- "codex review lane model reasoning effort flags"
```

Result: `181 nodes found`, all from unrelated indexed repos (a `frontend/`,
`web/`, `pkg/models` Go/TS project with fields literally named `Reasoning`,
`Model`, `review` etc. — homonym matches, not codex). **Zero codex-source
nodes appeared.** This is consistent with, not contradicted by, `build = skip`
in `sources/codex.manifest` (§0) — the source was never extracted, so the
graph structurally cannot answer this. Per `probes-need-a-control-arm.md`,
this is reported as a corpus gap, not as "the graph says codex has no model
config" (it says nothing about codex at all). All model-catalog research
below therefore reads `sources/codex/` directly, per Ray's standing rule
(2026-09-03): *"we have access to the codex source code … inspect it"*.

## 1. This repo's EXISTING codex lane machinery (file:line)

### 1.1 The guard: `python/src/kb_setup/codex_lane.py`

Denies a raw `codex exec`/`review`/`resume`/`fork`/`queue`/`cloud`/`apply`/
`sandbox` (plus one-letter aliases `e`/`a`, confirmed against
`codex-rs/cli/src/main.rs:137,188,213` for `visible_alias`/`alias`) at the
Bash PreToolUse hook and redirects to `mise run kb-codex`
(`codex_lane.py:79-93,113-115,140-203`). `--help`/`--version`/`-V`/`-h` always
exempt the segment (`:97,177`); `mcp`/`login`/`logout`/`completion`/`agents`/
`doctor`/`features`/`help` are introspection and never denied (`:113-115`).

### 1.2 The runner: `python/src/kb_setup/codex_run.py`

Two builders, because `codex exec` and `codex review` do not share flags:

- **`_codex_argv` (`codex_run.py:64-94`)** — builds `codex exec` argv.
  `LaneSpec` (`:47-62`) fields: `write: bool = False`, `network: bool = False`,
  **`effort: str = "xhigh"` (already the default!)**, `sandbox_override:
  str | None`, `model: str | None`, `output: str | None`. Fixed argv shape:
  `["codex", "exec", "--sandbox", <ro|ww>]`, then `--model <m>` if given,
  `-o <file>` if given, then (write-sandbox only) `--add-dir <uv cache>` +
  optional `-c sandbox_workspace_write.network_access=true`, then always
  `-c model_reasoning_effort=<effort>`, then always
  `--dangerously-bypass-hook-trust`, then always trailing `-` (stdin prompt).
  **No `--ephemeral`** (deliberate, module docstring `:21-22`: an ephemeral
  lane is invisible to `kb-session-search`/`~/.codex/sessions/`).

- **`_review_argv` (`codex_run.py:110-171`)** — builds `codex review` argv,
  which is **NOT** `codex exec` with a flag and accepts **none** of the four
  mandatory lane flags (no `--sandbox`, `--add-dir`, `--dangerously-bypass-
  hook-trust`; docstring `:119-122`, sourced from `codex-rs/exec/src/cli.rs:
  272-305` — `--uncommitted`/`--base`/`--commit`/`[PROMPT]` all pairwise
  `conflicts_with`, one `ReviewTarget` enum at
  `codex-rs/protocol/src/protocol.rs:3310-3344`). The METHOD/instructions
  paragraph rides in over `-c developer_instructions=<toml-quoted-string>`
  (`:146-171`), confirmed as a **global** `ConfigToml` key
  (`config/src/config_toml.rs:223-228`) NOT in the conflict set
  (`codex-rs/cli/src/main.rs:99-129`), threaded through
  `core/src/tasks/review.rs:99-127` and rendered as a developer message in
  `core/src/session/mod.rs:718-734,3808-3817`. `--title` is silently ignored
  unless `--commit` is also given (`exec/src/lib.rs:2132-2149`) — this repo's
  builder only ever passes `--base`, so `--title` is never sent (`:166-168`
  guards on `title and commit`, and `commit` is hardcoded `None` at the one
  call site inspected below).

  **`_review_argv` builds NO reasoning-effort / no model flag at all.**
  `codex review --help` needs to be checked (§2) to see whether `-c
  model_reasoning_effort=` / `-c model=` are even accepted on this subcommand
  — the exec builder passes effort via `-c`, but the review builder
  (`:166`) only ever emits `["codex", "review", "--base", base]` plus
  optionally `--title` and `-c developer_instructions=…`. **This is the single
  biggest gap for the Astra lane spec** (§6): today's `--review` path has no
  way to select a model or an effort level at all.

- **`_run_review` (`:174-211`)** reads the prompt from the positional arg or
  stdin, builds via `_review_argv`, and — this matters for §6 — **hardcodes**
  `title=args.title, commit=None` at its one call site (`:183`), so `--commit`
  is not wired even though `_review_argv`'s signature accepts it.

### 1.3 `mise.toml [tasks.kb-codex]` (`mise.toml:1076-1090`, confirmed exact
line numbers from `grep -n`)

```toml
[tasks.kb-codex]
description = "Run a codex lane with this repo's mandatory flags (#672 U1)"
raw = true
run = "uv run kb-setup codex"
timeout = "1800s"
```

`raw = true` is required because the lane reads its prompt from stdin (`-`);
without it mise reads task stdio by line instead of connecting it (comment,
same block). **`timeout = "1800s"` (30 minutes) is the CURRENT ceiling on any
`kb-codex` invocation** — this is the number Ray's "anticipate a very long
review" directive must beat; see §6 for the sizing discussion.

### 1.4 `codex_config.py` — unrelated to model selection

This is the `#710` tripwire for `.codex/config.toml` getting silently
overwritten by ChatGPT desktop's import-sync (`kb-codex-config-check` task,
`mise.toml:1303-1310`). Not part of the lane-invocation path; flagged here
only because it explains why `.codex/config.toml`'s `[mcp_servers]` /
`[agents]` blocks may drift and why re-reading it live (§5) rather than
trusting a stale note matters.

## 2. The model catalog (primary source: `sources/codex/codex-rs/models-manager/models.json`)

The 6-line `model_presets.rs` file is a **legacy stub**: *"Hardcoded model
presets were removed; model listings are now derived from the active
catalog."* The catalog is `codex-rs/models-manager/models.json` (1365 lines,
11 models), bundled in the binary and used as the default/offline model list
(`bundled_models_response()`, referenced from ~20 test files and
`core/src/test_support.rs:45` — this is a real runtime fallback, not test-only
fixture, per `core/src/config/config_loader_tests.rs:1302`'s
`model_catalog_json = "models.json"` config key, i.e. it can also be replaced
per-`$CODEX_HOME` for enterprise-pinned catalogs).

### 2.1 `gpt-6-astra` entry (`models.json:4-172`)

| field | value |
|---|---|
| `slug` | `"gpt-6-astra"` |
| `display_name` | `"GPT-6-Astra"` |
| `description` | *"Our most capable model for complex, demanding work."* |
| `context_window` | `272000` |
| `max_context_window` | `872000` |
| `default_reasoning_level` | `"low"` |
| `supported_reasoning_levels` | `low, medium, high, xhigh, max, ultra` (`:40-63`) — **`xhigh` is supported**, and there is a level ABOVE it (`max`, `ultra`) that Ray's directive does not ask for |
| `multi_agent_reasoning_effort` | `"xhigh"` — the model's OWN internal multi-agent sub-tasks default to xhigh even when the top-level effort is lower |
| `minimal_client_version` | `"0.153.0"` — our pinned/installed `codex-cli` is **0.153.4**, so the version floor is met with margin |
| `visibility` | `"list"` (shown in pickers, not hidden) |
| `priority` | `1` — **the lowest (=highest-ranked) priority number in the entire catalog**; `gpt-5.6-sol` (today's default cold-lane model) is priority `6` |
| `context_window` / effort list | identical shape to `gpt-5.6-sol`'s entry (`:173-303`) — same context window (272k/872k), same six effort levels |
| `model_messages.instructions_template` | *"You are Codex, an agent based on **GPT-6**. ..."* (`:73`) — confirms Astra is genuinely GPT-6-based, not a rename; `gpt-5.6-sol`'s equivalent field is `base_instructions` (a **different top-level key**, not `model_messages`), starting *"You are Codex, an agent based on GPT-5. ..."* — Astra's schema entry has evolved to a `model_messages` object where the older models use a flat `base_instructions` string. Not investigated further; irrelevant to lane wiring. |

Catalog ordering by `priority` (ascending = more prominent): `gpt-6-astra`(1) <
`gpt-5.6-sol`(6) < `gpt-5.6-terra`(7) < `gpt-5.6-luna`(8) <
`gpt-daybreak-{blue,red}-latest`(10,11, both `visibility:"hide"`) <
`gpt-5.5`(12) < `gpt-5.4`(16, hidden) < `gpt-5.4-mini`(23, hidden) <
`gpt-5.2`(29) < `codex-auto-review`(43, hidden).

**`codex-auto-review` is a DIFFERENT feature — do not confuse it with `codex
review`.** It is `provider.rs:131`'s `DEFAULT_APPROVAL_REVIEW_PREFERRED_MODEL`,
used by the **Guardian** subsystem (`core/src/guardian/review.rs`,
`async_scorer`, `sync_reviewer`) that auto-approves/scores risky tool calls
inline during an ordinary turn. It has nothing to do with the `codex review`
CLI subcommand this task is about (confirmed: `ReviewTask::start_review_conversation`
at `core/src/tasks/review.rs:123-127`, below, never references
`codex-auto-review` or `DEFAULT_APPROVAL_REVIEW_PREFERRED_MODEL`).

### 2.2 How `codex review` actually picks its model — THE key mechanism

`core/src/tasks/review.rs:99-140` (`start_review_conversation`):

```rust
let mut sub_agent_config = config.as_ref().clone();      // :106 — full clone of the CURRENT config
...
sub_agent_config.base_instructions = Some(crate::REVIEW_PROMPT.to_string());  // :119 — dedicated review rubric
...
let model = config
    .review_model                                         // :123-126
    .clone()
    .unwrap_or_else(|| ctx.model_info().slug.clone());     // falls back to whatever model the CURRENT session/turn uses
sub_agent_config.model = Some(model);                      // :127
```

So `codex review`'s target model is **`config.review_model` if set, else the
current session's own model.** `model_reasoning_effort` is NOT touched by this
function — the sub-agent config is a full clone of the top-level config, so it
inherits whatever effort the top-level `-c model_reasoning_effort=` set.
**`review_model` is a first-class, DOCUMENTED config key**, not an
undocumented internal:

```
core/src/config/mod.rs:623   pub review_model: Option<String>,         (the resolved Config struct)
config/src/config_toml.rs:157 (ConfigToml struct):
  pub model: Option<String>,                     // "Optional override of model selection."
  pub review_model: Option<String>,              // "Review model override used by the `/review` feature."
  ...
  pub developer_instructions: Option<String>,     // (:228)
  ...
  pub model_reasoning_effort: Option<ReasoningEffort>,  // (:360)
```

`review_model`, `model`, `developer_instructions`, and `model_reasoning_effort`
are **all plain top-level `ConfigToml` fields** — i.e. all four are valid
`-c key=value` overrides. This is also **officially documented**: fetched
`https://developers.openai.com/codex/config-reference.md` (2694 lines) lists
`key: "review_model"` at line 32.

`override_review_model` (the CLI-flag-populated half of the `.or()` chain at
`core/src/config/mod.rs:3943`) has **no CLI flag wired to it anywhere** in
`main.rs` — grepped, zero non-test call sites set it. So **the only way to set
`review_model` today is `-c review_model=<slug>` or a `review_model = "..."`
line in a config.toml/profile layer.** There is no `--review-model` flag.

### 2.3 The two clap surfaces named "review", and why only one takes `-m`

| Surface | Defined | Own flags (verified live, `--help`, §3) | Reaches `-m/--model`? |
|---|---|---|---|
| **top-level** `codex review` | `cli/src/main.rs:139` `Review(ReviewCommand)`, args = `codex_exec::ReviewArgs` (`exec/src/cli.rs:270-303`) | `-c`, `--strict-config`, `--enable`, `--disable`, `--uncommitted`, `--base`, `--commit`, `--title`, `[PROMPT]` | **NO** — `ReviewArgs` itself declares no model flag, and this subcommand is a *sibling* of `exec` on `MultitoolCli`, so it does not inherit `exec`'s own `-m` |
| **nested** `codex exec review` | `exec/src/cli.rs`'s `Command` enum (listed in `codex exec --help`'s own Commands table) | same `ReviewArgs`, but AS A SUBCOMMAND OF `exec` it also inherits `exec`'s top-level flags: `-m/--model`, `-s/--sandbox`, `--add-dir`, `--dangerously-bypass-hook-trust`, etc. | **YES** — this is the surface `fable-orchestrator`'s `run-lane.sh` uses (`codex exec review --model "$MODEL" ...`, §5.4) |

Both share the identical `ReviewArgs` struct, so `--uncommitted`/`--base`/
`--commit`/`[PROMPT]` remain mutually exclusive on EITHER surface
(`conflicts_with_all`, `exec/src/cli.rs:238-268`, live-confirmed in
`codex review --help`'s flag list, §3). Either way, **the model/effort must
travel through `-c review_model=`/`-c model_reasoning_effort=` on the
top-level surface, or through `-m`/`-c` directly on the nested surface** —
never through a subcommand-specific `--model` flag on top-level `review`.

This repo's `kb_setup.codex_run._review_argv` uses the **top-level** surface
(`["codex", "review", "--base", base]`, `codex_run.py:166`) to keep the
structured `--base` targeting `kb-review`'s lanes.md already relies on. It
currently forwards `-c developer_instructions=` only — **never
`-c review_model=` / `-c model_reasoning_effort=`**, which is exactly issue
#678's finding (§5.2) and the concrete gap this task's proposal (§6) closes.

## 3. `codex --help` / `codex exec --help` / `codex review --help` (secondary, live, `codex-cli 0.153.4`)

Verbatim, confirms §2.3 exactly:

- **`codex --help`** (top-level `MultitoolCli`): `review` is listed as a
  sibling `Commands` entry beside `exec`/`apply`/`cloud`/etc. Global flags
  include `-c/--config`, `-m/--model <MODEL>` ("Model the agent should use"),
  `-s/--sandbox <read-only|workspace-write|danger-full-access>`,
  `--dangerously-bypass-hook-trust`, `--add-dir`, `-a/--ask-for-approval`.
  **These are declared on `MultitoolCli` itself**, so they apply before a
  subcommand is chosen — this is what lets `codex_run.py`'s exec-mode
  `_codex_argv` place `--model`, `--sandbox`, `--add-dir`,
  `--dangerously-bypass-hook-trust` around the `exec` token freely.
- **`codex exec --help`**: same `-m/--model`, `-c`, `-s/--sandbox`,
  `--add-dir`, `--dangerously-bypass-hook-trust`, `--ephemeral`,
  `-o, --output-last-message <FILE>` (confirms `-o` writes ONLY the agent's
  **last message**, not a transcript — matches the two-line content our live
  probe's `--output` file actually held, §4). `exec`'s own nested Commands
  list includes `resume`, `fork`, **`review`** (`Run a code review against the
  current repository`), `help`.
- **`codex review --help`**: **no `-m`, no `-s/--sandbox`, no
  `--dangerously-bypass-hook-trust`, no `--add-dir`, no `-o`.** Only:
  `-c/--config`, `--strict-config`, `--enable`, `--disable`, `--uncommitted`,
  `--base <BRANCH>`, `--commit <SHA>`, `--title <TITLE>`, `[PROMPT]`. This is
  an exact, independent confirmation of `codex_run.py:119-122`'s docstring
  claim (which cites the pinned source, not this help text) and of §2.3's table.

## 4. Live probe (through the sanctioned `mise run kb-codex` task, read-only sandbox, bounded 300s)

Both calls completed **well inside the 300s Bash-tool bound** (no timeout
fired; both printed a full `tokens used` summary and returned rc 0) —
`codex-cli 0.153.4`, project config from this repo's `.codex/config.toml` and
`.codex/hooks.json` (hooks fired: `SessionStart` ×8 including one
**`Failed`**, `UserPromptSubmit` ×2, `Stop` ×3 — **identical in both runs**,
so this is a pre-existing, model-independent hook-config issue in this repo,
not an Astra-specific defect; out of scope for this task and not investigated
further). An unrelated pre-existing MCP OAuth error (`exa` server's refresh
token revoked) also appeared identically in both runs — same reasoning, not
Astra-specific.

**Astra** — `mise run kb-codex -- --model gpt-6-astra --effort xhigh --output
<file> "Reply with exactly two lines: OK / the exact model id you are
running as."`
```
model: gpt-6-astra
provider: openai
reasoning effort: xhigh
--------
OK
I don't have access to my exact model ID.
```
rc=0. **The banner (`model: gpt-6-astra`) is the authoritative proof of which
model ran — the model's own self-report is NOT** (see control arm).

**Control arm** — identical invocation with `--model gpt-5.6-sol`:
```
model: gpt-5.6-sol
--------
OK
gpt-5.4-mini
```
rc=0. Sol **hallucinated a wrong model id** (`gpt-5.4-mini`, an unrelated
smaller model in the same catalog) when asked to self-report, while Astra
honestly declined. **Neither model's self-report is trustworthy; the codex
CLI's own startup banner (or `--json` event stream / analytics fields) is the
only reliable source of "which model actually ran."** This is a concrete,
repo-relevant instance of the standing finding in this repo's memory that a
model cannot reliably report its own resolved id (`openai-cli-cannot-report-
its-resolved-model.md`, previously observed only for `openai-cli`/`llm.py`
echo behavior — now independently reproduced on a **direct** `codex exec`
call with **no echo involved**, so the cause is model self-knowledge, not an
echo artifact).

**Verdict: `gpt-6-astra` is LIVE and reachable on this account/subscription,
today, through the exact `mise run kb-codex` entry point this repo already
uses.** No plan-gating error, no "at capacity", no refusal was observed for
this trivial prompt. Exact wall-clock latency was not captured (zsh's `time`
reserved word did not emit its report line into the captured output under
`{ time cmd; } 2>&1` — a shell quirk, not re-derived further to avoid spending
a third paid Astra call purely on a stopwatch reading, given the community
cost-burn reports in §5.1). **The only thing this probe establishes about
timing is a floor, not the ceiling Ray's directive is actually asking about**
— a trivial one-line prompt is fast on both models; nothing here bounds a
real "complicated and large" review's wall-clock time, which by every
external signal in §5.1 is the actual risk.

## 5. Upstream signals (openai/codex, `gh api search/issues`, 2026-09-09)

**These are community bug-report titles/bodies as filed — leads, not
confirmed current behavior** (`probes-need-a-control-arm.md`: an issue tracker
is a secondary source; "open" does not mean "still true," but these are all
very recent — issue numbers in the low-to-mid 43000s, filed 2026-09-05 through
2026-09-09, against codex-cli 0.153.3/0.153.4, i.e. the version we run).

- `repo:openai/codex astra` → **332** results; `repo:openai/codex "gpt-6"` →
  **2935** results (both via `gh api -X GET search/issues`, never `gh search`
  per this repo's own standing caution). All of the ~20 read titles are
  **open**.

### 5.1 The risk signals that matter for THIS task

| Concern | Issue(s) | What it says |
|---|---|---|
| **Timing** — the direct ask | #43038 *"ChatGPT Working Astra Compaction takes 5x longer than before Astra update with Sol"* | Read in full: *"Auto-Compaction and Manual Compaction are taking 3-5x+ longer... 5-6 minute manual compactions on relatively new chat sessions [vs] 45 seconds to 1.5 min before... I did notice Astra is definitely slower than Sol."* (ChatGPT desktop app, same backend models) |
| **Timing** | #43004 *"GPT-6 Astra Loop/Long hours"* (created 2026-09-05, codex-cli 0.153.3) | Title alone is corroborating; body was a `codex doctor` dump with no free-text detail |
| **Availability/capacity** | #43706 *"GPT-6 and GPT-5.6 constantly show 'Selected model is at capacity'"* (created 2026-09-08, ChatGPT Pro, codex-cli 0.153.4) | Read in full: *"Since September 7, 2026, GPT-6 and GPT-5.6 models constantly show: 'Selected model is at capacity. Please try a different model.' ...Other models, including GPT-5.4-mini and GPT-5.6 Sol Light, work normally."* **This is 1-2 days before this research and on our exact CLI version** — our live probe (§4) did NOT hit this, but it is evidence the failure mode is real and current, not hypothetical |
| **Quota/cost burn** | #43484 *"Astra is burning too much usage"*, #43506 *"[Astra High Non-Fast] Very high subscription drain"*, #43222 *"[Pro 20x][Windows] GPT-6 Astra weekly quota depletion appears disproportionate to local token telemetry"* | Titles only (not read in full — consistent pattern across three independent reports). Directly relevant to Ray's subscription-only constraint (`ai-cli-invocation.md`, `do-not.md` #4): an Astra xhigh review lane could consume a disproportionate share of the WEEKLY quota window |
| **Reliability** | #43446 *"GPT-6 Astra: repeated 503 overload followed by apparent routing/quality inconsistency on Pro"*, #42937 *"GPT-5.6 Sol and GPT-6 Astra in Codex: higher intelligence, lower autonomous completion and operational reliability"* | Titles only — supports designing for retry-on-5xx and not treating a single failed run as conclusive |
| **False-positive policy refusals on security-adjacent work** | #43163 *"GPT-6 Astra returns invalid_prompt for harmless prompts across multiple PCs"*, #43781 *"[Codex App] GPT-6 Astra rejects harmless prompt as usage-policy violation"*, #43131 *"Astra Light repeatedly hits cyber_policy during authorized bug-triage coordination"*, #43208 *"GPT-6 astra repeatedly blocks authorized defensive local work and benign follow-ups"*, #42939 *"Cyber program doesn't work with gpt-6-astra"* | Titles only, but **five independent reports of the same shape**. Directly relevant: `kb-review`'s cold lane explicitly hunts for "a check, a gate, or a guard" (`references/lanes.md`'s METHOD paragraph) — adversarial-flavored review language on THIS repo's own guard/secret-scanning code (`hook_guard.py`, `secret_guard.py`) is close to the shape these reports describe triggering false refusals |
| Model picker bugs (app/desktop, not CLI) | #43342, #42853 | *"/model picker omits usable gpt-6-astra"*, *"missing from model picker for eligible ChatGPT Pro account"* — app/desktop-surface bugs; **our CLI `--model gpt-6-astra` live-probed successfully (§4)**, so this class did not reproduce here |

**Releases**: `gh api -X GET repos/openai/codex/releases` (first attempt
malformed — `-f` flags without `-X GET` default `gh api` to **POST**, which
tried to hit the *create release* endpoint and errored "tag_name wasn't
supplied"; a self-caught control-arm failure, corrected). Latest 8:
`rust-v0.154.0-alpha.11` (2026-09-09, today), down through several
`0.154.0-alpha.*` builds to **`rust-v0.153.4`** (2026-09-04) — **our pin is
the newest STABLE (non-alpha) release**; nothing currently unreleased-stable
supersedes it.

### 5.2 Docs (`developers.openai.com`, fetched `.md` suffix per this repo's mintlify-style preference chain; all 3 candidate URLs returned HTTP 200)

`codex/models.md` (586 lines) — the **official model card** for `gpt-6-astra`:

- Description: *"Our most capable model for complex work across code, apps,
  and research, combining advanced reasoning, computer use, and stronger
  judgment."*
- Feature table: Capability = 5/5 (max sparkles shown), Speed = 2/5 flashes
  (slower), **Codex CLI: true**, Codex IDE extension: true, **Codex cloud:
  false** (the `codex cloud`/`cloud-tasks` subcommand — irrelevant to our
  lane, noted because `codex_lane.py`'s guard set also covers `cloud`), API
  Access: true.
- *"## Choosing Astra, Sol, Terra, and Luna... Choose **Astra** when a task
  needs the strongest capability across multiple steps and tools... **Astra,
  for the hardest end-to-end work.** Choose Astra for complete workflows
  across code, apps, and research that need sustained reasoning and
  judgment... Astra is better at asking focused questions and incorporating
  your guidance while keeping the original goal and constraints in view."*
  This is OpenAI's own stated rationale, and it matches Ray's framing
  ("complicated and large review") closely enough to cite directly as the
  justification for the size/complexity trigger in §6.
- Plan gating (app/web surface only, under `<ContentModeSwitch ids="app,web">`
  — **not** shown as gated for the `cli` surface, whose row above just says
  "Codex CLI: true" unconditionally): *"For eligible Pro, Business ($100), and
  Enterprise accounts, the Astra rollout updates the Power options to Terra
  Light, Sol Light, Sol Medium, Astra Light, Astra Medium, and Astra Extra
  High. Options can differ by plan and rollout stage."* Also: *"Availability
  depends on the rollout, your sign-in method, and your client."* **This
  repo's account already has live CLI access (§4), so plan-gating does not
  block us today** — flagged only as something that could regress if the
  account's plan or the rollout changes, consistent with `#43706`'s 5.1 row.
- *"### Experimental context management... Astra keeps notes across context
  windows and can search earlier messages and tool results from the same
  task... off by default... isn't available with Business, Enterprise, or
  API-key sign-in at launch."* Opt-in via
  `features.context_management.experimental_mode = true`. Plausibly useful
  for a long review (mitigates the #43038-style compaction cost) but
  UNVERIFIED whether this account's specific plan tier qualifies (Plus/Pro do
  per the doc; this repo's account tier was not independently confirmed in
  this session) — a candidate for a follow-up, not part of this proposal.
- *"### Pick a reasoning effort — Use the lowest reasoning effort that
  produces the result you need. Increase it for tasks that need more
  planning, analysis, or checking."* Generic guidance; consistent with `xhigh`
  (not `max`/`ultra`) being the right choice per Ray's directive rather than
  reaching for the ceiling.

`codex/config-reference.md` (2694 lines) — confirms `review_model` (line 32)
as a documented top-level key, consistent with §2.2.

## 5.3 This repo's `kb-review` skill (`.claude/skills/kb-review/SKILL.md` +
`references/lanes.md`) — the constraint the Astra lane must fit inside

- **"One lane, always. There is no diff-type table and no multi-lane mode."**
  (SKILL.md step 2) — a hard-won, MEASURED constraint: the prior 4-lane
  version cost 2.93M subagent tokens over 17 lane-runs on #67 for one real
  defect among three "blocking" findings. **Ray's "2 types of codex lanes"
  must therefore mean two VARIANTS competing for the SAME one cold-lane slot
  — not a second lane run alongside the first.** This is confirmed
  independently by `kb_setup.review._lane_prefix` (`review.py:200-202`):
  `entry.partition(":")[0]` strips any `lane:variant` suffix before matching
  against the closed `LANES = ("standards", "spec", "cold",
  "silent-failure")` tuple (`review.py:110`) and before building the report
  filename (`review.py:620-621`, `_safe_lane(_lane_prefix(lane))`). So a lane
  recorded as `cold:codex-astra` files as lane-family `cold` (report
  `review-<sha>-cold.md`, identical filename convention to `cold:codex`) —
  **no change to `LANES` or the report-naming scheme is needed**; `review.py`
  explicitly documents changing `LANES` itself as touching "63 references
  across 11 files," which this proposal avoids entirely.
- **The cross-family table is a hard constraint on WHEN Astra may be chosen**
  (SKILL.md step 2): cold reviewer must be a different model FAMILY than
  the implementer. Claude wrote the diff → `codex-reviewer` (OpenAI); codex
  wrote the diff (this repo's default implementer lane per
  `.claude/CLAUDE.md`) → `antigravity:review` (Google). **`cold:codex-astra`
  is still OpenAI/codex family** — it may substitute for `cold:codex` (when
  Claude or antigravity implemented the diff), but it must NEVER substitute
  for `cold:antigravity` (when codex implemented the diff), or the receipt
  would silently record a same-family read as cross-family. This is the
  single most important correctness rule for §6's proposal.
- The mandatory dispatch template (`references/lanes.md`): fixed range,
  `git diff <FIXED>...HEAD -- . ':(exclude)docs/research/**'` scope, a METHOD
  paragraph ("do NOT review only by reading... RUN the check... report the
  exit code"), "state the HEAD commit... in full," save to
  `.agent/kb/review/reports/review-<HEAD SHA>-<lane>.md`. Bounded at **two
  rounds**, no exceptions — a slower Astra lane makes the wall-clock cost of
  a mandatory round 2 proportionally worse, worth flagging in the timing plan.
- The receipt (`mise run kb-review-receipt -- --lanes cold:codex-astra ...`)
  requires the lane's report to exist, be non-empty, and **name the SHA**
  (full or ≥12 hex) in its body (`review.py`'s `_report_gaps`, #56) —
  applies identically regardless of which cold variant ran.

## 5.4 `kb-codex-advisor` — the existing Claude-agent ↔ codex-agent mirror pattern

`.claude/agents/kb-codex-advisor.md` (frontmatter: `name`, `description`,
`tools: Bash, Read, Grep, Glob, Write`, `color: teal` — **no `model:` key**,
because the WRAPPER's own Claude-side reasoning is trivial; the real reasoning
happens inside the `codex exec` call the body instructs it to make) mirrors
`.codex/agents/kb-codex-advisor.toml` (`model_reasoning_effort = "xhigh"`,
`developer_instructions = '''<same body as the .md, verbatim>'''`, **no
`model` key** — it relies on `.codex/config.toml`'s
`[agents] default_subagent_model = "gpt-5.6-sol"` for its target model).
**Nothing generates one from the other** — both are hand-maintained and both
are scanned by a `lane_recording` gate (per the `.toml`'s own comment) because
a prior round updated only one and the gate missed it.

Confirmed from `config/src/config_toml.rs:157,166,228,360` (§2.2): the
`.codex/agents/<name>.toml` file referenced by `AgentsToml.roles[name].config_file`
(`config_toml.rs`, `AgentRoleToml` struct at `:708-719` — itself only declares
`description`/`config_file`/`nickname_candidates`) is loaded as **a full
`ConfigToml` layer**, so `model`, `model_reasoning_effort`, and
`developer_instructions` are ALL legal top-level keys inside it. A
`kb-codex-astra-reviewer.toml` can therefore set `model = "gpt-6-astra"`
directly, overriding `.codex/config.toml`'s repo-wide
`default_subagent_model = "gpt-5.6-sol"` for this one named agent — this is a
direct, source-confirmed answer, not an inference from the advisor's own file
alone. **Caveat, stated because it matters for scope:** this `.toml` roster is
codex's OWN internal multi-agent spawn mechanism (invoked when a running codex
session spawns a *sub*-agent named `kb-codex-astra-reviewer` mid-turn); it is
a SEPARATE invocation path from the `mise run kb-codex --review` CLI dispatch
`kb-review`'s lanes.md actually uses today. Proposed for parity with the
existing `kb-codex-advisor` pair (§6), not as the primary mechanism.

## 5.5 `.codex/config.toml` (this repo, read in full) — nothing here blocks Astra

No `review_model`, no `[model_providers]`, no top-level `model` default is set
anywhere in this file — confirming §2.2's finding that model selection is
purely per-invocation today (via `--model`/`-c`), never a committed default.
`[agents] default_subagent_model = "gpt-5.6-sol"` / `default_subagent_reasoning_effort
= "high"` govern codex's OWN internal sub-agent spawns (§5.4) and do not
affect the top-level model of a `mise run kb-codex` invocation. The `[mcp_servers.kb]`
/ `[mcp_servers.kb-memory]` blocks (`default_tools_approval_mode = "approve"`,
`startup_timeout_sec = 120`, `tool_timeout_sec = 120`, `env_vars =
["GRAPHIFY_MAX_GRAPH_BYTES"]`) are project-scoped and already solve "can a
headless codex lane reach this repo's knowledge graph over MCP" (#668) — an
Astra lane inherits this for free if it is ever given MCP access; no new
plumbing is needed on that front.

## 5.6 `fable-orchestrator`'s `run-lane.sh` (`~/.claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.21.0/scripts/run-lane.sh`, 224 lines, read in full) — the proven detach/watchdog/poll template

This plugin (already enabled per `.claude/CLAUDE.md`) solves EXACTLY the
"harness caps a foreground call at ~10 minutes, so a long lane must not block
in one call" problem Ray's directive anticipates, and does so with a pattern
this repo's OWN `kb_setup.codex_run` does **not** yet have (today it is a
single blocking `subprocess.run()`, §1.2):

- `start <lane> <spec-file> [secs] [model]` — **already takes a `model` as its
  4th positional argument**, defaulting to `gpt-5.6-sol`. For `codex-review`
  it builds `codex exec review --model "${MODEL:-gpt-5.6-sol}" -c
  model_reasoning_effort="$EFFORT" ... -c 'sandbox_mode="read-only"' --json
  --output-last-message "$FINAL" - < "$SPEC" > "$LOG" 2>&1`, backgrounded
  (`&`) inside a subshell with its OWN process group (`set -m`), so
  `start codex-review <spec> <secs> gpt-6-astra` works TODAY with **zero code
  change to this plugin** — it uses the **nested** `codex exec review` surface
  (§2.3), which is why it can pass `--model` directly.
- `SECS` default: **600s (10 min) for `*-review`/`*-research` lanes**, 1800s
  for plain implement lanes (`run-lane.sh:58-60`). **This is the number Ray's
  "very long review" directive needs to override** — 600s is very likely
  short given §5.1's community reports of multi-minute compactions and "long
  hours" issues on Astra specifically.
- `wait <pid> [slice-secs<=90]` — polls in ≤90s slices (hard-capped,
  `run-lane.sh:196-198`), returning `EXITED`/`STILL-RUNNING`. This is the
  exact "poll in successive ≤90s calls, never one long blocking call" pattern
  `long-running-command-hangs.md` prescribes.
- `reap <pid> [watchdog-pid]` — kills the process GROUP (`kill -- -PID`,
  never just the PID), because the CLI spawns child workers that would
  otherwise orphan.
- A **pure-bash watchdog subshell** (no coreutils dependency) polls every 10s
  up to the caller's `SECS` budget and only then group-kills, appending
  `WATCHDOG: killed <lane> after <SECS>s` to the log — so a killed-by-timeout
  run is distinguishable after the fact from a clean `EXIT: <code>` line.

**This script is NOT something this repo may copy or extend** —
`zero-bash-logic.md`/`do-not.md` #8 forbid new `.sh` files and inline shell
logic in this repo outright. It is cited here as the **proven algorithm** (an
external, already-working reference implementation) whose *shape* — detach via
non-blocking spawn, a separate timeout watchdog, poll in bounded slices, reap
the process group — is what a future `kb_setup` python module would need to
port natively if `mise run kb-codex` is ever extended to support a
long-running detached mode. §6 states this as a proposal, not something
implemented in this session.

## GitHub repos touched (running list — appended to, never trimmed)

- [openai/codex](https://github.com/openai/codex) — pinned source
  (`sources/codex/`, `rust-v0.153.4`) for the model catalog
  (`models-manager/models.json`, `model_presets.rs`), CLI flag definitions
  (`cli/src/main.rs`, `exec/src/cli.rs`), review-target/model-selection logic
  (`core/src/tasks/review.rs`, `core/src/config/mod.rs`,
  `config/src/config_toml.rs`), and Guardian/auto-review internals (read to
  rule OUT relevance, `core/src/guardian/*`); also queried live via `gh api`
  for issues (`astra`, `gpt-6` searches) and releases.
- `developers.openai.com` (OpenAI's Codex docs site, not itself a GitHub
  repo — fetched `codex/models.md` and `codex/config-reference.md` per this
  repo's mintlify-style `.md`-suffix doc-fetch preference chain) for the
  official Astra model card and `review_model` config-key documentation.

---

# 6. PROPOSAL — the Astra lane spec

**Everything below this line is a recommendation, not a measured fact.** It is
built on the facts above but represents judgment calls a human should confirm
before code changes land — this session did not edit any tracked file.

## 6.1 The two codex lane "types," named precisely

Not two lanes running together (§5.3 forbids that) — **two VARIANTS of the one
`cold` slot, chosen by diff size/complexity**, both OpenAI/codex family:

| | `cold:codex` (unchanged) | `cold:codex-astra` (new) |
|---|---|---|
| Model | `gpt-5.6-sol` | `gpt-6-astra` |
| Effort | `xhigh` (already the `LaneSpec` default, `codex_run.py:58`) | `xhigh` |
| When | the default — an ordinary diff | **explicitly chosen**, never auto-detected in this proposal (see 6.4) — "a complicated and large review" |
| Eligible when implementer was | Claude or antigravity (never codex — same-family rule, §5.3) | identical constraint — Astra is still codex-family |
| Receipt lane string | `cold:codex` | `cold:codex-astra` |
| Report file | `review-<sha>-cold.md` | `review-<sha>-cold.md` (same — `_lane_prefix` strips the variant, §5.3) |

## 6.2 Exact invocation

**Recommended — fix #678 properly, using the top-level `codex review` surface
this repo already standardizes on** (keeps structured `--base`/`--commit`
targeting and `codex review`'s dedicated review rubric, `crate::REVIEW_PROMPT`,
`review.rs:119` — a plain `codex exec` turn gets neither):

```
codex review --base <ref> \
  -c review_model="gpt-6-astra" \
  -c model_reasoning_effort="xhigh" \
  -c developer_instructions="<METHOD paragraph + scope + save-path instructions from lanes.md>"
```

This requires extending `kb_setup.codex_run._review_argv`/`_run_review` (today
`codex_run.py:110-171,174-211` builds ONLY `--base` + optional
`-c developer_instructions=`) to also emit `-c review_model=` and
`-c model_reasoning_effort=` when `--model`/`--effort` are passed to `mise run
kb-codex -- --review ...` — which is precisely what issue #678 already asks
for, now with the exact two config keys named (source-confirmed in §2.2,
officially documented in §5.2) rather than "check which of -o/model_reasoning_
effort/--model codex review actually accepts," which #678's body left open.
`_toml_str` (already used for `developer_instructions`, `codex_run.py:97-107`)
should wrap `review_model`'s value too for consistency, though a bare model
slug needs no escaping in practice.

**Immediately available TODAY, with zero code change** (workaround, not the
target state): use the plain **`exec`** path, which already fully supports
`--model`/`--effort`/`--output` (`codex_run.py:64-94`, live-confirmed §3-4),
with a prompt that embeds the target instruction directly — this is exactly
`kb-review`'s own documented `cold:codex-cli-direct` fallback variant
(`references/lanes.md`, "Spawning: prefer an unnamed subagent" section):

```
mise run kb-codex -- --model gpt-6-astra --effort xhigh \
  --output .agent/kb/review/reports/review-<sha>-cold.md \
  "$(cat <<'EOF'
Review <FIXED>...HEAD in this repository. Run:
    git diff <FIXED>...HEAD -- . ':(exclude)docs/research/**'
yourself and read it. [... METHOD paragraph + report format from lanes.md,
verbatim ...]
State the HEAD commit you reviewed, in full, at the top of your report.
EOF
)"
```

The trade-off: this loses `codex review`'s dedicated rubric/structured
`ReviewOutputEvent` formatting (§2.2) and pushes target-resolution into prose
codex must act on with its own shell access, rather than the CLI's own
`ReviewTarget` resolution. Recommend this only as a stopgap if the #678 fix is
not landed before an Astra review is needed.

**Do not use `fable-orchestrator`'s `run-lane.sh codex-review ... gpt-6-astra`
(§5.6) as the primary mechanism for THIS repo's `kb-review` skill** — it is a
different plugin's own reviewer-agent lane (`fable-orchestrator:codex-reviewer`),
uses the **nested** `codex exec review` surface, and its receipt/report
conventions are not this repo's `kb_setup.review` schema. It remains cited as
the reference implementation for the *timing/detach mechanism* (6.3), and
remains a legitimate independent fallback per `kb-review`'s existing fallback
chain if `kb_setup`'s own codex lane is unavailable.

All four mandatory flags from `ai-cli-invocation.md`/`codex_lane.py` still
apply unconditionally: `--add-dir "$HOME/Library/Caches"` (write-sandbox
lanes only — a review lane is read-only, so N/A here, confirmed
`codex_run.py:82-87` only adds it under `workspace-write`),
`-c sandbox_workspace_write.network_access=true` (N/A, read-only), **`--dangerously-
bypass-hook-trust`** (always — this repo's hooks are skipped silently
otherwise, §guard docstring), prompt on `-` stdin (ARG_MAX safety for a large
METHOD paragraph).

## 6.3 Timing plan

**Expected duration class: "10s of minutes, not sub-minute" for a genuinely
large/complex diff.** Basis: §5.1's community reports (5-6 min compactions,
"long hours" issue titles) plus the structural fact that a large review
reading many files at `xhigh` effort compounds both per-turn latency (Speed
2/5 per the official model card, §5.2) and multi-turn tool-call count. The
live probe (§4) only bounds the FLOOR (a trivial prompt finishes fast); it
says nothing about the ceiling this directive is actually asking about, and
no larger probe was run in this session (out of scope per the task's own
"do NOT run anything larger" instruction).

**Concrete numbers to change, and where:**

1. **`mise.toml`'s `[tasks.kb-codex]` `timeout = "1800s"` (`mise.toml:1090`,
   §1.3) is the outer ceiling for ANY `kb-codex` invocation, Astra or not.**
   30 minutes may already be tight for a "very long" Astra review per §5.1 —
   consider a `kb-codex-astra`-specific task (or an env-var-driven timeout
   override on the existing task) at **e.g. 3600s-5400s (60-90 min)**,
   mirroring `run-lane.sh`'s own pattern of a lane-specific `SECS` rather than
   one constant for every lane shape. Whatever number is chosen, state it as
   a deliberate ceiling with the same "why this number, not a guess" rigor
   `.codex/config.toml`'s `startup_timeout_sec = 120` comment models (§5.5)
   — this repo's own convention is to justify a timeout from a real
   measurement, and no such measurement exists yet for an Astra review at
   realistic size (flagged, not fabricated).
2. **The harness's own foreground-call cap (~600s, `long-running-command-
   hangs.md` rule 2) will fire well before either of the above ceilings** on
   a genuinely long review. `kb_setup.codex_run.run()` is a single blocking
   `subprocess.run()` (§1.2) with no detach/poll capability today — it will
   either get silently auto-backgrounded by the calling harness (losing the
   `raw=true` stdio connection the task explicitly documents as required,
   §1.3) or simply exceed the caller's patience. **This is a real gap, not
   covered by extending `_review_argv` alone.**
3. **Recommended fix, modeled on `run-lane.sh`'s proven shape (§5.6) but
   native to this repo's `zero-bash-logic` constraint:** a
   `kb_setup.codex_run` addition — call it `start_detached()` — that:
   - `subprocess.Popen`s the built argv (never `.run()`) with stdout/stderr
     redirected to a log file and `--output <file>` for the final message,
     returns the PID immediately;
   - a companion `mise run kb-codex -- --poll <pid>` (or a bare
     `kill -0 <pid>` + log-file tail, no new mechanism needed if the caller
     already has the PID) checks liveness in the caller's own ≤90s polling
     loop, per `long-running-command-hangs.md` rule 2 — **the calling AGENT
     does this via the harness's `run_in_background` Bash parameter today,
     with zero code change**, so the python-side `start_detached()` is only
     needed if this must be driven from inside a `kb_setup` module itself
     (e.g. a future automated `kb-review` re-run) rather than from an
     orchestrating Claude/Codex session;
   - a `reap`-equivalent (`os.killpg` on the process group, matching
     `run-lane.sh:209-217`'s "kill the group, not just the PID" lesson,
     since codex spawns child tool-call workers).
   **This is a design sketch, not evaluated for effort or filed as an issue
   in this session** — flagged for the team-lead to size.
4. **Partial-progress reporting**: `codex exec`/`codex review` support
   `--json` (events-as-JSONL to stdout, confirmed in `codex exec --help`,
   §3) — a detached Astra lane's log file, if launched with `--json`, gives a
   poller something better than "still running" to report (the latest event
   type/timestamp), matching `run-lane.sh`'s own `--json` choice for its
   `codex-review` lane (§5.6). `codex review`'s CLI (top-level) does not list
   `--json` in its own `--help` (§3) — this would require the nested `codex
   exec review` surface instead, another point in favor of that surface if
   live progress visibility is a hard requirement; left as an open trade-off
   for the team-lead rather than resolved here.

## 6.4 When to choose Astra — a rule, not a vibe

Recommend an **explicit, human/orchestrator-stated choice**, not automatic
size-detection: `kb-review`'s own step 2 already replaced a diff-type
*table* with a single lane specifically because an automatic per-diff
decision procedure was the thing that cost 2.93M tokens across 17 runs (§5.3)
— resist rebuilding that table one lane deeper. Concretely, extend
`references/lanes.md`'s step-2 routing table with a note: *"When the diff is
large and/or touches multiple interacting guards/gates (the shape Ray called
out directly), and the implementer was Claude or antigravity, the human/
orchestrator may request `cold:codex-astra` instead of `cold:codex` explicitly
— never silently, given §5.1's cost/capacity signals."* Given §5.1's refusal-risk
row, the dispatch should ALSO instruct: *"if the model returns a policy
refusal or `invalid_prompt`-shaped error instead of a review, report that
verbatim and do not retry silently — fall back to `cold:codex` (gpt-5.6-sol)
and record which lane actually produced the receipt's findings,"* mirroring
this repo's existing "never silently substitute" doctrine for a missing/failed
CLI (SKILL.md step 2, `kb-codex-advisor.md`'s "Hard limits").

## 6.5 Files to add/change (proposal only — none written this session)

| File | Change |
|---|---|
| `python/src/kb_setup/codex_run.py` | Extend `_review_argv`/`_run_review` to accept `--model`/`--effort` (already parsed by `run()`'s `argparse`, `codex_run.py:255-257`, and already silently dropped for `--review`, per #678) and forward `-c review_model=`/`-c model_reasoning_effort=` |
| `.claude/skills/kb-review/references/lanes.md` | Add the `cold:codex-astra` variant note per 6.4; keep the METHOD-paragraph/scope/save-path template identical — only the model/effort flags differ |
| `.agent/kb/reports/agents/…` receipts | No schema change — `cold:codex-astra` is a legal `lanes_ran` entry today per `_lane_prefix` (§5.3); `mise run kb-review-receipt -- --lanes cold:codex-astra ...` needs no code change |
| `.claude/agents/kb-codex-astra-reviewer.md` (new, optional, for parity with `kb-codex-advisor`) | Frontmatter: `name: kb-codex-astra-reviewer`, `description` (a cold, cross-family code reviewer for large/complex diffs, running gpt-6-astra via the codex CLI at xhigh), `tools: Bash, Read, Grep, Glob, Write`, `color:` (pick one unused — `teal` is taken by `kb-codex-advisor`), **no `model:` key** (same reasoning as `kb-codex-advisor.md` — the wrapper's own Claude-side reasoning is trivial). Body: the lanes.md dispatch template + the invocation from 6.2 + the "write report to disk before returning" discipline already standard for every codex-backed agent in this repo |
| `.codex/agents/kb-codex-astra-reviewer.toml` (new, optional, mirrors the `.md` per `kb-codex-advisor`'s existing pair) | `name`, `description`, **`model = "gpt-6-astra"`** (source-confirmed legal key, §5.4 — unlike `kb-codex-advisor.toml`, which omits `model` and relies on the repo-wide `default_subagent_model`, this one MUST set it explicitly or it would inherit `gpt-5.6-sol`), `model_reasoning_effort = "xhigh"`, `developer_instructions = '''<same body as the .md>'''`. Caveat from §5.4 still applies: this is codex's own internal sub-agent roster, a parity addition, not the mechanism `kb-review` actually dispatches through |
| `mise.toml` | Optionally a longer-timeout variant task or an env-driven override per 6.3 item 1 — sizing left to the team-lead |
| issue #678 | Update/close once `codex_run.py` is fixed — its body already asks for exactly this, plus a `--print-argv` regression test pinning review-mode argv (its own "Suggested fix" section) |

## 6.6 What stays the same

- The `cold:codex` / `gpt-5.6-sol` / `xhigh` default path (`kb-codex-advisor`,
  the ordinary `kb-review` cold lane) is untouched — Astra is additive.
- `kb-review`'s one-lane-always policy, two-round bound, cross-family table,
  METHOD-paragraph template, scope exclusion, and receipt schema are all
  unchanged — Astra is a drop-in model/effort substitution inside the
  existing `cold` slot, not a new lane family.
- All four mandatory `ai-cli-invocation.md` flags, the `mise run kb-codex`
  entry point, and the PreToolUse guard (`codex_lane.py`) — unchanged; the
  guard does not distinguish by model, so no guard change is needed to permit
  `--model gpt-6-astra`.
- "Resynced codex graphify sources" (Ray's directive): `sources/codex.manifest`
  is already pinned to `rust-v0.153.4` (`3d2ee51c`), matching the installed
  binary exactly (§0) — **no resync was needed or performed**; the pin was
  already current. `sources/codex/` remains `build = skip` in `kb-build`
  (#417, an unrelated `Cargo.toml`-zero-nodes blocker) — this repo's
  knowledge graph still cannot answer "what does codex's source say about
  Astra" natively (§0a); this report is the substitute until #417 is
  resolved, and should itself be considered a `sources/REGISTRY.md`
  candidate note per `research-repo-enumeration.md`'s closing-the-loop rule.
