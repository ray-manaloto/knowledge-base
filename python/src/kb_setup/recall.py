# Copyright (c) 2026 Raymond Manaloto
"""`kb-recall` — rank work-memory for a natural-language question (knowledge-base#540).

WHY THIS MODULE EXISTS. `mise run kb-remember` writes one file per Q&A outcome
to `graphify-out/memory/` — 364 of them, 1.05 MB, dated 2026-07-22 onward. The
only reader was `graphify reflect`, which folds them into a lessons digest and
cannot answer "what did we already learn about X?" for an arbitrary question.
Issue #540 names the failure this causes: a session re-derives a lesson that is
already on disk, because the only way to find it was to already know its
filename. This module is the missing read path.

WHY CUSTOM CODE IS JUSTIFIED HERE (`use-tool-builtins.md` rules 3/5). `graphify
--help` lists exactly two memory verbs, `save-result` and `reflect`; there is no
`recall` and nothing that ranks a subset of `memory/` against a question. There
is no native mechanism to prefer.

WHAT IS REUSED, AND WHAT IS NOT (a ratified decision, not a preference — see the
U-R9 spec). `graphify.reflect.parse_memory_doc`/`load_memory_docs` are the
frontmatter parser for this exact file format, including the escaped multi-line
`correction` field, and are reused unmodified — writing a second parser for the
same format would be exactly the kind of reinvention `use-tool-builtins.md`
exists to block. `kb_setup.lexical`'s BM25 math (`Index.idf`, `Index.score`,
`tokenize`, `search`) is reused the same way — but this module builds its OWN
`Document`/`Index` instead of calling `lexical.build_index()`. That function's
`INDEXED_FIELDS = ("label", "rationale")` is scoped, by its own docstring, to
what a *graph node* carries; force-fitting a memory record into a
`{label, rationale}` shape would surrender exactly the control over indexed
text this module needs (see below). `lexical.py` itself is not edited — both
`Document` and `Index` are public frozen dataclasses, constructible directly.

THE INDEXED-TEXT DECISION, which the spec required be stated and measured
rather than assumed. `lexical.py`'s `K1` is kept at the literature default
because its own documents are short (~15-50 tokens: a label plus a one-line
summary) and "saturation rarely binds" there. A memory document's `## Answer`
body is an order of magnitude longer (~300-600 tokens, median 2,398 bytes on
disk). This module indexes the WHOLE answer body — plus the `question` and, for
a `corrected` record, the `correction` text — rather than an arbitrary excerpt,
for two reasons found by testing rather than assumed from the constants'
comment:

1. BM25's length normalisation (`B = 0.75`, unmodified) exists precisely to
   compensate for varying document length — that is what `B` is *for*, and
   `lexical.py`'s own docstring notes it already matters there at a 3x length
   spread. A 300-600 token spread is the same mechanism doing more work, not a
   different regime.
2. An arbitrary excerpt (first N characters) would silently exclude the words
   of a lesson that states its point at the end — which is common in this
   corpus's `## Answer` bodies, several of which open with context and land the
   correction in the final sentence. Cutting there would reintroduce exactly
   the false-negative failure mode `probes-need-a-control-arm.md` names for
   this module: a genuinely relevant memory losing on term overlap because its
   matching words were truncated away.

   Measured against the live corpus (`mise run kb-recall -- "<query about a
   known 2026-09-03 memory>"`): full-body indexing surfaces the target record
   at rank 1; K1 saturation is observed to suppress a handful of very-common
   corpus-wide terms (e.g. "graphify", "repo") from dominating a long body,
   which is the desired behaviour, not a defect to correct for.

   If a future corpus growth makes this degenerate (long bodies drowning out
   short, sharply-relevant ones), the fix is a bounded excerpt — stated here so
   the next session does not have to re-derive the same measurement.

OUTCOME AND RECENCY WEIGHTING — ruled by the U-R9 advisor consult
(`.agent/kb/reports/agents/ur9-advisor-recall-transport.md`), not invented here:

- `corrected` weighs *at least as much* as `useful` (123 of 364 records are
  corrections — lessons learned the expensive way, and `remember.py` exists
  precisely because they were the ones getting lost. See `_OUTCOME_WEIGHT`.
- `dead_end` weighs low but is NEVER excluded — a "this did not work" is still
  a lesson. The store holds zero `dead_end` records today, so
  `tests/test_recall.py` carries a synthetic fixture for it; it is not
  reachable from the live corpus.
- Recency reuses the `graphify reflect --half-life-days 30` semantics (a 30-day
  half-life), REIMPLEMENTED rather than importing `graphify.reflect._decay` —
  that name is private (leading underscore) to its own module, and this module
  reuses graphify's PUBLIC surface only (`parse_memory_doc`, `load_memory_docs`
  are public; `_decay` is not a contract graphify has committed to keep
  stable). The formula is two lines and is reproduced verbatim below.
- `--min-corroboration` is deliberately NOT imported as a filter. `reflect`
  needs corroboration before a lesson is trusted for routing; a recall hit is a
  *candidate for the reader to judge*, and requiring two corroborating memories
  would hide exactly the single well-evidenced correction this store exists to
  keep findable.
- **Relevance dominates, WITHIN A STATED BOUND — not unconditionally.** A round-2
  cold review (`.agent/kb/review/reports/review-062ab296…-cold.md`, P1) executed
  the arithmetic this bullet only asserted before: the outcome and recency
  multipliers combine to a worst-case ratio of `1.15 x 1.0 / (0.6 x 0.85) ≈
  2.255x`. That is not a guarantee ordering survives — it is a guarantee ordering
  survives *only where the unweighted BM25 gap already exceeds ~2.255x*. A
  documented, measured, constructed pair whose unweighted gap is ~1.66x (inside
  the band) DOES reorder — a `dead_end`, six-year-stale record loses to a
  `corrected`, same-day one that matches one fewer query term. The correct
  claim, and the one the tests below actually assert: **a lexical gap wider than
  the band survives the multiplier; a gap inside it may not.** See
  `test_no_reorder_when_the_lexical_gap_exceeds_the_multiplier_band` (the outer
  bound, a real earlier fixture already comfortably outside the band even under
  worst-case multiplier extremes) and
  `test_reorder_is_possible_when_the_lexical_gap_is_inside_the_multiplier_band`
  (the inner bound, the constructed counterexample above) in
  `tests/test_recall.py` — together the property, not a comment asserting it.

THE THREE EXIT STATES (`kb_setup.result.Rc`), kept distinct per
`probes-need-a-control-arm.md`: hits found is `Rc.OK`; the store was read and
nothing matched (by filter, or by term overlap) is ALSO `Rc.OK`, but the
message says so explicitly and names how many documents were searched — silence
here is the exact failure that rule exists to stop; the memory directory being
absent or holding no parsable document is `Rc.NOT_RUN` — a request that was
fine and was never actually asked.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from graphify.reflect import load_memory_docs

from kb_setup import lexical
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import NoReturn

#: `--outcome` filter values. `all` is not a real outcome — it means "no filter".
#: `dead_end` IS a real outcome and belongs here — `_OUTCOME_WEIGHT`'s own comment
#: promises "only `--outcome` can exclude it", and a cold review (P2) found the
#: filter refusing exactly the value the ranking comment says it owns. Ranking
#: still never drops a `dead_end` record on its own; `--outcome dead_end` is the
#: reader asking for them explicitly, which is a different action.
_OUTCOME_FILTERS = ("useful", "corrected", "dead_end", "all")

#: Multiplier applied to a document's BM25 score by its recorded outcome.
#: `corrected` >= `useful`, per the U-R9 advisor ruling: a correction is a
#: lesson learned the expensive way and must not rank below an ordinary useful
#: answer. `dead_end` is weighted low but is never dropped from the results —
#: only `--outcome` can exclude it, ranking never does.
_OUTCOME_WEIGHT: dict[str, float] = {"corrected": 1.15, "useful": 1.0, "dead_end": 0.6}
_DEFAULT_OUTCOME_WEIGHT = 1.0

#: Same half-life `graphify reflect --half-life-days 30` uses. Reimplemented
#: rather than imported — see the module docstring for why.
_HALF_LIFE_DAYS = 30.0

#: The floor and ceiling of the recency multiplier. Narrow on purpose: recency
#: "matters but does not dominate" (spec §1), so a six-week-old memory about a
#: still-relevant topic can still win on relevance alone.
_RECENCY_FLOOR = 0.85
_RECENCY_SPAN = 0.15

#: How many characters of the `## Answer` body are shown per hit. This bounds
#: DISPLAY only — see the module docstring for why the INDEXED text stays
#: unbounded.
_EXCERPT_CHARS = 320

#: `--top` default, per spec §3.
_DEFAULT_TOP = 5


@dataclass(frozen=True, slots=True)
class RecallRequest:
    """A validated `kb-recall` invocation."""

    question: str
    top: int
    outcome: str
    since: str | None
    as_json: bool
    memory_dir: str | None


@dataclass(frozen=True, slots=True)
class RecallHit:
    """One memory, ranked and enough of it to act on."""

    path: str
    question: str
    outcome: str
    date: str
    score: float
    excerpt: str
    correction: str | None


@dataclass(frozen=True, slots=True)
class RecallReport:
    """What a `kb-recall` run found, and how much of the store it looked at."""

    hits: list[RecallHit]
    total: int
    """How many memories `graphify.reflect.load_memory_docs` could PARSE.

    Not "how many memories exist in the store" — that claim, which this field
    carried until a round-2 cold review (P3), is more than the module can know:
    `load_memory_docs` silently swallows `OSError`/`UnicodeDecodeError` per file
    and `continue`s, so an unreadable file is counted nowhere. `unparsable`
    below closes that gap.
    """
    unparsable: int
    """`.md` files present on disk that `load_memory_docs` could NOT parse.

    0 on every live run today — the corpus has no such file — but a store that
    silently under-reports its own denominator is exactly the failure
    `probes-need-a-control-arm.md` names, and this module's own docstring
    already promises the searched-count is never silent about what it looked
    at. `render_report` surfaces this only when nonzero.
    """
    searched: int
    """How many memories survived `--outcome`/`--since`, before term matching."""
    outcome: str
    since: str | None
    question: str = field(repr=False)


def _parse_record_date(date_str: str | None) -> datetime | None:
    """A record's `date` field as an aware `datetime`, or `None` if absent/unparsable.

    The ONE place a memory's date string is parsed. Both `_decay` and
    `_filter_records` call this — a round-2 cold review (P2) found the two
    disagreeing about an undated/unparsable record: the recency weight treated
    it as maximally fresh while `--since` treated it as infinitely old, silently
    dropping it. Sharing the parse makes "unparsable ⇒ `None`" a single decision
    both call sites act on consistently, rather than two independent readings of
    the same string.
    """
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _decay(date_str: str | None, now: datetime, half_life_days: float) -> float:
    """Time-decay weight in (0, 1]: halves every `half_life_days`.

    Same semantics as `graphify.reflect._decay` (`reflect.py:275`) — undated or
    unparsable dates keep full weight, a future-dated one is clamped to age 0.
    Reimplemented rather than imported; see the module docstring.
    """
    if half_life_days <= 0:
        return 1.0
    dt = _parse_record_date(date_str)
    if dt is None:
        return 1.0
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


def _weight(record: dict[str, object], now: datetime) -> float:
    """The outcome-and-recency multiplier applied to one record's BM25 score."""
    outcome = str(record.get("outcome") or "")
    outcome_w = _OUTCOME_WEIGHT.get(outcome, _DEFAULT_OUTCOME_WEIGHT)
    date_str = str(record.get("date") or "") or None
    recency_w = _RECENCY_FLOOR + _RECENCY_SPAN * _decay(date_str, now, _HALF_LIFE_DAYS)
    return outcome_w * recency_w


class _ArgumentError(Exception):
    """Raised by `_NonExitingParser.error` instead of exiting the process."""


class _NonExitingParser(argparse.ArgumentParser):
    """An `ArgumentParser` that reports a malformed flag instead of exiting.

    Stock `argparse` calls `self.error()` for a malformed flag — e.g. `--top`
    with no value — which prints a usage banner to stderr and calls
    `sys.exit(2)`. A round-2 cold review (measured: `kb-recall q --top` exits 2
    with a usage banner on stderr) found this contradicts `check_recall`'s own
    docstring, "Returns, never raises, PRINTS NOTHING" — every OTHER malformed
    request in this module returns an `Err` through the ordinary `Result` path;
    this was the one that bypassed it via `SystemExit`. Overriding `error()` to
    raise instead keeps `check_recall` in sole control of both the message and
    whether anything is printed.
    """

    def error(self, message: str) -> NoReturn:
        raise _ArgumentError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _NonExitingParser(prog="kb-recall", add_help=False)
    parser.add_argument("question", nargs="?")
    parser.add_argument("--top", default=str(_DEFAULT_TOP))
    parser.add_argument("--outcome", default="all")
    parser.add_argument("--since", default=None)
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--memory-dir", dest="memory_dir", default=None)
    return parser


def _parse_top(raw: str) -> int | Err:
    """`--top` as a positive int, or the `Err` naming what was wrong with it."""
    try:
        top = int(raw)
    except ValueError:
        return Err(f"--top must be an integer (got {raw!r})", rc=Rc.BAD_REQUEST)
    if top < 1:
        return Err(f"--top must be at least 1 (got {top})", rc=Rc.BAD_REQUEST)
    return top


def _validate_flags(opts: argparse.Namespace, unknown: list[str]) -> Err | None:
    """The flag-shape checks that do not need a converted value. `None` when clean."""
    if unknown:
        return Err(f"unknown argument(s): {' '.join(unknown)}", rc=Rc.BAD_REQUEST)
    if not opts.question or not opts.question.strip():
        return Err(
            'a question is required: mise run kb-recall -- "<question>"',
            rc=Rc.BAD_REQUEST,
        )
    if opts.outcome not in _OUTCOME_FILTERS:
        return Err(
            f"--outcome must be one of {', '.join(_OUTCOME_FILTERS)} (got {opts.outcome!r})",
            rc=Rc.BAD_REQUEST,
        )
    if opts.since is not None:
        try:
            date.fromisoformat(opts.since)
        except ValueError:
            return Err(f"--since must be YYYY-MM-DD (got {opts.since!r})", rc=Rc.BAD_REQUEST)
    return None


def check_recall(argv: Sequence[str]) -> Result[RecallRequest]:
    """Validate a `kb-recall` request. Returns, never raises, PRINTS NOTHING."""
    try:
        opts, unknown = _parser().parse_known_args(list(argv))
    except _ArgumentError as exc:
        return Err(str(exc), rc=Rc.BAD_REQUEST)

    bad = _validate_flags(opts, unknown)
    if bad is not None:
        return bad

    top = _parse_top(opts.top)
    if isinstance(top, Err):
        return top

    return Ok(
        RecallRequest(
            question=opts.question,
            top=top,
            outcome=opts.outcome,
            since=opts.since,
            as_json=opts.as_json,
            memory_dir=opts.memory_dir,
        )
    )


def _since_ok(record: dict[str, object], since_dt: datetime) -> bool:
    """Whether `record` survives `--since`.

    A round-2 cold review (P2) found `--since` doing a STRING comparison
    (`"2026-9-3" >= "2026-10-01"` is `True` lexically, so an unpadded date from
    BEFORE the cutoff survived it), and found it silently dropping every undated
    record — the opposite of `_decay`'s "undated keeps full weight". Both are
    fixed by routing through `_parse_record_date`, the same parser `_decay`
    uses: an unparsable/absent date is treated as "no information", which keeps
    the record rather than excluding it — consistent with `_decay` giving it
    full recency weight rather than zero.
    """
    dt = _parse_record_date(str(record.get("date") or "") or None)
    if dt is None:
        return True
    return dt >= since_dt


def _filter_records(
    records: list[dict[str, object]], outcome: str, since: str | None
) -> list[dict[str, object]]:
    """Apply `--outcome`/`--since`. Neither ranks — both only narrow the pool."""
    out = records
    if outcome != "all":
        out = [r for r in out if r.get("outcome") == outcome]
    if since is not None:
        # `since` is already validated as YYYY-MM-DD by `_validate_flags`.
        since_dt = datetime.combine(date.fromisoformat(since), datetime.min.time(), tzinfo=UTC)
        out = [r for r in out if _since_ok(r, since_dt)]
    return out


#: The exact byte sequences `graphify.ingest.save_query_result` writes
#: immediately after its own `## Outcome`/`## Source Nodes` headings
#: (`sources/graphify/graphify/ingest.py:329-336`: `body_lines += ["", "##
#: Outcome", ""]` then `- Signal: …` and/or `- Correction: …`; `body_lines +=
#: ["", "## Source Nodes", ""]` then `- <node>` bullets). Matching on the
#: heading PLUS its first bullet — not the heading alone — is load-bearing: a
#: round-2 cold review found `_answer_body` truncating 51 of 364 live records
#: (23.5% of all answer bytes) because an answer can legitimately contain its
#: OWN `## Outcome`-titled subsection as prose (measured: 3 live records do,
#: as a narrative retrospective), and a `correction` value written raw into the
#: body can itself contain markdown headings (measured: at least one live
#: record's correction is a multi-paragraph write-up with nested `## `
#: headings) — so neither "first `## `" nor "first `## Outcome`" is a safe
#: terminator. The first bullet is the writer's own structural signature and
#: cannot appear by coincidence in ordinary answer prose describing the same
#: heading text.
_FOOTER_MARKERS: tuple[str, ...] = (
    "\n## Outcome\n\n- Signal:",
    "\n## Outcome\n\n- Correction:",
    "\n## Source Nodes\n\n- ",
)


def _answer_body(text: str) -> str:
    """The text between the `## Answer` heading and graphify's OWN footer (or EOF).

    Mirrors the shape `graphify.ingest.save_query_result` writes: frontmatter, a
    `# Q: ...` title, then `## Answer`, then that function's own `## Outcome` /
    `## Source Nodes` footer section(s) — identified by `_FOOTER_MARKERS`, the
    earliest of which wins (only one should normally be present; taking the
    minimum is robust if more than one marker string appears). Re-measured
    against every one of the 364 live files under `graphify-out/memory/` after
    this fix: **0 truncated, 0 bytes lost** (was 51 files / 154,261 bytes with
    the naive "next `## ` heading" rule this replaces — see the P1 finding in
    `.agent/kb/review/reports/review-062ab296…-cold.md`). A doc with no
    `## Answer` heading (foreign markdown that slipped past
    `parse_memory_doc`'s frontmatter check) contributes no body text rather
    than raising — it still indexes on its `question` alone. A doc whose
    `## Answer` heading is present but none of the footer markers are found
    (foreign or hand-edited markdown) keeps its whole remaining text as body
    rather than guessing at a boundary that is not there.
    """
    marker = "\n## Answer"
    start = text.find(marker)
    if start == -1:
        return ""
    remainder = text[start + len(marker) :]
    end = None
    for footer in _FOOTER_MARKERS:
        idx = remainder.find(footer)
        if idx != -1 and (end is None or idx < end):
            end = idx
    body = remainder if end is None else remainder[:end]
    return body.strip()


def _indexed_text(record: dict[str, object], body: str) -> str:
    """What gets tokenized for one memory.

    See the module docstring for why the body is included whole rather than
    as a bounded excerpt.
    """
    parts = [str(record.get("question") or ""), body]
    if record.get("outcome") == "corrected":
        parts.append(str(record.get("correction") or ""))
    return " ".join(p for p in parts if p)


def _build_index(
    records: list[dict[str, object]], memory_dir: Path
) -> tuple[lexical.Index, dict[str, dict[str, object]], dict[str, str], int]:
    """Index `records` for BM25 search, returning the index, lookups, and a skip count.

    Deliberately NOT `lexical.build_index()` — see the module docstring: that
    function's field scope is locked to graph nodes, and this module needs its
    own field extraction (`question` + the `## Answer` body, not `label` +
    `rationale`). This is `build_index`'s own aggregation loop
    (`lexical.py:196-220`), re-derived over memory records rather than nodes,
    reusing only the public `Document`/`Index` shapes and `lexical.tokenize`.

    The 4th return value is how many records were skipped because their file
    could not be RE-read here. `graphify.reflect.load_memory_docs` already
    caught this once — a round-2 cold review constructed a case (a fixture
    file removed between `load_memory_docs` and this second read) that raised
    `FileNotFoundError` straight through `run_recall`, contradicting its own
    "Returns, never raises" docstring and, worse, dropping the exact
    `(OSError, UnicodeDecodeError)` protection `load_memory_docs` deliberately
    applies to its own read of these same files
    (`sources/graphify/graphify/reflect.py:140-147`). Skipping here rather
    than raising keeps that protection intact on the second read too.
    """
    documents: list[lexical.Document] = []
    document_frequency: dict[str, int] = {}
    by_path: dict[str, dict[str, object]] = {}
    excerpts: dict[str, str] = {}
    skipped = 0
    for record in records:
        path_name = str(record.get("_path") or "")
        if not path_name:
            continue
        try:
            text = (memory_dir / path_name).read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            skipped += 1
            continue
        body = _answer_body(text)
        terms_list = lexical.tokenize(_indexed_text(record, body))
        if not terms_list:
            continue
        terms = Counter(terms_list)
        documents.append(
            lexical.Document(
                node_id=path_name,
                label=str(record.get("question") or ""),
                source_file=path_name,
                terms=terms,
                length=sum(terms.values()),
            )
        )
        for term in terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1
        by_path[path_name] = record
        excerpts[path_name] = body

    total_length = sum(d.length for d in documents)
    index = lexical.Index(
        documents=tuple(documents),
        document_frequency=document_frequency,
        average_length=total_length / len(documents) if documents else 0.0,
    )
    return index, by_path, excerpts, skipped


def check_memory_dir(memory_dir: Path) -> Result[list[dict[str, object]]]:
    """Load the memory store, or `NOT_RUN` if there is nothing to search.

    Returns, never raises, PRINTS NOTHING. Mirrors `remember.check_memory_lessons`:
    an absent directory and an empty one collapse to the same `NOT_RUN` — both
    mean "the question was never actually asked" — because
    `graphify.reflect.load_memory_docs` already returns `[]` for both cases
    and there is no distinguishing them without a second, redundant `is_dir()`
    check that would only ever fire on the directory-absent half.
    """
    records = load_memory_docs(memory_dir)
    if not records:
        return Err(f"no memories under {memory_dir} — nothing was searched", rc=Rc.NOT_RUN)
    return Ok(records)


def run_recall(request: RecallRequest, memory_dir: Path) -> Result[RecallReport]:
    """Rank the memory store against `request.question`. Returns, never raises."""
    loaded = check_memory_dir(memory_dir)
    if isinstance(loaded, Err):
        return loaded
    if isinstance(loaded, External):  # pragma: no cover - check_memory_dir never returns one
        return loaded
    records = loaded.value
    total = len(records)
    # `load_memory_docs` silently drops a file it cannot parse — a round-2 cold
    # review (P3) found `total` claiming to count "how many memories exist in
    # the store" when it only ever counted what got parsed. The real file count
    # on disk is the honest denominator; the gap between the two is surfaced as
    # `unparsable` rather than absorbed into a claim `total` cannot support.
    real_total = sum(1 for _ in memory_dir.glob("*.md"))
    unparsable = max(0, real_total - total)

    filtered = _filter_records(records, request.outcome, request.since)
    if not filtered:
        return Ok(
            RecallReport(
                hits=[],
                total=real_total,
                unparsable=unparsable,
                searched=0,
                outcome=request.outcome,
                since=request.since,
                question=request.question,
            )
        )

    index, by_path, excerpts, skipped_on_reread = _build_index(filtered, memory_dir)
    unparsable += skipped_on_reread
    hits = lexical.search(index, request.question)

    now = datetime.now(UTC)
    weighted = [
        (hit.score * _weight(by_path[hit.node_id], now), position, hit)
        for position, hit in enumerate(hits)
    ]
    weighted.sort(key=lambda row: (-row[0], row[1]))

    ranked: list[RecallHit] = []
    for weighted_score, _, hit in weighted[: request.top]:
        record = by_path[hit.node_id]
        outcome = str(record.get("outcome") or "")
        # A `corrected` record with no `correction` field must render as "no
        # correction" (`None`), not the literal string `"None"` from
        # `str(None)` — a round-2 cold review (P3) found the earlier form doing
        # exactly that, unreachable on the live store today (`kb-remember`
        # refuses `--outcome corrected` with no correction) but reachable from
        # any other writer, and the sibling `_indexed_text` already got this
        # right with `or ""` 100 lines above.
        raw_correction = record.get("correction")
        ranked.append(
            RecallHit(
                path=hit.node_id,
                question=str(record.get("question") or ""),
                outcome=outcome,
                date=str(record.get("date") or ""),
                score=round(weighted_score, 6),
                excerpt=excerpts.get(hit.node_id, "")[:_EXCERPT_CHARS],
                correction=(
                    str(raw_correction) if outcome == "corrected" and raw_correction else None
                ),
            )
        )

    return Ok(
        RecallReport(
            hits=ranked,
            total=real_total,
            unparsable=unparsable,
            searched=len(filtered),
            outcome=request.outcome,
            since=request.since,
            question=request.question,
        )
    )


def _unparsable_suffix(report: RecallReport) -> str:
    """The " (N file(s) present but unreadable)" suffix, or "" when unparsable is 0."""
    if not report.unparsable:
        return ""
    noun = "file" if report.unparsable == 1 else "files"
    return f" ({report.unparsable} {noun} present but unreadable)"


def render_report(report: RecallReport) -> str:
    """The operator-facing rendering of a `RecallReport`."""
    if not report.hits:
        return (
            f'[recall] "{report.question}" — 0 of {report.searched} matched '
            f"(searched {report.searched} of {report.total} total memories; "
            f"outcome={report.outcome}, since={report.since or 'any'})"
            f"{_unparsable_suffix(report)}"
        )
    lines = [
        (
            f'[recall] "{report.question}" — {len(report.hits)} of {report.searched} '
            f"matched ({report.total} total memories in the store)"
            f"{_unparsable_suffix(report)}"
        )
    ]
    for i, hit in enumerate(report.hits, start=1):
        lines.append(f"  {i}. [{hit.outcome}] {hit.date}  score={hit.score}  {hit.path}")
        lines.append(f"     Q: {hit.question}")
        if hit.excerpt:
            lines.append(f"     {hit.excerpt}")
        if hit.correction:
            lines.append(f"     correction: {hit.correction}")
    return "\n".join(lines)


def render_json(report: RecallReport) -> str:
    """The `--json` rendering of a `RecallReport`."""
    payload = {
        "question": report.question,
        "total": report.total,
        "unparsable": report.unparsable,
        "searched": report.searched,
        "outcome": report.outcome,
        "since": report.since,
        "hits": [asdict(hit) for hit in report.hits],
    }
    return json.dumps(payload, indent=2)


def main(repo_root: Path, argv: Sequence[str] = ()) -> int:
    """Rank the work-memory store against a question. Renders, then converts."""
    args = list(argv)
    validated = check_recall(args)
    if isinstance(validated, Err):
        print(f"[recall] refusing — {validated.message}")
        return exit_code(validated)
    if isinstance(validated, External):  # pragma: no cover - check_recall never returns one
        return exit_code(validated)

    request = validated.value
    memory_dir = (
        Path(request.memory_dir) if request.memory_dir else repo_root / "graphify-out" / "memory"
    )

    result = run_recall(request, memory_dir)
    if isinstance(result, Err):
        print(f"[recall] {result.message}")
        return exit_code(result)
    if isinstance(result, External):  # pragma: no cover - run_recall never returns one
        return exit_code(result)

    report = result.value
    print(render_json(report) if request.as_json else render_report(report))
    return exit_code(result)
