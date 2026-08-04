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
