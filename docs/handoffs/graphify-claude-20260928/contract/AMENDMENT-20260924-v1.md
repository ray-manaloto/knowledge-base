# Graphify workflow adoption amendment — 20260924-v1

Status: user-approved implementation scope, issued by the audit task; adoption by the delivery coordinator requires acknowledgment. No implementation or acceptance is asserted by this document.

Delivery coordinator: `01a0ca59-2291-76a0-a5e7-bc6163a8567f` (local).
Audit/transfer task and return channel: `01a0d0cb-95d1-7ed2-ad0c-5fc26c4fe92b` (local).
Authority: the user's explicit “PLEASE IMPLEMENT THIS PLAN” message in the audit task, including the codex-goal lifecycle addition, reproduced in `USER-APPROVED-PLAN.md`.

## 1. Authority and retained scope

This is an execution amendment to the existing approved Graphify delivery work, not a replacement goal or a declaration that ticket 787 is complete. Retain `../../SPEC.approved.md`, `../../TICKETS.approved.md`, original goal bytes, all 34 specification stories, all capability rows, all failed/partial receipts and user-approved exclusions. Relative paths in this bundle resolve from this directory. Their exact current hashes are in `bundle-manifest.json`.

The user now expressly includes the reusable cross-repository automation, dotfiles project-sync/currency work, skill enforcement and proof obligations below. This expands the prior specification's “do not expand delivery into dotfiles” boundary only for these named features. It does not authorize unrelated dotfiles/services/global configuration work, paid full-corpus extraction, scheduler activation or deletion of preserved work. Maintain product routing defaults (Claude opus/xhigh, explicit OpenAI gpt-5.6-sol/high) independently of development-team models.

The prior autopromotion exclusion is superseded only for the explicitly invoked deterministic delivery workflow: ship, verify the exact PR checkpoint, and land/recover using repository-owned interfaces. Preserve dotfiles ship -> verified merge -> land ordering and KB ship -> merge-owning land -> main-sync/postmerge ordering. No background scheduler or recurring maintenance is authorized. Initial independent reviews/live qualification remain required and cannot be replaced by a machine attestation.

Use `/Users/rmanaloto/.codex/skills/codex-goal/SKILL.md` and its native-lifecycle reference whenever handling this goal. The current exposed `update_goal` supports status only, not objective replacement. The delivery task must call its own `get_goal`, preserve the unfinished native goal/accounting, and record the actual state and objective hash. Do not falsely complete, recreate, pause, reset a budget or create a new task to adopt this amendment. Unsupported objective replacement remains unperformed. Checkpoint this amendment's requirements, statuses, evidence, gates and next action in existing artifacts and explicitly report that the native objective remains unchanged. Reread the amendment and current checkpoints after compaction/resume.

## 2. Adoption and safe cutover

The coordinator first verifies this file and bundle hashes and returns a native task message to the audit task. The acknowledgment must contain: amendment path/SHA256; original objective state/hash and unchanged status; current checkout/branch/HEAD plus dirty paths and source hashes; actual active workers/processes and their existing deadlines; adopted Astra/Sol/Luna roles and requested/observed models; exact first action; and ownership boundaries. Distinguish acknowledgment from completed implementation.

The audit task owns this immutable bundle only. It does not own Graphify source, the existing evidence index, KB or dotfiles writes. The existing delivery coordinator retains integration ownership and assigns one writer per Git common directory. No second writer may enter while an existing producer owns files.

At preparation, the latest observed checkpoint had one completion writer in `lanes/maintenance-post-r2-completion-writer` with original producer cutoff 2026-09-24T02:51:59.421627Z and total handback cutoff 02:52:59.421627Z. These are historical observations, not fresh process authority. Reconcile live state before acting. Default to its settled handback or existing deadline. Do not reset that deadline or relaunch the same expired attempt. Earlier controlled stop is authorized only under the approved ownership/repeated-infrastructure/invalidation conditions; settle exact owned processes using the existing bounded procedure, never unrelated processes.

At cutover, stop new old-workflow dispatch, verify settlement, snapshot commits/branches/index/worktree/untracked content/owned refs/attempts and receipts, preserve partial work, and explicitly transfer ownership. Classify prior evidence against exact current inputs. Resume attributable implementation; otherwise use a new isolated registered worktree and transfer only the preserved reviewed delta. A full restart is authorized when needed for trustworthy proof, with reasons and evidence invalidation recorded. Keep all originals. No destructive cleanup or silent reset is implied.

## 3. Team and executable architecture

Use the existing `codex-task-orchestration` skill and native parent-controlled subagents. After the current writer settles, preferred development assignments are Astra (`gpt-6-astra`, xhigh) for heavy reasoning/planning, Sol (`gpt-6-sol`, high) for implementation and tests, and Luna (`gpt-6-luna`, high) for bounded retrieval/evidence. Preserve the current gpt-5.6-sol/high producer until settlement. Inspect callable model/capability support and record actual assignments; unknown served identity remains unknown. Never silently replace a requested unavailable model.

Give each role source identity, bounded inputs/deadline, ownership, success criteria and return channel; require acknowledgment and a live status probe. Reuse suitable idle workers; do not repurpose active ones. Check resource admission for CPU/Docker-heavy work, container ownership, interpreter, loopback and readable review roots. Use native waits rather than nested polling. Keep coupled production/test repairs together. Separate independent Standards and Spec/security reviews from authorship, and review exact final identities. Read all mandatory review inputs, but do not replay broad history research.

One canonical composition at each layer: wrapper skill -> component skill -> wrapper mise task -> canonical task -> Python composite -> reusable functions. Skills are interactive interfaces; routine execution enters mise directly without an agent. Native tools remain the collaboration transport. Python alone owns execution order, checkpoint validity, bounded recovery and retry decisions. Do not encode a second workflow in shell, task dependencies or skill prose. Individual diagnostic stages call the same functions as composites. Keep repo ownership and explicit versioned interfaces; do not import sibling private modules or duplicate implementations.

Extend existing graphify-currency, graphify-fork-maintenance and codex-task-orchestration; add only missing thin project routers/ship-land wrappers. Keep one authored skill source per repository with generated/verified Claude/Codex mirrors. Extend existing KB skill lint/shared hook policy and mirror checks instead of a second policy registry. Make required delegation/missing target/cycle/drift/raw-command checks executable. Explicitly read approved skill versions now; fresh worker discovery canaries prove availability.

## 4. Implementation requirements and dependency map

Owners: C = delivery coordinator/integrator; A = Astra reasoning lead; G = Graphify Sol writer; K = KB Sol writer; D = dotfiles Sol writer; L = Luna evidence worker; R = independent reviewers. G/K/D are ownership roles, not authorization for competing writers. Reuse available slots sequentially. All rows begin PENDING until their stated evidence exists. Dependencies are requirement IDs, with retained ticket dependencies 787 -> 788 -> 789 -> 790 -> 791 -> 792 preserved and new work reconciled with existing project-sync tickets instead of duplicated.

| ID | Required outcome and source | Owner | Dependency | Acceptance evidence |
|---|---|---|---|---|
| AD01 | Exact amendment delivered and acknowledged; all original requirements retained (plan 1) | C | none | Native message plus recipient acknowledgment with recomputed hash |
| AD02 | codex-goal lifecycle used; native objective preserved if replacement unsupported; checkpoints reread on resume (1) | C | AD01 | Own get_goal receipt, objective comparison, resume instructions |
| AD03 | Existing plan/tickets include every row and original 34 stories, ownership and dependency (1) | C/L | AD01 | Evidence-index requirement registry; missing/duplicate coverage check |
| AD04 | Skills loaded explicitly and discoverable in fresh workers (1,3) | C/L | AD01 | Read/discovery traces and version/hash bindings |
| CT01 | Bounded current writer settled; no overlapping write ownership (2) | C | AD01 | Direct terminal receipt/process observations/ownership handback |
| CT02 | Preservation snapshot and evidence validity classification (2) | C/L | CT01 | Git/content/ref hashes; valid/stale/incomplete/absent classifications |
| CT03 | Reasoned checkpoint resume or clean restart; originals retained (2) | C/A | CT02 | Chosen start identity, reason, invalidation mapping, isolated worktree when needed |
| ST01 | Existing evidence index is authoritative; status/checkpoint projections generated, no conflicting next actions (2) | G/C | AD03,CT01 | Shared Python projection function; consistency/resume tests |
| TM01 | Astra/Sol/Luna native team adopted; model changes recorded, product profiles preserved (3) | C/A | CT01 | Role assignments, actual acknowledgments, requested/reported identity fields |
| TM02 | Preflight readable input roots, interpreter, loopback, resources and ownership before expensive dispatch (3) | G/C | TM01 | Positive/negative preflight cases; no unsupported full-suite relaunch |
| TM03 | One coupled repair owner; bounded native waits; idle-worker reuse; independent final reviewers (3) | C | TM01 | Assignment/settlement traces and independent exact-identity review receipts |
| AR01 | Skill -> mise -> Python composition; Python-only sequencing; stage/composite parity (3) | G/K/D | CT01 | Source ownership map and seam tests through public tasks |
| AR02 | Existing three skills extended; only missing thin routers and delivery wrappers added (3) | G/K/D | AR01 | Reuse inventory, skill diffs, child delegation/discovery checks |
| AR03 | Existing lint/hook/mirror enforcement extended for missing targets, cycles, drift and alternate raw commands (3) | K/D | AR02 | Shared-policy tests and runtime refusal controls |
| RS01 | Existing project-sync design/tickets identified and adopted, not recreated (4 repair) | K/D | AD03,AR01 | Existing ticket mapping with owners, dependencies and exact design identity |
| RS02 | Runtime validated even with unchanged lock; skills/refs/stamps generated from verified runtime (4) | K/D | RS01 | Stale/missing environment control; installed identity and generated bundle checks |
| RS03 | Dirty authored/dependency content protected; atomic complete bundle; coordinated writers/readers (4) | K/D | RS02 | Dirty file/partial bundle/concurrency/failure injection controls |
| RS04 | Startup/resume <=600 seconds; accepted inputs only; no new release/extraction (4) | K/D | RS03 | Whole-operation timing and process-attempt evidence |
| RS05 | AGENTS.md consolidation retained separately; owned skill generation/mirrors still mandatory (4) | D/K/G | AR02 | Safe delivered consolidation behavior and Claude/Codex compatibility/authored-content controls; remain PENDING if only assessed or tracked |
| RS06 | Existing project-sync design/tickets completed (4 repair) | K/D/C | RS02,RS03,RS04 | Joint runtime/bundle/startup acceptance and existing ticket closure evidence |
| FM01 | run/resume/status added without removing preview/apply (4 fork) | G | AR01,787 | CLI compatibility and stage/composite/replay tests |
| FM02 | Frozen candidate/config/target; stable publication chronology and usable non-yanked package selection (4) | G | FM01 | Selection fixtures, provenance, exact target pin and invalid-target zero-mutation checks |
| FM03 | Upstream ancestry and every capability verified; conflict/unknown/fresh-model-evidence stops (4) | G/A | FM02,788 | Ancestry and retained/equivalent/superseded/user-excluded matrix; stop controls |
| FM04 | Currency rechecked before publication/integration/completion; <=3 target attempts (4) | G/C | FM03 | Changed-release controls, invalidation receipts and bounded terminal state |
| FM05 | Relevant-identity checkpoint reuse and explicit partial cross-repo progress (4) | G/K/D | FM01,ST01 | Changed input/config/environment tests and safe resume evidence |
| DL01 | Graphify fork, KB fork consumption and dotfiles upstream ownership retained (4 delivery) | C | AD03 | Ownership/dependency map; no accidental fork pin in dotfiles |
| DL02 | Qualified immutable fork published before KB installation/live acceptance (4) | G/K/C | FM03,FM04,OG03 | Independently resolved immutable ref and installed direct-URL identity |
| DL03 | Thin ship/land wrappers preserve each repository's ordering and interrupted/merged recovery (4) | K/D | AR02,DL01 | Verified PR head, exact operation recovery, main sync/postmerge checks |
| DL04 | Machine attestation covers complete reproducible diff/generator inputs/outputs and exact head; others normal review (4) | K/D/R | DL03 | Stale/head-moved/mixed-change refusal and positive attestation controls |
| EV01 | Shared Python capture/parsing; direct nested exits; separate raw streams; durable owned artifacts (4) | G/K/D | AR01 | Wrapper-zero/child-failure, malformed JSON, timeout and ownership controls |
| PF01 | Fresh clean end-to-end routine attempt has zero model launches and zero agent repairs (5) | C/G/K/D | CT03,FM05,DL04,RS04 | Exact-input attempt with subprocess-tree/egress inference-attempt evidence |
| PF02 | Identical replay avoids repeated primary mutation/unneeded regeneration (5) | G/K/D | PF01 | Same public invocation; tree/ref/output identity and operation counts |
| PF03 | Invalid target, dirty inputs, conflict, unknown compatibility stop; no promotion on refresh failure/outer rc0 (5) | G/K/D | FM03,RS03,EV01 | Positive/negative real-process/task controls |
| PF04 | Retarget/invalidation bounds and interrupted/merged-but-unsynced recovery use same workflow (5) | G/K/D | FM04,DL03 | Controlled changed release and interrupted delivery tests |
| PF05 | Injected model attempt rejected; missing skill/input/capability caught before dispatch (5) | G/K/D | TM02,AR03 | Attempt-denial and preflight control receipts |
| PF06 | Causal improvement evidence; elapsed/commands/models/known-or-unknown tokens recorded honestly (5) | L/A/C | PF01-PF05 | Matched fixture comparisons; no general speed claim from unlike runs |
| PF07 | Each fixed audited failure updates its same-fix regression/control and owning instructions/enforcement | G/K/D/L | EV01,AR03 | Failure-to-fix-to-control-to-skill/policy crosswalk; broader reusable work remains owned and tracked |
| OG01 | All original 34 specification stories and exclusions retained | C/L | AD03 | Existing criterion index crosswalk; no dropped or silently accepted item |
| OG02 | Linux Python3.10/3.12/3.13/3.14 full suites; five skillgen; upstream/fresh install gates | G | FM03 | Exact final commit, direct exit codes, explained existing skips, no hidden failures |
| OG03 | Independent Standards + Spec/security acceptance on final commits | R/C | OG02 | Complete review-input coverage and authentic final decisions |
| OG04 | Exactly eight approved KB cold cases and matching warm zero-extraction replays after publication | K | DL02 | Frozen two-source/two-backend/NORMAL-DEEP receipts and predeclared expected evidence |
| OG05 | Routing/fallback/timeout/partial output/raster/cache/provenance/usage controls preserved | K/G | OG04 | Required causal controls, product profiles unchanged, unknown usage not zero |
| OG06 | KB declarations/lock/source/installed SDK/both skills/baselines/build/graph facts aligned | K | DL02,RS03 | Exact installed identity, owning-task generated assets, deterministic build and graph controls |
| OG07 | Actual KB main merge, postmerge CI, currency and installed identities verified | K/C | OG03,OG04,OG05,OG06,DL03,FM04 | Remote main/CI and fresh installed evidence; no open-PR completion |

AD03 must reconcile these rows with existing ticket IDs and each original story rather than replace the old chain. Do not invent hosted ticket IDs. Publish/update tracker dependencies only through existing repository workflow and authorized scope. First local dependency update is sufficient to begin owned prerequisite work.

### Original specification story crosswalk

These rows preserve the exact substantive requirements of the numbered stories in SPEC.approved.md. Their full implementation/testing sections remain authoritative. The original ordered ticket chain remains a prerequisite, not a substitute for observed acceptance.

| Original story | Owner | Requirement/dependency | Acceptance evidence |
|---|---|---|---|
| US01 Latest qualifying publication | G | FM02 | Published chronology plus usable package selection fixtures |
| US02 Explicit SHA override | G | FM02 | User-requested exact override/reason; no inferred fallback |
| US03 Frozen tag/version/commit | G | FM02 | Frozen manifest and source/target identities |
| US04 Final timestamped currency | C | FM04,OG07 | Fresh final release check and bounded retarget state |
| US05 Upstream ancestry | G | FM03 | Actual ancestry on delivered tree/ref |
| US06 Every fork capability classified | G/A | FM03,788 | Complete capability matrix with evidence |
| US07 Isolated worktrees and preserved work | C/G/K | CT02,CT03 | Before/after inventories and registered isolation |
| US08 One skill-task-engine path | G/K/D | AR01,AR02 | Actual public-seam invocation and source ownership map |
| US09 Clean execution without agent edits | C | PF01 | No repair writes during frozen routine attempt |
| US10 Idempotent repeat | G/K/D | PF02 | Same identity, no repeated mutation |
| US11 Invalid target before mutation | G | PF03 | Nonzero stopped result with unchanged candidate/ref/files |
| US12 Recoverable conflict stop | G | PF03 | Conflict receipt retained, no automatic resolution/reset |
| US13 Default Claude opus/xhigh | G/K | OG05 | Default selector and live receipts on approved product profile |
| US14 Explicit OpenAI gpt-5.6-sol/high | G/K | OG05 | Explicit selector and live receipts, independent of team models |
| US15 Selector conflict before launch | G/K | OG05 | Contradictory selector negative control with zero launches |
| US16 No implicit metered route | G/K | OG05 | Routing refusal/attempt evidence |
| US17 Explicit fallback only after zero primary successes | G/K | OG05 | Allowed/forbidden fallback controls |
| US18 Partial/uncertain output retained | G/K | OG05 | Failure artifacts and uncertainty labels |
| US19 Bounded attempts and wall time | G/K | OG05 | Frozen finite limits and timeout/retry receipts |
| US20 Finalized success/failure receipts | G/K | EV01,OG05 | Direct outcomes, finalization and failure controls |
| US21 Warm replay zero extraction | K | OG04 | All eight compatible warm replays add zero extraction calls |
| US22 Incompatible execution identity isolated | G/K | OG05 | Cache incompatibility control |
| US23 Original producer provenance on hits | G/K | OG05 | Cache-hit producer/request identity distinction |
| US24 Requested/reported models distinct | G/K/C | TM01,OG05 | Separate reported/unknown service identity fields |
| US25 Unknown usage is not zero | G/K/C | PF06,OG05 | Structured known/unknown accounting |
| US26 Meaningful static raster on both CLIs | G/K | OG05 | Pixel-dependent answer and opposite-direction control |
| US27 Real Graphify/planning-with-files NORMAL/DEEP | K | OG04 | Eight frozen real-source cold cases with predeclared expectations |
| US28 Register planning-with-files if absent | K | OG04 | Legitimate source registry identity before source use |
| US29 Full Linux and skill generation gates | G | OG02 | Four Python suites and all five skillgen checks, no waived baseline |
| US30 KB identities aligned | K | OG06 | Declarations/lock/install/source/SDK/skills/stamps/baselines agree |
| US31 Independent final reviews | R/C | OG03 | Authentic independent Standards and Spec/security final-commit decisions |
| US32 Graph facts/provenance survive refresh/collisions | G/K | OG06 | Collision, AST refresh and provenance controls |
| US33 Immutable publish and actual KB main/postmerge CI | G/K/C | DL02,OG07 | Remote published ref, merged main, CI and installed identity |
| US34 Durable status/evidence across resume | C/L | ST01,AD02 | Authoritative criterion index and generated resume checkpoint |

## 5. Acceptance interpretation and work order

Initial development, independent review and the eight approved cold live cases may use models. Routine checks/upgrades/repair/replay/delivery must enter the canonical CLI directly and attempt no inference, including keyless CLI fallback. Zero telemetry is not evidence of zero calls; inject a model attempt and prove refusal. If an update needs new live evidence or semantic decisions, stop explicitly for a separately classified initial qualification. Do not turn routine automation into an implicit agent loop.

PF01's positive inputs must be explicitly eligible for deterministic qualification; label representative controlled inputs as fixtures. A safe STOP on an unknown candidate passes a negative control, not the positive end-to-end proof. Final real delivery retains the full original acceptance boundary. FM04 is implemented once and invoked at each named boundary with that boundary's exact identities; its final invocation is not a prerequisite that creates a cycle before publication.

Run the fresh proof on frozen inputs after implementation. The initial delivery may use a separately labeled model-backed qualification; no model-backed stage may be hidden inside PF01. Preserve original stage order: fork gates/reviews, target recheck and immutable publication, then eight installed-fork KB cold/warm cases, consumer gates/reviews and actual main integration. A postpublication repair creates a new immutable identity and invalidates affected evidence. Dotfiles upstream repair/promotion remains a separate consumer policy.

Within each ready dependency frontier, keep one production/test owner and parallelize useful read-only evidence or separately owned repository work. Complete immediate ticket787 repairs through the existing seam, then integrate new reusable stages rather than replace the implementation with another general framework. Do not block today's bounded correction on finishing all cross-repo automation; do not mark the full amended scope complete until every required row and original criterion passes.

Default order: acknowledgment -> bounded settlement/preservation -> explicit team and shared interfaces -> repairs and automation -> fresh model-free clean/replay/refusal proof -> initial qualification and delivery -> remaining project-sync/enforcement acceptance. Any necessary ordering adjustment must name its real dependency and retain every requirement.

The completion report distinguishes: adoption complete; implementation progress; proof complete; original delivery complete; full amended scope complete. It includes exact target/ref/installed identities, criterion evidence, remaining gates, measured durations/calls and unchanged native-objective status when applicable. Sending this amendment, spawning a team, green wrappers, historical passing tests, elapsed budgets or an open PR are never full completion.
