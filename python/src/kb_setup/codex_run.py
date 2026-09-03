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


def _review_argv(*, base: str, title: str | None) -> list[str]:
    """Build the argv for `codex review`, which is NOT `codex exec` with a flag.

    Measured on 0.152.1 from `codex review --help`: it accepts `-c key=value`,
    `--strict-config`, `--enable`/`--disable`, `--uncommitted`, `--base`,
    `--commit`, `--title`, and a `[PROMPT]` that may be `-` for stdin.

    🔴 **It accepts NONE of the four flags `_codex_argv` exists to enforce** —
    no `--sandbox`, no `--add-dir`, no `--dangerously-bypass-hook-trust`. So the
    lane-flag argument does not carry over, and building this by adding a flag
    to the exec argv would produce a command codex rejects. Different surface,
    different builder.

    What DOES carry over is the reason `kb-codex` exists at all: routing through
    mise gets the pinned binary rather than whatever a shell's PATH baked in.

    `--base` is the review's fixed point, matching `kb-review`'s own default of
    `origin/main` — the ref `ship`/`land` gate against, not local `main`, which
    can have drifted along this branch's ancestry and would silently shrink the
    reviewed diff.

    **OBSERVED 2026-09-03:** `codex review --base <BRANCH> … -` is rejected with
    `error: the argument '--base <BRANCH>' cannot be used with '[PROMPT]'`. So
    this builder passes no prompt when a base is given, and `_run_review` tells
    the caller on stderr that the METHOD paragraph was not delivered — a review
    that silently used codex's default instructions, reported as though it had
    ours, is worse than one that never ran.

    ⚠️ **DO NOT READ THAT AS "custom instructions are impossible with a base."**
    That is one error string, not a reading of the CLI's argument definitions,
    and drawing a design conclusion from it is the exact failure #672 exists to
    stop. `codex review` also takes `-c key=value` config overrides and
    `--enable <FEATURE>`, either of which may carry review instructions by
    another route; `--commit <SHA>` may pair with a prompt where `--base` does
    not. **The pinned source is local** — `sources/codex/` at
    `rust-v0.152.1`, the exact version we run — so the clap definitions settle
    this and the help text does not. A lane is reading them; until it reports,
    the constraint above is an OBSERVATION about one invocation, not a statement
    about what the subcommand can do.
    """
    argv = ["codex", "review", "--base", base]
    if title:
        argv += ["--title", title]
    return argv


def _run_review(args: argparse.Namespace) -> int:
    """Spawn `codex review`, prompt on stdin. Returns codex's own exit code."""
    built = _review_argv(base=args.base, title=args.title)

    if args.print_argv:
        print(" ".join(built))
        return Rc.OK

    if shutil.which("codex") is None:
        print("kb-codex: `codex` is not installed or not on PATH.", file=sys.stderr)
        return Rc.NOT_RUN

    # `--base` forbids a prompt, so the METHOD paragraph cannot be delivered on
    # this path. SAY SO rather than letting the caller believe it was passed —
    # a review that silently used codex's default instructions, reported as
    # though it had ours, is worse than one that never ran.
    print(
        f"kb-codex --review: reviewing against {args.base} with CODEX'S OWN review\n"
        "instructions. `--base` and a custom prompt are mutually exclusive on\n"
        "codex 0.152.1, so no METHOD paragraph was delivered — findings that need\n"
        "a check to be RUN rather than read may not appear (#672 U2).",
        file=sys.stderr,
    )
    completed = subprocess.run(built, check=False, env=os.environ.copy())
    return completed.returncode


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
    parser.add_argument(
        "--review",
        action="store_true",
        help="run `codex review` against --base instead of `codex exec` (#672 U2)",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="review fixed point; origin/main, not local main, matching kb-review",
    )
    parser.add_argument("--title", default=None, help="title shown in the review summary")
    args = parser.parse_args(argv)

    if args.review:
        return _run_review(args)

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
