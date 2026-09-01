# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.lane_recording` — a lane must leave a session record.

WHAT THIS GUARDS, in one line: `codex exec --ephemeral` persists no session
file, so an ephemeral lane cannot be reviewed afterwards by `kb-session-search`
or anything else.

THE HARD PART IS NOT DETECTION, IT IS THE FALSE POSITIVE. Both files the guard
scans now discuss `--ephemeral` at length, explaining why it is absent — so a
literal search flags its own documentation, which is how a gate loses its
readers. Most of the cases below are therefore about what must NOT fire: prose,
a quoted mention inside another command, and a fenced block that is a markdown
sample rather than an instruction.

Every fixture is built here. None reads `.claude/**`, because a test that passes
because today's tree happens to be clean is a test that stops meaning anything
the moment someone edits a rule file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import lane_recording as lr
from kb_setup.result import Rc

_GLOBS = ("*.md",)


def _write(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def test_an_ephemeral_lane_is_a_finding(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.md",
        "# lane\n\n```bash\ncat p.md | codex exec --ephemeral --sandbox read-only -\n```\n",
    )
    report = lr.check(tmp_path, globs=_GLOBS)
    assert report.rc is Rc.FINDINGS
    assert report.findings[0].line == 4


def test_a_recording_lane_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.md",
        "# lane\n\n```bash\ncat p.md | codex exec --sandbox read-only -\n```\n",
    )
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.OK


@pytest.mark.parametrize("spelling", ["--ephemeral", "--ephemeral=true"])
def test_the_equals_spelling_is_the_same_flag(tmp_path: Path, spelling: str) -> None:
    """Matching the raw token missed `=`-joined forms on a sibling guard this week."""
    _write(tmp_path, "a.md", f"```bash\ncodex exec {spelling} -\n```\n")
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.FINDINGS


def test_prose_about_the_flag_stays_clean(tmp_path: Path) -> None:
    """The central false positive: the docs that explain the ban must not trip it.

    This is not hypothetical — after the flag was removed, both scanned files
    gained several paragraphs naming `--ephemeral`, and a grep-based guard would
    have gone red on the very change that fixed the problem.
    """
    _write(
        tmp_path,
        "rule.md",
        "# rule\n\n`--ephemeral` is no longer in these patterns: `codex exec --ephemeral`\n"
        "means run without persisting session files, so a lane leaves nothing.\n",
    )
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.OK


def test_a_quoted_mention_in_another_command_stays_clean(tmp_path: Path) -> None:
    """`shlex` makes a commit message one token, so it never sits at a command position."""
    _write(
        tmp_path,
        "a.md",
        '```bash\ngit commit -m "drop codex exec --ephemeral from the lanes"\n```\n',
    )
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.OK


def test_a_non_shell_fence_stays_clean(tmp_path: Path) -> None:
    """A json/text sample is not an instruction."""
    _write(tmp_path, "a.md", '```json\n{"cmd": "codex exec --ephemeral -"}\n```\n')
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.OK


def test_another_tools_ephemeral_flag_stays_clean(tmp_path: Path) -> None:
    """Judged per segment on the COMMAND WORD — this is about codex, not the word."""
    _write(tmp_path, "a.md", "```bash\nsome-other-tool run --ephemeral\n```\n")
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.OK


def test_a_pipeline_hides_nothing(tmp_path: Path) -> None:
    """Another command in the chain must not excuse the codex call beside it."""
    _write(tmp_path, "a.md", "```bash\necho hi | codex exec --ephemeral - | tee /tmp/x\n```\n")
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.FINDINGS


def test_zero_files_is_not_run_rather_than_a_pass(tmp_path: Path) -> None:
    """The trap this repo just measured elsewhere, refused here.

    `hk run check --all -S <nonexistent-step>` exits 0 and its JSON says
    "passed" — a filter matching nothing is indistinguishable from a clean run.
    An empty finding list must therefore never be reported as OK.
    """
    report = lr.check(tmp_path, globs=("no-such-dir/*.md",))
    assert report.scanned == []
    assert report.rc is Rc.NOT_RUN


def test_an_unparsable_command_falls_back_rather_than_going_silent(tmp_path: Path) -> None:
    """A line shlex cannot tokenise is exactly where a real invocation could hide."""
    _write(tmp_path, "a.md", "```bash\ncodex exec --ephemeral 'unbalanced -\n```\n")
    assert lr.check(tmp_path, globs=_GLOBS).rc is Rc.FINDINGS


def test_main_reports_not_run_on_an_empty_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert lr.main([], tmp_path) == Rc.NOT_RUN
    assert "NOT RUN" in capsys.readouterr().out
