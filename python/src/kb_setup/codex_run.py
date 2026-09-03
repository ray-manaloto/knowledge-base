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
from dataclasses import dataclass
from pathlib import Path

from kb_setup.result import Rc

#: uv keeps its cache outside the workspace, and `workspace-write` makes only
#: the workspace writable. Without this the lane cannot open the cache and dies
#: rc 2 — armed on codex-cli 0.152.0 against `mise run kb-context`.
_UV_CACHE = Path.home() / "Library" / "Caches"


@dataclass(frozen=True)
class LaneSpec:
    """What an exec lane needs, as one object.

    A dataclass rather than six keyword arguments because the argument count
    tripped the complexity gate, and raising the gate to admit a wider signature
    is the trade `use-tool-builtins.md` asks us not to make.
    """

    write: bool = False
    network: bool = False
    effort: str = "xhigh"
    sandbox_override: str | None = None
    model: str | None = None
    output: str | None = None


def _codex_argv(spec: LaneSpec) -> list[str]:
    """Build the argv. Separated from `run` so a test can assert it without spawning.

    `model` and `output` exist because THE GUARD BROKE AN EXISTING WORKFLOW
    without them. `codex review` (P1) found that `kb-codex-advisor`'s own
    documented command — `codex exec --model gpt-5.6-sol … -o <file> -` — is
    denied the moment `codex_lane` is wired in, and this task offered no
    equivalent, so the advisor became unrunnable. That is this repo's own
    recorded lesson: *a guard whose redirect target cannot perform the redirected
    action is not enforcement, it is an outage.*
    """
    sandbox = spec.sandbox_override or ("workspace-write" if spec.write else "read-only")
    argv = ["codex", "exec", "--sandbox", sandbox]
    if spec.model:
        argv += ["--model", spec.model]
    if spec.output:
        argv += ["-o", spec.output]

    # `--add-dir` only means anything under a write sandbox; adding it to a
    # read-only lane would be noise that reads as though it granted something.
    if sandbox == "workspace-write":
        argv += ["--add-dir", str(_UV_CACHE)]
        if spec.network:
            argv += ["-c", "sandbox_workspace_write.network_access=true"]

    argv += ["-c", f"model_reasoning_effort={spec.effort}"]
    # Trust is per-hook-HASH and editing a hook re-breaks it, so this is not
    # one-time setup — it is required on every invocation, forever.
    argv.append("--dangerously-bypass-hook-trust")
    argv.append("-")  # prompt on stdin
    return argv


def _toml_str(value: str) -> str:
    """Quote a value as a TOML basic string, for `-c key=value`.

    `-c` parses the value portion as TOML and falls back to a literal string if
    that fails (`utils/cli/src/config_override.rs:47-83`). A METHOD paragraph
    contains newlines and quotes, so it is quoted explicitly rather than left to
    that fallback — an unescaped `"` would otherwise truncate the instructions
    silently, which is the failure mode this whole channel exists to avoid.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _review_argv(
    *, base: str, title: str | None, commit: str | None, instructions: str | None
) -> list[str]:
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

    **THE TARGET FLAGS AND `[PROMPT]` ARE MUTUALLY EXCLUSIVE — AND THAT DOES NOT
    COST US THE METHOD PARAGRAPH.** Both halves were settled from the pinned
    source at `sources/codex/` (`rust-v0.152.1`, the version we run), not from
    help text, after an earlier version of this docstring asserted the first half
    from a single error string.

    `codex-rs/exec/src/cli.rs:272-305`: `--uncommitted`, `--base`, `--commit` and
    `[PROMPT]` each declare `conflicts_with` the other three — no two may
    co-occur, confirmed by a six-pairing runtime matrix all returning rc 2. They
    are variants of ONE `ReviewTarget` enum
    (`codex-rs/protocol/src/protocol.rs:3310-3344`), so the prompt IS how you
    choose a scope, never supplemental instructions alongside one.

    🔴 **`-c developer_instructions=…` IS THE OTHER CHANNEL, and it is global —
    flattened into `MultitoolCli`, so it is NOT in the conflict set**
    (`codex-rs/cli/src/main.rs:99-129`). Traced through the source to the
    reviewer child: it is a real `ConfigToml` key
    (`config/src/config_toml.rs:223-228`); review clones the effective config and
    replaces only `base_instructions` with its rubric, leaving
    `developer_instructions` intact (`core/src/tasks/review.rs:99-127`); the
    spawned child copies it into session state and renders it as a developer
    message (`core/src/session/mod.rs:718-734,3808-3817`).

    So this builder selects the diff with `--base` AND delivers our METHOD
    paragraph with `-c`. #672 U2's stated risk — that a native subcommand's
    prompt is not ours to shape — is resolved rather than accepted.

    `--title` is deliberately NOT passed with a base: it declares
    `requires = "commit"`, and `build_review_request` reads it only in the commit
    branch (`exec/src/lib.rs:2132-2149`), so a title beside `--base` parses and is
    then silently IGNORED. This code passed one for an entire review run before
    the source said so.
    """
    argv = ["codex", "review", "--base", base]
    if title and commit:
        argv += ["--title", title]
    if instructions:
        argv += ["-c", f"developer_instructions={_toml_str(instructions)}"]
    return argv


def _run_review(args: argparse.Namespace) -> int:
    """Spawn `codex review`, prompt on stdin. Returns codex's own exit code."""
    # Instructions come from the positional prompt or stdin, and are delivered
    # through `-c developer_instructions=` rather than as `[PROMPT]`, which the
    # target flags conflict with. See `_review_argv`.
    instructions = args.prompt
    if instructions is None and not sys.stdin.isatty():
        instructions = sys.stdin.read()

    built = _review_argv(base=args.base, title=args.title, commit=None, instructions=instructions)

    if args.print_argv:
        print(" ".join(built))
        return Rc.OK

    if shutil.which("codex") is None:
        print("kb-codex: `codex` is not installed or not on PATH.", file=sys.stderr)
        return Rc.NOT_RUN

    if instructions and instructions.strip():
        print(
            f"kb-codex --review: reviewing against {args.base}, with our instructions\n"
            "delivered as `developer_instructions`. Codex's own review rubric still\n"
            "applies as base_instructions; ours is additive.",
            file=sys.stderr,
        )
    else:
        # A review with no METHOD paragraph is the #672 U2 risk. It is allowed —
        # codex's own rubric is not nothing — but never silently.
        print(
            f"kb-codex --review: reviewing against {args.base} with CODEX'S OWN review\n"
            "instructions ONLY. No METHOD paragraph was supplied, so findings that need\n"
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
    parser.add_argument("--title", default=None, help="review title; needs --commit to apply")
    parser.add_argument("--model", default=None, help="model override, e.g. gpt-5.6-sol")
    parser.add_argument("--output", default=None, help="write the transcript to this file (-o)")
    args = parser.parse_args(argv)

    if args.review:
        return _run_review(args)

    # `--network` without `--write` is not a refusal but it IS a correction:
    # `sandbox_workspace_write.network_access` is a write-sandbox key and does
    # nothing under read-only, so silently honouring it would hand back a lane
    # that reports a network outage the caller then debugs.
    write = args.write or args.network

    built = _codex_argv(
        LaneSpec(
            write=write,
            network=args.network,
            effort=args.effort,
            sandbox_override=args.sandbox,
            model=args.model,
            output=args.output,
        )
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
