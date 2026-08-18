# Copyright (c) 2026 Raymond Manaloto
"""Arms for the kb-check guard — both directions, and the false positives.

The DENY direction is easy and the ALLOW direction is where a redirect guard
actually fails. Every measured defect in this repo's guards has been a false
positive, never an evasion, so the allow table is longer than the deny table on
purpose.
"""

from __future__ import annotations

import pytest
from kb_setup import check_first, hook_guard
from kb_setup.result import Ok


def _verdict(payload: str) -> str | None:
    """The deny reason for one payload, narrowed on `Ok`.

    Narrowed POSITIVELY, which is the lesson `hook_guard` records about its own
    callers: `Result` has a third variant (`External`) that carries no `.value`,
    so testing against `Err` leaves a union ty rejects.
    """
    result = hook_guard.check_hook_call(payload)
    return result.value if isinstance(result, Ok) else None


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("uv run ruff check python/src/kb_setup/pr.py", id="ruff-check"),
        pytest.param("uv run ruff format tests/", id="ruff-format"),
        pytest.param("uv run ty check python/ tests/", id="ty-check"),
        pytest.param(
            "uv run ruff check python/src/ && uv run ty check python/",
            id="the-chain-that-motivated-this",
        ),
        pytest.param("uv run ruff check tests/ 2>&1 | tail -3", id="piped-so-the-rc-is-lost"),
        pytest.param("cd python && uv run ruff check .", id="after-an-operator"),
        pytest.param("ruff check python/src/kb_setup/graph_size.py", id="bare-via-the-mise-shim"),
        pytest.param("git status\nruff check python/", id="on-line-two-of-a-script"),
        pytest.param("echo start\nty check tests/", id="ty-on-line-two"),
        pytest.param("uv run ruff check python/ && ls -h", id="another-h-flag-is-not-our-help"),
        pytest.param(
            "uv run ruff check python/ && git commit --help",
            id="another-help-does-not-excuse-the-gate",
        ),
        pytest.param("python3 --version && uv run ruff check python/", id="another-version"),
        pytest.param("uv run -q ruff check python/", id="a-flag-before-the-tool"),
        pytest.param("uv run --directory python ruff check src/", id="a-flag-that-takes-a-value"),
        pytest.param("ruff --config ruff.toml check python/", id="subcommand-not-adjacent"),
        pytest.param("/usr/bin/ruff check .", id="an-absolute-path"),
        pytest.param("ruff check '", id="unparsable-falls-back-to-the-old-check"),
        pytest.param("uv -q run ruff check python/", id="a-uv-flag-before-run"),
        pytest.param("uv --directory python run ruff check src/", id="a-uv-value-flag-before-run"),
        pytest.param("env -i ruff check .", id="a-wrappers-own-flag"),
        pytest.param("time -p ruff check .", id="a-flag-that-takes-a-value-elsewhere"),
    ],
)
def test_a_hand_chained_gate_is_denied(command: str) -> None:
    """The shape this round produced 12 times, and a prior session 35 times."""
    reason = check_first.decide(command)

    assert reason is not None, f"guard missed: {command}"
    assert "kb-check" in reason


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("mise run kb-check -- python/src/kb_setup/pr.py", id="the-task-itself"),
        pytest.param(
            "mise run kb-check -- a.py && uv run ruff check b.py",
            id="anywhere-in-the-command",
        ),
        pytest.param("mise run lint", id="whole-repo-lint"),
        pytest.param("mise run test", id="whole-repo-test"),
        pytest.param("mise run kb-gates", id="ship-gates"),
        pytest.param("uv run pytest tests/test_pr.py::test_one -q", id="a-single-test-is-allowed"),
        pytest.param("uv run pytest tests/ -q", id="pytest-is-not-in-scope-at-all"),
        pytest.param("uv run ruff --version", id="version-probe"),
        pytest.param("ruff rule E501", id="asking-what-a-rule-means"),
        pytest.param("git commit -m 'ruff check the thing'", id="the-words-inside-a-message"),
        pytest.param("rg 'ruff check' hk.pkl", id="searching-for-the-string"),
        pytest.param(
            'git commit -m "fix: stop hand-running uv run ruff check"',
            id="a-commit-message-ABOUT-the-guard",
        ),
        pytest.param('rg "uv run ruff check" .', id="searching-for-the-uv-spelling"),
        pytest.param('echo "uv run ruff check"', id="echoing-the-uv-spelling"),
        pytest.param('git commit -m "fix bug; ruff check clean"', id="a-semicolon-inside-a-quote"),
        pytest.param('echo "done | ruff format"', id="a-pipe-inside-a-quote"),
        pytest.param("uv run ruff check --help", id="asking-the-gate-for-help"),
        pytest.param("uv run python -c 'ruff check'", id="the-words-passed-to-python"),
        pytest.param("ty --version", id="bare-ty-version"),
        pytest.param(
            'git commit -m "fix:\nruff check is now passing\nafter the edits"',
            id="a-MULTILINE-commit-message",
        ),
        pytest.param("uv run pytest -k ruff -k check", id="a-pytest-selector-naming-the-tools"),
        pytest.param("uv run python script.py ruff check", id="args-to-another-uv-run-command"),
        pytest.param("ruff help check", id="asking-ruff-about-its-check-subcommand"),
        pytest.param("ty explain check", id="asking-ty-to-explain"),
        pytest.param("ruff config format", id="asking-ruff-about-config"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
    ],
)
def test_legitimate_commands_are_allowed(command: str) -> None:
    """CONTROL ARM, and the longer half.

    A guard people route around is worse than none, and every measured defect in
    this repo's guards has been a false positive. `pytest` is absent from the
    guard entirely because `mise-tasks-only.md` explicitly permits a single-test
    run — a guard contradicting the rule it enforces is the worst kind.
    """
    assert check_first.decide(command) is None, f"false positive: {command}"


def test_the_guard_is_wired_into_the_hook() -> None:
    """A decision function nothing calls is not a guard.

    `kb_setup.check_first.decide` could be perfect and inert. This drives a real
    PreToolUse payload through `hook_guard.check_hook_call`, which is what
    `.claude/settings.json` actually invokes.
    """
    payload = (
        '{"tool_name": "Bash", "tool_input": {"command": "uv run ruff check python/src/"}, '
        '"session_id": "s1", "cwd": "/tmp"}'
    )
    reason = _verdict(payload)

    assert reason is not None
    assert "kb-check" in reason


def test_a_graphify_command_still_reports_its_own_redirect() -> None:
    """ORDER ARM: the older guard must not be shadowed by the newer one.

    A hand-run `graphify` has its own remedy, and reporting the kb-check redirect
    for it would send the reader to the wrong task. `_check_first` runs after
    `_graphify_redirect` precisely so this stays true.

    The command has to be one BOTH guards match, or the arm cannot fail: a bare
    `graphify label` is invisible to `check_first`, so the assertion held no
    matter which guard ran first, and the test measured nothing. Caught by the
    cold lane on this branch (finding 6).
    """
    assert check_first.decide("graphify label && uv run ruff check .") is not None, (
        "PRECONDITION: both guards must match, or this arm cannot detect shadowing"
    )
    payload = (
        '{"tool_name": "Bash", "tool_input": '
        '{"command": "graphify label && uv run ruff check ."}, '
        '"session_id": "s1", "cwd": "/tmp"}'
    )
    reason = _verdict(payload)

    assert reason is not None
    assert "kb-label" in reason
    assert "kb-check" not in reason


def test_the_hook_fails_open_on_a_malformed_payload() -> None:
    """A crashed guard must never brick every Bash call — `hook_guard`'s contract."""
    assert _verdict("{ not json") is None
    assert _verdict("") is None
