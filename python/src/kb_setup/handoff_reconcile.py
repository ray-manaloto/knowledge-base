# Copyright (c) 2026 Raymond Manaloto
"""Catch a handoff that silently dropped the previous handoff's backlog.

Ray approved this after the first real run of `session-review mode:'handoff'`
(2026-08-18, wf_701b4d8f-df8) produced a handoff that passed
`mise run kb-handoff-check` at **20 OK / 2 AMBIG / 0 broken** while dropping
SEVEN of the nine items under the previous handoff's own heading *"Owed,
unchanged from the previous handoff"* — the 18-name roster, two staleness gates,
rumdl use-or-remove, gitleaks->betterleaks, mongodb/kingfisher, the hk-builtin
review workflow, and `kb-update -- agent-harness-docs`. It also dropped the
standing environment traps: codex being out of credits, `find -newermt` failing
silently on BSD, `docs/session-review/runs/**` being formatter-exempt.

WHAT THE EXISTING CHECK COULD NOT SEE, and why that is not a criticism of it.
`handoff.check` verifies that the claims a handoff MAKES are true. Every claim in
that handoff was true. The defect was in the claims it did not make — and
completeness is a different question from correctness, invisible to every check
that starts from the document in hand. This module supplies the second document.

HOW A DETERMINISTIC GATE CAN POSSIBLY JUDGE THIS. It cannot read meaning
(`gates-cannot-read-meaning.md`), and two agents write the same commitment in
different words, so no prose comparison would work. What survives rewording is an
IDENTIFIER: a backticked task, path or flag, or an issue number. Every one of the
seven real losses carried one — `rumdl`, `kingfisher`, `betterleaks`,
`agent-harness-docs`, `proseExclude`. So the gate asks one narrow, exact
question: *the previous handoff committed to something it named `X`; does the new
handoff say the word `X` at all?*

That is a weaker question than "was it reconciled", and deliberately so. It has
no false negatives it can be blamed for hiding — an item whose token survives may
still be handled badly, and this module never claims otherwise — while the
direction it DOES catch is the one that actually happened.

ARMED ON THE REAL PAIR, not a fixture: `tests/test_handoff_reconcile.py` runs
`session-2026-08-18-b.md` -> `-c.md` and asserts the known losses are found, and
runs b -> b and asserts silence. A gate verified only on synthetic input is
decoration.

WHICH WAY IT MISSES, stated because a gate's scope is what its green means:

* An item named only in prose ("the 2h37m idle-on-one-AskUserQuestion pattern")
  carries no identifier and is NOT checked. Reported in the summary as the count
  not checked, never folded into the pass.
* A token that is a common English word is skipped — `_TOO_COMMON` — because a
  gate whose match is accidental is worse than no gate.
* It reads the OWED and GOTCHA sections only. A commitment buried in narrative
  prose is out of scope; that is what the owed section is for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Headings whose bullets are COMMITMENTS — the previous round said these were
#: still owed. Matched case-insensitively against the heading text.
#:
#: `things that will bite you` is here rather than in `_GOTCHA_HEADINGS` on
#: purpose: it is where the codex-out-of-credits and BSD-`find` traps lived, and
#: those were among the cleanest losses. A standing environment trap is owed
#: until something retires it.
#: A COMMITMENT: the previous round said this is still owed. Dropping one
#: without a word is the failure this module exists to fail on.
_OWED_HEADINGS = (
    "owed",
    "not done",
    "what is owed",
    "unchanged from the previous handoff",
    "next task",
)

#: INFORMATIONAL: a standing trap or a probe that misled. Still owed until
#: something retires it — the codex-out-of-credits and BSD-`find` traps were
#: among the cleanest losses — but reported, not failed.
#:
#: The split is what makes the gate proportionate, and it is drawn from the real
#: pair rather than from taste. Matching a gotcha is inherently looser: one
#: reads *"the cold lane is `agy`"* and the new handoff says `agy` twice while
#: dropping the "out of credits until…" half, so the honest verdict is "look at
#: this", not "you may not ship". An owed item is a commitment and gets the
#: harder verdict.
_GOTCHA_HEADINGS = (
    "things that will bite you",
    "gotcha",
)

#: Tokens that would match by accident, and the direction that matters.
#:
#: A junk token does not merely add noise — because a commitment is CARRIED when
#: ANY of its tokens survives, a word that appears in every handoff VOUCHES for
#: the real commitment beside it. That is a false CARRIED: a silent pass, and
#: strictly worse than a false DROPPED, which at least gets read. Measured on the
#: real pair before this list grew: `command not found` in a gotcha yielded the
#: token `command`, and `/clear` yielded `clear` — either would have cleared its
#: bullet on its own.
#:
#: Two classes, kept together because both are "a word this document always
#: contains": generic tooling names, and the vocabulary of a handoff itself.
_TOO_COMMON = frozenset(
    {
        # generic tooling and literals
        "main",
        "head",
        "true",
        "false",
        "none",
        "null",
        "git",
        "gh",
        "mise",
        "uv",
        "python",
        "json",
        "md",
        "py",
        "js",
        "run",
        "test",
        "lint",
        "fmt",
        "check",
        "0",
        "1",
        "2",
        # the vocabulary every handoff is written in
        "handoff",
        "branch",
        "commit",
        "session",
        "review",
        "receipt",
        "gates",
        "tree",
        "issue",
        "clear",
        "command",
        "nothing",
        "then",
        "kind",
        "mode",
        "the",
        "and",
        "not",
    }
)

#: A backticked span: `kb-update -- agent-harness-docs`, `hk.pkl`, `--prose`.
_CODE_SPAN = re.compile(r"`([^`\n]{2,80})`")

#: A bare issue or PR reference. Exact by construction and never reworded.
_ISSUE_REF = re.compile(r"(?<![\w/])#(\d{1,5})\b")

#: A markdown ATX heading, with its level.
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$", re.MULTILINE)

#: Inside a code span, the part worth matching on. A span like
#: `mise run kb-update -- agent-harness-docs` should match a new handoff that
#: says `agent-harness-docs` in any other phrasing, so the span is reduced to
#: its most distinctive WORD rather than compared whole. Hyphenated and dotted
#: identifiers are one word here; that is what makes `hk.pkl` and
#: `agent-harness-docs` single tokens.
_IDENTIFIER = re.compile(r"[A-Za-z][\w.\-/]{2,}")

#: What a MACHINE name has and an English word does not: a hyphen, dot, slash,
#: underscore, a digit, or an internal capital. `agent-harness-docs`, `hk.pkl`,
#: `d7e344f8` and `proseExclude` all match; `docs`, `found`, `checked` and `plan`
#: do not. This is the whole defence against a weak token vouching for a strong
#: one — see :func:`_tokens_in`.
_DISTINCTIVE = re.compile(r"[-./_\d]|[a-z][A-Z]")

#: How long a PLAIN word must be to count as naming something. Five, because on
#: the real pair four admits `docs` (a false CARRIED, silent) and six excludes
#: `newermt`'s neighbours. See :func:`_tokens_in` for the trade this settles.
_PLAIN_MIN = 5


@dataclass(frozen=True)
class Commitment:
    """One BULLET the previous handoff said was still owed, and how to spot it.

    The unit is the line, not the token, and that is the whole design. A first
    version made one commitment per identifier and was wrong in both directions
    at once: it reported four findings for one bullet about
    `docs/session-review/runs/**` (noise that would get the gate switched off),
    while a bullet whose tools were written as bare prose — *"rumdl
    use-or-remove. gitleaks->betterleaks. mongodb/kingfisher"* — yielded only the
    one backticked `skillopt` beside them and could be half-carried silently.

    Grouping per line fixes both: a bullet is carried when the new handoff names
    ANY of its identifiers, and the whole bullet is quoted when it names none. So
    one surviving token vouches for its sentence — which is the correct reading,
    because a handoff that says `skillopt` is talking about that currency bullet,
    and a handoff that says nothing in it is not.
    """

    tokens: tuple[str, ...]
    line: int
    context: str
    heading: str


def _sections(text: str) -> list[tuple[str, str]]:
    """Every (heading, body) pair in ``text``, body running to the next heading.

    Returns the pairs rather than a dict because a handoff may repeat a heading
    across rounds, and collapsing two sections named "Owed" would drop one of
    them — which is the very failure this module exists to catch, re-made inside
    the catcher.
    """
    marks = list(_HEADING.finditer(text))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(2), text[m.end() : end]))
    return out


#: A line that STARTS a bullet: `- `, `* `, `1. `, or a `| ` table row.
_BULLET_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|\|)")


#: A sentence boundary in prose: `. ` / `; ` before something that starts a new
#: clause. Deliberately crude — it only has to separate list-like prose such as
#: *"rumdl use-or-remove. gitleaks->betterleaks in parallel. mongodb/kingfisher."*
_SENTENCE_END = re.compile(r"(?<=[.;])\s+(?=[A-Z(`*—])")


def _blocks(body: str) -> list[tuple[int, str]]:
    """(offset, text) per block: a bullet plus its wrapped continuation lines.

    A handoff is hard-wrapped, so one commitment routinely spans two physical
    lines — the real pair this module is armed on splits its
    `kb-update -- agent-harness-docs` item exactly there, tool name on one line
    and `mise.toml:507` on the next. Treating each physical line as its own
    commitment reported that as TWO losses: the same sentence counted twice, and
    noise is how a gate gets switched off. A blank line ends a block.
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(body.splitlines()):
        if not line.strip():
            continue
        if out and not _BULLET_START.match(line):
            index, previous = out[-1]
            out[-1] = (index, previous + " " + line.strip())
        else:
            out.append((i, line))
    return out


def _units(body: str) -> list[tuple[int, str]]:
    """The commitment units: a bullet is one, a prose paragraph is per SENTENCE.

    Folding by block alone was the first fix and it over-corrected, which the
    real pair caught immediately: this repo's owed sections are not always lists.
    One is a dense PARAGRAPH — *"…`skillopt` NOT CHECKED. The 18-name roster (9
    missing). Two new top-level staleness gates. rumdl use-or-remove.
    gitleaks->betterleaks in parallel. mongodb/kingfisher…"* — nine separate
    commitments in six sentences. Folded whole, the single surviving `skillopt`
    vouched for all nine and the check went quiet on eight real losses: a gate
    passing over exactly the failure it was built for.

    So the unit follows the writing. A bullet author has already declared where
    one item ends; in prose, the sentence is that declaration. Both directions
    are armed in the tests, because each was wrong once.
    """
    out: list[tuple[int, str]] = []
    for index, text in _blocks(body):
        if _BULLET_START.match(text):
            out.append((index, text))
            continue
        out.extend((index, part) for part in _SENTENCE_END.split(text) if part.strip())
    return out


def _is_owed(heading: str) -> bool:
    lowered = heading.lower()
    return any(key in lowered for key in _OWED_HEADINGS + _GOTCHA_HEADINGS)


def _is_commitment(heading: str) -> bool:
    """True for an OWED heading, False for a gotcha — the severity split."""
    lowered = heading.lower()
    return any(key in lowered for key in _OWED_HEADINGS)


def _tokens_in(fragment: str) -> list[str]:
    """The identifiers worth matching on, from one commitment.

    An issue reference is taken whole (`#343`); a code span contributes its
    longest identifier, because the new handoff will re-word the sentence around
    a name but cannot re-word the name.

    THE FILTER THAT MATTERS IS THE LAST ONE. A commitment is CARRIED when ANY of
    its tokens survives, so a weak token VOUCHES for the strong ones beside it —
    and that is a false CARRIED, a silent pass, strictly worse than a false
    DROPPED which at least gets read. The real pair demonstrated it twice while
    this was being written: `` `kind = docs` `` yielded `docs`, which appears in
    every handoff ever written, and cleared the
    `kb-update -- agent-harness-docs` commitment sitting in the same sentence.

    So a token is kept when it is STRUCTURALLY DISTINCTIVE — carrying a hyphen,
    dot, slash, underscore, digit or internal capital, which is what machine
    names have and English words do not — OR when it is a plain word of at least
    `_PLAIN_MIN` characters that `_TOO_COMMON` does not name. `docs` and `kind`
    fail both tests; `agent-harness-docs`, `hk.pkl` and `#344` pass the first;
    `skillopt`, `newermt` and `antigravity` pass the second.

    The length floor is where the two errors were traded off against each other,
    and both were observed on the real pair rather than imagined. Keeping ONLY
    distinctive tokens — the previous version — made `antigravity` invisible and
    reported a carried commitment as dropped: a false DROPPED, noisy but read.
    Dropping the floor to 4 lets `docs` back in: a false CARRIED, silent. Five is
    the value where the real pair has neither.

    Extending `_TOO_COMMON` alone was the first fix and it is unwinnable — the
    next weak token is always a word nobody thought to list — which is why the
    structural test carries the load and the list only handles what slips past.
    """
    found: list[str] = ["#" + n for n in _ISSUE_REF.findall(fragment)]
    for span in _CODE_SPAN.findall(fragment):
        words = [w for w in _IDENTIFIER.findall(span) if w.lower() not in _TOO_COMMON]
        if words:
            found.append(max(words, key=len))
    return [t for t in found if _DISTINCTIVE.search(t) or len(t) >= _PLAIN_MIN]


def commitments(text: str) -> list[Commitment]:
    """Every named commitment in the OWED sections of ``text``, one per line.

    A line whose identifiers were ALL already claimed by an earlier line is
    skipped: handoffs restate the same tool across sections, and reporting the
    restatement as a second commitment would inflate the denominator this gate
    reports its coverage against.
    """
    found: list[Commitment] = []
    seen: set[str] = set()
    for heading, body in _sections(text):
        if not _is_owed(heading):
            continue
        base = text.count("\n", 0, text.find(body)) + 1 if body else 1
        for i, line in _units(body):
            fresh = tuple(t for t in _tokens_in(line) if t.lower() not in seen)
            if not fresh:
                continue
            seen.update(t.lower() for t in fresh)
            found.append(
                Commitment(
                    tokens=fresh,
                    line=base + i,
                    context=line.strip()[:160],
                    heading=heading,
                )
            )
    return found


@dataclass(frozen=True)
class Dropped:
    """A commitment the new handoff never mentions, in any form."""

    commitment: Commitment
    previous: str


def dropped(previous_text: str, new_text: str, *, previous_name: str) -> list[Dropped]:
    """Commitments in ``previous_text`` that ``new_text`` does not name at all.

    Case-insensitive substring, not word-boundary: a handoff writing
    ``kb-update -- agent-harness-docs`` must satisfy a commitment recorded as
    ``agent-harness-docs``, and a word-boundary match on the hyphenated form
    would refuse it. The looser test is the right direction here — this gate's
    credibility depends on not crying wolf (#145), and a token that appears
    inside a longer name HAS been carried.
    """
    haystack = new_text.lower()
    return [
        Dropped(commitment=c, previous=previous_name)
        for c in commitments(previous_text)
        if not any(t.lower() in haystack for t in c.tokens)
    ]


def previous_handoff(repo_root: Path, target: Path) -> Path | None:
    """The newest handoff older than ``target``, or None if it is the first.

    By mtime, matching `handoff.handoffs`. None is a real answer — the first
    handoff in a fresh clone has nothing to reconcile against — and it maps to a
    reported SKIP, never to a pass: a check that never asked the question is not
    a check that found nothing.
    """
    from kb_setup import handoff

    resolved = target.resolve()
    if not resolved.is_file():
        return None
    cutoff = resolved.stat().st_mtime
    for candidate in handoff.handoffs(repo_root):
        # Strictly OLDER, not merely "not the target". `handoffs` is newest-first,
        # so skipping only the target hands back a handoff written AFTER it
        # whenever an older one is checked explicitly — reconciling forwards, and
        # reporting every item the future added as a loss.
        if candidate.resolve() != resolved and candidate.stat().st_mtime < cutoff:
            return candidate
    return None


def is_commitment(heading: str) -> bool:
    """Public: does this heading carry COMMITMENTS rather than gotchas?

    Exported so the caller can choose the severity without re-deriving the split
    from the two heading tuples — one owner for the classification, which is the
    same reason `check_first.decide` is public.
    """
    return _is_commitment(heading)


@dataclass(frozen=True)
class Reconciliation:
    """What the comparison found, INCLUDING how much it was able to look at.

    `checked` is not bookkeeping. Zero dropped out of zero commitments and zero
    dropped out of twenty render identically as a pass, and the first is a check
    that found no question to ask — an older handoff with no owed section, or one
    whose commitments are all bare prose. Carrying the count is what lets the
    caller say *not verifiable here* instead of *in sync*, which is the same
    distinction `currency` refuses to collapse and the same one this module was
    built because `handoff.check` could not make.
    """

    previous: Path | None
    dropped: list[Dropped]
    checked: int


def reconcile(repo_root: Path, target: Path, text: str) -> Reconciliation:
    """What ``text`` dropped from the handoff before it, and how much was checked.

    A `None` `previous` means there was no earlier handoff — a real answer, and
    the caller must render it as UNVERIFIABLE rather than as a pass: a check that
    never asked the question has not answered it.

    Returns DATA, not `handoff.Finding`s, deliberately. Building them here would
    need `handoff` imported at module scope while `handoff` imports this — a
    cycle, broken only by a function-local import and a `cast` on the way back.
    Handing back the facts and letting the one module that owns `Finding` build
    them costs nothing and leaves the dependency pointing one way.
    """
    previous = previous_handoff(repo_root, target)
    if previous is None:
        return Reconciliation(previous=None, dropped=[], checked=0)
    previous_text = previous.read_text(encoding="utf-8", errors="replace")
    return Reconciliation(
        previous=previous,
        dropped=dropped(previous_text, text, previous_name=previous.name),
        checked=len(commitments(previous_text)),
    )


def summary(found: list[Dropped], *, checked: int, previous: str | None) -> str:
    """The report block, including what was NOT checkable.

    The unchecked count is printed even when nothing was dropped, because a
    silent gate and a gate reporting partial coverage are the two states this
    repo refuses to conflate.
    """
    if previous is None:
        return "reconcile: SKIP — no earlier handoff to reconcile against (this is the first)"
    head = f"reconcile: {len(found)} dropped of {checked} named commitments in {previous}"
    if not found:
        return head + " — every one is named in this handoff"
    lines = [head]
    for d in found:
        named = ", ".join(d.commitment.tokens)
        lines.append(f"  DROPPED  {named}  (under '{d.commitment.heading}')")
        lines.append(f"           was: {d.commitment.context}")
    lines.append(
        "  Each must be CARRIED (restated), DONE (with the commit or issue that "
        "closed it), or DROPPED (with the reason). Naming it is what clears this."
    )
    return "\n".join(lines)
