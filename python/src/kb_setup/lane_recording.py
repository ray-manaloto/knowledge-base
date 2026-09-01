# Copyright (c) 2026 Raymond Manaloto
"""A lane must leave a session record — `uv run kb-setup lane-recording`.

`codex exec --ephemeral` means *"run without persisting session files to disk"*
(`codex exec --help`, 0.151.0). A lane invoked that way leaves nothing behind, so
`mise run kb-session-search` — and any other review of what the lanes actually
did — is looking at an empty shelf. Control-armed 2026-09-01: with the flag, 0
new files under `~/.codex/sessions`; without it, +1 at ~104 KB.

WHY THIS IS A STATIC CHECK OVER OUR OWN SOURCE, and not a health probe.
Ray's first instinct was to make the tooling refuse to work unless agentsview was
running. Two advisor consults and this repo's own rules point the other way: hk
runs on every commit and `mise run lint` is a ship gate, so a stopped daemon, a
corrupt index, or a cold sync (2m19s measured over 8,829 sessions) would block
every commit *including the one that fixes agentsview*. A gate on mutable
external state is a gate that can take the repo down.

The invariant worth guarding is not "the viewer is up" — it is **"we did not
quietly stop recording"**, and that lives entirely in committed text. No process,
no database, nothing to be down.

WHY NOT A GREP, which is what this replaces. Both files this checks now *discuss*
`--ephemeral` at length, explaining why it is absent. A literal search flags its
own documentation, which is how a gate loses its readers — this repo has the same
false-positive class recorded against three earlier guards. So the walk is
`skill_lint.command_lines` (shell fences only, CommonMark-correct) and the parse
is `check_first.segments` (shlex, so a quoted mention inside `git commit -m` can
never sit at a command position). Neither is re-implemented here.

WHAT IT DOES NOT CLAIM. It sees committed instructions, not runtime. A lane
spawned with an argv assembled somewhere this does not scan is invisible to it,
and an agent that ignores its own instruction file is too. It closes the
regression path — someone re-adding the flag to a canonical pattern — not every
path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kb_setup import check_first, skill_lint
from kb_setup.result import Rc

DEFAULT_GLOBS: tuple[str, ...] = (
    ".claude/agents/*.md",
    ".codex/agents/*.toml",
    ".claude/rules/ai-cli-invocation.md",
)
"""Where a canonical codex invocation is written down.

Deliberately narrow. `.claude/agents/*.md` is the standing lane roster and
`ai-cli-invocation.md` is the rule that documents the patterns — between them
they are where a reintroduction would actually land.

`.codex/agents/*.toml` IS THE MIRROR CODEX ITSELF READS, and leaving it out was
a P1 in cold round 2. The first version scanned only `.claude/**`, so
`.codex/agents/kb-codex-advisor.toml:45` kept instructing
`--ephemeral --sandbox read-only` while the gate reported every file clean —
the flip had not actually reached the lane, and the guard said it had. Those
`.toml` files carry markdown-fenced commands, so the same walker applies.
There is no generator keeping the pair in sync, which is exactly why both
halves must be scanned rather than one trusted to imply the other. A wider glob would pull in
handoffs and reports, which QUOTE old invocations verbatim as history and must
not be rewritten to satisfy a gate (`agent-artifact-conventions.md`: corpus and
report content records what was said, not what is current).
"""

_FLAG = "--ephemeral"
_CODEX = "codex"


@dataclass
class Finding:
    """One instructed codex invocation that would leave no session record."""

    path: str
    line: int
    command: str


@dataclass
class Report:
    """What was examined and what was found — both, because one without the other lies."""

    findings: list[Finding] = field(default_factory=list)
    scanned: list[str] = field(default_factory=list)

    @property
    def rc(self) -> Rc:
        """`NOT_RUN` when nothing was examined — never a pass.

        A glob that matches nothing produces an empty finding list, which is
        byte-identical to a clean run. This repo has measured that exact shape
        as a gate that can only pass: `hk run check --all -S <nonexistent-step>`
        exits 0 and is labelled "passed", which is why a doctor wrapping hk
        steps was rejected. The same trap, refused here.
        """
        if not self.scanned:
            return Rc.NOT_RUN
        return Rc.FINDINGS if self.findings else Rc.OK


def join_continuations(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    r"""Fold backslash-continued shell lines into one logical command.

    THIS IS THE DEFECT THAT MADE THE FIRST VERSION DECORATION, so it is a
    named function rather than three lines inline. The real invocation in
    `.claude/agents/kb-codex-advisor.md` — the primary file this gate exists to
    protect — is written across five continued lines:

        cat prompt.md | codex exec \
          --sandbox read-only \
          --model gpt-5.6-sol \
          ...

    A per-line walk sees `--ephemeral` on a line whose command word is nothing,
    and the segment containing `codex` never contains the flag. Re-adding the
    flag exactly where it used to live was measured NOT CAUGHT (rc 0).

    The three arms that "proved" the gate all mutated the SINGLE-LINE patterns
    in `ai-cli-invocation.md` — a convenient break rather than the realistic
    one. `probes-need-a-control-arm.md` rule 2 is explicit that a mutation must
    be one that could really happen; this is what that costs when ignored.

    The reported line number is the line the command STARTS on, which is where
    a reader should look.

    FRAGMENTS ARE CONCATENATED WITH NO SEPARATOR, because that is what the
    shell does: a backslash-newline pair is DELETED, nothing substituted. Any
    token break comes from real whitespace (the space before the backslash or
    the continuation line's indentation), which is why `check` feeds this RAW
    lines rather than `command_lines`' stripped ones. Joining with `" "` (the
    first shape of this function) invented a boundary, so `--ephem\` + `eral`
    read as two tokens and the flag this gate exists to catch slipped through
    split across a continuation.
    """
    joined: list[tuple[int, str]] = []
    start: int | None = None
    previous: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal start, buffer
        if start is not None and buffer:
            joined.append((start, "".join(buffer)))
        start, buffer = None, []

    for line_no, text in lines:
        # CONTIGUITY IS THE FENCE BOUNDARY. `command_lines` yields a FLAT list
        # with no fence markers, so a continuation at the end of one fence would
        # otherwise merge into the next fence's first command. Cold round 2
        # reproduced the harm through the real CLI: a fence ending mid-quote
        # with a trailing backslash swallowed a complete
        # `codex exec --ephemeral -"` from a LATER fence into one quoted shlex
        # token, hiding both `codex` and the flag — rc 0, "every instructed
        # codex run persists a session record", with a live violation in a
        # scanned file. Lines inside one fence are consecutive; anything else
        # crossed prose or a boundary and must not be joined.
        if previous is not None and line_no != previous + 1:
            flush()
        if start is None:
            start = line_no
        previous = line_no
        stripped = text.rstrip()
        if stripped.endswith("\\"):
            # Drop ONLY the backslash. The whitespace before it is real shell
            # whitespace and is the sole thing separating `exec \` from the
            # next fragment's first token.
            buffer.append(stripped[:-1])
            continue
        buffer.append(stripped)
        flush()
    # A fence that ended mid-continuation. Keep it rather than dropping it:
    # an unterminated continuation is exactly where something could hide.
    flush()
    return joined


def _is_ephemeral_codex(command: str) -> bool:
    """True when `command` instructs a codex run that persists nothing.

    Judged per SEGMENT, so a pipeline's other commands cannot excuse the codex
    call beside them, and so `echo … | codex exec --ephemeral -` is read as the
    codex invocation it is rather than as an `echo`.

    WITHIN a segment the test is "does a `codex` token appear anywhere", not
    "is `codex` the command word". A command word alone missed
    `mise exec -- codex exec --ephemeral` — a wrapper form this repo uses
    routinely, since `mise exec --` is how you reach a pinned binary past a
    stale PATH. `env`, `time`, `nohup` and `sudo` are the same shape. Widening
    to any token costs little here because the fence walk has already excluded
    prose, and `shlex` has already collapsed any quoted mention into a single
    token that cannot equal `codex`.
    """
    parsed = check_first.segments(command)
    if parsed is None:
        # shlex could not parse it (an unbalanced quote, a heredoc body). Fall
        # back to the literal pair rather than to silence: a command this cannot
        # tokenise is exactly where a real one could hide.
        return _CODEX in command and _FLAG in command
    for tokens in parsed:
        if not any(Path(tok).name == _CODEX for tok in tokens):
            continue
        # Match the flag NAME, split at `=`. `--ephemeral=true` is the same
        # flag; matching the raw token missed that on a sibling guard this week.
        if any(tok.split("=", 1)[0] == _FLAG for tok in tokens):
            return True
    return False


def check(root: Path, *, globs: tuple[str, ...] = DEFAULT_GLOBS) -> Report:
    """Scan `globs` under `root` for instructed `codex … --ephemeral` runs."""
    report = Report()
    for path in sorted({p for pattern in globs for p in root.glob(pattern)}):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        report.scanned.append(rel)
        text = path.read_text(encoding="utf-8")
        raw_lines = text.splitlines()
        # `command_lines` decides WHICH lines are instructions, but it strips
        # indentation, and continuation joining is whitespace-sensitive (a
        # backslash-newline is deleted, so only real whitespace separates
        # tokens). Re-read each selected line raw so `join_continuations`
        # sees the whitespace the shell would.
        lines = [(no, raw_lines[no - 1]) for no, _ in skill_lint.command_lines(text)]
        for line_no, command in join_continuations(lines):
            if _is_ephemeral_codex(command):
                report.findings.append(Finding(path=rel, line=line_no, command=command))
    return report


def main(argv: list[str], repo_root: Path) -> int:
    """Print the report and return its `Rc`."""
    del argv
    report = check(repo_root)

    if not report.scanned:
        print(
            "lane-recording: NOT RUN — no files matched "
            f"{', '.join(DEFAULT_GLOBS)}. A gate that examined nothing is not a pass."
        )
        return Rc.NOT_RUN

    for f in report.findings:
        print(f"{f.path}:{f.line}: codex invoked with {_FLAG} — {f.command}")
    if report.findings:
        print(
            f"\nlane-recording: {len(report.findings)} instructed codex run(s) would persist "
            "NOTHING, so no review of what the lane did is possible afterwards. "
            f"{_FLAG} governs persistence only — dropping it weakens no sandbox or auth "
            "(`codex exec --help`). See .claude/rules/ai-cli-invocation.md."
        )
        return Rc.FINDINGS

    print(
        f"lane-recording: {len(report.scanned)} file(s) checked; "
        "every instructed codex run persists a session record"
    )
    return Rc.OK
