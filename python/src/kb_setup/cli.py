# Copyright (c) 2026 Raymond Manaloto
"""kb-setup CLI — build / update the knowledge graph.

Thin dispatch; logic lives in kb_setup.graph. Invoked by the mise tasks
`kb-build` and `kb-update` (run from the repo root).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kb_setup import __version__

_ASSEMBLE_MIN_ARGS = 2  # <name> + at least one <chunk.json>


#: Subcommands that ALWAYS hand graph.json to graphify. Each gets a
#: pinned-version preflight in `main` — a stale graphify rewriting the
#: artifact is data loss, not just a worse answer. `update` is deliberately
#: NOT here: a `kind = docs` pin advance is pure git and must not be blocked
#: by a stale binary it never runs (cold lane round 2, P2), so `graph.update`
#: gates its own code-kind branch instead — the one place the kind is known.
_GRAPH_WRITERS = frozenset({"build", "watch", "merge", "label", "artifacts"})


#: Opt-in path for the JSONL event sink. Set it and every event this run emits
#: is also written as one JSON object per line — R9's queryable surface, on
#: demand. Off by default so ordinary runs write exactly what they write today.
_JSONL_ENV = "KB_EVENTS_JSONL"


def main(argv: list[str] | None = None) -> int:
    """Dispatch a kb-setup subcommand under §2.5's stdout sink.

    **This is the ONE place the sink is attached**, and it has to be here rather
    than inside each command: a converted boundary emits events instead of
    printing, so a command reached with no sink attached would run correctly and
    say nothing. Wrapping the dispatch means every entry point gets it once.

    The sink renders each event's `text` verbatim, so what a task prints is
    unchanged by the conversion — which is exactly the property that keeps the
    existing assertions about task output a regression arm.
    """
    from kb_setup import events, sinks

    events.configure()
    with sinks.stdout_sink(jsonl_path=os.environ.get(_JSONL_ENV) or None):
        return _run(argv)


def _print_usage() -> int:
    """Print the subcommand list and return 0.

    Extracted from `_run` rather than left inline: this dispatcher is a long
    if-chain by design (one lazy import per branch, so `kb-setup <one command>`
    never pays for the other forty), and the usage text is the one block in it
    that is not dispatch. Moving it keeps the chain the only thing `_run` does.
    """
    print(
        "kb-setup: build | update <name> | watch | prose | query <question> [--prose] | "
        "affected <symbol> [--depth N] | "
        "code-intel [--lanes a,b] [--out PATH] [--format chunk|json] | "
        "insights [--top N] | graph-size | funnel | "
        "telemetry-prune | serve | "
        "merge <chunk> | label | "
        "transcribe <audio> | artifacts | currency [check|run|stamp|docs-reviewed] | "
        "brain [record|reflect|audit] | distill | session-reflect [--sessions N] | "
        "arms <spec.toml> [--dry-run] | "
        "reclaim [--apply] [--only c1,c2] [--skip c1,c2] | "
        "graph-counts [--by-source] [name...] | "
        "write-attribution <path> [--window N] [--limit N] | "
        "model-limits [--write] [--observed-at DATE] [model...] | "
        "md-budget | skill-lint | workflow-lint | "
        "skill-score [--write] [skill...] | skill-refresh | "
        "handoff-check [path] | gates [task...] [--stop] | check <path...> | "
        "plugin-validate <marketplace root> | "
        "research-trackers <OWNER/REPO> <term> [--out PATH] | "
        "research-links <URL...> [--out PATH] | "
        "research-packages <SYSTEM> <NAME> [--out PATH] | "
        "session-state [--no-pr] | context | next-ticket | "
        "session-select (--current | --sessions <id>... | --last N | "
        "--since <ISO> [--until <ISO>]) | "
        "session-review-archive --run-json PATH [--report-dir DIR] "
        "[--handoff PATH] [--date YYYY-MM-DD] [--dry-run] | "
        "remember --question Q [--answer A|--answer-file F] "
        "[--outcome useful|dead_end|corrected] "
        "[--correction C|--correction-file F] [--nodes N...] | remember --audit | "
        "goal-check <path|--text ...> | "
        "goal-outcome <pair> --result R [--turns N] [--note ...] | "
        "cc | cc-doctor | eval [--live] [--slow] | "
        "graphify-contract | graphify-baseline build|controls|verify [PATH] | "
        "graphify-native-extract [--out DIR] [--target DIR] [--token-budget N] "
        "[--max-concurrency N] [--model NAME] [--backend NAME] "
        "[--allow-parallel-claude-cli] [--cluster] "
        "[--artifacts [VIEW...]] [--dry-run] | "
        "skillopt-contract | "
        "tool-sync <currency-tool-name> | "
        "skillopt-reviewed --packet P --target T --backend mock|handoff | "
        "ecosystem-discovery-plan [alternative...] | "
        "detect-census [--output .agent/<path>.json] | "
        "source-groups-check [path] | "
        "artifact-download --provider P --source O/R --revision SHA --destination PATH | "
        "ensure-deps | version"
    )
    return 0


def _run(argv: list[str] | None = None) -> int:
    """Dispatch a kb-setup subcommand; returns the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path.cwd()

    if not args:
        return _print_usage()

    cmd, rest = args[0], args[1:]
    if cmd in {"-V", "--version", "version"}:
        print(f"kb-setup {__version__}")
        return 0
    if cmd in _GRAPH_WRITERS:
        from kb_setup import graphify_env

        # Writers only, and at the TASK layer rather than inside the library
        # functions, deliberately: every real invocation enters here (the
        # PreToolUse guard denies raw graphify), readers merely get worse
        # answers from a stale binary while writers destroy data with it
        # (cold lane on #186, P1 — see `assert_pinned_graphify`), and the
        # library functions stay drivable by test stubs that fake the exe.
        graphify_env.assert_pinned_graphify(repo_root)
    if cmd == "build":
        return _build_checked(repo_root)
    if cmd == "update":
        from kb_setup import graph

        # The rc is RETURNED, not discarded. A docs pin whose diff failed leaves
        # the pin correctly unmoved and prints "UNKNOWN — re-run", but this used
        # to `return 0` regardless, so the one failure path the module has was
        # invisible to anything reading an exit code. (Cold lane round 2, P2.)
        if not rest:  # update ALL sources
            return graph.update_all(repo_root)
        return graph.update(repo_root, rest[0])
    if cmd == "watch":
        from kb_setup import graph

        # Named `watch` for the task it replaces, and it is NOT a watcher — see
        # `graph.refresh_self`. One-shot by design: `graphify watch` refreshes
        # only a scoped sub-graph and offers no post-rebuild hook, so it cannot
        # keep the aggregate (the graph `affected` actually reads) current.
        # Same contract as `build` just above: success is a `None` return, a
        # refusal is a `SystemExit` the dispatcher's own caller renders.
        graph.refresh_self(repo_root)
        return 0
    if cmd == "prose":
        from kb_setup import prose

        prose.derive_for(repo_root)
        return 0
    if cmd == "query":
        from kb_setup import graphify_ops

        return graphify_ops.query(repo_root, rest)
    if cmd in {
        "graphify-contract",
        "graphify-baseline",
        "skillopt-contract",
    }:
        return _dispatch_contract(repo_root, cmd, rest)
    if cmd == "skillopt-reviewed":
        from kb_setup import skillopt_reviewed

        return skillopt_reviewed.reviewed_main(repo_root, rest)
    if cmd in {"source-groups-check", "artifact-download", "model-limits"}:
        return _dispatch_registry(repo_root, cmd, rest)
    if cmd == "ecosystem-discovery-plan":
        from kb_setup import ecosystem_discovery

        return ecosystem_discovery.plan_main(rest)
    if cmd == "affected":
        from kb_setup import graphify_ops

        return graphify_ops.affected(repo_root, rest)
    if cmd == "code-intel":
        from kb_setup import code_intel

        # Read-only, like `affected` just above: no graph write, so no
        # `_GRAPH_WRITERS` membership and no pinned-graphify preflight (#276).
        return code_intel.code_intel_main(repo_root, rest)
    if cmd == "funnel":
        from kb_setup import funnel

        # A bare arm, not grouped into `_dispatch_graph_hygiene` below: that
        # helper's members share "how big has this grown", and `funnel` asks a
        # different question (did this branch's research reach `sources/**`).
        # Left flat on the `pyproject.toml` per-file-ignore precedent this
        # dispatcher already carries (`C901`/`PLR0911`/`PLR0912`/`PLR0915` for
        # `cli.py`) — one more `if cmd == ...` arm is the intended shape here,
        # not a ceiling to work around with a new grouping helper.
        return funnel.main(repo_root, rest)
    if cmd in {"insights", "graph-size", "telemetry-prune"}:
        return _dispatch_graph_hygiene(repo_root, cmd, rest)
    if cmd == "serve":
        from kb_setup import mcp_serve

        # With no KB_MCP_TOOLS/KB_MCP_RESOURCES set the child inherits this
        # process's stdio, so the default path keeps nothing of ours in the DATA
        # path between the client and `graphify-mcp`. This comment claimed an
        # `execvpe` that the code stopped doing; the cold lane found the two
        # disagreeing.
        return mcp_serve.serve(repo_root, rest)
    if cmd == "artifacts":
        from kb_setup import artifacts, graphify_health

        rc = artifacts.generate(repo_root, only=rest or None)
        graphify_health.require_complete(
            graphify_health.assess(
                graphify_health.GraphifyOperation.ARTIFACT,
                graphify_health.GraphifyEvidence(observed=True, returncode=rc),
            )
        )
        return rc
    if cmd == "merge":
        from kb_setup import graphify_ops

        if not rest:
            print("kb-setup merge <chunk.json> [source_root]", file=sys.stderr)
            return 2
        return graphify_ops.merge_chunk(repo_root, rest[0], rest[1] if len(rest) > 1 else None)
    if cmd == "label":
        from kb_setup import graphify_ops

        return graphify_ops.label(
            repo_root,
            missing_only="--missing-only" in rest,
            claude_cli="--claude-cli" in rest,
        )
    if cmd == "transcribe":
        from kb_setup import graphify_ops

        if not rest:
            print("kb-setup transcribe <audio-file>", file=sys.stderr)
            return 2
        return graphify_ops.transcribe(repo_root, rest[0])
    # UNPARKED 2026-08-26. Removed 2026-08-24 so that three defects reachable
    # ONLY through this branch and its mise task — `_parse`'s flag-swallowing
    # (#479), the `GRAPHIFY_OUT` bypass of `_refuse_out` (#480), and the wholly
    # untested `_run_real`/`_run_cluster` (#481) — could not be reached while
    # they were fixed. All three are CLOSED; the module carries 70 tests, four
    # of which drive `_run_real`/`_run_cluster` directly.
    #
    # It belongs HERE, in `_run`, and not beside the park's old comment: that
    # comment had drifted into `_dispatch_contract`, which only ever receives
    # `graphify-contract`/`graphify-baseline`/`skillopt-contract`. Restoring the
    # branch where the comment sat produced code no caller could reach — caught
    # by running `--help` against it, not by the type checker or the tests,
    # both of which were green over the dead branch.
    if cmd == "graphify-native-extract":
        from kb_setup import graphify_native_extract

        return graphify_native_extract.native_extract_main(repo_root, rest)
    return _dispatch_ops(repo_root, cmd, rest)


def _dispatch_contract(repo_root: Path, cmd: str, rest: list[str]) -> int:
    """Run one strict dependency/API contract."""
    if cmd == "graphify-contract":
        from kb_setup import graphify_sdk

        return graphify_sdk.contract_main(repo_root)
    if cmd == "graphify-baseline":
        from kb_setup import graphify_baseline

        if rest[:1] == ["controls"]:
            from kb_setup import graphify_env

            # `controls` reaches `graphify_sdk.observe_detect` without passing
            # through `runtime_identity`, so it gets the same TASK-layer pin
            # guard as `_GRAPH_WRITERS`. `build` is covered by
            # `runtime_identity`; `verify` never runs Graphify.
            graphify_env.assert_pinned_graphify(repo_root)
        return graphify_baseline.baseline_main(repo_root, rest)
    # `graphify-native-extract` was UNPARKED 2026-08-26 and its branch lives in
    # `_run`, NOT here. The park's comment sat at this spot, which is misleading:
    # this helper only ever receives `graphify-contract`, `graphify-baseline` and
    # `skillopt-contract`, so a branch restored here would be unreachable — which
    # is exactly what happened on the first attempt, green under ty and pytest
    # alike, and caught only by running the command.
    from kb_setup import skillopt_contract

    return skillopt_contract.contract_main(repo_root)


def _dispatch_graph_hygiene(repo_root: Path, cmd: str, rest: list[str]) -> int:
    """Report on, or bound, what the graph and its telemetry have grown into.

    Grouped on `_dispatch_registry`'s precedent rather than left as three arms of
    the main chain, which had reached its statement ceiling. They belong together
    on more than length: each answers "how big has this got, and is that still
    all right" — `insights` reports, `graph-size` gates the ceiling graphify will
    refuse to read past, and `telemetry-prune` bounds the raw-body sink nothing
    else rotates.
    """
    if cmd == "insights":
        from kb_setup import insights

        return insights.report(repo_root, rest)
    if cmd == "graph-size":
        from kb_setup import graph_size

        return graph_size.main(repo_root)
    from kb_setup import telemetry

    return telemetry.main(repo_root)


def _dispatch_registry(repo_root: Path, cmd: str, rest: list[str]) -> int:
    """Run one typed registry or immutable artifact boundary.

    `model-limits` belongs here rather than with the advisory analysers: it is a
    typed registry of an EXTERNAL fact (a model's output ceiling) with a
    committed snapshot as its record, and it fails closed rather than reporting
    an empty result as clean.
    """
    if cmd == "source-groups-check":
        from kb_setup import source_groups

        return source_groups.check_main(repo_root, rest)
    if cmd == "model-limits":
        import os

        from kb_setup import model_limits

        return model_limits.main(repo_root, rest, os.environ)
    from kb_setup import artifact_download

    return artifact_download.main(repo_root, rest)


def _dispatch_lint(repo_root: Path, cmd: str) -> int | None:
    """Dispatch the authoring-time lint gates; ``None`` when ``cmd`` is not one.

    Grouped out of :func:`_dispatch_ops` because these three share a shape the
    operational commands do not: each takes only the repo root, each is an hk
    step, and each answers "is this tree well-formed to author in" rather than
    "do something to the graph". Splitting them also kept `_dispatch_ops` under
    ruff's statement ceiling when `skill-lint` was added — the ceiling doing the
    job it exists for, rather than being suppressed.
    """
    if cmd == "no-lint-skip":
        from kb_setup import lint_checks

        return lint_checks.no_lint_skip(repo_root)
    if cmd == "md-budget":
        from kb_setup import md_budget

        return md_budget.md_budget_main(repo_root)
    if cmd == "skill-lint":
        from kb_setup import skill_lint

        return skill_lint.skill_lint_main(repo_root)
    if cmd == "workflow-lint":
        from kb_setup import workflow_lint

        return workflow_lint.workflow_lint_main(repo_root)
    if cmd == "hk-test":
        from kb_setup import hk_test

        return hk_test.hk_test_main(repo_root)
    return None


#: Advisory analysers: they propose or measure, they gate nothing, and neither is
#: wired into `kb-gates`/`kb-ship`. Grouped so the ops dispatch stays under its
#: statement budget rather than growing a branch per tool.
#: `reclaim` is advisory in the same sense — it gates nothing — but it is the one
#: member that CAN delete, and only behind an explicit `--apply`. Grouped here
#: because its default path (report, rc 0, no mutation) is identical to the others'.
_ADVISORY = frozenset(
    {"distill", "session-reflect", "arms", "reclaim", "graph-counts", "write-attribution"}
)


def _dispatch_advisory(repo_root: Path, cmd: str, rest: list[str]) -> int:
    """Dispatch the advisory analysers (`distill`, `arms`, `reclaim`)."""
    if cmd == "distill":
        from kb_setup import distill

        return distill.distill_main(repo_root, rest)
    if cmd == "session-reflect":
        from kb_setup import session_reflect

        return session_reflect.reflect_main(repo_root, rest)
    if cmd == "write-attribution":
        from kb_setup import write_attribution

        return write_attribution.write_attribution_main(repo_root, rest)
    if cmd == "reclaim":
        from kb_setup import reclaim

        return reclaim.main(rest, repo_root)
    if cmd == "graph-counts":
        from kb_setup import graph_counts

        return graph_counts.report(repo_root, rest)
    from kb_setup import arms

    return arms.main(rest, repo_root)


def _dispatch_record(repo_root: Path, cmd: str, rest: list[str]) -> int | None:
    """Dispatch the round-record commands; ``None`` when ``cmd`` is not one.

    Grouped for the same reason :func:`_dispatch_lint` was, and stated here
    because the ceiling is doing its job again rather than being suppressed:
    adding `remember` pushed `_dispatch_ops` to 52 statements against ruff's
    limit of 50.

    These five share a shape the rest of the ops family does not — each one
    reads or writes the RECORD OF A ROUND rather than acting on the graph or
    the tree: what this branch handed off, what state the session is in, what
    the goal was and how it went, and what was learned. `remember` is the newest
    member and the reason the group exists.
    """
    if cmd == "handoff-check":
        from kb_setup import handoff

        return handoff.main(rest, repo_root)
    if cmd == "session-state":
        from kb_setup import session_state

        return session_state.main(rest, repo_root)
    if cmd == "session-select":
        from kb_setup import session_select

        return session_select.main(rest, repo_root)
    if cmd == "session-review-archive":
        from kb_setup import session_review_archive

        return session_review_archive.main(rest, repo_root)
    if cmd == "context":
        from kb_setup import context_usage

        return context_usage.main(rest, repo_root)
    if cmd == "remember":
        from kb_setup import remember

        return remember.main(repo_root, rest)
    if cmd == "goal-check":
        from kb_setup import goal

        return goal.main(rest, repo_root)
    if cmd == "goal-outcome":
        from kb_setup import goal

        return goal.outcome_main(rest, repo_root)
    if cmd == "next-ticket":
        from kb_setup import next_ticket

        return next_ticket.main(rest, repo_root)
    return None


def _dispatch_ops(repo_root: Path, cmd: str, rest: list[str]) -> int:
    """Dispatch the operational subcommands (hooks, brain, ship/land, currency, chunks)."""
    if cmd == "hookguard":
        from kb_setup import hook_guard

        return hook_guard.run()
    if cmd == "detect-census":
        from kb_setup import graph

        return graph.detection_census_main(repo_root, rest)
    if cmd == "brain":
        from kb_setup import brain

        return brain.dispatch(repo_root, rest)
    if cmd in _ADVISORY:
        return _dispatch_advisory(repo_root, cmd, rest)
    lint_rc = _dispatch_lint(repo_root, cmd)
    if lint_rc is not None:
        return lint_rc
    record_rc = _dispatch_record(repo_root, cmd, rest)
    if record_rc is not None:
        return record_rc
    if cmd == "research-trackers":
        from kb_setup.research import trackers

        return trackers.main(rest, repo_root)
    if cmd == "research-links":
        from kb_setup.research import links

        return links.main(rest, repo_root)
    if cmd == "research-packages":
        from kb_setup.research import packages

        return packages.main(rest, repo_root)
    if cmd == "gates":
        from kb_setup import gates

        return gates.main(rest, repo_root)
    if cmd == "check":
        from kb_setup import check

        # NOT in `_ADVISORY`: this one's exit code is the answer. It is also not
        # a gate — it writes no `.agent/kb/gates/` record, because a per-file
        # check is not evidence about a commit.
        return check.main(repo_root, rest)
    if cmd == "plugin-validate":
        from kb_setup import plugin_validate

        return plugin_validate.main(repo_root, rest)
    if cmd == "skill-score":
        from kb_setup import skill_eval

        return skill_eval.main(rest, repo_root)
    if cmd == "skill-refresh":
        from kb_setup import skill_refresh

        return skill_refresh.refresh(repo_root)
    if cmd == "cc":
        from kb_setup import launch

        return launch.cc_main(repo_root, rest)
    if cmd == "cc-doctor":
        from kb_setup import launch

        return launch.doctor_main(repo_root, rest)
    if cmd == "eval":
        from kb_setup import eval_cases, evals

        rc, report = evals.run(
            eval_cases.cases(repo_root), live="--live" in rest, slow="--slow" in rest
        )
        print(report)
        return rc
    if cmd == "ensure-deps":
        from kb_setup.graphify_env import ensure_runtime_deps

        got = ensure_runtime_deps(repo_root)
        print(f"[deps] {'installed ' + ', '.join(got) if got else 'all output deps present'}")
        return 0
    if cmd == "ship":
        from kb_setup import pr

        return pr.ship_main(repo_root, title=_opt(rest, "--title"))
    if cmd == "land":
        from kb_setup import pr

        positional = [a for a in rest if not a.startswith("-")]
        if not positional or not positional[0].isdigit():
            print("kb-setup land <PR#>", file=sys.stderr)
            return 2
        return pr.land_main(repo_root, int(positional[0]))
    if cmd == "review-receipt":
        return _review_receipt(repo_root, rest)
    if cmd == "currency":
        return _currency(repo_root, rest)
    if cmd == "tool-sync":
        from kb_setup import tool_sync

        return tool_sync.main(repo_root, rest)
    if cmd == "manifest-add":
        return _manifest_add(repo_root, rest)
    if cmd == "assemble":
        return _assemble(repo_root, rest)
    if cmd == "validate-chunks":
        return _validate_chunks(rest)
    if cmd == "fetch":
        return _fetch(repo_root, rest)
    if cmd == "fetch-verify":
        from kb_setup import fetch as fetch_mod

        return fetch_mod.fetch_verify_main(repo_root, [Path(arg) for arg in rest])

    print(
        f"kb-setup: unknown command {cmd!r} "
        "(build | update [name] | prose | query <question> [--prose] | "
        "merge <chunk> [root] | label [--missing-only] "
        "[--claude-cli] | transcribe <audio> | artifacts [fmt...] | "
        "currency [check|run|stamp|docs-reviewed] [--tool T --json --no-write] | "
        "tool-sync <currency-tool-name> | "
        "manifest-add <url> "
        "[--ref R --kind K --name N --comment C --force] | assemble <name> <chunk...> | "
        "brain [query|record|reflect|audit] | distill | arms <spec.toml> [--dry-run] | "
        "reclaim [--apply] [--only c1,c2] [--skip c1,c2] | "
        "md-budget | skill-lint | workflow-lint | "
        "skill-score [--write] [skill...] | "
        "handoff-check [path] | gates [task...] [--stop] | check <path...> | funnel | "
        "plugin-validate <marketplace root> | "
        "research-trackers <OWNER/REPO> <term> [--out PATH] | "
        "research-links <URL...> [--out PATH] | "
        "research-packages <SYSTEM> <NAME> [--out PATH] | "
        "session-state [--no-pr] | next-ticket | "
        "session-review-archive --run-json PATH [--report-dir DIR] "
        "[--handoff PATH] [--date YYYY-MM-DD] [--dry-run] | "
        "remember [--audit] | cc | cc-doctor | "
        "eval [--live] [--slow] | "
        "validate-chunks <chunk...> | fetch-verify <pages.toml...> | "
        "ship [--title T] | land <PR#> | ensure-deps | version)",
        file=sys.stderr,
    )
    return 2


def _build_checked(repo_root: Path) -> int:
    """Build and require typed evidence for the complete graph output set.

    Every exit from here is RECORDED (#397). A build that fails writes no stamp,
    and "no stamp" read identically to a fresh clone's — so the defect presented
    as a scheduling to-do and several handoffs in a row carried it as one. The
    record is what lets `kb-currency-check` tell the two apart; see
    `kb_setup.build_outcome`.
    """
    from kb_setup import build_outcome, graph, graphify_health

    try:
        graph.build(repo_root)
        expected = ("graphify-out/graph.json", "graphify-out/graph-prose.json")
        produced = tuple(path for path in expected if (repo_root / path).is_file())
        graphify_health.require_complete(
            graphify_health.assess(
                graphify_health.GraphifyOperation.BUILD,
                graphify_health.GraphifyEvidence(
                    observed=True,
                    mode="deep",
                    deep_required=True,
                    expected_artifacts=expected,
                    produced_artifacts=produced,
                ),
            )
        )
    except BaseException as exc:
        # BaseException, not Exception: `graph.build` refuses with `SystemExit`,
        # which is the single most likely failure to reach here and is NOT an
        # `Exception`. A KeyboardInterrupt is recorded too — an interrupted
        # build also leaves no stamp, and calling that "never run" is the same
        # lie in a smaller hat — but under its OWN stage, because nothing about
        # Ctrl-C says the build is broken or that a re-run will fail again.
        stage = build_outcome.INTERRUPTED if isinstance(exc, KeyboardInterrupt) else "build"
        build_outcome.record_failure(repo_root, stage, f"{type(exc).__name__}: {exc}")
        raise
    build_outcome.clear(repo_root)
    return 0


#: Every flag `kb-setup review-receipt` reads. Stating one twice is refused
#: rather than silently resolved to whichever `_opt` happens to find first.
_RECEIPT_FLAGS = ("--lanes", "--skipped", "--findings", "--blocking", "--fixed-point")

#: Digit bound on `--findings` / `--blocking`. Well under CPython's
#: `sys.int_info.str_digits_check_threshold` (4300), past which `int()` itself
#: raises ValueError — and far past any real finding count.
_MAX_COUNT_DIGITS = 18


def _review_receipt(repo_root: Path, rest: list[str]) -> int:
    """Write the `kb-review` skill's receipt for HEAD; `ship` refuses to push without it."""
    from kb_setup import review

    # No `--sha` override. A receipt is ALWAYS for HEAD: letting the caller name
    # a commit lets them file one for something that was never reviewed, and a
    # value containing a path separator would write outside the receipt dir.
    # (Spec lane.) An amend moves HEAD and invalidates the receipt — that is the
    # intended behaviour, not something to work around with a flag.
    sha = review.head_sha(repo_root)
    if not sha:
        print("review-receipt: could not read HEAD", file=sys.stderr)
        return 2

    # `_opt` returns the FIRST occurrence of a flag, so `--blocking 2 --blocking 0`
    # silently kept the 2 and `--blocking 0 --blocking 2` silently kept the 0 —
    # a one-token way to say something other than what the command line reads as,
    # on the one field that gates. Ambiguity is refused rather than resolved.
    # (Cold lane.)
    repeated = sorted({f for f in _RECEIPT_FLAGS if rest.count(f) > 1})
    if repeated:
        print(
            f"review-receipt: repeated flag(s) {', '.join(repeated)} — state each once",
            file=sys.stderr,
        )
        return 2

    lanes = [s.strip() for s in (_opt(rest, "--lanes") or "").split(",") if s.strip()]
    if not lanes:
        print(
            "review-receipt: --lanes is required, comma-separated "
            "(e.g. standards,spec,cold:codex,silent-failure)",
            file=sys.stderr,
        )
        return 2
    skipped = [s.strip() for s in (_opt(rest, "--skipped") or "").split(",") if s.strip()]

    # `--blocking` is REQUIRED and has no default. `review.receipt_state` rejects
    # a missing blocking count as ambiguity rather than consent — defaulting it to
    # "0" here would hand that fail-closed reader a fail-open writer, so the one
    # field that actually gates would be the one nobody had to state. (Found by
    # the silent-failure lane reviewing this command's own first draft.)
    #
    # `--findings` does default: it is reported, not gated, so an omission is
    # imprecision rather than an unearned pass.
    counts: dict[str, int] = {}
    for flag, default in (("--findings", "0"), ("--blocking", None)):
        raw = _opt(rest, flag)
        if raw is None and default is None:
            print(
                f"review-receipt: {flag} is required — state it explicitly, including {flag} 0",
                file=sys.stderr,
            )
            return 2
        raw = raw if raw is not None else default
        # `.isdigit()` and not `.lstrip("-").isdigit()`: the latter accepts "--5",
        # which then raises ValueError out of int(). `.isascii()` as well, because
        # `.isdigit()` alone is True for Unicode digits like "²" that `int()` then
        # REJECTS — so the guard whose comment claims it prevents a ValueError
        # raised one. (Cold lane, twice.)
        # The length bound is not cosmetic: CPython refuses `int()` on a
        # digit-string longer than `sys.int_info.str_digits_check_threshold`
        # (4300 by default) and raises ValueError — so an all-digit value could
        # still crash the parse this guard exists to protect. (Cold lane.)
        if raw is None or not raw.isascii() or not raw.isdigit() or len(raw) > _MAX_COUNT_DIGITS:
            print(f"review-receipt: {flag} must be a non-negative integer", file=sys.stderr)
            return 2
        counts[flag] = int(raw)

    # `_opt` returns its default when a flag is LAST with no value, so a dangling
    # `--fixed-point` silently reviewed against `main` while the command line said
    # otherwise. A stated flag with no value is a typo, not a default.
    #
    # The test is on the VALUE, not on `is None`. `_opt` returns `""` — not None —
    # for an explicitly empty `--fixed-point ""`, so the `is None` form let one
    # token slip past the guard and `or "main"` then substituted silently: the
    # receipt recorded a base the command line never stated. Same class as the
    # repeated-flag hole, and the third time this field has been the one that
    # drifts. `.strip()` closes the whitespace-only spelling in the same move,
    # because `git merge-base -- " " HEAD` is a refusal, not a base. (#55)
    if "--fixed-point" in rest and not (_opt(rest, "--fixed-point") or "").strip():
        print("review-receipt: --fixed-point needs a value", file=sys.stderr)
        return 2
    # Defaults to the SAME ref `ship`/`land` gate against (`review.DEFAULT_BASE_REF`
    # — `origin/main`), not a second spelling of it. The default was the literal
    # `"main"` while the gate resolved local `main` too, so they agreed by
    # coincidence; pointing only the gate at `origin/main` would have made the
    # writer record one base and the reader demand another. (#54)
    fixed_point = _opt(rest, "--fixed-point") or review.DEFAULT_BASE_REF
    receipt = review.Receipt(
        sha=sha,
        fixed_point=fixed_point,
        # Pinned to the SHA captured above, not to live HEAD: reading them a
        # moment apart let a checkout in between label this receipt with a base
        # from a different branch.
        fixed_point_sha=review.base_sha(repo_root, fixed_point, head=sha),
        lanes_ran=tuple(lanes),
        lanes_skipped=tuple(skipped),
        findings=counts["--findings"],
        blocking=counts["--blocking"],
    )

    # Validated BEFORE the write. Writing first and reporting REJECTED after
    # would leave an invalid receipt on disk for this SHA — harmless to the gate,
    # which re-reads and re-rejects it, but it turns "no review yet" into "a
    # review that failed", and those should not look the same on disk.
    reason = review.rejection(repo_root, receipt)
    if reason is not None:
        print(f"review-receipt: REFUSED — {reason}", file=sys.stderr)
        return 2

    path = review.write_receipt(repo_root, receipt)
    print(f"review-receipt: wrote {path.relative_to(repo_root)}")
    ok, summary = review.receipt_state(repo_root, sha)
    print(f"review-receipt: {'OK' if ok else 'REJECTED'} — {summary}")
    # A receipt this module just wrote and its own gate rejects means the writer
    # and the reader disagree — a defect in one of them, surfaced now rather
    # than at ship time.
    return 0 if ok else 1


def _fetch(repo_root: Path, rest: list[str]) -> int:
    """`kb-setup fetch <url> [--stem NAME]` — lossless fetch into sources/."""
    from kb_setup import fetch as fetch_mod

    flags = {"--stem"}
    positional = [
        a
        for i, a in enumerate(rest)
        if not a.startswith("--") and (i == 0 or rest[i - 1] not in flags)
    ]
    if not positional:
        print("kb-setup fetch: need a URL", file=sys.stderr)
        return 2
    return fetch_mod.fetch_main(repo_root, positional[0], stem=_opt(rest, "--stem"))


def _opt(rest: list[str], flag: str, default: str | None = None) -> str | None:
    """Read `--flag value` from a manual arg list (positional-friendly dispatch)."""
    if flag in rest and rest.index(flag) + 1 < len(rest):
        return rest[rest.index(flag) + 1]
    return default


def _currency(repo_root: Path, rest: list[str]) -> int:
    """Dispatch `kb-setup currency`.

    Modes: check | run | apply | daily | docs-reviewed | watch-reviewed |
    prune-reviewed | stamp.
    """
    from kb_setup.currency import run as currency_run

    only = _opt(rest, "--tool", "") or ""
    # Skip the VALUES of value-taking flags when looking for the positional mode,
    # or `currency --tool graphify` reads "graphify" as the mode and errors out.
    # `--ref`/`--note` are `watch-reviewed`'s (#486) — omitting either from this
    # set has its VALUE collected as a positional and misread as the mode, which
    # breaks the command's invocation outright rather than merely misparsing a flag.
    value_flags = {"--tool", "--version", "--source-ref", "--ref", "--note"}
    positional: list[str] = []
    skip_next = False
    for arg in rest:
        if skip_next:
            skip_next = False
            continue
        if arg in value_flags:
            skip_next = True
            continue
        if not arg.startswith("-"):
            positional.append(arg)
    mode = positional[0] if positional else "check"
    if mode == "check":
        return currency_run.check(repo_root, only=only, quiet="--verbose" not in rest)
    if mode == "run":
        return currency_run.run(
            repo_root,
            only=only,
            as_json="--json" in rest,
            write="--no-write" not in rest,
        )
    if mode == "apply":
        return currency_run.apply(repo_root, only=only, as_json="--json" in rest)
    if mode == "daily":
        return currency_run.daily(repo_root)
    if mode == "docs-reviewed":
        return currency_run.docs_reviewed(repo_root, only=only)
    if mode == "watch-reviewed":
        ref = _opt(rest, "--ref", "") or ""
        version = _opt(rest, "--version", "") or ""
        note = _opt(rest, "--note", "") or ""
        # `_opt` returns whatever token follows a flag, never checking whether
        # that token is itself another flag's name — `--tool --version 1.2.3`
        # yields only="--version". Guard every value THIS branch reads
        # explicitly; `_opt` itself is unchanged, so every other mode keeps
        # today's (also imperfect) behaviour rather than this task silently
        # changing it everywhere.
        for flag_name, value in (
            ("--tool", only),
            ("--ref", ref),
            ("--version", version),
            ("--note", note),
        ):
            if value.startswith("--"):
                print(
                    f"kb-setup currency watch-reviewed: {flag_name} looks dangling — "
                    f"got {value!r}, which is itself a flag",
                    file=sys.stderr,
                )
                return 2
        return currency_run.watch_reviewed(
            repo_root, only=only, ref=ref, version=version, note=note
        )
    if mode == "prune-reviewed":
        # A SEPARATE mode from watch-reviewed, deliberately (cold review, MAJ-1):
        # pruning is destructive and recording is not, so they do not share an
        # entry point or a flag — see `run.prune_reviewed`.
        return currency_run.prune_reviewed(repo_root, only=only)
    if mode == "stamp":
        if not only:
            print(
                "kb-setup currency stamp --tool <name> [--version V --source-ref R]",
                file=sys.stderr,
            )
            return 2
        return currency_run.stamp(
            repo_root,
            tool=only,
            version=_opt(rest, "--version", "") or "",
            source_ref=_opt(rest, "--source-ref", "") or "",
        )
    print(
        f"kb-setup currency: unknown mode {mode!r} "
        "(check | run | apply | daily | docs-reviewed | watch-reviewed | prune-reviewed | stamp)",
        file=sys.stderr,
    )
    return 2


def _manifest_add(repo_root: Path, rest: list[str]) -> int:
    from kb_setup import manifest

    urls = [a for a in rest if a.startswith(("http://", "https://", "git@"))]
    if not urls:
        print(
            "kb-setup manifest-add <url> [--ref --kind --name --comment --force]", file=sys.stderr
        )
        return 2
    source = manifest.NewSource(
        url=urls[0],
        ref=_opt(rest, "--ref", "main") or "main",
        kind=_opt(rest, "--kind", "code") or "code",
        name=_opt(rest, "--name"),
        comment=_opt(rest, "--comment"),
    )
    try:
        m = manifest.add(repo_root / "sources", source, force="--force" in rest)
    except (FileExistsError, RuntimeError) as e:
        print(f"[kb-manifest-add] {e}", file=sys.stderr)
        return 1
    print(f"[kb-manifest-add] wrote {m.path.relative_to(repo_root)} @ {m.commit}")
    return 0


def _assemble(repo_root: Path, rest: list[str]) -> int:
    import json

    from kb_setup import chunks

    args = [a for a in rest if not a.startswith("--")]
    if not args or len(args) < _ASSEMBLE_MIN_ARGS:
        print("kb-setup assemble <name> <chunk.json>...", file=sys.stderr)
        return 2
    name, *chunk_strs = args
    chunk_paths = [Path(a) for a in chunk_strs]
    try:
        out = chunks.assemble(repo_root, name, chunk_paths)
    except ValueError as e:
        print(f"[kb-assemble] {e}", file=sys.stderr)
        return 1
    combined = json.loads(out.read_text(encoding="utf-8"))
    print(
        f"[kb-assemble] wrote {out.relative_to(repo_root)}: "
        f"{len(combined['nodes'])} nodes, {len(combined['edges'])} edges "
        f"from {len(chunk_paths)} chunk(s)"
    )
    return 0


def _validate_chunks(rest: list[str]) -> int:
    from kb_setup import chunks

    paths = [Path(a) for a in rest if not a.startswith("--")]
    if not paths:
        print("kb-setup validate-chunks <chunk.json>...", file=sys.stderr)
        return 2
    results = chunks.validate_files(paths)
    bad = 0
    for p, issues in results.items():
        if issues:
            bad += 1
            print(f"✗ {p}:", file=sys.stderr)
            for i in issues:
                print(f"    {i}", file=sys.stderr)
        else:
            print(f"✓ {p}")

    # Cross-chunk ownership (#189) — a property of the SET, so it is reported
    # separately from the per-path rows rather than blamed on one of them. It is
    # skipped, and SAID to be skipped, for a single path: silence there would be
    # indistinguishable from "checked and clean", which is the reading that let
    # a colliding chunk through with a ✓ beside it.
    collisions = chunks.collision_issues(paths)
    if collisions:
        print(f"✗ cross-chunk: {len(collisions)} source_file collision(s):", file=sys.stderr)
        for c in collisions:
            print(f"    {c}", file=sys.stderr)
        bad += 1
    elif len(paths) > 1:
        print(f"✓ cross-chunk: no source_file collisions across {len(paths)} chunks")
    else:
        print("- cross-chunk: SKIPPED (needs 2+ chunks; pass the whole corpus to check)")

    bad += _report_edge_direction(paths)
    return 1 if bad else 0


def _report_edge_direction(paths: list[Path]) -> int:
    """Structural edge-direction contradictions (hard) and heuristics (advisory).

    Reported AFTER the schema rows because it answers a different question: not
    "is this chunk well-formed" but "does its edge set contradict itself". The two
    channels are printed separately and only the hard one counts toward `bad` —
    an advisory that failed a gate would be switched off, which is the failure
    mode the module's own allowlist experiment demonstrated (1936 firings on
    legitimate vocabulary).

    It CANNOT see semantic direction: `bun_requirement requires channels` is
    backwards and produces no cycle, no self-edge, nothing. Say so here rather
    than let a green line imply the class is covered.

    The chunks are handed to `check_many` as a SET, never looped over one at a
    time: a cycle whose two halves sit in different files is invisible to a
    per-file check, and re-extracting a page under a new chunk name is exactly
    how a corpus acquires two files describing the same node ids.

    The count in the green line is the number of chunks actually PARSED, not the
    number passed in. An unreadable chunk is skipped here (`validate_files` is
    what reports it, and fails the run), and reporting coverage of a file that
    was never read is the shape of claim this repo's gates exist to refuse.
    """
    import json

    from kb_setup import edge_direction

    items: list[tuple[str, object]] = []
    skipped: list[str] = []
    for p in paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            skipped.append(p.name)  # already reported (and failed) by `validate_files`
            continue
        items.append((p.name, chunk))

    hard_total, soft_total = edge_direction.check_many(items)

    if skipped:
        print(
            f"- edge direction: NOT CHECKED for {len(skipped)} unreadable chunk(s): "
            f"{', '.join(skipped)}",
            file=sys.stderr,
        )
    if hard_total:
        print(f"✗ edge direction: {len(hard_total)} contradiction(s):", file=sys.stderr)
        for h in hard_total:
            print(f"    {h}", file=sys.stderr)
    else:
        print(
            f"✓ edge direction: no structural contradictions across the UNION of "
            f"{len(items)} chunk(s) (cycles/self-edges/both-way symmetric edges; "
            f"SEMANTIC direction is NOT checked)"
        )
    for s in soft_total:
        print(f"  ~ {s}")
    return 1 if hard_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
