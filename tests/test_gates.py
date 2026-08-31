# Copyright (c) 2026 Raymond Manaloto
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
import threading
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Never

import pytest
from kb_setup import atomic, gates, pr
from kb_setup.result import Err, Ok, Rc, exit_code

_MISE = "mise.toml"

_SHA = "a" * 40

# Two gates that pass, one that fails, one after it. Enough to tell "stopped
# early" from "ran everything", which a list with the failure LAST cannot do:
# there, both flag positions produce identical output.
_TASKS = ("alpha", "beta", "gamma", "delta")
_FAILING = "beta"


def _repo(tmp_path: Path, tasks: tuple[str, ...] = _TASKS) -> Path:
    """A repo root whose `mise.toml` declares ``tasks``."""
    tmp_path.mkdir(parents=True, exist_ok=True)
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


def test_an_interrupt_still_records_the_gates_that_finished(monkeypatch, tmp_path):
    """Ctrl-C partway through must not take the completed gates' evidence with it.

    The likeliest way a real run ends early — it takes minutes — and the one the
    module exists to survive. `KeyboardInterrupt` is a `BaseException`, so it was
    caught by nothing and propagated out of the result-building loop before
    anything was written. (Cold lane, P2.)
    """
    calls: list[str] = []

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] != "mise":
            return subprocess.CompletedProcess(cmd, 0, "")
        calls.append(cmd[-1])
        if cmd[-1] == "gamma":
            raise KeyboardInterrupt
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)
    root = _repo(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        gates.run_and_record(root, _TASKS, stop_on_failure=False)

    # The interrupt still propagates — this records, it does not swallow.
    rows = _rows(_written(root)[0])
    assert rows["alpha"]["rc"] == 0
    assert rows["beta"]["rc"] == 0
    # Every requested gate is PADDED, not absent: a short list would read as a
    # complete run over fewer gates.
    assert set(rows) == set(_TASKS)
    # `gamma` was IN FLIGHT (the stub records the call before raising) and
    # `delta` was never reached. Both are `rc: null`, and that is now an honest
    # record rather than a false one, because `ran` claims only "produced a
    # result" — the two are genuinely indistinguishable from here, so the record
    # must not assert the stronger "never invoked". (Cold lane round 2.)
    assert "gamma" in calls
    assert rows["gamma"]["rc"] is None
    assert rows["delta"]["rc"] is None
    assert gates.GateResult("gamma", None, None, None).ran is False


def test_a_clean_run_records_the_same_way(monkeypatch, tmp_path):
    """CONTROL ARM — the same call with no interrupt records all four with real rcs."""
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    root = _repo(tmp_path)
    gate_run, _summary = gates.run_and_record(root, _TASKS, stop_on_failure=False)
    assert gate_run is not None
    assert [r["rc"] for r in json.loads(_written(root)[0].read_text())["gates"]] == [0, 0, 0, 0]


def test_record_never_truncates_a_previous_record_in_place(tmp_path):
    """The write is temp-then-rename, so a reader never sees a half-written file.

    Asserted by making the RENAME fail: the destination must still hold the old
    record. A truncating `Path.write_text` would have destroyed it before failing.
    (Cold lane, P2.)
    """
    first = gates.record(tmp_path, _results(), sha=_SHA)
    before = first.read_text(encoding="utf-8")

    def boom(_self: Path, _target: Path) -> None:
        msg = "disk full"
        raise OSError(msg)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Path, "replace", boom)
        with pytest.raises(OSError, match="disk full"):
            gates.record(tmp_path, [gates.GateResult("z", 9, _SHA, "t")], sha=_SHA)

    assert first.read_text(encoding="utf-8") == before
    # And no debris left beside the real artifact.
    assert not list(first.parent.glob("*.tmp"))


def test_a_gate_whose_head_read_failed_is_not_bound_to_a_commit(monkeypatch, tmp_path):
    """A transiently-empty HEAD must not become a passing row bound to nothing.

    `render`'s drift check filters falsy shas by design, so the raw `""` produced
    a PASS with no commit and no warning. (Cold lane round 2, P2.)
    """
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch, "")
    results = gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    assert results[0].sha is None
    assert results[0].bound_to_a_commit is False
    out = gates.render(results, sha=_SHA, path=Path("x.json"))
    assert "could not read HEAD" in out


def test_a_gate_with_a_real_head_is_bound(monkeypatch, tmp_path):
    """CONTROL ARM — the same shape with git answering."""
    _stub(monkeypatch, failing="__none__")
    _pin_sha(monkeypatch)
    results = gates.run(_repo(tmp_path), ("alpha",), stop_on_failure=False)
    assert results[0].bound_to_a_commit is True
    assert "could not read HEAD" not in gates.render(results, sha=_SHA, path=Path("x.json"))


def test_tree_dirty_is_unknown_when_git_output_cannot_be_decoded(monkeypatch, tmp_path):
    """`text=True` decodes inside `subprocess.run`, so a non-UTF-8 path raises.

    `UnicodeDecodeError` is a `ValueError` — neither `OSError` nor
    `SubprocessError` — so it went straight past a handler whose entire contract
    is to return "unknown" instead of raising. (Cold lane round 2, P3.)
    """

    def boom(_cmd: list[str], **_kwargs: object) -> Never:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(gates.subprocess, "run", boom)
    assert gates.tree_dirty(tmp_path) is None


def test_atomic_temp_name_is_per_process(tmp_path):
    """Two writers must not share one temp inode.

    Pre-existing in `skill_eval` and inherited by the extraction; fixed here
    because this module now has a second caller whose concurrent case is
    plausible. (Cold lane round 2, P2.)
    """
    import os

    target = tmp_path / "x.json"
    atomic.write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"
    # The name must vary with the process, or concurrency has one shared inode.
    assert str(os.getpid()) in f"{target.name}.{os.getpid()}.tmp"
    assert not list(tmp_path.glob("*.tmp"))


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


def test_render_flags_a_pass_whose_outcome_is_skip():
    """`kb-manifest-audit`'s SKIP is the worked case: rc=0, outcome != OK.

    Without the visibility fix this reads as an ordinary PASS with nothing to
    tell a reader the gate did not actually check anything — the exact collapse
    the sidecar channel (`outcome`) exists to prevent, alive in the printed
    report rather than only in the JSON.
    """
    results = [gates.GateResult("alpha", 0, _SHA, "t", outcome="SKIP")]
    out = gates.render(results, sha=_SHA, path=Path("x.json"))
    assert "PASS" in out  # rc-based state is unchanged — this is additive
    assert "alpha=SKIP" in out


def test_render_does_not_flag_an_ok_outcome():
    """CONTROL ARM — a gate that recorded OK must not be singled out.

    Same shape as the SKIP case (rc=0, `outcome` set), so this proves the check
    reads the VALUE, not merely "is `outcome` set at all".
    """
    results = [gates.GateResult("alpha", 0, _SHA, "t", outcome="OK")]
    out = gates.render(results, sha=_SHA, path=Path("x.json"))
    assert "differs from a clean pass" not in out.lower()
    assert "alpha=OK" not in out


def test_render_is_silent_when_no_gate_wrote_an_outcome():
    """CONTROL ARM — the overwhelmingly common case: no sidecar at all."""
    results = [gates.GateResult("alpha", 0, _SHA, "t")]
    out = gates.render(results, sha=_SHA, path=Path("x.json"))
    assert "differs from a clean pass" not in out.lower()


def test_a_recorded_skip_reaches_the_printed_report_through_the_real_sidecar(monkeypatch, tmp_path):
    """The end-to-end path.

    A gate WRITES a sidecar, `_run_one` reads it back via :func:`read_sidecar_outcome`,
    and `render` must then flag it.

    This is the assertion the writer-side tests at `tests/test_manifest_audit.py`
    cannot make — those call `read_sidecar_outcome` directly and would pass even
    if `_run_one` never called it. Here the sidecar is written by the STUBBED
    gate itself (mirroring what `kb_setup.manifest_audit.main` does before it
    exits), and nothing in this test touches `read_sidecar_outcome` — so a dead
    wire at `_run_one`'s `outcome = read_sidecar_outcome(...)` call shows up as a
    silently-vanished `SKIP`, exactly as it would for a real ship run.
    """
    root = _repo(tmp_path, ("alpha",))

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] == "mise" and cmd[-1] == "alpha":
            gates.write_sidecar_outcome(root, "alpha", _SHA, "SKIP")
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    gate_run, _ = gates.run_and_record(root, ("alpha",), stop_on_failure=False)

    assert gate_run is not None
    out = gates.render(gate_run.results, sha=gate_run.sha, path=gate_run.path)
    assert "alpha=SKIP" in out


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


# ---------------------------------------------------- reading a record back ----
#
# The lookup half of #147. Every arm here is about the ONE question the checker
# asks — "is there a record for THIS commit" — and the answers that are not yes
# are kept apart, because a lookup that folds "no record" into "wrong record"
# hands the composer a two-state answer to a three-state question.


def _write_record(root: Path, sha: str, rows: list[gates.GateResult]) -> Path:
    return gates.record(root, rows, sha=sha)


def _ok(task: str, sha: str = _SHA) -> gates.GateResult:
    return gates.GateResult(task, 0, sha, "t", dirty=False)


def test_find_record_returns_the_record_written_for_that_sha(tmp_path):
    _write_record(tmp_path, _SHA, [_ok("lint")])
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert found.sha == _SHA
    assert [r.task for r in found.gates] == ["lint"]
    assert detail == ""


def test_find_record_matches_the_abbreviated_sha_a_handoff_writes():
    """Handoffs cite seven characters; the record is keyed by forty."""
    assert _SHA.startswith(_SHA[:7])


def test_find_record_accepts_an_abbreviated_sha(tmp_path):
    _write_record(tmp_path, _SHA, [_ok("lint")])
    found, _ = gates.find_record(tmp_path, _SHA[:7])
    assert found is not None
    assert found.sha == _SHA


def test_find_record_says_so_when_there_is_no_record_at_all(tmp_path):
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is None
    assert "no gate record" in detail


def test_find_record_does_not_return_a_record_from_another_commit(tmp_path):
    """The rejecting arm for criterion 3, at the lookup layer.

    A record keyed to another commit must not answer for this one, and the
    detail must NAME it — a reader who is told only "not found" while a
    `gates-*.json` sits in the directory will reach for it.
    """
    other = "b" * 40
    _write_record(tmp_path, other, [_ok("lint", other)])
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is None
    assert other[:12] in detail


def test_find_record_refuses_an_ambiguous_abbreviation(tmp_path):
    """Two records sharing a prefix: answering with either would be a guess."""
    _write_record(tmp_path, "abc1" + "0" * 36, [_ok("lint")])
    _write_record(tmp_path, "abc2" + "0" * 36, [_ok("lint")])
    found, detail = gates.find_record(tmp_path, "abc")
    assert found is None
    assert "2 records" in detail


def test_find_record_treats_an_unparsable_record_as_unreadable(tmp_path):
    path = tmp_path / gates.GATES_DIR / f"gates-{_SHA}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is None
    assert "could not read" in detail


def _write_raw(root: Path, sha: str, body: str) -> None:
    path = root / gates.GATES_DIR / f"gates-{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_find_record_treats_a_record_of_the_wrong_shape_as_unreadable(tmp_path):
    """Valid JSON is not a valid record — `gates` must be a list of objects."""
    _write_raw(tmp_path, _SHA, '{"sha": "x", "gates": "lint"}')
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is None
    assert "could not read" in detail


def test_find_record_treats_a_record_with_no_gates_key_as_unreadable(tmp_path):
    """A truncated record, and the arm the case above could not provide.

    `"gates": "lint"` is caught by the PER-ROW check further down, so removing
    the shape guard left that test green — a mutation masked by the next guard.
    With no `gates` key at all there is no row loop to reach: without the guard
    this iterates None and crashes, which is not one of the three answers.
    """
    _write_raw(tmp_path, _SHA, '{"sha": "x"}')
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is None
    assert "could not read" in detail


def test_find_record_treats_a_non_string_sha_as_unreadable(tmp_path):
    """The other half of the shape guard: `record.sha` is sliced by its readers."""
    _write_raw(tmp_path, _SHA, '{"sha": 5, "gates": []}')
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is None


def test_a_record_round_trips_every_field_the_checker_reads(tmp_path):
    """`rc`, `sha` and `dirty` all survive the write; None survives as None."""
    _write_record(tmp_path, _SHA, [gates.GateResult("lint", None, None, None, dirty=None)])
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    (row,) = found.gates
    assert (row.task, row.rc, row.sha, row.dirty) == ("lint", None, None, None)


def test_find_record_ignores_a_file_that_is_not_a_gate_record(tmp_path):
    """A stray file in the directory must not become an ambiguous match."""
    (tmp_path / gates.GATES_DIR).mkdir(parents=True, exist_ok=True)
    (tmp_path / gates.GATES_DIR / "notes.md").write_text("x", encoding="utf-8")
    _write_record(tmp_path, _SHA, [_ok("lint")])
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None


def test_row_returns_none_for_a_gate_the_record_does_not_cover(tmp_path):
    _write_record(tmp_path, _SHA, [_ok("lint")])
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert found.row("lint") is not None
    assert found.row("lint-docs") is None


def test_a_real_exit_code_still_parses(tmp_path):
    """Control arm for the test above — rejecting bools must not reject ints."""
    _write_raw(
        tmp_path,
        _SHA,
        json.dumps({"sha": _SHA, "gates": [{"task": "lint", "rc": 1, "sha": _SHA}]}),
    )
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert found.gates[0].rc == 1


def test_an_empty_row_sha_is_read_back_as_unknown(tmp_path):
    """Write-side `iter_run` already normalises `"" -> None`; the read side now agrees."""
    _write_raw(
        tmp_path,
        _SHA,
        json.dumps({"sha": _SHA, "gates": [{"task": "lint", "rc": 0, "sha": ""}]}),
    )
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert found.gates[0].sha is None


def test_a_record_with_an_empty_top_level_sha_is_unreadable(tmp_path):
    """`record()` never writes one, so an empty key is corruption, not a state."""
    _write_raw(tmp_path, _SHA, json.dumps({"sha": "", "gates": []}))
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is None


def test_rows_for_returns_every_matching_row(tmp_path):
    """The plural lookup is what makes a duplicate row visible to the caller."""
    _write_record(
        tmp_path, _SHA, [_ok("lint"), gates.GateResult("lint", 1, _SHA, "t", dirty=False)]
    )
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert [r.rc for r in found.rows_for("lint")] == [0, 1]


def test_a_malformed_rc_makes_the_whole_record_unreadable(tmp_path):
    """`"rc": true` must not be COERCED to the value an unreached gate carries.

    Normalising it to None made a corrupt row indistinguishable from "this gate
    did not run", so it went on to help confirm a runner claim of failure — the
    "could not read rendered as a state" collapse, one layer down. A record with
    a field of the wrong type is not a record.
    """
    _write_raw(
        tmp_path,
        _SHA,
        json.dumps({"sha": _SHA, "gates": [{"task": "lint", "rc": True, "sha": _SHA}]}),
    )
    found, detail = gates.find_record(tmp_path, _SHA)
    assert found is None
    assert "could not read" in detail


def test_a_null_rc_is_still_a_legitimate_row(tmp_path):
    """Control arm: an unreached gate really does carry `rc: null` (#146)."""
    _write_raw(
        tmp_path,
        _SHA,
        json.dumps({"sha": _SHA, "gates": [{"task": "lint", "rc": None, "sha": None}]}),
    )
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert found.gates[0].rc is None


def test_a_row_with_a_wrong_typed_dirty_is_unreadable(tmp_path):
    """The same rule for every field: present-but-wrong-typed is not a state."""
    _write_raw(
        tmp_path,
        _SHA,
        json.dumps({"sha": _SHA, "gates": [{"task": "lint", "rc": 0, "dirty": "yes"}]}),
    )
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is None


def test_an_absent_field_is_unknown_rather_than_malformed(tmp_path):
    """ABSENT and WRONG-TYPED are different: one is an omission, one is corruption."""
    _write_raw(tmp_path, _SHA, json.dumps({"sha": _SHA, "gates": [{"task": "lint", "rc": 0}]}))
    found, _ = gates.find_record(tmp_path, _SHA)
    assert found is not None
    assert (found.gates[0].sha, found.gates[0].dirty) == (None, None)


# --------------------------------------------------------------------------
# Concurrency (#248) — "parallel where safe, sequential where a step writes"
#
# Every test here is PAIRED, because concurrency has the same problem the
# recorder has: a runner that quietly stayed sequential passes any assertion
# about results, and a runner that quietly raced a writer passes any assertion
# about speed. So concurrency is proven by a BARRIER (which can only be crossed
# if the gates genuinely overlap) and exclusivity by a PEAK COUNTER (which a
# sequential runner can never push above 1). Neither can be satisfied by the
# other's implementation.
# --------------------------------------------------------------------------

#: Real gate names, because `CONCURRENT_SAFE` membership is what is under test.
#: The suite's other tests deliberately use invented names and therefore exercise
#: the EXCLUSIVE path — which is why they kept passing unchanged when batching
#: landed, and why that alone was not evidence the new path worked.
_SAFE = ("lint", "test", "brain-audit", "eval")

#: Generous: it is only ever WAITED on when the runner has already failed, and a
#: loaded machine running this suite under `-n auto` must not turn a correct
#: implementation red.
_BARRIER_TIMEOUT = 20.0

#: Short: this one is waited on in the arm that is EXPECTED to time out, so it is
#: pure cost. Long enough that a merely-slow thread start does not read as
#: sequential execution.
_NEGATIVE_TIMEOUT = 2.0


def _barrier_stub(monkeypatch, parties: int, *, timeout: float) -> None:
    """Make every gate wait for ``parties`` gates to be running at once.

    The barrier IS the assertion. It can only be crossed if that many gates are
    genuinely in flight together, so a runner that stayed sequential does not
    return a wrong answer — it cannot return at all, and raises. There is no
    sleep to tune and no threshold to get wrong.
    """
    barrier = threading.Barrier(parties)

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] == "mise":
            barrier.wait(timeout=timeout)
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)


def _peak_stub(monkeypatch, *, hold: float = 0.05) -> dict[str, int]:
    """Record the greatest number of gates ever running SIMULTANEOUSLY.

    A peak of 1 is a positive statement that nothing overlapped: the counter is
    incremented inside the stub, so any overlap at all is observed. It cannot
    under-report the way a timing comparison can.
    """
    lock = threading.Lock()
    state = {"live": 0, "peak": 0}

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] != "mise":
            return subprocess.CompletedProcess(cmd, 0, "")
        with lock:
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
        time.sleep(hold)
        with lock:
            state["live"] -= 1
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    return state


#: The concurrency-safe members of `GATE_TASKS`, in requested order. DERIVED from
#: `CONCURRENT_SAFE` rather than spelled out, so the barrier's party count cannot
#: drift from the set it is proving things about — which is exactly what happened
#: when `eval` left the set in #321 and a hard-coded count of four made the
#: positive arm hang instead of pass.
_CONCURRENT = tuple(t for t in gates.GATE_TASKS if t in gates.CONCURRENT_SAFE)


def test_concurrency_safe_gates_really_do_run_at_the_same_time(monkeypatch, tmp_path):
    """The positive arm: every concurrency-safe gate in flight together, or this hangs out.

    The party count is `len(_CONCURRENT)`, not `len(_SAFE)`. Those were the same
    number until #321 moved `eval` out of `CONCURRENT_SAFE`; keeping the old one
    would demand a fourth party that can never arrive, turning the positive arm
    into a timeout — a test that fails for a reason unrelated to what it checks.
    """
    root = _repo(tmp_path, _CONCURRENT)
    _barrier_stub(monkeypatch, len(_CONCURRENT), timeout=_BARRIER_TIMEOUT)
    _pin_sha(monkeypatch)

    results = gates.run(root, _CONCURRENT, stop_on_failure=False)

    assert [r.task for r in results] == list(_CONCURRENT)
    assert all(r.passed for r in results)
    # Guards the derivation itself: if CONCURRENT_SAFE ever empties or collapses
    # to one, this arm silently stops proving overlap.
    assert len(_CONCURRENT) > 1


def test_the_barrier_arm_can_fail(monkeypatch, tmp_path):
    """The control on the arm above: with gates that must NOT overlap, it breaks.

    Without this, `test_concurrency_safe_gates_really_do_run_at_the_same_time`
    would be a probe with one face — it would also pass against a stub that
    ignored the barrier entirely. Here the SAME barrier, the same party count and
    the same runner are pointed at names outside `CONCURRENT_SAFE`, and the only
    thing that changed is whether the gates are allowed to overlap.
    """
    root = _repo(tmp_path, _TASKS)
    _barrier_stub(monkeypatch, len(_TASKS), timeout=_NEGATIVE_TIMEOUT)
    _pin_sha(monkeypatch)

    with pytest.raises(threading.BrokenBarrierError):
        gates.run(root, _TASKS, stop_on_failure=False)


def test_a_gate_outside_the_safe_set_never_overlaps_anything(monkeypatch, tmp_path):
    """Unknown gates run ALONE — the fail-closed default, measured not assumed."""
    root = _repo(tmp_path, _TASKS)
    state = _peak_stub(monkeypatch)
    _pin_sha(monkeypatch)

    gates.run(root, _TASKS, stop_on_failure=False)

    assert state["peak"] == 1


def test_a_writer_between_two_readers_separates_them(monkeypatch, tmp_path):
    """`fmt` is not concurrency-safe, so the readers around it cannot merge.

    This is the actual constraint — "sequential where a step writes files" — and
    it is the case a naive implementation gets wrong by hoisting every safe gate
    into one batch and running the writer beside them.
    """
    order = ("lint", "fmt", "test")
    root = _repo(tmp_path, order)
    state = _peak_stub(monkeypatch)
    _pin_sha(monkeypatch)

    gates.run(root, order, stop_on_failure=False)

    assert state["peak"] == 1


def test_two_safe_gates_around_a_writer_still_overlap_when_adjacent(monkeypatch, tmp_path):
    """Control on the test above: the same names ADJACENT do batch together."""
    order = ("lint", "test", "fmt")
    root = _repo(tmp_path, order)
    state = _peak_stub(monkeypatch)
    _pin_sha(monkeypatch)

    gates.run(root, order, stop_on_failure=False)

    assert state["peak"] == 2


def test_the_record_keeps_requested_order_despite_completion_order(monkeypatch, tmp_path):
    """Rows come back in the order ASKED FOR, not the order the threads finished.

    Concurrency makes completion order an accident of scheduling. Two records of
    the same gate set whose rows are ordered differently would invite a reader to
    think something about the run changed when nothing did.
    """
    root = _repo(tmp_path, _SAFE)
    # `eval` finishes first and `lint` last — the exact inversion of the request.
    delays = {"eval": 0.0, "brain-audit": 0.02, "test": 0.04, "lint": 0.06}

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] == "mise":
            time.sleep(delays[cmd[-1]])
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    gate_run, _ = gates.run_and_record(root, _SAFE, stop_on_failure=False)

    assert gate_run is not None
    written = json.loads(gate_run.path.read_text(encoding="utf-8"))
    assert [row["task"] for row in written["gates"]] == list(_SAFE)


def test_a_repeated_gate_keeps_both_rows_under_concurrency(monkeypatch, tmp_path):
    """`kb-gates -- lint lint` still records TWO rows once padding is a multiset.

    The count-based padding this replaced was correct only while results arrived
    in requested order; a set-based fix would have collapsed the two rows the CLI
    deliberately allows. The multiset difference is the only form that survives
    both.
    """
    root = _repo(tmp_path, ("lint",))
    _peak_stub(monkeypatch, hold=0.0)
    _pin_sha(monkeypatch)

    gate_run, _ = gates.run_and_record(root, ("lint", "lint"), stop_on_failure=False)

    assert gate_run is not None
    written = json.loads(gate_run.path.read_text(encoding="utf-8"))
    assert [row["task"] for row in written["gates"]] == ["lint", "lint"]


def test_only_a_shared_terminal_gets_mises_prefix(monkeypatch, tmp_path):
    """`-o prefix` appears when gates share stdio, and NOT when one runs alone.

    Both directions, because either alone is satisfiable by a constant: always
    prefixing would change what `kb-gates -- lint` has always printed, and never
    prefixing would let concurrent gates interleave into unattributable output.

    **A full `GATE_TASKS` run now exercises BOTH directions on its own**, which
    it did not before #321: the three concurrency-safe gates share a terminal and
    are prefixed, while `eval` runs alone in its own batch and is not. So the
    assertion is per-batch rather than "every gate in the run" — the old form
    read as a claim about the run, and was only ever true because every gate
    happened to be in one batch.
    """
    seen: list = []
    _stub(monkeypatch, failing="__none__", seen=seen)
    _pin_sha(monkeypatch)

    gates.run(_repo(tmp_path / "solo", ("lint",)), ("lint",), stop_on_failure=False)
    assert _mise(seen)[0][0] == ["mise", "run", "lint"]

    seen.clear()
    gates.run(_repo(tmp_path / "batch", _SAFE), _SAFE, stop_on_failure=False)
    prefixed = {cmd[-1] for cmd, _ in _mise(seen) if cmd[:4] == ["mise", "run", "-o", "prefix"]}
    bare = {cmd[-1] for cmd, _ in _mise(seen) if cmd[:2] == ["mise", "run"] and "-o" not in cmd}

    # Shared terminal -> prefixed. Alone -> bare. Both observed in one run.
    assert prefixed == {"lint", "test", "brain-audit"}
    assert bare == {"eval"}


def test_an_interrupt_under_concurrency_pads_the_gates_that_really_did_not_run(
    monkeypatch, tmp_path
):
    """The record must name the UNRUN gates, not however many happen to be left.

    This is the test that separates padding by multiset from padding by count,
    and nothing else in the suite can: with results arriving in requested order
    the two agree exactly. It needs a gate requested LATE to finish FIRST, so a
    `tasks[len(results):]` slice pads from the wrong index and produces a record
    naming a gate that never ran while dropping one that was requested. Both
    halves of that are the failure.

    **The inversion now happens inside the concurrent batch**, because #321 moved
    `eval` into a batch of its own and it can no longer finish first by any
    arrangement of the mock. `brain-audit` — requested last of the three that
    actually race — returns immediately, `test` interrupts, and `lint` is still
    running when it does. The property under test is unchanged; only the gate
    used to construct it moved, which is the kind of edit a fixture built around
    a specific NAME forces and one built around a ROLE would not have.
    """
    root = _repo(tmp_path, _SAFE)

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] != "mise":
            return subprocess.CompletedProcess(cmd, 0, "")
        task = cmd[-1]
        if task == "brain-audit":  # finishes first, inverting the requested order
            return subprocess.CompletedProcess(cmd, 0, "")
        if task == "test":
            time.sleep(0.05)
            raise KeyboardInterrupt
        time.sleep(0.3)  # still running when the interrupt lands; finishes after
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        gates.run_and_record(root, _SAFE, stop_on_failure=False)

    rows = _rows(_written(root)[0])
    written = json.loads(_written(root)[0].read_text(encoding="utf-8"))["gates"]
    # Every requested gate appears exactly once — no duplicate, no omission.
    assert sorted(row["task"] for row in written) == sorted(_SAFE)
    # `test` raised, so it produced no result; `eval` is a later batch and never
    # started. Both are honestly `None` — the two distinct routes to "did not
    # run", and neither may be padded into a pass.
    assert rows["test"]["rc"] is None
    assert rows["eval"]["rc"] is None
    # `brain-audit` finished first and `lint` finished after the interrupt: both
    # really ran, so both carry a real code. This is the half that fails if the
    # padding is by COUNT — the slice would name the wrong gates here.
    assert rows["brain-audit"]["rc"] == 0
    assert rows["lint"]["rc"] == 0


def test_a_sibling_that_finished_after_the_interrupt_is_not_recorded_as_unrun(
    monkeypatch, tmp_path
):
    """A gate that RAN TO COMPLETION must never be persisted as "did not run".

    The HIGH finding of round 2, and the sharpest defect this round produced.
    `as_completed` stopped handing over results the moment an exception left the
    loop — but the pool's `shutdown(wait=True)` still waited, so `lint` and
    `test` genuinely ran, genuinely printed their own PASS lines, and had their
    results dropped. The padding then wrote them as `rc: None`, which this module
    documents as "did not run". That is its own purpose inverted: not "could not
    check rendered as green", but "ran and passed rendered as never ran" — and
    reachable on the ship path, where all four gates are one batch.

    The test that used to stand here ASSERTED THE BUG. It said
    `rows["lint"]["rc"] is None` and its name called `lint` a gate that "really
    did not run", while its own 1.01s runtime was `lint`'s sleep — proof the gate
    it called unrun had run to completion. A test written alongside its own fix,
    agreeing with it. The lane found this by instrumenting which subprocess calls
    actually completed; no mutation of production code could have, because the
    test asserted the wrong thing rather than nothing.

    So the assertion here is tied to OBSERVED EXECUTION, not to a shape: the
    mocked runner appends to `finished` only after its sleep, and every task in
    that list must have a real `rc` in the record.
    """
    root = _repo(tmp_path, _SAFE)
    finished: list[str] = []

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] != "mise":
            return subprocess.CompletedProcess(cmd, 0, "")
        task = cmd[-1]
        if task == "brain-audit":
            time.sleep(0.05)
            raise KeyboardInterrupt
        if task != "eval":
            time.sleep(0.3)
        finished.append(task)
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        gates.run_and_record(root, _SAFE, stop_on_failure=False)

    rows = _rows(_written(root)[0])
    # The gates that really did run — asserted from the runner's own record of
    # completion, so this cannot drift into agreeing with the implementation.
    #
    # `eval` left this list when #321 moved it out of `CONCURRENT_SAFE`: it is a
    # later batch, the interrupt propagates first, so it never starts. Note that
    # only this one line needed changing — the loop below reads `finished`, so it
    # followed the behaviour on its own. That is the design in the docstring
    # working: an assertion tied to observed execution adapts, while one tied to
    # a hard-coded shape would have had to be re-guessed.
    assert sorted(finished) == ["lint", "test"]
    for task in finished:
        assert rows[task]["rc"] == 0, f"{task} ran to completion but was recorded {rows[task]}"
    assert rows["eval"]["rc"] is None


def test_a_gate_that_never_started_is_still_recorded_as_unrun(monkeypatch, tmp_path):
    """CONTROL ARM: the sweep must not invent a result for a gate that raised.

    Without this, the test above is satisfiable by recording `rc=0` for
    everything — which would be the same class of lie in the other direction.
    """
    root = _repo(tmp_path, _SAFE)

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] != "mise":
            return subprocess.CompletedProcess(cmd, 0, "")
        if cmd[-1] == "brain-audit":
            raise KeyboardInterrupt
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        gates.run_and_record(root, _SAFE, stop_on_failure=False)

    assert _rows(_written(root)[0])["brain-audit"]["rc"] is None


def test_the_shipped_gates_batch_exactly_as_concurrent_safe_declares():
    """Batching follows `CONCURRENT_SAFE`, and `eval` is deliberately outside it.

    This asserted "all four form ONE batch" until 2026-08-16, and it went red the
    moment `eval` was removed from `CONCURRENT_SAFE` (#321) — which is the check
    working, not breaking. `eval`'s `tier1.graph-answers` case runs
    `graphify query` against the ~771 MB graph under a 60s bound and was starved
    past it by a concurrent `test`, failing intermittently across three runs and
    passing every time it ran alone.

    So the shape is asserted from the DECLARATION rather than hard-coded to a
    count: consecutive concurrency-safe names group, anything else is isolated.
    Written this way, the test keeps its original job — a gate added to
    `GATE_TASKS` without being cleared lands in its own batch and is visible here
    — without having to be rewritten again the next time membership changes.

    **One real behaviour change comes with it.** `eval` now being a batch of its
    own means `stop_on_failure=True` CAN skip it on the ship path when an earlier
    batch fails. That is correct — a refusal is already decided — but it is no
    longer true that the ship path never skips a gate, and the docstring of
    `iter_run` should not be read as claiming so.
    """
    batches = list(gates._batches(gates.GATE_TASKS))

    assert [name for batch in batches for name in batch] == list(gates.GATE_TASKS)
    for batch in batches:
        if len(batch) > 1:
            assert set(batch) <= gates.CONCURRENT_SAFE, batch
        else:
            assert batch[0] in gates.GATE_TASKS
    # The measured fact this pins, stated directly: eval runs alone.
    assert ("eval",) in batches
    assert "eval" not in gates.CONCURRENT_SAFE


def test_a_non_adjacent_repeat_keeps_its_first_requested_position(monkeypatch, tmp_path):
    """A gate repeated NON-adjacently must not drag its first row to the back.

    The gap the whole concurrency suite had: every other repeat test uses
    ADJACENT duplicates, where last-write-wins and first-write-wins agree, so a
    `{task: i for ...}` comprehension passed all of them while sorting
    `("lint", "test", "lint")` to `test, lint, lint`. Found by a lane that
    executed the function instead of reading it.

    The assertion is GROUPED order, not the literal request, and deliberately so
    — two rows for one gate are indistinguishable, so `lint, lint, test` is the
    strongest thing that is actually true. Asserting the literal
    `lint, test, lint` would be pinning a fact the data cannot carry.
    """
    root = _repo(tmp_path, ("lint", "test"))
    _peak_stub(monkeypatch, hold=0.0)
    _pin_sha(monkeypatch)

    gate_run, _ = gates.run_and_record(root, ("lint", "test", "lint"), stop_on_failure=False)

    assert gate_run is not None
    written = json.loads(gate_run.path.read_text(encoding="utf-8"))["gates"]
    assert [row["task"] for row in written] == ["lint", "lint", "test"]


def test_ordering_a_list_with_no_repeats_is_exactly_the_request(monkeypatch, tmp_path):
    """CONTROL ARM: with no duplicate name, the order IS the requested order.

    Without this the test above is satisfiable by a function that groups by name
    and ignores position entirely — which would reorder the ordinary four-gate
    record and no other test would notice.
    """
    root = _repo(tmp_path, _SAFE)
    _peak_stub(monkeypatch, hold=0.0)
    _pin_sha(monkeypatch)

    gate_run, _ = gates.run_and_record(root, _SAFE, stop_on_failure=False)

    assert gate_run is not None
    written = json.loads(gate_run.path.read_text(encoding="utf-8"))["gates"]
    assert [row["task"] for row in written] == list(_SAFE)


def test_results_arrive_in_completion_order_within_a_batch(monkeypatch, tmp_path):
    """`iter_run` yields a batch's gates fastest-first, not in the order requested.

    Pinned directly, because two other tests DEPEND on it without asserting it.
    `test_the_record_keeps_requested_order_despite_completion_order` only has
    work to do if results genuinely arrive out of order — rebuild the batch's
    outcomes in submit order and that test still passes, vacuously, while the
    reordering it exists to check has stopped happening. A property two tests
    rest on should be somebody's assertion.
    """
    root = _repo(tmp_path, _SAFE)
    # Ordered so the CONCURRENT batch inverts: brain-audit finishes first and
    # lint last, against a requested order of lint, test, brain-audit. `eval` is
    # a batch of its own since #321, so its delay cannot affect where it lands —
    # it arrives last because it runs last, and giving it the shortest delay (as
    # this fixture used to) would prove nothing about ordering at all.
    delays = {"brain-audit": 0.0, "test": 0.05, "lint": 0.10, "eval": 0.0}

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] == "mise":
            time.sleep(delays[cmd[-1]])
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    arrived = [r.task for r in gates.iter_run(root, _SAFE, stop_on_failure=False)]

    assert arrived == ["brain-audit", "test", "lint", "eval"]
    assert arrived != list(_SAFE)  # the inversion is the point
    # And it is an inversion WITHIN the batch, not just eval being appended.
    assert arrived[:3] == ["brain-audit", "test", "lint"] != ["lint", "test", "brain-audit"]


def test_an_interrupt_on_the_main_thread_still_collects_the_gates_that_finished(
    monkeypatch, tmp_path
):
    """Ctrl-C lands on the MAIN thread, not in a worker — and the sweep is for that.

    Constructed deliberately, because the arm for the sweep SURVIVED without it
    and the survival was informative rather than noise. The sibling test raises
    `KeyboardInterrupt` inside the mocked subprocess, which makes it a *future's*
    exception — `future.exception()` reports it, the `as_completed` loop runs to
    the end, and every result is consumed. The sweep is never reached, so
    deleting it changed nothing and no test noticed.

    A real Ctrl-C does not work that way: the signal is delivered to the main
    thread, which is sitting in `as_completed`. That path abandons the iterator
    with siblings still running, and the pool then waits for them — the exact
    shape of the round-2 HIGH. `as_completed` is patched here to raise after
    handing over one future, which is the cheapest honest way to reach it.

    Without the sweep this records the still-running gates as `rc: None` while
    they run to completion. With it, the record says what happened.
    """
    root = _repo(tmp_path, _SAFE)
    real_as_completed = gates.as_completed

    def interrupted(fs: Iterable) -> Iterator:
        # Hand over exactly one result, then interrupt the consumer — a Ctrl-C
        # arriving while the main thread waits on the rest of the batch.
        iterator = real_as_completed(fs)
        yield next(iterator)
        raise KeyboardInterrupt

    monkeypatch.setattr(gates, "as_completed", interrupted)

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        # `lint` returns immediately and is the one future handed over; its two
        # batch-mates are still running when the interrupt lands, which is the
        # state the sweep exists for. This used to single out `eval` as the fast
        # one — it cannot any more, because #321 moved `eval` into a batch of its
        # own, and a fixture naming a gate that is not in the batch under test
        # would have quietly stopped constructing the scenario.
        if cmd[0] == "mise" and cmd[-1] != "lint":
            time.sleep(0.2)
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        gates.run_and_record(root, _SAFE, stop_on_failure=False)

    rows = _rows(_written(root)[0])
    # The CONCURRENT batch ran to completion — the pool waited for all of it — so
    # each of its gates carries a real exit code, not the "did not run" state.
    assert [rows[t]["rc"] for t in ("lint", "test", "brain-audit")] == [0, 0, 0]
    # `eval` is a later batch and the interrupt propagates first, so it never
    # starts. `rc: None` is the honest record of that, and is never a pass.
    assert rows["eval"]["rc"] is None


def test_an_unexpected_error_in_one_gate_does_not_discard_the_others(monkeypatch, tmp_path):
    """A worker raising anything at all must not cost the batch its evidence.

    The third shape, and the one `_invoke`'s own `except (OSError,
    subprocess.SubprocessError)` does not cover: something raised in `_run_one`
    outside the subprocess call — a closed stdout on the `print`, a `RuntimeError`
    from a future refactor. Neither the interrupt handler (which names
    `KeyboardInterrupt`/`SystemExit`) nor the sweep alone would keep it from
    escaping `_run_batch` and taking three completed gates with it; reading each
    future's outcome with `.exception()` instead of `.result()` is what does.

    The error still surfaces — it is returned and re-raised, not swallowed.
    Losing the failure would be the mirror defect of losing the results.

    **`eval` is asserted as NOT RUN, and that is the point rather than a
    concession.** It left `CONCURRENT_SAFE` in #321, so it is now a batch of its
    own AFTER the one that raises, and the re-raise means it is never reached.
    Its row is therefore `rc: None` — the schema's explicit "did not run", which
    `GateResult`'s docstring states is never a pass. The property under test is
    unchanged: every gate that COMPLETED kept its evidence, and the one that did
    not is recorded as not-run rather than as absent or as green. Asserting
    `rc == 0` here would have been asserting a gate ran when it did not.
    """
    root = _repo(tmp_path, _SAFE)

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if cmd[0] == "mise" and cmd[-1] == "brain-audit":
            msg = "gate runner blew up"
            raise RuntimeError(msg)
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    _pin_sha(monkeypatch)

    with pytest.raises(RuntimeError, match="gate runner blew up"):
        gates.run_and_record(root, _SAFE, stop_on_failure=False)

    rows = _rows(_written(root)[0])
    assert [rows[t]["rc"] for t in ("lint", "test")] == [0, 0]
    assert rows["brain-audit"]["rc"] is None
    assert rows["eval"]["rc"] is None


# --- §2 R5 tranche 4: the `Result` boundary ---------------------------------
#
# Every exit-code assertion above is unchanged and is the regression arm proving
# the split changed no behaviour. What is NEW is that this module's three
# outcomes are now three TYPES. `kb-gates` already drew the 0/1/2 split by hand;
# no int-returning test can see whether a 2 arrived as a refusal-to-run or as a
# claim about the gates, because both are the integer 2.


def test_gates_boundary_failing_gate_is_ok_with_rc_findings(tmp_path: Path, monkeypatch) -> None:
    """A gate that ran and FAILED is a finding, not a broken tool — recipe rule 1.

    If someone "simplifies" this to an `Err`, every exit-code assertion in this
    file stays green: `exit_code(Err(rc=FINDINGS))` is unrepresentable, but
    `Err(msg)` defaults to 2 and the pre-existing tests assert 1 — so only the
    rc would move, and only on the failure path. This asserts the TYPE.
    """
    root = _repo(tmp_path)
    _pin_sha(monkeypatch)
    _stub(monkeypatch)

    result = gates.check_gates(list(_TASKS), root)

    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    gate_run, _summary = result.value
    assert not gate_run.all_passed


def test_gates_boundary_all_passing_is_ok_with_rc_ok(tmp_path: Path, monkeypatch) -> None:
    """CONTROL ARM: `Ok` is reachable with BOTH rcs, so the test above discriminates."""
    root = _repo(tmp_path)
    _pin_sha(monkeypatch)
    _stub(monkeypatch, failing="nothing-fails")

    result = gates.check_gates(list(_TASKS), root)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    gate_run, _summary = result.value
    assert gate_run.all_passed


def test_gates_boundary_unknown_flag_is_an_err_not_a_verdict(tmp_path: Path, monkeypatch) -> None:
    """Refusing to run is a THIRD state, and the type now says so.

    The int has been 2 all along and `main`'s tests pin it. What they cannot see
    is whether that 2 arrived as an `Ok` — which would assert the gates ran and
    reported something — or as an `Err`, which is the truth. A `--stop-on-failure`
    typo must never read as a gate verdict.
    """
    calls = _never_runs(monkeypatch)
    root = _repo(tmp_path)

    result = gates.check_gates(["--stop-on-failure"], root)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "--stop-on-failure" in result.message
    assert _mise(calls) == []


def test_gates_boundary_undeclared_gate_is_an_err(tmp_path: Path, monkeypatch) -> None:
    """The other never-ran route: a task `mise.toml` does not declare."""
    root = _repo(tmp_path, tasks=("alpha",))
    _pin_sha(monkeypatch)
    _never_runs(monkeypatch)

    result = gates.check_gates(["nope"], root)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "nope" in result.message


def test_gates_boundary_returns_its_summary_rather_than_printing_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The REPORT is returned; only the gates' own live output may reach the terminal.

    This is the carve-out `check_gates` documents, asserted rather than asserted
    away: the summary — the thing `main` prints — must not appear on stdout when
    only the boundary has run. Armed on the FAILING path, since a passing run
    printing no summary would also be true of a boundary that merely forgot to
    report failures.
    """
    root = _repo(tmp_path)
    _pin_sha(monkeypatch)
    _stub(monkeypatch)

    result = gates.check_gates(list(_TASKS), root)
    captured = capsys.readouterr()

    assert isinstance(result, Ok)
    _, summary = result.value
    assert summary
    assert summary not in captured.out
    assert summary not in captured.err


def test_gates_int_wrapper_is_exit_code_of_boundary(tmp_path: Path, monkeypatch) -> None:
    """The equivalence that makes the split safe — catches a renderer computing its own rc."""
    root = _repo(tmp_path)
    _pin_sha(monkeypatch)
    _stub(monkeypatch)

    rc_main = gates.main(list(_TASKS), root)
    rc_boundary = exit_code(gates.check_gates(list(_TASKS), root))

    assert rc_main == rc_boundary == int(Rc.FINDINGS)


# ── the inner/outer timeout ordering (cold lane, batch 2) ──────────────────


def _mise_task_timeouts() -> dict[str, str]:
    """Every `[tasks.<name>]` timeout declared in the real `mise.toml`.

    Read from the repo's own file rather than a fixture: the defect this guards
    is a DRIFT between two files, so a fixture copy of one of them would assert
    that the fixture agrees with itself.
    """
    import tomllib

    raw = tomllib.loads(Path("mise.toml").read_text(encoding="utf-8"))
    tasks = raw.get("tasks", {})
    return {
        name: body["timeout"]
        for name, body in tasks.items()
        if isinstance(body, dict) and "timeout" in body
    }


def _seconds(spec: str) -> int:
    unit = spec[-1]
    value = int(spec[:-1])
    return value * {"s": 1, "m": 60, "h": 3600}[unit]


def test_every_gate_task_bound_is_strictly_under_the_outer_gate_timeout() -> None:
    """An equal bound is a RACE, not a belt-and-braces pair.

    `gates.py` wraps each `mise run <task>` in `_GATE_TIMEOUT`. When the task
    declares the same number, which one fires is decided by scheduling — and the
    outer one names no task and kills no process tree, so the worse message wins
    half the time. `test` and `eval` were both exactly 1800s. (Cold lane, batch 2.)

    Asserted over ALL gate tasks rather than the two that were wrong, because the
    next one added would otherwise reintroduce it silently.
    """
    declared = _mise_task_timeouts()
    offenders = {
        task: declared[task]
        for task in gates.GATE_TASKS
        if task in declared and _seconds(declared[task]) >= gates._GATE_TIMEOUT
    }
    assert not offenders, (
        f"these gate tasks declare a bound >= the outer {gates._GATE_TIMEOUT}s "
        f"and therefore race it: {offenders}"
    )


def test_the_ordering_check_can_actually_fail() -> None:
    """The control arm for the test above — it must reject a bound that races.

    Without this, a `_seconds` that always returned 0, or a `GATE_TASKS` that
    stopped intersecting `mise.toml`, would make the assertion vacuous and green
    forever.
    """
    assert _seconds("30m") >= gates._GATE_TIMEOUT
    assert _seconds("25m") < gates._GATE_TIMEOUT


def test_the_gate_tasks_are_actually_found_in_mise_toml() -> None:
    """A bound-limited probe: the check above skips any task it cannot see.

    If `GATE_TASKS` and `mise.toml` stopped intersecting, `offenders` is empty
    and the test passes having examined nothing — the "gate that never asked the
    question" shape. This pins that the intersection is non-trivial.
    """
    declared = _mise_task_timeouts()
    covered = [task for task in gates.GATE_TASKS if task in declared]
    assert len(covered) >= 3, f"only {covered} of {list(gates.GATE_TASKS)} declare a timeout"
