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
        r"git ls-remote --tags.*sources/|sed -i.*sources/\S+\.manifest",
        "uv run kb-setup manifest-add / the currency engine's apply",
        "hand-resolving a tag and sed-ing it in skips the v-prefix and "
        "annotated-tag handling the module already carries.",
    ),
    _rule(
        "gate-by-hand",
        r"\buv run (?:ruff|ty|pytest)\b.*&&.*\buv run (?:ruff|ty|pytest)\b",
        "mise run kb-gates",
        "kb-gates records each result to .agent/kb/gates/gates-<sha>.json, so a "
        "later claim about them has a surviving artifact.",
    ),
)
"""Work an existing task already owns. The remedy is the point of the row."""

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
        r"(?m)(?:^|[;&|]\s*)cd\s+(?![\"']?(?:[/~]|\$\(|\$\{?HOME))[^\s;&|]+",
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
            rf"(?m)(?:^|[;&|]\s*)"
            rf"(?:mise run (?:{_GATE_TASKS})|hk |pytest|uv run (?:ruff|ty|pytest))"
            rf"{_SEG}\|\s*(?:tail|head)\b(?!{_SEG}\brc=)",
            '<cmd> > /tmp/out.log 2>&1; echo "rc=$?" >> /tmp/out.log',
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
        # What remains unexcused: an unrelated `${PIPESTATUS[0]}` for a DIFFERENT
        # pipeline in the same command. That is a false negative on an input
        # nobody has written, and closing it would mean parsing the pipeline
        # rather than matching it.
        unless=r"PIPESTATUS\[0\]",
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


def _last_arg(args: str) -> str:
    """The final shell WORD of `args`, quotes resolved; "" when there is none."""
    try:
        words = shlex.split(args)
    except ValueError:
        words = args.split()
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

    The ORDER of the three checks is load-bearing, not tidiness. `also` and
    `unless` are cheap alternations; `pattern` is the expensive one, and the
    adversarial input for `mutation-harness` — many patch tokens, no run token —
    is exactly the input `also` rejects. Measured with the old spanning pattern
    restored: 398 ms executing it directly against that command, 0.28 ms through
    this function, because the pattern is never reached. Moving `pattern` above
    these two would hand back the cost the split was made to remove.
    """
    for rule in rules:
        if rule.unless is not None and rule.unless.search(command):
            continue
        if rule.also is not None and not rule.also.search(command):
            continue
        match = rule.pattern.search(command)
        if match:
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
    remedies = {f.rule.id: f.rule.remedy for f in report.violations}
    out += _section(
        "Standing-directive violations (a RATE, not a yes/no)",
        [
            f"- `{rid}` x{count} -> **{remedies[rid]}**"
            for rid, count in Counter(f.rule.id for f in report.violations).most_common()
        ],
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
