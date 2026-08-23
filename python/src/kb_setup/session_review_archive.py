# Copyright (c) 2026 Raymond Manaloto
"""Archive a session-review run into a tracked, reproducible directory.

`mise run kb-session-review-archive` — the other half of "every session-review
run always leaves a detailed report" (see `.claude/workflows/session-review.js`).
That change makes the workflow's return NAME every artifact it wrote; this
module is what turns that return into the tracked
`docs/session-review/runs/<date>-<n>/` directory, instead of the hand-assembly
every prior run required.

WHY A TASK, NOT A HAND COPY. `docs/session-review/runs/<date>-<n>/` has been
assembled by hand for every run so far — a `cp` per file, typed from memory of
what the run wrote. Two failure modes this module exists to close:

1. **The next run's evidence overwrites the previous run's.** Both existed
   dirs prior to this change (`2026-08-18-1`, `2026-08-18-2`) share the SAME
   root `reportDir` default (`.agent/kb/reports/agents`) that a fresh run also
   defaults to — so a second run with no dated `reportDir` argument would
   silently clobber the first run's lane reports before anyone archived them
   (#431). Archiving reads from wherever the caller says the run actually
   wrote, but the DESTINATION here is unconditionally fresh: it refuses to
   overwrite an existing `<date>-<n>/` directory rather than merging into one.
2. **"What did the review do" has no file to open.** A hand-copy skips
   whatever the copier forgot, and forgetting is silent — there is no green
   check for "you missed a file". This module REFUSES rather than silently
   omitting: no synthesis on disk is a hard refusal (rc 2, nothing written),
   because "a run always leaves a report" is exactly the contract this module
   exists to enforce, not merely to document.

TWO INPUT SHAPES, and record which. `archive()`'s `run_json` argument is the
workflow's return, which the harness renders as EITHER the tasks-output
envelope (`{agentCount, logs, result, summary, totalTokens, totalToolCalls,
workflowProgress}`) or the bare `result` object underneath it, depending on how
the caller captured it. Both are accepted; which one arrived is recorded in the
written `run.json["archive"]["input_shape"]` rather than normalised away, so a
later reader can tell which fields (`agentCount`, `totalTokens`) are even
possible to have been present.

THREE SHAPES ON THE README SIDE, and that is a DIFFERENT question from the one
above. The landing index at `docs/session-review/README.md` walks EVERY
existing `runs/<date>-<n>/` directory, and those directories were not all
written by this module — two pre-date it entirely:

- the NEW shape (what this module itself writes, and what `archive()` accepts
  as input): envelope-or-bare, `result.{confirmed,refuted,unverified,
  not_triaged}` as ARRAYS, `result.run_meta.{output,lanes}` when present;
- the OLD hand-archived shape (`runs/2026-08-18-1/run.json`): top-level
  `outcome.{confirmed,refuted,unverified,not_triaged,agents}` as NUMBERS
  (not list lengths) and `findings.{confirmed,refuted,not_triaged}` as arrays
  with no `findings.unverified` at all;
- NO `run.json` (`runs/2026-08-18-2/`): the run predates a `run.json` archive
  entirely and only carries ad-hoc hand-written files.

The README reader must survive all three, emitting `?` per field rather than
crashing or guessing — a crash on an old run would make every future archive
also fail to regenerate the index, and a guess (e.g. inferring `mode` from
which lanes appear) would misreport `2026-08-23-1`, whose lane set happens to
overlap both output modes.

VERBATIM MEANS BYTES (`.claude/rules/agent-artifact-conventions.md`,
`agent-report-persistence.md`). Every copied report is `read_bytes` ->
`write_bytes`; nothing here re-encodes, strips, or reformats what an agent
wrote. `docs/session-review/runs/**` is `hk.pkl`'s `proseExclude`, so
formatters and the spell-checker already leave it alone — this module is the
other half of that promise, holding it at the point of COPY rather than only
at the point of lint.

NO OVERWRITE, NO PARTIAL WRITE. Everything is staged into a
`tempfile.mkdtemp(dir=runs_root, prefix=".archive-")` sibling and only
renamed into its final name once every file has copied successfully; a
destination that already exists at rename time is a refusal (rc 2), not a
merge. A caller that dry-runs (`--dry-run`) sees the plan — the destination
name, which files would copy, which lane reports are missing — without any
write at all.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import msgspec

#: The shared, undated report directory every un-dated run and every
#: `kb-extract`-style caller defaults to. Archiving FROM this path is legal —
#: refusing it would make the tool useless for exactly the runs #431 describes
#: — but the refute-*.md glob under it may carry a PRIOR run's cross-check
#: evidence, since nothing scopes that directory to one run. Warn, don't drop.
_SHARED_REPORT_ROOT = Path(".agent") / "kb" / "reports" / "agents"

#: The synthesis filename REPORT_PROMPT (`session-review.js`) is told to write,
#: and the one file whose absence is a hard refusal — it is the artifact that
#: makes "a run always leaves a report" a checkable claim rather than a hope.
_SYNTHESIS_NAME = "session-review-synthesis.md"

#: The verbatim copy of whatever `--handoff` named, when a handoff was given.
_HANDOFF_NAME = "handoff.md"


class ArchiveOutcome(msgspec.Struct, frozen=True):
    """What one archive attempt did — or refused to do.

    `refusal` is the ONLY field that matters when it is not None: a refusal
    means nothing was written, `dest` is None, and every other field is at its
    empty default. A successful archive leaves `refusal` None and `dest` set.
    """

    dest: str | None
    files_written: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    index_rows: int = 0
    refusal: str | None = None


def _abs(repo_root: Path, value: str | Path) -> Path:
    """Resolve a possibly-relative path against `repo_root`.

    Every path this module handles — the CLI's `--report-dir`/`--handoff`
    flags, and the `report_dir`/`handoff_out` strings a workflow return
    embeds — is written as repo-relative by convention (`.agent/kb/reports/
    agents`, not an absolute path). Joining unconditionally when the value is
    not already absolute makes both sources behave the same way rather than
    silently depending on the caller's cwd.
    """
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _classify(data: dict) -> tuple[str, dict]:
    """Classify one run.json-shaped payload; see the module docstring.

    Returns `(shape, the_result_ish_dict)`. `archive()` only ever receives a
    FRESH workflow return, so it only expects `"envelope"`/`"bare"` back and
    refuses anything else; the README reader (`_readme_row`) additionally
    handles `"old"` and falls back to `"unknown"` for the third shape and for
    garbage, rendering `?` rather than raising.
    """
    result = data.get("result")
    if isinstance(result, dict):
        return "envelope", result
    outcome = data.get("outcome")
    if isinstance(outcome, dict):
        return "old", data
    if "confirmed" in data or "run_meta" in data:
        return "bare", data
    return "unknown", data


def _lane_keys(lanes: object) -> list[str]:
    """The `lane` field of every well-formed entry in a `lanes` array.

    Shared between the new shape's `result.lanes` and the old shape's
    top-level `lanes` — both are `[{lane, findings, coverage}, ...]`.
    """
    if not isinstance(lanes, list):
        return []
    return [
        entry["lane"]
        for entry in lanes
        if isinstance(entry, dict) and isinstance(entry.get("lane"), str)
    ]


def _copy_verbatim(src: Path, dest: Path) -> None:
    """Bytes in, bytes out. No re-encoding, no reformatting, no line-ending fix."""
    dest.write_bytes(src.read_bytes())


def _latest_session_date(result: dict) -> str | None:
    """The date this run's evidence is dated by, derived from ITS OWN sessions.

    NEVER a clock — the archive may run long after the workflow finished, and
    `--date` exists precisely so a caller can override this when it matters.
    `result.run_meta.sessions` may hold OBJECT entries (each with a
    `started_at` ISO string) or BARE STRINGS (a path, `s.path || s` in the
    workflow) with no timestamp at all; only the objects contribute. When none
    do — a bare-string-only session list, or a `run_meta`-less legacy return —
    this returns None and the caller must supply `--date` explicitly.
    """
    run_meta = result.get("run_meta")
    if not isinstance(run_meta, dict):
        return None
    sessions = run_meta.get("sessions")
    if not isinstance(sessions, list):
        return None
    started_ats = [
        entry["started_at"]
        for entry in sessions
        if isinstance(entry, dict)
        and isinstance(entry.get("started_at"), str)
        and entry["started_at"]
    ]
    if not started_ats:
        return None
    # ISO-8601 UTC timestamps compare correctly as strings (session_select.py
    # relies on the same property); the newest one's date prefix is the answer.
    return max(started_ats)[:10]


def _next_run_name(runs_root: Path, date: str) -> str:
    """`<date>-<n>`, `n` = 1 + the highest existing `<n>` for that date."""
    highest = 0
    if runs_root.is_dir():
        prefix = f"{date}-"
        for entry in runs_root.iterdir():
            if entry.is_dir() and entry.name.startswith(prefix):
                suffix = entry.name[len(prefix) :]
                if suffix.isdigit():
                    highest = max(highest, int(suffix))
    return f"{date}-{highest + 1}"


def _load_run_json(run_json: Path) -> tuple[dict, str, dict] | ArchiveOutcome:
    """Read + parse + classify `run_json`. Returns `(data, input_shape, result)`."""
    try:
        raw = run_json.read_bytes()
    except OSError as exc:
        return ArchiveOutcome(dest=None, refusal=f"cannot read --run-json {run_json}: {exc}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ArchiveOutcome(dest=None, refusal=f"--run-json {run_json} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        return ArchiveOutcome(dest=None, refusal=f"--run-json {run_json} is not a JSON object")

    input_shape, result = _classify(data)
    if input_shape not in ("envelope", "bare"):
        return ArchiveOutcome(
            dest=None,
            refusal=(
                f"--run-json {run_json} is not a recognised workflow return "
                "(expected the harness envelope or a bare result object)"
            ),
        )
    return data, input_shape, result


def _resolve_report_dir(
    repo_root: Path, report_dir: Path | None, result: dict
) -> Path | ArchiveOutcome:
    """`--report-dir`, or `result.artifacts.report_dir` when it was not given."""
    if report_dir is not None:
        return _abs(repo_root, report_dir)
    artifacts = result.get("artifacts")
    candidate = artifacts.get("report_dir") if isinstance(artifacts, dict) else None
    if not candidate:
        return ArchiveOutcome(
            dest=None,
            refusal=(
                "no --report-dir given and result.artifacts.report_dir is "
                "absent from the run JSON — state --report-dir explicitly"
            ),
        )
    return _abs(repo_root, candidate)


def _check_synthesis(synthesis_src: Path) -> ArchiveOutcome | None:
    """The one hard refusal that makes `archive()` a checkable contract."""
    if synthesis_src.is_file():
        return None
    return ArchiveOutcome(
        dest=None,
        refusal=(
            f"no synthesis at {synthesis_src} — the run did not leave a "
            "report; this is the contract the archive exists to enforce"
        ),
    )


def _resolve_handoff(
    repo_root: Path, handoff: Path | None, result: dict
) -> Path | ArchiveOutcome | None:
    """`--handoff` (refused if given but missing), else the AUTO-DETECTED one.

    Auto-detection only fires when `result.artifacts.handoff_out` names a path
    that actually exists on disk — an un-run handoff-mode composer, or a
    report-mode run with no handoff at all, both leave this None rather than
    inventing a refusal for a file nobody claimed should exist.
    """
    if handoff is not None:
        resolved = _abs(repo_root, handoff)
        if not resolved.is_file():
            return ArchiveOutcome(dest=None, refusal=f"--handoff {resolved} does not exist")
        return resolved
    artifacts = result.get("artifacts")
    candidate = artifacts.get("handoff_out") if isinstance(artifacts, dict) else None
    auto = _abs(repo_root, candidate) if candidate else None
    return auto if auto is not None and auto.is_file() else None


def _resolve_date(date: str | None, result: dict) -> str | ArchiveOutcome:
    """`--date`, or the latest `result.run_meta.sessions[].started_at`."""
    if date is not None:
        return date
    derived = _latest_session_date(result)
    if derived is None:
        return ArchiveOutcome(
            dest=None,
            refusal=(
                "no --date given and result.run_meta.sessions carries no "
                "usable started_at — state --date YYYY-MM-DD explicitly"
            ),
        )
    return derived


def archive(
    repo_root: Path,
    *,
    run_json: Path,
    report_dir: Path | None,
    handoff: Path | None,
    date: str | None,
    dry_run: bool = False,
) -> ArchiveOutcome:
    """Archive one session-review run's return into `docs/session-review/runs/`.

    See the module docstring for the refusal conditions and the staging
    protocol. Every refusal leaves the filesystem untouched — no temp
    directory, no partial destination. The six keyword-only parameters mirror
    the CLI's flags 1:1 (`--run-json`/`--report-dir`/`--handoff`/`--date`/
    `--dry-run`) — see the `PLR0913` per-file-ignore in `pyproject.toml`.
    """
    loaded = _load_run_json(run_json)
    if isinstance(loaded, ArchiveOutcome):
        return loaded
    data, input_shape, result = loaded

    resolved_report_dir = _resolve_report_dir(repo_root, report_dir, result)
    if isinstance(resolved_report_dir, ArchiveOutcome):
        return resolved_report_dir

    synthesis_src = resolved_report_dir / _SYNTHESIS_NAME
    refusal = _check_synthesis(synthesis_src)
    if refusal is not None:
        return refusal

    resolved_handoff = _resolve_handoff(repo_root, handoff, result)
    if isinstance(resolved_handoff, ArchiveOutcome):
        return resolved_handoff

    resolved_date = _resolve_date(date, result)
    if isinstance(resolved_date, ArchiveOutcome):
        return resolved_date

    runs_root = repo_root / "docs" / "session-review" / "runs"
    dest = runs_root / _next_run_name(runs_root, resolved_date)

    plan = _Plan(
        data=data,
        result=result,
        input_shape=input_shape,
        report_dir=resolved_report_dir,
        synthesis_src=synthesis_src,
        handoff_src=resolved_handoff,
        dest=dest,
        run_json=run_json,
    )
    return _preview(repo_root, plan) if dry_run else _write(repo_root, runs_root, plan)


@dataclass(frozen=True)
class _Plan:
    """Everything `archive()` resolved before staging or previewing."""

    data: dict
    result: dict
    input_shape: str
    report_dir: Path
    synthesis_src: Path
    handoff_src: Path | None
    dest: Path
    run_json: Path


def _lane_and_refute_sources(plan: _Plan) -> tuple[list[tuple[str, Path]], list[str], list[Path]]:
    """Which lane-report files exist, which are missing, and every `refute-*.md`.

    Split out of `_write`/`_preview` so both share the exact same file list —
    a dry-run must preview the plan the real run would execute, not a
    re-derivation that could disagree with it.
    """
    present: list[tuple[str, Path]] = []
    missing: list[str] = []
    for lane_key in _lane_keys(plan.result.get("lanes")):
        src = plan.report_dir / f"{lane_key}.md"
        if src.is_file():
            present.append((f"{lane_key}.md", src))
        else:
            missing.append(f"{lane_key}.md")
    refute_files = sorted(plan.report_dir.glob("refute-*.md"))
    return present, missing, refute_files


def _shared_root_warning(repo_root: Path, report_dir: Path) -> str | None:
    if report_dir != repo_root / _SHARED_REPORT_ROOT:
        return None
    return (
        f"report_dir is the SHARED root {_SHARED_REPORT_ROOT} — the refute-*.md "
        "glob may carry an earlier run's refutations (#431); archiving them "
        "anyway rather than dropping cross-check evidence"
    )


def _preview(repo_root: Path, plan: _Plan) -> ArchiveOutcome:
    """The dry-run path: report the plan, write nothing."""
    present, missing, refute_files = _lane_and_refute_sources(plan)
    files = [_SYNTHESIS_NAME, *(name for name, _ in present), *(p.name for p in refute_files)]
    if plan.handoff_src is not None:
        files.append(_HANDOFF_NAME)
    files.append("run.json")
    warnings = []
    warning = _shared_root_warning(repo_root, plan.report_dir)
    if warning is not None:
        warnings.append(warning)
    return ArchiveOutcome(
        dest=str(plan.dest.relative_to(repo_root)),
        files_written=tuple(files),
        missing=tuple(missing),
        warnings=tuple(warnings),
        index_rows=0,
        refusal=None,
    )


def _stage(repo_root: Path, plan: _Plan, tmp_dir: Path) -> tuple[list[str], list[str], list[str]]:
    """Copy every artifact into `tmp_dir` and write its `run.json`.

    Returns `(files_written, missing, warnings)`. Raises on any `OSError` from
    a copy — the caller is responsible for cleaning up `tmp_dir` when this
    does not return normally; staging never touches `plan.dest`.
    """
    files_written: list[str] = [_SYNTHESIS_NAME]
    _copy_verbatim(plan.synthesis_src, tmp_dir / _SYNTHESIS_NAME)

    present, missing, refute_files = _lane_and_refute_sources(plan)
    for name, src in present:
        _copy_verbatim(src, tmp_dir / name)
        files_written.append(name)
    for src in refute_files:
        _copy_verbatim(src, tmp_dir / src.name)
        files_written.append(src.name)

    warnings: list[str] = []
    warning = _shared_root_warning(repo_root, plan.report_dir)
    if warning is not None:
        warnings.append(warning)

    if plan.handoff_src is not None:
        _copy_verbatim(plan.handoff_src, tmp_dir / _HANDOFF_NAME)
        files_written.append(_HANDOFF_NAME)

    combined = dict(plan.data)
    combined["archive"] = {
        "archived_from": str(plan.run_json.resolve()),
        "report_dir": str(plan.report_dir.relative_to(repo_root)),
        "input_shape": plan.input_shape,
        "files": list(files_written),
        "missing": list(missing),
        "refute_reports_note": "expected paths from the return; actual files matched by glob",
    }
    (tmp_dir / "run.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files_written.append("run.json")
    return files_written, missing, warnings


def _write(repo_root: Path, runs_root: Path, plan: _Plan) -> ArchiveOutcome:
    """Stage every file into a temp sibling, then atomically rename into place.

    `renamed` tracks whether the rename actually landed the directory at
    `plan.dest`: the `finally` block removes `tmp_dir` on every OTHER path
    (a staging exception, an existing `plan.dest`, or a failed rename) and
    leaves it alone on success, since a renamed directory no longer exists at
    the temp path there is nothing left to remove.
    """
    runs_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(dir=runs_root, prefix=".archive-"))
    renamed = False
    try:
        files_written, missing, warnings = _stage(repo_root, plan, tmp_dir)

        if plan.dest.exists():
            return ArchiveOutcome(
                dest=None, refusal=f"{plan.dest} already exists — refusing to overwrite"
            )
        try:
            tmp_dir.rename(plan.dest)
            renamed = True
        except OSError as exc:
            return ArchiveOutcome(dest=None, refusal=f"could not rename into {plan.dest}: {exc}")
    finally:
        if not renamed:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    index_rows = regenerate_readme(repo_root)
    return ArchiveOutcome(
        dest=str(plan.dest.relative_to(repo_root)),
        files_written=tuple(files_written),
        missing=tuple(missing),
        warnings=tuple(warnings),
        index_rows=index_rows,
        refusal=None,
    )


@dataclass
class _Counts:
    """One README row's typed fields, `"?"` where the source shape can't say."""

    mode: str = "?"
    lanes: str = "?"
    confirmed: str = "?"
    refuted: str = "?"
    not_triaged: str = "?"
    unverified: str = "?"
    agents: str = "?"
    tokens: str = "?"


@dataclass
class _Row:
    """One rendered README table row."""

    run: str
    counts: _Counts = field(default_factory=_Counts)
    synthesis: str = "—"
    handoff: str = "—"


def _counts_from_new_shape(data: dict, result: dict) -> _Counts:
    """The envelope-or-bare shape this module itself writes (and may receive)."""
    counts = _Counts()
    run_meta = result.get("run_meta")
    if isinstance(run_meta, dict):
        output = run_meta.get("output")
        if isinstance(output, str):
            counts.mode = output
        lanes = run_meta.get("lanes")
        if isinstance(lanes, list) and lanes:
            counts.lanes = ",".join(str(entry) for entry in lanes)
    if counts.lanes == "?":
        keys = _lane_keys(result.get("lanes"))
        if keys:
            counts.lanes = ",".join(keys)
    for attr in ("confirmed", "refuted", "not_triaged", "unverified"):
        value = result.get(attr)
        if isinstance(value, list):
            setattr(counts, attr, str(len(value)))
    agent_count = data.get("agentCount")
    if isinstance(agent_count, int):
        counts.agents = str(agent_count)
    total_tokens = data.get("totalTokens")
    if isinstance(total_tokens, int):
        counts.tokens = str(total_tokens)
    return counts


def _counts_from_old_shape(data: dict) -> _Counts:
    """`runs/2026-08-18-1/run.json`'s pre-existing shape: `outcome` holds NUMBERS."""
    counts = _Counts()
    keys = _lane_keys(data.get("lanes"))
    if keys:
        counts.lanes = ",".join(keys)
    outcome = data.get("outcome")
    if isinstance(outcome, dict):
        for attr in ("confirmed", "refuted", "not_triaged", "unverified", "agents"):
            value = outcome.get(attr)
            if isinstance(value, int):
                setattr(counts, attr, str(value))
    return counts


def _readme_row(run_dir: Path) -> _Row:
    """One row, reading whichever of the three shapes `run_dir` actually has.

    Never raises: a directory this cannot make sense of still gets a row of
    `?`s and a link into the directory itself, so a reader can browse whatever
    IS there (`runs/2026-08-18-2/`'s two oddly-named files, for instance) even
    when nothing here recognises the shape.
    """
    name = run_dir.name
    synthesis_link = (
        f"[synthesis](runs/{name}/{_SYNTHESIS_NAME})"
        if (run_dir / _SYNTHESIS_NAME).is_file()
        else "—"
    )
    handoff_link = (
        f"[handoff](runs/{name}/{_HANDOFF_NAME})" if (run_dir / _HANDOFF_NAME).is_file() else "—"
    )
    row = _Row(run=f"[{name}](runs/{name}/)", synthesis=synthesis_link, handoff=handoff_link)

    run_json_path = run_dir / "run.json"
    if not run_json_path.is_file():
        return row
    try:
        data = json.loads(run_json_path.read_text(encoding="utf-8"))
    # PEP 758: unparenthesized multi-exception `except` is valid on Python
    # 3.14, and this repo's ruff config (target-version py314) ACTIVELY STRIPS
    # the parentheses via `mise run fmt` — see session_select.py's identical
    # comment. Written unparenthesized here to begin with.
    except OSError, json.JSONDecodeError:
        return row
    if not isinstance(data, dict):
        return row

    shape, result = _classify(data)
    if shape in ("envelope", "bare"):
        row.counts = _counts_from_new_shape(data, result)
    elif shape == "old":
        row.counts = _counts_from_old_shape(data)
    return row


_README_COLUMNS = (
    "run",
    "mode",
    "lanes",
    "confirmed",
    "refuted",
    "not-triaged",
    "unverified",
    "agents",
    "tokens",
    "synthesis",
    "handoff",
)


def _render_readme(rows: list[_Row]) -> str:
    intro = (
        "Generated by `mise run kb-session-review-archive` — do not hand-edit; "
        "edit `python/src/kb_setup/session_review_archive.py` instead. One row "
        "per `docs/session-review/runs/<date>-<n>/` directory, oldest first by "
        "name. `?` means the field could not be read from that run's shape — "
        "the module docstring names the three shapes this reads."
    )
    lines = [
        "# Session-review runs",
        "",
        intro,
        "",
        "| " + " | ".join(_README_COLUMNS) + " |",
        "|" + "|".join("---" for _ in _README_COLUMNS) + "|",
    ]
    for row in rows:
        c = row.counts
        lines.append(
            f"| {row.run} | {c.mode} | {c.lanes} | {c.confirmed} | {c.refuted} | "
            f"{c.not_triaged} | {c.unverified} | {c.agents} | {c.tokens} | "
            f"{row.synthesis} | {row.handoff} |"
        )
    if not rows:
        lines.extend(["", "_No runs archived yet._"])
    return "\n".join(lines) + "\n"


def regenerate_readme(repo_root: Path) -> int:
    """Rebuild `docs/session-review/README.md` from every `runs/<date>-<n>/` dir.

    Public — not just an `archive()` internal — so the FIRST generation can be
    produced standalone, before any run has been archived by this module, and
    so a caller can force a regeneration (e.g. after hand-editing a stray
    run directory) without archiving anything new. Returns the row count.
    """
    runs_root = repo_root / "docs" / "session-review" / "runs"
    rows = []
    if runs_root.is_dir():
        rows = [
            _readme_row(entry)
            for entry in sorted(runs_root.iterdir())
            if entry.is_dir() and not entry.name.startswith(".")
        ]
    readme_path = repo_root / "docs" / "session-review" / "README.md"
    readme_path.write_text(_render_readme(rows), encoding="utf-8")
    return len(rows)


def _opt(args: list[str], flag: str) -> str | None:
    """Read `--flag value` from a manual arg list — the `cli.py::_opt` shape."""
    if flag in args and args.index(flag) + 1 < len(args):
        return args[args.index(flag) + 1]
    return None


_USAGE = (
    "kb-setup session-review-archive --run-json PATH [--report-dir DIR] "
    "[--handoff PATH] [--date YYYY-MM-DD] [--dry-run]"
)


def main(args: list[str], repo_root: Path) -> int:
    """`kb-setup session-review-archive …` — the CLI boundary `cli.py` dispatches to."""
    run_json_str = _opt(args, "--run-json")
    if not run_json_str:
        print(_USAGE, file=sys.stderr)
        return 2

    report_dir_str = _opt(args, "--report-dir")
    handoff_str = _opt(args, "--handoff")
    outcome = archive(
        repo_root,
        run_json=Path(run_json_str),
        report_dir=Path(report_dir_str) if report_dir_str else None,
        handoff=Path(handoff_str) if handoff_str else None,
        date=_opt(args, "--date"),
        dry_run="--dry-run" in args,
    )

    if outcome.refusal is not None:
        print(f"session-review-archive: REFUSED — {outcome.refusal}", file=sys.stderr)
        return 2

    for missing in outcome.missing:
        print(f"session-review-archive: missing (not fatal): {missing}", file=sys.stderr)
    for warning in outcome.warnings:
        print(f"session-review-archive: WARNING — {warning}", file=sys.stderr)

    verb = "would write" if "--dry-run" in args else "wrote"
    print(
        f"session-review-archive: {verb} {outcome.dest} "
        f"({len(outcome.files_written)} file(s)); "
        f"README.md regenerated ({outcome.index_rows} row(s))"
    )
    return 0
