# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.code_intel`.

Every assertion here is written to FAIL if its subject is reverted. Two of
them exist because the property they pin is invisible in the output: a
double-counted skill and a cwd-less subprocess both produce plausible-looking
edge lists, which is exactly what let the original prototype ship with the
wrong number in it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import chunks, code_intel

# ---------------------------------------------------------------------------
# Fixtures — an isolated fake repo, never the real one
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A repo skeleton with ONE skill mirrored into both skill trees.

    The mirror is the point: `DEFAULT_SKILL_GLOBS` walks `.claude/skills/` and
    `.agents/skills/`, and in the real repo every skill lives in both.
    """
    for tree in (".claude/skills/demo", ".agents/skills/demo"):
        d = tmp_path / tree
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "# demo\n\nRun it:\n\n```bash\nmise run kb-build\n```\n",
            encoding="utf-8",
        )
    src = tmp_path / "python" / "src" / "kb_setup"
    src.mkdir(parents=True)
    # A minimal `_run` dispatch arm (for `dispatch_edges`) and a config read
    # (for `config_edges`) — bare name `build` on both sides so the same
    # fixture also backs the bare-name-collision reasoning in test 3, even
    # though that test builds its edges by hand rather than through the AST
    # lanes.
    (src / "cli.py").write_text(
        "def _run(argv):\n"
        "    cmd = argv[0]\n"
        '    if cmd == "build":\n'
        "        return build(cmd)\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (src / "other.py").write_text(
        'def load_thing():\n    path = "config/settings.toml"\n    return open(path).read()\n',
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Every lane stamps its own provenance and cites something
# ---------------------------------------------------------------------------


def test_skill_lane_stamps_its_provenance_and_cites_a_file_line(fake_repo: Path) -> None:
    edges = code_intel.skill_edges(fake_repo)

    assert edges, "the fixture has one fenced command; the lane found none"
    for edge in edges:
        assert edge.provenance == "SKILL_FENCE"
        assert edge.evidence, "an edge with no evidence is an unsourced claim"
        assert ":" in edge.evidence, f"evidence {edge.evidence!r} is not file:line"


def test_every_edge_carries_a_namespaced_source_and_target(fake_repo: Path) -> None:
    for edge in code_intel.skill_edges(fake_repo):
        assert ":" in edge.source, f"{edge.source!r} is not namespaced"
        assert ":" in edge.target, f"{edge.target!r} is not namespaced"


def test_dispatch_lane_stamps_its_provenance_and_cites_a_file_line(fake_repo: Path) -> None:
    """The fixture's `cli.py` has one `if cmd == "build": return build(cmd)` arm."""
    edges = code_intel.dispatch_edges(fake_repo)

    assert edges, "the fixture's cli.py has one dispatch arm; the lane found none"
    for edge in edges:
        assert edge.provenance == "CLI_DISPATCH"
        assert edge.evidence
        assert edge.evidence.startswith("python/src/kb_setup/cli.py:")
    assert any(e.source == "cli:build" and e.target == "fn:build" for e in edges)


def test_config_lane_stamps_its_provenance_and_cites_a_file_line(fake_repo: Path) -> None:
    """The fixture's `other.py` reads one config-shaped literal path."""
    edges = code_intel.config_edges(fake_repo)

    assert edges, "the fixture's other.py reads a config path; the lane found none"
    for edge in edges:
        assert edge.provenance == "CONFIG_READ"
        assert edge.evidence
        assert edge.evidence.startswith("python/src/kb_setup/other.py:")
    assert any(e.target == "config:config/settings.toml" for e in edges)


def test_task_lane_stamps_its_provenance_and_cites_a_command(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real (non-empty) `mise tasks --json` reply, tagged MISE_TASK."""

    class _Result:
        stdout = json.dumps([{"name": "build", "run": ["uv run kb-setup build"]}])

    def _fake_run(_argv: list[str], **_kwargs: object) -> _Result:
        return _Result()

    monkeypatch.setattr(code_intel.subprocess, "run", _fake_run)
    edges = code_intel.task_edges(fake_repo)

    assert edges, "the fake task list has one run line; the lane found none"
    for edge in edges:
        assert edge.provenance == "MISE_TASK"
        assert edge.evidence
    assert any(e.source == "task:build" and e.target == "cli:build" for e in edges)


# ---------------------------------------------------------------------------
# 2c. The dedup — a mirrored skill is ONE skill
# ---------------------------------------------------------------------------


def test_a_skill_mirrored_into_both_trees_yields_one_source_not_two(
    fake_repo: Path,
) -> None:
    """Fails if the dedup is removed.

    The fixture writes the SAME skill into `.claude/skills/demo/` and
    `.agents/skills/demo/`. A naive walk of both globs emits every command
    twice. Asserting on the SOURCE SET rather than a count is what makes this
    survive someone adding a second command to the fixture.
    """
    edges = code_intel.skill_edges(fake_repo)

    assert {e.source for e in edges} == {"skill:demo"}
    # One fenced command in one logical skill => exactly one edge.
    assert len(edges) == 1, f"mirrored skill double-counted: {[e.evidence for e in edges]}"


def test_dedup_keeps_the_claude_tree_which_skill_lint_calls_authoritative(
    fake_repo: Path,
) -> None:
    """`.claude/` wins, not whichever the filesystem happened to yield first."""
    (edge,) = code_intel.skill_edges(fake_repo)

    assert edge.evidence.startswith(".claude/skills/"), (
        f"dedup kept the mirror rather than the authoritative tree: {edge.evidence}"
    )


# ---------------------------------------------------------------------------
# 2b. The chunk mapping is checked against the REAL schema, imported
# ---------------------------------------------------------------------------


def test_chunk_nodes_and_edges_satisfy_the_imported_schema_tuples() -> None:
    """Asserts against `chunks._NODE_REQUIRED` / `_EDGE_REQUIRED` themselves.

    Imported rather than retyped: a copied schema drifts from its source
    silently, and the copy always looks right.
    """
    chunk = code_intel.to_chunk(
        [
            code_intel.Edge(
                source="task:kb-build",
                target="cli:build",
                relation="invokes",
                provenance="MISE_TASK",
                verified=True,
                evidence="mise.toml:1",
            )
        ]
    )

    assert chunk["nodes"], "no nodes emitted"
    for node in chunk["nodes"]:
        missing = [k for k in chunks._NODE_REQUIRED if k not in node]
        assert not missing, f"node missing required field(s) {missing}"
    for edge in chunk["edges"]:
        missing = [k for k in chunks._EDGE_REQUIRED if k not in edge]
        assert not missing, f"edge missing required field(s) {missing}"


def test_to_chunk_raises_loudly_if_the_real_schema_grows_a_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mapping must fail at the mapping, never emit a short chunk.

    Simulates `chunks._NODE_REQUIRED` gaining a field this module cannot fill.
    Without the guard, `to_chunk` would emit a chunk one field short and the
    loss would surface at `kb-merge`, far from the cause.
    """
    monkeypatch.setattr(
        code_intel, "_NODE_REQUIRED", (*chunks._NODE_REQUIRED, "a_field_we_cannot_fill")
    )

    with pytest.raises(RuntimeError, match="schema moved"):
        code_intel.to_chunk(
            [
                code_intel.Edge(
                    source="task:x",
                    target="cli:y",
                    relation="invokes",
                    provenance="MISE_TASK",
                    verified=True,
                    evidence="mise.toml:1",
                )
            ]
        )


# ---------------------------------------------------------------------------
# 2. An unverified edge round-trips AS unverified
# ---------------------------------------------------------------------------


def test_an_unverified_edge_survives_to_chunk_still_marked_unverified() -> None:
    """Fails if `verified` is dropped from the emitted edge.

    A lower `confidence_score` alone is NOT sufficient: the whole point of the
    flag is that an edge a lane could not confirm is visibly unconfirmed, not
    merely ranked lower.
    """
    chunk = code_intel.to_chunk(
        [
            code_intel.Edge(
                source="task:mystery",
                target="cli:unknown",
                relation="invokes",
                provenance="MISE_TASK",
                verified=False,
                evidence="mise.toml:99",
            )
        ]
    )

    (edge,) = chunk["edges"]
    assert edge["verified"] is False
    assert edge["confidence_score"] < 1.0


# ---------------------------------------------------------------------------
# 3. Two lanes never collide on a bare name
# ---------------------------------------------------------------------------


def test_a_task_and_a_function_sharing_a_bare_name_get_different_ids() -> None:
    """`build` the task and `build` the function must not be one node."""
    chunk = code_intel.to_chunk(
        [
            code_intel.Edge(
                source="task:build",
                target="cli:build",
                relation="invokes",
                provenance="MISE_TASK",
                verified=True,
                evidence="mise.toml:1",
            ),
            code_intel.Edge(
                source="fn:build",
                target="config:pyproject.toml",
                relation="reads",
                provenance="CONFIG_READ",
                verified=True,
                evidence="python/src/kb_setup/graph.py:1",
            ),
        ]
    )

    ids = [n["id"] for n in chunk["nodes"]]
    assert len(ids) == len(set(ids)), "node ids collided"
    assert {"task:build", "fn:build"} <= set(ids)


def test_task_and_dispatch_lanes_use_disjoint_ids_for_the_same_bare_name(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The REAL lanes, not hand-built edges: a task AND a function both "build"."""

    class _Result:
        stdout = json.dumps([{"name": "build", "run": ["uv run kb-setup build"]}])

    def _fake_run(_argv: list[str], **_kwargs: object) -> _Result:
        return _Result()

    monkeypatch.setattr(code_intel.subprocess, "run", _fake_run)
    task_sources = {e.source for e in code_intel.task_edges(fake_repo)}
    dispatch_targets = {e.target for e in code_intel.dispatch_edges(fake_repo)}

    assert "task:build" in task_sources
    assert "fn:build" in dispatch_targets
    assert task_sources.isdisjoint(dispatch_targets), (
        f"bare name 'build' collided across layers: {task_sources} vs {dispatch_targets}"
    )


# ---------------------------------------------------------------------------
# 4. `mise tasks --json` runs with cwd=repo_root
# ---------------------------------------------------------------------------


def test_task_lane_runs_mise_from_the_repo_root_not_the_process_cwd(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts on the SUBPROCESS CALL, not on the output.

    Run from anywhere but the repo root, `mise tasks --json` returns mise's own
    bootstrap tasks rather than this repo's. The output looks perfectly
    plausible either way, which is why this asserts on `cwd` — an output-shaped
    test cannot see this bug at all.
    """
    seen_argv: list[str] = []
    seen_cwd: list[Path | None] = []

    class _Result:
        stdout = "[]"

    def _fake_run(argv: list[str], **kwargs: object) -> _Result:
        seen_argv.extend(argv)
        cwd = kwargs.get("cwd")
        seen_cwd.append(cwd if isinstance(cwd, Path) else None)
        return _Result()

    monkeypatch.setattr(code_intel.subprocess, "run", _fake_run)
    code_intel.task_edges(fake_repo)

    assert seen_cwd == [fake_repo], f"mise ran with cwd={seen_cwd!r}"
    assert "tasks" in seen_argv
    assert "--json" in seen_argv


# ---------------------------------------------------------------------------
# 5. A lane that ran and found nothing is distinguishable from one that did not
# ---------------------------------------------------------------------------


def test_run_lanes_reports_a_lane_that_ran_and_found_nothing(fake_repo: Path) -> None:
    """`ty` is stubbed and returns []. It must still report as HAVING RUN.

    A silent zero and an absent lane are the same shape in a flat edge list,
    and this repo treats that conflation as a defect in its own right.
    """
    runs = {r.name: r for r in code_intel.run_lanes(fake_repo, ["ty"])}

    assert "ty" in runs, "the stubbed lane vanished instead of reporting"
    assert runs["ty"].edges == ()


def test_requesting_an_unknown_lane_raises_a_value_error_naming_the_known_lanes(
    fake_repo: Path,
) -> None:
    """`ValueError` specifically, and the message must name the known set.

    An earlier version of this test accepted `(ValueError, KeyError)` and was
    therefore incapable of failing: delete the explicit guard and the dict
    lookup raises `KeyError` on the very next line, so the test passed over a
    module with no guard at all. A mutation arm caught it (A7 SURVIVED).

    The distinction is not pedantry. `KeyError: 'no-such-lane'` tells a caller
    nothing; the guard's message names every lane that does exist, which is the
    difference between a dead end and a usable refusal.
    """
    with pytest.raises(ValueError, match="known lanes") as excinfo:
        code_intel.run_lanes(fake_repo, ["no-such-lane"])

    message = str(excinfo.value)
    assert "no-such-lane" in message, "the refusal does not name what was asked for"
    for known in ("task", "skill", "dispatch", "config", "ty"):
        assert known in message, f"the refusal omits the known lane {known!r}"


# ---------------------------------------------------------------------------
# 6. The end-to-end shape the CLI writes
# ---------------------------------------------------------------------------


def test_code_intel_main_writes_json_that_parses(fake_repo: Path, tmp_path: Path) -> None:
    out = tmp_path / "edges.json"
    rc = code_intel.code_intel_main(fake_repo, ["--lanes", "skill", "--out", str(out)])

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload, "wrote an empty document"
