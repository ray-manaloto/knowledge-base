# FH SYNTHESIS — reconciling two sweeps against the tracked 2026-09-10 prior work

Synthesist: `kb-codex-astra-advisor`. Date **2026-09-12**. Repo HEAD `4cdd8bfb`,
branch `feat/754-plugin-types-contract`.

I ran none of the research. I read all seven lane reports plus the two tracked
2026-09-10 reports, and re-derived every load-bearing citation I report as
settled. **RE-DERIVED** = I ran the probe myself this session. **RELAYED** = I am
carrying a lane's word and have not checked it.

**The single most valuable thing in this document:** the brief's headline
UNVERIFIED — *does the shipped engine pin `next.origin` or trust the caller* — is
**SETTLED, RE-DERIVED, and the answer is "pinned"**. Admin seating is
enforcement, not decoration. See C1.

---

# 1. CONTRADICTIONS

Ordered by how much the disagreement changes a decision.

## C1. 🔴 `next.origin` is HOST-SET. The lane that called this the deciding risk was carrying a claim the tracked prior report had already retired.

**The claim.** `fh-source-sweep.md` D4 (and its "WHAT I COULD NOT VERIFY" #5):

> *"`Monte9/claude-function-hooks` issue #2 is titled ‘The §6.4 guard covers one
> synchronous tick, and **`next.origin` is caller-supplied**'. If `next.origin`
> is caller-supplied in the shipped engine, the built-in security mod's
> authority check is spoofable. **UNVERIFIED** … That single question decides
> whether admin seating is enforcement or decoration."*

**RE-DERIVED — it is not caller-supplied.** From the generated declarations for
2.1.269, `claude-code.d.ts:3841-3846`, verbatim:

```
 * Set by the host alone, from the environment the call came from (its own
 * MessagePort) and that plugin's seat; nothing a plugin writes reaches it.
 * Every hook of one dispatch sees the same origin, and `next.to` keeps it.
```

and the type's own comment, `:4324-4330`:

```
 * Set by the host from where the call came from and where that plugin was
 * seated; nothing a plugin writes.
```

`Origin` is `{ readonly plugin: string; readonly tier: Tier }` (`:4332-4344`).
Origin is keyed on the **MessagePort** — the transport identity of the realm the
call arrived from — which a plugin cannot forge from inside its own realm. Two
corroborating structural facts in the same file: `origin` is stripped from every
caller-facing argument type (`CommandRunArgs = Omit<CommandRunInput, 'origin' |
'args'>` at `:1184`; `PaneCloseArgs = Omit<PaneCloseInput, 'origin'>` at `:4356`;
`PromptFillArgs = Omit<PromptFillInput, 'origin'>` at `:4945`), each with a
comment saying *"`origin` is the engine's to set"*. **The caller has no argument
slot to put it in.**

**So `sec-default`'s `next.origin.tier === 'user'` check is real enforcement.**

**And the disagreement is older than this round.** The tracked
`2026-09-10-github-function-hooks-examples.md:316-322` already published a
correction covering this exact issue tracker:

> *"**All three `Monte9` issues are therefore about a reference implementation,
> not the platform.** Downgrade them from 'critique of the semantics' to
> 'critique of one reimplementation, with transferable failure modes.'"*

That correction was written about Monte9 #3. It applies to #2 identically — #2
is a statement about Monte9's own `src/`, not about Anthropic's engine. The
sweep imported #2 as a live risk against the shipped engine **because it never
read the tracked report**. Evidence favours the tracked report, decisively.

**Residual, and it is not nothing:** the declarations describe the *contract*. I
did not run an adversarial probe attempting to forge an origin at runtime. What
is settled is that the API gives a plugin no slot to write one and the engine
documents itself as the sole writer.

## C2. 🟡 `deny` — one lane's HEADLINE is wrong, its own BODY is right, and the d.ts agrees with the body.

Three artifacts, apparently three positions:

| artifact | what it says |
|---|---|
| `fh-source-sweep.md` X2 heading | *"`deny` does NOT stop the tool running"* |
| `fh-source-sweep.md` X2 body (quoting poteat verbatim) | *"To make the tool not get called, **don't call `next(e)`**… `const approved = result.deny === undefined`"* |
| `claude-code.d.ts:7110-7115` (**RE-DERIVED**) | `deny: string;` — *"Refuses the call: the model receives the text as an error result. Absent when the call was answered."* |

**They reconcile exactly, and the reconciliation is the fact worth carrying:**

- **`next(e)` decides whether the tool RUNS.**
- **`deny` decides what the model is TOLD.**

Return `{deny}` *without* calling `next` and both are true: nothing ran and the
model is told it was refused. `await next(e)` *then* return `{deny}` and the tool
ran while the model is told it did not — `gbrussich52`'s reproduction on 2.1.263
(`astra-verdict.md` D2.1, `91870-comments.md:2429-2431`, RELAYED). The sweep's
heading compresses a conditional into an absolute; the d.ts sentence describes
the ordinary case. Neither is evidence against the other.

**The surviving, genuinely load-bearing half is `{deny: ""}`**, and the two
lanes together state it better than either alone:

- sweep X2: presence, not truthiness — `result.deny === undefined` — so `{deny:
  ""}` **denies**, and a `if (r.deny)` truthy check is a real bug. **RE-DERIVED
  as type-consistent**: `deny: string` admits `""`.
- astra-verdict D2.4 adds the condition the sweep dropped: **this CHANGED**.
  `{deny:""}` allowed execution on 2.1.260, blocked on 2.1.261 (RELAYED,
  `91870-comments.md:1665-1677`). A fact with no version attached is the failure
  mode `verify-before-advancing.md` § *carry a fact's condition* names.

## C3. 🔴 The two `claude-code.d.ts` copies are NOT "same version, two machines". Same machine, same version — the generator's output depends on the SESSION.

The brief records the disagreement as *"a lane called dotfiles' `claude-code.d.ts`
'the richest source' at 9,192 lines. A freshly generated one on this machine is
9,263. Same version, two machines."*

**RE-DERIVED, and the mechanism is now known.** Four declaration artifacts exist
on this machine right now:

| copy | lines | bytes | header |
|---|---|---|---|
| `dotfiles/.claude/types/claude-code.d.ts` (tracked) | 9,192 | 347,960 | `// Written by Claude Code 2.1.269.` |
| this session's scratchpad | **9,263** | 350,185 | `// Written by Claude Code 2.1.269.` |
| two knowledge-base scratchpads + one dotfiles scratchpad | 7,966 | 302,096 | `// Written by Claude Code 2.1.267.` |

`diff` between the two **2.1.269** copies: **71 lines added, 0 removed** — a
strict superset. And every added line is an **MCP tool schema**:
`ListMcpResourcesTool`, `ReadMcpResourceTool`, `ReadMcpResourceDirTool`,
`RemoteTrigger`, plus their result types.

**So `/plugin-types` emits the schemas of the MCP servers connected to the
session that generated it.** Not two machines — two MCP configurations. This is
the repo's own recorded memory `generated-declarations-are-environment-dependent`
reproducing on a new artifact.

**Three consequences, and the third is a working rule:**

1. *"9,192 lines"* and *"9,263 lines"* are both correct and neither is a property
   of Claude Code 2.1.269. **Never quote a line count of this file.**
2. Any `claude-code.d.ts:<N>` citation **above line 8379 does not transfer**
   between copies. **RE-DERIVED**: `diff` of lines 2411-2424 between the two
   2.1.269 copies is **IDENTICAL**, and the first insertion is at 8380. So every
   citation the sweep makes below ~8379 (`:2413`, `:2419`, `:3138`, `:5323`,
   `:5328`, `:7528`) **does** transfer; `:7528` is comfortably inside the safe
   region.
3. This is exactly why `ray-amjad/awesome-claude-code-function-hooks` warns
   *"The type declarations are not in git… a checked-in copy goes stale and lies
   to you"* (`2026-09-10-github-function-hooks-examples.md:227`). It is worse
   than staleness: **two copies from the same binary on the same day disagree.**

## C4. ✅ The leaked mirror is byte-identical to local regeneration — the 2026-09-10 report's own named missing control arm is now ARMED, and it PASSES.

`2026-09-10-github-function-hooks-examples.md:407` lists as unverified:

> *"`claude-code.d.ts` is quoted from an unofficial mirror… It self-identifies as
> `// Written by Claude Code 2.1.267.` and is reproducible locally via
> `/plugin-types`, but **I did not run `/plugin-types` to confirm. That is the
> one control arm this finding is missing**, and it is cheap for whoever acts on
> this."*

**RE-DERIVED.** That report recorded the mirror's blob sha as
`36aec298dd76c950b774045707427e26c46bd799`, 302,096 bytes, 7,966 lines
(`:69`). `git hash-object` on a locally-generated 2.1.267 copy:

```
36aec298dd76c950b774045707427e26c46bd799
```

**Exact match.** `asgeirtj/system_prompts_leaks` is verbatim `/plugin-types`
output, not a transcription. Every claim that report drew from it — the five
`TIERS`, `TargetTier`, `ClassicEventName`, the 66-name catalog — inherits that
provenance. Spot-checked one: `:6110` in the local 2.1.267 copy is exactly
`const TIERS: readonly ["prepend", "user", "append", "builtin", "core"];`.

## C5. ⚪ `tool.check` is not "contested" — it is SEQUENTIAL. It shipped between 2.1.267 and 2.1.269.

`fh-source-sweep.md` "WHAT I COULD NOT VERIFY" #6 calls this contested:
10 occurrences at 2.1.269 vs `sirmaelstrom` reporting it absent from 2.1.267
declarations, *"Two versions apart, so both may be true; I did not reconcile
them."* And `astra-verdict.md` D11 downgrades the sweep's S9 on that basis.

**RE-DERIVED, both copies on disk, one command, with controls:**

| token | 2.1.267 | 2.1.269 |
|---|---:|---:|
| `tool.check` | **0** | **10** |
| `tool.call` (positive control) | 46 | 61 |
| `ZZQQXX_NOT_REAL` (negative control) | 0 | 0 |
| `hook.error` | 0 | 0 |
| `next.trace` | 4 | 4 |
| `TraceOutcome` | 2 | 2 |

Both are right and nothing is contested. `tool.check` **landed in (2.1.267,
2.1.269]**. `astra-verdict`'s "my S9 is weaker than I stated" downgrade is now
unnecessary at the current pin. `next.trace` was already present at 2.1.267, so
the sweep's X7 *"they landed"* is right about `.catch` but overstates novelty for
`next.trace`. `hook.error` 0/0 confirms the sweep's own self-correction.

## C6. 🔴 The repositories index: one lane got 1 hit and generalised; the other got 16. The query shape, not the index, is what differed.

**Un-flagged by either lane, and they ran the same day.**

| lane | query | repos-index total | conclusion drawn |
|---|---|---:|---|
| `fh-source-sweep.md` Phase 2 | `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` | **1** | *"Repositories-index result is near-useless (1 hit)… a repositories-only or code-only sweep would have missed almost everything"* |
| `extract-research-a-live.md` F11/F12 | `claude code function hooks` | **16** | lists 7 dedicated reference implementations as corpus candidates |
| `2026-09-10-…-examples.md:133` | `claude function hooks` → 20; `function-hooks claude in:name,description` → 5 | 20 / 5 | *"Four of those five never appeared in the code index at all"* |

**Evidence favours a-live and the 2026-09-10 report.** A repositories index
matches **name and description**, and no repo names itself after an env var, so
searching it with a code literal is the wrong instrument —
`change-the-route.md` rule 1, arriving as a measurement. The sweep's number is
correct for its query; its *generalisation about the index* is not supported by
it, and it points the opposite direction from the round's other two measurements.

Net: **the repositories index is valuable and needs natural-language terms.**
Neither lane's headline should be carried alone.

## C7. ⚪ `ingest.py` — the 12,000-character slice is `:160`, and the wrong citation survives in a second file the lead did not correct.

`extract-research-lead.md:137-139` corrects B2: *"B2 cited `:144`, which is the
`_html_to_markdown` call site; the slice itself is `:160`."*

**RE-DERIVED** — `:144` is `markdown = _html_to_markdown(html, url)` and `:160`
is `{markdown[:12000]}`. The lead is right.

**But the lead corrected B2 and not its own Track A report.**
`extract-research-a-live.md:428` still reads *"keep the first 12,000 characters
(`ingest.py:144`)"*. Two files on disk now disagree about the same line. Trivial
in consequence, and it is the shape this repo keeps paying for
(`the-fix-is-where-the-defect-lives`): the correction landed in the delegated
lane's report and not in the corrector's own.

## C8. ⚪ Two non-contradictions worth naming so nobody re-litigates them.

- **B2 vs the lead on the fetch cap.** B2 wrote the failure as *"wrong output for
  smaller binaries, **bounded download failure** for oversized ones"* and said a
  40 MB response would raise. The lead/a-live measured every asset under the cap,
  so only the silent arm is live. **Both are right**; B2 read the source
  correctly without the sizes, which it did not have. **RE-DERIVED**:
  `security.py:22` is `_MAX_TEXT_BYTES  = 10_485_760`, and the largest measured
  asset is 9,789,851 B — under it by 695,909 B.
- **"A broken hook is SKIPPED" — astra says *too broad*, the sweep says
  *confirmed and incomplete*.** These are about different layers and both hold.
  The d.ts sentence (`:2413-2415`, **RE-DERIVED verbatim**) governs a failed
  **invocation**. `astra-verdict.md` D1's module-unload-with-**retained
  withholding** case (`91870-comments.md:2688-2715`, 2.1.263, RELAYED) is a
  **load**-layer failure the d.ts sentence does not reach. Carry both, labelled.

---

# 2. THE DELTA — what today's sweeps add over 2026-09-10

Ruthlessly: **the mechanism was already known two days ago.** The delta is
concentrated in three places — the shipped `mods/` source, the 161 comments, and
the extraction logistics. Everything about tiers, `next.to`, `classic.*`,
`{deny}`, the flag, the rename and `/plugin-types` is confirmation.

| finding | new / confirms / contradicts | where |
|---|---|---|
| `next.origin` is host-set, MessagePort-keyed, unforgeable | **NEW — and settles the round's top risk** | C1 above, RE-DERIVED from the 2.1.269 declarations |
| `/plugin-types` output varies by **connected MCP servers**, same binary same day | **NEW** | C3 above, RE-DERIVED |
| The leaked `system_prompts_leaks` d.ts is byte-identical to local regeneration | **NEW — closes a named 09-10 gap** | C4 above, RE-DERIVED |
| `tool.check` shipped in (2.1.267, 2.1.269] | **NEW** | C5 above, RE-DERIVED |
| `Register = (on: On, options: PluginOptions) => unknown`; **options are fixed per activation — changing them RELOADS the plugin and re-runs `register`** | **NEW** | RE-DERIVED, `claude-code.d.ts` `export type Register` doc |
| `options` = the manifest's `userConfig`; `register` must be a plain exported function | **NEW** | `astra-verdict.md` D6, `mods/diff/hooks/backend/installed-backend-probes.ts:10-12` (RELAYED) |
| `turn.step` handlers are **async generators** — a second hook shape entirely | **NEW, and it breaks any single-signature contract** | `fh-source-sweep.md` D11; `astra-verdict.md` S2 |
| `next.to` skips are **deferred to the end of your own tier and INTERSECT across the tier — lowest wins** | **NEW, and it contradicts a naive reading of the 09-10 report** | `fh-source-sweep.md` X1 (poteat verbatim); `astra-verdict.md` D7 |
| `prependPlugins` **REPLACES** the whole prepend list — an admin adding their own array silently drops `sec-default` unless they name `sec-default@builtin` | **NEW** | `astra-verdict.md` D7; `mods/sec-default/README.md:45-55` |
| Withholding a `$` noun does **not** constrain the model's own `Write`/Bash/MCP | **NEW, and it caps what a `$`-based guard can promise** | `astra-verdict.md` D3 (`91870-comments.md:1523`, REPORT) |
| `TraceOutcome` is a 7-member union; `skipped` **conflates a failure with a `next.to` skip from above** — only `reason` separates them | **NEW** | `fh-source-sweep.md` X9, `claude-code.d.ts:7528` |
| `engine.create` has **no budget**, and its failure is **the load's** | **NEW** | `fh-source-sweep.md` X10 + RE-DERIVED from the `Register`/`.catch` doc |
| `{ result }` — answering a tool call yourself — is a return shape | **NEW** | `claude-code.d.ts:2419-2424`, RE-DERIVED |
| *"The managed-settings hooks run first: their deny is the call's result"* | **NEW — the admin override stated as a guarantee** | `claude-code.d.ts:2424`, RE-DERIVED verbatim |
| `.catch` is declared; without it *"a failed hook is absent"*; a second `.catch` throws | **NEW** | RE-DERIVED, `Register` doc + `:5328` |
| `next.trace` lets a plugin read every event snapshot **below** it, defeating an inner redactor | **NEW, highest security value** | `fh-source-sweep.md` D14; `astra-verdict.md` D9 |
| Issue is at **161 comments** (was 154 on 09-09); code index **106** (was 65) | confirms + movement | lead §4.6; a-live F11 |
| 22 assets / 50.7 MB, not "9 videos + a PDF" | **NEW** (the 09-10 reports never inventoried assets) | a-live F3; sweep Phase 1a — **two independent routes agreeing**: Content-Type fetch vs markdown structure |
| `_detect_url_type` classifies every `github.com` URL as `"github"` before the `.pdf` branch | **NEW** | RE-DERIVED, `ingest.py:65-84` |
| `gh api <absolute URL>` downloads attachment bytes, byte-identical to curl | **NEW** | a-live F13 + a1 (`pkg/cmd/api/http.go:16-27`) |
| Three distinct silent comment truncations (30 / 100 / minimized-omitted), all rc 0 | **NEW** | a-live F1+F15; a1 Q3 — source reading and live probe agreeing |
| graphify has **no** URL/media handler seam; `resolver_registry.register()` is the positive control proving the search could find one | **NEW** | B1 + B2 independently, same control arm |
| `graphify install` **REPLACES** this repo's `## graphify` section | confirms `do-not.md` #1 from graphify's own source | B1 Q4; lead §6 |
| Five tiers; `TargetTier = Exclude<Tier,'prepend'\|'user'>`; `classic.PreToolUse` is the real event name | **confirms 2026-09-10** (which established all three) | sweep X1/X4 rediscovered them independently |
| `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`, "Claude Mods", shipping-in-weeks, `mods/` tree, `#92469`, `#92533`, lcm migration, phate45 version archaeology | **confirms 2026-09-10 — re-derived at cost** | both 09-10 reports |

## 🔴 The meta-finding: the loss is THREE-LAYERED, and each layer was measured this round

1. **Not in the graph.** `fh-source-sweep` Phase 0, control-armed: zero
   function-hooks material in 11,330 prose nodes. True.
2. **Not read from this repo.** Two **tracked** reports at
   `docs/research/reports/2026-09-10-*` already held the flag, the rename,
   `next.to`, `next.origin`, `plugin-types`, five tiers, `#92469`, `#92533` and
   the version archaeology. Neither sweep read them. The lead discovered them
   only at §4.6, after the work.
3. **Not read from the machine.** Nine function-hooks reports and a 9,192-line
   `claude-code.d.ts` sat in the sibling dotfiles checkout the whole time
   (`fh-source-sweep` Phase 2a).

And the tool built to prevent exactly this **returned a false negative**:
`kb-recall-work -- "function hooks issue 91870 extraction attachments"` reported
`tracked_files examined 3427 matched 0` while `git grep -ln 91870` returns 3
tracked files. The lead armed it both directions (`extract-research-lead.md:200-219`,
RELAYED): the `git grep`-backed probes **AND** the stems, so *adding words to be
more specific silently converts 410 matches into a clean-looking zero*. The
task's documented promise is that it *"REFUSES rather than returning an empty
list"* — it did not return empty, it returned **wrong**, which no refusal can
catch. **This is worth a ticket, and it is the highest-leverage fix in the
document**: every future round's phase 0 rests on it.

---

# 3. WHAT NOBODY ESTABLISHED

Deduplicated across all seven reports plus the two tracked ones, ranked by
whether it blocks a decision.

## Blocks a decision

| # | open question | why it blocks | who flagged it |
|---|---|---|---|
| U1 | **Can a `prepend` hook calling `next.to(e,"core")` skip an `append`-seated redactor — and is there any unskippable floor?** | This is the enforcement question `next.origin` does *not* answer. C1 proves the *identity* is trustworthy; this asks whether a trusted identity can be **routed around**. `Spencer-Morley` asked for separate placement/skip authority and **got no answer in the thread**. Combined with X1 (skips INTERSECT across a tier, lowest wins), one prepend peer can remove `append` for everyone. | astra D9 (`:2636-2642`, `:2717-2719`); sweep X1 |
| U2 | **Does `#92533` still reproduce at 2.1.269?** Registering *any* `tool.call` hook on Bash — *"even a pure passthrough `next(e)`"* — breaks Bash in `Agent(isolation:"worktree")` subagents. | This repo's entire guard stack is a `PreToolUse` matcher on `Bash\|Grep`, and this repo runs worktree-isolated subagents routinely. The obvious migration lands exactly here, and **it would look like the guards broke, not like a platform bug**. | 2026-09-10 examples report `:160-166`; a-live F12 lists it still open |
| U3 | **Can a function hook call this repo's Python guards at all?** A hooks module has *"no DOM, no Node"* and lcm had to keep a daemon and POST to it. `kb_setup`'s guards are Python via `uv run`. | Decides whether migration is even shaped like a port, or is a rewrite plus a daemon. Not a new risk — a *measured* one, from a project that hit it. | 2026-09-10 examples `:337`; `claude-code.d.ts:13-15` |
| U4 | **Does the project `.claude/settings.json` `env` block actually enable the flag, and when is it read relative to project-settings parsing?** | `do-not.md` #11 forbids `~/.claude`, which is the path every third party documents. If the project block does not work, this repo has **no sanctioned always-on route** and every probe is per-invocation. | flagged UNVERIFIED in **both** 2026-09-10 reports and still open |
| U5 | **Does yt-dlp handle a `user-attachments` mp4?** | The only open question in Track B. Settles route (b) vs (c) for 9 videos. One command. | B2 headline; lead §5 |
| U6 | **What `options`/`PluginOptions` actually contains at runtime, and its secret-handling.** | `register`'s config channel. I settled its *type name* and reload semantics (§2); contents and secret policy remain open. | astra D6 |

## Shapes the work but does not block it

| # | open question | flagged by |
|---|---|---|
| U7 | Whether a **rate limit** reads as a zero in the GitHub search path. Never armed — `code_search` read 10/10 the whole round in every lane. | sweep #8; 2026-09-10 examples `:414`; a1 Q4 |
| U8 | Whether GitHub ever expresses secondary throttling as **HTTP 200 with no GraphQL `errors` and no pagination metadata** — the one shape that makes gh's rc-1 guarantee fail open (`findEndCursor` returns `""`, not an error). | a1 Q3/Q4; lead §5 |
| U9 | Whether `gh issue view --json comments` truncates **above ~161** comments. No ceiling found in source or live. | a-live; a1; lead |
| U10 | **Private-repo** attachment behaviour. All probes were public + unauthenticated; gh deliberately drops auth across a cross-host redirect (`api/http_client.go:151-169`). | a-live; lead |
| U11 | Whether `.catch`, grace budgets and typed failures cover a failed `engine.create` **across all modes**. I settled that its failure is the load's; the recovery contract is not stated. | astra C |
| U12 | **Durable audit evidence** — are records committed before execution? What survives process death, retries, a swallowed exception? Asked directly, unanswered. | astra C |
| U13 | Complete **agent spawn/completion** coverage: background dispatch fired `tool.call` but not `agent.spawn`/`turn.start`/`turn.step`; `agent.list` empty. | astra D12 |
| U14 | `fs.read`/`fs.list` vs `fs.readFile`/`fs.listDir` — rename, or op-name vs method-name split. | 2026-09-10 examples `:158`; astra S7 |
| U15 | graphify's `register()` **API stability across releases** — public at this commit is not a compatibility promise. | B1 |
| U16 | The **architecture PDF** and the **2400×1600 affordance cheat sheet** are unread by anyone. The cheat sheet needs vision; nothing in the pipeline does OCR. | sweep #3/#4 |
| U17 | Whether `poteat` is Anthropic staff. Circumstantially overwhelming, never confirmed via API. Two days old and still open. | 2026-09-10 research `:78` |

**Retired by this synthesis** (do not carry forward as open): `next.origin`
forgeability (C1), `tool.check` shipped status (C5), the leaked-d.ts provenance
arm (C4), `options`' type and refresh lifetime (§2), the 9,192-vs-9,263 mystery
(C3).

---

# 4. WHAT IS NOW CHEAPLY PROBEABLE

`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is publicly sanctioned by the issue author
and present in the installed 2.1.269 binary. Several items above stop being
declaration-reading and become one command. **Proposed only — I ran none of
these; none mutates the repo, but P4/P5 write files and P6 spawns a subagent.**

Cheapest first.

| # | settles | command | cost |
|---|---|---|---|
| P1 | **U5** — the only open Track B question | `mise run kb-transcribe -- <one 4 MB durable video URL>` | one command; ~minutes |
| P2 | **Is the flag even readable from project scope (U4)** — the *negative* half, free | `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude --debug -p /exit` then grep `~/.claude/debug/<session>.txt` for `hooks module … loaded (worker, environment 1); events:` | seconds. **This is the CLI-observable proof line** the 2026-09-10 *research* report said did not exist; the *examples* report found it at `:154-156` and the engine names its own event list at load |
| P3 | **U4 proper** — project-scope enablement | add `"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"` to `.claude/settings.json`'s existing `env` block, then rerun P2 **with the env var unset in the shell**. Control arm: remove the block, rerun, expect no load line | one settings edit, reversible. **Arm both directions or it proves nothing** |
| P4 | **U1 — the enforcement question that matters most** | two throwaway plugin dirs run via `claude --plugin-dir`: a `prepend`-ish hook calling `next.to(e,"core")` and an `append`-ish redactor that records whether it ran. Read `next.trace` or the debug log for `TraceOutcome`; `skipped` + `reason` distinguishes a failure from a skip-from-above | an afternoon. **The only probe here that answers a question nobody has answered anywhere**, including in the 161 comments |
| P5 | **U2 — does `#92533` still bite at 2.1.269** | a plugin whose *only* content is `on('tool.call', ($,e,next) => next(e))` on Bash, then one `Agent(isolation:"worktree")` subagent running one `Bash` call. Control arm: same subagent with the plugin absent | ~30 min. **Run this before designing any guard migration** — it decides whether the migration is possible at all |
| P6 | **U16** — the densest unread artifact in the issue | `curl -L -o raw/fh-cheatsheet.png <asset 2fad9a87…>`, then a host-agent **vision** read | one subagent turn |
| P7 | **U6** — `PluginOptions` at runtime | `$.ui.log(JSON.stringify(options))` inside a throwaway `register`, with a `userConfig` set in the plugin manifest | folds into P4's harness |
| P8 | **U7** — does a rate limit read as a zero | deliberately exhaust `code_search` (10/min) with 11 queries, then run a query with **known** hits and read `total_count`, `incomplete_results` and rc | 2 min, and it arms a probe three reports have now declined to arm |

**Two cautions.** `claude plugin validate` is **syntactic only** — it checks the
spelling of `$`, not the existence of the noun (`fh-source-sweep` S10, RELAYED),
so a green validate is not evidence a mod resolves. And `mods/README.md` states
the API *"may change between releases without notice"*: pin a version condition
to every result P1–P8 produces.

---

# 5. THE INGESTION ORDER — both sweeps' plans, reconciled, in cost order

Established and agreed by both sweeps: **22 assets / 50.7 MB · 21 of 22 URLs
carry no extension · all 22 sit under graphify's 10 MiB text cap so ingestion
fails SILENTLY · `gh api <durable URL>` downloads the bytes · no fork patch.**

**RE-DERIVED**: `_MAX_TEXT_BYTES = 10_485_760` (`security.py:22`); largest asset
9,789,851 B; `_detect_url_type` puts `github.com` third, so `.pdf` at `:78` is
unreachable for every asset (`ingest.py:65-84`); the 12,000-char truncation is
`ingest.py:160`; `VIDEO_EXTENSIONS` accepts `.mp4` directly (`transcribe.py:11`);
current pin is `ref = v2.1.258` / `aef74afe…`.

## Stage 0 — the two probes that could change the plan (run FIRST)

| | action | if it fails |
|---|---|---|
| 0a | `mise run kb-transcribe -- raw/fh-v1.mp4` on **one** 4 MB video (fetch it by hand first) | the whole of stage 2 changes shape |
| 0b | P2 above — confirm the flag produces a load line | stages 1-4 are unaffected; only the probe work is |

## Stage 1 — free, deterministic, no LLM (do all of it)

| # | source | command | why it is first |
|---|---|---|---|
| 1a | **`sources/claude-code.manifest` resync** `v2.1.258 → v2.1.269` / `df52d04a4e65195c1621fe6222e0564bcccb1804`, then `mise run kb-build` | edit + build | **Gains `mods/` — 580 blobs of SHIPPED source, the only authoritative API artifact that exists.** Control-armed by the sweep: `mods/` is **404** at the current pin and present at the new one, so the probe discriminates both ways |
| 1b | `davila7/claude-code-templates` | `mise run kb-manifest-add` | **Covers BOTH of Ray's aitmpl URLs at once** — the site IS this repo (`sameAs` in its own JSON-LD). Scraping the SPA is the wrong route |
| 1c | `Monte9/claude-function-hooks` | `mise run kb-manifest-add` | the reference implementation. **Ingest it with the condition attached** (C1): its issues critique *itself*, not the platform |
| 1d | `amitray007/claude-code-schema`, `phate45/claude-patching` | `mise run kb-manifest-add` | per-release machine-readable env/settings schema + binary env-var diffs. These are what answer "what changed between 2.1.258 and 2.1.269" without a binary scan |
| 1e | `ray-amjad/awesome-claude-code-function-hooks` | `mise run kb-manifest-add` | MIT, complete, tested, and `secret-redactor` is **`kb_setup.secret_guard`'s job at the function-hook layer** — the closest analogue to something this repo already owns |
| 1f | `AdityaRon/claude-code-harness`, `cvuijst/cc-function-hooks-poc`, `lossless-claude/lcm` | `mise run kb-manifest-add` | lcm is the **completed** classic→function-hooks migration, and the source of U3 |

**🔴 1g — and it outranks every external repo above.** The nine dotfiles reports
and its `claude-code.d.ts` are the richest function-hooks material on this
machine and none of it is in the graph. Route them in as media/extractions.
**Do not commit a `claude-code.d.ts` copy** — C3 proves two copies from one
binary on one day disagree; commit the *regeneration command* and a version
condition instead.

## Stage 2 — whisper time, no LLM, no key

| | action |
|---|---|
| 2a | The **YouTube** video is the ONE case where Ray's directive works verbatim: `mise run kb-add -- 'https://www.youtube.com/watch?v=B-YQANvDOq0'` → `kb-transcribe`. It matches `ingest.py:74` and reaches `download_audio` |
| 2b | The **9 issue videos** need a hand fetch — `curl -L -o raw/fh-<n>-<slug>.mp4 <durable URL>` (or `gh api <durable URL>`, byte-identical and returns a real rc) — then `mise run kb-transcribe`. Run **one** first (stage 0a) |
| 2c | Transcripts → `sources/media/` (committed). The host serves 5-minute signed URLs, so these are **non-refetchable by definition** |

## Stage 3 — Claude tokens

| | action |
|---|---|
| 3a | The **architecture PDF** — fetch by hand, host-agent extract → `sources/extractions/` → `kb-merge`. `kb-add` would markdownify it (`_detect_url_type`) |
| 3b | The **2400×1600 affordance cheat sheet** — a **vision** read. Nothing in this pipeline does OCR, and it is the densest single artifact in the issue |
| 3c | The **issue itself**: `gh issue view --json body,comments` (the only route returning all 161 without flag gymnastics) + `gh api .../timeline --paginate` for the 23 cross-references and the 1 deleted comment. **Require rc 0 and discard stdout entirely on non-zero** — gh streams each page before requesting the next |

## Stage 4 — close the loop (`kb-curator` MANDATE)

`mise run kb-label` → `kb-remember` → `kb-reflect`.

## Two conditions that must travel WITH the corpus

1. **aitmpl's ten components are PROVISIONAL.** The page says so itself: *"Every
   API name in these components is provisional and comes from the proposal's
   architecture doc and demo videos."* They are *community interpretation*, not
   *the API*. Ingesting them unconditioned seeds the graph with names that may
   already disagree with `mods/`.
2. **Every comment-sourced fact needs its date and version.** The thread spans
   2.1.260→2.1.269 and the API changed inside it: `fs.readFile`→`fs.read`,
   `next.origin` string→object, bare `PreToolUse`→`classic.PreToolUse`,
   `{deny:""}` allowed→blocked, `tool.check` absent→present. A fact from this
   thread without a version is not a fact.

---

# What I could not verify

- **I ran no ingestion, no transcription and no function-hook probe.** Every
  command in §4 and §5 is proposed.
- **The declarations describe a contract, not observed runtime.** C1 settles that
  a plugin has no slot to write `origin` and the engine documents itself as sole
  writer; **I did not attempt to forge one**.
- **I did not open the architecture PDF or the cheat-sheet image** — neither did
  any lane.
- **Everything sourced from the 161 comments is RELAYED.** I read the
  astra-verdict's citations, not `91870-comments.md` itself; its anchors are line
  numbers into a file I did not open.
- **I did not re-verify the `cli/cli` Go citations** (a1's `view.go:152`,
  `pagination.go:39-47`, `errors.go:35`). a-live armed the `issue list` cap
  prediction live and it held exactly, which is the strongest corroboration
  available, and it is not the same as reading the source.
- **I did not re-run any GitHub search.** The 106/38/16/1 and 161 figures are
  RELAYED; the disagreement in C6 is between two relayed numbers whose *queries*
  I compared, not whose results I reproduced.
- **`kb-recall-work`'s AND-ing defect is RELAYED** from the lead's two-row table.
  I did not run either query.
- **Line citations into `claude-code.d.ts` are copy-specific above ~8379** (C3).
  Mine are from this session's scratchpad copy at 9,263 lines; I verified the
  region below 8379 is identical between the two 2.1.269 copies, and did not
  check the 2.1.267 copy's line numbering against either.
- **The graph was not queried by me.** `fh-source-sweep` Phase 0 ran it,
  control-armed; I am relaying that zero. The PreToolUse graph-first guard fired
  on my searches as expected and I stayed inside named-file reads.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — the subject: issue 91870, its 161 comments and 22 attachments, the `mods/` tree at v2.1.269, and issues #92440, #92469, #92533, #92675, #93215, #93426, #93831. Read only as relayed by the lanes; I opened none of it directly.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo: the seven lane reports, the two tracked 2026-09-10 research reports, `sources/graphify/graphify/{ingest,security,transcribe}.py` and `sources/claude-code.manifest`, all read directly and re-derived.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — `.claude/types/claude-code.d.ts` (9,192 lines, tracked) read directly and diffed; the nine 2026-09-11/12 function-hooks reports located but **not read**.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork; the `_detect_url_type` ordering, the 10 MiB text cap and `VIDEO_EXTENSIONS` re-derived from the pinned clone.
- [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) — the mirrored `claude-code.d.ts`; **its blob sha re-derived as byte-identical to local `/plugin-types` output**. Not fetched this session.
- [cli/cli](https://github.com/cli/cli) — `gh` at the v2.98.0 pin; relayed from lane A1, not re-read.
- [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) — its issue #2 is the source of the `next.origin` claim refuted in C1; a critique of itself, not of the platform.
- [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) — IS aitmpl.com; the blog post and all ten provisional components.
- [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) — MIT marketplace; `secret-redactor` is this repo's `secret_guard` at the hook layer.
- [lossless-claude/lcm](https://github.com/lossless-claude/lcm) — the completed classic→function-hooks migration; source of the no-Node/no-SQLite constraint (U3).
- [phate45/claude-patching](https://github.com/phate45/claude-patching) · [amitray007/claude-code-schema](https://github.com/amitray007/claude-code-schema) — per-version env-var scans and per-release config schema.
- [AdityaRon/claude-code-harness](https://github.com/AdityaRon/claude-code-harness) · [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc) · [scriptease/claude-code-redact-plugin](https://github.com/scriptease/claude-code-redact-plugin) · [noopz/commonplace](https://github.com/noopz/commonplace) · [mahuebel/segmem](https://github.com/mahuebel/segmem) · [pleaseai/honmoon](https://github.com/pleaseai/honmoon) · [yonatangross/orchestkit](https://github.com/yonatangross/orchestkit) · [cam-douglas/hermes-playground](https://github.com/cam-douglas/hermes-playground) — ingestion candidates named by the lanes; none read by me.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream of our fork; named, not read.

**Registry action (`research-repo-enumeration.md`):** none of the function-hook
repos above has a `sources/*.manifest` or a `sources/REGISTRY.md` row today.
§5 stage 1 is the proposal; **I appended nothing** — this is a flagged,
unperformed action.

**STATUS: COMPLETE.**
