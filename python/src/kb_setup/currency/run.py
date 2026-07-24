"""Orchestration and the three entry points the outside world uses.

* `check`  — offline step 1 only. This is what the SessionStart hook runs, so it
             must stay subprocess-free and finish in milliseconds, and it must
             print NOTHING when everything is in sync. Always exits 0: a hook
             that blocks a session over a version pin would be worse than the
             drift it reports.
* `run`    — the full loop (steps 1-4 and 6), emitting the ambiguities that the
             skill turns into AskUserQuestion prompts (step 5). Judgment is the
             model's; this only assembles the facts and the verdict.
* `stamp`  — record which version built the artifacts. Called by the build task,
             never by a check, because a check that writes the thing it verifies
             is a check that can only pass.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from kb_setup.currency import config, issues, report, sync, upstream
from kb_setup.currency.decide import decide


def _specs(repo_root: Path, only: str = "") -> tuple[config.ToolSpec, ...]:
    specs = config.load(repo_root)
    return tuple(s for s in specs if s.name == only) if only else specs


def check(repo_root: Path, *, only: str = "", quiet: bool = True) -> int:
    """Step 1 across every configured tool. Prints only what needs attention.

    `quiet` is the hook's mode — silence when clean. Silence is the design: this
    repo has measured always-on context being ignored (the mcp2cli surface: 971
    prompt echoes, 0 loads), so a nudge that fires every session would train the
    reader to skip the one session it matters.
    """
    drifted: list[sync.SyncStatus] = []
    for spec in _specs(repo_root, only):
        status = sync.check_sync(repo_root, spec)
        if status.drifted:
            drifted.append(status)
        elif not quiet:
            print(f"[currency] {status.summary()}")

    if not drifted:
        return 0

    print("[currency] tool drift detected — run the tool-currency skill:")
    for status in drifted:
        for finding in status.drifted:
            print(f"[currency]   {status.tool}: {finding.check} — {finding.detail}")
    return 0


def _run_one(repo_root: Path, spec: config.ToolSpec) -> report.RunRecord:
    # deep=True: the full workflow is already spending network calls, so it can
    # afford the one `mise where` subprocess the extras probe needs when the
    # binary resolves through a shim. The hook path stays subprocess-free.
    status = sync.check_sync(repo_root, spec, deep=True)
    up = upstream.probe(pypi=spec.pypi, github=spec.github, current=status.pinned)
    observations = issues.observe_all(spec)
    report_root = repo_root / report.REPORT_DIR
    previous = issues.load_previous(report_root, spec.name)
    moved = issues.changes(observations, previous)
    verdict = decide(sync=status, upstream=up, moved=moved)
    return report.RunRecord(
        tool=spec.name,
        sync=status,
        upstream=up,
        observations=observations,
        moved=moved,
        verdict=verdict,
    )


def run(repo_root: Path, *, only: str = "", as_json: bool = False, write: bool = True) -> int:
    """The full workflow. Returns 0 always — findings are output, not failure.

    An out-of-date tool is a signal, not an error: making this red would turn the
    daily job into noise the moment upstream ships anything, which is exactly how
    a currency check stops being read.
    """
    specs = _specs(repo_root, only)
    if not specs:
        print(f"[currency] no tools configured in {config.CONFIG_NAME}", file=sys.stderr)
        return 0

    payloads: list[dict[str, object]] = []
    lines: list[str] = []
    for spec in specs:
        record = _run_one(repo_root, spec)
        detail: Path | None = None
        if write:
            report_root = repo_root / report.REPORT_DIR
            _, detail = report.write_run(repo_root, record)
            issues.save_current(report_root, spec.name, record.observations)

        if not write:
            where = "dry run — nothing written"
        elif detail:
            where = str(detail.relative_to(repo_root))
        else:
            where = "landing row only"
        lines.append(f"[currency] {record.verdict.summary()} — {where}")
        payloads.append(
            {
                "tool": spec.name,
                "verdict": asdict(record.verdict),
                "sync": asdict(record.sync),
                "upstream": asdict(record.upstream),
                "observations": [asdict(o) for o in record.observations],
                "moved": [asdict(o) for o in record.moved],
                "detail_page": str(detail.relative_to(repo_root)) if detail else None,
            }
        )

    if as_json:
        print(json.dumps(payloads, indent=2))
    else:
        for line in lines:
            print(line)
    return 0


def stamp(repo_root: Path, *, tool: str, version: str, source_ref: str = "") -> int:
    """Record which version built this repo's artifacts for `tool`."""
    specs = _specs(repo_root, tool)
    if not specs:
        print(f"[currency] no [tool.{tool}] in {config.CONFIG_NAME}", file=sys.stderr)
        return 2
    spec = specs[0]
    if not spec.stamp:
        print(f"[currency] [tool.{tool}] declares no `stamp` path", file=sys.stderr)
        return 2
    resolved = version or sync.pinned_version(repo_root, spec)[0]
    if not resolved:
        print(f"[currency] cannot determine a version to stamp for {tool}", file=sys.stderr)
        return 2
    path = sync.write_stamp(repo_root, spec, version=resolved, source_ref=source_ref)
    print(f"[currency] stamped {path.relative_to(repo_root)} at {resolved}")
    return 0
