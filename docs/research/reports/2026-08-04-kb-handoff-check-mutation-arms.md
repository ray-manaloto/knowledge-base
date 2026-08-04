# `kb-handoff-check` mutation arms (#145)

Evidence for #145's last acceptance criterion:

> Every check is mutation-tested: break it, confirm the test fails, restore,
> confirm it passes. The harness must clear cached bytecode — a same-size edit is
> otherwise served from a stale .pyc and the arm reports a false pass.

The harness is committed here rather than left in a scratchpad because a
mutation result nobody can re-run is an assertion, not evidence — and because
`.claude/rules/probes-need-a-control-arm.md` #6 says an inherited number is not a
measurement. Anyone can re-derive the table below from the script.

Run 2026-08-04 against `feat/145-kb-handoff-check`:
**32 of 32 arms discriminated, control included.**

The arms grew across two rounds of cold cross-family review. Round 1 added six
(repo-escape containment, the `sources/` root's own level, a directory citation
naming a file, an `(absent)` marker over an AMBIGUOUS resolution, a reversed
line range, fence-length tracking); round 2 added nine more, closing both the
symlink half of containment and four CommonMark rules the fence and code-span
parsing did not implement.

## Why row 0 is a control

Every other row asserts that a mutation makes a named test FAIL. If the harness
itself were broken — wrong path, a `uv run` that cannot resolve, a fragment that
never applies — every arm would "fail" and the run would read as total success.
Row 0 applies a no-op edit and asserts the suite stays GREEN, so a uniformly
dead harness is distinguishable from a working one.

This is not hypothetical in this repo: a previous round recorded four mutation
arms that appeared to die at once, and the cause was zsh word-splitting in the
harness rather than anything in the code under test.

## Why bytecode is cleared every round

CPython invalidates a cached `.pyc` on `(mtime, size)`. A mutation that swaps
two lines changes neither, so the interpreter serves the *pre-mutation*
bytecode and the arm reports the test still passing — a false pass, on the one
class of edit a reviewer is most likely to try. The harness deletes every
`__pycache__` under the repo before and after each arm AND runs the suite with
`PYTHONDONTWRITEBYTECODE=1`.

## Results

| # | Arm — what was broken | Test that had to fail | Result |
|---|---|---|---|
| 0 | **CONTROL** — no-op comment edit | *(suite must stay green)* | ✓ |
| 1 | path check: direct-exists guard removed | `test_a_cited_path_that_does_not_exist_fails` | ✓ |
| 2 | file:line check: the past-EOF comparison dropped | `test_a_line_reference_past_the_end_of_the_file_fails` | ✓ |
| 3 | task check: declaration lookup bypassed | `test_an_undeclared_task_fails` | ✓ |
| 4 | absent marker: reverse direction removed | `test_a_path_marked_absent_that_actually_resolves_fails` | ✓ |
| 5 | fence stripping: the call that blanks a fenced block deleted | `test_code_spans_ignore_fenced_blocks_but_keep_line_numbers` | ✓ |
| 6 | exclusion by construction: the elision character dropped | `test_an_elided_path_is_not_a_path` | ✓ |
| 7 | suffix match: segment boundary weakened to substring | `test_a_suffix_must_align_on_a_segment_boundary` | ✓ |
| 8 | resolution order: vendored consulted before authored | `test_a_vendored_source_clone_never_shadows_the_authored_tree` | ✓ |
| 9 | pruning: the derived tree no longer pruned by name | `test_a_nested_derived_tree_is_pruned_too` | ✓ |
| 10 | line_count: unreadable reported as zero instead of unknown | `test_line_count_of_an_unreadable_file_is_none_not_zero` | ✓ |
| 11 | exit code: a broken citation no longer exits 1 | `test_main_exits_1_on_a_real_miss` | ✓ |
| 12 | single-segment circularity: the len==1 escape removed | `test_an_absent_top_level_directory_is_a_real_miss_not_unverifiable` | ✓ |
| 13 | near-hit rule: the typo escape removed | `test_a_typo_in_the_leading_segment_is_a_real_miss_and_names_the_near_hit` | ✓ |
| 14 | near-hit floor: two-segment minimum dropped to one | `test_a_single_segment_tail_is_not_enough_to_claim_a_near_hit` | ✓ |
| 15 | derived probe: directories no longer resolved | `test_a_top_level_derived_directory_resolves_too` | ✓ |
| 16 | containment: the repo-escape guard removed | `test_a_citation_that_escapes_the_repo_does_not_resolve` | ✓ |
| 17 | sources/ root: the authored-level escape removed | `test_a_source_manifest_beside_the_clones_is_authored` | ✓ |
| 18 | directory citations: the kind check dropped | `test_a_trailing_slash_on_a_plain_file_does_not_resolve` | ✓ |
| 19 | absent marker: AMBIGUOUS accepted as confirmed absent | `test_an_absent_marker_on_an_ambiguous_citation_fails` | ✓ |
| 20 | file:line: the reversed-range check removed | `test_a_reversed_line_range_fails` | ✓ |
| 21 | fences: the length comparison dropped entirely | `test_a_longer_fence_survives_a_shorter_one_inside_it` | ✓ |
| 22 | containment: resolved back to lexical, so a symlink escapes | `test_a_symlink_pointing_outside_the_repo_does_not_resolve` | ✓ |
| 23 | fences: a closing fence may carry an info string again | `test_a_fence_line_carrying_an_info_string_does_not_close_a_block` | ✓ |
| 24 | fences: the same-character guard dropped | `test_a_fence_of_the_other_character_does_not_close_a_block` | ✓ |
| 25 | fences: length predicate weakened from >= to == | `test_a_longer_closing_fence_still_closes` | ✓ |
| 26 | fences: the three-space indent cap removed | `test_a_deeply_indented_backtick_run_is_not_a_fence` | ✓ |
| 27 | spans: maximal-run rule dropped, so ``a`b`` splits in two | `test_a_double_backtick_span_is_read_as_one_span` | ✓ |
| 28 | tasks: the dotted-tail capture removed | `test_a_task_name_with_trailing_junk_is_not_the_declared_task` | ✓ |
| 29 | file:line: the lower-bound half of the range check removed | `test_a_zero_line_reference_fails` | ✓ |
| 30 | sources: the committed extractions subtree reclassified vendored | `test_the_committed_extractions_subtree_counts_as_authored` | ✓ |
| 31 | task lookup: aliases no longer counted as declared | `test_an_alias_counts_as_declared` | ✓ |

Baseline rc=0 before the run; rc=0 after the last restore, so no arm left the
tree mutated.

## Each mutation is a realistic break

`.claude/rules/probes-need-a-control-arm.md` rule 2 warns that a mutation which
is not the real failure proves nothing — renaming `def foo` to `def foo_REMOVED`
leaves the original as a substring, so a substring check still passes and the
*probe* was the no-op. Every arm above deletes or inverts the line that does the
work (`near = _near_hit(...)` → `near = None`, `if candidate.exists():` →
`if True:`), never a definition's name.

## The harness

```python
"""Mutation harness for #145 — break each check, confirm its test fails.

Not repo code: run it by hand from a scratch copy. It exists to satisfy
the acceptance criterion that every check be mutation-tested, and it clears
cached bytecode because a same-size edit is otherwise served from a stale .pyc
and the arm reports a false pass (measured in the immediately preceding round).

Row 0 is a CONTROL: a no-op edit that must leave the suite GREEN. Without it, a
harness whose arms all die for an unrelated reason reads as total success.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # the repo root
SUITES = ["tests/test_citations.py", "tests/test_resolve.py", "tests/test_handoff.py"]

# (label, file, old-line-fragment, new-line-fragment, test that MUST break)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    (
        "CONTROL (no-op comment edit — must stay GREEN)",
        "python/src/kb_setup/handoff.py",
        "    index = resolve.build_index(repo_root)",
        "    index = resolve.build_index(repo_root)  # control",
        "",
    ),
    (
        "path check: direct-exists guard removed",
        "python/src/kb_setup/resolve.py",
        "    if not (candidate.exists() and _inside(repo_root, candidate)):\n        return None",
        "    if False:\n        return None",
        "test_a_cited_path_that_does_not_exist_fails",
    ),
    (
        "file:line check: the past-EOF comparison dropped",
        "python/src/kb_setup/handoff.py",
        "    if cite.start < 1 or cite.end > total:",
        "    if cite.start < 1:",
        "test_a_line_reference_past_the_end_of_the_file_fails",
    ),
    (
        "task check: declaration lookup bypassed",
        "python/src/kb_setup/handoff.py",
        "        ok = cite.name in declared",
        "        ok = True",
        "test_an_undeclared_task_fails",
    ),
    (
        "absent marker: reverse direction removed",
        "python/src/kb_setup/handoff.py",
        "    if got.state is resolve.State.MISSING:\n        return Finding(check_name, Verdict.OK",
        "    if True:\n        return Finding(check_name, Verdict.OK",
        "test_a_path_marked_absent_that_actually_resolves_fails",
    ),
    (
        "fence stripping: the call that blanks a fenced block deleted",
        "python/src/kb_setup/citations.py",
        "    stripped = strip_fences(text)\n    spans: list[Span] = []",
        "    stripped = text\n    spans: list[Span] = []",
        "test_code_spans_ignore_fenced_blocks_but_keep_line_numbers",
    ),
    (
        "exclusion by construction: the elision character dropped",
        "python/src/kb_setup/citations.py",
        '_NON_PATH_CHARS: frozenset[str] = frozenset("*?[]{}<>|\\\\$!\\"\'`^…")',
        '_NON_PATH_CHARS: frozenset[str] = frozenset("*?[]{}<>|\\\\$!\\"\'`^")',
        "test_an_elided_path_is_not_a_path",
    ),
    (
        "suffix match: segment boundary weakened to substring",
        "python/src/kb_setup/resolve.py",
        '        return [p for p in pool if p == needle or p.endswith(f"/{needle}")]',
        "        return [p for p in pool if p == needle or p.endswith(needle)]",
        "test_a_suffix_must_align_on_a_segment_boundary",
    ),
    (
        "resolution order: vendored consulted before authored",
        "python/src/kb_setup/resolve.py",
        "_suffix_matches(token, idx.files, idx.dirs)",
        "_suffix_matches(token, idx.vendored, ())",
        "test_a_vendored_source_clone_never_shadows_the_authored_tree",
    ),
    (
        "pruning: the derived tree no longer pruned by name",
        "python/src/kb_setup/resolve.py",
        "        _DERIVED_ROOT,\n    }\n)",
        "    }\n)",
        "test_a_nested_derived_tree_is_pruned_too",
    ),
    (
        "line_count: unreadable reported as zero instead of unknown",
        "python/src/kb_setup/resolve.py",
        "    except OSError:\n        return None",
        "    except OSError:\n        return 0",
        "test_line_count_of_an_unreadable_file_is_none_not_zero",
    ),
    (
        "exit code: a broken citation no longer exits 1",
        "python/src/kb_setup/handoff.py",
        "    return 1 if any(f.verdict is Verdict.FAIL for f in findings) else 0",
        "    return 0",
        "test_main_exits_1_on_a_real_miss",
    ),
    (
        "single-segment circularity: the len==1 escape removed",
        "python/src/kb_setup/resolve.py",
        "    if len(segments) == 1 or (repo_root / first).exists():",
        "    if (repo_root / first).exists():",
        "test_an_absent_top_level_directory_is_a_real_miss_not_unverifiable",
    ),
    (
        "near-hit rule: the typo escape removed",
        "python/src/kb_setup/resolve.py",
        "    near = _near_hit(token, segments, index)",
        "    near = None",
        "test_a_typo_in_the_leading_segment_is_a_real_miss_and_names_the_near_hit",
    ),
    (
        "near-hit floor: two-segment minimum dropped to one",
        "python/src/kb_setup/resolve.py",
        "_MIN_NEAR_HIT_SEGMENTS = 2",
        "_MIN_NEAR_HIT_SEGMENTS = 1",
        "test_a_single_segment_tail_is_not_enough_to_claim_a_near_hit",
    ),
    (
        "derived probe: directories no longer resolved",
        "python/src/kb_setup/resolve.py",
        "    return candidate if candidate.exists() else None",
        "    return candidate if candidate.is_file() else None",
        "test_a_top_level_derived_directory_resolves_too",
    ),
    (
        "containment: the repo-escape guard removed",
        "python/src/kb_setup/resolve.py",
        "    if not (candidate.exists() and _inside(repo_root, candidate)):",
        "    if not candidate.exists():",
        "test_a_citation_that_escapes_the_repo_does_not_resolve",
    ),
    (
        "sources/ root: the authored-level escape removed",
        "python/src/kb_setup/resolve.py",
        "    if len(parts) < _SOURCES_CHILD_PARTS:\n        return False\n",
        "",
        "test_a_source_manifest_beside_the_clones_is_authored",
    ),
    (
        "directory citations: the kind check dropped",
        "python/src/kb_setup/resolve.py",
        '    if not token.endswith("/") or candidate.is_dir():',
        "    if True:",
        "test_a_trailing_slash_on_a_plain_file_does_not_resolve",
    ),
    (
        "absent marker: AMBIGUOUS accepted as confirmed absent",
        "python/src/kb_setup/handoff.py",
        "    if got.state is resolve.State.MISSING:\n        return Finding(check_name, Verdict.OK",
        "    if got.state is not resolve.State.RESOLVED:\n        return Finding(check_name, Verdict.OK",
        "test_an_absent_marker_on_an_ambiguous_citation_fails",
    ),
    (
        "file:line: the reversed-range check removed",
        "python/src/kb_setup/handoff.py",
        "    if cite.start > cite.end:",
        "    if False:",
        "test_a_reversed_line_range_fails",
    ),
    (
        "fences: the length comparison dropped entirely",
        "python/src/kb_setup/citations.py",
        '        elif fence[0] == opener[0] and len(fence) >= len(opener) and not m.group("info").strip():',
        '        elif fence[0] == opener[0] and not m.group("info").strip():',
        "test_a_longer_fence_survives_a_shorter_one_inside_it",
    ),
    (
        "containment: resolved back to lexical, so a symlink escapes",
        "python/src/kb_setup/resolve.py",
        "    root = repo_root.resolve()\n    target = candidate.resolve()",
        "    root = Path(os.path.normpath(repo_root))\n"
        "    target = Path(os.path.normpath(candidate))",
        "test_a_symlink_pointing_outside_the_repo_does_not_resolve",
    ),
    (
        "fences: a closing fence may carry an info string again",
        "python/src/kb_setup/citations.py",
        '        elif fence[0] == opener[0] and len(fence) >= len(opener) and not m.group("info").strip():',
        "        elif fence[0] == opener[0] and len(fence) >= len(opener):",
        "test_a_fence_line_carrying_an_info_string_does_not_close_a_block",
    ),
    (
        "fences: the same-character guard dropped",
        "python/src/kb_setup/citations.py",
        '        elif fence[0] == opener[0] and len(fence) >= len(opener) and not m.group("info").strip():',
        '        elif len(fence) >= len(opener) and not m.group("info").strip():',
        "test_a_fence_of_the_other_character_does_not_close_a_block",
    ),
    (
        "fences: length predicate weakened from >= to ==",
        "python/src/kb_setup/citations.py",
        '        elif fence[0] == opener[0] and len(fence) >= len(opener) and not m.group("info").strip():',
        '        elif fence[0] == opener[0] and len(fence) == len(opener) and not m.group("info").strip():',
        "test_a_longer_closing_fence_still_closes",
    ),
    (
        "fences: the three-space indent cap removed",
        "python/src/kb_setup/citations.py",
        'r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$"',
        'r"^\\s*(?P<fence>`{3,}|~{3,})(?P<info>.*)$"',
        "test_a_deeply_indented_backtick_run_is_not_a_fence",
    ),
    (
        "spans: maximal-run rule dropped, so ``a`b`` splits in two",
        "python/src/kb_setup/citations.py",
        'r"(?P<ticks>`+)(?!`)(?P<body>[^\\n]+?)(?<!`)(?P=ticks)(?!`)"',
        'r"`(?P<ticks>)(?P<body>[^`\\n]+)`"',
        "test_a_double_backtick_span_is_read_as_one_span",
    ),
    (
        "tasks: the dotted-tail capture removed",
        "python/src/kb_setup/citations.py",
        'r"\\bmise run ([A-Za-z][A-Za-z0-9_:-]*(?:\\.[A-Za-z0-9_:-]+)*)"',
        'r"\\bmise run ([A-Za-z][A-Za-z0-9_:-]*)"',
        "test_a_task_name_with_trailing_junk_is_not_the_declared_task",
    ),
    (
        "file:line: the lower-bound half of the range check removed",
        "python/src/kb_setup/handoff.py",
        "    if cite.start < 1 or cite.end > total:",
        "    if cite.end > total:",
        "test_a_zero_line_reference_fails",
    ),
    (
        "sources: the committed extractions subtree reclassified vendored",
        "python/src/kb_setup/resolve.py",
        '_SOURCES_KEPT: frozenset[str] = frozenset({"extractions", "media"})',
        '_SOURCES_KEPT: frozenset[str] = frozenset({"media"})',
        "test_the_committed_extractions_subtree_counts_as_authored",
    ),
    (
        "task lookup: aliases no longer counted as declared",
        "python/src/kb_setup/resolve.py",
        "        names.update(_aliases(body))",
        "        pass",
        "test_an_alias_counts_as_declared",
    ),
]


def clear_bytecode() -> None:
    """Remove every __pycache__ under the repo. The stale-.pyc arm is why."""
    for cache in REPO.rglob("__pycache__"):
        if ".venv" not in cache.parts and "sources" not in cache.parts:
            shutil.rmtree(cache, ignore_errors=True)


def run_suite() -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        ["uv", "run", "pytest", *SUITES, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=600,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    clear_bytecode()
    rc, out = run_suite()
    if rc != 0:
        print(f"BASELINE NOT GREEN (rc={rc}) — harness cannot discriminate\n{out[-2000:]}")
        return 2
    print("baseline rc=0\n")

    bad = 0
    for label, rel, old, new, expect_test in MUTATIONS:
        path = REPO / rel
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"x {label}\n    MUTATION DID NOT APPLY — fragment not found in {rel}")
            bad += 1
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        clear_bytecode()
        try:
            mrc, mout = run_suite()
        finally:
            path.write_text(original, encoding="utf-8")
            clear_bytecode()

        is_control = expect_test == ""
        if is_control:
            ok = mrc == 0
            detail = "suite stayed green" if ok else f"suite BROKE (rc={mrc}) — harness is lying"
        else:
            ok = mrc != 0 and expect_test in mout
            named = expect_test in mout
            detail = (
                f"rc={mrc}, named test failed"
                if ok
                else f"rc={mrc}, expected test in output: {named}"
            )
        print(f"{'ok' if ok else 'x'} {label}\n    {detail}")
        if not ok:
            bad += 1

    rc, out = run_suite()
    print(f"\nrestored rc={rc}")
    if rc != 0:
        print(out[-2000:])
        bad += 1
    print(f"\n{len(MUTATIONS) - bad}/{len(MUTATIONS)} arms discriminated")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```

It is a document rather than a `.py` file on purpose. `.claude/rules/zero-bash-logic.md`
requires a recurring workflow to ship as a `kb_setup` module plus a mise task,
and this is not one: it edits the working tree, it is run by hand at review
time, and turning it into a task would make it look like a gate it is not. The
fragments above are line-exact against the commit that introduced them, so a
later refactor will make an arm report `MUTATION DID NOT APPLY` — loudly,
rather than silently passing.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under test.
