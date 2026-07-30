---
type: "query"
date: "2026-07-30T22:46:10.421262+00:00"
question: "Why did a sentence in a SKILL.md get split in half with a bogus '# 81' heading inserted?"
contributor: "graphify"
outcome: "corrected"
correction: "I assumed a formatter gate passing meant my text survived it; hk's fmt path REWRITES content, so a green commit can still contain mangled prose."
source_nodes: ["kb-curator/SKILL.md"]
---

# Q: Why did a sentence in a SKILL.md get split in half with a bogus '# 81' heading inserted?

## Answer

A bare '#<number>' at the START OF A LINE is a malformed markdown heading, and rumdl's MD018 ('no space after # in heading') AUTO-FIXES it into '# 81' — splitting the sentence and injecting an H1. hk runs 'rumdl fmt' in the pre-commit hook, so the mangled text was committed before it could be reviewed (d56ab77, amended to c75153f). ISSUE REFERENCES ARE THE CASE THAT PRODUCES THIS: prose that reflows so '#81.' lands at a line start. The failure is silent because the formatter SUCCEEDS — it reports a fix, not an error. Two habits: never let a '#<n>' reference begin a line (write 'See issue #81', not a trailing 'See' + newline + '#81'), and after any hk fmt run confirm the file is a FIXED POINT ('rumdl fmt --check' wants no further change), not merely that the gate passed.

## Outcome

- Signal: corrected
- Correction: I assumed a formatter gate passing meant my text survived it; hk's fmt path REWRITES content, so a green commit can still contain mangled prose.

## Source Nodes

- kb-curator/SKILL.md