---
name: graphify-semantic-corpus
description: Provider-free complete-source planning and evidence contract for Graphify v0.9.42.
---

# Graphify Semantic Corpus

Issue [#301](https://github.com/ray-manaloto/knowledge-base/issues/301) scales the
landed one-document real-provider proof into a complete, reproducible plan for
the exact Graphify v0.9.42 tree. The planner and verifier are provider-free: they
prove what would run, how it would be cached, and how evidence fails closed. One
separately authorized max-chunk boundary attempt is retained below; it does not
authorize the cold run.

## Current exact scope

| Boundary | Exact result |
|---|---:|
| Git commit | `7fe58b0b0f3873be9a21c30106b8b8527c353aa6` |
| Git tree | `15ca81a8dbd3ded7083c4b573197140e62e95fcc` |
| Detected semantic source files | 372 |
| Units after Graphify's 20,000-character expansion | 474 |
| Provisionally admitted units | 470 |
| Typed intentional exclusions awaiting review | 4 |
| Provisional token budget | 20,000 |
| Planned serial calls | 57 |
| Largest estimated chunk | 19,985 tokens / 5 units |

The four decisions are typed, content-addressed intentional exclusions rather than
silent omissions. `docs/demo-path.svg` must regenerate byte-for-byte from the tracked
generator. `worked/rsl-siege-manager/graph.html` must reconcile every embedded node
and edge semantic identity with its tracked companion `graph.json`. The two PNG files must
retain their exact Git bytes and exact README presentation bindings. Those checks run
again against the immutable source tree and fail on drift. They do not claim OCR or
image-semantic coverage, and remain `provisional` until independent review.

Graphify detection also emits one exact large-corpus token-cost advisory for this tree.
Pinned source identifies it as a cost warning, not a partial-detection or correctness
condition: detection still returns the complete typed file set and counts. The planner
therefore preserves the exact commit, detector Git object, thresholds, observed counts,
message, and provisional review state in `advisories.json`. Only that exact advisory is
eligible for separate review; any unknown or additional warning remains fatal. The
public verifier reports structurally complete but `execution_authorized=false`. Earlier
authority roots are deliberately empty because the one-call authority was consumed.
Accepted roots remain only in historical receipts. A fresh checkout therefore reports
`plan-authority-unset`, and deleting output/state cannot make the launcher runnable.
Any replacement roots require a new review outside planner bytes and do not authorize
the full corpus run by themselves.

The planner reuses issue #299's accepted complete Git-source manifest digest
`da56d50eadb82b0889d8e9ad4b1260c98d4d8e6ab413e8abed5ddfcac0bdee68`, so the
source bytes are not in doubt. That baseline cannot erase this warning: #299's
warning-free receipt covers its 410-input deterministic admission and 402-input AST
extraction, whereas #301 invokes Graphify's official full-corpus `detect()` SDK for
semantic scope and receives 782 total files / about 1.37 million words. The only SDK
controls are symlink, Google Workspace, exclusion, cache-root, and gitignore behavior;
there is no supported warning-threshold override. Subdirectory-by-subdirectory
detection would avoid the aggregate advisory by construction and is therefore not
equivalent evidence. The advisory is neither suppressed nor hidden by partitioning.
Full provider execution remains blocked. The first max-size adapter launch replaced
rather than overlaid the ambient auth environment. Its exact inner stderr and boundary
phase were not retained, so the append-only correction records one adapter invocation
and `provider_inferences=unknown`.

A fresh user authorization later allowed exactly one corrected call despite that unknown
state. Independent review removed an unenforceable derived three-turn claim because
Claude Code 2.1.232 exposes no `--max-turns` option. The exact user bounds were Max OAuth,
no API key, no tools, a `$0.25` cap, a 120-second timeout, and no retry. Fresh preflight
proved the reviewed plan, launcher, adapter, prompt, Max first-party auth, and absent
output/state roots before the call. The adapter started one Claude CLI subprocess at the
reviewed provider boundary and failed closed after 35,524 ms. It was not retried. The
marker proves one process-boundary invocation; provider inference remains unknown. Safe
receipts preserve a 53,947-byte CLI stdout digest but not the raw response; the adapter could not derive a typed result
envelope, model usage, or structured output from those bytes. This is an
adapter-observation contract failure. It does not prove a provider or model failure, and
it does not authorize the 57-chunk run. The preserved terminal metadata's
`turn-bound-exceeded` reason came from an obsolete local three-turn post-parse policy;
it is not evidence of the provider's turn count. The #301 adapter now retains observed
positive turn counts without claiming an unenforceable upper bound, while #300 keeps
its independently accepted three-turn contract.

Durable authored evidence is tracked under `docs/agents/evidence/issue-301/`:
the append-only unknown-boundary audit, the exact hardened launcher, and the last
pre-hardening no-inference preflight receipt (retained as historical evidence, not
current authorization). Plan, staging, and earlier preflight artifacts under
`graphify-out/` are derived runtime outputs and remain untracked. The implementation
module remains intentionally cohesive for this incomplete infrastructure slice;
splitting planning, provider evidence, and execution verification is deferred to the
continuation of #301 before full-corpus execution, when their public seams stop moving.

## Plan and execution boundary

```mermaid
flowchart LR
    PIN["Pinned Graphify Git tree"] --> DETECT["Graphify public detection"]
    DETECT --> WARN{"Detection finding"}
    WARN -->|"exact pinned cost advisory"| ADV["Content-addressed advisories.json"]
    WARN -->|"unknown or additional warning"| FAILED["FAILED: typed reason"]
    WARN --> EXPAND["Graphify 20k source expansion"]
    EXPAND --> INV["474-unit source inventory"]
    INV --> DECIDE["4 evidence-bound provisional exclusions"]
    INV --> ADMIT["470 provisionally admitted units"]
    ADMIT --> PACK["57-chunk provisional ledger"]
    PACK --> CONFIG["Exact execution config and cache namespace"]
    ADV --> MANIFEST["Content-addressed plan manifest"]
    DECIDE --> MANIFEST
    CONFIG --> MANIFEST
    MANIFEST --> VERIFY["Read-only typed verifier"]
    VERIFY -->|"review roots unset"| INCOMPLETE["INCOMPLETE: zero provider calls"]
    VERIFY -->|"unknown warning, digest, evidence, coverage, or drift"| FAILED
    VERIFY -->|"historical reviewed one-call authority"| PROTO["One max-size prototype"]
    PROTO -->|"53,947-byte CLI stdout not typed"| BLOCKED["FAILED CLOSED: no retry"]
    BLOCKED --> REVOKE["Active authority roots cleared"]
```

The supported public seam is:

```text
mise run kb-graphify-semantic-corpus -- plan|run|verify [PATH]
```

- `plan` materializes the immutable pin, detects and expands the source, packs
  units, and atomically publishes the plan directory.
- `verify` materializes the exact pinned source snapshot and independently reruns
  detection, advisory counts/message, exclusions, inventory, and ledger before it can
  consider authority. The library verifier requires this snapshot argument; there is
  no artifact-only authorization bypass. It never invokes Claude.
- `run` currently fails closed with a typed abort receipt and zero provider
  calls. Provider execution remains intentionally unimplemented until review.

## Future cache and result lifecycle

```mermaid
stateDiagram-v2
    [*] --> Planned
    Planned --> Aborted: provisional decision or config
    Planned --> Cold: independently authorized
    Cold --> Aborted: first warning, error, timeout, drift, or malformed fragment
    Cold --> Staged: validated fragment, atomic chunk rename
    Staged --> Cold: next ledger chunk
    Staged --> Complete: every planned chunk present
    Complete --> Reuse: exact namespace, zero provider calls
    Complete --> Rebuild: retained fragments, zero provider calls
    Complete --> Variance: separate empty namespace
    Reuse --> Verified: byte parity with cold
    Rebuild --> Verified: byte parity with cold
    Variance --> Verified: exact coverage and nonzero semantic quality
```

The namespace binds source inventory, provisional decisions, chunk ledger, exact
Graphify runtime and semantic/LLM code, planner and adapter bytes, prompt/schema
fingerprints, Claude executable/help/version/requested and resolved model, endpoint and
auth policy, disabled tools, token and file caps, timeout, output/cost/retry bounds,
concurrency, deep mode, and cache policy. A cold run may not read prior fragments.
Provider and adapter agreement is not authority: both are independently compared with
the derived config, tracked Graphify/Claude identities, tracked schema, and a prompt
reconstructed from pinned source bytes plus Graphify's deep extraction prompt bytes.
Each chunk retains the exact provider receipt, exact adapter metadata, semantic
fragment, and a content-addressed stage receipt. Warning-, error-, truncation-,
uncovered-, out-of-scope-, wrong-source-, or malformed evidence is retained with a
typed failed stage rather than rewritten as clean. Publication uses a directory rename
only after the issue #300 referential/source-scope checks and an exact regular-file
census. A stage also binds the exact plan manifest, execution config, prompt and schema
contracts, provider prompt, corpus chunk ordinal/total, source Git object, source byte
size/digest, 20,000-token budget, Graphify chunk/deep/retry/cache/timeout controls, and
Claude model/tool/auth/endpoint/cost controls. Observed turns remain evidence, but no
hard turn cap is claimed because the pinned Claude CLI cannot enforce one. The landed
issue #300 receipt is
valuable real evidence, but its single-file chunking, disabled deep mode, and unset
token budget make it intentionally cache-incompatible with this corpus plan; it is
retained as a typed failed stage and cannot certify a corpus execution.

Execution-mode verification accepts artifact directories, never caller evidence
objects. It opens and lstat-censuses every run root and staged chunk; rehashes the
provider receipt, adapter metadata, fragment ledger, semantic fragments, and graph;
then reconciles exact plan units, source identities, counts, namespaces, config, and
call semantics. Reuse and rebuild must make zero provider calls and reproduce retained
byte identities; variance uses a fresh namespace and compares exact coverage and
positive semantic quality, not nondeterministic provider bytes. Review-owned authority
roots live in a separate importable module, outside the planner bytes whose digest the
execution config binds, so authorization can converge without changing its target.
The verifier deterministically rebuilds the semantic-only graph from the retained
fragments through Graphify's public SDK, requires exact exported graph-byte equality,
and independently checks node, edge, hyperedge, and source provenance references.
Issue #301 does not compose the issue #299 AST graph: issue #302 owns AST/semantic
composition and continuity, so claiming that continuity here would be a false positive.

The prototype marker and staged output deliberately have separate topologies. The
launcher creates only `graphify-semantic-corpus-prototype-corrected-state/` before the
adapter call; `graphify-semantic-corpus-prototype-corrected/` remains absent for the
atomic stage publisher. Marker creation is kernel-exclusive and refuses concurrent or
pre-existing destinations rather than checking and later replacing a path. The adapter
opens the marker parent as a no-follow directory descriptor, creates the marker relative
to that descriptor, and fsyncs both the file and parent directory.
Before creating state, the topology contract rejects lexical `..`, any symlinked
ancestor, equal or nested canonical identities, and non-sibling roots. It creates and
returns the marker only after creating state relative to an already-opened trusted
parent descriptor while leaving the resolved output absent. A later parent swap cannot
redirect marker creation: the adapter refuses a symlinked replacement. Preflight
independently binds the imported topology-contract
bytes as well as the launcher and adapter, so a changed helper cannot inherit an
accepted launcher identity.

The immutable cache namespace is the execution-config digest; a separate per-run
namespace locates staged artifacts. Cold, reuse, and rebuild share the cache-derived
run namespace. Variance keeps the same cache identity but uses a distinct fresh run
namespace. A changed cache namespace is drift, while a fresh variance run namespace is
the intended isolation control.

The exact-plan tests regenerate the plan from the pinned Graphify source into pytest
temporary storage. They do not read the untracked runtime corpus/prototype directories,
so a fresh checkout cannot inherit locally generated acceptance bytes.

The HTML exclusion preserves the source order and multiplicity of every normalized
node and edge identity. Duplicate node IDs or edge identities fail explicitly before
HTML and companion-graph lists are compared. The PNG evidence parser binds the exact
expected `src` to its own `alt`, and binds the graph screenshot to the immediately
following exact caption block; matching prose or alternate-image attributes elsewhere
in the README cannot satisfy the contract.

```mermaid
flowchart LR
    PLAN["Reviewed plan bytes"] --> RUN["Exact run artifact directory"]
    REAL["Real provider result"] --> PR["Provider receipt"]
    REAL --> AM["Adapter metadata"]
    REAL --> SF["Semantic fragment"]
    PR --> STAGE["Atomic staged chunk"]
    AM --> STAGE
    SF --> STAGE
    STAGE --> FL["Content-addressed fragment ledger"]
    FL --> REBUILD["Graphify SDK semantic rebuild"]
    REBUILD --> EXPECTED["Expected semantic graph bytes"]
    GRAPH["Retained semantic graph bytes"] --> RUN
    FL --> RUN
    RUN --> VERIFY["Read-only census, rehash, and reconciliation"]
    EXPECTED --> VERIFY
    VERIFY -->|"warning, truncation, drift, gap, or fabricated struct"| FAIL["FAILED"]
    VERIFY -.->|"future full reviewed evidence"| COMPLETE["COMPLETE"]
    AST["Issue #299 AST baseline"] -.-> NEXT["Issue #302 composition boundary"]
    COMPLETE -.-> NEXT
```

```mermaid
flowchart LR
    CONFIG["Immutable execution config"] --> CACHE["Cache namespace digest"]
    CACHE --> NORMAL["Cold, reuse, rebuild run namespace"]
    CACHE --> VAR["Variance keeps cache identity"]
    FRESH["Fresh per-run namespace"] --> VAR
    WRONG["Changed cache namespace"] -->|"typed drift"| FAIL["FAILED"]
```

## Remaining decision sequence

1. Preserve the first-attempt unknown audit and corrected one-call terminal receipts
   without rewriting either history.
2. Diagnose the adapter observation boundary from source and public-safe receipts. The
   retained evidence proves Claude CLI subprocess return code zero, zero stderr, 53,947 stdout
   bytes, and an empty typed envelope; it cannot distinguish invalid JSON from a
   non-object JSON top level because raw response bytes and parse status were not retained.
3. Decide and review a no-call parser-diagnostic improvement that retains only a typed
   parse classification and bounded public metadata. Do not reconstruct or fabricate the
   discarded response.
4. Keep the cold 57-chunk run and issue #302 blocked. Any later provider call requires a
   new explicit authority; the corrected prototype authority is consumed.

```mermaid
sequenceDiagram
    participant Review as Independent review
    participant Adapter as Hardened adapter
    participant CLI as Claude CLI boundary
    participant Evidence as Public-safe evidence
    Review->>Adapter: Exact one-call authorization
    Adapter->>Evidence: fsync provider-boundary-start marker
    Adapter->>CLI: One subprocess invocation, no tools, no retry
    CLI-->>Adapter: rc 0, stderr 0, 53,947 stdout bytes
    Adapter->>Evidence: Empty typed envelope and failed stage
    Evidence-->>Review: Hashes and typed reasons, raw response excluded
    Note over Adapter,CLI: Provider inference unknown; no retry or full-corpus run
```
