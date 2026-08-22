# Copyright (c) 2026 Raymond Manaloto
"""Report this session's CONTEXT-WINDOW occupancy, which nothing else surfaces.

Why this module exists
----------------------
`clear-prep`'s headline trigger is *"as soon as the session's context passes
~20% of the model's window"*. That condition was **unobservable from inside a
session**, so it could never fire, and flipping `disable-model-invocation` did
not help: the flag governs whether the model MAY invoke the skill, not whether
it can tell the condition is met.

The only context-ish signal a session receives is the harness reminder
``<total_tokens>N tokens left</total_tokens>``. That is a **spend budget**, not
window occupancy, and the two disagree wildly. Measured on transcript
``672f23a4`` (2026-08-21):

===========================================  ==================
real peak occupancy                          475,917 (**47.6%** of a 1M window)
what the reminder said at that moment        14,981,005 / 15,000,000 left (**99.9% remaining**)
===========================================  ==================

A model reading "99.9% of your budget remains" reasonably concludes there is
plenty of room, while sitting at more than twice the trigger threshold. That is
the whole defect, and it is this repo's own *"a gate that never asked the
question"* class: a trigger phrased against a quantity nothing reports.

The SDK does expose the right pair — ``totalTokens`` is "the session's current
context usage" and ``maxTokens`` "the window that usage is measured against"
(`sources/agent-harness-docs/docs/claude-code/agent-sdk__typescript.md:761`) —
but Claude Code surfaces that to a **custom status line**, i.e. to the human,
not into the conversation. So a session has to go and read it.

What it reads, and why that is sound
------------------------------------
Occupancy is recomputed from the transcript's own last assistant turn:

    input_tokens + cache_read_input_tokens + cache_creation_input_tokens

That sum is what the model was actually charged to see on that turn, which IS
the context it held. It is a measurement of a past turn, so it is a **floor** on
current occupancy, never a ceiling — stated in the output rather than left for a
reader to assume.

It deliberately does NOT read the `total_tokens` reminder. Reporting a budget
under a heading that says "context" is how this defect was born.

Main thread only — AND WHY THIS MODULE NO LONGER CLAIMS TO DETECT IT
-------------------------------------------------------------------
Ray, 2026-08-21: this must *"only trigger on the main session thread/agent — not
on subtasks or spawned agents or agent teams"*. A subagent offering to prepare a
handoff is offering to end a session it does not own. That requirement stands;
what changed on 2026-08-22 is the claim that THIS MODULE could enforce it.

**A session id cannot make the distinction** — measured on a live fork, whose
`CLAUDE_CODE_SESSION_ID` is identical to the main session's, which reads the same
transcript, and for which id comparison, transcript ownership and `isSidechain`
all say "main". That part was true and remains true.

The module then reached for two environment markers, and **both readings were
wrong**. It declined to report on the main thread 100% of the time, from the day
it was written until 2026-08-22 — a check that could only refuse, which is
`probes-need-a-control-arm.md`'s subject in its purest form. The docstring here
even named the hole: the negative case (a main session carrying neither marker)
was *"asserted, not measured"*. It is now measured, and it is false.

What the two markers actually mean, per the vendor's own documentation, which
**this repo had already ingested** — so `research-doc-sources.md` step 0 would
have answered it before a line was written:

* `CLAUDE_CODE_CHILD_SESSION` is *"Set to 1 in subprocesses Claude Code spawns
  via the Bash, PowerShell, and Monitor tools, hook commands, and status line
  commands"*
  (`sources/agent-harness-docs/docs/claude-code/env-vars.md:208`). It marks a
  **subprocess**, not an agent. Every Bash tool call carries it — from the main
  thread exactly as much as from a subagent — so it holds ZERO information about
  which agent issued the call, and `kb-setup context` runs in precisely such a
  subprocess.
* `CLAUDE_CODE_FORK_SUBAGENT` is a **capability flag the operator sets to enable
  forking**, not a marker the harness sets to announce being a fork:
  *"Forked subagents can now be enabled on external builds by setting
  CLAUDE_CODE_FORK_SUBAGENT=1"* and *"SDK and `claude -p`:
  CLAUDE_CODE_FORK_SUBAGENT=1 now works in non-interactive sessions"*
  (`changelog.md:2211` and `:2060`). Where forking is enabled it is set for
  everyone, main thread included.

Measured on the main thread, 2026-08-22, with the sanctioned presence form:
both markers PRESENT; control `HOME` PRESENT and a bogus name ABSENT, so the
probe discriminates. The original "positive case observed on a live fork" was
never evidence — the markers are present in both arms, so observing them in one
arm could not distinguish anything. **A probe run in only one arm cannot
discriminate no matter how carefully it is run.**

So the environment does not expose the answer, and this module stops pretending
otherwise: it MEASURES, and the main-thread requirement lives where it is
actually enforceable — in `clear-prep`'s own instruction to the model, which is
where it always really lived. A subagent that runs this now gets a number
instead of a refusal; that is not a regression from working enforcement, it is
the removal of a placebo that only ever silenced the caller it was written for.

If a genuine discriminator ever appears, it belongs here and the guard comes
back with an arm on BOTH directions — a fork and a main session — because that
is the arm this module skipped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kb_setup import session_select

#: Occupancy at or above which `clear-prep` should be offered — Ray's standing
#: "request /clear-prep at 20% context", now expressed against the quantity that
#: is actually measured rather than one nothing reports.
THRESHOLD_PCT = 20.0

#: Context windows by model family, keyed by a substring of the transcript's
#: recorded model id. Only used when the transcript names a model it recognises;
#: an unknown model reports UNKNOWN rather than guessing, because a wrong window
#: turns a percentage into confident fiction.
_WINDOWS: tuple[tuple[str, int], ...] = (
    ("fable", 1_000_000),
    ("mythos", 1_000_000),
    ("opus-5", 1_000_000),
    ("opus", 200_000),
    ("sonnet-5", 1_000_000),
    ("sonnet", 200_000),
    ("haiku", 200_000),
)


#: Environment variables once mistaken for "this is NOT the main session thread".
#:
#: RETIRED 2026-08-22. Kept as a NAMED, EMPTY tuple rather than deleted so the
#: refutation has an anchor: this is the extension point a future discriminator
#: would use, and an empty one says "we looked and there is nothing" where a
#: deleted symbol would say nothing at all.
#:
#: Neither of the two it held is an agent-identity marker — see the module
#: docstring for the citations. `CLAUDE_CODE_CHILD_SESSION` marks any subprocess
#: Claude Code spawns (every Bash tool call, main thread included) and
#: `CLAUDE_CODE_FORK_SUBAGENT` is an operator-set capability flag. Putting either
#: back reinstates a check that can only refuse.
CHILD_MARKERS: tuple[str, ...] = ()


def child_marker(env: dict[str, str] | None = None) -> str | None:
    """The first genuine child/subagent marker present, or None.

    Always None while :data:`CHILD_MARKERS` is empty, which it is: no environment
    variable known to this repo distinguishes a subagent's Bash call from the
    main thread's. Retained as the seam a real discriminator would fill.

    A marker set to an empty string is treated as ABSENT: an exported-but-empty
    variable is how a shell says "unset" in practice, and treating it as present
    would silence the main session in exactly the environments that export
    placeholders.
    """
    import os

    source = os.environ if env is None else env
    for name in CHILD_MARKERS:
        if str(source.get(name) or "").strip():
            return name
    return None


@dataclass(frozen=True)
class Usage:
    """One transcript's measured context occupancy."""

    transcript: Path
    model: str
    occupancy: int
    window: int | None
    turns: int

    @property
    def pct(self) -> float | None:
        """Occupancy as a percentage of the window, or None if it is unknown."""
        if not self.window:
            return None
        return self.occupancy / self.window * 100.0

    @property
    def over_threshold(self) -> bool:
        """Whether occupancy has reached :data:`THRESHOLD_PCT`.

        False when the window is unknown — an unmeasured session must not
        assert it is over any line.
        """
        pct = self.pct
        return pct is not None and pct >= THRESHOLD_PCT


def window_for(model: str) -> int | None:
    """The context window for ``model``, or None when it is not recognised."""
    lowered = model.lower()
    for token, size in _WINDOWS:
        if token in lowered:
            return size
    return None


def _last_usage(path: Path) -> tuple[int, str, int]:
    """Return (occupancy, model, turns_with_usage) for a transcript."""
    occupancy = 0
    model = ""
    turns = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError, TypeError:
                continue
            # A bare `null`, number or string is VALID JSON, so it decodes without
            # raising and the except above never sees it — then `.get` raises
            # AttributeError and the whole measurement dies on one odd line.
            # The except clause guards the parse; this guards the parse's RESULT.
            if not isinstance(record, dict):
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            # THE SAME LESSON AS THE COMMENT ABOVE, one step further in. Guarding
            # the parse and the parse's RESULT still left the FIELDS unguarded:
            # `{"input_tokens": "unknown"}` is a dict, so it reaches here, and
            # `int()` then raises ValueError out of the whole function — killing
            # the measurement of every later well-formed turn over one odd line.
            # Reproduced: a good/bad/good transcript raised instead of returning
            # the good turns. (Cold lane, `e2b697c9`.)
            try:
                total = (
                    int(usage.get("input_tokens") or 0)
                    + int(usage.get("cache_read_input_tokens") or 0)
                    + int(usage.get("cache_creation_input_tokens") or 0)
                )
            except ValueError, TypeError:
                continue
            if total <= 0:
                continue
            turns += 1
            occupancy = total
            if isinstance(message.get("model"), str):
                model = message["model"]
    return occupancy, model, turns


def own_transcript(repo_root: Path, env: dict[str, str] | None = None) -> Path | None:
    """THIS session's transcript, by id — or the newest by mtime as a fallback.

    A transcript is named `<CLAUDE_CODE_SESSION_ID>.jsonl`, so the id names the
    file exactly. Measured: `CLAUDE_CODE_SESSION_ID` is 36 chars, uuid-shaped,
    and `<that id>.jsonl` exists in the transcript directory.

    Newest-by-mtime was the ONLY rule until the cold lane on `870c020c` found
    that it answers a different question — "which transcript was written most
    recently" — and those diverge the moment a SECOND session runs against this
    repo. Whichever session wrote last wins, so a concurrent Claude Code or
    Codex session hands `mise run kb-context` the other session's occupancy, and
    `clear-prep` treats that number as authoritative for its 20% trigger.

    **A fork does not create that divergence, and the module docstring above is
    why**: a fork's `CLAUDE_CODE_SESSION_ID` is *identical* to its parent's and
    it writes the same transcript. That measurement is what makes this change
    safe rather than behavioural — for the fork case, id-selection and
    mtime-selection resolve to the same file.

    mtime survives as the fallback for the case the id cannot serve: no
    `CLAUDE_CODE_SESSION_ID` in the environment (a hook shell, a test), or an id
    naming a file that does not exist yet. That direction fails the safe way —
    back to exactly the behaviour that shipped before.
    """
    directory = session_select.transcript_dir(repo_root, env)
    if not directory.is_dir():
        return None
    import os

    source = os.environ if env is None else env
    session_id = str(source.get("CLAUDE_CODE_SESSION_ID") or "").strip()
    if session_id:
        own = directory / f"{session_id}.jsonl"
        if own.is_file():
            return own
    found = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0] if found else None


def measure(repo_root: Path, env: dict[str, str] | None = None) -> Usage | None:
    """Measure the newest transcript's context occupancy, or None if there is none."""
    path = own_transcript(repo_root, env)
    if path is None:
        return None
    occupancy, model, turns = _last_usage(path)
    if not turns:
        return None
    return Usage(
        transcript=path,
        model=model or "unknown",
        occupancy=occupancy,
        window=window_for(model),
        turns=turns,
    )


def render(usage: Usage | None) -> tuple[str, int]:
    """Render the report and the exit code.

    Exit codes are a SIGNAL, not a gate — nothing should fail a build on them:

    * ``0``  measured, below the threshold
    * ``10`` measured, AT OR ABOVE the threshold — time to offer `/clear-prep`
    * ``127`` could not measure (no transcript, no usage, unknown window)

    127 rather than 0 because "could not ask" must never render as "you are
    fine" — the distinction this repo keeps in every other check.
    """
    if usage is None:
        return (
            (
                "context: NOT MEASURABLE — no transcript with usage for this directory.\n"
                "  This is not 'you have room'; it is 'the question was not asked'."
            ),
            127,
        )
    lines = [
        f"transcript : {usage.transcript.name}",
        f"model      : {usage.model}",
        f"occupancy  : {usage.occupancy:,} tokens (last of {usage.turns} measured turns)",
    ]
    if usage.window is None:
        lines.append(
            f"window     : UNKNOWN for model {usage.model!r} — percentage NOT computed.\n"
            "             A guessed window turns a percentage into confident fiction."
        )
        return "\n".join(lines), 127
    pct = usage.pct or 0.0
    lines.append(f"window     : {usage.window:,} tokens")
    lines.append(f"USED       : {pct:.1f}%  (threshold {THRESHOLD_PCT:.0f}%)")
    lines.append(
        "note       : measured from the LAST completed turn, so it is a FLOOR on\n"
        "             current occupancy, never a ceiling."
    )
    if usage.over_threshold:
        lines.append("")
        lines.append(
            "=> OVER THRESHOLD. Offer /clear-prep now: ask the user via AskUserQuestion\n"
            "   whether to prepare the handoff. Do not clear anything yourself."
        )
        return "\n".join(lines), 10
    lines.append("")
    lines.append("=> under threshold; carry on.")
    return "\n".join(lines), 0


def main(argv: list[str], repo_root: Path) -> int:
    """`uv run kb-setup context` — report context occupancy for this session."""
    if argv and argv[0] in {"-h", "--help"}:
        print("usage: kb-setup context")
        print()
        print(__doc__ or "")
        return 0
    if argv:
        print(f"context: unknown argument(s): {' '.join(argv)}")
        return 2
    marker = child_marker()
    if marker is not None:
        print(
            f"context: NOT THE MAIN THREAD ({marker} is set) — declining to report.\n"
            "  /clear-prep belongs to the session that owns the round. A subagent\n"
            "  offering to prepare a handoff is offering to end a session it does\n"
            "  not own, and its context is not the main thread's context anyway."
        )
        return 3
    report, code = render(measure(repo_root))
    print(report)
    return code
