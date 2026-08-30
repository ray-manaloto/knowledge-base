# Copyright (c) 2026 Raymond Manaloto
"""`aggregated-research <verb> [args...]` — the plugin's console-script entry.

Pure argv routing onto `kb_setup.cli.main`, which is where the JSONL event
sink is attached exactly once (`cli.py:33-50`). This module never attaches a
second sink and never dispatches directly to a `research.*` module itself.
"""

from __future__ import annotations

import sys

from kb_setup.result import Rc

#: The verbs this entry point knows. Slice 2+ appends here, not to an
#: if-chain — see `.claude/rules/mise-tasks-only.md` and the spec's ban on
#: pre-building future dispatch.
_VERBS = ("trackers", "links", "packages", "codesearch")

_USAGE = f"aggregated-research <verb> [args...]\n  verbs: {', '.join(_VERBS)}"


def main(argv: list[str] | None = None) -> int:
    """Route `aggregated-research <verb> [args...]` to `kb-setup research-<verb>`.

    Args:
        argv: The verb and its arguments, excluding the program name. `None`
            reads `sys.argv[1:]`.

    Returns:
        0 after printing usage (no verb, or `-h`/`--help`); `Rc.BAD_REQUEST`
        for an unknown verb; otherwise the delegated command's own exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(_USAGE)
        return int(Rc.OK)

    verb, rest = args[0], args[1:]
    if verb not in _VERBS:
        print(f"aggregated-research: unknown verb {verb!r}", file=sys.stderr)
        return int(Rc.BAD_REQUEST)

    from kb_setup import cli

    return cli.main([f"research-{verb}", *rest])
