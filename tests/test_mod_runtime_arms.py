# Copyright (c) 2026 Raymond Manaloto
"""FAIL-direction arms for the `mod_runtime` gate.

Two families, kept in one file because they share the same stub scaffolding:

* the arms for `c33a1fb5`'s fix, which shipped UNREVIEWED and UNARMED — its own
  commit message said so, and reverting it left all 26 existing tests green;
* the arms for the three P1s that fix closed nothing of.

Each test here FAILS on the code as it stood before its fix. That is the whole
point: an arm verified only against the repaired code is decoration
(`probes-need-a-control-arm.md` rule 2). The measured matrix is in
`.agent/kb/review-round/lanes/a3-code-faults.md`.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from kb_setup import mod_runtime
from kb_setup.result import Rc

REPO = Path(__file__).resolve().parents[1]
_SRC = (REPO / mod_runtime.REGISTER_TS).read_text(encoding="utf-8")
_ANCHOR = "const lane = laneOf(e);"

#: The contract as committed. Pinned by NAME so that a change to the extractor
#: shows up as a diff a human reads, rather than as a silently different set.
_COMMITTED = frozenset(
    {"agentId", "deny", "file_path", "fs", "kind", "list", "log", "name", "tool", "tool.call", "ui"}
)


def _stub_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod_runtime, "resolve_claude", lambda: Path("/stub/claude"))
    monkeypatch.setattr(mod_runtime, "claude_version", lambda _binary: "9.9.9 (stub)")


def _spy_subprocess(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Record the kwargs `generate_declarations` hands to `subprocess.run`."""
    seen: dict[str, object] = {}

    def spy(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(mod_runtime.subprocess, "run", spy)
    return seen


# --------------------------------------------------------------- c33a1fb5's fix


def test_the_generator_subprocess_is_handed_the_function_hooks_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _spy_subprocess(monkeypatch)
    # The session running the tests may carry the flag itself. Deleting it is
    # load-bearing: inheritance via `{**os.environ}` would otherwise satisfy this
    # assertion without the explicit set, making the test tautological inside a
    # Claude Code session — which is exactly where it will usually run.
    monkeypatch.delenv("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS", raising=False)
    _stub_binary(monkeypatch)

    mod_runtime.check(REPO)

    env = seen.get("env")
    assert isinstance(env, dict)
    assert env.get("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS") == "1"


def test_an_unknown_plugin_types_command_is_not_run_rather_than_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_binary(monkeypatch)

    def fake_generate(
        _binary: Path, _workdir: Path, *_rest: object
    ) -> subprocess.CompletedProcess[str]:
        # What the binary does with the flag OFF, measured: writes nothing,
        # prints this, exits 0. rc 0 is why the existing rc check cannot see it.
        return subprocess.CompletedProcess([], 0, "Unknown command: /plugin-types\n", "")

    monkeypatch.setattr(mod_runtime, "generate_declarations", fake_generate)

    # Pre-fix this returned FINDINGS — "expected output not written" — which
    # reads as a real contract breach rather than as a probe that never ran.
    assert mod_runtime.check(REPO) == Rc.NOT_RUN


# ------------------------------------------------------- P1-1: the derived set


def test_the_committed_contract_is_exactly_the_pinned_set() -> None:
    assert mod_runtime.required_runtime_tokens(_SRC) == _COMMITTED


@pytest.mark.parametrize(
    "form",
    [
        'const pm = e["permissionMode"];',
        "const { permissionMode } = e;",
        "$.ui.log(`pm ${e.permissionMode}`);",
    ],
)
def test_ordinary_access_forms_join_the_contract(form: str) -> None:
    """Bracket access, destructuring and template interpolation were all invisible.

    Each left the derived set at 11 — so the module's claim that a new field
    joins the contract with no edit held only for dotted access outside a
    template literal.
    """
    derived = mod_runtime.required_runtime_tokens(_SRC.replace(_ANCHOR, _ANCHOR + "\n    " + form))
    assert derived is not None
    assert "permissionMode" in derived


def test_destructuring_with_rename_keeps_the_key_not_the_alias() -> None:
    derived = mod_runtime.required_runtime_tokens(
        _SRC.replace(_ANCHOR, _ANCHOR + "\n    const { permissionMode: pm } = e;")
    )
    assert derived is not None
    assert "permissionMode" in derived
    assert "pm" not in derived


# --------------------------------------------------- P1-2: presence vs declared


def test_a_symbol_present_only_in_a_comment_is_missing() -> None:
    declarations = (
        "// agentId was removed\n/** old agentId */\ninterface ToolCallEvent { file_path: string; }"
    )
    assert mod_runtime.missing_tokens(frozenset({"agentId"}), declarations) == frozenset(
        {"agentId"}
    )


def test_a_longer_dotted_name_does_not_satisfy_the_event() -> None:
    """`tool.callback` contains `tool.call`; the dotted arm had no right boundary."""
    assert mod_runtime.missing_tokens(frozenset({"tool.call"}), 'on("tool.callback")') == frozenset(
        {"tool.call"}
    )


# ------------------------------------------------------------- P1-3: the caller's HOME


def test_the_generator_runs_under_an_isolated_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate left 13 directories in the real `~/.claude/projects/` in one day."""
    seen = _spy_subprocess(monkeypatch)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/should/be/dropped")
    _stub_binary(monkeypatch)

    mod_runtime.check(REPO)  # the verdict is irrelevant; the spy records env and cwd

    env = seen.get("env")
    assert isinstance(env, dict)
    home = Path(env["HOME"])
    assert env["HOME"] != os.environ["HOME"]
    assert "CLAUDE_CONFIG_DIR" not in env
    tmp = Path(tempfile.gettempdir())
    assert home.is_relative_to(tmp) or home.is_relative_to(tmp.resolve())
    work = Path(str(seen["cwd"]))
    assert home.parent == work.parent, "HOME must sit BESIDE the work dir"
    assert home != work, "a HOME inside the work dir surfaces as UNEXPECTED OUTPUT"


# ═══════════════════════════════════════════════════════════════════════════
# Round 2 — arms for the nine findings a cold `gpt-6-astra` lane raised against
# the round-1 fixes above. Four of the nine were defects IN THOSE FIXES, which
# is this repo's fifth recorded instance of "the fix is where the defect lives".
# Every test below FAILS on the round-1 code.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "form",
    [
        "const pm = e['permissionMode'];",  # single quotes
        "const { permissionMode }: any = e;",  # a type annotation before `=`
    ],
)
def test_single_quotes_and_type_annotations_are_not_invisible(form: str) -> None:
    """Round 1 matched only double quotes and only un-annotated destructuring."""
    derived = mod_runtime.required_runtime_tokens(_SRC.replace(_ANCHOR, _ANCHOR + "\n    " + form))
    assert derived is not None
    assert "permissionMode" in derived


@pytest.mark.parametrize(
    "noise",
    [
        'const status = ["bogusMember"];',  # an array literal has no receiver
        # Prose inside a string. 🔴 The QUOTING here is load-bearing and the first
        # version of this case was a no-op: written as
        # `$.ui.log("see e[\\"bogusMember\\"] ...")` the character after `[` is a
        # BACKSLASH, so `_BRACKET_ACCESS` never matched it at all and the arm that
        # severs the span filter SURVIVED — a test that could not fail, caught by
        # the mutation sweep rather than by reading it. A TS single-quoted string
        # holding unescaped double quotes is both realistic and actually matches.
        "$.ui.log('see e[\"bogusMember\"] for details');",
    ],
)
def test_ordinary_data_and_prose_do_not_become_runtime_dependencies(noise: str) -> None:
    """Round 1's bracket scan needed no receiver and ran with strings intact."""
    derived = mod_runtime.required_runtime_tokens(_SRC.replace(_ANCHOR, _ANCHOR + "\n    " + noise))
    assert derived is not None
    assert "bogusMember" not in derived


def test_a_url_in_a_string_does_not_erase_the_property_read_beside_it() -> None:
    """`strip_ts_comments` sees `//` inside `"https://…"` and eats the rest of the line."""
    injected = 'const url = "https://example.com"; const pm = e.permissionMode;'
    derived = mod_runtime.required_runtime_tokens(
        _SRC.replace(_ANCHOR, _ANCHOR + "\n    " + injected)
    )
    assert derived is not None
    assert "permissionMode" in derived


def test_an_extended_event_name_does_not_satisfy_the_required_one() -> None:
    """`tool.call.after` contains `tool.call`; the right boundary must reject a dot."""
    assert mod_runtime.missing_tokens(
        frozenset({"tool.call"}), 'on("tool.call.after", handler)'
    ) == frozenset({"tool.call"})


def test_the_resolved_binary_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generation changes cwd, so a relative `which` result fails after the chdir."""
    monkeypatch.setattr(mod_runtime.shutil, "which", lambda _name: "relative/dir/claude")

    resolved = mod_runtime.resolve_claude()

    assert resolved is not None
    assert resolved.is_absolute()


def test_the_vendored_delta_does_not_claim_live_presence_for_a_token_absent_from_both(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reporter runs after a FAILED reconciliation too, and contradicted it."""
    mod_runtime._report_vendored_delta(
        REPO,
        fresh="interface ToolCallEvent { file_path: string; }",
        required=frozenset({"kbTokenInNeitherInput"}),
    )

    printed = capsys.readouterr().out
    assert "present in the live one: kbTokenInNeitherInput" not in printed
    assert "absent from BOTH" in printed


# ═══════════════════════════════════════════════════════════════════════════
# Round 3 — arms for the THREE P1 blocking findings a cold lane raised against
# round 2. All three were defects round 2 introduced. Sixth instance in one day.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_resolved_binary_is_not_symlink_dereferenced(monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 `.resolve()` returned the MISE binary and reported mise's version as Claude's.

    `claude` on PATH here is a mise shim. `.resolve()` follows it to
    `~/.local/bin/mise`, and `claude_version()` on that exits 0 reporting
    `"2026.9.5 macos-arm64"` — a version certified with no error anywhere. The
    gate's own docstring says the shim IS what runs and is deliberately what it
    probes.

    This test is written to fail under `.resolve()` and pass under `.absolute()`;
    the round-2 version asserted only `is_absolute()`, which BOTH satisfy, and a
    cold lane measured that as a surviving mutation.
    """
    link = Path(tempfile.mkdtemp()) / "claude"
    target = link.parent / "real-binary"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    link.symlink_to(target)
    monkeypatch.setattr(mod_runtime.shutil, "which", lambda _name: str(link))

    resolved = mod_runtime.resolve_claude()

    assert resolved is not None
    assert resolved.is_absolute()
    assert resolved.name == "claude", "the symlink must NOT be dereferenced to its target"


def test_a_stray_backtick_in_a_comment_does_not_swallow_the_code_beneath_it() -> None:
    """The other direction of the strip-order bug, which round 2's reorder opened.

    Measured by a cold lane: 11 tokens collapsed to 6 — losing `permissionMode`
    among others — and landed exactly on the minimum-token floor, so the gate
    stayed green while the contract had lost half its members.
    """
    injected = "// a comment with a stray ` backtick\n    const pm = e.permissionMode;"
    derived = mod_runtime.required_runtime_tokens(
        _SRC.replace(_ANCHOR, _ANCHOR + "\n    " + injected)
    )
    assert derived is not None
    assert "permissionMode" in derived
    assert derived >= _COMMITTED, "the committed contract must survive a backtick in a comment"


@pytest.mark.parametrize(
    "form",
    [
        'const pm = e?.["permissionMode"];',  # optional chaining
        '$.ui.log(`pm ${e["permissionMode"]}`);',  # inside a template interpolation
    ],
)
def test_forms_round_one_extracted_are_not_lost_by_round_twos_narrowing(form: str) -> None:
    """Both were extracted before round 2 and dropped by it — a silent regression."""
    derived = mod_runtime.required_runtime_tokens(_SRC.replace(_ANCHOR, _ANCHOR + "\n    " + form))
    assert derived is not None
    assert "permissionMode" in derived


def test_every_named_write_location_override_is_scrubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 The round-2 test derived its fixture AND its assertion from the same tuple.

    Deleting five of the six entries left the suite green while the variables
    genuinely leaked into the child environment — a cold lane measured two
    surviving mutations with four `XDG_*` variables present in the spied env
    while the assertion computed `leaked == []`. A test whose expectation is
    read from the thing under test cannot fail when that thing shrinks.

    The names are pinned LITERALLY here for exactly that reason.
    """
    expected = {
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_DEBUG_LOGS_DIR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
    assert set(mod_runtime._WRITE_LOCATION_OVERRIDES) == expected, (
        "a name removed from the tuple is a variable that leaks; add it back or "
        "change this literal deliberately"
    )

    seen = _spy_subprocess(monkeypatch)
    for name in sorted(expected):
        monkeypatch.setenv(name, f"/should/be/dropped/{name}")
    _stub_binary(monkeypatch)

    mod_runtime.check(REPO)

    env = seen.get("env")
    assert isinstance(env, dict)
    leaked = sorted(name for name in expected if name in env)
    assert leaked == [], f"the child can still write outside the isolated HOME via {leaked}"


def test_a_relative_path_from_which_is_made_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generation changes cwd, so a relative `PATH` entry breaks after the chdir.

    Kept SEPARATE from the no-dereference test on purpose: that one cannot fail
    under a relative path (its fixture is already absolute), and this one cannot
    fail under `.resolve()` (which is also absolute). One test covering both
    would be satisfied by either half, which is how round 2 shipped a
    `.resolve()` that reported mise's version as Claude Code's.
    """
    monkeypatch.setattr(mod_runtime.shutil, "which", lambda _name: "relative/dir/claude")

    resolved = mod_runtime.resolve_claude()

    assert resolved is not None
    assert resolved.is_absolute()
