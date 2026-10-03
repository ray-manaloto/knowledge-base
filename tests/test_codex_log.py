# Copyright (c) 2026 Raymond Manaloto
"""Positive stderr evidence is a failure even when Codex returned success."""

from pathlib import Path

from kb_setup import codex_log


def test_malformed_role_line_and_clean_control(tmp_path: Path):
    warning = "Ignoring malformed agent role definition: fixture-role: unknown field"
    assert codex_log.malformed_agent_roles("progress\n" + warning + "\nfinal") == [warning]
    assert codex_log.malformed_agent_roles("progress\nfinal") == []
    path = tmp_path / "lane.log"
    assert codex_log.main([str(path)]) == 1
    path.write_text(warning + "\n")
    assert codex_log.main([str(path)]) == 1
    path.write_text("clean\n")
    assert codex_log.main([str(path)]) == 0
