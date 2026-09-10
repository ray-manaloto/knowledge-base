---
type: "query"
date: "2026-09-10T18:00:27.668306+00:00"
question: "Does building a gate for a class close the class?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does building a gate for a class close the class?

## Answer

A gate you just built does not close the class it names — and the second half of
one round proved it twice.

`kb-graphify-catalog` shipped to catch *a pin move leaves its derived values
behind*. ONE COMMIT LATER the `antigravity-cli` bump moved `mise.toml`,
`currency.toml` and the source manifest and left `mise.lock` at the old version.
All nine gates went green and it MERGED (`6b3ab427`). A second instance had been
sitting there for weeks: `[[tools.codex]] version = "0.149.1" backend =
"aqua:openai/codex"` while `mise.toml` pins `npm:@openai/codex@0.154.0` — an
ORPHAN from a backend change, not merely a stale version.

`kb-lock-drift` closes it natively — `mise lock --dry-run` previews without
writing — with one twist worth keeping: **mise returns rc 0 whether the lock is
in sync or five versions stale**, so the gate reads the REPORT, not the rc.

🔴 AND THAT SENTENCE BECAME MY OWN DEFECT. I let "the rc cannot tell in-sync from
stale" license ignoring the rc ENTIRELY, so a mise that CRASHED — printing no
`would` line — read as a clean lockfile. A cold review found it. "The rc cannot
answer question A" does not mean the rc answers nothing; a crash is a THIRD
STATE, and collapsing it into "clean" is `probes-need-a-control-arm.md` rule 4 in
the module whose whole subject is a gate that missed something.

Three more from the same review round, each a class this repo already names:
a comment claiming an anchor the regex did not have; two tests that would pass
against a stubbed `drift()` returning `[]`; and a prose test that could not have
exercised the anchor because it never contained the string.

THE DURABLE SHAPE: after building a gate for a class, ask what ELSE in the repo
is in that class — the answer that round was `mise.lock`, one directory up, and
nothing was looking at it.


## Outcome

- Signal: useful