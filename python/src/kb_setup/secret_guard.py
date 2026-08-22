# Copyright (c) 2026 Raymond Manaloto
"""Deny the credential commands that PRINT A VALUE (#441).

`docs/secrets.md` carried the forbidden-verb contract in prose only — the layer
this repo has twice measured as not working: the warning-only graph-first rule
was complied with **0 times out of 19**, while the DENY that replaced it took its
violations **62 → 0**.

⚠️ **NEITHER REPO ENFORCED THE VERBS, and #441 said dotfiles did.** That premise
was refuted 2026-08-22 by reading the installed source rather than the ticket:
`dotfiles_setup/hook_guard.py` has exactly ONE secret rule,
`secret_value_substitution` (line 531), covering the `${VAR:…}` printing shape
alone — `fnox get`, `fnox export`, `fnox list --values`,
`doppler secrets get`/`download` and `security … -w`/`-g` are **0 hits there**,
against a control of the rule names that do exist. So this module is not a
catch-up with the sibling; on the verbs it is the only guard in either repo, and
dotfiles has the gap filed as its own #780. Corrected here rather than only in
the ticket, because the false version had already reached four artifacts —
`docs/secrets.md`, `.claude/CLAUDE.md`, #441's body, and this docstring.

What the guard is FOR, stated because it is narrower than it looks
------------------------------------------------------------------
Not "secrets are dangerous". The set here is exactly the commands whose SUCCESS
CASE writes a credential to stdout, where stdout is a transcript that is stored,
searched, and fed to other models. A failed `fnox get` is harmless; a successful
one is the incident. That is why presence probes, health checks and name-only
listings are all allowed and must stay allowed — a guard that refuses its own
recommended alternative gets routed around, and every measured defect in this
repo's guards has come from false positives rather than from evasion.

Why it TOKENISES rather than pattern-matching
---------------------------------------------
`check_first.segments` / `command_word`, imported rather than re-implemented, on
`absent_binary`'s precedent. A regex sees `fnox get` inside
`git commit -m "…fnox get…"` and denies it; both of `check_first`'s confirmed
false positives were that shape. After tokenising, a quoted message is one token
and can never sit at a command position.

Unlike `check_first` there is NO regex fallback for an unparsable command. That
guard keeps one because its own earlier version *was* the regex, so degrading to
it opens no hole. This guard has no earlier version, and a bare-word regex for
`get` or `export` would fire inside every sentence that mentions one.

The substitution trap, and why the rule here is NARROW
------------------------------------------------------
`${FOO:+SET}${FOO:-ABSENT}` reads as a presence probe and is not one:
``${FOO:-ABSENT}`` substitutes **FOO's VALUE** when FOO is set. It opens with the
compliant-looking `:+` half, and on an *unset* variable it behaves perfectly — so
an unset-only control arm certifies nothing. A live Doppler token reached a
transcript this way (dotfiles' incident log, 2026-08-02).

Only the PAIRED shape is denied — both `${NAME:+…}` and `${NAME:-…}` for the same
NAME in one command. That is unambiguously the probe idiom and nothing else.
Denying `${NAME:-default}` on its own was considered and rejected: it is one of
the most common idioms in shell (`${HOME:-/tmp}`), so the rule would fire
constantly on code that leaks nothing, and this guard's false positives are the
direction that actually costs.
"""

from __future__ import annotations

import posixpath
import re

from kb_setup import check_first

#: Subcommands that print a credential value, keyed by the command word.
#:
#: `fnox export` is here for a reason worth stating: it renders `export KEY=value`
#: lines, which is the same payload `fnox hook-env` produces. The difference is
#: that `hook-env` is documented to be consumed by `eval "$(…)"` — inside
#: command substitution nothing reaches stdout — while `export` is documented to
#: be READ. So `hook-env` is deliberately absent from this table and `export` is
#: in it; the cold lane on `870c020c` rated an eval-wrapped `hook-env` fence a
#: leak, and it is not one under normal execution.
_VALUE_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "fnox": frozenset({"get", "export"}),
    "doppler": frozenset(),  # handled by _doppler_reason — its shape is two-word
}

#: `fnox list` prints names; `fnox list --values` prints values.
_FNOX_LIST_VALUE_FLAGS = frozenset({"--values", "-V"})

#: `security find-generic-password` prints metadata; `-w` and `-g` print the
#: password itself (`-w` to stdout, `-g` to stderr — both land in a transcript).
_SECURITY_FIND = frozenset({"find-generic-password", "find-internet-password"})
_SECURITY_VALUE_FLAGS = frozenset({"-w", "-g"})

#: Bare, these dump the whole environment of a secret-injected process.
#:
#: Checked against the RAW segment rather than `command_word`, which is not a
#: nicety: `env` is in `check_first._TRANSPARENT_PREFIXES`, so `command_word`
#: strips it and returns an EMPTY list for a bare `env` — the guard would look
#: straight past the exact command it is meant to catch. `env FOO=1 cmd` still
#: passes, because that segment has tokens after the wrapper.
_BARE_DUMPERS = frozenset({"env", "printenv", "set"})

#: Every command this guard judges is `<binary> <subcommand> …`, so a segment with
#: fewer tokens cannot be one of them. A bare `fnox` prints usage and leaks
#: nothing — the early return is what keeps it allowed.
_NEEDS_A_SUBCOMMAND = 2

#: `${NAME:+…}` and `${NAME:-…}`, capturing NAME so the pair can be matched on
#: the SAME variable. Applied to tokens, so a name inside a quoted commit message
#: is one token and still only matches if it really is this construct.
_SUBST_PLUS = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):\+")
_SUBST_DASH = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):-")

_PROBE_INSTEAD = (
    "Probe presence with `[[ -v NAME ]]`. Names, health and structure are all "
    "still allowed: `fnox list`, `fnox check`, `fnox config-files`, "
    "`fnox profiles`, `fnox doctor`, `mise run doctor`, and "
    "`doppler secrets --only-names`."
)

_ATTRIB = (
    "(kb_setup.secret_guard, #441; the contract is docs/secrets.md and it lived "
    "in prose alone until now.)"
)


def _fnox_reason(words: list[str]) -> str | None:
    """`fnox get`/`export` always; `fnox list` only when it asks for values."""
    if len(words) < _NEEDS_A_SUBCOMMAND:
        return None
    sub = words[1]
    if sub in _VALUE_SUBCOMMANDS["fnox"]:
        return (
            f"`fnox {sub}` writes a credential VALUE to stdout, and stdout here is "
            f"a stored transcript. {_PROBE_INSTEAD} {_ATTRIB}"
        )
    if sub == "list" and any(flag in _FNOX_LIST_VALUE_FLAGS for flag in words[2:]):
        return (
            "`fnox list --values` prints every declared credential's VALUE. Bare "
            f"`fnox list` prints the NAMES and is what you want. {_ATTRIB}"
        )
    return None


def _doppler_reason(words: list[str]) -> str | None:
    """`doppler secrets` prints values UNLESS `--only-names` is passed.

    That default is the amendment this guard makes to #441's proposed list,
    which named only `get` and `download`. Control-armed against the installed
    CLI: `doppler secrets --help` documents `--only-names` as *"only print the
    secret names; omit all values"*, so omitting the flag is what prints them.
    A guard that denied the two explicit verbs and waved through the bare
    command would have missed the shortest way to dump the project.
    """
    if len(words) < _NEEDS_A_SUBCOMMAND or words[1] != "secrets":
        return None
    rest = words[2:]
    if "--only-names" in rest:
        return None
    verb = rest[0] if rest and not rest[0].startswith("-") else ""
    if verb in {"get", "download"}:
        return (
            f"`doppler secrets {verb}` writes credential VALUES to stdout. "
            f"{_PROBE_INSTEAD} {_ATTRIB}"
        )
    if verb in {"set", "delete", "upload", "substitute"}:
        # Write verbs. They take a value as INPUT rather than printing one, and
        # the nine-step add procedure in docs/secrets.md runs `doppler secrets
        # set`. Denying the sanctioned add path would be the guard refusing the
        # procedure it exists to protect.
        return None
    return (
        "`doppler secrets` prints VALUES by default — `--only-names` is what "
        "omits them (its own `--help`). Add `--only-names`, or name the verb you "
        f"meant. {_ATTRIB}"
    )


def _security_reason(words: list[str]) -> str | None:
    """The macOS `security find-*-password` verbs print the password with `-w`/`-g`."""
    if len(words) < _NEEDS_A_SUBCOMMAND or words[1] not in _SECURITY_FIND:
        return None
    if not any(flag in _SECURITY_VALUE_FLAGS for flag in words[2:]):
        return None
    return (
        f"`security {words[1]} -w`/`-g` prints the stored password itself (`-g` "
        f"to stderr, which lands in the transcript too). {_PROBE_INSTEAD} "
        f"{_ATTRIB}"
    )


#: A heredoc opener whose delimiter is QUOTED (`<<'EOF'`, `<<-"EOF"`).
#:
#: Quoting the delimiter is what makes the body literal — the shell performs no
#: expansion inside it — so a substitution written there leaks nothing. An
#: UNQUOTED `<<EOF` does expand and is deliberately NOT matched here.
#:
#: Not `graph_first.HEREDOC`: that one matches the opener of either kind, because
#: it answers "is there a heredoc?" while this must answer "is this body inert?".
#: Sharing it would have made this guard skip the expanding form, which is the
#: half that can actually leak.
_QUOTED_HEREDOC = re.compile(r"<<-?\s*(['\"])(\w+)\1")


def _without_quoted_heredocs(command: str) -> str:
    """`command` with every QUOTED heredoc body removed.

    THE GUARD'S FIRST FALSE POSITIVE, twenty minutes after its first true one.
    Writing a file through `cat > x <<'EOF'` whose text *described* the paired
    substitution was denied — but a quoted heredoc never expands, so there was
    nothing to leak. Its true positive minutes earlier was the mirror image: a
    DOUBLE-QUOTED `gh issue comment --body "…"` really is expanded by the shell
    before `gh` sees it, so that one would have posted a value.

    Both come from the same rule, and only one is a defect. That is why the body
    is stripped rather than the rule relaxed.
    """
    out = command
    while True:
        opener = _QUOTED_HEREDOC.search(out)
        if opener is None:
            return out
        delimiter = opener.group(2)
        rest = out[opener.end() :]
        closer = re.search(rf"^\s*{re.escape(delimiter)}\s*$", rest, re.MULTILINE)
        # No closer means the heredoc runs to the end of the command — strip the
        # remainder rather than nothing, or an unterminated body stays scannable
        # and the false positive survives in its most common interactive shape.
        stop = opener.end() + (closer.end() if closer else len(rest))
        out = out[: opener.start()] + out[stop:]


def _substitution_reason(text: str) -> str | None:
    """The `${NAME:+…}${NAME:-…}` presence probe that prints the value.

    Matched on the PAIR for one NAME, never on `${NAME:-default}` alone — see
    the module docstring for why that narrowness is deliberate.

    Takes the RAW command rather than tokens: `shlex` discards the quoting, and
    quoting is exactly what decides whether the shell expands this. The caller
    strips quoted-heredoc bodies first.
    """
    joined = text
    plus = set(_SUBST_PLUS.findall(joined))
    dash = set(_SUBST_DASH.findall(joined))
    both = plus & dash
    if not both:
        return None
    name = min(both)
    return (
        f"`${{{name}:+…}}${{{name}:-…}}` is not a presence probe — the `:-` half "
        f"substitutes {name}'s VALUE when it is set, so this PRINTS the "
        f"credential. It looks correct on an unset control arm, which is how a "
        f"live token reached a transcript on 2026-08-02. Use "
        f"`[[ -v {name} ]]`. {_ATTRIB}"
    )


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` would print a credential, else None.

    Public and pure, matching `hook_guard.decide` / `check_first.decide` /
    `absent_binary.decide`: the function that denies a command is the one a
    fixture table can grade.
    """
    if not command or not command.strip():
        return None
    # Once, on the RAW command, before tokenising: `shlex` discards the quoting
    # that decides whether the shell expands a substitution at all.
    reason = _substitution_reason(_without_quoted_heredocs(command))
    if reason:
        return reason
    segs = check_first.segments(command)
    if segs is None:
        return None
    for tokens in segs:
        if not tokens:
            continue
        # BEFORE `command_word`, which strips `env` as a transparent prefix and
        # would hand back an empty list for the bare dump this catches.
        if len(tokens) == 1 and posixpath.basename(tokens[0]) in _BARE_DUMPERS:
            name = posixpath.basename(tokens[0])
            return (
                f"A bare `{name}` dumps the WHOLE environment of a "
                f"secret-injected process. {_PROBE_INSTEAD} {_ATTRIB}"
            )
        words = check_first.command_word(tokens)
        if not words:
            continue
        for handler in (_fnox_reason, _doppler_reason, _security_reason):
            reason = handler([posixpath.basename(words[0]), *words[1:]])
            if reason:
                return reason
    return None
