---
type: "query"
date: "2026-08-03T14:31:35.572959+00:00"
question: "Bumping mise/hk/fnox: what actually needs care, versus what is routine?"
contributor: "graphify"
outcome: "useful"
---

# Q: Bumping mise/hk/fnox: what actually needs care, versus what is routine?

## Answer

hk is the dangerous one: its version lives in THREE places (mise.toml plus hk.pkl's amends AND import package URLs) and a mise.toml-only bump runs a new binary against old schemas. Assert on the occurrence count, then prove with hk validate + mise run lint. mise's watch item on PATH handling fired for the second release running (2026.8.0's hook-env now restores removed PATH entries; 7.18 deduped exact duplicates) and NEITHER retires resolve_from_path/_is_mise_shim, because our defect is a stale DIFFERENT directory ordered AHEAD of the shims — nothing removed, nothing duplicated. Also: the 'mise dotfiles' deprecation watch item now REFUTES ITSELF — a naive grep returns 8 where the item records 0, and all 8 are the item's own text plus prior currency reports. A watch item that names a token makes itself grep-positive forever; exclude currency.toml and docs/currency/ when re-probing. pyproject: exact-pin [dependency-groups] dev (PEP 735, not installed by consumers) but NOT [project.optional-dependencies], which dotfiles imports as a SHA-pinned git dep — an == there exports our preference as someone else's constraint.

## Outcome

- Signal: useful