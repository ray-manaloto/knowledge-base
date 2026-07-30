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
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from kb_setup.currency import baseline, config, docs, issues, report, sync, upstream
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
    configured = config.load(repo_root)
    if not configured:
        # NOT silent. Silence is this design's definition of "clean", so a
        # renamed/moved config, a wrong `-C` in the hook, or a consumer repo that
        # copies the hook without the config would disable the check forever while
        # looking green. A check that cannot run must say so.
        print(
            f"[currency] no {config.CONFIG_NAME} at {repo_root} — step 1 did NOT run",
            file=sys.stderr,
        )
        return 0
    if only and not any(s.name == only for s in configured):
        names = ", ".join(s.name for s in configured)
        print(
            f"[currency] unknown tool {only!r}; configured: {names}",
            file=sys.stderr,
        )
        return 2

    # OFFLINE docs check: report pages nobody has verified lately. It cannot say
    # a page CHANGED — that needs a fetch, which belongs in the full run, not on
    # the SessionStart path this mode serves (offline, ~10ms, silent when clean).
    # "Not verified since <date>" is a different and honest finding.
    docs_store = docs.load(repo_root)
    stale: list[tuple[str, docs.DocsFinding]] = [
        (spec.name, finding)
        for spec in _specs(repo_root, only)
        if spec.docs_watch
        for finding in docs.staleness(spec.docs_watch, docs_store)
    ]

    # OFFLINE upstream check: is the pin behind the last version a full run saw?
    # Step 1 otherwise compares install-against-pin only, which agreed with itself
    # while graphify sat four releases behind (see `baseline`'s module docstring).
    cache = baseline.load(repo_root)
    behind: list[baseline.BaselineFinding] = []

    drifted: list[sync.SyncStatus] = []
    unverifiable: list[sync.SyncStatus] = []
    for spec in _specs(repo_root, only):
        status = sync.check_sync(repo_root, spec)
        # Collected BEFORE the branches below, which `continue` past a drifted
        # tool: being behind upstream is an independent fact from being out of sync
        # locally, and a tool can easily be both.
        behind.extend(_upstream_finding(spec, status, cache))
        if status.drifted:
            drifted.append(status)
            continue
        # A tool that APPLIES here but had no check succeed is not clean — it is
        # unchecked, and silence is this design's word for clean. The same
        # reasoning as the missing-config branch above, one level down: a broken
        # `version_pattern` or an unreadable binary would otherwise disable a
        # tool's check permanently while every session looked green.
        #
        # Gated on applies_here() so a tool declared for another platform stays
        # quiet: that one is genuinely not-applicable rather than not-checked,
        # and nagging about it every session is the noise this mode avoids.
        if spec.applies_here() and not status.verified:
            unverifiable.append(status)
        elif not quiet:
            print(f"[currency] {status.summary()}")

    _report_check(drifted, unverifiable)
    _report_upstream(behind)
    if stale:
        print("[currency] tracked docs pages not verified recently (this is not drift):")
        for tool, finding in stale:
            print(f"[currency]   {tool}: {finding.detail} — {finding.url}")
    return 0


def _upstream_finding(
    spec: config.ToolSpec, status: sync.SyncStatus, cache: Mapping[str, object]
) -> list[baseline.BaselineFinding]:
    """The offline pin-vs-upstream verdict for one tool, as a 0-or-1 element list.

    A list rather than an Optional so the caller stays a single `extend` — the
    branch it replaces was what pushed `check` past its complexity budget.
    """
    if not (spec.applies_here() and spec.tracks_upstream):
        return []
    found = baseline.behind(spec.name, status.pinned, cache)
    return [found] if found else []


def _report_upstream(behind: list[baseline.BaselineFinding]) -> None:
    """Print the pin-vs-upstream findings, splitting the two that mean different things.

    Same principle as `_report_check`: "we know the pin is stale" and "we have no
    observation to judge it against" are different answers, and one header over
    both would let the weaker borrow the stronger's weight.
    """
    stale_pin = [f for f in behind if f.check == "upstream-version"]
    no_record = [f for f in behind if f.check != "upstream-version"]
    if stale_pin:
        print("[currency] pin is behind the last upstream version seen:")
        for finding in stale_pin:
            print(f"[currency]   {finding.tool}: {finding.detail}")
    if no_record:
        print("[currency] NOT CHECKED against upstream (this is not a pass):")
        for finding in no_record:
            print(f"[currency]   {finding.tool}: {finding.detail}")


def _report_check(drifted: list[sync.SyncStatus], unverifiable: list[sync.SyncStatus]) -> None:
    """Print the two non-clean outcomes, kept apart because they mean different things.

    DRIFT is "checked, and it disagrees"; NOT CHECKED is "could not ask". Merging
    them would let an unreadable probe borrow the credibility of a real finding —
    and, worse, let a real finding be dismissed as a flaky probe.
    """
    if drifted:
        print("[currency] tool drift detected — run the tool-currency skill:")
        for status in drifted:
            for finding in status.drifted:
                print(f"[currency]   {status.tool}: {finding.check} — {finding.detail}")
    if unverifiable:
        print("[currency] NOT CHECKED (this is not a pass) — step 1 could not read:")
        for status in unverifiable:
            for finding in status.findings:
                print(f"[currency]   {status.tool}: {finding.check} — {finding.detail}")


def _verify_docs(repo_root: Path, specs: tuple[config.ToolSpec, ...]) -> None:
    """NETWORK half of the docs check — only ever from the full run.

    Kept out of `check()` on purpose: that path is the SessionStart hook and must
    stay offline and ~10ms. Here we are already spending round trips on PyPI and
    GitHub, so two more are free by comparison.
    """
    watched = [s for s in specs if s.docs_watch]
    if not watched:
        return
    store = docs.load(repo_root)
    for spec in watched:
        findings, store = docs.verify(spec.docs_watch, store)
        for f in findings:
            if f.drifted:
                print(f"[currency] {spec.name}: DOCS DRIFT — {f.url}")
                print(f"[currency]   {f.detail}")
            elif not f.verified:
                print(f"[currency] {spec.name}: {f.detail} — {f.url}")
    docs.save(repo_root, store)


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
    verdict = decide(sync=status, upstream=up, moved=moved, observations=observations)
    return report.RunRecord(
        tool=spec.name,
        sync=status,
        upstream=up,
        observations=observations,
        moved=moved,
        verdict=verdict,
    )


def _where_written(repo_root: Path, detail: Path | None, *, write: bool) -> str:
    """How to describe where this tool's output went, for the human-readable line.

    Three distinct outcomes, and "landing row only" must not be confused with a
    dry run: the first means the run had nothing worth a detail page, the second
    means nothing was written at all.
    """
    if not write:
        return "dry run — nothing written"
    return str(detail.relative_to(repo_root)) if detail else "landing row only"


def _payload(
    repo_root: Path, tool: str, record: report.RunRecord, detail: Path | None
) -> dict[str, object]:
    """One tool's `--json` object — the shape the tool-currency skill reads."""
    return {
        "tool": tool,
        "verdict": asdict(record.verdict),
        "sync": asdict(record.sync),
        "upstream": asdict(record.upstream),
        "observations": [asdict(o) for o in record.observations],
        "moved": [asdict(o) for o in record.moved],
        "detail_page": str(detail.relative_to(repo_root)) if detail else None,
    }


def run(repo_root: Path, *, only: str = "", as_json: bool = False, write: bool = True) -> int:
    """The full workflow. Returns 0 always — findings are output, not failure.

    An out-of-date tool is a signal, not an error: making this red would turn the
    daily job into noise the moment upstream ships anything, which is exactly how
    a currency check stops being read.
    """
    configured = config.load(repo_root)
    if not configured:
        print(
            f"[currency] no {config.CONFIG_NAME} at {repo_root} — nothing to do",
            file=sys.stderr,
        )
        return 0
    specs = _specs(repo_root, only)
    if not specs:
        # The config exists and is fine; the FILTER matched nothing. Saying "no
        # tools configured" here would be a lie, and a silent 0 would hide a typo.
        names = ", ".join(s.name for s in configured)
        print(f"[currency] unknown tool {only!r}; configured: {names}", file=sys.stderr)
        return 2

    # Before the per-tool records, because a docs revision changes how you READ
    # the version findings that follow: a page that moved under you is the
    # likelier explanation for surprising behaviour than any pin.
    if write:
        _verify_docs(repo_root, specs)

    payloads: list[dict[str, object]] = []
    lines: list[str] = []
    cache = baseline.load(repo_root)
    for spec in specs:
        record = _run_one(repo_root, spec)
        detail: Path | None = None
        if write:
            report_root = repo_root / report.REPORT_DIR
            _, detail = report.write_run(repo_root, record)
            issues.save_current(report_root, spec.name, record.observations)
            # Hand the offline check the third version it cannot see for itself.
            # Only from a REACHABLE probe: caching "" from a failed lookup would
            # turn an outage into a recorded claim that upstream offers nothing.
            if record.upstream.reachable:
                cache = baseline.record(cache, spec.name, record.upstream.latest)

        where = _where_written(repo_root, detail, write=write)
        lines.append(f"[currency] {record.verdict.summary()} — {where}")
        payloads.append(_payload(repo_root, spec.name, record, detail))

    if write:
        baseline.save(repo_root, cache)

    if as_json:
        print(json.dumps(payloads, indent=2))
    else:
        for line in lines:
            print(line)
    return 0


def docs_reviewed(repo_root: Path, *, only: str = "") -> int:
    """Roll the docs baseline forward after a human has re-read the drifted pages.

    The deliberate second step that `docs.verify` no longer does for itself. Until
    this runs, a drifted page keeps being reported — which is the point: the
    signal used to be consumed by the same run that raised it, so the committed
    report said "clean" while three watched pages had changed.

    Requires `--tool`, for the same reason `apply` does and one more. CONSUMING a
    signal is never a fan-out: this asserts a human read those pages, and nobody
    reads every watched tool's docs in one sitting. The extra reason is that
    `_opt` treats a DANGLING `--tool` (the flag as the last token) as absent, so
    a typo'd `kb-setup currency docs-reviewed --tool` arrived here as `only=""`
    and silently rolled the fingerprint for every watched tool — swallowing
    exactly the drift this whole surface exists to keep un-swallowed. (Cold lane.)

    Returns 1 when any page could not be FETCHED. `mark_reviewed` leaves such a
    page's baseline alone and reports `NOT CHECKED`, so a bare `return 0` told a
    caller scripting the exit code that the roll had succeeded during a network
    outage that left pages unrolled. (Cold lane.)
    """
    if not only:
        print("[currency] docs-reviewed requires --tool <name>", file=sys.stderr)
        return 2
    specs = [s for s in _specs(repo_root, only) if s.docs_watch]
    if not specs:
        print(f"[currency] no tool for {only!r} watches any docs page", file=sys.stderr)
        return 2
    unfetched = 0
    for spec in specs:
        for finding in docs.mark_reviewed(repo_root, spec.docs_watch):
            print(f"[currency] {spec.name}: {finding.detail} — {finding.url}")
            unfetched += not finding.verified
    if unfetched:
        print(
            f"[currency] {unfetched} page(s) could not be fetched, so their baseline was "
            "NOT rolled — re-run once they are reachable",
            file=sys.stderr,
        )
        return 1
    return 0


def apply(repo_root: Path, *, only: str, as_json: bool = False) -> int:
    """Apply the authorized bump for ONE tool (steps 2's "and update").

    Requires `--tool`: applying a version change is never a fan-out over every
    configured tool, and an unauthorized verdict must fail loudly, not be one of
    several statuses. Returns 2 if the tool is unknown or its verdict does not
    authorize a bump, 0 on a successful edit. Opening the PR is the ship task's
    job (H3), so this only edits and reports.
    """
    from kb_setup.currency import apply as apply_mod

    if not only:
        print("[currency] apply requires --tool <name>", file=sys.stderr)
        return 2
    specs = _specs(repo_root, only)
    if not specs:
        configured = ", ".join(s.name for s in config.load(repo_root))
        print(f"[currency] unknown tool {only!r}; configured: {configured}", file=sys.stderr)
        return 2

    spec = specs[0]
    record = _run_one(repo_root, spec)
    try:
        result = apply_mod.apply(repo_root, spec, record.verdict)
    except apply_mod.NotAuthorizedError as e:
        print(f"[currency] not applied — {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, RuntimeError) as e:
        print(f"[currency] apply failed — {e}", file=sys.stderr)
        return 2

    if as_json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(
            f"[currency] {result.tool} {result.from_version} → {result.to_version}: "
            f"edited {', '.join(result.changed)} — {result.note}"
        )
        print("[currency] open the PR with `mise run kb-ship` (auto-merge on).")
    return 0


def daily(repo_root: Path) -> int:
    """The daily standing-issue report: deep signal + broad sweep, one markdown doc.

    Prints markdown to stdout for the workflow to upsert as the standing issue
    (dotfiles' `tool-currency` job). Deep-tracked tools that MOVED get a one-line
    verdict; every other outdated pin gets a broad-table row. Host-only tools that
    do not apply here (graphify on an Ubuntu runner) are skipped from the deep
    signal, never failed — the hard constraint from the handoff.

    Renders only — it never writes the committed per-run pages (that is the
    session `run`) and never applies (H4: the daily job reports, never bumps).
    Always exits 0: an out-of-date tool is a signal, not a failure.
    """
    from kb_setup.currency import broad

    specs = config.load(repo_root)
    deep_lines: list[str] = []
    na_lines: list[str] = []
    for spec in specs:
        if not spec.applies_here():
            # e.g. graphify on the Ubuntu daily runner — not a failure, but not
            # silence either: a bare `continue` made a host-only tool vanish from
            # the report, so "skipped here" was indistinguishable from "nothing to
            # report". Emit an explicit not-applicable line so the reader sees the
            # tool was deliberately not checked, not silently dropped.
            na_lines.append(
                f"- {spec.name}: not checked on this host "
                f"(declared for {', '.join(spec.os) or 'any platform'})"
            )
            continue
        record = _run_one(repo_root, spec)
        v = record.verdict
        if v.has_upgrade or v.ambiguities or record.sync.drifted:
            deep_lines.append(f"- {v.summary()}")

    deep_body = "\n".join(deep_lines) if deep_lines else "_No deep-tracked tool needs attention._"
    if na_lines:
        deep_body += "\n\n_Not applicable on this host:_\n" + "\n".join(na_lines)
    broad_body = broad.broad_section(repo_root, exclude=broad.deep_tracked_keys(repo_root))
    print(
        "# Tool currency (daily)\n\n"
        "Deep due-diligence on the fast-movers, a broad `mise outdated` sweep on "
        "the rest. Review the deep section via the `tool-currency` skill; the "
        "broad table is a signal, not a verdict.\n\n"
        "## Deep-tracked — needs review\n\n"
        f"{deep_body}\n\n"
        f"{broad_body}\n"
    )
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
    # NO fallback to the PIN. Stamping the pinned version without reading the
    # binary records the version we HOPED ran, not the one that did — the exact
    # false green G3 forbids ("never a false green"). Mirror the build path
    # (`graph._stamp_build`): fall back to what ACTUALLY resolves on PATH, and if
    # neither an explicit --version nor the binary can supply a version, refuse
    # rather than stamp an unverified one (a manual stamp has not just rebuilt, so
    # writing an empty stamp would only clobber a good one).
    resolved = version or sync.observed_version(spec.binary)
    if not resolved:
        print(
            f"[currency] cannot determine a version to stamp for {tool} — pass "
            f"--version, or make `{spec.binary} --version` readable (refusing to "
            f"stamp the pin, which nothing verified actually ran)",
            file=sys.stderr,
        )
        return 2
    path = sync.write_stamp(repo_root, spec, version=resolved, source_ref=source_ref)
    print(f"[currency] stamped {path.relative_to(repo_root)} at {resolved}")
    return 0
