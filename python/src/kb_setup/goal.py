"""Mechanical checks for a `/goal` goal+rider pair.

WHAT THIS IS AND IS NOT. The `/goal` evaluator is a small fast model that reads
ONLY the conversation transcript — it runs no tools, opens no files. So the
quality of a goal rests entirely on its text, and a text can be checked. This
module owns every test that is *decidable without a model*: a character count, a
present-or-absent section, a filename shape, a regex over sentinels. The tests
that need judgement — can this clause be satisfied without the work being done,
is this really one round — live in `.claude/skills/goal-engineering` and are the
model's job. Splitting them the other way is the failure the rubric warns about:
a heuristic standing in for judgement produces false confidence, which is worse
than no check at all.

ADVISORY BY CONSTRUCTION — `main` always returns 0. A goal document is authored
input, not repo source, and a WARN-level heuristic (an adjective that may or may
not carry a verdict) must never be able to block a PR. Same posture as
`kb_setup.currency`: read the report, not the exit code.

The three verdicts are kept distinct for the reason the currency engine keeps
them distinct — collapsing "could not check" into "fine" is how a checker starts
lying. A file that cannot be read is NOT a pass.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

#: The cap `/goal` enforces on the objective text. Both Claude Code and Codex
#: refuse longer input and tell you to put the detail in a file — which is what
#: the rider is. Ceccarelli's corpus runs 3,929-4,112; past ~4,100 the goal is
#: doing work that belongs in the rider.
GOAL_CHAR_CAP = 4000
_GOAL_CHAR_SNUG = 3900

#: Sections a goal must carry. Order is not enforced — authors reorder for flow,
#: and a section present-but-moved is not a defect.
_REQUIRED_GOAL_SECTIONS: tuple[tuple[str, str], ...] = (
    ("GOAL:", "the opening verb + the current pain, named with real paths"),
    ("Read first", "absolute/relative paths the agent grounds itself in"),
    ("Preserve", "the change-everything-except list (the Goodhart fence)"),
    ("Posture", "what this round does NOT do — mostly negations"),
    ("Verification", "the literal transcript assertions"),
    ("Stop when", "one sentence tying verification to a final state"),
)

#: Adjectives that cannot carry a completion verdict. "Make it good" is not a
#: finish line; "scores over 8/10 using my grading skill" is. Flagged as WARN
#: rather than FAIL because a word on this list may sit in explanatory prose
#: where it decides nothing — only a human can tell which.
_VERDICT_ADJECTIVES: tuple[str, ...] = (
    "adequate",
    "appropriate",
    "clean",
    "comprehensive",
    "good",
    "major",
    "minor",
    "proper",
    "reasonable",
    "robust",
    "sensible",
    "thorough",
    "well-formed",
)

#: `<YYYY-MM-DD>-<HHMM>-<project>-<topic>-{goal,rider}.md`. The HHMM is local
#: authoring time so `ls` sorts in true authoring order; the pair shares one
#: timestamp, and splitting them across minutes breaks that sort.
_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*-(goal|rider)\.md$")

#: A sentinel is a backticked ALL-CAPS token that EITHER contains a hyphen
#: (`REDACT-ARM+`, `GOAL-BLOCKED:`) OR ends in a colon (`HANDBACK:`).
#:
#: Both halves of that disjunction are load-bearing, and the first version of
#: this regex had neither. Matching any ALL-CAPS run flagged `PASS` (from the
#: literal expected output `PASS  gate lint rc=0`) and `S105` (a ruff rule code)
#: as sentinels missing their sha — a false positive on the very first real
#: document. The distinction the checker has to make is between a token the
#: AGENT MUST EMIT, which needs a run-specific value or it is pre-satisfied, and
#: a literal string the agent QUOTES BACK from a tool's output, which is already
#: run-specific because the tool produced it.
_SENTINEL_RE = re.compile(r"`([A-Z][A-Z0-9]*(?:-[A-Z0-9+]+)+:?|[A-Z][A-Z0-9]{2,}:)[^`]*`")

#: The run-specific suffix that stops a sentinel being pre-satisfied. Setting a
#: goal starts a turn WITH THE CONDITION AS THE DIRECTIVE, so any literal string
#: spelled out in the condition is already in the transcript at turn 0.
_SHA_SUFFIX_RE = re.compile(r"@\s*<?sha>?", re.IGNORECASE)

_HEADLINE_RE = re.compile(r"Headline word:\s*([A-Za-z][\w-]*)", re.IGNORECASE)
_TURN_BOUND_RE = re.compile(
    r"stop after \d+ turns?|after \d+ turns?|within \d+ (?:turns?|minutes)", re.IGNORECASE
)
_NEGATION_RE = re.compile(r"\bno\b|\bnot\b|\bnever\b|\bdo not\b", re.IGNORECASE)
_PHASE_RE = re.compile(r"^#{2,4}\s*P\d+\b", re.MULTILINE)

_MIN_NEGATIONS = 3
_MIN_PHASES = 3


class Verdict(Enum):
    """OK / WARN / FAIL, kept distinct so "could not check" is never green."""

    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Finding:
    """One check's result. ``line`` is 1-indexed when the check found a location."""

    check: str
    verdict: Verdict
    detail: str
    line: int | None = None


def _line_of(text: str, needle: str) -> int | None:
    """1-indexed line containing ``needle``, or None."""
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return i
    return None


def _check_char_cap(text: str) -> Finding:
    """The 4,000-character cap `/goal` itself enforces.

    CHARACTERS, not bytes — `len()` and not `wc -c`. The two disagree by exactly
    the number of multi-byte characters, and this convention's prose is full of
    em dashes: the first goal written here measured 3,729 bytes and 3,703
    characters. The cap is stated in characters, so `wc -c` over-counts and would
    send you trimming a goal that already fits. Prefer this check over `wc`.
    """
    n = len(text)
    if n > GOAL_CHAR_CAP:
        return Finding(
            "char-cap",
            Verdict.FAIL,
            f"{n} / {GOAL_CHAR_CAP} — `/goal` will refuse this. Move detail into the rider.",
        )
    if n > _GOAL_CHAR_SNUG:
        return Finding(
            "char-cap",
            Verdict.WARN,
            f"{n} / {GOAL_CHAR_CAP} — snug. Leave room; a later edit will push it over.",
        )
    return Finding("char-cap", Verdict.OK, f"{n} / {GOAL_CHAR_CAP}")


def _check_sections(text: str) -> list[Finding]:
    """Every required goal section is present (order not enforced)."""
    missing = [
        (key, why) for key, why in _REQUIRED_GOAL_SECTIONS if key.lower() not in text.lower()
    ]
    if missing:
        return [
            Finding("required-sections", Verdict.FAIL, f"missing `{key}` — {why}")
            for key, why in missing
        ]
    return [
        Finding(
            "required-sections",
            Verdict.OK,
            f"{len(_REQUIRED_GOAL_SECTIONS)}/{len(_REQUIRED_GOAL_SECTIONS)} present",
        )
    ]


def _check_headline(text: str) -> Finding:
    """Exactly one headline word — the test of whether this is ONE round."""
    words = _HEADLINE_RE.findall(text)
    if not words:
        return Finding(
            "headline-word",
            Verdict.FAIL,
            "no `Headline word:` — if you cannot pick one word, the scope is too "
            "wide; split the round.",
        )
    if len(words) > 1:
        return Finding(
            "headline-word",
            Verdict.FAIL,
            f"{len(words)} headline words ({', '.join(words)}) — that is more than one round.",
            _line_of(text, words[1]),
        )
    return Finding("headline-word", Verdict.OK, f"exactly one (`{words[0]}`)")


def _check_sentinels(text: str) -> Finding:
    """Every sentinel carries a run-specific suffix, so none is satisfied at turn 0.

    This is the subtlest defect the rubric found and the easiest to reintroduce:
    the condition's own text sits in the transcript from the moment the goal is
    set, so a clause reading "the transcript contains FOO" can be true before any
    work happens — satisfied by the condition quoting itself.
    """
    sentinels = {m.group(1) for m in _SENTINEL_RE.finditer(text)}
    if not sentinels:
        return Finding(
            "sentinel-format",
            Verdict.WARN,
            "no sentinels found — verification may be relying on prose the "
            "evaluator has to interpret.",
        )
    bare = sorted(s for s in sentinels if not _sentinel_has_sha(text, s))
    if bare:
        return Finding(
            "sentinel-format",
            Verdict.FAIL,
            f"{len(bare)} sentinel(s) without a run-specific value ({', '.join(bare)}) — "
            "add `@ <sha>` or they are arguably already in the transcript at turn 0.",
            _line_of(text, bare[0]),
        )
    return Finding(
        "sentinel-format", Verdict.OK, f"{len(sentinels)} sentinel(s), all carry `@ <sha>`"
    )


def _sentinel_has_sha(text: str, sentinel: str) -> bool:
    """True when every backticked span naming ``sentinel`` also carries the sha suffix."""
    spans = [m.group(0) for m in _SENTINEL_RE.finditer(text) if m.group(1) == sentinel]
    return all(_SHA_SUFFIX_RE.search(span) for span in spans)


def _check_adjectives(text: str) -> list[Finding]:
    """Words that cannot carry a completion verdict."""
    hits = [
        Finding(
            "adjective-scan",
            Verdict.WARN,
            f'"{word}" — if this word carries the pass/fail judgement, name the '
            "literal string or number a reader would search for instead.",
            i,
        )
        for i, line in enumerate(text.splitlines(), start=1)
        for word in _VERDICT_ADJECTIVES
        if re.search(rf"\b{re.escape(word)}\b", line, re.IGNORECASE)
    ]
    return hits or [Finding("adjective-scan", Verdict.OK, "no verdict-bearing adjectives")]


def _check_turn_bound(text: str) -> Finding:
    """A turn or time clause — nothing else bounds a goal run."""
    if _TURN_BOUND_RE.search(text):
        return Finding("turn-bound", Verdict.OK, "a turn/time clause is present")
    return Finding(
        "turn-bound",
        Verdict.FAIL,
        "no turn or time clause — a goal runs until the condition holds or you clear it. "
        'Add prose like "stop after 25 turns" (it is prose in the condition, not a flag).',
    )


def _check_posture_negations(text: str) -> Finding:
    """Posture is a fence, and a fence is made of negations."""
    posture = _section(text, "Posture")
    if posture is None:
        return Finding("posture-fence", Verdict.FAIL, "no Posture section to check")
    n = len(_NEGATION_RE.findall(posture))
    if n < _MIN_NEGATIONS:
        return Finding(
            "posture-fence",
            Verdict.WARN,
            f"only {n} negation(s) — an agent under pressure invents solutions; "
            "Posture is what keeps it inside this round.",
        )
    return Finding("posture-fence", Verdict.OK, f"{n} negations")


def _check_preserve(text: str) -> Finding:
    """The change-everything-except list — the defence against metric-gaming."""
    if _section(text, "Preserve") is None:
        return Finding(
            "preserve-list",
            Verdict.FAIL,
            "no Preserve list — without one, the cheapest way to satisfy the metric is to "
            "delete the thing the round exists to protect.",
        )
    return Finding("preserve-list", Verdict.OK, "present")


def _section(text: str, name: str) -> str | None:
    """The body of a `Name.` / `## Name` section, up to the next section break."""
    pattern = re.compile(
        rf"^\s*(?:#+\s*)?\*{{0,2}}{re.escape(name)}\b[.:]?\*{{0,2}}", re.IGNORECASE | re.MULTILINE
    )
    m = pattern.search(text)
    if m is None:
        return None
    rest = text[m.start() :]
    lines = rest.splitlines()
    body = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            break
        body.append(line)
    return "\n".join(body)


def _check_name(path: Path | None, kind: str) -> Finding:
    """The `<date>-<HHMM>-<project>-<topic>-{goal,rider}.md` schema."""
    if path is None:
        return Finding("naming-schema", Verdict.WARN, "checked from text — no filename to validate")
    if not _NAME_RE.match(path.name):
        return Finding(
            "naming-schema",
            Verdict.FAIL,
            f"`{path.name}` does not match <YYYY-MM-DD>-<HHMM>-<project>-<topic>-{kind}.md — "
            "the HHMM keeps `ls` in authoring order, and the pair must share one timestamp.",
        )
    return Finding("naming-schema", Verdict.OK, path.name)


def check_goal(text: str, path: Path | None = None) -> list[Finding]:
    """Every mechanical test that applies to a goal document."""
    findings = [_check_char_cap(text), _check_name(path, "goal")]
    findings.extend(_check_sections(text))
    findings.extend([_check_headline(text), _check_sentinels(text)])
    findings.extend(_check_adjectives(text))
    findings.extend(
        [_check_turn_bound(text), _check_posture_negations(text), _check_preserve(text)]
    )
    return findings


def check_rider(text: str, path: Path | None = None) -> list[Finding]:
    """The structural subset that applies to a rider.

    A rider has no character cap and no sentinel rules, so most goal tests do not
    apply. What it owes is structure: numbered phases, an explicit out-of-scope
    list (the overflow valve that keeps a round from quietly widening), and a
    pointer back at the goal it serves.
    """
    findings = [_check_name(path, "rider")]
    phases = _PHASE_RE.findall(text)
    findings.append(
        Finding("rider-phases", Verdict.OK, f"{len(phases)} phase heading(s)")
        if len(phases) >= _MIN_PHASES
        else Finding(
            "rider-phases",
            Verdict.WARN,
            f"{len(phases)} phase heading(s) — a rider carries the phases the capped goal cannot.",
        )
    )
    findings.append(
        Finding("rider-out-of-scope", Verdict.OK, "present")
        if re.search(r"out.of.scope", text, re.IGNORECASE)
        else Finding(
            "rider-out-of-scope",
            Verdict.WARN,
            "no out-of-scope section — the overflow valve that stops a round "
            "widening under pressure.",
        )
    )
    findings.append(
        Finding("rider-cites-goal", Verdict.OK, "cites its goal")
        if "-goal.md" in text
        else Finding("rider-cites-goal", Verdict.FAIL, "does not name the goal it serves")
    )
    return findings


def check_pair(goal_path: Path) -> list[Finding]:
    """Goal + rider together, including the always-a-pair rule and cross-reference."""
    rider_path = goal_path.with_name(goal_path.name.replace("-goal.md", "-rider.md"))
    findings = check_goal(goal_path.read_text(encoding="utf-8"), goal_path)
    if not rider_path.is_file():
        findings.append(
            Finding(
                "pair",
                Verdict.FAIL,
                f"no rider at {rider_path.name} — the cap sends detail to the rider, so a missing "
                "rider means the phases and out-of-scope list have nowhere to live.",
            )
        )
        return findings
    findings.append(Finding("pair", Verdict.OK, rider_path.name))
    findings.extend(check_rider(rider_path.read_text(encoding="utf-8"), rider_path))
    return findings


def render(findings: list[Finding]) -> str:
    """The report. Ordered as authored so related checks stay adjacent."""
    lines = []
    for f in findings:
        where = f":{f.line}" if f.line else ""
        lines.append(f"{f.verdict.value:<4} {f.check:<20}{where:<6} {f.detail}")
    counts = {v: sum(1 for f in findings if f.verdict is v) for v in Verdict}
    lines.append("")
    lines.append(
        f"{counts[Verdict.OK]} OK, {counts[Verdict.WARN]} WARN, {counts[Verdict.FAIL]} FAIL"
        "   (advisory — always exits 0; read the report, not the rc)"
    )
    return "\n".join(lines)


def _resolve(target: str, repo_root: Path) -> tuple[str, Path | None, bool]:
    """Return ``(text, path, is_pair)`` for a path, a pair prefix, or raw text."""
    candidate = (repo_root / target).resolve() if not Path(target).is_absolute() else Path(target)
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8"), candidate, candidate.name.endswith("-goal.md")
    goal = candidate.with_name(candidate.name + "-goal.md")
    if goal.is_file():
        return goal.read_text(encoding="utf-8"), goal, True
    return target, None, False


def main(args: list[str], repo_root: Path) -> int:
    """`kb-goal-check` — always returns 0; this is advisory, never a gate."""
    if args and args[0] == "--text":
        text, path, is_pair = " ".join(args[1:]), None, False
    elif args:
        text, path, is_pair = _resolve(args[0], repo_root)
    elif not sys.stdin.isatty():
        text, path, is_pair = sys.stdin.read(), None, False
    else:
        print(
            "kb-goal-check: pass a goal/rider path, a pair prefix, "
            "--text <goal text>, or pipe on stdin"
        )
        return 0

    if is_pair and path is not None:
        findings = check_pair(path)
    elif path is not None and path.name.endswith("-rider.md"):
        findings = check_rider(text, path)
    else:
        findings = check_goal(text, path)

    print(render(findings))
    return 0
