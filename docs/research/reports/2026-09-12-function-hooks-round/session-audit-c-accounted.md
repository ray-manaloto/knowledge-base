# Session audit C — durable-home accounting

Audit target: branch `feat/754-plugin-types-contract`, commit `4cdd8bfb`
(`4cdd8bfbc3a2d7919adc8057c34afd487813fa26`).

Status: **COMPLETE** for the fixed `4cdd8bfb` audit target. Concurrent worktree
changes discovered during the audit are itemized separately and are not silently
folded into that commit's result.
The nine named agent reports, the raw Astra verdict, the two untracked documents,
Git history/tracked docs, GitHub issues and comments, committed work-memory, and
the external agent memory index are all in scope. A file under `.agent/**` is
treated as volatile evidence, not as a durable home.

## Method and retained diagnostics

- Initial required `graphify query "…"` orientation attempt was denied before
  execution by `kb_setup.hook_guard`: `Do not run graphify query by hand. Use the
  mise task: mise run kb-query -- "<question>".` No graph result came from this
  route.
- The repository-approved `mise run kb-query -- "…"` route emitted
  `mise WARN tool purgatory cleanup failed: Operation not permitted (os error 1)`.
  Graphify then warned that the graph uses the pre-#1504 node-ID scheme and needs
  a forced rebuild for path-qualified IDs. The wrapper rejected the answer as
  incomplete: Graphify returned rc=0 but only 60 of 1,442 BFS-depth-2 nodes fit
  the approximately 2,000-token budget; wrapper rc=3. This broad query is
  explicitly **TRUNCATED and not evidence of absence**. The returned prefix was
  generic and did not orient the session audit to a reliable finding set, so the
  reports themselves remain fallback authority.
- Plan recovery selected
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.planning/2026-08-30-upgrade-protocol-spec`.
  Direct execution of the resolver first failed with `permission denied`; running
  it through `sh` succeeded. An attempted environment-presence probe using bare
  `env` was denied by `kb_setup.secret_guard`; the corrected `[[ -v NAME ]]`
  probe showed both `PLAN_ID` and `PWF_PLAN_ROOT` unset.
- Initial worktree probe showed the expected two untracked files and no tracked
  diff: `docs/artifacts/function-hooks-work-order.html` and
  `docs/direction/2026-09-12-ray-directives.md`.

## Probe controls

Controls and route-specific bounds will be recorded here before negative homing
claims are accepted.

- **Git history/control.** `git log --all -S'kb-mod-runtime-check' --oneline`
  found `4cdd8bfb` (and earlier related commits); `git show 4cdd8bfb` contains the
  task, Python module, tests and arm. This is the positive control for the same
  `-S` route used for distinctive-string commit searches.
- **Tracked docs/control.** The bounded tracked-file route was
  `git ls-files docs graphify-out/memory sources` followed by fixed-string
  search. It found `consumer-required set` in committed
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/graphify-out/memory/query_20260912_134329_d5f…md:30-34`
  and the live-task retirement in
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.README.md:30-57`.
  Exact-zero results below are only claims about that bounded tracked set.
- **GitHub/control.** `gh issue list --state all --limit 200` is explicitly
  bounded at 200. Older named issues were fetched directly. GitHub issue search
  over title/body/comments found `kb-mod-runtime-check` in #754/#766/#771 and
  `consumer-required set` in #754, while the exact work-order phrases `36
  decisions settled across six rounds` and `the tsc layer` returned zero. The
  route therefore discriminated before it was used for negative claims.
- **Work-memory/control.** The external agent-memory search found
  `consumer-required set` in
  `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/memory/generated-declarations-are-environment-dependent.md:27-31`.
  The same route found none of the exact work-order phrases or six of Ray's
  seven verbatim directives. The seventh—keeping dotfiles #1020 current—is
  restated in GitHub comment 5647302470, not in the agent-memory tree.
- **Issue-state freshness.** Local and external issue/PR states were fetched
  live through `gh api` on 2026-09-12. For PRs, a second `/pulls/<n>` or
  `gh pr view` probe distinguished MERGED from merely CLOSED.
- **Source stability.** The final complete source census after the home map was
  5,285 lines / 406,417 bytes across the ten required volatile inputs. The
  owner report had grown from the inherited 494-line description to 873 lines;
  the addenda through line 873 are included. The final hashes were:
  `fh-source-sweep ccdef16e…`, `fh-synthesis 1f70a1ac…`,
  `extract-research-lead acca1118…`, `extract-research-a-live 997615c1…`,
  `extract-research-a1-gh-source 49d3f0f0…`,
  `extract-research-b1-extension-points b377bc76…`,
  `extract-research-b2-ingest-paths 103ebbb5…`,
  `graphify-extraction-owner f0cc9776…`, `754-advisor-verdict 85a7139c…`,
  and `astra-verdict 50934b9f…` (SHA-256 prefixes).

## Finding inventory and durable-home map

The table is deduplicated by actionable proposition, not by sentence. Its
`PENDING` cells preserve the incremental audit-time state; the authoritative
final disposition is the 20-homed/127-unhomed map below. A cross-reference to
another `.agent/**` report does not count as a home.

### Function-hook reconciliation and source/ingestion findings

| ID | Distinct finding, decision, measurement, or recommendation | Volatile evidence | Durable home |
|---|---|---|---|
| F001 | `next.origin` is host-set, MessagePort/seat-derived, readonly, and absent from caller-facing argument slots; admin tier checks therefore have contractual enforcement value, although runtime anti-forgery was not probed. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:22-76` | PENDING |
| F002 | Tool execution and model-visible refusal are separate: calling `next(e)` decides whether the tool runs, while returning `{deny}` decides what the model is told; an empty-string `deny` is presence-tested and denies on 2.1.261+, unlike 2.1.260. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:78-109` | PENDING |
| F003 | `/plugin-types` output depends on the generating session’s connected MCP servers, not only the Claude Code version: same-machine 2.1.269 outputs differed by 71 added MCP-schema lines; citations above the first insertion near 8,380 are copy-specific. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:111-149` | PENDING |
| F004 | The `asgeirtj/system_prompts_leaks` 2.1.267 declarations were byte-identical to a locally regenerated copy (`36aec298…`), closing the prior provenance control arm for that version. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:151-173` | PENDING |
| F005 | `tool.check` was absent in 2.1.267 and present ten times in 2.1.269; it shipped in `(2.1.267, 2.1.269]`, while `next.trace` already existed in 2.1.267 and `hook.error` remained absent in both. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:175-197` | PENDING |
| F006 | GitHub’s repositories index is useful when queried with natural-language name/description terms; the one-hit env-var-literal result did not support a general claim that the index is useless. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:199-217` | PENDING |
| F007 | Graphify’s 12,000-character HTML-to-Markdown slice is at `ingest.py:160`, not `:144`; a second volatile report still carries the wrong citation. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:219-232` | PENDING |
| F008 | Graphify’s text cap is 10,485,760 bytes and the largest issue asset measured 9,789,851 bytes, so the 22 current assets take the smaller-binary silent-wrong-output arm rather than the oversized-download failure arm. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:234-242` | PENDING |
| F009 | “A broken hook is skipped” covers failed invocations, not all load failures; a module can unload while previously established withholding behavior remains. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:243-248` | PENDING |
| F010 | `Register` receives fixed-per-activation `PluginOptions`; changing options reloads the plugin and reruns `register`, and the options channel is manifest `userConfig`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:259-266` | PENDING |
| F011 | `turn.step` handlers are async generators, so a one-signature hook contract is incomplete. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:267-267` | PENDING |
| F012 | `next.to` skips are deferred until the end of the current tier and intersect across that tier; the lowest target wins. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:268-268` | PENDING |
| F013 | `prependPlugins` replaces the full prepend list; an administrator-provided list can silently drop `sec-default@builtin` unless it is explicitly retained. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:269-269` | PENDING |
| F014 | Withholding a `$` capability noun constrains plugin capabilities but does not constrain the model’s own Write, Bash, or MCP effects; a `$`-only guard cannot claim universal tool enforcement. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:270-270` | PENDING |
| F015 | `TraceOutcome` is a seven-member union; `skipped` conflates hook failure with a `next.to` skip from above, and only its reason distinguishes them. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:271-271` | PENDING |
| F016 | `engine.create` has no execution budget, and its failure belongs to plugin load rather than an ordinary hook invocation. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:272-272` | PENDING |
| F017 | A `tool.call` hook may answer the call itself with `{result}`; managed-settings hooks run first and their deny becomes the call result. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:273-274` | PENDING |
| F018 | `.catch` is a declared recovery surface; without it a failed hook is absent, and registering a second catch throws. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:275-275` | PENDING |
| F019 | `next.trace` allows a plugin to observe snapshots from every hook below it, so an outer observer can defeat the confidentiality goal of an inner redactor. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:276-276` | PENDING |
| F020 | The 2026-09-12 issue-91870 inventory measured 161 comments, 22 assets totaling about 50.7 MB, 21 extensionless asset URLs, and 23 timeline cross-references; the counts are time-bound, not stable constants. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:277-281` | PENDING |
| F021 | `_detect_url_type` classifies `github.com` before checking `.pdf`; with 21 extensionless URLs, reordering the test is not the fix for this asset set. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:278-280` | PENDING |
| F022 | `gh api <absolute durable attachment URL>` can download asset bytes byte-identically to curl. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:280-280` | PENDING |
| F023 | Three GitHub comment routes truncate silently with rc=0: the comments REST default page at 30, an effective 100-comment view path, and omission of minimized comments; timeline pagination is additionally required for cross-references/deletion context. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:281-281` | PENDING |
| F024 | Graphify has no supported URL/media-handler extension seam; `resolver_registry.register()` is a real language-import seam and served as the positive location-control. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:282-282` | PENDING |
| F025 | `graphify install` replaces this repository’s `## graphify` instruction section, so it cannot be treated as a harmless additive refresh. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:283-283` | PENDING |
| F026 | The current contract confirms five tiers; `TargetTier` excludes `prepend` and `user`; classic tool interception is addressed as `classic.PreToolUse`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:284-285` | PENDING |
| F027 | The session’s knowledge loss was measured at three layers: absent from the graph, already present but unread in tracked 2026-09-10 reports, and already present but unread in the sibling dotfiles checkout. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:287-299` | PENDING |
| F028 | `kb-recall-work` produced a false negative because adding query terms ANDed stems until 410 matches became zero despite three tracked `91870` hits; this is recommended as the highest-leverage new ticket. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:300-309` | PENDING |
| F029 | Enforcement placement remains open: whether a prepend hook can skip an append redactor, and whether any unskippable floor exists, needs a two-plugin runtime arm. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:318-323` | PENDING |
| F030 | The 2.1.269 status of upstream issue #92533 remains decision-blocking; a passthrough `tool.call` Bash hook may break worktree-isolated subagent Bash and must be tested before migration. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:323-323` | PENDING |
| F031 | It remains unestablished whether a no-Node/no-DOM function-hook module can invoke this repository’s Python/`uv run` guards without a daemon or rewrite. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:324-324` | PENDING |
| F032 | Project-scoped `.claude/settings.json` enablement timing for `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` remained open in the synthesis and determines whether there is a sanctioned always-on route under the no-user-settings policy. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:325-325` | PENDING |
| F033 | The sole unresolved Track-B ingestion choice was whether `yt-dlp` accepts a GitHub `user-attachments` MP4 directly. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:326-326` | PENDING |
| F034 | Runtime contents and secret-handling of manifest `PluginOptions`/`userConfig` remained open. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:327-327` | PENDING |
| F035 | GitHub-search failure shapes remained unarmed: primary/secondary rate-limit responses, silent 200/empty GraphQL pagination, the `gh issue view` comment ceiling above 161, and private-repository attachment redirects. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:329-337` | PENDING |
| F036 | Recovery for failed `engine.create`, durable pre-execution audit evidence, complete agent spawn/completion coverage, and the `fs.read` versus `fs.readFile` naming split remained unestablished. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:337-340` | PENDING |
| F037 | Graphify `resolver_registry.register()` stability across releases is not promised; the architecture PDF and 2400×1600 affordance cheat sheet were still unread; poteat’s Anthropic employment was not confirmed. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:341-343` | PENDING |
| F038 | Retire as open questions: origin forgeability, `tool.check` shipment, leaked-declaration provenance, options type/lifetime, and the 9,192-versus-9,263 declaration mystery. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:345-348` | PENDING |
| F039 | Proposed probe order is: first test one local MP4 transcription and a function-hook load line; then project-scope flag enablement, tier-skip enforcement, #92533, cheat-sheet vision, runtime `PluginOptions`, and an exhausted-rate-limit known-hit control. None of these probes was run by the synthesist. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:352-376` | PENDING |
| F040 | `claude plugin validate` is syntactic only and cannot prove a requested `$` noun resolves; every runtime result needs its Claude Code version condition because the mods API permits unannounced changes. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:372-376` | PENDING |
| F041 | Recommended corpus order: resync `sources/claude-code.manifest` from 2.1.258 to 2.1.269 first; add eight named external repositories by manifest; ingest the richer local dotfiles reports as media/extractions; do not commit a generated `.d.ts`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:399-415` | PENDING |
| F042 | Recommended media route: one YouTube item through `kb-add`; hand-fetch nine issue MP4s, transcribe locally, and commit transcripts because the host’s signed fetch URLs expire. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:417-424` | PENDING |
| F043 | Recommended token-bearing route: separately extract the architecture PDF, vision-read the cheat sheet, and capture issue body/comments plus paginated timeline while discarding partial stdout on nonzero rc. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:425-431` | PENDING |
| F044 | Every imported aitmpl API/component claim must remain labelled provisional/community interpretation, and every comment-sourced claim must retain date and Claude Code version because the API changed within the thread. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:437-448` | PENDING |
| F045 | None of the proposed ingestion, transcription, vision, or runtime probes in the synthesis was executed; comment-derived statements were relayed, not independently read there. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:452-479` | PENDING |
| F046 | No named function-hook candidate repository had a `sources/*.manifest` or registry row at the audited point; the registry/ingestion action remained unperformed. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-synthesis.md:497-500` | PENDING |

### Graphify extraction, Codex runtime, fork-currency, and lane-permission findings

| ID | Distinct finding, decision, measurement, or recommendation | Volatile evidence | Durable home |
|---|---|---|---|
| F047 | The research lanes used explicit workspace-write plus network, not inherited danger-full-access, because `kb-codex --network` currently implies `--write`; the later source read shows that coupling is this repo’s wrapper policy, not a Codex requirement. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:7-28,498-512` | PENDING |
| F048 | The live Graphify target on 2026-09-12 was PyPI/tag 0.9.59, not 0.9.58; the fork was two releases behind, and upstream PRs #3073 and #3311 were both open, stale/idle, and merge-conflicted. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:32-54` | PENDING |
| F049 | `kb-graphify-native-extract --dry-run --backend openai-cli` reached the installed fork backend and produced the expected deep-extract argv, but no live extraction was run. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:58-75` | PENDING |
| F050 | The openai-cli extraction path defaults to serial operation because `GRAPHIFY_OPENAI_CLI_PARALLEL` is unset; the repo default backend remains `claude-cli`, and the task defaults its target to `sources/graphify`, so no default path exercises the fork backend as a general corpus route. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:77-90` | PENDING |
| F051 | The reviewed `graphify.llm.extract_corpus_parallel` SDK signature is pinned with backend/model parameters but has zero call sites; a same-shape positive control found callers for `public_api_fingerprint`. The rank-1 SDK route was specified and gated but never wired. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:92-111` | PENDING |
| F052 | The graph is degraded: every query warns about the pre-#1504 node-ID scheme; prose retrieval returned token-spelling noise; another query was truncated; the measured graph size was 472,069 nodes while `CLAUDE.md` still said 359,026. Rebuild and re-derive the count. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:113-139` | PENDING |
| F053 | `codex doctor --summary` on 0.154.0 returned 22 ok, 3 notes, 1 warning, 0 failures; it independently exposed ambient danger-full-access, 3,068 rollout files using 4.08 GB, and an incomplete/corrupt rollout scan. Recommendation: a redacted-JSON `kb-codex-doctor` currency probe. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:153-180` | PENDING |
| F054 | `codex features list` reported 137 flags while project config enabled none; the stable-but-disabled flags were `multi_agent_v2`, `recommended_plugins`, and `secret_auth_storage`. The report recommends project-scoped `-c features.multi_agent_v2=true`; `worktrees` remains experimental and disabled. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:182-223` | PENDING |
| F055 | `--strict-config` would convert silently ignored Codex config keys into errors, but `kb-codex` has no passthrough for it and the raw invocation is hook-denied; whether `.codex/config.toml` passes strict validation is unverified. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:225-247` | PENDING |
| F056 | Unused Codex orchestration surfaces worth evaluating include `codex agents`, `codex fork`, `codex queue --thread`, `--search`, `--worktree`, and `-C`. The initial recommendation to adopt `codex sandbox` was **withdrawn**: it is deliberately guard-denied because wrapping an arbitrary command hides that command from six inspectors. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:249-264,723-756` | PENDING |
| F057 | Neither Graphify upstream PR had human maintainer review; both only had an advisory bot review and are operationally blocked by conflict/abandonment, not by review objections. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:269-291` | PENDING |
| F058 | The bot’s “syntactically invalid module” findings on upstream #3073 do not apply to the installed fork; our copy imports, the cited line is unrelated, and the PR head has diverged from the twice-rebased working fork. Updating #3073 requires a fresh/current branch, and its head is owned by `TelB-io`, not this fork. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:293-313` | PENDING |
| F059 | Against #3311’s praised techniques, the fork already uses user-turn delivery, loud empty-envelope failure, stdin prompts, read-only sandboxing, forced-serial defaults, per-server MCP disabling, and consistent model-variable guards; its environment-independent tests were not verified. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:315-334` | PENDING |
| F060 | Two upstream bot findings do apply to the fork: MCP-server disabling fails open when `codex mcp list` is unavailable, and untrusted corpus text still reaches an agentic CLI with tools (read-only sandbox mitigates but does not eliminate prompt injection). | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:336-341` | PENDING |
| F061 | `GRAPHIFY_OPENAI_CLI_EFFORT` defaults to `ultra`, but Codex resolves `ultra` as a multi-agent alias to model metadata/Max/highest non-Ultra with a Medium floor; for single-shot extraction with `multi_agent_v2` off, the actual `gpt-5.6-sol` resolution is unverified and may be below `xhigh`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:343-376` | PENDING |
| F062 | The exact 0.9.59 target is lightweight tag/commit `522ea966…`; tag plus PyPI, not branch HEAD, remains the selection rule even though `v8` equalled that target that day. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:381-406` | PENDING |
| F063 | The fork was eight patches ahead and 37 upstream commits behind; predicted aggregate merge conflict is only `CHANGELOG.md`, while fork backend tokens remain absent upstream. The real rebase did not run because sandboxing denied `.git/FETCH_HEAD`, so per-commit conflicts remain unverified. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:408-449` | PENDING |
| F064 | Graphify 0.9.59 adds keyword-only `protected_ids` to `graphify.build.build`, breaking this repo’s exact SDK fingerprint; 12 other pinned symbols matched, but two imported symbols lie outside both fingerprint tuples and behavioral acceptance is still required even for unchanged signatures. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:451-485` | PENDING |
| F065 | The historical phrase “the SDK mismatch blocked every kb-setup command” is now too broad: current CLI wiring applies the contract check to graph writers after version handling. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:487-493` | PENDING |
| F066 | Codex filesystem and network policies compile independently. Named permission profiles are selected via `default_permissions`, custom policies start restricted/fail-closed, and built-ins `:read-only`/`:workspace` can be extended; this supports a read-only-with-network research profile. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:498-546` | PENDING |
| F067 | Permission-profile traps: legacy `profile = NAME` is a runtime error despite schema acceptance; typed `--sandbox` outranks `default_permissions`; choosing `:workspace` ignores legacy `[sandbox_workspace_write]` customizations; domain allowlists require `network_proxy` plus limited mode and are not enforced by `network.domains` alone. OS enforcement was not probed. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:548-571` | PENDING |
| F068 | Codex has separate OTLP log/trace/metric exporters with TLS/mTLS and trace propagation, but neither wrapper nor project config enables them; actual delivery was not tested. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:573-580` | PENDING |
| F069 | The Codex-docs lane hit its 1,500-second bound, left an empty final-output file, and preserved only incremental sections 1–5; its requested ranked top-ten section was never delivered, and the owner’s later priority list is an independent synthesis. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:582-592` | PENDING |
| F070 | Owner priorities were: add strict-config passthrough/probe; run and wrap `codex doctor`; decide project-scoped `multi_agent_v2`; use/resolve `xhigh`; perform the 0.9.59 bump with SDK update; build `kb-fork-rebase`; resolve #3073 ownership; consider isolated temp cwd plus capability detection from #2392; rebuild the graph; wire `extract_corpus_parallel`; and decouple network from write. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:596-678` | PENDING |
| F071 | `kb-fork-rebase` was absent by TOML parsing while two positive-control tasks were present; the report counted 31 pin/derived sites, seven of them derived and order-dependent, making a hand-edited binding-only bump unsafe. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:635-645` | PENDING |
| F072 | PR #2392 contributes one potentially applicable technique: per-call isolated temporary working directories plus CLI-capability detection, without copying Copilot-specific flags to Codex. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:654-660` | PENDING |
| F073 | Explicitly unverified: strict-config compatibility, `ultra` resolution for the selected model, the real rebase, OS enforcement of profiles, `secret_auth_storage`, the timed-out lane’s ranking, behavioral effects of upstream changes, and live extraction cost. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:682-705` | PENDING |

Source-stability note: this owner report grew from 494 lines (25,407 bytes), to
713 lines (36,896 bytes), and then to 873 lines (46,536 bytes) while the audit
was reading it. The inventory includes the 873-line addendum; final closure
requires a size/hash recheck.

### #754 design/verdict findings

| ID | Distinct finding, decision, measurement, or recommendation | Volatile evidence | Durable home |
|---|---|---|---|
| F074 | `guard_inventory` freezes `register.ts` to an exact `WRITE_TOOLS` declaration and single-statement registration loop; any second event, log, arrow handler, renamed loop variable, or other structural change produces NOT_RUN/127. `guard_codegen` independently requires the protected-suffix consumer, so the file is load-bearing for two gates. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:11-54` | PENDING |
| F075 | The actual mod contract depends on `tool.call`, matcher `tool`, event fields `agentId`/`file_path`/`tool`, `$.fs.list` entry name/kind, `$.ui.log`, `next(e)`, and `{deny:string}`; `$.session.cwd()` appears only in a rejected-design comment and must be stripped before consumer extraction. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:56-78` | PENDING |
| F076 | The arms runner is pytest-only and every non-control arm needs a pytest node, although data files are legal mutation targets; therefore live-contract behavior must be reachable through pytest or cannot be certified by current arms. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:80-89` | PENDING |
| F077 | `.claude/types/` was neither tracked nor ignored, so running `/plugin-types` in the repo root would dirty the worktree; the live task must generate in a task-owned empty temporary CWD and require exactly the expected Claude-owned output topology. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:90-93,117-128` | PENDING |
| F078 | The accepted #754 design is intentionally non-hermetic but deterministic relative to the resolved Claude binary: make it an EXCLUSIVE live gate, return NOT_RUN/127 when unavailable, fail only on missing mechanically derived consumer requirements/output topology, report the vendored 2.1.267 delta nonblockingly, and arm tracked detector logic through pytest rather than pretending the arms runner has filesystem actions. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:117-128` | PENDING |
| F079 | `/plugin-types` succeeded noninteractively with both credentialed and empty HOME on Claude Code 2.1.269; credentials are not the blocker, binary presence is. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:139-157` | PENDING |
| F080 | Generated declarations are environment-dependent: full versus empty HOME on the same binary produced 9,263/2,588 versus 9,156/10 lines because MCP and tool inventory differ; whole-file hashes/content cannot be a cross-machine gate. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:159-178` | PENDING |
| F081 | The ticket’s `+1,297` declaration delta was confounded: the version-only line delta is +1,190 and 107 lines came from local environment/tool inventory; the staleness conclusion and the `tool.call` 37→46 measurement survive. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:179-183` | PENDING |
| F082 | All mod-required tokens were invariant across full/bare 2.1.269 environments, while the expected two output filenames were also stable; mechanically extracted required-set membership plus exact relative-path topology is the correct gate surface. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:184-203` | PENDING |
| F083 | Still unverified in the #754 verdict: output filename stability across Claude Code versions and whether arms preserves a pytest process exit 127 distinctly. Graph queries in both lanes failed or truncated and contributed no code facts. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/754-advisor-verdict.md:205-216` | PENDING |

### GitHub extraction and Graphify extension-point details

| ID | Distinct finding, decision, measurement, or recommendation | Volatile evidence | Durable home |
|---|---|---|---|
| F084 | For issue extraction, `gh issue view --json comments` uniquely returned all 161 comments including minimization/edit metadata; the REST issue object supplied the authoritative count/REST-only keys; paginated comments supplied update/app/reaction details; paginated timeline supplied 479 events including 23 cross-references and one deletion; issue reactions supplied 141 attributed rows. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:31-63` | PENDING |
| F085 | The 22-asset type breakdown was nine MP4, nine JPEG, one GIF, one PNG, one 591-KB SVG, and one eight-page PDF; the SVG is directly ingestible text, while the GIF is not in Graphify’s video-extension list. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:65-79,175-180` | PENDING |
| F086 | `curl -I` returning 403 is a probe artifact for GitHub attachments because the signed S3 request is method-bound; GET returns partial content and the real media type. Durable attachment URLs must be stored, not five-minute signed redirects. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:71-79` | PENDING |
| F087 | gh 2.99.0 added attachment upload, not existing-attachment discovery/download; 2.100.0 added nothing relevant. At pinned 2.98.0, `--comments --json` is accepted but `--comments` is silently ignored, while 2.99.0 rejects the combination; use `--json comments`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:81-89` | PENDING |
| F088 | A failed paginated gh request can leave valid partial pages on stdout before exiting 1, so ingestion must require rc=0 and discard all stdout otherwise; malformed/missing GraphQL page metadata can also terminate silently with rc=0. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:91-98` | PENDING |
| F089 | `manifest_ingest.py` handles package manifests only, not this repo’s source manifests or URL/media type declarations; `mcp_ingest.py` indexes local MCP configuration rather than reading from MCP servers, and `serve.py` exposes ten query/impact tools with no ingestion/transcription endpoint. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:141-157` | PENDING |
| F090 | The gh JSON field list comes from two hand-written slices, not generated struct metadata; reflection is used only during export. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:189-193` | PENDING |
| F091 | The issue thread moved materially in two days: comments 154→161 and exact code-index query hits 65→106; any counts inherited from the 2026-09-10 reports require live remeasurement. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:221-233` | PENDING |
| F092 | Three filenames are misleading: `hooks.py` installs Git hooks, not agent hooks; `LANGUAGE_EXTRACTORS` is an unread migration seed while `_DISPATCH` is live; `manifest_ingest.py`/`mcp_ingest.py` do not provide the desired URL route. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:240-249` | PENDING |
| F093 | Public Graphify seams actually available are cross-file resolver registration, semantic chunk completion callbacks, OpenAI-compatible custom HTTP providers, graph interchange/build/merge, `.graphifyignore`/`.graphifyrc`, and about 43 environment variables. The project already uses graph interchange. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:297-307` | PENDING |
| F094 | Missing seams include a live language-extractor registry, exporter discovery/ABC, Python plugin entry points, and built-in-provider override. The HTTP-provider seam cannot replace the existing openai-cli transport patch. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:308-332` | PENDING |
| F095 | Project-local provider configuration requires `GRAPHIFY_ALLOW_LOCAL_PROVIDERS=1` because it controls where corpus data and API keys are sent; this is a security boundary, not just configuration convenience. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:301-306` | PENDING |
| F096 | Graphify’s `always_on` templates are cached and installed into seven host instruction surfaces; root `CLAUDE.md` and `.claude/CLAUDE.md` graphify blocks come from different generators despite similar headings. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:334-365` | PENDING |
| F097 | Graphify’s agent-host integrations live in `install.py`, whereas `hooks.py` installs post-commit/post-checkout Git hooks and a merge driver; no general build-event bus was found. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:367-374` | PENDING |
| F098 | Extension-point conclusions were source-only: no runtime validation, no release-stability proof, no formal whole-program absence proof, incomplete end-to-end reads, and no Git-blame proof of local block authorship. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-lead.md:376-390` | PENDING |
| F099 | On gh 2.98.0, `issue view --json` and `issue list --json` expose the same 27 hand-maintained fields and neither has a structured attachment field; attachments must be parsed from body/comment Markdown. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a-live.md:49-66,259-274` | PENDING |
| F100 | A zero from the discussions index for `anthropics/claude-code` is structural because that repository has discussions disabled; it is not evidence that no discussion exists. Preserve `incomplete_results` when interpreting code/issues searches. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a-live.md:311-333` | PENDING |
| F101 | The issues index found five directly relevant sibling issues absent from the timeline (#93215, #92440, #92533, #92469, #93831), while the repositories index found dedicated reference implementations; no single search/index route is complete. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a-live.md:335-376` | PENDING |
| F102 | gh deliberately drops authentication on cross-host redirects; public S3-backed assets worked unauthenticated, but that mechanism is why private-repository attachments remain a distinct unverified case. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a-live.md:515-532` | PENDING |
| F103 | Beyond comments, `gh issue view` bounds assignees, labels, classic project cards, and subissues at 100, and blocking/blocked-by connections at 50; those unrelated connection bounds must not be mistaken for the comment preloader’s behavior. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a1-gh-source.md:164-177` | PENDING |
| F104 | Graphify’s generic GitHub/text fallback reads 64-KB chunks under a 10-MiB cap and passes a 15-second socket timeout, but inspects neither Content-Type nor Content-Length and has no total elapsed-time deadline; “15 seconds” is not an end-to-end bound. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b2-ingest-paths.md:50-78` | PENDING |
| F105 | The supported no-patch route is local acquisition followed by this repo’s `kb-transcribe` wrapper, which calls Graphify’s local-file transcription path and bypasses URL classification; local PDFs likewise have a separate extractor. Runtime completeness/cost remains unverified. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b2-ingest-paths.md:148-158` | PENDING |

### Additional hook-runtime and capability findings from the raw Astra verdict

| ID | Distinct finding, decision, measurement, or recommendation | Volatile evidence | Durable home |
|---|---|---|---|
| F106 | Hook health requires separate states for inactive rollout/module, failed registration, retained withholding, skipped invocation, explicit refusal, and successful replacement; throw-before-next, throw-after-next, invalid shape, async overrun, wedged worker, and module-resolution failure have different fallbacks. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:11-30` | PENDING |
| F107 | A late deny can misreport an already-completed effect; repeated `next(e)` is intentionally supported for retry/backoff and can create two dispatches with the same tool-use ID, so IDs are not exactly-once receipts; a no-next return must still satisfy the event-specific result schema. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:32-46` | PENDING |
| F108 | Plugin isolation’s contract is “no ambient access,” while the observed Bun Worker plus per-plugin `node:vm` mechanism is explicitly non-contractual and not an OS sandbox; current runtime reports rejected common ambient escape routes. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:48-61` | PENDING |
| F109 | A source-level “read-only command” can still cause network effects: the diff mod’s Git-read environment permits partial-clone lazy fetch. Capability audits must trace child effects rather than infer them from the parent operation label. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:61-63` | PENDING |
| F110 | `$` capability availability can vary by hook; runtime extension is an `engine.create` fold visible to outer consumers, replacement differs from additive extension, TypeScript augmentation does not create runtime nouns, and plugin-provided declaration aggregation remained unverified. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:65-95` | PENDING |
| F111 | Custom capability providers do not automatically receive caller identity; telemetry requires callers to put identity into event names. Do not assume custom nouns inherit `next.origin`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:89-95` | PENDING |
| F112 | Static capability analysis rejects dynamic `$[expression]` and passing `$` to helpers; the allowed pattern keeps literal `$` calls at registration sites and passes narrow closures to helpers. Syntax validation, typechecking, capability availability, and real-engine execution are distinct evidence layers. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:97-110` | PENDING |
| F113 | User-tier dependency ordering is dependent-before-dependency (A depending on B registers A first), with a still-TBD deterministic topo-sort; configured order is not install chronology, hooks cannot self-reseat, and `next.to` authority is refused outside managed tiers. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:126-146` | PENDING |
| F114 | `sec-default` protects classic hooks, selected prompt/settings surfaces, managed descriptions/agent offerings, MCP registration, and managed tool inventory, but passes through `tool.call`, `tool.check`, execution, UI, and I/O generally; it adds no universal execution policy. Caller origin and subject provider provenance are separate. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:148-167` | PENDING |
| F115 | `sec-default` policy reads use a 500-ms memo window, including rejected reads; policy changes can take that long to appear, and local fail-closed decisions do not prove fail-closed module activation/timeout behavior. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:162-167` | PENDING |
| F116 | Component interception is limited to each surface’s declared elements/components; permission requests are deliberately unhookable. Terminal/Desktop supply the diff mod’s required kit, mobile lacks `Select` and is excluded; timers/callbacks can independently invalidate and redraw UI. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:179-205` | PENDING |
| F117 | Concurrency can overlap local work with an early `next(e)`, but downstream transforms must await it and parallel vetoes need a checking surface; `next.signal` only means the host abandoned the return value and does not cancel plugin work or later `$` calls. Late rejection ownership remained unanswered. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:207-220` | PENDING |
| F118 | `tool.call` was reported visible inside subagents, but background routes missed `agent.spawn`/turn events and `agent.list`; historical spawn inputs exposed model/type/prompt/background/cwd rewrites but not effort, and guaranteed completion across abort/error/fork/team routes remained open. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:222-232` | PENDING |
| F119 | Concurrent tool calls can re-enter a guard; suppression follows dispatch lineage rather than a global busy flag. Provider self-calls may suppress that provider’s own hooks, and `session.repo.root` may identify the main worktree rather than Jujutsu workspace context. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:234-238` | PENDING |
| F120 | The event/capability inventory is versioned and provenance-labelled: 2.1.263 reports listed 20 engine events and 36 capability operations; pinned mods add/rename concrete operations, `*` and `classic.*` exist, family globs are not concrete names, and numerous requested/example names—including `hook.error`—must not be reported as supported. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:240-317` | PENDING |
| F121 | Tool-input rewriting does not change the model’s cached original request; contextual explanation is a separate concern. `prompt.context` can repeat, commands/skills belong on `command.run`, and parity with classic Stop-style blocking at `turn.complete` remained unverified. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:325-331` | PENDING |
| F122 | Classic personal Pre/PostToolUse hooks execute inside `tool.call`’s `next(e)` and are bypassed by a function-hook refusal before delegation; migration history includes a 2.1.263 period where `classic.PreToolUse` was unresolved despite bare `PreToolUse` working. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:333-339` | PENDING |
| F123 | Persistent state and concurrency safety remain plugin responsibilities: historical store was machine-scoped JSON without compare-and-set, while shipped mods implement their own queuing, stale-result protection, timer cancellation, redraw coalescing, and failure-resistant telemetry queue. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:341-347` | PENDING |
| F124 | Built-in telemetry is an optional internal provider, not mandatory audit delivery: one POST per call, no batching/retry, strict token/property/value limits, runtime-only mark invariants, differing env truthiness rules, and swallowed optional failures; no external-audit guarantee follows. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:349-366` | PENDING |
| F125 | API churn observed includes fs method renames, origin string→object, classic namespace migration, evolving error handling, and expanding registries; the early-access API explicitly permits unannounced changes and built-in copies—not marketplace entries—are the deployed artifacts. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:368-379` | PENDING |
| F126 | Performance claims must separate dispatch overhead, policy work, and ordering: a staff p99 near 50 μs lacked a harness/guarantee; eight serial 300-ms waits measured about 2.4 s; earlier 1.9-s and universal Windows-spawn claims were withdrawn. Benchmark the intended control flow. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:381-388` | PENDING |
| F127 | Roadmap facts are qualified: shipping was promised on a weeks scale, more core features may become mods, cross-surface parity is a personal goal, no new signing/dependency system or public real-dispatch tester was promised, and several strong community claims were explicitly withdrawn. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:390-406` | PENDING |
| F128 | The Astra artifact ranked fetchable third-party implementations for ingestion (notably `cvuijst/cc-function-hooks-poc`, Monte9, PromptSign, harness/governance examples) while labelling comment-only/anonymous items as conditional, speculative, deferred, or noise; those repo descriptions were not independently inspected. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:408-441` | PENDING |
| F129 | Additional unresolved areas: recovery/late rejection, durable audit evidence, full agent terminal states, compulsory redaction placement, real dispatch testing, storage atomicity, context/cost controls, artifact integrity at use, mandatory installation/safe recovery, UI/headless parity, contract discovery/versioning, and rewrite-versus-permission evaluation. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/astra-verdict.md:443-459` | PENDING |
| F130 | The current `sources/claude-code.manifest` pin (2.1.258) lacks `mods/` while lightweight tag/commit 2.1.269 (`df52d04a…`) contains 580 blobs/247,235 bytes across diff, sec-default, telemetry, and README; resync is what adds the shipped source. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:237-273` | PENDING |
| F131 | “Claude Mods” is the product name and “function hooks” the implementation term; search/naming must include both. The issue author committed to shipping on a weeks scale, not a fixed release date. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:340-354` | PENDING |
| F132 | Shipped mod packaging uses `hooks/hooks.json` with a `modules` array and a plain `register` function; modules load only with the feature enabled, can run from source via `--plugin-dir`, and are not marketplace listings. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:255-295,463-470` | PENDING |
| F133 | Built-in `sec-default` protects existing organization controls but adds no policy; diff is a large cross-surface pane example; telemetry adds `$.telemetry` during `engine.create` and emits nothing when analytics is off. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:275-299` | PENDING |
| F134 | The linked aitmpl pages resolve to one repository with ten provisional components; their APIs come from proposal media, not the shipped engine. The examples surface candidate nouns/policies/JSX, but must be ingested as community interpretation. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:115-161` | PENDING |
| F135 | An external Ray Amjad YouTube video is an additional source and is the one media URL the existing `kb-add` YouTube route handles directly; it was found via code index and live-oEmbed controlled, not linked by issue 91870. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:323-338` | PENDING |
| F136 | The Astra launch first failed because the wrong cwd resolved no `kb-codex` task, yet a trailing `tail` masked the failure as exit 0; a relaunch captured the real rc and succeeded. Piped command status is not lane status. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:865-877` | PENDING |
| F137 | `LanguageConfig`’s `import_handler`, `resolve_function_name_fn`, and `sanitize_symbol_name_fn` are invoked, but declared `extra_walk_fn` had no consumer; actual extra walking is grammar-specific. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b1-extension-points.md:81-94` | PENDING |
| F138 | Registered language resolvers run after shared resolution in registration order and warn/continue on exceptions; an earlier Kotlin-only resolver pass is explicitly supplied and global registration does not insert a new earlier phase. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b1-extension-points.md:95-129` | PENDING |
| F139 | The eight accepted `graphify export` tokens are html, callflow-html, obsidian, wiki, svg, graphml, neo4j, and falkordb; JSON is ordinary extraction output, while canvas/cypher are outputs rather than accepted format tokens. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b1-extension-points.md:133-166` | PENDING |
| F140 | The source audit found additional callback seams (Google Sheets conversion, watch predicates/path normalization, atomic-write callback) but no general before/after-build bus; semantic completion callbacks fire only for successful combined top-level chunks. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b1-extension-points.md:189-207` | PENDING |
| F141 | About 43 real `GRAPHIFY_*` controls were classified separately from false-positive tokens; `.graphifyrc` and `.graphifyignore` are public/narrow inputs, `.graphify_build.json` and `manifest.json` are internal state, and no `graphify.toml` consumer or Python plugin-entrypoint group was found under the controlled package search. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b1-extension-points.md:290-383` | PENDING |
| F142 | `codex sandbox` and raw `codex exec --strict-config` are intentionally denied, while doctor/features/version are allowed; a permission-profile design cannot be behaviorally armed through `codex sandbox -P` without first resolving the command-wrapper blind spot tracked by #675 or finding another route. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:723-759` | PENDING |
| F143 | Several owner recommendations belong on existing issues rather than new tickets: strict-config on #652 paired with verification #744; `multi_agent_v2` as a precondition for #732; output-schema/resume/fork on #553; sandbox-wrapper conflict on #675; danger-full-access evidence on #767; `.agents/` write limits on #693; `kb-fork-rebase` under #728/#732. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:761-781,863-873` | PENDING |
| F144 | Graphify’s first-class worktree output control is `GRAPHIFY_OUT`, relative or absolute, read once at import/process start; this repo’s general Graphify environment cleaner preserves it, while one native-extract module intentionally strips it in favor of that task’s `--out`. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:783-813` | PENDING |
| F145 | Graphify watch rebuilds use a nonblocking per-output advisory lock with pending-change recovery, but `extract.py` and `cli.py` have no build lock; per-file atomic replacement is crash safety, not multi-writer exclusion. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:814-836` | PENDING |
| F146 | Concurrent worktrees are safe only with distinct output roots. Two builds targeting one shared tree can interleave into a self-inconsistent derived tree even if every file is individually valid. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:826-842` | PENDING |
| F147 | It remains unverified whether all repository derived-state consumers honor nondefault `GRAPHIFY_OUT`; several hardcode `graphify-out`, so stamp/catalog/prose state can strand in the default tree while a worktree graph is written elsewhere. | `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/graphify-extraction-owner.md:843-853` | PENDING |

## Unhomed findings requiring action

### Accounting result

Only **20 of 147** inventory entries have a complete or explicit operational
home inside the four accepted knowledge-base homes:

- **F003, F074-F083** — commit `4cdd8bfb`, its two committed work-memory notes,
  the revised provenance README, and the live #754 comment. The two work-memory
  notes are
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/graphify-out/memory/query_20260912_134329_d5f…md:9-46`
  and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/graphify-out/memory/query_20260912_134330_e957…md:10-64`.
- **F026, F131-F134** — tracked
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-function-hooks-research.md:20-37`
  and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-10-github-function-hooks-examples.md:1-105`.
  These older reports do not home the 2026-09-12 corrections or measurements.
- **F029, F030** — #771 explicitly owns tier behavior and the #92533 worktree
  interaction. This is a **stale home**, because the 2.1.269 result now exists
  only in dotfiles #1020; #771 still describes it as work to perform.
- **F031, F032** — #766 records that `$.process.run` reaches the Python guard
  and that the project settings flag is read in time; the external agent-memory
  files `function-hooks-are-claude-only.md` and the #766 body preserve the same
  decisions.

The other **127 findings are not completely homed in this repository**. The
numbered inventory above is the required self-contained one-line statement and
absolute `file:line` evidence for each. This matrix assigns an exact durable
destination to every one; ranges exclude no IDs silently:

| Unhomed finding IDs | Exact required durable destination |
|---|---|
| F001-F002, F004-F025, F027-F028, F033-F046 | Promote a corrected synthesis to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-function-hooks-synthesis.md`. It must retain the negative/control arms and explicitly supersede the source-sweep claims about `next.origin`, `tool.check`, `_detect_url_type`, and line 144. |
| F047-F073, F142-F147 | Promote the full 873-line owner report, including both late addenda, to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-graphify-extraction-owner.md`; do not promote only the original 494-line prefix. |
| F084-F098 | Promote the lead synthesis to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-function-hooks-extraction-research.md`. |
| F099-F102 | Promote the live GitHub study to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-github-issue-extraction-live.md`. |
| F103 | Promote the gh source/bounds result to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-gh-issue-source-bounds.md`. |
| F104-F105 | Promote the Graphify ingest-path analysis to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-graphify-ingest-paths.md`. |
| F106-F129 | Promote the current 462-line artifact to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-function-hooks-astra-verdict.md`. The existing tracked `2026-09-11-function-hooks-astra-verdict-raw.md` is not this artifact: 194 versus 462 lines, different SHA-256, `cmp` rc=1. |
| F130, F135-F136 | Promote only the corrected/new parts of the source sweep to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-function-hooks-source-sweep-corrected.md`; the full volatile file contains superseded claims and must not be copied verbatim. |
| F137-F141 | Promote the extension-point audit to `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-graphify-extension-points.md`. |

This audit itself is also gitignored evidence. After the lead consumes it,
promote it without changing the finding IDs to
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/2026-09-12-session-audit-c-accounted.md`;
otherwise the only complete finding-to-home ledger is itself unhomed.

Promotion alone preserves research, but it does not assign executable work. The
following issue updates are additionally required:

1. **F028:** create
   `gh issue create --repo ray-manaloto/knowledge-base --title 'kb-recall-work: avoid conjunctive-stem false negatives' --body 'A controlled 2026-09-12 run fell from 410 matches to zero as query stems were added despite three tracked 91870 hits. Preserve per-term evidence and rank/union useful matches instead of requiring every stem.'`.
2. **F020-F025, F041-F046, F084-F105, F130, F135:** update open #203 and create
   `gh issue create --repo ray-manaloto/knowledge-base --title 'Function-hooks corpus: ingest pinned sources, attachments, and continuing deltas' --body 'Resync the Claude Code pin; add the reviewed external sources; capture paginated issue body/comments/timeline and durable attachments; transcribe local MP4s; preserve content/type/rc receipts; keep the source set current.'`.
   #203 already owns truncating URL dispatch, but its suffix-based pdf/image
   exemptions do not cover extensionless GitHub attachment URLs.
3. **F048, F057-F065, F071-F072:** add the live 0.9.59/tag/conflict/SDK findings
   to #728 and #733. #728's title and latest comment still name 0.9.56/0.9.57.
4. **F053-F056, F061, F066-F070, F142-F143:** post the report's routed
   additions to #652/#744 (strict config and doctor), #732 (`multi_agent_v2`),
   #553 (output schema/resume/fork), #675 (command-wrapper/sandbox blind spot),
   #767 (permission evidence), and #693 (`.agents/` writes). Live body/comment
   search found the old owning topics but not the new `strict-config`, doctor,
   `multi_agent_v2`, or 0.9.59 findings.
5. **F144-F147:** create
   `gh issue create --repo ray-manaloto/knowledge-base --title 'Graphify builds: isolate output roots and serialize shared writers' --body 'GRAPHIFY_OUT is process-start scoped; watch locks rebuilds but ordinary build paths do not. Prove every derived-state consumer honors a nondefault root and prevent two worktrees from writing one output tree concurrently.'`.
6. **F030:** add a correction comment to #771 with the measured dotfiles
   2.1.269 result: native `tool.call` matchers reaching Bash reproduce #92533;
   `classic.*` and `classic.PreToolUse{tool=Bash}` do not. The current issue owns
   the probe but does not contain its answer.

### Wrong or stale claims that must not survive promotion

These are additional to the four corrections supplied in the brief:

- Dotfiles comment 5647302470 correctly measured that extensionless GitHub
  assets route to the generic GitHub path, but calls the cause a
  **classifier-ordering defect**. That causal label is wrong for 21 of 22 URLs,
  which have no extension for a reordered suffix check to see. The required
  follow-up comment on dotfiles #1020 should say the missing primitive is an
  attachment/content-type/media acquisition route, not reordering
  `_detect_url_type`.
- The same dotfiles issue's preceding 2026-09-11 comment says `tool.check` is
  not shipped. The controlled 2.1.267/2.1.269 comparison in F005 dates its
  arrival to `(2.1.267, 2.1.269]`; add a superseding note rather than leaving
  both claims undated.
- `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/memory/MEMORY.md:1`
  says #754 is **NOT IMPLEMENTED**. That was true before audit commit
  `4cdd8bfb`; it is now stale and will misroute the post-`/clear` resume.
- Open epic #766 still lists #755 as an active G02 row and omits #771/#772/#773,
  even though #755 is CLOSED and PR #775 merged the chain correction. Its body
  is stale even though the authoritative tracked chain was updated.
- Open #728's title says `v0.9.56 today`; its latest comment advances only to
  0.9.57. The live controlled PyPI probe returned `graphifyy` 0.9.59, and the
  exact GitHub tag resolves to lightweight commit `522ea966…`. The issue is
  valid but its target facts are stale.
- The untracked work-order artifact's promised `tsc` gate/wrong compile
  probe/TypeScript pin is not what commit `4cdd8bfb` implements. Details are in
  the untracked-file audit below.
- The owner report's early suggestion to use `codex sandbox` is withdrawn in its
  own 723-759 addendum because wrappers hide the inner command from guards.
  Copying only the original prefix would resurrect a recommendation the same
  report disproves.

## Untracked-file audit

### `docs/direction/2026-09-12-ray-directives.md`

The file is 142 lines and records seven directives, including the exact user
wording rather than only the session’s interpretation:

1. prefer modern Rust/C++/C/Zig tooling; the file records Biome as the chosen
   TypeScript formatter/linter and rules out ESLint/Prettier;
2. have the Astra advisor fan out Codex source re-review of every supplied link;
3. use browser/gh/Graphify-extension research and synthesize the fan-out;
4. continuously keep `ray-manaloto/dotfiles#1020` or successor issues current;
5. continuously monitor issue 91870 and adjacent issues/PRs/discussions;
6. every question to Ray must go through `/grilling` with interactive prompts;
7. execution/research Codex lanes must not be read-only, while still avoiding
   inherited danger-full-access.

Evidence: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/direction/2026-09-12-ray-directives.md:10-142`.

A tracked-file search bounded to `docs`, committed work-memory, `CLAUDE.md`,
`mise.toml`, `python`, and `tests` found **zero exact matches** for all seven
verbatim directives. Positive control, same `git grep -F` route and scope:
`consumer-required set` matched committed
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:44`.
The same exact-phrase search over the external agent-memory directory and live
knowledge-base issue title/body/comments also returned zero, with the controls
recorded above. Therefore sections 1-3 and 5-7 exist only in this untracked file.
Section 4's ongoing dotfiles-update obligation is echoed only by dotfiles comment
5647302470, outside this repo; no knowledge-base issue owns it.

The file’s section 7 recommendation of workspace-write-plus-network is not a
contradiction of commit `4cdd8bfb`, whose live runtime gate is EXCLUSIVE and
intentionally runs the installed binary. It is, however, partially superseded by
the later Codex-source finding that named permission profiles can supply
read-only filesystem policy with network independently (F066–F067). Preserve
Ray’s directive verbatim and attach that later technical condition; do not edit
his words into the newer implementation advice.

### `docs/artifacts/function-hooks-work-order.html`

The page is 171 lines and publishes a forced three-round order said to summarize
36 decisions: (1) ingest sources/resync Claude Code, (2) fix guard #772 with Node
tests and Biome, (3) land #754 with a `tsc` layer, a deliberately wrong compile
probe, and a TypeScript pin.

Evidence: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/artifacts/function-hooks-work-order.html:109-170`.

The exact page claims `36 decisions settled across six rounds` and `the tsc
layer` had zero matches in the bounded tracked-file search above; the same
positive control matched `mod_runtime.py`. Both exact phrases also returned zero
from live knowledge-base issue title/body/comments and the external agent-memory
tree. Its unique content is therefore: the six-round/36-decision assertion, the
forced ingest→#772→#754 order, and the promised TypeScript `tsc`/wrong-compile/
pin implementation shape.

The page **contradicts the committed #754 implementation**. Commit `4cdd8bfb`
adds a Python `mod_runtime.py` live `/plugin-types` reconciliation gate and Python
tests/arms; its eight changed paths include no TypeScript compiler config or
TypeScript test. The artifact instead promises `tsc`, a wrong compile probe, and
a TypeScript pin. It also labels #754 only “partly committed,” which is stale at
the audit target. The durable page must not be committed as a current work order
without an explicit superseded banner or rewrite to the actual shipped shape.
Exact destination: commit
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/artifacts/function-hooks-work-order.html`
only after adding a visible “SUPERSEDED by `4cdd8bfb`” banner and changing the
current-status panel; preserve the old plan below as historical decision evidence.

### Concurrent late worktree changes

The initial probe matched the brief: no tracked diff and exactly the two named
untracked docs. A later read-only `git status` found concurrent changes this lane
did not make and cannot attribute:

- seven modified agent/reviewer instruction mirrors;
- a staged 38-line change to
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:411-560`
  that explicitly sets `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and treats Claude's
  `Unknown command`/rc=0 response as NOT_RUN;
- a third untracked file,
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/claudex-loop.manifest:1-5`,
  pinning `chaseai-yt/claudex-loop` at `8cf5e2c…`;
- the original two untracked docs remain.

None of those later bytes is a durable home yet. The staged `mod_runtime.py`
change suggests the green `4cdd8bfb` gate may have inherited the feature flag
from the running Claude session and could misclassify a plain terminal/CI run;
this lane did **not** run the behavior arm because the brief permits no writes
outside this report and `/plugin-types` writes generated files. Treat that as
**unverified late evidence**, not a finding certified here. The new source
manifest should either be completed with its registry/source workflow and
committed at its current path or explicitly abandoned by its owner; a clean now
would lose it.

## Dotfiles #1020 comment audit

Live issue: `ray-manaloto/dotfiles#1020` is **OPEN**, updated
2026-09-12T16:50:57Z. Comment
<https://github.com/ray-manaloto/dotfiles/issues/1020#issuecomment-5647302470>
is the requested comment and says future knowledge-base findings will continue
to be posted there.

The declaration/gate core is not unique to that comment: no-credential
generation, environment dependence, `agentId`, `NotebookEdit`, and the
consumer-required-set decision are committed locally in `4cdd8bfb`, work-memory,
#754 and #772. Four result groups are nevertheless **external-only relative to
the four knowledge-base homes**:

1. the measured 2.1.269 #92533 matrix: native `tool.call`/wildcard/Bash fails,
   while `classic.*` and `classic.PreToolUse{tool=Bash}` succeed;
2. the v2.1.258-versus-v2.1.269 `mods/` 404/presence control;
3. the 21 durable attachment URLs, nine rendered videos, unauthenticated ranged
   GET/bogus-UUID control, and five-minute signed-redirect details;
4. Node 26.8.2 direct TypeScript/test execution and the Biome/generator-ownership
   measurements.

Tracked-file and knowledge-base-issue searches found no exact `node 26.8.2` or
`X-Amz-Expires=300` hit; the known `consumer-required set` control found #754.
Those four groups must be promoted via the report paths assigned above, and the
#92533 result must be copied into #771. The comment's `_detect_url_type`
**outcome** is useful, but its “classifier-ordering defect” diagnosis is the
wrong claim described above.

The comment creates real work with no local tracker: *“further measured findings
will be added here”* until function-hooks work completes. Neither #766 nor #771
assigns the cross-repository synchronization duty. Create the proposed
“Function-hooks corpus: ingest pinned sources, attachments, and continuing
deltas” issue and put the dotfiles-update obligation in its acceptance criteria.

## Live issue ledger

All states below are from live `gh` calls, not copied from reports.

### Knowledge-base programme and work owners

| Item | Live state | Audit consequence |
|---|---|---|
| #203 | OPEN | Still owns truncating-URL dispatch, but its pdf/image exemption assumes suffixes; extensionless GitHub attachments make the body incomplete/stale. |
| #397 | OPEN | Moving-ref manifest gate remains open; mentioned by the Graphify owner. |
| #480 | CLOSED | Fixed only the native-extract `GRAPHIFY_OUT` bypass; it does not cover F145-F147's general multi-writer/consumer questions. |
| #553, #652, #675, #686, #693 | all OPEN | Correct topic owners; the new doctor/strict-config/profile/output-root evidence has not been posted except where already noted in their bodies. |
| #727 | CLOSED | `kb-recall-work` shipped, but F028 is a new false-negative mode and is not tracked by this closed ticket. |
| #728, #732, #733, #739, #744 | all OPEN | Still valid; #728's target is stale at 0.9.56/0.9.57, and the session's 0.9.59/doctor/feature evidence is absent. |
| #753 | CLOSED | G00 completion remains valid. PRs #768/#769/#770 are MERGED. |
| #754 | OPEN | Correct: implemented at local `4cdd8bfb` but not delivered to remote main, and a concurrent staged fix now exists. Do not silently close it from local gates. |
| #755 | CLOSED | Correctly delivered by MERGED PR #774. Its static scope does not close #772 or #773. |
| #756, #758-#765 | all OPEN | The remaining original G03/G05-G12 programme is still live. |
| #757 | OPEN | Cold bootstrap/liveness remains valid and was not satisfied by the declaration generator. |
| #766 | OPEN | Programme epic is valid but its chain table is stale: it retains #755 and omits #771/#772/#773. |
| #767 | OPEN | The danger-full-access issue remains valid; the owner report adds first-party doctor evidence only. |
| #771 | OPEN | Still valid for live behavior and cost, but stale about #92533 because the measured result is only in dotfiles. |
| #772 | OPEN | Not fixed by #755; `NotebookEdit.notebook_path` remains its live defect. |
| #773 | OPEN | Static-gate/runtime gaps remain valid; `4cdd8bfb` does not close them. |
| #774, #775 | MERGED | #774 delivered #755; #775 updated the tracked chain. Neither merge updates #766's GitHub body automatically. |

No programme issue was silently closed by `4cdd8bfb`. The silent-staleness cases
are #203, #728, #766 and #771; #754 is intentionally still open because the
branch has not reached remote main.

### External issues and PRs actually named in the artifacts

- `anthropics/claude-code`: #91870, #92440, #92469, #92533, #92675, #93426 and
  #93831 are **OPEN**; PR #93215 is **MERGED**. The upstream engine/worktree
  questions therefore remain live even though the built-in mods PR landed.
- `Graphify-Labs/graphify`: PRs #1404, #2392, #3073 and #3311 are **OPEN**;
  PR #1063 is **MERGED**; PRs #856, #1062 and #2981 are **CLOSED unmerged**;
  issues #1059, #1423, #1504 and #3477 are **CLOSED**. Closed #1504 does not
  rebuild this repo's pre-fix graph; open #3073/#3311 do not remove the fork work.
- `cli/cli`: the attachment-upload stack PRs #14177-#14184, the
  `--comments --json` PR #14215, and the 50-file-cap PR #14289 are all
  **MERGED**. These explain current gh behavior; they do not add a structured
  existing-attachment field.
- Ecosystem references: `Monte9/claude-function-hooks#2/#3`,
  `yonatangross/orchestkit#3917`, `goondocks-co/myco#1172`,
  `jeremylongshore/tons-of-skills-marketplace#1437`,
  `anchorwatch-dev/anchorwatch#8`, and `giadaf-boosha/claude-code#88` are
  **OPEN**. The named `davila7/claude-code-templates#867`,
  `yonatangross/orchestkit#3918/#3993`, `lossless-claude/lcm#376`,
  `Yeachan-Heo/gajae-code#5263`, `goondocks-co/myco#1111`,
  `notdp/hive#80`, `pleaseai/honmoon#90`,
  `JoshuaOliphant/claude-plugins#23`, `makikub/kb-notebooklm-podcast#19`, and
  `thkt/dotclaude#651` are **CLOSED** (the PR subset was live-checked separately
  for merge state). The six `96loveslife/big_model_radar` issues #435/#440/#445/
  #456/#461/#471 and `junlinzhao327-oss/big_model_radar#610` are **OPEN**.
- `ray-manaloto/dotfiles#1020` is **OPEN**. Its continuing-update promise is the
  only cross-repo work commitment identified with no local knowledge-base issue.

Numeric references such as `do-not.md #13`, correction “claim #3,” and report
list item numbers are not GitHub issues and were deliberately not fabricated
into the ledger.

## What I could not verify

- I did not run any writing gate, Graphify build, ingestion, transcription,
  plugin session, or `/plugin-types` behavior arm. The required graph query was
  warning-bearing and truncated as recorded above; source/report inspection is
  the fallback authority.
- I could not behaviorally verify the concurrent staged feature-flag fix without
  allowing `/plugin-types` to write generated files. I therefore do not claim
  that the post-`4cdd8bfb` fix is correct or complete.
- I did not inspect the architecture PDF or cheat-sheet image, did not prove
  private-repository attachment behavior, and did not run the OS-level Codex
  permission-profile arms. Their report statuses remain UNVERIFIED.
- I did not fetch every third-party source repository again. I live-checked the
  named issue/PR states; detailed implementation claims retain the volatile
  report's provenance until the proposed tracked reports are promoted.
- The `--limit 200` issue-list result is bounded. Every explicitly named local
  issue outside that result was fetched directly, but I make no claim that an
  unnamed older issue contains no related text.
- HEAD stayed `4cdd8bfbc3a2d7919adc8057c34afd487813fa26`; the working tree did not stay
  clean. Because other writers were active, this is an audit of the named commit
  plus an explicit late-dirty-state warning, not a certification of the final
  worktree.

## GitHub repos touched

- `ray-manaloto/knowledge-base` — audited the commit, tracked docs/work-memory, volatile reports, and all named local issues/PRs.
- `ray-manaloto/dotfiles` — read live issue #1020 and exact comment 5647302470.
- `anthropics/claude-code` — fetched live state for issue #91870, its sibling issues, and PR #93215.
- `Graphify-Labs/graphify` — fetched live state for the named upstream issues/PRs and exact v0.9.59 tag.
- `cli/cli` — fetched live state for PRs #14177-#14184, #14215, and #14289 cited by the gh extraction study.
- `Monte9/claude-function-hooks` — fetched live state for issues #2 and #3.
- `davila7/claude-code-templates` — fetched live state for PR #867.
- `yonatangross/orchestkit` — fetched live state for issue #3917 and PRs #3918/#3993.
- `lossless-claude/lcm` — fetched live state for issue #376.
- `Yeachan-Heo/gajae-code` — fetched live state for issue #5263.
- `goondocks-co/myco` — fetched live state for issues #1111/#1172.
- `jeremylongshore/tons-of-skills-marketplace` — fetched live state for issue #1437.
- `anchorwatch-dev/anchorwatch` — fetched live state for issue #8.
- `notdp/hive` — fetched live state for issue #80.
- `pleaseai/honmoon` — fetched live state for PR #90.
- `JoshuaOliphant/claude-plugins` — fetched live state for PR #23.
- `makikub/kb-notebooklm-podcast` — fetched live state for PR #19.
- `giadaf-boosha/claude-code` — fetched live state for PR #88.
- `thkt/dotclaude` — fetched live state for PR #651.
- `96loveslife/big_model_radar` — fetched live state for issues #435/#440/#445/#456/#461/#471.
- `junlinzhao327-oss/big_model_radar` — fetched live state for issue #610.
