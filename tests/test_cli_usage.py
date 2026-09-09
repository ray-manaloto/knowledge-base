# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.cli._print_usage` — the subcommand list's own shape.

WHY THIS FILE EXISTS. The usage text is one Python expression built from ~50
adjacent string literals, each ending `" | "`. Implicit concatenation means a
dropped trailing space is invisible in the source — the two literals still sit
on separate lines, still line up, still read correctly — and only shows up in
the RENDERED output as `…|arms <spec.toml>`, two subcommands run together.

That is exactly what happened: a `replace_all` edit adding `--last` to the
`session-reflect` row rewrote the literal without its trailing space, and no
test noticed because no test had ever rendered the string. A cold review lane
found it by RUNNING `uv run kb-setup` with no arguments, which is the one probe
the diff could not survive and the reading passes did.

So the arm is the render, not the source. These tests call `_print_usage()` and
assert on what a user actually sees.
"""

from __future__ import annotations

import re

from kb_setup import cli

#: Two subcommands run together across a separator: a `|` immediately followed
#: by a word character. Never legitimate in the rendered list — every real
#: separator is `" | "` — while an ALTERNATION inside one row (`mock|handoff`,
#: `[--sessions N|--last]`, `[record|reflect|audit]`) is preceded by a word
#: character or a bracket, so it cannot match.
_RUN_TOGETHER = re.compile(r"(?<=[\s\]])\|\w")


def test_usage_renders_without_two_subcommands_run_together(capsys):
    """The FAIL direction of the defect a cold lane caught by running the command.

    The realistic break is exactly how it happened: an edit to one row drops the
    trailing space from its literal. Nothing in the source looks wrong, and only
    the rendered string shows `|arms`.
    """
    assert cli._print_usage() == 0
    rendered = capsys.readouterr().out

    stuck = _RUN_TOGETHER.findall(rendered)
    assert not stuck, f"subcommands run together in the usage text: {stuck}"


def test_the_run_together_probe_can_actually_fire():
    """CONTROL ARM: prove the assertion above is capable of failing.

    Without this, a regex that matched nothing for the WRONG reason — a bad
    lookbehind, a stray escape — would make the test above pass forever while
    the real output was broken. `probes-need-a-control-arm.md` rule 2: a gate
    verified only on clean input is decoration.

    It also pins the other direction: a legitimate in-row alternation must NOT
    be flagged, or the real test fails on correct output.
    """
    assert _RUN_TOGETHER.search("distill | session-reflect [--x] |arms <spec>")
    assert not _RUN_TOGETHER.search("distill | session-reflect [--sessions N|--last] | arms")
    assert not _RUN_TOGETHER.search("skillopt-reviewed --backend mock|handoff | ensure-deps")


def test_usage_names_every_separator_the_same_way(capsys):
    """Each row is `" | "`-separated, so the count of separators is stable and checkable.

    A weaker but independent read of the same string: if a literal loses its
    space the ` | ` count drops by one while the `|` count does not. Asserting
    the RELATIONSHIP rather than either number means this survives adding and
    removing subcommands, which happens constantly.
    """
    assert cli._print_usage() == 0
    rendered = capsys.readouterr().out.strip()

    # Every `|` is either a row separator (` | `) or an in-row alternation
    # (`a|b`, no surrounding spaces). Nothing else is a legitimate shape.
    for match in re.finditer(r"\|", rendered):
        i = match.start()
        spaced = rendered[i - 1 : i] == " " and rendered[i + 1 : i + 2] == " "
        tight = rendered[i - 1 : i] not in (" ", "") and rendered[i + 1 : i + 2] not in (" ", "")
        assert spaced or tight, f"malformed separator at offset {i}: {rendered[i - 30 : i + 30]!r}"
