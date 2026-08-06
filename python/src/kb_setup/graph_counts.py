"""Count continuity across `graph.json` writers (#191).

Three times running, the only thing that noticed a graph losing nodes was a
human subtracting two numbers printed one line apart:

| when | what was lost | who noticed |
|---|---|---|
| the #186 round | 11 hyperedges -> 8 on a rebuild | a session diffing rebuild against incremental |
| the #185 round | 69 nodes rebuilding, 13 incrementally — opposite ways | `[merge]` arithmetic |
| PR #197 (`d5da30c`) | 72 nodes of an UNRELATED source | `[merge]`-line arithmetic, by eye |

Every gate was green each time. `assert_composition` checks id depth and
dangling members, not disappearance; the review lanes read the chunk as data;
`kb-build` exits 0. And graphify's own #479 shrink guard is structurally unable
to see it — `build_merge` reassigns `existing_nodes` to the POST-prune list
(`build.py:1536`) before comparing `len(existing_nodes)` against the new count
(`:1650`), so a supersession is subtracted from both sides of the inequality
that exists to catch it.

**Why a ledger rather than a second parse.** The honest way to ask "how many
nodes did this write remove" is to count them before and after. `graph.json` is
several hundred MB and `kb_setup.insights` measures peak RSS at ~3.7x file size
for one live parse, so a second one to obtain a single integer is the most
expensive possible way to learn it. Every writer that could answer for free
already does: `_merge_docs.py` holds `G` in memory, and
`graph_checks.assert_composition` parses the file it just produced anyway. So
they record; the next writer reads.

**A recorded count is only usable if the graph has not moved since.** The record
carries the artifact fingerprint (`size:mtime_ns`, the same identity
`currency.sync` uses) observed at write time. A reader whose current fingerprint
disagrees gets `None` — *cannot check* — never a number. That is the third state
this repo insists on keeping distinct: a rebuild that bypassed a tracked writer
must report unknown rather than a confidently wrong delta, exactly as
`kb-currency-check` reports *version unknown* rather than a false green.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import atomic

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Sits beside `.currency-stamp.json` in the derived tree, and is derived like
#: it: gitignored, rebuilt by whichever writer runs next. Nothing reads it as a
#: gate — an absent or stale ledger degrades every check here to "unknown",
#: which is why a fresh clone needs no seeding step.
_LEDGER = "graphify-out/.graph-counts.json"

#: Every count worth carrying, in the order a report prints them. Node count is
#: the one the three measured losses moved, but hyperedges moved on their own in
#: the #186 round (11 -> 8 with the node count untouched), so a node-only ledger
#: would have been blind to the very first instance.
_FIELDS = ("nodes", "edges", "hyperedges", "members")


def _fingerprint(graph_path: Path) -> str:
    """`<size>:<mtime_ns>` for the graph, or `""` when it is absent/unreadable.

    Deliberately the same cheap stat `currency.sync.artifact_fingerprint` uses,
    and imported from there rather than re-derived so the two can never drift
    into disagreeing about what "the graph moved" means.
    """
    from kb_setup.currency.sync import artifact_fingerprint

    return artifact_fingerprint(graph_path)


def ledger_path(repo_root: Path) -> Path:
    """Where the counts ledger lives for this repo."""
    return repo_root / _LEDGER


def record(repo_root: Path, graph_path: Path, counts: Mapping[str, object], *, tag: str) -> None:
    """Record `counts` for the graph AS IT IS ON DISK RIGHT NOW.

    Call AFTER the write, never before: the fingerprint captured here is what a
    later reader compares against to decide whether these counts still describe
    the file. Recording pre-write bytes would certify counts against an artifact
    that no longer exists.

    `counts` is `Mapping[str, object]`, NOT `Mapping[str, int]`, and the widening
    is the honest annotation rather than a concession. This is called with
    whatever a foreign-interpreter subprocess wrote to a JSON file — the values
    are untrusted by construction, and an annotation promising `int` was a type
    that LIED: it told every reader the validation had already happened, which is
    precisely why the `int()` conversion below was written without a guard and
    crashed a successful merge on `{"nodes": "many"}`.

    Best-effort by design — a ledger that cannot be written must not fail an
    otherwise-successful build. The cost of failure is one "cannot check" at the
    next writer, which is the same state a fresh clone starts in.
    """
    # `int(...)` on a value that is not a number raises, and this function is
    # called from a merge path holding whatever a foreign-interpreter subprocess
    # wrote to a file. A payload of `{"nodes": "many"}` therefore crashed an
    # otherwise-successful merge with an uncaught ValueError — a best-effort
    # recorder taking down its caller. Non-integers are DROPPED, so a partly
    # usable payload still records what it can and the rest reads as unknown.
    # (Cold lane, round 2, P2.)
    payload: dict[str, object] = {"fingerprint": _fingerprint(graph_path), "tag": tag}
    payload.update(
        {
            k: counts[k]
            for k in _FIELDS
            # `bool` IS an `int` in Python, so `True` would record as 1 — a count
            # nobody measured, indistinguishable from one somebody did.
            if isinstance(counts.get(k), int) and not isinstance(counts.get(k), bool)
        }
    )
    try:
        atomic.write_text(ledger_path(repo_root), json.dumps(payload, indent=2) + "\n")
    except OSError as e:
        print(f"[{tag}] WARNING: could not record graph counts: {e}")


def read(repo_root: Path, graph_path: Path) -> dict[str, int] | None:
    """The recorded counts, or `None` when they cannot be trusted for this graph.

    `None` covers four genuinely different situations, and they are collapsed on
    purpose: no ledger, an unreadable ledger, a ledger with no fingerprint, and a
    ledger whose fingerprint disagrees with the file on disk. Every one of them
    means the same thing to a caller — *we do not know what this graph held
    before* — and a caller that distinguished them would be tempted to treat one
    of them as good enough.

    The fingerprint comparison is what makes this safe rather than merely
    convenient. Without it a rebuild outside a tracked writer would leave counts
    describing a graph two generations back, and the next merge would report a
    confident delta computed against fiction.
    """
    try:
        data = json.loads(ledger_path(repo_root).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    recorded = data.get("fingerprint")
    if not recorded or recorded != _fingerprint(graph_path):
        return None
    return {k: int(v) for k, v in data.items() if k in _FIELDS and isinstance(v, int)}
