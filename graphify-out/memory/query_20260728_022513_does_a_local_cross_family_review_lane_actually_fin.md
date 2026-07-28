---
type: "query"
date: "2026-07-28T02:25:13.215005+00:00"
question: "Does a local cross-family review lane actually find things a Claude author's own tests miss?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a local cross-family review lane actually find things a Claude author's own tests miss?

## Answer

Measured on its own feature, two rounds, yes and repeatedly. The cold codex lane found that --lanes placeholder satisfied the gate; the silent-failure lane found the writer defeated the reader by defaulting --blocking to 0 behind a reader that rejects a missing count; the spec lane found the whole receipt was honor-system; the standards lane found the pre-push re-check was decoration (deleting it kept the suite green). Every one was green under the module's own unit tests first. The sharpest: TWO lanes independently found that _safe() stripped the hyphen so the gate hunted silentfailure.md while every doc said silent-failure.md — the tests could not catch it because they built fixtures with report_path() and inherited the same normalisation, a tautological probe.

## Outcome

- Signal: useful