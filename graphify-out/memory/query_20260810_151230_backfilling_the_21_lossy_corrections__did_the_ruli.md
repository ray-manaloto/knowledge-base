---
type: "query"
date: "2026-08-10T15:12:30.948419+00:00"
question: "Backfilling the 21 lossy corrections: did the ruling's stated arm actually verify the fix?"
contributor: "graphify"
outcome: "corrected"
correction: "An audit that reports 0 is not automatically the arm — ask WHICH PARSER it used. The ruling named `kb-remember -- --audit` reporting `0 WITHOUT` as the arm for the backfill, and it reads `kb_setup.remember._frontmatter`, a PRESENCE check (split on the first colon, strip surrounding quotes). The consumer that actually renders LESSONS.md is a different parser with a stricter contract — `graphify.reflect.parse_memory_doc`'s `_SCALAR_RE` requires the line to END with a quote and then unescapes `\\n` / `\\\"` / `\\\\`. A correction satisfying the audit but not that regex would have reported `0 WITHOUT` while still rendering an empty arrow: the defect surviving its own gate, in the round that closed it. Running BOTH parsers over all 33 and comparing byte-for-byte is what makes the number mean something; the one disagreement is the previous round's own memory and is benign (12 `\\n` escapes graphify unescapes and the audit does not, equal after unescape). Generalises past this task: when a gate and the real consumer read the same bytes through different code, the gate measures its own parser, not the artifact — arm it against the consumer.\n"
---

# Q: Backfilling the 21 lossy corrections: did the ruling's stated arm actually verify the fix?

## Answer

Backfilled all 21. `kb-remember -- --audit` goes 21 WITHOUT -> 0 WITHOUT (12 with
a lesson -> 33, rc=0), and `kb-reflect`'s artifact goes 42 empty arrows -> 0 with
the correction-line total UNCHANGED at 66 (33 entries x the overall and
by-community sections), so nothing was dropped or duplicated -- only filled in.

THE RULING'S OWN ARM WAS NOT SUFFICIENT, and finding that out cost one command.
The handoff named `--audit` reporting 0 as the arm. `--audit` reads
`kb_setup.remember._frontmatter`, which does a PRESENCE check: it splits on the
first colon and strips surrounding quotes. The consumer that actually renders
LESSONS.md is `graphify.reflect.parse_memory_doc`, a DIFFERENT parser with a
stricter contract -- `_SCALAR_RE = ^([A-Za-z_][\w-]*):\s*"(.*)"\s*$`, so the line
must END with a quote, and `_yaml_unescape` then processes `\n` / `\"` / `\\`.
A correction that satisfied the audit and not the regex would have reported 0
WITHOUT while still rendering an empty arrow -- the exact defect, surviving its
own gate.

So I ran both parsers over all 33 and compared. They agree byte-for-byte on my
21. The single disagreement is the PREVIOUS round's own memory and is benign: 12
`\n` escapes that graphify unescapes and the audit does not (equal after
unescape, verified). Two routes agreeing is the arm; one route is a presence
check wearing an arm's clothes.

WHAT THE 21 ACTUALLY WERE. Not one shape, which is why mechanising them would
have been wrong beyond the fabrication risk Ray named. Three groups:
(a) a belief that was wrong and got replaced -- #147's before-ship-not-before-land
ordering, the tests-extraction diagnosis, the cross-chunk gate's ranking rule;
(b) a measurement whose SCOPE was wrong, where the correction is the scope and
not the number -- currency.toml covering 7 of 14, R5's "alone in its own
ecosystem" measured over four Python projects and stated as the field;
(c) a round report with the replacement belief buried mid-paragraph -- the
navigable-graph round, kb-tool-review.js. Group (c) is where a generated summary
would have invented something: the lesson is one clause inside 300 words of
outcome, and picking it is the judgment.

BOTH FIELDS, because `save-result` writes both: the frontmatter scalar
`reflect.py:128` reads, and the `- Correction:` line under `## Outcome` that a
human reads. Backfilling only the first would have left every file still showing
a bare `- Signal: corrected` -- green to the machine, unchanged to the reader.

STILL OPEN. `reflections/LESSONS.md` is gitignored (#212), so this makes a richer
file that reaches no consumer and no fresh clone; the committed half,
`graphify-out/memory/**`, is what survives. #211 stays open for `source_nodes`.

TWO COLD ROUNDS, 4 FINDINGS, 0 BLOCKING. Round 1 found two P2s, both mine and
both ONE class -- a scoped measurement restated without its scope: "0 false
positives" for a figure the source scopes to 25 chunks, and a SHA "verified
twice" where the source describes one verification corroborated two ways. The
second is this corpus's own standing lesson (a number travels without its
condition) written freshly INTO the artifact that teaches it.

I swept the class rather than the two cited lines, because "a finding is a
SAMPLE of a class" failed on exactly this shape last round. The class had two
members; round 2 independently read all 21 and confirmed no third. Reporting
that a sweep found nothing further is the point of running it.

Round 1 also armed the gate I was relying on, which I had not: it reverted one
file, saw `1 WITHOUT` naming that file, restored it, saw clean. A lane that was
never told what the change was for proved the audit's FAIL direction.

DECLINED, with the reason recorded rather than silently: round 2's P4 notes two
corrections that OMIT an Answer-only figure entirely ("10 verified / 16 refuted",
"1,092 nodes over 37 files"). Omission is not misstatement, and those are yield
and delivery figures rather than the replacement belief -- the `## Answer` keeps
the full record, which is the division of labour between the two sections.

Gates at 7e8a1f818aa7: lint rc=0, test rc=0, brain-audit rc=0, eval rc=0.


## Outcome

- Signal: corrected
- Correction: An audit that reports 0 is not automatically the arm — ask WHICH PARSER it used. The ruling named `kb-remember -- --audit` reporting `0 WITHOUT` as the arm for the backfill, and it reads `kb_setup.remember._frontmatter`, a PRESENCE check (split on the first colon, strip surrounding quotes). The consumer that actually renders LESSONS.md is a different parser with a stricter contract — `graphify.reflect.parse_memory_doc`'s `_SCALAR_RE` requires the line to END with a quote and then unescapes `\n` / `\"` / `\\`. A correction satisfying the audit but not that regex would have reported `0 WITHOUT` while still rendering an empty arrow: the defect surviving its own gate, in the round that closed it. Running BOTH parsers over all 33 and comparing byte-for-byte is what makes the number mean something; the one disagreement is the previous round's own memory and is benign (12 `\n` escapes graphify unescapes and the audit does not, equal after unescape). Generalises past this task: when a gate and the real consumer read the same bytes through different code, the gate measures its own parser, not the artifact — arm it against the consumer.
