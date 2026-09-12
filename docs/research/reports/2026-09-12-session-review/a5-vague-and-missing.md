# Lane a5-vague-and-missing — cold read of the round's own outputs

Commit examined: `c1d8afb8` (`c1d8afb8cf686a6e39f186debb0e9499d794a5dc`), branch
`feat/754-plugin-types-contract`. Also read: two UNTRACKED files that exist on
disk right now but are not part of that commit —
`docs/dag/2026-09-12-session-review-round.toml` and
`docs/artifacts/session-review-3b921834-grill.html` (both `git check-ignore`
rc=1, i.e. not gitignored — just never `git add`-ed).

Findings are ranked by what they would cost the **next session**, most
expensive first.

---

## 1. 🔴 SILENT DROP, most expensive: an entire session's decisions exist nowhere a future session will look

**Where.** The current session is `kb-20260912.000` (confirmed from lane
`a1-behaviour`'s report: it identifies session 5, `3b921834`, as the audit
*target*, and the session I am running inside — the one that spawned lanes
a1–a5 — is a later one still). This session ran **seven `/grilling` rounds
(27 answers)**, per the DAG file's own header comment, and produced:

- `docs/dag/2026-09-12-session-review-round.toml` (8,183 bytes, 10 units + 2
  deferred items, a full worktree/merge-order plan)
- `docs/artifacts/session-review-3b921834-grill.html` (112 lines, the decision
  page referenced by the DAG header)
- the entire `.agent/kb/review-round/` fan-out you are reading right now

**Control-armed absence.** `grep -rl "session-review-3b921834-grill\|2026-09-12-session-review-round" -- '*.md'`
across the tracked tree returns **zero** hits outside `.agent/`. Neither file
is mentioned in `.agent/plans/session-2026-09-12-f.md` (the handoff
`/session-resume` reads — it predates this session), nor in any of the five
earlier `session-2026-09-12{,-b,-c,-d,-e}.md` handoffs, nor in
`docs/direction/2026-09-12-ray-directives.md`, nor in
`.planning/2026-08-30-upgrade-protocol-spec/progress.md` (whose most recent
entry is the session-audit-synthesis work, written before this grilling round
started).

**What a reader would conclude.** Reading handoff `-f` (the only pointer
`/session-resume` follows), the next session sees: "next task = run
`kb-codex-astra-advisor` fanning out to codex lanes, fix what it finds,
re-run `/clear-prep`." That is exactly what is happening right now. But it
has **no way to discover** that Ray already spent seven grilling rounds
settling *how* — worktree-per-unit, `pr_policy = "one PR per unit"`, the
reviewer (`kb-codex-astra-reviewer`, cold, by ref), the exact five review
lanes and their scratch-file contract, the wave order for the function-hook
migration, or that `next-ticket`'s removal is now explicitly deferred behind
a new unit (S7) rather than being an immediate 8-file edit.

**What is actually true.** These decisions exist, are detailed, and are
currently sitting as two **untracked, uncommitted files** with no commit, no
`git add`, and no handoff line pointing at them. If this session ends (crash,
`/clear` with no handoff write, `git clean -xdf` on another machine) without
someone (a) committing the DAG + the HTML page and (b) writing a handoff `-g`
that names them, this entire round of `/grilling` — the thing Ray explicitly
asked for because "we keep going backwards due to all the technical debt" —
is lost in exactly the way that phrase describes.

**The one-line repair.** Before this session ends: `git add
docs/dag/2026-09-12-session-review-round.toml
docs/artifacts/session-review-3b921834-grill.html`, commit them, and the next
handoff's first line must be "read `docs/dag/2026-09-12-session-review-round.toml`
before doing anything — it supersedes the OWED list in `-f`."

---

## 2. 🔴 CONTRADICTION: the fix pass you are inside right now is not gated on the unit the DAG says blocks everything

**Where.** `docs/dag/2026-09-12-session-review-round.toml`, unit `P0`:

```toml
[[unit]]
id = "P0"
title = "Fix the three mod_runtime P1s, review, ship and land #754"
...
blocks_all = true   # every other unit branches off main AFTER this lands
```

Every other mutating unit (`S1`, `S2`, `S3`, `S5`, `S6`) explicitly declares
`depends_on = ["P0"]`. Two do not: `S8` (`depends_on = []`, "the review
fan-out — 6 sessions, 5 angles" — the unit spawning **this lane**) and `S9`
(`depends_on = ["S8"]`, "fix what the review found" — **this lane's own
consumer**).

**Measured, not asserted.** `git log --oneline -- python/src/kb_setup/mod_runtime.py`
shows the last commit touching that file is `c33a1fb5`; HEAD (`c1d8afb8`) does
not touch it. **P0 has not landed.** Yet S8 is running right now (this very
lane), and S9 — which will apply fixes, per its own note "the defects get
fixed in THIS session, not handed off" — has no `depends_on = ["P0"]` entry
despite `blocks_all = true`'s stated intent that "every other unit branches
off main AFTER this lands."

**What a reader would conclude.** That `blocks_all = true` on P0 means no
other mutation happens until #754's three P1s are fixed, reviewed, shipped
and landed. Reasonable, since P0's own note says shipping #754 as-is "merges a
gate whose central claim is measured FALSE."

**What is actually true / unknown.** S8 and S9 are silently exempted, with no
line explaining why. Two readings are both plausible and nothing in the file
picks one: (a) S8/S9 are read-first/fix-here-only and deliberately run
in-place on the *current* branch rather than a fresh worktree off `main`, so
`blocks_all` was never meant to reach them; or (b) this is an oversight, and
S9's fixes (which may well touch `mod_runtime.py`, `mise.toml`, or `hk.pkl` —
files P0, S1 and S2 all also touch) will be applied and possibly committed
**before** P0's fix lands, meaning the "gate whose central claim is measured
FALSE" note in P0 could still be true when S9 finishes.

**The one-line repair.** State explicitly in the DAG whether `blocks_all`
exempts non-worktree units by definition, or add `depends_on = ["P0"]` to S9.

---

## 3. 🔴 MISSING: S9's `touches` is unknown, so it cannot be placed in the merge-order the whole DAG exists to enforce

**Where.** Unit `S9`: `touches = ["UNKNOWN — set from S8's findings before
dispatch"]`. The DAG's own semantics comment says: *"units sharing a `touches`
entry are serialized at MERGE time, in the order their ids appear here."* That
ordering is computed from the **id order in the file**, which is fixed at
authoring time — S9 is listed last, after S1–S6.

**What a reader would conclude.** That merge-order serialization is a solved
problem here, since the file states the rule plainly.

**What is actually true.** If S9's real `touches` set (once populated from
S8's actual findings — e.g. this very finding recommends editing the DAG
file itself, or `mise.toml`/`hk.pkl` per unit S1/S2's own scope) overlaps
with S1 or S2's `touches`, there is no stated mechanism for re-inserting S9
into the id-ordered serialization *after* the fact, since the ordering is
positional in a file written before the overlap was known. Nothing says who
updates the file, or whether S9's position (last) is meant to always mean
"merges last regardless of what it touches" (which would actually be a fine
rule — it just is not written down).

**The one-line repair.** State explicitly: "S9 always merges after every unit
whose `touches` it overlaps, regardless of id order" (if that's the intent),
or add a step to populate S9's `touches` and re-check for new overlaps before
its PR opens.

---

## 4. 🟡 CONTRADICTION: two different scopes for the same OWED item, in two places, neither aware of the other

**Where.** Handoff `-f`'s OWED list: *"`#754` stays OPEN (Ray's call) but
**must stop blocking** #756/#771/#772/#759/#763 — remove the `754` edge from
those chain rows."* That is a narrow, surgical edit: keep
`docs/roadmap/aggregated-research-chain.toml`, remove one blocker id from five
rows.

The DAG's `[[deferred]] D1`: *"Remove next-ticket and the chain file entirely
(8 files)... Ray, round 6 Q4 — waits for S7's verdict."* That is a wholesale
removal of the mechanism the first item's edit would have been made inside.

**Measured.** `docs/roadmap/aggregated-research-chain.toml` today still has
`blockers = [754, 755]` / `[754, 755, 757]` / `[754, 757]` on four rows and a
comment naming `754` as a fifth row's only blocker (lines 61–136) — neither
edit has happened yet, so the contradiction is still latent rather than
already having produced conflicting work. But nothing in the DAG says "this
supersedes the handoff's narrower ask" — a reader who does the narrow edit
first (because it is the OWED item their handoff names) will have just
touched the exact file D1 says to delete outright, for no benefit once S7
lands.

**The one-line repair.** One line in D1: "supersedes handoff `-f`'s narrower
'remove the 754 edge' item — do not do that edit separately."

---

## 5. 🟡 MISSING: D1/S7 name `/session-resume` as the consumer to rewrite; `/clear-prep` is an equally real consumer and is never named

**Where.** DAG unit `S7`'s note: *"Its verdict decides what `/session-resume`
reads."* D1 defers `next-ticket` removal behind S7.

**Measured.** `grep -n "next-ticket\|next_ticket" .claude/skills/clear-prep/SKILL.md`
returns two hits: line 59 (the fallback next-task source) and line 457 (a
checklist item requiring `next-ticket` to have been generated and re-run).
`/clear-prep` depends on `next-ticket` at least as much as `/session-resume`
does — it is the skill that *writes* the handoff the removal is meant to
replace.

**What a reader would conclude from S7's note alone.** That rewriting
`/session-resume` is the whole job.

**What is actually true.** Two skills need rewriting, not one, and only one
is named. If S7's verdict lands and D1 executes against `/session-resume`
only, `/clear-prep` silently keeps calling a task/file that D1 deleted.

**The one-line repair.** S7's note: add "`/clear-prep`'s own next-task
generation (SKILL.md:59, its close-out checklist at :457) is the same
dependency and must be rewritten in the same pass."

---

## 6. 🟡 MEASURED, not previously quantified: the auto-memory index overage, and exactly what is being cut

Handoff `-f` (carrying `-e`'s language) says the index "is still over its read
limit" and "this round replaced the lead line rather than appending" — true,
but never gives a number.

**Measured this lane, with a control.** `wc -c` on
`~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/memory/MEMORY.md`
returns **31,479 bytes**. The system-reminder banner for this same file states
a 24.4 KB (≈24,986-byte) limit and that lines 79–109 (31 of 109) were cut. That
overage is **~6,493 bytes, ~26% over the limit** — not a rounding error, and
growing every round per `-e`'s own note ("grew ~290 bytes this round").

**What is actually being cut is not filler.** Lines 79–109 (read directly by
this lane) contain, among other things, the entire "How my own fixes fail"
section, the "Gates that pass over a real loss" section, "The corpus and
graphify" section, and half of "Environment and tooling" — each a
one-line pointer into a real lesson file, not padding. A future session
reading this index literally cannot see that "the fix is the least-reviewed
code in the diff" is a recorded lesson, at the exact moment (finding #2/#3
above) where that lesson is directly relevant.

**The one-line repair.** Not this lane's job to fix (Ray's standing call: do
not hand-compact, it needs U8's generator) — but the handoff should carry the
measured number, not the qualitative "still over," so the next session can
tell whether U8 made progress or the gap widened again.

---

## 7. ⚪ Minor inaccuracy inside the DAG file itself

Unit `P0`'s comment: `# already exists, 4 commits ahead`. Measured: `git log
--oneline main..feat/754-plugin-types-contract` returns **6** commits, not 4
(the DAG was authored after `c1d8afb8` was already HEAD, per the lane reports
citing that SHA as "commit examined"). Low cost on its own — nobody merges
based on a commit count — but it is exactly the shape `change-the-route.md`
warns about: a plausible small number, never re-derived, sitting in a file
written to be authoritative.

---

## Summary for the caller

**Silent drops, most expensive first:** (1) the whole grilling round / DAG /
decision page is invisible to every handoff and every planning-with-files
artifact — commit it and point to it before this session ends, or it is lost
exactly the way Ray's directive complains about. (3) S9's touches are
unresolved, so the DAG's own merge-order guarantee has no way to include the
fix pass currently running.

**Contradictions across artifacts:** (2) `blocks_all = true` on P0 vs. S8/S9
running unblocked right now, with no line explaining the exemption. (4) the
handoff's narrow "remove the 754 edge" vs. the DAG's later "remove the whole
chain file", not marked as superseding.

**Vague / missing:** (5) `/clear-prep` is a real consumer of `next-ticket`
and is never named as needing the same rewrite `/session-resume` gets. (6)
the MEMORY.md overage was described qualitatively but never measured — it is
~26% over limit today. (7) a small stale fact inside the DAG file itself.

## GitHub repos touched

_None._

---

## UPDATE (live, same session): finding #2 has been corrected in the DAG file itself, #1 and #3 have not

Re-checked `docs/dag/2026-09-12-session-review-round.toml` after filing the
above. Someone (a concurrent teammate — `kb-session-search` shows the edit
landing at 2026-09-12T20:22:16Z) has already fixed finding #2: `blocks_all =
true` is now commented out, replaced with:

> `# CORRECTED on first read: blocks_all = true was wrong. Only S9 depends on
> P0 (both edit mod_runtime.py). Every other unit branches off the CURRENT
> main and runs now; P0 lands independently. The DAG caught this — which is
> the point.`

and `S9`'s `depends_on` is now `["S8", "P0"]`. Good — that confirms finding #2
was a real defect, not a misreading, and it is now closed. **Still open:**
finding #3 (S9's `touches` is still literally `"UNKNOWN"`), and finding #1 —
`git status --short` still shows both `docs/dag/` and
`docs/artifacts/session-review-3b921834-grill.html` as untracked (`??`).
Nothing has committed them yet. **The commit is the part that actually
prevents the loss** — an in-session fix to an uncommitted file is still lost
if the session ends before `git add` + commit.
