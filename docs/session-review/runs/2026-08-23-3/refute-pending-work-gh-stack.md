# Refutation: "codex/gh-stack-skill is genuinely unlanded pending work with no tracking issue"

Lane: pending-work. Verdict: **REFUTED** (the second conjunct is false).

## What holds

- `git merge-base --is-ancestor 9a3cab2a origin/main` -> `NOT ancestor`
- `git ls-tree -r --name-only origin/main | grep -i 'gh.stack'` -> rc=1 (0 hits)
  CONTROL, same shape: `... | grep -i 'kb-curator'` -> 4 paths. Probe discriminates.
- `gh pr list --state all --limit 300 --json headRefName ... select(test("gh.stack"))` -> empty
  CONTROL: same filter on `salvage|codex` -> PRs 325, 312, 311, 310, 309, 308, 307, 291, 288, 286.
  So: genuinely unlanded, no PR. That half is true.

## What is false: "no tracking issue"

The original probe was `gh issue list --search 'gh-stack'` with NO `--repo`, so it
searched only the cwd repo (`gh repo view --json nameWithOwner` -> ray-manaloto/knowledge-base).
That is a repo bound, and it is the whole finding.

Exact same command shape, bound lifted:

```
$ gh issue list --repo ray-manaloto/dotfiles --state all --limit 500 --search 'gh-stack' \
    --json number,title --jq '.[]|[.number,.title]|@tsv'
730     Install and validate gh-stack as a project-scoped skill

$ gh issue view 730 --repo ray-manaloto/dotfiles --json number,title,state,url,createdAt
730  OPEN  2026-08-12T10:01:07Z  Install and validate gh-stack as a project-scoped skill
     https://github.com/ray-manaloto/dotfiles/issues/730
```

Issue #730 is OPEN, created 2026-08-12T10:01:07Z — the day after commit 9a3cab2a
(2026-08-11T20:47:52-0500). Its acceptance criteria name exactly what the branch does:
"Callable Codex and Claude project surfaces are explicit and parity-checked" vs the
commit adding BOTH `.agents/skills/gh-stack/SKILL.md` and `.claude/skills/gh-stack/SKILL.md`.

## This was already recorded, and the lane re-derived past it

docs/session-review/runs/2026-08-18-2/handoff-c-before-reconcile-fix.md:99-102 (verbatim):

    - **Repo-scoped `gh issue list --search` is a bound.** It missed dotfiles#730
      (tracks the gh-stack skill) because the search only sees the cwd repo. Five other
      "no issue exists" claims about cross-repo/salvage work were never probed with
      `--repo ray-manaloto/dotfiles` — treat every such negative as unarmed.

## Class defect

Findings 24, 25, 26 in the same lane make the same "no tracking issue" claim about
cross-repo/salvage work with the same repo-bound probe. None should be believed
without a `--repo ray-manaloto/dotfiles` arm.
