# 2026-09-12 — the function-hooks round, verbatim agent reports

Sixteen findings-bearing reports from session `kb-20260911.004`, promoted from
`.agent/kb/reports/agents/` **verbatim**. `.agent/` is gitignored and dies with a
fresh clone or any `git clean -xdf`; these are cited by tracked work, so they live
here instead (`agent-report-persistence.md` rule 1b).

**Why this directory exists at all.** The round's own audit inventoried **147
distinct findings** across these reports and found **20 with a durable home and
127 without**. That ratio is the reason for the promotion, not tidiness.

## What is here

| report | what it settles |
|---|---|
| `graph-first-hook.md` | **The function-hooks migration is VIABLE.** `#92533` is specific to `tool.call` on Bash; `tool.check` on Bash fires, denies with our own reason, and leaves worktree isolation intact — four arms on 2.1.269. Verdict: viable, **not worth building today**. |
| `fh-synthesis.md` | `next.origin` is **host-set and unforgeable** (`claude-code.d.ts:3841-3846`), so tier-based authority is real enforcement. Reconciles `deny` vs `next(e)`. |
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

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — function hooks, `#91870`, `#92533`, the `mods/` tree.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — PRs #3073, #3311, #2392; the ingest classifier.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork, the openai-cli patch.
- [chaseai-yt/claudex-loop](https://github.com/chaseai-yt/claudex-loop) — mined for codex transport technique.
- [openai/codex](https://github.com/openai/codex) — sandbox, permission profiles, `--output-schema`.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the cross-repo record, `#1020`.
