---
type: "query"
date: "2026-09-03T06:30:22.498238+00:00"
question: "Does kb-codex --review --output persist the lane's report?"
contributor: "graphify"
outcome: "corrected"
correction: "`kb-codex --review --output <path>` SILENTLY DROPS THE FLAG.\n\nI passed `--output .agent/kb/review/reports/review-<sha>-cold.md` expecting the\nlane to persist its own report — the exact remedy the previous round's handoff\nprescribed after losing a transcript to the reaped scratchpad. No file was\nwritten. The lane ran fine, rc 0, and the report simply did not exist.\n\nControl-armed, both directions, via `--print-argv` (which spawns nothing):\n\n  review mode: `codex review --base origin/main -c developer_instructions=\"…\"`\n               -> no `-o` anywhere\n  exec mode:   `codex exec --sandbox read-only -o /tmp/x.md -c … -- -`\n               -> `-o` present\n\nSo the flag is honoured in exec mode and dropped in review mode. It is ACCEPTED\nby the argument parser in both, which is what makes it dangerous: nothing errors,\nnothing warns, and the caller's evidence-persistence step becomes a no-op at\nexactly the moment it is being relied on.\n\nTHE GENERAL FORM: an accepted flag that does nothing is worse than a rejected\none. A rejected flag fails loudly at the call site; an ignored one succeeds and\ntakes the guarantee with it. When a flag exists to produce an ARTIFACT, the arm\nis to check the artifact, not the exit code — rc 0 says the command ran, never\nthat the flag did anything.\n\nI recovered by copying the 391,827-byte transcript out of the scratchpad by hand\nbefore it was reaped, so nothing was lost this time. The previous round was not\nso lucky and had to reconstruct its report from commit bodies.\n"
---

# Q: Does kb-codex --review --output persist the lane's report?

## Answer

**No. `kb-codex --review --output <path>` accepts the flag and writes nothing.**
Three flags behave this way, not one — `--output`, `--effort` and `--model` are
all parsed and then discarded when `--review` is set. Only the positional prompt
survives, delivered as `-c developer_instructions`. Filed as **#678**.

Control-armed with `--print-argv`, which spawns nothing:

    kb-codex --review --base origin/main --output /tmp/x.log  ->  codex review --base origin/main
    kb-codex --review --base origin/main --effort high        ->  codex review --base origin/main
    kb-codex --review --base origin/main --model gpt-5.6-sol  ->  codex review --base origin/main
    kb-codex "hi" --output /tmp/x.log
        -> codex exec --sandbox read-only -o /tmp/x.log -c model_reasoning_effort=xhigh
           --dangerously-bypass-hook-trust -

Both directions covered: present in exec mode, absent in review mode, so the
probe discriminates.

**TWO THINGS THE FIRST VERSION OF THIS RECORD GOT WRONG**, both found by running
the pinned parser instead of reasoning about it:

1. **`codex review` does not merely ignore `--output` — it REJECTS it.**
   `error: unexpected argument '--output' found`, **rc 2**. So the fix cannot be
   "forward the flag"; it has to be "refuse it at parse time in review mode".
   `_review_argv`'s own docstring (`codex_run.py:113-165`) already documents that
   review mode takes only `-c key=value` / `--base` / `--title`. The module knew;
   the parser did not.
2. **Even in exec mode, `-o` is not what the help string says.** It is
   `--output-last-message` — the agent's LAST MESSAGE, not the transcript. So
   `codex_run.py:257`'s help (*"write the transcript to this file (-o)"*) is
   wrong in BOTH modes. A caller relying on it for evidence persistence gets a
   final summary where they expected a transcript.

**THE GENERAL FORM: an accepted flag that does nothing is worse than a rejected
one.** A rejected flag fails loudly at the call site; an ignored one succeeds and
takes the guarantee with it. `rc 0` says the command ran, never that the flag did
anything — when a flag exists to produce an ARTIFACT, the arm is to check the
artifact.

**WHY IT COST SOMETHING.** `--output` was the exact remedy the previous handoff
prescribed after a transcript was lost to a reaped `/private/tmp` scratchpad. It
fails at the moment it is relied on, silently. The 391,827-byte transcript had to
be copied out by hand before reaping.

**WHAT ACTUALLY SAVES A LANE TRANSCRIPT**, learned the hard way the next day when
a shell-redirect capture of a later lane was destroyed by its own archiving step:
`~/.codex/sessions/<date>/rollout-*.jsonl`. Codex writes it itself, it survives
the scratchpad reaper and the caller's mistakes, and it exists only because
`--ephemeral` was removed from this repo's lane patterns on 2026-09-01 for an
unrelated reason (`kb-session-search` needs it). Reach for the session record
first; treat any stdout capture as the copy you can afford to lose.

NOTE ON THIS RECORD: its `## Answer` section was, until 2026-09-03, a byte-identical
copy of a sibling record's answer about METHOD paragraphs — `kb-remember` was
called twice one second apart reusing a single `--answer-file` while varying only
`--question` and `--outcome`. The real answer existed only in the `correction:`
field. A record whose answer does not answer its question is worse than no
record: it is retrievable, and it is wrong.

## Outcome

- Signal: corrected
- Correction: `kb-codex --review --output <path>` SILENTLY DROPS THE FLAG.

I passed `--output .agent/kb/review/reports/review-<sha>-cold.md` expecting the
lane to persist its own report — the exact remedy the previous round's handoff
prescribed after losing a transcript to the reaped scratchpad. No file was
written. The lane ran fine, rc 0, and the report simply did not exist.

Control-armed, both directions, via `--print-argv` (which spawns nothing):

  review mode: `codex review --base origin/main -c developer_instructions="…"`
               -> no `-o` anywhere
  exec mode:   `codex exec --sandbox read-only -o /tmp/x.md -c … -- -`
               -> `-o` present

So the flag is honoured in exec mode and dropped in review mode. It is ACCEPTED
by the argument parser in both, which is what makes it dangerous: nothing errors,
nothing warns, and the caller's evidence-persistence step becomes a no-op at
exactly the moment it is being relied on.

THE GENERAL FORM: an accepted flag that does nothing is worse than a rejected
one. A rejected flag fails loudly at the call site; an ignored one succeeds and
takes the guarantee with it. When a flag exists to produce an ARTIFACT, the arm
is to check the artifact, not the exit code — rc 0 says the command ran, never
that the flag did anything.

I recovered by copying the 391,827-byte transcript out of the scratchpad by hand
before it was reaped, so nothing was lost this time. The previous round was not
so lucky and had to reconstruct its report from commit bodies.
