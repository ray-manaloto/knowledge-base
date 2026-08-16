---
type: "query"
date: "2026-08-16T17:46:03.393776+00:00"
question: "What does a truncated error message tell you about the population it came from?"
contributor: "graphify"
outcome: "corrected"
correction: "A truncated error message is a BIASED SAMPLE, not a small one — and paths sort alphabetically.\n\n`kb-build`'s preflight failure printed each source's unclassified list cut at 240\ncharacters. I read that as the population and reported to Ray that the 7,603\nunclassified files were \"third-party repo metadata — not code, not ours.\"\n\nThe truncation window is alphabetical, and dotfiles sort first. Every sample I\nsaw was `.gitignore`, `.editorconfig`, `.gitattributes`. The full census showed\n**27% of a 3,304-record sample was real source in languages graphify cannot\nparse** — `.pkl` (the language of this repo's own `hk.pkl`), `.pyi`, `.owl`,\n`.graphql`, `.hxx`. A metadata class that swallowed those would have hidden\ngenuine corpus loss behind a green build: the #231 shape.\n\nTwo distinct errors, and the second is the one to carry:\n\n1. I generalised from a bounded display. `probes-need-a-control-arm.md` rule 3\n   already says a DISPLAY BOUND is a bound.\n2. **The bias had a DIRECTION I could have predicted without any new data.**\n   Truncation is not random sampling. Alphabetical order plus a head-cut means\n   dotfiles are over-represented BY CONSTRUCTION. The moment a sample comes from\n   a truncation, ask which end it came from and what sorts there.\n\nThe fix that made everything after it cheap was to stop reading truncated output\nand make the tool report the actionable subset: receipts now carry\n`unresolved_paths` (unclassified minus everything absorbed). `mise` went from\n\"~1,075 paths, truncated\" to `unresolved(4)=[...]` — the four that actually\nblocked. Three builds' worth of guessing collapsed into reading a list.\n\n**And the same bound bit a second time in the same round.** Ray ruled to sample\nthe three biggest sources before writing the policy; I couldn't (three nested\ntimeouts) and proceeded on 43% predicting the rest was \"more of the same\". Those\nexact three sources were then the only ones still failing. The unsampled part is\nwhere the surprises live — that is what makes it unsampled.\n"
---

# Q: What does a truncated error message tell you about the population it came from?

## Answer

A truncated error message is a BIASED SAMPLE, not a small one — and paths sort alphabetically.

`kb-build`'s preflight failure printed each source's unclassified list cut at 240
characters. I read that as the population and reported to Ray that the 7,603
unclassified files were "third-party repo metadata — not code, not ours."

The truncation window is alphabetical, and dotfiles sort first. Every sample I
saw was `.gitignore`, `.editorconfig`, `.gitattributes`. The full census showed
**27% of a 3,304-record sample was real source in languages graphify cannot
parse** — `.pkl` (the language of this repo's own `hk.pkl`), `.pyi`, `.owl`,
`.graphql`, `.hxx`. A metadata class that swallowed those would have hidden
genuine corpus loss behind a green build: the #231 shape.

Two distinct errors, and the second is the one to carry:

1. I generalised from a bounded display. `probes-need-a-control-arm.md` rule 3
   already says a DISPLAY BOUND is a bound.
2. **The bias had a DIRECTION I could have predicted without any new data.**
   Truncation is not random sampling. Alphabetical order plus a head-cut means
   dotfiles are over-represented BY CONSTRUCTION. The moment a sample comes from
   a truncation, ask which end it came from and what sorts there.

The fix that made everything after it cheap was to stop reading truncated output
and make the tool report the actionable subset: receipts now carry
`unresolved_paths` (unclassified minus everything absorbed). `mise` went from
"~1,075 paths, truncated" to `unresolved(4)=[...]` — the four that actually
blocked. Three builds' worth of guessing collapsed into reading a list.

**And the same bound bit a second time in the same round.** Ray ruled to sample
the three biggest sources before writing the policy; I couldn't (three nested
timeouts) and proceeded on 43% predicting the rest was "more of the same". Those
exact three sources were then the only ones still failing. The unsampled part is
where the surprises live — that is what makes it unsampled.


## Outcome

- Signal: corrected
- Correction: A truncated error message is a BIASED SAMPLE, not a small one — and paths sort alphabetically.

`kb-build`'s preflight failure printed each source's unclassified list cut at 240
characters. I read that as the population and reported to Ray that the 7,603
unclassified files were "third-party repo metadata — not code, not ours."

The truncation window is alphabetical, and dotfiles sort first. Every sample I
saw was `.gitignore`, `.editorconfig`, `.gitattributes`. The full census showed
**27% of a 3,304-record sample was real source in languages graphify cannot
parse** — `.pkl` (the language of this repo's own `hk.pkl`), `.pyi`, `.owl`,
`.graphql`, `.hxx`. A metadata class that swallowed those would have hidden
genuine corpus loss behind a green build: the #231 shape.

Two distinct errors, and the second is the one to carry:

1. I generalised from a bounded display. `probes-need-a-control-arm.md` rule 3
   already says a DISPLAY BOUND is a bound.
2. **The bias had a DIRECTION I could have predicted without any new data.**
   Truncation is not random sampling. Alphabetical order plus a head-cut means
   dotfiles are over-represented BY CONSTRUCTION. The moment a sample comes from
   a truncation, ask which end it came from and what sorts there.

The fix that made everything after it cheap was to stop reading truncated output
and make the tool report the actionable subset: receipts now carry
`unresolved_paths` (unclassified minus everything absorbed). `mise` went from
"~1,075 paths, truncated" to `unresolved(4)=[...]` — the four that actually
blocked. Three builds' worth of guessing collapsed into reading a list.

**And the same bound bit a second time in the same round.** Ray ruled to sample
the three biggest sources before writing the policy; I couldn't (three nested
timeouts) and proceeded on 43% predicting the rest was "more of the same". Those
exact three sources were then the only ones still failing. The unsampled part is
where the surprises live — that is what makes it unsampled.
