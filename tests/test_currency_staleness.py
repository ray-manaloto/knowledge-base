"""kb_setup.currency.staleness — does the graph still match its committed inputs?

Every test here runs BOTH arms, because the failure this detector exists to
prevent is a check that can only pass. The negative arm is not decoration: the
whole reason `size:mtime_ns` was rejected for inputs is that it fires on
content-preserving git operations, so a suite proving only that "a real edit is
detected" would have certified the rejected scheme just as happily.

The three git operations are run against a REAL repository rather than simulated
by touching mtimes. Simulating them would test this suite's model of git, which
is precisely the thing #89 found people had got wrong.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from kb_setup.currency import config, staleness, sync

_GIT_TIMEOUT = 30

_CURRENCY = """\
[tool.graphify]
mise_key = "pipx:graphifyy"
binary = "graphify"
artifact = "graphify-out/graph.json"
inputs = [
  "sources/*.manifest",
  "sources/extractions/*.json",
]
stamp = "graphify-out/.currency-stamp.json"
"""


def _spec(root: Path) -> config.ToolSpec:
    return config.load(root)[0]


def _repo(tmp_path: Path) -> Path:
    """A repo with the two input globs populated and a graph artifact present."""
    (tmp_path / "currency.toml").write_text(_CURRENCY, encoding="utf-8")
    (tmp_path / "mise.toml").write_text('[tools]\n"pipx:graphifyy" = "0.9.30"\n', encoding="utf-8")
    sources = tmp_path / "sources"
    (sources / "extractions").mkdir(parents=True, exist_ok=True)
    (sources / "alpha.manifest").write_text(
        "url = https://example/alpha\nref = main\ncommit = aaa111\n", encoding="utf-8"
    )
    (sources / "beta.manifest").write_text(
        "url = https://example/beta\nref = main\ncommit = bbb222\n", encoding="utf-8"
    )
    (sources / "extractions" / "alpha-docs.json").write_text(
        '{"nodes": [{"id": "n1"}], "edges": []}\n', encoding="utf-8"
    )
    artifact = tmp_path / "graphify-out" / "graph.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"nodes": []}', encoding="utf-8")
    return tmp_path


def _stamp(root: Path) -> Path:
    """Stamp the repo the way a real build does: inputs digested and passed in."""
    spec = _spec(root)
    return sync.write_stamp(
        root, spec, version="0.9.30", inputs=sync.input_fingerprints(root, spec)
    )


def _state(root: Path) -> str:
    return staleness.check_inputs(root, _spec(root)).state


# --------------------------------------------------------- the fingerprint ----


def test_fingerprint_covers_both_declared_globs(tmp_path):
    """Both globs, and nothing outside them.

    The clones under `sources/<name>/` are gitignored and re-fetched from a pinned
    SHA, so including them would report drift on every refresh at the same pin.
    """
    root = _repo(tmp_path)
    (root / "sources" / "alpha").mkdir()
    (root / "sources" / "alpha" / "README.md").write_text("clone content\n", encoding="utf-8")
    prints = sync.input_fingerprints(root, _spec(root))
    assert set(prints) == {
        "sources/alpha.manifest",
        "sources/beta.manifest",
        "sources/extractions/alpha-docs.json",
    }
    assert all(v.startswith("sha256:") for v in prints.values())


def test_fingerprint_is_content_not_stat(tmp_path):
    """Rewriting identical bytes must NOT move the digest — the whole thesis.

    Control arm below: a real content edit DOES move it, so this is not a probe
    that reports "unchanged" for everything.
    """
    root = _repo(tmp_path)
    manifest = root / "sources" / "alpha.manifest"
    before = sync.input_fingerprint(manifest)

    original = manifest.read_bytes()
    manifest.unlink()
    manifest.write_bytes(original)  # new inode, new mtime, identical bytes
    assert sync.input_fingerprint(manifest) == before

    manifest.write_text("url = https://example/alpha\nref = main\ncommit = ccc333\n")
    assert sync.input_fingerprint(manifest) != before


def test_fingerprint_map_is_sorted(tmp_path):
    """Sorted so two builds of one tree write byte-identical maps."""
    root = _repo(tmp_path)
    prints = sync.input_fingerprints(root, _spec(root))
    assert list(prints) == sorted(prints)


def test_an_unreadable_input_is_recorded_not_omitted(tmp_path):
    """It gets the sentinel, and the sentinel is not a digest anything can match."""
    root = _repo(tmp_path)
    unreadable = root / "sources" / "gamma.manifest"
    unreadable.write_text("url = https://example/gamma\n", encoding="utf-8")
    unreadable.chmod(0o000)
    try:
        prints = sync.input_fingerprints(root, _spec(root))
        assert prints["sources/gamma.manifest"] == sync.UNREADABLE
        assert not sync.UNREADABLE.startswith("sha256:")
    finally:
        unreadable.chmod(0o644)
    assert sync.input_fingerprints(root, _spec(root))["sources/gamma.manifest"].startswith(
        "sha256:"
    )


def test_a_new_and_unreadable_input_is_not_verifiable_not_ok(tmp_path):
    """THE round-2 regression: the false green that omission produced.

    A file that is NEW *and* unreadable is absent from the live map (nothing to
    digest) and absent from the recorded one (it did not exist at build time), so
    `_diff`'s `set(recorded) | set(live)` union never sees it and the whole check
    returned OK — an input nobody could read, reported as verified. Reproduced
    end to end by the cold lane before it was fixed.

    Note the arm this needs that the old test did not have: the previously-
    readable-then-unreadable case surfaces as "removed" either way, so a suite
    covering only that one passes on the broken code.
    """
    root = _repo(tmp_path)
    _stamp(root)
    assert _state(root) == staleness.OK  # control: clean before the new file

    newcomer = root / "sources" / "delta.manifest"
    newcomer.write_text("url = https://example/delta\n", encoding="utf-8")
    newcomer.chmod(0o000)
    try:
        status = staleness.check_inputs(root, _spec(root))
        assert status.state == staleness.NOT_VERIFIABLE, "an unread input must never read as OK"
        assert "sources/delta.manifest" in status.detail
    finally:
        newcomer.chmod(0o644)
    # And once it IS readable it is ordinary drift — so the guard above is not
    # simply jamming the check into a permanent not-verifiable.
    assert _state(root) == staleness.CHANGED


# ------------------------------------------------------------ both arms -------


def test_detector_fires_on_a_real_content_change(tmp_path):
    """ARM+ — a real edit to each glob is detected, and NAMED."""
    root = _repo(tmp_path)
    _stamp(root)
    assert _state(root) == staleness.OK

    (root / "sources" / "alpha.manifest").write_text(
        "url = https://example/alpha\nref = main\ncommit = zzz999\n", encoding="utf-8"
    )
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.CHANGED
    assert status.changes == ("sources/alpha.manifest  (content changed)",)


def test_detector_names_added_and_removed_inputs(tmp_path):
    """A fingerprint proves THAT something moved, never what — so it is per path."""
    root = _repo(tmp_path)
    _stamp(root)
    (root / "sources" / "beta.manifest").unlink()
    (root / "sources" / "extractions" / "new-docs.json").write_text(
        '{"nodes": [], "edges": []}\n', encoding="utf-8"
    )
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.CHANGED
    assert status.changes == (
        "sources/beta.manifest  (removed since the build)",
        "sources/extractions/new-docs.json  (added since the build)",
    )


def test_detector_is_silent_when_nothing_moved(tmp_path):
    """ARM- (the cheap half) — an untouched tree reports OK and prints nothing."""
    root = _repo(tmp_path)
    _stamp(root)
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.OK
    assert status.quiet


# ------------------------------- the three git operations #89 measured --------


def _git(root: Path) -> Callable[..., str]:
    def run(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT,
        )
        return proc.stdout

    return run


@pytest.fixture
def git_repo(tmp_path: Path) -> tuple[Path, Callable[..., str]]:
    root = _repo(tmp_path)
    git = _git(root)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (root / ".gitignore").write_text("graphify-out/\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "seed")
    return root, git


def test_silent_after_checkout_of_a_reverted_edit(git_repo):
    """ARM- #1 — `git checkout --` restores the bytes; the digest must not move.

    This is the row that killed `size:mtime_ns`: the restore rewrites the file, so
    the mtime moves while the content is identical.
    """
    root, git = git_repo
    _stamp(root)
    manifest = root / "sources" / "alpha.manifest"
    manifest.write_text("url = https://example/alpha\nref = main\ncommit = edited\n")
    assert _state(root) == staleness.CHANGED  # control: the probe CAN fire

    git("checkout", "--", "sources/alpha.manifest")
    assert _state(root) == staleness.OK


def test_silent_after_branch_round_trip_touching_sources(git_repo):
    """ARM- #2 — a round trip through a branch that edits `sources/` and comes back."""
    root, git = git_repo
    _stamp(root)
    git("checkout", "-q", "-b", "side")
    (root / "sources" / "beta.manifest").write_text(
        "url = https://example/beta\nref = main\ncommit = sidework\n"
    )
    git("commit", "-qam", "side edit")
    git("checkout", "-q", "main")
    assert _state(root) == staleness.OK


def test_silent_after_stash_and_pop_of_a_sources_edit(git_repo):
    """ARM- #3 — stash a `sources/` edit, pop it, revert it, and land back on OK."""
    root, git = git_repo
    _stamp(root)
    manifest = root / "sources" / "alpha.manifest"
    original = manifest.read_text(encoding="utf-8")
    manifest.write_text("url = https://example/alpha\nref = main\ncommit = stashed\n")
    git("stash", "push", "-q", "--", "sources/alpha.manifest")
    assert _state(root) == staleness.OK  # the edit is gone, so the bytes match again

    git("stash", "pop", "-q")
    assert _state(root) == staleness.CHANGED  # control: it comes back with the edit

    manifest.write_text(original, encoding="utf-8")
    assert _state(root) == staleness.OK


# ----------------------------------------- P3: never-built vs not-verifiable ---


def test_absent_stamp_is_never_built_not_drift(tmp_path):
    """An ABSENT stamp means there is no build to have gone stale."""
    root = _repo(tmp_path)
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.NEVER_BUILT
    assert status.state != staleness.CHANGED


def test_absent_graph_is_never_built_even_with_a_stamp(tmp_path):
    """Either half of "a build exists" missing is enough. The stamp can outlive the graph."""
    root = _repo(tmp_path)
    _stamp(root)
    (root / "graphify-out" / "graph.json").unlink()
    assert _state(root) == staleness.NEVER_BUILT


def test_never_built_short_circuits_before_comparing(tmp_path):
    """The ORDERING rule — a fresh clone must not be told its corpus went stale.

    Inputs that differ wildly from any recording still report *never built*,
    because absence of a build is checked first. Without this ordering the first
    session in a new clone reports every input as moved.
    """
    root = _repo(tmp_path)
    _stamp(root)
    (root / "graphify-out" / ".currency-stamp.json").unlink()
    (root / "sources" / "alpha.manifest").write_text("totally different\n", encoding="utf-8")
    (root / "sources" / "beta.manifest").unlink()
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.NEVER_BUILT
    assert status.changes == ()


def test_unreadable_stamp_is_not_verifiable_not_never_built(tmp_path):
    """An unreadable stamp is a DIFFERENT answer from an absent one, and from OK."""
    root = _repo(tmp_path)
    _stamp(root)
    (root / "graphify-out" / ".currency-stamp.json").write_text("{not json", encoding="utf-8")
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.NOT_VERIFIABLE
    assert status.state not in (staleness.NEVER_BUILT, staleness.OK)


def test_stamp_without_input_fingerprints_is_not_verifiable(tmp_path):
    """A pre-input stamp (v3, and every stamp on disk today) never asked the question.

    It must not read as clean. `{}` is the OTHER answer — recorded, and there were
    none — and the two are kept apart on purpose.
    """
    root = _repo(tmp_path)
    spec = _spec(root)
    sync.write_stamp(root, spec, version="0.9.30")  # inputs omitted, like an old build
    assert _state(root) == staleness.NOT_VERIFIABLE

    sync.write_stamp(root, spec, version="0.9.30", inputs={})
    assert _state(root) == staleness.CHANGED  # recorded-as-empty, live has three


def test_skips_silently_when_nothing_is_declared(tmp_path):
    """No `inputs` glob ⇒ no check. Not-applicable, not not-checked."""
    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        _CURRENCY.replace(
            'inputs = [\n  "sources/*.manifest",\n  "sources/extractions/*.json",\n]\n', ""
        ),
        encoding="utf-8",
    )
    status = staleness.check_inputs(root, _spec(root))
    assert status.state == staleness.SKIP
    assert status.quiet


# ----------------------------------------------- restamp must not launder -----


def test_restamp_artifacts_carries_inputs_forward_unchanged(tmp_path):
    """`kb-artifacts` regenerates views; it must not restate what the graph was built from.

    Re-digesting here would silently adopt a post-build input edit as the build's
    own inputs — a false green produced by the repair task.
    """
    root = _repo(tmp_path)
    spec = _spec(root)
    _stamp(root)
    (root / "sources" / "alpha.manifest").write_text("edited after the build\n", encoding="utf-8")

    sync.restamp_artifacts(root, spec)
    assert _state(root) == staleness.CHANGED


def test_restamp_does_not_invent_an_empty_input_map(tmp_path):
    """Carrying None forward as `{}` would turn *never recorded* into a clean pass."""
    root = _repo(tmp_path)
    spec = _spec(root)
    sync.write_stamp(root, spec, version="0.9.30")  # no input map
    sync.restamp_artifacts(root, spec)
    stamp = json.loads((root / "graphify-out" / ".currency-stamp.json").read_text())
    assert "input_fingerprints" not in stamp
    assert _state(root) == staleness.NOT_VERIFIABLE


# ------------------------------------------------------------- reporting -----


def test_report_is_silent_when_clean(tmp_path, capsys):
    root = _repo(tmp_path)
    _stamp(root)
    staleness.report([staleness.check_inputs(root, _spec(root))])
    assert capsys.readouterr().out == ""


def test_report_names_each_changed_path_and_the_right_remedy(tmp_path, capsys):
    """The remedy must be `kb-build`, not the tool-currency skill (#88)."""
    root = _repo(tmp_path)
    _stamp(root)
    (root / "sources" / "alpha.manifest").write_text("moved\n", encoding="utf-8")
    staleness.report([staleness.check_inputs(root, _spec(root))])
    out = capsys.readouterr().out
    assert "mise run kb-build" in out
    assert "tool-currency skill" not in out
    assert "sources/alpha.manifest  (content changed)" in out


def test_report_keeps_never_built_out_of_the_changed_block(tmp_path, capsys):
    """A fresh clone must not read as "your corpus went stale"."""
    root = _repo(tmp_path)
    staleness.report([staleness.check_inputs(root, _spec(root))])
    out = capsys.readouterr().out
    assert "no graph has been built here yet" in out
    assert "corpus inputs changed" not in out


def test_report_never_renders_not_verifiable_as_a_pass(tmp_path, capsys):
    root = _repo(tmp_path)
    _stamp(root)
    (root / "graphify-out" / ".currency-stamp.json").write_text("{broken", encoding="utf-8")
    staleness.report([staleness.check_inputs(root, _spec(root))])
    out = capsys.readouterr().out
    assert "NOT CHECKED against its inputs (this is not a pass)" in out
