"""kb-setup CLI — build / update the knowledge graph.

Thin dispatch; logic lives in kb_setup.graph. Invoked by the mise tasks
`kb-build` and `kb-update` (run from the repo root).
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_setup import __version__

_ASSEMBLE_MIN_ARGS = 2  # <name> + at least one <chunk.json>


def main(argv: list[str] | None = None) -> int:
    """Dispatch a kb-setup subcommand; returns the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path.cwd()

    if not args:
        print(
            "kb-setup: build | update <name> | prose | query <question> [--prose] | "
            "merge <chunk> | label | "
            "transcribe <audio> | artifacts | currency [check|run|stamp] | "
            "brain [record|reflect|audit] | md-budget | goal-check <path|--text ...> | "
            "goal-outcome <pair> --result R [--turns N] [--note ...] | "
            "cc | cc-doctor | eval [--live] [--slow] | "
            "ensure-deps | version"
        )
        return 0

    cmd, rest = args[0], args[1:]
    if cmd in {"-V", "--version", "version"}:
        print(f"kb-setup {__version__}")
        return 0
    if cmd == "build":
        from kb_setup import graph

        graph.build(repo_root)
        return 0
    if cmd == "update":
        from kb_setup import graph

        if not rest:  # update ALL github-repo sources
            graph.update_all(repo_root)
        else:
            graph.update(repo_root, rest[0])
        return 0
    if cmd == "prose":
        from kb_setup import prose

        prose.derive_for(repo_root)
        return 0
    if cmd == "query":
        from kb_setup import graphify_ops

        return graphify_ops.query(repo_root, rest)
    if cmd == "artifacts":
        from kb_setup import artifacts

        return artifacts.generate(repo_root, only=rest or None)
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
    return _dispatch_ops(repo_root, cmd, rest)


def _dispatch_ops(repo_root: Path, cmd: str, rest: list[str]) -> int:
    """Dispatch the operational subcommands (hooks, brain, ship/land, currency, chunks)."""
    if cmd == "hookguard":
        from kb_setup import hook_guard

        return hook_guard.run()
    if cmd == "brain":
        from kb_setup import brain

        return brain.dispatch(repo_root, rest)
    if cmd == "no-lint-skip":
        from kb_setup import lint_checks

        return lint_checks.no_lint_skip(repo_root)
    if cmd == "md-budget":
        from kb_setup import md_budget

        return md_budget.md_budget_main(repo_root)
    if cmd == "goal-check":
        from kb_setup import goal

        return goal.main(rest, repo_root)
    if cmd == "goal-outcome":
        from kb_setup import goal

        return goal.outcome_main(rest, repo_root)
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
    if cmd == "manifest-add":
        return _manifest_add(repo_root, rest)
    if cmd == "assemble":
        return _assemble(repo_root, rest)
    if cmd == "validate-chunks":
        return _validate_chunks(rest)
    if cmd == "fetch":
        return _fetch(repo_root, rest)

    print(
        f"kb-setup: unknown command {cmd!r} "
        "(build | update [name] | prose | query <question> [--prose] | "
        "merge <chunk> [root] | label [--missing-only] "
        "[--claude-cli] | transcribe <audio> | artifacts [fmt...] | "
        "currency [check|run|stamp] [--tool T --json --no-write] | manifest-add <url> "
        "[--ref R --kind K --name N --comment C --force] | assemble <name> <chunk...> | "
        "brain [query|record|reflect|audit] | md-budget | cc | cc-doctor | "
        "eval [--live] [--slow] | "
        "validate-chunks <chunk...> | ship [--title T] | land <PR#> | ensure-deps | version)",
        file=sys.stderr,
    )
    return 2


def _review_receipt(repo_root: Path, rest: list[str]) -> int:
    """Write the `kb-review` skill's receipt for HEAD; `ship` refuses to push without it."""
    from kb_setup import review

    sha = _opt(rest, "--sha") or review.head_sha(repo_root)
    if not sha:
        print("review-receipt: could not read HEAD", file=sys.stderr)
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

    counts: dict[str, int] = {}
    for flag in ("--findings", "--blocking"):
        raw = _opt(rest, flag) or "0"
        if not raw.lstrip("-").isdigit() or int(raw) < 0:
            print(f"review-receipt: {flag} must be a non-negative integer", file=sys.stderr)
            return 2
        counts[flag] = int(raw)

    path = review.write_receipt(
        repo_root,
        review.Receipt(
            sha=sha,
            fixed_point=_opt(rest, "--fixed-point") or "main",
            lanes_ran=tuple(lanes),
            lanes_skipped=tuple(skipped),
            findings=counts["--findings"],
            blocking=counts["--blocking"],
        ),
    )
    ok, summary = review.receipt_state(repo_root, sha)
    print(f"review-receipt: wrote {path.relative_to(repo_root)}")
    print(f"review-receipt: {'OK' if ok else 'REJECTED'} — {summary}")
    # A receipt this module just wrote and its own gate rejects is a defect in
    # one of the two; surface it now rather than at ship time.
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
    """Dispatch `kb-setup currency {check|run|stamp}` (see kb_setup.currency.run)."""
    from kb_setup.currency import run as currency_run

    only = _opt(rest, "--tool", "") or ""
    # Skip the VALUES of value-taking flags when looking for the positional mode,
    # or `currency --tool graphify` reads "graphify" as the mode and errors out.
    value_flags = {"--tool", "--version", "--source-ref"}
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
        f"kb-setup currency: unknown mode {mode!r} (check | run | apply | daily | stamp)",
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
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
