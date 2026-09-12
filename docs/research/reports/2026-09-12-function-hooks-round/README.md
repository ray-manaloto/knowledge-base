# 2026-09-12 — the function-hooks round, verbatim agent reports

Findings-bearing reports from session `kb-20260911.004`, promoted from
`.agent/kb/reports/agents/` **verbatim**. `.agent/` is gitignored and dies with a
fresh clone or any `git clean -xdf`; these are cited by tracked work, so they live
here instead (`agent-report-persistence.md` rule 1b).

**Count them, do not quote a number.** This line said "Sixteen" while nineteen
files sat beside it, and then twenty once `session-audit-a-code.md` was promoted
on 2026-09-12. `ls docs/research/reports/2026-09-12-function-hooks-round/*.md | wc -l`.

**Why this directory exists at all.** The round's own audit inventoried **147
distinct findings** across these reports and found **20 with a durable home and
127 without**. That ratio is the reason for the promotion, not tidiness.

## What is here

| report | what it settles |
|---|---|
| `graph-first-hook.md` | **The function-hooks migration is VIABLE.** `#92533` is specific to `tool.call` on Bash; `tool.check` on Bash fires, denies with our own reason, and leaves worktree isolation intact — four arms on 2.1.269. Verdict: viable, **not worth building today**. |
| `fh-synthesis.md` | `next.origin` is **host-set** at `claude-code.d.ts:3841-3846`, so tier-based authority is real enforcement. Reconciles `deny` vs `next(e)`. ⚠️ **"Unforgeable" is the TYPE-LEVEL claim only** — `session-audit-b-claims.md:416` downgraded it: *"An adversarial 2.1.269 transport-forgery arm was not run, so the stronger runtime word 'unforgeable' remains UNVERIFIABLE beyond the exposed contract."* That caveat was dropped as the claim propagated into this summary; restored 2026-09-12. |
| `fh-source-sweep.md` | The 22-asset inventory of `anthropics/claude-code#91870`, the `_detect_url_type` classifier defect, and the `mods/` tree at v2.1.269. |
| `graphify-extraction-owner.md` | Fork currency (0.9.59 is a **code** change), `GRAPHIFY_OUT` and the missing build lock, the 31 pin sites. **Take all 873 lines — an earlier 494-line prefix is not the report.** |
| `agentsview-research.md` | **The 283 "lost" sessions are in the archive**, control-armed. Zero tombstones, so reachability is luck. 1,263 unread subagent transcripts. |
| `scratch-isolation-review.md` | **Every harness-derived identity a lane can read about itself is shared with concurrent siblings** — scratchpad path, `$TMPDIR`, `$CLAUDE_CODE_SESSION_ID`, measured with an echo control. 13 collision classes. |
| `advisor-durability.md` | `kb-advisor` has **no `Write`** — the work-memory note recommending it as the durable substitute was wrong. `#520` already owns this. |
| `claudex-loop-mining.md` · `claudex-loop-synthesis.md` | Four ADOPT NOW items; their validator checks **form, not evidence quality**, and would have caught none of our three historical failures. |
| `extract-research-lead.md` · `extract-research-a-live.md` | `gh` capability for issue extraction; durable `user-attachments` URLs download unauthenticated. |
| `session-audit-{b,c,d,e}-*.md` | The round's self-audit: claims re-derived, the 147/20/127 ledger, unmeasured numbers, missed prior art. |
| `754-advisor-verdict.md` | The #754 G01 design consult. |

## Read these first, and their caveats

- **`session-audit-d-vague.md` is PARTIAL** — its lane was ended at a 2400s bound
  (`rc 124`). It wrote incrementally so every section reached disk, but its sweep
  may be incomplete. Do not read its silence as coverage.
- **`session-audit-c-accounted.md` flags itself as unhomed** and asks to be
  promoted without renumbering. This promotion honours that.
- Several reports carry **post-publication addenda** correcting their own earlier
  claims. Read to the end; the correction is usually the finding.

## 🔴 A correction that was queued against these files and must NOT be applied

Added 2026-09-12 by the cold session review of `3b921834`.

That review's report-facts lane graded the citation `claude-code.d.ts:3841-3846`
— the `next.origin` anchor above — as **"wrong by ~500 lines"**, and recommended
editing four tracked files to "fix" it: this README at `:17`, `fh-synthesis.md:33`,
`graphify-extraction-owner.md:858`, and the session handoff.

**The citation is CORRECT. Do not apply that correction.**

The lane measured `sources/media/claude-code-function-hooks-types.d.ts`, the
**vendored 2.1.267 snapshot, 7,966 lines**. The citation is to
`.claude/types/claude-code.d.ts`, the file `/plugin-types` **generates** and which
is never committed — **9,156 lines** under an isolated `HOME`. The synthesis lane
regenerated it live and read `sed -n '3838,3850p'`: lines 3841-3846 are exactly
the `next.origin` doc-comment.

The same text sits at vendored `:3336-3343` and generated `:3841-3846`. The
**+505-line offset the lane measured is the distance between two files, not the
size of an error** — it is the signature of a *correct* citation to the other one.

This is `change-the-route.md` rule 4 in its purest form: **a bare basename is
ambiguous across copies and resolves silently to the wrong one.** It is worth
leaving on the record because the lane that made the error was the lane whose
whole job was catching exactly this, and because a false correction applied to
four correct citations is more expensive than the uncorrected claim would have
been.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — function hooks, `#91870`, `#92533`, the `mods/` tree.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — PRs #3073, #3311, #2392; the ingest classifier.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork, the openai-cli patch.
- [chaseai-yt/claudex-loop](https://github.com/chaseai-yt/claudex-loop) — mined for codex transport technique.
- [openai/codex](https://github.com/openai/codex) — sandbox, permission profiles, `--output-schema`.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the cross-repo record, `#1020`.
