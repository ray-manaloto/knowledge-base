# Copyright (c) 2026 Raymond Manaloto
"""The in-place-shell-edit guard, armed in BOTH directions.

Half of this file is the ALLOW set, and that is deliberate: every measured
defect in this repo's Bash guards has been a false positive, never an evasion
(`mise-tasks-only.md` § Extending). A guard that fires on legitimate work erodes
trust faster than a missed case, so the commands this must NOT deny are pinned
as hard as the ones it must.
"""

from __future__ import annotations

import json

import pytest
from kb_setup import hook_guard, inplace_edit
from kb_setup.result import Ok


@pytest.mark.parametrize(
    "command",
    [
        # The exact shape measured in #671 arm B.
        "perl -pi -e 's/add_one(1)/add_one(\"one\")/' python/src/kb_setup/events.py",
        "sed -i 's/foo/bar/' python/src/kb_setup/events.py",
        # BSD sed takes a backup suffix as part of the flag.
        "sed -i.bak 's/foo/bar/' tests/test_events.py",
        # GNU long spelling — a short-cluster test alone misses this.
        "sed --in-place 's/foo/bar/' python/src/kb_setup/cli.py",
        # Clustered flags: the `i` is not the first letter.
        "sed -ne -i 's/foo/bar/' python/src/kb_setup/cli.py",
        # `.pyi` stubs are type-checked too.
        "sed -i 's/foo/bar/' python/src/kb_setup/py.typed.pyi",
        # Buried in a chain — every segment is judged, not just the first.
        "git status && sed -i 's/a/b/' python/src/kb_setup/events.py",
    ],
)
def test_denies_in_place_python_rewrites(command: str) -> None:
    reason = inplace_edit.decide(command)
    assert reason is not None, command
    assert "Edit tool" in reason


@pytest.mark.parametrize(
    "command",
    [
        # No in-place flag: this only READS, and reading is nobody's business here.
        "sed -n '1,20p' python/src/kb_setup/events.py",
        "sed 's/foo/bar/' python/src/kb_setup/events.py > /tmp/out.py",
        # In-place, but not a file ty checks.
        "sed -i 's/foo/bar/' README.md",
        "perl -pi -e 's/a/b/' docs/currency/README.md",
        # A quoted MENTION is not a command position. This is the exact class
        # both confirmed false positives in `check_first` came from.
        'git commit -m "sed -i on events.py was the wrong move"',
        # Another command's flags must not leak across the segment boundary.
        "grep -i 'sed' python/src/kb_setup/events.py",
        # `--` ends the flags; a later operand cannot switch in-place back on.
        "sed -- -i.py",
        # A long flag containing `i` is not the short cluster.
        "sed --expression='s/i/x/' python/src/kb_setup/events.py",
    ],
)
def test_allows_everything_else(command: str) -> None:
    assert inplace_edit.decide(command) is None, command


def test_unparsable_command_fails_open() -> None:
    """An unbalanced quote is not evidence of a violation."""
    assert inplace_edit.decide("sed -i 's/foo/bar/ python/src/kb_setup/events.py") is None


@pytest.mark.parametrize(
    "command",
    [
        # The cold lane confirmed both of these bypass the guard: the command
        # word is `find`/`xargs`, and `sed` is merely an argument.
        "find python -name '*.py' -exec sed -i 's/a/b/' {} +",
        "find python -name '*.py' | xargs sed -i 's/a/b/'",
    ],
)
def test_known_bypasses_are_not_denied(command: str) -> None:
    """These SHOULD get through — and the remedy text must say so.

    Pinned as an ALLOW rather than left undefined, because the alternative is a
    guard that quietly grows to catch them and starts firing on `find` commands
    that touch no Python at all. The disclosure is the contract, not the catch.
    """
    assert inplace_edit.decide(command) is None, command


def test_reason_states_what_it_cannot_cover() -> None:
    """A guard naming two commands must not let silence imply the rest are safe.

    Pinned because the omission is invisible: nothing fails if the caveat is
    dropped, and the next reader concludes a heredoc is checked. `find`/`xargs`
    were missing from this list until the cold lane on `1b7f686c4aff` confirmed
    they bypass — the disclosure was wrong by omission, which is the same defect
    as a wrong claim and harder to see.
    """
    reason = inplace_edit.decide("sed -i 's/a/b/' python/src/kb_setup/events.py")
    assert reason is not None
    for uncovered in ("heredoc", "tee", "python -c", "find", "xargs"):
        assert uncovered in reason, uncovered


def test_wired_into_the_shared_decision_function() -> None:
    """The guard must reach BOTH clients, which is the whole point of the wiring.

    `.codex/hooks.json` calls this same entry point on matcher `Bash`, so a
    guard that works only when called directly would silently cover Claude and
    not codex — the asymmetry this change exists to remove.
    """
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "sed -i 's/a/b/' python/src/kb_setup/events.py"},
        }
    )
    result = hook_guard.check_hook_call(payload)

    assert isinstance(result, Ok)
    assert result.value is not None
    assert "Edit tool" in result.value
