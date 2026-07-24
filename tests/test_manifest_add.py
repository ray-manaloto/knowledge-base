"""kb_setup.manifest — name derivation + the add() write-guard.

Network-free: name_from_url is pure, and add()'s exists-guard fires BEFORE the
`git ls-remote` in latest_commit, so the refuse-to-clobber path needs no network.
"""

import pytest
from kb_setup import manifest


def test_name_from_url_strips_git_and_trailing_slash() -> None:
    assert manifest.name_from_url("https://github.com/openai/symphony") == "symphony"
    assert manifest.name_from_url("https://github.com/openai/symphony.git") == "symphony"
    assert manifest.name_from_url("https://github.com/openai/symphony/") == "symphony"


def test_add_refuses_to_clobber_existing_manifest(tmp_path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    existing = sources / "symphony.manifest"
    existing.write_text("url = x\nref = main\ncommit = deadbeef\n")
    # exists-guard raises before any network call
    with pytest.raises(FileExistsError):
        manifest.add(sources, manifest.NewSource("https://github.com/openai/symphony"))
    assert "deadbeef" in existing.read_text()


def test_resolve_tag_wraps_subprocess_failures_as_runtime_error(monkeypatch) -> None:
    """An unreachable host must surface as RuntimeError, not a raw traceback.

    `apply()` catches RuntimeError; a bare `CalledProcessError`/`TimeoutExpired`
    would bypass that and escape as an uncaught traceback instead of the clean
    "[currency] apply failed" message.
    """
    import subprocess
    from typing import Never

    def _boom(*_a: object, **_k: object) -> Never:
        raise subprocess.CalledProcessError(128, "git ls-remote")

    monkeypatch.setattr(manifest.subprocess, "run", _boom)
    with pytest.raises(RuntimeError, match="git ls-remote failed"):
        manifest.resolve_tag("https://example/x", "0.9.26")


def test_resolve_tag_returns_ref_and_commit_on_success(monkeypatch) -> None:
    """Control arm: a real ls-remote answer yields (ref, sha)."""
    import subprocess

    def _ok(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout="cafe1234\trefs/tags/v0.9.26\n", stderr="")

    monkeypatch.setattr(manifest.subprocess, "run", _ok)
    assert manifest.resolve_tag("https://example/x", "0.9.26") == ("v0.9.26", "cafe1234")
