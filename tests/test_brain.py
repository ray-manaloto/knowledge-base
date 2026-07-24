"""Tests for the second-brain routing seam (kb_setup.brain).

Covers the contract, the deterministic >=3/session-dedup aggregator (both the
decisive and the noise-suppressing directions), memory parsing, the record
audit, and the advisory transcript-mining audit (verified-but-unrecorded).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import brain
from kb_setup.brain import Outcome, RecordRequest

if TYPE_CHECKING:
    import pytest


def _o(task_class: str, lane: str, verdict: str, session: str) -> Outcome:
    return Outcome(task_class=task_class, lane=lane, verdict=verdict, session=session)


# --- contract --------------------------------------------------------------


def _req(
    task_class: str = "migration",
    lane: str = "codex",
    effort: str = "high",
    verdict: str = "clean",
    session: str = "s1",
) -> RecordRequest:
    return RecordRequest(
        task_class=task_class, lane=lane, effort=effort, verdict=verdict, session=session
    )


def test_validate_record_rejects_missing_field() -> None:
    assert brain.validate_record(_req(verdict="")) is not None
    assert brain.validate_record(_req(session="")) is not None
    assert brain.validate_record(_req(task_class="")) is not None


def test_validate_record_rejects_unknown_verdict() -> None:
    err = brain.validate_record(_req(verdict="great"))
    assert err is not None
    assert "verdict" in err


def test_validate_record_accepts_complete() -> None:
    assert brain.validate_record(_req()) is None


def test_record_refuses_incomplete_with_rc2(tmp_path: Path) -> None:
    rc = brain.record(
        tmp_path,
        RecordRequest(
            task_class="migration", lane="codex", effort="high", verdict="", session="s1"
        ),
    )
    assert rc == 2
    # nothing written
    assert not (tmp_path / "brain" / "graphify-out" / "memory").exists()


# --- aggregator: decisive directions --------------------------------------


def test_aggregate_preferred_needs_three_clean() -> None:
    outs = [_o("migration", "codex", "clean", f"s{i}") for i in range(3)]
    (lesson,) = brain.aggregate(outs)
    assert (lesson.tag, lesson.good, lesson.bad) == ("preferred", 3, 0)


def test_aggregate_two_clean_is_only_tentative() -> None:
    outs = [_o("migration", "codex", "clean", f"s{i}") for i in range(2)]
    (lesson,) = brain.aggregate(outs)
    assert lesson.tag == "tentative"


def test_aggregate_three_bad_is_avoid() -> None:
    outs = [_o("test-generation", "antigravity", "rework", f"s{i}") for i in range(3)]
    (lesson,) = brain.aggregate(outs)
    assert lesson.tag == "avoid"


def test_aggregate_mixed_is_contested() -> None:
    outs = [
        _o("auth-security", "grok", "clean", "s1"),
        _o("auth-security", "grok", "failed", "s2"),
    ]
    (lesson,) = brain.aggregate(outs)
    assert lesson.tag == "contested"


# --- aggregator: session-dedup (the noise guard) ---------------------------


def test_session_dedup_collapses_a_burst_to_one_vote() -> None:
    # one bad spec producing three reworks in ONE session must NOT read as avoid
    outs = [_o("test-generation", "antigravity", "rework", "s1") for _ in range(3)]
    (lesson,) = brain.aggregate(outs)
    assert lesson.tag == "tentative"
    assert lesson.bad == 1


def test_distinct_sessions_do_count_independently() -> None:
    outs = [_o("test-generation", "antigravity", "rework", f"s{i}") for i in range(3)]
    (lesson,) = brain.aggregate(outs)
    assert lesson.tag == "avoid"
    assert lesson.bad == 3


def test_aggregate_empty_is_empty() -> None:
    assert brain.aggregate([]) == []


# --- memory parsing + round-trip ------------------------------------------


def _write_memory(memory: Path, name: str, body: str) -> None:
    memory.mkdir(parents=True, exist_ok=True)
    (memory / name).write_text(body, encoding="utf-8")


def test_parse_outcome_reads_frontmatter(tmp_path: Path) -> None:
    memory = tmp_path / "brain" / "graphify-out" / "memory"
    _write_memory(
        memory,
        "route.md",
        "---\n"
        'type: "routing-outcome"\n'
        'question: "route migration via codex [session=s7]"\n'
        'outcome: "useful"\n'
        'source_nodes: ["lane-codex", "task-class-migration"]\n'
        "---\n\nbody\n",
    )
    outs = brain.load_outcomes(tmp_path)
    assert outs == [_o("migration", "codex", "clean", "s7")]


def test_parse_outcome_ignores_non_routing(tmp_path: Path) -> None:
    memory = tmp_path / "brain" / "graphify-out" / "memory"
    _write_memory(
        memory,
        "query.md",
        '---\ntype: "query"\noutcome: "useful"\nsource_nodes: ["reflect"]\n---\n\nbody\n',
    )
    assert brain.load_outcomes(tmp_path) == []


# --- audit -----------------------------------------------------------------


def test_audit_passes_on_closed_records(tmp_path: Path) -> None:
    memory = tmp_path / "brain" / "graphify-out" / "memory"
    _write_memory(
        memory,
        "ok.md",
        "---\n"
        'type: "routing-outcome"\n'
        'question: "route migration via codex [session=s1]"\n'
        'outcome: "useful"\n'
        'source_nodes: ["lane-codex", "task-class-migration"]\n'
        "---\n\nbody\n",
    )
    assert brain.audit(tmp_path) == 0


def test_audit_fails_on_unclosed_routing_record(tmp_path: Path) -> None:
    memory = tmp_path / "brain" / "graphify-out" / "memory"
    # looks like a routing record (type) but is missing the session -> does not parse
    _write_memory(
        memory,
        "broken.md",
        "---\n"
        'type: "routing-outcome"\n'
        'question: "route migration via codex"\n'
        'outcome: "useful"\n'
        'source_nodes: ["lane-codex", "task-class-migration"]\n'
        "---\n\nbody\n",
    )
    assert brain.audit(tmp_path) == 1


def test_audit_empty_store_is_ok(tmp_path: Path) -> None:
    assert brain.audit(tmp_path) == 0


# --- query wrapper guards --------------------------------------------------


def test_query_without_graph_returns_1(tmp_path: Path) -> None:
    assert brain.query(tmp_path, ["lane-codex"]) == 1


def test_query_without_question_returns_2(tmp_path: Path) -> None:
    graph = tmp_path / "brain" / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text('{"nodes": [], "links": []}', encoding="utf-8")
    assert brain.query(tmp_path, []) == 2


# --- render ----------------------------------------------------------------


def test_render_lessons_has_row_per_cell() -> None:
    lessons = brain.aggregate([_o("migration", "codex", "clean", f"s{i}") for i in range(3)])
    out = brain.render_lessons(lessons)
    assert "| migration | codex | preferred | 3 | 0 |" in out


# --- transcript-mining audit (advisory) ------------------------------------


def _agent(subagent_type: str) -> dict[str, object]:
    return {"type": "tool_use", "name": "Agent", "input": {"subagent_type": subagent_type}}


def _bash(command: str) -> dict[str, object]:
    return {"type": "tool_use", "name": "Bash", "input": {"command": command}}


def _line(session: str, *blocks: dict[str, object]) -> str:
    return json.dumps(
        {"type": "assistant", "sessionId": session, "message": {"content": list(blocks)}}
    )


def _transcript(tmp_path: Path, name: str, *lines: str) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


_CODEX = "fable-orchestrator:codex-implementer"


def _verdict_of(paths: list[Path], session: str) -> str:
    return {s: verdict for s, *_rest, verdict in brain.audit_transcripts(paths).sessions}[session]


def test_verdict_verified_but_unrecorded(tmp_path: Path) -> None:
    # delegated to an implementation lane + ran a gate, but recorded nothing
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _agent(_CODEX)),
        _line("s1", _bash("mise run test")),
    )
    result = brain.audit_transcripts([p])
    assert result.counts.get("verified-unrecorded") == 1
    assert _verdict_of([p], "s1") == "verified-unrecorded"


def test_verdict_recorded_when_outcome_written(tmp_path: Path) -> None:
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _agent(_CODEX)),
        _line("s1", _bash("mise run test")),
        _line("s1", _bash("mise run brain-remember -- --task-class migration --lane codex")),
    )
    assert brain.audit_transcripts([p]).counts.get("recorded") == 1


def test_verdict_unverified_when_no_gate_and_no_record(tmp_path: Path) -> None:
    # delegated but no verification seen — cannot tell abandoned from logs-missed
    p = _transcript(tmp_path, "a.jsonl", _line("s1", _agent(_CODEX)))
    assert brain.audit_transcripts([p]).counts.get("unverified") == 1


def test_verdict_under_recorded_when_records_lag_delegations(tmp_path: Path) -> None:
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _agent(_CODEX), _agent(_CODEX)),
        _line("s1", _bash("pytest")),
        _line("s1", _bash("mise run brain-remember -- --task-class migration --lane codex")),
    )
    assert brain.audit_transcripts([p]).counts.get("under-recorded") == 1


def test_review_and_general_lanes_are_not_delegations(tmp_path: Path) -> None:
    # a reviewer/researcher/general-purpose agent closes no routing record
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _agent("fable-orchestrator:codex-reviewer")),
        _line("s1", _agent("general-purpose")),
        _line("s1", _bash("mise run test")),
    )
    result = brain.audit_transcripts([p])
    assert result.counts.get("none") == 1
    assert result.sessions == []  # nothing flagged


def test_readonly_codex_exec_is_not_a_delegation(tmp_path: Path) -> None:
    # research invocation (read-only sandbox) records no outcome — must not flag
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _bash("echo prompt | codex exec --ephemeral --sandbox read-only -")),
        _line("s1", _bash("mise run test")),
    )
    assert brain.audit_transcripts([p]).counts.get("none") == 1


def test_write_capable_codex_exec_counts_as_delegation(tmp_path: Path) -> None:
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _bash("echo prompt | codex exec --full-auto --sandbox workspace-write -")),
        _line("s1", _bash("mise run lint")),
    )
    assert brain.audit_transcripts([p]).counts.get("verified-unrecorded") == 1


def test_malformed_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    path.write_text("not json\n" + _line("s1", _agent(_CODEX)) + "\n", encoding="utf-8")
    assert brain.audit_transcripts([path]).counts.get("unverified") == 1


def test_empty_scan_is_empty() -> None:
    result = brain.audit_transcripts([])
    assert result.counts == {}
    assert result.sessions == []


def test_render_report_headlines_the_alarm(tmp_path: Path) -> None:
    p = _transcript(
        tmp_path,
        "a.jsonl",
        _line("s1", _agent(_CODEX)),
        _line("s1", _bash("mise run test")),
    )
    out = brain.render_transcript_report(brain.audit_transcripts([p]))
    assert "🚨 1 session(s)" in out
    assert "verified-unrecorded" in out


def test_transcript_audit_writes_report_and_rc0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # stand up a fake Claude projects dir so transcript_audit finds a transcript
    config = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    repo = tmp_path / "repo"
    repo.mkdir()
    project_dir = config / "projects" / brain._encode_cwd(repo)
    project_dir.mkdir(parents=True)
    _transcript(
        project_dir,
        "sess.jsonl",
        _line("s1", _agent(_CODEX)),
        _line("s1", _bash("mise run test")),
    )
    rc = brain.transcript_audit(repo, output=Path(".omc/brain-audit.md"))
    assert rc == 0
    report = (repo / ".omc" / "brain-audit.md").read_text(encoding="utf-8")
    assert "verified-unrecorded" in report


def test_transcript_audit_no_transcripts_is_rc0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty"))
    assert brain.transcript_audit(tmp_path / "repo") == 0
