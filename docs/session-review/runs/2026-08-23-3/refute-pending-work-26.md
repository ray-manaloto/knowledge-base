# Refutation — finding 26 (lane pending-work), gh-stack skill

CLAIM: "codex/gh-stack-skill (1 commit, 9a3cab2a) is a complete, never-shipped
skill (.claude/skills/gh-stack/SKILL.md + .agents/skills/gh-stack/SKILL.md,
142 lines each) with no PR, no issue, and no copy anywhere in origin/main."

VERDICT: REFUTED on the "no issue" clause. All other clauses hold.

## Confirmed sub-claims (with control arms)

- 1 commit: `git log --oneline origin/main..codex/gh-stack-skill` -> `9a3cab2a feat(skills): add project-scoped gh-stack`
- 2 files, 142 lines each: `git show --stat 9a3cab2a` -> `142 +++` x2; `git show 9a3cab2a:<path> | wc -l` -> 142, 142.
  Both paths are the SAME blob `fbc2cd874bb2349eab7db3403e5e8c3a493d6c29`.
- No copy in KB origin/main (content-level, not path-level):
  `git ls-tree -r origin/main | grep fbc2cd87...` -> rc=1.
  CONTROL: same shape on `CLAUDE.md`'s blob `2c17cb84...` -> 1 hit. Probe discriminates.
- No copy in dotfiles origin/main:
  `git -C .../dotfiles ls-tree -r --name-only origin/main | grep -i gh-stack` -> rc=1.
  CONTROL: same command `| grep -c 'skills/'` -> 52; `grep -i stack` -> 2 hits
  (docs/research/kb/reports/agents/jdx-crate-stack.md, logging-stack-research.md).
- No PR, either repo — enumerated by HEAD REF, not by GitHub's search index:
  KB: `gh api 'repos/ray-manaloto/knowledge-base/pulls?state=all&per_page=100' --paginate --jq '.[] | "\(.number) \(.head.ref) \(.state)"' | grep -i stack` -> rc=1;
  CONTROL: same call `--jq '.[].number' | wc -l` -> 136.
  dotfiles: same shape -> rc=1; CONTROL -> 478 PRs.

## The refutation: an issue DOES exist — it is in the OTHER repo

ray-manaloto/**dotfiles** #730 "Install and validate gh-stack as a project-scoped
skill" — OPEN, created 2026-08-12T10:01:07Z (~13h after 9a3cab2a, 2026-08-12T01:47Z),
with Problem / Required work / a mermaid flowchart / 6-box Acceptance checklist,
citing https://github.com/github/gh-stack and `gh skill install`.
Probe: `gh api repos/ray-manaloto/dotfiles/issues/730 --jq '{number,title,state,created_at}'`.

The original probe's bound is REPO SCOPE, not token spelling: `gh issue list
--search "gh-stack"` resolves to the cwd repo (knowledge-base) only. The token
spelling was fine — the KB-side grep over all 345 enumerated KB issues+PRs for
`gh.stack|stacked (pr|pull)|stacking` returned only one unrelated line
(CONTROL: 'graphify' -> 678 hits, 'kb-review' -> 51 in the same file).

That the artifact is cross-repo is stated by the artifact itself: the SKILL.md
frontmatter/body says "This project adapter keeps the upstream pin while adding
the **dotfiles and knowledge-base** delivery contracts", and git carries
`refs/salvage/dotfiles-5701ee4e2c3f/heads/codex/gh-stack-skill` (9c7ff53f) plus
`.../codex/gh-stack-skill-install` (683fa64f) — i.e. the same work had dotfiles-side
branches too. A single-repo issue search cannot see the tracker for it.

## Also worth recording

- The skill is gated on a **private preview**: its Preconditions require
  `gh stack --version == 0.1.0` and "Confirm the repository is enabled for GitHub
  Stacked PRs private preview. Exit code 9 means unavailable". So "never-shipped"
  is not obviously neglect; #730's acceptance list is an unmet research contract.
- Same repo-scope bound likely applies to sibling "no GitHub issue exists" claims
  (findings 13, 16, 17, 18, 25) — none of those was re-probed here.
