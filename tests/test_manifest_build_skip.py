# Copyright (c) 2026 Raymond Manaloto
"""`build = skip` and the enumerated-field validation that arrived with it (#409).

The two hazards these cover are opposite. `build = skip` can turn a red build
green by removing the source that was reporting a real problem, so it must be
loud and must refuse to be used without a stated reason. The enum validation
covers the reverse: until 2026-08-20 `scope` had one reader and no check, so a
typo fell through to the `corpus` default and merged a peer tool into the
aggregate — the exact outcome the field exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import graph
from kb_setup import manifest as mf

_BASE = "url = https://example.invalid/x\nref = main\ncommit = " + "a" * 40 + "\n"


def _write(tmp_path: Path, body: str, name: str = "demo") -> Path:
    path = tmp_path / f"{name}.manifest"
    path.write_text(_BASE + body, encoding="utf-8")
    return path


def test_defaults_are_include_with_no_reason(tmp_path: Path) -> None:
    m = mf.load(_write(tmp_path, ""))
    assert (m.kind, m.scope, m.build, m.skip_reason) == ("code", "corpus", "include", "")


def test_build_skip_carries_its_reason(tmp_path: Path) -> None:
    m = mf.load(_write(tmp_path, "build = skip\nskip_reason = #409 inventory does not scale\n"))
    assert m.build == "skip"
    assert m.skip_reason == "#409 inventory does not scale"


def test_build_skip_without_a_reason_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a non-empty `skip_reason`"):
        mf.load(_write(tmp_path, "build = skip\n"))


def test_build_skip_with_an_empty_reason_is_refused(tmp_path: Path) -> None:
    """An empty value is the shape a half-finished edit leaves behind."""
    with pytest.raises(ValueError, match="requires a non-empty `skip_reason`"):
        mf.load(_write(tmp_path, "build = skip\nskip_reason =\n"))


@pytest.mark.parametrize(
    ("field", "bad"),
    [("scope", "study-graph"), ("kind", "Code"), ("build", "skipped"), ("build", "true")],
)
def test_an_unrecognised_enum_value_is_refused_not_defaulted(
    tmp_path: Path, field: str, bad: str
) -> None:
    """The defect this closes: a wrong value indistinguishable from the default.

    None of these four is spelled like a dictionary word, deliberately. The first
    draft used a doubled-consonant misspelling of the scope value, and
    `mise run fmt`'s `typos` step CORRECTED it into the valid spelling — so the
    case then asserted that a LEGAL manifest raises. Same class as `ruff format`
    moving a mutation anchor: a fixture whose whole job is to be wrong must be
    wrong in a way no formatter will tidy up, and must not be written literally
    in prose either.
    """
    with pytest.raises(ValueError, match=f"{field} = "):
        mf.load(_write(tmp_path, f"{field} = {bad}\n"))


def test_every_committed_manifest_still_loads() -> None:
    """The validation is new; the 73 committed manifests predate it."""
    root = Path(__file__).resolve().parents[1]
    loaded = mf.load_all(root / "sources")
    assert loaded, "no manifests found — the probe would pass vacuously"
    assert [m.name for m in loaded if m.build == "skip"] == ["GitNexus"]


def test_gitnexus_is_skipped_but_still_pinned() -> None:
    """`build = skip` is an exclusion from THIS build, never from the record."""
    root = Path(__file__).resolve().parents[1]
    m = mf.load(root / "sources" / "GitNexus.manifest")
    assert m.build == "skip"
    assert m.scope == "study", "the reason it was study must survive being skipped"
    assert len(m.commit) == 40, "the pin is what keeps provenance intact"
    assert m.url, "the pin is what keeps provenance intact"
    assert "#409" in m.skip_reason


def _manifest(name: str, *, build: str = "include", reason: str = "") -> mf.Manifest:
    return mf.Manifest(
        name=name,
        path=Path("sources") / f"{name}.manifest",
        url="https://example.invalid/x",
        ref="main",
        commit="a" * 40,
        build=build,
        skip_reason=reason,
    )


def test_a_skipped_source_is_dropped_before_the_clone() -> None:
    """The drop must happen in `build()`, not only in the parser."""
    kept = graph._drop_skipped_builds(
        [_manifest("keeper"), _manifest("dropped", build="skip", reason="#409")]
    )
    assert [m.name for m in kept] == ["keeper"]


def test_a_skipped_source_announces_itself_with_its_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A silent exclusion is indistinguishable from a source nobody noticed was gone."""
    graph._drop_skipped_builds(
        [_manifest("keeper"), _manifest("dropped", build="skip", reason="#409 inventory")]
    )
    out = capsys.readouterr().out
    assert "dropped" in out
    assert "#409 inventory" in out, "the reason must reach the operator, not just the file"
    assert "keeper" not in out, "an included source must not be announced as excluded"


def test_a_build_with_every_source_skipped_is_refused() -> None:
    """Otherwise an empty build would compose a graph out of nothing."""
    with pytest.raises(SystemExit, match="nothing to build"):
        graph._drop_skipped_builds([_manifest("only", build="skip", reason="#409")])


def test_build_actually_calls_the_drop_before_cloning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CALL SITE, not the helper — R4 of the mutation sweep survived without it.

    Deleting `manifests = _drop_skipped_builds(manifests)` from `build()` left the
    helper perfectly tested and completely unreachable, and every test stayed
    green: the direct-call tests above cannot see a caller that stopped calling.
    A validator nothing calls is not a gate.

    Ordering matters as much as the call: the drop must run BEFORE `_ensure_clone`,
    or an excluded source is still cloned (51 MB, for GitNexus) before being
    discarded. `_ensure_clone` is monkeypatched to fail loudly so that inversion
    is caught rather than merely being slow.
    """
    sentinel = RuntimeError("the drop ran")

    def _drop(manifests: list[mf.Manifest]) -> list[mf.Manifest]:
        raise sentinel

    def _no_clone(m: mf.Manifest) -> None:
        raise AssertionError(f"cloned {m.name} before the build=skip drop")

    monkeypatch.setattr(graph, "_drop_skipped_builds", _drop)
    monkeypatch.setattr(graph, "_ensure_clone", _no_clone)
    monkeypatch.setattr(graph, "_required_input_fingerprints", lambda _root: {})

    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    (tmp_path / "sources" / "demo.manifest").write_text(_BASE, encoding="utf-8")

    with pytest.raises(RuntimeError) as excinfo:
        graph.build(tmp_path)
    assert excinfo.value is sentinel, "build() reached the clone without dropping first"
