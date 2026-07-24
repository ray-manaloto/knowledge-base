"""kb_setup.currency.broad — the `mise outdated` sweep for non-deep-tracked tools.

This is a SIGNAL renderer, not a decision surface, so the tests that matter are:
the deep-tracked tools are excluded (no tool appears twice), and a probe failure
reads as a failure and not as "all clear".
"""

from __future__ import annotations

from pathlib import Path

from kb_setup.currency import broad


def test_deep_tracked_tools_are_excluded_from_the_broad_table() -> None:
    """A tool the deep engine owns must not also appear as a bare broad row.

    Otherwise one tool reads as two unrelated findings — the deep verdict AND a
    context-free "outdated" row.
    """
    outdated = {
        "pipx:graphifyy": {"current": "0.9.25", "latest": "0.9.26"},
        "hk": {"current": "1.52.0", "latest": "1.53.0"},
        "docker-cli": {"current": "29.6.2", "latest": "29.7.0"},
    }
    table = broad.render_broad(outdated, exclude={"pipx:graphifyy", "hk"})
    assert "graphifyy" not in table
    assert "hk " not in table
    assert "docker-cli" in table


def test_nothing_outside_the_deep_set_reads_as_a_clean_note() -> None:
    """Control arm: an empty broad set is a friendly note, not an empty table."""
    outdated = {"hk": {"current": "1.52.0", "latest": "1.53.0"}}
    assert broad.render_broad(outdated, exclude={"hk"}) == (
        "_No other pinned tool has upstream movement._"
    )


def test_release_links_route_by_backend() -> None:
    assert broad.release_link("npm:renovate").startswith("https://www.npmjs.com/")
    assert broad.release_link("pipx:graphifyy").startswith("https://pypi.org/project/graphifyy/")
    assert broad.release_link("github:jdx/mise") == "https://github.com/jdx/mise/releases"
    assert broad.release_link("cargo:rtk").startswith("https://crates.io/crates/rtk/")
    # An unknown/short key falls back to the registry page, never a broken URL.
    assert broad.release_link("hk") == broad._REGISTRY_URL


def test_pipx_extras_are_stripped_from_the_pypi_link() -> None:
    """`graphifyy[all]` must link to the `graphifyy` project, not a 404."""
    assert (
        broad.release_link("pipx:graphifyy[all]") == "https://pypi.org/project/graphifyy/#history"
    )


def test_a_failed_sweep_says_so_rather_than_all_clear(monkeypatch) -> None:
    """A broken `mise outdated` must not render as 'nothing moved'.

    That is the absence-of-evidence trap: an empty table from a failed probe is
    indistinguishable from an empty table because everything is current.
    """
    monkeypatch.setattr(broad, "mise_outdated", lambda _r: ({}, "mise blew up"))
    section = broad.broad_section(Path("/x"), exclude=set())
    assert "Could not run the broad sweep" in section
    assert "mise blew up" in section


def test_a_clean_sweep_renders_the_note(monkeypatch) -> None:
    """Control arm: a successful empty sweep is the clean note, not an error."""
    monkeypatch.setattr(broad, "mise_outdated", lambda _r: ({}, ""))
    section = broad.broad_section(Path("/x"), exclude=set())
    assert "No other pinned tool" in section
    assert "Could not run" not in section


def test_mise_outdated_bad_json_is_an_error_not_a_crash(monkeypatch) -> None:
    import subprocess

    from kb_setup.currency import _proc

    def _fake_run(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout="not json", stderr="")

    # The subprocess now runs inside the shared `_proc` helper, so patch it there.
    monkeypatch.setattr(_proc.subprocess, "run", _fake_run)
    data, err = broad.mise_outdated(Path("/x"))
    assert data == {}
    assert "non-JSON" in err
