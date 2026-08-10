# Copyright (c) 2026 Raymond Manaloto
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
from kb_setup.result import Ok, Rc, exit_code


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


def test_tab_indented_closer_terminates_a_dash_heredoc():
    """Cold lane P1 on c1374b99e032, corrected by round 2 and by real bash.

    `<<-` strips leading TABS, so a tab-indented terminator really does end the
    heredoc — and demanding column 0 made the lazy body run forward to the next
    column-0 delimiter. Verified against bash:

        cat <<-'PY' … <TAB>PY   -> body is `line1` alone
    """
    command = (
        "for f in a b; do\n"
        "\tpython3 - <<-'PY'\n"
        "\timport json\n"
        "\tprint(f)\n"
        "\tPY\n"
        "done\n"
        "echo unrelated\n"
        "PY\n"
    )
    found = list(distill.detect_scripts(command))
    assert len(found) == 1
    body = found[0][1]
    assert "import json" in body
    for leaked in ("done", "echo unrelated"):
        assert leaked not in body, f"{leaked!r} leaked into the captured script body"


def test_space_indented_closer_does_not_terminate_a_dash_heredoc():
    r"""The MIRROR of the test above, and the defect round 2 caught.

    Bash's `<<-` strips TABS only. A space-indented line equal to the delimiter
    is ordinary body content, so treating it as a terminator silently truncates
    the rest of a real script. Verified against bash:

        cat <<-'PY' … `    PY` … line2 … PY  -> body is `line1\\n    PY\\nline2`
    """
    command = "python3 - <<-'PY'\nimport json\n    PY\nprint(1)\nPY\n"
    found = list(distill.detect_scripts(command))
    assert len(found) == 1
    assert "print(1)" in found[0][1], "a SPACE-indented line ended a <<- heredoc early"


def test_plain_heredoc_still_requires_column_zero():
    """A plain `<<` terminator must be at column 0 in bash, indent of any kind."""
    for indent in ("    ", "\t"):
        command = f"python3 - <<'PY'\nimport json\n{indent}PY\nprint(1)\nPY\n"
        found = list(distill.detect_scripts(command))
        assert len(found) == 1
        assert "print(1)" in found[0][1], f"indent {indent!r} ended a plain heredoc early"


def test_escaped_quote_does_not_truncate_a_double_quoted_payload():
    """Cold lane P2 on c1374b99e032: truncation fell under the floor, so ALL of it vanished."""
    payload = 'print(\\"hi\\"); x=1;' + ("y=2;" * 30)
    assert len(payload) >= distill.MIN_INLINE_CHARS
    found = list(distill.detect_scripts(f'python3 -c "{payload}"'))
    assert [k for k, _ in found] == ["inline"]
    assert len(found[0][1]) == len(payload)


def test_a_single_quoted_payload_has_no_escapes():
    r"""The MIRROR of the test above — cold lane round 2, P1 on 37020536f63c.

    Bash single quotes have NO escape mechanism: a trailing backslash is
    literal and the very next `'` closes the string. Treating `\\'` as an escaped
    quote kept scanning and glued unrelated shell text into the reported script.
    Verified against bash:

        bash -c "echo 'print(1)\\' AFTERQUOTE"  ->  print(1)\\ AFTERQUOTE
    """
    payload = "print(1); x=1;" + ("y=2;" * 30) + "\\"
    assert len(payload) >= distill.MIN_INLINE_CHARS
    command = f"python3 -c '{payload}' && echo AFTERQUOTE_SHOULD_NOT_LEAK"
    found = list(distill.detect_scripts(command))
    assert len(found) == 1
    assert "AFTERQUOTE_SHOULD_NOT_LEAK" not in found[0][1]
    assert found[0][1] == payload


def test_a_vendored_clones_source_tree_is_still_ad_hoc():
    """Cold lane P3 on c1374b99e032 — somebody else's python/src is not ours."""
    assert distill.repo_source("/repo/python/src/kb_setup/x.py") is True
    assert distill.repo_source("/repo/sources/vendored/python/src/thing.py") is False
    assert distill.repo_source("/scratch/apython/src/foo.py") is False


def test_the_vendored_marker_only_disqualifies_when_it_comes_first():
    """The MIRROR of the test above — cold lane round 2, P3 on 37020536f63c.

    A bare substring test would disown our own source for containing the word
    `sources` further down the path. Position is the question, not presence.
    """
    assert distill.repo_source("/repo/python/src/kb_setup/sources/x.py") is True
    assert distill.repo_source("/repo/tests/raw/fixture.py") is True
    assert distill.repo_source("/repo/sources/v/python/src/kb_setup/sources/x.py") is False


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


# --------------------------------------------------------------------------
# The `check_distill` boundary (§2 R5)
# --------------------------------------------------------------------------
#
# This is the module where the conversion is genuinely informative rather than
# mechanical. `distill` FINDS things — that is its entire job — and it still
# must never return `Rc.FINDINGS`, because that is a code a caller can gate on
# and #219 rules this analyser advisory. The leads travel in the VALUE.
#
# No int assertion can see that: `distill_main` returned a literal 0 before and
# an `exit_code` of 0 after, whatever the report said.


def _with_transcripts(monkeypatch, paths) -> None:
    """Point the boundary's transcript discovery at a fixture, not the real machine."""
    monkeypatch.setattr(distill.brain, "transcripts_base", lambda: Path("/nonexistent"))
    # `**_kw` rather than a named `limit`: the caller passes it as a KEYWORD, so a
    # positional-looking stub raises TypeError and the test fails for a reason
    # that has nothing to do with what it is measuring.
    monkeypatch.setattr(distill.brain, "project_transcripts", lambda _base, _root, **_kw: paths)


def test_distill_a_proposal_is_ok_with_rc_ok_not_findings(tmp_path, monkeypatch):
    """The load-bearing arm: it FOUND something and the rc is still OK.

    If someone "improves" this to `Rc.FINDINGS` because a candidate was found,
    `kb-distill` starts failing any build it is wired into — the exact outcome
    #219's never-a-gate decision rules out. Every pre-existing assertion in this
    file stays green through that change; only this test notices.
    """
    path = _transcript(
        tmp_path,
        "repeat",
        [_heredoc("import json\nPath('graphify-out/graph.json')")] * 3,
    )
    _with_transcripts(monkeypatch, [path])

    result = distill.check_distill(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    assert result.rc is not Rc.FINDINGS


def test_distill_a_one_off_session_proposes_nothing_and_is_ok(tmp_path, monkeypatch):
    """CONTROL ARM: the test above is not merely observing "this boundary is always OK".

    Same rc, DIFFERENT rendered text — three probes that each ask a different
    question, so the detector ran and correctly found nothing. Without this
    contrast the test above could not tell a real proposal from an empty one.
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
    _with_transcripts(monkeypatch, [path])

    result = distill.check_distill(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    assert "nothing to propose" in result.value


def test_distill_no_transcripts_at_all_is_the_documented_divergence(tmp_path, monkeypatch):
    """Zero transcripts reports `Rc.OK` while SAYING the detector did not run.

    Pinned, not endorsed — and this module states the contradiction in its own
    output: *"NO TRANSCRIPTS FOUND — the detector did not run. This is not a
    clean result."* By this repo's doctrine that is `Rc.NOT_RUN`, which is
    exactly what `skill_lint` returns for the structurally identical case.

    It stays `OK` because the R5 conversion is behaviour-preserving by rule, so
    the pre-existing exit-code assertions remain a valid regression arm. The
    third module with this shape (`md_budget`'s `counted == 0` is the other),
    which is why it is being filed as one gap rather than fixed three times in
    a conversion nobody would review as a behaviour change.
    """
    _with_transcripts(monkeypatch, [])

    result = distill.check_distill(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    assert "did not run" in result.value


def test_distill_boundary_prints_nothing(tmp_path, monkeypatch, capsys):
    """Rendering belongs to `distill_main`; the boundary returns the text."""
    _with_transcripts(monkeypatch, [])

    distill.check_distill(tmp_path)
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""


def test_distill_int_wrapper_is_exit_code_of_boundary(tmp_path, monkeypatch):
    """The equivalence that makes the split safe."""
    _with_transcripts(monkeypatch, [])
    assert distill.distill_main(tmp_path) == exit_code(distill.check_distill(tmp_path))
