"""Tests for the citation-extraction primitive (kb_setup.citations).

Pure text-in / data-out, so every test here is a string and a list — no repo, no
git, no filesystem. What the module gets wrong is not "did it find the path" but
"did it find something that was never a path": #145's acceptance criteria call a
first run that emits false positives fatal to the checker's credibility, and the
measured naive version produced **4 false positives out of 9** on a real handoff.

So every extraction test is paired with an exclusion test over a token that
really appears in this repo's handoffs — a branch name, a glob, a dotted python
module — and the exclusion cases outnumber the inclusion ones on purpose.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import citations

# ------------------------------------------------------------ code spans ----


def test_code_spans_record_the_line_they_appeared_on():
    text = "intro\nsee `docs/a.md` here\n\nand `mise.toml`\n"
    spans = citations.code_spans(text)
    assert [(s.text, s.line) for s in spans] == [("docs/a.md", 2), ("mise.toml", 4)]


def test_code_spans_ignore_fenced_blocks_but_keep_line_numbers():
    """A fenced block is an EXAMPLE; its paths need not exist.

    Line numbering must survive the strip, or every finding after the first
    fence points at the wrong line — which is the exact defect class (`:1836`
    for `:1830`) this checker exists to catch.
    """
    text = "before `a.md`\n```bash\nrm `nonexistent/x.md`\n```\nafter `b.md`\n"
    spans = citations.code_spans(text)
    assert [(s.text, s.line) for s in spans] == [("a.md", 1), ("b.md", 5)]


def test_code_spans_flag_an_explicit_absent_marker():
    """`` `path` (absent) `` marks a path cited BECAUSE it does not exist."""
    text = "the hardcoded `docs/agents/issue-tracker.md` (absent) it looks for\n"
    (span,) = citations.code_spans(text)
    assert span.marked_absent


def test_code_spans_do_not_flag_a_neighbouring_marker():
    """The marker binds to the span it follows, not to the whole line.

    A line-wide rule would let one `(absent)` silence every citation beside it —
    the marker has to be unable to cover anything the author did not point at.
    """
    text = "`a.md` and `b.md` (absent)\n"
    a, b = citations.code_spans(text)
    assert not a.marked_absent
    assert b.marked_absent


# ------------------------------------------------------- path citations ----


def test_path_citation_with_a_separator_is_extracted():
    (c,) = citations.path_citations("see `.claude/rules/do-not.md` for this\n")
    assert c.text == ".claude/rules/do-not.md"


def test_bare_filename_with_a_known_extension_is_extracted():
    (c,) = citations.path_citations("declared in `mise.toml`\n")
    assert c.text == "mise.toml"


def test_directory_citation_ending_in_a_slash_is_extracted():
    (c,) = citations.path_citations("committed under `sources/extractions/`\n")
    assert c.text == "sources/extractions/"


# --- the exclusion arms: tokens that look path-shaped and are not paths ---


def test_a_branch_name_is_not_a_path():
    """`feat/145-kb-handoff-check` has a separator and is not a path.

    The control arm for the whole separator rule. Treating every
    separator-bearing token as repo-relative reports the branch this ticket is
    being built on as a broken citation — a false positive in the checker's own
    handoff, on its first run.
    """
    assert citations.path_citations("branch `feat/145-kb-handoff-check` @ `3cc355a`\n") == []


def test_a_git_ref_is_not_a_path():
    assert citations.path_citations("gate against `origin/main` always\n") == []


def test_a_glob_is_not_a_path():
    assert citations.path_citations("`graphify-out/memory/**` is exempt\n") == []
    assert citations.path_citations("every `sources/*.manifest` pin\n") == []


def test_a_placeholder_template_is_not_a_path():
    assert citations.path_citations("`.agent/kb/review/reports/review-<sha>-<lane>.md`\n") == []


def test_a_dotted_python_module_is_not_a_path():
    """`kb_setup.hook_guard` ends in a dot-suffix that is not a file extension."""
    assert citations.path_citations("wired via `kb_setup.hook_guard` in settings\n") == []


def test_a_shell_flag_is_not_a_path():
    assert citations.path_citations("pass `--fixed-point` to it\n") == []


def test_a_version_or_date_is_not_a_path():
    assert citations.path_citations("`graphify` 0.9.31 on `2026-08-03` and `v2026.7.16`\n") == []


def test_an_absolute_or_home_path_is_not_repo_relative():
    """Outside the repo, so this module cannot adjudicate it either way."""
    assert citations.path_citations("logs to `/tmp/out.log` and `~/.claude/CLAUDE.md`\n") == []


def test_a_url_is_not_a_path():
    assert citations.path_citations("see `https://github.com/x/y.md` for it\n") == []


def test_a_multi_token_span_is_not_a_path():
    """A command is not a citation; only a whole-span single token is."""
    assert citations.path_citations("run `mise run kb-update -- name`\n") == []


def test_an_elided_path_is_not_a_path():
    """Handoffs abbreviate a sha with `…`; the result names no file.

    Measured over all 28 handoffs, this was the single largest false-positive
    class — every abbreviated review-report path read as a broken citation.
    """
    text = "at `.agent/kb/review/reports/review-f19b18d6…-cold.md` there\n"
    assert citations.path_citations(text) == []


def test_a_regex_fragment_is_not_a_path():
    assert citations.path_citations("the pattern `^graphify-out/` in it\n") == []


def test_a_bare_extension_is_not_a_filename():
    """A phrase like "every `.md` file" names an extension, not a file."""
    assert citations.path_citations("every `.md` and `.py` and `.json` file\n") == []


def test_a_real_dotfile_is_still_a_filename():
    """Control arm for the rule above — it must not eat `.gitignore`."""
    (c,) = citations.path_citations("listed in `.gitignore` already\n")
    assert c.text == ".gitignore"


def test_a_documentation_url_without_a_scheme_is_not_a_path():
    """`code.claude.com/docs/en/skills.md` is a host, not a repo-relative path."""
    assert citations.path_citations("see `code.claude.com/docs/en/skills.md`\n") == []


# --------------------------------------------------- file:line citations ----


def test_file_line_citation_is_extracted_with_its_range():
    (c,) = citations.line_citations("see `.claude/skills/clear-prep/SKILL.md:214-216` there\n")
    assert (c.path, c.start, c.end) == (".claude/skills/clear-prep/SKILL.md", 214, 216)


def test_single_line_citation_has_equal_start_and_end():
    (c,) = citations.line_citations("at `python/src/kb_setup/goal.py:88`\n")
    assert (c.path, c.start, c.end) == ("python/src/kb_setup/goal.py", 88, 88)


def test_a_line_citation_is_not_also_reported_as_a_path():
    """Otherwise one wrong reference produces two findings for one mistake."""
    text = "at `docs/a.md:12`\n"
    assert citations.line_citations(text) != []
    assert citations.path_citations(text) == []


def test_a_clock_time_is_not_a_file_line_reference():
    assert citations.line_citations("finished at `14:22` today\n") == []


# --------------------------------------------------------------- tasks ----


def test_task_citation_is_extracted():
    (t,) = citations.task_citations("run `mise run kb-build` first\n")
    assert t.name == "kb-build"


def test_task_citation_stops_at_the_argument_separator():
    (t,) = citations.task_citations("`mise run kb-update -- agents`\n")
    assert t.name == "kb-update"


def test_a_task_placeholder_is_not_a_task_name():
    """`mise run <task>` names no task; reporting it would be a false positive."""
    assert citations.task_citations("`mise run <task>` is the shape\n") == []


def test_task_citations_ignore_fenced_examples():
    assert citations.task_citations("```\nmise run not-a-real-task\n```\n") == []


def test_a_longer_fence_survives_a_shorter_one_inside_it():
    """A ```` ```` ```` block quoting a ``` ``` ``` pair is ONE block, not three.

    Toggling on any fence line regardless of length made the inner pair close
    and reopen the outer block, so example content leaked out as real citations
    — and, with the nesting the other way, real content was swallowed.
    """
    text = "a\n````\n```\nsee `docs/nope.md`\n```\n````\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_plain_fence_still_closes_normally():
    """Control arm: the length rule must not stop an ordinary fence closing."""
    text = "a\n```\n`docs/nope.md`\n```\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_fence_line_carrying_an_info_string_does_not_close_a_block():
    """CommonMark: a CLOSING fence may not carry an info string.

    Treating ```` ```python ```` as a closer ended the block early and leaked the
    rest of the example out as real citations.
    """
    text = "a\n```\n```python\nsee `docs/nope.md`\n```\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_fence_of_the_other_character_does_not_close_a_block():
    """`~~~` cannot close a ``` ``` ``` block — the character must match."""
    text = "a\n```\n~~~\nsee `docs/nope.md`\n~~~\n```\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_shorter_fence_of_the_same_character_does_not_close_a_block():
    """Pins the `>=` in the close predicate, which `==` would also satisfy."""
    text = "a\n````\n```\nsee `docs/nope.md`\n````\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_longer_closing_fence_still_closes():
    """Control arm for the rule above: `>=`, not `==`."""
    text = "a\n```\n`docs/nope.md`\n`````\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_deeply_indented_backtick_run_is_not_a_fence():
    """CommonMark caps a fence's indent at 3 spaces.

    Unlimited indent made an indented literal-backtick line a delimiter, so a
    real citation between two of them was silently swallowed.
    """
    text = "a\n    ```\n`docs/real.md`\n    ```\nb\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_three_space_indented_fence_still_fences():
    """Control arm for the indent cap."""
    text = "a\n   ```\n`docs/nope.md`\n   ```\nb `docs/real.md`\n"
    assert [s.text for s in citations.code_spans(text)] == ["docs/real.md"]


def test_a_double_backtick_span_is_read_as_one_span():
    """`` ``a`b`` `` is ONE span whose body contains a backtick, not two spans.

    Matching only single-backtick pairs split it in two and manufactured a
    path citation out of the fragments.
    """
    spans = citations.code_spans("see ``docs/gone.md`x`` here\n")
    assert [s.text for s in spans] == ["docs/gone.md`x"]
    assert citations.path_citations("see ``docs/gone.md`x`` here\n") == []


def test_a_task_name_with_trailing_junk_is_not_the_declared_task():
    """`mise run kb-build.typo` must not be read as `mise run kb-build`.

    Without a trailing boundary the regex stopped at the `.` and reported a
    declared task, so a typo in a command the next session would run passed.
    """
    (t,) = citations.task_citations("run `mise run kb-build.typo` first\n")
    assert t.name != "kb-build"


# ------------------------------------------------------------ gate claims ----
#
# Every case below is a phrasing that occurs in this repo's own committed
# handoffs, not one invented for the test. `test_gate_claims_are_found_in_the
# _real_handoff_corpus` is the arm that keeps it that way: a parser tuned to
# fixtures alone is the dead detector this repo has already shipped once.


def test_a_direct_gate_claim_is_extracted():
    (c,) = citations.gate_claims("- `mise run lint` **rc=0**\n")
    assert (c.task, c.rc, c.line) == ("lint", 0, 1)


def test_an_arrow_between_the_task_and_its_rc_is_not_a_barrier():
    """`` `mise run lint` → **rc=0** `` — the form six handoffs use."""
    (c,) = citations.gate_claims("- `mise run lint` → **rc=0**\n")
    assert (c.task, c.rc) == ("lint", 0)


def test_a_bare_task_name_before_rc_is_a_claim():
    """`lint rc=0 · test rc=0` — no backticks at all, and just as much a claim."""
    claims = citations.gate_claims("- Gates green: lint rc=0 · test rc=1\n")
    assert [(c.task, c.rc) for c in claims] == [("lint", 0), ("test", 1)]


def test_a_backticked_bare_task_name_is_a_claim():
    """`` `brain-audit` rc=0 `` — the hyphen must survive into the task name."""
    (c,) = citations.gate_claims("- `brain-audit` rc=0\n")
    assert c.task == "brain-audit"


def test_a_claim_inherits_the_commit_its_block_names():
    text = "- Gates on `7f97305`: `mise run lint` rc=0\n"
    (c,) = citations.gate_claims(text)
    assert c.shas == ("7f97305",)


def test_a_claim_does_not_inherit_a_commit_from_another_block():
    """The false-positive arm for the binding, and the one that decides the design.

    A handoff names shas everywhere — in gotchas, in review tables, in the
    header. Binding a claim to the nearest PRECEDING sha in the document would
    make the gotcha paragraph above a gate list vouch for it. The unit is the
    block, so a claim in a block that names no commit is bound to nothing.
    """
    text = "- I typed `db0a770` by hand and it named no commit.\n- `mise run lint` rc=0\n"
    (c,) = citations.gate_claims(text)
    assert c.shas == ()


def test_a_branch_name_is_not_a_commit():
    """`Gates on `main`, all rc=0` — real, and `main` binds a claim to nothing."""
    text = "- Gates on `main`, all rc=0: `mise run lint`\n"
    (c,) = citations.gate_claims(text)
    assert c.shas == ()


def test_a_distributive_all_rc_covers_the_tasks_listed_after_it():
    """`Gates on `f3e233a`, all rc=0: <list>` — one phrase vouching for four gates.

    The highest-stakes form in the corpus, so it is read rather than skipped.
    """
    text = "- Gates on `f3e233a`, all rc=0: `mise run lint` · `mise run lint-docs`\n"
    claims = citations.gate_claims(text)
    assert [(c.task, c.rc, c.shas) for c in claims] == [
        ("lint", 0, ("f3e233a",)),
        ("lint-docs", 0, ("f3e233a",)),
    ]


def test_a_distributive_claim_stops_at_the_end_of_its_block():
    text = "- Gates, all rc=0: `mise run lint`\n\n- Later: `mise run test`\n"
    assert [c.task for c in citations.gate_claims(text)] == ["lint"]


def test_a_task_with_its_own_rc_is_not_claimed_twice():
    """A direct rc wins; the distributive phrase does not also claim that task.

    Without this, `` `mise run kb-gates` **rc=0** (lint/test all rc=0), `mise run
    lint-docs` **rc=0** `` — one real line — produced a second, accidental claim
    on `lint-docs` that happened to agree. Agreeing by luck is not verification.
    """
    text = "- all rc=0: `mise run lint` **rc=1**\n"
    assert [(c.task, c.rc) for c in citations.gate_claims(text)] == [("lint", 1)]


def test_a_distributive_phrase_needs_its_colon():
    """`(lint/test/brain-audit/eval all rc=0),` introduces no list — it trails one.

    Without the colon anchor that parenthetical swept up every `mise run` for the
    rest of the line, which is how a claim about the runner silently became four
    claims about gates nobody had written down.
    """
    text = "- `mise run kb-gates` **rc=0** (lint/test all rc=0), `mise run lint-docs`\n"
    assert [c.task for c in citations.gate_claims(text)] == ["kb-gates"]


def test_gate_claims_ignore_fenced_examples():
    text = "```\n`mise run lint` rc=0\n```\n"
    assert citations.gate_claims(text) == []


def test_an_rc_with_no_number_is_not_a_claim():
    """`lint rc=$?` records HOW an exit code was read, not what it was.

    The task token is directly adjacent to the `rc=`, so only the digit
    requirement excludes this. The first version of this test used
    `out=$(pytest); rc=$?`, where the `;` did the excluding — a fixture that
    could not exhibit the harm, so the arm on the digit run survived while
    looking armed.
    """
    assert citations.gate_claims("- Gates: lint rc=$? read from the file\n") == []


def test_the_shell_idiom_around_an_rc_is_not_a_claim_either():
    """`out=$(pytest | tail -3); rc=$?` — the form `/clear-prep` step 5 teaches."""
    assert citations.gate_claims("- `out=$(pytest); rc=$?` reads tail's 0\n") == []


def test_a_nonzero_rc_is_claimed_as_written():
    """A handoff recording a red gate is still making a checkable claim."""
    (c,) = citations.gate_claims("- `mise run test` **rc=1**\n")
    assert c.rc == 1


def test_gate_claims_are_found_in_the_real_handoff_corpus():
    """The control arm: a parser tuned to fixtures alone finds nothing real.

    `.agent/` is gitignored, so a fresh clone has no handoffs and this skips —
    but on any machine that HAS them, a parser that stopped matching the corpus
    fails here rather than passing quietly. (`fixture-shaped-tests-hide-a-dead-
    detector`.)
    """
    plans = sorted(Path(__file__).resolve().parents[1].joinpath(".agent", "plans").glob("*.md"))
    if not plans:
        pytest.skip("no handoff corpus on this machine (.agent/ is gitignored)")
    claimed = {
        (c.task, c.rc)
        for p in plans
        for c in citations.gate_claims(p.read_text(encoding="utf-8", errors="replace"))
    }
    assert ("lint", 0) in claimed
    assert ("test", 0) in claimed


def test_a_table_cell_claim_is_read():
    """`` | `mise run lint` | **rc=0** at `78f7190` | `` — verbatim from a handoff.

    Found by a review lane AFTER the pattern's own comment had claimed it
    covered "the four spellings this repo's handoffs actually use". A silent
    miss is worse than a reported one here: the claim simply disappears rather
    than being reported unverifiable.
    """
    text = "| `mise run lint` | **rc=0** at `78f7190` (re-run after the edit) |\n"
    (c,) = citations.gate_claims(text)
    assert (c.task, c.rc, c.shas) == ("lint", 0, ("78f7190",))


def test_a_claim_crosses_at_most_one_cell_boundary():
    """The task stays the token NEAREST the `rc=`, never the row's first one."""
    (c,) = citations.gate_claims("| lint | something else | rc=0 |\n")
    assert c.task == "else"


def test_the_sha_accessor_is_empty_unless_exactly_one_commit_is_named():
    """Zero and two are real answers; `shas[0]` raises on one and guesses on the other."""
    text = "- `mise run lint` rc=0\n\n- Gates on `77661a3` and `c25974b`: `mise run test` rc=0\n"
    unbound, ambiguous = citations.gate_claims(text)
    assert unbound.sha == ""
    assert ambiguous.sha == ""


def test_the_sha_accessor_returns_the_single_commit():
    (c,) = citations.gate_claims("- Gates on `77661a3`: `mise run lint` rc=0\n")
    assert c.sha == "77661a3"


def test_two_distributive_phrases_do_not_bleed_into_each_other():
    """`all rc=0: <list>; all rc=1: <list>` bound the SECOND list to rc=0.

    The parser reported the opposite of what was authored, and the checker would
    then confirm it. A manufactured claim is worse than a missed one: a miss
    leaves the handoff unchecked, this puts a verdict behind words nobody wrote.
    """
    text = "- all rc=0: `mise run lint`; all rc=1: `mise run test`\n"
    assert [(c.task, c.rc) for c in citations.gate_claims(text)] == [("lint", 0), ("test", 1)]


def test_a_single_distributive_phrase_still_reaches_the_end_of_its_block():
    """Control arm: bounding each phrase must not truncate the only one."""
    text = "- Gates, all rc=0: `mise run lint` ·\n  `mise run test` · `mise run eval`\n"
    assert [c.task for c in citations.gate_claims(text)] == ["lint", "test", "eval"]


def test_two_phrases_claiming_the_same_task_differently_both_survive():
    """`all rc=0: lint; all rc=1: lint` dropped the second claim silently.

    The shared `claimed` set suppressed it, so a contradiction the author WROTE
    never reached the checker. Emitting both means one fails against the record,
    which is how a reader gets told. Pre-existing, in the path this round
    touched. (Cold lane round 2.)
    """
    text = "- all rc=0: `mise run lint`; all rc=1: `mise run lint`\n"
    assert [(c.task, c.rc) for c in citations.gate_claims(text)] == [("lint", 0), ("lint", 1)]


def test_one_phrase_naming_a_task_twice_claims_it_once():
    """Control arm: dedup on (task, rc) must still collapse a real duplicate."""
    text = "- all rc=0: `mise run lint` · `mise run lint`\n"
    assert [(c.task, c.rc) for c in citations.gate_claims(text)] == [("lint", 0)]


# --------------------------------------------------- typo'd extensions ----
#
# The extraction half of #154. `citations` cannot know whether `mise.tomlx` is a
# typo — that is a filesystem question — so it PROPOSES the repairs and
# `kb_setup.resolve` disposes. Everything here is therefore about which tokens
# get proposed at all, and the exclusion arms are again the point: the mechanism
# this ticket originally specified (a bare stem probe) was measured to promote
# 233 distinct tokens over this repo's 156 authored markdown files, almost all of
# them `module.attribute` references. Those exclusions are asserted below.


def test_a_typod_extension_proposes_the_known_spelling():
    (cand,) = citations.typo_candidates("see `mise.tomlx` here\n")
    assert cand.text == "mise.tomlx"
    assert cand.repairs == ("mise.toml",)
    assert cand.line == 1


def test_a_known_extension_is_never_a_typo_candidate():
    """Control arm: the tokens `path_citations` already handles never appear here.

    Two extractors reporting one token would produce two findings for one
    mistake, which is the duplication `path_citations` already excludes
    `file:line` for.

    `config.yml` IS the fixture, and `mise.toml` alone was not. A known extension
    is usually far from every other known extension — `toml` and `md` have no
    neighbour within one edit — so removing the `is_path_like` guard leaves them
    proposing nothing and the arm reports a false pass. `yml` is one edit from
    BOTH `xml` and `yaml`, so it is the token that can actually exhibit the
    double-report. A fixture unable to exhibit the harm is the probe being the
    no-op, not the code.
    """
    assert citations.typo_candidates("see `mise.toml` `docs/a.md` `config.yml`\n") == []


def test_the_repair_covers_all_four_single_edit_typos():
    """Substitution, insertion, deletion and transposition — the classic set.

    Transposition is included because `.tmol` for `.toml` is one of the most
    common ways a human mistypes an extension, and it was measured to cost
    **0 additional promotions** over the corpus rather than assumed harmless.
    """
    got = {
        c.text: c.repairs
        for c in citations.typo_candidates(
            "`a.tomd` `b.tomll` `c.tom` `d.tmol`\n"  # sub, ins, del, transpose
        )
    }
    assert got["a.tomd"] == ("a.toml",)
    assert got["b.tomll"] == ("b.toml",)
    assert got["c.tom"] == ("c.toml",)
    assert got["d.tmol"] == ("d.toml",)


def test_a_module_attribute_reference_is_not_a_typo_candidate():
    """The measured false-positive class, asserted as an arm.

    `gates.record` names a real module and a real attribute. Under the stem
    probe this ticket originally proposed it resolved uniquely to
    `python/src/kb_setup/gates.py` and would have been reported as a typo — 278
    occurrences of exactly this shape across the corpus. Under extension repair
    it never reaches the filesystem, because no known extension is one edit from
    `record`.
    """
    text = "`gates.record` `graphify_env.clean_env()` `chunks._out_path` `resolve.build_index()`\n"
    assert citations.typo_candidates(text) == []


def test_a_version_number_is_not_a_typo_candidate():
    """`0.9.31` and `2026-08-03` occur in every handoff."""
    assert citations.typo_candidates("`0.9.31` and `2026-08-03` and `1.2.3`\n") == []


def test_a_typo_candidate_keeps_its_directory_prefix():
    """The repair replaces the extension and nothing else."""
    (cand,) = citations.typo_candidates("`python/src/kb_setup/handoff.pyy`\n")
    assert cand.repairs == ("python/src/kb_setup/handoff.py",)


def test_a_file_line_reference_is_not_a_typo_candidate():
    """A BOUND, stated rather than left implicit.

    `cli.pyx:287` is the same defect wearing a line number, and it is not
    reported. Measured over the corpus: **0 occurrences**, against 5 bare tokens
    that do reach the repair gate — so the recall given up is zero today, and
    that count is the condition on the claim.

    The arm matters in the other direction too: `cli.py:287` must not be
    proposed here, or a citation `line_citations` already checks would be
    reported twice.

    `foo.mp:3` IS the fixture that makes this test able to fail. `cli.py:287` and
    `cli.pyx:287` cannot: their extensions are far from every known spelling, so
    removing the guard entirely leaves them proposing nothing and the mutation
    arm reports a false pass — which is exactly what it did for one round. See
    :func:`test_the_line_ref_guard_is_load_bearing_not_decorative`.
    """
    assert citations.typo_candidates("`cli.py:287` `cli.pyx:287` `foo.mp:3`\n") == []


def test_a_typo_candidate_obeys_every_exclusion_a_path_does():
    """The categorical rejections are shared, not re-derived.

    A glob, an elision, a URL, a flag and a schemeless host are excluded from
    path citations by construction; a second extractor that forgot any one of
    them would reintroduce the false positives the first was built to avoid.
    """
    text = (
        "`docs/*.mdx` `review-f19b18d6….mdd` `https://x.com/a.tomll` "
        "`--out.tomll` `code.claude.com/docs/x.mdd`\n"
    )
    assert citations.typo_candidates(text) == []


def test_a_typo_candidate_carries_the_absent_marker():
    """So a deliberately-cited typo can be marked, exactly like a missing path."""
    (cand,) = citations.typo_candidates("the example `mise.tomlx` (absent) above\n")
    assert cand.marked_absent


def test_a_typod_extension_inside_a_fence_is_not_a_candidate():
    """Fenced content is EXAMPLE text — the same rule every other extractor obeys."""
    assert citations.typo_candidates("```\n`mise.tomlx`\n```\n") == []


def test_an_extension_far_from_every_known_one_proposes_nothing():
    """The control for the whole mechanism: two edits away is not a typo here.

    Stated so the bound is visible — `.tomlxx` is a real typo this will not
    catch, and silence is the documented safe direction.
    """
    assert citations.typo_candidates("`mise.tomlxx` `notes.org` `data.parquet`\n") == []


def test_a_colon_bearing_extension_proposes_nothing():
    """A `file:line` token earns no repair — now via ONE guard, not two.

    History worth keeping, because it is the reason this test exists rather than
    a second `_LINE_REF_RE` check: that guard was carried separately and declared
    "unreachable by construction" from three TRUE premises — a `file:line` token
    ends in `:<digits>`, so its extension contains a `:`; every `_KNOWN_EXT` entry
    is short and alphanumeric; therefore none is one edit away. The chain never
    asked whether a known extension ends in a DIGIT. **`mp3` does**, so `mp:3`
    repaired to `mp3` and the guard was live all along — its mutation arm had
    survived only because the fixtures (`cli.py:287`) could not exhibit it.

    The alphanumeric rule now covers the whole class, so the separate guard is
    gone rather than sitting beside this one. Two guards for one property mask
    each other's mutations: each mutates to a no-op while the other still holds,
    so the property reads as armed when neither site is.
    """
    assert citations._ext_repairs("mp:3") == ()
    assert citations._ext_repairs("py:287") == ()
    assert citations._ext_repairs("pyx:287") == ()


def test_mp3_is_why_the_colon_rule_cannot_be_relaxed():
    """Names the counterexample, so the old bad reasoning cannot be re-derived.

    If `mp3` ever leaves the allowlist, someone may reason their way back to
    "a colon-bearing extension can never earn a repair, so the rule is free" —
    which was true of every premise and false of the conclusion. This fails first.
    """
    assert sorted(ext for ext in citations._KNOWN_EXT if ext[-1].isdigit()) == ["mp3"]


def test_trailing_punctuation_is_not_a_mistyped_extension():
    """An extension is alphanumeric.

    Without that, the repair treats trailing punctuation as part of the extension
    and "fixes" it by deleting one character. Measured over 386 authored markdown
    files: 3 findings of this shape and **0 real typos** — `` `pr.py:` `` and
    `` `evals.py:` `` quoted a PATTERN in a review report rather than citing a
    file, and one path carried a comma inside the backticks. Precision 0/3, in
    the module whose whole design is under-reporting.
    (Silent-failure lane, F4.)
    """
    text = "`pr.py:` `evals.py:` `.agent/plans/session-2026-07-31.md,`\n"
    assert citations.typo_candidates(text) == []


def test_an_empty_extension_proposes_nothing():
    """`` `resolve.` `` proposed `resolve.c` and `resolve.h`.

    `_one_edit_apart("", "c")` is True — the deletion arm accepts a length
    difference of one against the empty string — and only `isdigit` was guarded.
    (Silent-failure lane, F5.)
    """
    assert citations._ext_repairs("") == ()
    assert citations.typo_candidates("see `resolve.` there\n") == []


def test_a_real_typo_still_survives_the_alphanumeric_rule():
    """Control arm for the two above: the rule must not eat the feature."""
    got = {c.text: c.repairs for c in citations.typo_candidates("`mise.tomlx` `graph.jsom`\n")}
    assert got == {"mise.tomlx": ("mise.toml",), "graph.jsom": ("graph.json",)}
