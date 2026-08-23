# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.workflow_lint` — the U8b0 transform-then-lint gate.

The interesting assertions are the FAIL direction and the line-number-fidelity
claim, per `probes-need-a-control-arm.md`: a gate proven only on clean input,
or one whose reported line numbers were never checked against the real file,
has demonstrated nothing. Every test here calls the REAL `biome` binary — a
mocked subprocess could not be evidence that biome actually catches a break.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import workflow_lint
from kb_setup.result import Err, External, Rc

_META = """export const meta = {
  name: 'x',
  description: 'a tiny fixture workflow',
}

"""

#: Meta is declared but never referenced elsewhere — the shape that produced
#: the `noUnusedVariables` artifact on the real `kb-extract.js`/
#: `kb-tool-review.js` before this gate's config neutralized it.
_CLEAN_UNUSED_META = (
    _META
    + """const found = await agent('do a thing', {schema: {}})
const audits = await pipeline(found.files, (file) => agent(`audit ${file}`))

return audits.filter(Boolean)
"""
)

#: Meta IS referenced elsewhere (like the real `session-review.js`) — the
#: shape that never needed the unused-variable exemption in the first place.
_CLEAN_USED_META = (
    _META
    + """log(`running ${meta.name}`)
const found = await agent('do a thing', {schema: {}})

return { found, name: meta.name }
"""
)


def _write_workflow(root: Path, name: str, body: str) -> Path:
    d = root / ".claude" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


# --- transform() : pure function, no subprocess ---------------------------


def test_transform_replaces_export_line_in_place_and_appends_closer() -> None:
    out = workflow_lint.transform(_CLEAN_UNUSED_META, name="fixture.js")
    lines = out.splitlines()
    assert lines[0] == "(async () => { const meta = {"
    # Every line of the ORIGINAL after the export line is untouched and at
    # the SAME index — this is the whole line-number-fidelity claim, checked
    # end-to-end (via biome) in test_line_numbers_survive_the_transform below.
    assert lines[-1] == "})()"
    assert lines[-2] == "return audits.filter(Boolean)"


def test_transform_preserves_total_original_line_count_plus_one_closer() -> None:
    original_lines = _CLEAN_UNUSED_META.splitlines()
    out = workflow_lint.transform(_CLEAN_UNUSED_META, name="fixture.js")
    # +1 for the appended closer; the export line was REPLACED, not inserted
    # before, so nothing else shifts.
    assert len(out.splitlines()) == len(original_lines) + 1


def test_transform_raises_shape_error_with_no_export_const_meta() -> None:
    with pytest.raises(workflow_lint.ShapeError, match="export const meta"):
        workflow_lint.transform("const x = 1\nreturn x\n", name="broken.js")


# --- run() : real biome, real files -----------------------------------------


def test_run_clean_workflow_with_unused_meta_returns_zero(tmp_path: Path) -> None:
    """The exact false-positive class this gate's config exists to neutralize."""
    _write_workflow(tmp_path, "a.js", _CLEAN_UNUSED_META)
    result = workflow_lint.run(tmp_path)
    assert isinstance(result, External)
    assert result.code == 0


def test_run_clean_workflow_with_used_meta_returns_zero(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "a.js", _CLEAN_USED_META)
    result = workflow_lint.run(tmp_path)
    assert isinstance(result, External)
    assert result.code == 0


def test_run_a_realistic_break_returns_nonzero(tmp_path: Path) -> None:
    """FAIL arm: truncate the `pipeline(...)` call.

    An accidentally-dropped closing paren — a realistic break, not a rename
    (`probes-need-a-control-arm.md` — a mutation must actually destroy what
    the check looks for).

    Truncation, not "delete the declaration and leave the dangling
    reference": that shape was tried first and biome's DEFAULT rule set does
    NOT flag it — `noUndeclaredVariables` is not in biome's recommended set
    (confirmed via `biome explain noUndeclaredVariables`, no "This rule is
    recommended" line, unlike `noUnusedVariables`'s explain output) — so a
    dangling reference to a deleted local is a runtime-only bug. That is
    explicitly out of this gate's scope: "You cannot run these workflows...
    validation that each workflow still executes correctly is the CALLER's
    integration step" (rev2 constraints). A syntactic truncation is squarely
    IN scope — it is the exact class of break the whole gate exists to catch
    — and the rev2 fail-arm instruction names it as an equally valid choice
    ("delete a line that calls a function, OR truncate a block").
    """
    broken = _CLEAN_UNUSED_META.replace(
        "agent(`audit ${file}`))\n",
        "agent(`audit ${file}`\n",  # dropped the call's closing paren
    )
    # Confirm the mutation actually landed before trusting the result below —
    # otherwise a no-op replace would make this test pass for the wrong reason.
    assert broken != _CLEAN_UNUSED_META
    _write_workflow(tmp_path, "a.js", broken)
    result = workflow_lint.run(tmp_path)
    assert isinstance(result, External)
    assert result.code != 0


def test_run_restoring_the_break_returns_zero_again(tmp_path: Path) -> None:
    """The other half of the control arm: the SAME fixture, unbroken, is clean."""
    _write_workflow(tmp_path, "a.js", _CLEAN_UNUSED_META)
    result = workflow_lint.run(tmp_path)
    assert isinstance(result, External)
    assert result.code == 0


def _capture_run_output(root: Path) -> str:
    """Re-run and capture stdout, for the one test that needs biome's exact text."""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        workflow_lint.run(root)
    return buf.getvalue()


#: A lint finding, not a parse error — deliberately. Probed first: an
#: unterminated call's parse error is reported at the transform's APPENDED
#: closer line (the point biome gives up looking for the matching paren),
#: not at the line the break actually sits on — which would make this test
#: assert something the transform never promised. A lint diagnostic (like
#: `useTemplate` on a string concatenation) is token-precise and reports
#: exactly where the offending expression sits, which is what rev2's
#: requirement ("break line N ... confirm the reported line is N") actually
#: needs to hold against.
_LINE_FIDELITY_MARKER = "const label = 'audit:' + found.id"
_LINE_FIDELITY_FIXTURE = (
    _META
    + f"""const found = await agent('do a thing', {{schema: {{}}}})
{_LINE_FIDELITY_MARKER}
const audits = await pipeline(found.files, (file) => agent(`audit ${{file}}`))

return {{ audits: audits.filter(Boolean), label }}
"""
)


def test_line_numbers_survive_the_transform(tmp_path: Path) -> None:
    """Break line N of a real file; confirm the reported line is N.

    Not "close to" N. `.claude/workflows/session-review.js` is 1,408 lines; a
    transform that shifts everything after the meta block would misreport
    almost every finding in that file. This is rev2's explicit requirement.
    """
    lines = _LINE_FIDELITY_FIXTURE.splitlines()
    marker_line_no = next(i for i, ln in enumerate(lines, start=1) if ln == _LINE_FIDELITY_MARKER)
    p = _write_workflow(tmp_path, "a.js", _LINE_FIDELITY_FIXTURE)
    real_path = workflow_lint.WORKFLOWS_DIR / p.name
    output = _capture_run_output(tmp_path)
    assert f"{real_path}:{marker_line_no}:" in output, output


def test_run_missing_export_const_meta_is_findings_not_a_crash(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "a.js", "const x = 1\nreturn x\n")
    result = workflow_lint.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.FINDINGS
    assert "export const meta" in result.message


def test_run_with_no_workflow_files_is_not_run(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "workflows").mkdir(parents=True)
    result = workflow_lint.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_run_the_real_committed_workflows_is_clean() -> None:
    """The whole point: exactly what `mise run lint` invokes, for real.

    Against the real repo, on the files as committed — not a synthetic
    fixture.
    """
    repo_root = Path(__file__).resolve().parent.parent
    result = workflow_lint.run(repo_root)
    assert isinstance(result, External), result
    assert result.code == 0, result.message
