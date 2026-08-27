# The Claude↔Codex handoff — what is fragile, what is slow, and where scarce Fable buys something

**Date:** 2026-08-27 · **Phase:** P4 of the Aggregated round · **Method:** the
`aggregated-research` skill, run on Ray's restated question. Primary evidence is
this repo's own 159 cross-family review reports and 235 lane reports; the
published literature is secondary and is labelled as such.

## Answer

**The transport is not slow because the models are slow. It is slow because
finished work sits undelivered.** In the one round measured end to end, a lane's
full run was **~35 minutes** and the round lost **222.4 minutes — 38.7% of its
574.3-minute span — to dead time with lanes already finished**. That is a
**6.4 : 1** ratio of delivery cost to recoverable lane work.

**And it is fragile in a way nobody can audit**: 150 of 159 cross-family review
reports are named `cold`, with only 2 naming codex, because `report_path` strips
the `:variant`. **For 157 of 159 reviews the artifact cannot tell you which model
family reviewed the code** — the transport erases the one attribute the
cross-family policy exists to enforce.

The fix is not a roster. It is three changes to the interface, all of which use
primitives that already exist and are unused (see #553).

## 1. Latency — measured, decomposed

The four components the round's rider required be separated, kept separate.

| component | measured | source |
|---|---|---|
| **Model reasoning** | 31.4 min, 26.3 min ("ordinary lane latency"); ~35 min for one full cold run; 61.9 min / 205 tool uses / 133.5M cache-read for the round's most expensive lane | `session-review-2026-08-21b-result.txt`, `session-review-synthesis.md` |
| **Dispatch overhead** | **48 min** from orchestration-skill trigger (06:19:57Z) to first lane spawn (07:08:01Z) | `session-review-2026-08-21b-result.txt` |
| **Delivery / reap** | **222.4 min (3h42m) = 38.7% of the round** with lanes finished and undelivered; last idle notification **223.0 min** late; **117.5 min** across 16 hand-rolled poll loops; **50.7 min** idle on one unanswerable question | same, plus `refute-circles-*`, `circles-2026-08-21-6ae19ff6.md` |
| **Architect re-read** | **53,656 lines / 3.67 MB ≈ 0.9M tokens** to re-read one round's lane output — approximately one full context window | measured this session over both report directories |

**The lane protocol emits no clock.** 150 of 159 cold reports carry findings and
no timing at all; only 5/159 review reports and 75/235 agent reports record any
duration. Every figure above was reconstructed from transcripts *after the fact*.
A transport that cannot say how long it took cannot be optimised — this is the
first thing to fix, and it is one flag (`codex exec --json`, a JSONL event
stream, unused here).

*Probe note, recorded because it nearly became a finding:* an early sweep used
`[0-9]\+` under `grep -E`, where `\+` is a literal plus, and returned 0 for both
directories. Armed against a term known present, the real counts are 75 and 5.
A "no report records timing" claim would have been a broken probe.

## 2. Fragility — of the transport

Recorded kills, from the reports themselves:

- **600 s** — a codex review lane killed by watchdog, leaving an **empty `FINAL`**
  (`review-90be7169…-cold.md:154`). The report exists; the finding does not.
- **900 s** — a lane timed out mid-run and had to be resumed
  (`handoff-verify.md:262`).
- **The notification channel outliving nothing and the disk channel outliving
  everything** — this session's own predecessor recorded two codex lanes as dead.
  Both had finished: one landed 16 s *before* the handoff was written, the other
  99 s *after* the session hit `Prompt is too long`
  (`docs/artifacts/the-116-second-blackout.html`). Nothing was lost **only
  because** `agent-report-persistence.md` rule 1 requires incremental writes to
  disk.

**The pattern across all three: the result survives, the notification does not.**
The repo already externalises state to an artifact store, which the literature
names as the countermeasure — and it is what saved the round. What it does not do
is *poll the artifact store instead of trusting the notification*.

## 3. Fragility — of the contract, and whether the ceremony pays

The seven-part spec, `PREMISES` blocks and attestation gates are real overhead.
The measurement that matters is that **the review half is disciplined and the
agent half is not**: review reports median **66** lines, max **416**, only
**5 of 159** over 300. Agent reports median **104**, max **768**, **38 of 235**
over 300. The contract is doing its job where it is applied.

**What the contract does NOT carry is a machine-readable result.** Every lane
returns prose an architect re-reads at architect prices. The literature's rule is
blunt: *"Typed contracts at every handoff… crosses a schema, not free prose.
Hand-offs are data, not narration. Validate at the boundary; reject and re-ask on
schema failure."* The installed `codex-cli 0.150.1` has `--output-schema <FILE>`
and has had it all along.

## 4. What the literature says, and where it agrees with Ray

Secondary, but it converges on Ray's own reframe rather than on the roster question.

- **"Decompose by context boundary, not by role type. Splitting
  planner/implementer/tester/reviewer (role-centric) creates a 'telephone game'
  where every handoff loses fidelity."** This is the direct argument against
  answering "which roles" — and against the 2026-08-02 seven-role directive,
  which the 2026-08-06 synthesis already rejected on different grounds.
- **"Start with a single agent. Add a second only when you can name the specific
  constraint it relieves: context-window overflow, serial latency on
  parallelizable work, or genuinely different tool/permission/policy scopes."**
- **Cost**: Anthropic measured multi-agent at **~15× chat tokens** against ~4× for
  a single agent, for a **90.2%** lift on research tasks. The multiplier has to be
  earned.
- **"Beyond ~4 substantive worker outputs the orchestrator's context routinely
  overflows; workers must return condensed, structured findings, with full detail
  parked in an artifact store."** Measured here: **0.9M tokens** of lane output per
  round. The repo is well past four.
- **The cross-model workflow that keeps recurring in the wild** reviews the *plan*
  before implementation, not only the diff after: Claude plans → Codex QA-reviews
  the plan against the codebase and **inserts** phases rather than rewriting →
  Claude implements phase-by-phase with test gates → Codex verifies against the
  plan.
- **Least privilege**: *"the agent that performs analysis must not hold write
  access"*; a deterministic engine, not the agent, posts results. This repo
  already does the second half via `kb_setup`.

## 5. Recommendation — the interface, then the team

### The interface (this is the deliverable)

| # | Change | Uses | Fixes |
|---|---|---|---|
| 1 | **Type the handoff.** Every lane dispatch passes `codex exec --output-schema <schema.json>`; the architect reads the validated object, not the prose. Full detail stays in the disk report; the return value is a pointer plus a typed summary. | `--output-schema`, already installed | the 0.9M-token re-read; malformed payloads propagating |
| 2 | **Poll the artifact, never trust the notification.** A lane is done when its report file says it is done, not when a notification arrives. Add a terminal sentinel line to the report contract and wait on the file. | the existing `.agent/kb/reports/` store | the 222.4 min of dead delivery; the 116-second blackout class |
| 3 | **Resume instead of re-dispatching.** A lane that hits the watchdog is resumed with `codex exec resume --last`, not restarted cold. | `codex exec resume` / `fork`, already installed | the 600 s empty-`FINAL` and 900 s timeout classes |
| 4 | **Emit a clock.** `codex exec --json` gives a JSONL event stream; record dispatch, first token, and completion into the report header. | `--json`, already installed | a transport nobody can measure |
| 5 | **Stop stripping the `:variant`.** The report filename must name the model family that ran. | `report_path` / `_lane_prefix` | 157 of 159 reviews being unattributable |

**The rule for when to offload to Codex**, which Ray asked for as a rule and not a
mode: **offload when the work is bounded by a spec the architect can write in full,
and the result is verifiable without the architect's context.** Concretely — a
diff review against a fixed ref, an implementation whose acceptance criteria are
already written, a mechanical migration. Keep it inline when writing the spec
would cost more than doing the work, or when the result can only be judged against
conversation the lane will not have. That is the "context boundary, not role type"
rule stated operationally.

### Where scarce Fable buys something

Three named decision points, and nowhere else:

1. **Before a change that is expensive to reverse** — a corpus migration, a gate
   design, a routing change. This is what `kb-advisor` already is.
2. **When the same problem has resisted two attempts.** The repo's own measured
   pattern is that round 2 finds defects *in round 1's fix*; a fresh strong lens at
   that boundary is worth more than a third attempt by the same reasoning.
3. **Adjudicating two lanes that disagree.** A disagreement between families is
   the cheapest defect detector available, and resolving it is judgment, not
   execution.

Not as the default architect — Ray's budget rules that out, and the measurement
supports it: the architect's expensive work here was re-reading, which a typed
contract removes rather than a stronger model.

### The roster

**No new roles are recommended, and that is not a default — it is a conclusion
with a reason.** The 2026-08-06 synthesis shipped six agents, five of which match
its proposal exactly. What changed since is the lane world: Gemini/`agy` is now a
one-call reserve rather than a routine reviewer, and `grok` is not installed.
Neither change adds a role; both narrow where an existing one may run.

**The one undocumented divergence must be resolved by Ray, not here** (#116):
`kb-advisor` (fable/high) sits where the synthesis proposed `kb-fallback-reviewer`
(opus/high), and that synthesis said fable was *"deliberately ABSENT from the
standing roster"*. Section 5's decision-point argument is a case *for* the
divergence, but it was made after the fact and the swap itself is still unrecorded.

## Not measured

- **Whether `--output-schema` actually improves lane fidelity here.** No lane was
  run with it this round. Recommendation 1 rests on the flag existing and on the
  literature, not on an execution in this repo.
- **Whether `codex exec resume` recovers a watchdog-killed lane's partial state.**
  Untested. It is the recommendation most likely to be wrong.
- **Contract-overhead attribution.** Whether reports carrying a `PREMISES` block
  have fewer refuted claims than those without was not answered — the lane's
  section 3 had not landed when this was written. Line-count discipline is
  measured; correctness-per-ceremony is not.
- **Latency outside the one round** measured end to end (2026-08-21). Every
  delivery figure comes from that round. The 600 s / 900 s kills are from others.
- **Any figure for `agy`.** One call was budgeted this round and none was spent.

## GitHub repos touched

- [pipeshub-ai/pipeshub-ai](https://github.com/pipeshub-ai/pipeshub-ai) — `docs/multi-agent-best-practices.md`, the synthesis of Anthropic's multi-agent guidance that supplies the context-boundary and typed-contract rules.
- [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) — the cross-model Claude+Codex workflow that reviews the plan before implementation.
- [kryota-dev/actions](https://github.com/kryota-dev/actions) — ADR-006, least-privilege separation between the analysing agent and the posting engine.
- [wtyler2505/protopulse](https://github.com/wtyler2505/protopulse) — `docs/collab/`, a Claude↔Codex protocol co-design that first surfaced the codex non-interactive flag set.
- [jgwill/miadi-orchestration-kit](https://github.com/jgwill/miadi-orchestration-kit) — orchestration pattern summaries; read only for the orchestrator-worker figures.
- [rmusser01/tldw_server](https://github.com/rmusser01/tldw_server) — a transcription of Anthropic's architecture; used only to cross-check the 15× / 90.2% figures.
- [anthropics/anthropic (anthropic.com/engineering)](https://github.com/anthropics) — the primary multi-agent research-system write-up.

None of these is currently a pinned source. The first three are the candidates
worth `sources/REGISTRY.md`.
