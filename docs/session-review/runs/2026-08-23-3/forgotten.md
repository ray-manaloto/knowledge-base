# forgotten-requirements lane — 2026-08-23 session review

Scope: docs/direction/2026-08-22-ray-directives.md (full), .agent/plans/session-2026-08-23-{a,b,c}.md
(full), docs/plans/2026-08-23-directive-execution-plan.md (1636 lines, grepped + targeted reads),
current repo state (mise.toml, pyproject.toml, sources/, .codex/config.toml), `gh issue list`/`gh issue
view` on the round's touched issues.

## Findings

1. **The "option 1" scope conflict the plan doc itself flagged was never put to Ray, and work
   proceeded on units outside his literal scope while units inside it went undone.** Ray's
   AskUserQuestion answer was `/fable-orchestrator:orchestration option 1`; the plan doc's own
   correction (docs/plans/2026-08-23-directive-execution-plan.md:1204-1215, "Corrected (cold lane,
   I7)") states option 1 as literally written to Ray was "the currency fix + antigravity resync +
   plugin audit + the two source manifests" = U2(partial)+U3+U4+U5, and explicitly notes "U0 appears
   nowhere in option 1." The session instead executed U0 (8f285ce051d1) and U8b0 (e4d3d27a5aa3) —
   neither in that list — while U4 (reconfigure the cold-review lane, #445) and U5 (register
   yuting0624/antigravity-for-claude-code as a source, #446) were not done, and U3's bump list is
   2/8 complete (finding 3). The plan doc names this as its own open question ("my assumption,
   stated so it can be corrected") and no handoff records an answer.
   - evidence: docs/plans/2026-08-23-directive-execution-plan.md:1198-1215; handoff commit tables
     in .agent/plans/session-2026-08-23-c.md §2 (U0, U8b0 present; U4, U5 absent)
   - control_arm: the same grep methodology finds U4b (b9ce6e0a4a8b) and U9b in the commit table,
     confirming the probe can detect a done unit — its absence for U4/U5 is a real gap, not a
     missed grep.
   - remedy: AskUserQuestion to Ray: confirm whether U0/U8b0 were sanctioned scope additions, and
     whether U4/U5 (in his literal option-1 list) are still owed inside this PR or deferred.
   - cost_rank: 1
   - still_live: true

2. **10 of the 12 "LOST" requirements the round's own cold-lane review found (Ray's words, absent
   from the plan) are not named in any handoff's OWED section — only reachable by reading the
   1636-line plan doc, which the `/kb-resume` chain does not surface.** Table at
   docs/plans/2026-08-23-directive-execution-plan.md:1148-1197 (L1–L12). Only L11 (telemetry) was
   discharged in the execution log, and L1's "find the writer" half was separately (and earlier,
   2026-08-21) resolved — but L1's OTHER half ("adding claude telemetry lines" to
   `.codex/config.toml`) was not (finding 4). L2 ("all skills should be created via
   `/skill-creator` and use `/mattpocock-skills:writing-for-agents`") was narrowed to clear-prep
   only, filed as #468. L3, L5, L6, L7, L8, L9, L10, L12 have no issue and no handoff-OWED mention
   at all. Grepped every handoff (a, b, c) for `disable-model-invocation`, `skill-creator`,
   `writing-for-agents`, `ls-remote`, `excalidraw`, `kb-extract.js`, `kb-tool-review.js`, `python
   code`, `20%` — only handoff c matches (#468 and the disable-model-invocation misdiagnosis, a
   DIFFERENT bug from L3's ask). Handoff b: zero matches.
   - evidence: docs/plans/2026-08-23-directive-execution-plan.md:1148-1197; grep across
     .agent/plans/session-2026-08-23-{a,b,c}.md (b: 0 hits; c: 2 hits, both partial)
   - control_arm: the same grep for "L11"/telemetry-shaped text finds the discharged section
     (:1170-1187), proving the grep methodology surfaces items that WERE carried forward.
   - remedy: fold the LOST table's still-open rows into the next handoff's §OWED explicitly, one
     bullet per L-item, or file each as its own issue under epic #435/#436 so `gh issue list`
     surfaces them independently of a 1636-line doc.
   - cost_rank: 2
   - still_live: true

3. **Two of the LOST items are literal QUESTIONS Ray asked Claude, not work items, and neither has
   been answered back to him.** L4: "use graphify as ai agent memory … deep extraction and
   reflection … from its final output **or on its intermediate steps**" — a direct either/or
   question, still unanswered, and directly adjacent to the literal next-task
   ("deep extraction and reflection of the graphify clone repo source is the priority") that WAS
   executed this round. L7: "can you just use `mise ls-remote antigravity-cli`…?" — a direct
   question about tooling choice; the plan silently adopted `mise outdated -b -J` instead without
   ever telling Ray why not his suggested command.
   - evidence: docs/plans/2026-08-23-directive-execution-plan.md:1178 (L4), :1180 (L7)
   - control_arm: `gh issue list --search "intermediate steps" in:body` returns only the broad
     epic #435 (title-level capture), never a standalone answered item — confirms the question
     was filed but not resolved.
   - remedy: AskUserQuestion to Ray on both, since `clarify-before-acting.md` requires resolving a
     direct question rather than silently picking an answer.
   - cost_rank: 3
   - still_live: true

4. **U3's "eight real bumps" is 2/8 done, and the "one upgrade interface" (U2) it was meant to
   exercise was never built** — so even the 2 that landed (antigravity-cli, claude-code) went
   through ad hoc commands, not the interface Ray asked to be built first. Currently pinned:
   `mise.toml:46` `hk = "1.56.0"` (spec'd 1.56.1), `mise.toml:54` `rumdl = "0.2.58"` (spec'd 0.2.60),
   `pyproject.toml:82` `"ty==0.0.73"` (spec'd 0.0.74). `tree-sitter`, `boto3`/`botocore`,
   `pydantic-core` also untouched.
   - evidence: mise.toml:46,54; pyproject.toml:82; docs/plans/2026-08-23-directive-execution-plan.md:663-678
     (U3 spec) vs .agent/plans/session-2026-08-23-c.md §2 commit table (only `0e088a04bd65`
     antigravity-cli, and the separate resync commit `4e9f3fe785fc` for claude-code)
   - control_arm: `grep -n "^hk\s*=\|^rumdl\s*="  mise.toml` returns the live pins directly from the
     tracked file, not an inference.
   - remedy: run the 6 remaining bumps (or explicitly re-scope U3 down and say so in the next OWED
     section).
   - cost_rank: 4
   - still_live: true

5. **L1's second half — "adding claude telemetry lines" to `.codex/config.toml` — was asked on
   2026-08-21 and restated as still-lost on 2026-08-23; neither date shipped it.** `.codex/config.toml`
   currently has only `[shell_environment_policy]` and `[mcp_servers.graphify]` — no telemetry
   lines of any kind.
   - evidence: `.codex/config.toml` (repo root, read in full — 20 lines, no telemetry section);
     docs/plans/2026-08-23-directive-execution-plan.md:788 (08-21 citation `:133`) and :1160 (still
     LOST on 08-23)
   - control_arm: the writer-hunt HALF of the same ask (`kb-attribute-write`, finding the process
     that writes the file) genuinely was discharged 2026-08-21 and promoted to
     docs/research/reports/2026-08-21-codex-config-writer.md — confirming the two-part ask can be
     told apart and one part really did ship while the other didn't.
   - remedy: add the telemetry lines (or record why the discovered writer — the ChatGPT desktop
     app's "Import from another AI app" — makes them pointless, and close the ask with that
     reasoning instead of leaving it silently open).
   - cost_rank: 5
   - still_live: true

6. **U5 — register `yuting0624/antigravity-for-claude-code` as a graphify source (#446) — is
   undone.** Ray named this repo specifically: "https://github.com/yuting0624/antigravity-for-claude-code
   should be a currency/critical dependency that is in sync w the latest version of the
   antigravity @ antigravity-for-claude-code plugin." No manifest exists for it.
   - evidence: `ls sources/*.manifest | grep -i antigrav` → only `antigravity-plugin-cc-chris.manifest`
     and `antigravity-plugin-cc-marcos.manifest` (different repos, confirmed by
     docs/plans/2026-08-23-directive-execution-plan.md:748-756's own text); `grep -rn "yuting0624"
     sources/ currency.toml` finds only two incidental mentions inside a prior extraction's prose,
     not a manifest or currency.toml row.
   - control_arm: the same `ls`/`grep` pair finds `antigravity-plugin-cc-chris.manifest` cleanly,
     proving the search isn't blind to real manifests.
   - remedy: `mise run kb-manifest-add` with `build = skip` (kb-build is RED, #397/#417) + a
     currency.toml row, as U5 already specifies.
   - cost_rank: 6
   - still_live: true

7. **codex's `build = skip` was never lifted, though U0 built the exact machinery its own skip
   reason said was missing.** `sources/codex.manifest:49` still reads `build = skip`; the manifest's
   comment (`:43`) still cites the old #1666 zero-node blocker as the reason, which U0's own
   diagnosis (execution log, docs/plans/2026-08-23-directive-execution-plan.md:1562-1591) superseded
   with a different, now-fixable cause (the TOML package-manifest approver). This is already named
   in handoff c's OWED §5 ("Lift codex's build=skip"), so it is tracked, not silently dropped — but
   it is a cheap, already-diagnosed fix that has now carried across the round without being applied.
   - evidence: sources/codex.manifest:43,49; .agent/plans/session-2026-08-23-c.md §5
   - control_arm: n/a (already CARRIED in a handoff — not asserting a new negative, confirming a
     tracked one is still true against the live file)
   - remedy: flip the flag, re-run kb-build for that source only, confirm nodes appear.
   - cost_rank: 7
   - still_live: true

## Coverage

- **Reached and analysed**: docs/direction/2026-08-22-ray-directives.md (full, including the ADDENDUM
  and ADDENDUM (b) verbatim directive blocks); all three round handoffs in full
  (.agent/plans/session-2026-08-23-{a,b,c}.md); docs/plans/2026-08-23-directive-execution-plan.md's
  structural map (all `##`/`###` headers) plus full reads of the DECISIONS, LOST, Second-sweep,
  U0/U4/U4b/U5/U3 sections and the entire Execution log; `gh issue list --state open` (all 40 open
  issues by number/title/updatedAt); targeted `gh issue list --search … in:body` probes for L-item
  phrases; live repo state checks (mise.toml, pyproject.toml, sources/*.manifest, .codex/config.toml,
  review report lane-invocation strings).
- **Opened but not finished analysing**: the remaining ~1400 lines of docs/plans/2026-08-23-directive-execution-plan.md
  not directly quoted above (U1, U6, U7, U8, U9, U9b, U10, U11 full bodies — read via header grep and
  spot-checked, not exhaustively cross-verified against current repo state line by line); the full
  bodies of issues #435 and #436 (only `in:body` search-hit confirmation, not a full `gh issue view`
  read, so it is possible some L-items are captured there in more detail than credited in finding 2);
  whether `/antigravity:setup` (agy-doctor) was actually run this round (referenced as a U4 action
  item, not confirmed done or not-done from available evidence).
- **Never reached**: the actual live working-session transcripts (096161cc, and the ones behind
  handoffs a/b/c) — out of scope per the task's SCOPE line, which names only this review's own
  transcript (f74823ff...) plus the directive and handoffs; anything Ray said in those live sessions
  that never made it into a handoff, directive addendum, or the tracked plan doc is invisible to
  this lane by construction. Issues #216, #124/#125 (skill-measurement) and other older backlog
  items outside this round's touched set were not swept for forgotten sub-asks.

## GitHub repos touched

_None._ (All evidence was this repo's own tracked files and issue tracker.)
