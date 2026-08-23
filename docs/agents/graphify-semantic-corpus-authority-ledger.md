---
name: graphify-semantic-corpus-authority-ledger
description: Append-only history of reviewed semantic-corpus execution authority.
---

# Semantic Corpus Authority Ledger

Each bullet records one accepted authority transition. The JSON authority file is the machine-readable source of truth; this ledger preserves the reviewer-facing history. The first bullet was seeded by hand from git history (the authority that landed in `cc265101` and its predecessor in `8929d47f`), not by the verb — its plan predates the `effort` field, so that value reads `not-recorded`; every later bullet is appended by `kb-setup graphify-semantic-corpus record --accept`.

- **2026-08-22T21:07:13Z** — graphify 0.9.47 (b2cd36267456c166788c95be6e68574064a92a42) · claude 2.1.240 · effort not-recorded · cap $100.0 · units 475 / chunks 58 · decision digests: unchanged · plan_manifest 25612cb450dcdb4e538c1e92b46a42a0db8f83223761659e98c5b19c57ef7d03→b4b741b5f0bb992c16f42b57f1e855c751e2de1c331dde1f979c1b80c8fad719 · execution_config 83a1fc8da307c9f86daa414ff064b9135eda4066a54644ae9ce93230b635bc92→710dbbfb2d15ac05c9857bd6f0e14ed03a9b7a858e85936a9adbda568938d9da · HEAD cc26510121c752a87eb0a2002a5c68ca1f90eb01 · superseded none
- **2026-08-23T01:43:58Z** — graphify 0.9.48 (b2cd36267456c166788c95be6e68574064a92a42) · claude 2.1.240 · effort high · cap $63.0 · units 170 / chunks 26 · decision digests: unchanged · plan_manifest b4b741b5f0bb992c16f42b57f1e855c751e2de1c331dde1f979c1b80c8fad719→ef78a85ba194ff4eea2d02a41629ced8cb632cbab965c879fba4ea67b753f73c · execution_config 710dbbfb2d15ac05c9857bd6f0e14ed03a9b7a858e85936a9adbda568938d9da→755943f00b6f591f1eca92b219d413ca07f15ab85c7c28d2b1f9d9b63a2c89a0 · HEAD 29caf0433cde348ed83a47b85cd36907e57f7ab1 · superseded graphify-semantic-corpus.superseded-20260823T014358Z
