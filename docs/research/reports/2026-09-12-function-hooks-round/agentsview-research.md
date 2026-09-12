# agentsview research — 2026-09-12

**Lane:** `kb-codex-astra-advisor`. Status: **COMPLETE**.
**Codex consult:** ONE lane — `codex exec --sandbox read-only --model gpt-6-astra -c model_reasoning_effort=xhigh` (argv verified with `--print-argv`), rc=0, 57,799 tokens. It did **not** refuse, time out, or return empty. Its verdict is quoted where used; every measurement in this report is mine, not the lane's.
**Report path:** `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/agentsview-research.md`

## 🔴 LANE DEVIATION, stated up front

The task said to fan out to `mise run kb-codex -- --network`. I did **not** do that,
and the reason is a permission boundary, not a preference.

`uv run kb-setup codex --help` (measured 2026-09-12):

```
  --network          allow network egress; implies --write, since the flag is
                     a write-sandbox key
```

`--network` **implies `--write`**. This lane's own configuration
(`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/agents/kb-codex-astra-advisor.md`)
states: *"Never `--write`, never `--network`. You advise; you change nothing, and
codex must not be given permission to."* A network lane here is a
workspace-write lane, which this agent is configured not to launch.

**What I did instead:** gathered every network fact MYSELF (`gh api`, the
firecrawl/exa MCP surfaces), then used read-only codex lanes for synthesis over
that evidence. Same coverage, no sandbox escalation. Where a fact came from a
codex lane rather than from my own probe, it says so.

---

# 🔴 HEADLINE: the retention panic is over. The archive already has the data.

**The single decision this forces:** stop treating transcript loss as urgent, and
start treating *tombstoning* as the thing to guard against. The 30-day wall
deletes **files**; agentsview kept the **content**. What is now at risk is not the
data — it is our ability to keep querying it after a future agentsview
reconciliation marks those rows `source_missing`.

## The measurement, control-armed, 2026-09-12

Archive: `/Users/rmanaloto/.agentsview/sessions.db` — **4.8 GB, 9,526 sessions**.

| probe | result |
|---|---|
| KB Claude sessions in archive started **before** 2026-08-14 (oldest file on disk) | **283** |
| …of those, how many still have their `.jsonl` on disk | **0** |
| …how many are **missing from disk** | **283** |
| **CONTROL ARM** — same existence test on sessions started ≥ 2026-09-09 | **110 on disk, 0 missing** |

The control arm is what makes the negative trustworthy: the same one-line test
returns "present" for recent sessions and "absent" for old ones, so it
discriminates. It is not blind.

**Reproduce it:**

```bash
DB="file:$HOME/.agentsview/sessions.db?mode=ro"
sqlite3 "$DB" "SELECT COUNT(*) FROM sessions
  WHERE project='knowledge_base' AND agent='claude' AND started_at < '2026-08-14';"
# then test each file_path with [ -f "$p" ]
```

## End-to-end proof that the CLI still reaches them

Session `3cd95785-6d0e-4e33-a4da-db05b9a80a0c` — started 2026-08-02T22:00,
**765 messages**, transcript file **deleted from disk**:

```bash
mise exec -- agentsview session get 3cd95785-6d0e-4e33-a4da-db05b9a80a0c --json
# rc=0, returns the full record
```

It came back complete, including fields **nothing in this repo computes**:
`outcome: completed`, `outcome_confidence: medium`, `health_score: 37`,
`health_grade: F`, `tool_failure_signal_count: 8`, `edit_churn_count: 5`,
`consecutive_failure_max: 3`, `compaction_count: 1`,
`mid_task_compaction_count: 1`, `secret_leak_count: 0`,
`peak_context_tokens: 794360`, `git_branch`, `cwd`.

## Why it still works, and the fragility that replaces the old risk

```bash
sqlite3 "$DB" "SELECT COUNT(*), SUM(deleted_at IS NOT NULL) FROM sessions;"
# 9526|0
sqlite3 "$DB" "SELECT COALESCE(deletion_cause,'(null)'), COUNT(*) FROM sessions GROUP BY 1;"
# (null)|9526
```

**Zero tombstones.** Upstream `kenn-io/agentsview#1470` describes the intended
behaviour: *"AgentsView keeps sessions in its SQLite archive after they disappear
from the source agent. It marks them with `deleted_at` and `deletion_cause =
source_missing`, then excludes them from search, token counts, and cost totals."*

Here that marking has **never fired**, which is why every standard CLI command
still returns those 283 sessions. That is luck, not design. `#1471` (OPEN) spells
out the consequence when it does fire: *"all standard CLI commands (session
search, session list, session get, session messages) filter out records where
`deleted_at IS NOT NULL`. This makes historical conversations invisible (from CLI
and Web) even though the data remains intact in the SQLite archive."*

**So the risk inverted.** It is no longer "we are losing sessions to a 30-day
wall". It is: *the day a reconciliation pass tombstones those 283 rows, they
vanish from every sanctioned query path while the bytes stay on disk* — and the
flag that would bring them back (`--include-deleted`, `preserve_missing_sources`)
**does not exist yet**; both #1470 and #1471 are OPEN as of 2026-09-12.

## What the old memory note got wrong, and why

`the-30-day-transcript-wall-has-already-fired.md` says the corpus went 182 → 174
and "loses a day per day", and Ray ruled HOLD on that basis. Re-measured today:

| | 2026-09-01 (recorded) | 2026-09-12 (measured) |
|---|---|---|
| KB transcripts on disk | 174 | **198** |
| oldest survivor on disk | 2026-08-02 | **2026-08-14** |

The **count went up** while the **oldest survivor moved forward 12 days**. Both
are true: new sessions are created faster than old ones age out. **The count was
the wrong instrument** — it cannot distinguish "nothing is being deleted" from
"deletions are being outpaced". The oldest-survivor date is the right one, and it
confirms the wall is live and still moving one day per day.

`cleanupPeriodDays` is **absent from all four settings files** (checked
`.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json`;
`~/.claude/settings.local.json` does not exist), so Claude Code's 30-day default
is still in force. Control arm: the same `jq` against
`.claude/settings.json` lists its real keys (`enabledPlugins, env,
extraKnownMarketplaces, hooks, outputStyle, teammateMode`), so the probe reads the
file correctly and "absent" means absent.

---

# 1. What changed upstream since 2026-09-01

**The decision this forces:** whether to stay on the newest *release* (which we
already are) or build from `main` to get the fix for our single biggest measured
limitation. Staying still is a real choice with a real cost.

## Upstream identity, established not assumed

`gh api repos/kenn-io/agentsview` → `full_name: kenn-io/agentsview`, MIT,
**5,879 stars**, `open_issues: 106`, `archived: false`, `pushed_at:
2026-09-12T17:32:27Z` (today). Control arm: `gh api
repos/kenn-io/definitely-not-a-real-repo-xyz` → HTTP 404, so the probe
discriminates.

**`has_discussions: false`** — the discussions index is **structurally empty** for
this repo. That is a control-armed zero, not an unsearched one. Three indexes
exist to sweep here, not four.

## Our pin is current with the newest RELEASE, and 114 PRs behind `main`

| probe | result |
|---|---|
| newest release | **v0.42.0**, published 2026-09-01T19:51:59Z |
| newest tag | v0.42.0 (`gh api .../tags` → v0.42.0, v0.41.1, v0.41.0, …) |
| what `mise ls-remote github:kenn-io/agentsview` resolves | 0.42.0 |
| our pin (`mise.toml:104`) | `"github:kenn-io/agentsview" = "0.42.0"` |
| installed | `agentsview v0.42.0 (commit ff8fb4e8, built 2026-09-01T19:37:18Z)` |
| **PRs merged since 2026-09-01** | **114** (control arm: 937 merged before that date) |
| prereleases / drafts | none |

**So a currency check here is correctly silent and simultaneously 11 days stale.**
There is no newer tag to find; every fix below lives only on `main`. The repo's
memory note recorded the pin as 0.41.1 — it has since moved to 0.42.0 and
`sources/agentsview.manifest` now exists (`mise.toml:91`, 2026-09-11).

## 🔴 The one that matters: reasoning effort is now persisted

Issue **#1670** *"Show reasoning effort alongside model in session breadcrumb"* —
**CLOSED 2026-09-10** by PR **#1677** (`eebb51d9a5440605478a3c108ba226cd878280ec`).

From the PR's own diff to `internal/db/db.go`:

```go
-const dataVersion = 105
+// (106: Claude and Codex assistant messages now persist reasoning effort.
+// Existing rows need re-parsing so the field is populated.)
+const dataVersion = 106
```

and to `internal/db/schema.sql`:

```sql
     model TEXT NOT NULL DEFAULT '',
+    reasoning_effort TEXT NOT NULL DEFAULT '',
```

`ReasoningEffort` now appears in **33 files** on `main` including
`internal/parser/codex.go` and `internal/parser/codex_cursor.go` — so the **Codex
parser extracts it**, not just the UI. Control arm on the code index:
`deletion_cause` → 20 hits, `incomplete_results: false` on both queries, so these
are real totals and not a truncated or rate-limited response.

**This closes the gap our own memory recorded as unclosable** —
`agentsview-adopted-and-what-it-cannot-answer.md` says *"`effort`/`sandbox`/
`ephemeral` → 0 of 483 DB columns. 'Did this lane run at xhigh' is NOT
checkable."* Re-derived today against our installed 0.42.0: **472 columns,
0 matching `effort|sandbox|ephemeral`**; control arm found `messages.model`,
`sessions.health_score`, `insights.model`. So the limit still holds *for us*, and
is fixed *upstream*.

**Two conditions that must travel with that fact:**

1. **It is unreleased.** No tag carries it.
2. **`dataVersion` 105 → 106 forces a full re-parse** — the comment says so
   outright. Against a **4.8 GB** archive, on a tool whose own open issues
   (#1717, #1723) say resync already wastes 12% and 22% of its time on directory
   rescans and serialization. Budget that before adopting.
3. **UNVERIFIED:** whether the persisted effort is the *applied* value or merely
   the *requested* one. Our prior finding distinguishes them; I did not confirm
   which the transcript carries. Do not claim lane-attribution is solved until
   someone reads a real row.

## Other fixes landed but unreleased — several are ours

| issue | closed | why it matters here |
|---|---|---|
| **#1621** | 2026-09-04 | `daemon stop` cannot recover from an already-dead daemon; stale lock **permanently blocks all writes**. This is `ray-manaloto/dotfiles#1018` ("detect and recover silent daemon failure") — fixed upstream, unreleased. |
| **#1688** | 2026-09-10 | idle `serve` daemon burns most of a machine's CPU re-reading every rollup row per 256-session batch. Reported on v0.42.0 **and still on `main` at 988c7406**. We autostart a daemon. Measured here: our `agentsview serve` at **4.1% CPU** over 6m elapsed — not obviously burning on this machine, but the reporter's box was 24-core Linux. |
| **#1645** | 2026-09-09 | `sync` writes in-place progress (`CR` + `ESC[K`) to **non-TTY stdout**, no quiet/summary mode. Directly affects `kb-session-search`, which runs sync in the foreground and parses output. |
| **#1644** | 2026-09-08 | Codex **guardian review threads indexed as root sessions** since Codex switched `thread_source` to `guardian_review` — inflates our codex session counts. |
| **#1611** | 2026-09-07 | first-class config for alternate Claude and Codex homes. |
| **#1617** | 2026-09-06 | `duckdb serve` renders no transcripts **in v0.42.0** — a known bug in the exact version we pin. Not biting us (we are on SQLite), but it is there. |
| **#1676** | 2026-09-10 | one NULL value fails **every** sync worker pass — the class of failure that looks like "no results". |

## Still OPEN and relevant

| issue | what it costs us |
|---|---|
| **#1470 / #1471** | the tombstone problem — see the HEADLINE section. **These are the two to watch.** |
| **#1375** | no official compaction/compression story for a large `sessions.db`. Ours is 4.8 GB. |
| **#1717 / #1723** | resync wastes 12% (per-session directory rescans) and 22% (one-file-at-a-time serialization) of a full pass. |
| **#1081 / #1082** | daemon startup races sync: a *successful* ingest can report **0 sessions synced**. A false zero that reads exactly like an answer. |
| **#1352** | Roadmap: hosted sync — updated today. Worth watching; we are local-first by policy. |
| **#692** | local-first multi-machine sync — the durable answer to "which machine holds the history". |

---

# 2. The retention clock, re-measured

See the HEADLINE section for the full measurement. The short form:

```bash
# the clock itself — the RIGHT instrument is the oldest survivor, not the count
KB=~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base
ls $KB/*.jsonl | wc -l                                   # 198 (was 174 on 2026-09-01)
stat -c '%y %n' $KB/*.jsonl | sort | head -1             # 2026-08-14 (was 2026-08-02)

# what the archive still holds that disk does not
DB="file:$HOME/.agentsview/sessions.db?mode=ro"
sqlite3 "$DB" "SELECT COUNT(*) FROM sessions
  WHERE project='knowledge_base' AND agent='claude' AND started_at<'2026-08-14';"   # 283
```

**Note on `stat`:** this repo pins `conda:coreutils`, so `stat` is **GNU**, not
BSD. `stat -f '%Sm %N'` (the macOS form) fails here with *"cannot read file system
information"* because GNU `-f` means filesystem status. Use `stat -c '%y %n'`.

**What it would take to archive them before they age out: nothing. It is already
done.** The only remaining action is to make the archive *durable*, which is the
next section.

---

# 3. What agentsview adds over our existing session tooling — honestly

**The decision this forces:** whether to extend `kb-session-select` and friends to
read the archive, or to accept that they permanently see a fraction of the record.

## Where the honest answer is "little"

- **Search.** `kb-session-search` already wraps it. A second search wrapper adds
  nothing. The Astra lane agreed: *"Search already belongs to `kb-session-search`;
  another search wrapper adds little."*
- **Durable lessons.** `kb-remember` / `kb-reflect` / `graphify-out/memory/` own
  this. agentsview has no durable-lesson concept and should not acquire one here.
- **Distillation.** `kb-distill` already proposes `skill → task → module` triples
  from repeated throwaway scripts. agentsview does not do this.

## Where it adds something real — four capabilities, each measured

### (a) Coverage: our own selector sees ~7% of the record

| what | count |
|---|---|
| `.jsonl` files `kb-session-select` reads (top-level, KB project) | **198** |
| KB **root** Claude sessions in the archive | **248** |
| KB **subagent** Claude sessions in the archive | **1,484** |
| KB **Codex** sessions in the archive (801 root + 284 child) | **1,085** |
| **total KB sessions in the archive** | **2,818** |

And this is not only an archive story — **1,263 `agent-*.jsonl` subagent
transcripts are sitting on disk right now** under
`<project>/<parent-uuid>/subagents/`, and `kb-session-select` does not read them
because it globs top-level `*.jsonl` only.

```bash
find ~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base \
  -name 'agent-*.jsonl' | wc -l   # 1263
```

Four repo tools read `~/.claude/projects/` directly and share this blindness:
`kb-session-select`, `kb-attribute-write`, `kb-session-review-archive`,
`brain-transcript-audit`. **This repo's lanes ARE subagents** — the work is in the
half we do not read.

### (b) Computed session diagnostics — nothing in `kb_setup` produces these

Per session, already populated in our 0.42.0 DB: `outcome`,
`outcome_confidence`, `health_score`, `health_grade`,
`tool_failure_signal_count`, `tool_retry_count`, `edit_churn_count`,
`consecutive_failure_max`, `compaction_count`, `mid_task_compaction_count`,
`secret_leak_count`, `peak_context_tokens`, `total_output_tokens`, `is_automated`,
`git_branch`, `cwd`, `parent_session_id`, `relationship_type`.

This is the triage layer `kb-session-reflect` and `kb-distill` currently leave to
interpretation. **UNVERIFIED** (and the lane flagged it too): whether
`health_score` actually correlates with sessions worth mining. Do not build a
trigger on it until someone checks.

### (c) Semantic and hybrid search — our wrapper exposes NEITHER

`agentsview session search --help` offers `--semantic` (vector over
user/assistant messages), `--hybrid` (semantic + FTS via reciprocal rank fusion),
`--scope top|all|subordinate`, `--context N`, `--exclude-system`,
`--date-from`/`--date-to`, `--machine`, `--in messages,tool_input,tool_result`.

`kb-session-search` supports **none** of them and **refuses unknown flags by
design** (`python/src/kb_setup/agentsview.py:145-163`) — correctly, because a
curated argv silently drops anything it does not recognise:

> *"`kb-session-search -- foo --fts` would accept `--fts`, never send it, and
> return ordinary results that read as an FTS search."*

That refusal is right. The consequence is that **concept-level search over our own
history is unavailable through any sanctioned path.**

One accident worth knowing: because our wrapper never sends `--fts`, it always
runs **plain** search — which upstream **#1511** (CLOSED 2026-09-03) shows is the
*correct* mode for identifier hunts. That issue measured `--fts` finding **0** hits
in the session that actually created a tracker id, versus **19** for plain search
with `--in tool_input`. We are on the right mode by omission, not by design.

### (d) Cross-agent reach

Archive by agent: `claude 4,493 · codex 4,053 · opencode 512 · antigravity 222 ·
antigravity-cli 139 · gemini 50 · cowork 49 · amp 10`. Every repo tool except
`kb-session-search` reads Claude only.

## The limits that still hold, re-derived today

- `effort|sandbox|ephemeral` → **0 of 472 columns** in our 0.42.0 DB. Control arm
  found `messages.model` and `sessions.health_score`, so the probe discriminates.
  Fixed on `main`, unreleased (§1).
- Parenting stays within-family, so a `codex exec` dispatched by a Claude lane is
  still not attributable to its round. *(Inherited from the 2026-09-01 round; NOT
  re-derived today — treat as unverified.)*
- `sync` is not concurrency-safe. *(Inherited, not re-derived.)*

---

# 4. The proposed self-optimisation loop

**The decision this forces:** one bounded action now (make the archive durable),
then one new task. Everything else is an extension of what exists.

## 🔴 Step 0, before anything else: make the archive durable

This is the Astra lane's deciding risk, and I agree with it:

> *"The deciding risk is losing access to the sole surviving evidence during sync
> or migration. The cheapest closure is a SQLite-consistent backup **before another
> sync or upgrade**, followed by a readback proving archive-only records —
> including tool payloads — are accessible independently of CLI deletion filters."*

Why it is urgent in a way the old retention worry was not: those 283 sessions are
**the only copy**. Three things could take them away, and none is hypothetical —
a reconciliation pass that finally sets `deletion_cause='source_missing'` (#1470's
documented behaviour, which has simply not fired here yet); a `dataVersion` 105→106
re-parse on upgrade; or the stale-lock / failed-sync classes in #1621, #1676,
#1081.

**I did not run this** — it writes ~4.8 GB and this lane advises only. Recommended
command, for whoever decides:

```bash
# SQLite-consistent, safe against the live daemon's writes
sqlite3 "file:$HOME/.agentsview/sessions.db?mode=ro" \
  ".backup '/path/to/archive/agentsview-sessions-2026-09-12.db'"

# then the READBACK arm — prove an archive-only row survived
sqlite3 "file:/path/to/archive/agentsview-sessions-2026-09-12.db?mode=ro" \
  "SELECT COUNT(*) FROM sessions
   WHERE project='knowledge_base' AND agent='claude' AND started_at<'2026-08-14';"
# must return 283
```

**Keep 0.42.0 for this round.** The reasoning-effort field is worth having, but not
at the price of re-parsing the only copy of 283 sessions. Upgrade against a
*disposable copy* first. Whether a 106 re-parse preserves source-deleted rows is
**UNVERIFIED** — nobody has tested it, and the upstream comment (*"Existing rows
need re-parsing so the field is populated"*) says nothing about what happens to
rows whose source file is gone. That is the single most important unknown in this
report.

Also worth doing at the same time, and nearly free: set `cleanupPeriodDays` in
`.claude/settings.json` to stop the disk-side bleed. It is absent today.
`settings-reference.md:628` gives it scope "Any file", but the sibling note on
`permissions.defaultMode` warns that project scope silently drops some values —
so **verify it took effect**, do not assume.

## The loop

| | |
|---|---|
| **Trigger** | One manual backfill pass over ≤10 archive-only sessions now. Thereafter: when `kb-session-reflect` reports a recurring failure or a repeated manual script. **Not** a scheduled job — this repo has no CI and a cron that mines nobody reads is a fourth store in disguise. |
| **Mine** | Three shapes only: (1) a repeated failure followed by a demonstrated recovery; (2) manual work a task already owns (`kb-distill`'s input, but over history rather than this session); (3) a correction or decision that never reached durable memory. Select candidates with the diagnostics in §3(b), then read the actual exchange — a score is a pointer, never a finding. |
| **Into** | **No new store.** `kb-remember` for recovered decisions (with session id + message ordinal as evidence); `kb-reflect` for validated reusable lessons; the graph only when a finding warrants a real source. |
| **Close the loop** | Exercise one proposal against a concrete recurrence and record whether it prevented the original failure. *"A better health score alone does not establish improvement"* — the lane's line, and it is the right stop rule. |

## Tasks

- **NEW — `kb-session-mine`** (`kb_setup.session_mine`): bounded selection over the
  archive, a snapshot/readback helper, and output shaped for `kb-remember`.
  Refuses rather than returning a partial list, matching the house pattern in
  `kb-session-select` and `kb-recall-work`.
- **EXTEND — `kb-session-select`**: teach it the archive as an explicitly selected
  input, reporting coverage and refusing incomplete retrieval. Its current
  top-level-glob blindness to **1,263 on-disk subagent transcripts** is worth
  fixing on its own, independent of everything else here.
- **EXTEND — `kb-session-search`**: expose `--semantic` / `--hybrid` /
  `--in` / `--context`, which the wrapper deliberately refuses today. Concept
  search over our own history currently has no sanctioned path.
- **REUSE — `kb-recall`** for dedup against existing memory before writing a new
  one; **`kb-distill`** for the repeated-script half.
- **DEFER** the other three direct filesystem readers (`kb-attribute-write`,
  `kb-session-review-archive`, `brain-transcript-audit`).

Scope check: step 0 plus `kb-session-mine` plus the `kb-session-select` fix is one
round. The search-flag extension is a separate, smaller one.

---

# 5. COULD NOT ESTABLISH

- **Whether the persisted `reasoning_effort` is the APPLIED or the REQUESTED
  value.** PR #1677 adds the column and `internal/parser/codex.go` references it;
  I did not read a populated row (we cannot — it is unreleased). Our standing
  finding distinguishes the two. **Do not claim lane attribution is solved.**
- **Whether a `dataVersion` 105→106 re-parse preserves rows whose source file no
  longer exists.** The decisive unknown. Test on a copy.
- **Whether `health_score` correlates with sessions worth mining.** Unvalidated;
  do not build a trigger on it yet.
- **Why the 283 rows were never tombstoned.** I established *that* they are not
  (`SUM(deleted_at IS NOT NULL)` → 0) and what the documented behaviour is
  (#1470), but not why reconciliation has not fired. Could be a version
  behaviour, a config, or simply that it runs on a path we do not trigger.
- **Whether #1688's CPU burn affects this machine.** Our daemon measured 4.1% CPU
  over 6m — not obviously burning, but that is one sample on a quiet machine, not
  a refutation of a bug reported on 24 cores.
- **Cross-family parenting and sync concurrency** — carried from the 2026-09-01
  round and **not re-derived today**. Labelled inherited above.
- **agentsview's project attribution.** One child row labelled
  `project='knowledge_base'` has a `file_path` under the *dotfiles* project
  directory. That may be correct (attribution by `cwd` rather than by directory
  name, which would be better than what we do) or a mis-attribution. Observed, not
  explained.
- **The `--last30days` / firecrawl / exa / context7 surfaces were not used.** The
  GitHub API answered every question with control arms attached, and reaching for
  a second index after the first gave a controlled answer would have added cost
  without adding evidence. Stated so the gap is visible rather than silent.

---

# GitHub repos touched

- [kenn-io/agentsview](https://github.com/kenn-io/agentsview) — the upstream under
  research: issues #1470, #1471, #1511, #1621, #1644, #1645, #1670, #1676, #1688,
  #1717, #1723, #1375, #1081, #1082, #1352, #692, #1611, #1617; PR #1677
  (`eebb51d9a5440605478a3c108ba226cd878280ec`); the code index for
  `reasoning_effort` / `ReasoningEffort` / `deletion_cause`.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — issues
  #1014–#1018, the prior art for this integration; #1018 is closed upstream by
  agentsview #1621 but the fix is unreleased.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) —
  this repo: `mise.toml:104` (the pin), `python/src/kb_setup/agentsview.py`,
  the `kb-session-*` task family.
- [openai/codex](https://github.com/openai/codex) — the lane transport
  (`codex exec`), via `mise run kb-codex`. No source read this round.

---

# 🔴 AMENDMENT (same day, after `kb-recall-work`) — two findings above were NOT new

I ran `mise run kb-recall` and read the two named memory files before researching,
but I did **not** run `mise run kb-recall-work` until the lead made it a standing
precondition. Running it turned up prior art that **retracts the novelty of §1**.
Recording this as a correction rather than editing §1 silently, because someone may
already have acted on it.

`mise run kb-recall-work -- "agentsview"` → 75 matches (tracked_files 15/3427,
artifact_pages 6/144, issues 6/969, plans 42/218, memory 6/426; branches 0/503,
worktrees 0/2). Report: `.agent/kb/recall/agentsview.md`.

## What was already on disk

**1. `docs/research/reports/2026-09-11-astra-agentsview-standalone.md` (516 lines)** —
a `kb-codex-astra-advisor` report from YESTERDAY. Its §R2-A already establishes
the entire §1 headline: #1670 → PR #1677, merged 2026-09-10, in no release,
*"effort capture for Claude Code AND Codex"*. **It is better-sourced than mine**:
it quotes the upstream issue body directly —

> *"Existing archives perform a **full session resync on upgrade** to populate
> effort from source transcripts. This can take time for large archives."*

— where I inferred the same thing from the `dataVersion` 105→106 comment in the
diff. Its four-index sweep also ran first, including the same structurally-zero
discussions result.

**2. `mise.toml:100-103` — the warning is already IN THE PIN COMMENT:**

> *"⚠️ 0.42.0 does NOT carry the feature we want. `effort` capture for Claude Code
> AND Codex sessions is upstream PR #1677, merged 2026-09-10, in no release yet.
> When the release carrying it lands — do not assume it is 0.43.0 — the bump
> triggers a documented FULL SESSION RESYNC against a ~5 GB archive."*

**So §1's "🔴 The one that matters" was already known, already written down, and
already attached to the pin it governs.** Treat §1 as a re-derivation, not a
finding. Its only additions are the `schema.sql`/`db.go` diff text and the
re-derived 472-column count.

## The finding I should have led with, from yesterday's F2

**Codex's own rollouts already record model, effort AND sandbox per turn.
agentsview is not needed for lane attribution at all.**

`~/.codex/sessions/**/*.jsonl`, record `type: "turn_context"`, carries `model`,
`effort`, `sandbox_policy.type`, `approval_policy`, `permission_profile`. Yesterday's
lane measured a sample reading `model: gpt-6-astra, effort: xhigh,
sandbox_policy: {'type': 'read-only'}`.

This **changes §4's recommendation for the better**. I advised "keep 0.42.0
because the re-parse risk outweighs the effort field". The stronger reason is:
**we do not need the agentsview upgrade for effort attribution at all** — a reader
over the codex rollouts answers it *retroactively, for every past run*, with no
resync and no risk to the 283 archive-only sessions. That reader does not exist yet
and is a better candidate for a new task than anything in my §4.

Three conditions from yesterday's lane that must travel with it:

- **F3 — coverage is 49.7%**: 149 of the 300 newest rollouts carry a
  `turn_context` record at all; 151 do not. It is version-gated.
- **F5 — `turn_context.model` is the REQUESTED slug, not the served model.** Proven
  by control arm: the sweep contains 2× `model: 'definitely-not-a-real-model-xyz'`,
  a slug that cannot exist, recorded verbatim.
- **F4 — the data already shows policy breaches**: 7× `('gpt-5.6-sol','xhigh',
  'danger-full-access')` and 6× at `medium`, against `do-not.md` #13. This is
  memory-index item **#767**, still open.

**This also substantially answers my §5 "decisive unknown."** Since upstream
populates effort *from source transcripts*, and the source transcripts for those
283 sessions are **gone**, a re-parse cannot populate effort for them — and what it
does to rows whose source is missing is now a sharper question, not a softer one.
The §4 advice (test on a disposable copy first) holds with more force.

## One correction to §3(b), found by re-deriving yesterday's F6

Yesterday's F6 records `tool_result_events` as having **0 rows for `agent='claude'`**.
Re-derived today: `codex 126,174 · opencode 520 · claude 0`. Confirmed.

That does **not** invalidate §3(b), but it narrows it. The diagnostics ARE populated
for Claude — `health_score` on **4,244 of 4,502** Claude sessions,
`tool_failure_signal_count > 0` on **501** — so they are derived from something
other than the tool-status table. What agentsview cannot give you for Claude is
**per-tool-call outcome**, which is a different thing from the session-level scores
§3(b) claims. Anyone building a trigger on tool failures specifically should read
yesterday's F6 and F7 first.

## What survives as genuinely new in this report

- The **283 archive-only sessions**, control-armed, and the end-to-end proof that
  `agentsview session get` still returns one whose file is gone. Yesterday's report
  does not mention retention, tombstones, `deleted_at` or `source_missing` at all
  (`grep -n -i 'deleted_at|source_missing|tombstone|retention|30-day|cleanupPeriod'`
  → no hits in its findings).
- The **tombstone fragility** (#1470/#1471) and the backup-first recommendation.
- The **re-measured retention clock** and the finding that the *count* is the wrong
  instrument.
- **1,263 on-disk subagent transcripts** that `kb-session-select` does not read.
- The **`--semantic`/`--hybrid` gap** in `kb-session-search`.

## One stale claim in yesterday's report, now fixed

Its §R2-B says *"There is **NO** `sources/agentsview.manifest`"*. It exists today —
`sources/agentsview.manifest`, tracked, written 2026-09-11 22:05, i.e. ~7 hours
after that report. Not an error; the world moved. Noting it so the next reader of
that file does not re-open a closed item.

## The other two recall runs

- `kb-recall-work -- "session review"` → **1,933 matches** (tracked 1030/3427,
  issues 295/969, plans 203/218, memory 266/426). Too broad to discriminate — the
  failure mode opposite to the lead's warning: a topic can be too GENERIC as well
  as too specific, and 203 of 218 plans matching is not a signal.
  Report: `.agent/kb/recall/session-review.md`.
- `kb-recall-work -- "transcript retention"` → **82 matches** (tracked 33/3427,
  issues 5/969, plans 14/218, memory 25/426, artifacts **0**/144).
  Report: `.agent/kb/recall/transcript-retention.md`.
  **Nothing in it pre-empts the archive finding.** Its tracked hits are about
  telemetry retention (#400, #461, #345, #374) and context loss across
  handoff/resume, not about agentsview's archive outliving Claude Code's deletion.
  Adjacent prior art worth a reader's time, not a retraction:
  `dotfiles:docs/research/kb/reports/agents/2026-09-01-plan-review-context-loss.md`.

**Method note for the next lane:** `kb-recall` (BM25 over work-memory) and
`kb-recall-work` (seven probes over tracked files, artifacts, branches, issues,
plans, memory) are **not substitutes**. I ran the first and read the two memory
files it named, which is why I still walked into §1 — the thing I missed was a
**tracked research report** and a **comment in `mise.toml`**, and only
`recall-work` reaches those. Run both.
