---
type: "query"
date: "2026-08-17T02:27:10.544810+00:00"
question: "Did the cold review that passed PR #331 actually run cross-family, and what did a real codex pass find?"
contributor: "graphify"
outcome: "corrected"
correction: "A REVIEW LANE'S NAME IS NOT EVIDENCE OF WHICH MODEL RAN, and a receipt that\nrecords the intended lane records nothing.\n\nThe belief overturned: that dispatching `fable-orchestrator:codex-reviewer` and\nreceiving a completion report meant a cross-family review had happened. It did\nnot. The agent type, the agent's name (`cold-codex-…`) and the receipt's\n`cold:codex` were all LABELS chosen by the orchestrator. Nothing in the path\nobserved the model.\n\nThe specific error to not repeat: I reported \"Lane is\n`fable-orchestrator:codex-reviewer` (OpenAI) — checked rather than assumed.\"\nWhat had actually been checked was the AUTHORSHIP of the diff — establishing\nthat a cross-family lane was WARRANTED. Checking that a lane is warranted is not\nchecking that it RAN.\n\nHow to verify, and the trap in the obvious probe:\n\n- `pgrep -f \"codex exec\"` is the probe. `pgrep -f codex` is NOT — on this\n  machine `codex` as a substring matches at least three unrelated things\n  (`OpenSymphony/codex-otel/otelcol-contrib`, the bundled Chrome extension-host,\n  the ChatGPT app). Measured: 19 pids matched `codex` while `codex exec` matched\n  0 at the same instant. A liveness probe that can only answer \"alive\" is not a\n  probe.\n- Confirm by reading the matched pid's `command=`, not by trusting the match.\n- A 0 result is ambiguous between \"not running now\" and \"never ran\". I read it\n  as \"the lane is dead\" when it meant \"the lane is not codex\", and asked the user\n  a question I could have answered by waiting for the completion signal.\n\nThe evidence was already in hand and misread. `pgrep -f \"codex exec\"` returned 0\nthroughout the whole review window; I collected that repeatedly while waiting and\ndrew the wrong conclusion from it.\n\nWhat to do instead, concretely:\n1. Invoke the CLI directly (`cat prompt.md | codex exec --ephemeral --sandbox\n   read-only -c model_reasoning_effort=high -`) when the family property is\n   load-bearing, so the process is yours to observe.\n2. Verify the process exists and read its command line BEFORE writing a receipt\n   that names a vendor.\n3. If the lane cannot be verified, record the lane you can defend\n   (`cold:claude-…`), never the one you intended. A same-family reviewer still\n   catches real defects; the receipt must not imply it was cross-family.\n4. `fable-orchestrator:doctor` answers \"is the lane configured\" — it reported\n   `auth + gpt-5.6-sol access confirmed`, 0 failures, the whole time. A healthy\n   lane that is never invoked looks identical, from the receipt, to one that was.\n\nThe gate-design consequence, worth a ticket: `kb-review-receipt` accepts a\n`--lanes cold:<vendor>` string on trust. Nothing requires evidence the vendor\never ran. Ten historical receipts in this repo claim `cold:codex`; whether any of\nthem were genuine is UNKNOWN and was deliberately not rewritten, because\nrewriting unverifiable history is its own fabrication.\n"
---

# Q: Did the cold review that passed PR #331 actually run cross-family, and what did a real codex pass find?

## Answer

On 2026-08-17, on branch `feat-semantic-corpus-runner` (PR #331), the SAME diff
was reviewed twice:

- A lane dispatched as `fable-orchestrator:codex-reviewer`, named
  `cold-codex-42e82f5a`, reported **0 blocking**. It later disclosed, unprompted,
  that it had **never invoked the `codex` CLI** and was a Claude Sonnet subagent.
  Same model family as the author of every commit in the range.
- A verified `codex exec` run (GPT-5.6 Sol, `--sandbox read-only`,
  `model_reasoning_effort=high`, process observed in the process table) reported
  **8 findings, 4 HIGH and blocking**, each demonstrated by construction.

The four HIGH findings, all on code the same-family lane had passed:

1. Stage directories are trusted without verification, so an empty, corrupt or
   symlinked stage counts as `resumed`/`repaid` and the run exits 0.
   DEMONSTRATED: substituting an unrelated directory for every stage produced
   "58 resumed, 0 failed, success" — silent corpus loss wearing a green result.
2. The `on_chunk_done` guard checks index RANGE, not ordinal UNIQUENESS.
   Duplicate callbacks conceal an unvisited chunk because the accounting counts
   EVENTS and `skipped=max(planned - accounted, 0)` clamps the negative away.
   DEMONSTRATED: 58 callbacks over 57 unique indices -> resumed=58, skipped=0,
   failed=0, success.
3. "Warm" resumption never reads graphify's cache. RE-VERIFIED INDEPENDENTLY: an
   AST walk of `extract_corpus_parallel` in the pinned 0.9.45 finds ZERO
   cache/load/recover calls and only `_checkpoint_chunk`, a writer; the control
   in the same probe finds the checkpoint call, so the probe discriminates. The
   `resumed` (free) vs `repaid` (paid) distinction built this round therefore
   rests on a false premise — every already-staged chunk is always repaid — and
   its test manufactures the "free" case by omitting metadata, asserting a state
   the real system cannot produce.
4. Configured adaptive retries are inert for output truncation: the adapter
   rejects `stop_reason=max_tokens` as `stop-reason-invalid` before graphify can
   observe `finish_reason=length`.

Plus Medium: staging `OSError` bypasses the `except (TypeError, ValueError,
msgspec.DecodeError)` added this round, so the very failure that fix claimed to
close is still half-open. Medium: the graphify skill stamps are still 0.9.44 (a
THIRTEENTH pin site; `mise run kb-skill-refresh`). Low: a comment written this
round asserts `_broken_graph_canary` "deliberately keeps the default" timeout
while the code passes `timeout=30` — CONFIRMED at `eval_cases.py:714` against
the comment at `:873`.

The mechanism is not only "different weights". The codex lane CONSTRUCTED inputs
and watched behaviour — a substituted stage directory, 58 callbacks over 57
indices, a `max_tokens` envelope — while the same-family lane read code and ran
the existing suite. `kb-review`'s own skill file already says method rather than
lane identity is what predicted blockers historically; this round is another
measurement of that.

Bound worth carrying: the codex lane could not run `mise` or `pytest` (no
writable temp dir, `Operation not permitted`), so source was fallback authority
and its demonstrations were direct function calls and constructed probes rather
than suite runs.


## Outcome

- Signal: corrected
- Correction: A REVIEW LANE'S NAME IS NOT EVIDENCE OF WHICH MODEL RAN, and a receipt that
records the intended lane records nothing.

The belief overturned: that dispatching `fable-orchestrator:codex-reviewer` and
receiving a completion report meant a cross-family review had happened. It did
not. The agent type, the agent's name (`cold-codex-…`) and the receipt's
`cold:codex` were all LABELS chosen by the orchestrator. Nothing in the path
observed the model.

The specific error to not repeat: I reported "Lane is
`fable-orchestrator:codex-reviewer` (OpenAI) — checked rather than assumed."
What had actually been checked was the AUTHORSHIP of the diff — establishing
that a cross-family lane was WARRANTED. Checking that a lane is warranted is not
checking that it RAN.

How to verify, and the trap in the obvious probe:

- `pgrep -f "codex exec"` is the probe. `pgrep -f codex` is NOT — on this
  machine `codex` as a substring matches at least three unrelated things
  (`OpenSymphony/codex-otel/otelcol-contrib`, the bundled Chrome extension-host,
  the ChatGPT app). Measured: 19 pids matched `codex` while `codex exec` matched
  0 at the same instant. A liveness probe that can only answer "alive" is not a
  probe.
- Confirm by reading the matched pid's `command=`, not by trusting the match.
- A 0 result is ambiguous between "not running now" and "never ran". I read it
  as "the lane is dead" when it meant "the lane is not codex", and asked the user
  a question I could have answered by waiting for the completion signal.

The evidence was already in hand and misread. `pgrep -f "codex exec"` returned 0
throughout the whole review window; I collected that repeatedly while waiting and
drew the wrong conclusion from it.

What to do instead, concretely:
1. Invoke the CLI directly (`cat prompt.md | codex exec --ephemeral --sandbox
   read-only -c model_reasoning_effort=high -`) when the family property is
   load-bearing, so the process is yours to observe.
2. Verify the process exists and read its command line BEFORE writing a receipt
   that names a vendor.
3. If the lane cannot be verified, record the lane you can defend
   (`cold:claude-…`), never the one you intended. A same-family reviewer still
   catches real defects; the receipt must not imply it was cross-family.
4. `fable-orchestrator:doctor` answers "is the lane configured" — it reported
   `auth + gpt-5.6-sol access confirmed`, 0 failures, the whole time. A healthy
   lane that is never invoked looks identical, from the receipt, to one that was.

The gate-design consequence, worth a ticket: `kb-review-receipt` accepts a
`--lanes cold:<vendor>` string on trust. Nothing requires evidence the vendor
ever ran. Ten historical receipts in this repo claim `cold:codex`; whether any of
them were genuine is UNKNOWN and was deliberately not rewritten, because
rewriting unverifiable history is its own fabrication.
