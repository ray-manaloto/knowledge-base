# Copyright (c) 2026 Raymond Manaloto
"""Staleness gate for the ONE tracked file under `graphify-out/reflections/` (#212).

WHAT #212 WAS. `graphify-out/reflections/LESSONS.md` is the only durable output of
the self-improving loop this repo mandates closing on every ingestion
(`notepad-enforcement.md`), and it was gitignored — so a consumer repo, a fresh
clone, or another machine had no lessons at all, while `CLAUDE.md` and the rules
described it as the durable cross-session half. Ray ruled the fix on 2026-08-10:
track it, **and gate it**, because tracking a derived file with no sync check is
how this repo gets a *generated, never edited* lie, and a stale lessons file is
worse than an absent one — an absent one is not believed.

WHAT THE GATE ASSERTS. The tracked bytes equal what `kb-reflect` would produce
right now from the committed `graphify-out/memory/` plus the local graph. Byte
equality, not a fingerprint: `size:mtime_ns` cannot see an unchanged-but-stale
file, which is the defect #182 already paid for one directory over.

WHY A SKIP EXISTS, AND WHY IT IS NOT A PASS. `kb-reflect` passes `--graph`, so the
tracked file's `## By topic` section and its source-node filtering both come from
`graph.json` + two sidecars — all derived, all gitignored, and ~672 MB. A machine
without them cannot answer the question. Measured on the day the gate was written:

| regenerated | bytes | equals the tracked file |
|---|---:|---|
| with the graph | 62,888 | **yes** |
| without the graph | 30,953 | no — the topic section and deleted nodes come back |

So a graph-less run does not produce a weaker version of the answer; it produces a
different file. Reporting OK there would be a gate that never asked the question,
which is why the no-graph path is `Rc.NOT_RUN` (127) and never 0
(`probes-need-a-control-arm.md`).

COST, measured, because it is why this is a `kb-gates` task and not an hk step:
7.15s and ~2.9 GB peak RSS, essentially all of it two `json.loads` of the 672 MB
graph inside graphify's own loaders. hk runs steps in parallel on every commit;
that footprint does not belong there. As a gate it is exclusive by default
(`gates.CONCURRENT_SAFE` names the four that were measured safe to race, and this
is deliberately not one of them) and costs ~7s against a ~249s run.
"""

from __future__ import annotations

import difflib
import subprocess
import tempfile
from pathlib import Path

from kb_setup import events
from kb_setup.graphify_env import clean_env, graphify_python
from kb_setup.result import Err, Ok, Rc, Result, exit_code

#: The tracked artifact, relative to the repo root. The ONE file carved out of
#: `.gitignore`'s `graphify-out/reflections/` rule — kept here as the single
#: definition so the gate and any future reader cannot drift from the ignore file.
LESSONS_REL = Path("graphify-out") / "reflections" / "LESSONS.md"

#: Everything the render reads. `memory/` is committed; the other three are
#: derived and gitignored, which is what makes the SKIP path reachable at all.
MEMORY_REL = Path("graphify-out") / "memory"
GRAPH_REL = Path("graphify-out") / "graph.json"
ANALYSIS_REL = Path("graphify-out") / ".graphify_analysis.json"
LABELS_REL = Path("graphify-out") / ".graphify_labels.json"

#: Half an hour is `gates._GATE_TIMEOUT`; this render is a two-digit number of
#: seconds, so a bound two orders of magnitude above the measurement still means
#: "wedged" rather than "slow host" (`long-running-command-hangs.md`).
_RENDER_TIMEOUT = 600

#: Diff lines shown in the report. A drift is fixed by re-running one task, so the
#: report only has to make the drift CREDIBLE, not reviewable in full.
_DIFF_PREVIEW = 20

_REMEDY = "run `mise run kb-reflect`, then commit graphify-out/reflections/LESSONS.md"


def _missing(repo_root: Path) -> list[Path]:
    """The derived inputs the render needs that this machine does not have."""
    return [rel for rel in (GRAPH_REL, ANALYSIS_REL, LABELS_REL) if not (repo_root / rel).is_file()]


def _render(repo_root: Path, out: Path) -> str | None:
    """Regenerate the lessons doc into ``out``; return an error message, or None.

    Runs `_render_lessons.py` under graphify's bundled interpreter with a
    Claude-only env (`clean_env` strips every non-Claude backend trigger — this
    render uses no LLM at all, but the invariant is that NO graphify subprocess
    is ever handed one, `do-not.md` #4).
    """
    try:
        python = graphify_python(repo_root)
    except (OSError, RuntimeError, ValueError) as exc:
        return f"no interpreter that can import graphify: {exc}"

    script = Path(__file__).with_name("_render_lessons.py")
    cmd = [
        python,
        str(script),
        str(repo_root / MEMORY_REL),
        str(out),
        "--graph",
        str(repo_root / GRAPH_REL),
        "--analysis",
        str(repo_root / ANALYSIS_REL),
        "--labels",
        str(repo_root / LABELS_REL),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            env=clean_env(),
            check=False,
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"the render did not finish within {_RENDER_TIMEOUT}s"
    except OSError as exc:
        return f"could not start the render: {exc}"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return f"the render exited {proc.returncode}: {' / '.join(tail) or 'no output'}"
    return None


def _drift_report(tracked: str, regenerated: str) -> str:
    """A report naming the drift and enough of it to be believed."""
    diff = list(
        difflib.unified_diff(
            tracked.splitlines(),
            regenerated.splitlines(),
            "tracked",
            "regenerated",
            lineterm="",
            n=0,
        )
    )
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    preview = "\n".join(f"    {line}" for line in diff[:_DIFF_PREVIEW])
    more = (
        f"\n    … {len(diff) - _DIFF_PREVIEW} more diff lines" if len(diff) > _DIFF_PREVIEW else ""
    )
    return (
        f"[lessons] DRIFT — {LESSONS_REL} does not match what kb-reflect would "
        f"produce from the committed memory/: "
        f"{len(tracked.encode())} tracked vs {len(regenerated.encode())} regenerated bytes, "
        f"+{added}/-{removed} lines.\n"
        f"{preview}{more}\n"
        f"[lessons] remedy: {_REMEDY}"
    )


def _precondition_error(repo_root: Path) -> Result[str] | None:
    """Return the first reason the graph-backed render cannot run, if any."""
    if not (repo_root / MEMORY_REL).is_dir():
        return Err(f"[lessons] SKIP — no {MEMORY_REL}; nothing to reflect over", rc=Rc.NOT_RUN)

    absent = _missing(repo_root)
    if absent:
        names = ", ".join(str(rel) for rel in absent)
        return Err(
            f"[lessons] SKIP — {names} absent, so the graph-grouped render cannot be "
            f"reproduced here and the tracked file is UNVERIFIED (not verified clean). "
            f"Run `mise run kb-build` on a machine that carries the graph.",
            rc=Rc.NOT_RUN,
        )
    return None


def check(repo_root: Path) -> Result[str]:
    """Assert the tracked lessons doc matches a fresh render. See the module doc.

    `Ok(report)` when they agree, `Ok(report, rc=Rc.FINDINGS)` on drift — a gate
    that ran and found something is a SUCCESSFUL run — and `Err(..., NOT_RUN)`
    whenever the question could not be asked, which is every path where an input
    is missing or the render did not produce a file.
    """
    precondition_error = _precondition_error(repo_root)
    if precondition_error is not None:
        return precondition_error

    tracked_path = repo_root / LESSONS_REL
    with tempfile.TemporaryDirectory(prefix="kb-lessons-") as tmp:
        out = Path(tmp) / "LESSONS.md"
        problem = _render(repo_root, out)
        if problem is not None:
            return Err(f"[lessons] SKIP — {problem}", rc=Rc.NOT_RUN)
        if not out.is_file():
            return Err("[lessons] SKIP — the render wrote no file", rc=Rc.NOT_RUN)
        regenerated = out.read_text(encoding="utf-8")

    if not tracked_path.is_file():
        return Ok(
            f"[lessons] MISSING — {LESSONS_REL} is not on disk, but the render produced "
            f"{len(regenerated.encode())} bytes from the committed memory/.\n"
            f"[lessons] remedy: {_REMEDY}",
            rc=Rc.FINDINGS,
        )

    tracked = tracked_path.read_text(encoding="utf-8")
    if tracked == regenerated:
        return Ok(
            f"[lessons] OK — {LESSONS_REL} matches a fresh render "
            f"({len(tracked.encode())} bytes, byte-for-byte)"
        )
    return Ok(_drift_report(tracked, regenerated), rc=Rc.FINDINGS)


def main(repo_root: Path) -> int:
    """`kb-setup lessons-check` — print the verdict, return its exit code.

    The single `Result` -> exit-code conversion is `result.exit_code`; this only
    chooses the LEVEL, and both non-OK states emit at WARNING rather than INFO so
    that R9's "did this run emit anything at WARNING or above?" sees a skip too. A
    skip that whispers at INFO is how an unverified file reads as a verified one.
    """
    outcome = check(repo_root)
    if isinstance(outcome, Ok):
        (events.say if outcome.rc is Rc.OK else events.warn)(
            "lessons.check", outcome.value, drift=outcome.rc is not Rc.OK
        )
    else:
        events.warn("lessons.skip", getattr(outcome, "message", str(outcome)), ran=False)
    return exit_code(outcome)
