# #194/#133 — the graphify-docs round, cold review, both rounds, verbatim

Promoted from `.agent/kb/review/reports/` because PR
[#197](https://github.com/ray-manaloto/knowledge-base/pull/197)'s body cites
these filenames, and `.agent/` is gitignored — a citation only one machine can
open is not a citation.

Promotion was **deferred to the branch after the round** for the third time
running, and the reason is structural rather than laziness: `docs/research/**`
is not in `review.EXEMPT_PATHS`, so committing these onto the reviewed branch
would move HEAD past its own receipt and orphan it. Same handling as `e566a9e`
(#185's reports) and `98a77a2` (#190's).

Lane: `cold:codex` (GPT-5.6 Sol via `codex exec review`, codex-cli 0.146.1,
read-only sandbox), cross-family against a Claude-written diff. Two rounds, the
`kb-review` bound. **16 findings across the two rounds, 0 blocking at HEAD.**

| file | round | reviewed | outcome |
|---|---|---|---|
| `review-5204e57-cold.md` | 1 | `5204e57` | 11 findings — 3 **P1 blocking**, 5 P2, 3 P3 |
| `review-ea6ab63-cold.md` | 2 | `ea6ab63` | 5 findings — 4 P2 (lane marked all blocking), 1 P3 |
| `review-e6eb8e3d2026ca342aa2f25308214379aab9661e-cold.md` | fix | `e6eb8e3d2026` | no lane re-ran; records what verified the fixes |

## Why these are worth keeping past the round

**Every one of round 2's four lane findings was a defect in round 1's own
fixes**, and B4 is the one to read first because it was mutation-confirmed
against the full suite: the new Step 5 `Addendum` registration could be
**deleted outright — all 23 lines — with `uv run pytest tests/` returning
rc=0**. Round 1's own remedy for F11 (`assert checked > 0`) was already
satisfied by the pre-existing `references/query.md` entry, so the aggregate
said nothing about the new registration. The control arm is what makes the
claim precise: breaking the addendum's `anchor` string instead **does** fail,
so the test discriminates on content mismatch and is blind only to deletion of
the registration.

That is this repo's `a-validator-nothing-calls-is-not-a-gate` shape arriving
through the one door `lost_addenda` does not watch — an unregistered addendum
is silently erased by the next `kb-skill-refresh`, with no test, no gate, and
no diff signal.

**Round 1's F1/F2 changed what the round shipped, by changing the remedy rather
than the finding.** Both are real defects in the regenerated `SKILL.md` Step 5
— a `graph.json` write through graphify's bundled interpreter (the invocation
`hook_guard` denies), and a `print('Report updated with community labels')` at
**indent 0** that runs on the export-refusal path, leaving `GRAPH_REPORT.md`
and `.graphify_labels.json` describing a graph that was never written. Step 4,
twenty lines earlier, has the correct shape and its own comment names the
upstream issue (#1392) that Step 5 reintroduces.

The adjudication is what mattered: the reviewer went and read the **installed
0.9.34 `skill.md` template** and found the same bytes there, control-armed
against a token known to be in that template. So these are upstream's bytes,
not a hand-edit — and this round's own central lesson is that a hand-edit to
this tree gets eaten by the next refresh. The remedy became an `ADDENDA` entry
plus an upstream report (this repo's
[#196](https://github.com/ray-manaloto/knowledge-base/issues/196)), not a fix
in place.

## The finding that came from neither lane

The extraction chunk was superseding **72 nodes of an unrelated source**
(mattpocock/skills' `CHANGELOG.md`), because `kb-extract` yields a **bare
basename** as `source_file` for any file at a clone's root — so six identities
were global names before two chunks ever competed for one.

**Every gate was green over it**: the chunk validated, the cold lane passed it
as data, `kb-build` exited 0. The only detector was `[merge]`-line arithmetic —
`+796` printed while the total rose **681** — for the third round running.
Re-measured after the fix and the rebuild: `336461 + 796 = 337257`, exactly
what the merge line reports, zero replaced. The mechanisation is
[#191](https://github.com/ray-manaloto/knowledge-base/issues/191) (the
merge-arithmetic assertion) and
[#189](https://github.com/ray-manaloto/knowledge-base/issues/189) (the
cross-chunk collision detector).

## Corrections the reports carry about themselves

- Round 1's severities are **the reviewer's adjudication, not codex's**: codex
  ranked F1/F2/F3/F4 as P1 and the rest P2; two of its weakest test findings
  were lowered to P3, and the upstream-origin context for F1/F2 was added,
  changing their remedy without changing their truth. F8, F9 and F12 are the
  reviewer's own, found while spot-checking citations — all nine codex
  citations resolved against `5204e57`.
- Round 2's A1/A2 are **mechanical verification the reviewer measured rather
  than trusted**: the `source_file` rewrite is byte-identical with the field
  blanked (796/1099/45 unchanged, 1940 occurrences both sides), and the deleted
  `graphify-docs.json` is a supersede rather than a loss (43 → 407 nodes across
  the same 8 files, zero dangling references). A lexical label probe reported
  37 of 43 labels "missing" and **its control arm passed** (6 of 43 matched), so
  the follow-up was semantic, not a shrug.
- `graphify/skill.md` → `graphify/graphify/skill.md` looks like a doubled
  prefix and is correct — the file genuinely lives at
  `sources/graphify/graphify/skill.md` in the pinned clone.

## What the lane did NOT cover, stated rather than dropped

The extraction chunk `sources/extractions/graphify-2026-08-06-docs.json`
(+20,128 lines in round 1) was never sent to codex — it is corpus data, not
judgeable behaviour, and would have blown the single-shot guard and degraded
the review of the 604 lines that are. It was verified directly instead, by two
independent routes that agree: a 13-row structural check with a **mutant
control arm** (an unresolvable edge target, an unresolvable hyperedge member, a
duplicated node id — all three detected), and `kb-validate-chunks` rc=0 read
from a file rather than a piped tail.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the
  installed 0.9.34 `install.py` (stamp write at `:229`/`:860`,
  `.claude/CLAUDE.md` at `:263`/`:629`, root `CLAUDE.md` at `:1708`,
  `_CLAUDE_MD_MARKER` at `:683`) and the `skill.md` installer template
  (`:517`), read to establish whether the Step 5 bytes were upstream-generated.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base)
  — the repository under review.
- [mattpocock/skills](https://github.com/mattpocock/skills) — the source whose
  `CHANGELOG.md` nodes the bare-basename collision was destroying.
- [jdx/hk](https://github.com/jdx/hk) — `hk.pkl` imports `Builtins.pkl` from
  v1.54.0; consulted to confirm the `newlines` builtin is live over the
  graphify skill tree.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — the
  `github` source for the `[tool.claude-code]` currency entry whose `expected`
  moved 2.1.222 → 2.1.223 in this diff.
