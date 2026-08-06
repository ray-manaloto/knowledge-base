# Synthesis — the founding self-reflection pass

STATUS: COMPLETE

Agent: kb-synthesist. Date: 2026-08-06. Repo:
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base`, branch `chore/post-209`.

**Role: combine, not research, not re-verify.** Every claim below is carried from
one of seven input reports and is attributed to the slice that produced it. Where
a claim was independently probed by an adversarial verifier, the verification
outranks the reader and that is stated **in place**. Where I could not resolve a
disagreement from the inputs alone, I say so rather than filling the hole.

The only numbers I re-derived myself are the `.claude/rules/` budget figures in
§4 — because a RULE recommendation built on an inherited byte count is unusable,
and one of the brief's own figures did not reproduce (§4.0).

## Inputs

| report | slice | ranked findings | status |
|---|---|---|---|
| `reflect-handoffs.md` | 45 session handoffs, 2026-07-27 → 2026-08-06 | 22 | COMPLETE (45/45 read in full) |
| `reflect-memories.md` | 121 committed work-memories + LESSONS.md | 15 | COMPLETE (121/121) |
| `reflect-issues.md` | 71 open + 57 closed issues | 17 + 18 backlog actions | COMPLETE (128/128) |
| `reflect-currency.md` | 24 currency runs + the 108-file auto-memory store | 12 | COMPLETE |
| `refute-currency-count.md` | verification | — | `refuted: false` (claim CONFIRMED) |
| `refute-close-134.md` | verification | — | `refuted: TRUE` **as stated** |
| `refute-lessons-gitignored.md` | verification | — | **PARTIAL** — 1 half confirmed, 2 halves refuted |

**66 raw ranked findings** (22 + 15 + 17 + 12). Every one is mapped in §6.

---

## 0. Read this first — three things only the synthesis seat can see

### 0.1 · The verifier ran, and it changed two answers. That is the good news.

Three verifications produced **one confirmation, one refutation, one partial**.
A pass with zero refutations would mean the verifier had not really run; that is
not this pass.

But the coverage is thin and should be reported as a fact about the process, not
hidden: **3 of 66 findings were adversarially verified (4.5%).** The other 63
carry forward at *reader confidence*, which — as the brief warns — is not
comparable across the four readers. Everything in §5 is tagged with its
verification status for exactly this reason.

The refutation matters disproportionately because it landed on a reader's own
**#1 ranked finding and its #1 recommended action** (`reflect-issues.md`:
*"Close #134 … This is the highest-value finding in the pass"*). Acting on that
reader's top recommendation, unverified, would have:

- closed a **completed** issue as **refuted** — the inverse of the mistake
  already recorded *inside that same issue*, which was auto-closed once on
  `299af16`'s "closes #134" and then **reopened on evidence**;
- cited a wrong commit (`459de7a` does not touch the file; the deletion was
  `299af16`, repaired by `dfae6ce` the same day, three days before the reader
  called it a live hazard);
- and destroyed the only tracked record of a real, live gap (`#134`'s ask A1 —
  no hk step or `kb-ship` gate runs `kb-validate-chunks`; `GATE_TASKS` is
  `("lint", "test", "brain-audit", "eval")`).

The reader was not sloppy — its 3-arm probe **reproduced exactly** under the
verifier's re-run. It was reading a stale layer of a multi-layer issue.

### 0.2 · The prose-saturation finding — the readers proposed 19 prose remedies for classes they themselves measured prose failing to fix

This is the cross-cutting result that is invisible from any single slice, and it
is the most important thing in this report.

Three of the four readers independently recorded a **measured verdict that
writing the lesson down did not work**:

| slice | verbatim |
|---|---|
| handoffs (F11) | *"Six occurrences of a rule that is already written, eager, and detailed. That is the finding: **this class is not fixed by more prose.**"* |
| handoffs (F6) | the credential prohibition *"was added to lane prompts and **a round-2 lane still did it** and self-reported"* |
| memories (F8) | *"**Writing the lesson down has now failed twice consecutively**, so the remedy is structural, filed as issue 160."* |
| issues (§5b) | *"A rule that has been violated after being written is the repo's own stated trigger for adding a machine layer"* — citing `mise-tasks-only.md`: markdown alone is *"relying on the LLM"* |

And yet the four readers' combined remedy list is **22 additions to
`.claude/rules/`** — ~18 KB, a **+18.2%** increase on the eager launch budget
(§4). Several of those additions target the exact classes quoted above.

I am not recommending the RULE bucket be discarded — a judgement failure with no
mechanisable form has nowhere else to go, and most of the 22 are that. I am
recommending the round **read §4's cost line before adopting §5's RULE column**,
and treat "add a rule" as the answer of last resort for any finding that already
has a rule.

### 0.3 · Convergence is the strongest signal here, and it is concentrated

**Ten findings were reached independently by 2+ readers.** Three were reached by
**all-but-one** of the relevant slices. Convergence is what §2 is for, and it is
the reason the top of §7 looks the way it does.

---

## 1. How I deduplicated

Two findings were merged **only** when they name the same *mechanism*, not when
they name the same *symptom*. Four near-misses I deliberately did **not** merge,
recorded here because the temptation was real:

| kept separate | why |
|---|---|
| **M4** (the gate ran, opened the right artifact, and was blind to the loss class) vs **M13** (the gate's *scope excluded the path*, so it never opened the file) | `reflect-handoffs.md` draws this distinction explicitly (F20 vs F5) and it is load-bearing: M13's fix is a coverage assertion, M4's fix is an absence-injection arm. One does not produce the other. |
| **M10** (a correctly-measured figure that later became false) vs **M32** (two numbers from *different sets* read as a fraction) | Staleness vs a category error. `refute-currency-count.md` is explicit that the memory's *body* sentence is "literally true" and only the headline is wrong — that is not decay. |
| **M7** (one record states two different things) vs **M34** (an immutable record carries a *mutable* property) | Contradiction-at-a-moment vs correctness-decaying-by-design. M7's remedy is "amend the loser"; M34's is "don't put the pointer there at all". |
| **M25** (`corrected` with no `correction:`) vs **M26** (`--nodes` unrecorded since July) | Two different dropped fields with two different downstream artifacts (LESSONS.md's Corrections section vs `.graphify_learning.json`). They share **one fix** (fail closed in `kb-remember`) and I say so — but they are two findings and the fix must cover both. |

**Counts are never added across slices.** The readers count different units
(rounds vs memories vs issues vs run pages). Where two slices give different
counts for one mechanism, both are shown with their unit, and the wider window is
preferred — see M3, where handoffs says *5 harnesses* and memories says *3*, and
the difference is the reading window, not a disagreement.

---

## 2. Convergence — findings 2+ readers reached independently

The single most valuable output of this pass. Each row is one mechanism that
more than one slice arrived at from a different corpus, and — critically — the
column that says **what each slice contributed that the others did not**. A
finding reached three ways is not three copies of one claim; it is three
different pieces of evidence about one mechanism.

| id | mechanism | slices | what each slice uniquely contributed |
|---|---|---|---|
| **M2** | `kb-land` leaves you on `main`, and the next commit lands there | **3** — handoffs, memories, issues | handoffs: the *recurrence* (≥6 commits, 4 sessions, +2 in the sibling repo). memories: the *diagnosis* (`do-not.md` #7 was eagerly in context and **nothing asked the question**) + a grep proving the one-line remedy is unshipped in `pr.py`. issues: control-armed proof that **no issue tracks it** (`branch FIRST` → 0 of 128; control `hyperedge` → 109). |
| **M3** | The mutation harness is re-authored every round and re-acquires the `__pycache__` defect | **3** — handoffs, memories, issues | handoffs: the *count* — **five** harnesses, and the fifth "extracted the runner programmatically rather than restating it, which is the interim mitigation, not the fix". memories: the *verdict* — "writing the lesson down has now failed twice consecutively, so the remedy is structural". issues: #160 used as the **control** proving the section's other zeros are real greps. |
| **M6** | The ingestion path loses content silently, and the defect was re-derived from scratch 12 days later | **3** — handoffs, memories, issues | handoffs: the *generalisation* — "the roundtrip samples what was KEPT, so it is structurally blind to what was never extracted". memories: the **proven casualty** (`mindstudio-advisor-executor.md`, 54% of a 17,161-char article, 0 of 17 concepts past the 60% mark) **with a control row** under the cap reaching 94%. issues: the *cost of not triaging* — all 10 of the 2026-07-24 cohort untouched since 2026-07-26, so #200/#203 re-derived #10/#21. |
| **M7** | One durable record states two different things, and the reader picks one silently | **3** — handoffs, issues, currency | handoffs: **6 of 6** tickets in the #143 chain needed an amendment; #149's body and criterion 1 stated different rules and building the criterion "**relocated the ticket's own harm instead of removing it**". issues: the same shape on the *oldest* tickets (#21/#22 both end `Shipped in #18.` while their titles are undone) and on #106 vs #129. currency: the same shape in a **memory** — `roster-round-landed`'s `description:` says #198 is next, its body says "**#198 is therefore NOT next**". |
| **M9** | The committed durable stores have no reviewer, and there are two of them | **3** — issues, currency, memories | issues: `graphify-out/memory/**` is in `review.EXEMPT_PATHS` — 3 closed issues, **0 open**, so nothing tracks the asymmetry. currency: the *other* store has the identical defect (B1), and **neither store reviews the other**; 121 + 107 records, no stated division of labour. memories: the consequence — "nothing reviews these files", cited for a memory whose present-tense parenthetical is 11 releases stale. |
| **M8** | A bounded probe reported as an answer | **3** — handoffs, issues, **and a live near-miss inside this pass** | handoffs: 6 rounds, and the bound was a token spelling / `--limit` / `-k` / a regex anchor / a pinned clone. issues: the reader *applied* the lesson (`--limit 200`, noting the default 30 would truncate) and cites an earlier pass that "under-counted by six". `refute-close-134.md`: searching the new chunk for #134's own node ids returns **zero** because the re-extraction renamed the namespace `graphify_*` → `gfyarch_*` — "a probe stopping at #134's own vocabulary would have concluded the pipeline is still missing". |
| **M1** | A fix becomes the next round's defect; the countermeasure that worked is mutating your **own** fix | **2** — handoffs, memories | handoffs: 9 rounds, 11 citations, and **four named sub-shapes** (removes a guard nobody re-armed / trades one failure for its mirror / makes the sequence unrunnable / raises a bound instead of removing it). memories: the **control-armed proof that no rule states it** (`grep -rn 'your own fix\|own fixes\|fix breeds\|fix introduced' .claude/rules/` → NO HITS, against a control of `control arm` → 3 files) plus the observation that MEMORY.md carries **four separate slugs** for the same lesson, which is itself evidence it keeps being re-learned rather than looked up. |
| **M4** | A check the repo **ships** cannot see the thing it names; the loss happens past the gate | **2** — handoffs, issues | handoffs: 4 rounds of *real corpus loss* while every gate was green, and the diagnostic question — "ask what the check *reads*, then ask what a total loss would look like **to that reader**". issues: the *scope* argument — `probes-need-a-control-arm.md` says it applies to "every **ad-hoc** probe … because nothing reviews them", and that scope "is now wrong by measurement": ad-hoc probes now get armed, **shipped checks do not**, and six open issues (#131 #138 #158 #188 #198 #207) are that. |
| **M5** | Prose asserts what the code does not do — and the prose is what prevents the re-read | **2** — handoffs, memories | handoffs: the *worse* harm — a comment that **disarms the next reviewer** ("a reviewer given that rationale would have nodded"), plus `agent-artifact-conventions.md` glossing `dirty` with **inverted polarity** on the very field added to stop a false reading. memories: the *mechanism* — "**the docstring is what stopped me re-reading the one line beneath it**", and that the fix is a *method* (a mutating lane brief), not more care. |
| **M10** | A committed figure goes stale and is re-cited as a measurement | **3** — handoffs, memories, currency | handoffs: `CLAUDE.md` carried a **3×-wrong** graph size and a stale prose-node count simultaneously. memories: a present-tense "(NOT installed)" about features shipped 11 releases ago. currency: `substrate-map-is-the-active-thread`'s "the IMMEDIATE work is #143/#144–#150" — four of those are CLOSED and the survivor is recorded as not-next. |

### 2.1 · Convergence that is NOT convergence — two look-alikes I rejected

- **M13 (green gate that examined nothing)** looks like M4 and is not. Only
  handoffs reports it. `reflect-issues.md`'s #158 (*a malformed `mise.toml`
  silently drops the entire gate check*) is adjacent and would corroborate it,
  but the issues reader filed #158 under the M4 cluster, so treating it as
  corroboration would be me re-classifying another agent's finding rather than
  combining it. Recorded as an **adjacency**, not a second slice.
- **M29 (the corpus records building the tool, not using it — 4 of 121 memories
  mention `kb-query`)** and **handoffs M23 ("query the graph FIRST", measured
  compliance 2 of 7)** point the same direction from two slices, but they are
  different mechanisms: one is *what gets recorded*, the other is *what gets
  done*. They corroborate each other as **evidence about the same blind spot**
  and I say so in §5 — without merging them, because their fixes differ (a
  `kb-remember` habit vs #117's enforcement).

---

## 3. Where a verification overrides a reader

Stated in place, per the brief. These three rows are the only claims in this
synthesis carrying probe-grade confidence, and two of them changed a reader's
answer.

### 3.1 · `refute-close-134.md` — reader's #1 action REFUTED as stated

`reflect-issues.md` ranked *"Close #134 — refuted; its remedy already caused data
loss"* as finding #1 and recommended action #1.

**Verdict: `refuted: TRUE` — as stated.** The verifier's three separate
corrections:

1. **"as refuted" is wrong — the issue is COMPLETED.** #134's finding was real
   (37 dangling edges, validator never swept). It was fixed across `299af16`
   (wiring) → `dfae6ce` (correcting the wiring's own damage) → `d5da30c` (the
   re-extraction: 43 nodes/33 edges/2 hyperedges → **796/1099/45**, with the
   seven-stage pipeline hyperedge's 8 members all resolving in-chunk).
2. **The stated reason is false on the issue's current text.** #134 was
   auto-closed once and **deliberately reopened on evidence**; its newest text
   says the opposite of the remedy it is accused of recommending — verbatim,
   *"That needs re-extraction, not edge deletion."*
3. **The commit citation is wrong.** `459de7a` does not touch
   `goal-and-skills-workflow-docs.json` (empty `git show --stat`). The deletion
   was `299af16` and it was repaired by `dfae6ce` **the same day**, three days
   before the reader called it a live hazard.

**What survives and must not be lost:** #134's ask **A1** — an hk step or a
`kb-ship` gate running `kb-validate-chunks` over the committed set — is real,
untracked anywhere else, and confirmed live by the verifier (`hk.pkl` has no
`validate_chunks` step; `kb_setup/gates.py:94` `GATE_TASKS = ("lint", "test",
"brain-audit", "eval")`). The residual window is bounded — `graph.build()`
validates every committed chunk atomically and fails closed, so the *artifact*
is never corruptible — but **detection is deferred to whenever someone next runs
`kb-build`**.

→ Destination changed from `BACKLOG: close as refuted` to **`BACKLOG: close as
COMPLETED, and re-file A1 FIRST`** (M40).

### 3.2 · `refute-lessons-gitignored.md` — reader's claim PARTIALLY refuted

`reflect-memories.md` finding F2 / rank 10: *"LESSONS.md — the output of the
self-improving loop — is **gitignored**, so a consumer repo or fresh clone has no
lessons until someone **rebuilds the graph** and re-runs `kb-reflect`."*

| half | verdict |
|---|---|
| gitignored / never tracked on any branch | **CONFIRMED** — 4 control-armed probes, incl. `git log --all --diff-filter=A -- '*LESSONS.md'` empty against a control that finds `CLAUDE.md`'s add |
| "…until someone **rebuilds the graph**" | **REFUTED** — `graph_path` is an *optional* argument in the pinned 0.9.34 `reflect.py`; both graph loaders fail safe to `None`, and `return known or None` closes the drop-everything failure mode by construction |
| "…has **no lessons**" | **REFUTED** — regenerable from the 121 committed memories by `kb-reflect` alone; the artifact's self-reported input count (121) equals `git ls-files 'graphify-out/memory/*.md'` (121), zero untracked |
| companion: the wrong path is *"stated by several documents"* | **REFUTED** — `grep -rn 'memory/reflections'` → **zero** hits against a control of 14 files naming the correct path. No document is wrong; several write it *relative*, which reads as nested |

**Two caveats the verifier says DO survive**, and they are narrower than the
reader's claim: the regenerated file is **degraded** (flat, no community
grouping, no dropping of lessons pointing at deleted code), and the
**`.graphify_learning.json` overlay genuinely IS graph-dependent** — for the
overlay half, "rebuild the graph first" is correct.

The verifier also states its own evidence class honestly: §4 of that report is
*source-grounded inference, not a measurement* — it read the pinned source and
did not execute the fresh-clone case.

→ M31 destination changed from `ISSUE` to **`DROP (not a defect)` + a
`CORRECTION` to the reader's own report**. The surviving overlay caveat is folded
into M26, where it belongs.

### 3.3 · `refute-currency-count.md` — reader CONFIRMED, committed memory is wrong

`reflect-currency.md` A1: *"`currency.toml` tracks **4 of 14** mise pins, not 7 of
14."*

**Verdict: `refuted: false` — the claim survives every arm.** The engine's own
`broad.deep_tracked_keys()` returns 4 covered / 10 uncovered. Three arms cleared
the alternatives: a mutant `[tool.typos]` block *with* a `mise_key` moves the
count to 5 (so the probe can return the other answer); a case-insensitive
structural TOML-key search finds `mise` 116 times **as text** and zero times as a
pin, against four controls that match; and all 14 pins carry exact versions, so
14 is not sensitive to the definition.

The record needing correction is the **committed memory**
`currency-tracks-half-the-pins.md` — its `description`, its **filename slug**
(*"half"*; it is under a third), and the body phrase "the untracked half"
(really 10 of 14 ≈ 71%). Its body's *declares 7 / pins 14* sentence is fine, and
its agnix lesson is untouched — in fact made slightly worse, since the blind set
is larger than the memory records.

→ M32 confirmed at probe grade; the correction target is the memory file, not
`currency.toml`.

---

## 4. The RULE budget — measured, and it does not fit without a split

### 4.0 · Re-derived, because the brief's figure did not reproduce

The brief states *"22 rules, ~120,305 bytes, ~30,076 tokens today"*. I could not
reproduce 120,305 under any denominator I tried, so I am **not carrying it**
(`probes-need-a-control-arm.md` rule 6 — an inherited number is not a
measurement). Measured 2026-08-06 on branch `chore/post-209`:

| denominator | files | lines | bytes |
|---|---|---|---|
| **eager rules only** (no `paths:` frontmatter — these load at LAUNCH) | **20** | **1,898** | **100,810** |
| all `.claude/rules/*.md` | 22 | 2,180 | 115,257 |
| all 22 + `CLAUDE.md` + `.claude/CLAUDE.md` | 24 | 2,444 | 134,774 |

Two of the 22 are **path-scoped** and therefore *not* part of the launch cost:
`md-size-budgets.md` (191 lines) and `ci-local-parity.md` (91 lines). Together
they are 14,447 bytes — close to, but not equal to, the brief's excess. I cannot
say which denominator the brief used.

**The operative base for every estimate below is 100,810 bytes / 20 files**,
because the brief's own constraint is specifically about *unscoped* files loading
at launch.

Ceilings (from `kb_setup.md_budget`): `DOCUMENTED_LINE_TARGET = 200`,
`EAGER_BYTE_BACKSTOP = 24_000`. The byte figure is a **self-imposed anti-gaming
backstop**, explicitly not an Anthropic figure — so lines are the binding
constraint here, and by a wide margin.

### 4.1 · Headroom on every file the four readers want to touch

| file | lines | line headroom | bytes | byte headroom |
|---|---|---|---|---|
| **`probes-need-a-control-arm.md`** | **180** | **20** | 10,629 | 13,371 |
| `verify-before-advancing.md` | 129 | 71 | 7,251 | 16,749 |
| `agent-report-persistence.md` | 107 | 93 | 5,675 | 18,325 |
| `long-running-command-hangs.md` | 93 | 107 | 5,076 | 18,924 |
| `clarify-before-acting.md` | 92 | 108 | 4,545 | 19,455 |
| `agent-artifact-conventions.md` | 84 | 116 | 5,482 | 18,518 |
| `notepad-enforcement.md` | 62 | 138 | 2,812 | 21,188 |
| `zero-bash-logic.md` | 61 | 139 | 2,824 | 21,176 |

### 4.2 · The collision, stated plainly

**Eight proposed additions target `probes-need-a-control-arm.md`, which has 20
lines of headroom.** They come from three of the four readers independently:

| # | proposed addition | from |
|---|---|---|
| 1 | mutate your own fix, not just the code you inherited | handoffs F1 |
| 2 | arm your own **remedy**: revert it to its pre-fix line, confirm the guarding test reddens | memories F4 |
| 3 | revert your fix and confirm its own **new test** goes red | handoffs F17 |
| 4 | an arm score is a statement about your TESTS; the premise needs a different probe | handoffs F21 |
| 5 | a comment/docstring asserting a property is the **trigger to verify it**, not evidence of it | memories F10 |
| 6 | extend the rule from **ad-hoc** probes to **shipped** checks; a check must declare what it cannot see, and its FAIL arm must inject **absence** | issues finding 2 |
| 7 | a wait condition is a probe and owes rule 1's arm | handoffs F24 |
| 8 | a mechanism that hides a thing from listings makes "absent from listings" look like corroboration | handoffs F11 |

Sized against comparable existing sections in that file (a section with an
evidence table plus two paragraphs runs 16–24 lines), items 1–6 are **~110–130
lines**. Added to 180, the file lands at **~290–310 lines — 45–55% over the
200-line ceiling**, and `md-size-budgets.md` explicitly calls splitting-to-evade
"a non-reduction", so the file cannot simply be cut in two after the fact.

### 4.3 · The seam — and it is a real one, not a filing convenience

`probes-need-a-control-arm.md` today is about **arming a probe you write to
answer a question**. Items 1–6 above are about a different subject:
**arming the thing you produce** — your fix, your test, your comment, the check
you ship. The tell is that rule 2 ("arm the positive") is the *only* part of the
existing file those six attach to, and every one of them is about output rather
than about a question.

That is where the file already wants to divide, and the six findings are a
coherent unit on the far side of it.

**Recommendation: ONE new eager rule file — `arm-your-own-work.md`.**

| section | source finding(s) | ~lines |
|---|---|---|
| Why: a fix is unreviewed code (the 4 sub-shapes) | M1 (handoffs F1 + memories F4) | 26 |
| Revert the fix and watch its own test go red — one command, and the only probe that can catch this class | M12 (handoffs F17) | 20 |
| An arm score is about your TESTS, never the PREMISE | M11 (handoffs F21) | 22 |
| A shipped check must declare what it cannot see; its FAIL arm injects ABSENCE | M4a (handoffs F20 + issues 2) | 24 |
| A comment is a claim and owes the same arm as a gate | M5 (handoffs F16 + memories F10) | 20 |
| Applies to / See also | — | 14 |
| **total** | | **~126 lines, ~7,500 bytes** |

Well inside 200/24,000, and it **drains `probes-need-a-control-arm.md`
completely**: only items 7 and 8 remain there, as one-line amendments to rules 1
and 3 respectively — **~7 lines**, leaving that file at ~187/200 with 13 lines
spare.

**Honest cost, stated because a recommendation that hides it is not usable:** the
new file must be **eager**. Its trigger is a *behaviour* (you are about to apply
a fix), and `md-size-budgets.md`'s trigger test says only rules whose trigger IS
a file may be `paths:`-scoped. So it costs its full ~7,500 bytes at launch, every
session, forever. There is no scoped variant of this recommendation.

### 4.4 · Every RULE finding, with its destination shape and byte estimate

`NEW` = the new file · `SECTION` = a new `##`/`###` in a named existing file ·
`LINE` = a one-to-four-line amendment inside an existing section.

| id | shape | target file | ~lines | ~bytes | file after |
|---|---|---|---|---|---|
| M1 | NEW | `arm-your-own-work.md` | 26 | 1,550 | — |
| M12 | NEW | `arm-your-own-work.md` | 20 | 1,200 | — |
| M11 | NEW | `arm-your-own-work.md` | 22 | 1,300 | — |
| M4a | NEW | `arm-your-own-work.md` | 24 | 1,450 | — |
| M5 | NEW | `arm-your-own-work.md` | 20 | 1,200 | — |
| — | NEW | scaffolding (title/why/applies/see-also) | 14 | 800 | **126 / 7,500** |
| M21 | LINE | `probes-need-a-control-arm.md` rule 1 | 3 | 220 | |
| M8a | LINE | `probes-need-a-control-arm.md` rule 3 | 4 | 300 | **187 / 11,149** |
| M13a | SECTION | `verify-before-advancing.md` | 18 | 1,150 | |
| M10a | LINE | `verify-before-advancing.md` § Evidence discipline | 4 | 280 | **151 / 8,681** |
| M7a | SECTION | `clarify-before-acting.md` | 18 | 1,100 | |
| M19 | SECTION | `clarify-before-acting.md` | 16 | 1,000 | **126 / 6,645** |
| M17 | SECTION | `agent-report-persistence.md` | 16 | 1,000 | |
| M27a | LINE | `agent-report-persistence.md` (Workflow fan-outs) | 4 | 300 | **127 / 6,975** |
| M18 | LINE | `long-running-command-hangs.md` rule 4 | 10 | 700 | **103 / 5,776** |
| M20 | LINE | `agent-artifact-conventions.md` (receipt row) | 4 | 300 | |
| M22 | LINE | `agent-artifact-conventions.md` rule 5-adjacent | 5 | 350 | **93 / 6,132** |
| M14a | LINE | `zero-bash-logic.md` § Where the line falls | 8 | 550 | **69 / 3,374** |
| M9 | SECTION | `notepad-enforcement.md` | 18 | 1,100 | |
| M34 | SECTION | `notepad-enforcement.md` | 14 | 850 | |
| M36 | LINE | `notepad-enforcement.md` | 4 | 280 | |
| M28 | LINE | `notepad-enforcement.md` | 5 | 320 | |
| M29 | LINE | `notepad-enforcement.md` | 6 | 380 | **109 / 5,742** |

**No file exceeds its ceiling under this plan.** The tightest is
`probes-need-a-control-arm.md` at 187/200 — which is why items 1–6 must go to the
new file and not there.

### 4.5 · The total, and the decision it forces

```
new eager file            +7,500 bytes  (net new launch cost)
additions to 8 existing   +10,850 bytes
                          ───────────
total                     +18,350 bytes on a 100,810-byte eager base = +18.2%
                          ≈ +4,600 tokens per session, every session
```

**Two things the round must decide, and I will not decide them:**

1. **Is +18.2% acceptable?** It is the largest single expansion of the launch
   budget this repo has made. Nothing in the four reports costs it out.
2. **Should the RULE bucket be trimmed against §0.2?** Five of these 22
   additions target classes where a reader *measured* prose failing. The
   strongest candidates for demotion to ISSUE-only are **M8a** and **M21**
   (handoffs itself says of M8's class: *"this class is not fixed by more
   prose"*, and routes it to the `kb-probe` issue instead) and **M27a** (the
   `Workflow({name:…})` trap, where memories proposes a *grep-based gate* as the
   real remedy and the rule line as the secondary). Dropping those three saves
   ~820 bytes — small, and the point is the precedent, not the bytes.

`notepad-enforcement.md` is chosen over a second new file for the five
memory-store findings (M9, M34, M36, M28, M29) precisely to avoid a second net-new
launch cost: it already names **both** stores and already says "Both, every
time", so the division of labour belongs there. 62 → ~109 lines.

---

## 5. The master deduplicated finding list

**Destination taxonomy** (each finding carries exactly one):

- `RULE` — a recurring **judgement** failure → a `.claude/rules/` section. Sized
  in §4.4.
- `ISSUE` — a **mechanisable** fix with no existing ticket → a new GitHub issue.
- `BACKLOG` — a triage action on an **existing** issue (close / merge / rewrite).
- `CORRECTION` — a stale or wrong **durable record**, fixed in place.

**Verification column:** `PROBED` = an adversarial verifier independently
re-derived it · `READER` = single-slice reader confidence · `READER×N` = N
independent readers · `PROBED-REV` = a verifier **changed** the reader's answer.

**One constraint that shapes several CORRECTION rows.** Five corrections target
`/Users/rmanaloto/.claude/projects/…/memory/` (the auto-memory store). `do-not.md`
#11 forbids this repo editing anything outside the project, so those are **not**
repo commits — they are edits the session makes through its own memory mechanism.
Filing them as repo issues would produce tickets nothing in this repo can close.

### 5.1 · RULE (22)

| id | finding | slices | verif | shape → target |
|---|---|---|---|---|
| **M1** | A fix becomes the next round's defect. Four sub-shapes: removes a guard nobody re-armed · trades one failure for its mirror · makes the sequence unrunnable · raises a bound instead of removing it. The countermeasure that measurably worked is **mutating your own fix**, and no rule states it (control-armed). | handoffs 9 rounds · memories 6 memories | READER×2 | NEW → `arm-your-own-work.md` |
| **M4a** | A check the repo **ships** cannot see the thing it names; the loss happens past the gate while every gate is green. A check that samples its own output is structurally blind to what never entered it. | handoffs 4 rounds · issues 6 open issues | READER×2 | NEW → `arm-your-own-work.md` |
| **M5** | Prose asserts what the code does not do — worst form, a comment **defending** the choice that is the bug. The prose is what prevents the author's re-read and what disarms the next reviewer. | handoffs 7 rounds · memories 5 memories | READER×2 | NEW → `arm-your-own-work.md` |
| **M11** | A mutation-arm score is a statement about your **tests**, never about the **premise**. 17- and 21-arm sweeps were green over a wrong ownership rule; neither was reachable by adding arms. | handoffs 5 rounds | READER | NEW → `arm-your-own-work.md` |
| **M12** | A test written alongside its fix cannot fail, and **neither a review lane nor an arm sweep can see it**. Revert the fix, watch its own test go red — one command. | handoffs 5 rounds | READER | NEW → `arm-your-own-work.md` |
| **M7a** | A ticket's body, criteria and justification are three separate claims; **6 of 6** tickets in the #143 chain needed an amendment, twice to the ticket's own premise. Measure each against real data; amend the loser, never pick one silently. | handoffs 6 tickets · issues §3 · currency B1 | READER×3 | SECTION → `clarify-before-acting.md` |
| **M19** | A killed theory gets re-proposed and a settled decision re-litigated — one theory retracted 3×, a "Banned answers" table needed, rotation carried 8 consecutive handoffs. Re-opening needs a **NEW discriminator**; re-raising a deferral needs a **NEW fact**. | handoffs 10+ handoffs | READER | SECTION → `clarify-before-acting.md` |
| **M13a** | A green gate is only evidence about files **inside its scope**. `Fetching staged files (0 files)` is a SKIP, not a pass. Name the gate's scope and show the path is inside it before citing it. | handoffs 6 gates | READER | SECTION → `verify-before-advancing.md` |
| **M10a** | A log you did not watch appear is an **inherited number**, not a measurement — a file-recorded `rc` beats a pipe only if the file is known to belong to this run. | handoffs 5 rounds | READER | LINE → `verify-before-advancing.md` § Evidence discipline |
| **M17** | An agent's notification is not its artifact — in both directions: reports declared "killed" that had landed, "complete" agents that wrote nothing, and a workflow with **no filesystem access at all**. Poll the artifact. | handoffs 7 rounds | READER | SECTION → `agent-report-persistence.md` |
| **M27a** | Invoke a saved workflow by `scriptPath`, never by `name` — `name` resolves to a stale cached copy and silently runs pre-edit code. | memories 3 memories | READER | LINE → `agent-report-persistence.md` |
| **M18** | `pgrep`/`ps` matched the ChatGPT desktop app or a **sibling repo's session**; `long-running-command-hangs.md` rule 4 would have had you kill it. The string is not ownership — the command PATH, parent, or output path is. Plus: a single `%CPU` sample is not a stall. | handoffs 5 rounds | READER | LINE → `long-running-command-hangs.md` rule 4 |
| **M20** | "Close the loop BEFORE `kb-ship`" was read as "before landing" — one irreversible step out, two commits stranded. State the **mechanism** ("the push is what fixes the PR head"), never the ordinal. | handoffs 3 rounds | READER | LINE → `agent-artifact-conventions.md` receipt row |
| **M22** | A command destroyed the only copy of an artifact (`git checkout --`, `git mv` into a gitignored path, `rm` with a SHA glob). Verify a move/copy by **reading the destination**, never by the rc of the command that wrote it. | handoffs 3 rounds | READER | LINE → `agent-artifact-conventions.md` |
| **M21** | A wait/verification condition is a probe and owes rule 1's arm: it must be verifiably **FALSE before** the work starts. Got wrong twice in one hour. | handoffs 4 occurrences | READER | LINE → `probes-need-a-control-arm.md` rule 1 |
| **M8a** | A mechanism that hides a thing from listings makes "absent from listings" read as **corroborating evidence** — two independent-seeming probes that are actually one probe. | handoffs (F11 sub-case) | READER | LINE → `probes-need-a-control-arm.md` rule 3 |
| **M14a** | A probe whose answer you will **report** is logic, not a seam, and belongs in python. `zero-bash-logic.md`'s own seam/logic table simply never considered probes. | handoffs 8 occurrences | READER | LINE → `zero-bash-logic.md` § Where the line falls |
| **M9** | The committed durable stores have **no reviewer**, and there are two of them with converging content and no stated division of labour (121 + 107 records). `graphify-out/memory/**` is `review.EXEMPT_PATHS`; the auto-memory store is outside review entirely. A fact stored twice is a fact that will disagree with itself. | issues · currency · memories | READER×3 | SECTION → `notepad-enforcement.md` |
| **M34** | An **immutable** record cannot carry a **mutable** pointer. 27 gate questions across 14 of 24 run pages read as open when zero are; four memories each claim "read first" and at most one can be true. Point at a location whose newest entry is authoritative; never mint a new claimant per round. | currency A4+B2 | READER | SECTION → `notepad-enforcement.md` |
| **M36** | A memory **slug** that encodes a temporal status goes stale and **cannot be corrected** — renaming breaks every `[[link]]`. Slugs name the *lesson*, not the *status*; the lesson-shaped slugs have not aged at all. | currency 3 slugs | READER | LINE → `notepad-enforcement.md` |
| **M28** | `dead_end` has **never** been used in 121 memories, so LESSONS.md's Contested/recency machinery is inert and abandoned approaches are all filed `useful`. The distinction is *did the approach survive*, not *was the session productive*. | memories 0/121 | READER | LINE → `notepad-enforcement.md` (or the `kb-curator` MANDATE) |
| **M29** | The corpus records **building** the tool, not **using** it — only **4 of 121** memories mention `kb-query`, on a repo whose stated single purpose is querying. `kb-remember` is tied to the ingestion cycle and nothing ties it to a query. Record a memory for a query that came back *bad*. | memories 4/121 | READER | LINE → `notepad-enforcement.md` |

> **M29 corroborates M23** (query-first compliance measured 2 of 7) from a
> different slice. They are not merged — M29 is about what gets *recorded*, M23
> about what gets *done*, and their fixes differ — but a reader should see them
> together: **the repo's founding premise is both under-practised and
> under-recorded, measured independently.**

### 5.2 · ISSUE (15) — mechanisable, no existing ticket

| id | finding | slices | verif | the issue to file |
|---|---|---|---|---|
| **M2** | `kb-land` leaves you on `main`; ≥6 commits landed on the default branch across 4 sessions. `do-not.md` #7 was **eagerly in context the whole time** and nothing asked the question. A structural seam in the land→next-task transition, currently fixed by convention only. | handoffs · memories · issues | READER×3 | `kb_setup.pr.land` prints one line after syncing (or cuts a dated branch); belt-and-braces is a `hook_guard` `_REDIRECT` on `git commit` while HEAD is `main`. **Cheapest high-recurrence fix in the pass.** |
| **M25** | `kb-remember` records `outcome: corrected` with no `correction:`, so **12 of 23** corrections render as empty bullets in LESSONS.md — and `mise.toml:487`, the advertised interface, **never mentions `--correction`**. The empties cluster in the *recent* half. | memories | READER | Fail closed: require `--correction` when `--outcome corrected` (or fall back to the body's `## Outcome`), and fix `mise.toml:487`. **One fix with M26.** |
| **M26** | `source_nodes` has not been recorded since July — **23/121 overall, 0 of 57 August memories** — so `.graphify_learning.json`, the graph-side half of `kb-reflect`, is fed by nothing and every recent lesson lands in `Uncategorized`. | memories | READER | Same fail-closed shape on `--nodes`. **Carries the one surviving caveat from `refute-lessons-gitignored.md`: the overlay genuinely IS graph-dependent, so this is the half that does not regenerate from committed inputs.** |
| **M15** | Live credentials printed into transcripts **three times**, by two agents and the main session, the last one **after** the prohibition was written into every lane prompt. Aggravated by a preserve-listed research report that recommends the exact command. | handoffs | READER | `hook_guard` `_REDIRECT` denying `mise env --values/--json/--json-extended`, printing the safe form. PreToolUse-deny reaches subagents, which is where two of the three leaks happened. |
| **M16** | "Never read a number from a `mise run` log" appears in **9 handoffs over 10 days** and still bit twice in one day. The cause is settled and out of reach (the user's `_.fnox-env`), so the advice is correct — nine handoffs telling a reader to remember something is a **missing affordance**. | handoffs | READER | Give every figure-producing `kb-*` task a documented redaction-free read path, stated **at the point of use**. Precedent: `mise-tasks-only.md` already carries exactly one such row, for `session-state`. |
| **M13b** | No test asserts that each tracked path class is opened by ≥1 gate. | handoffs | READER | Path-coverage test over `sources/**`, `graphify-out/memory/**`, `docs/goals/*-goal.md`, `docs/research/**`. Generalises the two that already work: `tests/test_gitleaks_scope.py` and `tests/test_hk_scanner_scope.py`. |
| **M14b** | Every probe in this repo is a shell one-liner, and **eight** were defeated by zsh (word-splitting ×3, MULTIOS, `:r`, an unquoted glob). Every one produced a **false negative**. | handoffs | READER | `kb-probe` — a python escape hatch (`uv run kb-setup probe <file.py>`). **This is also M8's mechanisable half**: handoffs explicitly routes the bounded-probe class here rather than to a seventh prose amendment. |
| **M10b** | `CLAUDE.md` — the most-read file in the repo — carried a **3×-wrong** graph size and a stale prose-node count at the same time. | handoffs · memories · currency | READER×3 | Figure-freshness markers (`<!-- measured: YYYY-MM-DD -->`) plus a `kb_setup` check that re-derives the cheap ones from `graph.json` / `.currency-stamp.json`. `CLAUDE.md` already does this by hand for two figures. |
| **M24** | Report promotion to `docs/research/reports/` has been deferred **three rounds running**, and the reason is structural, not laziness: `docs/research/**` is not in `review.EXEMPT_PATHS`, so promoting inside the reviewed round moves HEAD past its own receipt. | handoffs | READER | Same shape as the #66 fix for `graphify-out/memory/**`: exempt a verbatim promotion of an already-reviewed `.agent/` report, or teach `kb-ship` to accept it. |
| **M30** | `kb-validate-chunks` still cannot see a chunk with **zero edges** or a high orphan count — the 2026-07-27 lesson named the check and it was never built. **Latent, and the reader says so**: worst committed chunk today is 2/20 orphans, none zero-edge, so the practice has substituted for the gate. | memories | READER | Add edge-count and orphan-rate checks to `chunks.validate()`. Ranked as latent, not bleeding. |
| **M33** | Nothing gates a new `mise.toml` pin into `currency.toml`. **10 of 14 pins are untracked**, including `agnix` (hand-bumped 0.40.0 → 0.46.0 on 2026-08-06; the intervening 0.44.0 fixed rules rejecting `model: fable`) and both **self-updating** AI lanes (`agy` reported 1.1.10 from inside a 1.1.5 install dir). | currency | **PROBED** (the 4-of-14 denominator; see M32) | Assert every `[tools]` key either has a `currency.toml` block or appears in an explicit commented `untracked = [...]` allowlist. **The allowlist half is the point**: silence must become a recorded decision. |
| **M35** | 6 dangling `[[wikilinks]]` across 18 files; **4 target memories that exist** — 3 written from the human *title* instead of the *slug*, 1 a self-link with the wrong name. A dangling link is silent by design; this is the one defect class in that store with no reader at all. | currency | READER | A resolver check over the 107 slugs that separately flags any target case-folding to an existing **title** — the near-miss the rule cannot tolerate. (The 4 link *fixes* are CORRECTIONs; see §5.4.) |
| **M37** | Seven `docs/currency/README.md` rows render a **SKIP** with the word `clean` (`ffmpeg 8.1.2, not version-tracked: clean`). The qualifier is present so it is a rendering defect, not a false green — but it is the exact three-state collapse this engine's design names, in the row shape that occurs seven times. Control: the same engine renders other not-checked states as `skip` and "_No gate was evaluated_". | currency | READER | Use the existing SKIP vocabulary in the README verdict line. |
| **M38** | 14 README rows assert "nothing was found" with **no artifact a reader could check that against**. Link integrity is perfect in the direction usually checked (24 referenced, 24 present, 0 orphans **both** `comm` directions); the clean direction is unfalsifiable. | currency | READER | Write a `runs/` page for a clean run too. Same fix that worked for `kb-gates`: write the artifact unconditionally. |
| **M39** | Lockfile completeness has **no gate and no standalone issue** — `lockfile`/`mise.lock` appear in exactly two open issues, in both as a sub-bullet of a **round-scoped ticket that will close**. #184 records this as the **second** silent loss of the class (14 per-platform checksum blocks; previously 27 `conda_deps`), every gate green across both. | issues | READER | File it standalone before #184 closes and takes the question with it. |

### 5.3 · BACKLOG (18) — triage on existing issues

| id | action | issue(s) | slices | verif |
|---|---|---|---|---|
| **M40** | **Close #134 as COMPLETED — NOT "as refuted" — and re-file ask A1 FIRST.** See §3.1. The reader's rationale is false on the issue's current text and its commit citation is wrong. A1 (an hk step or `kb-ship` gate running `kb-validate-chunks`) is real, live, and tracked nowhere else. | #134 | issues | **PROBED-REV** |
| **M3** | Rewrite #160's criteria to carry the **four requirements** each throwaway harness re-derived: purge `__pycache__` + `PYTHONDONTWRITEBYTECODE=1` · anchor by reading the file, never a retyped literal · assert the mutant differs **at the intended line** · distinguish `rc=4` (collection error) from a real kill. Record the recurrence: handoffs counts **five** harnesses through 2026-08-06, memories counts **three** in a narrower window; the fifth "extracted the runner programmatically rather than restating it, which is the interim mitigation, not the fix". | #160 | handoffs · memories · issues | READER×3 |
| **M4b** | Generalise #198 beyond nodes: the merge-arithmetic assertion covers **node counts only**, while #191's own first instance was a **hyperedge-only** loss (11 → 8) with nodes untouched. Add the rebuild-vs-incremental diff as the routine control arm after any merge-machinery change — no gate runs it today. | #198 | handoffs | READER |
| **M6** | Consolidate the 12-issue ingestion cluster: merge **#10 into #200** (copying #10's JS-shell/SPA finding across first — the one thing #200 does not cover); close **#19** (body is literally `see session handoff`, and the handoff is gone) and **#21** (superseded by #203, which *is* #21's own preferred option); group **#122+#202+#201** under **#203**; re-parent **#16** and **#20**. | #10 #16 #19 #20 #21 #22 #122 #200 #201 #202 #203 #207 | handoffs · memories · issues | READER×3 |
| **M41** | Retitle #120 to the **upstream track only** (`prefix_graph_for_global` has no idempotence guard). Its local half is fixed — duplicate-prefix waste measures **0.00%**, id depth 1–2 not 1–22 — and #174's own text already calls it *"the retired #120 class"*. The current title asserts a fixed 41% waste is outstanding. | #120 | issues | READER |
| **M42** | Paste #129's refutation into **#106's body** and cross-link. #129 states *"#106's filed root cause is WRONG"* and carries the real one (a src-layout cross-root import-resolution defect, `~30 lines to repair locally`). Anyone opening the ticket **titled for the defect** currently gets the refuted diagnosis and no pointer to the fix. Cheapest real progress in the substrate-map cluster. | #106 #129 | issues | READER |
| **M43** | Narrow #110 to its **deletion arm alone**, citing #187 for adds/changes. Do **not** close it: #110's stated control arm was *"prove the diff reports a DELETION"*, and #187 demonstrates only adds and changes. | #110 #187 | issues | READER |
| **M44** | Replace #21's and #22's trailing `Shipped in #18.` with `Mechanism shipped in #18; the work in this title is NOT done.` Verified: `_UPSTREAM_RULES` at `fetch.py:272-275` still maps exactly **three** hosts. A skim-triage closes both wrongly — the M7 shape, sitting on the two oldest issues in the backlog. | #21 #22 | issues | READER |
| **M45** | Merge **#202 into #122** — same live defect (`fetch.py:423` unchanged), filed 4 days apart; #122 is strictly broader (it also covers the `.gitignore` half that leaves `sources/<name>.md` tracked). | #122 #202 | issues | READER |
| **M46** | Strike **ask 3 from #205** — the "live trap" is disproven: `--idf` **does** honour `--graph` (75,037 nodes from `study-graph.json` vs 4,170 from `graph-prose.json`, disjoint top hits; `graphify_ops.py:516` documents that unknown flags are *rejected, never ignored*). Asks 1 and 2 are real and unaddressed. | #205 | issues | READER |
| **M47** | Delete #150's `Blocked by` block — all three blockers (#147/#148/#149) are CLOSED — and the duplicated `#149`. Note: unblocked ≠ scheduled; the caller's own memory records #150 as *not next*. | #150 | issues | READER |
| **M48** | Retitle **#118** to the measured `~28.2M for 169 files` and strike the superseded `~24M` and `~134M` blocks. The body already says *"Do not quote 24M again"* while **the title still asks about 24M**, and a backlog grep surfaces `134M` as a live claim. | #118 | issues | READER |
| **M23** | Comment on **#117**: the missing piece is the ongoing **measurement**, not the enforcement. A session-scoped counter of "graph-answerable questions asked" vs "graph queried first" is what turned this from folklore into **2 of 7**, and nothing produces it on an ongoing basis. #117 is blocked on #132 and the blocker chain has stalled it while compliance stays measured-low. | #117 #132 | handoffs | READER |
| **M27b** | #13 (`Workflow({name:…})` stale cache) is OPEN and has been walked into **twice more since it was filed** — both times as *documentation* in a rider/skill, which would have shipped a false HARNESS-RAN. One shipped: the harness ran 31 agents and 4,589,913 subagent tokens and wrote nothing. Add the grep-based gate over `.claude/workflows/**` and skill prose for `Workflow({name:` — both recurrences were textual. | #13 | memories | READER |
| **M49** | Four issues cannot be acted on because "done" is undefined: **#19** (`see session handoff`), **#23** (self-describes as *"mostly moot"*, no criteria), **#129** (a research note with no acceptance section), **#142** (correctly a decision request waiting on Ray). Close #19 and #23; give #129 criteria or convert it. | #19 #23 #129 #142 | issues | READER |
| **M50** | **#111 is the cheapest unblock in the whole backlog** — one ~10-minute `GRAPHIFY_OUT` probe releasing #115. #114 is the deepest blocking node and its other blockers are heavier; #110 is now answered (M43). | #111 #115 | issues | READER |
| **M51** | #137 carries a literal **`#?`** placeholder cross-reference. It cannot be repaired by number — the referenced finding lives in work-memory (`a-task-that-exits-0-passes-every-check`), not in any issue. Point at the memory or file it. | #137 | issues | READER |
| **M52** | **Triage the 2026-07-24 cohort.** Exactly **10 open issues** have not been updated since 2026-07-26 (#10,12,13,14,16,19,20,21,22,23) — the only label group with zero movement in 13 days; every other cohort has been revisited. **The cost is measured, not speculative:** #200 and #203 are full re-derivations of #10 and #21, twelve days later, because the first pair was never triaged. | 10 issues | issues | READER |

### 5.4 · CORRECTION (7) — a durable record that is wrong

| id | record | correction | verif |
|---|---|---|---|
| **M32** | `~/.claude/…/memory/currency-tracks-half-the-pins.md` | Its `description` ("tracks 7 of 14"), its **filename slug** (*"half"* — it is under a third), and its body phrase "the untracked half" (really 10 of 14 ≈ 71%). The body's *declares 7 / pins 14* sentence is correct and stays; the agnix lesson and the #204 content are untouched. **Auto-memory store — edit via the memory mechanism, not a repo commit.** | **PROBED** (`refuted: false`, 4 arms incl. a mutant that moves the count to 5) |
| **M55** | `~/.claude/…/memory/roster-round-landed.md:3` | The `description:` field — **the field recall selects on** — says "#198 + the 12 overlaps are still the next round" while the body says "**#198 is therefore NOT next**". A session recalling on description alone learns the reversed ordering and never sees the reversal. Control arm that this is file-level, not store-wide: `MEMORY.md:107` states it correctly. **Auto-memory store.** | READER |
| **M54** | `~/.claude/…/memory/substrate-map-is-the-active-thread.md:3` | "as of 2026-08-03 the IMMEDIATE work is spec #143 / tickets #144-#150" — #145/#146/#147/#149 are **CLOSED** and #150 is recorded as not-next. The memory *carries its condition*, which is why this is cheap; what it cannot do is notice the condition expired, and its index line drops the date entirely. **Not claimed:** the same description's "17 open sub-issues" figure, which the reader flags as un-re-derived rather than reporting as wrong. **Auto-memory store.** | READER |
| **M35c** | 4 `[[wikilink]]` targets across 5 files | `a-cold-lane-runs-the-code` → `cold-lane-runs-the-code` (3 files) · `a-cold-review-catches-what-you-reasoned-past` → `cold-review-catches-reasoned-past` · `a-validator-that-works-can-sit-above-a-total-loss` → `loss-happens-past-the-gate` · `kb-first-then-dotfiles-parity` → the file's own name. **Auto-memory store.** The other 2 danglers are legitimate (a `.claude/rules/` filename, and a claim `MEMORY.md:4` records as refuted). | READER |
| **M53** | `docs/currency/runs/2026-08-06-*.md` | 3 of 3 gate questions unanswered; **two were answered in full on the previous run** with nothing upstream moved (same `v0.2.0`, same pinned SHA), and the third was resolved ~2h later by a build the immutable page cannot see (`.currency-stamp.json` `built_at 2026-08-06T20:11:02`, all three views' `graph` fingerprint identical to the live one). The record reads as two open questions when zero are. **In-repo.** The general form is M34. | READER |
| **M31** | `reflect-memories.md` finding F2 / rank 10 | *"…so a fresh clone has no lessons until someone **rebuilds the graph**"* — the causal half and the consequence are **REFUTED** (§3.2): `graph_path` is optional, both loaders fail safe to `None`, and `LESSONS.md` regenerates from the 121 committed memories by `kb-reflect` alone. The gitignore half stands. **Not a defect** — the surviving caveats (a degraded flat file; the overlay genuinely graph-dependent) are folded into M26. | **PROBED-REV** |
| **M58** | `reflect-memories.md` scope note | The path correction (`graphify-out/reflections/`, not `…/memory/reflections/`) is **right**; the accompanying implication that documents state the wrong path is **REFUTED** — `grep -rn 'memory/reflections'` returns zero against a control of 14 files naming the correct path. Several docs write it *relative* immediately after naming `memory/`, which reads as nested. Worth disambiguating to absolute; **no document is wrong**. | **PROBED-REV** |

### 5.5 · DROPPED (2) — with the reason

| id | finding | why dropped |
|---|---|---|
| **M56** | currency rank 12 — "the briefed 107-index-lines vs 108-files discrepancy" | **There is no discrepancy.** The 108th file is `MEMORY.md` itself; the bijection is exact in both directions, `uniq -d` empty, and frontmatter is 107/107 clean. The reader is right to report it, and it is right that it produces no action. Kept visible because *"108 vs 107" is precisely the shape that gets acted on* — a session trusting the framing would have hunted an orphan that does not exist. |
| **M57** | memories rank 14 — LESSONS.md's mtime is older than its two newest inputs | **Explicitly a warning against a false positive, not a finding.** The content contains both newest questions, so the mtime ordering is not evidence of staleness. This is the same trap `tool-currency-and-native-first.md` already records: an ordering rule *"was built, run, and refuted by its own first output"*. No action; the note itself is the value. |

### 5.6 · Not a finding, but do not lose it — what measurably WORKED

`reflect-handoffs.md` F25 is unranked and would vanish in a failures-only
synthesis, which would mis-state the trend. Three practices measurably fixed a
recurring problem inside the 11-day window:

- **"Branch first" as the handoff's FIRST ACTION** stopped M2 recurring from
  `session-2026-08-04-c` onward. The convention works — which is the argument
  *for* mechanising it (M2), since it is one forgetful session from returning.
- **The two-round review bound** replaced a five-round non-convergence that cost
  **2.93M tokens and was reverted**.
- **A MUTATING lane brief beats a reading one** — round 2 returned 9 findings /
  3 P1 over code **25 green arms had just certified**. Recorded verbatim as the
  thread to pull if the one-lane bound is ever revisited: *"the brief, not a
  second lane."*

---

## 6. Coverage map — every one of the 66 raw findings

Nothing is silently absorbed. `→` gives the master id; a finding appearing under
two ids was **split** (a JUDGEMENT half and a MECHANISABLE half), never
duplicated.

### `reflect-handoffs.md` — 22/22

| rank | raw finding | → |
|---|---|---|
| 1 | mutation harness re-authored, `.pyc` staleness | M3 |
| 2 | a fix becomes the next round's defect | M1 |
| 3 | "never read a number from a `mise run` log", 9 handoffs | M16 |
| 4 | a bounded probe reported as an answer | M8a + M14b |
| 5 | zsh one-liner probes, 8 false negatives | M14a + M14b |
| 6 | prose asserts what the code does not do | M5 |
| 7 | ticket body / criteria / justification disagree | M7a |
| 8 | an agent's notification is not its artifact | M17 |
| 9 | the loss happens PAST the gate | M4a + M4b |
| 10 | a green gate that examined nothing | M13a + M13b |
| 11 | `pgrep`/`ps` matched someone else's process | M18 |
| 12 | live credentials in transcripts ×3 | M15 |
| 13 | killed theory re-proposed / decision re-litigated | M19 |
| 14 | arms measure the TESTS, never the PREMISE | M11 |
| 15 | a test written alongside its fix cannot fail | M12 |
| 16 | `kb-land` leaves you on `main` | M2 |
| 17 | committed figures go stale, re-cited as measurements | M10a + M10b |
| 18 | structurally-correct deferral that never resolves | M24 |
| 19 | "close the loop BEFORE `kb-ship`" read as "before landing" | M20 |
| 20 | a wait condition is a probe | M21 |
| 21 | a command destroyed the only copy of an artifact | M22 |
| 22 | query-first compliance measured 2 of 7 | M23 |

### `reflect-memories.md` — 15/15

| rank | raw finding | → |
|---|---|---|
| 1 | `corrected` with no `correction:`, 12 of 23 empty | M25 |
| 2 | `source_nodes` unrecorded since July, 0 of 57 | M26 |
| 3 | "a fix breeds the next round's defect", no rule states it | M1 |
| 4 | `kb-add` 12,000-char truncation, proven casualty | M6 |
| 5 | `__pycache__` defect across three harnesses | M3 |
| 6 | "prose agreeing with itself is not verification" | M5 |
| 7 | records building the tool, not using it (4 of 121) | M29 |
| 8 | `Workflow({name:…})` stale cache, ×3 | M27a + M27b |
| 9 | `dead_end` never used in 121 memories | M28 |
| 10 | LESSONS.md is gitignored | **M31 — PARTIALLY REFUTED, dropped as a defect** |
| 11 | `kb-land` says nothing about `main` | M2 |
| 12 | `kb-validate-chunks` blind to zero-edge chunks | M30 |
| 13 | the July reflect memory's "(NOT installed)" is 11 releases stale | M10a *(instance; no separate action — the reader classifies it stale-not-wrong because it carries its condition)* |
| 14 | LESSONS.md's mtime is older than its inputs | **M57 — DROPPED, it is a warning against a false positive** |
| 15 | the brief's `LESSONS.md` path was wrong | M58 |

### `reflect-issues.md` — 17/17 (+1 promoted)

| rank | raw finding | → |
|---|---|---|
| 1 | #134 refuted, remedy caused data loss | **M40 — REFUTED as stated; close as COMPLETED** |
| 2 | the control-arm rule scopes itself to ad-hoc probes | M4a |
| 3 | #120's local half fixed; title asserts 41% waste | M41 |
| 4 | the 12 ingestion issues are one defect, re-derived | M6 |
| 5 | #106's root cause asserted wrong inside #129 | M42 |
| 6 | lockfile completeness: no gate, no standalone issue | M39 |
| 7 | #110 answered by #187 except the deletion arm | M43 |
| 8 | #21/#22 end `Shipped in #18.` while undone | M44 |
| 9 | #122 and #202 are the same defect | M45 |
| 10 | #205's live trap disproven | M46 |
| 11 | `kb-land` untracked in the issue backlog | M2 |
| 12 | #150 unblocked but reads blocked | M47 |
| 13 | #118 carries superseded token figures | M48 |
| 14 | work-memory is review-exempt, nothing reviews it | M9 |
| 15 | four issues never say what "done" is | M49 |
| 16 | #111 is the cheapest unblock | M50 |
| 17 | #137's literal `#?` placeholder | M51 |
| §4 *(unranked)* | the 2026-07-24 cohort, 10 issues untouched 13 days | **M52 — promoted; the measured cost of not triaging** |

### `reflect-currency.md` — 12/12

| rank | raw finding | → |
|---|---|---|
| 1 | `roster-round-landed`'s description contradicts its body | M55 |
| 2 | `currency.toml` tracks 4 of 14, not 7 of 14 | **M32 — CONFIRMED at probe grade** |
| 3 | nothing gates a new mise pin into `currency.toml` | M33 |
| 4 | an immutable artifact cannot carry a mutable pointer | M34 |
| 5 | the newest run leaves 3 of 3 questions unanswered | M53 |
| 6 | two memory stores, no division of labour | M9 |
| 7 | 6 dangling `[[wikilinks]]`, 4 resolvable | M35 + M35c |
| 8 | `substrate-map`'s "immediate work" is stale | M54 |
| 9 | ffmpeg SKIP rendered with the word "clean" | M37 |
| 10 | three slugs encode a status their content retracts | M36 |
| 11 | 14 clean rows with no checkable artifact | M38 |
| 12 | the "107 vs 108" discrepancy | **M56 — DROPPED, it does not exist** |

**66 raw → 64 master entries.** Ten merges collapse 23 raw findings into 10; six
splits expand 6 into 12; 2 are dropped with a reason. No finding is unmapped.

---

## 7. Top 10 of the whole pass

Ranked by **recurrence × cost**, not by how interesting. "Recurrence" is the
widest count any single slice measured (never summed across slices); "cost" is
what the corpus or the round actually lost.

| # | finding | recurrence | what it cost | id | dest |
|---|---|---|---|---|---|
| 1 | **A check the repo ships cannot see the thing it names — the loss happens past the gate.** The validator ran, opened the right artifact, and was structurally blind. "A check verified only on what it can see is decoration on the part it cannot." | 4 rounds · 6 open issues · **2 slices** | Real corpus loss, four times, with **every gate green** — 3 hyperedges, 72 nodes of a source, and a 46%-truncated article. Detected only by merge-line arithmetic, "for the third round running". | M4a / M4b | RULE + BACKLOG |
| 2 | **The ingestion path loses content silently, and the defect was re-derived from scratch after 12 days.** `markdown[:12000]`, no boilerplate removal, plus `kb-fetch`'s second loss class. | 12 issues · 2 memories · **3 slices** | One **proven** casualty at 54% of its article, 0 of 17 concepts past the 60% mark. Twelve days and a full re-derivation (#200/#203 = #10/#21) because ten tickets sat untriaged. Corpus integrity — `do-not.md` #6 promises reproducibility a half-ingested source silently breaks. | M6 | BACKLOG |
| 3 | **A fix becomes the next round's defect, and no rule says so.** The countermeasure that measurably worked is mutating your **own** fix — not another review lane. | 9 rounds · 6 memories · **2 slices** | The reason review rounds do not converge. One five-round loop cost **2.93M tokens and was reverted**. Control-armed: zero hits for this lesson across all 22 rule files. | M1 | RULE (new file) |
| 4 | **The mutation harness is re-authored every round and re-acquires the same defect.** A same-size mutation is served from a stale `.pyc`; CPython invalidates on `(mtime, size)` and a line swap changes neither. | **5 harnesses** · 3 slices | The third harness hit it **after a committed report predicted it verbatim**. The severity is asymmetric and the corpus names it: a false SURVIVAL makes you look, the same mechanism produces a false **DEATH**, "which makes an entire run worthless while reading green". | M3 | BACKLOG (#160) |
| 5 | **`kb-land` leaves you on `main`, and the next commit lands there.** A structural seam in the land→next-task transition. | 4 sessions · **3 slices** | ≥6 commits on the default branch, plus 2 prior in the sibling repo; recoverable only because nothing had been pushed. `do-not.md` #7 was **eagerly in context the whole time — nothing asked the question.** Cheapest fix in the pass: one printed line. | M2 | ISSUE |
| 6 | **The self-improvement loop is degrading while every gate stays green.** `kb-remember` drops `correction:` (12 of 23 render as empty bullets) and `--nodes` (0 of 57 August memories), so the graph-side overlay is fed by nothing and every recent lesson lands in `Uncategorized`. | 12/23 · 0/57 | The repo's **stated purpose**. The advertised interface at `mise.toml:487` never mentions `--correction`, so every caller following the documented contract produces a content-free correction — and the empties cluster in the *recent, hardest-won* half. | M25 / M26 | ISSUE (one fix) |
| 7 | **A bounded probe reported as an answer**, where the bound was a token spelling, a `--limit`, a `-k` selector, a regex anchor, or a pinned clone. | 6 rounds · **3 slices, incl. a live near-miss inside this pass** | Every instance a **false negative** — the expensive direction. The near-miss: searching for #134's own node ids returns zero because the namespace was renamed `graphify_*` → `gfyarch_*`. handoffs' own verdict: *"this class is not fixed by more prose."* | M8a / M14b | RULE line + ISSUE |
| 8 | **One durable record states two different things, and the reader picks one silently.** | **6 of 6** tickets amended · **3 slices** (tickets, issues, a memory) | #149's body and criterion 1 stated different rules; building the criterion **"relocated the ticket's own harm instead of removing it"** and refuses 8 of 21 branches. In a memory, the contradicted field is `description:` — *the field recall selects on*. | M7a | RULE |
| 9 | **Live credentials printed into transcripts three times — the last one after the prohibition was in every lane prompt.** | 3 leaks / 4 handoffs | Live AWS keys and API tokens in transcripts, by two agents and the main session, "despite knowing better". Aggravated: a **preserve-listed** research report recommends the exact command, so the instruction cannot be edited out. The definition of a control markdown cannot hold. | M15 | ISSUE |
| 10 | **Prose asserts what the code does not do — and the worst form defends the bug.** | 7 rounds · 5 memories · **2 slices** | *"A reviewer given that rationale would have nodded."* A docstring explaining that lexical containment was **deliberate**, walked through by a symlink the next round; a rule file glossing `dirty` with **inverted polarity** on the very field added to prevent a false reading. | M5 | RULE (new file) |

**Two things a five-minute reader should also know, which are not recurrences and
so do not belong in the table above:**

- **The pass's own near-miss (M40).** A reader's #1 recommended action was
  refuted by the verifier. Do not act on §5.3 row M40 as the reader wrote it —
  close #134 as **COMPLETED**, and re-file its ask A1 first or the gap loses its
  only tracked record.
- **The budget decision (§4.5).** The RULE bucket as proposed is **+18.2%** on
  the eager launch budget. It fits only because of one new file; it does not fit
  into `probes-need-a-control-arm.md`, which three readers independently wanted
  to extend and which has **20 lines** of headroom.

---

## 8. Tallies

### Destinations

| destination | count |
|---|---|
| **RULE** | **22** |
| **ISSUE** | **15** |
| **BACKLOG** | **18** |
| **CORRECTION** | **7** |
| DROPPED (with reason) | 2 |
| **total master entries** | **64** (from 66 raw) |

RULE breakdown by shape: **1 NEW file** (5 sections) · **5 SECTIONs** in existing
files · **12 LINE amendments** · plus 4 scaffolding/see-also edits. Target files:
`arm-your-own-work.md` (new), `notepad-enforcement.md` (5),
`clarify-before-acting.md` (2), `verify-before-advancing.md` (2),
`agent-report-persistence.md` (2), `agent-artifact-conventions.md` (2),
`probes-need-a-control-arm.md` (2), `long-running-command-hangs.md` (1),
`zero-bash-logic.md` (1).

BACKLOG breakdown: **5 closes/merges** (#134, #19, #21, #202→#122, #23) ·
**8 criteria rewrites** (#120, #110, #106, #205, #21/#22, #150, #118, #160) ·
**5 comments/re-parents** (#117, #13, #198, #111, the 2026-07-24 cohort).

### Verification

| status | count | note |
|---|---|---|
| **verified — confirmed** | **1** | M32 (`4 of 14`), `refuted: false`, 4 arms |
| **verified — reader's answer changed** | **3** | M40 (close-as-refuted → close-as-completed), M31 (defect → not a defect), M58 (companion claim refuted) |
| **unverified** (reader confidence only) | **60** | everything else |

**3 of 66 raw findings (4.5%) were adversarially verified**, and **2 of those 3
changed the answer** — a 67% hit rate on the sample. That is a strong argument
for verifying more of the 60, and a strong argument against treating any
unverified row here as settled. Per the brief's own test: refutations did occur,
so the verifier ran; the concern is coverage, not execution.

### Convergence

| independent slices | findings |
|---|---|
| 3 slices | **6** — M2, M3, M6, M7a, M9, M10 |
| 2 slices | **4** — M1, M4, M5, M8 (M8's third route is a verifier, not a reader) |
| 1 slice | 54 |

---

## 9. Bounds on this synthesis

Stated plainly, because a synthesis with no bounds is an opinion.

1. **I did not re-verify any reader's claim, by instruction.** Every `READER`-
   tagged row is exactly as strong as the report it came from, and those four
   reports had different corpora, different counting units, and non-comparable
   confidence. The verification tally in §8 is the honest picture: 4.5% probed.
2. **Recurrence counts are of what the corpora RECORD.** Handoffs are written by
   the agent that made the mistake; issues are what someone bothered to file;
   memories are what someone chose to remember. Every rate here is a **floor**.
   The single measured compliance rate in the whole pass is query-first's
   **2 of 7** (M23).
3. **The byte estimates in §4.4 are estimates**, sized against comparable
   existing sections in the same files. They are not measurements of text that
   exists. The *ceilings* and *current sizes* in §4.0–4.1 are measurements, taken
   2026-08-06 on `chore/post-209`; they will move with the next commit that
   touches `.claude/rules/`.
4. **The brief's `~120,305 bytes` figure did not reproduce** under any of three
   denominators I tried, and I do not know what it counted. I used my own
   re-derived 100,810 (eager rules only) and said so rather than carrying a
   number I could not reconstruct.
5. **Five CORRECTION rows target a store this repo must not write** (`do-not.md`
   #11). They are actionable by the session's memory mechanism, not by any commit
   here. A round that files them as repo issues will produce tickets nothing in
   this repo can close.
6. **`.agent/` is gitignored**, so this report is one `git clean -xdf` from gone.
   Per `agent-report-persistence.md` rule 1b, the durable copy belongs under
   `docs/research/reports/` — which is itself **M24**, the promotion debt this
   pass found deferred three rounds for a structural reason.
7. **One count I carried without re-deriving:** `reflect-issues.md`'s "71 open /
   57 closed / 128 total". `reflect-currency.md` independently reports the same
   figures from its own `gh issue list --state all --limit 250`, which is two
   routes agreeing — but both are the same tool on the same day, so it is
   corroboration, not independence.

## GitHub repos touched

I fetched nothing. Every source I read is a local file under
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/`
and `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/`. The
list below is the **union carried forward from the seven input reports'** own
enumerations, recorded here so the source backlog stays greppable from one place
(`research-repo-enumeration.md`) — **not independently consulted by me**.

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the subject of every input report; issues, chunks, commits and `python/src/kb_setup/**` cited throughout.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the pinned 0.9.34 tool; `reflect.py`, `cli.py`, `ingest.py`, `extract.py` read by the readers and by `refute-lessons-gitignored.md`.
- [jdx/mise](https://github.com/jdx/mise) — release notes quoted in `docs/currency/runs/2026-08-05-mise.md`; cited by `reflect-currency.md` and `reflect-issues.md`.
- [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) — the `source_only` currency entry; v0.2.0 notes as quoted in the skillopt run pages.
- [agent-sh/agnix](https://github.com/agent-sh/agnix) — the untracked pin in M33 (`mise.toml:52`), six versions stale invisibly.
- [openai/codex](https://github.com/openai/codex) — an untracked, self-updating lane (M33).
- [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli) — the other untracked, self-updating lane (M33); `agy` reported 1.1.10 from inside a 1.1.5 install dir.
