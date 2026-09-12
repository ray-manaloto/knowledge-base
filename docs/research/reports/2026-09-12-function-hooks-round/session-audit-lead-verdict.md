# Session audit — lead verdict (`kb-codex-astra-advisor`)

Audited commit: **`4cdd8bfb`** (`4cdd8bfbc3a2d7919adc8057c34afd487813fa26`),
branch `feat/754-plugin-types-contract`, repo
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base`. Written 2026-09-12.

**This file is the LEAD's own verdict and independent measurements.** The merged
five-lane product is
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/session-audit-synthesis.md`
(747 lines / 240,541 bytes), produced by a `gpt-6-astra` synthesis lane.

## Lanes dispatched, and their real exit codes

| lane | question | model | rc | report (absolute) |
|---|---|---|---:|---|
| A | is the SHIPPED CODE correct? | `gpt-5.6-sol` | 0 | `.agent/kb/reports/agents/session-audit-a-code.md` |
| B | are the function-hooks / `.d.ts` claims correct? | `gpt-5.6-sol` | 0 | `.agent/kb/reports/agents/session-audit-b-claims.md` |
| C | is every finding ACCOUNTED FOR? | `gpt-5.6-sol` | 0 | `.agent/kb/reports/agents/session-audit-c-accounted.md` |
| D | what is VAGUE or UNMEASURED? | `gpt-5.6-sol` | **124** | `.agent/kb/reports/agents/session-audit-d-vague.md` |
| E | what did the session MISS? | `gpt-5.6-sol` | 0 | `.agent/kb/reports/agents/session-audit-e-missed.md` |
| synthesis | merge into one handoff | `gpt-6-astra` | 0 | `.agent/kb/reports/agents/session-audit-synthesis.md` |

🔴 **Lane D was ENDED AT ITS BOUND, rc 124.** `kb-codex` reported verbatim:
*"the lane exceeded --timeout 2400s and was ended. Its output up to that point is
above (and in --output, if given); it reviewed a SUBSET, which is not a clean
pass."* Because it wrote incrementally, its report reached disk through every
requested section. **Its findings are usable; the completeness of its sweep is
unproven.** No lane's silence was filled with the lead's own reasoning.

**Routing.** Fan-out ran on `gpt-5.6-sol`, not Astra, deliberately: lane A reads
the guard surface (`register.ts`, `guard_inventory`, `guard_codegen`) where Astra
refuses authorized security work outright. Astra did the synthesis, which touches
no guard source. Ray specified Astra for the synthesis only.

## The verdict, one line

**The session's work is sound in its direction and defective in its evidence
discipline: the gate it shipped was green only because of WHERE it was run, and
127 of 147 findings have no durable home.**

## What the LEAD measured independently (not inherited from any lane)

### 🔴 P1 — the shipped gate passes only inside a Claude Code session

`/plugin-types` does not exist unless `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is
set. That flag is declared in
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/settings.json`'s
`env` block — so Claude Code injects it. **No task sets it**: zero hits for the
name in `mise.toml`, `python/src/kb_setup/mod_runtime.py`, `python/src/kb_setup/gates.py`.

Two arms, same binary (2.1.269), flag the only variable:

```
env -u CLAUDE_CODE_ENABLE_FUNCTION_HOOKS uv run kb-setup mod-runtime-check   -> rc=1
  [mod-runtime-check] EXPECTED OUTPUT NOT WRITTEN at 2.1.269: .claude/types/claude-code.d.ts
  [mod-runtime-check] EXPECTED OUTPUT NOT WRITTEN at 2.1.269: .claude/types/claude-code-mcp.d.ts
uv run kb-setup mod-runtime-check                                            -> rc=0, clean, 11 symbols
```

The probe discriminates. The failure is **misclassified**: CI or a plain terminal
reads *the runtime contract regressed* when the truth is *the question was never
asked*, and the message never names the flag. `Rc.NOT_RUN` (127) is this repo's
third state for exactly that case.

This **contradicts `4cdd8bfb`'s own commit message**, which claims the gate "needs
the BINARY, never credentials". It needs the binary **and** the feature flag.

**Status: being fixed live by the main session**, staged and uncommitted, +38
lines to `python/src/kb_setup/mod_runtime.py` — sets the flag on the subprocess
env AND maps a detected `Unknown command` to `Rc.NOT_RUN` with a message naming
the flag. The fix is correct in shape and **is itself unreviewed and unarmed**.

### Volatile counts, re-derived rather than quoted

| claim | stated at | measured | verdict |
|---|---|---|---|
| aggregate graph nodes 359,026 | `CLAUDE.md:47` | **472,069** | **STALE by 113,043** |
| prose graph nodes 11,330 | `CLAUDE.md:47` | 11,330 (+14,893 links, 484 hyperedges) | AGREES |
| agents | `CLAUDE.md` says re-derive | **9** | current |
| plugins declared / effective | `CLAUDE.md` | **21 / 17** | AGREES |
| task timeouts | `CLAUDE.md` | **29 of 102** | AGREES (updated in `4cdd8bfb`) |
| vendored `.d.ts` 7,966 lines | commit `4cdd8bfb` | **7,966** | CONFIRMED |
| `session.authorize` 0 in vendored | commit `4cdd8bfb` | **0** | CONFIRMED |
| gates 11/11 | commit message | **11/11 rc=0** | CONFIRMED from the artifact |

### The installed runtime — route corrected

Claude Code 2.1.269 ships as a **compiled Mach-O 64-bit arm64 executable**,
203,150,240 bytes. **There is no `cli.js` at this version**, so any probe that
greps a JS bundle for a flag cannot run at all.

The two candidate install paths are **byte-identical** — settled by hash, closing
a disagreement the synthesis left open:

```
shasum -a 256 \
  ~/.local/share/mise/installs/npm-anthropic-ai-claude-code/2.1.269/node_modules/@anthropic-ai/claude-code-darwin-arm64/claude \
  ~/.local/share/claude/versions/2.1.269
c942e1228b93cb4d52183b3dfbc77f28264f35aa947acd9c0853d029164cf450  (both)
```

`~/.local/bin/claude` is a symlink to `~/.local/share/claude/versions/2.1.269`;
`command -v claude` resolves to a **mise shim**, not the binary
(`change-the-route.md` rule 6, live).

### The lane count disagreement was the `grep -c` proxy trap

The lead measured `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` = 5; lane D measured 7.
Both correct, measuring different things on identical bytes:

| token | lines (`grep -c`) | occurrences (`grep -o \| wc -l`) |
|---|---:|---:|
| `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` | 5 | **7** |
| `session.authorize` | 8 | 8 |
| `CLAUDE_CODE_ENABLE_BOGUS_XYZQ` (control) | 0 | 0 |

`grep -c` counts LINES. The control arm returns 0 both ways, so the probe
discriminates. This is the repo's own recorded *"I measure a PROXY"* failure,
reproduced inside the audit that exists to find it.

### A probe of the lead's own that FAILED, recorded rather than hidden

The lead's first graph measurement reported `edges=0`. Wrong instrument, not a
real zero: the key is `links`, not `edges`. A later flag probe returned 0 on all
four arms from an empty glob path — caught only because two known-present control
tokens also returned 0. Both are the class this audit was commissioned to find.

## Accounting — the headline number

Lane C inventoried **147 distinct findings** across the nine session reports and
the raw Astra verdict. **20 are homed. 127 are not.** `.agent/**` is gitignored,
so a report living only there is not homed. Lane C produced a complete
ID-to-destination matrix with no silently skipped ranges, proposing nine
promotions under `docs/research/reports/` plus four issue actions. It flags
itself as unhomed and asks to be promoted without renumbering.

## 🔴 Two untracked files carry STANDING directives that exist nowhere else

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/direction/2026-09-12-ray-directives.md`
— **142 lines when the audit began, 177 by the end** (a §8 was added mid-audit).
Sections 4, 5, 6 (and now 8) are marked **STANDING**. `docs/direction/` is the
brief every round is measured against and `/clear-prep` reads the newest one.
Uncommitted, it reaches no other machine and no future session.

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/artifacts/function-hooks-work-order.html`
— 5,993 bytes; promises a tsc/compiler layer that `4cdd8bfb` did not implement.

**§5 of the directive file breaks a premise other work rests on:**
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is now publicly acknowledged for testing,
so *"the engine cannot be probed"* — the basis of `ray-manaloto/dotfiles#1020`'s
RUNTIME-UNVERIFIED banner and of deferring behavioural arms to #757 — is no
longer structurally true. It also records the product being renamed **"Claude
Mods"** and shipping committed "on the scale of weeks".

**§7 conflicts with this agent's own definition.** Ray directs that codex
research/execution lanes must not be sandboxed read-only, while
`.claude/agents/kb-codex-astra-advisor.md` and `kb-codex-astra-reviewer.md` mark
`--sandbox read-only` MANDATORY. `do-not.md` #13 forbids a repository lane at
`danger-full-access`, and **#767** is open about 13 codex sessions that already
ran that way. The conflict is currently recorded only in an untracked file.

## ⚠️ An in-flight correction whose EVIDENCE is unverified

The uncommitted edits to `.claude/agents/kb-codex-advisor.md` and
`kb-codex-astra-advisor.md` assert that on 2026-09-12 five same-type lanes ran
against a fixed `/tmp/<agent-name>-prompt.md` and one overwrote another's prompt
mid-flight. **The lead's five audit lanes used five distinct scratchpad paths**
(`.../scratchpad/audit/lane-{a,b,c,d,e}.md`, written 12:53–12:55), so they cannot
be the overwriting party. Exactly one fixed-path file exists,
`/tmp/kb-codex-astra-advisor-prompt.md`, mtime 13:08, from an unidentified later
actor. **The per-lane-directory fix is good hygiene; the incident narrative is
UNVERIFIED** and should not be shipped as established fact.

## Prior art the session re-derived — larger than the brief stated

The brief named "the 2026-09-10 function-hooks reports (2 tracked, 38 KB + 53 KB)".
Measured: **five** tracked function-hooks reports under
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/reports/`,
~224 KB total —
`2026-09-10-function-hooks-research.md` (38,363 B),
`2026-09-10-github-function-hooks-examples.md` (53,353 B),
`2026-09-11-astra-function-hooks-setup-coverage.md` (45,872 B),
`2026-09-11-function-hooks-astra-verdict-raw.md` (30,137 B),
`2026-09-11-function-hooks-enforcement-programme.md` (56,819 B).

One benign mystery resolved: lane A saw `graphify-extraction-owner.md` change
mtime mid-run and correctly refused to attribute it. Cause — that report grew
from 494 lines (25,407 B, 12:34) to **873 lines (46,536 B, 13:02)**; its agent
was still writing two late addenda. No gate wrote it. Any promotion must take the
full 873 lines, not the 494-line prefix.

## What the lead could NOT verify

- **The five research surfaces named in the brief were only partly reachable to
  this agent.** `ctx7` and `mcp2cli` are on PATH and were handed to lane E;
  `/last30days`, `/firecrawl:*`, `/exa:search` and `/context7:docs` are
  Claude-side tools this subagent does not hold, and a codex lane has no browser.
  The `llms.txt` route was probed and discriminates (`code.claude.com/docs/llms.txt`
  → 200, a bogus domain → 000). Coverage of those surfaces rests on lane E's
  report, not on the lead's own calls.
- **Lane D's sweep completeness**, per its rc 124 above.
- **Whether the staged `mod_runtime.py` fix is correct under arms** — it is
  unreviewed and unarmed, and this repo's measured pattern is that review-driven
  fixes are where the next defect lives.
- **The contents of the 16 concurrently-promoted files** under
  `docs/research/reports/2026-09-12-function-hooks-round/`, created by another
  actor during the synthesis and still untracked.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the audited repo: branch, commits, gates, reports, CLAUDE.md, mods surface.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the sibling holding nine function-hooks reports and issue #1020, comment 5647302470.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issue #91870, the installed 2.1.269 binary and its declarations.
