"""The build stamp must name the binary that ACTUALLY BUILT the graph.

This file exists because of a regression introduced while fixing #40 and caught
by adversarial verification. Moving the build's invocation to `graphify_exe`
(mise-resolved) while leaving `_stamp_build` reading `spec.binary` (PATH-resolved)
made the two resolve DIFFERENTLY — so a graph could be built by one binary and
stamped with another's version.

That is worse than the bug being fixed. Before the change both sides read PATH
and therefore always agreed; a mismatch was impossible. After it, a mismatch was
possible and silent — and `graphify_env.graphify_exe`'s own docstring calls a
graph built by one version and stamped another "the one failure this repo cannot
absorb". A fix that manufactures the failure it names is not a fix.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import graph

if TYPE_CHECKING:
    import pytest

_PINNED_EXE = "/mise/installs/pipx-graphifyy/0.9.26/bin/graphify"


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\nbinary = "graphify"\n'
        'stamp = "out/.stamp.json"\n',
        encoding="utf-8",
    )
    return tmp_path


def test_the_stamp_reads_the_binary_the_build_ran(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE regression test: stamp resolution must track build resolution.

    `graphify_exe` names the pinned binary; PATH names a different one. The stamp
    must follow the first, because that is what produced the artifact.
    """
    seen: list[str] = []

    monkeypatch.setattr(graph, "graphify_exe", lambda _root: _PINNED_EXE)

    def _observed(binary: str) -> str:
        seen.append(binary)
        return "0.9.26" if binary == _PINNED_EXE else "0.9.28"

    from kb_setup.currency import sync

    monkeypatch.setattr(sync, "observed_version", _observed)
    monkeypatch.setattr(sync, "manifest_ref", lambda *_a, **_k: None)
    written: dict[str, str | None] = {}
    monkeypatch.setattr(
        sync,
        "write_stamp",
        lambda _root, _spec, *, version, source_ref, inputs=None: (
            written.update(version=version, source_ref=source_ref, inputs=inputs),
            Path("stamp.json"),
        )[1],
    )

    graph._stamp_build(_repo(tmp_path), {"sources/x.manifest": "sha256:abc"})

    assert seen == [_PINNED_EXE], f"stamp resolved {seen}, not the built binary"
    assert written["version"] == "0.9.26"
    # The input map reaches the stamp UNCHANGED. `_stamp_build` must not compute
    # or edit it: the digests belong to the build that read them, and the only
    # caller allowed to produce them is `build()` — before it reads anything.
    assert written["inputs"] == {"sources/x.manifest": "sha256:abc"}


def test_a_path_resolved_stamp_would_have_recorded_the_other_version() -> None:
    """CONTROL ARM: prove the fixture can produce the WRONG answer.

    Without this, the test above passes for a fixture where both binaries happen
    to report the same version — i.e. it would be green even if the fix were
    reverted. Here the pre-fix behaviour is simulated explicitly and must yield
    the divergent version, which is what makes the assertion above meaningful.
    """

    def _observed(binary: str) -> str:
        return "0.9.26" if binary == _PINNED_EXE else "0.9.28"

    # The pre-fix code path resolved the stamp from the bare spec name, which in
    # this fixture reports a DIFFERENT version than the built binary. So the
    # assertion above is discriminating, not tautological.
    assert _observed("graphify") == "0.9.28"
    assert _observed(_PINNED_EXE) == "0.9.26"


def test_a_config_without_graphify_stamps_nothing_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM on the selector, and a correction to an earlier draft of it.

    This test used to assert "graphify's binary does not leak into another
    tool's stamp" against an ffmpeg-only config — and passed **vacuously**:
    `_currency_spec` selects by `name == "graphify"`, so that config yields no
    spec, `_stamp_build` returns early, and NOTHING is called. The assertion
    could not have failed.

    Finding that is what showed the guard it was defending (`spec.binary ==
    _STAMPED_TOOL`) to be unreachable via this path — and worse than unreachable,
    since a config setting `binary` to anything else would have fallen back to
    the PATH-resolved reading. The guard is gone; what is actually true is
    asserted here instead: no graphify entry means no stamp.
    """
    (tmp_path / "currency.toml").write_text(
        '[tool.ffmpeg]\nmise_key = "conda:ffmpeg"\nbinary = "ffmpeg"\nstamp = "out/.stamp.json"\n',
        encoding="utf-8",
    )
    from kb_setup.currency import sync

    calls: list[str] = []
    monkeypatch.setattr(graph, "graphify_exe", lambda _root: _PINNED_EXE)
    monkeypatch.setattr(sync, "observed_version", lambda b: calls.append(b) or "")
    monkeypatch.setattr(sync, "write_stamp", lambda *_a, **_k: calls.append("WROTE"))

    graph._stamp_build(tmp_path)

    assert calls == [], "an ffmpeg-only config must not reach the graphify stamp path"


def test_the_selector_does_reach_the_stamp_for_graphify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The arm that makes the test above mean something.

    Same shape, graphify present: the stamp path IS reached. Without this, the
    empty-`calls` assertion above is indistinguishable from a broken fixture —
    which is precisely the failure it was written to correct.
    """
    from kb_setup.currency import sync

    calls: list[str] = []
    monkeypatch.setattr(graph, "graphify_exe", lambda _root: _PINNED_EXE)
    monkeypatch.setattr(sync, "observed_version", lambda b: calls.append(b) or "0.9.26")
    monkeypatch.setattr(sync, "manifest_ref", lambda *_a, **_k: None)
    monkeypatch.setattr(sync, "write_stamp", lambda *_a, **_k: Path("stamp.json"))

    graph._stamp_build(_repo(tmp_path))

    assert calls == [_PINNED_EXE]
