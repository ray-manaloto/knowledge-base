# Copyright (c) 2026 Raymond Manaloto
"""Second-brain routing seam — record, aggregate, audit verified delegation outcomes.

The Fable-5 architect delegates implementation to codex / antigravity / grok lanes.
This module lets it (1) RECORD a verified outcome per delegation, (2) AGGREGATE those
outcomes deterministically into advisory routing lessons, and (3) AUDIT that every
record is complete ("closed").

Design (see dotfiles `docs/specs/second-brain-design.md`):

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
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from kb_setup.graphify_env import graphify_exe

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
        graphify_exe(repo_root),
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
        (
            f"Deterministic aggregation of verified outcomes. A tag other than `tentative` "
            f"requires >= {MIN_CONSISTENT} one-sided, session-deduplicated votes. This is "
            "ADVISORY over the static orchestrator-routing table — it nudges, never overrides."
        ),
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
    from kb_setup import graphify_health

    graphify_health.require_complete(
        graphify_health.assess(
            graphify_health.GraphifyOperation.REFLECT,
            graphify_health.GraphifyEvidence(
                observed=True,
                reflection_expected=True,
                reflection_produced=out.is_file(),
            ),
        )
    )
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
        [graphify_exe(repo_root), "query", *args, "--graph", str(graph)],
        cwd=repo_root,
        check=False,
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


# --- transcript-mining audit (advisory; the (b) half of §4a-3) -------------
#
# The contract (`validate_record`/`record`) guarantees a record cannot CLOSE
# without its outcome; :func:`audit` catches corrupt or hand-edited records.
# Neither catches the harder gap the design names (§4a-3b, research open-Q #1):
# a delegation that was VERIFIED done but whose outcome was never recorded at
# all. That evidence lives only in the session transcript, so this scanner
# mines it — the same 100%-native capture pattern as dotfiles' command-audit
# (every Agent/Bash call is already in the session JSONL; no logging hook).
#
# It is ADVISORY, never a gate. It runs from a SessionEnd hook — which *cannot*
# block by design (the 104-agent enforcement research was unanimous: a blocking
# hook fires before verification exists, so it structurally cannot capture the
# verdict). The blocking ship-gate stays :func:`audit` (the closed-record
# precondition). Output-only logs cannot perfectly tell "verified but
# unrecorded" from "abandoned / never verified" (~21% miss, open-Q #1), so the
# verdict is GRADUATED by confidence and the low-confidence class is labelled as
# such rather than raised as an alarm.
#
# Delegation signal = an Agent/Task tool_use to an IMPLEMENTATION lane
# (codex/grok implementer, antigravity delegate) — the schema is probe-verified
# (`name:"Agent"`, `input.subagent_type`). Review/research/advisor lanes are
# deliberately excluded: they produce no routing outcome to record. A
# write-capable `codex exec` run through Bash counts too (read-only research
# invocations do not).

#: Most-recent sessions to scan by default (mirrors command-audit's cap).
DEFAULT_SESSION_LIMIT = 50

#: An Agent/Task subagent_type that is an IMPLEMENTATION delegation. `-reviewer`,
#: `-researcher`, `advisor`, and `general-purpose` are NOT — they close no record.
_IMPL_SUBAGENT_RE = re.compile(r"implementer|antigravity-delegate")

#: A write-capable `codex exec` run through Bash (an implementation delegation).
#: Read-only/ephemeral research invocations are excluded — they record no outcome.
_CLI_DELEGATE_RE = re.compile(
    r"\bcodex\s+exec\b.*(?:--full-auto|--sandbox\s+workspace-write)", re.DOTALL
)

#: A record was written this session: `mise run brain-remember` / `brain record`.
_RECORD_RE = re.compile(r"\bbrain[- ](?:remember|record)\b")

#: Verification activity: the gates the architect runs to earn a verdict.
_VERIFY_RE = re.compile(
    r"\bmise\s+run\s+(?:lint|test|verify|brain-audit)\b|\bpytest\b|\bgh\s+pr\s+checks\b"
)


def transcripts_base(env: dict[str, str] | None = None, home: Path | None = None) -> Path:
    """The Claude Code projects dir (env-aware; never hardcoded)."""
    env = env if env is not None else dict(os.environ)
    home = home if home is not None else Path.home()
    config_dir = env.get("CLAUDE_CONFIG_DIR")
    base = Path(config_dir) if config_dir else home / ".claude"
    return base / "projects"


def _encode_cwd(cwd: Path) -> str:
    """Claude Code's project-dir encoding of an absolute path (``/``, ``.`` -> ``-``)."""
    return re.sub(r"[/.]", "-", str(cwd))


def project_transcripts(base: Path, cwd: Path, *, limit: int) -> list[Path]:
    """The ``limit`` most-recent transcript files for ``cwd`` (newest first)."""
    project_dir = base / _encode_cwd(cwd)
    if not project_dir.is_dir():
        return []
    files = [p for p in project_dir.glob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


@dataclass
class _SessionTally:
    """Running per-session counts of the three transcript signals."""

    delegations: int = 0
    records: int = 0
    verifications: int = 0


def _apply_tool_use(block: object, tally: _SessionTally) -> None:
    """Fold one ``tool_use`` block's routing signal into the session tally."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return
    name = block.get("name")
    inp = block.get("input")
    inp = inp if isinstance(inp, dict) else {}
    if name in ("Agent", "Task"):
        sub = inp.get("subagent_type")
        if isinstance(sub, str) and _IMPL_SUBAGENT_RE.search(sub):
            tally.delegations += 1
        return
    if name != "Bash":
        return
    cmd = inp.get("command")
    if not isinstance(cmd, str):
        return
    if _CLI_DELEGATE_RE.search(cmd):
        tally.delegations += 1
    if _RECORD_RE.search(cmd):
        tally.records += 1
    if _VERIFY_RE.search(cmd):
        tally.verifications += 1


def _tally_line(obj: dict[str, object], tallies: dict[str, _SessionTally]) -> None:
    """Fold one assistant transcript line's tool calls into its session tally."""
    if obj.get("type") != "assistant":
        return
    message = obj.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return
    session = str(obj.get("sessionId", "")) or "(unknown)"
    tally = tallies.setdefault(session, _SessionTally())
    for block in content:
        _apply_tool_use(block, tally)


def _session_verdict(t: _SessionTally) -> str:
    """Graduated-confidence verdict for one session (see module docstring)."""
    if t.delegations == 0:
        return "none"  # no implementation delegation — nothing to record
    if t.records >= t.delegations:
        return "recorded"  # a record for every delegation — closed
    if t.records == 0 and t.verifications > 0:
        return "verified-unrecorded"  # THE alarm: verified work, zero records
    if t.verifications > 0:
        return "under-recorded"  # advisory: fewer records than delegations
    return "unverified"  # cannot confirm (abandoned OR logs-missed, open-Q #1)


@dataclass(frozen=True)
class TranscriptAudit:
    """The classified outcome of a transcript scan."""

    #: verdict -> number of sessions
    counts: dict[str, int]
    #: (session, delegations, records, verifications, verdict) for every non-``none`` session
    sessions: list[tuple[str, int, int, int, str]]
    scanned: int


#: verdicts that name a real gap, most-serious first (drives the report ordering).
_FLAGGED = ("verified-unrecorded", "under-recorded", "unverified")


def _scan(paths: list[Path]) -> dict[str, _SessionTally]:
    """Fold every transcript's tool calls into per-session tallies (one pass, defensive)."""
    tallies: dict[str, _SessionTally] = {}
    for path in paths:
        try:
            raw = path.read_text(errors="replace")
        except OSError:
            continue
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                _tally_line(obj, tallies)
    return tallies


def audit_transcripts(paths: list[Path]) -> TranscriptAudit:
    """Tally delegations/records/verifications per session and classify each."""
    tallies = _scan(paths)
    counts: Counter[str] = Counter()
    rows: list[tuple[str, int, int, int, str]] = []
    for session, t in tallies.items():
        verdict = _session_verdict(t)
        counts[verdict] += 1
        if verdict != "none":
            rows.append((session, t.delegations, t.records, t.verifications, verdict))
    order = {v: i for i, v in enumerate((*_FLAGGED, "recorded"))}
    rows.sort(key=lambda r: (order.get(r[4], 99), -r[1]))
    return TranscriptAudit(
        counts=dict(counts),
        sessions=[(s, d, rec, v, verdict) for s, d, rec, v, verdict in rows],
        scanned=len(paths),
    )


def render_transcript_report(result: TranscriptAudit) -> str:
    """Render an advisory markdown report for human review of the routing loop."""
    c = result.counts
    alarm = c.get("verified-unrecorded", 0)
    lines = [
        "# Brain audit — verified delegations missing a routing record",
        "",
        (
            f"Scanned **{result.scanned}** recent session transcript(s). "
            "ADVISORY only — this never blocks (SessionEnd cannot); the ship-gate is "
            "`mise run brain-audit` (the closed-record precondition)."
        ),
        "",
        "| verdict | sessions | meaning |",
        "|---|---:|---|",
        (
            f"| verified-unrecorded | {alarm} | delegated + verified but recorded "
            "NOTHING — record the outcome with `mise run brain-remember` |"
        ),
        (
            f"| under-recorded | {c.get('under-recorded', 0)} | fewer records than "
            "delegations (some may be review lanes — check) |"
        ),
        (
            f"| unverified | {c.get('unverified', 0)} | delegated, no verification seen "
            "— cannot tell abandoned from logs-missed (~21%, open-Q #1) |"
        ),
        f"| recorded | {c.get('recorded', 0)} | a record for every delegation — closed |",
        f"| none | {c.get('none', 0)} | no implementation delegation this session |",
        "",
    ]
    if alarm:
        lines += [f"## 🚨 {alarm} session(s) verified work without recording it", ""]
    flagged = [row for row in result.sessions if row[4] in _FLAGGED]
    if flagged:
        lines += [
            "| session | delegations | records | verifications | verdict |",
            "|---|---:|---:|---:|---|",
            *(
                f"| `{s[:12]}` | {d} | {rec} | {v} | {verdict} |"
                for s, d, rec, v, verdict in flagged
            ),
            "",
        ]
    else:
        lines += ["_No gaps — every delegating session recorded its outcomes._", ""]
    lines += [
        (
            "Record a verified delegation with "
            "`mise run brain-remember -- --task-class T --lane L --effort E "
            "--verdict clean|rework|failed --session S`. See "
            "`docs/specs/second-brain-design.md` §4a-3 and the enforcement research "
            "open-Q #1."
        ),
        "",
    ]
    return "\n".join(lines) + "\n"


def transcript_audit(
    repo_root: Path, *, limit: int = DEFAULT_SESSION_LIMIT, output: Path | None = None
) -> int:
    """Scan this project's recent transcripts for unrecorded verified delegations.

    Always rc 0 — advisory, never a gate. ``--output`` is what the SessionEnd
    hook writes to (``.agent/brain-audit.md``), making the loop recurring rather
    than remember-to-run. No transcripts (e.g. a CI runner) is a clean no-op.
    """
    base = transcripts_base()
    transcripts = project_transcripts(base, repo_root, limit=limit)
    if not transcripts:
        sys.stdout.write(f"brain transcript-audit: no transcripts for {repo_root} under {base}\n")
        return 0
    result = audit_transcripts(transcripts)
    text = render_transcript_report(result)
    if output is None:
        sys.stdout.write(text)
        return 0
    dest = output if output.is_absolute() else repo_root / output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    sys.stdout.write(
        f"brain transcript-audit: wrote {dest} "
        f"({result.counts.get('verified-unrecorded', 0)} verified-unrecorded, "
        f"{result.counts.get('under-recorded', 0)} under-recorded)\n"
    )
    return 0


# --- dispatch --------------------------------------------------------------


def _flag(rest: list[str], name: str, default: str = "") -> str:
    if name in rest and rest.index(name) + 1 < len(rest):
        return rest[rest.index(name) + 1]
    return default


def _record_cmd(repo_root: Path, args: list[str]) -> int:
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


def _transcript_audit_cmd(repo_root: Path, args: list[str]) -> int:
    limit = _flag(args, "--limit")
    out = _flag(args, "--output")
    return transcript_audit(
        repo_root,
        limit=int(limit) if limit.isdigit() else DEFAULT_SESSION_LIMIT,
        output=Path(out) if out else None,
    )


def dispatch(repo_root: Path, rest: list[str]) -> int:
    """Dispatch ``kb-setup brain {query|record|reflect|audit|transcript-audit}``."""
    usage = "kb-setup brain query|record|reflect|audit|transcript-audit"
    if not rest:
        print(usage)
        return 2
    sub, args = rest[0], rest[1:]
    handlers = {
        "query": lambda: query(repo_root, args),
        "record": lambda: _record_cmd(repo_root, args),
        "reflect": lambda: reflect(repo_root),
        "audit": lambda: audit(repo_root),
        "transcript-audit": lambda: _transcript_audit_cmd(repo_root, args),
    }
    handler = handlers.get(sub)
    if handler is None:
        print(f"kb-setup brain: unknown subcommand {sub!r} ({usage})")
        return 2
    return handler()
