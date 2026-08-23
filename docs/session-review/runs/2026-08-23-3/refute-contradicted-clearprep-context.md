# Refutation lane — finding 14 (contradicted): "clear-prep's context trigger cannot work"

Reviewing repo: /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base
HEAD at start of this lane: e82708d9 (2026-08-22 13:13:28 -0500)

## Facts established so far

- `git log --oneline -5 -- python/src/kb_setup/context_usage.py`
  -> `e82708d9 fix(context): kb-context could ONLY refuse - two subprocess vars read as identity (#451)`
  The commit ABOVE the one the finding describes.
- At `4f2193e9` (parent) the finding is verbatim accurate:
  - docstring lines 60-67 contain "The failure direction is the safe one: a main
    session wrongly detected as a child would merely stay silent"
  - `CHILD_MARKERS` = ("CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_FORK_SUBAGENT")
  - main() returns 3 with "NOT THE MAIN THREAD"
  - `.claude/skills/clear-prep/SKILL.md` at 4f2193e9 lines 15-38 say
    "kb-context checks the environment markers that do separate them; rc=3 is your answer"
- Vendor primary source confirms the MECHANISM:
  `sources/agent-harness-docs/docs/claude-code/env-vars.md:208` - CLAUDE_CODE_CHILD_SESSION
  "Set to 1 in subprocesses Claude Code spawns via the Bash ... tools"
  `env-vars.md:268` - CLAUDE_CODE_FORK_SUBAGENT "Set to 1 to LET Claude spawn forked subagents" (operator flag)
- Presence probe in this lane's own Bash env (control HOME PRESENT, BOGUS_NAME_XYZ ABSENT):
  CLAUDE_CODE_CHILD_SESSION PRESENT, CLAUDE_CODE_FORK_SUBAGENT PRESENT.

## Open question being probed next
Whether the claim holds at HEAD.

## VERDICT: REFUTED at the primary artifact (HEAD e82708d9)

### Probe (the decisive one)
```
$ mise run kb-context > /tmp/ctx_head.out 2>&1; echo "rc=$?" >> /tmp/ctx_head.out; cat /tmp/ctx_head.out
[kb-context] $ uv run kb-setup context
transcript : 5ec8da38-160b-4594-9560-c07a86b46f27.jsonl
model      : claude-opus-5
occupancy  : 379,891 tokens (last of 327 measured turns)
window     : 1,000,000 tokens
USED       : 38.0%  (threshold 20%)
note       : measured from the LAST completed turn, so it is a FLOOR on
             current occupancy, never a ceiling.

=> OVER THRESHOLD. Offer /clear-prep now: ask the user via AskUserQuestion
   whether to prepare the handoff. Do not clear anything yourself.
[kb-context] ERROR task failed
rc=10
```
It returned **10**, not 3 - and it did so from a SUBAGENT Bash call carrying
BOTH markers (CLAUDE_CODE_CHILD_SESSION PRESENT, CLAUDE_CODE_FORK_SUBAGENT
PRESENT; control HOME PRESENT, BOGUS_NAME_XYZ ABSENT).

### Control arm - proving the probe can return the other answer
Same env, same entry point, only the module revision changed:
```
$ git show 4f2193e9:python/src/kb_setup/context_usage.py > $SP/old_context_usage.py
$ uv run python $SP/arm.py $SP/old_context_usage.py
CHILD_MARKERS = ('CLAUDE_CODE_CHILD_SESSION', 'CLAUDE_CODE_FORK_SUBAGENT')
child_marker(os.environ) = CLAUDE_CODE_CHILD_SESSION
context: NOT THE MAIN THREAD (CLAUDE_CODE_CHILD_SESSION is set) - declining to report.
OLD main() rc = 3
```
rc=3 on 4f2193e9, rc=10 on e82708d9. The probe discriminates; the difference is
the REVISION, not the probe.

### Every limb of the claim, checked at HEAD
| limb of the claim | at 4f2193e9 | at HEAD e82708d9 |
|---|---|---|
| docstring asserts the "safe failure direction" for an unmeasured negative arm | TRUE (:60-67) | FALSE - replaced by "the module then reached for two environment markers, and **both readings were wrong**" (context_usage.py:63-70) |
| `CHILD_MARKERS` holds the two vars | TRUE | FALSE - `CHILD_MARKERS: tuple[str, ...] = ()` at context_usage.py:145 |
| `kb-context` refuses rc=3 on every main-thread call | TRUE for measuring calls (NOT for `--help`, which returns 0 at old :311-315 before the marker check - a minor overstatement even then) | FALSE - measured rc=10 above; `child_marker()` "Always None while CHILD_MARKERS is empty" (:151) |
| SKILL.md tells agents "kb-context checks the environment markers that do separate them; rc=3 is your answer" | TRUE (`git show 4f2193e9:.claude/skills/clear-prep/SKILL.md`, lines 33-38) | FALSE - now reads "**nothing tells you which you are, so this instruction IS the enforcement** ... so `kb-context` refused there 100% of the time until 2026-08-22 (#451)" (SKILL.md:32-36) |

### Why the finding could only have said what it said
`e82708d9` was committed **2026-08-22 13:13:28 -0500 = 18:13:28 UTC**. The
8-lane session review was dispatched at **18:07:03 UTC**, and sibling finding 4
records the main thread Editing `context_usage.py`, its tests and
`clear-prep/SKILL.md` from **18:07:13 onward**. The lane read a tree that was
being fixed underneath it. This is the "wrong artifact" failure in its temporal
form: the right question asked of a revision that stopped existing six minutes
into the lane's run.

### What survives, and is worth keeping
The MECHANISM the finding names is real and independently confirmed from the
primary vendor source already in this corpus:
- `sources/agent-harness-docs/docs/claude-code/env-vars.md:208` -
  `CLAUDE_CODE_CHILD_SESSION` "Set to `1` in subprocesses Claude Code spawns via
  the Bash, PowerShell, and Monitor tools" - i.e. set from the MAIN thread too.
- `env-vars.md:268` - `CLAUDE_CODE_FORK_SUBAGENT` "Set to `1` to let Claude spawn
  forked subagents" - an operator capability flag, not a fork announcement.
So the pre-fix defect was genuine. It is already fixed, tested both directions
(`tests/test_context_usage.py:64-65` retired markers no longer disqualify;
`:107-112` rc=3 still fires given a real discriminator), and ticketed (#451).

### Contradiction with other findings in the set
- **Finding 4 corroborates, and explains the staleness**: it records the main
  thread "kept working the same kb-context rc=3 defect - 4 Edits to
  context_usage.py / tests / clear-prep SKILL.md ... and a draft of issue #451"
  during this very lane's run. Finding 14 and finding 4 are the same event seen
  from two sides; 14 reports as a live contradiction what 4 reports as work in
  progress.
- **Finding 24 is consistent, not contradictory**: "Session did not follow Ray's
  directive to issue /clear-prep at 20% context" is exactly what a
  could-only-refuse `kb-context` would produce - it is downstream evidence for
  the PRE-fix state, not for the present one.
- No finding in the set contradicts finding 14 on the facts; what refutes it is
  the repository itself at HEAD.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) - the repo under review; source, tests, skill and git history read.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) - via the vendored `sources/agent-harness-docs/docs/claude-code/{env-vars,changelog,sub-agents}.md` corpus, for the two env-var definitions.
