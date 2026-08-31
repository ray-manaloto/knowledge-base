# Copyright (c) 2026 Raymond Manaloto
"""`kb-manifest-audit` — offline registry/manifest consistency gate.

WHY THIS EXISTS. `mise run kb-build` has failed three times, once per build,
each on a different source, always the same mechanism: a package manifest that
extracts to ZERO nodes emits a graphify warning, and if that warning is neither
pre-approved in one of `graphify_health`'s four expectation registries
(`kb_setup.graph`'s `_EXPECTED_*` tuples) nor the source excluded by a manifest
`build` key, `graphify_health` fails closed and the build goes red. Each build
costs ~55 minutes and reveals exactly one name. This gate answers the two
MECHANICALLY-DETECTABLE causes offline, in seconds, before the next build pays
for them:

* **coverage** — every zero-node PACKAGE MANIFEST is either registered or its
  source is excluded (`build = skip`/`defer`).
* **freshness** — every registration still describes the file at the
  *current* manifest pin.

The failure this closes: commit `b2d51b53` bumped six `sources/*.manifest`
files and touched `graph.py` zero times. `uv`'s registered `content_sha256`
silently began describing bytes at the OLD pin. Nothing caught it; the next
`kb-build` would have (and did, eventually, at ~55 minutes a try).

**NOT the objective**: this does not replace `kb-build` as the authoritative
detector — that still runs and still fails closed. This gate makes the cheap
causes cheap to find.

EXPLICITLY OUT OF SCOPE (state so nobody believes otherwise):

1. **Registry TRUTH.** This gate verifies registry <-> manifest AGREEMENT,
   never whether a registration is *correct*. A real extraction regression can
   still be laundered by approving it into a registry with a fresh hash and a
   fresh pin: every tier green, real loss standing. That is procedural, not
   mechanical, and no offline check can catch it.
2. **Pin-site / currency-table completeness.** "Full protocol" (every pin site
   tracked in a currency table) is a DIFFERENT check owned by `kb_setup.currency`
   — this gate does not couple into it.
3. **Coverage of the `extract_json` zero-node route.** 12 of the 31
   `_EXPECTED_METADATA_ONLY` entries are JSON files `extract_json` declines
   (`skipped_disposition="data json (not a config/manifest)"`), not package
   manifests. The FRESHNESS tier re-verifies those (routed via
   `is_package_manifest_path`, exactly as `graphify_sdk.
   approve_metadata_zero_node_warning` routes them). The COVERAGE tier — which
   hunts UNREGISTERED zero-node files — only scans package manifests
   (`graphify.manifest_ingest.PACKAGE_MANIFEST_NAMES`: `Cargo.toml`,
   `pyproject.toml`, `go.mod`, `pom.xml`, `apm.yaml`/`apm.yml`). No census of
   "every zero-node JSON file in every clone" exists to found a wider scan on,
   and inventing one here would silently promise more than this gate checks. A
   green coverage tier means "no unregistered zero-node *package manifest*",
   never "no unregistered zero-node file of any kind".

THE TWO TIERS, split by evidence availability — the core design decision:

* **Tier 1 — registry <-> manifest pin agreement. ALWAYS RUNS. OFFLINE. FAILS
  CLOSED.** For every registry entry: `entry.pinned_commit ==
  sources/<source_name>.manifest`'s `commit`. Needs no clone, answerable on a
  fresh checkout or in CI. Alone, it catches the entire `b2d51b53` class.
* **Tier 2 — content and coverage. Requires the clone.** Hashes each registered
  entry's file and compares `content_sha256` (plus, for `ExpectedMetadataOnly`
  entries, re-runs the exact zero-node predicate `graphify_sdk` already owns);
  and scans each BUILT source's clone for an unregistered zero-node package
  manifest. **All clones absent -> SKIP**, its own state. Note the MIXED case,
  which is the normal one on most machines: with some clones present and some
  absent, `elif verified_sources` wins and tier 2 reports OK, so the per-source
  skips reach stdout via `render` but NOT the sidecar. That is intended and
  pinned by `test_tier2_ok_when_some_clones_present_and_some_absent`; this line
  claimed "never collapsed into OK" absolutely, which was false for that case.

A DELIBERATE ASYMMETRY, do not "fix" it: tier 1 flags DRIFT on a pin bump even
when the file is byte-identical upstream. That is the correct direction to be
wrong in — the remedy is a cheap re-stamp, and tier 2 confirms the hash
whenever the clone exists.

ITERATION IS OVER MANIFESTS, NOT REGISTRY ENTRIES. Iterating entries cannot see
a new source with no registration at all — the biome case. Every
`sources/*.manifest` either has zero registry entries (fine, unless tier 2's
coverage scan finds an unregistered zero-node manifest under it) or every one
of its entries must pass both tiers.

A PARSE-FAILURE IS ITS OWN CLASS, NEVER A COVERAGE FAILURE. `extract_package_
manifest` can return `{"nodes": [], "edges": [], "error": "..."}` — a file that
does not even parse (two of `biome`'s `Cargo.toml`s are TOML syntax errors, not
`[workspace]` roots). `graphify_sdk._package_manifest_item_is_reviewed`
refuses an errored file's approval unconditionally
(`if result.get("error") or ...: return False`), so a coverage predicate that
demanded ONE be registered would demand something `kb-build` can never accept.
This module reuses `graphify_sdk`'s own three-way condition rather than
restating it, so an errored file is neither a coverage failure nor silently
approved — it is excluded from BOTH the "must register" and the "fine" classes.

THE SIDECAR CHANNEL. `kb_setup.gates._invoke` runs a gate with stdio
INHERITED, never captured (this repo already paid for a substitution that
broke that once), so nothing this module prints can reach `gates-<sha>.json`'s
per-gate row. Before exiting, :func:`main` therefore writes this run's
three-state outcome (OK/DRIFT/SKIP) to the sidecar `kb_setup.gates.
sidecar_path(repo_root, TASK_NAME, sha)`, which `gates._run_one` reads back and
folds into that row's `outcome` field. Read the sidecar or the row's `outcome`
key, never the process rc alone, to tell a tier-2 SKIP apart from an OK — the
exact collapse `.claude/rules/verify-before-advancing.md` forbids.

SHIP-BLOCKING (decided by the architect, spec REVISION 2 §C6): tier 1 DRIFT
always blocks; tier 2 blocks only when it RAN and found DRIFT; a tier-2 SKIP
never blocks. `main`'s exit code encodes exactly that union — never the raw
three-state outcome, which lives in the sidecar and the printed report instead.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from graphify.manifest_ingest import extract_package_manifest, is_package_manifest_path

from kb_setup import gates, graph, graphify_health
from kb_setup import manifest as mf
from kb_setup.graphify_sdk import (
    _json_metadata_item_is_reviewed,
    _package_manifest_item_is_reviewed,
    _sha256_file,
)
from kb_setup.result import Rc

#: The mise task name — must match `[tasks.kb-manifest-audit]` in `mise.toml`
#: exactly, since it keys both the `GATE_TASKS` membership check
#: (`gates.undeclared`) and the sidecar file `main` writes.
TASK_NAME = "kb-manifest-audit"

#: A registry entry, in the union `graph.py`'s four `_EXPECTED_*` tuples hold.
#: Named here rather than left as `object` so every attribute access below is
#: checked: all four share `source_name`/`relative_path`/`content_sha256`/
#: `pinned_commit`, and `isinstance` narrows to the one that additionally
#: carries `skipped_disposition` (`ExpectedMetadataOnly` alone).
RegistryEntry = (
    graphify_health.ExpectedUnclassifiedFile
    | graphify_health.ExpectedMetadataOnly
    | graphify_health.ExpectedPartialExtraction
    | graphify_health.ExpectedUnsupportedLanguage
)


class Outcome(StrEnum):
    """Three states, never two — collapsing SKIP into OK is the bug this gate exists to avoid."""

    OK = "OK"
    DRIFT = "DRIFT"
    SKIP = "SKIP"


@dataclass(frozen=True)
class Tier1Report:
    """Registry <-> manifest pin agreement. Never SKIP — always answerable offline."""

    outcome: Outcome
    #: One line per (source_name, relative_path) whose `pinned_commit` disagrees
    #: with that source's manifest `commit` right now.
    mismatches: tuple[str, ...] = ()
    #: Registry entries whose `source_name` has no `sources/<name>.manifest` at
    #: all. Not observed at HEAD (spec REVISION 2 §C8 — all 14 checked), kept as
    #: its own bucket rather than crashing, per the spec's explicit instruction.
    unmatched_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tier2Report:
    """Content freshness + coverage. SKIP per-source when its clone is absent."""

    outcome: Outcome
    hash_mismatches: tuple[str, ...] = ()
    #: `ExpectedMetadataOnly` entries whose zero-node re-run no longer matches
    #: their review (still hashes clean, but graphify would no longer accept
    #: the approval — e.g. the file now parses to real nodes).
    stale_reviews: tuple[str, ...] = ()
    #: Unregistered zero-node PACKAGE MANIFESTS under a BUILT source's clone —
    #: this run's whole reason for existing. `sources/biome/Cargo.toml` on the
    #: first run.
    uncovered: tuple[str, ...] = ()
    #: Sources whose clone is missing, so tier 2 could not ask about them.
    skipped_sources: tuple[str, ...] = ()
    #: Sources whose clone exists but every question tier 2 asks was
    #: answerable (registered entries hashed clean, coverage scan ran).
    verified_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditReport:
    """Both tiers, plus the ship-blocking decision (spec REVISION 2 §C6)."""

    tier1: Tier1Report
    tier2: Tier2Report

    @property
    def blocks(self) -> bool:
        """Whether `kb-ship`/`kb-land` must refuse on this result.

        Tier 1 DRIFT always blocks. Tier 2 blocks ONLY when it ran (i.e. found
        at least one source with a clone) AND found DRIFT — never on a SKIP,
        and never on a clean tier 2 that simply had nothing to check.
        """
        return Outcome.DRIFT in (self.tier1.outcome, self.tier2.outcome)

    @property
    def sidecar_outcome(self) -> Outcome:
        """The overall three-state verdict this run writes to the sidecar."""
        if self.blocks:
            return Outcome.DRIFT
        if self.tier2.outcome == Outcome.SKIP:
            return Outcome.SKIP
        return Outcome.OK


def _registries() -> tuple[tuple[str, tuple[RegistryEntry, ...]], ...]:
    """The four expectation registries, named, in `graph.py`'s own declaration order."""
    return (
        ("unclassified", graph._EXPECTED_UNCLASSIFIED),
        ("metadata-only", graph._EXPECTED_METADATA_ONLY),
        ("partial-extraction", graph._EXPECTED_PARTIAL_EXTRACTION),
        ("unsupported-language", graph._EXPECTED_UNSUPPORTED_LANGUAGE),
    )


def _entries_by_source() -> dict[str, list[tuple[str, RegistryEntry]]]:
    """Every registry entry, grouped by its `source_name`, tagged with its registry name."""
    by_source: dict[str, list[tuple[str, RegistryEntry]]] = {}
    for registry_name, entries in _registries():
        for entry in entries:
            by_source.setdefault(entry.source_name, []).append((registry_name, entry))
    return by_source


def _tier1(manifests: dict[str, mf.Manifest]) -> Tier1Report:
    """Tier 1: every registry entry's `pinned_commit` against its manifest's `commit`.

    Iterates REGISTRY ENTRIES grouped by source (`_entries_by_source`); the
    `manifests` argument is a lookup table, not the loop. This docstring said
    the opposite — "iterates MANIFESTS, not registry entries" — until a cold
    Gemini lane read it against line 239 (2026-08-31). The CONCLUSION it drew
    still holds, which is why the error survived: a manifest with zero entries
    is never visited here, so a brand-new wholly unregistered source — the
    `biome` case — falls through to tier 2's coverage scan rather than being
    silently invisible. Same outcome, different mechanism; state the mechanism.
    """
    by_source = _entries_by_source()
    mismatches: list[str] = []
    unmatched: list[str] = []
    for source_name, tagged_entries in by_source.items():
        manifest = manifests.get(source_name)
        if manifest is None:
            # Not observed at HEAD (spec REVISION 2 §C8) — defensive path only.
            unmatched.extend(f"{source_name}:{entry.relative_path}" for _, entry in tagged_entries)
            continue
        for _, entry in tagged_entries:
            if entry.pinned_commit != manifest.commit:
                mismatches.append(
                    f"{source_name}:{entry.relative_path} pinned_commit="
                    f"{entry.pinned_commit} manifest.commit={manifest.commit}"
                )
    outcome = Outcome.DRIFT if (mismatches or unmatched) else Outcome.OK
    return Tier1Report(
        outcome=outcome,
        mismatches=tuple(mismatches),
        unmatched_sources=tuple(unmatched),
    )


def _entry_is_fresh(root: Path, entry: RegistryEntry) -> tuple[bool, str]:
    """Whether ``entry`` still matches the file on disk. ``(is_fresh, reason_if_not)``.

    The additional zero-node re-check only applies to `ExpectedMetadataOnly`
    — `isinstance` narrows the type here rather than a registry-name string, so
    `entry.skipped_disposition` below is a checked attribute access, not a
    hopeful one.
    """
    path = root / entry.relative_path
    try:
        content_hash = _sha256_file(path)
    except OSError as exc:
        return False, f"{entry.source_name}:{entry.relative_path} unreadable ({exc})"
    if content_hash != entry.content_sha256:
        return False, (
            f"{entry.source_name}:{entry.relative_path} content_sha256 stale "
            f"(registered {entry.content_sha256[:12]}, now {content_hash[:12]})"
        )
    if not isinstance(entry, graphify_health.ExpectedMetadataOnly):
        # Tier 2's content check for the other three registries is the hash
        # alone, per the spec: re-running the actual extractor to confirm
        # "still zero nodes" needs a full build's sub-graph for partial-
        # extraction/unsupported-language entries, which is out of scope for an
        # offline-plus-clone gate.
        return True, ""
    routed_to_manifest = is_package_manifest_path(path)
    reviewed = (
        _package_manifest_item_is_reviewed(root, entry)
        if routed_to_manifest
        else _json_metadata_item_is_reviewed(root, entry)
    )
    if not reviewed:
        return False, (
            f"{entry.source_name}:{entry.relative_path} no longer reviewable "
            f"(re-run disagrees with skipped_disposition={entry.skipped_disposition!r})"
        )
    return True, ""


def _coverage_scan(
    clone_dir: Path,
    source_name: str,
    by_source: dict[str, list[tuple[str, RegistryEntry]]],
) -> tuple[str, ...]:
    """Unregistered zero-node package manifests under ``clone_dir``.

    Reuses `graphify_sdk._package_manifest_item_is_reviewed`'s exact three-way
    condition rather than restating `nodes == []`: a parse FAILURE
    (`result.get("error")`) is its own class, never a coverage failure (spec
    REVISION 2 §C2) — an errored file can never be approved, so demanding one
    be registered would be an impossible requirement.
    """
    registered_paths = {
        entry.relative_path
        for _, entry in by_source.get(source_name, [])
        if isinstance(entry, graphify_health.ExpectedMetadataOnly)
        and is_package_manifest_path(clone_dir / entry.relative_path)
    }
    uncovered: list[str] = []
    for candidate in sorted(clone_dir.rglob("*")):
        if not candidate.is_file() or not is_package_manifest_path(candidate):
            continue
        try:
            relative = str(candidate.relative_to(clone_dir))
        except ValueError:
            continue
        if relative in registered_paths:
            continue
        result = extract_package_manifest(candidate)
        if result.get("error"):
            # A parse failure is not registerable and not a coverage failure —
            # excluded from both classes, per spec REVISION 2 §C2/M1.
            continue
        if not result.get("nodes") and not result.get("edges"):
            uncovered.append(f"{source_name}:{relative}")
    return tuple(uncovered)


def _tier2(manifests: dict[str, mf.Manifest]) -> Tier2Report:
    """Tier 2: hash freshness + coverage, per BUILT source whose clone exists.

    Takes no ``repo_root``: `mf.load_all` resolves each `Manifest.path` off the
    directory it was called with (`audit` passes an absolute one), so
    `Manifest.clone_dir` is already absolute and needs no repo root to anchor it.
    """
    by_source = _entries_by_source()
    hash_mismatches: list[str] = []
    stale_reviews: list[str] = []
    uncovered: list[str] = []
    skipped_sources: list[str] = []
    verified_sources: list[str] = []

    # Union of every manifest name, whether or not it has registry entries —
    # this is what lets tier 2's coverage scan see a source (like `biome`) that
    # the registries have never heard of.
    for source_name, manifest in sorted(manifests.items()):
        clone_dir = manifest.clone_dir
        if not clone_dir.is_dir():
            skipped_sources.append(source_name)
            continue
        for _, entry in by_source.get(source_name, []):
            fresh, reason = _entry_is_fresh(clone_dir, entry)
            if fresh:
                continue
            if "content_sha256 stale" in reason or "unreadable" in reason:
                hash_mismatches.append(reason)
            else:
                stale_reviews.append(reason)
        # `kind == "docs"` sources never reach graphify's AST pass at all
        # (`graph.py`'s `kind == "docs"` branches short-circuit before any
        # extraction) — a bare Cargo.toml/pyproject.toml under one was never
        # going to be extracted, zero-node or not, so it is not a coverage gap.
        # Measured: `codex-docs` (kind=docs) carries an unregistered
        # `pyproject.toml` that a kind-blind scan flagged as uncovered on the
        # gate's very first run — a false positive this exclusion removes.
        if manifest.is_built and manifest.kind != "docs":
            uncovered.extend(_coverage_scan(clone_dir, source_name, by_source))
        verified_sources.append(source_name)

    if hash_mismatches or stale_reviews or uncovered:
        outcome = Outcome.DRIFT
    elif verified_sources:
        outcome = Outcome.OK
    else:
        outcome = Outcome.SKIP
    return Tier2Report(
        outcome=outcome,
        hash_mismatches=tuple(hash_mismatches),
        stale_reviews=tuple(stale_reviews),
        uncovered=tuple(uncovered),
        skipped_sources=tuple(skipped_sources),
        verified_sources=tuple(verified_sources),
    )


def audit(repo_root: Path) -> AuditReport:
    """Run both tiers and return the combined report. Never raises on a missing clone."""
    manifests = {m.name: m for m in mf.load_all((repo_root / "sources").resolve())}
    tier1 = _tier1(manifests)
    tier2 = _tier2(manifests)
    return AuditReport(tier1=tier1, tier2=tier2)


def render(report: AuditReport) -> str:
    """The printed report — states "tier 2 not verifiable here" rather than a bare pass."""
    lines = ["kb-manifest-audit", f"  tier 1 (registry <-> manifest pin): {report.tier1.outcome}"]
    lines.extend(f"    DRIFT  {line}" for line in report.tier1.mismatches)
    lines.extend(
        f"    DRIFT  {line} — no sources/<name>.manifest" for line in report.tier1.unmatched_sources
    )

    tier2 = report.tier2
    if tier2.outcome == Outcome.SKIP:
        lines.append(
            "  tier 2 (content + coverage): SKIP — "
            "tier 2 not verifiable here (no source clones present)"
        )
    else:
        lines.append(f"  tier 2 (content + coverage): {tier2.outcome}")
        lines.extend(f"    DRIFT  {line}" for line in tier2.hash_mismatches)
        lines.extend(f"    DRIFT  {line}" for line in tier2.stale_reviews)
        lines.extend(
            f"    DRIFT  unregistered zero-node package manifest: {line}"
            for line in tier2.uncovered
        )
        if tier2.skipped_sources:
            lines.append("    tier 2 not verifiable here for: " + ", ".join(tier2.skipped_sources))
    lines.append(f"  overall: {'BLOCKS' if report.blocks else 'does not block'}")
    return "\n".join(lines)


def main(repo_root: Path, args: list[str]) -> int:
    """CLI boundary. Writes the sidecar `gates._run_one` reads, then exits.

    Exit code encodes the ship-blocking decision (spec REVISION 2 §C6), never
    the raw three-state outcome — that lives in the sidecar and the printed
    report. `Rc.FINDINGS` (1) on a block, `Rc.OK` (0) otherwise (including a
    tier-2 SKIP, which never blocks).
    """
    if args:
        print(f"kb-manifest-audit: takes no arguments (got {args!r})", file=sys.stderr)
        return int(Rc.BAD_REQUEST)
    report = audit(repo_root)
    print(render(report))
    sha = gates.head_sha(repo_root)
    if sha:
        gates.write_sidecar_outcome(repo_root, TASK_NAME, sha, report.sidecar_outcome.value)
    return int(Rc.FINDINGS) if report.blocks else int(Rc.OK)
