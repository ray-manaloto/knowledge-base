---
type: "query"
date: "2026-08-21T02:04:18.993531+00:00"
question: "Does graphify's published self-graph confirm the sample.luau loss, and was the mise wedge a concurrent-install race?"
contributor: "graphify"
outcome: "corrected"
correction: "A PROBE THAT READS THE LOCAL CLONE REPORTS THE CLONE, NOT THE WORLD — and a\ncontrol arm drawn from the same clone cannot catch it.\n\nThree beliefs were overturned this round, all the same shape: a bounded probe\nwhose bound was invisible from inside it.\n\n1. THE PUBLISHED SELF-GRAPH IS NOT A CONTROL ARM FOR THIS QUESTION.\n   `graphify-self-graph.tar.gz` (v0.9.48) is built by\n   `graphify extract graphify/ --out .` over the PACKAGE directory only — 82 .py\n   files, with `*.md`/`*.txt` appended to `.graphifyignore`. It contains zero\n   bytes referring to `tests/`, `luau` or `fixture`. So it neither shows the same\n   loss nor a clean extraction: IT NEVER ASKED THE QUESTION. Both readings were\n   on offer and both were wrong. Never cite it as \"upstream sees the same loss\".\n   Control arm: the same grep over our whole-clone extraction of the same commit\n   returns 20 / 332 / the fixture.\n   Corollary refuted as a tautology: \"built from the EXACT pinned commit\" proves\n   nothing about comparability — the release pipeline stamps its own tag's commit\n   by construction, and the two builds differ in scope, ignore state, Python\n   version and clustering.\n\n2. \"v2026.8.9 AND v2026.8.10 DO NOT EXIST\" — false. A subagent enumerated\n   `sources/mise/`, the local clone, which had never fetched those tags.\n   `git ls-remote --tags --refs https://github.com/jdx/mise 'v2026.8.*'` returns\n   v2026.8.0 THROUGH v2026.8.10 with no gaps. Its control arm (a tag the clone\n   DOES have) was structurally incapable of detecting the bound.\n   The damage was worse than the claim: acting on it, it rewrote\n   `sources/mise.manifest` from the COMMIT `d9a27434a4` to the annotated TAG\n   OBJECT `084e518fba`. `refs/tags/v2026.8.9^{}` is the commit; `refs/tags/...`\n   without `^{}` is the tag object. Reverted.\n\n3. THE mise WEDGE WAS NEVER A RACE. `backend/mod.rs:3139` takes an fslock keyed\n   on (tool short, version) FORTY-SIX LINES BEFORE dispatching to the\n   backend-specific `install_version_` at :3185, so it is backend-agnostic —\n   upstream #11794 being a Rust PR was a red herring. `install_state.rs:633`\n   shows `.lock()` BLOCKS. So mise already serialises same-tool installs and two\n   `bun install` of one id could not race. A hung `dtrace-provider` gyp build held\n   that lock; every later `mise run` blocked at :3139. THE DISCRIMINATING\n   OBSERVATION: the waiters had NO CHILDREN — they blocked before reaching the\n   code that spawns bun. A race predicts two live install trees; a blocking lock\n   predicts one wedged holder and N childless waiters at 0% CPU.\n\nHOW TO APPLY\n- Before reporting \"X is absent upstream\", query the REMOTE (`git ls-remote`,\n  `gh api`), never a local clone. A clone is a bound you cannot see from inside.\n- A control arm must be able to produce the OTHER answer. A tag present in the\n  clone cannot test for one the clone never fetched.\n- When an artifact is offered as a control arm, first ask what it was BUILT\n  FROM. An artifact that never contained the input cannot testify about it in\n  either direction.\n- `%CPU` misleads on IO-bound work; sample CUMULATIVE cpu twice. Identical across\n  a window means wedged, not slow.\n- Grepping a directory of SYMLINKS for their target text returns 0 forever. Read\n  the targets. A same-shape control (`knowledge-base` -> 0) is what exposed it.\n"
---

# Q: Does graphify's published self-graph confirm the sample.luau loss, and was the mise wedge a concurrent-install race?

## Answer

Round of 2026-08-20 on `graphify-corpus-0947`.

ASKED: finish the green kb-build, then run the graphify semantic extraction.

WHAT WAS BUILT
A fourth stderr approver for graphify's #1689 "no AST extractor for this
language" warning, with its own `ExpectedUnsupportedLanguage` struct — kept
separate from `ExpectedPartialExtraction` because the two expire on different
events: a partial extraction changes when the FILE or grammar changes, a missing
extractor only when UPSTREAM ships one. Approval requires the reviewed inventory
to account for every counted file exactly (same languages, same per-language
totals, compared as dicts so an over-covering inventory also fails), each path to
still hash as reviewed, and each to still contribute ZERO nodes. That last check
is what expires the approval the day an extractor lands. 7/7 mutation arms died,
1/1 control held.

MEASURED ENTRIES
- code-review-graph tests/fixtures/sample.R + test_sample.R: 0 nodes each,
  7 symbols lost. Control arm: 53 other tests/fixtures files ARE in the sub-graph.
- code-review-graph tests/fixtures/sample.luau: 10 nodes, lost_symbols=2 — NOT 3.
  The control arm changed the number: the sibling sample.lua (same fixture, no
  type annotations) misses `local x = function` too, so graphify's Lua extractor
  never graphs that form and `transform` was never lost to the parse error.
- graphify tests/fixtures/sample.luau: 5 nodes (stub + 4 functions),
  lost_symbols=0, first error line 8 (the `type ServerConfig` alias).

THE SURVEY THAT REPLACED TWENTY BUILDS
`graph.build` fails fast on the first unapproved warning, so each ~15-minute
build cleared exactly one source. A survey calling the same `_extract_code` per
source and catching the refusal named EVERY blocker in one pass: 65 askable,
50 OK, 15 BLOCKED, all `scope = corpus`, in three cause groups.

OUTCOME: useful. The approver, three measured entries and the survey all landed;
the extraction did not run because C4 authority was never given.


## Outcome

- Signal: corrected
- Correction: A PROBE THAT READS THE LOCAL CLONE REPORTS THE CLONE, NOT THE WORLD — and a
control arm drawn from the same clone cannot catch it.

Three beliefs were overturned this round, all the same shape: a bounded probe
whose bound was invisible from inside it.

1. THE PUBLISHED SELF-GRAPH IS NOT A CONTROL ARM FOR THIS QUESTION.
   `graphify-self-graph.tar.gz` (v0.9.48) is built by
   `graphify extract graphify/ --out .` over the PACKAGE directory only — 82 .py
   files, with `*.md`/`*.txt` appended to `.graphifyignore`. It contains zero
   bytes referring to `tests/`, `luau` or `fixture`. So it neither shows the same
   loss nor a clean extraction: IT NEVER ASKED THE QUESTION. Both readings were
   on offer and both were wrong. Never cite it as "upstream sees the same loss".
   Control arm: the same grep over our whole-clone extraction of the same commit
   returns 20 / 332 / the fixture.
   Corollary refuted as a tautology: "built from the EXACT pinned commit" proves
   nothing about comparability — the release pipeline stamps its own tag's commit
   by construction, and the two builds differ in scope, ignore state, Python
   version and clustering.

2. "v2026.8.9 AND v2026.8.10 DO NOT EXIST" — false. A subagent enumerated
   `sources/mise/`, the local clone, which had never fetched those tags.
   `git ls-remote --tags --refs https://github.com/jdx/mise 'v2026.8.*'` returns
   v2026.8.0 THROUGH v2026.8.10 with no gaps. Its control arm (a tag the clone
   DOES have) was structurally incapable of detecting the bound.
   The damage was worse than the claim: acting on it, it rewrote
   `sources/mise.manifest` from the COMMIT `d9a27434a4` to the annotated TAG
   OBJECT `084e518fba`. `refs/tags/v2026.8.9^{}` is the commit; `refs/tags/...`
   without `^{}` is the tag object. Reverted.

3. THE mise WEDGE WAS NEVER A RACE. `backend/mod.rs:3139` takes an fslock keyed
   on (tool short, version) FORTY-SIX LINES BEFORE dispatching to the
   backend-specific `install_version_` at :3185, so it is backend-agnostic —
   upstream #11794 being a Rust PR was a red herring. `install_state.rs:633`
   shows `.lock()` BLOCKS. So mise already serialises same-tool installs and two
   `bun install` of one id could not race. A hung `dtrace-provider` gyp build held
   that lock; every later `mise run` blocked at :3139. THE DISCRIMINATING
   OBSERVATION: the waiters had NO CHILDREN — they blocked before reaching the
   code that spawns bun. A race predicts two live install trees; a blocking lock
   predicts one wedged holder and N childless waiters at 0% CPU.

HOW TO APPLY
- Before reporting "X is absent upstream", query the REMOTE (`git ls-remote`,
  `gh api`), never a local clone. A clone is a bound you cannot see from inside.
- A control arm must be able to produce the OTHER answer. A tag present in the
  clone cannot test for one the clone never fetched.
- When an artifact is offered as a control arm, first ask what it was BUILT
  FROM. An artifact that never contained the input cannot testify about it in
  either direction.
- `%CPU` misleads on IO-bound work; sample CUMULATIVE cpu twice. Identical across
  a window means wedged, not slow.
- Grepping a directory of SYMLINKS for their target text returns 0 forever. Read
  the targets. A same-shape control (`knowledge-base` -> 0) is what exposed it.
