# #754 G01 — kb-codex-advisor verdict

Lane: `kb-codex-advisor` (reasoning runs inside `codex exec`, `gpt-5.6-sol`, `xhigh`).
Written 2026-09-12 against `feat/754-plugin-types-contract` @ `6563b6ef`.

**Part 1 (below) is this agent's own re-derivation from the repo.** Part 2 is the
codex verdict, appended verbatim after the call returns.

---

## Part 1 — premise P8, re-read this session (the lead flagged it unverified)

**P8 CONFIRMED, and it is stronger than the ticket states.** `register.ts` is frozen
in two independent ways, and the ticket names only one of them.

`python/src/kb_setup/guard_inventory.py:823-831`:

```python
_WRITE_TOOLS_ARRAY = re.compile(
    r"const\s+WRITE_TOOLS\s*:\s*readonly\s+string\[\]\s*=\s*\[(?P<body>[^\]]*)\]\s*;"
)
_REGISTER_LOOP = re.compile(
    r"export\s+function\s+register\s*\([^)]*\)\s*:\s*void\s*\{\s*"
    r"for\s*\(\s*const\s+tool\s+of\s+WRITE_TOOLS\s*\)\s*\{\s*"
    r'on\s*\(\s*"tool\.call"\s*,\s*\{\s*tool\s*\}\s*,\s*\w+\s*\)\s*;?\s*'
    r"\}\s*\}"
)
```

`function_hook_write_tools` (`:864-887`) returns `None` — reported as a `NOT_RUN`
finding (`:898-904`), which `guard_inventory` maps to `Rc.NOT_RUN` = **127**
(`:1160-1161`) — when ANY of these hold:

| break | why it returns `None` |
|---|---|
| rename `WRITE_TOOLS`, drop `: readonly string[]`, or switch to `as const` | `_WRITE_TOOLS_ARRAY` misses |
| a second array of that exact shape | `len(arrays) != 1` |
| a nested array / any `]` inside the body | `[^\]]*` stops early |
| a duplicate tool name in the array | `len(set(tools)) != len(tools)` |
| loop variable renamed from `tool` | `_REGISTER_LOOP` hardcodes `tool` |
| matcher written `{ tool: tool }` instead of `{ tool }` | hardcoded shape |
| handler passed as an inline arrow instead of a named identifier | 3rd arg is `\w+` |
| `export async function register`, or a return type other than `void` | hardcoded |
| **any second statement inside `register()`** — a second `on(...)`, a log line, a guard | the regex requires `}` `}` immediately after the single `on(...)` |
| **any second event registered at all** (e.g. `on("session.authorize", …)`) | same clause |

The last two are the ones that bite #754. A design that wants `register.ts` to
also register a new event, or to read a newly-available field via a second
registration, cannot do it without re-authoring G00's regexes in the same PR.

**Second freeze, not in the ticket.** `guard_codegen._check_consumer`
(`guard_codegen.py:414-430`) independently requires that `register.ts` still
imports AND uses `PROTECTED_SUFFIXES` inside `isProtectedPath`. So `register.ts`
is load-bearing for TWO shipped gates, not one.

## Part 1b — what the mod surface actually reads (the B2 field set, derived, not assumed)

The whole mod surface is four files (`find .claude/mods -type f`), and only
`register.ts` touches an event. Every runtime dependency it has on the Claude
Code declarations:

| kind | symbol | site |
|---|---|---|
| event name | `tool.call` | `register.ts:register()` |
| matcher key | `tool` | `on("tool.call", { tool }, handler)` |
| event field | `agentId` (camelCase — the spelling trap) | `laneOf`, `register.ts:96-99` |
| event field | `file_path` | `handler`, `register.ts:152` |
| event field | `tool` | used in both `$.ui.log` messages |
| context member | `$.fs.list(dir)` → entries with `.name` / `.kind` | `targetInLinkedWorktree` |
| context member | `$.ui.log(string)` | `handler`, 3 sites |
| hook signature | `($, e, next)`, `next(e)` | `handler` |
| return shape | `{ deny: string }` | `handler`, 2 sites |

`$.session.cwd()` appears ONLY in a comment describing a REJECTED earlier design
(`register.ts:110-113`) — a regex-derived set that does not strip comments would
wrongly include it. `guard_inventory.strip_ts_comments` is public specifically so
a second consumer can reuse it (`:846-859`), which is the precedent for how this
set should be derived.

## Part 1c — two facts the spec did not carry

1. **`arms.py` is pytest-only, hard.** `run_suite` (`arms.py:289-306`) shells
   `[sys.executable, "-m", "pytest", *suites, …]`; `Arm.test` is a pytest node
   name and every non-control arm REQUIRES one. There is no command-runner
   backend. So any part of #754 that is proved by `--arms` must be reachable
   from a pytest test — i.e. **hermetic** — or it is not armable at all.
   Independently, `arms.py:9-17` confirms a **data** file is a legal target
   (G00 mutates `docs/guards/inventory.toml`), so a committed contract file IS
   an armable surface.
2. **`.claude/types/` is neither tracked nor gitignored** (`git check-ignore`
   rc=1; the directory does not exist). A live `/plugin-types` run in the repo
   root writes two untracked files into `.claude/`, dirtying the tree — which a
   gate must not do (`gates.py` `CONCURRENT_SAFE` question 1; `clean-git-state.md`).

## Part 1d — graph query, with its control arm

`mise run kb-query -- "how does the guard inventory reconcile function hook
registrations in register.ts"` returned **rc 3, TRUNCATED** — 686 nodes, 65 shown,
and every visible node was from a vendored source (pytest, codex-rs, hermes), none
from `python/src/kb_setup/`. That is the known aggregate-graph crowding
(`kb-query --prose` reads 11,330 nodes vs 359k+ aggregate), not evidence of absence.
**This session's code facts are all read from the files directly**, cited above.

---

## Part 2 — codex verdict

_(pending — appended below when `codex exec` returns)_

**The codex call SUCCEEDED.** `mise run kb-codex -- --model gpt-5.6-sol --effort xhigh
--timeout 900 --output …` → **rc 0**. (A first attempt at a raw `codex exec` was correctly
DENIED by `kb_setup.codex_lane` and re-run through the task.) Codex's output is reproduced
verbatim below; nothing in it is this agent's own reasoning.

### Verbatim codex verdict (gpt-5.6-sol, xhigh)

> ### Verdicts
>
> - **A — A1, corrected:** Put the live task directly in `GATE_TASKS`, EXCLUSIVE, and generate in a fresh temporary CWD. Delete "hermetic"; missing/unrunnable Claude returns 127. **Deciding risk:** A2/A3 can green without examining the installed runtime they claim to certify.
> - **B — B3:** Fresh declarations versus mechanically extracted consumer requirements is blocking; fresh versus vendored 2.1.267 is informational only. After `strip_ts_comments`, extract the registration literal/matcher, exact `e` and `$` property chains, `$.fs.list` result fields, `next(e)`, and deny shape. Preserve `agentId` exactly—never normalize it to `agent_id`. **Deciding risk:** a hand-authored contract can encode the documented/classic spelling and silently miss the guard's allow-on-absence failure.
> - **C — Declaration-specific detector:** Reuse only a generic exact-set comparison helper, not `_stale_generated_files` or its marker. Generate in a task-owned empty temporary root and require exactly the expected Claude-owned relative outputs; missing and extra paths are symmetric failures. **Deciding risk:** without a controlled provenance marker, the existing heuristic must either miss stale `.d.ts` files or classify unrelated neighbors as generated.
> - **D — No command-runner extension:** A named pytest can invoke the live module and construct missing/extra states; arms should mutate tracked resolver or exact-set detection code. The ticket's literal delete/add Arm action is not supported as-is. **Deciding risk:** otherwise the receipt claims a filesystem mutation the pytest-only runner never performed.
>
> ### Proposed ticket edits
>
> - Replace **"deterministic, hermetic"** with: "Deterministic relative to the resolved installed Claude binary; intentionally non-hermetic; runs in an isolated temporary CWD and returns NOT_RUN 127 when Claude cannot be executed." The hermetic half gives way.
> - Replace blocking **"reconcile against the vendored file"** with: "Integrity-check and report the 2.1.267 corpus delta nonblockingly; only missing mechanically extracted consumer requirements or invalid generated-output topology fail." Negative vendored authority gives way.
> - Replace the literal filesystem FAIL arm with: "Mutate tracked missing/extra detection logic; the named pytest generates live declarations and constructs deletion plus stale-extra cases." The "arms-able as-is" claim gives way; retaining literal Arm filesystem actions would make #754 depend on #771.
>
> ### Not determined
>
> - Whether `/plugin-types` succeeds with a binary present but no credentials; "no model call" does not prove that.
> - Whether `kb-arms` preserves a pytest process exit of 127 distinctly.
> - Whether the two observed declaration filenames are a documented stable output set or merely the current 2.1.269 behavior.
> - The repository graph could not be consulted: `mise run kb-query` exited 1 before Graphify with `purgatory cleanup failed: Operation not permitted` and another temp-path `Operation not permitted`. The supplied re-derived premises are therefore the authority for this verdict.

---

## Part 3 — two of codex's open items, ARMED this session

Codex's first open item decides verdict A, so it was measured rather than left open.

### Arm 1 — does `/plugin-types` need credentials? NO.

Two arms, one variable (`HOME`), same binary `~/.local/share/claude/versions/2.1.269`,
both from an empty CWD, both `< /dev/null`:

| arm | `HOME` | rc | outputs |
|---|---|---|---|
| A | the real `$HOME` (credentialed, 12 MCP servers) | **0** | both `.d.ts` written |
| B | a **fresh empty temp dir** — no `~/.claude`, no credentials | **0** | both `.d.ts` written |

**So A1 is viable: the live path needs no credentials and does not hang or prompt.**
`guard_codegen`'s hermeticity rule exists so a gate reachable through `pytest` runs on a
machine with no Claude credentials — and this check would satisfy the *spirit* of that rule
even while shelling to `claude`. The remaining true blocker for pytest-reachability is the
BINARY's presence, not credentials.

### Arm 2 — the generated declarations are ENVIRONMENT-dependent, not version-dependent alone

🔴 **This is new, it was not in the ticket, and it changes B and C.** Same binary, same
command, two HOMEs:

| | armA (full env) | armB (bare env) |
|---|---|---|
| `claude-code.d.ts` | 9,263 lines, `51e327a1…` | **9,156 lines, `15eccaa7…`** |
| `claude-code-mcp.d.ts` | 2,588 lines, `c0e53657…` | **10 lines, `47979a1c…`** |
| the tool's own log | "30 built-in tools" · "170 MCP tools from 12 servers" | "24 built-in tools" · "no MCP tools are connected" |

The diff is the local **tool inventory** — `Monitor` and `ListMcpResourcesTool` present under
the real HOME and absent under the bare one — plus a settings-dependent doc comment on
`scheduled_tasks` persistence.

**Consequences:**

1. **B1 is dead twice over.** The ticket rejects it because a version bump reds it; it is worse
   than that — a whole-file compare reds on a *different machine at the same version*. Any
   content hash of these artifacts is machine-local and can never be a gate.
2. **The ticket's headline delta is CONFOUNDED.** `+1,297 lines` is the full-environment
   figure; the version-only delta is **+1,190** (7,966 → 9,156). **107 of the 1,297 lines are
   this machine's MCP/tool inventory, not 2.1.267→2.1.269 drift.** The staleness conclusion is
   unaffected and the corrected `tool.call 37 → 46` row **survives** (46 in BOTH arms), but the
   line-delta row should be restated or labelled.
3. **B2 is feasible, and this is the measurement that proves it.** Every token the mod actually
   relies on sits in the environment-INVARIANT region:

| token | armA | armB | vendored 2.1.267 |
|---|---|---|---|
| `"tool.call"` | 2 | 2 | 2 |
| `agentId` | 26 | 26 | 16 |
| `agent_id` | 4 | 4 | 4 |
| `file_path` | 10 | 10 | 9 |
| `NotebookEdit` / `Edit` / `Write` | 2 / 12 / 6 | 2 / 12 / 6 | 2 / 11 / 5 |
| `session.authorize` | 7 | 7 | **0** |
| `ZZZ_control_absent` (control arm) | 0 | 0 | 0 |

armA == armB on **every** required token, so a required-set membership check is stable across
machines. The control arm returns 0 everywhere, so the probe discriminates.

4. **Codex's C verdict survives this and is strengthened.** Both filenames are written in BOTH
   arms, so the *topology* (exact expected relative output paths) is environment-invariant even
   though the *content* is not. An exact-set check over filenames is the right instrument;
   a content marker would not have been.

### Still not determined (carried forward honestly)

- Whether `/plugin-types` output is stable across *Claude Code versions* in its filename set —
  both arms here ran 2.1.269. Codex's third open item stands.
- Whether `kb-arms` distinguishes a pytest exit of 127. Not measured; `Arm.test` (a named test
  in the failure summary) is what the runner actually keys on, so this is likely moot, but it
  is unverified.
- Codex reported it could not run `mise run kb-query` from its read-only sandbox
  (`purgatory cleanup failed: Operation not permitted`). This agent's own `kb-query` ran and
  returned **rc 3 TRUNCATED** noise from vendored sources — so the graph contributed nothing to
  this verdict in either lane, and every code fact above is a direct file read with its
  `file:line`.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under advisement; issue #754 read via `gh issue view`.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — referenced only through the ticket's citation of issue #92469 (`session.authorize` / `flag.value` omissions); not fetched this session.
