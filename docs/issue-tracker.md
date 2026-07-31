# Issue tracker: GitHub

Issues for this repo live as GitHub issues on
[`ray-manaloto/knowledge-base`](https://github.com/ray-manaloto/knowledge-base). Use the `gh` CLI
for all operations — it infers the repo from `git remote -v` when run inside a clone.

Consumed by `/mattpocock-skills:wayfinder`, `to-spec`, `to-tickets`, `triage`, and `code-review`.
Without this file those skills fall back to a local-markdown tracker
(`wayfinder` SKILL.md:25, *"If no tracker has been provided, default to the local-markdown
tracker"*), which would plan away from the GitHub issues this repo actually uses.

> **Why this file is not at `docs/agents/issue-tracker.md`**: `agnix` treats any
> `**/agents/*.md` as an agent definition needing YAML frontmatter. Probed on 2026-07-30 with
> the same three-line file at both paths — `docs/agents/issue-tracker.md` →
> `error: Agent file must have YAML frontmatter`, rc=1; `docs/issue-tracker.md` → clean. The
> probe discriminates on path alone.
>
> ⚠️ **That relocation has a real cost, and it is not only `setup` that cares.**
> `code-review/SKILL.md` **reads the hardcoded path twice** — line 13 (*"run
> `/setup-matt-pocock-skills` if `docs/agents/issue-tracker.md` is missing"*) and line 29
> (*"fetch via the workflow in `docs/agents/issue-tracker.md`"*). So
> `/mattpocock-skills:code-review` **will not find this file** and will behave as though no
> tracker were configured. Verified against the installed plugin, control-armed: `docs/agents`
> appears in exactly two skills (`setup-matt-pocock-skills`, `code-review`) while the looser
> term `issue tracker` hits eight files, so the grep discriminates.
>
> Tolerated deliberately: **`kb-review` is this repo's review gate**, not
> `mattpocock-skills:code-review`. `wayfinder` is unaffected — it never names the path, asking
> only for "the tracker doc", which `.claude/CLAUDE.md` now points at. If someone does want
> `code-review` working here, hand it this path explicitly rather than moving the file into
> `docs/agents/`, which `mise run lint-docs` rejects.
>
> **Do not run `/setup-matt-pocock-skills`** to generate this — it writes the rejected path and
> also edits the root `CLAUDE.md`.

## PRs are not opened with `gh`

Unlike the sibling dotfiles repo, this repo's PreToolUse guard (`kb_setup.hook_guard`) redirects
**only `graphify` invocations** — it does not intercept `gh`. The rule still stands:

| Instead of | Use |
|---|---|
| `gh pr create` | **`mise run kb-ship`** — checks the `kb-review` receipt, then runs `lint`, `test`, `brain-audit`, `eval` before pushing |
| `gh pr merge` | **`mise run kb-land -- <PR#>`** |

`gh issue *` commands are unguarded — everything below is safe to run as written.
See `.claude/rules/mise-tasks-only.md`.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line
  bodies.
- **Read an issue**: `gh issue view <number> --comments`.
- **List issues**: `gh issue list --state open --limit 200 --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`
  with `--label` / `--state` filters.

  ⚠️ **`--limit` is not optional, and raising it does not remove the bound —
  it moves it.** `gh issue list` defaults to **30** and truncates silently: no
  warning, no count, just a short list that looks complete. This repo is already
  past #90, so the default would hide issues on any unfiltered listing. But
  `--limit 200` truncates silently at 200 in exactly the same way, so treating a
  bigger number as a fix reproduces the failure one order of magnitude later.

  **Read the returned count.** If it equals your `--limit`, assume the list is
  truncated and raise it — a full page is indistinguishable from a complete
  answer, which is `.claude/rules/probes-need-a-control-arm.md` rule 3 ("a bound
  that turns absent into unreachable") in its cheapest form.
- **Comment**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

### ⚠️ A merged PR does NOT close the issue it resolved

`mise run kb-ship` builds the PR body itself and emits no `Closes #N` / `Fixes #N` keyword, so
GitHub's auto-close never fires. Issue #76 stayed open through the merge of PR #83 for exactly this
reason. **Close the issue by hand after landing**, or add the keyword to the PR body before merge.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo starts treating external PRs as
feature requests; `/triage` reads this flag.)_ This is a solo corpus repo — PRs here are our own
work and `mise run kb-ship` / `kb-land` already gate them.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either — resolve with
`gh pr view 42`, falling back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog
  body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues
  endpoint). Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed,
  assign to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**. Add an edge with
  `gh api --method POST repos/ray-manaloto/knowledge-base/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`,
  where `<blocker-db-id>` is the blocker's numeric **database id**
  (`gh api repos/ray-manaloto/knowledge-base/issues/<n> --jq .id` — **not** the `#number` or
  `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only). A ticket
  is unblocked when every blocker is closed.
- **Frontier query**: the open, unblocked, unclaimed children, in map order. A bare
  `gh issue list --state open` is **wrong here** — it is repo-wide, carries no blocker or
  assignee data, and would happily hand back an unrelated issue. Walk the map's sub-issues
  instead:

  ```bash
  R=ray-manaloto/knowledge-base; MAP=<map issue number>
  for n in $(gh api --paginate "repos/$R/issues/$MAP/sub_issues" \
               --jq '.[] | select(.state=="open") | .number'); do
    gh api "repos/$R/issues/$n" \
      --jq 'select((.issue_dependencies_summary.blocked_by // 0) == 0 and (.assignees|length) == 0)
            | "\(.number)\t\(.title)"'
  done
  ```

  **`--paginate` is load-bearing** for the same reason `--limit` is above: the REST
  endpoint pages, so a map with more children than one page would silently drop the
  tail from the frontier — and a short frontier looks exactly like a nearly-finished
  map.

  Verified against map #85 on 2026-07-30, and it **discriminates**: 5 open children in,
  4 out — it correctly withheld the one ticket carrying 4 blockers. A filter that
  returned all 5 would have been a no-op wearing a filter's clothes.
- **Claim**: `gh issue edit <n> --add-assignee @me` — the session's first write.

  ⚠️ **This is not atomic, and against your OWN parallel sessions the assignee cannot
  detect a race at all.** Two sessions can both pass the frontier check and both assign.
  Re-reading the assignees does not save you: this is a solo repo, so every session
  resolves `@me` to the **same account** — the second claim is a no-op and the field
  looks identical either way. An assignee marks a ticket as taken by *a person*; it
  cannot distinguish two sessions of that person.

  So the real control is upstream of the tooling, and wayfinder states it: *"never
  resolve more than one ticket per session"*, and the user chooses which unblocked
  tickets to run in parallel. **Do not run two sessions on the same ticket** — nothing
  here will stop you. If you need a machine-checkable claim, post a comment carrying
  the session id and read comments rather than assignees; that is not set up today and
  is deliberately not being invented for a solo repo.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a
  context pointer to the map's Decisions-so-far.

### Prerequisites — probed live on this repo, 2026-07-30

`/wayfinder` needs three things from GitHub. Each was probed against
`ray-manaloto/knowledge-base` — **not** inherited from dotfiles' equivalent table:

| Prerequisite | Probe | Result |
|---|---|---|
| `wayfinder:*` labels | `gh label list` | **were absent, now created** — `map`, `research`, `prototype`, `grilling`, `task` (colours matched to dotfiles) |
| **Sub-issues** (child tickets) | `gh api repos/ray-manaloto/knowledge-base/issues/84/sub_issues` | `[]` — endpoint live, feature enabled ⇒ use the sub-issue path |
| **Issue dependencies** (blocking) | `gh api …/issues/84 --jq .issue_dependencies_summary` | `{"blocked_by":0,"blocking":0,"total_blocked_by":0,"total_blocking":0}` — available ⇒ use native dependencies |

**The sub-issues probe carries its control arm**: the same endpoint on a nonexistent issue
(`issues/99999/sub_issues`) returns `404 Not Found`, so the `[]` on issue 84 is a real empty list
and not an endpoint that answers emptily for everything.

Upstream's two documented fallbacks — task-list children and `Blocked by: #<n>` body lines — are
therefore **unnecessary here** and are deliberately omitted above; reintroduce them only if a probe
shows the native mechanism has gone away.

**The db-id gotcha is real here too** — worked example on this repo:
`gh api repos/ray-manaloto/knowledge-base/issues/84 --jq .id` → `5025038694`, whereas its `node_id`
is `I_kwDOTgoLOs8AAAABK4QBZg` and its number is `84`. The dependencies endpoint wants
**`5025038694`**.

## How this relates to the existing practice

This repo already runs multi-round efforts two other ways, and wayfinder retires neither:

- **`docs/goals/`** — committed goal+rider pairs, one round of agent work each. That is a
  *finish line* for a bounded round.
- **GitHub issues as a backlog** — #81/#82/#84 and friends are *work to do*.

Wayfinder's map is an index of *decisions made*, with the unknown written down explicitly (its
"Not yet specified" section). Different axis from both; they coexist.

## See also

- `.claude/rules/mise-tasks-only.md` — why `kb-ship`/`kb-land` rather than raw `gh pr`.
- `.claude/skills/goal-engineering/SKILL.md` — the goal+rider pairs under `docs/goals/`.
- `.claude/skills/kb-review/SKILL.md` — the review receipt `kb-ship` gates on.
