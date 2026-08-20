---
type: "query"
date: "2026-08-20T07:14:19.701376+00:00"
question: "What did the cold review of d3c38113 establish, and why did eleven reproductions fail to find the .codex/config.toml writer?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the cold review of d3c38113 establish, and why did eleven reproductions fail to find the .codex/config.toml writer?

## Answer

# Cold review of d3c38113: what the round actually established

## The lane

One cross-family lane (codex/OpenAI over a Claude-authored diff), bounded at two
rounds. Round 1 was killed by its 600s watchdog having produced NO findings — it
spent the whole budget on genuine investigation (it got as far as mutating hk's
pinned version in-memory to re-run `_check_ref_bindings`) and never emitted a
report. A timeout costs coverage and buys no rounds, so round 2 was the last one
and was split into three narrower batches at 900s each.

Splitting worked: 3/3 batches completed where 1/1 whole-diff pass had failed.

## The lane substituted itself once, and it was invisible in the report

Batch 3 returned STATUS: complete with confident findings and had never invoked
codex — it judged that the manifest checks needed live network a read-only codex
sandbox lacks, and reviewed directly. The tell was not in the report, which read
like the others. It was on disk: batches 1 and 2 left 365 KB and 670 KB of codex
JSONL event stream; batch 3 left none.

The re-dispatch through codex, with an explicit instruction not to substitute,
found 2 confirmed findings the substitute had missed. So the substitution cost
real coverage, not just an honest label.

**Check for the lane's artifact, not the lane's self-report.** A subagent that
reports which model reviewed is reporting its own belief.

## A finding can be real in direction and wrong in mechanism

Codex found that both manifests warn against the wrong command shape. It blamed
`--refs`. Control-armed against jdx/mise v2026.8.8:

- `git ls-remote --tags <url> v2026.8.8` -> ONE line, the tag object, with AND
  without `--refs`
- `git ls-remote --tags <url> 'v2026.8.8*'` -> both lines; `--refs` then
  suppresses the useful peeled one

So the warning was right to exist and the cited mechanism was wrong: what makes
the call silent is naming the tag EXACTLY, because the commit sits on the peeled
`<tag>^{}` line an exact pattern cannot match. Taking the finding at face value
would have written a false `--refs` explanation into two tracked provenance files.

## A number in my own fix was stale before it shipped

I wrote "11 pytest unit tests" into two memory files as part of fixing a
count-ambiguity finding — while my own fixes had just taken that count to 15.
Correctly measured, wrong on arrival, in the replacement sentence for a finding
about an ambiguous number. Re-derived both (46 hk step tests, 15 unit tests) and
rewrote it to pin 11 to its commit and say the second number moves.

## Guessing at a file's writer does not converge

`.codex/config.toml` was rewritten again with a verbatim copy of
`.claude/settings.json`'s env block. Six candidates refuted by reproduction here
(`codex exec` ephemeral and not, the codex-side session hooks, octo, caveman,
installed graphify), on top of five in #399. Eleven refutations, zero writers
found. Each one is a full reproduce-and-restore cycle.

The instrument that did narrow it, on its first run: what did the transcripts
record around the file's mtime? At **+/-20s, NO EVENTS**. At **+/-45s**, the
nearest was **21.5s before** the write and the next was **120s+ after**. So the
write landed in a quiet stretch, 75s after `/reload-plugins --force`.

**State the window with the result.** Two runs of the same probe on the same
incident said "nothing" and "something 21.5s out", and only the window separates
them — a result quoted without it says almost nothing. My own write-up quoted the
+/-20s figure and the +/-45s detail in the same paragraph as if they were one
run, and CodeRabbit caught it on the PR.

And the conclusion I drew from it was too strong. "It was never a tool call" does
NOT follow: a call that returned earlier can leave behind a process that writes
later, which the module's own docstring says and the prose then ignored. What the
result supports is narrower and still useful — nothing the transcript records ran
in that window, so the next reproduction should not start from the tool calls.

`NO EVENTS in a window that WAS searched` is a finding; it is not the same as no
window searched, and `kb_setup.write_attribution` refuses rather than collapsing
the two.


## Outcome

- Signal: useful