# Refutation lane — finding 12 (forgotten)

CLAIM: "The 'option 1' scope conflict the plan doc's own cold-lane review flagged
(U0 not in Ray's literal scope; U4/U5 were, and are undone) was never put to Ray,
and the session proceeded on the unconfirmed assumption."

## Artifacts

- `docs/plans/2026-08-23-directive-execution-plan.md:1198-1215` — conflict text CONFIRMED present.
  mtime of the plan file: Aug 23 07:45.
- Transcripts (reviewed round = two sessions):
  - `10290cde-d1e5-4fac-b1ec-3db4da5d0585.jsonl` (06:41Z -> 09:41Z, the planning session)
  - `f74823ff-3ee4-4b02-a2af-11106a762c9f.jsonl` (09:45Z -> 18:03Z, the execution session)

## PROBE 1 — was the scope question put to Ray AFTER the plan flagged it?

YES. `AskUserQuestion` at 2026-08-23T09:06:55.344Z (session 10290cde), question 4:

  Q: "Twelve units, each through orchestration then /clear-prep. Realistically this
      session cannot do all of them. Where should it stop?"
  option [U2a only — resync, start the run, clear-prep (Recommended)]:
      "... Also the honest read of 'option 1' plus your immediate-task instruction."
  other options named U0 explicitly: "[U2a then U0, in parallel with the run]"

Ray ANSWERED at 2026-08-23T09:09:24.176Z:
  "Twelve units ... Where should it stop?"="U2a only — resync, start the run, clear-prep (Recommended)"

That is 1h21m AFTER the plan file was written (07:45) — i.e. after the cold-lane
correction the finding cites.

## PROBE 2 — was U0 itself put to Ray?

YES, twice in the same call at 09:06:55:
  Q: "U0 — the plan opens by re-running `kb-build` ... If the re-run does NOT fix it,
      what happens?"  -> answered 09:09:24 "Register the failing sources `build = skip` and move on"
  Q: "U5 — you asked that yuting0624's plugin be 'in sync w the latest version of the
      antigravity plugin'... What does 'in sync' mean mechanically?"
      -> answered "Manifest tracks the tag matching the INSTALLED plugin version (Recommended)"

So U5 (one of the two units the finding says was silently dropped) was ALSO put to
Ray and ruled on in the same call.


## PROBE 3 — THE DECISIVE ONE: the finding's OWN cited file refutes it, 1,130 lines earlier

`git show HEAD:docs/plans/2026-08-23-directive-execution-plan.md | sed -n '66,79p'`
(file is clean at HEAD `34bc4557`, `git status --porcelain` on it -> empty):

| 14 | U0 if the rebuild still fails | **register the failing sources `build = skip` ...** |
| 16 | U5 "in sync" | **the manifest tracks the tag matching the INSTALLED plugin version** ... |
| 17 | **this session's scope** | **U2a only** — resync, start the run, `/clear-prep`. ... |
| 18 | how U2a runs, given U2 is not built | **hand-run it, ...** |

followed verbatim by:

  "**The frontier is empty.** Every branch above was put to Ray and answered; nothing
   below is silently assumed. ... it is out of this session's scope by decision 17"

Decision 17 IS Ray's 09:09:24Z answer, recorded. The plan doc was committed
`b47a5a81` at 2026-08-23T04:19:06-05:00 = 09:19:06Z — ten minutes AFTER Ray
answered. Timezone confirmed: `date` -> CDT (UTC-5).

## Why the original probe could only give the answer it gave

It read `:1198-1215` — a 18-line slice of a 1,636-line file. That slice is the
"Second sweep" section where the conflict is RAISED ("My assumption, stated so it
can be corrected"). The RESOLUTION lives at `:52-78`, 1,130 lines earlier, in the
settled-decisions table. A bounded read of the raising site cannot see the
resolution site. This is `probes-need-a-control-arm.md` rule 3 exactly.

## CONTROL ARM (the probe discriminates)

Same jq extraction of every `AskUserQuestion` tool_use input across both
in-scope transcripts (28 calls), then token counts:

  POSITIVE: "option 1" 4 · "U0" 11 · "U2a" 12 · "U5" 3 · "U4b" 3 · "yuting0624" 2
  NEGATIVE: "ls-remote" 0 · "agent memory" 0 · "U4 " 0

So the probe returns 0 when a topic genuinely was not asked (it correctly finds
finding 14's L7 `mise ls-remote` and L4 `agent memory` absent, and U4 proper
absent), and non-zero for U0/U5/option-1. It is not a one-faced coin.

## VERDICT: REFUTED

Both halves fail:
- "never put to Ray": the scope question naming 'option 1' was asked
  2026-08-23T09:06:55Z and answered 09:09:24Z ("U2a only"). U0 was asked in the
  same call and answered ("Register the failing sources build = skip"). U5's
  mechanics were asked in the same call and answered ("Manifest tracks the tag
  matching the INSTALLED plugin version"). U0's scope was RE-asked and WIDENED by
  Ray at 14:17:49Z: "U0 unblocks 1 of 8 sources as specced. How wide should the
  corrected spec go?" = "All 24 files across all 8 sources (Recommended)".
- "proceeded on the unconfirmed assumption": Ray's 09:09:24Z ruling SUPERSEDED
  option 1 with "U2a only", and at 16:16:58Z he was told "U0 is verified" and
  chose the next lane. U0 was executed under an explicit Ray ruling, not an
  assumption.

## Residual true kernel (belongs to findings 7/17, not to 12)

U4 was never named in any AskUserQuestion ("U4 " -> 0 hits; only U4b, a
mid-round invention) and U4/U5 are undone. That is finding 7 and finding 17.
Finding 12's causal story — an unasked conflict — is the part that is wrong.

## CONTRADICTS

Finding 7 ("Ray's directive item 2 ... had to be RE-ISSUED VERBATIM 7h14m
later") contradicts finding 12's "never put to Ray": at 2026-08-23T17:02:43Z Ray
himself answered "How much of the antigravity setup should I fix before running
the cold review?" with "full setup using: /antigravity:setup, /antigravity:migrate
...". The antigravity scope was actively re-negotiated with Ray in-session.
Also finding 17 (U5 undone) is compatible only with "undone", not with "never
put to Ray" — decision 16 in the plan records Ray's ruling on U5's mechanics.

## GitHub repos touched

_None._
