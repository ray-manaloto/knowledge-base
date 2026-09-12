# Advisor verdict — the `.claude/settings.json` lane guard (function-hook design)

Lane: `kb-codex-advisor`. Reasoning runs in `codex exec` on `gpt-5.6-sol` at
`xhigh`. This section is the ADVISOR'S OWN MEASUREMENT, taken before the consult
and handed to codex as the prompt's evidence base. The codex verdict is appended
below under "## Codex verdict

The `codex exec` call SUCCEEDED (rc 0, 13,939 bytes, `gpt-5.6-sol` at `xhigh`).
What follows is its output VERBATIM. My own arming of its citations is in the
section AFTER it — read both; two of its claims needed correction.

---

VERDICT — DO NOT SHIP this as an enforcement guard until normal marketplace delivery and full-chain behavior are proven by a mandatory external headless arm; tracked settings and static validation alone can be green while the guard is absent.

## THE RISK THAT DECIDES IT

A syntactically valid module can be declared, enabled, cached, and tested yet never observe the protected call: the plugin may be uninstalled, disabled by a latch, shadowed, rejected by the static validator, skipped after failure, or short-circuited by an outer hook.

I agree that “seated outermost” concerns chain authority. I reject “not seated means innermost”: the evidence establishes that this personal installation cannot obtain the managed `prepend` seat, not its exact ordering among user-tier plugins. That is already sufficient: an earlier matching hook can return without `next`, preventing this guard from running.

## 1. DELIVERY

**No: tracked configuration alone cannot load a previously uninstalled external plugin.** It can register its marketplace and enable it, but installation remains per-user.

Settled:

- A trusted project’s `extraKnownMarketplaces` automatically registers a GitHub marketplace without another marketplace prompt.
- Since 2.1.195, a project-enabled external plugin does not load until each user installs it. `enabledPlugins` is enablement, not installation. This is explicit in [discover-plugins.md](/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/claude-code-docs/content/en/docs/claude-code/discover-plugins.md:484) and [settings-reference.md](/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/claude-code-docs/content/en/docs/claude-code/settings-reference.md:4248).
- An untrusted folder’s project marketplace entry is ignored without a message, including by `claude -p`.
- The relative-path prohibition applies to an inline `source: "settings"` marketplace, which has no repository base. It does not prohibit relative plugin paths in a Git-based marketplace: Claude clones that repository, so `./plugins/guard` resolves normally.
- `file` and `directory` marketplace sources exist, but are machine-local/development delivery, not portable tracked delivery.

Therefore §F’s inference is partly right:

- Right: every machine needs one explicit plugin installation.
- Wrong: project configuration merely “offers” a GitHub marketplace pending separate marketplace trust. After workspace trust, Claude adds that marketplace automatically.
- S:192917 is not in conflict with the GitHub case. It addresses a marketplace whose recorded filesystem location is a network path; it does not repeal the documented project-scoped `github`/`git` source types.

Best delivery: publish `kb-settings-lane-guard` through the already-declared `ray-manaloto` Git marketplace, add it to `enabledPlugins`, and require once per machine:

```text
claude plugin install kb-settings-lane-guard@ray-manaloto
mise run kb-function-hook-arm
```

If same-repository source is mandatory, the knowledge-base repository can itself carry `.claude-plugin/marketplace.json` with a relative plugin directory. It will still be fetched and loaded from Claude’s installed cache—not from the current working tree—and still requires that one-time installation. Do not use the reaped scratchpad directory or `command`/link mode as production delivery.

Exact unresolved-delivery probe:

1. Use a unique Git marketplace/plugin name not already installed.
2. Put a relative plugin source in its Git marketplace; separately create an inline-marketplace control using the same relative source.
3. In a fresh Claude user profile, trust the test repository.
4. Before installation, run normal project configuration with `claude --debug-file … --init-only`: assert marketplace registration, “plugin not installed,” and no module-loaded line.
5. Run `claude plugin install <plugin>@<marketplace>`.
6. Repeat without `--plugin-dir`: require the exact module-loaded line.
7. Require the inline relative-source control to be rejected and the Git-relative source to load.
8. Run the main/lane behavioral arms below.

That settles tracked declaration, installation consent, relative-path resolution, and actual module loading separately.

## 2. THE SILENT-OFF MODE

Implement `kb_setup.function_hook_liveness` behind repository mise tasks, but run its decisive check **outside the Claude session being trusted**.

Load-bearing design:

1. `mise run kb-function-hook-arm` creates disposable repository copies and launches normal installed-plugin `claude -p` sessions—no `--plugin-dir` and no process-level enable flag masking the tracked `env` setting.

   It must prove:

   - main-thread `Edit` of the copied `.claude/settings.json` succeeds;
   - a first-level lane’s identical edit is denied with the guard’s exact reason and unchanged bytes;
   - that lane can edit an ordinary control file;
   - a nested lane is also denied;
   - a reply containing the target path still completes;
   - the debug log names the expected plugin/module and matcher events;
   - no rollout-off, managed-disable, bare-mode, collision, or module-load-failure diagnostic appears.

2. The resulting receipt binds the final repository SHA, Claude binary hash/version, settings digest, installed plugin digest/path, enabled-plugin inventory/order, and relevant managed-settings state. Any change invalidates it.

3. A repository launcher such as `mise run kb-claude-guarded -- <claude arguments>` checks that receipt and performs a cheap normal-delivery startup/load probe before launching the real session. It must support `-p`, reject `--bare` and disabling `--settings` overrides, and exit nonzero before forwarding a prompt when liveness is absent.

Without mandatory use of that launcher—or managed outer seating—the repository cannot guarantee this invariant. Raw `claude` remains a bypass.

Supporting checks:

- `claude plugin validate`: load-bearing for manifest/module/static-`$` correctness; **not runtime liveness**.
- `--plugin-dir` end-to-end arm: useful code control; **not delivery evidence**.
- Ship gate: must require static validation, mutations, and a final-SHA normal-delivery receipt. It protects what is merged, not every teammate’s machine.
- Classic `SessionStart`: warning only. It may check the receipt and print `KB FUNCTION GUARD OFF: …` to stderr, but Claude documents that SessionStart cannot block and Claude itself does not see the notice; see [hooks.md](/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/claude-code-docs/content/en/docs/claude-code/hooks.md:858). The same hook-disable states can suppress it. It is decoration, not the gate.

## 3. #92533 BLAST RADIUS

Register narrow per-tool handlers:

```ts
on("tool.call", { tool: "Edit" }, guard)
on("tool.call", { tool: "Write" }, guard)
```

Do not register an all-tools hook and filter inside it. That still intercepts Bash at dispatch and enters #92533’s reported failure surface.

The matcher is a partial equality object. It can match `{tool: "Edit"}`. It cannot express “`agentId` exists with any value”; the ID is dynamic, so lane classification belongs inside the handler.

Each narrow registration needs a fail-closed `.catch` for its own matched protected call. The handler must:

- lane + target: return the correct denial without calling `next`;
- everything else: call `next(e)` exactly once;
- never serialize the whole event;
- inspect only `e.file_path` and `e.agentId`.

Inventory `MultiEdit` and every future arbitrary-file mutation tool through validator/runtime evidence. Add exact per-tool matchers when proven necessary. Do not add Bash. `NotebookEdit` should be added only if a live arm proves it can target this JSON file.

## 4. THE BASH ROUTE

Extend the existing classic Python `kb-instruction-shell-write`; do not handle Bash in the TS module.

Reasons:

- It already owns Bash tokenization, redirects, `tee`, in-place tools, `uv run python -c`, and `cd`.
- A TS Bash matcher hits #92533 and still cannot solve arbitrary shell interpretation.
- The function-hook sandbox would need process capability merely to reuse the Python logic.
- The classic payload supplies the required `agent_id`.

Do not force `.claude/settings.json` into `md_budget.classify()`. Add an exact protected-target classifier beside the budget classifier:

- budgeted Markdown targets retain their current policy;
- exact `.claude/settings.json` is denied only when the classic origin parser reports a lane;
- missing `agent_id` is main-thread only under the version-bound liveness contract;
- present-but-null, empty, or wrong-type `agent_id` fails closed for this target;
- widen `_PATH_LITERAL` only enough to recognize the exact JSON target in `python -c`.

The present implementation is explicitly `.md`-only and fail-open at [instruction_shell_write.py](/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/instruction_shell_write.py:74). Extending it remains **necessary but insufficient**: its documented `find -exec`, `xargs`, `sh -c`, `eval`, substitution, alias, and computed-path gaps remain bypasses. An absolute “no lane can shell-write this file” invariant requires either closing those paths with a stricter lane Bash policy or refusing lane Bash commands that cannot be proven safe. A known fail-open scanner must not be described as complete Bash enforcement.

## 5. WHAT MAKES THIS GUARD GREEN AND STILL USELESS

- Project settings register and enable the plugin, but the user never installed it.
- Tests use `--plugin-dir`; production uses the missing marketplace installation.
- The test repository is trusted; a fresh or headless untrusted checkout silently ignores `extraKnownMarketplaces`.
- The marketplace points into the reaped scratchpad and works only until that path disappears.
- Copy mode tests current source while Claude runs an older cached copy. Link mode runs mutable, branch-dependent files or a path that later vanishes.
- The flag is present, but `disableAllHooks`, `allowManagedHooksOnly`, customization disabling, safe/bare mode, or later managed enrollment suppresses the module.
- A same-name managed or earlier plugin wins the collision.
- Unit tests import the module under Node, while Claude’s static validator rejects its `$` use or dynamic registration pattern and skips it.
- The handler throws and has no fail-closed registration catch.
- An outer/user-tier hook answers `Edit` without `next`, so this guard is never reached.
- The lane branch calls `next` before returning a denial: the bytes change while the transcript says denied.
- The main branch returns without `next`: tests see “no denial,” but main-thread edits never execute.
- An internal serialized-event search matches the assistant’s outgoing message and prevents the reply that reports the result.
- Only `Edit`/`Write` are registered while `MultiEdit` or a new arbitrary-file tool writes the file.
- First-level lanes carry `agentId`, but a nested lane loses or renames it and is classified as main.
- The Edit/Write arms pass while `sed -i`, computed `python -c`, `sh -c`, `eval`, `find -exec`, or aliases bypass the classic scanner.
- `.claude/settings.local.json` disables the project-enabled plugin or hooks for the next session. The tracked target remains untouched while its guard is removed.
- The guard’s own module, manifest, marketplace entry, or liveness receipt can be altered without invalidating the runtime receipt.
- The ship receipt covers an ancestor SHA, different plugin digest, or reduced plugin set that did not exercise the actual seating order.

## 6. THE `agentId` / `agent_id` SPELLING SPLIT

Do not use one undifferentiated constant. Generate two surface-specific adapters from one declarative mapping:

```text
function_hook -> agentId
classic_hook  -> agent_id
```

Only those adapters may access the fields. Enforce this with source checks that reject `agent_id` in TS and `agentId` in the classic Python path.

Each adapter returns a three-state result:

- valid non-empty ID → `LANE`;
- field absent → `MAIN`, but only while the exact-version live receipt proves main-absent and lane-present;
- field present but null, empty, or wrong type → `INVALID`, denied for the protected target.

A locally fail-closed default cannot solve field absence: absence is also the measured main-thread representation. Treating absence as denied would violate the required main-thread allow semantics. The only sound protection against an upstream rename is the external two-arm runtime contract.

Required fixtures and live arms:

- function main: no `agentId`;
- function lane: non-empty `agentId`;
- classic main: no `agent_id`;
- classic lane: non-empty `agent_id`;
- wrong-spelling mutation on each surface must survive no test;
- malformed-present values must deny;
- first-level and nested live lanes must both emit the expected spelling.

## WHAT I COULD NOT VERIFY

- The new plugin does not exist, so I could not run the decisive normal-marketplace install/load/behavior probe.
- The quoted 2.1.268 strings do not establish exact ordering among user-tier plugins; they establish only that this machine lacks managed outer seating.
- #92533 was not re-run against 2.1.268. Treat it as active until a narrow-Bash passthrough control in a worktree-isolated lane disproves it.
- Whether `--init-only` emits the module-loaded line on 2.1.268 needs the named probe; if it does not, the preflight must use a minimal `-p` launch.
- The complete arbitrary-write tool inventory and nested-lane `agentId` propagation require runtime capture.
- The repository graph’s local IDF query succeeded over 11,330 nodes, but the normal `mise run kb-query` and a fresh `kb-recall-work` report were blocked by this read-only sandbox’s temp/cache/report-write restrictions; I did not treat either failure as a pass or zero-result census.

---

## ADVISOR: arming codex's citations (done AFTER the verdict, by me)

Codex cited three corpus documents. This repo's doctrine is that a line number
is a measurement, so I read all three.

### ✅ ARMED AND CORRECT — the delivery refutation

Codex refuted my §F inference and it is RIGHT. `discover-plugins.md:484`,
verbatim:

> As of Claude Code v2.1.195, adding the marketplace doesn't install plugins
> that come from an external source, on any path that loads plugins. A plugin
> that only the project's `.claude/settings.json` enables, and that comes from
> an external source such as a GitHub repository or npm package, doesn't load
> until the team member installs it. Until then, Claude Code reports the plugin
> as not installed and shows the `claude plugin install` command to run.

And two lines above it, `discover-plugins.md:482`, which is the half I had
wrong:

> Once a team member [trusts the repository folder], Claude Code adds these
> marketplaces without a further prompt.

So my reading that project scope merely "offers" a marketplace was WRONG: after
folder trust the marketplace is added automatically. The per-machine cost is a
one-time `claude plugin install`, not a marketplace-trust prompt. Codex's
correction stands and the conclusion it supports — the guard cannot ship by
`git clone` + tracked config alone — survives the correction unchanged.

`settings-reference.md:4248` also verifies: `enabledPlugins` scope is
"Any file", i.e. enablement, not installation.

### ⚠️ CLAIM CORRECT, LINE NUMBER WRONG

Codex cited `hooks.md:858` for "SessionStart cannot block". The claim is true
and I verified it — but at **`hooks.md:871`**, not `:858`:

> `| `SessionStart`        | No         | Shows stderr to user only |`

`hooks.md:858` is the `TaskCreated` row. Act on the claim, not the citation.

### 🔴 A MECHANISM NEITHER LANE NAMED — found by arming the citation

Reading the blocking table around codex's bad line number turned up
**`ConfigChange`**, a CLASSIC hook event that appears to be purpose-built for
this exact job and is absent from the brief, from codex's answer, and from this
repo's 12 registered hooks:

- `hooks.md:57` — fires "When a configuration file changes during a session".
- `hooks.md:863` — **Can block? YES**: "Blocks the configuration change from
  taking effect (except `policy_settings`)".
- `hooks.md:318` — its `source` field is one of `user_settings`,
  **`project_settings`**, **`local_settings`**, `policy_settings`, `skills`.
- `hooks.md:2673` — the payload carries `source` AND `file_path`.
- `hooks.md:2688` — "Use exit code 2 or a JSON `decision` to prevent the change.
  When blocked, the new settings are not applied to the running session."

Why this matters more than its absence suggests — it is **route-independent**.
`ConfigChange` fires on the FILE CHANGING, not on which tool changed it. So
every documented blind spot of `instruction_shell_write.py` (`find -exec`,
`xargs`, `sh -c`, `eval`, `$(…)`, aliases, computed paths) is covered by it,
and so is the `.claude/settings.local.json` bypass in §4 above, via
`source: "local_settings"`.

🔴 Its limitation, measured in the same document and stated so nobody ships it
believing otherwise — `hooks.md:2704`, verbatim:

> A blocked change surfaces no message to you or to Claude, whether you block
> with `reason` or with stderr on exit 2. Claude Code only writes a line to the
> debug log.

So `ConfigChange` blocks SILENTLY. It is good enforcement with zero feedback,
which makes it a backstop rather than the primary guard — the model is never
told why its change did not take. It also fires on the change, i.e. AFTER the
bytes were written, so it prevents the change being APPLIED to the session, not
the write itself. That distinction is UNVERIFIED by me and needs an arm before
anyone relies on it as file protection rather than session protection.

**This does not contradict Ray's ruling.** He ruled the lane-discrimination
guard is a function hook; `ConfigChange` is an additional, cheaper layer that
covers the routes a function hook structurally cannot (shell writes) and the
file it does not watch (`settings.local.json`). It should be evaluated on its
own merits, not substituted for what he ruled.

### What I did NOT verify

- `ConfigChange`'s exact ordering relative to the write hitting disk.
- Whether `ConfigChange` fires for an UNTRACKED `settings.local.json` created
  for the first time, versus only for modifications to an existing file.
- Codex reported that its read-only sandbox blocked `mise run kb-query` and
  `kb-recall-work`; it explicitly did not treat those failures as zero-result
  censuses. I did not re-run them on its behalf, so the corpus-prior-art
  question remains open.
- `anthropics/claude-code#92533` was not re-verified by me or by codex against
  2.1.268. Codex's advice is to treat it as active until a narrow-Bash
  passthrough control in a worktree-isolated lane disproves it.

## GitHub repos touched (final)

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — the installed product; issue #92533 (unverified); its docs are vendored at `sources/claude-code-docs/`.
- [ray-manaloto/claude-code-marketplace](https://github.com/ray-manaloto/claude-code-marketplace) — the existing Git marketplace codex recommends as the delivery vehicle.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo.

---

# ROUND 2 — advisor's own measurements (2026-09-11, after the guard was built)

The lead reported four items as SETTLED. Three hold. One needs restating, and I
found three defects in the built artifact. Everything below is mine, measured
this round, before the round-2 codex consult returned.

## M1. 🔴 The delivery proof did not use TRACKED repo config

The lead's settled finding #1 reads "Delivery WORKS from tracked config alone —
`extraKnownMarketplaces` (`source:"directory"`) + `enabledPlugins`, no
`--plugin-dir`." The mechanism demonstration is real. What it demonstrated is
narrower than the sentence, and the gap matters.

Measured in the tracked tree, right now:

| what the claim needs | what is actually there |
|---|---|
| `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` in the tracked `env` block | **absent** — grepped `.claude/settings.json`, `.claude/settings.local.json` AND `~/.claude/settings.json`; not in any of the three |
| a `directory`-source `extraKnownMarketplaces` entry | **absent** — the 11 entries are all `source:"github"` |
| an `enabledPlugins` entry for the guard | **absent** |
| the plugin tracked | `git status --short` → `?? .claude/mods/` (**untracked**) |
| `.claude/settings.json` modified | `git status --short` → empty (**unmodified**) |

The marketplace the proof used is USER-level, in
`~/.claude/plugins/known_marketplaces.json`:

```json
"kb-local": {
  "source": {"source": "directory",
             "path": "/private/tmp/claude-501/…/281f4093…/scratchpad/kb-local-mk"},
  "installLocation": "/private/tmp/claude-501/…/scratchpad/kb-local-mk",
  "lastUpdated": "2026-09-11T18:17:25.414Z"
}
```

So what was proven is: **delivery from a disposable copy, via an absolute
machine-local path into a session scratchpad that gets reaped.** Two consequences
the claim does not carry:

1. An absolute `path` in tracked config is not portable — not to another
   machine, not to another checkout location of this repo.
2. I found NO evidence that a marketplace `directory.path` expands
   `${CLAUDE_PROJECT_DIR}` or `$HOME`, or resolves relative to the project root.
   `CLAUDE_PROJECT_DIR` appears in the binary only around hook-command strings.
   **UNVERIFIED** — but if it cannot be made portable, then "delivery from
   tracked config" is true only on the machine that wrote the absolute path, and
   finding #1 needs restating rather than relying on.

This is not a contradiction of the lead's measurement. It is the CONDITION that
measurement holds under, which is the thing this repo's rules say to carry.

## M2. 🔴 The module matches ALL tools and filters internally

`register.ts` registers `on("tool.call", hook)` with **no matcher**, then filters
with `WRITE_TOOLS`. Its own comment states a loader constraint — *"`on` is always
`on("<event>", hook)`"* — and that over-generalises.

The matcher validator in the running 2.1.268 binary is live and rich
(`strings` dump, ~S:240055-240072):

```
 is matched by the literal value or, as a string, by a RegExp, e.g. { … : /^prefix/ }
 is a RegExp with the <g> flag, which keeps state between tests; drop it
 is a RegExp with a nested quantifier (…), which can backtrack without bound; rewrite it
 has the key …, which no event has
 must be a string, a number, a boolean, null, a RegExp, an array of those, or a nested object; got …
: the matcher must be a plain object (a partial of e)
```

and the binary's own embedded `plugin-authoring` skill documents
`on(event, matcher?, hook)`, hooking `tool.call` with `{ tool: 'mcp__<plugin>__<name>' }`.

So the shipped registration intercepts EVERY tool dispatch, Bash included —
exactly the surface of `anthropics/claude-code#92533`, and the opposite of what
round 1 advised. A matcher may also be a RegExp, so
`{ tool: /^(Edit|Write|NotebookEdit)$/ }` is expressible as ONE registration.

## M3. The module cites a mise task that does not exist

`register.ts` points at `mise run kb-guard-arm` as the end-to-end arm. There is
no `kb-guard-arm` task in `mise.toml` (parsed the task table; ABSENT). The single
pointer to the arm is dangling — and per this repo's own rules, a document naming
an unreachable mechanism is worse than one naming none, because it reads as
authority.

## M4. Codegen here emits PYTHON ONLY

`mise run kb-codegen` = `datamodel-codegen --all-jobs` over `schemas/*.schema.json`
→ `python/src/kb_setup/generated/*.py` (msgspec Structs, 8 modules today).
`kb-codegen-check` is the `--check` drift gate. **No TypeScript emitter exists in
this toolchain**, which is the constraint question A runs into.

What the loader constraint permits, and the module's own notes understate: imports
are limited to relative paths and `"claude-code"` — which ALLOWS a sibling file
inside the plugin directory imported relatively. So a generator CAN emit a `.ts`
sibling. UNVERIFIED: whether a relative JSON-module import (`from "./x.json"`) is
accepted, or only `.ts`/`.js`.

## What of the lead's four I did NOT re-derive

Findings #2 (the three-arm proof), #3 (the Bash route open at
`md_budget.classify`) and #4 (folder trust) I accepted as measured and did not
re-run. #3 is consistent with what I read in
`instruction_shell_write.py:349` last round.


## Round-2 codex verdict (A-D)

`codex exec` SUCCEEDED (rc 0, 10,445 bytes, `gpt-5.6-sol`/`xhigh`). Verbatim:

---

VERDICT — REJECT AS A SECURITY GUARD: the function-hook logic is promising, but ordinary delivery can be absent or stale while its arm remains green.

## THE RISK THAT DECIDES IT

The decisive failure is proof-subject substitution: `--plugin-dir` or a disposable marketplace proves one copy of `register.ts`, while a fresh clone runs no guard and an established clone may run different cached bytes. That exactly reproduces “the gate is green while the thing it guards is unguarded.”

## A. ONE SOURCE OF TRUTH

Choose **(i): a language-neutral schema as the authority, generating both languages**.

- Put the closed path set in a dedicated JSON Schema `enum`, matching the repo’s existing schema-first convention.
- Let existing codegen produce the Python representation used before `md_budget.classify`.
- Add a small deterministic emitter producing `hooks/protected-paths.generated.ts`; `register.ts` imports that sibling relatively.
- Do not use Python or TypeScript as the policy authority. Either makes the other language a derivative of implementation code.

The gate must assert:

1. The schema enum has no duplicates, contains only normalized `/`-separated repo-relative paths, and is canonically sorted.
2. Each generated file is byte-for-byte equal to a fresh deterministic rendering. Do not compare Python bytes to TypeScript bytes.
3. Parsed values in both outputs equal the schema set. Set equality is the security contract; ordering is only a deterministic-generation requirement.
4. Cross-language path vectors produce identical decisions: exact relative path, absolute suffix, Windows separators, decoy names, dot segments, case variants, and symlink/alias cases where supported.
5. `kb-codegen-check` covers both emitters and fails for missing as well as stale outputs.

Python must test the protected-settings classifier before the Markdown classifier; otherwise sharing the list does not close the Bash route.

A current tree plus stale running `.ts` is still failure. `kb-codegen-check` proves only the tree. The runtime-copy check in C must fail until the cached payload matches.

**Matcher adjudication:** use **N literal matchers with one shared handler**, one registration per audited arbitrary-file writer. Reject the all-tools registration. The anchored non-global RegExp is technically expressible, but literals make the covered inventory reviewable and independently armable. All-tools interception adds Bash and unrelated dispatches without adding protection.

## B. THE COLD-CACHE FIRST-RUN GAP

Use two independent detection seats:

- A tracked classic `SessionStart` command in `.claude/settings.json` invokes a Python entrypoint such as `kb-setup settings-guard-liveness`. The hook contains no shell logic beyond dispatching to the repository task.
- `kb-gates` invokes the same checker directly, then runs the real-client arm through tracked delivery—never `--plugin-dir`.

At session start, the checker evaluates:

- function-hooks feature enablement;
- tracked relative marketplace declaration;
- effective plugin enablement, including `settings.local.json`;
- installed/running version and payload digest;
- whether the loader identified the expected hook module;
- cold-cache/orphan/not-found states.

On failure, it should exit `0` with structured output containing both:

- `systemMessage`: a prominent human warning;
- `SessionStart.additionalContext`: `GUARD UNAVAILABLE—DO NOT DELEGATE SETTINGS CHANGES` for Claude.

That is preferable to exit `2`: `SessionStart` cannot block, and its error stderr reaches only the user, whereas successful stdout/additional context reaches Claude. [Anthropic’s hook reference](https://code.claude.com/docs/en/hooks)

A detection-only `ConfigChange` hook should rerun the checker after project/local settings changes. It must always allow and only report; a silent blocking response would violate Ray’s ruling.

**Nothing inside the stated constraints closes the first-run gap.** `SessionStart` runs inside the already-unguarded session and cannot load the missed plugin retroactively. Closing it requires an upstream ordering fix, a pre-seeded cache, or an external bootstrap/restart barrier—which would be a separate enforcement mechanism.

Therefore the honest contract is:

> The first session after clone/cache-clear is unguarded. Before its first prompt, both the human and Claude must receive that warning, and the human must exit and restart before delegating.

That changes “silently unguarded” to “loudly unguarded”; it does not make the session guarded.

I disagree with only one implication in M1: current Anthropic documentation says a relative `directory`/`file` marketplace path resolves against the repository’s main checkout, including from worktrees. Your proof still did not demonstrate that, and the current tracked config still delivers nothing. [Anthropic’s marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces)

The settling probe is a two-location, fresh-state matrix:

1. Clone the repo into two unrelated absolute paths.
2. Give each an empty isolated Claude config/plugin cache.
3. Use only the tracked relative marketplace declaration—no user marketplace and no `--plugin-dir`.
4. Capture run 1 and run 2 debug logs, installed registry, resolved marketplace path, and hook firings.
5. Repeat from a linked worktree and assert resolution points to that repository’s main checkout.

## C. COPY VS LINK

Choose **copy plus an exact runtime drift check**. Link mode is not worth making guard availability depend on repository shell commands, repeated acceptance, folder trust, and a managed command-source kill switch. It would also make unreviewed working-tree edits live immediately.

The checker must compare:

- **Expected payload:** every regular file beneath the tracked plugin root—relative path, exact bytes, and relevant mode/symlink information—plus a canonical SHA-256 manifest.
- **Running payload:** bytes beneath the exact cache directory that the current Claude process reports loading, obtained from its session-correlated startup debug record. Never choose “the newest” cache directory by glob.
- Missing files, extra files, version mismatch, loader ambiguity, or absence of a loaded-module record all mean `UNGUARDED`, not “unknown but pass.”

The explicit `0.1.0` version is part of the defect: Claude’s documented cache behavior skips updates while the version remains unchanged. Require a version change whenever the payload digest changes, or adopt another proven content-derived cache key. [Anthropic’s plugin reference](https://code.claude.com/docs/en/plugins-reference)

Required control arms in an isolated cache:

1. Install through tracked delivery and assert `same`.
2. Change one cached byte in `register.ts`; expect nonzero `DRIFT`.
3. Restore it, then change only generated TS; expect `DRIFT`.
4. Change only the source tree while retaining the old cache; expect `DRIFT`.
5. Provide both stale and current cache directories; verify the checker follows the loader-reported path, not whichever looks newest.

The real arm must use that loaded path and tracked delivery. `--plugin-dir` takes precedence over installed copies, so it is valid only as a module-development arm, never delivery certification. [Anthropic’s plugin guide](https://code.claude.com/docs/en/plugins)

## D. WHAT MAKES THIS GUARD GREEN AND USELESS

1. **Nothing tracked:** `.claude/mods/` is untracked; feature enablement, marketplace delivery, and guard enablement are absent. A clone receives no guard.

2. **Substituted delivery:** an arm using the disposable marketplace or `--plugin-dir` passes while normal startup loads nothing else—or nothing.

3. **Cold-cache ordering:** tracked configuration may eventually work, but run 1 has zero hook registrations.

4. **Cached-copy drift:** the tree is fixed while the version-pinned cache still runs old bytes.

5. **Invisible local disable:** ignored `.claude/settings.local.json` sets the plugin false with clean `git status`. Bash can write it, and after restart the missing guard cannot defend itself.

6. **Incomplete writer inventory:** `MultiEdit`, Bash, MCP/plugin file writers, and any future arbitrary-file tool outside `WRITE_TOOLS` bypass the handler. Nonstandard tools also require tool-specific path extraction.

7. **Over-broad registration:** the current no-matcher hook intercepts Bash and every unrelated tool. An isolation/Bash interaction can make delegation unusable even though the three Edit/Write arms pass.

8. **Fail-open provenance:** absent, empty, renamed, or unpropagated `agentId` is classified as main thread and allowed.

9. **Hook preemption:** an earlier function hook that answers without `next` prevents this hook from observing the call. There is no managed outer seat here.

10. **Logging before denial:** if `$.ui.log` throws, the function returns no denial. Nonessential logging must not sit on the critical path; return the deny without it or prove a guarded logging form.

11. **Dangling certification:** `mise run kb-guard-arm` does not exist, so the only named end-to-end proof is neither runnable nor bound into `kb-gates`.

12. **Path aliases:** case-insensitive filesystem aliases, symlinks, or other spellings reaching the same settings file can bypass a string-suffix test unless the live tool contract and normalization arms cover them.

## WHAT YOU COULD NOT VERIFY

- The relative-marketplace behavior specifically in **2.1.268**; current primary documentation supports it, but the clean two-location probe must certify that target binary.
- Whether JSON module imports load. The recommended generated `.ts` sibling avoids depending on that.
- The authoritative way for a classic hook to locate the current process’s loaded cache path. If the session debug record cannot provide it, the runtime drift checker cannot certify “running copy”; only the real-client arm can.
- The complete 2.1.268 arbitrary-writer inventory and whether `MultiEdit` is actually exposed. Capture one live `tool.call` event per candidate.
- `systemMessage` plus `SessionStart.additionalContext` behavior in 2.1.268. Arm both the visible user warning and Claude’s received context.
- Repository graph/recall state: the sanctioned `mise` tasks failed before dispatch because the sandbox could not create temp files; the prohibited bare Graphify command was correctly blocked.

---

## ADVISOR: arming the round-2 verdict's two doc claims

Codex disagreed with one of my readings and cited docs for two claims. I read
both against the vendored corpus. **Both arm clean, and one of them refutes me.**

### ✅ M1(b) REFUTED — a RELATIVE marketplace path IS portable

I said I found no evidence a `directory` marketplace path resolves
project-relatively, and flagged it as the probe that decides whether tracked
delivery works off this machine. Codex said current docs support it. Codex is
right. `sources/claude-code-docs/content/en/docs/claude-code/plugin-marketplaces.md:867`,
verbatim:

> If you use a local `directory` or `file` source with a relative path, the path
> resolves against your repository's main checkout. When you run Claude Code
> from a git worktree, the path still points at the main checkout, so all
> worktrees share the same marketplace location. Marketplace state is stored
> once per user in `~/.claude/plugins/known_marketplaces.json`, not per project.

Control arm: the same grep shape returned 205 hits for `marketplace` in that
file, so a zero would have been meaningful; it discriminates.

**So the remedy is concrete: use a RELATIVE `directory` path, not the absolute
scratchpad path the proof used.** My M1(a) still stands unchanged — an absolute
path is not portable, and an absolute path into a reaped scratchpad is what the
proof actually used. What is refuted is only my inference that no portable form
exists.

Two riders that sentence carries, and they are load-bearing:

1. **Marketplace state is per USER, not per project.** Two clones of this repo
   on one machine share ONE `known_marketplaces.json` entry, which resolves to
   "your repository's main checkout" — singular. Which checkout wins when there
   are two is UNVERIFIED and is exactly the shape of codex's two-location probe.
2. Relative paths "work when users add your marketplace from a git source or a
   local directory" but **do not resolve for a URL-sourced marketplace**
   (`plugin-marketplaces.md:293`), since only the one file is downloaded.

### ✅ ARMED — SessionStart is context-only, and there is a stronger lever

Codex's B design (exit 0, `systemMessage` for the human +
`hookSpecificOutput.additionalContext` for Claude) is correct.
`hooks.md:1024`, verbatim:

> `SessionStart, SubagentStart, PostModelSwitch` | Context only |
> `hookSpecificOutput.additionalContext` adds context for Claude. SessionStart
> also accepts `initialUserMessage`, `watchPaths`, `sessionTitle`, and
> `reloadSkills`. **No blocking or decision control**

`hooks.md:1150` confirms `additionalContext` is "added to Claude's context at
the start of the conversation, before the first prompt", and `hooks.md:926`
confirms `systemMessage` is a "Warning message shown to the user".

🔴 **A lever codex did not name, and it matters for the headless case.**
`hooks.md:1151`, verbatim:

> `initialUserMessage` | String used as the first user message of the session.
> Applies in non-interactive mode with the `-p` flag, where it becomes the first
> turn even if no prompt is provided. If a prompt is provided, it follows as the
> next turn. Unlike `additionalContext`, which attaches to an existing turn,
> this creates the turn.

`additionalContext` attaches to an existing turn; in a headless `-p` run that is
weaker. `initialUserMessage` CREATES the first turn, so an unguarded headless
session can be made to open with the warning rather than with the delegation.
Still detection, not enforcement — it cannot stop anything — so it stays inside
Ray's ruling. UNVERIFIED on 2.1.268; arm it before relying on it.

### Where I still disagree with codex

Nowhere on substance. One framing note: codex's B concludes "nothing inside the
stated constraints closes the first-run gap", and I agree — but the honest
contract it proposes ("the human must exit and restart before delegating")
depends on a human reading a warning, which this repo has measured as a weak
control twice (the warning-only graph-first rule scored 0 compliance in 19
chances; the deny that replaced it took violations 62 to 0). Say that out loud
when the contract is written, rather than discovering it later.

### Still UNVERIFIED after round 2

- The relative-marketplace behaviour on **2.1.268** specifically. The docs are
  the claim; the two-location fresh-cache probe codex specified is what settles
  it, and it has not been run.
- Which checkout wins when one machine has two clones (per-user marketplace
  state, singular "main checkout").
- Whether `initialUserMessage` and `systemMessage` behave as documented on
  2.1.268.
- Whether a relative JSON-module import loads in a hooks module. Codex's
  recommended generated `.ts` sibling sidesteps the question entirely.
- The full 2.1.268 arbitrary-writer tool inventory (is `MultiEdit` exposed?).
  One live `tool.call` capture per candidate is the arm.
- How a classic hook locates the CURRENT process's loaded cache directory. If
  the session debug record cannot supply it, the runtime drift check in C
  cannot certify the running copy at all, and only the real-client arm can.
- Codex reported its read-only sandbox blocked `mise run kb-query` and
  `kb-recall-work` (could not create temp files) and that the bare graphify
  command was correctly denied by the guard. It did not treat those as
  zero-result censuses, and neither do I.
