# Copyright (c) 2026 Raymond Manaloto
"""Extraction census: every source's AST extraction, in ONE pass, no early exit.

`kb-build` stops at the first source whose extraction fails closed, so a corpus
with N blocked sources needs N full builds to enumerate them — and each build
re-extracts everything already known to pass. On 2026-09-02 that loop measured
8 -> 16 -> 31 -> 32 sources across five builds with 65 manifests still never
reached, which is what this module exists to replace: run every source once,
keep going past each failure, and report the whole set.

It is a MEASUREMENT, not a gate. It never writes the aggregate graph, it never
edits a manifest, and it always exits 0 unless it could not run at all — a
blocked source is the finding, not an error. `kb-build` remains the thing that
decides whether the corpus is buildable.

Two failure classes are recognised because those are the two the corpus actually
produces, and they want different remedies:

* SYNTAX — "N file(s) had syntax errors and may be partially extracted". Common in
  dev tooling, whose fixture trees are deliberately invalid input. Remedy is a
  reviewed `ExpectedPartialExtraction` per file, or `build = defer` when the count
  makes that absurd (biome: 1,138 files, #654).
* COLLISION — "node '<id>' is minted by two different files". Distinct ids are
  counted, not lines: one id can warn dozens of times. The corpus-visible cause is
  sibling files differing only by extension (`App.tsx` / `App.js`), which no purge
  or rebuild clears (#654).

Anything else is reported verbatim under OTHER rather than bucketed, because a
class this module does not know is exactly the thing a summary must not swallow.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from kb_setup import manifest as mf
from kb_setup.graphify_env import clean_env
from kb_setup.result import Rc

#: graphify's #2551 warning. The count is authoritative; the path list it carries
#: is truncated by graphify itself ("(+5 more)"), so paths are recorded as a
#: SAMPLE and the count is never derived from them.
_SYNTAX = re.compile(r"(\d+) file\(s\) had syntax errors")

#: graphify's dedup warning. Captured by ID because one id warns once per
#: referencing site — `dependency-cruiser` emitted 37 lines for 7 ids.
_COLLISION = re.compile(r"node '([^']+)' is minted by two different files")

#: Colliding ids listed per source before the report elides the rest. Enough to
#: show the SHAPE of a collision set (all `.d.ts`/`.js` siblings, say) without
#: reprinting 1,138 of them.
_MAX_LISTED_IDS = 12

#: Unclassified stderr lines printed per source before the report elides the rest.
#: Paired with an explicit "… N more" note: the elision is the thing that has to
#: be visible, not the bound.
_MAX_LISTED_STDERR = 10


@dataclass
class SourceOutcome:
    """One source's extraction result. `blocked` is the only judgement here."""

    name: str
    returncode: int
    syntax_files: int = 0
    collision_ids: tuple[str, ...] = ()
    sample_paths: tuple[str, ...] = ()
    other_stderr: str = ""
    nodes: int = 0

    @property
    def blocked(self) -> bool:
        """Whether this source stops `kb-build`: any warning class, or a bad rc.

        `returncode` is part of the judgement, not just a printed column. It was
        omitted at first, which made the predicate blind to the one source whose
        ONLY signal is the exit status: `fable-advisor` exited 1 with an empty
        graph and no classifiable stderr line of its own. It happened to carry
        residue that caught it, so the gap never showed — a source failing
        closed with clean stderr would have printed `ok`. (Cold review of
        `69c126cbaef8`.)
        """
        return bool(self.returncode or self.syntax_files or self.collision_ids or self.other_stderr)


@dataclass
class Census:
    """One sweep's outcomes, in the order the sources were extracted.

    `examined` is the denominator every figure here is against, and it is
    deliberately NOT `len(sources)`: a source selected but never extracted (no
    clone on disk) belongs in `missing`, where it is visible, rather than
    dropped. A run that examined nothing must be able to say so — see `main`.
    """

    started_at: str
    sources: list[SourceOutcome] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> list[SourceOutcome]:
        """Every source that would stop the build, build order preserved."""
        return [s for s in self.sources if s.blocked]

    @property
    def examined(self) -> int:
        """How many sources were actually extracted. Never the selection size."""
        return len(self.sources)


def _classify(stderr: str) -> tuple[int, tuple[str, ...], tuple[str, ...], str]:
    """Split one extraction's stderr into (syntax count, ids, sample paths, residue).

    Residue is every line neither pattern claimed, kept verbatim. A line this
    function cannot name is the case worth surfacing, so it is never dropped.
    """
    syntax = 0
    samples: list[str] = []
    ids: list[str] = []
    residue: list[str] = []
    for line in stderr.splitlines():
        if match := _SYNTAX.search(line):
            syntax = max(syntax, int(match.group(1)))
            samples.extend(re.findall(r"([\w./@+-]+\.[A-Za-z]+) \(first error at line", line))
            continue
        if match := _COLLISION.search(line):
            ids.append(match.group(1))
            continue
        if line.strip():
            residue.append(line)
    # dict.fromkeys: distinct ids, first-seen order — a set would make the report
    # non-deterministic across runs and this file is committed evidence.
    return syntax, tuple(dict.fromkeys(ids)), tuple(samples[:8]), "\n".join(residue)


def _unapproved_stderr(repo_root: Path, name: str, stderr: str) -> str:
    """Drop the warning lines `kb-build` has already accepted for this source.

    The build does not fail on every warning — `graphify_sdk.account_for_extract_stderr`
    clears any line covered by a reviewed inventory in `kb_setup.graph`. A census
    that skipped this step would answer a DIFFERENT question than "does this block
    the build", and it did: `datamodel-code-generator` has a registered
    package-manifest entry and was still reported BLOCKED.

    The inventories are read from `kb_setup.graph` rather than copied, so there is
    one reviewed list and no second one to drift.
    """
    from kb_setup import graph, graphify_sdk

    clone = repo_root / "sources" / name
    _approved, residual = graphify_sdk.account_for_extract_stderr(
        clone, stderr, graph.extract_warning_review(name, _nodes(clone))
    )
    return residual


def _nodes(clone: Path) -> list[object]:
    """The sub-graph's node list, or empty when it could not be read."""
    try:
        data = json.loads((clone / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return []
    raw = data.get("nodes", [])
    return raw if isinstance(raw, list) else []


def _node_count(clone: Path) -> int:
    graph = clone / "graphify-out" / "graph.json"
    try:
        data = json.loads(graph.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return 0
    nodes = data.get("nodes", [])
    return len(nodes) if isinstance(nodes, list) else 0


def _extract(repo_root: Path, name: str, clone: Path) -> subprocess.CompletedProcess[str]:
    """The SAME argv `kb_setup.graph._extract_code` runs, from a COLD sub-graph.

    Two things this must not get wrong, both learned by getting them wrong:

    The argv is copied from the build rather than re-invented; if it drifted, the
    census would measure something the build never hits.

    And the clone's own `graphify-out/` is REMOVED first. On the pinned 0.9.50,
    `--force --code-only` silently reverts to incremental when a warm sub-graph is
    present (fixed upstream in 0.9.51, `ae074b2`), so a census run after a build
    re-reads almost nothing and reports the silence as health. Measured: a warm
    `dependency-cruiser` reported 0 syntax errors and 0 collisions where the cold
    build had just measured 10 and 7. The sub-graph is derived and gitignored, so
    removing it costs nothing and is what makes the two runs comparable.
    """
    from kb_setup.graph import graphify_exe

    shutil.rmtree(clone / "graphify-out", ignore_errors=True)
    return subprocess.run(
        [graphify_exe(repo_root), "extract", f"sources/{name}", "--code-only", "--force"],
        cwd=repo_root,
        check=False,
        env=clean_env(),
        capture_output=True,
        text=True,
    )


def selected(repo_root: Path, *, only: frozenset[str] | None = None) -> list[mf.Manifest]:
    """The manifests a census sweep covers: exactly what `kb-build` AST-scans.

    `is_ast_scanned`, never `is_built`. The census exists to predict which
    sources stop the build, so scanning one the build never opens produces a
    blocked row for a blockage that cannot happen — which is what put
    `codex-docs` on a census blocked list and then into a registration.
    """
    manifests = [m for m in mf.load_all(repo_root / "sources") if m.is_ast_scanned]
    if only is not None:
        manifests = [m for m in manifests if m.name in only]
    return manifests


def run(repo_root: Path, *, only: frozenset[str] | None = None) -> Census:
    """Extract every AST-scanned source once, past every failure."""
    census = Census(started_at=datetime.now(UTC).isoformat())
    manifests = selected(repo_root, only=only)
    total = len(manifests)
    for index, m in enumerate(manifests, start=1):
        if not m.clone_dir.exists():
            census.missing.append(m.name)
            print(f"[{index}/{total}] {m.name}: NO CLONE — run kb-build first, NOT EXAMINED")
            continue
        proc = _extract(repo_root, m.name, m.clone_dir)
        unapproved = _unapproved_stderr(repo_root, m.name, proc.stderr or "")
        syntax, ids, samples, residue = _classify(unapproved)
        outcome = SourceOutcome(
            name=m.name,
            returncode=proc.returncode,
            syntax_files=syntax,
            collision_ids=ids,
            sample_paths=samples,
            other_stderr=residue,
            nodes=_node_count(m.clone_dir),
        )
        census.sources.append(outcome)
        verdict = "BLOCKED" if outcome.blocked else "ok"
        if not outcome.blocked:
            detail = f"nodes={outcome.nodes}"
        else:
            # `other` is named explicitly: a source blocked ONLY by an
            # unclassified line used to print `syntax=0 collisions=0`, which
            # reads as blocked by nothing — and that is the class worth seeing.
            parts = []
            if syntax:
                parts.append(f"syntax={syntax}")
            if ids:
                parts.append(f"collisions={len(ids)}")
            if residue:
                parts.append(f"other={len(residue.splitlines())}")
            detail = " ".join(parts)
        print(f"[{index}/{total}] {m.name}: {verdict} rc={proc.returncode} {detail}", flush=True)
    return census


def _render(census: Census) -> str:
    lines = [
        "# Extraction census",
        "",
        (
            f"Started {census.started_at}. Sources extracted: {census.examined}. "
            f"Blocked: {len(census.blocked)}."
        ),
        "",
        (
            "Scope: every source `kb-build` AST-scans (`Manifest.is_ast_scanned`) — "
            "`kind = docs` manifests are excluded here because the build never opens them."
        ),
        "",
        "| source | rc | syntax-error files | distinct collision ids | nodes |",
        "|---|---:|---:|---:|---:|",
    ]
    ordered = sorted(census.blocked, key=lambda s: (-s.syntax_files, -len(s.collision_ids), s.name))
    lines.extend(
        f"| `{s.name}` | {s.returncode} | {s.syntax_files} | {len(s.collision_ids)} | {s.nodes} |"
        for s in ordered
    )
    lines += ["", "## Detail", ""]
    for s in census.blocked:
        lines.append(f"### `{s.name}`")
        if s.syntax_files:
            lines.append(f"- {s.syntax_files} file(s) with syntax errors. Sample paths:")
            lines += [f"  - `{p}`" for p in s.sample_paths]
        if s.collision_ids:
            lines.append(f"- {len(s.collision_ids)} distinct colliding id(s):")
            lines += [f"  - `{i}`" for i in s.collision_ids[:_MAX_LISTED_IDS]]
            if len(s.collision_ids) > _MAX_LISTED_IDS:
                lines.append(f"  - … {len(s.collision_ids) - _MAX_LISTED_IDS} more")
        if s.other_stderr:
            residue = s.other_stderr.splitlines()
            lines.append("- UNCLASSIFIED stderr (verbatim):")
            lines += [f"  > {line}" for line in residue[:_MAX_LISTED_STDERR]]
            # The sibling collision branch above says how many it elided; this one
            # did not, under a heading reading "verbatim". An unclassified line is
            # precisely the class a summary must not silently shorten.
            if len(residue) > _MAX_LISTED_STDERR:
                lines.append(f"  - … {len(residue) - _MAX_LISTED_STDERR} more line(s)")
        lines.append("")
    if census.missing:
        lines += [
            "## NOT EXAMINED",
            "",
            (
                f"{len(census.missing)} selected source(s) had no clone on disk and were "
                "never extracted. They are neither clean nor blocked — run `mise run "
                "kb-build` first, then re-run this census."
            ),
            "",
        ]
        lines += [f"- `{name}`" for name in census.missing]
        lines.append("")
    return "\n".join(lines) + "\n"


def main(repo_root: Path, argv: list[str]) -> int:
    """Run the sweep, write the report, and report what was actually examined.

    `--only <name>...` narrows it to named sources. A blocked source is never a
    non-zero rc — it is the finding this exists to produce. Two other states are:

    * `Rc.BAD_REQUEST` — `--only` with no names, or with a name matching no
      AST-scanned source. A name that matches nothing silently filtered the
      worklist to empty and still printed "0 BLOCKED", which is a clean bill of
      health for a question nobody asked. The message NAMES the misses, because
      the usual cause is a typo or a source that is `kind = docs`.
    * `Rc.NOT_RUN` — the selection was fine and nothing was examined anyway
      (no clones on disk). Same reasoning, different cause: "we did not look" is
      a third state, and `kb-session-select`, `kb-attribute-write` and
      `skill_lint` all already refuse rather than return an empty list.

    (Both added after the cold review of `69c126cbaef8`.)
    """
    only: frozenset[str] | None = None
    if "--only" in argv:
        names = argv[argv.index("--only") + 1 :]
        if not names:
            print("--only needs at least one source name")
            return Rc.BAD_REQUEST
        only = frozenset(names)
        known = {m.name for m in selected(repo_root)}
        unknown = sorted(only - known)
        if unknown:
            print(f"--only names no AST-scanned source: {', '.join(unknown)}")
            print("(a `kind = docs` source is not scanned here — the build never opens it)")
            return Rc.BAD_REQUEST
    census = run(repo_root, only=only)
    out_dir = repo_root / ".agent" / "kb" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    report = out_dir / f"extract-census-{stamp}.md"
    report.write_text(_render(census), encoding="utf-8")
    print()
    if not census.examined:
        print(f"NOT RUN — 0 source(s) examined, {len(census.missing)} with no clone on disk.")
        print("This is not a clean corpus: run `mise run kb-build` first.")
        print(f"report: {report}")
        return Rc.NOT_RUN
    print(f"extracted {census.examined} source(s); {len(census.blocked)} BLOCKED")
    if census.missing:
        print(f"NOT EXAMINED: {len(census.missing)} source(s) with no clone — {census.missing}")
    print(f"report: {report}")
    return Rc.OK
