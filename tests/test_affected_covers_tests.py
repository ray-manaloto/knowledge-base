"""The `#101` depth test: can `affected` name the tests that cover OUR code?

WHY THIS TEST IS ARTIFACT-LEVEL, AND WHY IT HAS TO BE. Every other test of the
self-extraction path stubs `graph._run`, so it asserts on the argv graphify
would have been given. That is the right shape for "which subcommand runs", and
it is structurally incapable of catching this defect: the bug is not in the
argv, it is in what `merge-graphs` does to node ids AFTER two separate
extraction runs. `test_refresh_self_uses_one_extraction_path` says so in its own
docstring — "the artifact-level consequence is verified out-of-band by
rebuilding and re-running `affected`, which no stubbed test can do". This file
is that out-of-band check, brought in-band.

THE DEFECT. `python/` and `tests/` were extracted as TWO runs, and
`merge-graphs` re-namespaces ids per merge, so the halves land in disjoint
namespaces (`knowledge-base::python::…` vs `tests::…`) that no edge can span.
Measured before the fix: 3,368 tests-touching edges, **0** crossing into
`python::`, against a control of 2,194 within `python/`.

BOTH ARMS RUN HERE. A test that only ever asserts the positive would pass just
as happily against a graphify that had stopped resolving symbols at all, so the
control arm asserts that `affected` CAN return nodes under `tests/` — using a
test-side symbol, whose callers are tests within one namespace and therefore
reachable even while the defect is present. If the control fails, the failure is
in the tool or the graph, not in what this test is about, and it says so.

SKIPPING IS NOT PASSING. `graphify-out/graph.json` is derived and gitignored, so
a fresh clone has none and this test cannot run. It skips there — loudly, naming
the command that would produce the graph — because a skip that reads as a pass
is the failure mode this repo has paid for most often. The skip is the ONLY
tolerated non-answer: a graph that exists but cannot be probed is a failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kb_setup.graphify_env import clean_env, graphify_exe

#: A symbol defined under `python/src/kb_setup/` that tests really do reference.
#:
#: THIS TARGET WAS CHANGED ONCE, AND THE REASON MATTERS more than the target.
#: It was `build_index`, chosen because `grep -rl build_index tests/` finds it.
#: After the one-root rebuild it STILL returned no test node — and the census
#: below showed why: `build_index` has no crossing edge even INSIDE the single
#: extraction, where no merge namespacing exists to lose one. Tests call it as
#: `lexical.build_index(...)`, module-qualified, and graphify's extractor does
#: not resolve that form back to the `build_index()` node. So the original
#: target could never have exhibited the defect this file is about, in either
#: direction — it was a broken probe, not a failing capability.
#:
#: Changing a probe target until it passes is the Goodhart move, so the
#: distinction is stated rather than assumed: the sub-graph census went from
#: **0** crossing edges before the change to **314** after it (234 `calls`, 57
#: `imports_from`, 22 `references`, 1 `indirect_call`), against controls of
#: 1,952 within `python/` and 2,857 within `tests/`. The capability moved; the
#: probe was re-aimed at a symbol that can observe it.
_OUR_SYMBOL = "check_goal"

#: KNOWN LIMITATION, recorded here because a green test would otherwise imply
#: more than it proves: `affected` resolves DIRECT calls (`check_goal(...)`,
#: 18 test functions; `audit_transcripts(...)`, 11) and does NOT resolve
#: module-qualified ones (`lexical.build_index(...)`, 0). So "which tests cover
#: this symbol" is answerable for our code, not universally answerable. Do not
#: read a pass here as full coverage-query support.
_UNRESOLVED_CALL_STYLE = "build_index"

#: A symbol whose callers are test functions in the SAME namespace. This is the
#: control: it is reachable with or without the one-root fix, so it separates
#: "the crossing is broken" from "nothing resolves at all".
_TEST_SIDE_SYMBOL = "_state"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GRAPH = _REPO_ROOT / "graphify-out" / "graph.json"


def _affected(symbol: str) -> str:
    """Run `graphify affected <symbol>` against the aggregate graph.

    Read-only introspection with no mise-task equivalent, which is exactly the
    category `mise-tasks-only.md` leaves direct. `clean_env()` keeps every
    non-Claude backend trigger out of the subprocess, as every graphify call in
    this repo must.
    """
    proc = subprocess.run(
        [str(graphify_exe(_REPO_ROOT)), "affected", symbol, "--graph", str(_GRAPH)],
        cwd=_REPO_ROOT,
        env=clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout


def _lines_under_tests(output: str) -> list[str]:
    """Returned nodes whose location is a test module.

    `affected` prints one `- <label> [<relation>] <file>:<line>` per node, so a
    test node is one whose file component names a `test_*.py`. Matching on the
    filename rather than on a `tests/` path prefix is deliberate: the path a node
    carries depends on the extraction root, and this test must not silently
    change meaning when that root does.
    """
    return [line for line in output.splitlines() if line.startswith("- ") and "test_" in line]


@pytest.fixture(scope="module")
def _graph_present() -> None:
    if not _GRAPH.is_file():
        pytest.skip(
            f"no {_GRAPH.relative_to(_REPO_ROOT)} — this is the derived aggregate graph, "
            f"absent in a fresh clone. Run `mise run kb-build` to produce it. "
            f"THIS SKIP IS NOT A PASS: the coverage claim is unverified here."
        )


@pytest.mark.usefixtures("_graph_present")
def test_affected_can_return_test_nodes_at_all() -> None:
    """CONTROL ARM. Without it the test below is a coin with one face.

    A graphify that resolved nothing, a graph that failed to build, or a
    `--graph` path typo would each make the real assertion fail for a reason that
    has nothing to do with `#101`. This arm fails first and names that.
    """
    hits = _lines_under_tests(_affected(_TEST_SIDE_SYMBOL))
    assert hits, (
        f"`affected {_TEST_SIDE_SYMBOL}` returned no test node, so this probe cannot "
        f"produce a positive at all. Fix the graph or the tool before reading the "
        f"companion test's result as evidence about #101."
    )


@pytest.mark.usefixtures("_graph_present")
def test_affected_names_the_tests_that_cover_our_own_code() -> None:
    """#101. FAILS at HEAD before the one-extraction-root change — by design.

    Realistic break, once this passes: someone splits self-extraction back into
    one run per tree as an optimisation, which is how the two-root arrangement
    arrived in the first place. That break is invisible to every argv-level test
    and shows up only here.
    """
    output = _affected(_OUR_SYMBOL)
    hits = _lines_under_tests(output)
    assert hits, (
        f"`affected {_OUR_SYMBOL}` returned no test node. Tests DO reference it, and "
        f"the control arm proves `affected` can return test nodes, so the tests and "
        f"the source are in namespaces no edge spans — #101. Output was:\n{output}"
    )
