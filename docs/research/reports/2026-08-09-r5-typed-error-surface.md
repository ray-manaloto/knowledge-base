# R5 — a typed error surface for `kb_setup`: screening and recommendation

**Date:** 2026-08-09 · **Requirement:** §2.1 R5 — *"treat `kb_setup` as an SDK,
with proper error codes via enums (not bare ints, not ad-hoc rcs)"*
(`docs/directives-2026-08-08.md:92`).

**Status of the ask:** Ray ruled the *approach*, not the answer — research
first, recommend, then decide. Three readings were offered in the previous round
and explicitly **not** chosen. This report screens the field and recommends one;
it does not decide.

---

## 1. What the previous round recorded, and the one correction

`docs/research/reports/2026-08-09-r1-r12-answers.md:97` states *"No enum-based
error surface exists, and no candidate for one was screened."*

The second clause is right. The first is **half right, and the half that is
wrong changes the recommendation**: `Enum` is already the house idiom here — for
*outcomes*, never for *errors*.

| measured in `python/src/kb_setup/` | value | probe |
|---|---:|---|
| `Enum` / `StrEnum` classes | **15** across **8** modules | `grep -rn "from enum import\|(Enum)\|(StrEnum)"` |
| — named `Verdict` | 4 (`handoff`, `arms`, `evals`, `goal`) | same |
| — others | `Decision`, `Phrasing` (`evals`), `State` (`resolve`), `PrState` (`session_state`), `Coverage` (`handoff`) | same |
| custom exception classes | **5** | `grep -rn "^class .*Error"` |
| `raise` sites (code-anchored) | **73** | `grep -rn "^\s*raise "` |
| — of which `raise SystemExit(<str>)` | **22** | `grep -rn "raise SystemExit"` |
| `return 0` / `return 1` / `return 2` | **70 / 34 / 71** | `grep -rn "^\s*return [0-9]+\s*$"` |

Control arm for the counting greps: `from dataclasses import` → **39** files, so
the probe shape discriminates rather than always returning zero.

The five existing exceptions, with their bases — note that four already
subclass a *semantic* stdlib error rather than `Exception`:

| class | base | module |
|---|---|---|
| `FetchRejectedError` | `Exception` | `fetch.py:96` |
| `BadRequestError` | `ValueError` | `skill_eval.py:621` |
| `SpecError` | `ValueError` | `arms.py:122` |
| `ReclaimError` | `RuntimeError` | `reclaim.py:105` |
| `NotAuthorizedError` | `RuntimeError` | `currency/apply.py:57` |

### The finding that reframes R5

**The enum R5 asks for already exists — as an undeclared convention written 175
times.** `0` / `1` / `2` are not arbitrary here:

- `2` is *malformed request or the check never ran*. `check.py:321` returns 2
  when no paths were passed; `check.py:327` returns 2 when **nothing actually
  ran** — the "a gate that never asked the question is not a pass" rule, encoded
  as an integer literal with no name.
- The meaning is asserted in prose in `CLAUDE.md` (`kb-skill-score` … *"rc 2 on
  a malformed request"*) and in `mise-tasks-only.md`, but is **declared nowhere
  in code**.

So R5 is not introducing a taxonomy. It is **naming one that 175 call sites
already agree on and that no reader can discover without grepping.**

> ⚠️ **The "already agree" half of that sentence is FALSE — see §8a.** It is left
> standing rather than edited because the claim, and how it survived into a
> shipped PR, is itself the finding. The count is also 173, not 175 (§8c).

---

## 2. What real tools do — screened against pinned or SHA-recorded source

Screened by shallow clone and read directly; every claim below is from source,
not from a docs page or an issue tracker.

### 2a. Modern Python SDKs do **not** use enums for error codes

| project | SHA / pin | error surface |
|---|---|---|
| `anthropics/anthropic-sdk-python` | `009b035305e0` | exception hierarchy; the code is a **class attribute**: `status_code: Literal[400] = 400` (`src/anthropic/_exceptions.py:108-150`) |
| `openai/openai-python` | `0c09a3fe8151` | **identical** shape, same lines, same `Literal[...]` attributes |
| `pallets/click` | `9c4dfdaebe0e` | `ClickException.exit_code: ClassVar[int] = 1`; `UsageError.exit_code: ClassVar[int] = 2` (`src/click/exceptions.py:39,77`) |
| `encode/httpx` | `b5addb64f016` | pure hierarchy, **no codes at all** (`httpx/_exceptions.py`) |

**openai-python is not an independent data point** — it is Stainless-generated
from the same generator as the Anthropic SDK, which is why the two files agree
line for line. Counting it as corroboration would be counting one decision
twice.

The Anthropic SDK result is worth stating precisely because it is the opposite
of what R5's phrasing assumes:

> **Zero `from enum import` across all 1,097 Python files in the `anthropic`
> package.**
>
> Control arm, same tree, same command shape: **939** files match `class `,
> **748** match `Literal[`. The probe discriminates; the zero is real.

Its wire-level error discriminator (`.type` → `"invalid_request_error"`,
`"rate_limit_error"`, …) is a plain **string**, not an enum.

The shared pattern across all four: **the code rides on the exception class as a
typed attribute, and the taxonomy is the class hierarchy.**

### 2b. The tools that *do* use an enum are CLIs — and this repo pins two of them

| project | pin | enum |
|---|---|---|
| `astral-sh/ruff` | `0.16.2` / `5b48a04097` | `pub enum ExitStatus { Success, Failure, Error }` → `0 / 1 / 2` (`crates/ruff/src/lib.rs:38-53`) |
| `astral-sh/uv` | `0.12.3` / `507230998c` | `pub enum ExitStatus { Success, Failure, Error, External(u8) }` → `0 / 1 / 2 / passthrough` (`crates/uv/src/commands/mod.rs:108-120, 243-252`) |

`ruff`'s doc comments map onto this repo's convention almost word for word:

```rust
/// Linting was successful and there were no linting errors.   Success => 0
/// Linting was successful but there were linting errors.      Failure => 1
/// Linting failed.                                            Error   => 2
```

**But ruff and uv disagree on the meaning of 1 and 2.** uv's `Failure` is *"a
failure caused by user input"* and its `Error` is *"an unexpected failure"* —
the inverse emphasis. That disagreement is the argument *for* an enum rather
than against it: two tools by the same vendor, sharing the same three integers,
mean different things by them, and only the enum's member names and doc comments
record which.

This repo's meaning matches **ruff**, not uv: `1` is *we ran and found
something*, `2` is *we could not run / you asked wrong*.

`uv`'s fourth member, `External(u8)`, is directly relevant here — `kb_setup`
constantly propagates a subprocess's rc (`graphify`, `hk`, `pytest`), which is
neither of the three named cases.

---

## 3. The R6 interaction — answered, and the answer is "capable but not
indicated"

The previous round left this explicitly open: *"nothing here establishes that
`datamodel-code-generator` is the right tool for enums as opposed to models."*

**It is capable.** From the pinned source (`sources/datamodel-code-generator`):

- `src/datamodel_code_generator/model/enum.py:128,241,248` defines `Enum`,
  `StrEnum` (`BASE_CLASS = "enum.StrEnum"`), and `IntEnum`
  (`BASE_CLASS = "enum.IntEnum"`).
- `enum.py:256-259` maps `Types.int32/int64/integer → IntEnum` and
  `Types.string → StrEnum`.
- `arguments.py:776` exposes `--use-specialized-enum` — *"Use specialized Enum
  class (StrEnum, IntEnum). Requires --target-python-version 3.11+"*.

**It is not indicated for this.** `datamodel-code-generator` generates *from a
schema*. An exit-code enum with three or four members has no upstream schema and
no external contract; authoring a JSON Schema whose only purpose is to emit a
four-member `IntEnum` inverts the cost. R6's case is models parsed from external
shapes; R5's enum is an internal vocabulary. **Hand-write this one, and let R6
own the generated models.**

Recorded because the path-probe nearly produced a false negative: the first
grep used `sources/datamodel-code-generator/datamodel_code_generator/...` and
returned zero. The real path carries a `src/` prefix. Control arm (`find … -name
'*enum*'`) is what caught it — a bound, not an absence.

---

## 4. Recommendation — one reading, and what it is not

Of the three readings offered and not chosen:

| reading | my verdict | **Ray's ruling, 2026-08-09** |
|---|---|---|
| an exception hierarchy with an **enum code on each** | recommended | not chosen |
| a `Result` / error-return type, **no exceptions across the boundary** | not recommended — **for a reason that did not survive re-probing**, see below | **CHOSEN** |
| **only the process exit codes** become an enum | recommended as phase 1 | not chosen as the whole answer |

**Ray ruled the `Result` reading**, against my recommendation and having read the
evidence-against in the option text. Re-probing after the ruling found my
argument against it was scope-broken (below) and that the ruling has direct
precedent in `ruff` and `uv`. The design that follows from it is in §6.

### Recommended: `IntEnum` exit codes **plus** an exception hierarchy — in that order

**Phase 1 — declare the convention that already exists.** One `IntEnum` in
`kb_setup`, modelled on `ruff`'s `ExitStatus` with `uv`'s passthrough member:

```python
class Rc(IntEnum):
    OK = 0            # ran, nothing to report
    FINDINGS = 1      # ran, found something the caller must act on
    BAD_REQUEST = 2   # could not run: malformed request, or nothing was checked
```

`IntEnum` and not `Enum`, because these values *are* returned to `SystemExit`
and compared against subprocess `returncode`s — an `IntEnum` member is an `int`
everywhere the current literals are, so this is a rename, not a rewrite. That is
also why this phase is safe to do first: it is 175 mechanical substitutions with
no behaviour change, and `ty` will catch a site that meant something else.

Phase 1 alone satisfies R5's literal words (*"proper error codes via enums, not
bare ints"*), which is why it is worth doing even if phase 2 is declined.

**Phase 2 — a root exception with the code attached.** This is the part the SDK
screening actually supports, and it is `anthropic`'s shape with the `Literal`
swapped for the phase-1 enum:

```python
class KbError(Exception):
    rc: ClassVar[Rc] = Rc.FINDINGS

class KbBadRequestError(KbError):
    rc: ClassVar[Rc] = Rc.BAD_REQUEST
```

The five existing exceptions reparent under `KbError`; the 22
`raise SystemExit(<string>)` sites become raises of a named subclass, and **one**
place converts a `KbError` to an exit code. That single conversion point is the
concrete win: today a caller cannot catch `kb_setup`'s failures at all, because
`SystemExit` inherits from `BaseException` and unwinds past every `except
Exception`.

### On the `Result`-type reading — and the scope error in my first answer

My first pass argued against it: *"nothing screened uses it; all four Python
projects raise; adopting it would mean `kb_setup` alone in its own ecosystem."*

**That claim was scoped to the four Python projects and then stated as though it
were about the whole field.** It is the `verify-before-advancing.md` §"carry a
fact's CONDITION" failure: the measurement was real, the condition ("…among
Python SDKs") got dropped, and the conclusion travelled further than the
evidence.

Re-probed against the two tools this repo already pins, with a control arm:

| project | `-> Result<` signatures | control (`-> ZZZNOPE<`) |
|---|---:|---:|
| `ruff` (`crates/ruff/src/`) | **49** | 0 |
| `uv` (`crates/uv/src/`) | **229** | 0 |

So the reading is not ecosystem-orphaned — it is how **this repo's own
toolchain** is built. `ruff`, `uv`, and `ty` are Rust, and Rust is
`Result`-native. What the Python SDKs show is a *Python* convention, not a
universal one, and `kb_setup` is closer in kind to `ruff` (a CLI whose callers
are mise tasks reading exit codes) than to `anthropic` (a library whose callers
are `try`/`except` blocks).

**And the two are not alternatives.** `ruff` uses both, which my three-way
framing obscured by presenting them as mutually exclusive:

```rust
pub fn run(...) -> Result<ExitStatus>   // lib.rs:128-133

Ok(ExitStatus::Success)   // ran, clean
Ok(ExitStatus::Failure)   // ran, FOUND SOMETHING  <- still Ok
Err(err)                  // could not run
```

The distinction that makes it work: **`Err` is reserved for "the tool broke".
"The tool ran and found problems" is `Ok`,** carrying an `ExitStatus` enum that
says so. A findings-bearing run is a *successful* run. `From<ExitStatus> for
ExitCode` (lib.rs:47-53) is the single conversion to `0`/`1`/`2`.

That is exactly the shape `kb_setup` needs, because its central confusion today
is precisely this one — `return 1` currently means both "found lint errors" and
"failed", and `return 2` means both "you asked wrong" and "nothing ran".

### What this recommendation does **not** claim

- **It does not claim an enum would have caught a past defect.** No such case
  was measured, and I did not go looking for one after forming the
  recommendation. The case rests on discoverability and on the ruff/uv
  disagreement, not on a prevented bug.
- **It does not claim the 175 sites are all correct.** They were counted, not
  audited. Phase 1 is where an incorrect one would surface.
- **It does not settle where `Rc` lives** (its own module vs. an existing one),
  which is a phase-1 implementation detail.
- **`FetchRejectedError` / `SpecError` / etc. keep their stdlib bases as a
  second base if desired** — `class SpecError(KbError, ValueError)`. Whether the
  `ValueError`-ness is load-bearing at any call site was **not** checked, and
  must be before reparenting.

---

## 5. Probes run, with their arms

| claim | probe | control arm |
|---|---|---|
| 15 enums / 8 modules in `kb_setup` | `grep -rn "from enum import\|(Enum)\|(StrEnum)"` | `from dataclasses import` → 39 files |
| 70/34/71 rc literals | `grep -rn "^\s*return [0-9]+\s*$"` | same probe with `ZZZNOPE` → 0 |
| anthropic SDK has no enums | `grep -rl "from enum import"` → **0** | `class ` → 939, `Literal[` → 748, of 1,097 `.py` files |
| dcg emits `StrEnum`/`IntEnum` | read `model/enum.py`, `arguments.py:776` | first path returned 0; `find -name '*enum*'` found the real `src/` path |

**Not verified, stated as such:** an earlier `grep -rhoE "raise [A-Za-z_]+"`
over-counted by matching the word "raise" inside prose comments (`raise out`,
`raise here`). The code-anchored `^\s*raise ` count of 73 is the one used above;
the exception-type frequencies from the bad probe are not reproduced here.

---

## 6. What was built under the ruling

`python/src/kb_setup/result.py` + `tests/test_result.py`, and **one command
converted end to end** as the proving slice: `kb_setup.check`.

```python
class Rc(IntEnum):        # IntEnum: a member IS an int, so adoption is a rename
    OK = 0                # ran, nothing to report
    FINDINGS = 1          # ran, FOUND something          <- still a success
    BAD_REQUEST = 2       # could not run / nothing checked

Ok[T](value, rc=Rc.OK)    # rejects rc=BAD_REQUEST — not representable
Err(message, rc=…)        # rejects rc=OK, and rejects a blank message
External(code)            # a subprocess's OWN code, passed through (uv)
type Result[T] = Ok[T] | Err | External
exit_code(result) -> int  # the ONLY conversion (ruff's `From<ExitStatus>`)
```

**`External` is a third variant, not an `Rc` member — and that is a substitution
worth flagging rather than burying.** Ray asked for `Rc.EXTERNAL` on 2026-08-09.
It is not representable: an `IntEnum` member is one fixed integer, and the whole
point of `uv`'s `External(u8)` is that it *carries* the code — `External(17)`
and `External(3)` are different exit codes. Making it a member would mean either
inventing a fixed integer (then it is not a passthrough) or hanging a payload
off an enum member (`IntEnum` has no room). The behaviour is uv's, unchanged;
only the spelling differs, and `Rc` stays the vocabulary of codes *we* choose.

It carries a range guard, for a reason that is not hypothetical:
`subprocess.run(...).returncode` is **negative** when the child was killed by a
signal (`-9` for SIGKILL). Passed through, that exits `247` after two's-complement
truncation — a plausible-looking code that means nothing. `External(-9)` raises.

The `check.py` conversion is deliberately ruff's two-function split:

```python
def check(...) -> Result[list[Outcome]]:   # boundary; returns, never raises, never prints
def main(...) -> int:                      # renders, then `return exit_code(result)`
```

**`main` deliberately still returns `int`.** Every pre-existing
`assert check.main(...)` in `tests/test_check.py` is the regression arm: each
observable exit code is byte-identical after the refactor, which is what makes
the change safe to repeat across the other commands.

*(This sentence said "the eight" until the cold lane counted 7 — see §7.)*

### What the conversion actually bought, in one assertion

`check.py` previously had **two different `return 2`s** — a malformed request,
and a request that checked nothing (`kb-check -- x.rs`). They were the same
integer, so no caller and no test could tell them apart. Now:

```python
assert exit_code(malformed) == exit_code(nothing_ran) == 2   # unchanged
assert malformed != nothing_ran                              # newly true
```

### Verification

| gate | result |
|---|---|
| `mise run kb-check` (the three touched files) | rc **0** — ruff, format, ty, pytest |
| `mise run kb-gates` | **4/4** — lint, test, brain-audit, eval |
| `mise run kb-arms -- 2026-08-09-r5-result-arms.toml` | **7/7 arms died**, each naming its own test; **1/1 control held**; `restored rc=0` |

The arms spec is `docs/research/reports/2026-08-09-r5-result-arms.toml`, and its
header states what the sweep cannot measure. The short version: it is a
statement about the *tests*, not about the premise — nothing in it re-opens
whether `Result` is the right answer, whether any caller actually **needs** the
`External` passthrough (it exists and is armed, but no command returns one yet —
`check.py` aggregates four tools and forms its own verdict, which is `Ok`), or
whether the other **174** rc sites mean what `check.py`'s four meant. Those were
counted, not audited.

### One test error worth recording, because it was mine

The first version of `test_findings_are_ok_not_err` asserted
`[o.tool for o in result.value if not o.passed] == ["ty"]` and failed with
`['ty', 'pytest']`. `Outcome.passed` is also `False` for a **skipped** tool, and
`a.py` has no sibling test, so pytest was skipped rather than failed. The
production code filters `not o.skipped` first; my test did not mirror it. The
fix was to the test. It is recorded because the failure mode is the one this
repo keeps paying for in the other direction — had the assertion happened to
pass, it would have been asserting something the module never claims.

### Not done, and deliberately

- **The remaining rc sites and message-raising `SystemExit` sites.** One command
  is the proving slice, not the migration. The sweep should be its own change
  with its own review. (This bullet said "174 rc sites and 22 `raise
  SystemExit`" until the audit; both were wrong — §8b and §8c. The live counts
  are tracked in §9, by MODULE rather than by site, because converting sites is
  what makes a site count stale.)
- **No command returns an `External` yet.** The variant exists on Ray's ruling
  and is armed, but the commands that wrap a *single* subprocess — where a
  passthrough is the right answer — are part of the un-done sweep. Until one
  does, the claim "flattening loses information" remains reasoned, not measured.
- **No `kb-remember` / `kb-reflect` yet** — the round is not closed.

## 7. Cold review — 1 finding, and it was an unarmed count

One lane (`fable-orchestrator:codex-reviewer`, OpenAI family — this diff was
Claude-written), reviewed cold against `origin/main...e846827`, scope excluding
`docs/research/**`. **1 finding, LOW, 0 blocking.** Report:
`.agent/kb/review/reports/review-e846827-cold.md`.

The finding: `check.py`'s `main` docstring claimed *"the eight existing
exit-code assertions"*. **There are seven.**

Verified before accepting it — a reader finding is a lead, not a fact — and it
is confirmed. The cause is worth more than the correction:

```
grep -n "main(" tests/test_check.py        -> 10 lines   <- what I counted
grep -c "assert check\.main(" …            ->  7         <- the actual thing
the three impostors: _touch(tmp_path / "x.rs", "fn main() {}\n")
```

Three of the hit-lines are a **Rust** `fn main() {}` inside a fixture string. I
counted grep hit-lines from a loose pattern and never armed it — in a change
whose own report has a §5 table about arming counting greps, and in a repo whose
last round measured its armed-grep rate at **9.5%**. Awareness did not produce
compliance; a different reader did.

Armed on the re-count: strict pattern → 7, a known-present sibling
(`check.check(`) → 6, a bogus token → 0. The probe discriminates.

**Fixed structurally, not correctively** — the docstring now names the *thing*
(*"every pre-existing `assert check.main(...)`"*) and carries **no figure at
all**, because a count there is invalidated by the next commit that adds a test.
Same remedy the previous round applied to a regex comment.

**What the lane verified by execution** (its own report, condensed): full suite
green, `ty` + `ruff` clean on all four touched files, the `Result`→exit-code
mapping traced by hand against pre-refactor behaviour and matching, `cli.py:234`
confirmed the only external caller of `check.main`/`check.check`, and all four
`result.py` guards confirmed to have paired accept/reject tests executed in both
directions.

**Round 2 was not run, deliberately.** The bound is two rounds; the finding was
LOW, non-blocking, and the fix is prose inside a docstring with no behaviour to
re-review. Spending a second cold lane on a comment edit is the disproportion
this skill was rewritten to remove (#67: 2.93M tokens, one real defect, change
reverted). Verification for the fix is the local gates, recorded below and in the
fix-round report.

## 8. The sweep's audit — three claims above are FALSIFIED

Written after the fact, deliberately left contradicting the sections above
rather than editing them into agreement: what §1 and §4 claimed, and what
auditing the sites actually found, is itself the finding.

### 8a. "175 call sites already agree" — **false**

§1 said the convention was consistent and merely undeclared.
`.claude/rules/mise-tasks-only.md` documents it **both ways**:

| line | tool | "matched nothing" exits |
|---|---|---:|
| 72 | `skill_lint` | **1** |
| 31 | `kb-skill-score` | **2** |

`check.py` independently chose **2**; `distill` returns a **string** (advisory,
always exits 0). One failure, three spellings, two of them documented in one
file. So the sweep is a **reconciliation**, not a rename — and every
disagreement is a behaviour change to a live gate, not something to fold into a
mechanical pass.

**Ray ruled a fourth member** on 2026-08-09 rather than force the case into a
code that misdescribes it: `Rc.NOT_RUN`. Neither `1` ("we looked and found
something" — we did not look) nor `2` ("you asked wrong" — the request was
fine).

**Its value was not invented.** The repo had already chosen `127` for exactly
this meaning, twice — `check.RC_COULD_NOT_RUN` and `gates._RC_COULD_NOT_RUN`,
both documented *"distinct from any tool's own failure rc, so 'broken' never
reads as 'failed'"*. Both now alias the member, so the constant is defined once.
Probed before adopting: no bare rc other than `0`/`1`/`2` is in use, and
**nothing in `kb_setup` branches on a specific non-zero code** (every check is
`!= 0`), so no consumer changed. `gates._RC_TIMEOUT = 124` stays a literal — a
gate that *started and was killed* is a different state, which `Rc` does not
model.

### 8b. "22 `raise SystemExit(<str>)` sites" — **19**

Three of the 22 are `raise SystemExit(main())` / `SystemExit(run())` — the
canonical `__main__` conversion, and **exactly** the `From<ExitStatus> for
ExitCode` boundary §4 argues for. Converting them would break the pattern. The
19 that remain split further: **6 at a command boundary** (`build()`,
`refresh_self()`, `generate()`) which convert to `Err` cleanly, and **13 in deep
helpers returning real values** (`_verified_ledger_chunks() -> list[...]`,
`derive_for() -> ProseStats`) which cannot without changing their contracts.
For those the defect is not that they raise — it is that `SystemExit` inherits
`BaseException`, so no consumer can catch a `kb_setup` failure at all.

### 8c. "the 174 rc sites" — **173, and 8 are not exit codes**

Two independent routes now agree at **173** (anchored grep; AST walk to the
enclosing function). Getting them to agree required fixing a defect in the AST
probe: **`bool` subclasses `int` in Python**, so `isinstance(v.value, int)`
matched every `return True`/`False` and reported 228. The grep disagreeing is
what surfaced it — a cross-check, not a re-read.

And **8 sites in 6 functions are not exit codes at all** — `_dir_size()`,
`_node_count()`, `_parse_size()`, `_brew_freed_bytes()`, `_as_int()`,
`line_count()`. Their `0` is zero-of-a-quantity. Renaming those to `Rc.OK`
would be a byte count asserting success. This is the "counted, not audited"
caveat in §6 paying off literally.

### What this tranche shipped

`Rc.NOT_RUN`, the two-constant dedup, the `skill_lint` reconciliation and the
amended rule line — plus a **closed** `Ok` guard (`rc not in _RAN`) replacing
the blacklist, so a fifth member is rejected by default rather than silently
becoming a valid `Ok`. That is the mutation `ok-guard-back-to-a-blacklist` arms.

**Arms: 10/10 died, 1/1 control held, restored rc=0.** The remaining conversion
of ~165 sites is a separate tranche and is NOT done.

## 9. The conversion tranche — the recipe, and where it stopped

**Converted so far: `check` (tranche 1), `lint_checks` (tranche 2),
`md_budget` / `skill_lint` / `handoff` / `session_state` / `distill` /
`skill_eval` (tranche 3, 2026-08-10), and `goal` / `hook_guard` / `gates` /
`launch` (tranche 4, 2026-08-10).** Stated as a count of modules rather than of
sites, because the site figure is what the conversion itself invalidates.

**The denominator was re-derived in tranche 3 and the old one was wrong in a
way worth recording.** An AST walk over `python/src/kb_setup/**` finds **95**
functions annotated `-> int` (control arm: 0 unannotated of 887 total, so the
walk is not silently skipping anything). That is *not* the conversion surface:
most are quantity-returners — `_dir_size`, `citations.line_of`, `lexical.size`,
the five `evals` counters — and §8c's "8 dangerous rows" are a subset of that
larger population, not the whole of it. The real surface is **the ~35 functions
`cli.py` dispatches to**. Eight are now converted.

### The recipe, in the shape both converted modules use

`ruff`'s two-function split (`crates/ruff/src/lib.rs:128` / `main.rs`):

```python
def check_<verb>(...) -> Result[T]:   # returns, never raises, PRINTS NOTHING
    ...
    return Ok(value, rc=Rc.FINDINGS if found else Rc.OK)

def <verb>(...) -> int:               # renders, then converts
    result = check_<verb>(...)
    if isinstance(result, Ok) and result.value:
        ...print...
    return exit_code(result)
```

Four rules that are not obvious from the shape:

1. **Findings are `Ok`.** A gate that ran and found something did its job.
   `Err` is only "could not run" — and several modules have *no* such case, so
   their boundary legitimately never returns `Err`.
2. **The `int`-returning wrapper stays.** `cli.py` and every pre-existing
   exit-code assertion are the regression arm; converting them in the same
   change removes the only thing proving the split changed no behaviour.
3. **The boundary prints nothing**, and there is a test asserting that. It is
   the property that makes the split worth anything — a boundary that prints
   cannot be re-rendered by §2.5's stdout sink.
4. **Do not touch the 8 quantity-returners** (§8c).

### Three traps this tranche hit, all of which cost a cycle

- **`ty` catches the annotation you guessed.** `check_no_lint_skip` was
  annotated `Result[list[tuple[str, int, str]]]`; the hits carry `Path`.
- **`TC002`**: a `pytest` import used only in an annotation must move into a
  `TYPE_CHECKING` block, which requires `from __future__ import annotations`
  in that test file.
- **Never write a suppression marker as a literal in a test.** `tests/test_lint_checks.py`
  concatenates (`"no" + "qa"`) precisely so `no_lint_skip` does not flag the
  repo itself. A generated test that planted the literal would have broken the
  gate it was testing.

### 9a. Tranche 3 (2026-08-10) — what six more modules taught

Six converted in one pass, all six mechanical against the recipe above. The
value was not in the mechanics; it was in three things the recipe did not
predict.

**1. Most of the split already existed.** `md_budget`, `skill_lint` and
`handoff` each already had a pure `check() -> Report` walker plus an
int-returning renderer. R5 typed the seam between them rather than inventing
one, which is why six modules fit in one tranche where two had filled the last.

**2. The "gate that never asked" divergence is in THREE places, and one module
says so in its own output.** All three return `Rc.OK` for a walk that matched
nothing:

| module | the never-asked case | what it returns | what it says |
|---|---|---|---|
| `skill_lint` | glob matched no skill | **`Err(rc=NOT_RUN)`** | "the gate did not run" |
| `md_budget` | `report.counted == 0` | `Ok(rc=OK)` | *(silent)* |
| `distill` | no transcripts found | `Ok(rc=OK)` | **"the detector did not run. This is not a clean result"** |

`distill`'s row is the sharp one: the module *prints* that it did not run and
still reports success, so the contradiction is already visible on stdout and
was invisible to every test. By this repo's own doctrine
(`probes-need-a-control-arm.md`) all three are `Rc.NOT_RUN`.

**They were NOT changed**, because rule 2 of the recipe keeps a conversion
behaviour-preserving so the pre-existing exit-code assertions stay a valid
regression arm. Each is pinned instead by a test named
`*_is_the_documented_divergence`, so closing it later is a deliberate edit to a
failing assertion rather than a silent behaviour change riding inside a
refactor nobody reviews as one. **Filed as one gap, not fixed three times: #270.**

**3. One module needed TWO boundaries, and the type is why.** `skill_eval`
printed its score table and *then* returned 2 when `--write` failed — a partial
success the vocabulary refuses to flatten: `Err` carries a message rather than a
table, and `Ok(rc=BAD_REQUEST)` is unrepresentable by construction. So scoring
and recording are separate boundaries (`check_skill_score` / `record_baseline`)
and the failed write is an honest `Err` of its own. This is the first case where
the closed `Ok` guard *changed a design* rather than merely validating one.

**A behaviour change worth stating rather than burying.** `skill_eval`'s
`[skill-score] scored by <X>` stderr line now prints *after* the scoring
subprocesses instead of before, because the boundary may not print. Content and
every exit code are unchanged; what is lost is a start-of-work signal on a slow
multi-skill run. That is rule 3 doing exactly what it says, and the progress
line is the kind of thing §2.5's event stream is for.

**Two more traps, both cheap and both repeatable:**

- **Narrow on `Ok`, never against `Err`.** `Result` has a *third* variant, so
  `if isinstance(result, Err)` leaves `Ok | External` and `External` has no
  `.value`. `ty` catches it; the positive narrow is also what keeps a renderer
  correct if its boundary later grows a passthrough.
- **A same-named test in two files can mis-target an arm.** Tranche 3's first
  draft added a second `test_findings_are_ok_not_err` (the other is in
  `tests/test_check.py`, and an existing arm targets it by name). Boundary tests
  are now module-prefixed — `test_skill_lint_findings_are_ok_not_err` — so an
  arm's `test =` cannot match the wrong module's test.

### 9b. What tranche 3 did NOT convert, and why it is a different shape

`graph_counts.report`, `insights.report`, and the `graphify_ops` family print
**progressively as they compute** rather than rendering once at the end. The
two-function split does not fit them without first restructuring their
rendering into a returned string — real work, and precisely the work §2.5's
stdout sink needs, so it belongs in that tranche rather than smuggled into this
one. They are named here so "not converted" reads as a decision rather than an
omission.

### 9c. The arms, and the one they caught

`docs/research/reports/2026-08-10-r5-tranche3-arms.toml` — **13/13 died, 1/1
control held, restored OK**, every arm naming its own test. The two that no
int-returning test could ever have caught are the *inverse* pair:
`distill-claims-findings` and `session-state-claims-findings` mutate an
advisory command into a gate, and both returned `0` before and after.

**`--dry-run` caught a stale anchor before the sweep ran.** The tranche-2 spec's
`skill-lint-back-to-bare-one` arm anchored on `        return Rc.NOT_RUN`, a
line this tranche's split deleted. It reported `PROBE BROKEN - a refactor moved
it` rather than passing; left alone it would have sat in the spec reading as
coverage it no longer had. Re-derived in the same change. This is the third
recorded instance of a refactor invalidating a mutation spec — `--dry-run`
after *any* edit to converted code is not optional.

### 9d. Tranche 4 (2026-08-10) — the ruling that half the list did not fit

Ray's tranche-4 ruling named **eight** boundaries: `goal.main` /
`goal.outcome_main`, `skill_refresh.refresh`, `hook_guard.run`, `gates.main`,
`launch.cc_main` / `launch.doctor_main`, `pr.ship_main` / `pr.land_main`. Measured
against recipe rule 3 before converting any of them, **only four are
render-once**. The other four print progressively between subprocess and network
calls — `pr.land_main` writes four `==>` lines interleaved with await / checks /
receipt / merge; `pr.ship_main` prints between push, upstream and PR-open;
`skill_refresh.refresh` prints, runs `fmt`, prints; `cc_main` prints, kills the
tmux server, prints, then execs a child. That is the same shape as the
`graphify_ops` family §9b already deferred, arrived at from the other direction.

Re-ruled on the measurement rather than on the list: **convert the four that fit,
defer the four that do not.** The deferred four join §9b's set as §2.5 stdout-sink
work. The cost of doing otherwise was specific and was what made this worth
asking about rather than deciding quietly — splitting `pr` under rule 3 would make
`kb-land` silent for the whole check-wait and `kb-ship` silent through the push,
on the two tasks this repo runs most.

**Converted: `goal` / `hook_guard` / `gates` / `launch`. That is 12 of ~35.**

**Three things the tranche taught that the recipe did not predict.**

**1. Two boundaries deliberately never return `Rc.FINDINGS`, and neither is an
oversight.** This is the first departure from recipe rule 1, and it happened
twice in four modules:

| module | why a findings-bearing run is still `Rc.OK` |
|---|---|
| `hook_guard` | a PreToolUse hook's verdict travels in its **stdout JSON**; the exit code only says whether the hook survived, and this guard is documented to fail OPEN. `Rc.FINDINGS` would make `exit_code` return 1, which in that protocol means *the hook crashed*. |
| `goal` | `kb-goal-check` is advisory by ruling — `render` prints "always exits 0; read the report, not the rc". `Rc.FINDINGS` would silently promote an advisory report to a gate. |

Both are pinned by a test carrying a control arm proving the two inputs really do
differ in what they found, so the shared `rc` reads as a choice rather than as a
checker that failed to look. Both are also armed: the realistic break is a
reviewer making the odd ones out *consistent* with the other ten boundaries.

**2. `gates.check_gates` needed a stated carve-out from rule 3, and stating it is
the point.** The boundary does print: `_run_one` writes a `==> gate:` line and
each gate's own stdio is inherited, so a 57-second run stays legible while it
happens (#146 criterion 8). Buffering that to satisfy the letter of rule 3 would
turn every gate run silent. What is asserted instead is the checkable part — the
**summary**, the thing `main` prints, does not escape the boundary — and there is
an arm on exactly that. A carve-out named and armed is a different object from
one nobody wrote down.

**3. `gates` is the recipe's cleanest fit so far**, because the three outcomes it
already drew by hand are the three the vocabulary names: gates ran and passed
(`Ok`), gates ran and one failed (`Ok`/`FINDINGS`), and *nothing ran* — an unknown
flag, an undeclared gate, an unreadable HEAD — which was already reserved as 2 and
is now `Err`/`BAD_REQUEST` carrying its reason in the type instead of only on
stderr.

**A fourth instance of #270's divergence was found and pinned, not fixed.**
`goal.main` with no argument and a tty stdin prints usage and returns 0, having
checked nothing. Same shape as `md_budget`'s `counted == 0` and `distill`'s
no-transcripts. Pinned as `test_goal_no_input_is_the_documented_divergence` for
the same reason the other three were: a conversion's regression arm IS the
pre-existing exit-code assertions.

### 9e. The arms — 11/11 died, and the survivor that taught the most

`docs/research/reports/2026-08-10-r5-tranche4-arms.toml` — **11/11 died, 1/1
control held, restored OK**, every arm naming its own test.

It took two runs, and the first run's single survivor is the finding worth
carrying. The arm meant to prove `gates.main` funnels through `exit_code`
replaced `return exit_code(result)` with `return 0 if gate_run.all_passed else 1`
and **survived**. The reflex reading is "the test is weak". The measurement says
otherwise — both arms, run rather than argued:

```text
all_passed=True   original=0  mutated=0  agree=True
all_passed=False  original=1  mutated=1  agree=True
```

`Rc.OK` **is** 0 and `Rc.FINDINGS` **is** 1, so the hand-rolled mapping is
*extensionally equal* to `exit_code` across the whole `Ok` branch. That is an
**inert mutant**, not a coverage gap: no test could kill it, and none written
later could either.

The consequence is the durable part. "Funnels through the single documented
conversion" is, in `gates.main` as it stands today, an **unobservable property** —
genuinely worth keeping, and not something a mutation arm can measure. Leaving
the arm in place would have been an id promising more than it can see
(`probes-need-a-control-arm.md` rule 9). It was replaced with a break that is both
observable and realistic — the renderer quietly made advisory (`return 0`), the
live temptation for a task people run constantly and want to stop failing — and
renamed `gates-renderer-drops-the-findings-rc` so the id names what it measures.

**Two survivor classes now have worked examples in this repo**: a real gap, and a
mutant that could never die. The sweep output renders them identically, so the
diagnosis has to be a separate step — and the cheap form of that step is asking
whether the mutated expression and the original can *ever* disagree.

### 9f. #270 closed (2026-08-10) — the one commit that moves an exit code on purpose

Every conversion tranche is behaviour-preserving by rule, precisely so the
pre-existing exit-code assertions stay a valid regression arm. This commit spends
that arm deliberately, in two places and nowhere else — which is why Ray ruled it
a separate commit rather than folding it into tranche 4, and why its arms live in
their own spec (`2026-08-10-r5-270-arms.toml`).

| module | case | was | now |
|---|---|---|---|
| `md_budget` | `report.counted == 0` | `Ok(rc=OK)` | `Err(rc=NOT_RUN)` |
| `distill` | no transcripts scanned | `Ok(rc=OK)` | `Err(rc=NOT_RUN)` |

`skill_lint` already drew it this way; these two were the structurally identical
cases reporting success. `distill`'s was the sharpest, because it *printed* the
contradiction — "the detector did not run. This is not a clean result" — while
returning 0, so it was visible to every operator and invisible to every test.

**Three things this cost that the ticket did not name.**

**1. `mise.toml`'s task comment said "ALWAYS rc 0".** A comment left contradicting
its own code is how the next reader is misled, so it was rewritten in the same
commit. The distinction it now draws is the real one: a *lead* still exits 0 —
that is what "never a gate" protects — but a run that examined nothing stops
claiming it examined nothing successfully.

**2. Three CLI tests broke, and they were a finding rather than a chore.**
`test_cli_dispatches_distill` and both `--limit` / `--min-scripts` fallback cases
stubbed `project_transcripts` to `[]`, using the never-ran case as a convenient
fixture while testing *dispatch* and *flag fallback*. They were given real
transcripts rather than re-pinned to 127: asserting dispatch by observing a
refusal is weaker than what they were written to check, and "did not raise"
demonstrated on a run that never read a flag cannot distinguish a working
fallback from an early exit. A test that fails when an unrelated behaviour
changes is usually testing through the wrong fixture.

**3. The over-correction is worse than the bug, so each new assertion ships with
a control arm.** `Err(rc=NOT_RUN)` returned *unconditionally* satisfies both new
tests — and would take the `md_size_budget` gate permanently red in **two** repos
and make an analyser documented as "never a gate" fail every run that found
something. `md-budget-always-refuses` and `distill-always-refuses` exist to prove
those controls can fail.

**Blast radius, checked rather than reasoned about.** dotfiles' `hk.pkl` does run
`uv run --project python kb-setup md-budget`, so the concern was real. It pins
this package by SHA (`46a3e7d8…` at the time of writing), so the change reaches
it only when that pin advances; and measured there on 2026-08-10, dotfiles counts
**57** instruction files against this repo's 32. `counted == 0` cannot arise in
either repo under normal operation — which is the point, not a reason to skip the
check: the change exists so that if a walk ever silently matches nothing, it says
so instead of reporting clean.

**Arms: 4/4 died, 1/1 control held, restored OK.** `--dry-run` caught a
non-unique anchor before the sweep — `if not report.scanned:` also appears in
`distill.render` — reporting *pattern is not unique* rather than mutating the
wrong occurrence. Fourth recorded instance of a spec anchor needing re-derivation.

**Still open: the FOURTH instance.** `goal.main` with no input (§9d) checks
nothing and returns 0. It is deliberately NOT closed here — `kb-goal-check` is
advisory by ruling, so a `NOT_RUN` there is a separate decision about an advisory
command rather than a consequence of this one. Pinned as
`test_goal_no_input_is_the_documented_divergence`.

## GitHub repos touched

- [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) — read `src/anthropic/_exceptions.py`; the primary Python-SDK error-surface data point. **Not in `sources/`** — candidate for `REGISTRY.md`.
- [openai/openai-python](https://github.com/openai/openai-python) — read `src/openai/_exceptions.py` as a second route; found to be the same generator, so not independent. **Not in `sources/`.**
- [pallets/click](https://github.com/pallets/click) — read `src/click/exceptions.py` for the `exit_code`-on-exception pattern and the 2-means-usage-error convention. **Not in `sources/`** — candidate.
- [encode/httpx](https://github.com/encode/httpx) — read `httpx/_exceptions.py` as the no-codes-at-all end of the range. **Not in `sources/`.**
- [astral-sh/ruff](https://github.com/astral-sh/ruff) — `ExitStatus` enum; already pinned at `sources/ruff.manifest` (0.16.2).
- [astral-sh/uv](https://github.com/astral-sh/uv) — `ExitStatus` enum incl. `External(u8)`; already pinned at `sources/uv.manifest` (0.12.3).
- [koxudaxi/datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator) — `model/enum.py`, `arguments.py`; already pinned at `sources/datamodel-code-generator.manifest`.
- [googleapis/python-api-core](https://github.com/googleapis/python-api-core) — attempted (the grpc `StatusCode`→exception mapping would have been the strongest enum precedent); the default branch clone contained only `LICENSE`/`README.rst`/`SECURITY.md`, so **nothing was read and no claim rests on it**. The package moved into the `google-cloud-python` monorepo. Left unscreened.

### 9g. Tranche 5 (2026-08-10) — the sink, and the six that needed it

**All six boundaries §9b and §9d deferred are converted** — `launch`
(`cc_main`/`doctor_main`), `graph_counts`, `insights`, `skill_refresh`,
`graphify_ops`, `pr` (`ship_main`/`land_main`). PR #273. This closes the
deferred set; what remains are the dispatched boundaries that were never blocked
on anything.

**The "~35" denominator this report has used since §9 is WRONG, and a cold lane
caught it while checking a status table built on it (2026-08-10).** `cli.py`
dispatches **44** distinct commands, not ~35, and **13 of 62 modules** import
`kb_setup.result`. Two corrections follow from that:

- every `N of ~35` above — including §9's own "eight are now converted" framing
  and §9d's "12 of ~35" — understates the remaining work by roughly a quarter.
  They are left in place as the record of what was believed at the time; this
  note is the correction, because rewriting them would erase the fact that four
  tranches were planned against a denominator nobody re-derived.
- **`goal.outcome_main` and `evals` are NOT converted**, though `goal.main` is.
  §9d recorded `goal` as converted, which is true of one of that module's two
  boundaries and was read as both.

`probes-need-a-control-arm.md` rule 6: an inherited number is not a measurement.
This one was inherited four times inside one report.

The unblocking work was §2.5's stdout sink, not more conversion — every one of
the six printed progressively, so recipe rule 3 ("the boundary prints nothing")
could not be met until events existed to print into.

**The conversion rule, stated once because it is what makes the tranche
checkable:** INFO wherever the original wrote to stdout, `warn`/`fail` ONLY
where it passed `file=sys.stderr`. The sink routes WARNING+ to stderr, so
choosing a level by its "natural" meaning would silently move lines between
streams — a behaviour change smuggled inside a refactor, which is the thing
recipe rule 2 exists to prevent. `pr.py` has zero stderr sites, so all 32 of its
conversions are `say` and nothing moves.

**`External` gets its first real user, and §9d's reasoned claim becomes
measured.** `launch.cc_main` returned a child's raw returncode:

| child died of | returncode | reported BEFORE | now |
|---|---:|---:|---:|
| SIGINT (Ctrl-C) | −2 | **254** | 130 |
| SIGKILL | −9 | **247** | 137 |
| SIGTERM | −15 | **241** | 143 |

Two's-complement truncation, exactly as `External.__post_init__`'s docstring
predicted. The dangerous part is that all three are *plausible* application exit
codes, so nothing ever flagged them — a Ctrl-C'd session read as a program that
chose to fail. `result.external_from_returncode` states the conversion once.

**One divergence declared rather than closed**, on §9a's #270 precedent:
`graph_counts.record_failed` emits at INFO while its text says "WARNING:".
Raising it would move the line to stderr AND double the prefix into
`WARNING: [tag] WARNING: …`. Both are fixable; neither is fixable *silently
inside a refactor*, because the pre-existing assertions about that output are the
only evidence the conversion changed nothing.

### 9h. What the tranche's defects say about where to look

Seven defects, and **none came from reading the diff** — five from a test going
red while building, two from an end-to-end arm after everything was green.

1. an `emit` with no sink attached writes **nothing**, so converting a function a
   test calls directly turns it silent while `cli.main` keeps working;
2. *"the logger has handlers"* is **not** *"a sink is attached"* — pytest's own
   `LogCaptureHandler` satisfied the lazy guard, a probe that could only answer
   one way;
3. a `StreamHandler` pins `sys.stdout` at construction, so on a process-global
   logger every later test's output went to the **first** test's buffer;
4. stdlib's `QueueHandler.prepare()` **stringifies** `record.msg` by design, so
   the listener hands `ProcessorFormatter` a `str` and the render raises *inside*
   the logging machinery — which swallows handler errors, making the symptom
   silently missing output;
5. teardown order — flushing before the listener drains writes nothing and looks
   correct on stdout.

**The two that only an end-to-end arm found**, after 30 green unit tests: every
line printed **twice**, and structlog internals leaked into the JSONL. Every test
passed an explicit `stream=` or ran `offload=False`, so all 30 were blind to the
**default path** — the only place either bug lived, and the only configuration a
user gets. That is the inverse of a test failing to own its environment: these
owned it too thoroughly.

### 9i. The review, and the finding that was inside the fix

Two rounds, `cold:codex`, 2 findings, 0 blocking.

Round 1 found `main` branching on `if "--audit" in args` — a membership test over
argv — silently discarding a record request. **Round 2 found the same bug still
reachable through `--question=Q`**, because the fix matched flag STRINGS.

The durable answer was not handling one more spelling. It was that **a decision
about what was asked for must come from the PARSED request, never from raw
tokens**: argparse already knows about `=`, prefix abbreviation and everything
else that would otherwise be re-implemented one discovered form at a time. The
test written to cover "the class, not just one flag" had used only the
two-token form, which is exactly why it could not see it.

A third defect surfaced from the CONTROL ARM of round 1's finding rather than
from the finding: `save-result` requires an answer and `check_remember` did not,
so a request valid at our gate died downstream in a raw argparse dump. The
original live arm had passed `--answer "yes"` — **an arm that supplies the field
cannot discover that the field is unchecked.**

**Still open from this tranche:** a malformed argv escapes the `Result` contract
entirely, because `argparse.error()` calls `sys.exit(2)`. The exit code is
coincidentally correct, which is why it is written down rather than left.
