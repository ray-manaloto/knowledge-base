# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.manifest — name derivation + the add() write-guard.

Network-free: name_from_url is pure, and add()'s exists-guard fires BEFORE the
`git ls-remote` in latest_commit, so the refuse-to-clobber path needs no network.
"""

import re
from pathlib import Path

import pytest
from kb_setup import manifest

# `_repo`/`_clone_at`/`_git` build a REAL local git repo with a genuine
# annotated tag — exactly what #500's regression needs and no `resolve_tag`
# test above has ever seen (every one monkeypatches `subprocess.run`). They
# already exist for this in `test_currency_sync.py`; reusing them is
# `use-tool-builtins.md` applied to test fixtures, not a stretch of it — a
# from-scratch rebuild here would be the exact mistake that rule exists to
# prevent, and pytest's per-file import (no `tests/__init__.py`) makes the
# cross-module import work with no extra plumbing.
from test_currency_sync import _clone_at, _git, _repo


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


# --- #245: a project whose tags carry a prefix -------------------------------


def _remote(monkeypatch, *tags: str) -> list[str]:
    """A fake `git ls-remote` holding exactly `tags`. Returns the refs ASKED for.

    A remote that answers only for the tags it really has, rather than a stub
    that answers everything: the defect being fixed is that the prefixed
    candidate was never GENERATED, and a stub returning a SHA for any input
    passes with or without the fix.

    argv now ends `[..., ref, f"{ref}^{{}}"]` (#500: `_resolve_ref` asks for the
    dereference too), so the REF is the second-to-last element, not the last —
    a fake keyed on `argv[-1]` would key on the peel PATTERN instead and never
    match a real tag name again.
    """
    import subprocess

    asked: list[str] = []

    def _ls_remote(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        ref = argv[-2]
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

    Left AS-IS, deliberately (#500 spec §5): `_remote(monkeypatch)` with no
    tags answers "" for every candidate, so this test's green does not depend
    on `_resolve_ref`'s peeling shape being correct — it is testing the miss
    MESSAGE, not the resolution. Do not read its green as evidence for #500.
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


# --- #500: resolve_tag and latest_commit share one peeling code path --------
#
# Every test above fakes the remote, so none of them has ever seen a genuine
# annotated tag — the fake always answers with a SINGLE `refs/tags/<ref>` line,
# which is exactly the LIGHTWEIGHT shape. These tests drive a REAL local git
# repo instead (via `_repo`/`_clone_at`/`_git`, reused from
# `test_currency_sync.py`), because a stub can only confirm the stub.


def _local_manifest(url: str, ref: str) -> manifest.Manifest:
    """A `Manifest` good enough for `latest_commit` — it reads only `url`/`ref`."""
    return manifest.Manifest(
        name="fixture", path=Path("/dev/null"), url=url, ref=ref, commit="0" * 40
    )


def test_resolve_tag_returns_the_peeled_commit_for_an_annotated_tag(tmp_path) -> None:
    """The regression #500 exists to fix, against a real remote.

    Before this fix `resolve_tag` returned the TAG OBJECT here, not the
    commit — the identity `write_pin` recorded and `_ensure_clone` never
    actually checks out.
    """
    root = _repo(tmp_path)
    peeled = _clone_at(root, "v0.9.25", annotated=True)
    tag_object = _git(root, "rev-parse", "v0.9.25")
    url = str(root / "sources" / "graphify")

    ref, commit = manifest.resolve_tag(url, "0.9.25")

    assert ref == "v0.9.25"
    assert commit == peeled
    assert commit != tag_object, (
        "an assertion that only checks A sha came back would pass against the bug"
    )


def test_resolve_tag_control_arm_a_lightweight_tag_has_one_identity(tmp_path) -> None:
    """CONTROL ARM: without this, the annotated test above cannot be shown to discriminate."""
    root = _repo(tmp_path)
    sha = _clone_at(root, "v0.9.25", annotated=False)
    url = str(root / "sources" / "graphify")

    ref, commit = manifest.resolve_tag(url, "0.9.25")

    assert (ref, commit) == ("v0.9.25", sha)
    assert commit == _git(root, "rev-parse", "v0.9.25"), "lightweight: one sha, both resolvers"


def test_latest_commit_control_arm_a_branch_ref_is_unchanged(tmp_path) -> None:
    """A plain branch through the SAME shared helper — unchanged from today.

    The fixture also carries an annotated tag at the same commit, so this
    proves the branch match is not merely the ONLY thing present to match.
    """
    root = _repo(tmp_path)
    sha = _clone_at(root, "v0.9.25", annotated=True)
    branch = _git(root, "symbolic-ref", "--short", "HEAD")
    m = _local_manifest(str(root / "sources" / "graphify"), branch)

    assert manifest.latest_commit(m) == sha


def test_resolve_tag_and_latest_commit_agree_on_an_annotated_ref(tmp_path) -> None:
    """THE INVARIANT #500 exists to establish: one identity, one shared path.

    `resolve_tag` resolves the tag NAME; `latest_commit` resolves the same
    string as a manifest's `ref`. Both must land on the peeled commit.
    """
    root = _repo(tmp_path)
    peeled = _clone_at(root, "v0.9.25", annotated=True)
    url = str(root / "sources" / "graphify")
    m = _local_manifest(url, "v0.9.25")

    _, tag_commit = manifest.resolve_tag(url, "0.9.25")
    manifest_commit = manifest.latest_commit(m)

    assert tag_commit == manifest_commit == peeled


def test_resolve_tag_does_not_over_match_a_sibling_tag(tmp_path) -> None:
    """Pins §3's rejected-glob case as a test: a real sibling tag, DIFFERENT commit.

    A glob candidate (`ref + "*"`) — or any "scan for the last `^{}` line" —
    would also match `v1.0.0-alpha.1` and could return ITS commit for a
    `v1.0.0` resolve. That is exactly the corruption measured against
    `codex`'s real `rust-v0.149.0` siblings (§3's rejected-shapes table). Two
    DISTINCT commits make the assertion meaningful; a fixture with one commit
    under two tags could "pass" while resolving the wrong tag entirely.
    """
    root = _repo(tmp_path)
    alpha_sha = _clone_at(root, "v1.0.0-alpha.1", annotated=True)
    clone = root / "sources" / "graphify"
    (clone / "f2.txt").write_text("y\n", encoding="utf-8")
    _git(root, "add", "--", "f2.txt")
    _git(root, "commit", "-q", "-m", "c2")
    _git(root, "tag", "-a", "-m", "release v1.0.0", "v1.0.0")
    release_sha = _git(root, "rev-parse", "HEAD")
    assert release_sha != alpha_sha, "control: the two tags must name different commits"

    ref, commit = manifest.resolve_tag(str(clone), "1.0.0")

    assert (ref, commit) == ("v1.0.0", release_sha)


def test_resolve_tag_refuses_a_tail_matched_tag_it_did_not_ask_for(tmp_path) -> None:
    """#503: a live latent bug, independent of #500, fixed as a side effect.

    `git ls-remote` patterns are TAIL matches on `/` boundaries: a repo holding
    `sub/v1.0.0` and NO `v1.0.0` answers a `v1.0.0` pattern with
    `refs/tags/sub/v1.0.0` anyway. The old `if out: return ref, out.split()[0]`
    took that line and silently pinned a manifest to a tag it never named.
    §3's exact-refname rule (`refs/tags/<ref>` — not merely non-empty output)
    fixes this for free: a non-exact match is a MISS, and every candidate
    missing must raise, never guess. `_clone_at` tags at exactly the `ref` it
    is given, and a tag name may contain `/`, so it builds this fixture too.
    """
    root = tmp_path
    _clone_at(root, "sub/v1.0.0", annotated=True)
    url = str(root / "sources" / "graphify")

    with pytest.raises(RuntimeError, match="no tag found"):
        manifest.resolve_tag(url, "1.0.0")
