# The founding self-reflection pass — 2026-08-06

The first pass in which this repo read its own history looking for recurring
failure. Run by the standing agent roster (PR #209), which had never been
dispatched before this.

**Corpus, all four re-derived rather than inherited:** 45 session handoffs
(`.agent/plans/`) · 121 committed work-memories (`graphify-out/memory/`) · 71
open issues + all 57 closed · 24 tool-currency runs plus the 108-file assistant
memory store.

**Output:** 66 raw findings → 64 after dedup. 8 claims adversarially verified.
One new rule, six new issues, seven durable-record corrections, seven issue
comments. **No issue closed.**

---

## 1. The result that should govern the next pass

> **A reader's ranked table is a set of LEADS, not findings.**

**8 claims were adversarially verified. 7 changed the answer.** The single
confirmation (`currency.toml` tracks 4 of 14 pins, not 7) still corrected the
committed record it was checked against.

That includes **5 of 5 close/merge recommendations refuted** — every one, each
for a different reason. And the refutation landed hardest on a reader's own
**#1 ranked finding and #1 recommended action**.

The readers were not sloppy. The `close #134` reader's three-arm probe
**reproduced exactly** under the verifier's re-run; it was reading a *stale
layer of a multi-layer issue*. That is the failure mode to design against: not
carelessness, but a correct probe pointed at superseded text.

| recommendation | verdict | why it was wrong |
|---|---|---|
| close **#134** as refuted | refuted *as stated* | It is **completed**, not refuted. Rationale false on the issue's current text (*"That needs re-extraction, not edge deletion"*); commit citation `459de7a` wrong (it was `299af16`, repaired by `dfae6ce` the same day); and #134 had already been auto-closed once and **reopened on evidence**. |
| close **#19** as dup of #200 | do not close | Both asks live — `ingest.py:159` is still `markdown[:12000]`, and the boilerplate grep is a *discriminating* zero. #19 is **upstream**-scoped, #200 the **local** wrapper; #20's body records the split as authored. |
| close **#21** as superseded | do not close | #203 is a **proper subset**: #21 asks to *route* `kb-add` losslessly in one step, #203 only to *deny* it in two. All of #21/#22/#203 unshipped — `mise.toml:442` is still `run = "graphify add"`. |
| merge **#202 → #122** | refuted | Both cited facts hold; the **superset relation** does not. #202 carries a contradicting destination. |
| close **#23** as moot | do not close | All four asks live, and ask 4 **regressed** (see §3). A ticket's missing acceptance criteria is a defect *in the ticket*, not evidence the question is dead. |

**Implication for `kb-reflector`** (the seventh agent, still unwritten): its
output contract must be *candidate findings with a verification cost estimate*,
never a recommended-actions list. A pass that files its readers' conclusions
directly would have closed five live tickets today.

---

## 2. The prose-saturation finding

The most important structural result, and it indicts the pass's own remedy list.

**Three of four readers independently recorded a *measured* verdict that
writing the lesson down did not work:**

| slice | verbatim |
|---|---|
| handoffs | *"Six occurrences of a rule that is already written, eager, and detailed. That is the finding: **this class is not fixed by more prose**."* |
| memories | *"**Writing the lesson down has now failed twice consecutively**, so the remedy is structural."* |
| issues | a rule violated after being written is this repo's own stated trigger for a machine layer (`mise-tasks-only.md`: markdown alone is *"relying on the LLM"*) |

Supporting measurements: compliance with "query the graph FIRST" — this repo's
founding premise, stated eagerly in `CLAUDE.md` — was **2 of 7**. `do-not.md` #7
("branch FIRST") is eager and was violated with ≥6 commits onto `main`. Live
credentials reached transcripts **three times, the last after** the prohibition
was in every lane prompt.

And the four readers' combined remedy was **22 additions to `.claude/rules/`** —
costed at **+18,350 bytes on a 100,810-byte eager base (+18.2%)**, ≈ +4,600
tokens in every session, forever.

### The criterion adopted instead

A finding becomes eager rule text only if **all three** hold:

1. **No mechanisable form exists.** If a gate, task, hook or test could catch
   it, that is the remedy and the rule is at best a footnote.
2. **No existing rule already covers it** — established by a control-armed
   grep, not by assumption.
3. **Its trigger is a behaviour**, so `paths:`-scoping would make it absent
   exactly when needed (`md-size-budgets.md`'s trigger test).

**One file cleared all three.** `.claude/rules/arm-your-own-work.md`, 113 lines
/ 6,428 bytes, agnix `--strict` rc=0. Measured cost: eager context 120,305 →
**126,732 bytes, +5.3%**. The other 17 amendments are specced in **#216**,
including the three the synthesist itself nominated for demotion.

---

## 3. What was found

### Top findings by recurrence × cost

1. **Loss happens *past* the gate.** Real corpus loss four times — 3
   hyperedges, 72 nodes of a source, a 46%-truncated article — with **every
   gate green**. The validator ran, opened the right artifact, and was
   structurally blind to the loss class.
2. **The ingestion path loses content silently, and was re-derived from
   scratch after 12 days.** The 12 ingestion tickets are one defect; #200/#203
   re-derived #10/#21 because the 2026-07-24 cohort was never triaged.
3. **A fix becomes the next round's defect** — 9 rounds, 6 work-memories,
   **control-armed zero hits across all 22 rule files**. One non-converging
   loop cost 2.93M tokens and was reverted. Now `arm-your-own-work.md`.
4. **The self-improvement loop is degrading with every gate green** — #211.
5. **`kb-land` leaves you on `main`**, 3-slice convergence, cheapest fix in the
   pass — #213.

### Findings produced by the verification stage, in no reader's report

- **The crawl posture regressed.** `fetch.py:83` spoofs a full Chrome
  User-Agent, with **zero** robots.txt / ETag / crawl-delay handling anywhere
  in `kb_setup` (control-armed). Found by an agent dispatched to *close* #23.
  Filed as **#215**.
- **`md-budget` counts only the git index.** A newly written 6,428-byte eager
  rule produced a **zero delta** and rc=0. Armed both directions: untracked →
  30 files / 120,305 bytes; `git add` → 31 / 126,732; `git reset` → back.
  Filed as **#214**.

### Two of this pass's own findings recurred inside the pass

Recorded because they cost seconds here and rounds elsewhere:

- **A fix introducing the defect it fixes.** Repairing dangling `[[wikilinks]]`,
  the correction itself wrote ``breaks every `[[wikilink]]` silently`` — and a
  backticked double-bracket token *is* a link target. Caught only by
  re-deriving the set: the count came back 6 → **5**, not 4.
- **Three more zsh false zeros.** An unquoted `--include=*.py` → "no matches
  found"; a `gh search --search/--json` → a false `[]`. Both survived only
  because a control arm ran.

---

## 4. Roster exercise — the pass's second purpose

First-ever dispatch of the standing roster. **5 of 6 agent types exercised; 1
produced nothing.**

| agent | dispatched | result |
|---|---|---|
| `kb-adversarial-verifier` (opus) | 7× | The pass's highest-value stage — 7 of 8 verdicts changed an answer |
| `kb-synthesist` (opus) | 1× | 73KB; produced the prose-saturation and convergence results no reader could see |
| `kb-advisor` (**fable**) | 1× | **No output. ~25 min, no file, no reply to a direct ping.** |
| `kb-corpus-curator`, `kb-tool-researcher`, `kb-extraction-worker` | 0× | Not applicable to this pass |

**`kb-advisor`'s silence is a measurement for #208**, not a retry. The handoff
predicted it: `model` frontmatter is only **step 3 of 4** in resolution, and a
blocked model falls back silently. What is declared is not what runs.

**The roster has no reader role** — the four corpus readers ran as
`general-purpose` because `kb-tool-researcher` binds itself to "one *peer tool*
per agent" and the rest are ingestion executors. The `kb-reflector` deferred
last round is exactly the missing seat. Its spec is now informed by a real run
(§1's output contract, and the `STATUS: IN PROGRESS (n/N)` line that made
incremental progress observable without interrupting an agent).

---

## 5. State after this round

**Filed:** #211 (kb-remember drops `correction:`/`source_nodes`) · #212
(LESSONS.md gitignored) · #213 (kb-land leaves you on main) · #214 (md-budget
counts only the index) · #215 (UA spoof / no robots) · #216 (17 parked rule
amendments).

**Commented, so the refutations are not re-derived:** #134, #19, #21, #22, #23,
#202, #150 (unblocked — all three blockers closed, and #149 listed twice).

**Corrected in the assistant memory store:** `currency-tracks-half-the-pins`
(4 of 14, ~71% untracked; slug kept as a flagged misnomer because inbound links
resolve by name) · `roster-round-landed` (its `description:` — *the field recall
selects on* — contradicted its own body) · 3 dangling wikilinks, all written
from the human title instead of the slug.

**Not done, deliberately:** no issue closed; the 17 rule amendments parked in
#216; `/clear-prep` integration still spec-only, per the standing decision that
a loop is not automated until it has run once by hand.

**Open issues: 71 → 77.** The backlog grew, which is the honest outcome of a
pass whose verification stage refuted every proposed close.

---

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the subject; all 71 open and 57 closed issues, 45 handoffs, 121 work-memories, 24 currency runs, and `python/src/kb_setup/**` read for verification.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the pinned 0.9.34 dependency; `ingest.py:159` (the 12k truncation) and `build.py` read via the pinned clone. PyPI probe at session start confirmed **0.9.35 has not published** (upstream #2514, publish cancelled in the 2026-08-06 GitHub Actions outage).
- [jdx/mise](https://github.com/jdx/mise) — pin currency, as cited by `docs/currency/runs/`.
- [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) — the `source_only` currency entry examined by the currency reader.
- [agent-sh/agnix](https://github.com/agent-sh/agnix) — the pin that sat six versions stale invisibly; the worked case behind #211's sibling finding.
- [openai/codex](https://github.com/openai/codex) and [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli) — the two untracked self-updating lanes in the currency coverage gap.
