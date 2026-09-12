# Lane E session audit: missed prior art and unused external surfaces

- Audit target: `4cdd8bfb` (`4cdd8bfbc3a2d7919adc8057c34afd487813fa26`)
- Date: 2026-09-12
- Scope: read-only analysis across the named local repositories and external documentation/index surfaces. This report is the lane's only intended file write.
- Evidence rule: negative results are paired with a known-positive control using the same command shape; every search bound is stated.

## Incremental audit log

### 0. Method and graph-first orientation

The repository Graphify query is the first project-evidence probe, before raw-source inspection. Exact stdout/stderr, graph health, warnings, source omissions, and truncation are recorded below after the probe.

Graph-first result for `mise run kb-query -- "function hooks mod runtime" --prose --idf`:

- rc=0. The query reported `11,330 indexed node(s) from graph-prose.json`.
- It returned 20 displayed rows and explicitly truncated `557 more scoring above zero (raise --top)`; this is a bounded orientation result, not a complete search.
- The strongest relevant rows were runtime permission and hook documentation (`PreToolUse hooks evaluate permissions at runtime`, source `claude-code-docs/content/en/docs/claude-code/permissions.md`), but the top result was about dynamic agent configuration, not the shipped `kb_setup.mod_runtime` probe. The graph therefore oriented the source families but did not directly recover the 2026-09-10 local reports.
- Preserved stderr: `mise WARN  tool purgatory cleanup failed: Operation not permitted (os error 1)`. No Graphify source-omission or receipt warning was printed by the task itself.
- Pre-probe `git status --short` showed only the two user-declared untracked files: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/artifacts/function-hooks-work-order.html` and `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/direction/2026-09-12-ray-directives.md`.

### 1. Phase-0 recall probes (incremental)

`mise run kb-recall-work -- "function hooks"` (exact two-word topic; AND stems `function, hook`) returned rc=0 and:

| probe | state | examined | matched |
|---|---:|---:|---:|
| tracked_files | ran | 3,427 | 410 |
| artifact_pages | ran | 144 | 15 |
| branches | ran | 503 | 25 |
| worktrees | ran | 2 | 0 |
| issues | ran | 969 | 41 |
| plans | ran | 218 | 57 |
| memory | ran | 426 | 78 |

The task reports 626 topic matches and 97 live branches with unique commits and no merged PR. Search scope was the `knowledge-base`, `graphify`, and `dotfiles` checkouts; its printed branch list was bounded to 25 rows (`… 72 more in the report`). The `worktrees` zero is not interpreted as “none exist”: the same run positively examined two worktrees, while matching is topic-dependent rather than a worktree inventory result. Preserved stderr: `mise WARN  tool purgatory cleanup failed: Operation not permitted (os error 1)`.

`mise run kb-recall-work -- "plugin types"` (exact two-word topic; AND stems `plugin, type`) returned rc=0 and:

| probe | state | examined | matched |
|---|---:|---:|---:|
| tracked_files | ran | 3,427 | 354 |
| artifact_pages | ran | 144 | 20 |
| branches | ran | 503 | 22 |
| worktrees | ran | 2 | 0 |
| issues | ran | 969 | 8 |
| plans | ran | 218 | 59 |
| memory | ran | 426 | 67 |

The task reports 530 topic matches and again 97 live branches with unique commits and no merged PR; the displayed branch list was bounded to 25 rows. The same `mise` purgatory-cleanup warning appeared.

`mise run kb-recall-work -- "codex sandbox"` (exact two-word topic; AND stems `codex, sandbox`) returned rc=0 and:

| probe | state | examined | matched |
|---|---:|---:|---:|
| tracked_files | ran | 3,427 | 201 |
| artifact_pages | ran | 144 | 4 |
| branches | ran | 503 | 69 |
| worktrees | ran | 2 | 0 |
| issues | ran | 969 | 30 |
| plans | ran | 218 | 53 |
| memory | ran | 426 | 137 |

The task reports 494 topic matches and again 97 live branches with unique commits and no merged PR; the displayed branch list was bounded to 25 rows. The same `mise` purgatory-cleanup warning appeared. All three topic probes had positive matches, so the requested zero-hit control (`"graphify fork"`) was not required for those topic results.

`mise run kb-recall -- "what do we know about function hooks?"` returned rc=0 and reported `showing 5 of 355 matched (searched 426 of 426 total memories in the store)`. This route immediately surfaced 2026-09-11 memories about the module import restriction, invisible load error without `--debug-file`, four-part enablement, `deny`, agent identity, and bounded-probe errors. Its display was explicitly top-5 bounded. Preserved stderr: the same `mise` purgatory-cleanup warning.

Taken with the Graphify query above, these two retrieval modes differ materially: BM25 work-memory directly surfaced the immediately preceding function-hook findings, while the graph query's top 20 did not surface the local session reports or shipped module-runtime probe. The graph query still supplied useful corpus orientation; it was not a sufficient prior-work search by itself.

### 2. The two tracked 2026-09-10 reports

The requested tracked-file location probe (`git ls-files docs/ | grep -i hook`) found the two known reports at:

- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-function-hooks-research.md` — 112 lines, 38,363 bytes.
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-github-function-hooks-examples.md` — 435 lines, 53,353 bytes.

This was a complete tracked-file census under `docs/`; the auxiliary `find docs/research -type f -maxdepth 3` was explicitly depth-bounded and added no additional 2026-09-10 function-hook report. Today's comparison inputs are `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md` (1,463 lines, 118,324 bytes) and `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md` (502 lines, 38,342 bytes).

#### What today re-derived at cost

The September 10 reports already contained, before today's sweep:

- The Graphify corpus gap and its positive control: the earlier query used the same 11,330-node graph, found no function-hook concept, and proved the query mechanism with `PreToolUse permissionDecision` (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-function-hooks-research.md:5`). Today's source sweep repeated the zero/corpus conclusion (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:8`).
- The feature flag, Mod/plugin folder shape, `register(on, options)`, middleware model, tier-based inward routing, `{deny}`, `$`, `e`, `next.origin.tier`, `classic.*`, early-access instability, and the distinction between project-scope enablement and per-process enablement (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-function-hooks-research.md:20`, `:22`, `:39`, `:69`). Today's D1/D3-D10 largely re-established these (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:348`, `:368`, `:373`, `:387`, `:393`, `:406`, `:412`, `:418`, `:423`).
- Five tiers, the restricted `TargetTier`, the real `classic.PreToolUse` spelling, a generated declaration catalog, the debug load line, #92469, #92533, the completed `lossless-claude/lcm` migration, the no-Node/no-SQLite constraint, and the `/plugin-types` regeneration warning (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-github-function-hooks-examples.md:61`, `:71`, `:123`, `:147`, `:160`, `:186`, `:224`, `:324`). Today's source sweep rediscovered these before acknowledging the tracked reports (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:727`, `:802`, `:819`, `:835`).
- GitHub's index-specific behavior, the need to query code/repositories/issues separately, tokenizer noise, qualifiers, authenticated code-search limits, the false-completeness risk, and a reusable four-index search contract (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-github-function-hooks-examples.md:9`, `:25`, `:46`, `:131`, `:273`, `:300`, `:340`). Today's four-index sweep repeated this at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:65`.
- The `phate45/claude-patching` version archaeology and the correction of the claimed 2.1.266 introduction (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-github-function-hooks-examples.md:249`). Today's sweep again selected that repository as ingestion prior art (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:305`).

The strongest proof of duplication is today's synthesis itself: it concludes that “the mechanism was already known two days ago” and classifies tiers, `next.to`, `classic.*`, `{deny}`, the flag, the rename, and `/plugin-types` as confirmation (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:252`). It further records that neither sweep read the two tracked reports until after the work (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:287`).

#### What today genuinely added

Today's work was not valueless. Its novel delta is concentrated and concrete:

- Evidence from the released/pinned 2.1.269 `mods/` source and generated declarations, rather than the 2.1.267-era pre-release surface used on September 10. This yielded host-set `next.origin`, session-dependent `/plugin-types` output, a byte-identity control for the leaked 2.1.267 declaration, `tool.check`'s `(2.1.267, 2.1.269]` arrival, register reload semantics, `PluginOptions`, `.catch`, `TraceOutcome`, `{result}`, and an unbudgeted `engine.create` (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:252`).
- Later issue-thread semantics: `turn.step` is an async-generator hook; user-tier order is a dependency topological sort; `next.to` requests are deferred through the current tier and combined by the furthest-inward target; `prependPlugins` replaces rather than extends the prepend list; `next.trace` exposes snapshots below a hook; withholding a `$` noun does not constrain the model's own Write/Bash/MCP routes (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:543`, `:638`, `:727`, `:896`).
- Failure semantics beyond the earlier “broken hook is skipped”: before/after-`next` differences, wrong-shape and budget failure, named reporting, module-unload versus invocation failure, retained withholdings, and the seven-outcome trace union (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:758`, `:775`, `:933`).
- The complete 22-asset inventory, byte/content-type retrieval route, 30/100/minimized GitHub comment truncations, `gh api <absolute URL>` attachment behavior, and Graphify ingestion limitations. These are new extraction/logistics findings rather than new hook-contract fundamentals (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:277`).

One correction must travel with that delta: today's recommendation to “move the extension check before the GitHub host check” is not a general repair. The session later established that 21 of 22 attachment URLs have no extension, so reordering only helps the single PDF-style URL and leaves the dominant attachment route broken. I do not repeat the broader claim from `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:233`.

### 3. Sibling-repo reports and September 1 sandbox memory

The initial spelling-bounded dotfiles filename probe found eight reports under `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/`; the ninth name from today's source sweep was not returned by that regex, so its tracked status was checked separately below. Across the nine initially named files, `wc` measured 4,027 lines and 202,649 bytes; these are fresh measurements, not inherited figures. The corrected complete count follows immediately after the list.

The nine absolute paths are:

1. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhook-harvest.md` — 1,099 lines, 48,716 bytes.
2. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-aitmpl.md` — 315 lines, 18,535 bytes.
3. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-codesearch.md` — 440 lines, 22,027 bytes.
4. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-examples-review.md` — 597 lines, 32,236 bytes.
5. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-upstream-91870.md` — 308 lines, 17,484 bytes.
6. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-firing-probe.md` — 251 lines, 13,559 bytes.
7. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-retrieval-advisory.md` — 197 lines, 11,187 bytes.
8. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-worktree-bash-probe.md` — 224 lines, 12,792 bytes.
9. `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-12-function-hook-gate-substrate.md` — 596 lines, 26,113 bytes.

The requested unbounded recursive content probe over `graphify-out/memory/` returned eight files; the same probe over the Claude project-memory directory returned seven files. These are keyword matches, not yet a claim that all are relevant. The precise September 1 candidate is `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/graphify-out/memory/query_20260901_235935_can_a_codex_lane_run_this_repo_s_uv_backed_gates.md`; it is read below together with the matching project-memory notes.

#### Correction: there are ten relevant dotfiles reports, not nine

The filename filter above was itself spelling-bounded. It missed `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-skillsdir-and-gate-probes.md` because its name contains neither `fnhook` nor `function-hook`; `git ls-files` confirms it is tracked (118 lines, 6,223 bytes). `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-12-function-hook-gate-substrate.md` is also tracked (`git ls-files --stage` returned mode `100644` and blob `53cb4187…`); the first regex missed it because it searched plural `function-hooks` while the filename is singular `function-hook`. The complete relevant set is therefore **ten tracked reports**, 4,145 lines and 208,872 bytes, not nine. All ten were read for this audit.

This is an uncaught error in today's `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:92`: a filename-spelling inventory claimed nine while omitting the most directly relevant prior report for the type/validation gate now shipped by #754.

#### What those reports already established

The sibling repo contained not merely background research but deployed-version behavioral evidence that today's synthesis still listed as open:

- Function-hook loading, `classic.SessionStart` injection, and `classic.PreToolUse{tool=Read}` denial were measured on Claude Code 2.1.269, including a negative arm and bypass-permissions behavior (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-firing-probe.md:84`, `:101`, `:112`). The same report measured that wrong-shaped `additionalContext` fails open and is visible only in `--debug-file` (`:124`).
- #92533 was already reproduced on 2.1.269 with six arms. Native `tool.call{Bash}`, bare `tool.call`, and `*` broke worktree Bash; `classic.*` and `classic.PreToolUse{tool=Bash}` were safe and actually fired (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-worktree-bash-probe.md:35`, `:63`). Therefore today's synthesis question U2, “Does #92533 still reproduce at 2.1.269?”, was already answered **yes** before this knowledge-base session (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:322`).
- A project-local `.claude/skills/<name>/` plugin was measured loading as `@skills-dir` with no install step, and `$.fs.read` plus both validation gates were probed (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-skillsdir-and-gate-probes.md:10`, `:17`, `:41`, `:63`). That report is exactly the gate precursor the filename-only count missed.
- `claude plugin validate` and `tsc --noEmit` were already shown complementary: validation catches event-name and parse errors but not a wrong result shape; typed `tsc` catches `string` versus `string[]`; an `(on: any)` module makes the type gate decorative (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-skillsdir-and-gate-probes.md:63`). This is the conceptual contract #754 shipped again.
- The harvest had already catalogued `.catch`, fail-open recovery patterns, dual classic/module wiring, visible liveness, contract canaries, native Bash exposure, matcher shapes, result shapes, and real-world `$` usage across 12 repositories (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhook-harvest.md:14`, `:43`, `:71`, `:469`, `:587`).
- The upstream issue report had already harvested all 161 comments and documented the 2.1.260–2.1.267 evolution, including settings `env` enablement as reported by `cwschroeder`, `classic.*`, failure modes, and `tool.check`'s then-future status (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-upstream-91870.md:1`, `:34`, `:116`, `:185`).

#### Additional wrong or stale claims the session did not catch

1. **The “nine reports” count is false; there are ten.** Mechanism: filename token selection omitted `skillsdir-and-gate-probes.md` and a singular `function-hook` name.
2. **Today's U2 is a false open question.** The deployed-version #92533 reproduction and the safe classic bridge were already measured in dotfiles, as cited above.
3. **One dotfiles report contradicts itself at its end.** Its six-arm table says `classic.*` and `classic.PreToolUse{tool=Bash}` were tested and passed (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-worktree-bash-probe.md:35`), while its Limits section says that exact classic bridge was “not tested” (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-function-hooks-worktree-bash-probe.md:213`). The limits sentence is stale and wrong.
4. **“Nobody” uses `@skills-dir` is false.** The large harvest says zero public deployment examples (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhook-harvest.md:384`), but the same repo's independent code-search report found `eshaanshah1/shepherd` (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-fnhooks-codesearch.md:117`), and its own live probe loaded a project-local plugin as `@skills-dir` (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/2026-09-11-skillsdir-and-gate-probes.md:17`). The harvest's zero was query-shaped, not a corpus fact.

#### The September 1 sandbox memory

The exact work-memory is `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/graphify-out/memory/query_20260901_235935_can_a_codex_lane_run_this_repo_s_uv_backed_gates.md` (67 lines, 4,391 bytes). It states both independent walls plainly:

- uv-backed tasks fail because the lane cannot write `/Users/rmanaloto/Library/Caches`; `--add-dir "$HOME/Library/Caches"` changed the same `mise run kb-context` shape from rc=2 to rc=0 (`:24-32`, `:53-56`).
- network egress is off by default; `git ls-remote` returned rc=128 / `Could not resolve host: github.com`, while `-c sandbox_workspace_write.network_access=true` is the needed switch (`:24-38`).

The project-memory copies make the same measurements independently explicit: `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/memory/a-codex-lane-has-no-network-by-default.md:11` records the two-arm rc=128/rc=0 network probe, and `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/memory/codex-lane-cannot-write-agents-or-run-uv-gates.md:21` records the uv-cache rc=2/rc=0 probe. This was discoverable before dispatch: today's `"codex sandbox"` recall examined all 426 memories and matched 137. Re-discovering the no-network wall was therefore a recall failure, not absent documentation.

### 4. Failure mechanism and one implementable prevention

The failure is a chain of three concrete mechanisms, not “agents forgot”:

1. **Recall is mandated but not enforced.** The graph query is machine-enforced, while `kb-recall-work` is only prose: compare `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/research-doc-sources.md:17` with the mandate at `:30`. Today's source sweep ran only the graph and then concluded that every planned source was net-new (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:8`). A graph corpus miss was incorrectly treated as a workspace/prior-work miss.
2. **The full recall result is high-recall but its human report is path-ordered and globally truncated.** `_grep_tracked` sorts each repo's hits lexicographically (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/recall_work.py:420`), `probe_files` appends repositories in configured order (`:434`), and `render_report` prints only the first default 40 hits before `… more not shown` (`:1169`, `:1193`). The live `"function hooks"` report therefore displays 40 knowledge-base paths ending before the two September 10 reports and before any dotfiles result, even though it measured 410 matching tracked files. Control arm: the same rendered report does show a known-present early path, `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/artifacts/function-hooks-dont-reach-codex.html`, at report line 70; searches for the two September 10 report names and the dotfiles report paths returned zero in the rendered file. The data exists behind the truncation; the decision surface hides it.
3. **More specificity can erase results.** `_grep_tracked` passes every stem to `git grep --all-match` (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/recall_work.py:421`). Today's synthesis records a long query falling from hundreds of matches to zero despite `git grep -ln 91870` finding three tracked files (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:300`). The two-to-three-word constraint in this brief is therefore necessary but currently caller discipline, not an API invariant.

**One proposed change: add a machine-enforced `kb-recall-gate` receipt before any research workflow can make an external call.** Its implementable contract:

- Input is a two- or three-word topic; reject more stems instead of silently ANDing them.
- Consume the full `kb-recall-work --json` result, not the 40-row Markdown projection.
- Select and print at least one candidate **per repository with tracked-file matches**, ranked by exact phrase, `docs/research/**`/report path, and recency; also print the top memory candidate when memory matched.
- Require the caller to pass `--reviewed <absolute-path>` for every selected candidate or `--dismiss <path>:<reason>`. Open/read validation records each path's current blob SHA (or content hash for untracked memory).
- Write a receipt containing topic, stems, repo HEADs, all examined/matched counts, selected paths, hashes, and acknowledgements. The research launcher refuses external `gh`/curl/Context7 work without a fresh receipt for the current HEADs.

This one gate would have surfaced and required acknowledgement of both the two knowledge-base reports and the ten dotfiles reports for `function hooks`; for `codex sandbox`, the existing BM25 top result would have required acknowledgement of the September 1 memory. Its acceptance test is the three known failures in this brief: the gate must name at least one relevant path for each topic and refuse when `reviewed` is empty. That is checkable behavior, not another reminder.

## Part 2 — external surfaces omitted by the session

### 5. `llms.txt`, page Markdown, and Context7

#### Anthropic's cheap-document route works

`curl https://code.claude.com/docs/llms.txt` succeeded: HTTP 200, `text/plain; charset=utf-8`, 45,749 bytes. The index explicitly links the Markdown forms of the hooks and plugin references. Direct fetches of `https://code.claude.com/docs/en/hooks.md` and `https://code.claude.com/docs/en/plugins-reference.md` also succeeded with HTTP 200 and `text/markdown; charset=utf-8`, measuring 322,665 and 132,321 bytes respectively. No 404 control was needed because the asserted route was a positive arm, not a negative result.

The first broad hooks-page filter was itself a bad probe: the token `mod` matched ordinary words such as “mode” and produced 17,157 output tokens; the command runner explicitly truncated that output. I do not treat the truncated stream as an exhaustive search. Exact-token controls follow below.

The public page extends today's local sweep in two practical ways:

- The live plugin reference says `claude plugin validate` reports unrecognized fields as warnings rather than errors and documents `--strict`; this strengthens #754's decision to treat validation and `tsc` as separate contracts rather than treating a successful default validation as type evidence.
- The live hooks reference says command `PreToolUse` timeouts allow the call to continue, while `PreModelSwitch` timeouts block, and documents agent-hook behavior changing before v2.1.210. Those are useful classic-hook boundary conditions, but neither is evidence about function-hook timeout semantics.

#### Context7 works, but its answer is only as current and well-routed as its corpus

`ctx7` resolved “Claude Code” to five candidates. The official `/anthropics/claude-code` entry exposed only versions `v2.1.39` and `v2.1.89`; the higher-scoring live-doc candidate was `/websites/code_claude` (benchmark 87.48). A query against that live-doc corpus for `function hooks .claude/mods ToolCallResult deny next.origin plugin TypeScript` returned only classic `PreToolUse` and Agent SDK hook examples. It did confirm that a public `permissionDecision: "deny"` cancels a tool call and that classic hook decisions do not bypass deny/ask permission rules. It surfaced no `.claude/mods`, `tool.call`, `next.origin`, or `ToolCallResult` contract.

That absence is not yet claimed as exhaustive: a Context7 semantic result is a ranked projection, not a corpus scan. The exact Markdown negative/control probe below is the location-appropriate evidence for whether those spellings are present in the named public pages.

The exact two-page probe now supplies that evidence, with an explicit bound: it searched only the live `hooks.md` and `plugins-reference.md` bodies, case-insensitively and as fixed strings. Each page returned zero for `.claude/mods`, `tool.call`, `next.origin`, and `function hook` (each `rg` rc=1). Positive control using the identical fetch-and-fixed-string-count shape found `PreToolUse` 71 times in `hooks.md` and once in `plugins-reference.md` (rc=0). Therefore those two public reference pages do not publish the private function-hook spellings today; this is not a claim about every page on the site.

For TypeScript, `ctx7 library TypeScript ...` resolved `/microsoft/typescript` with versions including 5.8.3, 5.9.2, 5.9.3, 6.0.2, and 7.0.2. Its docs answer extended the local design rationale: `noEmit: true` is the ordinary compiler-backed type-check route; `createSemanticDiagnosticsBuilderProgram` is the compiler-API choice for repeated pure type checks; and `skipLibCheck` applies to **all** `.d.ts` files, not merely third-party libraries. The last point is important for #754: enabling `skipLibCheck` would be capable of skipping the declaration contract the gate is meant to certify. Context7 returned these as TypeScript repository/wiki material rather than evidence about Claude's private function-hook ABI.

#### `mcp2cli`: transport works, configured GitHub call and tool invocation do not

`mcp2cli bake list` succeeded and found two configured stdio servers, `exa` (`npx -y exa-mcp-server`) and `github` (`npx -y @modelcontextprotocol/server-github`). A one-off configured GitHub tools-list call failed before MCP initialization. Exact error (the CLI masked the final path component as shown):

```text
npm error code EPERM
npm error syscall open
npm error path /Users/rmanaloto/.npm/_cacache/tmp/***
npm error errno EPERM
npm error Your cache folder contains root-owned files
Error: cannot use MCP server at npx -y @modelcontextprotocol/server-github: Connection closed
```

The direct HTTP route, `mcp2cli --mcp https://mcp.context7.com/mcp --list --json`, did work and returned the live `resolve-library-id` and `query-docs` tool schemas. A subsequent attempt to invoke `resolve-library-id` did not reach the tool because `mcp2cli` tried to save its discovered schema outside the permitted workspace. The exact terminal exception was:

```text
PermissionError: [Errno 1] Operation not permitted: '/Users/rmanaloto/.cache/mcp2cli/2b1c7e41aa812229_tools.json'
```

I did not redirect the cache to a new writable path because this lane is allowed to author exactly one file. Thus `mcp2cli` proves the remote MCP endpoint and schema are reachable but contributes no new function-hook fact. The separate `ctx7` CLI queries above are the successful content calls; they must not be misreported as `mcp2cli` results.

### 6. GitHub's four indexes, kept separate

The first verbose REST run was too large and the command runner reported truncation at 18,121 tokens. I therefore reran compact projections that retained `total_count`, `incomplete_results`, and the identities needed for follow-up; the counts below come from those reruns, not the truncated output.

#### Code index

`gh api -X GET search/code -f q='"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"' -f per_page=100 --paginate` returned **107 files in 32 unique repositories**, with `incomplete_results:false`. The API's first page was explicitly bounded to 100; `--paginate` retrieved the second page, and the 32-repository count was re-derived with `sort -u | wc -l`. An exact `.claude/mods` code query returned 18 files, all in `ray-manaloto/dotfiles` or `ray-manaloto/knowledge-base`; this literal-path query does not cover repositories that use another plugin location.

An exact-name comparison against only today's `fh-source-sweep.md` and `fh-synthesis.md` found **12 of those 32 repository names absent** from both reports: `SApplefeld/claude-kit`, `TheSmokeDev/taskchad-os`, `TransmuteLabs/Catalyst`, `TransmuteLabs/Catalyst-CC-Patch`, `bsamiee/Rasm`, `conorluddy/tokenblast.cc`, `gillisandrew/dotfiles`, `link-assistant/hive-mind`, `renchris/claude-infrastructure`, `shcv/harness-investigations`, `wandercom/kindex`, and `xkazm04/ai-registry`. Positive control using the same exact-name count found `lossless-claude/lcm` five times. This is a candidate-list gap, not a claim that all 12 contain unique implementation evidence.

Follow-up reads found two genuinely useful omitted implementations:

- `TheSmokeDev/taskchad-os` has an adaptive runtime adapter at [`claude_function_hooks.py`](https://github.com/TheSmokeDev/taskchad-os/blob/master/.claude/scripts/runtime/claude_function_hooks.py). It probes the **actual executable**, runs `/plugin-types` in an isolated directory with network/telemetry suppressed, checks required markers, records a SHA-256 fingerprint in a receipt, refuses to enable the mod when the probe is unavailable, records actual event coverage, and falls back to a host adapter when required events were not observed. This extends #754 with a production consumption pattern: an environment-specific hash is useful as a per-run receipt/fingerprint even though it is unsafe as a cross-machine equality gate—the same distinction made in `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:58`.
- `TransmuteLabs/Catalyst-CC-Patch` documents moving the live plugin out of a dirty patch checkout into `TransmuteLabs/Catalyst`, while retaining a session-only launcher that exports the feature flag and uses one `--plugin-dir`. This is deployment prior art the local sweep omitted, but it does not change the event/type contract.

The omitted Kindex document is explicitly qualified only against Claude Code 2.1.263, so I do not use it as current 2.1.269 authority. The 36-KB SApplefeld spike is no longer on that repository's default branch; GitHub code search points to a historical blob and the document itself says it was retired. Those are useful archaeological leads, not current contract evidence.

#### Issues index

The exact feature-flag issues query returned **38 issues/PRs**, `incomplete_results:false`. It rediscovered `anthropics/claude-code#91870`, #92440 and #92533 and the known ecosystem migrations, but also exposed a source today's report simultaneously called unavailable: [`anchorwatch-dev/anchorwatch#8`](https://github.com/anchorwatch-dev/anchorwatch/issues/8), created 2026-09-11.

That issue reports—and the installed-binary positive probe below corroborates—that `claude plugin validate <mod> --strict` runs the engine's module scan. Its diagnostics expose structural rules a token-presence gate cannot: registrations cannot be stored or arbitrarily chained; event names and `next.to` tiers must be literals; `$` use is constrained to direct `$.noun.event(...)` calls with limited same-file forwarding; `engine.create` cannot take `.catch`; imports must stay inside the plugin; and imported top-level await is refused. It also reports a real false-positive type design that led to a rejected module (`Registration<K> | void` motivated conditional `.catch` chaining; the engine requires a direct chain).

Live positive probe on the installed **2.1.269** binary:

```text
$ claude plugin validate .claude/mods/kb-settings-guard --strict
❯ ./register.ts hooks: tool.call{tool=tool}
❯ ./register.ts calls: $.fs.list (via targetInLinkedWorktree), $.ui.log
✔ Validation passed
```

This verifies that the scan is reachable and analyzes the real #754 consumer. I did **not** mutate a fixture to reproduce every refusal because this lane may author only its report, so the issue's individual negative rules remain upstream-reported rather than independently re-proven here. The #754 runtime check currently derives declaration tokens and explicitly disclaims positional/behavioral proof (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:86`); the live module scan is therefore a complementary missing gate, not a replacement for `/plugin-types` or `tsc`.

This exposes two more session claims that should not survive unqualified:

5. `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:1411` puts Anchorwatch in the “no fetchable repository” list, while the same report links `anchorwatch-dev/anchorwatch` at `:1457` and its issue #8 is publicly fetchable. The “no fetchable repository” claim is false.
6. `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:1454` labels `scriptease/claude-code-redact-plugin` “the sole repositories-index hit.” That was at best a query-time result, not a durable fact: the current exact feature-flag README query returns 11 repositories with `incomplete_results:false`, including Anchorwatch, two Catalyst repositories, `cvuijst/cc-function-hooks-poc`, `diegorv/claude-functions-hook`, and `ray-amjad/awesome-claude-code-function-hooks`.

#### Repository index

The first repository query (`function hooks claude code in:name,description,readme`) was too broad: **64,466** total results, only 100 returned. That bounded page is noise and supports no coverage claim. The corrected exact-flag README query returned **11**, all 11 delivered, `incomplete_results:false`. An exact `.claude/mods` README query returned 22, but manual title/repository review showed heavy collision with game mods and personal configuration. The useful repository-index contribution is discovery/ranking of dedicated projects; it is not a substitute for code or issue reads.

#### Discussions index

GraphQL discussion search for the exact feature flag returned **0**. Control arm with the identical `search(type:DISCUSSION, first:100)` shape and broader query `"function hooks" "Claude Code"` returned 27, proving the transport/index can return results; those 27 were mostly lexical noise. Exact `.claude/mods` returned 8. The only title that appeared plausibly relevant, `hlsitechio/Claude-Code-Mods#6`, was fetched in full and was an untouched GitHub welcome template with zero comments, not function-hook prior art. Thus discussions added no contract evidence in these query arms; the zero is control-armed and bounded to the exact feature-flag spelling.

#### What the TypeScript surface means for #754

The current consumer declares `register(on: any)` and its hook parameters as `any` (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/mods/kb-settings-guard/hooks/register.ts:147`, `:200`). Therefore merely adding `tsc --noEmit` today would not type-check its function-hook ABI; the `any` annotations erase the relationship. This is exactly the decorative-gate failure the pre-existing dotfiles probe had already measured. A meaningful compiler gate must bind the generated declaration's `Register`/event/result types into this source (or compile a typed conformance fixture) and keep `skipLibCheck` off for the target declaration. The engine module scan then remains necessary for loader rules TypeScript cannot express, such as “literal event at the call site” and restricted `$` flow.

This sharpens, rather than refutes, #754's own disclaimer: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:86` says the present implementation reads text and does not prove token position or live firing. It is a lexical drift detector over a live generated artifact—not a complete type or loader contract.

### 7. Live upstream changes since 2026-09-10

#### Releases and installed-version drift

The unbounded paginated releases query found exactly two releases since `2026-09-10T00:00:00Z`:

- [`v2.1.268`](https://github.com/anthropics/claude-code/releases/tag/v2.1.268), published 2026-09-10 20:30:54Z. Relevant entries: a fix to `plugin validate` for paths beginning with two dots, `PermissionRequest` hooks in print mode, the SessionEnd timeout variable, and plugin-menu changes taking effect without `/reload-plugins`.
- [`v2.1.269`](https://github.com/anthropics/claude-code/releases/tag/v2.1.269), published 2026-09-11 19:17:55Z. The relevant addition is `claude plugin eval`, producing scored reproducible JSON/HTML plugin-eval results.

An exact scan over both complete release bodies found zero bodies containing `function hooks`, `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`, or `.claude/mods`. Positive control with the identical body set found `plugin` in both bodies. Thus neither changelog announces an ABI change to the private function-hook surface. `gh api .../releases/latest` identifies 2.1.269 as the latest non-draft, non-prerelease release, and `claude --version` on this host is also **2.1.269**. The gate receipt at audited SHA `4cdd8bfb` therefore targets the current public release at audit time; there is no installed-versus-latest version drift now.

`plugin eval` extends the validation toolbox but does not invalidate the shipped live probe: an eval measures model/plugin task outcomes, while `/plugin-types`, the module scan, and an enabled hook arm measure artifact, loader, and runtime wiring respectively.

#### Issue 91870 comments

The fresh issue query still reports **161 comments**, matching today's source sweep; the issue remains open and was last updated 2026-09-12 00:40:29Z. Seven comments were created since September 10. Two staff clarifications affect authoring:

- A hook can overlap independent work by starting `const beneath = next(e)` before its own asynchronous check; guarding belongs on `tool.check` because starting `next` on `tool.call` can execute the tool ([comment 5618866247](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5618866247)).
- When an outer hook settles and abandons a dispatch, plugins still own their outstanding work; `next.signal` says the host no longer wants the return value, but does not stop `$` calls or floating work ([comment 5638914414](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5638914414)).

Today's source sweep already captured both facts at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:1145` and `:1150`. The last September 12 comment asks who must observe a downstream rejection after the outer hook has already denied; it explicitly says it is a question, not a reproduced bug, and has no answer yet. That rejection-ownership detail remains **unverified**. No newer comment than the 161 already harvested changes #754's present contract.

#### Docs update status

The live hooks and plugin Markdown pages return `Last-Modified: Sat, 12 Sep 2026 18:13:21 GMT`, but both values equal their fetch time and came from Mintlify's dynamic Markdown route; they are not credible source-edit timestamps. The public `anthropics/claude-code` repository does not contain `docs/en/hooks.md`: the contents endpoint returned HTTP 404. Location control with the same endpoint returned `README.md` (2,873 bytes, SHA `80aa75e…`), and a repository-wide commit control found eight commits since September 10. Consequently there is no public source-history arm here from which to prove whether the page text changed after September 10.

What is verifiable in today's snapshot is narrower: the current pages document classic hooks richly, but the fixed-string negative/control arm above finds no private function-hook vocabulary. A post-September-10 documentation *update* is **unverified**; a current public function-hook contract is absent from the two relevant reference pages.

### Final workspace integrity check

`HEAD` remains exactly `4cdd8bfbc3a2d7919adc8057c34afd487813fa26`. The final status is no longer the two-file untracked state observed before the first graph probe: six agent/skill configuration files are modified, `python/src/kb_setup/mod_runtime.py` has a staged 38-line addition, and `sources/claudex-loop.manifest` is newly untracked, alongside the two declared untracked documents. These changes arrived concurrently; this lane did not author, stage, discard, or inspect them as audit inputs. I left them untouched. The report itself is ignored by `.gitignore:190`, as expected for `.agent/` reports.

No writing gate, commit, PR, reset, clean, or checkout was run. The required recall tasks generated their normal ignored recall artifacts; the only file content this lane intentionally authored is this report.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — audited the two tracked September 10 reports, today's reports, the recall/runtime implementations, and the #754 consumer at `4cdd8bfb`.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — read all ten relevant tracked function-hook/gate reports and compared their measured 2.1.269 findings.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — read releases since September 10, issue 91870 and its seven new comments, and probed the public repository for docs history.
- [microsoft/TypeScript](https://github.com/microsoft/TypeScript) — queried official compiler/config/wiki material through Context7 for `noEmit`, compiler APIs, and `skipLibCheck` semantics.
- [TheSmokeDev/taskchad-os](https://github.com/TheSmokeDev/taskchad-os) — read the adaptive function-hook runtime probe and receipt/fallback implementation omitted by the local sweep.
- [TransmuteLabs/Catalyst-CC-Patch](https://github.com/TransmuteLabs/Catalyst-CC-Patch) — read the mods deployment README and session-only launcher.
- [anchorwatch-dev/anchorwatch](https://github.com/anchorwatch-dev/anchorwatch) — read issue #8's engine module-scan findings and validation failure account.
- [Digital-Process-Tools/claude-supertool](https://github.com/Digital-Process-Tools/claude-supertool) — read issue #2293 as an issues-index control/follow-up implementation proposal.
- [wandercom/kindex](https://github.com/wandercom/kindex) — read its 2.1.263-qualified function-hooks integration document as stale archaeological prior art.
- [SApplefeld/claude-kit](https://github.com/SApplefeld/claude-kit) — read the historical, retired 36-KB function-hooks spike blob found by code search but absent from the default branch.
- [conorluddy/tokenblast.cc](https://github.com/conorluddy/tokenblast.cc) — read the function-hook feature-flag region of its large environment-variable catalog.
- [hlsitechio/Claude-Code-Mods](https://github.com/hlsitechio/Claude-Code-Mods) — read discussion #6 in full to reject a lexical `.claude/mods` false lead.
