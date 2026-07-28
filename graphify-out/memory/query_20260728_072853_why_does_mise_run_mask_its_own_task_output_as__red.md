---
type: "query"
date: "2026-07-28T07:28:53.048779+00:00"
question: "Why does mise run mask its own task output as [redacted], and what populates the redaction set?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does mise run mask its own task output as [redacted], and what populates the redaction set?

## Answer

mise redaction is a DISPLAY feature: Redactor::redact is an Aho-Corasick multi-pattern literal-substring replace with '[redacted]' (jdx/mise src/redactions.rs:64-81, v2026.7.15), no word boundaries and no length floor — its own test asserts 'token1 and token2' -> '[redacted]1 and [redacted]2'. The set is populated by _.fnox-env in the USER-level mise config (~/.config/mise/config.toml:64), NOT by this repo's mise.toml [env] — which is why a prior probe of this repo's [env] correctly found nothing and wrongly generalised. Discriminator: with the user config ignored, the three vars are absent from mise env (0) and the redacted set is empty (0); honoured, 3 and 3 — while the same secrets sit in the ambient shell in BOTH arms. Before 2026-07-27 fnox defaulted to env=true and exposed all 49 declared secrets including one-character telemetry flags, so the literal string '1' was in the set and every digit mise printed was masked. Ray's env='exec' change cut it to three 36-40 char values. Also: redactions.rs:31 filters EMPTY patterns, so an empty redacted value masks nothing — flagging it is a false positive.

## Outcome

- Signal: useful