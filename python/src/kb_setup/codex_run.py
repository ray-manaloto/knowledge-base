# Copyright (c) 2026 Raymond Manaloto
"""Run a codex lane with the flags a lane cannot be right without.

`codex_lane` is the guard that stops a raw `codex exec`; this is what it
redirects to. The split is deliberate: the guard is stateless and imported by
`hook_guard` on every Bash call, while this module spawns a process.

**Every flag here is load-bearing and none is a preference.** The provenance for
each is in `codex_lane`'s docstring and `ai-cli-invocation.md`; the short form:

- `--add-dir <uv cache>` or every uv-backed gate exits rc 2 looking like a gate
  failure;
- `--dangerously-bypass-hook-trust` or this repo's hooks are skipped SILENTLY —
  trust is keyed to each hook's hash and this repo has 0 trusted
  `post_tool_use` entries (measured 2026-09-03);
- `-` so the prompt arrives on stdin rather than through ARG_MAX;
- network egress OFF unless asked, because `workspace-write` blocks it
  separately from the write sandbox and the resulting `Could not resolve host`
  reads exactly like a transient.

`--ephemeral` is deliberately NOT passed: a lane that persists nothing cannot be
reviewed afterwards, and `mise run kb-session-search` reads `~/.codex/sessions/`.

Invoked through mise (`mise run kb-codex`), so the lane gets the PINNED codex
rather than whatever the calling shell's PATH baked in — a live skew of 0.152.1
vs 0.152.0 was measured on this machine the day this module was written.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from kb_setup.result import Rc

#: uv keeps its cache outside the workspace, and `workspace-write` makes only
#: the workspace writable. Without this the lane cannot open the cache and dies
#: rc 2 — armed on codex-cli 0.152.0 against `mise run kb-context`.
_UV_CACHE = Path.home() / "Library" / "Caches"


def _codex_argv(
    *, write: bool, network: bool, effort: str, sandbox_override: str | None
) -> list[str]:
    """Build the argv. Separated from `run` so a test can assert it without spawning."""
    sandbox = sandbox_override or ("workspace-write" if write else "read-only")
    argv = ["codex", "exec", "--sandbox", sandbox]

    # `--add-dir` only means anything under a write sandbox; adding it to a
    # read-only lane would be noise that reads as though it granted something.
    if sandbox == "workspace-write":
        argv += ["--add-dir", str(_UV_CACHE)]
        if network:
            argv += ["-c", "sandbox_workspace_write.network_access=true"]

    argv += ["-c", f"model_reasoning_effort={effort}"]
    # Trust is per-hook-HASH and editing a hook re-breaks it, so this is not
    # one-time setup — it is required on every invocation, forever.
    argv.append("--dangerously-bypass-hook-trust")
    argv.append("-")  # prompt on stdin
    return argv


def run(argv: list[str] | None = None) -> int:
    """Parse the task's flags, build the argv, and spawn the lane.

    Returns codex's own exit code so a caller reads the LANE's result rather
    than this wrapper's — the whole point of `verify-before-advancing.md`'s
    "read the real rc". `--print-argv` returns `Rc.OK` having spawned nothing,
    and a missing binary or an empty prompt returns `Rc.NOT_RUN` rather than a
    failure code, because "it never ran" is not "it ran and failed".
    """
    parser = argparse.ArgumentParser(
        prog="kb-codex",
        description="Run a codex lane with this repo's mandatory flags.",
    )
    parser.add_argument("prompt", nargs="?", help="the prompt; omitted reads stdin")
    parser.add_argument(
        "--write",
        action="store_true",
        help="workspace-write sandbox (default: read-only analysis)",
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="allow network egress; implies --write, since the flag is a write-sandbox key",
    )
    parser.add_argument("--effort", default="xhigh", help="model_reasoning_effort (default: xhigh)")
    parser.add_argument("--sandbox", default=None, help="override the sandbox outright")
    parser.add_argument(
        "--print-argv",
        action="store_true",
        help="print the argv that WOULD run and exit; spawns nothing",
    )
    args = parser.parse_args(argv)

    # `--network` without `--write` is not a refusal but it IS a correction:
    # `sandbox_workspace_write.network_access` is a write-sandbox key and does
    # nothing under read-only, so silently honouring it would hand back a lane
    # that reports a network outage the caller then debugs.
    write = args.write or args.network

    built = _codex_argv(
        write=write, network=args.network, effort=args.effort, sandbox_override=args.sandbox
    )

    if args.print_argv:
        print(" ".join(built))
        return Rc.OK

    if shutil.which("codex") is None:
        print(
            "kb-codex: `codex` is not installed or not on PATH. "
            "`mise install` pins it as npm:@openai/codex.",
            file=sys.stderr,
        )
        return Rc.NOT_RUN

    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        print("kb-codex: refusing to run with an empty prompt.", file=sys.stderr)
        return Rc.NOT_RUN

    if args.network and not args.write:
        print(
            "kb-codex: --network implies --write (it is a workspace-write key); "
            "running under workspace-write.",
            file=sys.stderr,
        )

    # argv is built by `_codex_argv` from validated flags and never goes through
    # a shell, so nothing here interpolates caller text into a command line.
    completed = subprocess.run(
        built,
        input=prompt,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    return completed.returncode
