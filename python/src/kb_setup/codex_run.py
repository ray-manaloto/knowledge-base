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
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from kb_setup.result import Rc

#: uv keeps its cache outside the workspace, and `workspace-write` makes only
#: the workspace writable. Without this the lane cannot open the cache and dies
#: rc 2 — armed on codex-cli 0.152.0 against `mise run kb-context`.
_UV_CACHE = Path.home() / "Library" / "Caches"

_RC_TIMED_OUT = 124
"""What `--timeout` returns when the watchdog fired, GNU `timeout`'s own code.

Not an :class:`Rc` member on purpose. `Rc` names THIS repo's vocabulary, and 124
is a borrowed one — `long-running-command-hangs.md` rule 3a already cites it as
*"`timeout`'s rc 124 on expiry"*, so a lane bounded here reports the same integer
a `timeout(1)`-bounded one would, and a caller comparing the two is not reading
two conventions. It is deliberately NOT `Rc.NOT_RUN`: the lane DID run, it just
never finished, and collapsing those is the exact "we did not look" confusion
`Rc.NOT_RUN`'s own docstring exists to prevent.
"""

_KILL_GRACE = 5.0
"""Seconds between the watchdog's SIGTERM and its SIGKILL.

TERM first so codex can flush the session file `mise run kb-session-search`
reads — the whole reason `--ephemeral` is refused. KILL after, because a
watchdog that can be ignored is not a bound.
"""


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


def _terminate_group(proc: subprocess.Popen[str], *, own_group: bool) -> None:
    """End the lane's whole process GROUP, TERM then KILL.

    The group, not the PID, because codex spawns child tool-call workers that
    outlive a bare `kill <pid>` and go on holding the terminal — the lesson
    `fable-orchestrator`'s own watchdog records as *kill the group, never just
    the PID*.

    🔴 **The group is only ours to kill when we CREATED it**, so `own_group` is
    passed in by the caller rather than inferred. `_spawn` sets
    `start_new_session` exactly when a timeout is set, and the two must stay
    coupled: signalling a group we did not create would take down this process,
    its mise task and its shell.

    🔴 **THE PGID IS `proc.pid`, AND IT IS NOT LOOKED UP.** This function used to
    start with `os.getpgid(proc.pid)` and treat a `ProcessLookupError` as "already
    reaped, nothing to do". On macOS that error also fires for a **zombie** —
    measured: a child that has exited but not been waited on returns `pgid == pid`
    while alive and `ProcessLookupError` the moment it exits, before any `wait()`.
    So the leader exiting first (exactly the case a watchdog exists for) made this
    function return having signalled NOTHING, leaving the rest of the group alive
    and the caller blocked on a pipe those survivors still held.

    No lookup is needed: `start_new_session=True` makes the child its own session
    and group leader, so its pgid IS its pid, by definition and while it is a
    zombie too.
    """
    pgid = proc.pid

    def _signal(sig: int) -> None:
        # A reaped process frees its PID for reuse, and `pgid` is that PID — so
        # once `wait()` has returned, signalling could reach a stranger. The
        # watchdog can fire in exactly that window, between `wait()` returning
        # and `cancel()` landing.
        if proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            if own_group:
                os.killpg(pgid, sig)
            else:
                proc.send_signal(sig)

    _signal(signal.SIGTERM)
    # Poll rather than sleep the grace out, so SIGKILL can never reach a PID the
    # OS has since handed to someone else.
    #
    # 🔴 **WAIT ON THE GROUP, NOT THE LEADER.** This loop returned as soon as
    # `proc.poll()` went non-None — i.e. the moment codex itself exited — which
    # skipped the SIGKILL entirely while a descendant that ignored SIGTERM was
    # still running and still holding stdout. Measured by the cold lane: with
    # `timeout=0.3` and a tee, a TERM-ignoring descendant kept the call blocked
    # past six seconds, while the TERM-responsive control returned 124 in 0.31s.
    # A leader-only check turns the hard bound this whole function exists to
    # provide back into an unbounded wait.
    deadline = time.monotonic() + _KILL_GRACE
    while time.monotonic() < deadline:
        if _group_gone(pgid, own_group=own_group, proc=proc):
            return
        time.sleep(0.1)
    _signal(signal.SIGKILL)


def _group_gone(pgid: int, *, own_group: bool, proc: subprocess.Popen[str]) -> bool:
    """Has every process in the lane's group exited — not merely its leader?

    `killpg(pgid, 0)` sends no signal and raises `ProcessLookupError` only when
    the group has no members left, which is the question `proc.poll()` cannot
    answer: poll speaks for one PID.

    When the group is NOT ours it is the caller's own, which always has members
    (us), so asking about it would never terminate and would end in a SIGKILL to
    this process. There the leader IS the whole lane, so poll is both correct and
    the only safe probe.
    """
    if not own_group:
        return proc.poll() is not None
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        # A member survives that we may not signal; treat it as still present
        # rather than reporting a clean exit we did not observe.
        return False
    return False


def _tee(stream: IO[str], path: Path) -> None:
    """Copy the lane's output to `path` AND to ours, line by line.

    The stream handed in carries stdout AND stderr merged (see `_spawn`), because
    codex puts incremental progress on stderr and only the final message on
    stdout. "The lane's output" therefore means both, deliberately.

    Line-buffered rather than captured-then-written because an Astra review runs
    for tens of minutes: a caller polling a background run needs to see progress,
    and a report that only exists after a clean exit is exactly the artifact #678
    was filed about — the flag was accepted, the run returned rc 0, and no file
    existed.

    The parent directory is created first. `.agent/kb/review/reports/` is
    gitignored, so a fresh clone does not have it, and losing a 40-minute review
    to a missing directory is the same class of loss with a longer fuse.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in stream:
            sys.stdout.write(line)
            sys.stdout.flush()
            handle.write(line)
            handle.flush()


def _spawn(
    argv: list[str],
    *,
    prompt: str | None = None,
    timeout: float | None = None,
    tee: Path | None = None,
) -> int:
    """Run the lane and return ITS exit code — bounded, and optionally teed.

    Two behaviours ride on `timeout` being set, and neither happens without it,
    so an unbounded call is byte-for-byte the `subprocess.run` this replaced:

    - the child gets its OWN session, which is what makes a group-kill safe;
    - a watchdog thread ends that group at the deadline and the call returns
      `_RC_TIMED_OUT` instead of codex's own code.

    A new session also means Ctrl-C no longer reaches the child, which is why it
    is not the default: an interactive lane should stay interruptible.

    `prompt` (stdin) and `tee` (the merged output stream) never co-occur — `exec` takes its prompt
    on stdin and writes its own `-o` file, while `review` takes its instructions
    through `-c developer_instructions=` and has no `-o` to write. Feeding a pipe
    while draining another needs a select loop nothing here calls for, so the
    combination raises rather than deadlocking on a caller's first large prompt.
    """
    if prompt is not None and tee is not None:
        raise ValueError("_spawn cannot write stdin and tee the output stream in one call")

    # argv is built by this module from validated flags and never goes through a
    # shell, so nothing here interpolates caller text into a command line.
    bounded = timeout is not None
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE if prompt is not None else None,
        stdout=subprocess.PIPE if tee is not None else None,
        # 🔴 **THE PROGRESS IS ON STDERR, so the tee must take both streams.**
        # codex's human renderer sends every agent message through `eprintln!`
        # (`exec/src/event_processor_with_human_output.rs:99-105`) and only
        # prints the FINAL message to stdout, at shutdown (`:399-408`). A
        # stdout-only tee therefore writes nothing at all until the run ends —
        # which made this module's own promise of incremental evidence false,
        # and a lane killed at its bound left an EMPTY report.
        #
        # Observed before it was understood: during a 1143s review the tee file
        # sat at 0 bytes while the run's combined output passed 500 KB. The
        # per-line flush was working; there was simply nothing on stdout to
        # flush.
        #
        # The cost is real and accepted: hook warnings and MCP errors now land
        # in the report too. A noisy report that exists beats a clean one that
        # is empty exactly when the lane died early.
        stderr=subprocess.STDOUT if tee is not None else None,
        text=True,
        env=os.environ.copy(),
        start_new_session=bounded,
    )

    timed_out = threading.Event()

    def _fire() -> None:
        timed_out.set()
        _terminate_group(proc, own_group=bounded)

    watchdog = threading.Timer(timeout, _fire) if timeout is not None else None
    if watchdog is not None:
        watchdog.daemon = True
        watchdog.start()
    try:
        if tee is not None and proc.stdout is not None:
            _tee(proc.stdout, tee)
        if prompt is not None and proc.stdin is not None:
            # A child that exited before reading the prompt leaves us writing to
            # a closed pipe. That is the CHILD's story to tell, not an error of
            # ours: raising here replaced its real exit code with a wrapper
            # traceback (rc 1), and on a timeout it also swallowed the 124 and
            # the SUBSET warning. Measured against a 1 MB prompt and an
            # early-exiting child: this wrapper returned 1 where the
            # `subprocess.run` it replaced returned the child's own 7.
            with contextlib.suppress(BrokenPipeError):
                proc.stdin.write(prompt)
                proc.stdin.close()
        rc = proc.wait()
    except BaseException:
        # The child is already running, so an exception here (a `_tee` that
        # cannot open its destination is the real case) must not leave it
        # orphaned. Kill and REAP before the `finally` cancels its watchdog —
        # cancelling first would remove the only thing that would ever have
        # bounded it.
        _terminate_group(proc, own_group=bounded)
        proc.wait()
        raise
    finally:
        if watchdog is not None:
            watchdog.cancel()

    if timed_out.is_set():
        print(
            f"kb-codex: the lane exceeded --timeout {timeout:g}s and was ended. "
            "Its output up to that point is above (and in --output, if given); "
            "it reviewed a SUBSET, which is not a clean pass.",
            file=sys.stderr,
        )
        return _RC_TIMED_OUT
    return rc


@dataclass(frozen=True)
class ReviewSpec:
    """What a `codex review` lane needs, as one object.

    A dataclass for the same reason `LaneSpec` is one: #678's fix takes this
    builder from four arguments to six and trips the same complexity gate, and
    raising the gate to admit a wider signature is the trade
    `use-tool-builtins.md` asks us not to make.
    """

    base: str
    title: str | None = None
    commit: str | None = None
    instructions: str | None = None
    model: str | None = None
    effort: str | None = None
    sandbox: str | None = None


def _review_argv(spec: ReviewSpec) -> list[str]:
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

    🔴 **MODEL AND EFFORT TRAVEL AS `-c`, NEVER AS A FLAG — #678.** This builder
    emitted neither until 2026-09-09, so `--model`/`--effort` were accepted by the
    parser and dropped on the floor: the lane ran at whatever `codex review`
    defaulted to while `--print-argv` was the only way to notice. An accepted flag
    that does nothing is worse than a rejected one.

    There IS no flag to forward. Read from the pinned source at `sources/codex/`
    (`rust-v0.153.4`, the version we run): `ReviewArgs`
    (`codex-rs/exec/src/cli.rs:270-303`) declares exactly `--uncommitted`,
    `--base`, `--commit`, `--title` and `[PROMPT]` — no `-m`, no `-o`, no
    `--sandbox`. Live-confirmed against `codex review --help` on 0.153.4, which
    lists only those plus `-c`, `--strict-config`, `--enable`, `--disable`.
    `-m/--model` is real on `codex exec` and on the NESTED `codex exec review`,
    which is a different surface than the one this builder uses.

    So the two keys go through `-c`, and both are plain top-level `ConfigToml`
    fields, i.e. legal `-c key=value` overrides:

    - **`review_model`** (`config/src/config_toml.rs:157`, and documented at
      `developers.openai.com/codex/config-reference.md`) is what
      `start_review_conversation` reads FIRST — `config.review_model` else the
      current session's own slug (`core/src/tasks/review.rs:123-127`). It is the
      only way in: `override_review_model` has no CLI flag wired to it anywhere,
      so there is no `--review-model` to prefer over this.
    - **`model_reasoning_effort`** (`:360`) is untouched by that function, which
      clones the whole effective config for the reviewer child — so the
      top-level override is inherited rather than overwritten.

    `review_model` is TOML-quoted and `model_reasoning_effort` is not, which looks
    inconsistent and is deliberate: the effort key is emitted bare by
    `_codex_argv` too, and ONE key spelled two ways across the two builders is the
    drift worth avoiding. A model slug is caller text, so it is quoted rather than
    left to `-c`'s parse-then-fall-back-to-literal path.

    🔴 **`--sandbox` ALSO travels as `-c`, and it is the ONLY way to sandbox a
    review.** `codex review` has no `-s/--sandbox` (same `ReviewArgs`), and a
    `.codex/agents/*.toml` role file is REFUSED one by design — `apply_role`
    copies seven fields into `AgentRoleOverrides` and `sandbox_mode` is not among
    them (`core/src/agent/role.rs:80-89`; the test feeding `hostile-role.toml`
    asserts *"role must not control sandbox_mode"*, `role_tests.rs:351-480`).

    A CLI `-c` is a different layer and is NOT filtered: it lands in
    `ConfigLayerSource::SessionFlags`, precedence **30**, above the user config's
    **20** (`config/src/config_layer_source.rs:38-47`) — so it overrides a
    `sandbox_mode` set in `$CODEX_HOME/config.toml`. The reviewer sub-agent then
    inherits it, because `start_review_conversation` CLONES the whole effective
    config (`core/src/tasks/review.rs:106`) and modifies only `web_search_mode`,
    two features, `base_instructions`, `approval_policy` and `model` — never the
    sandbox.

    Without this, a review here runs at whatever the user config says, which on
    the machine this was written on is `danger-full-access` — the thing
    `do-not.md` #13 forbids. `approval_policy` is deliberately NOT forwarded: the
    sub-agent's is hard-set to `Never` at `review.rs:121`, so passing one would
    be a flag that does nothing, which is the defect #678 was about.
    """
    argv = ["codex", "review", "--base", spec.base]
    if spec.title and spec.commit:
        argv += ["--title", spec.title]
    if spec.sandbox:
        argv += ["-c", f"sandbox_mode={_toml_str(spec.sandbox)}"]
    if spec.model:
        argv += ["-c", f"review_model={_toml_str(spec.model)}"]
    if spec.effort:
        argv += ["-c", f"model_reasoning_effort={spec.effort}"]
    if spec.instructions:
        argv += ["-c", f"developer_instructions={_toml_str(spec.instructions)}"]
    return argv


def _run_review(args: argparse.Namespace) -> int:
    """Spawn `codex review`. Returns codex's own exit code.

    `--output` is honoured HERE rather than as an argv flag, because `codex
    review` has none — see `_review_argv` for the source citation. So this path
    tees the lane's output to the file itself, and that is a real difference from
    `exec` mode worth stating: `-o` is codex's own `--output-last-message` and
    holds only the final message, while this holds everything the lane printed.
    For a review report that is the better artifact, but it is not the same
    artifact, and a caller diffing the two should know why.
    """
    # Instructions come from the positional prompt or stdin, and are delivered
    # through `-c developer_instructions=` rather than as `[PROMPT]`, which the
    # target flags conflict with. See `_review_argv`.
    instructions = args.prompt
    if instructions is None and not sys.stdin.isatty():
        instructions = sys.stdin.read()

    built = _review_argv(
        ReviewSpec(
            base=args.base,
            title=args.title,
            commit=None,
            instructions=instructions,
            model=args.model,
            effort=args.effort,
            sandbox=args.sandbox,
        )
    )

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

    return _spawn(
        built,
        timeout=args.timeout,
        tee=Path(args.output) if args.output else None,
    )


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
    parser.add_argument(
        "--sandbox",
        default=None,
        help="override the sandbox outright. exec: `--sandbox <v>`. --review: sent "
        'as `-c sandbox_mode="<v>"`, the only channel that exists, and the only way '
        "a review is not run at whatever $CODEX_HOME/config.toml says",
    )
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
    parser.add_argument(
        "--model",
        default=None,
        help="model override, e.g. gpt-5.6-sol or gpt-6-astra; in --review mode "
        "this is sent as `-c review_model=`, the only channel that exists (#678)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="persist the lane's output to this file. exec: codex's own `-o` "
        "last-message file. --review: this task tees the lane's merged stdout+stderr, "
        "since `codex review` "
        "has no -o (#678)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="seconds before the lane's process GROUP is ended and rc 124 is "
        "returned; unbounded when omitted. Must be <= the mise task's own timeout "
        "or mise kills the lane first",
    )
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

    return _spawn(built, prompt=prompt, timeout=args.timeout)
