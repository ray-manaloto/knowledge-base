# Refute: graphify semantic corpus produced zero corpus output

## Probe 1 — the chunks directory (DEFECT FOUND in the original probe)
`ls graphify-out/graphify-semantic-corpus-chunks/` -> `No such file or directory`, rc=1.
The finding's probe `ls graphify-out/graphify-semantic-corpus-chunks/ | wc -l` = 0
counted an ERROR, not an empty directory. stderr swallowed; wc counted zero lines of stdout.
This is the "a parse error read as a no" failure. The directory does not exist at all.

## Probe 2 — a directory that DOES exist and IS from the round
`graphify-out/graphify-semantic-corpus/` mtime **Aug 19 10:30**, 6 files:
advisories.json(541) chunk-ledger.json(94961) exclusions.json(1939)
execution-config.json(2727) manifest.json(782) source-inventory.json(200074)
=> ~300KB of artifacts written DURING the round.

## Probe 3 — subcommands are real
python/src/kb_setup/cli.py:86  "graphify-semantic-corpus plan|run|verify [PATH]"
mise.toml:571 [tasks.kb-graphify-semantic-corpus] run = "uv run kb-setup graphify-semantic-corpus"
NOTE: mise passes args after `--`, so the real command text is
`mise run kb-graphify-semantic-corpus -- plan`, NOT `kb-graphify-semantic-corpus plan`.
The finding's grep string `'kb-graphify-semantic-corpus plan'` (space, no `--`) is a
TOKEN-SPELLING BOUND. Must verify.

## Round transcript identified
773421d1-632d-44fb-a680-8117295016ad.jsonl
span 2026-08-18T20:14:42Z -> 2026-08-19T19:18:51Z (~23h); 508 `"name":"Bash"` occurrences
(finding says "492 commands" — small delta, likely dedup).
Control: `grep -c '"timestamp":"2026-08-19T1[0-8]'` over ALL transcripts -> only this one is non-zero.

## Probe 4 — per-verb counts, restricted to Bash tool_use lines, no && short-circuit
graphify-semantic-corpus plan            8
graphify-semantic-corpus run             0
graphify-semantic-corpus verify          0
graphify-semantic-corpus-merge           0
graphify_semantic_corpus_run             1
graphify_semantic_corpus_authority      14   <-- CONTROL (non-zero, same probe shape)
kb-merge                                 0
kb-validate-chunks                       0
=> plan=8 / run=0 / verify=0 REPRODUCES EXACTLY.

## Probe 5 — spelling bound test (the finding's grep string undercounts elsewhere)
Across ALL transcripts: 'kb-graphify-semantic-corpus plan'=20, '... -- plan'=51,
'graphify-semantic-corpus plan'=122, '... -- run'=31, '... -- verify'=33.
So the finding's string IS a bound in general. Within the ROUND transcript it does not
bite (mise was invoked without `--`), and the permissive spelling still yields run=0/verify=0.

## Probe 6 — no staged chunks anywhere
find <repo> /private/tmp/claude-501 -type d -name "*corpus*chunks*"  -> 0 hits
CONTROL: same find with -name "*corpus*"                            -> 8 hits (discriminates)
graphify-out/cache/ contains exactly 1 file (last_query_stamp).
Both scratchpad backups (gsc-0945.bak Aug 18 02:27, gsc-mid.bak Aug 19 00:38) hold the
same 6 plan files, no chunks.

## Probe 7 — nothing committed
git log -- sources/extractions/  last commit = fd7e1a5b 2026-08-07 (control: probe returns a commit)
git log --since="2026-08-18 15:00" -- sources/extractions/ -> EMPTY
control: git log --since="2026-08-18 15:00" --all | wc -l -> 30 commits (discriminates)

## Probe 8 — the plan was regenerated to the same bytes
md5 chunk-ledger.json: current fac49f2a... ; gsc-mid.bak fac49f2a... (IDENTICAL);
gsc-0945.bak 4d1f198e... => replanned, then replanned again to no change.

## VERDICT: NOT REFUTED (substance holds)
Two real probe defects that do NOT reverse it:
(a) `ls graphify-out/graphify-semantic-corpus-chunks/ | wc -l` = 0 counted an ERROR
    (`No such file or directory`, rc=1), not an empty directory. The finding's wording
    "is empty" is wrong; the directory has never existed. Non-existence is STRONGER evidence.
(b) "66 Bash calls" is not reproducible from the corpus token: only 14 Bash tool_use lines
    in the round mention it. The 66 is a cost-family aggregate incl. adjacent work
    (authority=14 etc.) — label UNVERIFIED, the plan/run/verify counts are the load-bearing part.
No other live finding contradicts this one; #5 (authority re-recorded 6x) is corroborated
by the authority=14 count from the same probe.
