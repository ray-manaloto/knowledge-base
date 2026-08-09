# Copyright (c) 2026 Raymond Manaloto
"""End-of-session self-reflection: what did this round do BY HAND that is code?

`kb_setup.distill` answers one question — *was a program written twice?* — by
grouping ad-hoc scripts across sessions on their import signature. It is a
frequency miner, and frequency mining structurally cannot see the work this
module looks for:

- a step done by hand **once**, in one session, that a `kb-*` task already owns;
- a directive violated at a *rate* rather than a yes/no;
- a probe that answered without ever asking;
- a run of tasks, skills or library calls that wants a single wrapper.

None of those repeat across sessions in a way an import signature groups, and
the first is the expensive one: `kb-arms` exists precisely so nobody hand-writes
a mutation harness, and distill still reports **149 hand-written harnesses across
21 sessions** because each one is a fresh scratchpad rather than a recurring
import shape.

So this module reads the same transcripts and asks the complementary question:
**what did this session do by hand that already has a home?**

## Reading a report

Every finding is a LEAD, never a verdict, and the command always exits 0. An
un-automated step is a statement about future cost, not a failure — the same
posture `distill` takes and for the same reason: a gate here would turn "you
could have used a task" into a blocked commit, which is a cure worse than the
disease.

**An empty section is the common, correct result** for a session that did
genuinely novel work. That is what makes a non-empty one worth reading.

## Why the rules are DATA

`OWNED`, `DIRECTIVES` and `UNARMED` are tuples of :class:`Rule`, not `if`
branches, so adding a detector is a table row plus a test. That mirrors
`distill.Policy` and `kb_setup.arms`' TOML specs, and it is what lets
`reflect()` stay one loop rather than growing a branch per question.
"""

from __future__ import annotations

import re
import shlex
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from kb_setup import brain
from kb_setup.distill import tool_uses

DEFAULT_SESSION_LIMIT = 1
"""Sessions to scan. ONE by default, unlike `distill`'s 50.

This module asks "what did THIS round do by hand", and a round is one session.
Widening it answers a different question — *is this a habit?* — which is worth
asking deliberately (`-- --sessions N`) rather than by default, because a
per-session count read as a per-round count overstates every rate.
"""

MIN_RUN = 2
"""Consecutive same-kind calls before a run is worth proposing a wrapper for.

Two is deliberate and not a placeholder: a wrapper's whole value is removing a
hand-typed sequence, and a sequence exists at two. Raising it to three would
hide exactly the `lint`-then-`test` pair that is the most common one here.
"""


@dataclass(frozen=True)
class Rule:
    """One thing to look for, and what to do instead.

    `remedy` is not decoration — a finding that names a problem without naming
    its replacement is a complaint, and the reader has to go and find the task
    themselves. Every rule here carries the command it is arguing for.
    """

    id: str
    pattern: re.Pattern[str]
    remedy: str
    why: str
    unless: re.Pattern[str] | None = None
    """An exemption checked against the WHOLE command, not the matched span.

    `piped-rc` needed this and its own control arm is what proved it: the
    negative lookahead inside the pattern can only see bytes AFTER the pipe, so
    `mise run lint > log; echo "rc=$?" | tail -1` — the exact remedy this rule
    argues for — tripped the rule. A detector that flags its own recommendation
    is worse than no detector, because following the advice makes the report
    louder.
    """
    also: re.Pattern[str] | None = None
    """A SECOND requirement, searched independently against the whole command.

    The mirror of `unless`, and it exists for a measured reason rather than for
    symmetry. A rule meaning "A appears, and later so does B" is naturally
    written `A.*?B` under DOTALL — which makes the engine retry the lazy gap out
    to end-of-string from EVERY `A` start position, O(k·n) on a command with
    many `A`s and no `B`. `mutation-harness` was exactly that shape, and a long
    transcript line is all it takes to stall an advisory report (cold lane,
    2026-08-08). Two independent linear searches answer the same question in
    O(n) and cost one field.

    The ORDER of A-then-B is given up by the split, deliberately: a command that
    runs `pytest` before it patches a file is still a hand-rolled harness, so
    ordering was never part of what the rule meant.
    """


@dataclass(frozen=True)
class Finding:
    """One observed instance of a :class:`Rule`, with the bytes that matched."""

    rule: Rule
    session: str
    excerpt: str


@dataclass
class Report:
    """Everything one reflection run observed, grouped by question asked."""

    sessions: tuple[str, ...] = ()
    commands: int = 0
    owned: list[Finding] = field(default_factory=list)
    violations: list[Finding] = field(default_factory=list)
    unarmed: list[Finding] = field(default_factory=list)
    repeats: list[tuple[str, int]] = field(default_factory=list)
    runs: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    graph_skipped: int = 0
    graph_queries: int = 0
    counts: int = 0
    counts_armed: int = 0


def _rule(rid: str, pattern: str, remedy: str, why: str) -> Rule:
    """The four fields EVERY rule has. Guards are attached with `_guard`.

    Split rather than grown to six parameters: `unless` and `also` are each used
    by one rule out of eight, so carrying them through every call site would put
    two `None`s in six rows to spare two rows a wrapper.
    """
    return Rule(id=rid, pattern=re.compile(pattern), remedy=remedy, why=why)


def _guard(rule: Rule, *, unless: str | None = None, also: str | None = None) -> Rule:
    """`rule` with an exemption and/or a second requirement compiled onto it."""
    return replace(
        rule,
        unless=re.compile(unless) if unless else None,
        also=re.compile(also) if also else None,
    )


_GAP = 200
"""Max characters a rule's `A…B` gap may span. NEVER write `.*` in a rule.

An unbounded gap between two required tokens is **quadratic**: the engine
re-expands it from every `A` start position, so a command with many `A`s and no
`B` — the ordinary worst case, not a contrived one — costs O(k·n). `Rule.also`
removes the gap entirely and is the better fix where A-then-B ORDER does not
matter. Where it does, bound the gap: backtracking then costs at most `_GAP`
per start, which is linear in the command length.

Measured 2026-08-09 on a single-line command of k `A` tokens and no `B`
(`uv run python -c`, one process, same machine, back-to-back):

| pattern | k=800 | k=1600 | k=3200 | ratio per doubling |
|---|---|---|---|---|
| `manifest-pin` unbounded | 7.97 ms | 31.40 ms | 129.25 ms | 3.9-4.1x — **O(n^2)** |
| `manifest-pin` bounded | 1.16 ms | 2.34 ms | 4.99 ms | 2.0-2.1x — linear |
| `gate-by-hand` unbounded | 5.76 ms | 23.04 ms | 91.77 ms | 4.0x — **O(n^2)** |
| `gate-by-hand` bounded | 1.23 ms | 2.39 ms | 4.66 ms | 1.9-2.0x — linear |

**2x input for 4x cost is the signature**, and it is what the ratio column is
for: an absolute millisecond figure ages with the machine, a scaling exponent
does not. Both bounded forms were checked to match and reject exactly what the
unbounded ones did on realistic commands before the bound was applied.

**Every figure above is per PATTERN, and the label is load-bearing.** The
`unbounded` rows are the code as it stood BEFORE 2026-08-09; the `bounded` rows
are what ships. Stating that explicitly because the inline comment on
`gate-by-hand` carried the unbounded numbers for two revisions while sitting
beside the bounded pattern, where they read as its cost and said the opposite of
the truth. A cold review caught it by reproducing the pattern from this file's
own constants — the cheapest possible refutation, and one nothing else here
would have run.

**The classification does not depend on the regime**, which is the natural next
doubt and was measured rather than argued. Sweeping `gate-by-hand` over
k=100/200/400/800/1600/3200 (median of 15 reps, one process):

| form | ratio per doubling, across the whole sweep |
|---|---|
| unbounded | 3.56x, 3.74x, 3.81x, 4.10x, 3.89x — quadratic throughout |
| bounded | 2.05x, 2.04x, 2.02x, 2.02x, 2.00x — linear throughout |

So the bound is not merely an optimisation that arrives once `n` exceeds
`_GAP`; the bounded form is linear at every size measured, including the
smallest.

`test_no_rule_carries_an_unbounded_gap` enforces this over EVERY rule, so a new
`.*` cannot be added without the suite going red. That test replaced a
wall-clock assertion which flaked under `-n auto` (73.9 ms against a 50 ms
bound) — a timing proxy cannot survive parallel execution, and the property it
was proxying for is checkable directly.
"""

OWNED: tuple[Rule, ...] = (
    _guard(
        _rule(
            "mutation-harness",
            # A source file being patched. The "...and then something is RUN over
            # it" half lives in `also`, not in a `.*?` gap here: see Rule.also —
            # the spanning form backtracked to end-of-string from every
            # `write_text` in a long command and could stall the report it exists
            # to produce.
            r"(?:read_text|\.replace\(|write_text)",
            "mise run kb-arms -- <spec.toml>",
            "distill's largest group: 149 hand-written harnesses across 21 sessions. "
            "A scratchpad harness loses the __pycache__ mitigation, which can credit "
            "an arm with a death the mutation never caused.",
        ),
        also=r"pytest|subprocess\.run|rc=",
    ),
    _rule(
        "graph-counts",
        r"json\.load\(open\(['\"]graphify-out/graph\.json|graph\.json['\"]\)\)",
        "uv run kb-setup graph-counts",
        "graph.json spells it `links`; a `.get('edges', [])` probe returns 0 on a "
        "perfectly healthy graph.",
    ),
    _rule(
        "manifest-pin",
        # `.{0,_GAP}?` and not `.*?` — see _GAP. Unbounded here was O(n²) on a
        # command with many `git ls-remote --tags` and no `sources/`.
        rf"git ls-remote --tags.{{0,{_GAP}}}?sources/"
        rf"|sed -i.{{0,{_GAP}}}?sources/\S+\.manifest",
        "uv run kb-setup manifest-add / the currency engine's apply",
        "hand-resolving a tag and sed-ing it in skips the v-prefix and "
        "annotated-tag handling the module already carries.",
    ),
    _rule(
        "gate-by-hand",
        # Two gaps. Only the FIRST could ever go quadratic — the blowup factor
        # is the number of START positions for the leading token, and gap 2
        # expands once per start. Both are bounded anyway: the cheap one is not
        # worth reasoning about twice, and an unbounded gap beside a bounded one
        # invites a future edit to "match the style" in the wrong direction.
        # Costs are in `_GAP`, which states them per PATTERN — do not restate a
        # figure here; a number next to a pattern reads as that pattern's cost,
        # and the unbounded form's numbers sat here for two revisions saying
        # exactly the opposite of what the line below them does.
        rf"\buv run (?:ruff|ty|pytest)\b.{{0,{_GAP}}}?&&"
        rf".{{0,{_GAP}}}?\buv run (?:ruff|ty|pytest)\b",
        "mise run kb-gates",
        "kb-gates records each result to .agent/kb/gates/gates-<sha>.json, so a "
        "later claim about them has a surviving artifact.",
    ),
)
"""Work an existing task already owns. The remedy is the point of the row."""

_CMD_POS = r"(?:^|[;&|]\s*|\b(?:if|then|elif|else|do|while|until)\s+)"
"""Where a COMMAND can start: line start, after a separator, or after a keyword.

The keyword arm is the part that had to be added. `[;&|]` alone missed
`if mise run test | head; then …` — a gate inside a conditional, whose exit code
is not merely discarded but is the thing the conditional branches on, so it is
the worst case of the directive rather than an edge one (cold lane, round 2).
"""

_SEG = r"(?:[^|\n;&]|&(?!&))*"
"""Bytes inside ONE simple command — never across `;`, `&&`, `||` or a pipe.

A single `&` IS allowed, and that exception is the whole reason this is not the
obvious `[^|\\n;&]*`: `2>&1` is the most common thing to appear between a gate
and its pipe, so excluding `&` outright would stop `mise run lint 2>&1 | tail`
— the canonical violation — from matching at all. `&(?!&)` keeps the redirect
and still refuses the separator.
"""

_GATE_TASKS = "lint-docs|lint|test|fmt|eval|brain-audit|kb-gates|check"
"""The `mise run` tasks whose exit code is EVIDENCE, so losing it is the defect.

Deliberately a list rather than `mise run \\S+`: most tasks here are reads
(`kb-query`, `kb-session-state`), and piping a read into `head` is a display
bound on output already in hand, not a discarded gate.

A hand-maintained list's failure mode is OMISSION, and it had one on arrival:
`check` (`mise.toml`, `depends = ["lint", "test"]`) is the composite gate, so
`mise run check | tail` discarded two gates' exit codes and tripped nothing
(cold lane, round 1). Longest-first ordering so `lint-docs` is not read as
`lint` followed by a stray `-docs`.
"""

DIRECTIVES: tuple[Rule, ...] = (
    _rule(
        "bare-interpreter",
        r"(?m)(?:^|[;&|]\s*)(?:python3?|node|ruby|perl)\s",
        "uv run python …",
        "A bare interpreter resolves off $PATH, so it silently depends on "
        "whether a venv happens to be active. This repo ran its gates on 3.14.0 "
        "under a 3.14.7 pin for two weeks that way.",
    ),
    _rule(
        "relative-cd",
        # Not just a literal leading `/`. `cd ~`, `cd "$HOME/repo"` and
        # `cd $(git rev-parse --show-toplevel)` all resolve to an ABSOLUTE path
        # after expansion, and flagging them inflated the reported rate with
        # commands that were already compliant. What the directive is about is a
        # target relative to a cwd that persists across Bash calls, and none of
        # those three is one.
        #
        # The exemption names those forms rather than exempting `$` wholesale,
        # which was the first fix and went too far the other way: `REL=sources/x;
        # cd $REL` is the rule's exact hazard and a blanket `$` excused it (cold
        # lane, round 1). A bare `$VAR` therefore FIRES. That costs a false
        # positive on `cd $REPO_ROOT` holding an absolute path — accepted, because
        # a variable's contents cannot be read from the command, so the honest
        # report is "could not be shown absolute" and this rule reports a rate of
        # candidates, not a verdict on each.
        #
        # QUOTING IS NOT DECORATION, and treating a leading quote as skippable
        # was the round-2 defect: what expands depends on WHICH quote (round 2).
        #   `/`     absolute quoted or not      -> ["']? allowed
        #   `~`     expands ONLY unquoted       -> no quote allowed
        #   `$…`    expands unquoted and in ""  -> "? allowed, never '
        # So `cd "~/repo"` and `cd '$HOME/repo'` are RELATIVE paths naming
        # directories literally called `~` and `$HOME`, and both were excused.
        r"(?m)(?:^|[;&|]\s*)cd\s+"
        r"(?!(?:[\"']?/|~|\"?(?:\$\(|\$\{?HOME)))[^\s;&|]+",
        "git -C <path> …, or an absolute path",
        "cwd persists across Bash calls; two relative cds once made "
        "`gh issue view` return a different repository's PR.",
    ),
    _guard(
        _rule(
            "piped-rc",
            # ONLY a gate on the left-hand side. The first draft matched any
            # `| head`/`| tail` and fired 111 times in one session — every
            # display pipe over a log file. A rule at that volume is noise, and
            # noise is what teaches a reader to skip the section that holds the
            # real one. The directive is about losing a GATE's exit code, so the
            # left side must be something whose rc means anything.
            #
            # Three separate precision fixes, all from one cold-lane finding:
            #
            # 1. The gate must sit at a COMMAND POSITION. A bare `\bpytest\b`
            #    matched the word anywhere, so `rg pytest /tmp/log | head` — a
            #    grep FOR the string, whose rc means nothing — was reported as a
            #    lost gate.
            # 2. `mise run` is narrowed to the tasks that ARE gates. `mise run
            #    kb-query -- "…" | head -20` is a browse; its rc is not evidence
            #    and flagging it says the directive applies where it does not.
            # 3. `_SEG` refuses to cross a command separator in BOTH the gap and
            #    the lookahead. The old `[^|\n]*` crossed `;`, which produced a
            #    matched pair of OPPOSITE errors: `mise run lint > log; echo
            #    "rc=$?" | tail` (the remedy) FIRED because the gap ran past the
            #    `;` to the pipe, and `mise run lint | tail; echo "rc=$?"` (the
            #    real violation) was SUPPRESSED because the lookahead ran past
            #    the `;` to an `rc=` that is `tail`'s status, not the gate's.
            rf"(?m){_CMD_POS}"
            rf"(?:mise run (?:{_GATE_TASKS})|hk |pytest|uv run (?:ruff|ty|pytest))"
            rf"{_SEG}\|\s*(?:tail|head)\b(?!{_SEG}\brc=)",
            "mise run kb-check -- <paths>  (or kb-gates for the ship gates)",
            "Bash returns the LAST pipeline command's exit code, so a failed gate reports success.",
        ),
        # `${PIPESTATUS[0]}` is the one form that pipes a gate and STILL reads
        # the gate's own status, so it is compliance rather than a violation.
        # It replaces a `\brc=\$\?` exemption that was checked against the whole
        # command and therefore excused fix 3's false negative all over again —
        # the very defect the tightened lookahead exists to catch.
        #
        # INDEX 0 specifically, not a bare `\bPIPESTATUS\b`. The gate is the
        # left-hand side of the pipe, so index 0 is the only element that holds
        # its status: `mise run lint | tail; echo ${PIPESTATUS[1]}` reads TAIL's
        # again and was excused, and so was any command that merely contained
        # the word — `echo "see PIPESTATUS docs"` bought a full exemption. That
        # is the same whole-command over-reach as the exemption it replaced,
        # reintroduced one commit later (cold lane, round 1).
        #
        # The `$` sigil is REQUIRED, because without it this was still matching
        # a literal substring anywhere in the command: `echo "read PIPESTATUS[0]
        # first"` bought a full exemption while nothing expanded anything. That
        # is the third time this one rule's exemption has been written too wide
        # — `rc=$?`, then bare `PIPESTATUS`, then an unsigiled `PIPESTATUS[0]` —
        # which says the shape is the defect, not the instances: `unless` is
        # searched against the WHOLE command, so it must name a form that only
        # occurs when the thing is actually happening (cold lane, round 2).
        #
        # WHAT REMAINS, stated precisely — the earlier wording ("a false
        # negative on an input nobody has written") was too comfortable, and a
        # cold lane said so. `unless` is now searched only FORWARD of each match
        # (`scan`), so an exemption BEFORE a violation no longer excuses it. Two
        # things still do:
        #
        #   1. `mise run lint | tail; mise run test | tail; echo ${pipestatus[1]}`
        #      — two pipelines, one status read, both excused. Closing this means
        #      parsing the pipeline rather than matching it.
        #   2. the literal text appearing after a violation for some other
        #      reason. Note this is narrower than it sounds: the `$` sigil is
        #      required, so `grep 'pipestatus\[1\]' file.py` does NOT excuse
        #      anything (control-armed), and a form that DOES expand has in fact
        #      printed that pipeline's status.
        #
        # Recorded rather than fixed because this rule is advisory and always
        # exits 0 — it narrows a report's numerator, it gates nothing.
        #
        # THE SPELLING IS `pipestatus[1]`, NOT `PIPESTATUS[0]`, and that is the
        # fourth correction to this one exemption rather than a fifth instance
        # of the same over-reach. `PIPESTATUS` is a **bash** array; this repo's
        # shell is zsh, which spells it lowercase and indexes from 1. Armed both
        # directions in zsh 5.9 (`BASH_VERSION=none`): `${PIPESTATUS[0]}` returns
        # `''` for a FAILING gate and `''` for a PASSING one — it cannot
        # discriminate, so a command writing it captured nothing while buying a
        # full exemption. `${pipestatus[1]}` returns `1` and `0`.
        #
        # So the bash spelling is deliberately NOT excused here. Every transcript
        # this module reads is zsh, where that form is inert by construction;
        # excusing it would be excusing the absence of the thing being asked for.
        # A bash user would be flagged for a compliant command — accepted,
        # because the rule reports a rate of candidates rather than a verdict,
        # and the safe direction for a false-green detector is to over-report.
        unless=r"\$\{?pipestatus\[1\]",
    ),
)
"""Standing directives whose compliance is a RATE, not a yes/no."""

UNARMED: tuple[Rule, ...] = (
    _rule(
        "bounded-search",
        # `-maxdepth` on a find, or a recursive search truncated by `head`.
        # Deliberately NOT every `| head`: piping a /tmp log through head is a
        # display bound on evidence already in hand, while bounding a search of
        # the TREE is what turns "absent" into "unreachable".
        r"\bfind\b[^\n]*-maxdepth|\b(?:grep -r|grep -R|rg)\b[^\n]*\|\s*head\s+-\d",
        "remove the bound, or prove the target is inside it",
        "A bound turns 'absent' into 'unreachable'. One session reported a file "
        "missing that sat at depth 7.",
    ),
)
"""Probe shapes that can report a negative they never actually tested."""

_MISE_RUN = re.compile(r"\bmise run ([a-z0-9][\w-]*)")
_KB_SETUP = re.compile(r"\buv run kb-setup ([a-z][\w-]*)")
_GRAPHIFY = re.compile(r"\bgraphify (?:query|explain|path|god-nodes)\b|\bkb-query\b")
_SOURCE_READ = re.compile(r"\.(?:py|pkl|toml|js|ts)$")
_COUNT = re.compile(r"\bgrep\s+-[A-Za-z]*c[A-Za-z]*((?:[^\n;&|]|&(?!&))*)")
"""A counting grep, capturing the ARGUMENTS of that one invocation.

Armed-ness cannot be decided per-command by a pattern, which is why this is a
rate rather than a Rule: one `grep -c` is a probe, two over the same corpus is
a probe plus its control. Reporting one row per count produced pure noise on
the first run — the excerpt was literally `grep -c` every time.

The arguments are captured because COUNTING the invocations is not the same
question. `grep -c missing a; grep -c unrelated b` is two counts and two
matches, and the first version credited it as one validated probe — two
independently-unanswered negatives reported as one armed one, which is the
exact failure this whole section exists to name (cold lane, 2026-08-08).
"""


def _armed(command: str) -> bool:
    """Do two of this command's counting greps search the SAME corpus?

    That shared target is what makes the second grep a control rather than a
    second question: a term known to be present, counted the same way, over the
    same bytes. Different targets are two probes, and two probes do not arm each
    other however many there are.

    Approximated by the LAST argument, which is where a path sits in ordinary
    `grep -c <term> <path>` usage. It cannot see a grep reading stdin, and it
    would be fooled by a trailing flag — both under-report (a stdin pair is
    called unarmed), which is the safe direction for a rule whose whole subject
    is claiming an answer you did not get.

    Split with `shlex`, not `str.split`, because a quoted path is one argument.
    Whitespace-splitting `grep -c missing "a corpus"; grep -c known "b corpus"`
    left both as the trailing token `corpus"` — so two probes over DIFFERENT
    corpora matched, and the function reported the precise false ARMED it was
    written to remove (cold lane, round 1). `shlex` raises on an unbalanced
    quote, which a transcript fragment can easily carry; that falls back to the
    whitespace split rather than losing the command, since an approximate target
    is still better than none.
    """
    targets = [t for args in _COUNT.findall(command) if (t := _last_arg(args))]
    return len(targets) >= MIN_RUN and any(targets.count(t) >= MIN_RUN for t in targets)


_REDIRECT = ("<", ">", ">>", "<<", "2>", "2>>", "&>", "&>>")
"""Operators after which a word names a STREAM, never the corpus being counted."""


def _last_arg(args: str) -> str:
    """The final shell WORD of `args`, quotes resolved; "" when there is none.

    Everything from the first redirection is dropped. `grep -c missing corpus >
    /tmp/miss; grep -c known corpus > /tmp/control` compared `/tmp/miss` against
    `/tmp/control` and called a genuinely armed pair UNARMED — the mirror of the
    round-1 defect, and a worse direction than it looks: redirecting each count
    to its own file is what a careful probe DOES, so the rule punished the habit
    it exists to encourage (cold lane, round 2).
    """
    try:
        words = shlex.split(args)
    except ValueError:
        words = args.split()
    for i, word in enumerate(words):
        if word in _REDIRECT:
            words = words[:i]
            break
    return words[-1] if words else ""


def _normalise(command: str) -> str:
    """A command reduced to its SHAPE, so two runs of one idea collapse.

    Digits, quoted strings and absolute paths are the parts that vary between
    two executions of the same manual step, so they are exactly what a
    repeat-detector must ignore. Without this, `sed -i '' 's/1.54.0/1.54.1/'`
    and the same edit on the next file look like two unrelated commands.
    """
    shape = re.sub(r"'[^']*'|\"[^\"]*\"", "Q", command)
    shape = re.sub(r"/[^\s'\"]+", "P", shape)
    return re.sub(r"\d+", "N", shape).strip()


SELF = "session_reflect"
"""This module's own name. A command mentioning it is almost always EDITING
the rule table, and a rule table contains every pattern by construction — so
it matches itself and reports the author as the offender. Measured on the
first run: `bounded-search` fired on the `sed` that wrote `bounded-search`.
The sibling guard `kb_setup.hook_guard` records the same class — its first
false positives were all text ABOUT the guard."""


def commands_in(path: Path) -> Iterator[str]:
    """Every Bash command string in one transcript, in the order issued."""
    for name, payload in tool_uses(path):
        if name != "Bash":
            continue
        command = payload.get("command")
        if isinstance(command, str) and SELF not in command:
            yield command


def _reads_source(payload: dict[str, object]) -> bool:
    """Did this Read/Grep record go at SOURCE, rather than at prose or a log?

    All three keys, in specificity order. `path` was the missing one and it is
    the one a Grep actually carries: `{"pattern": "needle", "path": "…/cli.py"}`
    has no `file_path`, so the old chain fell through to the PATTERN and asked
    whether the search term looked like a filename. Every targeted grep of a
    module therefore went uncounted, understating `graph_skipped` — the half of
    the graph-first ratio that is supposed to be the uncomfortable one.
    """
    for key in ("file_path", "path", "pattern"):
        target = payload.get(key)
        if isinstance(target, str) and _SOURCE_READ.search(target):
            return True
    return False


def scan(rules: Iterable[Rule], command: str, session: str) -> Iterator[Finding]:
    """Every rule in `rules` that `command` trips, with the matched bytes.

    EVERY match, not the first. One `Finding` per command made the reported `xN`
    a count of COMMANDS while reading as a count of violations, and the two are
    not close: measured over the 2026-08-08 transcript, `piped-rc` reported x17
    against **35** actual matches, with 10 of those 17 commands chaining more
    than one piped gate (`ruff … | tail; ruff format … | tail; ty … | tail;
    pytest … | tail` is one command and four discarded exit codes). A directive's
    compliance is a RATE, and a rate whose numerator is silently deduplicated
    per-command understates itself by whatever the chaining habit happens to be.

    The ORDER of the three checks is load-bearing, not tidiness. `also` and
    `unless` are cheap alternations; `pattern` is the expensive one, and the
    adversarial input for `mutation-harness` — many patch tokens, no run token —
    is exactly the input `also` rejects. Measured with the old spanning pattern
    restored: 398 ms executing it directly against that command, 0.28 ms through
    this function, because the pattern is never reached. Moving `pattern` above
    these two would hand back the cost the split was made to remove.
    """
    for rule in rules:
        if rule.also is not None and not rule.also.search(command):
            continue
        for match in rule.pattern.finditer(command):
            # PER MATCH, and only from `match.end()` onward. A status read for
            # THIS pipeline necessarily comes after it, so an exemption sitting
            # earlier in the command cannot be about it — `echo ${pipestatus[1]};
            # mise run lint | tail` used to buy the lint pipeline a full pass
            # from a read of some previous pipeline's status. Whole-command
            # `unless` is the shape behind all four of this rule's too-wide
            # exemptions (cold lane, round 1, P2), and scoping it forward is the
            # part of that class closable without parsing the pipeline.
            if rule.unless is not None and rule.unless.search(command, match.end()):
                continue
            excerpt = " ".join(match.group(0).split())[:110]
            yield Finding(rule=rule, session=session, excerpt=excerpt)


def _sequences(commands: Sequence[str], matcher: re.Pattern[str]) -> list[tuple[str, ...]]:
    """Adjacent same-family invocations, as runs of the captured names.

    Adjacency is what makes a run a wrapper candidate rather than a coincidence:
    `lint` then `test` back-to-back is one intention typed twice, while the same
    two calls an hour apart are two decisions. A command matching nothing breaks
    the run, which is why the reset lives in the else-branch.
    """
    runs: list[tuple[str, ...]] = []
    current: list[str] = []
    for command in commands:
        found = matcher.findall(command)
        if found:
            current.extend(found)
            continue
        if len(current) >= MIN_RUN:
            runs.append(tuple(current))
        current = []
    if len(current) >= MIN_RUN:
        runs.append(tuple(current))
    return runs


def reflect(
    root: Path,
    *,
    transcripts: Sequence[Path] | None = None,
    limit: int = DEFAULT_SESSION_LIMIT,
    locate: Callable[[Path, int], Sequence[Path]] | None = None,
) -> Report:
    """Read this project's recent transcripts and report automatable by-hand work.

    `transcripts` and `locate` are injected by tests and by any caller that
    already knows which sessions it means; the default path resolves them through
    `kb_setup.brain`, the one locator this repo has, rather than adding a second.
    """
    found = list(transcripts) if transcripts is not None else _locate(root, limit, locate)
    report = Report(sessions=tuple(p.stem for p in found))
    for path in found:
        _scan_one(path, report)
    return report


def _locate(
    root: Path, limit: int, locate: Callable[[Path, int], Sequence[Path]] | None
) -> list[Path]:
    if locate is not None:
        return list(locate(root, limit))
    return list(brain.project_transcripts(brain.transcripts_base(), root, limit=limit))


def _scan_one(path: Path, report: Report) -> None:
    """Fold one transcript's findings into `report`."""
    session = path.stem
    commands = list(commands_in(path))
    report.commands += len(commands)
    for command in commands:
        report.owned.extend(scan(OWNED, command, session))
        report.violations.extend(scan(DIRECTIVES, command, session))
        report.unarmed.extend(scan(UNARMED, command, session))
        report.graph_queries += len(_GRAPHIFY.findall(command))
        if _COUNT.search(command):
            report.counts += 1
            report.counts_armed += 1 if _armed(command) else 0

    shapes = Counter(_normalise(c) for c in commands)
    report.repeats.extend(
        (shape, count) for shape, count in shapes.most_common() if count >= MIN_RUN
    )
    for label, matcher in (("mise task", _MISE_RUN), ("kb_setup call", _KB_SETUP)):
        report.runs.extend((label, run) for run in _sequences(commands, matcher))

    report.graph_skipped += sum(
        1
        for name, payload in tool_uses(path)
        if name in {"Read", "Grep"} and _reads_source(payload)
    )


MAX_ROWS = 10
"""Rows shown per list section before the rest are summarised, never dropped."""


def _capped(lines: Sequence[str], *, limit: int = MAX_ROWS) -> list[str]:
    """The first `limit` rows, plus a line SAYING how many were withheld.

    A silent truncation reads as "that was everything", which is how a bounded
    report becomes a wrong one. Naming the remainder costs one line and is the
    difference between a display bound and a false negative.
    """
    shown = list(lines[:limit])
    withheld = len(lines) - len(shown)
    if withheld > 0:
        shown.append(f"- … {withheld} more not shown (raise MAX_ROWS to see them)")
    return shown


def _section(title: str, lines: Sequence[str], empty: str) -> list[str]:
    out = [f"## {title}", ""]
    out.extend(lines or [f"_{empty}_"])
    out.append("")
    return out


EXCERPTS_PER_RULE = 3
"""Offending commands SHOWN per directive, before the rest are counted only.

Three rather than all of them because this section reports a rate and can run to
dozens of rows; three rather than one because a single excerpt reads as *the*
violation rather than a sample, and the question a reader actually has — "are
these real, or is the rule over-firing?" — needs more than one data point to
answer.
"""


def _violation_lines(violations: Sequence[Finding]) -> list[str]:
    """One row per directive: the count, the remedy, and SOME OF THE BYTES.

    The bytes are the part that was missing, and their absence had a measured
    cost. Every other section of this report prints `f.excerpt`; this one printed
    a bare `id xN -> remedy`, so a reader who doubted a count had nothing to
    check it against. On 2026-08-08 that is exactly what happened: a handoff
    recorded `piped-rc x17` with the guess that "several were the RECOMMENDED
    form plus a read", and re-deriving the 17 commands showed **none** of them
    were — the rule was right 17 times out of 17. A count nobody can drill into
    does not get verified, it gets speculated about, and the speculation is what
    the next session inherits.

    A rate section is exactly where this bites hardest, because a rate is the
    kind of number a reader is *entitled* to disbelieve.
    """
    grouped: dict[str, list[Finding]] = {}
    for finding in violations:
        grouped.setdefault(finding.rule.id, []).append(finding)

    lines: list[str] = []
    for rid, found in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"- `{rid}` x{len(found)} -> **{found[0].rule.remedy}**")
        lines.extend(f"    {f.excerpt}" for f in found[:EXCERPTS_PER_RULE])
        withheld = len(found) - EXCERPTS_PER_RULE
        if withheld > 0:
            lines.append(f"    … {withheld} more (raise EXCERPTS_PER_RULE to see them)")
    return lines


def render(report: Report) -> str:
    """The human-facing report. Leads, never verdicts — see the module docstring."""
    header = (
        f"session-reflect: {len(report.sessions)} session(s), "
        f"{report.commands} bash command(s) scanned"
    )
    out: list[str] = [
        header,
        "",
        "  Every line is a LEAD. An empty section is the common, correct result —",
        "  which is what makes a non-empty one worth reading.",
        "",
    ]

    out += _section(
        "Hand-rolled work a mise task already owns",
        [
            f"- `{f.rule.id}` -> **{f.rule.remedy}**\n  {f.excerpt}\n  _{f.rule.why}_"
            for f in report.owned
        ],
        "nothing — every step went through its task",
    )
    out += _section(
        "Standing-directive violations (a RATE, not a yes/no)",
        _violation_lines(report.violations),
        "none observed",
    )
    unarmed_lines = [f"- `{f.rule.id}`: {f.excerpt}\n  _{f.rule.why}_" for f in report.unarmed]
    if report.counts:
        bare = report.counts - report.counts_armed
        unarmed_lines.append(
            f"- counting greps: {report.counts_armed}/{report.counts} carried a control "
            f"in the same command; {bare} stood alone\n"
            "  _A 0-result grep is not an answer until a control arm has run — a token "
            "SPELLING is a bound too (`LM Studio` has a space)._"
        )
    out += _section("Probes that could not have answered", _capped(unarmed_lines), "none observed")
    out += _section(
        "Command shapes repeated inside ONE session",
        _capped([f"- x{count}  `{shape[:100]}`" for shape, count in report.repeats]),
        "none repeated",
    )
    out += _section(
        "Sequential calls that want ONE wrapper",
        _capped([f"- {label} run: {' -> '.join(run)}" for label, run in report.runs]),
        "none — no adjacent runs to collapse",
    )
    ratio = (
        f"- {report.graph_queries} graphify/kb-query call(s) against "
        f"{report.graph_skipped} direct source read(s)"
    )
    out += _section(
        "Graph-first",
        [ratio] if report.graph_skipped or report.graph_queries else [],
        "no source reads to compare against",
    )
    return "\n".join(out)


def reflect_main(root: Path, args: Sequence[str] = ()) -> int:
    """`kb-setup session-reflect` — always 0; this reports, it never gates."""
    limit = DEFAULT_SESSION_LIMIT
    rest = list(args)
    if "--sessions" in rest:
        index = rest.index("--sessions")
        if index + 1 < len(rest) and rest[index + 1].isdigit():
            limit = int(rest[index + 1])
    report = reflect(root, limit=limit)
    if "--quiet" in rest:
        # SessionEnd shares a 1.5 s budget across hooks and its output competes
        # with the audit's. One line naming the counts is enough to decide
        # whether to run the task properly; the full report is one command away.
        findings = len(report.owned) + len(report.violations) + len(report.unarmed)
        wrappable = len(report.repeats) + len(report.runs)
        print(
            f"session-reflect: {findings} finding(s), {wrappable} wrapper lead(s) "
            f"— `mise run kb-session-reflect` for the report"
        )
        return 0
    print(render(report))
    return 0
