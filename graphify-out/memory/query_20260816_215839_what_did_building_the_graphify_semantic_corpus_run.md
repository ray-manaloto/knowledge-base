---
type: "query"
date: "2026-08-16T21:58:39.151203+00:00"
question: "What did building the graphify semantic corpus runner reveal about the plan-to-execution gap?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did building the graphify semantic corpus runner reveal about the plan-to-execution gap?

## Answer

The corpus `run` verb returned `provider-execution-not-implemented` and nothing
else in the repository defined that string — the plan could be built and verified
but never executed. Building the missing driver surfaced four defects that were
each invisible until real tokens were spent, and one that made the obvious design
impossible.

**The obvious design is impossible, and a control arm proved it.** The natural
runner is a loop that dispatches each planned chunk. It cannot exist:
`extract_corpus_parallel` re-runs `expand_oversized_files` on whatever it is
handed, which calls `is_splittable_text(f) -> f.suffix`, and `FileSlice` has no
`suffix`. The plan's slice-level units cannot reach the public entry point at
all. Armed both ways — `expand_oversized_files([FileSlice(...)])` raises
`AttributeError` while `expand_oversized_files([Path(...)])` returns — so the
probe discriminates rather than merely failing.

The design that works is the faithful one: the PLANNER built its ledger with
graphify's own `expand_oversized_files` + `_pack_chunks_by_tokens`, so one call
over the admitted FILES at the plan's `token_budget` reproduces that grouping
exactly, with `on_chunk_done` staging each chunk as it completes. Serial
execution is what makes it safe rather than merely slower: the callback fires
between calls, so it can rotate the adapter's single metadata file and its
`O_EXCL` boundary marker before the next call needs those paths.

**Four defects that would only have appeared after spending.** The corpus
verifier kept a private copy of the expected claude argv and rendered the budget
as `str(config.max_cost_usd)` — which agreed with the adapter's literal only
while the cap happened to be `0.25`; at 25.0 it renders `"25.0"` against an argv
carrying `"25.00"`. `claude_required_flags` omitted `--effort` while being
compared for EQUALITY against the receipt. The plan recorded a `concurrency` the
extractor force-overrides. And `_effective_config` hardcoded
`graphify_version="0.9.43"` beside a runtime identity that said 0.9.44, so every
plan since the pin bump recorded two versions for one run.

**`--effort` does not reject a bad value.** Measured on Claude Code 2.1.233:
`claude -p --effort not-a-level` WARNS, discards the value, and runs at DEFAULT
effort. A typo'd level would therefore produce a complete, plausible,
fully-verified, expensive run at the wrong setting, with the mistake visible only
in a warning nothing reads. The prover for it has to parse the CLI's own
`Valid values:` enumeration and confirm the chosen level is in it — the existing
numeric-flag prover asserts "must be a number" and could never have covered this.

**`GRAPHIFY_NO_INCREMENTAL_CACHE` is read for TRUTHINESS**, so setting it to
`"0"` DISABLES the cache. Enabling checkpointing means omitting the name
entirely. A run configured with `"0"` looks warm in every artifact and is cold in
every invoice.

**And a test-suite defect the authorization exposed.** Four tests asserted "no
plan is ever authorized" — true only while `AUTHORITY_JSON` was empty. Because
planning is deterministic, a plan rebuilt from the same pinned source is
byte-identical to the authorized one, so recording the digests made three of
those tests silently describe the opposite case while still passing. Only one
failed. A test that inherits the repository's authorization state is measuring
the repository's mood, not the verifier.


## Outcome

- Signal: useful