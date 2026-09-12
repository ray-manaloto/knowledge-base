# Session audit B — function-hook and declaration claims

Audit anchor: `4cdd8bfb` (`4cdd8bfbc3a2d7919adc8057c34afd487813fa26`), branch `feat/754-plugin-types-contract`.

Scope: independently re-derive the load-bearing claims in `fh-source-sweep.md`,
`fh-synthesis.md`, `astra-verdict.md`, the vendored Claude Code function-hook
declarations/README, and issue `anthropics/claude-code#91870`. This report is
written incrementally. Verdicts use **CONFIRMED**, **REFUTED**, and
**UNVERIFIABLE**.

## Evidence-health preflight

- **Graph query incomplete, not evidence of absence.** Required orientation via
  `mise run kb-query -- "Which function-hook TypeScript declarations, reports,
  runtime probes, and issue 91870 evidence establish tool.call deny semantics,
  agentId spelling, capability limits, and version-specific line locations for
  commit 4cdd8bfb?"` failed at the repository wrapper with rc=3 because Graphify
  returned a truncated 67-of-1,726-node prefix at its approximately 2,000-token
  budget. Graphify itself reported rc=0. It also warned that the graph uses the
  pre-#1504 node-ID scheme and needs `graphify extract --force` for path-qualified
  IDs. The command additionally emitted `mise WARN  tool purgatory cleanup
  failed: Operation not permitted (os error 1)`. Source inspection is therefore
  fallback authority for this audit.
- **Worktree identity confirmed.** `git branch --show-current` returned
  `feat/754-plugin-types-contract`; `git rev-parse HEAD` returned the full audit
  anchor above. The pre-existing untracked files were
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/artifacts/function-hooks-work-order.html`
  and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/direction/2026-09-12-ray-directives.md`.
  This audit does not modify them.

## Audit method and bounds

- Declaration claims are checked against both the vendored copy and a freshly
  generated installed copy. A line citation is accepted only when its copy is
  identified or uniquely inferable.
- Negative capability/search results require a same-shape positive control. A
  type declaration can prove that a typed field exists; by itself it cannot
  prove that no runtime escape hatch or host behaviour exists.
- GitHub code, issue, and repository searches are treated as separate indexes.
  Query qualifiers and result caps are recorded with each result.

## Installed versus vendored declarations

- **CONFIRMED — running version.** `claude --version` returned `2.1.269 (Claude
  Code)`. `command -v claude` resolved to `/Users/rmanaloto/.local/bin/claude`,
  whose real path is `/Users/rmanaloto/.local/share/claude/versions/2.1.269`.
- **REFUTED — `claude plugin-types --help` is not useful command help.** On this
  installation it printed the top-level `claude` usage and command list, which
  contains no `plugin-types` subcommand. The real generator is the interactive
  slash command invoked headlessly as `claude -p '/plugin-types'
  --permission-mode bypassPermissions`.
- **CONFIRMED — headless generation and installed-copy measurements.** In
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY`, the slash command returned rc=0
  and wrote `.claude/types/claude-code.d.ts` plus
  `.claude/types/claude-code-mcp.d.ts`. The former is 9,263 lines, 350,185 bytes,
  sha256 `51e327a1b0badc09b138746a743cdcbfb0910ac2c5edc70b21075a1fc25b003c`,
  and begins `// Written by Claude Code 2.1.269.` The MCP file is 2,588 lines,
  253,837 bytes, sha256
  `c0e536571e8d3b3f980daf9fceb4107a1bfa96778bd2289078b2a36b47b856f4`.
- **CONFIRMED — vendored-copy measurements.** The vendored
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts`
  is 7,966 lines, 302,096 bytes, sha256
  `ed6cf189ee388d62735e39219402124eca1e40cea6139ce09776b2f006f80b1a`,
  and self-identifies at line 1 as Claude Code 2.1.267. These match the sibling
  README's line-count/hash claims at absolute lines 3-4 and 89-90.
- **CONFIRMED — same-version output depends on the session environment.** The
  tracked dotfiles 2.1.269 copy is 9,192 lines and 347,960 bytes; the fresh
  2.1.269 copy adds exactly 71 lines and removes none. The first insertion is at
  generated line 8,380 and all additions are schemas for MCP-connected tools
  (`ListMcpResourcesTool`, `ReadMcpResourceDirTool`, `ReadMcpResourceTool`, and
  `RemoteTrigger`). This confirms the mechanism asserted by `fh-synthesis.md`.
  It also means a bare `claude-code.d.ts:N` citation above the shared 8,379-line
  prefix is environment-specific.
- **REFUTED in wording, not substance — README's “2,061 changed diff lines.”** A
  content-line recount for 2.1.267 versus the fresh 2.1.269 output is 1,677
  additions plus 380 deletions = **2,057 changed content lines**, while the line
  count grows by 1,297. The number 2,061 is obtained only by also counting the
  four unified-diff file-header lines. The version-skew conclusion stands, but
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.README.md:92`
  calls diff metadata “changed lines.”

## Issue 91870 freshness and capture integrity

- **CONFIRMED — live issue state.** The REST issue endpoint currently reports
  title `Function Hooks - make plugins 10x more powerful`, state `open`, created
  `2026-09-03T18:00:23Z`, updated `2026-09-12T00:40:29Z`, and 161 comments.
  This agrees with the sweep.
- **CONFIRMED — the local body is current.** After normalizing the command-added
  terminal newline, a byte comparison between the live REST `body` and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/91870-body.md`
  returned rc=0.
- **CONFIRMED — the 332 KB local comment capture is complete and current.** Both
  live REST pagination and the local capture contain 161 comment IDs; the sorted
  ID-set difference is empty. Canonicalizing each item as `[numeric id, body]`
  and removing only trailing newlines produced the same sha256 on both sides:
  `fbf71007e928fae496f4b5832efac7669b8a5ab676790229af782409b4d4e3e3`.
  Thus the local line citations are valid for the current comments capture as of
  this audit. One count probe emitted `tee: /dev/stderr: Operation not
  permitted`; the count and subsequent no-`tee` canonical comparison still
  completed successfully.
- **CONFIRMED/non-contradiction — “580 KB fetched” versus “332 KB capture.”** A
  new paginated REST transfer is 590,177 bytes (about 576 KiB), while the
  normalized local comment markdown is 3,127 lines and 332,721 bytes. The sweep
  and task describe different representations, not different comment sets.

## B4 — `agentId` versus `agent_id`

- **CONFIRMED — function-hook spelling is `agentId`.** The installed 2.1.269
  declaration defines `AgentLoop.agentId?: string` and says it is absent on the
  main loop at
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:102`;
  `ToolCallInput = ToolCallEnvelope & AgentLoop` at the same file's line 7,075.
  Lines 7,068-7,073 explicitly describe and reserve `agentId`. The vendored
  2.1.267 copy has the same `AgentLoop.agentId` contract at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts:102`
  and the same spelling in its `ToolCallInput` documentation at line 6,158.
- **CONFIRMED — classic-hook spelling is `agent_id`.** The classic
  `SubagentStartHookInput` and `SubagentStopHookInput` in the installed copy use
  `agent_id` at absolute lines 6,855 and 6,862; the base classic payload also
  declares optional `agent_id` at line 448. This is a surface distinction, not
  two spellings for the same runtime event.
- **REFUTED/misleading — calling the pair an `agentId`/`agent_id`
  “generated-declaration mismatch.”** `fh-source-sweep.md` makes that comparison
  at its lines 429-432, but both spellings coexist deliberately in both generated
  versions: camelCase for function-hook events and snake_case for wrapped classic
  hook payloads. The audited reports otherwise avoid asserting the wrong spelling;
  their broader warning that identity does not prove full ancestry/coverage is
  sound.

## Pinned `mods/` source integrity

- **CONFIRMED — local source snapshot is byte-for-byte the cited upstream
  commit.** The live recursive Git tree at
  `anthropics/claude-code@df52d04a4e65195c1621fe6222e0564bcccb1804`
  contains 580 blobs below `mods/`; the local
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/mods`
  also contains 580 files. Comparing every upstream blob SHA with `git
  hash-object` for the corresponding local file produced an empty difference.
  Therefore the absolute local `mods/...:line` citations below are primary-source
  citations to exactly the claimed tag commit, not an unchecked cache.
- A first all-file comparison attempt exceeded its 30-second yield because it
  launched 580 serial `git hash-object` processes. The batched control completed
  rc=0. A diagnostic `ps` attempt was blocked by the sandbox with
  `zsh:1: operation not permitted: ps`; neither failure changes the successful
  batched comparison.

## B1 — source-sweep citation failures found so far

- **REFUTED — D3's `sec-default/hooks/register.ts:29` citation.** At exact
  upstream commit `df52d04a`, absolute source
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/mods/sec-default/hooks/register.ts:29`
  registers `tool.describe`; `classic.*` is actually registered at line 20. The
  namespaced-wildcard claim is true, but the cited line is false for the named
  copy.
- **REFUTED — D4's `sec-default/hooks/register.ts:41-42` citation and follow-on
  `:47`.** Lines 41-42 are a blank line and the start of `const isRefused`; the
  organization-tier expression is at absolute lines 35-36, and the user-tier
  comparison is at line 43. The authority logic is real, but all three cited
  locations in the sweep are wrong for the byte-verified `v2.1.269` source.
- **REFUTED — D5's `sec-default/hooks/register.ts:55` citation.** Absolute line
  55 is `() => undefined,` inside the later `tool.list` handler. The quoted
  `return isRefused ? { deny: TOOL_REGISTER_REFUSAL } : next(e)` is at absolute
  line 49. Again, the shape is real and the location is not.
- **CONFIRMED — D6's telemetry fold citation.** Absolute
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/mods/telemetry/hooks/register.ts:15`
  starts the `engine.create` hook; lines 16-19 await `next(e)` and spread the
  result. The cited `:15-19` range says what the sweep claims.
- A citation-extraction command initially failed before reading anything with
  `zsh:1: unmatched "` because an unescaped backtick appeared in the shell
  pattern. The corrected single-quoted search succeeded; no finding relies on
  the failed command.

## B2 — `deny` dependency audit

- **CONFIRMED — current declared contract.** In the fresh 2.1.269 copy,
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:7100`
  defines the `tool.call` result as either `{ result, context? }` or `{ deny }`;
  lines 7,110-7,120 say `deny: string` “Refuses the call” and is absent when the
  call was answered. The same contract exists in vendored 2.1.267 at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts:6199`.
  The engine-event documentation independently says “Return `{ deny: reason }`
  to refuse” at fresh lines 2,419-2,424.
- **REFUTED — source-sweep X2's derived absolutes.** Its statements “`deny` is a
  message to the model, not an engine-level block,” “not calling `next(e)` is the
  only actual block,” and “both are right” about Monte9's “deny has no engine
  meaning” do not follow from the quoted historical explanation and contradict
  the current declarations. Correct conditional: calling `next(e)` can already
  execute the tool, so a later deny cannot undo that effect; returning an
  accepted `{ deny }` without dispatching core refuses the call.
- **REFUTED/overcompressed — synthesis C2's two independent axes.** “`next(e)`
  decides whether the tool RUNS; `deny` decides what the model is TOLD” is safe
  only when read together with its following examples. As a stand-alone rule it
  repeats the false “deny is reporting-only” model. The synthesis's concrete
  examples are sound: `{deny}` without `next` refuses; `await next(e)` followed
  by `{deny}` can misreport an already-performed effect.
- **CONFIRMED — astra D2 does not depend on the false absolute.** It confines its
  claim to a **late** deny, says not calling `next` alone is insufficient without
  an accepted event-specific result, and cites the diff mod's valid `{}` result
  for `command.run`. Those distinctions agree with the declarations and source.
- **UNVERIFIABLE here as a current runtime measurement — `{deny: ""}`.** The
  current type admits the empty string and documents the union member as a
  refusal; issue lines 1,665-1,677 report a 2.1.260-to-2.1.261 behaviour change.
  This lane did not execute a new live 2.1.269 deny arm, so it does not promote
  that historical runtime report into an independently measured current-runtime
  fact.

## Additional contract and citation corrections

- **REFUTED — D9's “`register`'s second parameter is OPTIONAL in practice.”**
  Both vendored 2.1.267 and freshly generated 2.1.269 declarations make the
  parameter required: `Register = (on: On, options: PluginOptions) => unknown`
  at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts:4569`
  and
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:5316`.
  The shipped implementations accepting only `on` at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/mods/sec-default/hooks/register.ts:17`
  and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/mods/telemetry/hooks/register.ts:14`
  show only that JavaScript/TypeScript functions may ignore supplied trailing
  arguments. They do not make the host's second argument optional. The synthesis
  correctly uses the required two-argument signature; astra D9's statement that
  the type was unavailable was already stale against both declaration copies.
- **REFUTED — X11's stated citation range is one line short.** Its quote headed
  `:2419-2423` includes the sentence about managed settings hooks, but that
  sentence is at
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:2424`.
  The quoted content is real in 2.1.269; the published range is not.
- **REFUTED — README token counts.** Recounting literal occurrences with
  `rg -F -o` gives `tool.call` **37 → 46**, not the claimed **46 → 61**, between
  vendored 2.1.267 and fresh 2.1.269. The same probe confirms
  `session.authorize` **0 → 7**, `flag.value` **0 → 0**, and
  `classic.PreToolUse` **9 → 9**. The positive `tool.call` counts are the control
  for both zero-result tokens. Thus the README's event-presence conclusions are
  supported, but its `tool.call` numeric control at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.README.md:95`
  is not reproducible from the two files the paragraph names.
- **CONFIRMED — generation is environment-dependent, with the claimed exact
  counts.** Re-running the same 2.1.269 binary in a fresh `HOME`, while preserving
  the already-set `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, wrote a 9,156-line,
  346,444-byte `claude-code.d.ts` with 24 built-in tools and a 10-line,
  439-byte empty MCP declaration. The normal-home generation wrote 9,263 lines
  with 30 built-in and 170 MCP tools from 12 servers. This reproduces the
  9,263-versus-9,156 and 2,588-versus-10 line counts at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.README.md:49`.
  An earlier stronger isolation (`env -i`, which changed much more than `HOME`)
  returned `Unknown command: /plugin-types` with rc=0; it is not evidence
  against the successful HOME-only arm. A prohibited whole-environment dump was
  stopped before execution by `kb_setup.secret_guard`; the corrected presence
  probe reported the feature flag set, and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/settings.json:4`
  independently records its value as `1`.
  The arithmetic also confirms README lines 55-57: 9,156 minus 7,966 is the
  **1,190-line version-only** delta, and the normal session contributes the
  remaining **107** core-declaration lines.
- **REFUTED as an absolute — “No content hash of these artifacts can ever be a
  gate” and “its successor cannot be checked in.”** A second independent fresh-
  HOME generation, with the same binary and explicit activation flag, reproduced
  both files byte-for-byte: core sha256
  `15eccaa7f31a263cade146814076fc535c263e434721331eb9d76934c9d7f9e5`
  and empty-MCP sha256
  `47979a1cef42168e2f600c759eb3f650bc33f515baa7a9674a632db16b2533e1`.
  An **uncontrolled-session** hash is unsuitable because inventories vary; a
  version-pinned, isolated-generation hash or a normalized core-surface hash is
  technically gateable. Whether the repository should vendor it is a policy
  choice, not a construction impossibility. This refutes the categorical wording
  at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.README.md:49`.

## B5 — live GitHub index sweep

- **REFUTED — this external check was not absent from the session.** The audited
  sweep explicitly records the same four-index exercise at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/fh-source-sweep.md:65`.
  I nevertheless reran every index because search indexes drift.
- **CONFIRMED with one live-count change.** Separate paginated searches for the
  exact token `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` currently return: repository
  index **1** (`scriptease/claude-code-redact-plugin`), issue/PR index **38**,
  code index **107 files in 32 repositories**, and discussion index **0**.
  All three REST responses say `incomplete_results: false`; pagination consumed
  one repository page, one issue page, and two code pages, so none approached
  GitHub Search's 1,000-result exposure bound. The sweep recorded 106 code hits,
  so that inherited number is now stale by one. Its report retained no complete
  prior item set, so the identity of the added/removed/reindexed item is
  **UNVERIFIABLE**, even though the current count is measured.
- **CONFIRMED — discussion zero has a control.** The same paginated GraphQL
  shape using `claude code plugin` returned `discussionCount: 3503` and real
  discussion nodes. Pagination exposed ten 100-node pages (the search exposure
  bound), but only the nonzero control was needed. The exact-token zero is
  therefore discriminating, not an authentication or transport failure.
- **CONFIRMED — qualifier-aware code queries find real modules and avoid the
  punctuation-token trap.** `filename:hooks.json
  CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` returns only
  `noopz/commonplace/hooks/hooks.json`; `path:.claude/mods tool.call` returns only
  this repository's tracked guard; and `filename:register.ts tool.call
  claude-code` returns four files: Anthropic's diff mod, this repository's guard,
  `TheSmokeDev/taskchad-os`'s persona-cognition module, and `bsamiee/Rasm`'s
  function-hooks module. By contrast, the broader `path:hooks tool.call
  claude-code` returns ten mostly classic-hook/token-collision results, exactly
  the noise the tokenizer warning predicts.
- **CONFIRMED as public source, not as runtime behaviour — implementations the
  sweep's prioritized repository table did not describe.** At the immutable
  search-result commits:
  - `TheSmokeDev/taskchad-os` imports `Register`, hooks `session.start`,
    `tool.call`, `turn.complete`, and `prompt.submit`, and bridges events to a
    Python command via `$.process.run` ([blob lines 1-48](https://github.com/TheSmokeDev/taskchad-os/blob/6da9b5cfb3b26ddc73022031590c94fa3da174e0/.claude/plugins/persona-cognition/hooks/register.ts#L1-L48)).
  - `bsamiee/Rasm` uses the required `(on, options)` signature, `next.trace`,
    `{ deny }`, `classic.*`, `$.process`, `$.fs`, and `$.agent.spawn` in a large
    typed module ([blob lines 1-14](https://github.com/bsamiee/Rasm/blob/83b13046ba9628a36ec7c5f6d3677cce10a02b32/.claude/plugins/function-hooks/hooks/register.ts#L1-L14),
    [lines 318-350](https://github.com/bsamiee/Rasm/blob/83b13046ba9628a36ec7c5f6d3677cce10a02b32/.claude/plugins/function-hooks/hooks/register.ts#L318-L350)).
  - `pleaseai/honmoon` uses a typed `(on, options)` registration and implements
    pre/post `tool.call` decisions and redaction with accepted `{ deny }`
    results ([blob lines 538-664](https://github.com/pleaseai/honmoon/blob/0e8c91a822f424171e2fa1975cb39ea7142e5272/packages/claude-plugin/hooks/honmoon.ts#L538-L664)).
  - `djnsty23/claude-auto-dev` is a JSDoc-typed JavaScript module whose Bash
    hook can return `{ deny }` and redact the downstream result
    ([blob lines 55-110](https://github.com/djnsty23/claude-auto-dev/blob/b9d0d564f832fb2d9294c64a805d1199a348eb64/plugins/autodev-core/hooks/fn/autodev-fn.mjs#L55-L110)).
  These are reaching examples for API usage, not proof that each module loaded
  or behaved as intended in a live Claude Code process. `cam-douglas/hermes-playground`
  was also inspected, but its matched `gland.mjs` is a #92533 evidence viewer,
  not a registerable hook implementation.
- **CONFIRMED — natural-language repository search found a post-sweep
  implementation that code search has not indexed.** The exact repository
  queries now return 16 for `claude code function hooks`, **21** for `claude
  function hooks` (the prior report recorded 20), and **6** for
  `function-hooks claude in:name,description` (prior 5). The added dedicated
  result is `AnExiledDev/cc-changelog-plugin`, updated September 12. Three
  repo-qualified code searches against it each returned zero with
  `incomplete_results: true`, so those zeros are invalid. Same-shape controls
  returned three Anthropic `register.ts` files, three Anthropic `tool.call`
  files, and five exact-token files in `noopz/commonplace`.
- **CONFIRMED after changing route — `AnExiledDev/cc-changelog-plugin` is real
  function-hook source.** A recursive Git-tree request at immutable commit
  `06de723fd87d0206d01fb2e6e9b6574f3edb6291` returned nine files with
  `truncated: false`; `hooks/hooks.json` declares `modules: ["module.js"]`.
  The module is JSDoc-typed as `Register`, hooks `session.start`, `command.run`,
  `ui.render`, and nine separate `tool.call` handlers, and uses `$.tool.register`,
  `$.command.register`, `$.http`, `$.store`, `$.process`, and UI capabilities
  ([blob lines 169-264](https://github.com/AnExiledDev/cc-changelog-plugin/blob/06de723fd87d0206d01fb2e6e9b6574f3edb6291/hooks/module.js#L169-L264)).
  Its README reports live 2.1.267/2.1.269 testing, but this audit did not rerun
  those tests. The first tree request accidentally used `-f recursive=1`
  without `-X GET`, became a POST, and returned HTTP 404; the corrected GET is
  the successful evidence.

## Further current-surface claims the reports got wrong

- **REFUTED — synthesis C5's occurrence table as well as the README count.** Its
  `tool.call` **46 → 61** row is not reproducible (literal occurrences are
  **37 → 46**). Its `tool.check` “10 occurrences” is actually ten matching
  lines containing **11 literal occurrences** in 2.1.269; line 2,436 contains
  the token twice. The event's 0-to-present conclusion remains correct. This is
  a count-method error, not a semantic disagreement.
- **REFUTED as a current defect — source-sweep S1 on `agent.offer`.** Live issue
  `anthropics/claude-code#92440` remains open and correctly names a 2.1.263
  mismatch, but both vendored 2.1.267 and generated 2.1.269 use `isOffered`
  consistently in the result, prose, and example. See
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts:150`
  and `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:2493`.
  Calling it a “live upstream defect” at 2.1.269 silently drops the version
  condition; only the still-open issue is live.
- **REFUTED/incomplete — source-sweep D2's “~40 event taxonomy.”** The current
  base declaration defines 32 `EngineEventOf` names, 45 disjoint `OpEventOf`
  names, and 33 `classic.${ClassicHookEvent}` names: **110 named core events**
  before any plugin-added noun methods. The counts were derived from the three
  defining unions/mappings at
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:711`,
  line 2,417, and line 4,006; the engine/op name-set intersection was empty.
  The sweep later admits its D2 list was a comment-token frequency count, but it
  never retracts the load-bearing taxonomy number.
- **REFUTED — astra D6 and synthesis U6 say the options type, defaults, secret
  handling, and refresh lifetime are unavailable.** Those facts are stated in
  both required declarations. Vendored 2.1.267 says values come from manifest
  `userConfig`, defaults are filled, sensitive fields use secure storage,
  validation precedes load, and missing required values fail the load at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts:4027`;
  it defines the exact readonly value union at line 4,035. Its `Register` prose
  says an options change reloads the plugin and reruns registration at lines
  4,558-4,569. Fresh 2.1.269 repeats these contracts at lines 4,550-4,558 and
  5,305-5,316. The secure-storage implementation and actual runtime object were
  not inspected, so implementation behaviour beyond this declared contract is
  **UNVERIFIABLE**, but “the contract does not say” is false.
- **REFUTED as current — astra S1/D10's treatment of `ui.ask` as staff intent
  with headless fallback unverified.** `$.ui.ask` is declared in both 2.1.267 and
  2.1.269. Vendored lines 1,327-1,341 and fresh lines 1,539-1,553 say it uses the
  engine's AskUserQuestion dialog, rejects when dismissed, and rejects in a
  plain `-p` run. `AnExiledDev/cc-changelog-plugin` now also calls it in public
  source. Runtime behaviour was not rerun here, but the declared capability and
  headless contract are no longer unspecified.
- **REFUTED as current — astra S1's `plugin.register` full signature remains
  unverified.** It is absent from vendored 2.1.267 but fully declared in fresh
  2.1.269: event semantics at lines 2,706-2,716, pinned input fields and scanned
  `uses` metadata at lines 4,560-4,595, and `{allow:true}|{refuse:string}` at
  lines 4,597-4,614. Firing is still unmeasured, but the current type/signature
  is settled.
- **CONFIRMED with a version boundary — historical `agent.spawn` results do not
  transfer.** Astra D12 correctly labels `{model,text,isError}` as a 2.1.260
  report. Fresh 2.1.269 instead declares `{model,agentId}|{deny}` and says the
  spawned agent's answer arrives on its own `turn.complete` at
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:258`.
  Complete coverage across background/workflow/fork/teammate routes remains
  **UNVERIFIABLE**; the newer result type does not prove every route fires.

## B3 — capability claims and unreachable negatives

The declarations can settle the typed contract. A current live reaching or
adversarial arm is still required before turning contract text or absence into a
runtime impossibility.

| Claim in the audited reports | Contract verdict | Current-runtime verdict |
|---|---|---|
| A mod has no ambient DOM or Node API / cannot import `fs` | **CONFIRMED as declared contract.** The generated header says “no DOM, no Node” at `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:15`; issue reports and staff comments describe historical enforcement. | **UNVERIFIABLE.** No 2.1.269 adversarial import/escape arm was run here. The reports correctly distinguish a JS realm boundary from an OS sandbox. |
| Therefore a mod cannot perform filesystem, process, or network effects | **REFUTED if read broadly.** The same current interface exposes `$.fs.read/write/list/...` at lines 2,023-2,053, host argv execution through `$.process.run` at lines 2,165-2,186, and host HTTP at lines 2,148-2,162. These are mediated capabilities, not ambient globals. | The external `TheSmokeDev/taskchad-os` module constructs the Python bridge in source; whether that exact module loaded and ran is **UNVERIFIABLE** here. |
| `engine.create` can use `$` or every hook shares the same interface | **REFUTED.** `NoEngineInterface` maps every noun to `never` at fresh lines 3,895-3,901, while `EngineCreateResult` is the open extension record at lines 2,398-2,407. This also explains the historical report that `$.ui.log` was absent there. | No contrary runtime arm was attempted. |
| `engine.create` has no hook budget | **CONFIRMED as declared contract** at fresh lines 5,318-5,324. The stronger sweep gloss “every other hook is budgeted” is **UNVERIFIABLE** from that exception sentence alone; no complete per-event budget table or current overrun suite was supplied. |
| The permission-request component cannot be hooked/rendered | **CONFIRMED as the 2.1.269 declared render grammar.** `RenderComponent` explicitly says the engine alone draws it and omits it from the union at fresh lines 5,344-5,352. `tool.check` can intercept the decision at lines 1,900-1,911; that is not permission-dialog rendering. | **UNVERIFIABLE as an absolute runtime negative.** No deliberately rejected component registration/render arm was constructed. |
| `next.origin` is plugin-supplied or forgeable through event data | **REFUTED by the declared API.** It is host-set from the caller's MessagePort and seat, and plugin writes cannot reach it, at fresh lines 3,839-3,849. Caller-facing arguments also omit `origin`. | An adversarial 2.1.269 transport-forgery arm was not run, so the stronger runtime word “unforgeable” remains **UNVERIFIABLE** beyond the exposed contract. |
| A downstream plugin cannot unregister/inhibit an enclosing admin hook; a hook cannot move itself inward | **CONFIRMED as documented design/source**, and `Registration` exposes only one `.catch`, not unregister/reseat, at fresh lines 5,318-5,331. `next.to` is documented as managed-only/inward at lines 3,804-3,815. | **UNVERIFIABLE as an exhaustive runtime negative.** The reports cite staff statements but construct no current lower-tier attempt to unregister, reseat, or call `next.to`. |
| Abandoning a dispatch automatically cancels plugin work | **REFUTED by contract wording.** `next.signal` is an `AbortSignal` that work “should stop on,” at fresh lines 3,817-3,824: cancellation is cooperative. The live issue's staff statement says abandoned work may continue. | The exact 2.1.269 continuation-after-abandonment behaviour is **UNVERIFIABLE** because no reaching timer/request arm was run. |
| A custom noun provider necessarily receives its caller identity | **UNVERIFIABLE/generalized too far.** Telemetry's own type says that noun cannot see its caller, while current `OpEventOf` says hooks above a `$` operation receive `next.origin` at fresh lines 3,998-4,004. That supports a specific provider design, not a universal impossibility for every custom architecture. |
| There is no public real-engine dispatcher or synthetic-event CI harness | **UNVERIFIABLE.** The issue corpus contains requests, not an exhaustive product/repository proof. The four-index sweep found modules, validators, fixtures, and the #92533 evidence viewer, but no result was demonstrated to import Claude's real dispatcher. Absence from these bounded searches cannot prove nonexistence. |
| `hook.error` is a current hookable event | **REFUTED for the generated typed surface.** It has zero literal hits in both declarations; `tool.call` is the positive control (37 and 46 literal hits), and the issue occurrence is a request. | Runtime-hidden/undeclared dispatch remains **UNVERIFIABLE**; the source sweep appropriately retracted its original positive assertion. |
| `tool.check` does not exist | **CONFIRMED only for vendored 2.1.267; REFUTED for installed 2.1.269.** It has zero hits in the former with `tool.call` as positive control, and 11 literal occurrences in the latter. Fresh lines 1,900-1,911 and 7,184-7,247 define its no-execution query and verdict. | No independent live firing arm was run; declared presence is not firing proof. |
| Only `turn.step` is a streaming hook and it must be an async generator | **CONFIRMED as current type contract** at fresh lines 6,801-6,845: `StreamingEventName = 'turn.step'`, and a plain function is a type error. | No current chunk-transform runtime arm was run. |

Two positive constructions narrow the “cannot” space even though they are not
runtime certifications: `TheSmokeDev/taskchad-os` invokes an existing Python
command from four function-hook events, and `djnsty23/claude-auto-dev` supplies a
JSDoc-typed JavaScript `Register`. The current declarations likewise make every
host-served `$` operation hookable by exact name or `*` at fresh lines
3,998-4,004. Any future negative must therefore name the exact route, tier,
event, and environment it attempted.

## B1 — complete citation ledger

### Generated declaration citations

- **CONFIRMED, but only for the named 2.1.269 copy.** Every bare
  `claude-code.d.ts:<line>` citation in the non-appendix portion of
  `fh-source-sweep.md` was checked at
  `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/types/claude-code.d.ts`:
  lines 904, 2,405, 2,413-2,424, 3,138, 3,160, 3,173, 3,858, 4,328,
  5,323, 5,328, 6,761, 6,850, 7,005, and 7,516-7,528 say what the
  surrounding report claims, apart from X11's one-line-short range already
  reported. The dotfiles file and fresh 2.1.269 generation are byte-identical
  through line 8,379, so these anchors are valid in both 2.1.269 copies.
- **REFUTED if those numbers are applied to vendored 2.1.267.** The same symbols
  have different anchors in
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts`:
  render overrun at 874; `EngineCreateResult` at 2,092; generic failure at
  2,100-2,102; `tool.call` at 2,106-2,111; trace members at 2,682, 3,355,
  and 5,916; catch budget at 2,704/2,717; `Origin` trace text at 3,808;
  registration/catch at 4,569/4,581; tier trace text at 6,094; and
  `TraceOutcome` at 6,518-6,530. Vendored 2.1.267 has no streaming trace member
  corresponding to 2.1.269 line 6,850. A valid symbol claim is therefore not a
  transferable numeric citation.
- **CONFIRMED — synthesis C1's origin anchors are 2.1.269 anchors.** The host-only
  text at lines 3,841-3,846, the `Origin` definition at 4,324-4,344, and the
  three caller-argument omissions at 1,184, 4,356, and 4,945 all say what the
  synthesis quotes in the dotfiles and fresh installed copies. They are not
  vendored line numbers. Synthesis C4's `:6110` is explicitly and correctly a
  vendored 2.1.267 anchor for `TIERS`.

### Pinned mod-source citations

- **CONFIRMED — every `mods/...:line` range in `astra-verdict.md`.** Each cited
  path exists in the 580-file byte-verified `df52d04a` snapshot, each range is
  in bounds, and each contains the implementation/comment the adjacent claim
  attributes to it. This covers the diff mod's registration, backend probe,
  host/argv/repository/render/state helpers; all sec-default registration and
  policy helpers; and all telemetry registration, validation, opt-out, queue,
  and safety helpers. No Astra mod-source line mismatch was found.
- **REFUTED — only the source sweep's earlier direct-reading locations fail.**
  Its sec-default anchors `:29`, `:41-42`, `:47`, and `:55` are the D3/D4/D5
  errors itemized above. The same claims' later Astra appendix uses correct
  ranges (for example register lines 20 and 34-49). The source sweep embeds the
  Astra verdict verbatim after line 930, so those duplicated citations are one
  citation set, not independent corroboration.

### Issue-body and issue-comment citations

- **CONFIRMED for attribution.** Every explicit `91870-body.md:<line>` and
  `91870-comments.md:<line>` anchor in `astra-verdict.md` and the direct portion
  of `fh-source-sweep.md` was checked against the current, live-identical local
  captures. The cited lines contain the quoted staff statement, community
  runtime report, request, or artifact description assigned to them. No line
  mismatch was found. Absolute capture paths are
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/91870-body.md`
  and
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh/91870-comments.md`.
- **UNVERIFIABLE as current behaviour where labelled REPORT.** A correct line
  citation to a 2.1.260/2.1.261/2.1.263 community comment proves what that person
  reported, not 2.1.269 behaviour. The Astra report generally preserves this
  distinction correctly. Its staff citations prove a documented design answer
  at that date; negative-capability statements still lack the reaching arms
  listed in B3.
- **CONFIRMED — two easy-to-misread issue anchors are used correctly.** Absolute
  line 2,163 in the comments is a request for `hook.error`, not evidence that the
  event exists; the sweep explicitly corrected itself. Absolute body line 7
  contains both the “Claude Mods” name and weeks-scale commitment; body line
  167 is the onion image. Those direct sweep citations are accurate.

## Remaining artifact claims and evidence-loss notes

- **CONFIRMED — the binary-string warning in the provenance README is correct.**
  Running the README's first command shape against the installed 2.1.269 binary
  at `/Users/rmanaloto/.local/share/claude/versions/2.1.269` found exactly the
  four meaningful literals it names: `classic.PreToolUse`,
  `classic.SessionEnd`, `classic.SessionStart`, and `classic.Setup` (plus the
  unrelated filename fragment `classic.ts`). The negative control
  `classic.DefinitelyNotAnEvent` returned zero. The second command shape found
  the complete 33-name array beginning `"PreToolUse","PostToolUse"`; it includes
  `PostToolUse`, `InstructionsLoaded`, and `SubagentStart`. That set is exactly
  the 33 alternatives in fresh 2.1.269 `HookInput` at
  `/private/tmp/kb-audit-b-plugin-types.oNQcZY/.claude/types/claude-code.d.ts:3186`.
  Thus the direct-literal zero would indeed be a false negative for registration
  capability, as
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.README.md:130`
  warns.
- **REFUTED — “no content hash ... can ever be a gate” is repeated in the
  implementation rationale, not only the README.** The same categorical claim
  appears at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:58`.
  The two isolated-HOME generations in this audit produced the same 9,156-line
  core file and the same SHA-256, so a version-pinned, environment-pinned hash
  gate is constructible. The narrower engineering decision in that module — use
  stable required tokens for the ordinary host-dependent generation — remains
  sound; the refutation is of the word **ever**, not of the implemented token
  check.
- **UNVERIFIABLE in this lane — the implementation rationale's claim that all
  11 derived tokens were identical across both generation environments.** It is
  stated at
  `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:73`,
  but I did not execute the focused checker or its tests because this lane's
  one-file-write constraint excludes commands that may create caches or other
  workspace state. The directly measured discriminators in this audit agree,
  but that is not a complete remeasurement of the derived 11-token set.
- **Evidence-retention note.** My first broad `rg -C` extraction over all four
  large artifacts was output-truncated by the execution wrapper at 12,394
  original tokens / 260 displayed lines. I did not use the missing tail as
  evidence; subsequent bounded reads targeted the reported locations. The first
  direct `gh issue view` response was likewise display-truncated, so live issue
  completeness is based instead on the paginated REST ID/body comparison and
  equal canonical hash reported above.

## Bottom line

The reports contain substantial correct primary-source work, but they are not a
safe current contract without the corrections above. The most consequential
newly caught errors are: versionless declaration line citations; the optional
`Register` parameter claim; the current event/token counts; the categorical
content-hash impossibility; stale treatment of `agent.offer`, `ui.ask`, and
`plugin.register`; omission of documented option defaults, validation, secret
storage, and reload semantics; and broad capability negatives contradicted by
both the declarations and public reaching examples. `deny: string` remains an
explicit refusal result in both declaration versions, and every downstream
statement that assumed it could not stop a call must be discarded or narrowed
to the case where the hook has already invoked `next`.

What remains unverified is behavioural rather than syntactic: current 2.1.269
firing/ordering for the declared events, malformed-result handling, timeout and
worker-failure policy, empty-deny behaviour, origin-forgery resistance under an
adversarial live module, all agent route/terminal coverage, and whether the
public third-party modules actually load and behave as their source intends. I
ran no repository-writing gate, no hook-dispatch probe, and no third-party
module execution. This report is the only file I wrote.

## GitHub repos touched

- `ray-manaloto/knowledge-base` — audited the vendored declarations, provenance
  README, function-hook reports, issue captures, runtime-check rationale, and
  pinned Anthropic mod snapshot.
- `ray-manaloto/dotfiles` — read the tracked 2.1.269 declaration mirror for the
  version/copy-specific line-citation comparison.
- `anthropics/claude-code` — read live issues 91870 and 92440, the 2.1.269 mod
  tree, and immutable source blobs used by the report citations.
- `TheSmokeDev/taskchad-os` — read the immutable persona-cognition function-hook
  registration that bridges events to Python.
- `bsamiee/Rasm` — read the immutable typed function-hook module using options,
  trace, deny, classic events, process, filesystem, and agent capabilities.
- `pleaseai/honmoon` — read the immutable typed tool-call policy and redaction
  implementation.
- `djnsty23/claude-auto-dev` — read the immutable JSDoc-typed JavaScript hook
  implementation.
- `cam-douglas/hermes-playground` — inspected the matching source and determined
  it is an evidence viewer rather than a registerable hook module.
- `noopz/commonplace` — read the exact-token hooks manifest/source used as a
  code-search control and real-world occurrence.
- `AnExiledDev/cc-changelog-plugin` — read the immutable Git tree, hook manifest,
  module, and README after code search returned an invalid incomplete zero.
