# #189 + #191 — cross-chunk collision + merge arithmetic: mutation arms

**29 of 30 arms died**, control green at both ends, tree restored
(`RESTORED rc=0`). Run 2026-08-06 on `chore/post-197`. Row `A0` is a **declared
no-op CONTROL** that must SURVIVE: if it ever dies, the harness is mutating
something it should not and every other row is meaningless.

The runner half is **COPIED, not restated** — extracted programmatically from
the `<!-- HARNESS -->` block in
`2026-08-04-kb-ship-handoff-gate-mutation-arms.md`, with only `TESTS` and `ARMS`
replaced. This is the FIFTH harness in this repo; the `__pycache__` mitigation it
carries has been lost by three successive re-writes, and
[#160](https://github.com/ray-manaloto/knowledge-base/issues/160) — make it a
`kb_setup` module with a test — is still open. Its existence is the evidence that
"write it down" keeps failing.

## The survivor, and why it was a REAL gap rather than a no-op

`A6 path dedup` deletes the `.resolve()`-and-dedup from `collision_issues`:

```python
unique = list(dict.fromkeys(p.resolve() for p in paths))   # ->  list(paths)
```

First sweep: **SURVIVED, suite green.** The tempting reading is "the tests do not
cover it"; the other reading is "the mutation is inert". Both were measured
rather than argued, because a surviving arm is only a coverage gap once the
mutant is shown to behave differently:

| input | with `.resolve()` | mutant |
|---|---|---|
| two IDENTICAL `Path` objects (what the fixture passed) | 0 issues | **0 issues** |
| one file as a RELATIVE path and an ABSOLUTE one | 0 issues | **1 issue** |

So the mutant is inert on the fixture and live on the real shape. `claims` is a
dict keyed by `Path`, so two identical objects collapse whether or not anything
resolves them — the fixture **could not exhibit its own harm**. The live shape is
the ordinary one: `mise run kb-merge -- sources/extractions/x.json` hands
`merge_chunk` a RELATIVE path while `_committed_chunks` globs from `repo_root`
and yields an ABSOLUTE one, so every re-merge of a committed chunk passes exactly
these two spellings. Without the dedup the single most routine `kb-merge`
invocation there is refuses itself — and a gate that blocks the ordinary case is
one somebody turns off.

Test added, arm re-run, **DIED**. That is the fourth round running in which a
refusal fixture could not exhibit the thing it was written for.

## What a clean sweep did NOT catch, and running the thing did

The sweep was clean at 17 arms while `_report` still printed
*"the identities collided (#189) and the loss is real"* for a **routine
re-merge**. Measured live: re-merging `claude-commands-docs.json` reports
`REPLACED 10` with the total unchanged — its own ten nodes, pruned and re-added,
which is what every re-merge does. Every test asserted the message was produced;
none asked whether it was TRUE for that input.

That is the same lesson three earlier rounds in this repo recorded from the other
side — a full mutation score is a statement about the TESTS, never about the
design — arriving here through the mildest possible door: not a wrong number, a
wrong *sentence*, on the most common operation the feature has. A check that
cries wolf on the ordinary path is one people learn to skip, which would have
cost the whole feature.

The fix gives the caller the discriminator (`graphify_ops._self_remerge`:
committed **and** sole claimant of every `source_file` it names — neither
condition alone), and arms `A18`–`A20` exist so it cannot be quietly neutered
back into always-EXPECTED.

## Round 2: four arms the sweep could not have had

`A21`–`A24` exist because the COLD REVIEW found four real defects that 21 green
arms said nothing about — two of them P1. The sharpest is worth stating because
it was a wrong MODEL rather than wrong code: `collision_issues` decided ownership
by replay order, which is right for `kb-build` and wrong for a lone `kb-merge`,
where `build_merge` prunes on the INCOMING chunk's claims unconditionally
(`build.py:1531-1537`). Re-merging an OLDER committed chunk over a newer sibling
that had legitimately declared the shared file was reported CLEAN, and would then
have deleted the newer chunk's nodes — the gate's own subject, walking in through
the gate. Every arm here had been mutating an implementation of the wrong rule.

That is the second time in one round that a full sweep certified something the
tests agreed with and the world did not. Mutation arms measure the tests; they
cannot measure the premise.

**Two arms reported `SKIPPED — pattern matched 0 times` on the first re-run after
the fixes**, because the code they anchor to had moved. The harness reports that
as *never ran* rather than as a survivor, which is the whole reason
`source.count(old) != 1` is checked before the mutation is applied — three
"survivors" in an earlier round were exactly this, misread. Patterns updated,
both then died.

## Round 2 added five more, and two more patterns went stale

The cold lane's SECOND round ran with a **mutating brief** — execute, construct
inputs, run the suite — rather than a reading one, and returned **9 findings, 3
P1**, all reproducible, over code that 25 green arms had just certified. `A25`–`A29`
pin the fixes.

The sharpest was again a comparison asking the wrong question: `build_merge`
matches `_norm_source_file`'s output (`build.py:275-287`), not the raw
`source_file` string, so `docs\x.md` and `docs/x.md` were two identities to this
gate and ONE to graphify — judged disjoint, then silently pruned. What
normalisation cannot reconcile without a root (an absolute path) is now refused at
the door rather than approximated; measured across all **3,733** committed
identities, zero are absolute or backslashed, so the narrowing rejects nothing
that exists.

**Two more arms reported `SKIPPED — pattern matched 0 times`** after these fixes
moved their anchors, on top of the two in round 1. Four stale patterns across two
rounds is the honest cost of anchoring arms to source text — and every one was
reported as NEVER RAN rather than as a survivor, which is the only reason the
count above means anything.

## What the arms cover

Each arm is a break that could really happen — an inverted comparison, a deleted
guard, a loosened bound — never a renamed symbol. `source.count(old) != 1` is
asserted BEFORE each mutation is applied, so an arm whose pattern matched the
wrong occurrence is reported as *never ran* rather than as a survivor; three
"survivors" in an earlier round were exactly that mistake.

The table below is **generated from the harness's own `ARMS` list**, not
transcribed, per `probes-need-a-control-arm.md` rule 8.

| arm | file | what a SURVIVAL would mean |
|---|---|---|
| `A0 CONTROL no-op` | `chunks.py` | NOTHING — this arm must SURVIVE; if it dies the harness is broken |
| `A1 replay winner` | `chunks.py` | the chunk that does NOT own the file is asked to declare it |
| `A2 undeclared refusal` | `chunks.py` | an undeclared cross-chunk claim is admitted — the 72-node loss |
| `A3 declaration ignored` | `chunks.py` | a declared supersession still refuses — the gate blocks ordinary work |
| `A4 inversion direction` | `chunks.py` | a stale winner is silent and a fresh one is reported |
| `A5 set-of-one bound` | `chunks.py` | collision_issues never checks anything at real corpus sizes |
| `A6 path dedup` | `chunks.py` | re-merging a committed chunk refuses itself |
| `A7 supersedes read` | `chunks.py` | every declaration is ignored; refusal is unconditional |
| `A8 supersedes shape` | `chunks.py` | a string `"a.md"` declaration passes and then iterates as characters |
| `A9 array-chunk guard` | `chunks.py` | a top-level JSON array crashes chunk_captured_at with AttributeError |
| `A10 fingerprint gate` | `graph_counts.py` | counts from a graph two generations back are handed back as current |
| `A11 recorded fingerprint` | `graph_counts.py` | the ledger certifies counts against an artifact it never observed |
| `A12 replaced sign` | `_merge_docs.py` | a destructive merge reports a negative replacement and reads as growth |
| `A13 unknown prior` | `_merge_docs.py` | an unknown prior is treated as 0 and every merge reports a huge replacement |
| `A14 handoff consumed` | `graph.py` | chunk N+1 inherits chunk N's count and reports a fabricated delta |
| `A15 merge preflight` | `graphify_ops.py` | kb-merge admits a chunk that collides with the committed corpus |
| `A17 build prior unknown` | `graph.py` | chunk 1 invents a baseline of 0 and reports the whole graph as replaced |
| `A16 record on failure` | `graphify_ops.py` | a failed merge writes a ledger entry for a graph it may have half-written |
| `A18 self-remerge committed` | `graphify_ops.py` | an UNCOMMITTED chunk's replacement is reported as its own re-extraction |
| `A19 self-remerge exclusivity` | `graphify_ops.py` | a cross-chunk supersession is waved through as a routine re-merge |
| `A20 report self branch` | `_merge_docs.py` | every replacement reads EXPECTED, including a real collision |
| `A21 merge-door winner` | `chunks.py` | a lone kb-merge is judged by replay order, so an older chunk eats a newer one |
| `A22 ledger in the collision set` | `graphify_ops.py` | a chunk merged from outside the tree is invisible to the collision gate |
| `A23 assemble carries supersedes` | `chunks.py` | kb-assemble strips the declaration and the chunk then fails its own gate |
| `A24 prose refreshes the ledger` | `graphify_ops.py` | every merge after a relabel gets a baseline of 0 instead of the real count |
| `A25 separator fold` | `chunks.py` | two spellings of one identity are judged disjoint, then silently pruned |
| `A26 absolute guard` | `chunks.py` | an absolute source_file is accepted and compares as a different identity |
| `A27 corrupt vs absent ledger` | `graph.py` | a corrupt ledger silently narrows the collision gate, unknown as permission |
| `A28 stale handoff cleared` | `graphify_ops.py` | an interrupted run's counts are recorded against THIS run's graph |
| `A29 wrong-typed payload` | `graph_counts.py` | a best-effort recorder crashes an otherwise-successful merge |

## Result

```
CONTROL (unmutated) rc=0  OK
A0 CONTROL no-op             rc=0 SURVIVED   <- intended
A1..A29                      rc=1 DIED       <- all twenty-nine
RESTORED rc=0  OK
29/30 arms died
```

## What a full sweep does NOT say

It says the TESTS cover these lines. It says nothing about whether the design is
right — three earlier rounds in this repo scored 12/12, 15/15 and 17/17 clean
immediately before a real blocking defect was found by review, and twice the
defect was inside the previous round's own fix. This round adds a fourth: 17/17
clean over a message that was false on its most common input. The cold review,
and actually RUNNING the thing, are the other halves.

Two things this sweep genuinely cannot reach, stated rather than dropped:

- **`_merge_docs.main()`** — it imports graphify and runs under the bundled
  interpreter. Only `_opt` and `_report` are reachable from the repo's uv python,
  which is why the graphify imports were moved INSIDE `main()` in this change.
  The arithmetic in `_report` is the whole point of #191; leaving it unreachable
  by the suite would have made it a check verified only by the incident it was
  written for. `main()`'s wiring is covered by the live `kb-build` instead.
- **The live corpus.** Every arm runs against fixtures. The detector's behaviour
  on the real 19 committed chunks is the round's own evidence, not this report's:
  a full rebuild replayed all 19 with per-chunk arithmetic, and the ONE chunk
  declaring a supersession was the ONE reporting a replacement — 20 nodes,
  matching the superseded chunk's own 5 + 15 counted independently.

<!-- HARNESS -->
```python
"""#189 + #191 mutation arms — the FIFTH harness, runner COPIED not restated.

Extracted programmatically from the #149 report's `<!-- HARNESS -->` block, so
the two bytecode mitigations survive: every `__pycache__` under python/src is
deleted before each arm, and every arm runs with PYTHONDONTWRITEBYTECODE=1.
CPython validates a cached `.pyc` by (source mtime in whole seconds, source
size), so single-token mutations collide routinely and pytest imports the
PREVIOUS arm's bytecode. That has cost three harnesses. #160 is still open.

Every arm mutates PRODUCTION code with a break that could really happen and
asserts the suite goes RED. `source.count(old) != 1` is checked first, so an arm
whose pattern matched the wrong occurrence is reported as NOT RUN rather than as
a survivor — three "survivors" in an earlier round were exactly that.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base")
SRC = ROOT / "python" / "src" / "kb_setup"
TESTS = [
    "tests/test_chunk_collisions.py",
    "tests/test_graph_counts.py",
    "tests/test_merge_counts_wiring.py",
]

CHUNKS = SRC / "chunks.py"
COUNTS = SRC / "graph_counts.py"
MERGE = SRC / "_merge_docs.py"
GRAPH = SRC / "graph.py"
OPS = SRC / "graphify_ops.py"

#: (id, file, old, new, what a reader should conclude if it SURVIVES)
ARMS: list[tuple[str, Path, str, str, str]] = [
    (
        "A0 CONTROL no-op",
        CHUNKS,
        "def collision_issues(paths: list[Path], *, merging: Path | None = None) -> list[str]:",
        "def collision_issues(paths: list[Path], *, merging: Path | None = None) -> list[str]:  # control",
        "NOTHING — this arm must SURVIVE; if it dies the harness is broken",
    ),
    (
        "A1 replay winner",
        CHUNKS,
        "        winner = max(holders, key=lambda p: rank[p])",
        "        winner = min(holders, key=lambda p: rank[p])",
        "the chunk that does NOT own the file is asked to declare it",
    ),
    (
        "A2 undeclared refusal",
        CHUNKS,
        "        if sf not in claims[winner][1]:",
        "        if False:",
        "an undeclared cross-chunk claim is admitted — the 72-node loss",
    ),
    (
        "A3 declaration ignored",
        CHUNKS,
        "        if sf not in claims[winner][1]:",
        "        if True:",
        "a declared supersession still refuses — the gate blocks ordinary work",
    ),
    (
        "A4 inversion direction",
        CHUNKS,
        '        stale = [p for p in losers if claims[p][0].get(sf, "") > won_at]',
        '        stale = [p for p in losers if claims[p][0].get(sf, "") < won_at]',
        "a stale winner is silent and a fresh one is reported",
    ),
    (
        "A5 set-of-one bound",
        CHUNKS,
        "    if len(unique) < _MIN_CHUNKS_FOR_COLLISION:",
        "    if len(unique) < 99:",
        "collision_issues never checks anything at real corpus sizes",
    ),
    (
        "A6 path dedup",
        CHUNKS,
        "    unique = list(dict.fromkeys(p.resolve() for p in paths))",
        "    unique = list(paths)",
        "re-merging a committed chunk refuses itself",
    ),
    (
        "A7 supersedes read",
        CHUNKS,
        "        {n for n in (normalise_source_file(d) for d in declared) if n is not None}",
        "        set()",
        "every declaration is ignored; refusal is unconditional",
    ),
    (
        "A8 supersedes shape",
        CHUNKS,
        "    if not isinstance(declared, list):\n"
        "        return [f\"{label}: '{_SUPERSEDES}' is not a list\"]",
        "    if not isinstance(declared, list):\n        return []",
        'a string `"a.md"` declaration passes and then iterates as characters',
    ),
    (
        "A9 array-chunk guard",
        CHUNKS,
        "    if not isinstance(data, dict):\n        # THIRD instance",
        "    if False:\n        # THIRD instance",
        "a top-level JSON array crashes chunk_captured_at with AttributeError",
    ),
    (
        "A10 fingerprint gate",
        COUNTS,
        "    if not recorded or recorded != _fingerprint(graph_path):",
        "    if not recorded:",
        "counts from a graph two generations back are handed back as current",
    ),
    (
        "A11 recorded fingerprint",
        COUNTS,
        'payload: dict[str, object] = {"fingerprint": _fingerprint(graph_path), "tag": tag}',
        'payload: dict[str, object] = {"fingerprint": "x", "tag": tag}',
        "the ledger certifies counts against an artifact it never observed",
    ),
    (
        "A12 replaced sign",
        MERGE,
        "    replaced = added - observed",
        "    replaced = observed - added",
        "a destructive merge reports a negative replacement and reads as growth",
    ),
    (
        "A13 unknown prior",
        MERGE,
        "    if prior is None:",
        "    if False:",
        "an unknown prior is treated as 0 and every merge reports a huge replacement",
    ),
    (
        "A14 handoff consumed",
        GRAPH,
        "    finally:\n        handoff.unlink(missing_ok=True)\n"
        "    n = data.get(\"nodes\") if isinstance(data, dict) else None",
        "    finally:\n        pass\n"
        "    n = data.get(\"nodes\") if isinstance(data, dict) else None",
        "chunk N+1 inherits chunk N's count and reports a fabricated delta",
    ),
    (
        "A15 merge preflight",
        OPS,
        "        [chunk_path, *_committed_chunks(repo_root)], merging=chunk_path\n    )\n"
        "    if collisions:",
        "        [chunk_path, *_committed_chunks(repo_root)], merging=chunk_path\n    )\n"
        "    if False:",
        "kb-merge admits a chunk that collides with the committed corpus",
    ),
    (
        "A17 build prior unknown",
        GRAPH,
        "    prior_nodes: int | None = None",
        "    prior_nodes: int | None = 0",
        "chunk 1 invents a baseline of 0 and reports the whole graph as replaced",
    ),
    (
        "A16 record on failure",
        OPS,
        "    if isinstance(counts, dict):",
        "    if True:",
        "a failed merge writes a ledger entry for a graph it may have half-written",
    ),
    (
        "A18 self-remerge committed",
        OPS,
        "    if resolved not in {p.resolve() for p in committed}:",
        "    if False:",
        "an UNCOMMITTED chunk's replacement is reported as its own re-extraction",
    ),
    (
        "A19 self-remerge exclusivity",
        OPS,
        "        if mine.keys() & theirs.keys():",
        "        if False:",
        "a cross-chunk supersession is waved through as a routine re-merge",
    ),
    (
        "A20 report self branch",
        MERGE,
        "    if self_remerge:\n        why = (",
        "    if True:\n        why = (",
        "every replacement reads EXPECTED, including a real collision",
    ),
    (
        "A21 merge-door winner",
        CHUNKS,
        "    incoming = merging.resolve() if merging is not None else None",
        "    incoming = None",
        "a lone kb-merge is judged by replay order, so an older chunk eats a newer one",
    ),
    (
        "A22 ledger in the collision set",
        OPS,
        "    return paths + [p for p in ledger if p.is_file() and p.resolve() not in known]",
        "    return paths",
        "a chunk merged from outside the tree is invisible to the collision gate",
    ),
    (
        "A23 assemble carries supersedes",
        CHUNKS,
        "    if declared_supersedes:\n        combined[_SUPERSEDES] = sorted(declared_supersedes)",
        "    if False:\n        combined[_SUPERSEDES] = sorted(declared_supersedes)",
        "kb-assemble strips the declaration and the chunk then fails its own gate",
    ),
    (
        "A24 prose refreshes the ledger",
        OPS,
        '{"nodes": stats.nodes_in, "edges": stats.links_in,',
        '{"nodes": 0, "edges": stats.links_in,',
        "every merge after a relabel gets a baseline of 0 instead of the real count",
    ),
    (
        "A25 separator fold",
        CHUNKS,
        '    cleaned = value.replace("\\\\", "/")',
        '    cleaned = value',
        "two spellings of one identity are judged disjoint, then silently pruned",
    ),
    (
        "A26 absolute guard",
        CHUNKS,
        '        if isinstance(sf, str) and (sf.startswith("/") or (len(sf) > 1 and sf[1] == ":")):',
        '        if False:',
        "an absolute source_file is accepted and compares as a different identity",
    ),
    (
        "A27 corrupt vs absent ledger",
        GRAPH,
        "    if entries is None:\n        return None",
        "    if entries is None:\n        return []",
        "a corrupt ledger silently narrows the collision gate, unknown as permission",
    ),
    (
        "A28 stale handoff cleared",
        OPS,
        "    counts_out.unlink(missing_ok=True)",
        "    pass",
        "an interrupted run's counts are recorded against THIS run's graph",
    ),
    (
        "A29 wrong-typed payload",
        COUNTS,
        "            if isinstance(counts.get(k), int) and not isinstance(counts.get(k), bool)",
        "            if k in counts",
        "a best-effort recorder crashes an otherwise-successful merge",
    ),
]


def purge() -> None:
    for cache in SRC.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def suite() -> int:
    purge()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode


def main() -> None:
    control = suite()
    print(f"CONTROL (unmutated) rc={control}  {'OK' if control == 0 else 'BROKEN HARNESS'}")
    if control != 0:
        sys.exit("control arm is red — every result below would be meaningless")

    survived: list[str] = []
    for name, path, old, new, meaning in ARMS:
        source = path.read_text(encoding="utf-8")
        if source.count(old) != 1:
            print(f"{name:28} SKIPPED — pattern matched {source.count(old)} times")
            survived.append(f"{name} (pattern did not match — the arm never ran)")
            continue
        path.write_text(source.replace(old, new), encoding="utf-8")
        try:
            rc = suite()
        finally:
            path.write_text(source, encoding="utf-8")
        verdict = "DIED" if rc != 0 else "SURVIVED"
        print(f"{name:28} rc={rc} {verdict}")
        if rc == 0:
            survived.append(f"{name}: {meaning}")

    after = suite()
    print(f"\nRESTORED rc={after}  {'OK' if after == 0 else 'TREE LEFT DIRTY'}")
    print(f"{len(ARMS) - len(survived)}/{len(ARMS)} arms died")
    for s in survived:
        print(f"  SURVIVED — {s}")


main()
```
<!-- /HARNESS -->

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base)
  — the repository under test; `chore/post-197`.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the
  installed 0.9.34 `build.py` to establish that `build_merge` reassigns
  `existing_nodes` to the POST-prune list at `:1536` before the `#479` shrink
  guard compares it at `:1650`, which is why that guard is structurally blind to
  the loss class these arms defend. Filed as
  [graphify#2497](https://github.com/Graphify-Labs/graphify/issues/2497).
