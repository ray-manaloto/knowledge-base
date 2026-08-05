# kb-ship's branch-matched handoff gate (#149) — 17 mutation arms

Evidence for the gate `mise run kb-ship` now runs between the review receipt and
the four gates: it checks the **newest** `.agent/plans/session-*.md`, and only
when that handoff records the branch you are on. If it does and the handoff cites
something that is not there, the push is refused; otherwise the gate prints an
explicit SKIP.

Read **Finding 1 first**. The gate shipped for one review round reading a
different rule — scan handoffs newest-first for one matching the branch — and
that rule reproduces this ticket's own harm on 8 of 21 branches. The count below
is the count after that was fixed.

Two smaller things are worth more than the count. One arm SURVIVED and the
survival was a **no-op mutation, not a test gap** — chasing it found a comment
crediting the wrong mechanism for a property the code does enforce. And designing
the arms, before running any of them, found **two tests that could not fail**.

## Result

**17 of 17 arms died.** Control green before and after; tree restored. Every arm
mutates production code, runs `tests/test_citations.py tests/test_handoff.py
tests/test_pr.py`, and asserts rc≠0. The harness is embedded in full at the
bottom of this file — it is written to a session scratchpad, which does not
survive, so the copy here is the one a reader can actually run.

The table is **generated from the harness's own `ARMS` list** and asserted back
against this file (`probes-need-a-control-arm.md` rule 8) — a hand-transcribed
evidence table is a probe with no control arm, and this report's own Finding 1 is
a row that was wrong on first reading.

<!-- ARMS-TABLE -->
| # | mutation | site | if it SURVIVED |
|---|---|---|---|
| A1 | same-line rule | `citations._BRANCH_RE` | a `branch` word can claim a span on a LATER line |
| A2 | nearest-span (class) | `citations._BRANCH_RE` | `on branch **`x`** @ `sha`` yields the SHA, not the branch |
| A3 | ref-shape guard | `citations._is_ref_shaped` | prose captured between two spans is reported as a branch |
| A4 | lead bound | `citations.document_lead` | a branch named anywhere in the document counts as the recorded one |
| A5 | fence stripping | `citations.branch_mentions` | an example branch inside a fenced block is read as real |
| A6 | newest-first order | `handoff.handoffs` | the OLDEST handoff is treated as the newest |
| A7 | the branch match itself | `handoff.check_for_branch` | THE #149 REGRESSION — another session's handoff blocks this ship |
| A8 | skip is not a pass | `handoff.check_for_branch` | a skip with no handoffs at all renders as a pass |
| A9 | advisory stays advisory | `handoff.check_for_branch` | an UNVERIFIABLE gate claim refuses the push |
| A10 | first mention wins | `handoff.recorded_branch` | an aside naming another branch overrides the coordinates |
| A11 | unreadable-branch guard | `handoff.check_for_branch` | an unreadable branch reports as a checked no-match |
| A12 | the ship wiring line | `pr._pre_push_checks` | the gate is defined and never called |
| A13 | the refusal | `pr._handoff_holds` | a broken handoff is reported and shipped anyway |
| A14 | the report | `pr._handoff_holds` | the SKIP is silent, which is indistinguishable from a pass |
| A15 | cheapest-first order | `pr._pre_push_checks` | a broken handoff costs four gate runs before it refuses |
| A16 | ref-shape second half | `citations._is_ref_shaped` | `a..b`, `trailing/` and `x.lock` are reported as branches |
| A17 | unreadable-handoff guard | `handoff.check_for_branch` | kb-ship dies with a traceback instead of reporting a SKIP |
<!-- /ARMS-TABLE -->

A7 is the arm this ticket exists for. A12 and A14 are the two "delete the wiring
line" breaks `probes-need-a-control-arm.md` rule 2 asks for by name. **A16 and
A17 exist because the first 15 did not catch them** — see Finding 7.

## Finding 1 — the gate was built to the wrong rule, and it is measurable

#149's body and its acceptance criterion disagreed:

> body: *"skips when **the newest** handoff describes a different branch"*
> criterion 1: *"the newest handoff **whose recorded branch equals** the current
> branch"*

The first inspects only the newest handoff. The second scans back for a match.
It was built to the criterion, and the criterion is wrong.

`.agent/plans/` is append-only and handoffs cite paths, so an old handoff **rots**
as unrelated commits delete what it named. Both rules run over every branch this
repo's 35 handoffs record:

| rule | branches that REFUSE a ship |
|---|---|
| scan newest-first for a match | **8 of 21** |
| newest handoff only | **0 of 21** |

The 8 are `feat/145-kb-handoff-check`, `feat/clear-prep-protocol-rework`,
`docs/ray-directives-2026-08-02`, `docs/kb-serve-reference`,
`feat/settled-claims`, `feat/local-cross-family-review`,
`chore/kb-memory-mise-path-findings` and `fix/cc-doctor-judges-session-path` —
each on a handoff 1–7 days stale, whose FAILs are dead paths rather than defects
in the work being shipped. That is exactly the harm the ticket's rationale names
("the gate would have blocked a healthy PR"), relocated one file back rather than
removed, and it grows monotonically with the handoff count.

The implementation now follows the **body**. Criterion 1 was amended on the issue
with this measurement rather than diverged from silently.

**A second correction fell out of the same probe.** The ticket justifies itself
with a handoff that "pinned a commit six commits behind" and "asserted 'no review
receipt'". Neither is a FAIL under this checker: a stale-but-valid SHA resolves,
and the receipt line is prose. Verified — **every** FAIL in the corpus probe is a
path. So the harm class is path rot over time; the branch match bounds it and
newest-only is what closes it.

Found by the Spec lane of the two-axis review, which sampled 3 of the 8;
re-measured independently before acting.

## Finding 2 — a SURVIVAL that was a no-op mutation, and the comment it exposed

A2's first spelling flipped the quantifier: `[^`\n]*?` → `[^`\n]*`. It
**SURVIVED**. The reflex reading is "the nearest-span property is untested".

It is not. A backtick-free run can terminate at exactly one position — the first
backtick — so greedy and lazy find the same match and the mutation is the
identity. Measured, both arms, rather than reasoned:

```text
lazy         -> ['docs/kb-serve-reference']
greedy       -> ['docs/kb-serve-reference']
wide+greedy  -> ['3c9a887']            <- the class, not the quantifier
lazy vs greedy over 35 handoffs: 0 differ
```

So the property is enforced by the **character class**. The quantifier is inert.

**The defect was in the prose.** The constant's comment listed three mechanisms
and credited the third to laziness — *"lazy, so the same rule holds when a line
names two"*. That sentence would have told anyone widening the class that they
were still protected by the `?`. They are not: `[^\n]*` yields the SHA. The
comment now names the token that does the work and says the `?` does none, and A2
mutates the class, where it dies.

## Finding 3 — designing the arms found two tests that could not fail

Both were found on paper, before a single arm ran, by asking of each guard *what
mutation would kill the test that covers it*:

1. **The `if not branch:` guard (A11).** Deleting it leaves behaviour identical —
   `None` matches no recorded branch, so the result is SKIPPED either way. What
   changes is only the sentence: `the newest handoff … records `x`, not `None``,
   which reads as a checked answer about a branch nobody is on. The test asserted
   `coverage is SKIPPED` and `findings == ()`, both of which survive the
   deletion. It now asserts the summary.
2. **First-mention-wins (A10).** Every fixture had a lead naming ONE branch, so
   `mentions[0]` and `mentions[-1]` are the same element and the rule was
   unfalsifiable. A test with a two-branch lead — the real
   `| branch | `main` (the round's branch `feat/settled-claims` is merged) |`
   row — was added.

## Finding 4 — a fixture that could not exhibit its own harm

`test_ship_refuses_a_broken_handoff_for_this_branch` first failed for the wrong
reason: a `docs/gone.md` citation came back **UNVERIFIABLE**, not FAIL, because
`kb_setup.resolve` reads a path whose first segment names no directory here as a
claim about ANOTHER repo. `tmp_path` had no `docs/`, so the handoff was never
broken and the refusal under test could not happen. The fixture now writes a real
`docs/present.md`, and the reason is recorded on the helper.

Same class as #144's rename arm, and this is the second consecutive round where
the first draft of a refusal fixture could not produce the state it asserted
about.

## Finding 5 — the bound on `citations.document_lead`, measured rather than assumed

The branch is read from the document's LEAD (everything before the first `##`),
which is a bound, and `probes-need-a-control-arm.md` rule 3 makes bounds suspect
by construction. Both arms, over all 35 handoffs:

| | |
|---|---|
| agree | 31 (including all 29 the lead can read) |
| lead silent, whole-file answers | 4 |
| …of those, WRONG | 3 (`kb-land` twice, from prose about the task; a stale branch listed for deletion) |
| …of those, right | 1 (a `\| branch \| …` row under `## State at handoff`) |

The bound costs one correct answer in 35 and suppresses three wrong ones — the
direction this checker is biased in everywhere else, because a branch it fails to
read becomes a reported SKIP while a branch it reads wrong becomes a claim about
which document describes the current work.

**6 of 35 handoffs record no branch in their lead at all**, so the gate SKIPs for
them. Handoffs written from here on carry it by construction:
`mise run kb-session-state` (#144) emits a backticked `- **branch**:` bullet, and
`/clear-prep` step 6 now says so.

## Finding 7 — a 15-arm sweep still left two guards unarmed

The cold cross-family lane (OpenAI) was given a MUTATING brief rather than a
reading one, because this repo has measured that method predicts a blocker better
than lane identity. It mutated production lines itself and found **two guards
with zero coverage** that the 15 arms above had passed over. Neither was a live
defect — both guards are present and correct — but both were untested, which is
the same thing one edit later.

1. **`_is_ref_shaped`'s second line (A16).** A3 mutated the WHOLE body to
   `return True` and died — on the regex half. Deleting only
   `".." not in name and not name.endswith(("/", ".lock"))` left all 96 citation
   tests passing, because nothing exercised `a..b`, `trailing/` or `x.lock`;
   `_REF_SHAPE_RE` matches all three happily. **One function, two guards, one
   tested** — the shape #147's report names, where a coarse arm scores defended
   code as armed.
2. **The `OSError` arm on reading the newest handoff (A17).** Deleting the whole
   try/except left every test passing. The lane did not reason about
   reachability, it **constructed** the reaching case: a *directory* named
   `session-2026-01-01.md` under `.agent/plans/`, which an interrupted checkout
   or a stray `mkdir` produces. Without the guard that raises `IsADirectoryError`
   up through `_handoff_holds` into `ship_main`, so `mise run kb-ship` dies with
   a traceback instead of reporting a SKIP — a gate that crashes is not a gate
   that refuses.

Three tests were added and the two arms above now die. The lesson is about arm
GRANULARITY: an arm that replaces a whole function body tests only whichever
guard the fixtures already reach, and reports the rest as armed. Mutate one line.

The lane also independently control-armed Finding 2's no-op claim, reaching the
same result without being told the answer — which is what makes that claim
verified rather than merely asserted twice.

## Finding 6 — the harness is the FOURTH, and #160 is still the fix

The `__pycache__` `(mtime, size)` defect has now cost three harnesses (#145 had
the invalidation; #146 and #144 each regressed it). This one carries both
mitigations from the start — `__pycache__` purged per arm **and**
`PYTHONDONTWRITEBYTECODE=1` — and no arm behaved anomalously.

That is not a fix. #160 (make the harness a `kb_setup` module with a test) stays
open, and this file existing at all is one more data point that "write it down"
is not working as a remedy.

What the harness does have is the other guard #145's report asks for: an arm
whose pattern fails to match is reported as **SKIPPED — pattern matched 0 times**
and counted as a survivor, never as a pass. That fired for real during this round
— A9's anchor drifted by four spaces when `check_for_branch` was rewritten for
Finding 1, and the run said so instead of quietly scoring 14/14.

## Live arm — the gate against the real corpus

Not only fixtures. Run against this repo's actual `.agent/plans/`, after the
Finding 1 fix:

```text
chore/144-close-the-loop     `session-2026-08-04-e.md` records branch `chore/144-close-the-loop` — 0 broken, 24 OK
feat/145-kb-handoff-check    SKIP — the newest handoff session-2026-08-04-e.md records
                             `chore/144-close-the-loop`, not `feat/145-kb-handoff-check`
0 of 21 recorded branches now refuse (was 8)
```

Two inputs, two different outcomes, the right one each time — so the probe
discriminates on real data and not only on fixtures.

## The harness

Committed here rather than left in a scratchpad, per `agent-report-persistence.md`
§1b: a citation to a file only one machine can open is not a citation, and this
report is promoted to `docs/research/reports/`, the tier that rule governs. Run it
with `uv run python arms.py` from a copy anywhere inside the repo.

<!-- HARNESS -->
```python
"""#149 mutation arms — the FOURTH harness, and it carries #160's two mitigations.

Every arm mutates PRODUCTION code with a break that could really happen (delete
the wiring line, loosen the regex, collapse a state) and asserts the suite goes
RED. An arm that survives means the tests do not cover that line.

THE BYTECODE MITIGATION IS NOT OPTIONAL. CPython validates a cached `.pyc` by
(source mtime in whole seconds, source size). Most single-token mutations change
a file's length by 0 or +/-1, so adjacent arms collide routinely and pytest
imports the PREVIOUS arm's bytecode. That has now cost three harnesses (#145 had
it, #146 and #144 regressed it). Both belts:

  * every `__pycache__` under python/src is deleted before each arm;
  * every arm runs with PYTHONDONTWRITEBYTECODE=1, so no arm can leave an entry.

#160 is the structural fix (make this a `kb_setup` module with a test) and is
still open — this file is the interim, and its existence is the evidence that
"write it down" keeps failing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base")
SRC = ROOT / "python" / "src" / "kb_setup"
TESTS = ["tests/test_citations.py", "tests/test_handoff.py", "tests/test_pr.py"]

CITATIONS = SRC / "citations.py"
HANDOFF = SRC / "handoff.py"
PR = SRC / "pr.py"

#: (id, file, old, new, what a reader should conclude if it SURVIVES)
ARMS: list[tuple[str, Path, str, str, str]] = [
    (
        "A1 same-line rule",
        CITATIONS,
        r'_BRANCH_RE = re.compile(r"\bbranch\b[^`\n]*?`(?P<name>[^`\n]+)`")',
        r'_BRANCH_RE = re.compile(r"\bbranch\b[^`]*?`(?P<name>[^`\n]+)`")',
        "a `branch` word can claim a span on a LATER line",
    ),
    (
        # The FIRST spelling of this arm flipped `*?` to `*` and SURVIVED. That
        # was not a test gap: a backtick-free run terminates at exactly one
        # position, so the quantifier is inert and the mutation was the identity.
        # The property is enforced by the CLASS, so the class is what this
        # mutates — measured to yield `3c9a887` instead of the branch.
        "A2 nearest-span (class)",
        CITATIONS,
        r'_BRANCH_RE = re.compile(r"\bbranch\b[^`\n]*?`(?P<name>[^`\n]+)`")',
        r'_BRANCH_RE = re.compile(r"\bbranch\b[^\n]*`(?P<name>[^`\n]+)`")',
        "`on branch **`x`** @ `sha`` yields the SHA, not the branch",
    ),
    (
        "A3 ref-shape guard",
        CITATIONS,
        '    if not _REF_SHAPE_RE.match(name):\n        return False\n    return ".." not in name'
        ' and not name.endswith(("/", ".lock"))',
        "    return True",
        "prose captured between two spans is reported as a branch",
    ),
    (
        "A4 lead bound",
        CITATIONS,
        '    kept: list[str] = []\n    for line in strip_fences(text).split("\\n"):\n'
        "        if _SUBHEADING_RE.match(line):\n            break\n        kept.append(line)",
        '    kept: list[str] = []\n    for line in strip_fences(text).split("\\n"):\n'
        "        kept.append(line)",
        "a branch named anywhere in the document counts as the recorded one",
    ),
    (
        "A5 fence stripping",
        CITATIONS,
        "    stripped = strip_fences(text)\n    found: list[BranchMention] = []",
        "    stripped = text\n    found: list[BranchMention] = []",
        "an example branch inside a fenced block is read as real",
    ),
    (
        "A6 newest-first order",
        HANDOFF,
        "        key=lambda p: p.stat().st_mtime,\n        reverse=True,\n    )",
        "        key=lambda p: p.stat().st_mtime,\n    )",
        "the OLDEST handoff is treated as the newest",
    ),
    (
        "A7 the branch match itself",
        HANDOFF,
        "    recorded = recorded_branch(text)\n    if recorded != branch:",
        "    recorded = recorded_branch(text)\n    if False:",
        "THE #149 REGRESSION — another session's handoff blocks this ship",
    ),
    (
        "A8 skip is not a pass",
        HANDOFF,
        "    if newest is None:\n        return BranchHandoff(\n            Coverage.SKIPPED,",
        "    if newest is None:\n        return BranchHandoff(\n            Coverage.OK,",
        "a skip with no handoffs at all renders as a pass",
    ),
    (
        "A9 advisory stays advisory",
        HANDOFF,
        "    broken = any(f.verdict is Verdict.FAIL for f in findings)",
        "    broken = any(f.verdict is not Verdict.OK for f in findings)",
        "an UNVERIFIABLE gate claim refuses the push",
    ),
    (
        "A10 first mention wins",
        HANDOFF,
        "    return mentions[0].name if mentions else None",
        "    return mentions[-1].name if mentions else None",
        "an aside naming another branch overrides the coordinates",
    ),
    (
        "A11 unreadable-branch guard",
        HANDOFF,
        "    if not branch:\n        # None means git could not be asked (#144) — not \"no branch\". Either way\n"
        "        # there is nothing to match a handoff against.\n"
        "        return BranchHandoff(\n            Coverage.SKIPPED,\n"
        '            "SKIP — the current branch could not be read, so no handoff can be matched to it",\n'
        "        )\n\n",
        "",
        "an unreadable branch reports as a checked no-match",
    ),
    (
        "A12 the ship wiring line",
        PR,
        "    if not _handoff_holds(repo_root, branch):\n        return False\n\n"
        "    if not run_gates(repo_root):",
        "    if not run_gates(repo_root):",
        "the gate is defined and never called",
    ),
    (
        "A13 the refusal",
        PR,
        "    if result.coverage is not handoff.Coverage.BROKEN:\n        return True",
        "    if result.coverage is not handoff.Coverage.BROKEN:\n        return True\n    return True",
        "a broken handoff is reported and shipped anyway",
    ),
    (
        "A14 the report",
        PR,
        '    print(f"==> handoff: {result.summary}")',
        "",
        "the SKIP is silent, which is indistinguishable from a pass",
    ),
    (
        "A15 cheapest-first order",
        PR,
        "    if not _handoff_holds(repo_root, branch):\n        return False\n\n"
        '    if not run_gates(repo_root):\n        print("ship: gates failed — not pushing")\n'
        "        return False",
        '    if not run_gates(repo_root):\n        print("ship: gates failed — not pushing")\n'
        "        return False\n\n    if not _handoff_holds(repo_root, branch):\n        return False",
        "a broken handoff costs four gate runs before it refuses",
    ),
    (
        # A3 mutated the WHOLE body of `_is_ref_shaped` to `return True` and
        # died — on the regex half. A cold lane deleted only the SECOND line and
        # every test still passed. One function, two guards, one tested: the
        # coarse arm scored defended code as armed. (#147's report names this.)
        "A16 ref-shape second half",
        CITATIONS,
        '    return ".." not in name and not name.endswith(("/", ".lock"))',
        "    return True",
        "`a..b`, `trailing/` and `x.lock` are reported as branches",
    ),
    (
        # The one guard the whole 15-arm sweep could not kill, found by the cold
        # lane by CONSTRUCTING the reaching case (a directory where the newest
        # handoff should be) rather than reasoning about it.
        "A17 unreadable-handoff guard",
        HANDOFF,
        "    try:\n        text = newest.read_text(encoding=\"utf-8\", errors=\"replace\")",
        "    if True:\n        text = newest.read_text(encoding=\"utf-8\", errors=\"replace\")",
        "kb-ship dies with a traceback instead of reporting a SKIP",
    ),
]


def purge() -> None:
    for cache in SRC.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def suite() -> int:
    purge()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode


def main() -> None:
    control = suite()
    print(f"CONTROL (unmutated) rc={control}  {'OK' if control == 0 else 'BROKEN HARNESS'}")
    if control != 0:
        sys.exit("control arm is red — every result below would be meaningless")

    survived: list[str] = []
    for name, path, old, new, meaning in ARMS:
        source = path.read_text(encoding="utf-8")
        if source.count(old) != 1:
            print(f"{name:28} SKIPPED — pattern matched {source.count(old)} times")
            survived.append(f"{name} (pattern did not match — the arm never ran)")
            continue
        path.write_text(source.replace(old, new), encoding="utf-8")
        try:
            rc = suite()
        finally:
            path.write_text(source, encoding="utf-8")
        verdict = "DIED" if rc != 0 else "SURVIVED"
        print(f"{name:28} rc={rc} {verdict}")
        if rc == 0:
            survived.append(f"{name}: {meaning}")

    after = suite()
    print(f"\nRESTORED rc={after}  {'OK' if after == 0 else 'TREE LEFT DIRTY'}")
    print(f"{len(ARMS) - len(survived)}/{len(ARMS)} arms died")
    for s in survived:
        print(f"  SURVIVED — {s}")


main()
```
<!-- /HARNESS -->

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under change (#149, and #144/#145/#146/#147/#154/#160 for context).
