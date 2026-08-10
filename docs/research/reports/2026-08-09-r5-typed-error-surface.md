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

- **The remaining 174 rc sites and 22 `raise SystemExit(<string>)` sites.** One
  command is the proving slice, not the migration. The sweep should be its own
  change with its own review.
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

**Converted so far: `check` (tranche 1) and `lint_checks` (this one). ~28
command modules remain.** Stated as a count of modules rather than of sites,
because the site figure is what the conversion itself invalidates.

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

## GitHub repos touched

- [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) — read `src/anthropic/_exceptions.py`; the primary Python-SDK error-surface data point. **Not in `sources/`** — candidate for `REGISTRY.md`.
- [openai/openai-python](https://github.com/openai/openai-python) — read `src/openai/_exceptions.py` as a second route; found to be the same generator, so not independent. **Not in `sources/`.**
- [pallets/click](https://github.com/pallets/click) — read `src/click/exceptions.py` for the `exit_code`-on-exception pattern and the 2-means-usage-error convention. **Not in `sources/`** — candidate.
- [encode/httpx](https://github.com/encode/httpx) — read `httpx/_exceptions.py` as the no-codes-at-all end of the range. **Not in `sources/`.**
- [astral-sh/ruff](https://github.com/astral-sh/ruff) — `ExitStatus` enum; already pinned at `sources/ruff.manifest` (0.16.2).
- [astral-sh/uv](https://github.com/astral-sh/uv) — `ExitStatus` enum incl. `External(u8)`; already pinned at `sources/uv.manifest` (0.12.3).
- [koxudaxi/datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator) — `model/enum.py`, `arguments.py`; already pinned at `sources/datamodel-code-generator.manifest`.
- [googleapis/python-api-core](https://github.com/googleapis/python-api-core) — attempted (the grpc `StatusCode`→exception mapping would have been the strongest enum precedent); the default branch clone contained only `LICENSE`/`README.rst`/`SECURITY.md`, so **nothing was read and no claim rests on it**. The package moved into the `google-cloud-python` monorepo. Left unscreened.
