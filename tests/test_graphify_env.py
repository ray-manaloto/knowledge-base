# Copyright (c) 2026 Raymond Manaloto
"""Tests for the locked uv Graphify resolver and clean environment.

`clean_env` is what every graphify subprocess runs under, and it strips for two
unrelated reasons — backend triggers by name, mise's secret-bearing `__MISE_*`
blob by prefix.

Every check is armed in both directions: a resolver that can only return the
mise answer would hide a mise-less machine, one that can only fall back would
silently reintroduce the PATH dependency this exists to remove, and an
"is it absent from clean_env?" assertion passes trivially on any host where mise
never set the variable — so each strip arm SETS the variable first.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from kb_setup import graphify_env


def test_graphify_exe_is_owned_by_the_project_venv() -> None:
    root = Path("/repo")
    assert graphify_env.graphify_exe(root) == "/repo/.venv/bin/graphify"


# --- clean_env: two independent strips ---------------------------------------
#
# Every arm below sets the variable in the fixture environment and asserts it is
# PRESENT in os.environ before asserting it is absent from clean_env(). Without
# that first half the test passes on a host where mise never ran — a check that
# can only pass (`probes-need-a-control-arm.md`).


def test_the_mise_secret_blob_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE point of the second strip: `__MISE_DIFF` must not reach a subprocess.

    It carries the *values* of the credentials `_STRIP_BACKEND_ENV` removes by
    *name*, gzip+base64'd past any secret scanner. Asserted on presence/absence of
    the KEY only — never decode the blob to inspect it; doing that is what put
    live credentials into a session transcript.
    """
    monkeypatch.setenv("__MISE_DIFF", "sentinel-not-a-real-blob")
    monkeypatch.setenv("__MISE_SESSION", "sentinel-session")
    assert "__MISE_DIFF" in os.environ  # arm: the fixture really set it
    assert "__MISE_SESSION" in os.environ

    env = graphify_env.clean_env()

    assert "__MISE_DIFF" not in env
    assert "__MISE_SESSION" not in env


def test_the_strip_is_a_prefix_not_a_spelling(monkeypatch: pytest.MonkeyPatch) -> None:
    """A name list would cover today's two blobs and fail open on a third.

    This arm is the difference between the rule as written and the rule the
    handoff proposed: an unknown future `__MISE_*` must be stripped too, without
    anyone editing this module.
    """
    monkeypatch.setenv("__MISE_FUTURE_BLOB", "sentinel-unknown-to-us")
    assert "__MISE_FUTURE_BLOB" in os.environ

    assert "__MISE_FUTURE_BLOB" not in graphify_env.clean_env()


def test_public_mise_config_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: the prefix must be `__MISE_`, not `MISE_`.

    A strip that also ate single-underscore `MISE_*` would pass every arm above
    and break real configuration — `kb_setup.currency.sync` reads `MISE_DATA_DIR`.
    Proves the rule discriminates rather than deleting anything mise-shaped.
    """
    monkeypatch.setenv("MISE_DATA_DIR", "sentinel-data-dir")
    monkeypatch.setenv("MISE_ENV_CACHE", "1")

    env = graphify_env.clean_env()

    assert env["MISE_DATA_DIR"] == "sentinel-data-dir"
    assert env["MISE_ENV_CACHE"] == "1"


def test_backend_triggers_are_still_stripped_and_claude_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTROL ARM for the FIRST strip, which the new prefix must not disturb.

    `ANTHROPIC_API_KEY` surviving is the other half: a clean_env that dropped
    everything would pass "the secret is gone" while silently killing the one
    backend this repo is allowed to use (`do-not.md` #4).
    """
    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-forbidden")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sentinel-forbidden")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sentinel-kept")
    assert "GEMINI_API_KEY" in os.environ

    env = graphify_env.clean_env()

    assert "GEMINI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["ANTHROPIC_API_KEY"] == "sentinel-kept"


def test_extra_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: `extra` is applied AFTER the strips, so callers can override."""
    monkeypatch.setenv("__MISE_DIFF", "sentinel-not-a-real-blob")

    env = graphify_env.clean_env({"GRAPHIFY_TEST": "on", "__MISE_DIFF": "explicit"})

    assert env["GRAPHIFY_TEST"] == "on"
    assert env["__MISE_DIFF"] == "explicit"


# --- the writer version gate (#186 cold lane, P1) -----------------------------
#
# The hyperedge carry is retired, so a stale pre-0.9.34 binary rewriting
# graph.json silently destroys hyperedges with nothing left to restore them —
# and graphify_exe's PATH fallback can hand exactly that binary back (live on
# the host this was found on: bare `graphify` was 0.9.32 under a 0.9.34 pin).


def _pyproject(tmp_path: Path, requirement: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "probe"\nversion = "0"\ndependencies = ["{requirement}"]\n',
        encoding="utf-8",
    )
    return tmp_path


def test_pinned_version_reads_exact_project_requirement(tmp_path: Path) -> None:
    root = _pyproject(tmp_path, "graphifyy[all]==0.9.41")
    assert graphify_env.pinned_graphify_version(root) == "0.9.41"


def test_non_exact_project_requirement_is_not_a_pin(tmp_path: Path) -> None:
    root = _pyproject(tmp_path, "graphifyy[all]>=0.9.41")
    assert graphify_env.pinned_graphify_version(root) == ""


def test_pinned_version_absent_pin_is_empty(tmp_path: Path) -> None:
    root = _pyproject(tmp_path, "msgspec==0.21.1")
    assert graphify_env.pinned_graphify_version(root) == ""


def test_pinned_version_unreadable_toml_is_empty_not_an_error(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\nbroken", encoding="utf-8")
    assert graphify_env.pinned_graphify_version(tmp_path) == ""


def test_running_version_parses_a_real_subprocess(tmp_path: Path) -> None:
    """Armed with a REAL exec, not a mock: the parse and the invocation together."""
    import sys as _sys

    exe = tmp_path / "fake-graphify"
    exe.write_text(f"#!{_sys.executable}\nprint('graphify 1.2.3')\n", encoding="utf-8")
    exe.chmod(0o755)

    assert graphify_env.running_graphify_version(str(exe)) == "1.2.3"


def test_running_version_unaskable_exe_is_empty(tmp_path: Path) -> None:
    assert graphify_env.running_graphify_version(str(tmp_path / "absent")) == ""


def test_gate_refuses_a_version_mismatch_naming_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphify_env, "graphify_exe", lambda _r: "/stale/graphify")
    monkeypatch.setattr(graphify_env, "pinned_graphify_version", lambda _r: "0.9.34")
    monkeypatch.setattr(graphify_env, "running_graphify_version", lambda _e: "0.9.32")

    with pytest.raises(SystemExit) as exc:
        graphify_env.assert_pinned_graphify(tmp_path)

    message = str(exc.value)
    assert "0.9.32" in message
    assert "0.9.34" in message
    assert "mise deps" in message


def test_gate_passes_silently_on_a_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(graphify_env, "graphify_exe", lambda _r: "/pinned/graphify")
    monkeypatch.setattr(graphify_env, "pinned_graphify_version", lambda _r: "0.9.34")
    monkeypatch.setattr(graphify_env, "running_graphify_version", lambda _e: "0.9.34")
    from kb_setup import graphify_sdk

    monkeypatch.setattr(graphify_sdk, "assert_public_sdk", lambda _version: None)

    assert graphify_env.assert_pinned_graphify(tmp_path) is None
    assert capsys.readouterr().err == ""


def test_gate_refuses_when_it_cannot_compare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphify_env, "graphify_exe", lambda _r: "/mystery/graphify")
    monkeypatch.setattr(graphify_env, "pinned_graphify_version", lambda _r: "0.9.34")
    monkeypatch.setattr(graphify_env, "running_graphify_version", lambda _e: "")

    with pytest.raises(SystemExit, match="REFUSING an unverified"):
        graphify_env.assert_pinned_graphify(tmp_path)


def test_gate_refuses_public_sdk_signature_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphify_env, "graphify_exe", lambda _r: "/pinned/graphify")
    monkeypatch.setattr(graphify_env, "pinned_graphify_version", lambda _r: "0.9.41")
    monkeypatch.setattr(graphify_env, "running_graphify_version", lambda _e: "0.9.41")
    from kb_setup import graphify_sdk

    def drift(_version: str) -> None:
        raise RuntimeError("signature changed")

    monkeypatch.setattr(graphify_sdk, "assert_public_sdk", drift)
    with pytest.raises(RuntimeError, match="signature changed"):
        graphify_env.assert_pinned_graphify(tmp_path)


def _fake_claude_dir(tmp_path: Path, name: str) -> Path:
    """A directory holding an EXECUTABLE `claude`, as `shutil.which` requires.

    The executable bit is the whole point: `_path_without_claude_cli` delegates to
    `shutil.which`, which checks `os.access(..., os.X_OK)`. A non-executable file
    named `claude` would NOT be found, so a fixture that forgot `chmod` would make
    the strip look like it worked while testing nothing.
    """
    directory = tmp_path / name
    directory.mkdir()
    binary = directory / "claude"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    return directory


def test_hide_claude_cli_removes_the_directory_that_can_launch_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Graphify >= 0.9.58 picks claude-cli whenever the CLI is merely INSTALLED.

    `llm.py:3513` — `if not backend and _claude_cli_available(): backend =
    "claude-cli"`, where availability is `shutil.which("claude")`. `kb-label` runs
    `graphify label .` with no `--backend`, so without this strip a task advertised
    as "deterministic, no-LLM" acquires an LLM call and spends tokens.
    """
    has_claude = _fake_claude_dir(tmp_path, "with-claude")
    no_claude = tmp_path / "without-claude"
    no_claude.mkdir()
    monkeypatch.setenv("PATH", os.pathsep.join([str(has_claude), str(no_claude)]))

    env = graphify_env.clean_env(hide_claude_cli=True)

    entries = env["PATH"].split(os.pathsep)
    assert str(has_claude) not in entries
    # The strip must be SURGICAL. Dropping PATH wholesale would also pass the
    # assertion above while breaking every other tool the subprocess resolves.
    assert str(no_claude) in entries


def test_clean_env_keeps_claude_on_path_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM, and it guards a REAL dependency, not just symmetry.

    `clean_env()` is used by EVERY graphify subprocess, and `claude-cli` is one of
    the two sanctioned extraction backends (`do-not.md` #4). If the strip were
    always-on it would break extraction — so the default MUST keep the directory,
    and this arm is what would catch someone "simplifying" the flag away.
    """
    has_claude = _fake_claude_dir(tmp_path, "with-claude")
    monkeypatch.setenv("PATH", str(has_claude))

    assert str(has_claude) in graphify_env.clean_env()["PATH"].split(os.pathsep)


def test_hide_claude_cli_is_a_no_op_when_the_cli_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A host without the CLI keeps every PATH entry — the strip is not a blanket.

    Without this, a `_path_without_claude_cli` that returned "" for everything
    would still pass the two arms above.
    """
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("PATH", str(plain))

    assert graphify_env.clean_env(hide_claude_cli=True)["PATH"] == str(plain)
