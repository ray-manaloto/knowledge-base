---
type: "query"
date: "2026-08-01T00:13:43.845050+00:00"
question: "How did the `2026-07-31-1348-kb-fluent-stale-graph` goal round actually behave when run?"
contributor: "graphify"
outcome: "useful"
---

# Q: How did the `2026-07-31-1348-kb-fluent-stale-graph` goal round actually behave when run?

## Answer

result=achieved turns=41. All 7 verification items met. P1-P4 landed the sha256 input fingerprint, the [graph] detector and its four states (never-built / not-verifiable / changed / ok), wired into kb-currency-check. P5-P6 read graphify 0.9.31 and mise 2026.7.17+7.18 notes, then bumped graphify (pin + manifest + a second full rebuild) and mise expected+soft floor. Cold lane (codex, cross-family) ran the full 2-round bound and found FOUR real P2 defects, all mine: the input digest ran 17 lines AFTER mf.load_all had already read the manifests (the exact false green its own comment claimed to prevent); min_version.soft did not move with currency.toml expected, repeating a drift the file's own comment warns about by name; input_fingerprints OMITTED an unreadable file, so a NEW-and-unreadable input was absent from both maps and _diff's union never saw it - a reproduced false-clean; and a mid-build chunk-mutation window, recorded as inherent rather than fixed. Three fixed with both-arm mutation proofs, one recorded. Evaluator: Opus 5. Lesson: every one of the four was in code I had reasoned about carefully and commented confidently - prose agreeing with itself is not verification.

## Outcome

- Signal: useful