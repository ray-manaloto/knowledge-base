# Copyright (c) 2026 Raymond Manaloto
"""The real-graph tests are serialised onto one xdist worker (#838).

Two halves have to agree, and neither does anything alone: the `xdist_group`
mark on each test that parses `graphify-out/graph.json`, and `--dist loadgroup`
on the `test` task. Under xdist's default `load` the mark is ignored, so
deleting the flag silently restores four concurrent ~4 GB graph parses and the
timeouts they caused, while every test still passes when run alone.
"""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

import pytest
import test_affected_covers_tests
import test_eval_cases
import test_mcp_serve

ROOT = Path(__file__).resolve().parents[1]
GROUP = "real_graph"

#: Every test that loads the real aggregate graph, measured 2026-10-02 by
#: `--durations` over the suite's graph-touching modules: all four take 11-31 s
#: alone, and nothing else in those modules takes more than 5 s.
REAL_GRAPH_TESTS = (
    (test_mcp_serve, "test_kb_serve_actually_answers_mcp"),
    (test_eval_cases, "test_the_real_offline_run_is_green_on_this_tree"),
    (test_affected_covers_tests, "test_affected_can_return_test_nodes_at_all"),
    (test_affected_covers_tests, "test_affected_names_the_tests_that_cover_our_own_code"),
)


def _groups(module: object, name: str) -> list[object]:
    marks = list(getattr(getattr(module, name), "pytestmark", []))
    module_marks = getattr(module, "pytestmark", [])
    marks += module_marks if isinstance(module_marks, list) else [module_marks]
    return [m.args[0] for m in marks if m.name == "xdist_group" and m.args]


@pytest.mark.parametrize(("module", "name"), REAL_GRAPH_TESTS)
def test_each_real_graph_test_is_in_the_group(module: object, name: str) -> None:
    assert _groups(module, name) == [GROUP], f"{name} must carry xdist_group({GROUP!r})"


def test_the_test_task_schedules_by_group() -> None:
    task = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))["tasks"]["test"]
    argv = shlex.split(task["run"])
    assert "-n" in argv, "the group only matters under xdist"
    dist = argv[argv.index("--dist") + 1] if "--dist" in argv else "load (default)"
    assert dist == "loadgroup", f"--dist is {dist}: xdist ignores the xdist_group mark"
