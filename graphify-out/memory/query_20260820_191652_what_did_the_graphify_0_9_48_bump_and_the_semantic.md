---
type: "query"
date: "2026-08-20T19:16:52.143426+00:00"
question: "What did the graphify 0.9.48 bump and the semantic-corpus cost analysis establish about clearing kb-build?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief was that clearing `kb-build` meant writing the reviewed-warning\ninventory entries by hand, and that the only open question was how to make 42 of\nthem cheap to generate. That framing was wrong in both directions.\n\n**Upstream had already fixed it.** graphify 0.9.48, released the same day,\ncarried #2879 — a data-shaped JSON the extractor declines is no longer counted as\na failed extraction. Bumping removed all 53 zero-node warnings and took the work\nfrom 42 entries to 1. The generator would have been built to industrialise a cost\nthat no longer existed. `tool-currency-and-native-first.md` says to check release\nnotes before building custom tooling; this round is the measured case for it, and\nthe check cost one `gh api` call.\n\n**And the remaining cost was not where the question pointed.** The question on\nthe table was which Claude model and effort level to use. The answer was that the\nmodel was nearly irrelevant: 55.1% of the planned tokens were spent re-extracting\nbyte-identical files, another 30% on README translations, and 24% on per-platform\nre-skins of a document already being extracted. Tuning the model would have\noptimised the last 19% while paying full price for the first 81%.\n\nThe generalisation: **when asked to optimise a parameter, first measure whether\nthe parameter is the cost.** Grouping the plan's units by content hash took one\ncommand and moved the answer more than any model choice could have.\n"
---

# Q: What did the graphify 0.9.48 bump and the semantic-corpus cost analysis establish about clearing kb-build?

## Answer

# What the 2026-08-20-c round established

## The bump that was supposed to be a detour turned out to be the fix

`kb-build` had failed for rounds on reviewed-warning inventories that do not
scale (#409). The plan was to exclude the blocking source and move on. Ray asked
whether graphify 0.9.48 — released that day — might help instead.

It did, decisively. 0.9.48's #2879 ("a data-shaped JSON that the extractor
deliberately declines is no longer counted as a failed extraction") removed
**every** zero-node warning in the build:

| build | graphify | zero-node warnings |
|---|---|---|
| first | 0.9.47 | 4 (10x-Team) + 8 (Attacca) + 41 (OpenSymphony) = **53** |
| second | 0.9.48 | **0** |

The hand-written inventory the round was about to generate went from 42 entries
to 1. **Check whether the tool fixed it before building the workaround.**

## 55% of the planned extraction was re-reading the same bytes

Grouping the semantic-corpus plan's 475 admitted units by `parent_sha256`:
**113 distinct files**, and **571,462 of 1,038,052 estimated input tokens
(55.1%) spent re-extracting byte-identical content**. `references/query.md`
appears 29 times identically; `skill-claw.md` 10 times.

Deduped further by path class, another 30% is README translations into 31
languages and 24% is per-platform re-skins of a skill document that is itself
extracted. The knowledge-bearing corpus is **199,934 tokens — 19% of the plan**.

The lesson is where the lever was: the question asked was "which model and
effort", and the answer was that **the model was not the expensive part**.

## Reflection is LLM-free, so one whole optimisation question was void

Control-armed: `reflect.py` contains **0** matches for
backend/`_call_claude`/api_key/anthropic against **190** in `llm.py`, and neither
`reflect()` nor `build_learning_overlay()` takes a backend while
`extract_corpus_parallel` does. There is no model or effort to choose at the
reflection layer and nothing to save there.

## A warning's TEXT does not tell you what was lost

Two partial-extraction entries were added, both measured from the sub-graph
rather than inferred from the warning, and they are **opposites**:

- `malformed.py` (OpenSymphony) — graphify says "1 symbol(s) extracted"; the
  sub-graph holds **2** nodes, the file stub AND `broken()`, and the file defines
  exactly one symbol. **Nothing lost.**
- `PathValidator.test.ts` (cclint) — **1** node, the stub alone, against **21**
  `describe`/`it` blocks. **All lost.** The file embeds literal `0x00` and `0x1f`
  bytes, read from the bytes because the rendered text shows them as spaces.

Reading "may be partially extracted" alone would have made these identical.

## The partial-extraction inventory does not converge in one build

Three builds, each clearing one source and revealing the next, and the
preflight's own warning list **grew from 2 to 3 between builds** — so it is not a
complete predictor. ~10-15 minutes per discovered entry. That is #409 with a
measured shape.


## Outcome

- Signal: corrected
- Correction: The belief was that clearing `kb-build` meant writing the reviewed-warning
inventory entries by hand, and that the only open question was how to make 42 of
them cheap to generate. That framing was wrong in both directions.

**Upstream had already fixed it.** graphify 0.9.48, released the same day,
carried #2879 — a data-shaped JSON the extractor declines is no longer counted as
a failed extraction. Bumping removed all 53 zero-node warnings and took the work
from 42 entries to 1. The generator would have been built to industrialise a cost
that no longer existed. `tool-currency-and-native-first.md` says to check release
notes before building custom tooling; this round is the measured case for it, and
the check cost one `gh api` call.

**And the remaining cost was not where the question pointed.** The question on
the table was which Claude model and effort level to use. The answer was that the
model was nearly irrelevant: 55.1% of the planned tokens were spent re-extracting
byte-identical files, another 30% on README translations, and 24% on per-platform
re-skins of a document already being extracted. Tuning the model would have
optimised the last 19% while paying full price for the first 81%.

The generalisation: **when asked to optimise a parameter, first measure whether
the parameter is the cost.** Grouping the plan's units by content hash took one
command and moved the answer more than any model choice could have.
