# #148 — elided report citations: mutation arms

**17/17 arms died.** Control green at both ends, tree restored
(`RESTORED rc=0`). Run: 2026-08-05, on `feat/148-agent-report-coverage`.

**Five of those 17 arms exist because REVIEW found defects the mutation sweep
could not** — see "What the review found" below.
The first sweep was 12/12 against code that was wrong in ways no arm asked
about; the second was 15/15 against code carrying a **false green shipped
inside the fix for the previous one**. That is this report's most useful
sentence: **a full mutation score is a statement about the tests, never about
the design** — and a fix is exactly as reviewable as the code it replaces.

Every arm mutates PRODUCTION code with a break that could really happen and
asserts the suite goes RED. An arm that survives means the tests do not cover
that line. The harness is the one committed with #149
(`2026-08-04-kb-ship-handoff-gate-mutation-arms.md`), **copied rather than
restated** — the `__pycache__` mitigation it carries has been lost by three
successive re-writes, so this round extracted the block programmatically and
swapped only `TESTS` and `ARMS`.

## What #148 closes

`kb_setup.citations` excludes the elision `…` from `path_citations` **by
construction** — it is in `_NON_PATH_CHARS`. That exclusion is correct for the
question `path_citations` asks (`Path.exists()` can say nothing about an
abbreviated name) and it made the hole total. Control-armed 2026-08-05:

| citation | before #148 |
|---|---|
| `review-0c58bd7…-cold.md` (real) | **no citation extracted** |
| `review-deadbee…-cold.md` (never existed) | **no citation extracted** |
| `review-0c58bd7…-silent-failure.md` (lane never ran) | **no citation extracted** |
| `review-0c58bd7cf4…-cold.md` (concrete, real) | `OK:path` |
| `review-deadbeef…-cold.md` (concrete, fake) | `FAIL:path` |

The last two rows are the control: the checker discriminates perfectly on
concrete paths and was blind on every elided one. Report citations carrying an
elision were the majority form.

**The count first written here — "21 of 52" — was wrong, and it now coincides
with the right one. Read that carefully.** The original 21 was a
pre-implementation tally of report-directory tokens *including* the brace forms
the extractor then went on to exclude; it was invalidated by the very commit
that wrote it, and the spec lane re-derived the extractor's actual output as
**18**. The F1 fix below (leading-elision normalisation) then admitted 3 more,
so `elided_citations` returns **21** over the 37 files in `.agent/plans/` today.

Two different quantities that happen to agree. Recorded rather than quietly
corrected back, because a reader seeing only the final number would conclude the
original claim had been right all along — it was not: it counted a different set
and was wrong about the set it named. `.agent/` is gitignored, so none of this is
re-derivable on another clone. The durable facts are the mechanism and the
control arm above, not the tally.

## Why prose extraction was NOT built

#148's criterion 1 says "agent names are extracted from the handoff". Three
readings were measured over all 37 handoffs before choosing:

| reading | yield | verdict |
|---|---|---|
| prose anchor (`\bagents?\b` + nearest span) | 42 captures, **1 correct** | unusable — `agent` is everywhere in this repo (`.agent/`, `docs/agents/`, `ready-for-agent`) |
| `<lane> lane` bound to its block sha | 31 mentions, **4 bindable**, 2 of those narrative | unusable |
| elided report citation | 21 report-directory tokens, **0 checked today** | built |

(That 21 is the pre-implementation tally described above — tokens naming a report
directory that `path_citations` refused. It is *not* the extractor's output, and
the two coinciding at 21 today is the coincidence recorded above.)

Criterion 1 was amended on the issue to name the extractable form.

## Why brace forms are NOT expanded

Ray adjudicated this on 2026-08-05. `session-2026-07-28-c.md` cites
`review-{fdd73c4…,e611b89…,2e43f8b…}-{standards,spec,cold,silent-failure}.md`,
which expands to 12 files while 9 exist — and the same table cell says
"(9 files)" while a table above it says round 3 was "cold only". The notation
compresses a list; it does not assert each member. Expanding it would report
three failures against a handoff that was accurate throughout.

## The one guard that was DELETED rather than tested

An arm flipping `elided_citations`' `_LINE_REF_RE` guard to `if False:`
**survived**. It was not a coverage gap: `is_path_like` already enforces the
property, because a `:<digits>` tail always lands inside the computed extension
and no allowlist entry contains a colon.

That claim was earned rather than derived (`probes-need-a-control-arm.md` rule 9,
whose worked example is a guard declared dead by true premises that never asked
whether an allowlisted extension ends in a digit — `mp3` does). **8 shapes across
all 36 known extensions, including that one, produced 0 tokens** that are both an
elided citation and a line reference, with both controls green. The guard was
removed: two guards for one property mask each other's mutations, which
`_ext_repairs` records being bitten by already.

## The arms

| arm | file | what it would mean if it SURVIVED | result |
|---|---|---|---|
| `B1 elision requirement` | `citations.py` | every ordinary path citation is ALSO extracted as an elided one | DIED |
| `B2 path-shape reuse` | `citations.py` | braces, templates and globs all become elided citations | DIED |
| `B4 segment bound` | `resolve.py` | an elision crosses `/` and becomes a `**` that matches almost anything | DIED |
| `B5 boundary anchor` | `resolve.py` | `laude/rules/x.md` resolves against `.claude/rules/x.md` | DIED |
| `B6 dir/file pool` | `resolve.py` | a trailing `/` no longer means a directory | DIED |
| `B7 vendored tier` | `resolve.py` | an elided citation into a pinned clone is reported broken | DIED |
| `B8 many matches resolve` | `resolve.py` | a deliberately loose elision is reported as needing disambiguation | DIED |
| `B9 miss classification` | `resolve.py` | a citation naming ANOTHER repo is reported as this repo's broken path | DIED |
| `B10 the wiring line` | `handoff.py` | THE #148 REGRESSION — the check is never called at all | DIED |
| `B11 variant strip wiring` | `handoff.py` | a lane recorded as `cold:codex` looks like a lane that never ran | DIED |
| `B12 absent marker both ways` | `handoff.py` | `(absent)` on an elided citation is ignored rather than adjudicated | DIED |
| `B13 variant strip scope` | `review.py` | any filename with a colon is silently rewritten before being checked | DIED |
| `B17 lane-suffix guard` | `review.py` | THE COLD-LANE BLOCKING DEFECT — a bare `review-x:y.md` is mangled into a false green | DIED |
| `B18 elided first segment` | `resolve.py` | an elided first segment softens a real miss to UNVERIFIABLE, which does not fail | DIED |
| `B14 variant strip directory scope` | `review.py` | a `review-` file in ANY directory is rewritten — the false-green direction | DIED |
| `B15 leading-elision normalisation` | `citations.py` | `…/review-abc…-cold.md` is dropped rather than checked | DIED |
| `B16 elision survives the variant strip` | `review.py` | `_safe_lane` eats the elision, turning a pattern into a literal | DIED |

## Finding on the live corpus

Running the new check over all 37 handoffs: **19 OK, 1 UNVERIFIABLE, 1 FAIL** (16 OK before the leading-elision fix below).

The FAIL is `docs/research/kb/reports/agents/…` in `session-2026-08-04.md`, and
it is self-confirming — that handoff's own sentence calls it "a report that is
nowhere on disk". `docs/research/kb/` does not exist; the real directory is
`docs/research/reports/`. The correct authored fix is the `(absent)` marker,
which the report's own hint teaches. It blocks nothing: `check_for_branch` reads
only the newest handoff recording the current branch.

The UNVERIFIABLE is `reflections/…`, which names `graphify-out/reflections/`.
`resolve_path` returns UNVERIFIABLE for the non-elided `reflections/LESSONS.md`
too, so the two checks agree rather than disagreeing.

## What the review found — three defects the 12/12 sweep did not

A two-axis review (Standards + Spec, both persisted under
`.agent/kb/reports/agents/`) ran against the first version. Every finding below
was re-verified here by executing before being accepted.

| # | defect | why the arms missed it |
|---|---|---|
| **H1** | `strip_lane_variant`'s docstring claimed a DIRECTORY scope the code never applied — it tested `startswith("review-")` on the basename alone, so `docs/review-2026:q3.md` became `docs/review-2026.md`. The FALSE-GREEN direction, defended by a sentence asserting the opposite. | the test varied the basename PREFIX, never the directory, so the reaching case was uncovered — a fixture that could not exhibit its own harm |
| **F1** | `…/review-5c38615…-cold.md` (4 occurrences) was dropped: an elided leading directory de-elides to a leading `/`, which reads as a path outside the repo. Concrete sha, concrete lane, concrete extension — the exact target class. | no arm mutates a case the extractor never reached |
| **H2/J3** | Two numeric claims were false. "4 `*` citations" was really **98** `*`-bearing spans (the 4 was a report-directory count that lost its bound on the way into a docstring — `md-size-budgets.md`'s own worked example, recommitted by the hand that cites it). "21 report citations" was a pre-implementation tally. | a comment is not executable, so no mutation can reach it |

One review suggestion was **declined after running it**: matching the writer
exactly by composing `_safe_lane(_lane_prefix(...))`. `_safe_lane` keeps only
alphanumerics, `-` and `_`, so it destroys the elision and silently turns a
pattern into a literal matching nothing. The two sides are asymmetric because
their inputs are — pinned by `test_strip_lane_variant_preserves_an_elision`.

Two further arms were added after the fixes exposed gaps of their own: **B13**
survived once the directory guard landed (the `review-` prefix is load-bearing
only for a BARE filename, which nothing tested), and **B7** reported
`SKIPPED — pattern matched 0 times` because the line it targeted had changed.
The harness naming a non-matching pattern rather than scoring it a pass is what
made both visible.

## Round 2 of review — the fix WAS the defect

A cold cross-family lane (OpenAI family; Claude authored the diff) reviewed
`2adf52057aaf` with a **mutating** brief, and found two more — both reproduced
end-to-end through `handoff.check` rather than reasoned about.

| # | severity | defect |
|---|---|---|
| **C1** | **BLOCKING** | `strip_lane_variant`'s directory guard — added to fix H1 — only fires when there IS a directory. A **bare** `review-gu…:draft.md` (a form the same function accepts on purpose) was rewritten to `review-gu….md`, globbed onto an unrelated `review-guide-notes.md`, and a citation existing NOWHERE was reported **OK**. The H1 fix closed one path to the false green and left the other open. |
| **C2** | MAJOR | `_elided_miss` stat-ed a first path segment that could itself contain an elision, so the test could never succeed and a real miss was softened from FAIL to **UNVERIFIABLE** — which does not fail the run. |

C1's fix is the guard that asks the actual question: does the variant-stripped
stem end in `-<lane>` for a lane in the closed `LANES` set? The two earlier
guards are proxies for "this names a lane report"; this one asks it.

**Adding it made both earlier guards' arms survive** (B13, B14) — not because
they were redundant, but because the cases they were armed on were now caught by
the new guard. Each needed a fresh reaching case constructed to prove it still
holds a distinct facet: `foo-cold:x.md` (lane suffix, no `review-` prefix) for
B13, and `docs/review-abc-cold:x.md` (prefix **and** lane suffix, wrong
directory) for B14. Three guards, three properties, three arms.

Two further arms reported `SKIPPED — pattern matched 0 times` because the lines
they targeted had moved under them. The harness naming a non-matching pattern
instead of scoring it a pass is the only reason that was visible.

## Reproducing it

The harness is NOT re-embedded here. It is byte-identical to the one committed
with #149 apart from `TESTS` and `ARMS`, and a second copy is the duplication
#160 exists to remove. Extract it and swap in the list below:

```python
src = Path("docs/research/reports/2026-08-04-kb-ship-handoff-gate-mutation-arms.md").read_text()
block = src.split("<!-- HARNESS -->\n```python\n", 1)[1].rsplit("\n```", 1)[0]
Path("arms.py").write_text(block)   # then replace TESTS and ARMS
```

`TESTS` for this round is `["tests/test_citations.py", "tests/test_handoff.py",
"tests/test_resolve.py", "tests/test_review.py"]`.

<!-- ARMS -->
```python
#: (id, file, old, new, what a reader should conclude if it SURVIVES)
ARMS: list[tuple[str, Path, str, str, str]] = [
    (
        "B1 elision requirement",
        CITATIONS,
        "        if token is None or ELISION not in token:",
        "        if token is None:",
        "every ordinary path citation is ALSO extracted as an elided one",
    ),
    (
        "B2 path-shape reuse",
        CITATIONS,
        '        if not is_path_like(token.replace(ELISION, "")):',
        "        if False:",
        "braces, templates and globs all become elided citations",
    ),
    (
        "B4 segment bound",
        RESOLVE,
        '    body = "[^/]*".join(re.escape(part) for part in needle.split(ELISION))',
        '    body = ".*".join(re.escape(part) for part in needle.split(ELISION))',
        "an elision crosses `/` and becomes a `**` that matches almost anything",
    ),
    (
        "B5 boundary anchor",
        RESOLVE,
        '    return re.compile(f"^(?:.*/)?{body}$")',
        '    return re.compile(f"^(?:.*)?{body}$")',
        "`laude/rules/x.md` resolves against `.claude/rules/x.md`",
    ),
    (
        "B6 dir/file pool",
        RESOLVE,
        "    pool = idx.dirs if wants_dir else idx.files",
        "    pool = idx.files",
        "a trailing `/` no longer means a directory",
    ),
    (
        "B7 vendored tier",
        RESOLVE,
        "    vendored = [p for p in idx.vendored if pattern.match(p)] if not wants_dir else []",
        "    vendored = []",
        "an elided citation into a pinned clone is reported broken",
    ),
    (
        "B8 many matches resolve",
        RESOLVE,
        '    return Resolution(State.RESOLVED, f"{label}{len(matches)} files match: {shown}{more}")',
        '    return Resolution(State.AMBIGUOUS, f"{label}{len(matches)} files match: {shown}{more}")',
        "a deliberately loose elision is reported as needing disambiguation",
    ),
    (
        "B9 miss classification",
        RESOLVE,
        "    segments = token.strip(\"/\").split(\"/\")\n    first = segments[0]\n"
        "    if len(segments) == 1 or (repo_root / first).exists():\n"
        '        return Resolution(State.MISSING, f"nothing matches (repo-relative): {token}")',
        "    segments = token.strip(\"/\").split(\"/\")\n    first = segments[0]\n"
        "    if True:\n"
        '        return Resolution(State.MISSING, f"nothing matches (repo-relative): {token}")',
        "a citation naming ANOTHER repo is reported as this repo's broken path",
    ),
    (
        "B10 the wiring line",
        HANDOFF,
        "    findings.extend(_check_elided(repo_root, c, index)"
        " for c in citations.elided_citations(text))\n",
        "",
        "THE #148 REGRESSION — the check is never called at all",
    ),
    (
        "B11 variant strip wiring",
        HANDOFF,
        "    got = resolve.resolve_elided(repo_root, review.strip_lane_variant(cite.text), index)",
        "    got = resolve.resolve_elided(repo_root, cite.text, index)",
        "a lane recorded as `cold:codex` looks like a lane that never ran",
    ),
    (
        "B12 absent marker both ways",
        HANDOFF,
        "    if cite.marked_absent:\n"
        '        return _check_absent_marker("elided", cite.text, cite.line, got)',
        "    if False:\n"
        '        return _check_absent_marker("elided", cite.text, cite.line, got)',
        "`(absent)` on an elided citation is ignored rather than adjudicated",
    ),
    (
        "B13 variant strip scope",
        REVIEW,
        '    if not dot or not stem.startswith("review-") or _SKIP_SEPARATOR not in stem:',
        "    if not dot or _SKIP_SEPARATOR not in stem:",
        "any filename with a colon is silently rewritten before being checked",
    ),
]
```

## GitHub repos touched

_None._ All measurement was against this repository's own corpus.
