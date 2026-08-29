---
type: "query"
date: "2026-08-29T22:35:33.523023+00:00"
question: "Which GitHub repo tracks issues for work that changes code in a sibling repo like claude-code-marketplace?"
contributor: "graphify"
outcome: "corrected"
correction: "# Wrong assumption: issue location follows code location\n\nWhile implementing #573 (which changes code in the sibling\n`claude-code-marketplace` repo), the architect ran `gh issue view 573` and\n`gh issue view 568` with no `-R` flag while `cwd` still happened to be inside\n`knowledge-base` — got the right answer by accident, then LATER assumed,\nwithout re-checking, that the packaging follow-up ticket (#587) must live in\nwhichever repo the code change was landing in (`claude-code-marketplace`).\n`gh issue comment 587` against that repo 404'd.\n\n**The actual rule, already documented in this repo's own\n`.claude/CLAUDE.md`** (\"Issue tracker\" section): ALL work across this whole\nmulti-repo project is tracked in `ray-manaloto/knowledge-base`'s GitHub\nIssues, regardless of which repo the resulting code change lands in. A repo\nwhose code changes are tracked elsewhere is not itself running a separate\nissue tracker just because it has its own `gh issue` namespace available.\n\n**How to apply:** before commenting on or closing a numbered issue, confirm\nwhich repo actually holds it — `gh issue view <n> -R ray-manaloto/knowledge-base`\nfirst, in this project, every time — rather than inferring the tracker from\nwhere the code lives. A 404 caught it cheaply here; in a repo where the\nnumber ALSO happens to resolve to a different, unrelated issue in the\n\"wrong\" tracker, the same assumption would silently post to the wrong place\nwith no error at all.\n"
---

# Q: Which GitHub repo tracks issues for work that changes code in a sibling repo like claude-code-marketplace?

## Answer

# #573 — Marketplace structure: plugins under plugins/, and the bin/ decision

Shipped as `ray-manaloto/claude-code-marketplace#10` (merged to main at
`6b5b092`), implemented entirely by `codex-implementer` (xhigh) per explicit
user instruction to use only codex lanes for implementation, cold-reviewed by
`grok-reviewer` (cross-family), pre-dispatch sanity-checked by `fable-advisor`.

**What shipped:**
1. `aggregated-research/` moved to `plugins/aggregated-research/` via pure
   git-mv renames (zero content diff on any moved file, verified both by the
   architect and by the cold reviewer via `git diff -M --stat`).
2. Every hardcoded old-path reference fixed across
   `.claude-plugin/marketplace.json`, `README.md`, `ci/acceptance.sh`, root
   `mise.toml` — including one the spec's known-list didn't name
   (`README.md`'s Acceptance section), caught by the lane's own
   grep-for-missed-paths verification step.
3. The `bin/` wrapper question answered with a real measured prototype
   (built in `/tmp`, throwaway, declared a spike, not committed) comparing
   `mise generate install-script`/`task-stubs` and a no-wrapper approach
   (modeled on the already-depended-on `context7` plugin, which ships neither
   `bin/` nor `hooks/`) against the hand-written `bin/mise-env`.
   **Decision: keep the status quo.** Neither candidate can express
   `bin/mise-env`'s runtime confinement of `$CLAUDE_PLUGIN_DATA` — both
   mise generators bake config paths in at *generation* time rather than
   reading env at *invocation* time, and dropping the wrapper also breaks
   env-scoping for the LSP server (`.lsp.json` has no channel to inject env
   at all). Recorded at
   `plugins/aggregated-research/docs/bin-wrapper-decision.md` and posted to
   issue #587 (the packaging ticket that inherits the decision).
4. Container acceptance CI green — verified via `gh pr checks --json
   name,bucket,state`, not the `--watch` exit code alone (per this repo's own
   verify-before-advancing discipline: `--watch` has reported 0 prematurely
   before).

**Process notes:**
- `fable-advisor`'s pre-dispatch review caught two real amendments before
  codex ever saw the spec: a broken verification-grep filter (assumed GNU
  grep's `./` prefix — would have made "empty = clean" unreachable and told
  the lane to keep "fixing" already-correct files) and a missing branch
  (codex's sandbox cannot create git refs, so the architect had to branch
  BEFORE dispatch, not describe branching as an assumption in the spec).
- Cold review (`grok-reviewer`) found one real, low-severity, cited
  arithmetic error in the decision doc (claimed "3 of 6" vars overlap;
  the doc's own supporting list only named 2) — confirmed by the reviewer
  independently re-running the generator, fixed inline by the architect as
  a trivial one-line correction rather than round-tripping back to codex.
- codex-implementer settled cleanly this round WITH a structured report and
  a clean git state, unlike the prior two rounds' idle-with-no-report
  pattern — no repeat of that finding this time.


## Outcome

- Signal: corrected
- Correction: # Wrong assumption: issue location follows code location

While implementing #573 (which changes code in the sibling
`claude-code-marketplace` repo), the architect ran `gh issue view 573` and
`gh issue view 568` with no `-R` flag while `cwd` still happened to be inside
`knowledge-base` — got the right answer by accident, then LATER assumed,
without re-checking, that the packaging follow-up ticket (#587) must live in
whichever repo the code change was landing in (`claude-code-marketplace`).
`gh issue comment 587` against that repo 404'd.

**The actual rule, already documented in this repo's own
`.claude/CLAUDE.md`** ("Issue tracker" section): ALL work across this whole
multi-repo project is tracked in `ray-manaloto/knowledge-base`'s GitHub
Issues, regardless of which repo the resulting code change lands in. A repo
whose code changes are tracked elsewhere is not itself running a separate
issue tracker just because it has its own `gh issue` namespace available.

**How to apply:** before commenting on or closing a numbered issue, confirm
which repo actually holds it — `gh issue view <n> -R ray-manaloto/knowledge-base`
first, in this project, every time — rather than inferring the tracker from
where the code lives. A 404 caught it cheaply here; in a repo where the
number ALSO happens to resolve to a different, unrelated issue in the
"wrong" tracker, the same assumption would silently post to the wrong place
with no error at all.
