# Lane: contradicted — session-review sweep, scope = 096161cc-2a22-4b34-ad40-168e202bd37f.jsonl (2026-08-23)

## Finding 1 — CLAUDE.md says AGENTS.md exists; the budget rule and its own engine say it does not

- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/CLAUDE.md:9` — "`AGENTS.md` DOES exist
  (tracked, 51 lines, codex's minimum) — a sibling, not an `@import` stub, so no budget counts it."
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/md-size-budgets.md:81` —
  "This repo is **Claude-only and ships no `AGENTS.md`**, so AGM-003's 12,000-char ceiling never
  binds here."
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/md_budget.py:123` —
  the same code comment: "This repo is Claude-only and ships no AGENTS.md at all; dotfiles
  separately guarantees every AGENTS.md has its stub..."

Verified: `git ls-files AGENTS.md` → tracked; `wc -l AGENTS.md` → 51. CLAUDE.md is correct.
`md-size-budgets.md` (a `paths:`-scoped rule that fires on `**/CLAUDE.md` edits) and the shared
`md_budget.py` engine both flatly assert the opposite, in prose written for a state that no longer
holds. The functional consequence matches CLAUDE.md's own admission: `_ENTRY_RE`/closure logic
(`md_budget.py:117-124`) only budgets an `AGENTS.md` as a member of a CLAUDE.md `@import` closure —
this repo's root `CLAUDE.md` never imports it — so the file is structurally invisible to every
budget class (`eager_root`/`rule_unscoped`/`nested`/`rule_scoped`/`skill`). CLAUDE.md says this is
intentional and accepted; the rule doc and the engine comment instead assert the premise ("ships no
AGENTS.md") that would make the gap not exist. Two committed, auto-loaded docs disagree about a
fact one `git ls-files` call settles.

Cost: low functional risk today (51 lines, far under any cap even if it were counted), but it is a
live trust defect in the doc a `.claude/CLAUDE.md`-touching session is told to treat as authoritative
— and it is duplicated in the code comment, so fixing only the rule doc would leave the same false
premise sitting on the engine `dotfiles` also consumes.

## Finding 2 — a version-equality comment is currently false in the code it sits on (already filed, still live)

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/graphify_semantic_slice.py:468-471`:
```
# ADVANCED to 2.1.238 (2026-08-21) ... It now equals `_CURRENT_CLAUDE_VERSION`
# below — evidence converging with intent, not the two questions collapsing —
_ACCEPTED_CLAUDE_VERSION = "2.1.238"
```
vs. `graphify_semantic_slice.py:561`: `_CURRENT_CLAUDE_VERSION = "2.1.240"`.

The comment's claim ("now equals") is false as the file stands at this scope's HEAD
(`272d14bc3785`, branch `claude-resync-2.1.241`): 2.1.238 ≠ 2.1.240. This is not a fresh discovery —
this session filed it as **#464** and the f0659e51 commit message explicitly defers the fix "into
the next deliberate edit of the digested slice module," and the handoff's own `next_task_RAY_VERBATIM`
schedules the 2.1.240→2.1.241 resync as the very next session. Reporting it here because the
instruction (`_ACCEPTED_CLAUDE_VERSION`'s own comment, which future readers use as ground truth for
"is the corpus's accepted authority in sync with what will run next") is still live and wrong on
disk right now, and a `contradicted`-lane sweep exists precisely to catch a deferral that reads as
closed. It is scoped for a fix already, not new work — surfacing it so it isn't silently dropped if
the resync session skips straight to bumping `_CURRENT_CLAUDE_VERSION` without touching this comment.

## Finding 3 — do-not.md cites a graphify version the project no longer pins

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/do-not.md:33` (item 2):
"the banned spelling `graphify --watch` is not a real invocation at all — `--watch` occurs **0**
times in the **pinned 0.9.31** `cli.py`, against a control of **7** for `--force`."

Actual current pin: `pyproject.toml:32` → `"graphifyy[all]==0.9.48"`. The rule's own evidence
citation names a version three minor releases behind the project's real pin — an "inherited number
with no condition" of exactly the shape `probes-need-a-control-arm.md` rule 6 warns about in this
same repo's own rule set. Re-armed against the currently installed package: `grep -c -- "--watch"
.venv/lib/python3.14/site-packages/graphify/cli.py` → 0, `grep -c -- "--force"` → 7, and `elif cmd
== "watch":` still present at line 1732 — so the underlying claim still holds at 0.9.48, but the
rule's stated evidence version is stale and would mislead a reader who tried to reproduce the count
at "the pinned" version and got 0.9.48 instead of 0.9.31, unsure whether that changes the answer.
(Control also re-checked do-not.md's other cited count in the same item — "all 18 `Path.home()`
call sites" — via `grep -c "Path.home()" .venv/.../graphify/install.py` → 18, still accurate at
0.9.48, so only the `--watch` paragraph's version label is stale, not the whole item.)

## Coverage

**Reached and analysed:** the settled-context JSON in full; the current HEAD's diff since the
prior receipted commit (`git show f0659e51`); `docs/agents/graphify-semantic-corpus.md` and
`tests/test_graphify_semantic_corpus.py` changes from this session's fix commit; the `.mcp.json` /
`sources/REGISTRY.md` / `docs/graphify-reference.md` treatment of the newly-registered `repowise`
MCP server (no contradiction found — it is omitted from `CLAUDE.md`'s MCP invariant but documented
elsewhere, judged a completeness gap not a contradiction); `.claude/skills/kb-review/SKILL.md` §4/§4a
fix-round mechanism against how this session actually used it for `d85f2835` (judged a legitimate,
transparently-logged, Ray-authorized use, not a contradiction — the report at
`review-d85f2835...-cold.md` says explicitly "No lane re-ran," so it does not misrepresent itself);
`do-not.md` items 1–2 spot-checked against the installed 0.9.48 `graphify` package; `AGENTS.md` /
`CLAUDE.md` / `md-size-budgets.md` / `md_budget.py` AGENTS.md-existence claims (Finding 1);
`graphify_semantic_slice.py` version constants (Finding 2); zero-bash-logic claim re-verified
(`find . -name "*.sh"` outside `sources/`/`.venv`/`graphify-out`/`raw` → 0 hits, control: `sources/`
does have vendored `.sh` files, so the probe discriminates); mise.toml spot-checked for 15 named
tasks (`kb-distill`, `kb-arms`, `hk-test`, etc.) — all present; `.github/` absence confirmed
(matches `gh-cli-watch.md`'s claim); `AGENTS.md` line count (51) matches CLAUDE.md's claim exactly;
a suspected Python-2-style `except A, B:` "bug" at `graphify_semantic_corpus.py:2185` was probed and
refuted — PEP 758 (Python 3.14) makes it valid, matching this session's own PR-reply refutation of
graphify-labs' identical false-positive finding; `ast.parse` on the whole file confirmed no syntax
error.

**Opened but not finished analysing:** the review-lane fix-round mechanism's general fit for
"HEAD moved past an already-receipted point" scenarios beyond this one instance — whether
`kb_setup.review.EXEMPT_PATHS` should have covered a one-line `.claude/CLAUDE.md` config change
(it currently only exempts `graphify-out/memory/**` and `docs/goals/README.md`) was not checked
against the module source, only inferred from the fix-round report's own text; the full 22-file
`.claude/rules/` set and 9-plugin `.claude/skills/` tree were not each cross-read against their
own described behaviour — only the files that surfaced from this session's actual work were
checked (md-size-budgets.md, do-not.md, gh-cli-watch.md, kb-review/SKILL.md, zero-bash-logic.md);
`hk.pkl` itself was not read line-by-line against `zero-bash-logic.md`'s claims about it.

**Never reached:** `.claude/skills/kb-curator`, `goal-engineering`, `tool-currency`,
`orchestrator-routing`, `clear-prep` SKILL.md bodies (only headings/sections directly referenced by
the transcript's own reads were checked); the 4 stale worktrees / many stale local branches named
in the handoff (out of scope for a contradiction sweep, not a doc-vs-code question); the ~58
needs-triage / 41+25 not-triaged issue backlog; `docs/goals/` pair completeness (whether every
`*-goal.md` has a `*-rider.md` and vice versa) was not audited; `currency.toml` vs the tool-currency
skill's described six-step loop was not cross-checked; the antigravity/fable-orchestrator plugin
config claims in `.claude/CLAUDE.md` (lane assignments, effort settings) were not verified against
the plugins' own installed source.

## GitHub repos touched

_None._ (No external repo source/docs were fetched for this analysis; all evidence is from this
repo's own tracked files, its `.venv` install, and its committed git history.)
