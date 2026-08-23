# Refutation attempt: finding #12 (CLAUDE.md vs md-size-budgets / md_budget "ships no AGENTS.md")

VERDICT: NOT REFUTED. Confirmed, and WIDER than reported (5 sites, not 2).

## Probes
- `git ls-files AGENTS.md` -> `AGENTS.md` (tracked). `wc -l AGENTS.md` -> 51.
- `sed -n '1,14p' CLAUDE.md` line 9: "`AGENTS.md` DOES exist (tracked, 51 lines, codex's minimum) — a sibling, not an `@import` stub, so no budget counts it."
- `grep -n "ships no" .claude/rules/md-size-budgets.md python/src/kb_setup/md_budget.py`
  - md_budget.py:123 `# wrong file. This repo is Claude-only and ships no AGENTS.md at all; dotfiles`
  - md-size-budgets.md:81 `This repo is **Claude-only and ships no `AGENTS.md`**, so AGM-003's 12,000-char`
  Both cited line numbers are EXACT.

## Why it went stale (blame)
- md_budget.py:123 and md-size-budgets.md:81 both written `3bb49a8cd` 2026-07-24.
- AGENTS.md first ADDED `c70f0f81` 2026-08-13 ("Upgrade Graphify to 0.9.42 (#291)").
- CLAUDE.md:9 written `37f6a1c57` 2026-08-17.
The comment predates the file by 20 days; CLAUDE.md is the corrected statement.

## The finding UNDERSTATES the blast radius — 3 more sites
- python/src/kb_setup/skill_lint.py:61 `#: `AGENTS.md`, a file this repo deliberately does not have.`
- tests/test_md_budget.py:12 "root `CLAUDE.md`, no `AGENTS.md`"
- (see report body for tests/AGENTS.md status)

## Refutation avenues tried and closed
1. Line numbers wrong -> no, exact.
2. "This repo" ambiguous in the SHARED engine (dotfiles consumes it) -> no: the same
   sentence contrasts "dotfiles separately guarantees...", so "This repo" = knowledge-base.
3. AGENTS.md derived/untracked so "not shipped" -> no, `git ls-files` tracks it.
4. Behaviour is correct, only prose is stale -> TRUE but does not refute: the finding
   is a documentation contradiction, and `md_budget.classify("AGENTS.md") is None`
   (tests/test_md_budget.py:90) is the correct BEHAVIOUR regardless.

## One sub-claim IS inaccurate (partial)
The finding calls both "auto-loaded instruction files". `.claude/rules/md-size-budgets.md`
carries `paths:` frontmatter (hk.pkl, **/CLAUDE.md, .claude/rules/*.md,
.claude/skills/**/SKILL.md) -> it is rule_scoped, NOT eager. Control: `do-not.md` has
no frontmatter and DOES appear in this session's eager rule set; md-size-budgets.md does
not. It still loads whenever CLAUDE.md is read, so the contradiction is still reachable.
And md_budget.py is code, not an instruction file at all.

## Probe hygiene note
An unquoted `--include=*.md` was eaten by zsh ("no matches found") — the exact
false-zero shape the brief warns about. Re-run quoted.

## tests/AGENTS.md status (settled)
`ls -la tests/AGENTS.md` -> "No such file or directory".
Control arm for that negative: `git ls-files '*AGENTS.md'` returns exactly `AGENTS.md`
(a file I KNOW is present) and no `tests/AGENTS.md` — so the probe discriminates.
`python/src/kb_setup/eval_cases.py:245` already documents tests/AGENTS.md as
"not there", so those references are internally consistent. Only the ROOT
AGENTS.md exists, and it is the one all three stale sites deny.

## Full stale-site list at HEAD (d85f2835)
1. `.claude/rules/md-size-budgets.md:81`  — "ships no `AGENTS.md`"
2. `python/src/kb_setup/md_budget.py:123` — "ships no AGENTS.md at all"
3. `python/src/kb_setup/skill_lint.py:61` — "a file this repo deliberately does not have"
4. `tests/test_md_budget.py:12`           — "this repo is Claude-only (... no `AGENTS.md`)"
vs `CLAUDE.md:9` — "`AGENTS.md` DOES exist (tracked, 51 lines, codex's minimum)".

AGENTS.md head confirms it is a real instruction file ("# Knowledge Base Agent
Instructions ... the minimum required for Codex and other Agent Skills clients"),
not a stub — matching CLAUDE.md's description, not the four denials.

## Cross-check against the other 36 findings
None contradicts this one. #14 (do-not.md cites "the pinned 0.9.31" while
pyproject.toml pins 0.9.48) and #11 (CLAUDE.md's stale 499 MB) are the SAME CLASS
— a committed instruction file carrying a fact that a later commit falsified —
which corroborates rather than disputes.
