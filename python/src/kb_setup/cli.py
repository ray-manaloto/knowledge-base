"""kb-setup CLI — build / update the knowledge graph.

Thin dispatch; logic lives in kb_setup.graph. Invoked by the mise tasks
`kb-build` and `kb-update` (run from the repo root).
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_setup import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path.cwd()

    if not args:
        print("kb-setup: build | update <name> | version")
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
    if cmd == "ensure-deps":
        from kb_setup.graphify_env import ensure_runtime_deps

        got = ensure_runtime_deps(repo_root)
        print(f"[deps] {'installed ' + ', '.join(got) if got else 'all output deps present'}")
        return 0

    print(
        f"kb-setup: unknown command {cmd!r} "
        "(build | update [name] | artifacts [fmt...] | ensure-deps | version)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
