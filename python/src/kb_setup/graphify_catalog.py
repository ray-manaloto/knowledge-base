# Copyright (c) 2026 Raymond Manaloto
"""Bind the Graphify disposition catalog to the commit its own manifest pins.

WHY THIS EXISTS, measured. `sources/graphify.dispositions.json` records, per
path, the sha256 and size of the files Graphify detection intentionally omits,
plus the `source_tree` of the commit those bytes came from. Nothing re-derived
any of it when the pin moved. On 2026-09-09 the pin advanced to `3c9b930f`
while `source_tree` still named `157a957e`'s tree and the `uv.lock` row still
named the old blob (1015646 bytes vs 1015799) — and **all eight gates passed
over it**. `graphify_baseline`'s own identity guard refuses that state, so a
`kb-build` would have surfaced it eventually; nothing asked the question first.

WHAT MAKES THIS A CHECK RATHER THAN A FINGERPRINT. It compares the RECORDED
values against values DERIVED from the pinned commit — never against a previous
run's copy of themselves. A stale value that nothing regenerated never moves, so
a same-versus-same comparison reads clean forever; that is the exact failure
`kb_setup.currency.views` was built to escape
(`.claude/rules/tool-currency-and-native-first.md`).

IT READS THE COMMIT, NEVER THE WORKTREE. `git cat-file <commit>:<path>` answers
*what does the pin say*, which is the question the catalog claims to answer. The
clone's worktree may legitimately be dirty — this repo's own `graph_first` guard
left a stray state file inside `sources/graphify/` on 2026-08-25, and it sat
there for weeks — and that must not change this answer. `graphify_baseline`'s
`source_manifest` deliberately asks the *other* question (does the worktree
still equal the blobs) and refuses on drift; the two are complements.

A MISSING PATH IS A DRIFT ROW, NOT AN EXCEPTION. A catalog can name a file the
new commit does not have. That is not hypothetical: it is precisely how the mise
resync red-lined `kb-build` last round — two files new at v2026.9.4 and absent
at v2026.9.0 — so the row has to say `absent` rather than raise and lose the
other nineteen answers.

NO CLONE IS `NOT_RUN`, NEVER A PASS. `sources/<name>/` is gitignored and
re-fetched by `kb-build`, so a fresh checkout has nothing to read. Reporting
that as clean is how a gate reports green without checking anything
(`.claude/rules/probes-need-a-control-arm.md`).

WHAT THIS CANNOT SEE, stated because a check that does not declare its blind
spot gets read as covering everything (`.claude/skills/kb-review` § *a check you
add must declare what it cannot see*):

- **`BaselineAuthority.source_manifest_sha256`.** Deriving it means rebuilding
  the whole `SourceManifest`, which `graphify_baseline.source_manifest`
  deliberately refuses against a dirty worktree — so checking it here would make
  this gate fail for a reason that has nothing to do with the pin. It is still
  verified, later and more expensively, by `_verify_candidate` at build time.
- **Whether a disposition's REASON is still true.** A file can keep its bytes
  and stop being unsupported because a new extractor shipped. That is a
  judgement, and only a real detection run answers it.
- **Paths the pin holds that the catalog never mentions.** A newly-added file
  needing a disposition is invisible here; the detected/extracted counts in the
  authority are what catch that, and only during a build.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import msgspec

from kb_setup import events
from kb_setup.result import Rc

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

#: The source whose catalog this module owns. One source, one catalog; a second
#: source wanting the same treatment gets its own name here rather than a
#: parameter nobody passes.
SOURCE = "graphify"

CATALOG_PATH = Path("sources") / "graphify.dispositions.json"
MANIFEST_PATH = Path("sources") / "graphify.manifest"
CLONE_PATH = Path("sources") / "graphify"

_FLAGS = frozenset({"--write"})


class _Catalog(msgspec.Struct, forbid_unknown_fields=False):
    """Just enough of the catalog to check it.

    Deliberately NOT `graphify_baseline.DispositionCatalog`: that model is
    `frozen=True, forbid_unknown_fields=True` and is validated by
    `load_disposition_catalog`, which raises on exactly the drift this module
    exists to REPORT. A checker that cannot decode the broken state cannot
    describe it.
    """

    source: str = ""
    source_ref: str = ""
    source_commit: str = ""
    source_tree: str = ""
    entries: list[dict] = []


@dataclass(frozen=True, slots=True)
class Drift:
    """One disagreement between what is recorded and what the pin actually holds."""

    what: str
    """`source_tree`, `authority_tree`, or the catalog path whose bytes moved."""

    recorded: str
    derived: str
    kind: str
    """`stale` (both known and different) or `absent` (the pin has no such path)."""

    def line(self) -> str:
        """The human row, rendered once so the report and the JSONL sink agree."""
        if self.kind == "absent":
            return f"{self.what}: recorded {self.recorded}, but the pinned commit has no such path"
        return f"{self.what}: recorded {self.recorded}, derived {self.derived}"


@dataclass(frozen=True, slots=True)
class Report:
    """What one check run examined and what it found."""

    commit: str
    derived_tree: str
    examined: int
    drift: tuple[Drift, ...]


class CatalogUnavailableError(Exception):
    """The question could not be asked — maps to `Rc.NOT_RUN`, never to a pass."""


def _git(clone: Path, *args: str) -> bytes:
    # Fixed argv, no shell; `git` resolves via PATH by design, as everywhere else here.
    proc = subprocess.run(
        ["git", "-C", str(clone), *args],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise CatalogUnavailableError(f"git {' '.join(args)} failed rc={proc.returncode}: {detail}")
    return proc.stdout


def pinned_commit(repo_root: Path) -> str:
    """The commit `sources/graphify.manifest` pins, via the shared parser.

    Uses `kb_setup.manifest.load` rather than re-parsing the file: ten
    hand-written `tomllib`/text probes of tracked config across two sessions is
    the standing `kb-distill` lead, and every one of them existed beside a
    loader that already worked.
    """
    from kb_setup import manifest

    path = repo_root / MANIFEST_PATH
    if not path.is_file():
        raise CatalogUnavailableError(f"no manifest at {MANIFEST_PATH}")
    return manifest.load(path).commit


def _blob(clone: Path, commit: str, path: str) -> tuple[str, int] | None:
    """sha256 and size of one path AT THE COMMIT, or None when the pin lacks it."""
    try:
        raw = _git(clone, "cat-file", "blob", f"{commit}:{path}")
    except CatalogUnavailableError:
        # `cat-file` exits non-zero for "no such path in that tree", which is a
        # legitimate answer here rather than a broken probe. It also exits
        # non-zero for a missing OBJECT, which is not — `derive` proves the
        # commit resolves before any of these run, so by this point the only
        # reachable cause is absence.
        return None
    return hashlib.sha256(raw).hexdigest(), len(raw)


def check(repo_root: Path, *, authority: object | None = None) -> Report:
    """Compare every recorded value against the pinned commit. Raises on NOT_RUN.

    ``authority`` is an injectable seam, on `skill_lint`'s precedent (its
    `decide` is a parameter for the same reason): the real one is a module
    literal naming the real graphify commit, so a test fixture repo would drift
    against it unconditionally and the catalog rows could never be tested alone.
    Production passes nothing and gets the real trust root.
    """
    clone = repo_root / CLONE_PATH
    if not (clone / ".git").exists():
        raise CatalogUnavailableError(
            f"no clone at {CLONE_PATH} — it is gitignored and rebuilt by `mise run kb-build`"
        )
    catalog_path = repo_root / CATALOG_PATH
    if not catalog_path.is_file():
        raise CatalogUnavailableError(f"no catalog at {CATALOG_PATH}")

    commit = pinned_commit(repo_root)
    try:
        catalog = msgspec.json.decode(catalog_path.read_bytes(), type=_Catalog)
    except (OSError, msgspec.DecodeError) as exc:
        raise CatalogUnavailableError(f"unreadable catalog: {exc}") from exc

    # Prove the commit resolves BEFORE deriving anything from it. Without this a
    # shallow clone missing the object is indistinguishable from a tree whose
    # every path is absent — twenty `absent` rows that mean "we could not look".
    derived_tree = _git(clone, "rev-parse", f"{commit}^{{tree}}").decode().strip()

    drift: list[Drift] = []
    if catalog.source_commit != commit:
        drift.append(Drift("source_commit", catalog.source_commit, commit, "stale"))
    if catalog.source_tree != derived_tree:
        drift.append(Drift("source_tree", catalog.source_tree, derived_tree, "stale"))

    examined, entry_drift = _entry_drift(clone, commit, catalog.entries)
    drift.extend(entry_drift)
    drift.extend(_authority_drift(repo_root, commit, derived_tree, authority))
    return Report(commit=commit, derived_tree=derived_tree, examined=examined, drift=tuple(drift))


def _entry_drift(clone: Path, commit: str, entries: list[dict]) -> tuple[int, list[Drift]]:
    """Per-path rows, and the count of paths actually EXAMINED.

    The count is returned rather than inferred from the drift list because those
    are different facts: zero drift over zero entries is not a clean catalog,
    and only the examined count tells them apart.
    """
    examined = 0
    rows: list[Drift] = []
    for entry in entries:
        path = str(entry.get("path", ""))
        if not path:
            continue
        examined += 1
        recorded_sha = str(entry.get("sha256", ""))
        found = _blob(clone, commit, path)
        if found is None:
            rows.append(Drift(path, recorded_sha, "", "absent"))
            continue
        sha, size = found
        if recorded_sha != sha:
            rows.append(Drift(f"{path} sha256", recorded_sha, sha, "stale"))
        if int(entry.get("size", -1)) != size:
            rows.append(Drift(f"{path} size", str(entry.get("size", "")), str(size), "stale"))
    return examined, rows


def _authority_drift(
    repo_root: Path, commit: str, derived_tree: str, authority: object | None = None
) -> list[Drift]:
    """The same identities, hard-coded a SECOND time in python.

    `graphify_baseline._ACCEPTED_AUTHORITY` is a module literal carrying its own
    `source_commit`, `source_tree` and `catalog_sha256`. A catalog fixed on its
    own leaves those copies stale and the build's guard still refusing, so both
    files are one check. The duplication is itself the finding; removing it is a
    separate change.

    `catalog_sha256` is the row that closes the loop on THIS module: editing the
    catalog to fix a stale entry invalidates the digest that names it, so a fix
    applied without this row would trade one drift for another and both gates
    would still be green.
    """
    from kb_setup import graphify_baseline

    root = (
        graphify_baseline.accepted_authority()
        if authority is None
        else cast("graphify_baseline.BaselineAuthority", authority)
    )
    rows: list[Drift] = []
    if root.source_commit != commit:
        rows.append(Drift("authority source_commit", root.source_commit, commit, "stale"))
    if root.source_tree != derived_tree:
        rows.append(Drift("authority source_tree", root.source_tree, derived_tree, "stale"))
    authority_digest = root.catalog_sha256
    try:
        catalog = graphify_baseline.load_disposition_catalog(repo_root)
    except ValueError as exc:
        # The strict loader refuses exactly the drift this module reports, so a
        # refusal here is a FINDING and never a reason to skip the row silently.
        rows.append(Drift("authority catalog_sha256", authority_digest, f"({exc})", "stale"))
        return rows
    digest = graphify_baseline.catalog_digest(catalog)
    if authority_digest != digest:
        rows.append(Drift("authority catalog_sha256", authority_digest, digest, "stale"))
    return rows


def _report(report: Report) -> None:
    events.say(
        "graphify_catalog.examined",
        f"[graphify-catalog] pin {report.commit[:12]} tree {report.derived_tree[:12]} — "
        f"{report.examined} catalog paths examined",
        commit=report.commit,
        tree=report.derived_tree,
        examined=report.examined,
    )
    for row in report.drift:
        events.warn(
            "graphify_catalog.drift",
            f"[graphify-catalog] {row.line()}",
            what=row.what,
            recorded=row.recorded,
            derived=row.derived,
            kind=row.kind,
        )


def main(repo_root: Path, args: Sequence[str] | None = None) -> int:
    """0 clean, `Rc.FINDINGS` on drift, `Rc.NOT_RUN` when it could not look.

    An unknown flag is `Rc.BAD_REQUEST` rather than a silent no-op, matching
    `funnel.main` and `gates.check_gates`.
    """
    rest = list(args or [])
    unknown = [a for a in rest if a not in _FLAGS]
    if unknown:
        events.fail(
            "graphify_catalog.bad_request",
            f"[graphify-catalog] unknown argument(s): {' '.join(unknown)}",
            unknown=unknown,
        )
        return Rc.BAD_REQUEST
    if "--write" in rest:
        events.fail(
            "graphify_catalog.not_implemented",
            "[graphify-catalog] --write is not implemented; re-derive deliberately and review "
            "the catalog and the authority literal together",
        )
        return Rc.BAD_REQUEST

    try:
        report = check(repo_root)
    except CatalogUnavailableError as exc:
        events.warn(
            "graphify_catalog.not_run",
            f"[graphify-catalog] COULD NOT ASK: {exc}",
            reason=str(exc),
        )
        return Rc.NOT_RUN

    _report(report)
    if report.drift:
        events.fail(
            "graphify_catalog.findings",
            f"[graphify-catalog] {len(report.drift)} value(s) do not describe the pinned commit",
            findings=len(report.drift),
        )
        return Rc.FINDINGS
    events.say("graphify_catalog.clean", "[graphify-catalog] every recorded value matches the pin")
    return Rc.OK
