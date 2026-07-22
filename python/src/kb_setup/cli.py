"""kb-setup CLI — build / update the knowledge graph.

Thin dispatch; logic lives in kb_setup.graph. Invoked by the mise tasks
`kb-build` and `kb-update` (run from the repo root).
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_setup import __version__


def main(argv: list[str] | None = None) -> int:
    """Dispatch a kb-setup subcommand; returns the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path.cwd()

    if not args:
        print(
            "kb-setup: build | update <name> | merge <chunk> | label | "
            "transcribe <audio> | artifacts | ensure-deps | version"
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
    if cmd == "hookguard":
        from kb_setup import hook_guard

        return hook_guard.run()
    if cmd == "ensure-deps":
        from kb_setup.graphify_env import ensure_runtime_deps

        got = ensure_runtime_deps(repo_root)
        print(f"[deps] {'installed ' + ', '.join(got) if got else 'all output deps present'}")
        return 0

    print(
        f"kb-setup: unknown command {cmd!r} "
        "(build | update [name] | merge <chunk> [root] | label [--missing-only] "
        "[--claude-cli] | transcribe <audio> | artifacts [fmt...] | "
        "ensure-deps | version)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
