# Copyright (c) 2026 Raymond Manaloto
r"""The shared heredoc tokeniser, armed across all three guards that inherit it.

`check_first.strip_heredoc_bodies` is not `check_first`'s. `codex_lane` and
`absent_binary` both tokenise through it, so a defect in it blinds three guards
at once — and the two defects fixed here did exactly that, in the direction that
makes a guard MISS a command rather than trip on an innocent one.

WHY THIS IS ITS OWN MODULE. The fix is one function; the blast radius is three
guards. Tests split across `test_check_first.py` / `test_codex_lane.py` /
`test_absent_binary.py` would each look like a local edge case, and the next
person to touch the opener would have no single place that says "this is shared,
and here is what shared means". Every test below therefore runs the SAME shell
shape through all three guards.

THE TWO DEFECTS, both live until 2026-09-03, both in the blinding direction.
The opener was `re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")`:

1. `\w+` stops at the first `-` or `.`, so `<<'END-MSG'` captured `END`. No
   later line equals `END`, so the heredoc never closed and EVERY command after
   it was discarded as body.
2. The regex matched anywhere, including inside quotes. `git commit -m 'see
   <<EOF note'` — a commit message ABOUT heredocs, which this repo writes
   routinely — opened a heredoc with the same consequence.

Both were found by `codex review` on two consecutive rounds before either was
fixed, which is the useful part: a reading pass sees a regex that plainly
handles `<<'EOF'`, because the case it handles is the one you think of.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from kb_setup import absent_binary, check_first, codex_lane, hook_guard
from kb_setup.result import Ok

#: One guard, its `decide`, and a command that guard denies on its own.
#:
#: `gtimeout` rather than `timeout` for `absent_binary`: `"conda:coreutils"` in
#: `mise.toml` makes `timeout`/`nproc`/`tac` genuinely resolve here, so only
#: `gtimeout` still denies on this host. The `absent` fixture fakes `which`
#: anyway, so the choice is belt-and-braces rather than load-bearing.
GUARDS: list[tuple[str, Callable[[str], str | None], str]] = [
    ("check_first", check_first.decide, "ruff check foo.py"),
    ("codex_lane", codex_lane.decide, "codex exec -"),
    ("absent_binary", absent_binary.decide, "gtimeout 5 ls"),
]

#: The same guards without the denied command, for tests whose bait comes from
#: `BODY_BAIT` instead. Derived rather than retyped so the two cannot drift.
DECIDERS: list[tuple[str, Callable[[str], str | None]]] = [
    (name, decide) for name, decide, _ in GUARDS
]

#: A body line each guard WOULD deny if it were read as a command position.
#: Used for the negative controls, which is where the original heredoc fix lives.
BODY_BAIT: dict[str, str] = {
    "check_first": "  ruff check foo.py    discards the exit code",
    "codex_lane": "  codex resume --last   spends the subscription",
    "absent_binary": "  gtimeout 5 ls         is not installed here",
}


@pytest.fixture(autouse=True)
def _traps_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `absent_binary`'s trap names unresolvable, host-independently.

    Copied in shape from `test_absent_binary.py`'s own `absent` fixture and for
    its stated reason: what `timeout`/`nproc`/`tac`/`gtimeout` do against the
    live host has changed three times as pins moved, and a tokeniser test must
    not fail because someone pinned a package.

    `autouse` because two of the three guards here never touch `shutil.which`,
    so applying it everywhere costs nothing and removes a per-test decision.
    """

    def which(name: str, *_args: object, **_kwargs: object) -> str | None:
        return None if name in absent_binary.TRAPS else f"/usr/bin/{name}"

    monkeypatch.setattr(absent_binary.shutil, "which", which)


def _ids(cases: list[tuple[str, str]]) -> list[str]:
    return [name for name, _ in cases]


# ---------------------------------------------------------------------------
# Defect 1 — the delimiter capture stopped at the first non-word character.
# ---------------------------------------------------------------------------

#: Delimiters `\w+` truncates or mangles. Each pairs the opener with the closing
#: line it must match, because the bug is precisely that the two stopped agreeing.
AWKWARD_DELIMITERS: list[tuple[str, str]] = [
    ("quoted-hyphen", "'END-MSG'"),
    ("quoted-dot", "'END.MSG'"),
    ("quoted-double-hyphen", '"END-MSG"'),
    ("bare-hyphen", "END-MSG"),
    ("bare-dot", "end.of.message"),
    ("quoted-plus", "'END+MSG'"),
    ("dash-form-hyphen", "'END-MSG'"),
]


@pytest.mark.parametrize(("guard", "decide", "denied"), GUARDS, ids=[g[0] for g in GUARDS])
@pytest.mark.parametrize(("label", "opener"), AWKWARD_DELIMITERS, ids=_ids(AWKWARD_DELIMITERS))
def test_a_command_after_an_awkward_delimiter_is_still_seen(
    guard: str,
    decide: Callable[[str], str | None],
    denied: str,
    label: str,
    opener: str,
) -> None:
    r"""The command AFTER the heredoc must still reach the guard.

    With `\w+`, `<<'END-MSG'` captured `END`, the closing `END-MSG` line never
    matched it, and the guarded command below was swallowed as body — the guard
    reported nothing and the command ran.
    """
    delimiter = opener.strip("'\"")
    dash = "-" if label == "dash-form-hyphen" else ""
    command = f"git commit -q -F - <<{dash}{opener}\nsome message body\n{delimiter}\n{denied}"
    assert decide(command) is not None, f"{guard} went blind after <<{dash}{opener}"


# ---------------------------------------------------------------------------
# Defect 2 — the opener matched inside quotes, where `<<` is data.
# ---------------------------------------------------------------------------

#: Shell lines containing the CHARACTERS `<<` where no redirection happens.
QUOTED_NON_OPENERS: list[tuple[str, str]] = [
    ("single-quoted-literal", "printf '<<EOF'"),
    ("double-quoted-literal", 'printf "<<EOF"'),
    ("commit-message-about-heredocs", "git commit -m 'the <<EOF form is safe'"),
    ("commit-message-double", 'git commit -m "the <<EOF form is safe"'),
    ("echo-into-a-file", "echo 'use <<EOF here' > /tmp/note.txt"),
    ("awk-program", "awk '{ print \"<<EOF\" }' /tmp/in.txt"),
]


@pytest.mark.parametrize(("guard", "decide", "denied"), GUARDS, ids=[g[0] for g in GUARDS])
@pytest.mark.parametrize(("label", "line"), QUOTED_NON_OPENERS, ids=_ids(QUOTED_NON_OPENERS))
def test_a_quoted_redirection_operator_opens_no_heredoc(
    guard: str,
    decide: Callable[[str], str | None],
    denied: str,
    label: str,
    line: str,
) -> None:
    """`<<` inside a quoted word is data, and must not swallow what follows.

    This is the realistic break, not a contrived one: the commit message that
    shipped the ORIGINAL heredoc fix described the `<<'EOF'` form in prose, so
    committing it would have blinded the guard to anything in the same call.
    """
    command = f"{line}\n{denied}"
    assert decide(command) is not None, f"{guard} went blind after a quoted `<<` ({label})"


def test_a_quote_left_open_carries_to_the_next_line() -> None:
    """A shell string spans newlines, so quote state must too.

    `git commit -m 'line one` + `line two <<EOF'` is one single-quoted token
    across two lines. Scanning each line from a clean slate would see the second
    line's `<<EOF` as a redirection. Tokenising per line is what a regex forces;
    carrying the state is what a scanner allows.
    """
    command = "git commit -m 'line one\nline two mentions <<EOF here'\nruff check foo.py"
    assert check_first.decide(command) is not None


# ---------------------------------------------------------------------------
# `<<<` is a HERESTRING and has no body at all.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("guard", "decide", "denied"), GUARDS, ids=[g[0] for g in GUARDS])
def test_a_herestring_consumes_nothing(
    guard: str, decide: Callable[[str], str | None], denied: str
) -> None:
    """`cmd <<<word` takes one word on the SAME line, not a delimited body.

    Reading its operand as a delimiter invents a heredoc no later line can
    close, discarding the rest of the command. The old regex did exactly that:
    `<<-?` matched the first two `<` of `<<<`, then took `<` as neither a quote
    nor a word character and captured whatever came after.
    """
    command = f"cat <<<'some inline text'\n{denied}"
    assert decide(command) is not None, f"{guard} went blind after a herestring"


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS — the original fix must survive all of the above.
# ---------------------------------------------------------------------------
#
# Without these, every test in this file could be satisfied by deleting
# `strip_heredoc_bodies` entirely. They are what make the arms above mean
# "the guard sees past a body" rather than "the guard sees everything".


@pytest.mark.parametrize(("guard", "decide"), DECIDERS, ids=[g[0] for g in GUARDS])
@pytest.mark.parametrize(("label", "opener"), AWKWARD_DELIMITERS, ids=_ids(AWKWARD_DELIMITERS))
def test_a_body_under_an_awkward_delimiter_is_still_hidden(
    guard: str,
    decide: Callable[[str], str | None],
    label: str,
    opener: str,
) -> None:
    """Widening the delimiter must not stop bodies being stripped.

    This is the direction the whole function exists for: a commit message
    listing guarded commands is DATA. The fix moved the closing-line match, and
    a delimiter that now parses but never closes would fail loudly here.
    """
    delimiter = opener.strip("'\"")
    dash = "-" if label == "dash-form-hyphen" else ""
    command = f"git commit -q -F - <<{dash}{opener}\n{BODY_BAIT[guard]}\n{delimiter}"
    assert decide(command) is None, f"{guard} tripped on heredoc BODY text"


@pytest.mark.parametrize(("guard", "decide", "denied"), GUARDS, ids=[g[0] for g in GUARDS])
def test_the_plain_delimiter_case_is_unchanged(
    guard: str, decide: Callable[[str], str | None], denied: str
) -> None:
    """The case the old regex DID handle still works — no regression.

    A fix that only ever runs against its own new fixtures proves nothing about
    what it replaced.
    """
    hidden = f"git commit -q -F - <<'EOF'\n{BODY_BAIT[guard]}\nEOF"
    assert decide(hidden) is None, f"{guard} tripped on a plain heredoc body"

    visible = f"cat <<'EOF' > /tmp/p.md\nsome prompt text\nEOF\n{denied}"
    assert decide(visible) is not None, f"{guard} went blind after a plain heredoc"


# ---------------------------------------------------------------------------
# END-TO-END, through the real hook entry point.
# ---------------------------------------------------------------------------
#
# Everything above calls a guard's `decide` directly. `check_hook_call` is what
# `.claude/settings.json` actually runs: it parses the hook payload and walks the
# whole ordered chain. A test at that level is the only one that can catch a
# guard being reachable in isolation but unreachable in the chain.
#
# It earned its place immediately. Probing this by hand first, the author called
# `hook_guard.decide` — which is ONLY the graphify redirect — got False for every
# heredoc case, and briefly read it as the fix having failed. A control arm
# (`uv run ruff check` with no heredoc at all, also False) showed the probe was
# measuring the wrong function. `probes-need-a-control-arm.md` rule 5, in the
# cheapest possible form: a uniform negative is usually one broken probe.

HOOK_CASES: list[tuple[str, str, bool]] = [
    # Controls that MUST deny — without these the parametrisation could pass by
    # the chain being broken rather than by the tokeniser being right.
    ("control-plain-gate", "uv run ruff check foo.py", True),
    ("control-plain-lane", "codex exec -", True),
    # Controls that MUST NOT deny.
    ("control-innocent", "git status --short", False),
    (
        "control-body-only",
        "git commit -q -F - <<'EOF'\nuv run ruff check x.py\nEOF",
        False,
    ),
    # The defect, at the entry point.
    (
        "hyphen-delimiter-then-gate",
        "git commit -q -F - <<'END-MSG'\nfix: x\nEND-MSG\nuv run ruff check foo.py",
        True,
    ),
    (
        "dot-delimiter-then-lane",
        "git commit -q -F - <<'END.MSG'\nfix: x\nEND.MSG\ncodex exec -",
        True,
    ),
    (
        "message-about-heredocs-then-lane",
        "git commit -m 'the <<EOF form is safe'\ncodex exec -",
        True,
    ),
    ("herestring-then-gate", "cat <<<'note'\nuv run ty check foo.py", True),
    ("quoted-printf-then-gate", "printf '<<EOF'\nuv run ruff check foo.py", True),
    # --- the four P1s a cold lane found in the FIRST version of this fix ------
    #
    # Two were REGRESSIONS the scanner introduced against the regex it replaced
    # (ANSI-C, backslash continuation): the old code denied these and the new
    # code did not. Two were pre-existing and newly discovered (nested command
    # substitution, multiple heredocs per line) — the old regex was blind to
    # them too, so they are not regressions; but a fix that hardens a guard
    # while leaving known blind spots in it is not a hardened guard.
    #
    # All four fail in the BLINDING direction, which is why all four are here
    # rather than deferred. Every one was found by RUNNING the shape, not by
    # reading the scanner — the third round in a row where that is what worked.
    (
        "ansi-c-delimiter-then-gate",
        "cat <<$'END-MSG'\nbody\nEND-MSG\nuv run ruff check foo.py",
        True,
    ),
    # `codex exec -`, NOT a `ruff` gate, and the difference is the whole test.
    # This case first shipped with `uv run ruff check foo.py` and its arm
    # SURVIVED: `check_first` has a regex fallback (`_HAND_GATE_FALLBACK`) that
    # matches the raw command text without consulting the tokeniser at all, so
    # the chain denied whether or not the heredoc had swallowed the line. The
    # test could not fail. Measured by simulating the mutation: with the
    # backslash taken as a delimiter, the `codex exec -` form goes blind
    # (denies=False) while the `ruff` form still denies=True.
    #
    # GENERAL FORM: when arming a SHARED tokeniser, pick a guard with no
    # independent fallback, or the fallback answers for it.
    (
        "backslash-continuation-then-lane",
        "cat <<\\\nEOF\nbody\nEOF\ncodex exec -",
        True,
    ),
    # `<<$VAR` is a delimiter only bash can resolve, so `_read_delimiter` refuses
    # it. Nothing covered that until an arm removed the refusal and survived.
    ("expansion-delimiter-then-lane", "cat <<$VAR\nbody\nEOF\ncodex exec -", True),
    (
        "nested-command-substitution-then-gate",
        'x="$(printf "%s" "<<EOF")"\nuv run ruff check foo.py',
        True,
    ),
    (
        "second-heredoc-body-hides-a-fake-opener",
        "cat <<A <<B\nbodyA\nA\n<<NEVER\nB\nuv run ruff check foo.py",
        True,
    ),
    ("two-heredocs-then-gate", "cat <<A <<B\nbodyA\nA\nbodyB\nB\nuv run ruff check foo.py", True),
    # ...and the matching negative: BOTH bodies must still be stripped, or the
    # queue fix would have bought visibility by giving up the function's purpose.
    (
        "two-heredoc-bodies-stay-hidden",
        "cat <<A <<B\nuv run ruff check foo.py\nA\nuv run ruff check foo.py\nB",
        False,
    ),
    # The ANSI-C step-over is load-bearing HERE, not in the case above it.
    # Refusing `$'END-MSG'` outright would still keep the guard un-blinded (the
    # `$`-in-delimiter refusal catches it), so only a BODY case can tell the two
    # apart: reading the delimiter correctly is what lets the body be stripped.
    # Without this the step-over is redundant and its arm survives.
    (
        "ansi-c-body-stays-hidden",
        "git commit -q -F - <<$'END-MSG'\ncodex exec -\nEND-MSG",
        False,
    ),
]


@pytest.mark.parametrize(("label", "command", "denied"), HOOK_CASES, ids=[c[0] for c in HOOK_CASES])
def test_the_whole_guard_chain_sees_past_a_heredoc(
    label: str, command: str, *, denied: bool
) -> None:
    """The ordered chain in `check_hook_call`, not one guard's `decide`."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = hook_guard.check_hook_call(payload)
    # Asserting Ok is part of the test, not ceremony: the chain fails OPEN on its
    # own errors, so an Err here would otherwise read as "nothing to report".
    assert isinstance(result, Ok), f"{label}: chain returned {result!r}"
    assert bool(result.value) is denied, f"{label}: chain denied={bool(result.value)} want={denied}"


# ---------------------------------------------------------------------------
# Unit-level arms on the tokeniser itself.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("no redirection here", "no redirection here"),
        ("cmd <<EOF\nbody\nEOF\nafter", "cmd <<EOF\nafter"),
        ("cmd <<'END-MSG'\nbody\nEND-MSG\nafter", "cmd <<'END-MSG'\nafter"),
        ("cmd <<-EOF\nbody\nEOF\nafter", "cmd <<-EOF\nafter"),
        ("printf '<<EOF'\nafter", "printf '<<EOF'\nafter"),
        ("cat <<<'inline'\nafter", "cat <<<'inline'\nafter"),
    ],
)
def test_strip_heredoc_bodies_directly(command: str, expected: str) -> None:
    """The tokeniser in isolation, so a failure names the function not a guard."""
    assert check_first.strip_heredoc_bodies(command) == expected


def test_an_unterminated_heredoc_still_drops_its_remainder() -> None:
    """Deliberate, and unchanged: after an unclosed delimiter there is only data.

    Stated as a test rather than left implicit, because it is the one case where
    the function DOES discard trailing lines and someone reading the arms above
    could reasonably think that was the bug.
    """
    assert check_first.strip_heredoc_bodies("cmd <<EOF\nbody\nmore body") == "cmd <<EOF"


def test_an_unreadable_delimiter_does_not_swallow_the_rest() -> None:
    """`<<` with nothing usable after it opens no body.

    An unterminated quote yields no delimiter, so there is no closing line to
    look for. Discarding the remainder on that basis would be the blinding
    failure again, arriving by a third route.
    """
    assert check_first.strip_heredoc_bodies("cmd << 'unclosed\nafter") == "cmd << 'unclosed\nafter"
