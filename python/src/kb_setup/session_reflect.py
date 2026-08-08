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
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
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


def _rule(rid: str, pattern: str, remedy: str, why: str, unless: str | None = None) -> Rule:
    return Rule(
        id=rid,
        pattern=re.compile(pattern),
        remedy=remedy,
        why=why,
        unless=re.compile(unless) if unless else None,
    )


OWNED: tuple[Rule, ...] = (
    _rule(
        "mutation-harness",
        r"""(?sx)
        (?:read_text|\.replace\(|write_text)     # a source file being patched
        .*?
        (?:pytest|subprocess\.run|rc=)           # ...then something run over it
        """,
        "mise run kb-arms -- <spec.toml>",
        "distill's largest group: 149 hand-written harnesses across 21 sessions. "
        "A scratchpad harness loses the __pycache__ mitigation, which can credit "
        "an arm with a death the mutation never caused.",
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
        r"(?m)(?:^|[;&|]\s*)cd\s+(?!/)[^\s;&|]+",
        "git -C <path> …, or an absolute path",
        "cwd persists across Bash calls; two relative cds once made "
        "`gh issue view` return a different repository's PR.",
    ),
    _rule(
        "piped-rc",
        # ONLY a gate on the left-hand side. The first draft matched any
        # `| head`/`| tail` and fired 111 times in one session — every display
        # pipe over a log file. A rule at that volume is noise, and noise is
        # what teaches a reader to skip the section that holds the real one.
        # The directive is about losing a GATE's exit code, so the left side
        # must be something whose rc means anything.
        r"\b(?:mise run|hk |pytest|uv run (?:ruff|ty|pytest))[^|\n]*"
        r"\|\s*(?:tail|head)\b(?![^|\n]*\brc=)",
        '<cmd> > /tmp/out.log 2>&1; echo "rc=$?" >> /tmp/out.log',
        "Bash returns the LAST pipeline command's exit code, so a failed gate reports success.",
        r"\brc=\$\?",
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
_COUNT = re.compile(r"\bgrep\s+-[A-Za-z]*c")
"""A counting grep. Armed only when the SAME command counts a second term.

Armed-ness cannot be decided per-command by a pattern, which is why this is
a rate rather than a Rule: one `grep -c` is a probe, two in one command is a
probe plus its control. Reporting one row per count produced pure noise on
the first run — the excerpt was literally `grep -c` every time."""


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
    target = payload.get("file_path") or payload.get("pattern") or ""
    return isinstance(target, str) and bool(_SOURCE_READ.search(target))


def scan(rules: Iterable[Rule], command: str, session: str) -> Iterator[Finding]:
    """Every rule in `rules` that `command` trips, with the matched bytes."""
    for rule in rules:
        if rule.unless is not None and rule.unless.search(command):
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
        found = len(_COUNT.findall(command))
        if found:
            report.counts += 1
            report.counts_armed += 1 if found >= MIN_RUN else 0

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
