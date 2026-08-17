---
type: "query"
date: "2026-08-17T05:00:34.268345+00:00"
question: "What did three rounds of verified cross-family review find on the semantic corpus runner, and what generalises?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did three rounds of verified cross-family review find on the semantic corpus runner, and what generalises?

## Answer

A verified `codex exec` cross-family lane found 8 findings (4 HIGH) on a diff a
same-family lane had passed with 0 blocking. Three rounds followed. What the
rounds actually measured:

**Round 1 (8 findings).** Every one re-verified against the code; none was a
false positive. The sharpest was not "a verifier is missing" but "a thorough
verifier exists and NOTHING CALLS IT" — `verify_staged_chunk` already rehashed
every staged member against the writer's own digests, and `execute()` decided
"already staged" from `Path.exists()`. I wrote a duplicate verifier before
finding the real one.

**Round 2 (1 blocker, introduced by round 1's fix).** My multi-call guard counted
boundary markers directory-wide. graphify's serial path does
`if exc is not None: ... continue`, so a chunk whose provider call FAILS never
reaches the callback that clears markers — its marker inflates the NEXT chunk's
count, and a good single-call chunk was refused as bisected. One failure became
two, and the second was misnamed.

**Round 3 (1 blocker + 2 lows, all mine).** The repaired discriminator still
SWAPPED the reason on `attempts > 1`, so a genuinely corrupt chunk following a
failed one was renamed a bisect. Fixed by making it ADDITIVE: the prompt
mismatch is always true and always reported; the count only ever appends an
explanation. Nothing available can separate a real bisect from
corruption-plus-carry-over, so a reason claiming to over-asserts.

The two low findings were both this session overstating its own prose: a
docstring that named version numbers in the sentence declaring it named none
(written that way TWICE), and a mutation arm whose id promised coverage it did
not have.

Durable lessons, in order of how much they cost:

1. **A fix is a hypothesis, and rounds 2 and 3 were both about MY fixes.** Two
   consecutive cold rounds found defects created by the previous round's repair,
   not pre-existing ones. The two-round bound assumes findings are discovered;
   it does not hold when they are manufactured.
2. **A guard keyed on a number must ask whether that number is scoped to the
   thing it judges.** The marker count was real and correctly measured, and it
   belonged to the RUN rather than to the chunk.
3. **Prefer additive reporting over substitution when the evidence is
   ambiguous.** A swapped reason asserts a cause; an appended one offers a fact.
4. **`--add-dir` lifts the codex sandbox limit that a previous report concluded
   was inherent.** That report searched for a `writable_roots` config KEY and
   correctly found none — the FLAG is advertised in `codex exec --help`. With
   `-s workspace-write --add-dir ~/Library/Caches/uv --add-dir ~/.cache`, codex
   ran `mise run kb-check`, `pytest` and `kb-arms`. Fixing the temp dir moved the
   error one layer out to uv's cache, so the second layer was only found by
   re-probing after the first fix.
5. **Verify a review lane by PROCESS TREE.** `pgrep -f "codex exec"` returned 2
   pids and one was the wrapping zsh whose argv contains the string. The
   parent/child chain from your own background shell to `comm=codex` is what
   settles it. (Control: bare `pgrep -f codex` matched 20.)
6. **A `kb-arms` `suites` entry accepts a pytest NODE ID.** That is the clean
   escape from the authority-digest trap: naming the whole corpus test file
   pulls in the authorization test, which fails under any byte change to the
   mutated modules and breaks the CONTROL rather than adding a row.
7. **Re-plan LAST.** The first re-authorization verified `execution_authorized:
   true` and was silently invalidated by later edits to the slice and adapter; it
   surfaced only when the suite ran. A green `verify` describes the tree at the
   moment it ran and nothing after.
8. **Know when to stop making a test observable.** Three attempts to observe
   `attempts` reaching the receipt each needed another stub, because the harness
   has no real source tree. Testing the counting unit directly and recording the
   composition as UNARMED (#332) beat a test that exercised mostly stubs.


## Outcome

- Signal: useful