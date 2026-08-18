# Refutation lane — "~539K tokens recoverable if sessions had queried graph first"

CLAIM: ~539K tokens recoverable; 59 graph queries replacing sequential Bash reads.
EVIDENCE OFFERED: "599 direct reads x ~1,000 tokens per 10 reads = ~60K current cost;
59 graph queries x 3K = 177K. Net savings: 60K - 177K = -117K (queries are MORE
expensive than reads). Detailed model in coverage section of
.agent/kb/reports/agents/iter1/context.md"

## Probe 0 — the cited artifact does not exist

    $ ls .agent/kb/reports/agents/iter1/context.md
    ls: .agent/kb/reports/agents/iter1/context.md: No such file or directory   (rc=1)
    $ find /Users/.../knowledge-base/.agent -name 'context*.md'
    .../.agent/kb/reports/agents/context.md
    .../.agent/kb/reports/agents/context-heavy-work-2026-08-17.md

Control: the same `find` (unbounded depth, no 2>/dev/null) DOES return two context
files, so the probe discriminates. The path in the finding is wrong.

## Probe 1 — the nearest real artifact contains no such model

    $ grep -n "539\|savings\|Savings\|coverage\|59 \|3K\|177" .agent/kb/reports/agents/context.md
    (no output)
    control: grep -c -i token .agent/kb/reports/agents/context.md -> 11

So the file is greppable and the terms are absent. Its ## COVERAGE section
(lines 156-170) is a reached/not-reached list, not a token model. Its section 7
(line 124) argues the OPPOSITE of the claim: the grep->graph-query substitution
"is blocked by a corpus gap, not just discipline" (kb_setup and the installed
graphify package are not in the corpus).

## Probe 2 — the headline figure exists nowhere

    $ grep -rn "539" --include='*.md' .agent/kb/reports/ docs/
    .agent/kb/reports/agents/iter1/refute-token-savings.md  (this file)
    .agent/kb/reports/agents/iter1/bot-reviews.md:267  (a review SHA, f85f848b...)
    docs/research/reports/session-audit-2026-08-02-f.md:141  ("539 tests")
    docs/research/reports/codegraph-retrieval-gap.md:161  ("tools.ts:2539")
    docs/research/reports/mise-path-research.md:129  ("src/env.rs:539-540")

Control: the same command shape on a figure known present in that tree returns
`.agent/kb/reports/agents/iter1/refute-forgotten.md:33` for "188". So the probe
discriminates. No artifact in the repo derives ~539K.

## Probe 3 — the finding contradicts ITSELF

Headline: "~539K tokens recoverable". Its own evidence line: "Net savings:
60K - 177K = -117K (queries are MORE expensive than reads)". A claim whose
own stated arithmetic has the opposite SIGN is refuted without any measurement.

## Probe 4 — both model parameters are wrong, measured against the transcripts

JSON-parsed every `tool_use`/`tool_result` pair in the 5 session transcripts
(scratchpad/measure.py, measure2.py; dedup by tool_use id so compaction copies
do not double count; chars/4 as the token estimate):

    49e2cc30: Read n=20 chars=65800  avg=3290 | graphquery n=1 chars=4067  avg=4067
    52f5798a: Read n=32 chars=154818 avg=4838 | graphquery n=1 chars=2389  avg=2389
    6b974f05: Read n=55 chars=222528 avg=4046 | graphquery n=2 chars=2339  avg=1170
    fb633adf: Read n=21 chars=185186 avg=8818 | graphquery n=1 chars=3444  avg=3444
    f1d1c0cf: Read n=19 chars=124338 avg=6544 | graphquery n=4 chars=10238 avg=2560

    TOTAL Read tool_use = 147; result chars = 752670 (~188,168 tokens)
    TOTAL graph-query Bash = 9; result chars = 22477 (~5,619 tokens)

Broad reading of "direct read" (Read tool + Bash whose command-position word is
cat/head/tail/sed/grep/rg/less/awk/find/ls/wc, split on && || ; |):

    49e2cc30 253 | 52f5798a 267 | 6b974f05 390 | fb633adf 180 | f1d1c0cf 76
    TOTAL 1166 direct reads; 1,727,128 chars (~431,782 tokens); avg ~370 tok/read

Against the finding's parameters:

| parameter | finding | measured | error |
|---|---|---|---|
| direct reads (5 sessions) | 599 | 147 (Read tool) or 1,166 (broad) | no reading gives 599 |
| cost per read | ~100 tok ("1,000 per 10") | ~1,280 tok (Read tool) / ~370 tok (broad) | 3.7x-12.8x understated |
| total read cost | ~60K | ~188K (Read tool) / ~432K (broad) | 3.1x-7.2x understated |
| cost per graph query | 3,000 tok | ~624 tok (22,477 chars / 9 / 4) | 4.8x overstated |

Every one of the four inputs to the model is wrong, so the model's output
(-117K) is not evidence for anything, in either direction.

## Probe 5 — the substitution itself does not work here (live arm)

    $ mise run kb-query -- "how does kb_setup graph_first decide whether to deny a search"
    rc=3
    ERROR: [kb-query] Graphify returned an incomplete TRUNCATED result with rc=0.
    Traversal: BFS depth=2 | Start: ['decide()','deny','search()','graph_first.py',...] | 1491 nodes found
    [!] TRUNCATED: showing 67 of 1491 nodes (~2000-token budget)
    (6,906 bytes ~= 1,726 tokens of output, and NO answer)

Control arm: the same task shape on a different question also returns nodes
(1,279 found) rather than an empty/dead result, so kb-query is live; what fails
is the ANSWER, not the tool. A query that costs ~1.7K tokens and still requires
the reads afterwards makes the cost ADDITIVE, not substitutive. This reproduces
what `.agent/kb/reports/agents/context.md:124-138` already recorded.

## Probe 6 — the counterfactual's premise is contested by a sibling lane

`.agent/kb/reports/agents/iter1/refute-graph-first.md` (Probe 4, the repo's own
`graph_first.decide()` replayed over every event) measures 5/5 sessions DID query
the graph, 4/5 within their first 5 commands, 2 violations across 1,198 events.
"If sessions had queried graph first" describes a counterfactual that largely
already happened.

## VERDICT: REFUTED
