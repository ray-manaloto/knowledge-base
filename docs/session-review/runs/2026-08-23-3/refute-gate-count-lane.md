# Refutation lane: "four rule files + gates.py docstring say FOUR gates, GATE_TASKS is FIVE"

Verdict so far: **NOT REFUTED — CONFIRMED on every cited line, and the class is
larger than the finding states.** (Report written incrementally; coverage line at end.)

## Probes run (all on worktree at 3d957f15, branch docs-directive-addendum, clean)

| claim | probe | result |
|---|---|---|
| GATE_TASKS has five elements | Read gates.py:110-170 | `gates.py:131` = `GATE_TASKS = ("lint", "test", "brain-audit", "eval", "graph-size")` — FIVE. CONFIRMED |
| docstring says "all four" | Read gates.py:380-430 | `gates.py:401` = "reachable on the ship path, since all four `GATE_TASKS` are one batch." CONFIRMED. 401−131=270, the "270 lines below" arithmetic holds |
| five "since #336" | `git log -L131,131:python/src/kb_setup/gates.py` | commit `37f6a1c5` "feat model limits resolver (#336)" changed the tuple from 4 to 5 elements. CONFIRMED |
| verify-before-advancing.md:22 "runs all four" | `sed -n '18,26p'` | line 22 = "**Always (any code/config/docs change):** `mise run kb-gates` runs all four and". CONFIRMED |
| verify-before-advancing.md:48 enumerates four | `sed -n '44,52p'` | line 48 = "then runs `lint` + `test` + `brain-audit` + `eval`, and refuses to push if any". CONFIRMED |
| gh-cli-watch.md:35 enumerates four | `sed -n '30,40p'` | line 35 = "(`lint`, `test`, `brain-audit`, `eval`) BEFORE pushing and opening the PR". CONFIRMED |
| mise-tasks-only.md:112 enumerates four | `sed -n '108,116p'` | lines 111-112 = "then `lint`, `test`, / `brain-audit`, and `eval` all run before a PR is pushed". CONFIRMED |

## The refutation angle that DIED

Best candidate refutation: "the rule files describe kb-ship, and maybe kb-ship
runs its own four-gate list while only kb-gates runs five." **False**:
`pr.py:156` = `gates.run_and_record(repo_root, gates.GATE_TASKS, stop_on_failure=True)`
and `pr.py:133` "Run every gate in :data:`gates.GATE_TASKS`; True only if all of
them pass" — ship runs the five-tuple, graph-size is binding on the ship path
(gates.py:126-130 says it was put there deliberately, Ray's ruling 2026-08-17).
So the four-enumerations misdescribe CURRENT ship behavior, not just style.

Second candidate: "line 401's 'all four' refers to the CONCURRENT_SAFE batch,
which really does have four members (gates.py:179)." Textually untenable — the
sentence names `GATE_TASKS`, and it is stale on a SECOND axis besides count:
since #321 (2026-08-16) eval is exclusive, so GATE_TASKS form TWO batches, not
one (gates.py:506-508 states this correctly two hundred lines further down).

## The class is BIGGER than the finding's sample (uncited instances, same defect)

- `python/src/kb_setup/pr.py:21-22` — module docstring: "runs every gate in
  :data:`gates.GATE_TASKS` (``lint``, ``test``, ``brain-audit``, ``eval``)" — four.
- `mise.toml:896` — kb-ship description: "gates (lint/test/brain-audit/eval)" — four.
- `gates.py:349` — "after all four gates' output" (comment, present-tense).
- `gates.py:506` — "Three of the four are :data:`CONCURRENT_SAFE` and form ONE
  batch" — now four of the FIVE are concurrent-safe (gates.py:179 includes
  graph-size). Ironically this exact paragraph carries a meta-note (gates.py:512)
  recording that it went stale once before, when #321 updated the constant's
  comment but not this docstring — #336 then repeated that failure against it.
- Historical-narrative "four"s at gates.py:139/163/166 are about the pre-#336
  measurement and are arguably legitimate as history, though 166 reads present-tense.

## Second independent route: the round's own runtime records agree with the code

- `.agent/plans/session-2026-08-17-g.md:7-11` — post-#336 (`main` at `37f6a1c5`),
  `mise run kb-gates` printed "lint PASS · test PASS · brain-audit PASS · eval
  PASS · graph-size PASS — **5 passed, 0 failed**"; g:27 even says graph-size is
  "in `GATE_TASKS`".
- `.agent/plans/session-2026-08-18-a.md:9-12` — same five-gate record on `fdcfba8e`.
- Handoffs b/c/d/e record "(4/4)" but all predate #336 (`main` at `ed20a77d`),
  so they are historically correct, not counter-evidence.

## The "four rule files" headline

The finding cites only THREE distinct rule files (verify-before-advancing ×2
lines, gh-cli-watch, mise-tasks-only) under a "Four rule files" headline — but a
FOURTH exists and makes the headline true: `.claude/rules/ci-local-parity.md:13`
("plus `brain-audit` and `eval` — all run by `mise run kb-ship`") and `:29`
("(`lint`, `test`, `brain-audit`, `eval`)"). Also stale the same way:
`verify-before-advancing.md:29` "the other two `kb-ship` enforces" (now three).
Grep control: the same sweep finds "graph-size" in ZERO rule files, while
finding it where it exists (4× gates.py, mise.toml:699/716) — the probe
discriminates.

## Directive + handoffs (read in full, per lane instructions)

`docs/direction/2026-08-18-ray-directives.md` and all seven handoffs contain
nothing that refutes or deprioritizes the finding; no handoff records the drift
as known/deferred. Directive item 9 (zero tolerance on repeating mistakes) makes
it MORE significant: gates.py:512's own meta-note records this exact
docstring-left-behind failure happening once before at #321 ("the constant's own
comment was updated and this docstring was not — the same file, the same
change"), and #336 then repeated it against lines 349/401/506, the four rule
files, pr.py:21-22, and mise.toml:896.

## One fairness caveat

gates.py:401's sentence is stale on a SECOND axis the finding does not mention:
GATE_TASKS no longer form ONE batch either — eval left CONCURRENT_SAFE in #321,
so the batches are {lint, test, brain-audit, graph-size} + {eval}
(gates.py:179, and gates.py:506-508 states it correctly). The function's guarded
scenario (a multi-gate batch on the ship path) is still reachable via the
four-member batch, so the docstring's PURPOSE stands; its count does not.

## Contradiction with other findings in the set

None visible from this lane (the set was not provided). Internally, every
independent probe of the fact agrees: constant (gates.py:131), git history
(37f6a1c5 = #336), ship call-site (pr.py:156), two post-#336 runtime records
("5 passed"), and all cited doc lines point the same way.

## VERDICT: refuted = FALSE — the finding is CONFIRMED and is an UNDERCOUNT of its class.

## COVERAGE

- REACHED AND ANALYSED: gates.py (lines 1-250, 345-430, 500-520, 840-850 read;
  every "four/five" hit from a whole-file grep classified); pr.py:18-26 + gate
  call sites; mise.toml kb-ship/kb-gates/graph-size task blocks; all four cited
  rule lines read at exact line numbers; the full rules-directory grep for gate
  enumerations; git -L history of gates.py:131; Ray's 2026-08-18 directive IN
  FULL; all seven named handoffs IN FULL.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: the transcripts themselves (not needed — the finding is about
  committed repo state, verified directly against the worktree at 3d957f15);
  the other findings in the lane's set (not provided to this lane).
