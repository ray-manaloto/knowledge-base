# Refutation attempt — finding [contradicted] #13 (notepad-enforcement.md)

**Claim under test:** the reviewed session (6697269c-34d2-4355-948e-48b775449a73,
2026-08-18T16:33:34.147Z -> 20:14:36.651Z) wrote nothing to `.agent/notepad.md`,
contradicting `notepad-enforcement.md`.

**Verdict: NOT REFUTED (refuted=false).** Every escape route probed came back
against the refutation.

## Probe 1 — token spelling bound (the classic failure)

```
F=6697269c-34d2-4355-948e-48b775449a73.jsonl
grep -ic notepad $F                -> 0
grep -c NOTEPAD / Notepad / note_pad / 'note pad' / '.agent/note'  -> 0 each
grep -c scratchpad $F              -> 34   (a DIFFERENT mechanism, not the notepad)
CONTROL: grep -ic 'kb-check' $F    -> 108
CONTROL: grep -ic handoff  $F      -> 349
```
The probe discriminates on the same file. Case and separator variants all zero.

## Probe 2 — the finding's search was BOUNDED to the top-level jsonl. Removed.

The session tree has 109 files (14 direct subagents + 2 workflow fan-outs of
~20 agents each + tool-results). Searched all of them:

```
grep -ril notepad .   -> 5 files (so the probe CAN hit in this tree)
grep -roh '"file_path":"[^"]*notepad[^"]*"' .   -> 0 occurrences
CONTROL in same tree: '"file_path":"[^"]*bot-reviews[^"]*"' -> 16 occurrences
grep -roh '>> *[^ "]*notepad' .  -> 0   (no bash-append write either)
```
The 5 `notepad` hits are all NON-writes, read verbatim:
- `subagents/agent-aseam-advisor-…jsonl` — `handoff_reconcile` output listing
  `agent/notepad.md` as an AMBIG path of a 2026-08-17 handoff
- `wf_701b4d8f/agent-ae4080c198f8a2bfb.jsonl` — prose citing `notepad-enforcement.md`
- `wf_df0ef2f9/agent-a2737bf1bd3492081.jsonl` — a lane writing
  `.agent/kb/reports/agents/bot-reviews.md` "incrementally per notepad-enforcement.md"
- `wf_df0ef2f9/agent-a4677e415b4ffaa3f.jsonl` — an `ls .agent/` output
- `tool-results/b6vq1hvwf.txt` — the injected CLAUDE.md/rules text (the rule itself)

## Probe 3 — CONTROL ARM that returns the OPPOSITE answer

A session that demonstrably DID write the notepad (it authored the
`## 2026-08-17 (e)` block):

```
grep -rl 'the merge path did NOT exist' --include='*.jsonl' .
  -> 49e2cc30-3352-4cb9-939d-b19f5ce68acb.jsonl
grep -o '"file_path":"[^"]*notepad[^"]*"' 49e2cc30-….jsonl | sort | uniq -c
  -> 6 "file_path":"/Users/…/knowledge-base/.agent/notepad.md"
```
Same probe, same corpus shape, POSITIVE. The reviewed session's whole tree: 0.

## Probe 4 — could the records have been lost (compaction / resumption)?

```
head -1 $F                      -> {"type":"mode","mode":"normal","sessionId":"6697269c-…"}
grep -c isCompactSummary $F     -> 0
grep -c '"type":"summary"' $F   -> 0
grep -o '"sessionId":"[^"]*"' $F | sort -u  -> exactly one id
type histogram: 630 assistant / 400 tool_use / 400 tool_result
```
Fresh session, no compaction record, no parent. Nothing was truncated away.

## Probe 5 — could a HOOK have written it (making the mtime inference wrong)?

```
grep -rn 'notepad' .claude/settings.json .claude/settings.local.json  -> rc=1
CONTROL: grep -c SessionEnd .claude/settings.json -> 1
```
No hook touches the notepad.

## Probe 6 — the finding's mtime inference, upgraded to CONTENT evidence

`.agent/notepad.md` headings (`grep -n '^#'`) jump straight from
`2026-08-17 (e)` (line 652) to `## 2026-08-18 (session e) — triage round`
(line 814). There is NO 2026-08-18 session-d block at all. The 08-18 block's
first bullet is *this* round's finding #6 (antigravity pin 1.1.11), i.e. it was
written by the NEXT session, exactly as the finding inferred from mtime.
File is now 62779 bytes (was 61460 when the finding was written) — still growing
under session e.

## Method nits in the original evidence (immaterial)

- "1845 timestamped records": `grep -o` counts occurrences; `grep -c '"timestamp":"'`
  gives 1838 LINES. Same fact, different unit. Does not move the verdict.
- The original probe was bounded to the top-level jsonl and would have MISSED a
  subagent write. Removing that bound (probe 2) still returns zero, so the bound
  was harmless here — but the finding as written was one directory short of safe.

## Does any other live finding contradict this one?

No — two corroborate it:
- #25 (kb-distill / kb-session-reflect never ran while kb-remember/kb-reflect did):
  consistent with a session that used the DURABLE memory layer and skipped the
  scratch layer. notepad-enforcement.md says "**Both, every time**", so
  kb-remember is not a substitute.
- #31 (the bot-reviews.md report lived only under `.agent/kb/reports/agents/`):
  matches probe 2's hit #3 — the session's incremental writing went to
  `agent-report-persistence.md`'s artifact path, not the notepad. That rule's
  clause 4 states notepad entries are "additive, not substitutes".
- #1 (heredoc file surgery bypassing Edit) would still leave the literal string
  `notepad` in the bash command; probe 1 returns 0, so no heredoc write happened.
