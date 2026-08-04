---
type: "query"
date: "2026-08-04T03:28:12.931928+00:00"
question: "What did building kb-handoff-check (#145) teach about writing a checker whose findings can be trusted?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did building kb-handoff-check (#145) teach about writing a checker whose findings can be trusted?

## Answer

Measurement, not the happy path. Running the checker over all 28 committed handoffs and auditing every finding by hand took it from 99 failures to 24, of which 3 are genuine broken citations. The naive version fails its own ticket exactly as the handoff predicted: it read a branch name, a glob, an elided sha, a dotted python module and a partial path as broken repo-relative paths. Five separate false-positive classes, each fixed with both arms.

Four resolution states, not two. RESOLVED and MISSING are verdicts; AMBIGUOUS (several files match a shorthand) and UNVERIFIABLE (the citation is about another repo) each mean something other than wrong, and folding either into a verdict is what makes a checker start lying.

Vendored sources belong IN the index. Reversing that acceptance criterion was the highest-value decision: this repo pins graphify and mise at a commit, so citations like watch.py:1499 and redactions.rs:31 are not just resolvable, they are the ones whose LINE NUMBERS can actually be checked. Excluding them removed the ticket's core value while manufacturing false positives.

A marker checked in only one direction is a mute button. A path can be cited because it is absent, so the marker exists; it is checked BOTH ways, and cold review found the first version accepting AMBIGUOUS as confirmed absent, which handed a citation matching seven real files the same pass as a genuine miss.

Two rounds of cold cross-family review found 16 defects in code that was already green on every gate, and two of them were false GREENS in the same class: Path.exists() follows .. straight out of the repo, and after that was fixed lexically, an in-repo symlink reached the same place. The lesson is that a containment fix has more than one route to close.

A mutation harness needs a no-op CONTROL row. Without it, a harness broken in any uniform way reads as total success. Four arms also failed across the rounds because ruff format had reshaped the lines they targeted, and each reported MUTATION DID NOT APPLY rather than passing silently, which is the property that makes the harness worth keeping.

A hand-copied evidence table drifts. My first regex-built version of the mutation report silently dropped a row and mis-paired two, which is precisely the defect class the ticket exists to catch. The committed report is now generated from the harness and verified programmatically, table rows and embedded source both executed and compared against the run.

A measured number invalidated by its own commit is not a measurement. Two separate stale counts shipped in one branch (45 vs 41 tasks, 82 files in docs/) and both were broken by the very commit that wrote them. State the delta or the ratio, which is the durable fact.

## Outcome

- Signal: useful