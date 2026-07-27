---
type: "query"
date: "2026-07-27T21:25:00.262764+00:00"
question: "Why is stripping AWS_SECRET_ACCESS_KEY/GEMINI_API_KEY by name from a subprocess env not enough on a mise host?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why is stripping AWS_SECRET_ACCESS_KEY/GEMINI_API_KEY by name from a subprocess env not enough on a mise host?

## Answer

Because __MISE_DIFF carries the same VALUES beside them. It is mise's env snapshot (gzip+base64+msgpack over the full new/old env maps), so every value mise's [env] resolved — including SOPS/age-decrypted secrets — rides through untouched. A by-name strip list removes the label and keeps the contents. gitleaks cannot pattern-match a gzip'd blob and mise's redaction is a stdout line filter that never touches a child's environment; v2026.5.6 widened it by propagating the blob to children. Expected upstream behaviour, no fix pending. Fix: kb_setup.graphify_env.clean_env() strips by PREFIX __MISE_ (not by the two known names — a name list is a token-spelling bound that fails open when mise adds a third var). The doubled underscore is load-bearing: public config is MISE_* with one underscore (MISE_DATA_DIR, read by currency.sync) and must survive. Never decode the blob to inspect it — assert on key presence only.

## Outcome

- Signal: useful