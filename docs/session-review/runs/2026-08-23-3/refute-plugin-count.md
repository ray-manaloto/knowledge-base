# Lane: refute-plugin-count — refutation attempt FAILED; finding CONFIRMED

FINDING UNDER TEST: `.claude/CLAUDE.md:46` says "Nine plugins are enabled in
total" while `.claude/settings.json:79-90` enables TEN.

VERDICT: **refuted = false — CONFIRMED by four independent routes.** The
original probe discriminates; the "Nine" prose is wrong under every available
reading, on this branch AND on main.

## Route 1 — mechanical count of the live file (2026-08-18)

`jq '.enabledPlugins | length' .claude/settings.json` → **10**;
`[to_entries[]|select(.value==true)]|length` → **10**; non-true → **0**;
control `has("nonexistent-control@nowhere")` → false (selection discriminates).
Entries sit at lines 80-89 inside the block at lines 79-90 (finding's cited
span, exact). SkillOpt is ABSENT from the map, not `false` — so no naive
entry-count could have inflated 9 to 10 by counting a disabled row.

## Route 2 — the same contradiction exists on main

`git show main:.claude/CLAUDE.md | grep -n 'Nine plugins'` → line 46;
`git show main:.claude/settings.json | jq '.enabledPlugins | length'` → 10.
Not an artifact of branch `docs-directive-addendum`.

## Route 3 — the 10th plugin is live, not a dead row

`codex@openai-codex` skills (`codex:rescue`, `codex:setup`,
`codex:codex-cli-runtime`, `codex:gpt-5-4-prompting`) appear in THIS session's
available-skills listing — the entry functions, it is not vestigial config.

## Route 4 — the cited budget doc itself says TEN

`.claude/rules/md-size-budgets.md:109-110`: "seven project skills plus **ten**
enabled plugins' skills (2026-08-03; it was five when this paragraph was
written, and PR #139 doubled it)". The very file CLAUDE.md:47 cites for the
count's significance disagrees with "Nine" and agrees with settings.json.
(The finding's evidence anchor ":85" is the "Plus the skill-listing budget"
section opener at line 85; the "ten" figure is at 109-110 — anchor imprecise by
~24 lines, same section, verdict unaffected.)

## Could the original probe only have produced "ten"? No — it discriminates

The identical count pipeline over history returns DIFFERENT numbers for
different states: parent of `7c9d62c4` → **11**; at `7c9d62c4` → **10**;
today → **10**. A probe that returns 11/10/10 across states is not a
one-faced coin.

## Could "Nine" be right under another denominator? No

- The sentence's own scope is "enabled in `.claude/settings.json`"
  (CLAUDE.md:39) → that count is 10.
- "Plugins surfacing skills this session" would be **8** (claude-md-management
  and mise@brentmitchell25 surface none) — a third number, still not nine.
  Recorded so nobody reads the 8 as a contradiction of the 10: different fact.

## Mechanism (git archaeology) — an inherited-number decrement

- `a2ef5d88` 2026-08-05 (PR #185) added `codex@openai-codex` → settings held 11
  (incl. skillopt, added by #139) while the prose still said "Ten" (already one
  behind; nothing bumped it for codex).
- `7c9d62c4` 2026-08-13 (PR #284, SkillOpt provenance) removed the skillopt
  entry (11→10) and edited the prose "**Ten** plugins are enabled" → "**Nine**"
  in the same diff — a decrement applied to the stale prose value instead of a
  re-count of the block being edited. `probes-need-a-control-arm.md` rule 6
  shape, in a commit. md-size-budgets.md's own warning applies verbatim: "A
  count in prose is stale the moment someone enables a plugin."

## Contradicting findings / probes: NONE found

- `docs/direction/2026-08-18-ray-directives.md` — read IN FULL. No plugin-count
  mention (codex/antigravity-cli appear only as currency roster items).
- All 7 handoffs (2026-08-17 b/c/d/e/f/g, 2026-08-18 a) — read IN FULL. No
  plugin-count mention.
- Transcript window `~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base`,
  `*.jsonl` mtime >= 2026-08-17: **14 files** (grew 14→15 mid-command once — a
  transcript being written; consistent with the settled window note).
  `grep -il 'ten plugins'` → **0 files** (nobody previously quoted/corrected the
  old wording). Controls in the same `-l` shape: `codex@openai-codex` → 2 files,
  `Nine plugins` → 1 file (this session's own transcript, which carries the
  finding text) — the pipeline can match, so the 0 is a real absence.
- The one in-repo statement that speaks to the same fact
  (md-size-budgets.md:109) AGREES with ten. Two probes of the fact disagree
  only in the sense the finding already states: the CLAUDE.md prose vs
  everything else, and the defect is in the prose.

## Fix note for the acting session (not attempted here)

One-word edit at `.claude/CLAUDE.md:46` "Nine" → "Ten" — or better, per
md-size-budgets.md's own doctrine, drop the literal and point at the
re-measure (`/doctor`, `/context`). Root CLAUDE.md is at its 200-line budget;
.claude/CLAUDE.md is 63 lines, no budget pressure.

## COVERAGE

- REACHED AND ANALYSED: `.claude/settings.json` (full, live + at `7c9d62c4` +
  parent + main), `.claude/CLAUDE.md` (full, live + main), `.claude/rules/
  md-size-budgets.md` (full), git history for both files (`-S` probes for
  "Nine plugins", "codex@openai-codex", "astral@astral-sh", "skillopt";
  `7c9d62c4` diff + stat), `docs/direction/2026-08-18-ray-directives.md`
  (full), all 7 named handoffs (full), transcript window (14 files, grep-level:
  4 probes + 2 controls).
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: the other lanes' findings (not provided to this lane); the
  CONTENT of any transcript (grep counts only, by rule); attribution of the 2
  `codex@openai-codex`-matching transcripts to specific sessions (not needed
  for the verdict).
