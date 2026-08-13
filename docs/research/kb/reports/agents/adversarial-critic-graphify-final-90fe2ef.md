---
name: adversarial-critic-graphify-final-90fe2ef
description: Final critical replay of coordinated source registry and baseline substitution.
---

# Adversarial critique — Graphify final 90fe2ef (2026-08-12)

Proposal under critique:

1. Coordinated registry and baseline identity/evidence substitution is rejected.

Record replayed against: `90fe2ef58096d2b325a155fd0802268049a67f67`
over `80994db620ac53cf8fd766d1ab24a26d24536c37`, through the public
`kb-setup source-groups-check` boundary. The derived graph is absent.

| # | Verdict | Proposal | Fires on its motivating cases? | Shape |
|---|---|---|---|---|
| 1 | BLOCK | Remote authority rejects coordinated identity/path/SHA substitution | All three mutations FIRE, but the unmodified real registry also fails with HTTP 403 | 2 |

## 1. Coordinated source substitution — BLOCK

Restated: resolve each repository and reviewed commit through GitHub and hash
each evidence path's raw bytes, preventing coordinated edits to the registry and
its local baseline from self-certifying. The motivating defects are the ghost
identity, nonexistent evidence path, and `aaaaaaaa…` SHA substitutions.

Replay:

| Case | Public result |
|---|---|
| Registry+baseline ghost identity | FIRES: rc=1, repository HTTP 404 |
| Registry+baseline nonexistent evidence path | FIRES: rc=1, raw path HTTP 404 |
| Registry+baseline 40-`a` reviewed/evidence SHA | FIRES: rc=1, commit HTTP 422 |
| Unmodified committed registry+baseline | **FAILS TOO**: rc=1, commit HTTP 403 |

Mutation replay, verbatim:

```text
source-groups-check: FAIL: ghost-context-protocol: remote authority returned HTTP 404 for https://api.github.com/repos/ghost-context-protocol/ghost-context-protocol
ghost_identity_rc=1
source-groups-check: FAIL: program-context-protocol: remote authority returned HTTP 404 for https://raw.githubusercontent.com/program-context-protocol/program-context-protocol/8a5eccc6a2034ab61c9d0738dedbc988ee9fda23/src/pcp/does-not-exist.py
nonexistent_path_rc=1
source-groups-check: FAIL: program-context-protocol: remote authority returned HTTP 422 for https://api.github.com/repos/program-context-protocol/program-context-protocol/commits/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
aaaa_sha_rc=1
```

Real control, verbatim:

```text
[kb-source-groups-check] $ uv run kb-setup source-groups-check
source-groups-check: FAIL: felipefrizzo-dotfiles: remote authority returned HTTP 403 for https://api.github.com/repos/felipefrizzo/dotfiles/commits/b26fa972413e0476a461b887523171d283e2afbf
[kb-source-groups-check] ERROR task failed
```

The exact motivating substitutions are now caught. But the control establishes
shape 2 at the public boundary: invalid mutations and the committed valid set
all receive refusal. `_fetch_remote` sends no authentication, while the task
makes repository and commit API requests across 20 sources. Fail-closed
unavailability is an honest state, but it cannot serve as positive shipping
evidence.

What fires first: local validation, then sequential live GitHub requests. The
remote authority closes the old two-file substitution hole, but request
availability dominates the valid control before completion.

Critical verdict: **BLOCK**. ACCEPT requires the same unmodified public control
to pass; mocked tests cannot replace it.

## What survives, and what it does NOT cover

Remote repository/commit/raw-byte verification correctly covers all three prior
substitutions. It does not currently provide a reliable positive result through
the unauthenticated public task.

## Re-verified before reporting

Immediately before reporting I re-read the verdict-bearing public dispatch and
remote fetch code in `source_groups.py`. HEAD remained
`90fe2ef58096d2b325a155fd0802268049a67f67`; implementation and tests had no
local diff.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base)
  — read-only replay; only this critique report was created locally.
- [program-context-protocol/program-context-protocol](https://github.com/program-context-protocol/program-context-protocol)
  — remote identity, commit, and evidence used by the negative replay.
- [felipefrizzo/dotfiles](https://github.com/felipefrizzo/dotfiles)
  — the unmodified control received HTTP 403 at its commit check.
