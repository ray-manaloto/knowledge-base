> **PROMOTED VERBATIM.** The completeness critic for the 2026-08-21 session review.
> Read this BEFORE the synthesis it audits.

# COMPLETENESS CRITIC — what the 2026-08-21 session-review synthesis is MISSING

Scope: `SYNTHESIS.md` (840 lines) + all 43 lane/verification notes in this directory, audited
against Ray's 94 messages, the SIXTH ADDENDUM, and the workflow's own machine record.

**Verdict: the synthesis is NOT complete.** 14 actionable gaps below. Three of them
(GAP-1, GAP-2, GAP-9) change how the document should be read, not just what it should add.

---

## 0. The probe that unlocked most of this — the workflow's own journal

The lanes' machine results were never consulted by the synthesis in their raw form. They exist:

```
/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/
  11db65d3-7823-4297-96b2-65e72f906316/subagents/workflows/wf_4ef74015-0a1/journal.jsonl
```

87 records: 7 lane `result`s carrying `claims[]`, 35 verify `result`s carrying `{id, verdict}`,
1 sibling-agent result, 1 `started` with no result (that is me, `ae3162d824cdfcdbb`).
Control arm for "the journal discriminates": `grep -l coverage_note *.jsonl` → 45 of 45 agent
files (the string is in every brief), while parsing the journal's `result` records yields exactly
7 objects with a `claims` key and 35 with a `verdict` key — two disjoint, non-trivial sets.

---

## GAP-1 (P0) — the synthesis's own headline arithmetic is wrong, in the direction that flatters it

`SYNTHESIS.md:3-4` says "**155 collected claims, 35 adversarially verified … 103 reported unreached**",
then `:753-756` flags that 155 − 35 = 120 ≠ 103 and says *"those two figures disagree by 17 and I did
not reconcile them."*

Reconciled here, from `journal.jsonl`:

| lane | claims | verified | unverified |
|---|---|---|---|
| ray-requests | 52 | 5 (RR-01..05) | **47** |
| addenda | 32 | 5 (A5-01,03,04,05,06) | **27** |
| deferred-work | 22 | 5 (DW-01..05) | **17** |
| skipped-checks | 15 | 5 (SC-01..05) | **10** |
| extraction-readiness | 13 | 5 (ER-01..05) | **8** |
| unpinned-tools | 8 | 5 (UT-01..05) | 3 |
| automation-candidates | 8 | 5 (AC-1..5) | 3 |
| **total** | **150** | **35** | **115** |

So: **150 claims, not 155. 115 unverified, not 103.** Verdict split 26 CONFIRMED / 9 REFUTED
reproduces exactly. The cap was a flat **top-5 per lane**, not a budget — which means the 115
unverified are not "what we ran out of time for", they are "claims 6..52 of every lane, by
construction". `probes-need-a-control-arm.md` rule 6: an inherited number with no control arm.
**Action:** replace `SYNTHESIS.md:3-5` and `§5c`'s first paragraph with 150/35/115 and state the
cap as flat-top-5.

## GAP-2 (P0) — §5c asserts "everything in §1 rests on a verified claim". Three gate items do not.

`SYNTHESIS.md:757-759`. Mapping each gate item to its lane claim id:

| gate | rests on | verified? |
|---|---|---|
| G1 | ER-01 | ✅ CONFIRMED |
| G2 | ER-03 | ✅ CONFIRMED |
| G3 (55.1% dedupe, ~$36) | **no lane claim at all** — the synthesist's own re-derivation from `source-inventory.json` | ❌ never adversarially passed |
| G4 | ER-02 | ✅ (observed live) |
| G5 | ER-04 + RR-04 | ✅ |
| G6 | ER-05 ✅ … but its **cache-read** half is ER-06 and its **cap-arithmetic** half is ER-07 | ❌ both unverified |
| G7 | the RED half is DW-01 + SC-04 ✅ … but the **ORDERING CORRECTION** is ER-10 | ❌ unverified, and ER-10's own `status` field is literally `"unknown"` |
| G8 | ER-11 / DW-19 | ❌ both unverified |
| G9 | SC-02 | ✅ |
| G10 | SC-05 | ✅ |

**The most load-bearing unverified claim in the document is ER-10.** SYNTHESIS.md:189 calls it
*"Ordering correction, and it is load-bearing"*; the whole "Recommended sequence" (`:829-838`) and
the "legs 1 and 2 can proceed, leg 3 cannot" framing (`:31-33`) rest on it — and the lane that
raised it recorded `status: "unknown"` and `blocks_extraction: false`. If ER-10 is wrong, the round
cannot start at all. **Action:** verify ER-10 before executing the sequence — the probe is cheap
(`grep -rn "graph.json" python/src/kb_setup/graphify_semantic_corpus_run.py graphify_semantic_corpus.py`
with a control arm on `graphify_ops.py`, plus one dry `verify` with `graphify-out/graph.json` moved
aside), and it is a REFUSAL-cheap arm against a $65 sequencing error.

## GAP-3 (P0) — the four claims flagged `blocks_extraction: true` that were never verified

18 of 150 claims carry `blocks_extraction: true`. 14 were verified. **These four were not:**

- **A5-11** — "the FIFTH ADDENDUM names the deep extraction as the thing that must complete SOON — still red" (`existing_issue: 397`).
- **RR-34** — "add both Anthropic python SDKs as graphify sources + evaluate `claude-agent-sdk-python` as a session-review mechanism". Sources DONE; **the question is answered only inside `.agent/kb/reports/agents/design-sdk-premise.md`, which is gitignored**. See GAP-8.
- **DW-14** — "25 committed extraction chunks, still ZERO merged" (`existing_issue: 301`).
- **DW-19** — "`build = skip` on five sources is a COVERAGE DEBT, not a fix" (`existing_issue: 417`).

DW-14 and DW-19 are the two that matter for the gate: DW-14 is the graphify-circle scoreboard the
whole round exists to move, and DW-19 is G8 with the honest framing. Neither survived an
adversarial pass. **Action:** verify DW-14 (`ls sources/extractions/ | wc -l` vs a merge-count
probe of `graph.json`) and DW-19 before the round claims progress.

## GAP-4 (P1) — the SIXTH ADDENDUM: 16 claims collected, **ZERO verified**, and 4 items have no claim in the synthesis at all

Control arm: the verified-id set contains `A5-01, A5-03, A5-04, A5-05, A5-06` — so the `A`-prefix
lane *was* sampled; it is specifically **A6-01..A6-16 that are 0-for-16**. Ray's SIXTH ADDENDUM is
the block this whole review was pointed at, and none of its findings was adversarially tested.

Bullet-by-bullet, against `docs/direction/2026-08-19-ray-directives.md:305-339`:

| SIXTH ADDENDUM bullet (verbatim) | claim | in SYNTHESIS? |
|---|---|---|
| "add a claude code rule and/or hook that whenever these files are loaded/read the following gets added to context: every bump goes through mise use / uv add, never an editor" | A6-01 | **PARTIAL — the mechanism is missing.** SYNTHESIS names `#381` only as "`mise use`/`uv add` enforcement" (`:706`). The ask is a **load/read-triggered context injector**; `grep -c "loaded/read" SYNTHESIS.md` → 0. The addenda lane measured it NOT done with a control arm (`grep -rln "mise use" .claude/rules/ CLAUDE.md` → 0; control `zero-bash` → 3 files) and that measurement never reached the synthesis. |
| "we need to be more dilligent about not hitting over 20% of context" | A6-02 | ✅ §6 item 4, #354/#218 |
| "are we using graphify pr features?" | A6-03 | ✅ F14 |
| "session-review should have a check for **linters/static analysis checks being skipped**" | A6-04 | **❌ ABSENT.** `grep -ic "linter" SYNTHESIS.md` → 0; `"static analysis"` → 0. Controls in the same file: `"gitleaks"`/`"hk.pkl"` hit. The `skipped-checks` LANE exists, but no claim in the synthesis says session-review lacks a *linter-skip detector*, which is what Ray asked for. **Unfiled** (`existing_issue` empty on A6-04). |
| "aggregation/triage of open issues/tasks/github issues should be a step" | A6-05 | ✅ by issue cite (#415, `:711`) |
| "re-applying to wayfinder/grilling maps" | A6-06 | ✅ §6 item 3 |
| "should find cases of using tools/clis/…/plugins/etc that are not tracked in mise.toml or pyproject.toml" | A6-07 | ✅ strongly — F10/F11/F12 |
| "get rid of currency.toml … just rely on mise.toml/pyproject.toml" | A6-08 | ✅ F15 + #393 |
| "find steps agents are doing that can be automated … skill -> mise task -> python library module/function" | A6-09 | **PARTIAL.** §2b does the work, but A6-09's decisive datum — *the distiller shipped (#219 CLOSED) and has run ZERO times* — is absent: `grep -c "kb-distill" SYNTHESIS.md` → 0, `grep -c "#219"` → 0 (control: `#380` → 4). |
| "just have parameters/arguments to enable/disable certain features to make it re-usable" | A6-10 | **❌ ABSENT.** `grep -ic parameteriz SYNTHESIS.md` → 0. The landed half (`session-review.js:503-532 cfg.lanes`) is nowhere stated, so a reader cannot tell this item is half-done. |
| "**record context/token usage when session-review workflow runs**" + its 5 sub-asks (record on session start after all context loaded · before/after the workflow · suggestions w pros/cons · **list all files read that were added to context** · derived from telemetry files) | A6-11 | **❌ ABSENT, all five.** `grep -ic "token usage" / "files read" / "session start" SYNTHESIS.md` → 0/0/0 (control: `"telemetry"` → 0 too; `"context"` → many). A6-11 records `existing_issue: ""` — **unfiled**. This is the item that would tell Ray whether this very review was worth its cost. |
| "add metrics to everything … use profiling tools … get down to cpu instructions and counts vs wall clock" | A6-12 | **❌ ABSENT.** `grep -ic profil SYNTHESIS.md` → 1, and that hit is `profile.effort` at `:129` — a false positive. `grep -ic "cpu"` → 0. **Unfiled.** |
| antigravity-cli: "should be associated with currency dependency" + "**follow the skill/protocol of syncing graphify source, reviewing release-notes/features/changes**" + "**especially any cli arguments we might be missing**" | A6-13 | **PARTIAL.** SYNTHESIS mentions `antigravity-cli` twice (`:555`, `:577`), both as a currency/pin observation. The **source-sync + release-notes protocol** and the **missing-CLI-args** halves are absent — which is doubly odd because §2b's own finding is that the agy lane was hand-driven 24 times with three flag spellings probed before one worked. Those two facts are the same finding and the synthesis does not join them. |
| `disallow:` → "must pin to a git commit sha" | A6-14 | ✅ G7 / #397 criterion 1 |
| mise 2026.8.9 resync + `min_version.hard` | A6-15 | ✅ F6 (3-file change) |
| "start semantic versioning after every successful pr" | A6-16 | ✅ F8 |

**Action:** file A6-04, A6-11, A6-12 (all `existing_issue: ""`), add A6-01's mechanism half and
A6-13's protocol half to the relevant issues, and state A6-10 as half-done rather than omitting it.

## GAP-5 (P1) — Ray messages with no representation anywhere in the synthesis

I read **all 94** messages in `scratchpad/humans/` (`grep -c '^### message ' *.md` → 94 across 14
files; control: `6320c6bb-2026-08-19.md` → 0, a header-only stub, so the real denominator of
sessions-with-Ray-input is **13**, not 14 — `SYNTHESIS.md:5` says 14 sessions without that caveat).

**Spot-checked for representation (22 messages, 10 different sessions):**

| msg | verdict |
|---|---|
| `fb633adf` m1 (graphify v0.9.46 resync) | ✅ currency/G2 |
| `fb633adf` m2 ("send me the interactive forms for the questions") | ✅ standing AskUserQuestion call |
| `fb633adf` m3 (add both python SDKs; **use claude-agent-sdk-python to review previous sessions?**) | **❌ half missing** — `grep -c "claude-agent-sdk" SYNTHESIS.md` → 0. See GAP-8 |
| `6b974f05` m1 (claude-code 2.1.234 release review) | ✅ G5/UT-05 claude-version thread |
| `52f5798a` m2 (kb-arms sweep → re-plan LAST → re-record authority) | ✅ G1/G2 "ONE commit, ONE re-plan" |
| `f1d1c0cf` m1 (PRs #337/#338/#339 bot reviews) | ✅ #380/#407 |
| `f1d1c0cf` m2+m3 **and m4's screenshot** ("not fable-5 for **each** agent … it hit session limit too quickly and is burning too many tokens") | **❌ ABSENT as an item.** `grep -ic "session limit" SYNTHESIS.md` → 0; the 3 `fable` hits are all about the fable-orchestrator review lane. Believed landed (#340-#344, the 78→23 agent tiering) but the synthesis neither says so nor verifies it — and **this round re-ran a 45-agent fan-out** |
| `f1d1c0cf` m9 (workflow stored in git + **nanosecond-precision timestamped report + the workflow's git sha** + landing-page pointer so there is no one massive ledger) | **❌ ABSENT.** `grep -ic nanosecond` → 0, `"landing page"` → 0. `docs/session-review/runs/` holds only 2 dirs, both 2026-08-18 (ray-requests-notes.md) — so the ask is both unbuilt AND the existing partial artifact is 3 days stale |
| `f1d1c0cf` m29+m30 (**screenshot**, "are we stuck, i see this failure") | **❌ never read** — see GAP-9 |
| `f1d1c0cf` m31 ("why is .codex/config.toml modified?") | ✅ #399/#374/#345 |
| `f1d1c0cf` m32 / `6697269c` m20 ("what is the prompt to run after /clear?") | ✅ #401 / §6 |
| `6697269c` m1 (session-review re-usable by datetime range/current/list + handoff flag; fable-5 advisor team; **DAG / mermaid visual**) | ✅ `kb-session-select` landed; visual half = #370 |
| `6697269c` m2-m9 (**eight consecutive "Try again" after a 529**) | ✅ #369 |
| `6697269c` m19 ("why did this happen? upstream tracking wasn't set because origin/<branch> didn't exist") | **❌ ABSENT.** `grep -ic "upstream tracking"` → 0, `"branch -u"` → 0. Small, but it is an unanswered *"why did this happen"* — the class Ray keeps saying session-review should catch |
| `6697269c` m19 (track which sessions the workflow has run on) | ✅ #352 |
| `6697269c` m19 (schemas/*.json enum dedup) | ✅ §6 closing note (#353 contradiction) |
| `6697269c` m19 (universal logger, stdout+stderr durable) | ✅ #350 |
| `773421d1` m2 (**adhd + ponytail** installed at project scope and made currency deps) | **⚠️ thin.** `adhd` appears once in SYNTHESIS (`:541`) — as a *control arm for a different probe*. `ponytail` appears **0** times in SYNTHESIS and once in all 44 notes. #384 is cited generically; neither plugin is named |
| `773421d1` m2 (`mise outdated -b -J` / `uv tree --outdated … --format json` → zero outdated) | ✅ #383 |
| `773421d1` m3 (PR #375 bot review; **graphify bot comments are critical**) | ✅ §2b BUILD IT / #380 |
| `773421d1` m4 ("**explore creating the eventual cli we are building — AST tree-sitter / lsp / graphql /** other features to make it easy for another ai/llm/ide to navigate our code") | **❌ ABSENT.** `grep -ic tree-sitter SYNTHESIS.md` → 0, `graphql` → 0, `lsp` → 0. Control: `pinact`/`requires-python` (same addenda lane) DO appear as F9/F7, so the omission is selective, not a lane failure |
| `773421d1` m4 ("update workflow to a **workflow engine using a state machine library** — dbos with sqlite or postgres / microsoft/pg_durable") | **❌ ABSENT.** `dbos` → 0, `pg_durable` → 0, `"state machine"` → 0. And `addenda-lane-notes.md:43-44` records the aggravating fact: **`docs/direction/2026-08-17-ray-directives.md:85` asks for it TOO** — this is its *second* statement and it is still unfiled |
| `6d692fdd` m5 (`update:claude` should update marketplace+plugins for all projects, parallelised via mise or python) | **❌ ABSENT.** `"update:claude"` → 0, `"update-all"` → 0 (control: `ctx7` → 7). Likely closed by #418, but the synthesis neither says so nor cites it |
| `6d692fdd` m7 ("remove that broken context7 install") | ✅ F15 bullet (status UNKNOWN, correctly flagged) |
| `61da2c9e` m2 (skip-and-file policy) | ✅ G8/#417 |
| `61da2c9e` m5 ("**i added comments to the artifact on what to research**") | **❌ never read** — see GAP-10 |
| `a03ce3ad` m3 ("was the deep extraction … done on graphify 0.9.47?") | ✅ implicitly (G3: the chunks dir does not exist). Answer is **NO** and the synthesis never states it plainly |
| `11db65d3` m1 ("C4") / m4 ("Wait for bots") | ✅ / ✅ class-level (#380) |

**Six Ray asks are represented nowhere:** the eventual CLI (tree-sitter/LSP/GraphQL), the
state-machine workflow engine (asked **twice**, 08-17 and 08-19), the nanosecond-stamped versioned
workflow report, the per-agent-model/session-limit cost item, `update:claude` parallelisation, and
the upstream-tracking "why did this happen".

## GAP-6 (P1) — which lanes said "not complete", and what they did not reach

From `journal.jsonl` (verbatim `coverage_note` fields). **5 of 7 said "NOT complete"; the other 2
said COMPLETE with substantive exclusions — so zero lanes were unqualified.**

| lane | coverage_note opens | did not reach (condensed, verbatim-sourced) |
|---|---|---|
| **extraction-readiness** | "NOT complete — three gaps" | did **not** run `kb-build` (ER-10 `status: unknown`); did **not** run the corpus `run` (ER-01 is inference, not observation); read `graphify_semantic_slice.py` only around preflight/effort/constants — **`:1356-1410` receipt-verification unaudited**; **never opened `graphify_semantic_corpus_authority.py` or `_prototype.py`**; never opened **#409 or #414** |
| **skipped-checks** | "NOT complete" | never ran `mise run lint` (SC-10 rests on a committed `lint-timing.json`); **SC-02's planted-secret arm deliberately not run in this repo**; SC-03's other direction never armed; counts exclude subagent + Workflow transcripts (**floors**); never examined `eval`/`brain-audit` internals nor `kb_setup.evals`' BLE001 catch-and-record — *"a plausible 'fewer cases reads as green' surface I ran out of budget to test"*; never cross-checked the window against `kb-session-select` |
| **deferred-work** | "NOT complete" | extractor reads assistant **text blocks only** — **1,592 keyword lines vs 27 extracted paragraphs, remainder untriaged**; `feat-kb-check-guard` fate left `unknown`; docs-drift items never re-probed upstream; `kb-build` not re-run; P0 set + #403-#409 confirmed OPEN by listing only |
| **unpinned-tools** | "NOT complete" | command-word parser is a heuristic (blind to heredocs, `$(…)`, `sh -c`, python `subprocess`); **subagent transcripts not audited**; **dotfiles sibling repo not checked** (UT-01 blast radius unmeasured); never probed whether `extraKnownMarketplaces` accepts a ref/SHA at all; node major for `.claude/workflows/*.js` unmeasured |
| **automation-candidates** | "NOT complete" | **647 Edit / 146 Write / 141 Read / 22 Agent calls never mined**; **10 Workflow + 22 Agent fan-outs never audited** — *"read my `blocks_extraction: false` on every claim as 'I found no blocker', not 'I verified there is none'"*; **never read Ray's 94 messages**; 189 further adjacent-task pairs unmined; no token-spend measurement at all, i.e. Ray's own ranking criterion was never applied; no `gh issue list` dedupe |
| **addenda** | "COMPLETE for the assigned scope with **two** stated exclusions" (actually three) | `docs/direction/2026-08-02` and `2026-08-17` **not read in full**; the 08-18 file's VERBATIM block + FIRST/SECOND/THIRD addenda only spot-checked; **never read Ray's 94 messages**, so every restatement count came from the brief; **absence probes were TITLE-ONLY** — and this lane's own A5-04 was REFUTED for exactly that reason (#391 found only by full-text) |
| **ray-requests** | "COMPLETE on the primary task" | two Ray messages **truncated** (`773421d1:104`, `:181`) and their tails never recovered from raw JSONL; RR-46 (ctx7) `unknown`; **#411/#414/#417/#389 judged by TITLE, not body** — and RR-04/RR-05's `blocks_extraction` calls rest on that; 4 directive files not read in full; issue-status from `--state open` titles, never checking whether an open issue is already implemented |

**The synthesis carries most of these into §5c but drops five:** the `graphify_semantic_slice.py:1356-1410`
audit gap is carried; **the 1,592-vs-27 deferral-extraction remainder is not**; **`kb_setup.evals`'
BLE001 "fewer cases reads as green" surface is not**; **the dotfiles-sibling blast radius is not**;
**the "never ran `mise run lint`" caveat under SC-10 is not**; and **the 189 unmined adjacent-task
pairs are not**.

## GAP-7 (P1) — three modalities were never run at all

1. **PR bot reviews.** `session-review.js:375` defines 8 standard lanes including `bot-reviews`.
   This run defined **7 custom lanes** and `bot-reviews` is not among them — `grep -n "key:"` over
   `workflows/scripts/session-review-2026-08-21-wf_4ef74015-0a1.js` returns exactly
   `ray-requests, addenda, deferred-work, unpinned-tools, skipped-checks, automation-candidates,
   extraction-readiness`. So `circles`, `forgotten`, `contradicted`, `context`, `pending-work` and
   `bot-reviews` **all never ran**. `bot-reviews` is the expensive one: Ray called graphify-labs bot
   comments *"critical since we need to understand how graphify works"* (`773421d1` m3), PR **#422
   is open on this very branch**, and `grep -ic "PR #422" SYNTHESIS.md` → 0. The synthesis
   *recommends* building bot harvesting (§2b) without ever harvesting this round's own.
2. **Telemetry.** Ray: *"probably can be derived from parsing telemetry files"* (A6-11).
   `grep -ic telemetry SYNTHESIS.md` → **0** (control: `gitleaks` → hits). `.agent/telemetry/` was
   never opened by any lane. It is the only surface that could have answered "was this review worth
   its token cost", which is A6-11's whole point.
3. **Non-Bash tool calls.** 647 Edit + 146 Write + 141 Read + 22 Agent + 10 Workflow calls: the
   automation lane states plainly it mined **Bash only**. Edit is the second-most-used tool.

## GAP-8 (P1) — a `blocks_extraction: true` answer exists only in a gitignored file

RR-34's answer ("should we use `claude-agent-sdk-python` to review previous sessions?") is the
`sdk-premise` verdict from `6697269c` m13: **no** — an SDK fan-out is a second, separately
authenticated, separately billed client with no shared prompt cache, and Anthropic's ToS forbids
reusing the claude.ai login (`sources/agent-harness-docs/docs/claude-code/agent-sdk__overview.md:41-44`).
That verdict lives only in `.agent/kb/reports/agents/design-sdk-premise.md`. `.agent/` is gitignored
(`agent-artifact-conventions.md`), so the answer does not survive a clone. F15 promotes exactly one
report (`otel-collector-plan.md`) and **not this one**. **Action:** add `design-sdk-premise.md` (and
`design-telemetry-codegen.md`, `seam-advisor-review.md`, which are the same class) to the F15
promotion bullet.

## GAP-9 (P2) — two Ray screenshots were never read, and they ARE recoverable

`f1d1c0cf` m4/m5 (*"this workflow is what i am referring to / it hit session limit too quickly and
is burning too many tokens"*) and m29/m30 (*"are we stuck, i see this failure"*). The extracted
`humans/*.md` carry only a `[Image: source: /var/folders/…]` placeholder, and that temp path is now
unreadable (`ls …/TemporaryItems/` → `Operation not permitted`; control: `ls -d …/T/` → exists).

**But the images are in the transcript.** `grep -c '"type":"image"' f1d1c0cf-…jsonl` → **2**
(control: `'"type":"text"'` → 182). **Action:** extract the two base64 blocks and read them; m29 in
particular is Ray reporting a *failure he saw* that nothing in this review names.

## GAP-10 (P2) — Ray put research instructions in artifact comments and nobody fetched them

`61da2c9e` m5, 2026-08-20T22:14:38: *"i added comments to the artifact on what to research"* —
17 minutes before m6 *"run the four lanes"*. `grep -ic "artifact comment" *.md` over all 44 files
→ 0. The `Artifact` tool's `action: "comments"` was never called. Those comments are, by Ray's own
words, the research brief for the lanes that then ran. **Action:** `Artifact({action:"list"})`,
then `action:"comments"` on the 2026-08-20 artifact, and reconcile against §2/§3.

## GAP-11 (P2) — the extraction lane never opened three files that gate the run

Its own coverage_note: `graphify_semantic_corpus_authority.py` and
`graphify_semantic_corpus_prototype.py` **were never read**, and `graphify_semantic_slice.py:1356-1410`
(receipt verification) was skipped. Yet the synthesis cites `graphify_semantic_corpus_authority.py`
at `:9`, `:89`, `:249`, `:413`, `:469`, `:1504` as evidence for G2, G5, G6 and F1 — i.e. **the
synthesis reads a file the lane did not**, so those citations have had no adversarial pass and no
second reader. Same for `_prototype.py:138` (cited in G5). **Action:** one pass over both files
before the F1+F2+G5 commit; they are the two most likely homes for another 0.9.47 straggler.

## GAP-12 (P2) — #409 and #414 were never opened, and the gate depends on both

Extraction lane: *"I did not open #409 (cited by #417 as the underlying wall) or #414."* G7's live
blocker **is** #409 and G3 **is** #414. The synthesis re-derived #414's figures independently (good)
but nobody read either issue body. Combined with ray-requests' *"I did not verify the CONTENT of
#411/#414/#417/#389 beyond their titles"*, **four of the gate's cited issues were judged by title.**
`SYNTHESIS.md:766-768` records the title-vs-body lesson (A5-04/#391) and then does not apply it.

## GAP-13 (P3) — the two figures that disagree between lane notes and the synthesis, unreconciled

`addenda-lane-notes.md:6` says "**421 issues**"; `ray-requests-notes.md:18` says "**276 titles**";
`SYNTHESIS.md:742` corrects to "**278 issues**, not 421 (421 is the highest issue-or-PR number)".
Three numbers, one corpus, and the addenda lane's **entire absence-probe set was run against the
421-row listing** — the same listing whose denominator the synthesis says is wrong. The absences
are probably still true (they were title-greps over the listing, not counts), but nobody re-ran them
against the corrected corpus. **Action:** re-run the addenda lane's absence probes with
`gh search issues --match body`, which is the method that found #391 when the title sweep missed it.

## GAP-14 (P3) — `docs/direction/2026-08-02` and `2026-08-17` were read by nobody

Both lanes that could have say so explicitly (addenda gap 1; ray-requests gap 4). `SYNTHESIS.md:762-763`
carries it. What it does not carry: the **consequence already observed** — `addenda-lane-notes.md:43-44`
found, from a single targeted grep, that `2026-08-17-ray-directives.md:85` contains a *second*
statement of the state-machine ask. One grep into an unread file produced one unfiled Ray item.
There are two unread files. **Action:** read both in full before the round claims the backlog is
enumerated; this is the cheapest remaining source of unfiled Ray asks in the whole document.

---

## What I did NOT reach (my own coverage note)

- I read all 94 Ray messages but **not the raw transcripts** — so the two truncated tails
  (`773421d1:104`, `:181`) are still unread by anyone, and I inherited that gap rather than closing it.
- I did **not** re-verify any of the 35 CONFIRMED verdicts; I audited *what was verified*, not
  *whether the verifications were sound*.
- I did **not** open the two screenshots (GAP-9) or the artifact comments (GAP-10) — I established
  that they are reachable and unread, not what they say.
- I did **not** read the 43 per-verification notes individually; I read `SYNTHESIS.md` in full,
  `addenda-lane-notes.md` and `ray-requests-notes.md` in full, and grepped the rest.
- My claim-to-gate mapping in GAP-2 rests on matching claim TITLES to gate text; ER-10→G7 and
  ER-11→G8 are unambiguous, G3's "no lane claim" rests on no ER/DW/SC claim mentioning dedupe or
  571,462 — control arm: `ER-01..ER-13` titles were printed in full and none does.
