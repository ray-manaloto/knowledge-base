# Copyright (c) 2026 Raymond Manaloto
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
from datetime import UTC, datetime
from pathlib import Path

from kb_setup.currency import (
    baseline,
    config,
    docs,
    issues,
    report,
    staleness,
    sync,
    upstream,
    views,
)
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
    # The graph-vs-inputs verdict, under its OWN header rather than folded into
    # the drift block above (#88). Deliberately after it: a tool that has drifted
    # is a reason to distrust the graph, so the reader should meet that first.
    # Same posture as everything else on this path — silent when clean, never a
    # rebuild, and the return below is unconditionally 0.
    staleness.report(staleness.check_inputs(repo_root, spec) for spec in _specs(repo_root, only))
    # And the derived-views verdict (#182), under its own header again and last:
    # of the three, it is the cheapest to act on (`kb-artifacts`, no network, no
    # re-extraction), so it is the one a reader should meet after the two that can
    # invalidate it. Cheap enough for the SessionStart path because it reads the
    # stamp and stats ONE file: the expensive part (`deep_artifact_fingerprint`'s
    # walk over `wiki/`, 35.6-63.3 ms) is paid at stamp time, after an operation
    # that already took minutes.
    views.report(views.check_views(repo_root, spec) for spec in _specs(repo_root, only))
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
    up = upstream.probe(
        pypi=spec.pypi,
        github=spec.github,
        current=status.pinned,
        tag_prefix=spec.tag_prefix,
    )
    observations = issues.observe_all(spec)
    report_root = repo_root / report.REPORT_DIR
    previous = issues.load_previous(report_root, spec.name)
    moved = issues.changes(observations, previous)
    # Recorded re-probe claims for this tool's local watch items (#486). Loaded
    # here, not inside `decide`, for the same reason `previous`/`view_status` are:
    # `decide` is pure judgment over facts handed to it, and the disk read stays
    # in the one function that already does every other disk read for this tool.
    reviewed = issues.load_reviewed(report_root, spec.name)
    # The derived-views verdict reaches gate 6 (#182). Without this it was
    # reported under its own header and nowhere else, so `apply()`'s
    # auto-authorization — which is built from THIS verdict — could clear a
    # 6/6 bump over views describing an earlier graph.
    view_status = views.check_views(repo_root, spec)
    verdict = decide(
        sync=status,
        upstream=up,
        moved=moved,
        observations=observations,
        # The WHOLE status, not just its stale lines. Passing `view_status.stale`
        # was round 2's P1: that tuple is empty for every NOT_VERIFIABLE verdict,
        # so a views check that could not verify anything reached gate 6 looking
        # exactly like a clean one.
        views=view_status,
        reviewed=reviewed,
    )
    return report.RunRecord(
        tool=spec.name,
        sync=status,
        upstream=up,
        observations=observations,
        moved=moved,
        verdict=verdict,
        # Round 2's second P2: this was computed, used for the verdict, and then
        # dropped — so `_payload` serialized the SKIP default forever, breaking the
        # machine surface its own docstring says it exists to provide. `reviewed`
        # below is the same lesson applied on arrival rather than found later.
        views=view_status,
        reviewed=reviewed,
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
    """One tool's `--json` object — the shape the tool-currency skill reads.

    `views` is present because the human path prints the derived-views verdict and
    the machine path did not, so a `--json` consumer — including `daily()` — saw a
    record with no trace of it (#182). `reviewed` (#486) follows the identical
    precedent rather than repeating that gap: it is consulted to build the
    verdict, so it belongs beside it here too.
    """
    return {
        "tool": tool,
        "verdict": asdict(record.verdict),
        "sync": asdict(record.sync),
        "upstream": asdict(record.upstream),
        "views": asdict(record.views),
        "observations": [asdict(o) for o in record.observations],
        "moved": [asdict(o) for o in record.moved],
        "reviewed": {key: asdict(value) for key, value in record.reviewed.items()},
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
        # The full run reports the derived-views verdict too (#182), not only the
        # SessionStart path — a view left behind by a `kb-label` is exactly the
        # kind of thing someone running the full loop is looking for, and having
        # it appear in the cheap mode but not the thorough one would read as the
        # thorough mode clearing it.
        #
        # Non-JSON only: `payloads` is a per-tool RunRecord shape, and appending
        # prose to a document a caller is about to `json.loads` would break the
        # machine mode to serve the human one. `daily()` and any `--json` consumer
        # keep a parseable stdout; `check()` above carries the verdict for them.
        views.report(views.check_views(repo_root, spec) for spec in specs)
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


def _missing_required(only: str, ref: str, version: str) -> list[str]:
    """Which of `--tool`/`--ref`/`--version` are absent, as their flag+placeholder.

    Split out so this specific guard is directly testable. An empty string
    ALSO fails `upstream.Version.parse`, so no input to `watch_reviewed` can
    tell "this check refused it" apart from "the parse check refused it" —
    they trip on the identical input by construction. A unit test against
    this function, in isolation from the parse check, is the only way to pin
    that dropping an entry here is itself a regression (cold review, m4).
    """
    required = (
        ("--tool <name>", only),
        ("--ref <watch-item-ref>", ref),
        ("--version <release>", version),
    )
    return [flag for flag, value in required if not value]


def _local_items(spec: config.ToolSpec) -> list[config.WatchItem]:
    """This tool's local watch items.

    `kind != "issue"` is how `issues.observe` itself decides an item is local,
    matched here so `watch_reviewed` and `prune_reviewed` can never disagree
    with the gate about which items are in scope.
    """
    return [item for item in spec.watch if item.kind != "issue"]


def watch_reviewed(
    repo_root: Path, *, only: str = "", ref: str = "", version: str = "", note: str = ""
) -> int:
    """Record that one LOCAL watch item has been re-probed against a release (#486).

    The counterpart to `docs_reviewed` for gate 5's other half. Until this
    existed, "N local watch item(s) must be re-probed against this release.
    Done?" had no answer the engine could check — a human hand-appended prose to
    a `currency.toml` note, which nothing read and which looked identical
    whether it described THIS release or one six bumps ago. This records the
    claim as data: which item, re-probed against which version, and when.
    `decide._gate_local` then clears an item only when the recorded version is
    the SAME RELEASE (`issues.cleared_for`, built on `upstream.same_release`) AND
    the item's CURRENT note still hashes to the digest recorded here
    (`issues.finding_digest`, cold review B1) — a record at an older version, or
    one whose watch item was since redefined, leaves the gate exactly as open as
    no record at all.

    Requires `--tool`, `--ref` and `--version`, all three for the reason
    `docs_reviewed` requires `--tool` and one more: this asserts a human
    re-probed ONE finding against ONE release, never a fan-out, so a dangling
    flag (present with no value — `_opt`'s own definition of absent) must never
    be silently read as "" and recorded as an empty claim. `cli._currency` also
    guards each value against being another flag's name (`--tool --version
    1.2.3` must not read `only` as `"--version"`) before this function is ever
    reached; this function still refuses on its own, because it must not trust a
    caller other than the CLI to have done that.

    NEVER prunes (cold review, MAJ-1) — see `prune_reviewed` below, a separate
    function reached only by a separate `--tool`-only command. An earlier cut
    folded pruning in here as a `--prune` flag on THIS command; that was still
    wrong, because it made a destructive action reachable from the same call
    that performs an ordinary, non-destructive one. Recording a clearance can
    now never delete a different one, structurally, regardless of any flag.

    Returns 2 for any unusable request, below, and writes NOTHING in that case —
    never partially. There is no `docs_reviewed`-style partial-success `1`: that
    command fans a network fetch out over several watched pages, so some can
    succeed while others 503; this command touches no network and records
    exactly one item, so the outcomes are "refused, nothing written" and
    "written" — plus one refusal (`ReviewedStoreUnreadableError`) that fires only
    when the STORE it would merge into cannot be parsed, so this write does not
    silently discard every other clearance already on disk (cold review, M2).
    """
    missing = _missing_required(only, ref, version)
    if missing:
        print(f"[currency] watch-reviewed requires {' '.join(missing)}", file=sys.stderr)
        return 2

    specs = _specs(repo_root, only)
    if not specs:
        configured = ", ".join(s.name for s in config.load(repo_root))
        print(f"[currency] unknown tool {only!r}; configured: {configured}", file=sys.stderr)
        return 2
    spec = specs[0]

    local_items = _local_items(spec)
    match = next((item for item in local_items if item.ref == ref), None)
    if match is None:
        # Fail closed: a recorded clearance for a key nothing observes could
        # never be checked again, and it would look, in the store, exactly like
        # a valid one — refuse before writing anything rather than record it.
        known = ", ".join(item.ref for item in local_items) or "none"
        print(
            f"[currency] {only!r} has no local watch item with ref {ref!r} (local refs: {known})",
            file=sys.stderr,
        )
        return 2

    if upstream.Version.parse(version) is None:
        print(
            f"[currency] {version!r} does not parse as a version — refusing to "
            "record an unreadable clearance (fail-closed)",
            file=sys.stderr,
        )
        return 2

    report_root = repo_root / report.REPORT_DIR
    at = datetime.now(UTC).date().isoformat()
    record = issues.Reviewed(
        key=match.key,
        version=version,
        at=at,
        finding_digest=issues.finding_digest(match.note),
        note=note,
    )
    try:
        path = issues.record_reviewed(report_root, spec.name, record)
    except issues.ReviewedStoreUnreadableError as e:
        print(
            f"[currency] refusing to record — the existing store could not be read ({e}); "
            "fix or remove it by hand first, so this write does not silently discard every "
            "other tracked clearance",
            file=sys.stderr,
        )
        return 2
    print(
        f"[currency] {spec.name}: {match.key} recorded reviewed @ {version} — "
        f"{path.relative_to(repo_root)}"
    )
    return 0


def prune_reviewed(repo_root: Path, *, only: str = "") -> int:
    """Remove stored `watch-reviewed` clearances for local items no longer configured (#486).

    A SEPARATE command from `watch_reviewed` (cold review, MAJ-1), reachable
    only by explicitly naming `--tool`, never as a side effect of recording a
    clearance. Pruning is destructive — it deletes a human's re-probe
    assertion, which no run can reconstruct — while recording is not, and an
    earlier cut that gave them one entry point let a config typo three lines
    away silently delete an unrelated item's clearance, with `rc 0` and no
    message. `config._watch_items` fails SOFT (an entry missing `ref` is
    silently skipped, pre-existing and out of scope here), so "absent from
    THIS `config.load()`" is not proof an item was genuinely removed; the
    remedy here is not detecting that — it is making the action require a
    human to specifically ask for it, at a time of their choosing, seeing
    exactly what is about to go before it does.

    Prints every key about to be removed BEFORE writing (never silent), and
    prints "nothing to prune" and writes nothing when there is nothing to do.
    Returns 2 for `--tool` missing or unknown, or when the store cannot be
    read (`ReviewedStoreUnreadableError`, the M2 refusal); 0 otherwise.
    """
    if not only:
        print("[currency] prune-reviewed requires --tool <name>", file=sys.stderr)
        return 2
    specs = _specs(repo_root, only)
    if not specs:
        configured = ", ".join(s.name for s in config.load(repo_root))
        print(f"[currency] unknown tool {only!r}; configured: {configured}", file=sys.stderr)
        return 2
    spec = specs[0]

    report_root = repo_root / report.REPORT_DIR
    valid_keys = frozenset(item.key for item in _local_items(spec))
    try:
        _path, removed = issues.prune_reviewed(report_root, spec.name, valid_keys)
    except issues.ReviewedStoreUnreadableError as e:
        print(
            f"[currency] refusing to prune — the existing store could not be read ({e}); "
            "fix or remove it by hand first",
            file=sys.stderr,
        )
        return 2
    if not removed:
        print(f"[currency] {spec.name}: nothing to prune")
        return 0
    print(f"[currency] {spec.name}: pruned {len(removed)} clearance(s): {', '.join(removed)}")
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
    if version:
        resolved = version
    elif spec.version_args == ("--version",):
        resolved = sync.observed_version(spec.binary)
    else:
        resolved = sync.observed_version(spec.binary, spec.version_pattern, spec.version_args)
    if not resolved:
        print(
            f"[currency] cannot determine a version to stamp for {tool} — pass "
            f"--version, or make `{spec.binary} --version` readable (refusing to "
            f"stamp the pin, which nothing verified actually ran)",
            file=sys.stderr,
        )
        return 2
    # `inputs` deliberately omitted: a manual stamp has NOT just built, so it
    # cannot say what the graph was built from. Omitting the key makes the
    # staleness check report *not verifiable* rather than adopting whatever
    # `sources/` says right now as the build's inputs — a false green that would
    # be indistinguishable from a real rebuild.
    path = sync.write_stamp(repo_root, spec, version=resolved, source_ref=source_ref)
    print(f"[currency] stamped {path.relative_to(repo_root)} at {resolved}")
    return 0
