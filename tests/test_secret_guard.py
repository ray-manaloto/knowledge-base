# Copyright (c) 2026 Raymond Manaloto
"""Both directions of `kb_setup.secret_guard` (#441).

The ALLOW arms carry as much weight as the DENY arms here, and deliberately more
of the file. Every measured defect in this repo's PreToolUse guards has been a
false positive, never an evasion — and a secret guard that refuses `fnox list`
or `[[ -v NAME ]]` is a guard people route around, which leaves the leak
unguarded AND costs the trust the other four guards run on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import secret_guard
from kb_setup.hook_guard import check_hook_call
from kb_setup.result import Ok

# --------------------------------------------------------------------------
# DENY — the commands whose SUCCESS case writes a credential to stdout.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "fnox get GEMINI_API_KEY",
        "fnox get GEMINI_API_KEY | wc -c",
        "fnox export --format shell",
        "fnox list --values",
        "fnox list -V",
        "doppler secrets get STRIPE_KEY",
        "doppler secrets download --no-file",
        "doppler secrets",
        "doppler secrets --project dotfiles --config dev_personal",
        "security find-generic-password -s doppler -w",
        "security find-internet-password -g -a me",
        "env",
        "printenv",
        "set",
    ],
)
def test_a_value_printing_command_is_denied(command):
    assert secret_guard.decide(command) is not None, command


def test_the_denial_names_the_probe_that_replaces_it():
    """A refusal with no alternative is what gets routed around."""
    reason = secret_guard.decide("fnox get SOME_KEY")
    assert reason is not None
    assert "[[ -v NAME ]]" in reason
    assert "fnox list" in reason, "the allowed names-only listing must be named"


def test_a_leak_behind_a_transparent_prefix_is_still_denied():
    """`env FOO=1 fnox get X` runs `fnox get`; the wrapper must not hide it."""
    assert secret_guard.decide("env FOO=1 fnox get SOME_KEY") is not None


def test_a_leak_in_a_later_pipeline_segment_is_denied():
    """Segments are judged individually — the leak is rarely the first word."""
    assert secret_guard.decide("echo hi && fnox get SOME_KEY") is not None


def test_an_absolute_path_to_the_binary_is_still_denied():
    """`basename` is applied, so `/opt/homebrew/bin/fnox get` cannot slip past."""
    assert secret_guard.decide("/opt/homebrew/bin/fnox get SOME_KEY") is not None


# --------------------------------------------------------------------------
# The substitution trap — the shape that LOOKS like a presence probe.
# --------------------------------------------------------------------------


def test_the_paired_substitution_probe_is_denied():
    """`${X:+SET}${X:-ABSENT}` prints X's VALUE when X is set."""
    reason = secret_guard.decide('echo "${DOPPLER_TOKEN:+SET}${DOPPLER_TOKEN:-ABSENT}"')
    assert reason is not None
    assert "DOPPLER_TOKEN" in reason
    assert "[[ -v DOPPLER_TOKEN ]]" in reason


def test_a_lone_default_substitution_is_allowed():
    """THE FALSE-POSITIVE ARM, and the reason the rule is the PAIR.

    `${HOME:-/tmp}` is one of the most common idioms in shell. A guard that
    denied it would fire constantly on code that leaks nothing, and this guard's
    false positives are the direction that actually costs.
    """
    assert secret_guard.decide("cd ${HOME:-/tmp}") is None
    assert secret_guard.decide('echo "${SOME_KEY:-unset}"') is None


def test_the_pair_must_be_the_same_variable():
    """Two different names are two ordinary defaults, not the probe idiom."""
    assert secret_guard.decide('echo "${FOO:+yes}${BAR:-no}"') is None


# --------------------------------------------------------------------------
# Heredocs — the guard's first FALSE POSITIVE, and its mirror.
#
# Both arms below were produced by this guard in one session, twenty minutes
# apart, from the same rule. Only one of them was a defect.
# --------------------------------------------------------------------------


def test_a_quoted_heredoc_body_is_allowed():
    """THE FALSE POSITIVE. `<<'EOF'` never expands, so nothing can leak.

    Writing a file whose TEXT described the paired substitution was denied.
    A guard that stops you documenting the trap it guards is the routed-around
    kind.
    """
    command = "cat > notes.md <<'EOF'\nbeware ${TOKEN:+SET}${TOKEN:-ABSENT}\nEOF"
    assert secret_guard.decide(command) is None


def test_an_unquoted_heredoc_body_is_still_denied():
    """THE ARM THAT PROVES THE FIX IS NOT JUST "HEREDOCS ARE EXEMPT".

    `<<EOF` with a bare delimiter DOES expand, so the same bytes really do
    print the value. Same shape as the test above; only the quoting differs.
    """
    command = "cat > notes.md <<EOF\nbeware ${TOKEN:+SET}${TOKEN:-ABSENT}\nEOF"
    assert secret_guard.decide(command) is not None


def test_a_double_quoted_argument_is_still_denied():
    """THE TRUE POSITIVE this guard scored on its own author.

    `gh issue comment --body "…"` is expanded by the shell before `gh` sees it,
    so a real credential name would have reached a public issue. Recorded as a
    test so a later "reduce false positives" pass cannot quietly take it out.
    """
    command = 'gh issue comment 441 --body "note: ${TOKEN:+SET}${TOKEN:-ABSENT} prints it"'
    assert secret_guard.decide(command) is not None


def test_an_unterminated_quoted_heredoc_is_allowed():
    """No closing delimiter means the body runs to the end — still inert."""
    command = "cat > notes.md <<'EOF'\nbeware ${TOKEN:+SET}${TOKEN:-ABSENT}"
    assert secret_guard.decide(command) is None


def test_a_leak_before_a_quoted_heredoc_is_still_denied():
    """Stripping the body must not strip what precedes it."""
    command = "fnox get SOME_KEY; cat > x <<'EOF'\ninert\nEOF"
    assert secret_guard.decide(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        # Closed heredoc — the case the cold lane did NOT predict.
        "cat <<'EOF' && echo \"${TOKEN:+SET}${TOKEN:-ABSENT}\"\nbody\nEOF",
        # Unclosed — the case it did.
        "cat <<'EOF' && echo \"${TOKEN:+SET}${TOKEN:-ABSENT}\"",
    ],
)
def test_a_leak_after_a_heredoc_opener_on_the_same_line_is_denied(command):
    """A heredoc BODY starts on the next line; the opener's line is real shell.

    Slicing from the end of the `<<'EOF'` match deleted the rest of that
    physical line, so `cat <<'EOF' && echo "$…"` reduced to `'cat '` and the
    trailing leak was never scanned. The cold lane on `e2b697c9` found this and
    diagnosed it as the missing-closer branch; reproducing it showed the CLOSED
    form loses the trailing command too — both residues were `'cat '` — so the
    fix is at the line boundary, not in `if closer is None`.

    Parametrised over both because a fix in the `closer is None` branch alone
    passes the second row and fails the first.
    """
    assert secret_guard.decide(command) is not None


def test_the_same_line_rescue_does_not_resurrect_the_false_positive():
    """THE ARM. Preserving the opener's line must not un-strip the BODY.

    This is the #441 false positive itself — a quoted heredoc documenting the
    trap. If the fix above had kept too much, this would go red.
    """
    command = "cat > notes.md <<'EOF'\nbeware ${TOKEN:+SET}${TOKEN:-ABSENT}\nEOF\necho done"
    assert secret_guard.decide(command) is None


# --------------------------------------------------------------------------
# The dumpers — `env` prints the environment when it has no COMMAND to run.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "env -0",  # NUL-separated dump
        "env FOO=1",  # assignment, then nothing to run
        "env -0 | grep TOKEN",
    ],
)
def test_env_with_no_utility_left_is_a_dump_and_is_denied(command):
    """`env` with no COMMAND argument PRINTS the environment.

    The original test was `len(tokens) == 1`, which reasoned about token count
    rather than about what `env` does — so these two-token dumps were allowed
    while bare `env` was denied. `command_word` already answers the real
    question, returning `[]` for exactly these and the utility for a wrapper.
    """
    assert secret_guard.decide(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "env FOO=1 gemini -p",  # the documented ai-cli-invocation wrapper
        "env -i sh -c true",
        "set -e",
        "set -o pipefail",
    ],
)
def test_a_dumper_that_does_reach_a_utility_is_allowed(command):
    """THE FALSE-POSITIVE ARM. `env` as a wrapper is ordinary and must pass.

    `ai-cli-invocation.md` prescribes `env GEMINI_FORCE_FILE_STORAGE=true
    gemini …`; a guard denying its own documented invocation is the
    routed-around kind.
    """
    assert secret_guard.decide(command) is None


# --------------------------------------------------------------------------
# Clustered short options — the ORDINARY spelling, not an evasion.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "security find-generic-password -wa ACCOUNT",
        "security find-internet-password -gs example.com",
    ],
)
def test_a_clustered_value_flag_is_denied(command):
    """`-wa` IS `-w -a`. Exact token equality matched only the spelled-out form.

    Reproduced before the fix: `-w -a` denied, `-wa` allowed — the guard caught
    the spelling nobody writes and missed the one everybody does.
    """
    assert secret_guard.decide(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "security find-generic-password -a ACCOUNT",  # metadata only
        "security find-generic-password --wait ACCOUNT",  # long opt, not a cluster
        "security list-keychains",
    ],
)
def test_declustering_does_not_invent_a_value_flag(command):
    """THE ARM. Splitting `--wait` into letters would deny a benign long option."""
    assert secret_guard.decide(command) is None


# --------------------------------------------------------------------------
# ALLOW — the sanctioned probes. A guard that refuses these is worse than none.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "[[ -v REPOWISE_KNOWLEDGE_BASE_API_KEY ]]",
        "fnox list",
        "fnox check",
        "fnox config-files",
        "fnox profiles",
        "fnox doctor",
        "mise run doctor",
        "doppler secrets --only-names",
        "doppler secrets --project dotfiles --config dev_personal --only-names",
        "doppler secrets set NEW_KEY",
        "command -v fnox",
        "which doppler",
        "type security",
        "env FOO=1 pytest tests/",
        "printenv PATH | tr : '\\n'",
        "git status --short",
    ],
)
def test_a_sanctioned_probe_is_allowed(command):
    assert secret_guard.decide(command) is None, command


def test_the_add_procedure_is_not_denied():
    """`docs/secrets.md`'s nine-step add runs `doppler secrets set`.

    A write verb takes a value as INPUT rather than printing one. Denying it
    would be the guard refusing the very procedure it exists to protect.
    """
    assert secret_guard.decide("doppler secrets set REPOWISE_KEY") is None


def test_prose_mentioning_a_denied_command_is_allowed():
    """THE CLASS EVERY FALSE POSITIVE HERE HAS COME FROM.

    A regex sees `fnox get` inside the commit message; the tokeniser sees one
    quoted token that can never sit at a command position.
    """
    assert secret_guard.decide('git commit -m "docs: explain why fnox get is banned"') is None
    assert secret_guard.decide('echo "never run doppler secrets download"') is None


def test_an_unparsable_command_is_allowed_rather_than_regex_matched():
    """No regex fallback — a bare-word fallback would fire on ordinary prose."""
    assert secret_guard.decide('fnox get "unbalanced') is None


@pytest.mark.parametrize("command", ["", "   ", "\n"])
def test_an_empty_command_is_allowed(command):
    assert secret_guard.decide(command) is None


# --------------------------------------------------------------------------
# Wiring — a guard nothing calls is not a guard.
# --------------------------------------------------------------------------


def _call(command: str, tmp_path: Path) -> str | None:
    """The deny-reason the whole PreToolUse chain returns for `command`.

    Asserts `Ok` rather than reaching straight for `.value`: the boundary can
    also return `Err`, and a helper that blew up on it would make every test
    below report a type error instead of the guard's verdict.
    """
    result = check_hook_call(
        json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "cwd": str(tmp_path),
                "session_id": "s1",
            }
        )
    )
    assert isinstance(result, Ok), f"boundary did not run for {command!r}: {result!r}"
    return result.value


def test_the_guard_is_wired_into_the_bash_chain(tmp_path: Path):
    """The realistic break for an added guard is the WIRING, not the logic."""
    reason = _call("fnox get SOME_KEY", tmp_path)
    assert reason is not None
    assert "secret_guard" in reason


def test_an_ordinary_command_still_passes_the_chain(tmp_path: Path):
    """CONTROL ARM for the two wiring tests — without it they prove nothing."""
    assert _call("git status --short", tmp_path) is None


def test_it_runs_before_the_gate_redirects(tmp_path: Path):
    """A command that both leaks and hand-runs a gate must report the LEAK.

    Ordering is the contract: the other guards compete on whose advice is
    better, but a printed credential is irreversible and outranks advice.
    """
    reason = _call("fnox get SOME_KEY && uv run ruff check python/", tmp_path)
    assert reason is not None
    assert "secret_guard" in reason, "the leak must win over the kb-check redirect"


def test_the_gate_redirect_still_fires_on_its_own(tmp_path: Path):
    """The arm that proves the test above measures ORDER, not a dead redirect."""
    reason = _call("uv run ruff check python/", tmp_path)
    assert reason is not None
    assert "kb-check" in reason
