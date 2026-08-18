# Refutation lane: "currency hard-block contradicts CLAUDE.md doctrine; no issue tracks it"

commit under review: 022e88f4 (branch docs-directive-addendum)

## Sub-claims to test
1. directive item 10 demands a hard block — at "line 40"
2. CLAUDE.md states the opposite doctrine
3. kb-currency-check always exits 0 by construction
4. NO GitHub issue tracks reconciling the contradiction

## Findings so far
- (1) PARTLY WRONG ANCHOR: the verbatim line is `docs/direction/2026-08-18-ray-directives.md:45`,
  not line 40. Line 40 is the "documentation and code in a state that a human/agent can take over" line.
  `grep -n "not doing any work until"` -> 45 and 220.
- (2) TRUE as text: CLAUDE.md:159-160 "**`mise run kb-currency` always exits 0** and can never serve
  as a CI gate — an out-of-date tool is a signal, not a failure." Also CLAUDE.md:143 for the hook.
  BUT the clause is scoped to `mise run kb-currency` (the full loop) and to the SessionStart HOOK,
  not to "a currency gate may never exist".
- (3) TRUE-ish: python/src/kb_setup/currency/run.py:44 `check()` returns 0 on every path
  EXCEPT run.py:69 `return 2` for an unknown `--tool`. So "always exits 0 by construction" is
  false in the strict sense: the function has a non-zero exit already.

## VERDICT: REFUTED (refuted=true)

The finding's *coverage* sub-claim holds. Its *diagnosis*, its *"unfixed"* framing,
and its *"no issue tracks it"* evidence line all fail.

### R1 — The offered probe DID NOT return zero. It returned #212 and #143.

Re-ran the finding's own command verbatim:

    $ gh issue list --search "handoff gitignored OR session handoff durable OR .agent/plans"
    188  OPEN  currency: a source_only tool pinned to a branch prints 'NOT CHECKED ...'
    212  OPEN  LESSONS.md is gitignored: the self-improving loop's only durable output
               never reaches a consumer or a fresh clone
    143  OPEN  Spec: make /clear-prep's mechanical steps mechanical (kb-handoff-check,
               kb-gates, kb-session-state)
    301  OPEN  Scale semantic extraction to complete pinned Graphify coverage
    116  OPEN  The reusable agent team: roles, model/effort per role, and allowed tools
    rc=0

"Zero on-point hits" was the reporter's JUDGMENT about that output, reported as a
zero RESULT. #212 is the same defect class verbatim (gitignored artifact never
reaches a fresh clone; #212 body line 7: "a consumer repo, a fresh clone, or
another machine has **no lessons at all**"), and #143 is the /clear-prep spec.

Two bounds in the original probe on top of that: `gh issue list` defaults to
`--state open` and `--limit 30`.

Unbounded re-probe (all states, 500, regex over TITLE+BODY):

    $ gh issue list --state all --limit 500 --json number,title,state,body --jq \
      '.[] | select((.title+" "+.body) | test("gitignor|survive a clone|durabl|between sessions|lost between|\\.agent/plans|session handoff";"i")) | ...'
    -> 33 issues, incl. 212, 241 ("16 P2/P3 findings ... live only in a gitignored
       report"), 142 (".agent/ tree: what belongs in git"), 313 (CLOSED, same),
       317, 143, 150.

CONTROL ARM: same jq shape with a term known present ("kb-review") -> 23 hits.
The probe discriminates; the zero was never produced by the tool.

### R2 — Causal refutation: the handoff DOES survive between sessions.

    $ ls -la .agent/plans/
    12 files, session-2026-08-15.md ... session-2026-08-18-a.md, mtimes Aug 15 19:05
    -> Aug 18 03:07.

`.gitignore` does not delete files. Every session in this repo runs on this
machine, against this working tree. Ray's losses occurred WITH all 12 handoffs on
disk. A clone-durability property cannot be the mechanism of a same-machine,
between-session loss. The finding conflates "not durable across a clone" with
"loses requirements between sessions".

### R3 — The property is DESIGNED and DOCUMENTED, not an undiagnosed unfixed defect.

`.claude/skills/clear-prep/SKILL.md:217-224` — a four-row durability matrix:

    | Layer | Survives `/clear` | Survives a fresh clone | Answers |
    | auto-memory (`~/.claude/projects/.../memory/`) | yes | yes | what the next session must know |
    | `.agent/plans/session-*.md` | yes | **no** — gitignored | how to resume *this* work |
    | `.agent/kb/reports/agents/*.md` | yes | **no** — gitignored | the evidence behind a finding |
    | `graphify-out/memory/` (via `kb-remember`) | yes | yes — committed | what the *corpus* learned |

and `:238` is literally the heading `### b. The handoff — survives /clear, dies
with the clone`. Clone-durability is deliberately assigned to auto-memory and
`graphify-out/memory/`; the handoff is scoped to "how to resume *this* work".
`.gitignore:143`'s own comment states the intent ("per-session scratch, never
source"). Calling a documented layering "not yet fixed" mischaracterises it.

### R4 — The source says "candidate", not "diagnosed".

`docs/direction/2026-08-18-ray-directives.md:74`: "That is a **candidate** root
cause and is not yet fixed." The finding upgrades the hedge to "has a diagnosed
root cause".

### R5 — A competing, MEASURED root cause exists and WAS fixed.

`CLAUDE.md:173` and `.claude/skills/clear-prep/SKILL.md:49-56`: "Until 2026-08-17
**nothing read this directory** ... so a directive could be filed carefully and
never consulted again, which is the failure this step now closes."
`docs/direction/*` is TRACKED (`git ls-files docs/direction/` -> 3 files).
#143's problem statement supplies a third: clear-prep's step 6 self-verification
is "verification performed by the same context that produced the thing being
verified ... from memory", already measured failing. Neither alternative was
excluded before naming the gitignore as the cause.

### What SURVIVES of the finding

Only the coverage sub-claim. `.claude/workflows/session-review.js:186-291` defines
exactly 8 lanes; none names handoff durability. `forgotten` (:203-208) sweeps
handoffs as a SOURCE, not as a subject; `pending-work` (:275-289) is scoped by its
own text to "git worktrees, branches, or the backup directory". So directive item 1
has no lane — that gap is real and is the only defensible part.

## (4) "No GitHub issue tracks it" — TRUE but trivially so, and their hit-set is mischaracterized
Probe (unbounded, all states, limit 1000):
`gh issue list --state all --limit 1000 --json number,title,state,body` -> 203 issues.
- Their regex reproduces EXACTLY 7 hits over all 203 (so their probe was not open/limit-bounded). Good.
- BUT "closest is #287" is wrong. **#88 is in their own 7 hits**: "Where does the stale-graph
  signal render, and does it ever block?" Its body quotes the identical CLAUDE.md clause
  ("always exits 0 and can never serve as a CI gate — an out-of-date tool is a signal, not a
  failure") and asks "Does it ever block?". Closed 2026-07-31 COMPLETED, resolution comment:
  "### 2. It NEVER blocks — advisory, like every other currency signal" and "All four settled;
  **1 and 2 by Ray**". So the "standing doctrine" IS Ray's own prior ruling; the 2026-08-18
  directive is Ray superseding himself, not repo-vs-user.
- #184 (OPEN) "Upgrade every pinned dependency in mise.toml and pyproject.toml" tracks item 10's
  SUBSTANCE, incl. an acceptance box "Consider whether lockfile completeness should become a gate".
- Token-spelling sweep over all 203: "critical currency"->0, "not doing any work"->0, "hard gate"->0,
  "must always be on the latest"->0, "0.9.46"->0. CONTROL: "kb-currency-check"->14. Probe discriminates.
  => NO issue references the 2026-08-18 directive AT ALL — not item 10, not any item. That is the
  recorded, scheduled state (row 3: the sweep "has **not been run** yet"; clear-prep ruling makes
  running it and filing issues the next session's FIRST task), not an unnoticed gap.

## (5) The decisive refutation: the repo ALREADY hard-blocks on a version disagreement
`python/src/kb_setup/graphify_env.py:152 assert_pinned_graphify` raises **SystemExit** when the
running graphify != the pyproject pin (graphify_env.py:178-185), and the refusal text points at
`mise run kb-currency-check`. Wired into 10 call sites (graph.py:2950, cli.py:119/238,
graphify_ops.py:636, graphify_baseline.py:315/1825, graphify_semantic_slice.py:783,
skill_refresh.py:143, graphify_sdk.py:256). Armed BOTH directions in the repo's own suite
(tests/test_graphify_env.py:168 refuses, :183 passes, :197 refuses-when-unreadable);
`uv run pytest tests/test_graphify_env.py -k "gate_refuses or gate_passes"` -> 4 passed.
So "the codebase's standing doctrine is the opposite [of a hard block]" is over-broad: the repo's
actual doctrine is *pin-vs-upstream staleness is advisory; install-vs-pin disagreement REFUSES*.

## (6) The gap is already recorded in the artifact under review
`docs/direction/2026-08-18-ray-directives.md:75` (status row 2): "...but **nothing BLOCKS work on a
stale pin, which is the gap this directive names**." The finding cites row 10 (line 83) and misses
row 2, which states the very gap it reports as undocumented.

## Control arm for the grep habit
`grep -rn "currency" python/src/kb_setup/gates.py` -> 6 hits, ALL of them the substring inside
**con**currency*. A naive currency-in-the-gates grep is a token trap here.

## VERDICT: refuted = true (as stated)
Residual true core: no issue exists for the 2026-08-18 directive, and CLAUDE.md:159-160 +
.claude/rules/tool-currency-and-native-first.md:75-76 will both need amending if item 10 is adopted
as a gate. That is a worthwhile follow-up, not the "direct contradiction, untracked" the finding claims.
