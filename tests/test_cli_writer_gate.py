# Copyright (c) 2026 Raymond Manaloto
"""The graph-WRITER preflight in `cli.main` (#186 cold lane, P1).

Writers get the pinned-version gate; readers never pay it. Tested at the
dispatch layer because that is where every real invocation enters (the
PreToolUse guard denies raw graphify), and gating there — rather than inside
the library functions — is what lets those functions stay drivable by test
stubs that fake the exe.
"""

from __future__ import annotations

import pytest
from kb_setup import cli, graphify_env, graphify_ops


def test_every_writer_is_gated_before_its_module_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate fires FIRST for each writer command.

    Proven by a tripwire that raises: a command that reached its real work
    would fail differently than with the tripwire's own message.
    """
    calls: list[str] = []

    def tripwire(_root: object) -> None:
        calls.append("gate")
        raise SystemExit("gate fired")

    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", tripwire)

    for cmd in sorted(cli._GRAPH_WRITERS):
        calls.clear()
        with pytest.raises(SystemExit, match="gate fired"):
            cli.main([cmd])
        assert calls == ["gate"], f"{cmd} bypassed the writer gate"


def test_a_reader_never_pays_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Readers never pay the gate.

    A stale binary gives a reader a worse answer; only a writer destroys data
    with one. Gating reads would turn every version skew into a query outage
    for no protective gain.
    """

    def boom(_root: object) -> None:
        raise AssertionError("a reader was gated")

    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", boom)
    monkeypatch.setattr(graphify_ops, "query", lambda _r, _rest: 0)

    assert cli.main(["version"]) == 0
    assert cli.main(["query", "anything"]) == 0


def test_the_writer_set_names_every_graph_writer() -> None:
    """The set is the contract.

    A writer added to the dispatch but not to `_GRAPH_WRITERS` silently skips
    the gate, so the membership is pinned. `update` is deliberately absent —
    a kind=docs pin advance is pure git, so `graph.update` gates its own
    code-kind branch where the kind is actually known (cold lane round 2).
    """
    assert {
        "build",
        "watch",
        "merge",
        "label",
        "artifacts",
        "critical-corpus",
    } == cli._GRAPH_WRITERS


def test_update_is_not_gated_at_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """`update` must reach `graph.update` ungated.

    The docs branch never runs graphify, and the code branch carries its own
    gate — tested with graph's own fixtures in test_graph_docs_kind.py.
    """
    from kb_setup import graph

    def boom(_root: object) -> None:
        raise AssertionError("update was gated at dispatch")

    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", boom)
    monkeypatch.setattr(graph, "update_all", lambda _r: 0)

    assert cli.main(["update"]) == 0
