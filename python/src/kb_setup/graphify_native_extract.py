# Copyright (c) 2026 Raymond Manaloto
"""Drive graphify's OWN native deep extraction over the pinned graphify clone.

## Why this exists

**This is now the ONLY semantic-extraction path in the repo — and it is a
STOPGAP, not the destination.** Read the ranking before changing anything here
(Ray, 2026-08-24):

1. **Best — call graphify's PUBLIC SDK directly**, 1:1 with the CLI verb.
   `graphify_baseline.py` already does this through `kb_setup.graphify_sdk`,
   which exists precisely to pin that public surface
   (`graphify_sdk.public_api_fingerprint()`).
2. **Fallback — shell out to the CLI**, which is what THIS module does, for
   verbs graphify does not yet expose as public SDK methods.
3. **Never — import graphify's private internals.**

So this module should SHRINK over time, not grow: as graphify promotes a verb to
its public API, the call moves from here to a `graphify_sdk` seam. Do not read
"the only path" as "the preferred shape".

Until 2026-08-24 there was a second path, and it died on rule 3. A bespoke
eight-module layer (`graphify_semantic_corpus*.py`, `graphify_semantic_slice.py`,
`graphify_semantic_adapter.py`) imported `_estimate_file_tokens`,
`_extraction_system`, `_pack_chunks_by_tokens` and `_read_files` from
`graphify.llm` — four private functions — and re-implemented planning, slicing
and provider calls around them. Archived and explained in
`docs/archive/README.md`.

Two facts about that layer are worth keeping, because they are why this module
was written and why the ruling went the way it did:

- **It never got cheaper on a second run.** An AST walk of the pinned 0.9.45
  found no cache read anywhere in `extract_corpus_parallel`'s call chain from
  that entry point, only the checkpoint WRITER — so a restart re-bought the
  whole corpus at full price.
- **It drifted.** It copied assumptions out of graphify's internals, and those
  expired silently when graphify changed: `.html` joined
  `_SPLITTABLE_TEXT_SUFFIXES` (#2900), a 1.85 MB excluded file went from one
  unit to ~93, and 24 tests went red on an assumption nobody had touched.

This module calls graphify's own `extract` verb directly —
`graphify extract sources/graphify --mode deep --backend claude-cli` — which
IS the code path with the semantic-deep cache namespace behind it
(`graphify/cli.py`'s deep-mode block: "Deep mode reads/writes its own cache
namespace (cache/semantic-deep/)"). Run 2 onward over an unchanged tree
should be near-free through that cache; the removed layer's per-chunk driver
never touched it.

**Confirmed by a real run, 2026-08-23**: `--allow-parallel-claude-cli
--max-concurrency 4` completed 19/19 chunks (three split-and-retried by
graphify's own adaptive retry) and wrote 13,442 nodes / 26,791 edges / 692
communities to `.agent/kb/native-extract/`, rc=0. See the
`GRAPHIFY_CLAUDE_CLI_PARALLEL` section below for what that run does and does
not establish.

`--cluster` reruns graphify's own `cluster-only <out-dir>` verb against an
already-extracted `--out` tree (no `graph.json` there yet is a refusal, not a
silent no-op) — the step graphify's own `extract` output names as "next" to
get `GRAPH_REPORT.md` and named communities. It is independent of the extract
path: it never touches `opts.target`, runs under bare `clean_env()` with no
`--backend`, and is honoured under `--dry-run` too.

## What this does NOT do

It does not touch the aggregate `graphify-out/graph.json` —
`--out` always points outside both the repo root and the pinned clone (see
`_refuse_out` below). Merging this extraction's output into the aggregate
graph, if ever wanted, is a separate, later decision.

## The `GRAPHIFY_CLAUDE_CLI_PARALLEL` clamp: claim vs. what actually holds

`graphify/llm.py` (pinned v0.9.48, lines 2569 and 3301) force-serializes the
`claude-cli` backend — `max_concurrency` is clamped to 1 — UNLESS
`GRAPHIFY_CLAUDE_CLI_PARALLEL` is exactly `"1"`. graphify's own comments at
both sites give one reason: "claude-cli shells out to a Claude Code session;
parallel subprocesses conflict over session state" / "...a single Claude
Code session that parallel subprocesses corrupt." An earlier draft of this
module took that comment at face value and kept the override opt-in-only on
the strength of it. Two things have since undercut the claim itself,
not just the caution built on it:

1. **The argv graphify itself builds contradicts the stated mechanism.**
   Every `claude-cli` invocation — `_call_claude_cli` (extraction,
   `llm.py:1631` onward) and the labelling call site (`llm.py:2854`) — passes
   `--no-session-persistence` unconditionally, alongside `-p --output-format
   json`. There is no persisted session for concurrent subprocesses to
   contend over; each invocation is a one-shot, stateless CLI call. The
   comment describes a mechanism the code does not exhibit.
2. **The neighbouring clamp is evidenced; this one is not.** The `ollama`
   clamp two lines above cites a real defect (#798: four concurrent 60k-token
   requests cause VRAM pressure and hollow responses after 3-4 chunks). The
   `claude-cli` clamp cites no issue number — it reads as an unevidenced
   precaution, not a measured failure.
3. **It was measured, once, here.** With the clamp lifted
   (`--allow-parallel-claude-cli`, `--max-concurrency 4`), a real deep
   extraction of the pinned `sources/graphify` clone ran 19 chunks: 19 of 19
   completed, three timed out and were split-and-retried by graphify's own
   adaptive-retry path (not corrupted — retried and recovered), and the
   resulting graph (13,442 nodes, 26,791 edges, 692 communities) shows no
   corruption signature. A second run against the same output replayed 241
   cached units and re-extracted 133, rc=0 both times.

**What this licenses, stated at the strength the evidence supports — no
more.** The specific mechanism graphify's own comment names (persisted
session state) does not apply to how it invokes the CLI, and one 19-chunk
run at concurrency 4 on this machine completed cleanly. That is NOT
"parallel claude-cli is proven safe in general" — it is one run, one
machine, one corpus size. This module still keeps
`--allow-parallel-claude-cli` **opt-in** rather than flipping the default:
the evidence is real but it is n=1, and changing a default silently affects
every caller who has not looked at either this evidence or graphify's own
(now-contradicted) reasoning. Passing the flag is an informed choice
backed by the argv and the one completed run above, not a documented risk
being silently ignored — which is the correction to make, without
overcorrecting past what one run can support.

## The dry-run print is deliberately NOT the raw subprocess environment

A dry-run is meant to be safe to paste anywhere. `clean_env()` (which the
real run uses, and must, to keep every non-Claude backend trigger and mise's
secret blob out of the child) is still a COPY of the calling shell's entire
`os.environ` minus a specific named strip list — it is not credential-free
in general (a `GITHUB_TOKEN`, an `NPM_TOKEN`, anything mise's `[env]` block
resolved that isn't on the strip list, all pass through untouched). Printing
that whole dict on `--dry-run` would be exactly the "emit a credential value
to stdout" this repo's `secret_guard` hook exists to deny elsewhere — an
invariant that does not stop applying just because the emitter is our own
code rather than a shell one-liner. So the dry-run prints only the small
OVERLAY this module adds on top of the inherited environment
(`GRAPHIFY_CLAUDE_CLI_MODEL` and, opted in, `GRAPHIFY_CLAUDE_CLI_PARALLEL`),
never the full resolved dict handed to `subprocess.run`.

## Verification scope

This module makes NO provider call, ever, including in its own tests. For
`extract`/`--cluster` the only path this session's verification exercises is
`--dry-run`, which prints the resolved plan and exits before `graphify_exe` is
invoked at all. A human runs the real extraction separately (multi-hour,
serial-by-default, no timeout is set here — the caller bounds it).

`--artifacts` is the one real (non-dry-run) path this suite DOES exercise,
because the thing worth proving — that `_run_artifacts` hands `repo_root` and
`opts.out` to `kb_setup.artifacts.generate` in the right roles (`repo_root` for
the exe/venv anchor, `opts.out` as `graph_root`) — is exactly the wiring a
`--dry-run` print string cannot verify on its own: a reverted arg order would
still print a correct-looking preview. `kb_setup.artifacts.generate` itself is
fully mocked in that test, so no graphify subprocess and no provider call ever
runs; it is a one-line wiring check, not a real extraction.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from kb_setup import events
from kb_setup.graphify_env import assert_pinned_graphify, clean_env, graphify_exe
from kb_setup.result import Rc

#: The pinned clone this task extracts — never this repo itself. Gitignored,
#: re-cloned at build time from `sources/graphify.manifest`.
DEFAULT_TARGET = "sources/graphify"

#: Deliberately OUTSIDE `sources/graphify` (writing into a gitignored,
#: re-cloneable pinned clone is the same class of defect #420 fixed for a
#: stray marker file) and OUTSIDE the repo root (which would place a
#: `graphify-out/` there and collide with the aggregate `kb-build` owns —
#: see `_refuse_out`). `.agent/` is this repo's gitignored scratch tree.
DEFAULT_OUT = ".agent/kb/native-extract"

#: Confirmed 2026-08-23: `claude --help` documents `--model <model>` as
#: accepting "a model's full name (e.g. 'claude-fable-5')" — the CLI's own
#: example proves the `claude-<tier>-5` spelling — and
#: `kb_setup.model_limits` (line ~375) independently recorded a live
#: `GET /v1/models/claude-opus-5` -> 200 on 2026-08-17. "Confirmed" means the
#: identifier's FORM: this module makes no provider call, so nothing here
#: sends a prompt to check it is accepted.
DEFAULT_MODEL = "claude-opus-5"

_MODEL_ENV = "GRAPHIFY_CLAUDE_CLI_MODEL"
_PARALLEL_ENV = "GRAPHIFY_CLAUDE_CLI_PARALLEL"

#: graphify/paths.py: `GRAPHIFY_OUT = os.environ.get("GRAPHIFY_OUT", "graphify-out")`.
#: Not read from the environment here — this module never sets that override,
#: so the literal default is the only value that can apply to a run it starts.
_GRAPHIFY_OUT_NAME = "graphify-out"


@dataclass(frozen=True, slots=True)
class Options:
    """Resolved, absolute inputs to one native-extract invocation."""

    target: Path
    out: Path
    token_budget: int | None = None
    max_concurrency: int | None = None
    allow_parallel_claude_cli: bool = False
    model: str = DEFAULT_MODEL
    dry_run: bool = False
    cluster: bool = False
    artifacts: bool = False
    artifacts_views: tuple[str, ...] = ()


class _UsageError(Exception):
    """Argv could not be parsed. Carries the message to print."""


def _consume_view_names(argv: list[str], start: int) -> tuple[tuple[str, ...], int]:
    """Every token from `start` that is not itself a flag, plus the next index.

    `--artifacts wiki graphml --dry-run` stops at `--dry-run`, mirroring how
    `kb-artifacts`'s own positional args already work (`cli.py`:
    `artifacts.generate(root, only=rest or None)`). An empty result (bare
    `--artifacts`) means "all", same as `only=None`.
    """
    views: list[str] = []
    i = start
    while i < len(argv) and not argv[i].startswith("--"):
        views.append(argv[i])
        i += 1
    return tuple(views), i


#: Flags that take no value and just flip a `bool` field on `Options` — kept as
#: data rather than more `elif` branches so `_parse` stays under the repo's
#: cyclomatic-complexity gate as flags are added.
_BOOL_FLAGS = {
    "--allow-parallel-claude-cli": "allow_parallel_claude_cli",
    "--dry-run": "dry_run",
    "--cluster": "cluster",
}


def _parse(repo_root: Path, argv: list[str]) -> Options:
    target = repo_root / DEFAULT_TARGET
    out = repo_root / DEFAULT_OUT
    token_budget: int | None = None
    max_concurrency: int | None = None
    model = DEFAULT_MODEL
    bool_fields = dict.fromkeys(_BOOL_FLAGS.values(), False)
    artifacts_requested = False
    artifacts_views: tuple[str, ...] = ()

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _BOOL_FLAGS:
            bool_fields[_BOOL_FLAGS[a]] = True
            i += 1
        elif a == "--out" and i + 1 < len(argv):
            out = repo_root / argv[i + 1]
            i += 2
        elif a == "--token-budget" and i + 1 < len(argv):
            token_budget = _parse_positive_int("--token-budget", argv[i + 1])
            i += 2
        elif a == "--max-concurrency" and i + 1 < len(argv):
            max_concurrency = _parse_positive_int("--max-concurrency", argv[i + 1])
            i += 2
        elif a == "--model" and i + 1 < len(argv):
            model = argv[i + 1]
            i += 2
        elif a == "--target" and i + 1 < len(argv):
            target = repo_root / argv[i + 1]
            i += 2
        elif a == "--artifacts":
            artifacts_requested = True
            artifacts_views, i = _consume_view_names(argv, i + 1)
        else:
            raise _UsageError(f"unrecognised argument: {a!r}")

    if bool_fields["cluster"] and artifacts_requested:
        raise _UsageError("pass at most one of --cluster / --artifacts")

    return Options(
        target=target,
        out=out,
        token_budget=token_budget,
        max_concurrency=max_concurrency,
        model=model,
        artifacts=artifacts_requested,
        artifacts_views=artifacts_views,
        **bool_fields,
    )


def _parse_positive_int(flag: str, raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise _UsageError(f"{flag} must be an integer (got {raw!r})") from exc
    if value <= 0:
        raise _UsageError(f"{flag} must be > 0 (got {value})")
    return value


def resolve_argv(exe: str, opts: Options) -> list[str]:
    """The graphify `extract` invocation this module runs.

    Used by both the dry-run preview and the real invocation, so they can
    never drift apart.
    """
    argv = [
        exe,
        "extract",
        str(opts.target),
        "--mode",
        "deep",
        "--backend",
        "claude-cli",
        "--out",
        str(opts.out),
    ]
    if opts.token_budget is not None:
        argv += ["--token-budget", str(opts.token_budget)]
    if opts.max_concurrency is not None:
        argv += ["--max-concurrency", str(opts.max_concurrency)]
    return argv


def env_overlay(opts: Options) -> dict[str, str]:
    """The variables THIS module adds — the safe, printable subset.

    See the module docstring's dry-run section. Never the full subprocess env.
    """
    overlay = {_MODEL_ENV: opts.model}
    if opts.allow_parallel_claude_cli:
        overlay[_PARALLEL_ENV] = "1"
    return overlay


def resolve_env(opts: Options) -> dict[str, str]:
    """The full environment the real subprocess runs under.

    `clean_env()` (every non-Claude backend trigger and mise's secret blob
    stripped) plus this module's overlay. Never printed in full — see
    `env_overlay`.
    """
    return clean_env(env_overlay(opts))


def _refuse_out(repo_root: Path, opts: Options) -> str | None:
    """`None` if `--out` is safe; otherwise the refusal message.

    Two distinct unsafe shapes, both checked against the RESOLVED (symlink-
    normalised) path so a relative detour cannot slip past a string
    comparison:

    1. `out == repo_root` — graphify would write `<repo_root>/graphify-out/`,
       which IS the aggregate graph `kb-build` owns. That is the class of
       defect this task exists to never cause.
    2. `out` inside `opts.target` (the pinned clone) — writing into a
       gitignored, re-cloneable checkout is the same class of defect #420
       fixed for a stray marker file: the next `mise run kb-build` re-clones
       over it with no warning that anything was lost.
    """
    out = opts.out.resolve()
    root = repo_root.resolve()
    if out == root:
        return (
            f"[graphify-native-extract] refusing --out {opts.out} — it resolves to the "
            f"repo root ({root}), which would write {_GRAPHIFY_OUT_NAME}/ there and collide "
            "with the aggregate graph `mise run kb-build` owns. Pick a directory outside "
            "the repo root, or omit --out to use the default "
            f"({DEFAULT_OUT})."
        )
    target = opts.target.resolve()
    if out == target or target in out.parents:
        return (
            f"[graphify-native-extract] refusing --out {opts.out} — it resolves inside "
            f"the pinned clone ({target}), which is gitignored and re-cloned on every "
            "`mise run kb-build`. Pick a directory outside sources/graphify, or omit "
            f"--out to use the default ({DEFAULT_OUT})."
        )
    return None


def resolve_cluster_argv(exe: str, opts: Options) -> list[str]:
    """The graphify `cluster-only` invocation `--cluster` runs.

    `cluster-only <path>` takes the SAME output-directory shape `extract --out`
    wrote to — its own default `--graph` is `<path>/graphify-out/graph.json`
    (confirmed against the installed `graphify --help`, not assumed) — so this
    passes `opts.out` unchanged, never `opts.out / "graphify-out"`.

    No `--backend`/`--model` flag, ever: the deterministic hub labeller is
    what runs when no backend is named AND the environment carries no
    backend-selecting key, which `clean_env()` already guarantees (mirrors
    `graphify_ops.label()`'s own default path — see `resolve_cluster_env`).
    """
    return [exe, "cluster-only", str(opts.out)]


def resolve_cluster_env(opts: Options) -> dict[str, str]:
    """The environment `--cluster` runs under: bare `clean_env()`.

    Deliberately NOT `resolve_env(opts)` — that adds `GRAPHIFY_CLAUDE_CLI_MODEL`
    (and, opted in, `_PARALLEL`), which would be inert here (no `--backend` is
    ever passed to `cluster-only` from this module) but would misleadingly
    suggest an LLM labelling backend is in play. `opts` is accepted for
    signature symmetry with `resolve_env` even though it is currently unused.
    """
    del opts
    return clean_env()


def _cluster_graph_json(opts: Options) -> Path:
    """Where `cluster-only` expects to find an existing `graph.json`."""
    return opts.out / _GRAPHIFY_OUT_NAME / "graph.json"


def _refuse_cluster_input(opts: Options) -> str | None:
    """`None` if `--out` already holds a `graph.json` to work with.

    Otherwise the refusal message. Shared by BOTH `--cluster` and
    `--artifacts` (see `_dispatch_artifacts`) — `cluster-only` and every
    artifact generator are rerun-only verbs that have nothing to do over an
    output tree extraction never wrote to. Refusing (rather than letting
    graphify's own error surface, or silently no-op) keeps this in the same
    shape as `_refuse_target`: a run that never asked the question is not a
    pass.
    """
    graph_json = _cluster_graph_json(opts)
    if not graph_json.is_file():
        return (
            f"[graphify-native-extract] refusing — {graph_json} does not exist. "
            "Run `mise run kb-graphify-native-extract` (with neither --cluster nor "
            f"--artifacts) first to produce it, or point --out at an existing "
            "extraction tree."
        )
    return None


def _print_cluster_dry_run(exe: str, opts: Options) -> None:
    argv = resolve_cluster_argv(exe, opts)
    print("[graphify-native-extract] DRY RUN (--cluster) — nothing was invoked")
    print(f"  $ {' '.join(argv)}")
    print(
        "  environment: bare clean_env() — no --backend is passed, so this always runs "
        "graphify's deterministic, LLM-free hub labeller (no LLM, no API)."
    )


def _run_cluster(repo_root: Path, exe: str, opts: Options) -> int:
    # Same rationale as `_run_real`: checked here, the one place graphify
    # actually runs, never on the dry-run path.
    assert_pinned_graphify(repo_root)
    argv = resolve_cluster_argv(exe, opts)
    env = resolve_cluster_env(opts)
    print(f"[graphify-native-extract] $ {' '.join(argv)}")
    result = subprocess.run([*argv], cwd=repo_root, env=env, check=False)
    return result.returncode


def _refuse_target(opts: Options) -> str | None:
    """`None` if the target exists; otherwise the refusal message.

    The pinned clone is gitignored (`sources/graphify.manifest` re-clones it
    at build time) and may simply be absent on a fresh checkout. Absence is
    not a silent success and not a crash — it is a refusal that names the
    remedy, per this repo's standing rule that a run which never asked the
    question is not a pass.
    """
    if not opts.target.is_dir():
        return (
            f"[graphify-native-extract] refusing — target {opts.target} does not exist. "
            "Run `mise run kb-build` to re-clone the pinned sources first."
        )
    return None


def _print_dry_run(exe: str, opts: Options) -> None:
    argv = resolve_argv(exe, opts)
    overlay = env_overlay(opts)
    print("[graphify-native-extract] DRY RUN — nothing was invoked")
    print(f"  $ {' '.join(argv)}")
    print("  environment overlay (added on top of clean_env(); nothing else is printed —")
    print("  see the module docstring's dry-run section for why):")
    for key, value in sorted(overlay.items()):
        print(f"    {key}={value}")
    if not opts.allow_parallel_claude_cli:
        print(
            "  NOTE: GRAPHIFY_CLAUDE_CLI_PARALLEL is NOT set — claude-cli runs serially "
            "(graphify's own default). graphify's clamp comment (llm.py:2569/:3301) cites "
            "session-state conflict, but every claude-cli invocation passes "
            "--no-session-persistence, and a real 19-chunk run at concurrency 4 with the "
            "clamp lifted completed cleanly (see the module docstring). Pass "
            "--allow-parallel-claude-cli to lift it — an informed opt-in, not a workaround "
            "for a live risk."
        )


def _run_real(repo_root: Path, exe: str, opts: Options) -> int:
    # Checked here, not in the dry-run path: this is the one place graphify
    # actually runs, and a stale binary rewriting output under an unverified
    # version is the exact hazard `assert_pinned_graphify` exists to refuse
    # before any writer touches disk.
    assert_pinned_graphify(repo_root)
    argv = resolve_argv(exe, opts)
    env = resolve_env(opts)
    print(f"[graphify-native-extract] $ {' '.join(argv)}")
    # No capture_output: stdio is inherited so a human watching sees graphify's
    # own progress output live, exactly like `merge_chunk`'s subprocess call.
    # No timeout: the caller bounds this (long-running-command-hangs.md).
    result = subprocess.run([*argv], cwd=repo_root, env=env, check=False)
    return result.returncode


def _dispatch_cluster(repo_root: Path, exe: str, opts: Options) -> int:
    """`--cluster`: standalone, never touches `opts.target`.

    A missing pinned clone must not block re-clustering an output tree that
    already exists — this checks only `_refuse_cluster_input`.
    """
    cluster_problem = _refuse_cluster_input(opts)
    if cluster_problem:
        events.fail("graphify_native_extract.missing_cluster_input", cluster_problem)
        return Rc.NOT_RUN
    if opts.dry_run:
        _print_cluster_dry_run(exe, opts)
        return Rc.OK
    return _run_cluster(repo_root, exe, opts)


def _dispatch_extract(repo_root: Path, exe: str, opts: Options) -> int:
    """The default mode: extract from `opts.target` into `opts.out`."""
    target_problem = _refuse_target(opts)
    if target_problem:
        events.fail("graphify_native_extract.missing_target", target_problem)
        return Rc.NOT_RUN
    if opts.dry_run:
        _print_dry_run(exe, opts)
        return Rc.OK
    return _run_real(repo_root, exe, opts)


def _refuse_unknown_views(views: tuple[str, ...]) -> str | None:
    """`None` if every requested view name is one `artifacts.generate` knows.

    Without this, `--artifacts wiky` (a typo) matches ZERO entries in
    `artifacts._ARTIFACTS` — `generate`'s own `only=` filter silently narrows
    to an empty selection and reports "0 artifacts generated" / "all
    artifacts generated" as a CLEAN rc=0 run. That is exactly the "partial
    success reported as success" failure mode this repo cares most about, so
    an unrecognised name is refused here, before it ever reaches `generate`
    as a silent no-op.
    """
    if not views:
        return None
    from kb_setup import artifacts

    known = artifacts.known_views()
    unknown = [v for v in views if v not in known]
    if not unknown:
        return None
    return (
        f"[graphify-native-extract] refusing --artifacts {' '.join(unknown)} — "
        f"not a known view (known: {', '.join(known)})"
    )


def _print_artifacts_dry_run(repo_root: Path, opts: Options) -> None:
    views = ", ".join(opts.artifacts_views) if opts.artifacts_views else "all (default registry)"
    print("[graphify-native-extract] DRY RUN (--artifacts) — nothing was invoked")
    print(f"  views: {views}")
    print(f"  graph_root (data + cwd, never the aggregate graphify-out/): {opts.out}")
    print(f"  repo_root (graphify exe + venv anchor only): {repo_root}")
    print("  via kb_setup.artifacts.generate(repo_root, only=<views>, graph_root=<out>)")


def _run_artifacts(repo_root: Path, opts: Options) -> int:
    # Same rationale as `_run_real`/`_run_cluster`: checked here, the one place
    # graphify actually runs.
    assert_pinned_graphify(repo_root)
    from kb_setup import artifacts

    only = list(opts.artifacts_views) or None
    return artifacts.generate(repo_root, only=only, graph_root=opts.out)


def _dispatch_artifacts(repo_root: Path, opts: Options) -> int:
    """`--artifacts`: standalone, never touches `opts.target`.

    Reuses `kb_setup.artifacts.generate` rather than a second generator
    registry — see that function's `graph_root` docstring for why `repo_root`
    (never `opts.out`) still anchors `graphify_exe`/`ensure_runtime_deps`.
    """
    view_problem = _refuse_unknown_views(opts.artifacts_views)
    if view_problem:
        events.fail("graphify_native_extract.unknown_artifact_view", view_problem)
        return Rc.BAD_REQUEST
    artifacts_problem = _refuse_cluster_input(opts)
    if artifacts_problem:
        events.fail("graphify_native_extract.missing_artifacts_input", artifacts_problem)
        return Rc.NOT_RUN
    if opts.dry_run:
        _print_artifacts_dry_run(repo_root, opts)
        return Rc.OK
    return _run_artifacts(repo_root, opts)


def native_extract_main(repo_root: Path, argv: list[str]) -> int:
    """`uv run kb-setup graphify-native-extract [-- <flags>]`."""
    try:
        opts = _parse(repo_root, argv)
    except _UsageError as exc:
        print(
            "[graphify-native-extract] "
            f"{exc} — usage: kb-setup graphify-native-extract [--out DIR] "
            "[--target DIR] [--token-budget N] [--max-concurrency N] [--model NAME] "
            "[--allow-parallel-claude-cli] [--cluster] "
            "[--artifacts [VIEW...]] [--dry-run]"
        )
        return Rc.BAD_REQUEST

    out_problem = _refuse_out(repo_root, opts)
    if out_problem:
        events.fail("graphify_native_extract.unsafe_out", out_problem)
        return Rc.BAD_REQUEST

    exe = graphify_exe(repo_root)
    if opts.cluster:
        return _dispatch_cluster(repo_root, exe, opts)
    if opts.artifacts:
        return _dispatch_artifacts(repo_root, opts)
    return _dispatch_extract(repo_root, exe, opts)
