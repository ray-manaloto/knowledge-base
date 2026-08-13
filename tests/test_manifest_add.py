# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.manifest — name derivation + the add() write-guard.

Network-free: name_from_url is pure, and add()'s exists-guard fires BEFORE the
`git ls-remote` in latest_commit, so the refuse-to-clobber path needs no network.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
from kb_setup import cli, manifest

_GIT_TIMEOUT = 30


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
    )
    return proc.stdout.strip()


def _upstream_with_reviewed_ancestor(tmp_path: Path) -> tuple[Path, str, str]:
    upstream = tmp_path / "upstream"
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(upstream)],
        check=True,
        timeout=_GIT_TIMEOUT,
    )
    _git(upstream, "config", "user.email", "t@example.com")
    _git(upstream, "config", "user.name", "T")
    _git(upstream, "config", "commit.gpgsign", "false")
    source = upstream / "source.txt"
    source.write_text("reviewed\n", encoding="utf-8")
    _git(upstream, "add", "--", "source.txt")
    _git(upstream, "commit", "-q", "-m", "reviewed")
    reviewed = _git(upstream, "rev-parse", "HEAD")
    source.write_text("unreviewed head\n", encoding="utf-8")
    _git(upstream, "commit", "-q", "-am", "unreviewed")
    return upstream, reviewed, _git(upstream, "rev-parse", "HEAD")


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


def test_add_emits_corpus_scope_by_default(tmp_path, monkeypatch) -> None:
    commit = "a" * 40
    monkeypatch.setattr(manifest, "latest_commit", lambda _manifest: commit)

    added = manifest.add(
        tmp_path / "sources",
        manifest.NewSource("https://github.com/openai/symphony"),
    )

    assert added.scope == "corpus"
    assert "scope = corpus\n" in added.path.read_text(encoding="utf-8")


def test_add_emits_study_scope_when_requested(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(manifest, "latest_commit", lambda _manifest: "b" * 40)

    added = manifest.add(
        tmp_path / "sources",
        manifest.NewSource("https://github.com/example/peer", scope="study"),
    )

    assert added.scope == "study"
    assert "scope = study\n" in added.path.read_text(encoding="utf-8")


def test_add_rejects_quarantine_scope_before_network_or_write(tmp_path, monkeypatch) -> None:
    def unexpected_network(_manifest: manifest.Manifest) -> str:
        pytest.fail("invalid scope reached the network")

    monkeypatch.setattr(manifest, "latest_commit", unexpected_network)
    sources = tmp_path / "sources"

    with pytest.raises(ValueError, match=r"scope.*corpus.*study"):
        manifest.add(
            sources,
            manifest.NewSource("https://github.com/example/peer", scope="quarantine"),
        )

    assert not sources.exists()


@pytest.mark.parametrize("commit", ["a" * 39, "a" * 41, "g" * 40, "", "a" * 20 + "Z" * 20])
def test_add_rejects_malformed_explicit_commit_before_network_or_write(
    tmp_path, monkeypatch, commit: str
) -> None:
    def unexpected_network(_manifest: manifest.Manifest) -> str:
        pytest.fail("malformed commit reached the network")

    monkeypatch.setattr(manifest, "latest_commit", unexpected_network)
    sources = tmp_path / "sources"

    with pytest.raises(ValueError, match="40 hexadecimal"):
        manifest.add(
            sources,
            manifest.NewSource("https://github.com/example/peer", commit=commit),
        )

    assert not sources.exists()


def test_add_pins_requested_reachable_commit_without_advancing_to_head(tmp_path) -> None:
    upstream, reviewed, current_head = _upstream_with_reviewed_ancestor(tmp_path)
    requested = reviewed.upper()

    added = manifest.add(
        tmp_path / "sources",
        manifest.NewSource(str(upstream), commit=requested),
    )

    body = added.path.read_text(encoding="utf-8")
    assert added.commit == requested
    assert f"commit = {requested}\n" in body
    assert current_head not in body
    assert list((tmp_path / "sources").iterdir()) == [added.path]


def test_add_rejects_well_formed_but_unfetchable_commit(tmp_path) -> None:
    upstream, _reviewed, _current_head = _upstream_with_reviewed_ancestor(tmp_path)
    sources = tmp_path / "sources"

    with pytest.raises(RuntimeError, match="not reachable"):
        manifest.add(
            sources,
            manifest.NewSource(str(upstream), commit="f" * 40),
        )

    assert not sources.exists()


def test_add_rejects_commit_that_exists_only_on_another_ref(tmp_path) -> None:
    upstream, reviewed, _current_head = _upstream_with_reviewed_ancestor(tmp_path)
    _git(upstream, "checkout", "-q", "-b", "other", reviewed)
    (upstream / "source.txt").write_text("other branch\n", encoding="utf-8")
    _git(upstream, "commit", "-q", "-am", "other branch")
    other_commit = _git(upstream, "rev-parse", "HEAD")
    _git(upstream, "checkout", "-q", "main")
    sources = tmp_path / "sources"

    with pytest.raises(RuntimeError, match="not reachable from ref 'main'"):
        manifest.add(
            sources,
            manifest.NewSource(str(upstream), ref="main", commit=other_commit),
        )

    assert not sources.exists()


def test_cli_forwards_scope_and_exact_commit(tmp_path, monkeypatch) -> None:
    requested = "A" * 40
    seen: list[tuple[Path, manifest.NewSource, bool]] = []

    def fake_add(
        sources_dir: Path, source: manifest.NewSource, *, force: bool = False
    ) -> manifest.Manifest:
        seen.append((sources_dir, source, force))
        return manifest.Manifest(
            name=source.stem,
            path=sources_dir / f"{source.stem}.manifest",
            url=source.url,
            ref=source.ref,
            commit=source.commit or "",
            kind=source.kind,
            scope=source.scope,
        )

    monkeypatch.setattr(manifest, "add", fake_add)
    monkeypatch.chdir(tmp_path)

    assert (
        cli.main(
            [
                "manifest-add",
                "https://github.com/example/peer",
                "--scope",
                "study",
                "--commit",
                requested,
                "--force",
            ]
        )
        == 0
    )
    assert seen == [
        (
            tmp_path / "sources",
            manifest.NewSource(
                "https://github.com/example/peer",
                scope="study",
                commit=requested,
            ),
            True,
        )
    ]


@pytest.mark.parametrize("scope", ["quarantine", ""])
def test_cli_rejects_invalid_scope_without_network_or_write(
    tmp_path, monkeypatch, capsys, scope: str
) -> None:
    def unexpected_network(_manifest: manifest.Manifest) -> str:
        pytest.fail("invalid CLI scope reached the network")

    monkeypatch.setattr(manifest, "latest_commit", unexpected_network)
    monkeypatch.chdir(tmp_path)

    assert (
        cli.main(
            [
                "manifest-add",
                "https://github.com/example/peer",
                "--scope",
                scope,
            ]
        )
        == 1
    )
    assert "scope must be one of: corpus, study" in capsys.readouterr().err
    assert not (tmp_path / "sources").exists()


@pytest.mark.parametrize("flag", ["--scope", "--commit"])
def test_cli_rejects_bare_value_flag_without_defaulting_to_head(
    tmp_path, monkeypatch, capsys, flag: str
) -> None:
    def unexpected_network(_manifest: manifest.Manifest) -> str:
        pytest.fail(f"bare {flag} reached the network")

    monkeypatch.setattr(manifest, "latest_commit", unexpected_network)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["manifest-add", "https://github.com/example/peer", flag]) == 2
    assert f"{flag} requires a value" in capsys.readouterr().err
    assert not (tmp_path / "sources").exists()


def test_mise_manifest_add_help_declares_scope_and_commit_contract() -> None:
    repo_root = Path(__file__).parents[1]
    proc = subprocess.run(
        ["mise", "run", "kb-manifest-add", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT,
    )

    assert proc.returncode == 0, proc.stderr
    assert "--scope <scope>" in proc.stdout
    assert "corpus" in proc.stdout
    assert "study" in proc.stdout
    assert "--commit <commit>" in proc.stdout


def test_mise_manifest_add_rejects_quarantine_before_running_cli() -> None:
    repo_root = Path(__file__).parents[1]
    proc = subprocess.run(
        [
            "mise",
            "run",
            "kb-manifest-add",
            "--",
            "https://example.invalid/peer",
            "--scope",
            "quarantine",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT,
    )

    assert proc.returncode != 0
    assert "Invalid choice for option scope: quarantine" in proc.stderr


def test_mise_manifest_add_dry_run_forwards_all_typed_arguments() -> None:
    repo_root = Path(__file__).parents[1]
    requested = "A" * 40
    proc = subprocess.run(
        [
            "mise",
            "run",
            "--dry-run",
            "kb-manifest-add",
            "--",
            "https://github.com/example/peer",
            "--scope",
            "study",
            "--commit",
            requested,
            "--name",
            "peer-study",
            "--comment",
            "reviewed source",
            "--force",
        ],
        cwd=repo_root,
        env={**os.environ, "MISE_TASK_SHOW_FULL_CMD": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT,
    )

    assert proc.returncode == 0, proc.stderr
    rendered = proc.stdout + proc.stderr
    assert "--scope 'study'" in rendered
    assert f"--commit '{requested}'" in rendered
    assert "--name 'peer-study'" in rendered
    assert "--comment 'reviewed source'" in rendered
    assert rendered.rstrip().endswith("--force")


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
        ref = argv[-1]
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
