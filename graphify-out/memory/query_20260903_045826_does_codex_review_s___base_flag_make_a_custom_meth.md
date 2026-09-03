---
type: "query"
date: "2026-09-03T04:58:26.551690+00:00"
question: "Does codex review's --base flag make a custom METHOD paragraph undeliverable?"
contributor: "graphify"
outcome: "corrected"
correction: "I wrote a design conclusion into a docstring from ONE CLI error string, and\ncommitted it as settled fact.\n\n`codex review --base origin/main … -` returned `error: the argument\n'--base <BRANCH>' cannot be used with '[PROMPT]'`. From that I concluded that\ncustom review instructions cannot be combined with base-branch selection, and\ntherefore that adopting `codex review` costs us the METHOD paragraph — the very\nthing this repo has measured as the difference between a review that finds\nthings and one that agrees with you.\n\nRay: \"dont guess, we have access to the codex source code … run codex lanes to\nresearch\". The pinned source sits at `sources/codex/` at the exact version we\nrun. A lane read the clap definitions and found the answer in minutes:\n\n- The four target arguments ARE mutually exclusive (`codex-rs/exec/src/cli.rs:\n  272-305`) — that half was right, and they are variants of one `ReviewTarget`\n  enum, so the prompt IS the scope.\n- But `-c key=value` is GLOBAL, flattened into `MultitoolCli`, and therefore\n  outside the conflict set. `-c developer_instructions=\"<METHOD>\"` delivers our\n  instructions WITH `--base`, traced through the source into the reviewer child\n  (`core/src/tasks/review.rs:99-127`).\n\nSo the capability existed the whole time and I had ruled it out.\n\nTHE GENERAL FORM: a CLI's help text and its error strings are SECONDARY\nartifacts. The argument definitions are primary. When a tool tells you something\nis impossible and it matters, read the code — and in this repo the code is\nusually already cloned under `sources/`.\n\nThis is the same failure as reading a stale-open issue as current behaviour,\nwhich `probes-need-a-control-arm.md` already records. The new part is that it\nhappened while I was actively fixing findings about exactly this.\n"
---

# Q: Does codex review's --base flag make a custom METHOD paragraph undeliverable?

## Answer

Phase U's first slice. The round set out to make the claude/graphify/codex setup
observable, enforced and owned by tasks (#672), and the enforcement it built kept
finding defects in itself.

WHAT SHIPPED (11 commits on feat/phase-u-setup-inventory, 8/8 gates green):
- `docs/setup-inventory.md` — #672's DoD 1: configured vs OBSERVED RUNNING, every
  row naming the command that proved it, plus an explicit list of what it did NOT
  observe.
- `kb_setup.graphify_health` — `mise run kb-build` was FAILING and nobody knew.
  The OpenSymphony extract succeeded (11,004 nodes) and the health check failed
  the whole build on one benign line graphify narrates. Approved narrowly, read
  out of graphify's own if/else (`build.py:1969-1997`) rather than by wording.
  kb-build is now GREEN: 359,146 nodes / 807,085 edges.
- `kb_setup.codex_lane` + `mise run kb-codex` — one place owns the four codex
  flags a lane cannot be right without; a raw lane is denied.
- `kb_setup.destructive_git` — the first STATEFUL guard in the chain; denies
  reset --hard / clean / checkout / restore only when there is uncommitted work.
- codex 0.152.0 -> 0.152.1, manifest + lockfile with it.
- Both clients wired: `graphify` = hosted, `kb` = the local 359k graph.

THE MEASURED RESULT WORTH KEEPING: `codex review` works as a cold lane, and the
METHOD paragraph is what makes it work. Default instructions: 6 findings. With
`-c developer_instructions=<METHOD>`: 7 findings, 6 P1, every one EXECUTED — it
built scratch repositories and destroyed real files to prove them.

ELEVEN defects were found in this round's own code. ONE was found by a test.


## Outcome

- Signal: corrected
- Correction: I wrote a design conclusion into a docstring from ONE CLI error string, and
committed it as settled fact.

`codex review --base origin/main … -` returned `error: the argument
'--base <BRANCH>' cannot be used with '[PROMPT]'`. From that I concluded that
custom review instructions cannot be combined with base-branch selection, and
therefore that adopting `codex review` costs us the METHOD paragraph — the very
thing this repo has measured as the difference between a review that finds
things and one that agrees with you.

Ray: "dont guess, we have access to the codex source code … run codex lanes to
research". The pinned source sits at `sources/codex/` at the exact version we
run. A lane read the clap definitions and found the answer in minutes:

- The four target arguments ARE mutually exclusive (`codex-rs/exec/src/cli.rs:
  272-305`) — that half was right, and they are variants of one `ReviewTarget`
  enum, so the prompt IS the scope.
- But `-c key=value` is GLOBAL, flattened into `MultitoolCli`, and therefore
  outside the conflict set. `-c developer_instructions="<METHOD>"` delivers our
  instructions WITH `--base`, traced through the source into the reviewer child
  (`core/src/tasks/review.rs:99-127`).

So the capability existed the whole time and I had ruled it out.

THE GENERAL FORM: a CLI's help text and its error strings are SECONDARY
artifacts. The argument definitions are primary. When a tool tells you something
is impossible and it matters, read the code — and in this repo the code is
usually already cloned under `sources/`.

This is the same failure as reading a stale-open issue as current behaviour,
which `probes-need-a-control-arm.md` already records. The new part is that it
happened while I was actively fixing findings about exactly this.
