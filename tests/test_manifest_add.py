# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.manifest — name derivation + the add() write-guard.

Network-free: name_from_url is pure, and add()'s exists-guard fires BEFORE the
`git ls-remote` in latest_commit, so the refuse-to-clobber path needs no network.
"""

import re

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


def test_resolve_tag_returns_the_peeled_commit_for_an_annotated_tag(monkeypatch) -> None:
    """A manifest pins executable source bytes, not the annotated tag object."""
    import subprocess

    def _ok(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [],
            0,
            stdout=("tagobject\trefs/tags/v1.2.3\ncommitsha\trefs/tags/v1.2.3^{}\n"),
            stderr="",
        )

    monkeypatch.setattr(manifest.subprocess, "run", _ok)
    assert manifest.resolve_tag("https://example/x", "1.2.3") == ("v1.2.3", "commitsha")


# --- #245: a project whose tags carry a prefix -------------------------------


def _remote(monkeypatch, *tags: str) -> list[str]:
    """A fake `git ls-remote` holding exactly `tags`. Returns the refs ASKED for.

    A remote that answers only for the tags it really has, rather than a stub
    that answers everything: the defect being fixed is that the prefixed
    candidate was never GENERATED, and a stub returning a SHA for any input
    passes with or without the fix.
    """
    import subprocess

    asked: list[str] = []

    def _ls_remote(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        ref = argv[-1].removesuffix("*")
        asked.append(ref)
        out = f"cafe1234\trefs/tags/{ref}\n" if ref in tags else ""
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    monkeypatch.setattr(manifest.subprocess, "run", _ls_remote)
    return asked


def test_resolve_tag_finds_a_prefixed_tag_when_given_the_prefix(monkeypatch) -> None:
    """Codex tags `rust-v0.147.0` — neither `v<version>` nor the bare form.

    Without `prefix=`, an authorized auto-apply for codex raised "no tag found"
    and aborted the entire bump, while `currency.toml` carried a comment saying
    the prefix had been wired in (it had — into the SYNC half only, #245).
    """
    asked = _remote(monkeypatch, "rust-v0.147.0")
    ref, commit = manifest.resolve_tag("https://example/x", "0.147.0", prefix="rust-v")
    assert (ref, commit) == ("rust-v0.147.0", "cafe1234")
    assert asked[0] == "rust-v0.147.0", "the prefix must be tried FIRST, not as a fallback"


def test_without_the_prefix_the_same_remote_resolves_nothing(monkeypatch) -> None:
    """CONTROL ARM: the prefix is what finds it, not the fake remote being lenient."""
    asked = _remote(monkeypatch, "rust-v0.147.0")
    with pytest.raises(RuntimeError, match="no tag found"):
        manifest.resolve_tag("https://example/x", "0.147.0")
    assert asked == ["v0.147.0", "0.147.0"]


def test_a_prefixed_miss_names_every_candidate_it_tried(monkeypatch) -> None:
    """A failure message that misdescribes its own probe misdirects the reader.

    The old wording hard-coded `<version>` and `v<version>`, so a prefixed miss
    reported that `rust-v` was never attempted when it had been — sending the
    reader to add config that is already present.
    """
    _remote(monkeypatch)
    with pytest.raises(RuntimeError, match=re.escape("rust-v0.147.0")):
        manifest.resolve_tag("https://example/x", "0.147.0", prefix="rust-v")


def test_the_v_and_bare_forms_survive_as_fallbacks(monkeypatch) -> None:
    """A stale or wrong `tag_prefix` must DEGRADE, never turn a hit into a miss."""
    asked = _remote(monkeypatch, "v0.9.26")
    assert manifest.resolve_tag("https://example/x", "0.9.26", prefix="wrong-") == (
        "v0.9.26",
        "cafe1234",
    )
    assert asked == ["wrong-0.9.26", "v0.9.26"]


def test_a_v_prefix_is_not_asked_for_twice(monkeypatch) -> None:
    """`tag_prefix = "v"` collides with the built-in candidate.

    Asking twice spends a second network round trip on a question already
    answered, and prints a "tried" list naming one ref twice — which reads as a
    bug in the caller.
    """
    asked = _remote(monkeypatch, "v0.9.26")
    assert manifest.resolve_tag("https://example/x", "0.9.26", prefix="v")[0] == "v0.9.26"
    assert asked == ["v0.9.26"]
