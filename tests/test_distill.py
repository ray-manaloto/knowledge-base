"""Tests for `kb_setup.distill` — the #219 throwaway-script distiller.

The load-bearing test in this file is :func:`test_one_off_session_proposes_nothing`.
#219 states the acceptance arm in writing: *"give it a session of one-off work
and confirm it proposes nothing. A distiller that always finds something is not
a detector."* Everything else here supports that one.

Tests drive `cli.main(["distill"])` as well as `distill()` directly. That is the
lesson PR #220 paid for: all 15 of `skill_lint`'s original tests called the
library, so deleting the CLI dispatch branch left 15/15 green while
`uv run kb-setup skill-lint` was already broken. When a ticket names a mutation,
write the test at the level the mutation happens.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from kb_setup import cli, distill


def _transcript(tmp_path, name, commands, writes=()) -> Path:
    """A minimal but REAL-shaped transcript: assistant records with tool_use blocks."""
    path = tmp_path / f"{name}.jsonl"
    lines = [
        json.dumps(
            {
                "message": {
                    "content": [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]
                }
            }
        )
        for command in commands
    ]
    for file_path, content in writes:
        lines.append(
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Write",
                                "input": {"file_path": file_path, "content": content},
                            }
                        ]
                    }
                }
            )
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _heredoc(body) -> str:
    return f"cd /repo && python3 - <<'PY'\n{body}\nPY"


# --- detection -------------------------------------------------------------


def test_detects_a_heredoc_script():
    kinds = list(distill.detect_scripts(_heredoc("import json\nprint(json)")))
    assert [k for k, _ in kinds] == ["heredoc"]
    assert "import json" in kinds[0][1]


def test_heredoc_body_ends_at_its_own_delimiter():
    """A fixed `EOF` would swallow the rest; the delimiter is captured per-script."""
    command = "python3 - <<'PY'\nimport json\nPY\necho done && python3 - <<'EOF'\nimport re\nEOF"
    bodies = [b for _k, b in distill.detect_scripts(command)]
    assert len(bodies) == 2
    assert "echo done" not in bodies[0]
    assert "import re" in bodies[1]


def test_short_inline_c_is_not_a_script():
    """`python -c "print(1)"` is shell arithmetic, not an authored program."""
    assert list(distill.detect_scripts('python3 -c "print(1)"')) == []


def test_long_inline_c_is_a_script():
    body = "import json;" + ("x=1;" * 40)
    assert len(body) >= distill.MIN_INLINE_CHARS
    kinds = [k for k, _ in distill.detect_scripts(f'python3 -c "{body}"')]
    assert kinds == ["inline"]


def test_written_repo_source_is_not_ad_hoc(tmp_path):
    """A module written to python/src IS the distilled form — counting it inverts the job."""
    path = _transcript(
        tmp_path,
        "s1",
        [],
        writes=[
            ("/repo/python/src/kb_setup/thing.py", "import json\n"),
            ("/scratch/probe.py", "import json\n"),
        ],
    )
    found = distill.scripts_in(path)
    assert [s.kind for s in found] == ["file"]
    assert len(found) == 1


# --- signatures ------------------------------------------------------------


def test_surface_signature_separates_probes_sharing_imports():
    """The measured defect in `import_signature`: 153 scripts in one `json` bucket."""
    a = "import json\nPath('sources/extractions/x.json')"
    b = "import json\nPath('.agent/kb/review/y.json')"
    assert distill.import_signature(a) == distill.import_signature(b)
    assert distill.surface_signature(a) != distill.surface_signature(b)


def test_signature_of_a_shapeless_script_is_empty():
    """No surface and no distinctive import ⇒ nothing to reuse ⇒ never a candidate."""
    assert distill.surface_signature("x = 1\nprint(x)\n") == ""


# --- the acceptance arms ---------------------------------------------------


def test_one_off_session_proposes_nothing(tmp_path):
    """#219's stated FAIL arm. Each probe asks a DIFFERENT question, so nothing recurs.

    This is the test the ticket asks for by name, and the one that makes a
    proposal mean something.
    """
    path = _transcript(
        tmp_path,
        "oneoff",
        [
            _heredoc("import json\nPath('sources/extractions/a.json')"),
            _heredoc("import ast\nPath('docs/research/b.md')"),
            _heredoc("import csv\nPath('mise.toml')"),
        ],
    )
    report = distill.distill(tmp_path, transcripts=[path])
    assert report.scripts_seen == 3, "the scripts WERE seen — this is not a blind probe"
    assert report.candidates == ()
    assert "nothing to propose" in distill.render(report)


def test_repeated_shape_is_proposed(tmp_path):
    """The POSITIVE arm: the same question asked twice is exactly what to distil."""
    path = _transcript(
        tmp_path,
        "repeat",
        [
            _heredoc("import json\nPath('sources/extractions/a.json').read_text()"),
            _heredoc("import json\nfor p in Path('sources/extractions').glob('*.json'): pass"),
        ],
    )
    report = distill.distill(tmp_path, transcripts=[path])
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert "sources/extractions" in candidate.signature
    assert len(candidate.scripts) == 2
    assert candidate.sessions == ("repeat",)


def test_min_scripts_is_a_policy_field_not_a_hardcoded_bound(tmp_path):
    """The parameterisation #219 makes the acceptance criterion, exercised."""
    path = _transcript(
        tmp_path, "solo", [_heredoc("import json\nPath('sources/extractions/a.json')")]
    )
    assert distill.distill(tmp_path, transcripts=[path]).candidates == ()
    loosened = replace(distill.DEFAULT_POLICY, min_scripts=1)
    assert len(distill.distill(tmp_path, transcripts=[path], policy=loosened).candidates) == 1


def test_detect_is_injectable(tmp_path):
    """Swapping `detect` serves another notion of an ad-hoc step without a fork."""
    path = _transcript(tmp_path, "shell", ["bash - <<'SH'\nsources/extractions\nSH"])
    assert distill.distill(tmp_path, transcripts=[path]).scripts_seen == 0

    def shell_detect(command) -> object:
        if "<<'SH'" in command:
            yield "shell", command

    report = distill.distill(
        tmp_path,
        transcripts=[path],
        policy=replace(distill.DEFAULT_POLICY, detect=shell_detect, min_scripts=1),
    )
    assert report.scripts_seen == 1
    assert len(report.candidates) == 1


def test_recurrence_across_sessions_is_grouped(tmp_path):
    a = _transcript(tmp_path, "s1", [_heredoc("import json\nPath('.agent/kb/gates/x')")])
    b = _transcript(tmp_path, "s2", [_heredoc("import json\nPath('.agent/kb/gates/y')")])
    report = distill.distill(tmp_path, transcripts=[a, b])
    assert len(report.candidates) == 1
    assert set(report.candidates[0].sessions) == {"s1", "s2"}


# --- reporting and the CLI seam -------------------------------------------


def test_no_transcripts_is_not_reported_as_clean(tmp_path):
    """A detector that never ran is a SKIP, not a pass (`verify-before-advancing`)."""
    report = distill.distill(tmp_path, transcripts=[])
    text = distill.render(report)
    assert "NO TRANSCRIPTS FOUND" in text
    assert "did not run" in text


def test_a_truncated_transcript_line_does_not_abort_the_scan(tmp_path):
    """Transcripts are append-only logs written by another process."""
    path = tmp_path / "torn.jsonl"
    good = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": _heredoc("import json\nPath('mise.toml')")},
                    }
                ]
            }
        }
    )
    path.write_text(good + '\n{"message": {"conte', encoding="utf-8")
    assert distill.distill(tmp_path, transcripts=[path]).scripts_seen == 1


def test_cli_dispatches_distill(monkeypatch, tmp_path, capsys):
    """The level PR #220's mutation happened at — a library-only test cannot see this."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(distill.brain, "project_transcripts", lambda *_a, **_k: [])
    assert cli.main(["distill"]) == 0
    assert "distill:" in capsys.readouterr().out


def test_cli_passes_min_scripts_through(monkeypatch, tmp_path, capsys):
    path = _transcript(
        tmp_path, "solo", [_heredoc("import json\nPath('sources/extractions/a.json')")]
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(distill.brain, "project_transcripts", lambda *_a, **_k: [path])
    assert cli.main(["distill", "--min-scripts", "1"]) == 0
    assert "sources/extractions" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["--limit", "--min-scripts"])
def test_a_non_numeric_flag_falls_back_rather_than_raising(flag, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(distill.brain, "project_transcripts", lambda *_a, **_k: [])
    assert cli.main(["distill", flag, "not-a-number"]) == 0
    assert "distill:" in capsys.readouterr().out


def test_distill_is_never_a_gate(monkeypatch, tmp_path, capsys):
    """An rc of 0 even with candidates: an undistilled probe is a signal, not a failure."""
    path = _transcript(
        tmp_path,
        "repeat",
        [
            _heredoc("import json\nPath('sources/extractions/a.json')"),
            _heredoc("import json\nPath('sources/extractions/b.json')"),
        ],
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(distill.brain, "project_transcripts", lambda *_a, **_k: [path])
    assert cli.main(["distill"]) == 0
    assert "candidate(s)" in capsys.readouterr().out
