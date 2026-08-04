# Silent-failure review — `feat/154-extension-typo`

**Commit reviewed: `7a32c8eadef89b1d294baaa112e5fef884b96965`** (branch
`feat/154-extension-typo`, base `main` = `6584fbd`). Lane: silent failures,
inadequate error handling, inappropriate fallback.

Scope read: `git diff main...HEAD` over
`python/src/kb_setup/citations.py`, `python/src/kb_setup/resolve.py`,
`python/src/kb_setup/handoff.py`, plus the three test modules.

Gate run: `uv run pytest tests/test_citations.py tests/test_resolve.py
tests/test_handoff.py -q` → **rc=0, 201 passed**.

Every claim below is either cited to a `file:line` and a probe I ran, or
labelled unverified. Scratch under
`/private/tmp/claude-501/…/scratchpad/` (`p1.py`–`p6.py`, `h1.md`); working
tree left clean.

---

## Summary

The feature works: an unmarked `graph.jsom` is caught, and the two extractors
are provably disjoint so one typo never produces two findings. The deliberate
silence is, in the main, honest silence.

Four defects, all in **`resolve_extension_typo` / `_check_extension_typos`**.
Three of them are the *opposite* of the risk the design argues about: the
module reasons carefully about under-reporting, and where it goes wrong it
**over**-reports — it emits `no file named X` about tokens the index says are
present. One is a real mute button. A fifth is pre-existing and out of diff but
was explicitly named in the brief.

| # | Sev | Claim | Anchor |
|---|---|---|---|
| F1 | MEDIUM | `(absent)` is an **unfalsifiable mute** for the new typo check, and the rendered hint tells the reader the opposite | `handoff.py:141`, `handoff.py:507` |
| F2 | MEDIUM | AMBIGUOUS under the written spelling is collapsed into `no file named X` — the four-state discipline broken in the one place it was newly extended | `resolve.py:315` |
| F3 | MEDIUM | The token's **own existence test** runs against the authored-only index, so a real vendored file is reported as absent | `resolve.py:314`–`316` |
| F4 | MEDIUM-LOW | Trailing `,` / `:` inside a code span is promoted to a mistyped-extension FAIL; 3 of 3 in-the-wild findings over 386 files are this class | `citations.py:97`, `citations.py:478` |
| F5 | LOW | A token ending in a bare `.` proposes `.c`/`.h` repairs — the empty extension is unguarded beside the `isdigit` guard | `citations.py:449`–`478` |
| F6 | MEDIUM (**pre-existing, not this diff**) | A malformed `mise.toml` silently disables the **entire gate check**, with no record | `resolve.py:495`, `handoff.py:262` |

---

## F1 — MEDIUM — `(absent)` is an unfalsifiable mute for the typo check, and the report advertises the opposite

`handoff.py:141-150`, `handoff.py:507-509`, `resolve.py:338-341`.

The brief asks me to verify the code's own argument rather than accept it. The
argument at `handoff.py:142-148` is:

> Always MISSING by construction here, so this can only ever confirm the
> marker. **The both-directions rule is not weakened**: a token that RESOLVES
> never reaches this function…

The first sentence is true and is precisely the problem. `resolve_extension_typo`
has exactly two exits — `None` (`resolve.py:316`, `resolve.py:330`) and
`Resolution(State.MISSING, …)` (`resolve.py:338`). `_check_absent_marker`
returns `Verdict.OK` for MISSING (`handoff.py:168-169`). So for a marked typo
candidate the only two outcomes in the whole input space are **no finding** or
**OK**. There is no input that makes the marker fail.

That is what makes it a different object from the marker on every other check.
For an ordinary path the marker is self-policing — mark something that exists
and you FAIL — and the docstring at `handoff.py:158-166` rests the whole design
on that ("a marker that could only suppress findings would be a mute button an
author could paste beside anything"). For extension typos the marker **is** that
mute button: paste `(absent)` next to any real typo and it is silenced forever,
with no way for the checker to catch you.

Probed end-to-end (`scratchpad/h1.md`, `uv run kb-setup handoff-check`):

```
FAIL  path  h1.md:3  `graph.jsom` — no file named graph.jsom … did you mean graphify-out/graph.json?
   (line 4, `graph.jsom` (absent), produced the single OK — no FAIL, no AMBIG)
…
  (a path cited BECAUSE it is absent: write `` `path` (absent) `` —
   the marker is checked both ways, so it cannot hide a real miss)

1 OK, 0 ambiguous, 0 unverifiable, 3 broken   (only broken exits 1)
```

The last part is the sharp end. `_check_extension_typos` files these under the
`path` check name **deliberately** so the hint reaches them — its own docstring
(`handoff.py:130-134`) says "this is the finding whose reader is most likely to
have cited the token on purpose … it is exactly the moment the hint exists for."
So the branch routes a user-visible promise — *"the marker is checked both ways,
so it cannot hide a real miss"* — to the one check for which that sentence is
false. A reader staring at a `graph.jsom` FAIL is told, by this tool, that
pasting `(absent)` is safe because it is checked both ways. It is not.

Two supporting observations:

- The both-directions rule has a genuine hole for unknown extensions, not merely
  an unexercised one. Probe C (`scratchpad/p5.py`): a tmp repo containing a real
  `notes.org`, input `` `notes.org` (absent) `` → `handoff.check` returns `[]`.
  A marked citation that resolves produces **no finding**, because
  `resolve_extension_typo` silences on RESOLVED before the marker is consulted
  (`resolve.py:315`). This is not a regression — `main` also produced nothing —
  but it means the "checked both ways" claim was already narrower than the hint
  states, and this branch widens the surface the hint is printed on.
- Minor internal inconsistency: the same docstring justifies the `continue` at
  `handoff.py:139-140` on the grounds that "an OK finding would inflate the OK
  count with tokens nothing actually checked", and then the branch nine lines
  below emits exactly such an OK.

**What would settle it:** either give `resolve_extension_typo` a way to
contradict the marker, or stop routing the "checked both ways" hint to typo
findings, or say plainly in the hint that for a mistyped extension the marker is
an assertion the checker cannot test.

## F2 — MEDIUM — AMBIGUOUS under the written spelling is collapsed into "no file named X"

`resolve.py:315`:

```python
if resolve_path(repo_root, token, authored).state is State.RESOLVED:
    return None
```

Only RESOLVED silences. `State` exists with four members precisely so that
"could not tell" is never rendered as a verdict (`resolve.py:96-114`, and the
module docstring's first paragraph). Here AMBIGUOUS — *several real files match
this token* — falls straight through to the repair gate and, if exactly one
repair resolves, produces `MISSING` with the detail string **`no file named
Program.cs`**, which the index directly contradicts.

Probe A (`scratchpad/p2.py`), tmp fixture with `a/Program.cs`, `b/Program.cs`,
`a/Program.c`:

```
A: resolve_path('Program.cs')      -> AMBIGUOUS  '2 files match: a/Program.cs, b/Program.cs'
A: resolve_extension_typo          -> MISSING    'no file named Program.cs — its extension looks mistyped; did you mean a/Program.c?'
A: check                           -> Finding(check='path', verdict=FAIL, …)
```

Reachability today, measured over 386 authored markdown files
(`scratchpad/p3.py`): **4 candidate occurrences are AMBIGUOUS under their
written spelling** — all four are `go.mod`, matching 37 files — and none of them
has a resolving repair, so **0 fire today**. That count is the condition on the
claim and it moves the moment a repair lands.

The weaker sibling is `len(hits) != 1 → None` (`resolve.py:329`). I do **not**
call that a defect: there the token genuinely names nothing, and two candidate
referents is a guess. But note the asymmetry — the code reaches for silence when
*it* cannot decide, and for a confident FAIL when the *filesystem* cannot.

## F3 — MEDIUM — the token's own existence test uses the authored-only index, so a real vendored file is reported absent

`resolve.py:313-316`. `authored = idx.authored_only()` is threaded into **both**
the token check and the repair check. The docstring at `resolve.py:297-311`
argues the narrowing only in terms of the repairs (`runner.os` suffix-matching
`sources/hk/src/step/runner.rs` — "the single false positive in the corpus
measurement"), and then explains what is *kept* checkable ("a literal
full-length vendored path a reader actually wrote"). What it does not address is
the bare vendored filename — which the `Index` docstring at `resolve.py:135-139`
says is the whole reason the vendored tier exists: *"handoffs cite
`watch.py:1499` and `redactions.rs:31` meaning graphify's and mise's own
source."*

Probe B (`scratchpad/p2.py`), tmp fixture with `sources/upstream/pkg/watch.pyi`
and `python/watch.py`:

```
B: resolve_path('watch.pyi')   -> RESOLVED  'vendored: sources/upstream/pkg/watch.pyi'
B: resolve_extension_typo      -> MISSING   'no file named watch.pyi — its extension looks mistyped; did you mean python/watch.py?'
B: check                       -> Finding(check='path', verdict=FAIL, …)
```

The tool asserts a file does not exist while its own `resolve_path` can open it.

Reachability today (`scratchpad/p3.py`): **2 candidate occurrences resolve
only-vendored** — both `docker-server.mjs` → `sources/GitNexus/docker-server.mjs`
— and neither has a resolving repair, so **0 fire today**. Same condition as F2.

The narrow fix that preserves the measured `runner.os` win: silence on the
**full** index for the token's own existence test, keep `authored_only()` for
the repairs. That is exactly the distinction the docstring already draws between
"the tier from the INDEX" and "the tier from the answer" — it is applied to one
of the two questions and not the other.

## F4 — MEDIUM-LOW — trailing punctuation is promoted to a mistyped-extension FAIL

`_NON_PATH_CHARS` (`citations.py:97`) lists `*?[]{}<>|\$!"'`^…` — no comma, no
colon. `_LINE_REF_RE` needs `:\d+`, so a bare trailing `:` slips past the guard
at `citations.py:546`. `_ext_repairs` then treats the punctuation as part of the
extension and "repairs" it by deleting one character.

Measured over 386 authored markdown files (`scratchpad/p3.py`): 173 candidates
reach the repair gate, **28 become findings**. 25 of those are self-referential
— review reports and the new `docs/research/reports/2026-08-04-…-mutation-arms.md`
quoting `mise.tomlx` / `graph.jsom` / `hk.pk` as examples of this very feature.
The **3 remaining, in-the-wild findings are all punctuation artifacts, and 0 are
real typos**:

| finding | source text |
|---|---|
| `` `pr.py:` `` → "did you mean python/src/kb_setup/pr.py?" | `review-3c38ceb…-standards.md:52` — *"converted every `pr.py:`/`evals.py:`"*, a **pattern**, not a citation |
| `` `evals.py:` `` → same | same line |
| `` `.agent/plans/session-2026-07-31.md,` `` | `review-6ca1a55…-cold.md:10` — a comma inside the backticks |

Reproduced end-to-end in `scratchpad/h1.md`: both forms FAIL.

**Bound on the severity, stated because it matters:** over the tool's *current*
input — the 33 `.agent/plans/session-*.md` handoffs — this class fires **0
times** (`scratchpad/p4.py`; the only 2 findings there are the self-referential
`mise.tomlx` in `session-2026-08-04-c.md`). So it does not break the checker
today. It matters because `citations.py`'s own opening docstring names "a goal
document, a research report" as the next consumers, and review reports are where
all three hits live. On that corpus the new extractor's precision is 0/3.

`citations.py:12-14` sets the standard this is measured against: the naive
version's "4 false positives out of 9" is why the module is biased to
under-report. This is the one place the branch reverses that bias.

## F5 — LOW — a token ending in a bare `.` proposes `.c`/`.h`

`_ext_repairs` (`citations.py:449-478`) guards `lowered.isdigit()` but not the
empty string. `_one_edit_apart("", "c")` is **True** (the deletion arm at
`citations.py:443-446` accepts `len` difference 1 with `shorter == ""`).

```
_ext_repairs('')                -> ('c', 'h')
typo_candidates('`resolve.`')   -> TypoCandidate(text='resolve.', repairs=('resolve.c', 'resolve.h'))
```
(`scratchpad/p1.py`.)

No `.c`/`.h` exists in this repo's authored tree, so it fires 0 times here — the
candidate is built and then silenced by the resolve step. In a repo with one, a
sentence-final `` `foo.` `` would be reported as a typo of `foo.c`. The same
one-line comment the `isdigit` guard already carries would cover it.

## F6 — MEDIUM — **pre-existing, out of this diff** — a malformed `mise.toml` silently disables the entire gate check

Named in the brief (item 3, `resolve.declared_tasks`), so I checked it, but it
is #147 code and unchanged on this branch.

`resolve.py:495-496` swallows `TOMLDecodeError` / `OSError` / `UnicodeDecodeError`
to `frozenset()`. `handoff.py:262` then filters gate claims with
`if c.task in declared`. Empty set ⇒ **every gate claim is dropped with no
record**, while every task claim is simultaneously FAILed — so the run exits 1
for the wrong reason and the highest-stakes claims in the document vanish
silently.

Control-armed (`scratchpad/p5.py`), same input text both arms:

| arm | `mise.toml` | task findings | gate findings |
|---|---|---|---|
| D | `this is not [ valid toml` | 2 × FAIL "not declared … (0 tasks declared)" | **0** |
| D2 (control) | valid, declares `lint`+`test` | 2 × OK | **2 × UNVERIFIABLE** |

The probe discriminates. The docstring at `resolve.py:487-489` calls the empty
set "the honest reading when there are no declarations to check against" — that
is defensible for the *task* check, which at least discloses `(0 tasks
declared)`. It is not defensible for the gate check, which produces nothing at
all. This is the pattern `.claude/rules/probes-need-a-control-arm.md` names —
a bound that removes a whole class with no record of the removal.

(Aside on the brief's wording: I could not find the literal string *"no silent
caps: if a workflow bounds coverage, log what was dropped"* in that rule file.
The rule's actual text is *"Bound-limited searches are suspect by
construction"* + *"Say which arm you ran"*. I evaluated against what the rule
says, which is the same principle.)

---

## Checked and cleared — not defects

- **`except tomllib.TOMLDecodeError, OSError, UnicodeDecodeError:`**
  (`resolve.py:495`) is **not** a Python-2 syntax error. PEP 758 (Python 3.14)
  allows unparenthesized `except` tuples. Control arm: `ast.parse` on the file
  returns `PARSE OK`, and the 201-test suite imports the module.
- **Double-reporting.** `path_citations` and `typo_candidates` are disjoint:
  over 386 markdown files the `(text, line)` intersection is **0**
  (`scratchpad/p6.py`). Control arm — the sets are not both empty:
  `` `mise.toml` and `mise.tomlx` `` yields `['mise.toml']` / `['mise.tomlx']`,
  so 0 is a real disjointness, not a vacuous one.
- **`_typo_candidate` ordering** (`citations.py:540-546`): `is_path_like` first,
  then the categorical rejections. The docstring's correction of its own earlier
  draft is accurate; the behaviour is right.
- **`hits` counted on RESOLVED alone, named afterwards** (`resolve.py:317-337`).
  The round-2 fix is correct. The `match is None → hits[0].detail` fallback is
  unreachable with today's tiers and fails to a string rather than a crash.
- **`line_count`** (`resolve.py:519-533`): `OSError → None`, not 0, documented,
  correct. `errors="replace"` removes the `UnicodeDecodeError` path.
- **No new `try`/`except` anywhere in the diff.** Nothing is swallowed by the
  new code itself; F6 is inherited.
- **`_ext_repairs` `isdigit` guard** (`citations.py:471-477`) is real and needed:
  `_ext_repairs('3')` → `()`, verified.
- **`typo_candidates` dropping tokens without a word** (`citations.py:570-577`)
  is genuinely "not a claim about this repo" — a bare `.md` in prose. Correct
  silence.

## On the brief's question 2 — is `None` a smuggled fifth state?

No, and I want to be precise about why, because it is the question the design
is most exposed on. `None` is not a *verdict*; it means the token never enters
the finding stream, which is `main`'s behaviour for every unknown extension
preserved unchanged. That is a legitimate shape.

The problem is not that `None` exists. It is that `resolve_extension_typo` uses
`None` for two things that are not the same: "this is not a claim about this
repo" (correct — the token resolves, `resolve.py:315`) and "I cannot tell
whether this is a typo" (`len(hits) != 1`, `resolve.py:329`). The second is what
`State.AMBIGUOUS` is for, and the module's own first paragraph says collapsing
"could not tell" is how every defect in the sibling engine's review happened.
Here it is collapsed toward silence, which is the safe direction — so I rate it
an observation, not a defect. F2 is the same collapse pointed the **other** way,
toward a confident FAIL, and that one is a defect.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; branch `feat/154-extension-typo` at `7a32c8eadef89b1d294baaa112e5fef884b96965`.
- [python/cpython](https://github.com/python/cpython) — PEP 758, to control-arm the `except A, B:` form at `resolve.py:495` before reporting it as a syntax error (verified locally via `ast.parse` rather than by fetching, so this is a knowledge citation, not a fetch).
