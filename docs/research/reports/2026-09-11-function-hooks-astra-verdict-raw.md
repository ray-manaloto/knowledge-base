**Q9 verdict: put the TypeScript shell parser in its own ticket; ship the settings guard first and retain the tested Python parser until a replacement proves equivalent behavior.**

Your measurements are the repository baseline for this advice. The required graph query failed because mise could not create a temporary file in this read-only session; graph health remains **UNVERIFIED**. No repository files were changed.

**1. Step zero: reuse existing tooling before building infrastructure.**

The important distinction is between a dependency usable by repository tooling and one usable **inside the mod loader**. Node-based tools can run through mise during development without being importable by a function hook.

| Candidate | Recommendation | Reachability and deciding reason |
|---|---|---|
| Anthropic’s generated `claude-code.d.ts` and published built-in mods | **Adopt as the runtime reference.** Regenerate declarations from the pinned executable; record its version and declaration digest. | Anthropic publishes complete mod examples using `/plugin-types` declarations and explicitly warns that the early-access API can change. This avoids inventing a parallel SDK contract. [Official mod sources](https://github.com/anthropics/claude-code/tree/main/mods) |
| Native `claude plugin validate` | **Adopt for packaging validation**, through a repository task. | It checks plugin structure and schemas. It does not prove module execution or enforcement. Whether its validation fully covers this preview’s module constraints is **UNVERIFIED**. [Plugin validation reference](https://code.claude.com/docs/en/plugins-reference#plugin-validate) |
| Claude Agent SDK | **Consider as an external live-test driver**, if existing repository tooling does not already provide one. | It belongs outside the mod. Equivalence between its launch/configuration path and Ray’s normal CLI sessions is **UNVERIFIED** and must be tested. Prefer the actual CLI when that avoids another integration. [Official SDK](https://github.com/anthropics/claude-agent-sdk-typescript) |
| pytest; optionally fast-check for TS properties | **Reuse pytest as coordinator.** Add fast-check only if TS property testing earns its dependency. | Development-time dependencies are outside the restricted loader. fast-check generates and shrinks test cases; it cannot establish that Claude loaded a hook. [fast-check documentation](https://fast-check.dev/) |
| Ready-made third-party mod framework or live harness | **No adoption recommendation yet.** | I did not verify a maintained, compatible harness covering cold installation, delegated events, loaded-source identity, and actual denial. Availability is **UNVERIFIED**; that is not a claim that none exists. |

For policy engines:

| Candidate | Decision for this programme |
|---|---|
| **OPA/Rego** | OPA can compile policies to WASM and provides a JavaScript SDK. That still requires a reachable evaluator, WASM runtime, module bytes, and supported built-ins. Those capabilities inside this loader are **UNVERIFIED**. **Do not adopt for the reference guard.** Running OPA externally would also add a process or service dependency without eliminating event extraction and path normalization. [OPA WASM documentation](https://www.openpolicyagent.org/docs/wasm) |
| **Cedar** | Its principal/action/resource/context model could express lane/path decisions, but a compatible runtime here is **UNVERIFIED**. Five protected paths do not justify another policy language and execution system. **Defer.** [Cedar reference](https://docs.cedarpolicy.com/) |
| **Conftest** | Plausible for repository-time configuration checks, because it evaluates structured data using Rego. **Reject as an additional dependency unless inventory finds existing adoption or substantial reusable policies.** Existing Python gates already occupy this role. [Conftest documentation](https://www.conftest.dev/) |
| **CUE / Jsonnet** | Plausible authoring or generation tools, not automatically reachable hook evaluators. **Do not introduce another source of truth alongside the mandated JSON Schemas.** [CUE introduction](https://cuelang.org/docs/introduction/), [Jsonnet](https://jsonnet.org/) |

**Rules should be data where their semantics are simple.** Put protected paths, rule IDs, tool selectors, scopes, dispositions, and exception records in schema-governed inputs. Generate relative `.ts` imports containing literals and generated types. Keep a small evaluator for those specific rule kinds; do not create a general policy language.

JSON Schema defines and validates the data contract. It does not itself establish whether a tool operation should be denied.

For command parsing:

| Candidate | Recommendation and limitation |
|---|---|
| **shell-quote** | Best small candidate to investigate for lexical tokenization. Its parser source is compact JavaScript, but uses CommonJS exports; direct package import is forbidden by the supplied loader contract. A reproducibly transformed, pinned relative `.ts` artifact is plausible, but live compatibility is **UNVERIFIED**. It would not replace the write-destination semantics in your Python module. [Parser source](https://github.com/ljharb/shell-quote/blob/main/parse.js) |
| **bash-parser** | Produces a Bash AST, but carries a substantial dependency graph. **Reject for the reference implementation**; consider only if a later evaluation demonstrates materially better coverage at acceptable packaging cost. Mod compatibility is **UNVERIFIED**. [Project](https://github.com/vorpaljs/bash-parser), [dependency manifest](https://github.com/vorpaljs/bash-parser/blob/master/package.json) |
| **tree-sitter-bash** | Provides a grammar requiring a Tree-sitter runtime. It does not identify which `tee`, `sed`, or Python arguments constitute writes. **Defer**; runtime and asset loading inside mods are **UNVERIFIED**. [Project](https://github.com/tree-sitter/tree-sitter-bash) |
| **mvdan/sh via WASM** | Strong parser candidate outside the reference implementation. Upstream points JavaScript users to `sh-syntax`, which packages a WASM build. WASM reachability here is **UNVERIFIED**. [Upstream guidance](https://github.com/mvdan/sh#javascript) |
| **nix-shell-parser** | Package identity, suitability, and maintenance are **UNVERIFIED**. Do not select it from its name. |
| **Existing Python parser** | **Retain as the production baseline.** It already handles repository-specific write behavior and has tests. Its immediate remaining integration question is how, or whether, a mod can invoke it. |

The import restriction does **not** prove bundled dependencies are impossible. It proves ordinary bare package imports are unavailable. A self-contained relative TS artifact might work; the real loader must decide that question.

If no existing parser is reachable, the options are **vendor a reproducibly generated single-file parser** or **keep parsing in Python**. My default is Python.

**2. Q9: separate the parser migration because behavior preservation decides the choice.**

The settings guard examines structured file-tool events. It needs no shell parser. Coupling it to a parser rewrite would combine two independent risks:

- Establishing that the function hook loads, receives the right event, and enforces its result.
- Preserving command semantics across `cd`, redirection, `tee`, in-place editors, heredocs, and `python -c`.

The decisive risk is **a migration that passes its new tests while silently dropping an existing write form**. A parser library reduces syntax work; it does not supply your repository’s interpretation of writes.

Use this decision order in the parser ticket:

1. **Probe an official process capability.** Whether this build permits a usable process call through `$`, with arguments, input, output, cancellation, and timeout behavior, is **UNVERIFIED**. Node’s `child_process` is unavailable under the supplied constraints.
2. If supported, prefer a thin TS adapter invoking the existing Python through its mise task. Pass the intercepted command as data; do not execute it to analyze it. Return a schema-defined decision and distinguish analysis failure from permission to proceed.
3. Measure end-to-end overhead against the existing classic hook: process startup, mise dispatch, interpreter startup, serialization, and parsing. **Actual latency is UNVERIFIED.** A function hook that still spawns Python does not remove the spawn cost.
4. If the bridge is unavailable or demonstrably too expensive, evaluate the vendored-parser route and preserve the Python behavioral cases plus independent expected outcomes.
5. Until one route passes, retain the existing classic Bash enforcement under an explicit migration exception.

Also probe whether invoking a process re-enters relevant hooks. Do not introduce recursion or a persistent worker merely to avoid measuring a straightforward bridge.

This revisits the earlier TS-port preference without overruling the settled function-hook mechanism: **the interception can move to TypeScript while the policy implementation remains Python**.

For unsupported syntax, preserve the documented contract and report its coverage limits. A timeout, malformed response, or loader error must never be relabeled as “unsupported syntax” and quietly allowed.

**3. Use a team whose outputs can be checked independently.**

These are reusable roles, not nine agents that must run simultaneously.

| Role | Owns | Input | Output | Objective check |
|---|---|---|---|---|
| **Tooling researcher** — added | Existing-tool evaluation and capability evidence | Required behavior, pinned runtime, loader constraints | Adoption/rejection matrix with versions, licenses, probes, and unknowns | Selected dependency loads through its intended path; retained alternatives have reproducible reasons for rejection |
| **Architect** | Runtime boundary, rule placement, scope, and compatibility decisions | Research, settled rulings, complete enforcement inventory | Architecture decision record and decision tables | Every requirement maps to an observable predicate or an explicit limitation; no assumed capability lacks a probe |
| **Planner** | Ticket dependencies, ownership, acceptance commands, and cutover order | Architecture and inventory | Tracked dependency graph and per-ticket contracts | No orphan rule, circular dependency, undefined proving command, or retirement without replacement evidence |
| **Implementer** — added | One bounded component or migration slice | Accepted ticket, schemas, immutable baseline cases | Reviewable commit plus local evidence | Focused checks pass; generated output reproduces; assigned behavior passes real controls |
| **Code-reviewer** | Cold review of correctness and maintainability | Final commit, requirements, independent cases | Findings or explicit no-findings verdict bound to that commit | Findings name reproducible behavior; fixes trigger a fresh review of changed scope |
| **QA** | Scenario matrix and expected outcomes | Rule inventory, user workflows, known failure history | Positive, negative, boundary, startup, and compatibility cases | Independent expected decisions cover every supported rule/tool/scope combination |
| **Verifier** | Execution evidence and failure-arm validity | Reviewed commit and QA-owned cases | Receipts with raw results, identities, counts, and restoration evidence | Real tools execute; intended mutations produce the intended failure; restored production passes |
| **Reliability improver** | Bounded self-healing and optimization | Immutable observations, failures, approved metric definitions | Diagnosis and one candidate repair or optimization | Candidate preserves coverage and behavior on independent cases; performance benefit is measured |
| **Release custodian** — added | Activation, source identity, cutover, rollback, and delivery | Reviewed and verified commits | Loaded-version evidence, retirement ledger, remote-main receipt | Tested bytes match deployed bytes; supported cold launch succeeds; merged commit is present on remote `main` |

Use stronger reasoning for architecture and cold review; use economical roles for inventory and deterministic execution once their contracts are clear. Pin actual model/effort routing in project-owned configuration after checking what the installed clients support. Specific available model settings are **UNVERIFIED** here.

The reliability improver must measure more than compliance:

- **Guard observation coverage:** matching opportunities seen by the guard divided by opportunities identified independently from tool traces.
- **Missed enforcement:** prohibited operations that actually executed.
- **False denials:** legitimate operations refused, including worktree-authorized edits.
- **Task completion:** whether agents can finish the intended work.
- **Operational health:** cold-start readiness, loader errors, source mismatch, unsupported parsing, and latency.
- **Compliance:** rule-following opportunities and outcomes, with raw numerators and denominators.

Zero opportunities means **N/A**, not 100% compliance. Missing guard telemetry is a liveness failure, not evidence of zero violations.

Its permitted changes are implementation repairs, deployment repairs, clearer denial guidance, and measured efficiency improvements. Changing protected paths, exclusions, expected outcomes, coverage definitions, or DENY into WARN is a **policy change**, outside autonomous optimization.

For each incident, stop after two candidate attempts, any hard-invariant regression, or an exhausted ticket budget. Escalate with evidence. Success requires all independent correctness checks plus the claimed improvement. Retain the 0/19 warning experience and 62→0 violation reduction as motivation, but do not compare future rates without preserving their opportunity counts and workload context.

**4. Sequence the programme around a releaseable reference guard.**

The identifiers and commands below are **proposed contracts**, not claims that these tasks already exist. Each ticket must deliver its named task, reusing repository tooling where possible. New orchestration remains Python under `python/src/kb_setup/`, invoked through mise; record a narrow language-policy exception for the settled TS mod surface.

Every `--arms` command must:

- Run the unmodified check successfully.
- Apply each named mutation separately in an isolated fixture checkout or registered worktree.
- Show the underlying check returning nonzero **for the expected invariant**, with the expected diagnostic.
- Restore, rerun successfully, and confirm restoration.
- Return nonzero for missing tools, unexecuted cases, malformed evidence, or missing controls.

A mutation runner may itself return zero after successfully proving those red/green transitions. It must retain the underlying exit codes. Neither a compiler failure nor an unrelated permission refusal counts as a behavioral mutation being caught.

Sizes below are approximate engineering effort, excluding external release waits.

| Ticket | Delivery and dependencies | Exact completion command | Required FAIL arm | Size |
|---|---|---|---|---|
| **G00 — Inventory and reuse decision** | Deliver the tooling decision and a stable-ID inventory mapping all 18 registrations, seven modules, 13 numbered invariants, and both subsections to owners, scopes, evidence, and migration dispositions. **Dependencies:** none. | `mise run kb-guard-programme-check -- --phase inventory --arms` | Remove an invariant mapping or add an unclassified hook registration; reconciliation fails. A recorded tooling choice without its required evidence also fails. | M: 1–2 days |
| **G01 — Runtime contract** | Deliver locally regenerated SDK declarations and live capability probes for event fields, imports, `$`, process access, filesystem behavior, namespace bridging, tiers, and the worktree bug. **Dependencies:** G00. | `mise run kb-mod-runtime-check -- --arms` | Read `agent_id` in the function-event adapter; the real delegated-call assertion fails. Separately introduce a JSON import and illegal `$` binding; loading failures must be visible and fatal to readiness. | M: 2–3 days |
| **G02 — Genuine code generation** | Deliver schema-owned policy data, generated repo models/enums and TS literals, truthful provenance headers, and a drift gate. **Dependencies:** G00. | `mise run kb-guard-codegen-check -- --arms` | Change a generated protected path, delete an output, and change schema input without regenerating; each fails. Regeneration must restore deterministic output. | M: 1–2 days |
| **G03 — Settings reference behavior** | Deliver the tracked settings mod using generated policy and verified event adapters, preserving the five paths and worktree authority ruling. **Dependencies:** G01, G02. | `mise run kb-settings-guard-check -- --live --arms` | Replace DENY with continuation; prohibited delegated edits execute in the fixture and verification fails. Remove the worktree exception; authorized worktree edits fail their positive control. | M: 2–3 days |
| **G04 — Cold bootstrap and liveness** | Deliver explicit activation, the tracked flag, independent SessionStart warning, session-bound readiness evidence, and integration into `kb-gates`. **Dependencies:** G03. **This releases the reference guard.** | `mise run kb-guard-liveness-check -- --cold --arms` | Remove the flag, disable registration, corrupt the module, serve a stale cached copy, or substitute an earlier session’s receipt. Each produces a warning and failing gate; a warmed second launch cannot rescue a failed first session. | L: 3–5 days |
| **G05 — Enforce the migration direction** | Deliver the rule file, `AGENTS.md` guidance, and structural lint for new or broadened classic enforcement without a recorded exception. **Dependencies:** G00, G02. | `mise run kb-guard-direction-check -- --arms` | Add classic enforcement without an exception; then broaden an excepted matcher beyond its recorded scope. Both fail; the narrowly excepted form passes. | S: 1 day |
| **G06 — Parser placement and parity** | Deliver the measured Python-bridge-versus-vendored-TS decision and its implementation, preserving the existing behavioral contract. **Dependencies:** G01, G02, G04. | `mise run kb-shell-policy-check -- --live --differential --arms` | Break `cd` tracking and each supported write mechanism separately; independent destination/decision expectations detect every regression. A bridge timeout must fail readiness and must not permit the intercepted operation. | L: 3–6 days |
| **G07 — Repo-owned file-tool migration** | Migrate the eligible file-tool policies, including the eight instruction-edit registrations, while preserving their complete effective coverage. **Dependencies:** G04, G05. | `mise run kb-file-policy-check -- --live --arms` | Drop one covered matcher, tool adapter, or protected-path case while leaving a happy-path case intact; coverage reconciliation and live tests fail. | M: 2–3 days |
| **G08 — Repo-owned command migration** | Migrate eligible command guards through G06’s selected implementation and prove compatibility with the supported worktree workflow. **Dependencies:** G05, G06. | `mise run kb-command-policy-check -- --live --arms` | Disable each migrated rule separately; its prohibited operation is detected. Enable the known-broken native isolation combination; compatibility validation fails before that workflow is advertised as supported. | L: 3–5 days |
| **G09 — Prose-to-enforcement conversion** | Deliver checks for mechanically decidable prose clauses at the appropriate hook, index/commit, or ingestion boundary, with explicit partial coverage for the rest. **Dependencies:** G00, G02, G04, G05. | `mise run kb-do-not-check -- --live --arms` | Put derived output outside the two actual allowed directories into the candidate index; omit required ingestion evidence; attempt a known prohibited configuration write. Each relevant check fails, and controls pass. | L: 3–5 days |
| **G10 — Graphify-owned migration** | Deliver the two owner-side hook changes through the fork’s workflow, update the KB pin and reviewed skills, and verify effective behavior. **Dependencies:** G01, G04. | `mise run kb-guard-graphify-check -- --live --arms` | Disable each third-party guard or substitute an older fork/plugin artifact; the corresponding behavior or provenance check fails. | L: 3–5 days, plus external wait |
| **G11 — Bounded improvement loop** | Deliver the role configuration, independent metrics, candidate evaluation, and stopping rules. **Dependencies:** G04, G07. | `mise run kb-guard-improvement-check -- --arms` | Supply a candidate that improves reported compliance by dropping observations, suppressing telemetry, converting DENY to WARN, or refusing all work. Every candidate is rejected. | M: 2–3 days |
| **G12 — Cutover and delivery** | Retire only proven replacements, account for every residual exception, complete final review/gates, and verify delivery on remote `main`. **Dependencies:** G05–G11. | `mise run kb-guard-delivery-check -- --remote origin --branch main --arms` | Remove a replacement while retaining its retirement record; remove the liveness dependency from `kb-gates`; present evidence for another commit; or present an unmerged branch. Each fails. | M: 1–2 days |

The delivery task must invoke the repository’s actual ship/land workflow after discovering its interface. Those exact interfaces are **UNVERIFIED** here. Required precommit checks remain:

```text
mise run check
mise run kb-gates
```

Three acceptance details need to be written into these tickets:

- **G03’s matrix:** each protected path; relevant file tools; main-thread allow; delegated-main denial; delegated-main decoy allow; delegated-own-worktree allow; and a worktree lane accidentally targeting the canonical checkout by absolute path. Worktree authority applies to destinations inside that worktree, not every destination merely because `.git` is a file.
- **G04’s independence:** a missing mod cannot reliably warn about its own absence. Use an independent SessionStart checker, potentially an existing classic lifecycle hook with a narrowly recorded reason. Before current-session evidence exists, report “unproven,” never “live.” If all hooks are disabled, an in-session warning cannot be guaranteed; the launcher and external gate must catch that state.
- **G09’s honesty:** inspect the actual staged/candidate content for derived-output rules. For ingestion, check manifests, provenance, and receipts that are mechanically observable. Do not label semantic source suitability or human intent as fully enforced.

G01 and G02 can run in parallel after G00. G05 can run alongside reference implementation work. After G04, G06, G07, G09, and owner-side G10 can proceed independently; G08 waits for G06. Serialize edits to shared schemas/settings and run mutation arms in separate fixtures.

**G04 is the ticket whose slippage blocks the most useful delivery.** Without a proven loading and liveness path, every later port can be correct on disk and absent at runtime. G10 may become the longest external wait, but it must not delay shipping the settings reference.

**5. These are the most likely ways to become green and useless.**

This ranking is a judgment based on your measured failures, not a statistical estimate.

| Rank | Failure | Observable that catches it |
|---|---|---|
| **1** | The mod is untracked, unregistered, disabled, or relies on an absent flag. | Clean-checkout launch through the supported entry point; actual matching event and denial; effective configuration and tracked-file reconciliation. |
| **2** | `agent_id` is read from a function event, making every lane look like the main thread. | A real spawned lane attempts the protected operation. Record the received discriminator and actual decision; a synthetic object supplied by the implementation is insufficient. |
| **3** | A warm cache hides the first-session gap. | Start with an empty plugin cache and score the **first** usable session separately. Never average first-run failure with second-run success. |
| **4** | Module compilation or capability errors remain only in a debug log. | Capture loader diagnostics on every live run; deliberately break imports and `$` usage. Missing execution evidence or relevant ERROR output fails readiness. |
| **5** | Tests exercise the tracked source while Claude executes a cache copy. | Bind evidence to the resolved loaded artifact and its digest. Intentionally make cache and tracked source differ. |
| **6** | Another classic hook or ordinary permission denial makes a dead function guard appear effective. | Isolate enforcement sources, attribute the denial to the expected rule, and prove the attempted tool executes when that function guard is mutated away. Include the bypass-permissions control. |
| **7** | “Generated” output is maintained by hand, or its drift check silently misses deleted/untracked files. | Regenerate from committed schema inputs into an isolated location and compare the complete expected file set and bytes. |
| **8** | Eight registrations become one hook with incomplete coverage. | Compare effective rule × tool × scope cases before and after migration; raw registration counts are not the denominator. |
| **9** | The gate validates yesterday’s receipt or a successful child probe while the current session is unguarded. | Match session identity, run nonce, loaded-source digest, effective configuration, runtime version, and relevant commit. Reject stale or foreign evidence. |
| **10** | A mutation runner calls any nonzero result success, or leaves a mutation behind. | Require the expected diagnostic and observed behavior, then restored success and a final tree comparison. Missing dependencies and test crashes are infrastructure failures. |
| **11** | Event-blob matching blocks replies or quoted examples. | A real outgoing message quotes a forbidden token and still succeeds; a genuine prohibited operation fails. Match only verified named fields. |
| **12** | Worktree detection becomes an unconditional exemption, or session root is mistaken for the operation’s destination. | Test own-worktree writes, canonical-checkout destinations from that lane, subdirectory launches, and ordinary relative paths. |
| **13** | Python/TS parity means both implementations agree on the same incorrect expected behavior. | Retain independently authored outcomes and isolated filesystem results, not merely equality between implementations. |
| **14** | Wrong event namespace or continuation routing skips enforcement. | Exercise the selected function event, any `classic.PreToolUse` bridge, and the actual installed hook composition. A registration log alone does not count. |
| **15** | Enabling native worktree isolation later breaks every Bash call. | Maintain a live compatibility probe and reject that combination when unsupported. The upstream report documents this exact failure. [Issue #92533](https://github.com/anthropics/claude-code/issues/92533) |
| **16** | Compliance rises because opportunities disappear, all work is denied, or hard cases become exclusions. | Independent opportunity counts, positive controls, task-completion checks, and reviewed changes to the coverage inventory. |

**6. What I would not do.**

- **I would not treat the preview API as stable.** The settled mechanism carries upgrade and operational costs. Cheapest mitigation: pin the executable, regenerate its declarations, and require live control arms before accepting a version change. Anthropic explicitly describes the surface as early access. [Official mod documentation](https://github.com/anthropics/claude-code/tree/main/mods)

- **I would not force all implementation logic into TypeScript.** That would discard a tested Python asset without evidence of benefit. Keep the interception in the settled mechanism and choose parser placement from measured compatibility, behavior, and cost.

- **I would not make the reference guard wait for an OPA integration, generic framework, or parser rewrite.** Its immediate unresolved problems are activation, provenance, generation, scope, and liveness.

- **I would not promise that warning plus gate failure prevents every unguarded action.** That settled design detects a problem, sometimes after a session has started. Cheapest mitigation: a supported bootstrap/launch task that establishes readiness before handing over ordinary work, plus an explicit unproven state elsewhere.

- **I would not mistake the five-path list for protection of the whole enforcement system.** The mod, schema, generator, and liveness machinery themselves fall outside it. Keep the settled list; mitigate accidental weakening through merge review and mutation-tested gates.

- **I would not exempt a merge merely because its author worked in an authorized worktree.** Full worktree authority shifts responsibility to the merge boundary. Validate the resulting candidate tree and refresh evidence after conflict resolution or other changes.

- **I would not remove the two Graphify hooks by editing only KB settings.** Their replacements need owner-side delivery and a verified pin transition. Installation remains through `mise run kb-skill-refresh`, retaining its diagnostics.

- **I would not count a recorded classic exception as completed migration.** Exceptions need an exact scope, owner, reason, and review trigger. Existing lifecycle hooks, temporary parser retention, and third-party ownership are different reasons.

- **I would not expand this into shell-evasion work or a general security boundary.** Preserve the accepted `sh -c`, `eval`, and substitution limits, while distinguishing those limits from accidental loss of already-supported behavior.

- **I would not let the self-improving role edit its own success criteria.** Optimizations remain candidates until independent review and verification establish that the guard still observes, denies, allows, and permits useful work as intended.

