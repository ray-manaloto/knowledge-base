---
type: "query"
date: "2026-08-22T21:45:53.959656+00:00"
question: "Did session-review ever check the open issues against the next graphify deep-extraction run, and is the model/effort used actually tracked?"
contributor: "graphify"
outcome: "useful"
---

# Q: Did session-review ever check the open issues against the next graphify deep-extraction run, and is the model/effort used actually tracked?

## Answer

NO — and, before `db7f9991` (the commit this same round then made), it could not
have: the eight lanes committed at that point all read TRANSCRIPTS. Control-armed at
that state: `grep -c "gh issue" .claude/workflows/session-review.js` -> 0, against
`grep -c "transcript"` -> 13. (From `db7f9991` on, the ninth lane below reads the
issue backlog; this paragraph describes the state the question was asked in.)

An `extraction-readiness` lane DID run once, ad hoc, on 2026-08-21, producing
F1-F13 and finding the corpus P0 (#426). It was NEVER in `LANES` — zero hits across
all four historical revisions of the file. So the question became unaskable the
moment that round ended, and FIVE of its thirteen findings were still unfiled a
day later.

That is the "detectors that nothing invokes run zero times" lesson arriving a
SECOND time in the same file — the first time about `tooling-gap` being left out
of handoff mode, this time about a lane that was never in the list at all. A lane
kept outside the default set is a lane that runs once.

On the specific question — is model/effort tracked?

- The MODEL is: `execution-config.json` carries `claude_model`, `claude_canonical_model`,
  `resolved_model`, plus `max_turns` and `deep_mode`.
- The EFFORT VALUE IS NOT, anywhere machine-readable. `--effort` appears only as a
  FLAG NAME inside `claude_required_flags`. Control-armed: `'high' in json.dumps(cfg)`
  -> False, while `deep_mode` and `max_turns` ARE real fields, so the probe
  discriminates. The value lives at `graphify_semantic_slice.py:567`
  (`CORPUS_PROFILE.effort="high"`) and is bound only INDIRECTLY via
  `semantic_slice_sha256`, a module digest — tamper-evident but UNREADABLE. You can
  prove effort did not change; you cannot say what it was without checking out that
  commit.
- Per-file provenance does not exist at all: `ls sources/*.extraction-provenance.json`
  -> no matches, against 73 `sources/*.manifest`. That is #411, designed and unbuilt.

And on switching family (Claude -> codex): NOT a config knob. `backend="claude-cli"`
is a literal at three sites and is checked for EQUALITY at
`graphify_semantic_slice.py:1488` (`receipt-backend-mismatch`), so a codex-backed run
would be PAID FOR and then rejected chunk by chunk — the same shape as #426. Zero of
222 open issues propose a non-Claude extraction family, against a control of 35
mentioning graphify.

The compound finding nobody had assembled: write-only checkpointing
(`check_semantic_cache` -> 0 call sites in installed 0.9.48 `llm.py`, control
`save_semantic_cache` -> 2) + `max_total_cost_usd = 100.0` against 58 x 1.12 = 64.96
+ no `timeout` on the one ~10.6-hour task while eight others declare one. Any one is
survivable; together, an interruption past chunk 31 costs a fresh authorization.

Filed: #455, #456; amended #411, #417, #397. Lane added in `db7f9991` and put in
HANDOFF_LANES deliberately — making it opt-in would rebuild the same failure.

The durable lesson, wider than graphify: A LANE THAT IS NOT IN THE DEFAULT SET RUNS
ONCE. When an ad-hoc sweep finds something expensive, the finding is only half the
value; committing the sweep is the other half, and it is the half that gets skipped.


## Outcome

- Signal: useful