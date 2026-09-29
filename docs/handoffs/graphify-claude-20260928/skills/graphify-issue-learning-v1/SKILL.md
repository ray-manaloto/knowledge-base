---
name: graphify-issue-learning-v1
description: Classify newly observed Graphify rebase and KB integration failures against a bounded transcript-backed issue ledger.
---

# Graphify issue learning

Run only after the existing `wait_threads` snapshot and `mise run watch-probe` says `CHANGED`, or the native delivery task reaches a terminal state. A valid `NO_CHANGE` while delivery is active ends the tick before this skill. The watch owns this skill, `GRAPHIFY-FORK-KB-ISSUE-HISTORY-20260928.md`, `issue_history_check.py`, and `issue-history-state.json`; it never edits the delivery checkout, index or native goal.

1. Run `mise run issue-history-check` from process-audit. A `CONFIGURATION_FAILURE` is a watch failure; stop using the ledger until its hash and ID set are repaired deliberately.
2. From the new probe reasons and named direct receipts, identify a concrete failed invariant. Do not classify an index update, running process, historical search snippet, outer-green wrapper, or changed source alone as a new failure. Obtain the exact source SHA and direct receipt SHA. Run `mise run issue-history-check -- --event-key <stable-class-key> --source-sha <64-hex> --evidence-sha <64-hex> --known-id <F/K ID> --commit` for a known class. `NO_CHANGE` ends same-input work; `KNOWN_CLASS_REVALIDATION` requires the existing gate at the changed source. Do not add `--known-id` for a genuinely new class.
3. On `NEW_CLASS_REVIEW`, use the installed `agentsview-finding-history` skill to search recorded parent sessions with the remote daemon. If unavailable, record the coverage gap; do not fabricate transcript evidence. Keep each pass to 4–6 probes and 2–4 parent windows; use FTS if hybrid is unavailable, filter this watcher, cite session ordinal ranges and anchors, and corroborate against native turns and direct rc/receipts. Do not recrawl all history every tick or publish private transcripts.
4. Add the new class once to a watch-owned, separately hash-bound ledger addendum. Classify historical versus current and confirmed versus refuted hypotheses. Route a single actionable correction to the sole delivery writer when needed; the writer owns production controls. Specify a thin Codex/Claude skill → canonical mise task → reusable Python predicate with positive, negative, unchanged-input, changed-source and failure-mutation checks. Recheck the next exact-head attempt, retaining failed historical evidence.

For Claude takeover, read the history ledger before the packet's build and live-case steps. The ledger is diagnostic context, never transfer authorization or acceptance. Respect the existing three-phase single-writer protocol and original delivery gates.
