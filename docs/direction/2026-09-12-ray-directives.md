# Ray's directives — 2026-09-12

VERBATIM. This file is the standing brief a round is measured against; do not
paraphrase, and do not "tidy" the wording. Session `kb-20260911.004`.

Written the moment each directive was given, not at round end — the 2026-09-10
file exists precisely because a whole round's directives were acted on and
recorded nowhere, surviving only in a transcript.

## 1. Modern tooling, with a systems-language preference

> use modern tooling w rust/c++/c/zig preference

Given as the answer to "do `.ts` files get a linter/formatter", so it is a
**ruling on tool selection generally**, not only about that question. It rules
out Prettier and ESLint. The adopted answer for TypeScript is **Biome**
(`aqua:biomejs/biome`, Rust, formats *and* lints, checksum-verified backend);
`oxlint` is also Rust but lint-only, `dprint` format-only.

## 2. Fan out the source re-review through codex lanes

> have codex lane kb-codex-astra-advisor fan out other codex lanes/subagents to
> rereview all the links i provided earlier to make sure we did not forget
> anything and follow links/sources it provides

With the link list: the aitmpl blog and function-hooks pages, `anthropics/claude-code#91870`
(videos + examples as graphify sources via video extraction; resync the claude
graphify sources to pick up `anthropics/claude-code/tree/main/mods`), the architecture PDF,
and `github.com/search?q=CLAUDE_CODE_ENABLE_FUNCTION_HOOKS&type=repositories`.

## 3. Browser / gh / graphify-extension research, fanned out and synthesized

> use computer use or chrome extensions for claude to inspect
> https://github.com/anthropics/claude-code/issues/91870
> or resync the gh cli and see what it provides in terms of pulling information
> out of github issues
> or do more research on graphify's extensions
>
> have kb-codex-astra-advisor initiate this research and fanout to other codex
> lanes/subagents to parallelize the work and synthesize the results to another
> astra subagent

**One structural constraint, recorded because it recurs:** a codex lane runs in a
sandbox with **no browser**. Chrome and computer-use are Claude-side tools, so the
browser track cannot be delegated to a codex lane and was run by the main session.

## 4. 🔴 STANDING — keep dotfiles aware of this repo's research

> also keep updating https://github.com/ray-manaloto/dotfiles/issues/1020 or add
> new github issues to dotfiles so it is aware of our research so it does not
> have to replicate the work
> keep doing this until we have completed all the claude function hook work

**Why this is a standing obligation and not a one-off.** The inverse failure was
measured the same day: `ray-manaloto/dotfiles` already held **nine** function-hooks reports
(~2,759 lines, dated 2026-09-11/12) and a control-armed query over this repo's
11,330 prose nodes returned **zero** function-hooks material. Two repos paid for
the same research because neither told the other. This directive closes one
direction of that; the corpus ingestion of the dotfiles reports closes the other.

First discharge: `ray-manaloto/dotfiles#1020` comment `5647302470` (2026-09-12), nine measured
findings in that issue's own evidence convention.

## 5. 🔴 STANDING — monitor the upstream function-hooks surface continuously

> must always keep checking https://github.com/anthropics/claude-code/issues/91870
> and other github issues/prs/discussions for claude function hooks as it is
> experimental and must keep up to date on changes and comments others are making
> to ensure that we have all the information available or understand new
> tips/techniques/projects others are sharing

**This directive paid for itself within minutes of being given.** A smoke test of
`mise run kb-research-trackers -- anthropics/claude-code "function hooks"` surfaced a
**Community Update dated Sep 9, 2026** in the issue body that nothing in this repo
knew about. Three facts from it that bear directly on work in flight:

1. **The product name is now "Claude Mods".** *"we are going to be calling this
   functionality 'Claude Mods'. The engineering term of art 'function hook' will
   still exist as the documented implementation primitive Mods are built on."*
   This repo's `.claude/mods/` path already matches, by luck rather than design.
2. **Shipping is committed, "on the scale of weeks"**, and *"we don't anticipate
   as many breaking changes as our first week."*
3. 🔴 **`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude` is now PUBLICLY
   acknowledged for testing.** Verified control-armed against the installed
   2.1.269 binary: the flag name appears **5** times, a bogus control name **0**.

   **Consequence:** the premise that the engine cannot be probed — the basis of
   `ray-manaloto/dotfiles#1020`'s RUNTIME-UNVERIFIED banner, and of deferring behavioural arms
   to #757 — is **no longer structurally true**. Every decision resting on "we
   cannot register and fire a hook" must be re-examined.

**The gap this exposes in our tooling.** `kb-research-trackers` returns a
*snapshot*, and this directive asks for a *delta* — what changed, what is new
since last look. A search cannot answer "what comment appeared today". That is a
real capability gap, not a usage error.

## See also

- `docs/direction/2026-09-10-ray-directives.md` — the previous brief, whose §3
  ("GitHub as a source — the FOURTH time asked") this round's §5 extends from
  one-off search to continuous monitoring.
- `ray-manaloto/dotfiles#1020` — the cross-repo record §4 obliges us to keep current.

## 6. 🔴 STANDING — every question to Ray goes through an interactive prompt

> always run /grilling w interactive prompts when needing an answer from me

**Given as a correction, in the moment.** The sandbox question in §7 below was put
to Ray as prose inside a `SendUserMessage` — a ❓ heading and a recommendation,
with no `AskUserQuestion` call behind it. That is the exact shape
`clarify-before-acting.md` already forbids (*"A question in prose at the end of a
`SendUserMessage` does NOT count"*), so this is a standing rule being reinforced
after it was broken, not a new one.

What it adds over the existing rule: the **`/grilling` frame**, not just the tool.
A question is put as a numbered frontier round with a recommended answer, options
rendered, and the rest of the tree recomputed after the answer — rather than a
single prompt fired in isolation.

## 7. Codex research/execution lanes must not be sandboxed read-only

> we have discussed this before
> there is no need to have a sandbox for codex lanes/agents that are supposed to
> be exeucting code/research

**Measured cost of the current setting, same day:** lane A1 could not call `gh` at
all (`--sandbox read-only` has no network egress), so the `gh` capability track had
to be run by the main session instead; and all three lanes tripped this repo's
PreToolUse graph-first guard, whose remedy is to run a mise task — which a
read-only lane cannot do. One lane misread the remedy as a user-forbidden command.

**The tension to resolve, recorded because it is not a simple flag flip.**
`.claude/agents/kb-codex-astra-*.md` mark `--sandbox read-only` MANDATORY for a
specific reason: omitting the flag makes the lane inherit
`$CODEX_HOME/config.toml`'s `sandbox_mode`, which on this machine is
`danger-full-access` — which `do-not.md` #13 forbids for a repository lane, and
which **#767** is open about after 13 codex sessions already ran that way.

`--sandbox workspace-write -c sandbox_workspace_write.network_access=true
--add-dir "$HOME/Library/Caches"` is the documented middle (`ai-cli-invocation.md`):
workspace writes and network, without `.git`/`.codex` losing protection. Put to Ray
per §6.

## 8. 🔴 STANDING — every lane runs `kb-recall-work` BEFORE any other research

> have all background tasks/subagents use /kb-recall-work first before doing
> other research as all of these have been discussed before

**A precondition, not a checklist item.** It runs before a lane starts, and it
applies to every sub-lane a fan-out spawns, not only to the owner.

**Why, measured in the session that prompted it — THREE re-derivations in one
day**, each of research already on disk:

1. `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, the "Claude Mods" rename and the
   shipping commitment — all already in `docs/research/reports/2026-09-10-function-hooks-research.md`
   (11 mentions of the flag) and `…-github-function-hooks-examples.md` (9). **The
   session's own phase-0 `kb-recall-work` named that file and it went unopened.**
2. Both codex sandbox walls and both flags — already in
   `graphify-out/memory/query_20260901_235935_can_a_codex_lane_run_this_repo_s_uv_backed_gates.md`,
   dated 2026-09-01, including the warning about the exact `Could not resolve
   host` misread the session then committed.
3. Nine function-hooks reports in `ray-manaloto/dotfiles` that had never reached
   this graph at all.

**The usage rule that makes it work, and the defect that makes it necessary.**
Keep topics to **2-3 words**. `kb-recall-work` ANDs its stems against the
git-grep probes while `branches`/`memory` OR them, so a longer, more specific
topic silently returns `examined 3427 / matched 0`. Measured the same day, and **the figure I first published was wrong** — the
session audit re-measured rather than repeating it:

| query | stems | tracked_files | memory |
|---|---:|---:|---:|
| `"function hooks"` | 2 | **410** | 78 |
| six-word form | 6 | **69** | 176 |
| seven-word form | 7 | **49** | 304 |

I reported the six-word case as **→ 0**. It does not reproduce: the lowest
observed was **49**, never zero, rc 0 throughout. **The mechanism is confirmed;
the figure was an inherited number I repeated without re-deriving** — the exact
failure the audit existed to find, committed by the person commissioning it.

🔴 **And there is a sharper finding underneath it.** `tracked_files` NARROWS with
more stems (410 → 69 → 49) while **`memory` WIDENS** (78 → 176 → 304). The probes
inside one tool do not share semantics, so **the counts in a single run are not
comparable to each other**, and neither the output nor the docs say so.

The refusal guarantee is worth stating precisely because it reads as protection:
it holds, and it is irrelevant. The list is never empty, merely wrong — so
*"it REFUSES rather than returning an empty list"* is structurally incapable of
catching this. Needs a ticket.

**And read the report it writes** (`.agent/kb/recall/<slug>.md`), not the summary
counts. Two of the three failures above were a probe that ran correctly and an
output nobody opened.

## 9. 🔴 STANDING — scope every codex-process search to THIS project

> must only search for codex exec processes initiating from this project as
> dotfiles and other projects are also running codex processes on this mac
> ensure this is followed always going forward

**Why a bare match is wrong, not merely imprecise.** `pgrep -f 'codex exec'` and
`ps aux | grep codex` match every codex lane on the machine. The sibling
`ray-manaloto/dotfiles` runs its own, concurrently — this session had a live
`dotfiles-20260912.000` peer throughout. An unscoped search therefore:

- **counts another project's lanes as ours**, so "3 lanes still running" can be
  entirely false;
- **kills another project's work** if the count feeds a `kill`/`pkill`, which is
  unrecoverable and invisible from here;
- **waits on a process that will never finish our work**, which reads as our lane
  hanging.

**Scope by the process's working directory, not by its command line.** The
command line of a codex lane launched from dotfiles is textually identical to
ours. `lsof -a -d cwd -p <pid>` (or `ps -o pid,command` cross-checked against
each pid's cwd) is what discriminates; the pattern alone cannot.

**Prefer not searching at all.** `ListAgents` reports this session's own lanes
with their status and needs no process table — the repo's existing note is
*liveness via ListAgents, never pgrep*. A process search is a fallback for
something `ListAgents` cannot answer, and when used it must be cwd-scoped.

**Control-arm it like any other probe** (`probes-need-a-control-arm.md`): a
scoped search that returns 0 should be checked against a pid you know is ours
before "no lanes running" is believed.
