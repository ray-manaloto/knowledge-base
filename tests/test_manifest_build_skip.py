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
    # An INVENTORY PIN, not a count: every `build = skip` is a source excluded
    # from the graph, so a new one must be a deliberate decision someone made,
    # never a line that slid in. Compared as a SET so the assertion survives a
    # change in `load_all`'s ordering — exactness is the point, order is not.
    #
    # GitNexus is #409. The other four were skipped 2026-08-20 under Ray's
    # ruling to skip any blocker, file it, and triage after the graphify
    # extraction; all four are registered in #417, which also records that
    # `codegraph` is the one whose `scope = corpus` makes it real aggregate loss.
    assert {m.name for m in loaded if m.build == "skip"} == {
        "GitNexus",
        "codebase-memory-mcp",
        "codegraph",
        "codex",
        "colibri",
    }


def test_gitnexus_is_skipped_but_still_pinned() -> None:
    """`build = skip` is an exclusion from THIS build, never from the record."""
    root = Path(__file__).resolve().parents[1]
    m = mf.load(root / "sources" / "GitNexus.manifest")
    assert m.build == "skip"
    assert m.scope == "study", "the reason it was study must survive being skipped"
    assert len(m.commit) == 40, "the pin is what keeps provenance intact"
    assert m.url, "the pin is what keeps provenance intact"
    assert "#409" in m.skip_reason


def _manifest(
    name: str, *, build: str = "include", reason: str = "", defer_reason: str = ""
) -> mf.Manifest:
    return mf.Manifest(
        name=name,
        path=Path("sources") / f"{name}.manifest",
        url="https://example.invalid/x",
        ref="main",
        commit="a" * 40,
        build=build,
        skip_reason=reason,
        defer_reason=defer_reason,
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


# --------------------------------------------------------------------------
# `build = defer` (Ray, 2026-08-24) — the cost-deferral state.
#
# `skip` had been carrying two unrelated meanings. All five sources excluded
# before `defer` existed were excluded by a DEFECT (#409, #417); a source that
# is merely not worth its extraction cost yet is a BUDGET decision, and filing
# it as `skip` makes it read as broken forever. The pair below is the point:
# the two states must be indistinguishable in EFFECT (both excluded, both loud,
# both still pinned) and distinguishable in MEANING.
# --------------------------------------------------------------------------


def test_build_defer_carries_its_reason(tmp_path: Path) -> None:
    m = mf.load(_write(tmp_path, "build = defer\ndefer_reason = 1,551 org files, deferred\n"))
    assert m.build == "defer"
    assert m.defer_reason == "1,551 org files, deferred"


def test_build_defer_without_a_reason_is_refused(tmp_path: Path) -> None:
    """A deferral must say what would bring it back, or it is just an absence."""
    with pytest.raises(ValueError, match="requires a non-empty `defer_reason`"):
        mf.load(_write(tmp_path, "build = defer\n"))


def test_build_defer_with_an_empty_reason_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a non-empty `defer_reason`"):
        mf.load(_write(tmp_path, "build = defer\ndefer_reason =\n"))


def test_defer_does_not_satisfy_skip_reason_and_vice_versa(tmp_path: Path) -> None:
    """The fields are not interchangeable — that separation IS the feature.

    Filing a cost deferral under `skip_reason` would put it back in the queue
    that waits on a fix, which is the conflation this state was added to end.
    """
    with pytest.raises(ValueError, match="requires a non-empty `defer_reason`"):
        mf.load(_write(tmp_path, "build = defer\nskip_reason = not a deferral reason\n"))
    with pytest.raises(ValueError, match="requires a non-empty `skip_reason`"):
        mf.load(_write(tmp_path, "build = skip\ndefer_reason = not a skip reason\n"))


@pytest.mark.parametrize(
    ("body", "stale"),
    [
        ("skip_reason = left over from a previous state\n", "skip_reason"),
        ("defer_reason = left over from a previous state\n", "defer_reason"),
    ],
)
def test_a_reason_for_a_state_the_manifest_is_not_in_is_refused(
    tmp_path: Path, body: str, stale: str
) -> None:
    """A leftover reason is worse than none: it reads as the CURRENT state's reason.

    The realistic edit that produces it is restoring a source — flipping `build`
    back to `include` and forgetting to delete the line underneath it.
    """
    with pytest.raises(ValueError, match=f"`{stale}` is set but build ="):
        mf.load(_write(tmp_path, body))


def test_defaults_carry_neither_reason(tmp_path: Path) -> None:
    m = mf.load(_write(tmp_path, ""))
    assert (m.build, m.skip_reason, m.defer_reason) == ("include", "", "")
    assert m.is_built is True
    assert m.exclusion_reason == ""


@pytest.mark.parametrize(
    ("build", "field", "reason"),
    [("skip", "skip_reason", "#417 zero nodes"), ("defer", "defer_reason", "too many docs")],
)
def test_exclusion_reason_reads_whichever_field_the_state_requires(
    tmp_path: Path, build: str, field: str, reason: str
) -> None:
    """Callers must never have to know which of the two fields is populated."""
    m = mf.load(_write(tmp_path, f"build = {build}\n{field} = {reason}\n"))
    assert m.is_built is False
    assert m.exclusion_reason == reason


def test_a_deferred_source_is_dropped_before_the_clone() -> None:
    """THE REGRESSION TEST FOR THE LAYER-2 BUG, and it is the reason this exists.

    Adding `defer` to the parser alone left `graph._drop_skipped_builds` testing
    `m.build != "skip"`, which is TRUE for `defer` — so the new exclusion state
    excluded nothing and a deferred source would have been cloned and extracted
    anyway. Revert `is_built` to a `!= "skip"` comparison and this case goes red;
    nothing in the parser tests above would notice.
    """
    kept = graph._drop_skipped_builds(
        [_manifest("keeper"), _manifest("deferred", build="defer", defer_reason="cost")]
    )
    assert [m.name for m in kept] == ["keeper"]


def test_a_deferred_source_announces_its_state_not_just_its_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The operator triaging the backlog needs to know WHICH queue the line is in.

    `skip` waits on a fix; `defer` waits on a budget or a backend. Printing only
    the reason would leave the two indistinguishable in the build log, which is
    where the distinction is actually consumed.
    """
    graph._drop_skipped_builds(
        [
            _manifest("keeper"),
            _manifest("broken", build="skip", reason="#417 zero nodes"),
            _manifest("costly", build="defer", defer_reason="5,360 docs, deferred on spend"),
        ]
    )
    out = capsys.readouterr().out
    assert "keeper" not in out, "an included source must not be announced as excluded"
    assert "build = skip" in out
    assert "build = defer" in out
    assert "#417 zero nodes" in out
    assert "5,360 docs, deferred on spend" in out


def test_a_build_with_every_source_excluded_is_refused_whichever_state() -> None:
    """A mix of the two exclusions still leaves nothing to build."""
    with pytest.raises(SystemExit, match="nothing to build"):
        graph._drop_skipped_builds(
            [
                _manifest("a", build="skip", reason="#417"),
                _manifest("b", build="defer", defer_reason="cost"),
            ]
        )
