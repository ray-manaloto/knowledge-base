---
name: graphify-semantic-corpus-authority-ledger
description: Append-only history of reviewed semantic-corpus execution authority.
---

# Semantic Corpus Authority Ledger

Each bullet records one accepted authority transition. The JSON authority file is the machine-readable source of truth; this ledger preserves the reviewer-facing history. The first bullet was seeded by hand from git history (the authority that landed in `cc265101` and its predecessor in `8929d47f`), not by the verb — its plan predates the `effort` field, so that value reads `not-recorded`; every later bullet is appended by `kb-setup graphify-semantic-corpus record --accept`.

- **2026-08-22T21:07:13Z** — graphify 0.9.47 (b2cd36267456) · claude 2.1.240 · effort not-recorded · cap $100.0 · units 475 / chunks 58 · decision digests: unchanged · plan_manifest 25612cb450dc→b4b741b5f0bb · execution_config 83a1fc8da307→710dbbfb2d15 · HEAD cc265101 · superseded none
- **2026-08-23T01:43:58Z** — graphify 0.9.48 (b2cd36267456) · claude 2.1.240 · effort high · cap $63.0 · units 170 / chunks 26 · decision digests: unchanged · plan_manifest b4b741b5f0bb→ef78a85ba194 · execution_config 710dbbfb2d15→755943f00b6f · HEAD 29caf043 · superseded graphify-semantic-corpus.superseded-20260823T014358Z
