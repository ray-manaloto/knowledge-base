"""Tests for kb_setup.gates — run the gates, record what actually happened.

Every behavioural assertion here is PAIRED with a control arm, because the
subject is a recorder: a test that only ever sees a green run cannot tell a
recorder from a stub that writes "pass".

The two flag positions (#146's criterion 7) are tested against the SAME gate
list and the SAME failure, so the only variable is the flag.

`head_sha` is pinned rather than `run()` being handed a sha. Passing one in
would have made every result carry it by construction, so the drift detector
`render` exists for could never fire and its test would have been asserting on
dead code — the fixture-shaped-test failure this repo has already paid for once.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Never

from kb_setup import gates, pr

_MISE = "mise.toml"

_SHA = "a" * 40

# Two gates that pass, one that fails, one after it. Enough to tell "stopped
# early" from "ran everything", which a list with the failure LAST cannot do:
# there, both flag positions produce identical output.
_TASKS = ("alpha", "beta", "gamma", "delta")
_FAILING = "beta"


def _repo(tmp_path: Path, tasks: tuple[str, ...] = _TASKS) -> Path:
    """A repo root whose `mise.toml` declares ``tasks``."""
    body = "".join(f'[tasks.{t}]\nrun = "true"\n\n' for t in tasks)
    (tmp_path / _MISE).write_text(body, encoding="utf-8")
    return tmp_path


def _pin_sha(monkeypatch, *shas: str) -> None:
    """Pin `head_sha`. Several values are yielded in turn, then the last repeats."""
    seq = list(shas) or [_SHA]

    def head(_root: Path) -> str:
        return seq.pop(0) if len(seq) > 1 else seq[0]

    monkeypatch.setattr(gates, "head_sha", head)


def _stub(monkeypatch, *, failing: str = _FAILING, seen: list | None = None) -> None:
    """Route gates' subprocess.run through a stub; ``failing`` exits 1."""

    def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        if seen is not None:
            seen.append((list(cmd), kwargs))
        # stdout="" because `run` also shells out to git for `tree_dirty`, and a
        # CompletedProcess with stdout=None is not what a captured call returns.
        return subprocess.CompletedProcess(cmd, 1 if cmd[-1] == failing else 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)


def _never_runs(monkeypatch) -> list:
    """Stub subprocess.run to RECORD, so a test can assert nothing invoked it."""
    calls: list = []

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    return calls


def _mise(seen: list) -> list:
    """Only the gate invocations.

    `run` also calls git for `tree_dirty`, so an index into the raw list picks
    up `git status` rather than the gate.
    """
    return [entry for entry in seen if entry[0][0] == "mise"]


def _written(root: Path) -> list[Path]:
    return list((root / ".agent" / "kb" / "gates").glob("*.json"))


def _rows(path: Path) -> dict:
    return {r["task"]: r for r in json.loads(path.read_text(encoding="utf-8"))["gates"]}


# --------------------------------------------------------------------------
# GateResult — the "not run is not a pass" contract
# --------------------------------------------------------------------------


def test_a_gate_that_never_ran_has_not_passed():
    """Asserted DIRECTLY on the dataclass, because no end-to-end path reaches it.

    `stopped` is only ever set after a gate fails, so today an unrun gate always
    travels beside a failing one and `all(r.passed for r in ...)` is already
    False via that gate. A mutation making `passed` accept None therefore
    survived every behavioural test here — the property was defensive code with
    a docstring asserting a contract nothing could check.

    Deleting it would make the next state that produces an unrun gate without a
    preceding failure (a "not applicable here" skip, say) pass silently. So the
    contract stays and is pinned at the only level that can see it.
    """
    assert gates.GateResult("x", None, None, None).passed is False
    assert gates.GateResult("x", None, None, None).ran is False


def test_a_gate_that_exited_zero_has_passed():
    """CONTROL ARM — the same property over the state that IS a pass."""
    assert gates.GateResult("x", 0, _SHA, "t").passed is True
    assert gates.GateResult("x", 1, _SHA, "t").passed is False


# --------------------------------------------------------------------------
# run() — the stop-on-failure flag, both positions (criterion 3 + 7)
# --------------------------------------------------------------------------


def test_run_without_stop_records_every_gate_after_a_failure(monkeypatch, tmp_path):
    """stop_on_failure=False: the gate AFTER the failure still has a real rc."""
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    results = gates.run(_repo(tmp_path), _TASKS, stop_on_failure=False)
    assert [r.task for r in results] == list(_TASKS)
    assert [r.rc for r in results] == [0, 1, 0, 0]
    # The point of the flag: nothing is left unknown.
    assert all(r.finished_at for r in results)


def test_run_with_stop_leaves_later_gates_unrun(monkeypatch, tmp_path):
    """CONTROL ARM for the test above — same list, same failure, flag flipped."""
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    results = gates.run(_repo(tmp_path), _TASKS, stop_on_failure=True)
    # Every requested gate is still PRESENT, so a partial run cannot read as a
    # complete one by omission. What differs is that the tail has no rc.
    assert [r.task for r in results] == list(_TASKS)
    assert [r.rc for r in results] == [0, 1, None, None]
    assert [r.finished_at for r in results][2:] == [None, None]


def test_run_all_green_is_identical_under_both_flags(monkeypatch, tmp_path):
    """The flag must change NOTHING when no gate fails."""
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    root = _repo(tmp_path)
    off = gates.run(root, _TASKS, stop_on_failure=False)
    on = gates.run(root, _TASKS, stop_on_failure=True)
    assert [(r.task, r.rc) for r in off] == [(r.task, r.rc) for r in on]
    assert [r.rc for r in on] == [0, 0, 0, 0]


def test_run_stops_invoking_after_a_failure(monkeypatch, tmp_path):
    """`rc=None` must mean "not invoked", not "invoked and discarded".

    Asserted on the subprocess calls rather than on the returned rows: a
    recorder that ran everything and then blanked the tail would satisfy the
    row-shape assertions above while costing the ship path the minutes the flag
    exists to save.
    """
    seen: list = []
    _stub(monkeypatch, seen=seen)
    _pin_sha(monkeypatch)
    gates.run(_repo(tmp_path), _TASKS, stop_on_failure=True)
    assert [c[0][-1] for c in _mise(seen)] == ["alpha", "beta"]


def test_run_invokes_the_gate_task_unwrapped(monkeypatch, tmp_path):
    """Criterion 8: the gate is invoked exactly as `ship` invokes it today.

    `mise run <task>` and nothing else — no shell, and no `capture_output`,
    which would take away the live output the criterion protects. This is the
    arm that fails if someone "improves" the runner into a capturing wrapper.
    """
    seen: list = []
    _stub(monkeypatch, failing="__none__", seen=seen)
    _pin_sha(monkeypatch)
    gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    cmd, kwargs = _mise(seen)[0]
    assert cmd == ["mise", "run", "alpha"]
    assert kwargs.get("capture_output") is None
    assert kwargs.get("stdout") is None
    assert kwargs.get("shell") is None


def test_run_records_the_head_it_observed(monkeypatch, tmp_path):
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch, "b" * 40)
    results = gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    assert results[0].sha == "b" * 40


def test_run_reads_head_per_gate_so_a_mid_run_amend_is_visible(monkeypatch, tmp_path):
    """HEAD is captured per gate, not once — the arm that makes drift detectable."""
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch, "a" * 40, "c" * 40)
    results = gates.run(_repo(tmp_path), ("alpha", "beta"), stop_on_failure=False)
    assert [r.sha for r in results] == ["a" * 40, "c" * 40]


def test_run_writes_nothing(monkeypatch, tmp_path):
    """Criterion 2: running is usable WITHOUT recording."""
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    root = _repo(tmp_path)
    gates.run(root, _TASKS, stop_on_failure=False)
    assert not (root / ".agent").exists()


def test_run_survives_a_runner_that_cannot_start(monkeypatch, tmp_path):
    """An OSError is a gate that did not pass, not a crash out of the runner."""

    def boom(_cmd: list[str], **_kwargs: object) -> Never:
        raise OSError("mise: not found")

    monkeypatch.setattr(gates.subprocess, "run", boom)
    _pin_sha(monkeypatch)
    results = gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    assert results[0].rc not in (0, None)


# --------------------------------------------------------------------------
# record() — the durable artifact (criterion 1 + 2)
# --------------------------------------------------------------------------


def _results() -> list[gates.GateResult]:
    return [
        gates.GateResult("alpha", 0, _SHA, "2026-08-04T10:00:00+00:00", dirty=False),
        gates.GateResult("beta", 1, _SHA, "2026-08-04T10:01:00+00:00", dirty=False),
        gates.GateResult("gamma", None, None, None, dirty=None),
    ]


def test_record_writes_every_field_the_ticket_names(tmp_path):
    """Criterion 1: task name, exit code, the commit, and when it finished."""
    path = gates.record(tmp_path, _results(), sha=_SHA)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sha"] == _SHA
    rows = {r["task"]: r for r in data["gates"]}
    assert rows["alpha"]["rc"] == 0
    assert rows["beta"]["rc"] == 1
    assert rows["alpha"]["sha"] == _SHA
    assert rows["alpha"]["finished_at"] == "2026-08-04T10:00:00+00:00"
    # The fifth field, beyond the ticket's four — without it "rc=0 at <sha>" can
    # be recorded for a tree that was never that commit.
    assert rows["alpha"]["dirty"] is False


def test_run_records_whether_the_tree_was_dirty(monkeypatch, tmp_path):
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "tree_dirty", lambda _root: True)
    results = gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    assert results[0].dirty is True


def test_run_records_a_clean_tree_as_clean(monkeypatch, tmp_path):
    """CONTROL ARM for the test above."""
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "tree_dirty", lambda _root: False)
    results = gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    assert results[0].dirty is False


def test_tree_dirty_reads_a_real_repo(tmp_path, commit_file):
    """The real git call, both arms — a stub here would only confirm the stub."""
    commit_file("a.txt")
    assert gates.tree_dirty(tmp_path) is False
    (tmp_path / "a.txt").write_text("changed\n", encoding="utf-8")
    assert gates.tree_dirty(tmp_path) is True


def test_tree_dirty_is_unknown_outside_a_repo(tmp_path):
    """Not-a-repo is "could not ask", which must not read as clean."""
    assert gates.tree_dirty(tmp_path) is None


def test_record_keeps_an_unrun_gate_visible_as_unrun(tmp_path):
    """A stopped run must not read as a complete one.

    The control arm for the row above: `gamma` is PRESENT with a null rc, so a
    reader auditing a handoff can tell "did not run" from "passed". Dropping it
    would be the "could not check rendered as green" failure, in the artifact.
    """
    rows = _rows(gates.record(tmp_path, _results(), sha=_SHA))
    assert "gamma" in rows
    assert rows["gamma"]["rc"] is None


def test_record_is_keyed_by_sha(tmp_path):
    a = gates.record(tmp_path, _results(), sha=_SHA)
    b = gates.record(tmp_path, _results(), sha="b" * 40)
    assert a != b
    assert a.exists()
    assert b.exists()
    assert _SHA in a.name


def test_record_runs_nothing(monkeypatch, tmp_path):
    """Criterion 2: recording is usable WITHOUT running."""
    calls = _never_runs(monkeypatch)
    gates.record(tmp_path, _results(), sha=_SHA)
    assert calls == []


def test_record_survives_an_empty_result_list(tmp_path):
    """No gates is a real state (an empty gate list); it must not crash."""
    path = gates.record(tmp_path, [], sha=_SHA)
    assert json.loads(path.read_text(encoding="utf-8"))["gates"] == []


# --------------------------------------------------------------------------
# undeclared() — criterion 5
# --------------------------------------------------------------------------


def test_undeclared_names_a_gate_this_repo_does_not_declare(tmp_path):
    assert gates.undeclared(_repo(tmp_path, ("alpha",)), ("alpha", "nope")) == ("nope",)


def test_undeclared_is_empty_when_every_gate_is_declared(tmp_path):
    """CONTROL ARM — the same call shape over a list that IS declared."""
    assert gates.undeclared(_repo(tmp_path, ("alpha", "beta")), ("alpha", "beta")) == ()


def test_undeclared_fails_closed_with_no_mise_toml(tmp_path):
    """No declarations to check against is not "everything is fine"."""
    assert gates.undeclared(tmp_path, ("alpha",)) == ("alpha",)


def test_undeclared_accepts_a_task_alias(tmp_path):
    """`resolve.declared_tasks` reads aliases; the gate list may name one."""
    (tmp_path / _MISE).write_text('[tasks.alpha]\nalias = "a"\nrun = "true"\n', encoding="utf-8")
    assert gates.undeclared(tmp_path, ("a",)) == ()


# --------------------------------------------------------------------------
# main() — the task's exit code (criterion 6)
# --------------------------------------------------------------------------


def test_main_exits_non_zero_when_a_gate_fails(monkeypatch, tmp_path, capsys):
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    assert gates.main([], _repo(tmp_path)) == 1
    capsys.readouterr()


def test_main_exits_zero_when_every_gate_passes(monkeypatch, tmp_path, capsys):
    """CONTROL ARM for the test above."""
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    assert gates.main([], _repo(tmp_path)) == 0
    capsys.readouterr()


def test_main_records_even_though_the_run_failed(monkeypatch, tmp_path, capsys):
    """The whole ticket: a failed run must still leave the artifact behind."""
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    root = _repo(tmp_path)
    gates.main([], root)
    capsys.readouterr()
    assert len(_written(root)) == 1
    # Ran to the end despite the failure — this task does NOT stop on failure.
    assert _rows(_written(root)[0])["delta"]["rc"] == 0


def test_main_refuses_an_undeclared_gate_without_running_anything(monkeypatch, tmp_path, capsys):
    """Criterion 5, and it must refuse BEFORE spending a gate run."""
    calls = _never_runs(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", ("alpha", "nope"))
    assert gates.main([], _repo(tmp_path, ("alpha",))) == 2
    assert calls == []
    assert "nope" in capsys.readouterr().err


def test_main_refuses_an_undeclared_gate_named_on_the_command_line(monkeypatch, tmp_path, capsys):
    """The validation follows the LIST, not the default constant."""
    calls = _never_runs(monkeypatch)
    _pin_sha(monkeypatch)
    assert gates.main(["nope"], _repo(tmp_path, ("alpha",))) == 2
    assert calls == []
    capsys.readouterr()


def test_main_refuses_an_unknown_flag(monkeypatch, tmp_path, capsys):
    """A flag the command does not know is a request that cannot be honoured.

    `--stop-on-failure` is the realistic spelling to get wrong: it is what the
    acceptance criterion calls this flag. It is dropped from the task list by the
    `startswith("-")` filter AND fails the `--stop` test, so without this guard
    the run silently took the OPPOSITE position of the only flag this command has
    and exited 0/1 as though that was what was asked for. (Spec lane.)
    """
    calls = _never_runs(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    assert gates.main(["--stop-on-failure"], _repo(tmp_path)) == 2
    assert calls == []
    assert "--stop-on-failure" in capsys.readouterr().err


def test_main_accepts_the_flag_it_documents(monkeypatch, tmp_path, capsys):
    """CONTROL ARM — the correctly spelled flag is not refused, and stops."""
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    root = _repo(tmp_path)
    assert gates.main(["--stop"], root) == 1
    capsys.readouterr()
    assert _rows(_written(root)[0])["gamma"]["rc"] is None


def test_main_refuses_when_head_is_unreadable(monkeypatch, tmp_path, capsys):
    """A record that cannot name its commit is not the artifact #146 asks for."""
    calls = _never_runs(monkeypatch)
    _pin_sha(monkeypatch, "")
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    assert gates.main([], _repo(tmp_path)) == 2
    assert calls == []
    capsys.readouterr()


def test_main_can_be_pointed_at_a_subset(monkeypatch, tmp_path, capsys):
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    root = _repo(tmp_path)
    assert gates.main(["alpha"], root) == 0
    capsys.readouterr()
    data = json.loads(_written(root)[0].read_text(encoding="utf-8"))
    assert [r["task"] for r in data["gates"]] == ["alpha"]


# --------------------------------------------------------------------------
# render() — the report a human reads
# --------------------------------------------------------------------------


def test_render_flags_a_sha_that_moved_mid_run():
    """HEAD moving during the gates makes the record's key partly untrue."""
    results = [
        gates.GateResult("alpha", 0, _SHA, "2026-08-04T10:00:00+00:00"),
        gates.GateResult("beta", 0, "c" * 40, "2026-08-04T10:01:00+00:00"),
    ]
    assert "moved" in gates.render(results, sha=_SHA, path=Path("x.json")).lower()


def test_render_does_not_cry_wolf_when_the_sha_held():
    """CONTROL ARM — the same shape with one commit throughout."""
    results = [
        gates.GateResult("alpha", 0, _SHA, "2026-08-04T10:00:00+00:00"),
        gates.GateResult("beta", 0, _SHA, "2026-08-04T10:01:00+00:00"),
    ]
    assert "moved" not in gates.render(results, sha=_SHA, path=Path("x.json")).lower()


def test_render_says_when_the_tree_was_dirty():
    """A green gate over uncommitted changes is not a fact about the commit."""
    results = [gates.GateResult("alpha", 0, _SHA, "t", dirty=True)]
    assert "uncommitted" in gates.render(results, sha=_SHA, path=Path("x.json")).lower()


def test_render_is_silent_when_the_tree_was_clean():
    """CONTROL ARM — the same shape over a clean tree."""
    results = [gates.GateResult("alpha", 0, _SHA, "t", dirty=False)]
    out = gates.render(results, sha=_SHA, path=Path("x.json")).lower()
    assert "uncommitted" not in out
    assert "could not tell" not in out


def test_render_distinguishes_unknown_cleanliness_from_clean():
    """`dirty=None` is "could not ask", which must not render as the clean answer."""
    results = [gates.GateResult("alpha", 0, _SHA, "t", dirty=None)]
    assert "could not tell" in gates.render(results, sha=_SHA, path=Path("x.json")).lower()


def test_render_names_unrun_gates_in_the_summary():
    """Asserted on the SUMMARY line, not on the output as a whole.

    The first version checked `"gamma" in out`, which `render`'s per-gate row
    satisfies no matter what the summary says — so dropping the named list from
    the summary passed all 42 tests. A blind test in the suite whose own report
    is about blind tests; found by the standards review lane, which mutated the
    clause and showed the survival, and re-confirmed here before the fix.
    """
    out = gates.render(_results(), sha=_SHA, path=Path("x.json"))
    summary = next(line for line in out.splitlines() if "passed," in line)
    assert "not run (gamma)" in summary
    assert "1 passed, 1 failed" in summary


# --------------------------------------------------------------------------
# the ship path delegates to the same two functions (criterion 4)
# --------------------------------------------------------------------------


def test_ship_gate_runner_delegates_and_records(monkeypatch, tmp_path):
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", ("alpha",))
    root = _repo(tmp_path, ("alpha",))
    assert pr.run_gates(root) is True
    assert len(_written(root)) == 1


def test_ship_gate_runner_stops_and_still_records(monkeypatch, tmp_path):
    """CONTROL ARM — a failing gate returns False, and the record survives it."""
    _stub(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", _TASKS)
    root = _repo(tmp_path)
    assert pr.run_gates(root) is False
    rows = _rows(_written(root)[0])
    # Stopped: the ship path has nothing to gain by continuing past a red gate.
    assert rows["beta"]["rc"] == 1
    assert rows["gamma"]["rc"] is None


def test_ship_gate_runner_refuses_an_unreadable_head(monkeypatch, tmp_path, capsys):
    """The ship path must make the SAME refusal `kb-gates` makes.

    It did not. `pr.run_gates` open-coded the sequence and skipped the empty-sha
    guard, so a ship with an unreadable HEAD wrote `gates-.json` carrying
    `"sha": ""` — a file that reads as a gate record and names no commit. Found
    independently by both review lanes; the fix gave the sequence one owner.
    """
    calls = _never_runs(monkeypatch)
    _pin_sha(monkeypatch, "")
    monkeypatch.setattr(gates, "GATE_TASKS", ("alpha",))
    root = _repo(tmp_path, ("alpha",))
    assert pr.run_gates(root) is False
    assert calls == []
    assert not _written(root)
    capsys.readouterr()


def test_ship_gate_runner_refuses_an_undeclared_gate(monkeypatch, tmp_path, capsys):
    calls = _never_runs(monkeypatch)
    _pin_sha(monkeypatch)
    monkeypatch.setattr(gates, "GATE_TASKS", ("alpha", "nope"))
    assert pr.run_gates(_repo(tmp_path, ("alpha",))) is False
    assert calls == []
    capsys.readouterr()


# --------------------------------------------------------------------------
# the shipped constants, against the REAL repo
# --------------------------------------------------------------------------


def test_ship_gates_are_the_repo_s_real_declared_tasks():
    """The shipped constant, checked against the REAL mise.toml.

    Every other test here builds a synthetic repo, so all of them would still
    pass if `GATE_TASKS` named something this repo does not declare.
    """
    root = Path(__file__).resolve().parents[1]
    assert gates.undeclared(root, gates.GATE_TASKS) == ()


def test_the_kb_gates_task_is_declared():
    root = Path(__file__).resolve().parents[1]
    assert gates.undeclared(root, ("kb-gates",)) == ()
