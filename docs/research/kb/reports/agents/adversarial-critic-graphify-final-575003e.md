---
name: adversarial-critic-graphify-final-575003e
description: Final replay of source authority controls and credential boundaries.
---

# Adversarial critique — Graphify final 575003e (2026-08-12)

Proposal under critique:

1. The public 20-source authority check passes valid state, rejects three coordinated substitutions, and keeps credentials out of argv/output.

Record replayed against: commit `575003ee977781ecf9abcf6d178fd85a6d10b160`
at `/private/tmp/kb-graphify-clean.55nHWG/repo`, including the real
`sources/groups/graphify-ecosystem.toml`, its 20 public sources, the public
`kb-source-groups-check` task, and focused credential-boundary tests.
The required project Graphify orientation query was attempted first but could
not run because this checkout has no `graphify-out/graph.json`; no graph result
is claimed as evidence.

| # | Verdict | Proposal | Fires on its motivating cases? | Shape |
|---|---|---|---|---|
| 1 | KEEP / ACCEPT | Authenticate remote source authority through a fixed `fnox` → `gh api` boundary | Valid 20-source control: PASS; hostile coordinated substitutions: 3 of 3 REJECT; credential boundary: 2 of 2 PASS | None |

## 1. Authenticated source authority and credential boundary — KEEP / ACCEPT

The proposal replaces the unauthenticated GitHub request that made the valid
20-source control fail at commit `90fe2ef` with an authenticated, fixed-argv
`fnox exec --non-interactive -- gh api` call. It is also intended to preserve
the rejection of the three registry-plus-baseline substitution defects fixed
after `80994db`: a ghost repository identity, a nonexistent source path, and an
all-`a` content hash.

Replay matrix:

| Case | Expected | Result |
|---|---|---|
| Unmodified real 20-source registry | PASS | PASS (`rc=0`, `source_count=20`) |
| Registry + baseline changed to ghost repository | REJECT | REJECT (`rc=1`) |
| Registry + baseline changed to nonexistent path | REJECT | REJECT (`rc=1`) |
| Registry + baseline changed to all-`a` SHA-256 | REJECT | REJECT (`rc=1`) |
| Exact credential argv and scrubbed ambient-token environment | PASS | PASS |
| Failure receipt excludes secret-bearing stderr | PASS | PASS |

Valid public control, verbatim:

```text
[kb-source-groups-check] $ uv run kb-setup source-groups-check
{"group_id": "graphify-ecosystem", "path": "/private/tmp/kb-graphify-clean.55nHWG/repo/sources/groups/graphify-ecosystem.toml", "source_count": 20, "statuses": {"REJECTED": 4, "REVIEWING": 16}}
```

Hostile coordinated mutations, verbatim:

```text
source-groups-check: FAIL: ghost-context-protocol: GitHub authority failed rc=1; stderr-bytes=25 stderr-sha256=d2c8985c89b29a842ac4946d13bdbc297709f44f20bb968faf9682664b211db6
ghost_identity_rc=1
source-groups-check: FAIL: program-context-protocol: GitHub authority failed rc=1; stderr-bytes=25 stderr-sha256=d2c8985c89b29a842ac4946d13bdbc297709f44f20bb968faf9682664b211db6
nonexistent_path_rc=1
source-groups-check: FAIL: program-context-protocol: GitHub authority failed rc=1; stderr-bytes=81 stderr-sha256=262729fd42e7be7ef358034948111b331394f5c98d48e82be4a5f1d55aaf286e
aaaa_sha_rc=1
```

Credential and argv replay, verbatim:

```text
tests/test_source_groups.py::test_github_authority_uses_exact_fnox_gh_boundary_and_scrubs_ambient_tokens PASSED [ 20%]
tests/test_source_groups.py::test_github_authority_retains_stderr_receipt_without_serializing_secret PASSED [ 40%]
tests/test_source_groups.py::test_public_check_rejects_registry_and_baseline_co_mutation[ghost-repo] PASSED [ 60%]
tests/test_source_groups.py::test_public_check_rejects_registry_and_baseline_co_mutation[nonexistent-path] PASSED [ 80%]
tests/test_source_groups.py::test_public_check_rejects_registry_and_baseline_co_mutation[aaaa-sha] PASSED [100%]

============================== 5 passed in 1.13s ===============================
```

The fixed argv contains no credential. The child environment removes ambient
GitHub tokens and mise activation variables before `fnox` supplies the narrowly
scoped credential. Failure reporting retains only stderr byte count and SHA-256,
not raw stderr. The real positive arm proves the authenticated path is usable;
the three negative arms prove the remote authority check still discriminates
coordinated substitutions.

The local schema and immutable baseline checks fire before the remote authority
checks; remote repository identity, commit, path, and content are then checked
against GitHub. The public task is on-demand rather than eager prose. Its real
control took about 29 seconds, a proportionate cost for a network authority
gate.

Verdict: **ACCEPT**. This proposal catches each motivating substitution while
allowing the real 20-source state, and its credential boundary does not expose
the secret in argv or diagnostics.

## What survives, and what the survivor does NOT cover

The authenticated authority gate covers registry/baseline coordinated source
substitution. It does not constitute evidence that a full Graphify corpus build
or query completed; no such claim is needed for this final source-authority
verdict.

## Re-verified before reporting

Immediately before reporting, I re-read the fixed argv, scrubbed environment,
stderr receipt, and focused tests at HEAD; HEAD remained
`575003ee977781ecf9abcf6d178fd85a6d10b160`. The critiqued implementation and
tests had not moved.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — read-only review checkout and public source-authority replay.
- [program-context-protocol/program-context-protocol](https://github.com/program-context-protocol/program-context-protocol) — read-only real and hostile source-identity control target.
