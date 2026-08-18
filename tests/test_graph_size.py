# Copyright (c) 2026 Raymond Manaloto
"""Arms for the graph-size gate — the number that was computed and never gated."""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import graph_size
from kb_setup.result import Rc


def _graph(root: Path, size: int) -> Path:
    out = root / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    graph = out / "graph.json"
    graph.write_bytes(b"x" * size)
    return graph


def test_the_gate_reads_graphifys_own_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """The effective ceiling comes from graphify, not from a parser of our own.

    The `1GB` arm is the one that matters and the reason this is not re-parsed
    here: graphify's suffix convention is BINARY, so `1GB` is 1024**3 and not
    10**9. A hand-rolled reading would agree on the string and be 7% wrong about
    the number — reporting headroom this repo does not have, in the gate whose
    entire job is headroom.

    The unset arm is the control: without it this would pass against a resolver
    that returned a constant.
    """
    monkeypatch.setenv("GRAPHIFY_MAX_GRAPH_BYTES", "1GB")
    assert graph_size.effective_cap_bytes() == 1024**3

    monkeypatch.delenv("GRAPHIFY_MAX_GRAPH_BYTES", raising=False)
    assert graph_size.effective_cap_bytes() == 512 * 1024 * 1024


@pytest.mark.parametrize(
    ("fraction", "state", "rc"),
    [
        pytest.param(0.10, "ok", 0, id="well-under"),
        pytest.param(0.79, "ok", 0, id="just-under-the-warning"),
        pytest.param(0.85, "near", 0, id="past-the-warning-still-passes"),
        pytest.param(1.50, "over", 1, id="over-the-ceiling-fails"),
    ],
)
def test_the_verdict_and_the_exit_code_move_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fraction: float, state: str, rc: int
) -> None:
    """Three bands, and the middle one is the point: WARN is not FAIL.

    A gate that failed at 80% would block every merge for months over a decision
    (federate, or de-duplicate) that takes a round to make. A gate that only
    warned at 100% would announce the problem after graphify had already stopped
    reading the file. The bands exist so the prompt and the stop are different
    events.

    `just-under-the-warning` is the control on the middle band: without it, a
    threshold accidentally set to zero would satisfy every other arm.
    """
    cap = 1024 * 1024
    monkeypatch.setenv("GRAPHIFY_MAX_GRAPH_BYTES", str(cap))
    _graph(tmp_path, int(cap * fraction))

    verdict = graph_size.measure(tmp_path)
    assert verdict.state == state
    assert graph_size.main(tmp_path) == rc


def test_an_unbuilt_graph_is_named_rather_than_reported_as_ok(tmp_path: Path) -> None:
    """An unbuilt graph must not render as checked-and-fine.

    It still exits 0 — a fresh clone has no graph to be too large, and failing
    there would train people to skip this gate. What it must not do is say OK,
    because that is the word a reader takes as evidence.
    """
    verdict = graph_size.measure(tmp_path)

    assert verdict.state == "unbuilt"
    assert graph_size.main(tmp_path) == 0
    assert "OK" not in graph_size.render(verdict)
    assert "kb-build" in verdict.note


def test_headroom_is_reported_even_when_the_gate_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trend is the product, not the verdict.

    A gate first heard from at the ceiling has told nobody anything they could
    act on, which is exactly how this number spent months in a report while the
    graph reached roughly three quarters of its cap.
    """
    cap = 1000
    monkeypatch.setenv("GRAPHIFY_MAX_GRAPH_BYTES", str(cap))
    _graph(tmp_path, 250)

    verdict = graph_size.measure(tmp_path)
    rendered = graph_size.render(verdict)

    assert verdict.state == "ok"
    assert verdict.headroom_bytes == 750
    assert "headroom" in rendered


def test_the_gate_is_a_stat_and_never_a_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reading the file would make the cheapest gate the slowest one.

    Armed by making the graph unreadable while leaving its SIZE intact: a
    directory-mode failure or a decode would surface here, and a `stat` does not
    care. Without this, a later "just parse it while we're here" edit would pass
    every other arm in this file.
    """
    cap = 1024
    monkeypatch.setenv("GRAPHIFY_MAX_GRAPH_BYTES", str(cap))
    graph = _graph(tmp_path, 100)
    graph.write_bytes(b"\xff\xfe not json at all, not even utf-8")

    assert graph_size.measure(tmp_path).state == "ok"


def test_the_gate_is_on_the_ship_path_rather_than_in_a_report() -> None:
    """Membership IS the change. Ray's ruling was to gate it, not to print it.

    Both assertions are needed. The first is the ruling; the second is the reason
    it can be honoured cheaply — this gate writes nothing and carries no
    wall-clock bound, the two questions `CONCURRENT_SAFE` requires.
    """
    from kb_setup import gates

    assert "graph-size" in gates.GATE_TASKS
    assert "graph-size" in gates.CONCURRENT_SAFE


def test_a_vanished_graph_is_not_run_while_a_never_built_one_is_fine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absent graph can mean two things, and only one of them is harmless.

    Two absences, two meanings, and collapsing them is what a cold lane flagged:

    * Nothing ever built here — a fresh clone, a CI runner. There is genuinely
      nothing to gate, and failing would make the repo unshippable until a
      multi-minute build ran. Exit 0, state NAMED `unbuilt` rather than `OK`.
    * The build stamp says this machine HAS built and the graph is gone. The gate
      could not ask its question, which is not a pass — `Rc.NOT_RUN`, the code
      `skill_lint` already returns when its glob matches nothing.

    The stamp's mere EXISTENCE is the discriminator, so the arm is one file.
    """
    monkeypatch.setenv("GRAPHIFY_MAX_GRAPH_BYTES", str(1024 * 1024))
    out = tmp_path / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)

    assert graph_size.measure(tmp_path).state == "unbuilt"
    assert graph_size.main(tmp_path) == int(Rc.OK)

    (out / ".currency-stamp.json").write_text("{}", encoding="utf-8")

    assert graph_size.measure(tmp_path).state == "missing"
    assert graph_size.main(tmp_path) == int(Rc.NOT_RUN)

    # The control: with the graph present, the stamp changes nothing — otherwise
    # this would be asserting that a stamped machine can never pass.
    _graph(tmp_path, 100)
    assert graph_size.measure(tmp_path).state == "ok"
    assert graph_size.main(tmp_path) == int(Rc.OK)
