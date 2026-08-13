---
name: adversarial-critic-graphify-follow-up-80994db
description: Critical replay of the two blockers from the Graphify fail-closed critique.
---

# Adversarial critique — Graphify follow-up 80994db (2026-08-12)

Proposals under critique:

1. Lifecycle wiring now rejects missing evidence rather than classifying it complete.
2. Source-group validation now rejects identity and evidence substitution.

Record replayed against: `80994db620ac53cf8fd766d1ab24a26d24536c37`
over `72c464caeb464d3e4ae4d5465e4759b9bbbd6531`, using the public
`kb-setup`/mise boundaries and mutations from the first critique. The derived
graph remains absent, so no corpus build/query result is claimed.

| # | Verdict | Proposal | Fires on its motivating cases? | Shape |
|---|---|---|---|---|
| 1 | KEEP | Missing lifecycle evidence is incomplete and lifecycle operations are wired | YES: every operation rejects absent evidence, and non-query lifecycle call sites now exist | — |
| 2 | KILL | Baseline makes source identity/evidence immutable | Registry-only substitution: YES. Consistent registry+baseline substitution: NO, both exact blocker mutations pass | 1, 5 |

## 1. Lifecycle wiring and missing evidence — KEEP

Restated: require an explicit `observed=True` before any Graphify health receipt
can be complete, and connect non-query lifecycle work to required receipts. The
motivating defect was exact: `assess(GraphifyOperation.BUILD)` with no evidence
returned `COMPLETE`, while only QUERY had a real health call site.

Replay:

| Case | Result |
|---|---|
| Missing evidence for HEALTH/QUERY/DETECT/EXTRACT/BUILD/REFLECT/ARTIFACT | FIRES: all seven are `incomplete`, reason `evidence-missing` |
| Real lifecycle wiring | FIRES: DETECT, EXTRACT, BUILD, REFLECT, and ARTIFACT now occur at production call sites; QUERY remains wired |
| Fresh absent control term | NO match, confirming the source-call search discriminates |
| Focused negative suite | 8 missing-evidence/partial cases pass |

Verbatim replay:

```text
health: state=incomplete reasons=('evidence-missing',)
query: state=incomplete reasons=('evidence-missing',)
detect: state=incomplete reasons=('evidence-missing',)
extract: state=incomplete reasons=('evidence-missing',)
build: state=incomplete reasons=('evidence-missing',)
reflect: state=incomplete reasons=('evidence-missing',)
artifact: state=incomplete reasons=('evidence-missing',)
```

Control-armed wiring search:

```text
python/src/kb_setup/cli.py:165:                graphify_health.GraphifyOperation.ARTIFACT,
python/src/kb_setup/cli.py:408:            graphify_health.GraphifyOperation.BUILD,
python/src/kb_setup/artifacts.py:82:        graphify_health.GraphifyOperation.ARTIFACT,
python/src/kb_setup/graphify_sdk.py:214:        GraphifyOperation.EXTRACT,
python/src/kb_setup/graphify_sdk.py:235:        GraphifyOperation.BUILD,
python/src/kb_setup/graphify_sdk.py:281:        GraphifyOperation.ARTIFACT,
python/src/kb_setup/graph.py:134:        graphify_health.GraphifyOperation.EXTRACT,
wired_control_rc=0
fresh_absent_control_rc=1
```

The focused suite returned `12 passed in 1.00s`; eight cases cover all seven
missing-evidence operation values plus the prior `PARTIAL: 278/562` query.

What fires first: missing observation is added to reasons before the receipt can
be classified complete; real callers set `observed=True` only after executing
and collecting their evidence. Project-local library/task placement has no eager
prose cost. This catches its exact motivating defect.

## 2. Source identity/evidence immutability — KILL

Restated: bind registry membership, repository identity, reviewed commit, and
capability evidence to `graphify-ecosystem.baseline.json` so substitution cannot
pass the public source-group check. The motivating defect was consistent
substitution of an identity or an evidence path/reviewed SHA while retaining a
structurally valid 20-record registry.

Replay:

| Mutation | FIRES? | Result |
|---|---|---|
| Unmodified registry + baseline | FIRES/PASS: 20 sources, 16 REVIEWING, 4 REJECTED |
| Registry-only identity substitution | FIRES/REFUSES: membership differs |
| Registry-only path/SHA substitution | FIRES/REFUSES: reviewed commit differs |
| Registry + baseline identity substitution together | **NO** | public `kb-setup source-groups-check` returns 0 |
| Registry + baseline nonexistent evidence path and reviewed/evidence SHA substitution together | **NO** | public command returns 0 |

The first two negative arms prove the comparison runs. The exact consistent
substitution replay is verbatim:

```text
{"group_id": "graphify-ecosystem", "path": "/private/var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/tmp.lpULJvBgQ1/sources/groups/graphify-ecosystem.toml", "source_count": 20, "statuses": {"REJECTED": 4, "REVIEWING": 16}}
co_mutated_identity_rc=0
{"group_id": "graphify-ecosystem", "path": "/private/var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/tmp.lpULJvBgQ1/sources/groups/graphify-ecosystem.toml", "source_count": 20, "statuses": {"REJECTED": 4, "REVIEWING": 16}}
co_mutated_evidence_sha_rc=0
```

The baseline's `content_sha256` is checked only for 64 lowercase hex
characters. The task does not resolve the evidence path at the reviewed commit
or hash those bytes, so retaining the old hash beside a fabricated path passes.
Both files are ordinary editable inputs in the same change; neither is an
independent retained receipt.

This is shape 1 on the motivating *consistent* substitutions and shape 5: the
reviewer deciding not to rewrite the baseline is the saving throw, not the gate.
What fires first is the within-change equality check; it is dominated by an
attacker or mistaken editor changing both sides together.

KILL the immutability claim. The structural baseline comparison is worth filing,
but it becomes enforcement only when the baseline is independently anchored or
the task resolves each path at `reviewed_commit` and compares its actual SHA-256
to the retained digest.

## What survives, and what the survivors do NOT cover

The lifecycle fix survives completely for the exact previous blocker. The
source-group baseline survives only as a same-change consistency check. It does
not cover coordinated registry/baseline substitution or prove evidence bytes
exist at the claimed remote commit.

## Re-verified before reporting

Immediately before reporting I re-read the verdict-bearing changes in
`graphify_health.py`, `graphify_sdk.py`, `graph.py`, `cli.py`, `brain.py`, and
`source_groups.py`, plus the new baseline mutation tests. HEAD was still
`80994db620ac53cf8fd766d1ab24a26d24536c37`; no implementation file was edited.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base)
  — read-only replay; only this critique report was created locally.
