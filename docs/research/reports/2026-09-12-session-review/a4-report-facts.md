# Review lane a4-report-facts — fact-checking the 19 promoted research reports

Commit examined: `c1d8afb8cf686a6e39f186debb0e9499d794a5dc` (branch `feat/754-plugin-types-contract`)
Directory: `docs/research/reports/2026-09-12-function-hooks-round/`

## Inventory (line counts, `wc -l`)

| File | Lines | Names commit examined? |
|---|---|---|
| fh-source-sweep.md | 1463 | HEAD `4cdd8bfb` (line 4) |
| graphify-extraction-owner.md | 873 | no explicit commit line found; dated/anchored via other reports citing it against `4cdd8bfb` |
| scratch-isolation-review.md | 830 | yes — `4cdd8bfb` (line 5) |
| session-audit-synthesis.md | 747 | yes — `4cdd8bfb` (line 3) |
| graph-first-hook.md | 707 | no explicit top-level commit line; scoped to a throwaway scratch repo (line 99), not this repo's HEAD |
| agentsview-research.md | 622 | no explicit repo-commit line (its subject is an external DB/tool, not this repo's tree) |
| session-audit-c-accounted.md | 606 | yes — `4cdd8bfb` (lines 3-4) |
| session-audit-b-claims.md | 589 | yes — `4cdd8bfb` (line 3) |
| advisor-durability.md | 587 | cites a different commit, `aef74afe…` (line 174) — a #754-consult artifact, not this round's audit anchor; not necessarily wrong, but worth flagging since it differs from every session-audit-*'s anchor |
| claudex-loop-mining.md | 563 | yes — pins the STUDIED repo `chaseai-yt/claudex-loop` at `8cf5e2c1…` (line 5); does not separately state this repo's own HEAD |
| extract-research-a-live.md | 532 | no explicit commit line in the first two hits; subject is GitHub API state, not this repo's tree |
| fh-synthesis.md | 502 | yes — `4cdd8bfb` (line 3) |
| extract-research-lead.md | 417 | no explicit commit line in the first hits |
| session-audit-e-missed.md | 317 | yes — `4cdd8bfb` (line 3) |
| 754-advisor-verdict.md | 221 | no explicit commit line in the first hits |
| session-audit-lead-verdict.md | 213 | yes — `4cdd8bfb` (line 3) |
| session-audit-d-vague.md | 165 | yes — `4cdd8bfb` (line 3); KNOWN PARTIAL, rc 124 at a 2400s bound (confirmed below) |
| claudex-loop-synthesis.md | 137 | cites BOTH `4cdd8bfbc3a2d7919adc8057c34afd487813fa26` (this repo, "the inspected working tree, including dirty instructions") and `8cf5e2c1…` (the studied repo) explicitly, in the same sentence (line 1) — the clearest of the 18 on this point |
| README.md | 45 | index, not a claim source |

**Reading of "names the commit": 9 of 18 report files state this repo's audited commit (`4cdd8bfb`) explicitly and near the top. The other 9 either study a different repo/tool (agentsview, claudex-loop, GitHub API state, a throwaway scratch repo) where a knowledge-base HEAD pin is not the relevant anchor, or omit it. None of the 9 "omit it" cases is FALSE evidence for a wrong tree — they just make the reader work harder to establish scope. `advisor-durability.md` is the one case where a DIFFERENT knowledge-base commit (`aef74afe…`) is named instead of this round's `4cdd8bfb` anchor; that is because it documents a separate, earlier #754 design consult, not a defect, but it means a reader must not assume every report in this directory examined the same tree.**

## Claims table (priority claims re-derived with a DIFFERENT instrument than the report used)

| # | claim | report:line | verdict | probe (route used) |
|---|---|---|---|---|
| 1 | `session-audit-d-vague.md` is a clean, complete audit | README.md:30-31, session-audit-lead-verdict.md:19-27, session-audit-synthesis.md:5 | **CONFIRMED PARTIAL** | Read the file's own body end-to-end (165 lines): it contains NO internal statement that it was cut short — its own "Input stability" / limitations section reads as an ordinary completeness caveat, not a timeout notice. The rc=124/2400s fact exists only in three OTHER files (README, lead-verdict, synthesis), never in the file itself. **A reader who opens only `session-audit-d-vague.md` cannot discover it is partial.** |
| 2 | `session-audit-a-code.md` ("is the SHIPPED CODE correct?") supports the round's #1 P1 finding | session-audit-synthesis.md:75 cites it for **P1 #2** (the highest-priority finding in the whole round) | **PROMOTION GAP — the cited evidence file was never promoted** | `ls docs/research/reports/2026-09-12-function-hooks-round/ \| grep session-audit-a` → no match. The file exists only at gitignored `.agent/kb/reports/agents/session-audit-a-code.md` (verified on disk, 197 lines / 28,286 bytes, matches synthesis's own retained hash table at line 718). Per `agent-report-persistence.md` rule 1b, a cited, load-bearing report belongs in `docs/research/reports/`; it is the ONLY one of the six audit lanes (A/B/C/D/E + lead-verdict/synthesis) not promoted. A fresh clone of this repo cannot verify P1 #2's own cited evidence. |
| 3 | `next.origin` is host-set and unforgeable, cited at `claude-code.d.ts:3841-3846` | README.md:17, `fh-synthesis.md:22` (C1, "settles the round's top risk"), `session-audit-b-claims.md:416` ("fresh lines 3,839-3,849"), `graphify-extraction-owner.md:857` | **CITATION IS WRONG BY ~500 LINES — but the underlying claim independently holds** | `sed -n '3835,3850p' sources/media/claude-code-function-hooks-types.d.ts` → that range is `PaneCloseInput`/`PaneCloseOrigin` (pane-close semantics), a **different** `origin` field entirely, not the hook-dispatch `Origin` type. The text that actually supports "host-set, nothing a plugin writes reaches it" is the `Next.origin` doc-comment at **lines 3336-3343** (`readonly origin: Origin; … Set by the host alone, from the environment the call came from (its own MessagePort) and that plugin's seat; nothing a plugin writes reaches it.`). Confirmed via `git log --oneline -- sources/media/claude-code-function-hooks-types.d.ts` that the file has not changed since a commit that predates this whole round (`696c9ae2`), so the wrong line range is not explained by file drift — it is a citation that was never re-derived and was copied forward into 4+ reports including the round's own README. The CONCLUSION is correct (verified independently against the real declaration); only the pointer is broken. |
| 3b | "unforgeable" is a settled fact, no caveat | README.md:17 states it flatly; `fh-synthesis.md` C1 calls it "settles the round's top risk" | **A caveat present in one report was DROPPED when the claim propagated into the round's own summary** | `session-audit-b-claims.md:416` (a LATER, independent audit lane) explicitly downgrades the word: *"An adversarial 2.1.269 transport-forgery arm was not run, so the stronger runtime word 'unforgeable' remains UNVERIFIABLE beyond the exposed contract."* That is: the TYPE contract says a plugin cannot set it; whether the running binary actually enforces that (vs. some prototype-pollution/monkeypatch bypass) was never tested. README.md and `fh-synthesis.md` present the type-level fact as if it settles runtime behaviour with no qualifier. |
| 4 | 283 KB Claude sessions predating 2026-08-14 are missing from disk but survive in agentsview's archive | `agentsview-research.md:46-48,254` | **AGREES, re-derived with a fresh `sqlite3` call, not copy-pasted** | `sqlite3 "file:$HOME/.agentsview/sessions.db?mode=ro" "SELECT COUNT(*) FROM sessions WHERE project='knowledge_base' AND agent='claude' AND started_at < '2026-08-14';"` → **283**, independently run right now. Oldest on-disk `.jsonl` for this project is `2026-08-14` (`stat -c '%y %n'`), consistent with the report's "before 2026-08-14 = 0 on disk" claim. DB total sessions is now 9,573 vs the report's 9,526 — expected drift (an actively-syncing DB), not a contradiction; the report itself labels the DB mutable. |
| 5 | The "full collision inventory" is 13 classes | `scratch-isolation-review.md` §7 header, restated in README.md:21 | **AGREES** | Counted the numbered list in §7 directly (`sed -n '693,723p'`) — exactly 13 numbered entries (1–13). The section itself discloses that only #1 (agent-definition scratch paths) was independently spot-checked by this report's author; the other 12 are "as reported by that [sweep] lane" — a disclosed, not hidden, inheritance. |
| 6 | `tool.result` is not a declared/registerable event; `tool.check` on Bash fires and can deny | `graph-first-hook.md:125,156-159,318,650`; README.md's "function hooks are VIABLE" verdict | **BOTH AGREE, checked two different ways** | (a) `grep -n "tool\.result\|tool\.check" sources/media/claude-code-function-hooks-types.d.ts` → zero hits for either literal in the (stale but unchanged-since-round) vendored `.d.ts`; `tool.call` is the only declared `tool.*` dispatch event visible there. This is consistent with, not proof of, the report's claim (the vendored file is 7,966 lines vs the installed runtime's larger surface, a known gap this same round's other reports document). (b) The report's own live-fire arm is the stronger evidence and does not depend on the stale `.d.ts`: it reports a **verbatim runtime deny message** — `Permission to use Bash denied by plugin plug-checkdeny: KBPROBE_TOOLCHECK_FIRED: denied by the tool.check hook.` — i.e., an actual 2.1.269 process denying a sentinel command via a registered `tool.check` hook. That is a real behavioural arm, not a grep. |
| 7 | The round's own accounting: 147 findings, 20 homed / 127 unhomed | README.md's opening paragraph; `session-audit-synthesis.md:88,335` | **AGREES** | `rg -c '^\| F[0-9]{3} \|' docs/research/reports/2026-09-12-function-hooks-round/session-audit-c-accounted.md` inside the FINDINGS table only → 147 distinct `F0xx` IDs (verified distinct via `sort -u \| wc -l` = 147; the raw grep across the whole file returns 148 because the file's separate disposition/promotion table also references `F103` — not a duplicate finding, a second table). Synthesis's stated 20 homed IDs (`F003, F026, F029–F032, F074–F083, F131–F134`) sum to exactly 20 by hand-count. |
| 8 | The P1 runtime-flag misclassification bug (`kb-mod-runtime-check` passes only inside a Claude session because `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` was declared in neither `mise.toml` nor the module) | `session-audit-synthesis.md:9` (P1 #1), `754-advisor-verdict.md` | **CONFIRMED FIXED**, but only in a LATER commit than the one the round audited | `git log --oneline 4cdd8bfb..c1d8afb8` shows `c33a1fb5 fix(754): the gate was green only because of WHERE it ran…`, whose commit message states the exact before/after arm (`flag stripped → rc 1` before, `rc 0` after). The round's own commit (`4cdd8bfb`) still had the bug; the fix landed one commit later. This is correctly described as "staged but unreviewed" at audit time in `session-audit-synthesis.md:75`, and that description was accurate for the commit under audit — not a defect, just worth flagging that later readers of these reports must not assume the bug is still open in HEAD. |
| 9 | README says "Sixteen findings-bearing reports" | README.md:3 | **AGREES, once the exclusion is understood** | Directory has 18 non-README report files. README's table enumerates 16 of them by name/glob, deliberately omitting `session-audit-lead-verdict.md` and `session-audit-synthesis.md` — the "audit of the audit" meta-files, not original findings. That is a defensible editorial choice, not a miscount, but it is not stated explicitly in the README, so a reader doing their own file count (as I initially did) will see 18 and think the "sixteen" is wrong. |

## Contradictions between reports (free defects — the disagreement, not adjudication, is the finding)

1. **"unforgeable" (flat, in README/fh-synthesis) vs. "UNVERIFIABLE beyond the exposed contract" (`session-audit-b-claims.md`, a later, independent lane).** See claim 3b above. The later lane is the more careful statement; the round's own front door (README) carries the less careful one. Anyone who reads only the README inherits an overstated certainty.
2. **`fh-source-sweep.md:1432`** ("`tool.check`'s shipped status is **contested**") **vs. `fh-synthesis.md:175`** ("`tool.check` is not 'contested' — it is SEQUENTIAL… both are right and nothing is contested"). This is a resolved disagreement, correctly labelled as a synthesis correction of an earlier lane — not a live contradiction, but worth listing because a reader who stops at `fh-source-sweep.md` (1,463 lines, the longest file, plausible fatigue point) will carry the retracted "contested" framing.
3. **`extract-research-a-live.md:302`** ("6 of 23 cross-references are daily-digest noise") **vs. the same report's own `:471`** ("7 of 23"). Caught and correctly flagged as STALE-then-AGREES by `session-audit-d-vague.md`'s own numeric table — a genuine within-report self-contradiction that the audit round did catch, cited here to confirm the audit's catch is itself correct (re-verified independently is out of scope given the GitHub thread is mutable, but the internal inconsistency between :302 and :471 is a plain text fact, not a live-data question).
4. **`graphify-extraction-owner.md:635-645`** claims "31 pin sites enumerated" but **its own cited origin table (`/tmp/lane-fork-currency.md`, non-promoted scratch) contains only 30 data rows** — already caught by `session-audit-d-vague.md`'s D4 section. I did not re-open the scratch file (gitignored, may no longer exist), but the arithmetic mismatch (31 claimed vs. "31" not matching a 30-row table) is exactly the kind of denominator-free count this lane was asked to watch for, and the existing catch looks sound on its face.

## `session-audit-d-vague.md`'s timeout: what it does NOT cover

Confirmed via the file itself plus the three files that describe it (`README.md`, `session-audit-lead-verdict.md`, `session-audit-synthesis.md`):

- It DID reach disk with every requested section present (Method, Numeric claims table, D1 Unfalsifiable, D2 Inherited numbers, D3 Self-invalidating, D4 Denominator-free, D5 CLAUDE.md volatile rows, Input stability) — the wrapper's incremental-write design worked as intended.
- What is NOT proven: that the SWEEP feeding those sections was exhaustive. The wrapper's own words, relayed by the lead: *"it reviewed a SUBSET, which is not a clean pass."* No lane or synthesis step re-ran D's sweep to confirm completeness — A/B/C/E cover different QUESTIONS (code correctness, claims correctness, accounting, missed items), not D's specific vague/unmeasured-numbers sweep, so there is no independent second pass over the same territory.
- Concretely at risk: any numeric or vague claim in the round's other reports that D's table does NOT mention has NOT been checked for vagueness/inheritance/self-invalidation by anyone — its absence from D's table is not evidence it passed, only evidence D didn't reach it (or reached it and the finding didn't survive to disk before rc 124, which is indistinguishable from D's output alone).
- One additional, previously unflagged wrinkle found in this lane's own read: `session-audit-synthesis.md:499` says the on-disk `session-audit-d-vague.md` was itself "**copied/created by another actor during synthesis**" and its "contents [were] not independently re-audited [t]here [i.e., by synthesis] (index read)." So the file's promotion into the tracked directory was not itself verified against the exact bytes synthesis reasoned about — a second, smaller layer of unverified-ness stacked on top of the rc-124 partial-sweep problem. I did not find a hash mismatch (SHA-256 in `session-audit-synthesis.md:721` is `afb8c23f…`, consistent with the current 165-line/64,038-byte file — `wc -c` on the tracked copy agrees with the byte count in that table), so this is a **process gap that happened not to produce a wrong file**, not a live corruption.

## What I did not verify (be explicit)

- I did not re-run every one of D's ~40 numeric rows against live GitHub/PyPI state — most are explicitly UNMEASURABLE-as-historical by the report's own admission (mutable remote counts), and re-running them would only produce a new current snapshot, not validate the report.
- I did not re-derive the 31-vs-30 pin-site scratch file (`/tmp/lane-fork-currency.md`) since it is gitignored scratch and may be gone; I relied on `session-audit-d-vague.md`'s own re-count of the table as sound on inspection.
- I did not attempt an adversarial forgery arm against `next.origin` myself (the very thing `session-audit-b-claims.md` says is missing) — that would require driving a live 2.1.269 hook session, out of scope for a fact-checking pass on already-written reports.
- The `mise run kb-query` orientation call I ran per the graph-first guard timed out at 120s and was moved to background; it returned before I needed its content for this lane's conclusions, so it did not block this report, but I note it because a 120s+ graph query for a routine orientation question is itself a minor data point about graph query latency this round (not otherwise a subject of this lane).

## GitHub repos touched

- `ray-manaloto/knowledge-base` — read all 19 promoted reports, the vendored `.d.ts`, `mod_runtime.py`/`mise.toml` diffs across two commits, git log for the vendored source, `.agent/kb/reports/agents/session-audit-a-code.md` (gitignored, local only), and issue #767 (`gh issue view 767 -R ray-manaloto/knowledge-base`) to verify the "13 of 150 rollouts, 300 newest, other 150 unknown" figure cited by `session-audit-d-vague.md`.

## Addendum: `--no-sync` unblock + `agentsview-research.md`'s #1676/version claim re-checked

Team-lead reported `mise run kb-session-search -- "<pattern>" --since Nd --no-sync` unblocks the
daemon-sync failure (two foreign files — a truncated Cursor composer record and an OpenCode part
file with an invalid UTF-16 surrogate pair — break the all-or-nothing sync pass across every
harness root). Verified independently:

- `gh issue view 1676 -R kenn-io/agentsview --json state,closedAt,title` → `CLOSED`, `closedAt:
  2026-09-10T15:00:27Z`, title confirms "one NULL cursorDiskKV value fails every sync worker
  pass" — matches `agentsview-research.md:226` exactly (issue number, close date, description).
- `agentsview --version` → `v0.42.0 (commit ff8fb4e8, built 2026-09-01T19:37:18Z)` — matches the
  report's own installed-version line (`:160`), and **predates** the #1676 fix's close date by 9
  days, so the fix cannot be in our installed build.
- **The report does NOT claim our installed version carries the #1676 fix.** The #1676 row sits
  inside a table explicitly headed "Other fixes landed but unreleased — several are ours"
  (`:218`), and the surrounding prose for the neighbouring #1670 fix states outright "It is
  unreleased. No tag carries it." (`:205`). So the concern that this report might overstate our
  coverage of #1676 is **not borne out** — the report already gets this right.
- Ran `mise run kb-session-search -- "next.origin" --since 3d --limit 3 --no-sync` myself just
  now → rc 0, `"synced": false`, live matches including one from this session (ordinal 21,
  timestamp `2026-09-12T19:32:56Z`) — confirms the daemon-sync workaround team-lead reported is
  real and reproducible, not a one-off.
- The report does not mention `--no-sync` or the specific two-file root cause (Cursor
  truncated-record / OpenCode UTF-16 surrogate) — that diagnosis happened later, outside this
  report's scope, and its absence here is not a defect in the report.
