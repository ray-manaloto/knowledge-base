---
type: "query"
date: "2026-08-21T20:02:34.339487+00:00"
question: "Pin-sync round 2026-08-21: how do you bump every first-level pin and its source manifest so nothing reads outdated, and what did the bump surface?"
contributor: "graphify"
outcome: "useful"
---

# Q: Pin-sync round 2026-08-21: how do you bump every first-level pin and its source manifest so nothing reads outdated, and what did the bump surface?

## Answer

Pin-sync round 2026-08-21 (branch tool-sync-0821, PR #439): every first-level pin in mise.toml and pyproject.toml was advanced through its OWNING tool (mise use / mise config set / uv add / uv lock --upgrade), the toolchain source manifests were advanced to the same versions with PEELED commits (codex rust-v0.149.0, rumdl v0.2.58 and mise v2026.8.10 are annotated tags), and the acceptance was Ray's two commands: `mise outdated --local -b -J` -> {} and `uv tree --outdated --all-groups` -> only two upstream-pinned entries (pydantic-core by pydantic 2.13.4, tree-sitter by graphifyy 0.9.48) that `uv lock --upgrade-package` cannot move. Two breakages the bump surfaced were fixed in the same PR: #403 (five tasks on the deprecated Tera arg() helpers -> raw_args = true, set natively) and #438 (kb-tool-sync refused every `mise lock` AND every `mise install` because the lifecycle treated any stderr as a refusal while mise writes lock progress there and this repo's own postinstall hook writes four hk lines there; bounded recognisers, fixtures captured verbatim, kb-arms 4/4 died). kb-build re-extracted 25/69 sources and failed closed at datamodel-code-generator (zero-node pyproject.toml ×3, #417 class); anthropic-sdk-python at v1.0.0 extracted cleanly, so #397's named blocker moved. Review: one cold codex lane, two rounds on the pins (2+1 findings, 0 blocking) and two rounds on the clear-prep flip (3+3 findings, 0 blocking) — every fix round introduced findings inside the text it added. clear-prep is now model-invocable with real triggers and an ask-to-/clear step.


## Outcome

- Signal: useful