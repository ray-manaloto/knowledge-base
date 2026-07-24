"""Second-brain routing seam — record, aggregate, audit verified delegation outcomes.

The Fable-5 architect delegates implementation to codex / antigravity / grok lanes.
This module lets it (1) RECORD a verified outcome per delegation, (2) AGGREGATE those
outcomes deterministically into advisory routing lessons, and (3) AUDIT that every
record is complete ("closed").

Design (see dotfiles `.omc/specs/second-brain-design.md`):

* Store — REUSE ``graphify save-result`` (no new store). Outcomes land in
  ``brain/graphify-out/memory/*.md``; this module derives (task_class, lane, verdict,
  session) from that frontmatter. Verdict vocab (clean / rework / failed) maps onto
  save-result's fixed vocab (useful / corrected / dead_end).
* Contract — a record cannot be written without its outcome field. ``record`` refuses
  (rc=2) any delegation missing task_class, lane, effort or verdict. This is the
  research-backed enforcement: the verdict is a post-verification judgment, so the
  guarantee is "you cannot close the record without it", not a pre-execution block.
* Verdict is computed HERE, deterministically — never by an LLM (LLMs drift aggregating
  many candidates). It is ADVISORY over the static ``orchestrator-routing`` table: a
  hint counts only when a (task_class x lane) cell has >= MIN_CONSISTENT one-sided,
  SESSION-DEDUPLICATED outcomes, so a single noisy result — or one bad spec producing a
  burst of reworks in one session — can never flip a route.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# --- vocab -----------------------------------------------------------------

VERDICTS = ("clean", "rework", "failed")
#: routing verdict -> save-result's fixed outcome vocab
VERDICT_TO_OUTCOME = {"clean": "useful", "rework": "corrected", "failed": "dead_end"}
OUTCOME_TO_VERDICT = {v: k for k, v in VERDICT_TO_OUTCOME.items()}
#: verdict polarity: clean is good, rework/failed are bad
GOOD_VERDICTS = frozenset({"clean"})

#: a (task_class x lane) cell needs this many one-sided, session-deduped votes
#: before its tag is anything other than "tentative". Stricter than graphify's
#: native reflect overlay (min-corroboration 2) — routing must not flip on noise.
MIN_CONSISTENT = 3

_BRAIN = "brain"
_MEMORY_SUBPATH = "graphify-out/memory"
_GRAPH_SUBPATH = "graphify-out/graph.json"
_LESSONS_SUBPATH = "graphify-out/reflections/ROUTING-LESSONS.md"


def _memory_dir(repo_root: Path) -> Path:
    return repo_root / _BRAIN / _MEMORY_SUBPATH


def _graph_path(repo_root: Path) -> Path:
    return repo_root / _BRAIN / _GRAPH_SUBPATH


# --- the record (contract lives here) --------------------------------------


@dataclass(frozen=True)
class Outcome:
    """One verified delegation outcome — the closed record."""

    task_class: str
    lane: str
    verdict: str
    session: str


@dataclass(frozen=True)
class RecordRequest:
    """The fields a delegation must supply to close a routing-outcome record."""

    task_class: str
    lane: str
    effort: str
    verdict: str
    session: str
    note: str = ""


def validate_record(req: RecordRequest) -> str | None:
    """Return an error string if the record cannot be closed, else None.

    The contract: a delegation record cannot close without every field, and the
    verdict must be a real verdict. This is the enforceable half of "hard".
    """
    missing = [
        name
        for name, value in (
            ("task-class", req.task_class),
            ("lane", req.lane),
            ("effort", req.effort),
            ("verdict", req.verdict),
            ("session", req.session),
        )
        if not value
    ]
    if missing:
        return f"record cannot close: missing {', '.join(missing)}"
    if req.verdict not in VERDICTS:
        return f"unknown verdict {req.verdict!r} (expected one of {', '.join(VERDICTS)})"
    return None


def record(repo_root: Path, req: RecordRequest) -> int:
    """Record one verified outcome via ``graphify save-result``; rc 0/1/2.

    rc=2 when the contract rejects the record (a missing field), rc=1 when the
    underlying save-result call fails, rc=0 on success.
    """
    err = validate_record(req)
    if err is not None:
        print(f"[brain] {err}", flush=True)
        return 2

    memory = _memory_dir(repo_root)
    memory.mkdir(parents=True, exist_ok=True)
    question = f"route {req.task_class} via {req.lane} [session={req.session}]"
    answer = (
        f"lane={req.lane}; task_class={req.task_class}; effort={req.effort}; verdict={req.verdict}"
    )
    if req.note:
        answer += f"; note={req.note}"
    cmd = [
        "graphify",
        "save-result",
        "--question",
        question,
        "--answer",
        answer,
        "--type",
        "routing-outcome",
        "--nodes",
        f"lane-{req.lane}",
        f"task-class-{req.task_class}",
        "--outcome",
        VERDICT_TO_OUTCOME[req.verdict],
        "--memory-dir",
        str(memory),
    ]
    proc = subprocess.run(cmd, cwd=repo_root, check=False)
    if proc.returncode != 0:
        print(f"[brain] save-result failed (rc={proc.returncode})", flush=True)
        return 1
    print(
        f"[brain] recorded: {req.task_class} -> {req.lane} = {req.verdict} (session {req.session})",
        flush=True,
    )
    return 0


# --- reading the store -----------------------------------------------------

_SESSION_RE = re.compile(r"session=([^\]\s]+)")


def _parse_frontmatter(text: str) -> dict[str, object]:
    """Parse the simple ``---`` YAML frontmatter save-result writes (JSON-scalar values)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, object] = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        raw = raw.strip()
        try:
            fields[key.strip()] = json.loads(raw)
        except ValueError:  # json.JSONDecodeError is a ValueError subclass
            fields[key.strip()] = raw.strip('"')
    return fields


def _outcome_from_fields(fields: dict[str, object]) -> Outcome | None:
    """Derive an :class:`Outcome` from parsed frontmatter, or None if not a routing record."""
    nodes = fields.get("source_nodes")
    outcome = fields.get("outcome")
    question = fields.get("question")
    if not isinstance(nodes, list) or not isinstance(outcome, str):
        return None
    lane = next(
        (n[len("lane-") :] for n in nodes if isinstance(n, str) and n.startswith("lane-")), ""
    )
    task_class = next(
        (
            n[len("task-class-") :]
            for n in nodes
            if isinstance(n, str) and n.startswith("task-class-")
        ),
        "",
    )
    verdict = OUTCOME_TO_VERDICT.get(outcome, "")
    session_match = _SESSION_RE.search(question) if isinstance(question, str) else None
    session = session_match.group(1) if session_match else ""
    if not (lane and task_class and verdict and session):
        return None
    return Outcome(task_class=task_class, lane=lane, verdict=verdict, session=session)


def parse_outcome(path: Path) -> Outcome | None:
    """Derive an :class:`Outcome` from a save-result memory file, or None if not routing."""
    return _outcome_from_fields(_parse_frontmatter(path.read_text(encoding="utf-8")))


def load_outcomes(repo_root: Path) -> list[Outcome]:
    """Load every parseable routing outcome from the brain memory store."""
    memory = _memory_dir(repo_root)
    if not memory.is_dir():
        return []
    outcomes = [parse_outcome(p) for p in sorted(memory.glob("*.md"))]
    return [o for o in outcomes if o is not None]


# --- the deterministic aggregator (the core logic) -------------------------


@dataclass(frozen=True)
class Lesson:
    """The advisory verdict for one (task_class x lane) cell."""

    task_class: str
    lane: str
    tag: str  # preferred | avoid | contested | tentative
    good: int
    bad: int


def aggregate(outcomes: list[Outcome]) -> list[Lesson]:
    """Deterministically reduce outcomes to per-cell advisory lessons.

    Session-dedup: within one session, same-cell same-polarity outcomes collapse to a
    single vote (one bad spec producing a burst of reworks is one vote, not N). A cell
    is decided only at >= MIN_CONSISTENT one-sided votes; conflicting evidence is
    contested; anything thinner is tentative.
    """
    # (session, task_class, lane, is_good) -> one vote after dedup
    deduped: set[tuple[str, str, str, bool]] = {
        (o.session, o.task_class, o.lane, o.verdict in GOOD_VERDICTS) for o in outcomes
    }
    tally: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"good": 0, "bad": 0})
    for _session, task_class, lane, is_good in deduped:
        tally[(task_class, lane)]["good" if is_good else "bad"] += 1

    lessons: list[Lesson] = []
    for (task_class, lane), counts in tally.items():
        good, bad = counts["good"], counts["bad"]
        if good and bad:
            tag = "contested"
        elif good >= MIN_CONSISTENT:
            tag = "preferred"
        elif bad >= MIN_CONSISTENT:
            tag = "avoid"
        else:
            tag = "tentative"
        lessons.append(Lesson(task_class=task_class, lane=lane, tag=tag, good=good, bad=bad))
    # stable, human-friendly ordering: task-class then lane
    return sorted(lessons, key=lambda le: (le.task_class, le.lane))


def render_lessons(lessons: list[Lesson]) -> str:
    """Render lessons as a readable markdown table.

    Written to the gitignored ``reflections/`` dir — regenerated by each reflect, not
    committed (the outcome records under ``memory/`` are the committed source).
    """
    lines = [
        "# Routing lessons (advisory)",
        "",
        f"Deterministic aggregation of verified outcomes. A tag other than `tentative` "
        f"requires >= {MIN_CONSISTENT} one-sided, session-deduplicated votes. This is "
        "ADVISORY over the static orchestrator-routing table — it nudges, never overrides.",
        "",
        "| task-class | lane | tag | clean | rework/failed |",
        "| --- | --- | --- | --: | --: |",
    ]
    lines.extend(
        f"| {le.task_class} | {le.lane} | {le.tag} | {le.good} | {le.bad} |" for le in lessons
    )
    if not lessons:
        lines.append("| _(no outcomes recorded yet)_ | | | | |")
    lines.append("")
    return "\n".join(lines)


def reflect(repo_root: Path) -> int:
    """Aggregate outcomes deterministically into ROUTING-LESSONS.md.

    We do NOT call graphify's native ``reflect`` here: its overlay uses a different,
    weaker threshold (min-corroboration 2, recency-weighted) than the routing spec's
    >= MIN_CONSISTENT + session-dedup, and it defaults its output to the ROOT
    graphify-out. A conflicting second signal would only confuse routing, so this
    deterministic aggregator is the single source of truth for routing lessons.
    """
    outcomes = load_outcomes(repo_root)
    lessons = aggregate(outcomes)
    out = repo_root / _BRAIN / _LESSONS_SUBPATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_lessons(lessons), encoding="utf-8")
    decided = [le for le in lessons if le.tag != "tentative"]
    print(
        f"[brain] {len(outcomes)} outcomes -> {len(lessons)} cells "
        f"({len(decided)} decided) -> {out.relative_to(repo_root)}",
        flush=True,
    )
    return 0


# --- the audit (ship-gate) -------------------------------------------------


def query(repo_root: Path, args: list[str]) -> int:
    """Query the brain vault graph. Wraps ``graphify query`` with the QUESTION FIRST.

    graphify's query parser only honours ``--graph`` when the positional question
    precedes it; mise appends user args last, so a task with ``--graph`` first would
    silently hit the default aggregate graph. This wrapper guarantees the order.
    """
    graph = _graph_path(repo_root)
    if not graph.is_file():
        rel = graph.relative_to(repo_root)
        print(f"[brain] no vault graph at {rel} — run `mise run brain-update`")
        return 1
    if not args:
        print('kb-setup brain query "<question>" [--budget N]')
        return 2
    proc = subprocess.run(
        ["graphify", "query", *args, "--graph", str(graph)], cwd=repo_root, check=False
    )
    return proc.returncode


def audit(repo_root: Path) -> int:
    """Fail (rc=1) if any recorded outcome is not a closed record.

    The contract already refuses to WRITE an incomplete record, so this catches
    corruption or hand-edits: a memory file that looks like a routing outcome
    (has ``routing-outcome`` type or lane-/task-class- nodes) but does not parse to
    a complete :class:`Outcome`. Transcript-mining for delegations that were run but
    never recorded is a documented follow-up (needs the delegation event stream).
    """
    memory = _memory_dir(repo_root)
    if not memory.is_dir():
        print("[brain] audit: no outcomes yet — ok")
        return 0
    unclosed: list[str] = []
    for path in sorted(memory.glob("*.md")):
        fields = _parse_frontmatter(path.read_text(encoding="utf-8"))
        nodes = fields.get("source_nodes")
        looks_routing = fields.get("type") == "routing-outcome" or (
            isinstance(nodes, list)
            and any(isinstance(n, str) and n.startswith(("lane-", "task-class-")) for n in nodes)
        )
        if looks_routing and _outcome_from_fields(fields) is None:
            unclosed.append(path.name)
    if unclosed:
        print(f"[brain] audit FAIL: {len(unclosed)} unclosed routing record(s):", flush=True)
        for name in unclosed:
            print(f"  - {name}", flush=True)
        return 1
    print(f"[brain] audit ok: {len(list(memory.glob('*.md')))} record(s), all closed")
    return 0


# --- dispatch --------------------------------------------------------------


def _flag(rest: list[str], name: str, default: str = "") -> str:
    if name in rest and rest.index(name) + 1 < len(rest):
        return rest[rest.index(name) + 1]
    return default


def dispatch(repo_root: Path, rest: list[str]) -> int:
    """Dispatch ``kb-setup brain {record|reflect|audit}``."""
    if not rest:
        print("kb-setup brain query|record|reflect|audit")
        return 2
    sub, args = rest[0], rest[1:]
    if sub == "query":
        return query(repo_root, args)
    if sub == "record":
        return record(
            repo_root,
            RecordRequest(
                task_class=_flag(args, "--task-class"),
                lane=_flag(args, "--lane"),
                effort=_flag(args, "--effort"),
                verdict=_flag(args, "--verdict"),
                session=_flag(args, "--session"),
                note=_flag(args, "--note"),
            ),
        )
    if sub == "reflect":
        return reflect(repo_root)
    if sub == "audit":
        return audit(repo_root)
    print(f"kb-setup brain: unknown subcommand {sub!r} (query | record | reflect | audit)")
    return 2
