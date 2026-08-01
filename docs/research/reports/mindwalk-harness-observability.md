# mindwalk — harness-observability gap analysis

**Tool**: [cosmtrek/mindwalk](https://github.com/cosmtrek/mindwalk) — Go, MIT,
pinned at `e208b6b8504138843f671e031f28129b66003a67` (`sources/mindwalk.manifest`,
`kind = code`, `scope = study`).

**Status**: COMPLETE. Written incrementally; every probe's arm is stated inline,
and §6 is the consolidated claim register.

**Bottom line**: **yes** — mindwalk parses the transcripts Claude Code writes on
this machine (confirmed by building the pinned binary and running it on a real
2,800-line session of this repo), and it can show a `kb-review` lane's exact
file footprint against the lane's own brief. Its "scope: does the footprint match
what the task needed?" is a named judge category, not an inference. It is **not**
a graphify substitute in any direction: its repo model carries no symbols and its
input lives only in an unversioned machine-local directory.

**Lens (set by the round, not by me)**: this is *not* a retrieval comparison.
mindwalk reads Claude Code / Codex **session logs** and replays agent footprint
on a 3D repo map. It does not index or retrieve code. The question is:

> Can it show what a `kb-review` lane or a `codex` implementer actually touched
> during a round, versus what the spec scoped?

---

## 0. What mindwalk is, from its own pinned source

Three artifacts, deliberately separate (`AGENTS.md`, `README.md` § Under the hood):

1. **trace** — a session log normalized into an ordered stream of file-touch
   events (`internal/adapter`, one adapter per agent format). Adapters also
   correlate subagent sessions into an **agent graph**, so each subagent's trace
   replays on its own.
2. **citymap** — a deterministic layout of the repository (`internal/citymap`);
   same tree → same map, so replays are comparable across sessions.
3. **report** — an LLM judge's evidence-anchored findings about one session
   (`internal/judge`), generated **only on explicit request**. The judge
   subprocess is sealed (no tools, no MCP, no user/project settings, no session
   persistence) and verdicts are rolled up **mechanically** from finding
   severities, never decided by the LLM.

CLI surface (`README.md:43-49`):

```text
mindwalk serve [--port N] [--no-open] [--claude-dir DIR] [--codex-dir DIR]
mindwalk open  [--no-open] <session.jsonl>
mindwalk map   [--no-open] <repo>
mindwalk build <repo> [-o out]        # citymap JSON
mindwalk trace <session> [-o out]     # normalized trace JSON
mindwalk analyze <session> [--judge claude|codex] [--model name]
```

`mindwalk trace` and `mindwalk build` are **headless JSON emitters** — no
browser, no 3D. That matters below: the machine-readable half of this tool is
usable from a mise task without any of the visualization.

---

## 1. Probe log — every claim below has its arm stated

### 1.1 The study graph is reachable, but not through a sanctioned path

**Finding (process defect, not a mindwalk finding).** The round's brief said to
query mindwalk's nodes with
`graphify query "<q>" --graph graphify-out/study-graph.json`. That command is
**denied** by `kb_setup.hook_guard`:

```text
Do not run `graphify query` by hand. Use the mise task: mise run kb-query -- "<q>".
```

and `mise run kb-query` (`kb_setup.query`, `mise.toml:263`) exposes only
`--prose` / `--idf` / `--budget` / `--top` — **there is no `--graph` flag**, and
`--prose` is hard-wired to `graph-prose.json`. So as of this commit the
`study-graph.json` that `kb-build` produces (`kb_setup.graph._build_study_graph`,
`graph.py:264`) has **no supported query path at all**. I read it as JSON
directly instead (read-only, no graphify invocation).

**Arm**: the guard denial is quoted verbatim above (it fired). `grep` of
`mise.toml:263-287` shows the flag list; `--graph` absent. Control: `--prose`
IS present in the same block, so the grep discriminates.

### 1.2 mindwalk IS in the study graph — my first count was a broken probe

| probe | result |
|---|---|
| count nodes whose `file` field contains `mindwalk` | **0** |
| inspect node schema | field is **`repo`**, not `file` |
| count nodes whose `repo == "mindwalk"` | **2,845** ✅ |

**REFUTED (my own claim #1).** "0 mindwalk nodes" was a field-name bound, the
same shape as the `lmstudio` vs `LM Studio` failure in
`probes-need-a-control-arm.md`. Control arm: `Counter(n['repo'])` over the whole
graph returns `{'knowledge-base': 41154, 'mindwalk': 2845}` — 43,999 total, so
the probe discriminates and nothing else is hiding in there.

### 1.3 Does mindwalk parse the transcript format Claude Code writes **on this machine**?

**Yes, on the essentials.** This is the round's headline question and it needed a
real-file arm, not an assumption.

mindwalk's `rawLine` (`internal/adapter/claudecode/adapter.go:261-273`) reads:
`type`, `timestamp`, `sessionId`, `agentId`, `isSidechain`, `cwd`, `gitBranch`,
`message`, `aiTitle`, `content`, `subtype`.

Recognition gate — `isClaudeLine` (`adapter.go:370-380`) — accepts a line if
`sessionId != ""`, **or** `type ∈ {user, assistant, system, ai-title}` with a
timestamp or a message.

**Arm run**: parsed **every** `~/.claude/projects/**/*.jsonl` on this machine —
**2,419 files** — plus a keyed field census over the 12 most recent sessions of
this repo's own project dir (2,898 lines).

| field mindwalk needs | present on this machine? | evidence |
|---|---|---|
| `sessionId` | **2,877 / 2,898 lines** | recognition gate passes on essentially every line |
| `type` | 100% | observed values include `user`, `assistant`, `system` |
| `timestamp`, `cwd`, `gitBranch` | 2,190 / 2,898 | present on every content-bearing line |
| `message.content[].type == "tool_use"` | 433 | the event source |
| `message.content[].type == "tool_result"` | 431 | pairs with the above (4 unpaired → flushed by `adapter.go:241-245`) |
| `message.model` | `claude-opus-5` | populates `trace.Session.Model` |
| `isSidechain: true` | **50,094 lines across 1,946 files** | subagent transcripts |
| `agentId` | **53,561 lines across 1,973 files** | subagent identity |
| `system` + `subtype` containing `compact` | **`compact_boundary`, 4 lines** | `isCompaction` (`adapter.go:366`) **matches** |
| `type == "ai-title"` | **1,595 lines** | title extraction works |

**REFUTED (my own claims #2, #3, #4).** From the first 12-file sample I had
written down that `isSidechain` is never true, `agentId` never present, and
`ai-title` never emitted. All three were **display-bound artifacts** — a
12-file, one-project sample. The full 2,419-file scan reversed every one. This
is `probes-need-a-control-arm.md` rule 3 (bound-limited searches) biting three
times in one paragraph.

**Control arm on the negative direction**: the same scan found `type` values
this machine writes that mindwalk does **not** model — `attachment` (836),
`mode`, `permission-mode`, `bridge-session`, `agent-setting`, `last-prompt`,
`custom-title`, `queue-operation`, `file-history-delta`,
`file-history-snapshot`. So the scan can distinguish "field present" from
"field absent", and it reports both.

### 1.4 The known unmodelled fields, and whether they cost anything

| this machine writes | mindwalk models it? | cost |
|---|---|---|
| `custom-title` / `customTitle` (**7,015** lines) | **no** — it only reads `ai-title`/`aiTitle` | session title falls back to the filename (`adapter.go:147-149`) when a session has only a custom title. Cosmetic. |
| `teamName` / `agentName` (929 lines in the sampled 12) | **no** | the fleet/team labels this harness attaches are dropped; agent identity comes only from the `.meta.json` sidecar |
| `effort`, `permissionMode`, `agentSetting` | **no** | not modelled; irrelevant to footprint |
| `file-history-snapshot` / `file-history-delta` | **no** | mindwalk derives edits from `tool_use`/`tool_result`, not from these |
| `toolUseResult` (top-level, 431 lines) | **no** — it reads `content[].tool_result` | the harness *also* writes a richer top-level result object mindwalk ignores; the nested one it does read is present, so no loss observed |

None of these is fatal. **UNVERIFIED**: whether `toolUseResult` ever carries a
touched path that the nested `tool_result` does not — I did not diff the two
representations field-by-field.

### 1.5 Subagent correlation — the layout question, and where it breaks

This is the part that decides whether the round's actual question ("what did the
**lane** touch?") is answerable.

`AgentGraphInputs` / `BuildAgentGraph` (`internal/adapter/claudecode/agents.go:41,78`)
both compute:

```go
subagentsDir := filepath.Join(filepath.Dir(root.Path), root.ID, "subagents")
```

i.e. `~/.claude/projects/<proj>/<sessionID>/subagents/`, enumerated with a
**non-recursive `os.ReadDir`** that **skips directory entries**
(`agents.go:49-51`, `agents.go:163-165`). Sidecars are `<basename>.meta.json`
carrying `name` / `agentType` / `description` / `toolUseId` / `spawnDepth`
(`agents.go:23-29`).

**Arm run**: enumerated the real layout of all 1,946 `agent-*.jsonl` on this
machine and bucketed by relative directory shape.

| actual layout | files | mindwalk sees it? |
|---|---|---|
| `<sessionID>/subagents/agent-*.jsonl` | **213** | **YES** — exact match |
| `<sessionID>/subagents/workflows/wf_<id>/agent-*.jsonl` | **1,733** | **NO** — one directory level too deep for a non-recursive `ReadDir` that skips dirs |

**And for *this repo* specifically**: the
`-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base` project dir holds
**158 root sessions and 89 `agent-*.jsonl`, and 100% of those 89 sit directly
under `<sessionID>/subagents/`** — zero workflow nesting. So **mindwalk's agent
lens works for this repo's Agent-tool subagents as-is.**

The sidecar shape also matches: sampled 400 `.meta.json` files → keys
`agentType` (400), `spawnDepth` (400), `description` (14), `toolUseId` (14).
Note the asymmetry — `toolUseId` is present on only ~3.5% of sidecars, and
`toolUseId` is what upgrades a link from `derived` to `exact`
(`agents.go:248-259`, `AgentLinkMethodClaudeToolUseID`). So most subagents would
be attached to the root by the weaker
`AgentLinkMethodClaudeSubagentsDirectory` / `LinkQualityDerived` path.

**Control arm on that 400-file sample**: `description`/`toolUseId` are *present
on some*, so the census can see them; they are genuinely absent on the rest,
not invisible to the probe.

**UNVERIFIED**: whether the ~3.5% figure holds over all 1,946 sidecars — I
sampled the first 400 by glob order, which is a bound I did not remove.

### 1.6 Codex sessions

`codex.DefaultDir()` = `~/.codex/sessions` (`internal/adapter/codex/adapter.go:24-29`),
walked with a **recursive `filepath.WalkDir`** accepting any `.jsonl`
(`adapter.go:49-70`).

**Arm run**: `~/.codex/sessions` exists on this machine with **1,251 session
files**, laid out as `YYYY/MM/DD/rollout-<ISO>-<uuid>.jsonl`. `WalkDir` is
recursive, so the date nesting is not an obstacle. It also filters
`!meta.Auxiliary`, i.e. codex subagent rollouts are excluded from the top-level
list the same way Claude's `agent-*` files are.

**UNVERIFIED**: I have not confirmed that mindwalk's codex `Summarize` actually
*recognizes* these 1,251 files (the codex analogue of `isClaudeLine`), nor that
any of them correspond to this repo. That needs an execution arm — see §2.

---

## 2. Execution arm — I built it and ran it on this repo's real sessions

Everything above is source reading. This section is the arm that makes it
evidence.

```text
go version go1.26.5 darwin/arm64   (mise shim)
cd sources/mindwalk && go build -o /tmp/mindwalk ./cmd/mindwalk   → rc=0
```

The build needed no network beyond the module cache and no frontend step —
`internal/server/static/` ships embedded in the pinned tree. **Working tree
stayed clean**: `git status --short` after the build shows only the three
untracked research reports (this one and two other agents'), no modification
under `sources/`.

### 2.1 A real main session of THIS repo

```text
/tmp/mindwalk trace ~/.claude/projects/-Users-…-knowledge-base/a86bf6ac-….jsonl → rc=0
```

2,800-line session → a trace that parsed cleanly:

| field | value |
|---|---|
| `session.harness` / `model` | `claude-code` / `claude-opus-5` |
| `session.cwd` | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base` ✅ |
| span | `2026-07-27T21:16:52Z` → `2026-07-28T01:25:56Z` |
| events | **388** |
| marks | 26 `user-message`, **14 `subagent`** |
| actions | exec 174, other 83, **edit 65**, read 42, search 12, verify 12 |
| **distinct file paths touched** | **135** |
| `edited` / `churnFiles` / `maxEditsPerFile` | 22 / 10 / 8 |
| `eventsBeforeFirstEdit` | 17 |
| `editsAfterLastVerify` | **11** |
| `regressionRate` / `errorRate` | 0.226 / 0.018 |
| `fovea` / `parafovea` | 42 / 93 |
| `observability` | `{reads: "estimated", errors: "exact"}` |

Top targets were exactly the files that session worked on —
`python/src/kb_setup/goal.py` (24), the goal+rider pair (19/16),
`docs/goals/README.md` (15), `python/src/kb_setup/graphify_env.py` (13),
`tests/test_goal.py` (13), `CLAUDE.md` (9), `mise.toml` (8).

Two details worth recording:

- It extracts **weak path hits out of Bash command lines**, tagged
  `{"touch": "hit", "weak": true}` — e.g. `wc -l .agent/plans/session-….md`
  became a target. So `exec`-heavy sessions (which this repo's are: exec was
  the single largest action bucket at 174/388) are not blind spots.
- Every event summary carries `"N targets, M outside"` — it counts paths
  **outside the repo** separately.

### 2.2 A real `kb-review` cold lane — the round's actual question

```text
/tmp/mindwalk trace …/4501d6ce-…/subagents/agent-a26083705fe9dc667.jsonl → rc=0
```

| | |
|---|---|
| events | 93 |
| actions | exec 48, read 34, search 11, **edit 0** |
| distinct paths | 24 |
| `userTurns` | 1 |
| top targets | `tests/test_pr.py` (20), `python/src/kb_setup/pr.py` (13), `.claude/skills/kb-review/SKILL.md` (11), `.claude/skills/kb-review/references/lanes.md` (10), `python/src/kb_setup/cli.py` (9), `tests/test_review_cli.py` (9), `python/src/kb_setup/review.py` (7), `tests/test_review.py` (7) |

**This is the round's question, answered from a real artifact.** A read-only
review lane, `edit: 0` as a reviewer should be, with its 24-file footprint
enumerated and ranked — and the footprint is recognisably the `kb-review`
surface.

And the *spec* half is there too. The single `user-message` mark is the lane's
own brief, verbatim:

> `Review the range 9521853...HEAD in the repository at …/knowledge-base (HEAD
> is b4d1063ec2ccc3151d7c7763b81a94406646ede6). Read the diff yourself with
> git; do not ask what it is for. …`

So mindwalk holds, in one artifact, both *what the lane was told to review*
(including the exact SHA — which `kb_setup.review` separately requires the
report to name, #56) and *what it actually opened*.

### 2.3 The citymap

```text
/tmp/mindwalk build . -o /tmp/mw-city.json → rc=0
```

357 file entries. Per file: `{id, path, dir, lines, bytes, lang, rect{x,z,w,d},
ghost}`. Deterministic layout; `ghost` marks files a session touched that no
longer exist. **That is the whole schema** — see §4.1 for why that matters.

### 2.4 What the judge would see (read, not run)

I did **not** run `mindwalk analyze` — it spends tokens through a real CLI. I
read `internal/judge/` instead.

- `SupportedCLIs = ["claude", "codex"]`, detected on PATH in that order
  (`judge/cli.go:32-49`). Both are installed here, so the judge is live on this
  machine. **UNVERIFIED**: that an actual `analyze` run succeeds end-to-end.
- The judge subprocess runs in `~/.mindwalk/judge` — "a neutral directory … no
  repository and no project instructions" (`cli.go:53-62`), sealed with no
  tools, no MCP, no user/project settings, no session persistence.
- `BuildInput` (`judge/input.go:26`) renders **only** the normalized trace:
  session meta, user messages, precomputed stats, one line per event. It never
  sees the raw log.
- The four judge categories (`judge/prompt.go:15-18`) are `exploration`,
  **`scope`**, `wandering`, `verification`. Category 2 reads, verbatim:

  > *"scope: does the footprint match what the task needed? Were files touched
  > that the task did not call for, or areas left unread that should have been
  > read?"*

  That is the round's question as a **first-class, named feature** of the tool.
- Verdicts are rolled up **mechanically from finding severities**, never decided
  by the LLM (`AGENTS.md`, "Evaluation invariants"). Reports are cached per
  session in `~/.mindwalk/reports` and go stale — never auto-rerun — when
  `InputDigest` moves.

**The hard limit on the spec side**, and it is a real one:
`maxUserMessages = 12`, **`maxUserMessageLen = 600`**, `maxNarrativeEvents = 2000`
(`judge/input.go:17-20`). The judge sees at most **600 runes of each user
message**. This repo's lane briefs and its `docs/goals/*-goal.md` payloads
(budgeted to ≤4,000 chars *by design*) are far longer than that. So the judge's
notion of "what the spec scoped" is a **600-rune prefix of the prompt**, not the
tracked goal document — which mindwalk cannot read at all.

One more sharp edge: `InjectedUserMessage` (`adapter/adapter.go:160-166`) drops
any user message that starts with `<` and ends with `>`. That correctly discards
`<system-reminder>` envelopes — and it would also discard a lane brief delivered
inside a `<teammate-message>` envelope, which is exactly how this round's own
brief arrived. **UNVERIFIED**: whether that specific envelope appears in a
recorded transcript as a standalone user message (my sampled lane brief was
plain text and survived).

---

## 3. Direction A — what mindwalk shows that this repo cannot see today

Each row is a capability this repo genuinely lacks, not a nicety.

| # | Capability | Why this repo has nothing equivalent |
|---|---|---|
| A1 | **Per-lane file footprint.** The exact set of paths a subagent opened, ranked by touch count, with edit/read/search/exec separated. | The `kb-review` receipt records *which lane ran* and its report path (`.agent/kb/review/receipt-<sha>.json`); it records **nothing about what the lane read**. A lane that reviewed 3 of 40 changed files leaves a receipt indistinguishable from one that read all 40. |
| A2 | **Footprint-vs-scope as a checkable question.** `judge/prompt.go` category 2, with findings anchored to real trace events. | The nearest thing here is `mattpocock-skills:code-review`'s Spec axis, which compares *the diff* to the issue — not *what the reviewer looked at* to the spec. Nothing in this repo reads a transcript. |
| A3 | **Verification-discipline metrics, computed not asserted.** `editsAfterLastVerify: 11` on the sampled session; also `eventsBeforeFirstEdit`, `regressionRate`, `churnFiles`, `maxEditsPerFile`. | `verify-before-advancing.md` states this discipline as a *rule*. There is no instrument that measures compliance after the fact. `editsAfterLastVerify` is literally a machine-readable score for that rule. |
| A4 | **An agent graph over one round.** Parent→child subagent tree with link *quality* (`exact` via `toolUseId` vs `derived` via directory) and `TraceAvailability` (available / missing / unavailable) — plus `unlinkedClaudeLaunchNode` for launches whose transcript is gone. | This repo can tell you 14 subagents were launched only by re-reading the transcript by hand. Nothing enumerates them, and nothing distinguishes "subagent ran and we have its trace" from "subagent launched, trace lost". |
| A5 | **Cross-harness parity.** The same trace/stat model for Claude Code **and** `codex` (`~/.codex/sessions`, 1,251 files here). | This repo's declared implementer lane is `codex`, and it has **zero** observability into what a codex run touched. `kb-review` reads codex's *output*; nothing reads its footprint. |
| A6 | **Headless, machine-readable output.** `mindwalk trace <s> -o out.json` and `mindwalk build <repo> -o out.json` — no browser, no 3D, exit code 0. | Directly wrappable as a `kb_setup` module + mise task under `zero-bash-logic.md`. The 3D UI is optional, not the product. |
| A7 | **The instrument grades its own confidence.** `observability: {reads: "estimated", errors: "exact"}` — per-signal, per-adapter. | The same discipline this repo enforces as DRIFT/SKIP/OK in `kb_setup.currency`, applied to a surface this repo does not instrument at all. |

**A note on A1 that sharpens it.** The `kb-review` skill's own §1 records that
on #67, **"56% of reviewed lines were prose under `docs/research/`"** — the previous
rounds' own lane reports. That number was reached the expensive way. A1 is the
cheap way: a lane's footprint is 24 paths in a JSON file, and *which* 24 is a
one-line check.

---

## 4. Direction B — what this repo has that mindwalk does not

A gap analysis naming only what we lack is advocacy. These are real, and two of
them are disqualifying for any thought of substitution.

| # | Capability | mindwalk's position |
|---|---|---|
| B1 | **Semantic code graph.** graphify's aggregate is ~128k nodes with EXTRACTED/INFERRED-tagged edges, communities, god nodes, `path`/`explain`/`query`. | mindwalk's citymap is **purely structural**: `{path, dir, lines, bytes, lang, rect, ghost}` — measured on this repo, 357 entries, §2.3. **No symbols, no call edges, no query surface.** It is a *layout*, not a graph. Height encodes LOC. There is nothing to ask it. |
| B2 | **Commit-keyed, gate-enforcing evidence.** `.agent/kb/review/receipt-<sha>.json`; `kb-ship` **and** `kb-land` refuse a HEAD with no receipt; a receipt naming a lane that left no report is refused; the report must name its SHA (#56). | mindwalk reports are keyed to a **session**, cached in `~/.mindwalk/reports`, and go stale on content change. Nothing binds a report to a commit; nothing can gate a merge on one. A session is not a change. |
| B3 | **Reproducibility from committed inputs.** Sources pinned by SHA, `kb-build` rebuilds the graph, `kb-currency-check` proves which version built it. | mindwalk's entire input is `~/.claude/projects` / `~/.codex/sessions` — machine-local, unversioned, never committed, and pruned by the harness. **A trace is not reproducible on another machine, ever.** |
| B4 | **Durable cross-session memory.** `kb-remember` → `graphify-out/memory/` (committed) → `kb-reflect` → `reflections/LESSONS.md`. | None. mindwalk's per-session reports do not aggregate; there is no notion of a lesson that outlives a session. |
| B5 | **Retrieval for consumers.** `kb-serve` MCP, `kb-query --prose --idf`, zero LLM tokens per read. | mindwalk exposes local HTTP APIs for its own frontend only. It answers "where did the agent go", never "what does this code do". |
| B6 | **Spec as a tracked artifact.** `docs/goals/*-goal.md` + rider, audited by `kb-goal-check`. | The judge's spec is a **600-rune prefix** of a user message (§2.4). mindwalk cannot read a goal document, and has no concept of one. |
| B7 | **Corpus-wide, cross-repo scope.** 26 pinned sources; a `scope=study` partition; prose + code in one graph. | Strictly one session × one repository at a time. There is no cross-session or cross-repo aggregate. |

**B1 and B3 are the disqualifying pair.** mindwalk is not a candidate to replace
or absorb any part of graphify's role here, and the round was right that
comparing them on retrieval would be a category error. They occupy disjoint
surfaces: graphify knows the *code*, mindwalk knows the *walk*.

---

## 5. Where the two actually meet

The one genuinely interesting composition, stated plainly and **not implemented
or tested** — this is a proposal, marked **UNVERIFIED** as a design:

`mindwalk trace` yields the set of paths a lane touched. graphify yields, for a
given diff, the set of files and symbols the change *implicates* (`graphify
affected`). Those are two sets over the same repo. The interesting quantity is
their difference:

- **changed ∖ touched** — files the diff altered that the review lane never
  opened. Today, unmeasurable here; this is A1 + B1 together and neither tool
  computes it alone.
- **touched ∖ changed** — the wandering signal, which mindwalk's judge already
  names but scores only against a 600-rune prompt prefix, not against the diff.

Both sets are already producible headlessly today (`mindwalk trace -o`,
`git diff --name-only`), which puts the cheap version of this within one
`kb_setup` module. I did not build it and make no claim it works.

---

## 6. Claim register — negatives and their arms

Per this repo's `probes-need-a-control-arm.md`, every absence claim above,
restated with the arm that discriminates it:

| claim | arm | verdict |
|---|---|---|
| mindwalk parses this machine's Claude transcripts | built the binary, ran `trace` on a real 2,800-line KB session → rc=0, 388 events, 135 paths | **CONFIRMED by execution** |
| mindwalk's agent lens works for *this repo's* subagents | 89/89 KB `agent-*.jsonl` sit at `<sessionID>/subagents/` — the exact path `agents.go:41` computes | **CONFIRMED** |
| mindwalk misses **workflow** subagents | 1,733 of 1,946 `agent-*.jsonl` machine-wide sit at `<sessionID>/subagents/workflows/wf_<id>/`, one level below a non-recursive `ReadDir` that skips dirs. Control: the other 213 DO match, so the layout probe discriminates | **CONFIRMED, but 0 of them are in this repo's project dir** |
| citymap carries no symbols | dumped the full entry schema from a real `mindwalk build .` run: 8 keys, none semantic. Control: `lines`/`lang` ARE present, so the dump is not empty | **CONFIRMED** |
| the judge sees ≤600 runes of the spec | `maxUserMessageLen = 600`, `judge/input.go:18`, used at `input.go:86`. Control: `maxUserMessages = 12` and `maxNarrativeEvents = 2000` in the same block, so the grep reads real constants | **CONFIRMED** |
| `study-graph.json` has no sanctioned query path | guard denied `graphify query --graph`; `mise.toml:263-287` flag list has `--prose`/`--idf`/`--budget`/`--top`, no `--graph`. Control: `--prose` found by the same grep | **CONFIRMED** |
| an `analyze` run succeeds here | **not run** | **UNVERIFIED** |
| `toolUseResult` never carries a path the nested `tool_result` lacks | not diffed | **UNVERIFIED** |
| the `toolUseId`-present rate (~3.5%) holds beyond 400 sidecars | sampled first 400 by glob order; bound not removed | **UNVERIFIED** |
| codex `Summarize` recognizes this machine's 1,251 rollouts | directory + walk semantics checked; recognition not executed | **UNVERIFIED** |
| the graphify × mindwalk set-difference idea works | not built | **UNVERIFIED (design only)** |

---

## GitHub repos touched

- [cosmtrek/mindwalk](https://github.com/cosmtrek/mindwalk) — the tool under
  analysis; read its `README.md`, `AGENTS.md`, `internal/adapter/claudecode/{adapter,agents}.go`,
  `internal/adapter/codex/adapter.go`, `internal/adapter/adapter.go`,
  `internal/judge/{cli,input,prompt}.go`, `internal/model/stats.go`, and built
  and ran `cmd/mindwalk` at the pinned SHA.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the
  counterparty in every Direction-B row; reached only through this repo's
  `kb-query` task and its own committed docs, not by reading upstream source
  this round.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base)
  — this repo: `mise.toml`, `python/src/kb_setup/graph.py`,
  `.claude/skills/kb-review/SKILL.md`, and the rule files cited above.

**Claims refuted during this work: 5.**

1. "The study graph contains 0 mindwalk nodes" — the probe keyed on `file`; the
   field is `repo`. Truth: **2,845**.
2. "`isSidechain` is never true on this machine" — 12-file sample. Truth:
   **50,094 lines across 1,946 files**.
3. "`agentId` is never present" — same bound. Truth: **53,561 lines across
   1,973 files**.
4. "Claude Code no longer writes `ai-title`, so mindwalk's title extraction is
   dead" — same bound. Truth: **1,595 `ai-title` lines** machine-wide (alongside
   7,015 `custom-title`, which mindwalk genuinely does not model).
5. "mindwalk cannot see this repo's subagents, because 1,733 of 1,946 agent
   transcripts are nested one level too deep" — true machine-wide, and **false
   for this repo**: all 89 KB subagent transcripts sit at the exact depth
   `agents.go:41` expects.

Refutations 2–4 were the *same* defect three times — a 12-file, one-project
sample reported as a property of the machine. Refutation 5 is the one that
would have shipped as a wrong headline: the pessimistic finding was real but
scoped to a directory shape this repo does not produce.
