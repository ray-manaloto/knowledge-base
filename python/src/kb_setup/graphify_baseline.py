# Copyright (c) 2026 Raymond Manaloto
"""Graphify-only deterministic source admission and AST baseline evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from copy import deepcopy
from dataclasses import replace
from enum import StrEnum
from pathlib import Path

import msgspec

from kb_setup import graph
from kb_setup import manifest as source_manifests


class BaselineState(StrEnum):
    """Whether evidence authorizes the next deterministic stage."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class DispositionKind(StrEnum):
    """Why Graphify detection intentionally omitted a reviewed source path."""

    UNSUPPORTED_FILE = "unsupported-file"
    IGNORED_TREE = "ignored-tree"
    ZERO_NODE_FILE = "zero-node-file"
    EXCLUDED_AST_FIXTURE = "excluded-ast-fixture"
    COMPATIBILITY_CORRECTION = "compatibility-correction"


class SourceDisposition(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-addressed review decision for one omitted source path."""

    path: str
    kind: DispositionKind
    reason: str
    sha256: str
    size: int
    file_type: str
    extraction_disposition: str = ""


class DispositionCatalog(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact omission policy bound to one immutable Graphify tree."""

    source: str
    # REQUIRED, and it used to default to the literal "v0.9.42". A catalog
    # constructed without a ref then silently CLAIMED that release, and
    # `load_disposition_catalog`'s ref check would have believed it. Defaulting it
    # to `_ACCEPTED_GRAPHIFY_REF` instead would be worse: the check becomes
    # unfalsifiable, since a constructed catalog would always agree with whatever
    # the code accepts. The only honest option is to make the caller say it.
    source_ref: str
    source_commit: str
    source_tree: str
    entries: tuple[SourceDisposition, ...]
    schema_version: int = 1


class DispositionVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Typed comparison of detector omissions, catalog, and current source bytes."""

    state: BaselineState
    reasons: tuple[str, ...]


class ArtifactMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One content-addressed member of the deterministic candidate."""

    name: str
    sha256: str
    size: int


class CandidateManifest(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Public manifest for the Graphify-only deterministic baseline candidate."""

    schema_id: str
    source: str
    source_ref: str
    source_commit: str
    source_tree: str
    catalog_sha256: str
    members: tuple[ArtifactMember, ...]
    warnings: tuple[str, ...]
    semantic_evidence_present: bool
    release_evidence_present: bool


class BaselineVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Highest-level typed consumer verdict for the evolving expert bundle."""

    state: BaselineState
    deterministic_complete: bool
    reasons: tuple[str, ...]


class BaselineAuthority(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Immutable trust root for the one accepted Graphify release candidate."""

    source_ref: str
    source_commit: str
    source_tree: str
    catalog_sha256: str
    source_manifest_sha256: str
    detected_count: int
    extracted_count: int


class RuntimeIdentity(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Locked distribution, running CLI, and reviewed public SDK identity."""

    version: str
    cli_version: str
    sdk_version: str
    executable: str
    sdk_fingerprint_sha256: str
    #: The locked DISTRIBUTION's identity, in one of two mutually exclusive forms.
    #:
    #: A PyPI install locks a wheel and an sdist, and both hashes are recorded.
    #: A GIT install (the fork, 2026-08-24) locks neither — uv writes
    #: `source = {git = "<url>?rev=<sha>#<resolved-sha>"}` with no `wheels` and no
    #: `sdist` key at all — so `git_commit` carries the identity instead.
    #:
    #: Empty defaults rather than a union type because the historical records in
    #: `graphify_semantic_slice` are wheel-shaped and must keep decoding
    #: unchanged; `runtime_identity` enforces that exactly one form is populated,
    #: so "both empty" can never be mistaken for a valid identity.
    #:
    #: The git form is STRONGER, not a downgrade: a wheel hash identifies a built
    #: artifact, while the resolved commit identifies the exact source tree it was
    #: built from.
    wheel_sha256: str = ""
    sdist_sha256: str = ""
    git_commit: str = ""
    schema_version: int = 1


class SourceMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One exact Git blob and its raw-byte SHA-256 identity."""

    path: str
    mode: str
    git_object: str
    sha256: str
    size: int


class SourceManifest(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Complete raw-byte inventory of one immutable Git source tree."""

    source: str
    commit: str
    tree: str
    members: tuple[SourceMember, ...]
    schema_version: int = 1


class CompatibilityCorrection(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One exact, source-bound correction applied before Graphify graph construction."""

    name: str
    source_path: str
    source_sha256: str
    original_id: str
    replacement_ids: tuple[str, str]
    rewritten_edges: int


class BaselineBuildReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-bound result of the deterministic Graphify SDK pipeline."""

    status: str
    source_commit: str
    source_tree: str
    runtime_version: str
    detected_count: int
    extracted_count: int
    node_count: int
    edge_count: int
    hyperedge_count: int
    reviewed_metadata_paths: tuple[str, ...] = ()
    zero_node_paths: tuple[str, ...] = ()
    excluded_paths: tuple[str, ...] = ()
    compatibility_corrections: tuple[CompatibilityCorrection, ...] = ()
    approved_classifications: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: int = 1


class BaselineHealth(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Fail-closed health verdict for one deterministic baseline build."""

    state: str
    source: str
    source_commit: str
    source_tree: str
    warnings: tuple[str, ...] = ()
    schema_version: int = 1


class ControlOutcome(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Observed outcome for one real-source opposite-direction control."""

    name: str
    expected: str
    observed: str
    reasons: tuple[str, ...]


class ControlsReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Certificate that clean and mutated real-source controls behaved oppositely."""

    state: str
    source_commit: str
    source_tree: str
    cases: tuple[ControlOutcome, ...]
    schema_version: int = 1


class BaselineBuildInputs(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Identity-bound inputs required to construct one baseline candidate."""

    catalog: DispositionCatalog
    runtime: RuntimeIdentity
    controls: ControlsReceipt
    authority: BaselineAuthority


_BASELINE_SCHEMA = "graphify-deterministic-baseline/v0"
_MAX_BASELINE_ARGS = 2
_ACCEPTED_GRAPHIFY_VERSION = "0.9.50"
# FORKED 2026-08-24: this names WHAT RUNS, so it followed the pin onto the fork
# (`currency.toml` binds it with `tracks = "manifest"`). Contrast the semantic
# corpus/slice constants, which are snapshot identities of completed runs and
# correctly hold at the upstream base `v0.9.48`.
_ACCEPTED_GRAPHIFY_REF = "kb-pin/openai-cli-backend-v0.9.50"

#: The public spelling of the version above, for the ONE cross-module consumer:
#: `graphify_semantic_slice.preflight`'s `graphify_version` default. That was a
#: hardcoded literal and lagged silently at two bumps in a row — its own comment
#: called it "the only one that is a function default rather than a module
#: constant… which is why no `ref_binding` row reaches it". Binding it here makes
#: it un-laggable, and a public alias is the honest way to do that rather than
#: reaching across the module boundary for a private name.
ACCEPTED_GRAPHIFY_VERSION = _ACCEPTED_GRAPHIFY_VERSION
_ACCEPTED_GRAPHIFY_EXECUTABLE = ".venv/bin/graphify"
# FORKED 2026-08-24 (Ray). This is the REVIEWED REMOTE — the repo the baseline's
# historical evidence is pinned against — and it moved with the pin, because
# `historical_graphify_manifest` refuses outright when this and
# `sources/graphify.manifest` disagree ("Graphify historical source remote
# identity drifted"). That refusal is correct and is why the constant is here:
# evidence attributed to the wrong remote is evidence about a different program.
#
# It is deliberately NOT the same thing as `currency.toml`'s `[tool.graphify]
# github`, which stays `Graphify-Labs/graphify`. That one names where RELEASES
# are watched for — the rebase trigger — while this names where the code we
# actually run comes from. Under a fork those are two different repos, and
# collapsing them would either stop us seeing upstream releases or attribute our
# fork's bytes to upstream.
#
# Reverts to `https://github.com/Graphify-Labs/graphify` when #2981 merges; see
# `[tool.graphify.fork]`'s `clears_when`.
_ACCEPTED_GRAPHIFY_URL = "https://github.com/ray-manaloto/graphify"
# Deliberately NOT renamed at the 0.9.44 bump. The version in this string names
# the release the defect was FIRST observed in, which is a stable identity; the
# defect itself is still live — the 0.9.44 build receipt records this correction
# applying with `rewritten_edges: 1`, so it was verified rather than assumed.
# Re-versioning an identity every release would churn the receipt and lose the
# one fact the name carries. The RANGE lives in the catalog's human-readable
# `reason`, which is where a condition belongs.
_LPK_CORRECTION_NAME = "graphify-0.9.42-lpk-file-unit-identity"
_LPK_CORRECTION_PATH = "tests/fixtures/sample.lpk"
_LPK_CORRECTION_SHA256 = "d35ab7cfc6b30910020239b7389a4e732b5545269fd4b1cd43d7459aa2c40e1f"
_LPK_COLLISION_ID = "tests_fixtures_sample_lpk_tests_fixtures_sample"
_LPK_PACKAGE_ID = "tests_fixtures_sample_samplepackage"
_LPK_FILE_ID = _LPK_COLLISION_ID
_PAS_FILE_ID = "tests_fixtures_sample_pas_tests_fixtures_sample"
_PAS_SOURCE_PATH = "tests/fixtures/sample.pas"
_ACCEPTED_RUNTIME_HASHES = {
    "sdk_fingerprint_sha256": "b10406f90fe7c369fc1396991679f6e4490e59f9351332c30b9fe2216f071157",
    # FORKED 2026-08-24: a git-locked dependency has NO wheel and NO sdist, so
    # the two hashes that used to live here cannot exist and their absence is
    # not a gap to paper over. `git_commit` is the substitute and it is a
    # STRONGER identity — a wheel hash names a built artifact, a resolved
    # commit names the source tree it was built from. Reverts to the wheel/sdist
    # pair when #2981 merges and the pin returns to PyPI.
    "git_commit": "0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956",
}
_ACCEPTED_AUTHORITY = BaselineAuthority(
    source_ref=_ACCEPTED_GRAPHIFY_REF,
    source_commit="0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956",
    source_tree="38f958e839905df52ca48d799054e27dff95dab3",
    catalog_sha256="dddef4925e07b2d7a018c245278fb19a24548243ebc098080eb1acdb9efb50b7",
    source_manifest_sha256="8dda1b70d234943e3061f303f352945c3b153da382e231a2566b5c27339d7ffc",
    # 424 -> 429 detected, 416 -> 421 extracted across v0.9.46 -> v0.9.47 (and
    # 418 -> 424 / 410 -> 416 across v0.9.45 -> v0.9.46 before it). Both
    # RE-DERIVED by a real build against the installed 0.9.47, never carried
    # forward: the same run reproduced `source_tree` independently of the GitHub
    # API derivation above, which is what makes these counts a measurement.
    # +5/+5 is ordinary upstream growth — every newly detected file was also
    # extracted, so the gap between the two counts is UNCHANGED at 8, and no
    # warning was emitted.
    #
    # The +5 is ACCOUNTED FOR rather than assumed: `compare/v0.9.46...v0.9.47`
    # lists exactly five ADDED files and all five are `tests/*.py` — ordinary
    # supported source, which is why none of them needed a disposition entry.
    # Nothing was removed. That is also why this bump touched ONE catalog entry
    # (`uv.lock`, whose bytes moved) out of the catalog's 20, against a first
    # reading of "30 files changed, the catalog needs re-curating" that was
    # inferred from the build's first error rather than measured.
    #
    # How these were obtained is worth recording, because it is what made the
    # 0.9.46 advance possible at all: `_authority_reasons` now prints OBSERVED vs
    # ACCEPTED for every drifted key (#373). Before that it named the key only
    # and deleted its output, so the build could not tell you what to move the
    # constants to while refusing to run until you had.
    detected_count=452,
    # FORKED 2026-08-24, then REBASED onto upstream v0.9.49 the same day:
    # 429 -> 450 detected, 421 -> 442 extracted. RE-DERIVED
    # by a real `kb-graphify-baseline build` against the INSTALLED fork, never
    # carried forward, exactly as the note above requires.
    #
    # The +21/+21 is ACCOUNTED FOR rather than assumed, and it is the sanity
    # check on the whole fork: #2981's own test files, the test files of the
    # three sibling features replanted with it, and v0.9.49's ten new test
    # modules. Every newly
    # detected file was also extracted, so the gap between the two counts is
    # UNCHANGED at 8 and no warning was emitted. A fork that changed the gap
    # would mean it changed EXTRACTION behaviour, which is the thing a
    # backend-only addition must not do.
    # REBASED 2026-08-25 onto upstream v0.9.50, plus an eighth fork commit:
    # 450 -> 452 detected, 442 -> 444 extracted. RE-DERIVED by a real
    # `kb-graphify-baseline build` against the INSTALLED fork, never carried
    # forward — the same run reproduced `source_tree` independently, which is
    # what makes these counts a measurement rather than an inheritance.
    #
    # The +2/+2 is ACCOUNTED FOR rather than assumed:
    # `compare/282976b2...43d54acb` lists exactly TWO added files,
    # `tests/test_csharp_enum_members.py` and
    # `tests/test_typescript_enum_members.py` — ordinary supported source, so
    # neither needed a disposition entry. Nothing was removed. The gap between
    # the two counts is UNCHANGED at 8: our eighth commit is backend-only and a
    # backend-only change must not move extraction behaviour.
    #
    # ONE catalog entry moved, again `uv.lock` (upstream f725eec synced it for
    # the postgres tree-sitter-sql extra), out of the catalog's 20.
    #
    # All three drifted authority values came from the build's own OBSERVED vs
    # ACCEPTED diagnostic (#373) rather than a hand derivation — which is the
    # thing that note says it exists to prevent, and it worked.
    extracted_count=444,
)
# The ignored-path control's fixture: an UNTRACKED file under a directory the
# pinned source's own `.gitignore` matches. Untracked is load-bearing.
#
# Until 0.9.44 this control force-ADDED the file (`git add -f`), making it
# TRACKED, and asserted a `disposition-evidence-mismatch` — which came from the
# tree digest moving, not from anything being ignored. graphify #2759 then
# stopped treating a tracked ignored path as ignored at all (matching git, which
# never un-tracks such a file), so that arm was one release away from measuring
# nothing while still reporting green.
#
# Armed at 0.9.44 across three repos before this was rewritten: tracked+ignored
# emits NO `ignored` key and lands in `files.document`; untracked+ignored emits
# `ignored`; and a control repo with no `.gitignore` emits neither — so the probe
# discriminates and the kind is measurably still live. The earlier plan to retire
# `DispositionKind.IGNORED_TREE` outright was refuted by exactly that run.
_CONTROL_IGNORED_PATH = "docs/superpowers/issue-299-control.md"
_EXPECTED_CONTROL_RESULTS = {
    "clean": ("complete", ()),
    "unknown-file": ("failed", ("unclassified-files", "unknown.issue299")),
    "changed-reviewed-file": (
        "failed",
        ("disposition-evidence-mismatch:.dockerignore",),
    ),
    "untracked-ignored-path": ("failed", ("ignored-paths",)),
    "post-admission-snapshot-drift": ("failed", ("source-snapshot-drift",)),
}
_REQUIRED_MEMBERS = frozenset(
    {
        "ast-graph.json",
        "source-census.json",
        "source-manifest.json",
        "build-receipt.json",
        "health.json",
        "runtime.json",
        "controls.json",
        "dispositions.json",
    }
)


def _lock_hash(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError(f"Graphify {label} lock hash is missing or malformed")
    return value.removeprefix("sha256:")


def _locked_distribution(package: dict[str, object]) -> dict[str, str]:
    """The locked distribution's identity fields, for a PyPI **or** a git install.

    Two shapes, and the git one is not a special case bolted on — it is what
    `uv.lock` genuinely contains once a dependency is pinned to a fork:

    * PyPI — a `wheels` list and an `sdist` table, each with a `sha256:` hash.
    * git  — NEITHER key exists. uv writes only
      ``source = {git = "<url>?rev=<sha>#<resolved-sha>"}``, and the fragment
      after ``#`` is the RESOLVED commit, which is the identity to bind.

    The old code demanded exactly one wheel and raised
    "must bind exactly one universal wheel" otherwise. That message is correct
    for a PyPI pin and actively misleading for a git one — it reads as a
    malformed lock rather than a differently-shaped one — which is exactly how it
    presented when graphify was forked: a hard failure in the runtime-identity
    gate, several layers away from the pin that caused it.

    Raises rather than returning a partial identity: a runtime whose distribution
    cannot be identified must not be blessed, and "no hash and no commit" is the
    one state that would let it be.
    """
    source = package.get("source")
    if isinstance(source, dict) and isinstance(source.get("git"), str):
        _, separator, resolved = source["git"].partition("#")
        if not separator or not re.fullmatch(r"[0-9a-f]{40}", resolved):
            raise ValueError(
                "Graphify uv.lock git source has no resolved 40-hex commit after '#' — "
                "the lock does not pin an exact tree"
            )
        return {"git_commit": resolved}
    wheels = package.get("wheels")
    if not isinstance(wheels, list) or len(wheels) != 1 or not isinstance(wheels[0], dict):
        raise ValueError("Graphify uv.lock entry must bind exactly one universal wheel")
    sdist = package.get("sdist")
    if not isinstance(sdist, dict):
        raise TypeError("Graphify uv.lock entry has no source distribution")
    return {
        "wheel_sha256": _lock_hash(wheels[0].get("hash"), label="wheel"),
        "sdist_sha256": _lock_hash(sdist.get("hash"), label="sdist"),
    }


def runtime_identity(repo_root: Path) -> RuntimeIdentity:
    """Prove the installed Graphify runtime agrees with the exact uv lock artifacts."""
    from kb_setup import graphify_env, graphify_sdk

    graphify_env.assert_pinned_graphify(repo_root)
    try:
        with (repo_root / "uv.lock").open("rb") as stream:
            lock = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"unreadable uv.lock: {exc}") from exc
    packages = [
        package
        for package in lock.get("package", [])
        if isinstance(package, dict) and package.get("name") == "graphifyy"
    ]
    if len(packages) != 1:
        raise ValueError(f"uv.lock must contain exactly one graphifyy package, got {len(packages)}")
    package = packages[0]
    version = str(package.get("version", ""))
    distribution = _locked_distribution(package)
    executable_path = Path(graphify_env.graphify_exe(repo_root))
    try:
        executable = str(executable_path.relative_to(repo_root))
    except ValueError as exc:
        raise ValueError("Graphify executable is outside the repository runtime") from exc
    fingerprint = json.dumps(
        graphify_sdk.public_api_fingerprint(),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    identity = RuntimeIdentity(
        version=version,
        cli_version=graphify_env.running_graphify_version(str(executable_path)),
        sdk_version=graphify_sdk.running_sdk_version(),
        executable=executable,
        sdk_fingerprint_sha256=hashlib.sha256(fingerprint).hexdigest(),
        wheel_sha256=distribution.get("wheel_sha256", ""),
        sdist_sha256=distribution.get("sdist_sha256", ""),
        git_commit=distribution.get("git_commit", ""),
    )
    if {identity.version, identity.cli_version, identity.sdk_version} != {
        graphify_env.pinned_graphify_version(repo_root)
    }:
        raise ValueError(
            "Graphify release, CLI, SDK, and locked distribution versions do not agree"
        )
    return identity


def historical_graphify_manifest(
    repo_root: Path, *, ref: str, commit: str
) -> source_manifests.Manifest:
    """Reuse the reviewed Graphify remote while pinning historical evidence explicitly."""
    current = source_manifests.load(repo_root / "sources" / "graphify.manifest")
    if (current.name, current.url, current.kind) != (
        "graphify",
        _ACCEPTED_GRAPHIFY_URL,
        "code",
    ):
        raise ValueError("Graphify historical source remote identity drifted")
    return replace(current, ref=ref, commit=commit)


def _git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return result.stdout


def _git_text(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout


def _git_blob_batch(root: Path, object_ids: tuple[str, ...]) -> dict[str, bytes]:
    unique_ids = tuple(dict.fromkeys(object_ids))
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=("\n".join(unique_ids) + "\n").encode(),
        check=True,
        capture_output=True,
        timeout=120,
    )
    output = result.stdout
    offset = 0
    blobs: dict[str, bytes] = {}
    for expected_id in unique_ids:
        header_end = output.find(b"\n", offset)
        if header_end < 0:
            raise ValueError("Git blob batch ended before its header")
        observed_id, object_type, raw_size = output[offset:header_end].decode("ascii").split()
        if observed_id != expected_id or object_type != "blob":
            raise ValueError(f"Git blob batch identity/type mismatch for {expected_id}")
        size = int(raw_size)
        start = header_end + 1
        end = start + size
        if end >= len(output) or output[end : end + 1] != b"\n":
            raise ValueError(f"Git blob batch truncated object {expected_id}")
        blobs[expected_id] = output[start:end]
        offset = end + 1
    if offset != len(output):
        raise ValueError("Git blob batch returned trailing bytes")
    return blobs


def source_manifest(root: Path, *, commit: str, tree: str) -> SourceManifest:
    """Inventory every Git blob and reject a worktree that differs from it."""
    observed_commit = _git_text(root, "rev-parse", "HEAD^{commit}").strip()
    observed_tree = _git_text(root, "rev-parse", "HEAD^{tree}").strip()
    status = _git_text(root, "status", "--porcelain=v1", "--untracked-files=all")
    if observed_commit != commit or observed_tree != tree or status:
        raise ValueError("source-snapshot-drift: Git identity or worktree bytes changed")
    raw_tree = _git_bytes(root, "ls-tree", "-rz", "--full-tree", commit)
    records = tuple(record for record in raw_tree.split(b"\0") if record)
    object_ids = tuple(
        record.split(b"\t", 1)[0].decode("ascii").split(" ", 2)[2] for record in records
    )
    blobs = _git_blob_batch(root, object_ids)
    members: list[SourceMember] = []
    for record in records:
        metadata, encoded_path = record.split(b"\t", 1)
        mode, object_type, git_object = metadata.decode("ascii").split(" ", 2)
        if object_type != "blob":
            raise ValueError(
                f"source manifest cannot bind non-blob entry {encoded_path!r}: {object_type}"
            )
        path = encoded_path.decode("utf-8")
        blob = blobs[git_object]
        worktree_path = root / path
        try:
            current = (
                str(worktree_path.readlink()).encode()
                if mode == "120000"
                else worktree_path.read_bytes()
            )
        except OSError as exc:
            raise ValueError(f"source-snapshot-drift:{path}: {exc}") from exc
        if current != blob:
            raise ValueError(f"source-snapshot-drift:{path}: worktree differs from Git blob")
        members.append(
            SourceMember(
                path=path,
                mode=mode,
                git_object=git_object,
                sha256=hashlib.sha256(blob).hexdigest(),
                size=len(blob),
            )
        )
    return SourceManifest(
        source="graphify",
        commit=commit,
        tree=tree,
        members=tuple(members),
    )


def load_disposition_catalog(repo_root: Path) -> DispositionCatalog:
    """Load and validate the committed Graphify omission authority."""
    path = repo_root / "sources" / "graphify.dispositions.json"
    try:
        catalog = msgspec.json.decode(path.read_bytes(), type=DispositionCatalog)
    except (OSError, msgspec.DecodeError) as exc:
        raise ValueError(f"unreadable Graphify disposition catalog: {exc}") from exc
    if catalog.schema_version != 1:
        raise ValueError(f"unsupported Graphify disposition schema: {catalog.schema_version}")
    if catalog.source != "graphify":
        raise ValueError(f"disposition catalog source must be graphify, got {catalog.source!r}")
    if catalog.source_ref != _ACCEPTED_GRAPHIFY_REF:
        raise ValueError(f"disposition catalog source_ref is not {_ACCEPTED_GRAPHIFY_REF}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", catalog.source_commit):
        raise ValueError("disposition catalog source_commit is not an immutable Git identity")
    if not re.fullmatch(r"[0-9a-f]{40,64}", catalog.source_tree):
        raise ValueError("disposition catalog source_tree is not an immutable Git identity")
    keys = [(entry.kind, entry.path) for entry in catalog.entries]
    if len(keys) != len(set(keys)):
        raise ValueError("disposition catalog contains duplicate kind/path entries")
    for entry in catalog.entries:
        if (
            not entry.path
            or not entry.reason.strip()
            or not re.fullmatch(r"[0-9a-f]{64}", entry.sha256)
            or entry.size < 0
            or not entry.file_type
            or (
                entry.kind
                in {
                    DispositionKind.ZERO_NODE_FILE,
                    DispositionKind.COMPATIBILITY_CORRECTION,
                }
                and not entry.extraction_disposition
            )
        ):
            raise ValueError(f"invalid disposition catalog entry: {entry.path!r}")
    return catalog


def _json_member(path: Path, reasons: list[str]) -> object | None:
    try:
        return json.loads(path.read_bytes())
    except OSError, json.JSONDecodeError, UnicodeDecodeError:
        reasons.append(f"member-corrupt:{path.name}")
        return None


def _manifest_structure_reasons(manifest: CandidateManifest) -> list[str]:
    reasons: list[str] = []
    if manifest.schema_id != _BASELINE_SCHEMA:
        reasons.append("schema-mismatch")
    if manifest.source != "graphify":
        reasons.append("source-scope-mismatch")
    if manifest.source_ref != _ACCEPTED_GRAPHIFY_REF:
        reasons.append("source-ref-mismatch")
    if not re.fullmatch(r"[0-9a-f]{40,64}", manifest.source_commit):
        reasons.append("source-commit-invalid")
    if not re.fullmatch(r"[0-9a-f]{40,64}", manifest.source_tree):
        reasons.append("source-tree-invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest.catalog_sha256):
        reasons.append("catalog-digest-invalid")
    if manifest.warnings:
        reasons.append("warning-bearing")
        if any("truncated" in warning.casefold() for warning in manifest.warnings):
            reasons.append("truncated")
    return reasons


def _member_reasons(
    candidate: Path, manifest: CandidateManifest
) -> tuple[list[str], dict[str, object]]:
    reasons: list[str] = []
    payloads: dict[str, object] = {}
    by_name = {member.name: member for member in manifest.members}
    if len(by_name) != len(manifest.members):
        reasons.append("member-duplicate")
    dispositions = by_name.get("dispositions.json")
    if dispositions is not None and dispositions.sha256 != manifest.catalog_sha256:
        reasons.append("catalog-digest-mismatch")
    reasons.extend(f"member-omitted:{name}" for name in sorted(_REQUIRED_MEMBERS - by_name.keys()))
    reasons.extend(
        f"member-unexpected:{name}" for name in sorted(by_name.keys() - _REQUIRED_MEMBERS)
    )
    for name in sorted(_REQUIRED_MEMBERS & by_name.keys()):
        member = by_name[name]
        path = candidate / name
        try:
            raw = path.read_bytes()
        except OSError:
            reasons.append(f"member-missing:{name}")
            continue
        if len(raw) != member.size:
            reasons.append(f"member-size-mismatch:{name}")
        if hashlib.sha256(raw).hexdigest() != member.sha256:
            reasons.append(f"member-digest-mismatch:{name}")
        payload = _json_member(path, reasons)
        if payload is not None:
            payloads[name] = payload
    return reasons, payloads


def _candidate_entry_reasons(candidate: Path) -> list[str]:
    expected = _REQUIRED_MEMBERS | {"manifest.json"}
    try:
        entries = tuple(candidate.iterdir())
    except OSError:
        return ["candidate-directory-unreadable"]
    by_name = {entry.name: entry for entry in entries}
    reasons = [
        *(f"candidate-entry-omitted:{name}" for name in sorted(expected - by_name.keys())),
        *(f"candidate-entry-unexpected:{name}" for name in sorted(by_name.keys() - expected)),
    ]
    reasons.extend(
        f"candidate-entry-invalid:{name}"
        for name in sorted(expected & by_name.keys())
        if by_name[name].is_symlink() or not by_name[name].is_file()
    )
    return reasons


def _graph_payload_reasons(payload: object) -> list[str]:
    reasons: list[str] = []
    if not isinstance(payload, dict):
        return ["member-schema-mismatch:ast-graph.json"]
    nodes = payload.get("nodes")
    edges = payload.get("links")
    hyperedges = payload.get("hyperedges")
    if not isinstance(nodes, list) or not nodes:
        reasons.append("zero-node-ast-graph")
    valid_nodes = isinstance(nodes, list) and all(
        isinstance(item, dict) and isinstance(item.get("id"), str) and bool(item["id"])
        for item in nodes
    )
    required_edge_fields = ("source", "target", "relation", "confidence", "_origin")
    valid_edges = isinstance(edges, list) and all(
        isinstance(item, dict)
        and all(
            isinstance(item.get(field), str) and bool(item[field]) for field in required_edge_fields
        )
        for item in edges
    )
    valid_hyperedges = isinstance(hyperedges, list) and all(
        isinstance(item, dict) and bool(item) for item in hyperedges
    )
    if not valid_nodes or not valid_edges or not valid_hyperedges:
        reasons.append("ast-graph-schema-mismatch")
    return reasons


def _build_payload_reasons(payload: object) -> list[str]:
    reasons: list[str] = []
    if not isinstance(payload, dict):
        return ["member-schema-mismatch:build-receipt.json"]
    if payload.get("status") != "complete":
        reasons.append("build-incomplete")
    if payload.get("warnings"):
        reasons.append("build-warning-bearing")
    if payload.get("runtime_version") != _ACCEPTED_GRAPHIFY_VERSION:
        reasons.append("build-runtime-version-drift")
    if payload.get("approved_classifications") != []:
        reasons.append("build-approved-classifications")
    if not isinstance(payload.get("node_count"), int) or payload.get("node_count", 0) <= 0:
        reasons.append("build-zero-node")
    return reasons


def _runtime_payload_reasons(payload: object) -> list[str]:
    reasons: list[str] = []
    if not isinstance(payload, dict):
        return ["member-schema-mismatch:runtime.json"]
    versions = {payload.get(key) for key in ("version", "cli_version", "sdk_version")}
    if versions != {_ACCEPTED_GRAPHIFY_VERSION}:
        reasons.append("runtime-version-drift")
    if payload.get("executable") != _ACCEPTED_GRAPHIFY_EXECUTABLE:
        reasons.append("runtime-executable-drift")
    reasons.extend(
        f"runtime-identity-drift:{key}"
        for key, expected in _ACCEPTED_RUNTIME_HASHES.items()
        if payload.get(key) != expected
    )
    return reasons


def _controls_payload_reasons(payload: object) -> list[str]:
    if not isinstance(payload, dict) or payload.get("state") != "complete":
        return ["controls-incomplete"]
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return ["controls-schema-mismatch"]
    observed: dict[str, tuple[str, tuple[str, ...]]] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("reasons"), list):
            return ["controls-schema-mismatch"]
        name = str(case.get("name"))
        if name in observed or case.get("observed") != case.get("expected"):
            return ["controls-incomplete"]
        observed[name] = (str(case.get("observed")), tuple(map(str, case["reasons"])))
    return [] if observed == _EXPECTED_CONTROL_RESULTS else ["controls-incomplete"]


def _member_tree_evidence(
    source_manifest: SourceManifest, relative_path: str
) -> tuple[str, int, str]:
    prefix = f"{relative_path.rstrip('/')}/"
    files = {
        member.path.removeprefix(prefix): member
        for member in source_manifest.members
        if member.path.startswith(prefix)
    }
    directories = {
        str(parent) for path in files for parent in Path(path).parents if str(parent) != "."
    }
    digest = hashlib.sha256()
    total_size = 0
    for path in sorted((*directories, *files)):
        digest.update(path.encode())
        is_directory = path in directories
        digest.update(b"\0d\0" if is_directory else b"\0f\0")
        if not is_directory:
            member = files[path]
            total_size += member.size
            digest.update(bytes.fromhex(member.sha256))
    return digest.hexdigest(), total_size, f"snapshot-tree:{len(directories) + len(files)}"


def _decode_catalog_payloads(
    payloads: dict[str, object],
) -> tuple[DispositionCatalog, SourceManifest, graph.DetectionCensusReceipt] | None:
    try:
        catalog = msgspec.convert(payloads.get("dispositions.json"), type=DispositionCatalog)
        source = msgspec.convert(payloads.get("source-manifest.json"), type=SourceManifest)
        census = msgspec.convert(
            payloads.get("source-census.json"), type=graph.DetectionCensusReceipt
        )
    except TypeError, msgspec.ValidationError:
        return None
    return catalog, source, census


def _catalog_entry_reasons(catalog: DispositionCatalog, source: SourceManifest) -> list[str]:
    if not source.members or len({member.path for member in source.members}) != len(source.members):
        return ["source-manifest-incomplete"]
    by_path = {member.path: member for member in source.members}
    reasons: list[str] = []
    for entry in catalog.entries:
        if entry.file_type.startswith("snapshot-tree:"):
            evidence = _member_tree_evidence(source, entry.path)
        else:
            member = by_path.get(entry.path)
            evidence = (
                (member.sha256, member.size, "regular")
                if member is not None and member.mode != "120000"
                else ("", -1, "missing")
            )
        if evidence != (entry.sha256, entry.size, entry.file_type):
            reasons.append(f"catalog-source-mismatch:{entry.path}")
    return reasons


def _catalog_coverage_reasons(
    catalog: DispositionCatalog,
    census: graph.DetectionCensusReceipt,
    build: dict[str, object],
) -> list[str]:
    if len(census.sources) != 1:
        return ["source-census-scope-mismatch"]
    observed_unclassified = {item.path for item in census.sources[0].unclassified}
    observed_ignored = {item.path for item in census.sources[0].ignored}
    expected_unclassified = {
        item.path for item in catalog.entries if item.kind is DispositionKind.UNSUPPORTED_FILE
    }
    expected_ignored = {
        item.path for item in catalog.entries if item.kind is DispositionKind.IGNORED_TREE
    }
    expected_zero = {
        item.path for item in catalog.entries if item.kind is DispositionKind.ZERO_NODE_FILE
    }
    expected_excluded = {
        item.path for item in catalog.entries if item.kind is DispositionKind.EXCLUDED_AST_FIXTURE
    }
    reviewed_metadata_paths = build.get("reviewed_metadata_paths")
    zero_node_paths = build.get("zero_node_paths")
    excluded_paths = build.get("excluded_paths")
    observed_zero = (
        {str(item) for item in zero_node_paths} if isinstance(zero_node_paths, list) else set()
    )
    observed_metadata = (
        {str(item) for item in reviewed_metadata_paths}
        if isinstance(reviewed_metadata_paths, list)
        else set()
    )
    observed_excluded = (
        {str(item) for item in excluded_paths} if isinstance(excluded_paths, list) else set()
    )
    comparisons = (
        (observed_unclassified, expected_unclassified, "catalog-unclassified-mismatch"),
        (observed_ignored, expected_ignored, "catalog-ignored-mismatch"),
        (
            observed_metadata,
            expected_zero,
            "catalog-reviewed-metadata-mismatch",
        ),
        (
            observed_excluded,
            expected_excluded,
            "catalog-excluded-mismatch",
        ),
    )
    reasons = [reason for observed, expected, reason in comparisons if observed != expected]
    if isinstance(reviewed_metadata_paths, list) and len(reviewed_metadata_paths) != len(
        observed_metadata
    ):
        reasons.append("catalog-reviewed-metadata-duplicate")
    if observed_zero:
        reasons.append("runtime-zero-node-input")
    detected_count = build.get("detected_count")
    extracted_count = build.get("extracted_count")
    if not isinstance(detected_count, int) or not isinstance(extracted_count, int):
        reasons.append("build-source-count-mismatch")
    else:
        expected_detected = extracted_count + len(expected_zero) + len(expected_excluded)
        if detected_count != expected_detected:
            reasons.append("build-source-count-mismatch")
    return reasons


def _catalog_payload_reasons(payloads: dict[str, object]) -> list[str]:
    decoded = _decode_catalog_payloads(payloads)
    if decoded is None:
        return ["catalog-source-schema-mismatch"]
    catalog, source, census = decoded
    build = payloads["build-receipt.json"]
    if not isinstance(build, dict):
        return ["member-schema-mismatch:build-receipt.json"]
    return [
        *_catalog_entry_reasons(catalog, source),
        *_catalog_coverage_reasons(catalog, census, build),
        *_compatibility_correction_payload_reasons(catalog, build, payloads),
    ]


def _compatibility_correction_payload_reasons(
    catalog: DispositionCatalog,
    build: dict[str, object],
    payloads: dict[str, object],
) -> list[str]:
    entries = tuple(
        entry for entry in catalog.entries if entry.kind is DispositionKind.COMPATIBILITY_CORRECTION
    )
    raw_receipts = build.get("compatibility_corrections", [])
    try:
        receipts = msgspec.convert(raw_receipts, type=tuple[CompatibilityCorrection, ...])
        expected = tuple(_lpk_correction_receipt(entry) for entry in entries)
    except TypeError, ValueError, msgspec.ValidationError:
        return ["compatibility-correction-mismatch"]
    if receipts != expected:
        return ["compatibility-correction-mismatch"]
    if not expected:
        return []
    graph_payload = payloads.get("ast-graph.json")
    if not isinstance(graph_payload, dict):
        return ["compatibility-correction-graph-mismatch"]
    nodes = graph_payload.get("nodes")
    links = graph_payload.get("links")
    if (
        not isinstance(nodes, list)
        or not isinstance(links, list)
        or any(not isinstance(node, dict) for node in nodes)
        or any(not isinstance(link, dict) for link in links)
    ):
        return ["compatibility-correction-graph-mismatch"]
    node_ids = [node.get("id") for node in nodes]
    expected_nodes = {
        _LPK_FILE_ID: ("sample.lpk", _LPK_CORRECTION_PATH),
        _PAS_FILE_ID: ("sample.pas", _PAS_SOURCE_PATH),
        _LPK_PACKAGE_ID: ("SamplePackage", _LPK_CORRECTION_PATH),
    }
    matching_nodes = {
        node_id: [node for node in nodes if node.get("id") == node_id] for node_id in expected_nodes
    }
    nodes_valid = (
        all(isinstance(node_id, str) for node_id in node_ids)
        and len(node_ids) == len(set(node_ids))
        and all(
            len(matches) == 1
            and (
                matches[0].get("label"),
                matches[0].get("source_file"),
                matches[0].get("file_type"),
                matches[0].get("_origin"),
                matches[0].get("source_location"),
            )
            == (*expected_nodes[node_id], "code", "ast", "L1")
            for node_id, matches in matching_nodes.items()
        )
    )
    expected_edges = {
        (_LPK_FILE_ID, _LPK_PACKAGE_ID),
        (_LPK_PACKAGE_ID, _PAS_FILE_ID),
    }
    correction_pairs = {
        *expected_edges,
        (_LPK_PACKAGE_ID, _LPK_FILE_ID),
        (_LPK_FILE_ID, _LPK_FILE_ID),
        (_LPK_PACKAGE_ID, _LPK_PACKAGE_ID),
        (_PAS_FILE_ID, _PAS_FILE_ID),
    }
    relevant_links = [
        link for link in links if (link.get("source"), link.get("target")) in correction_pairs
    ]
    links_valid = len(relevant_links) == len(expected_edges) and all(
        (link.get("source"), link.get("target")) in expected_edges
        and link.get("relation") == "contains"
        and link.get("confidence") == "EXTRACTED"
        and link.get("_origin") == "ast"
        and link.get("source_file") == _LPK_CORRECTION_PATH
        and link.get("source_location") == "L1"
        and link.get("weight") == 1.0
        and link.get("confidence_score") == 1.0
        for link in relevant_links
    )
    valid = (
        nodes_valid
        and links_valid
        and {(link.get("source"), link.get("target")) for link in relevant_links} == expected_edges
    )
    return [] if valid else ["compatibility-correction-graph-mismatch"]


def _identity_payload_reasons(
    manifest: CandidateManifest, payloads: dict[str, object]
) -> list[str]:
    reasons: list[str] = []
    expected = (manifest.source_commit, manifest.source_tree)
    for name in (
        "source-manifest.json",
        "build-receipt.json",
        "health.json",
        "controls.json",
        "dispositions.json",
    ):
        payload = payloads.get(name)
        if (
            isinstance(payload, dict)
            and (
                payload.get("source_commit", payload.get("commit")),
                payload.get("source_tree", payload.get("tree")),
            )
            != expected
        ):
            reasons.append(f"source-identity-mismatch:{name}")
    graph_payload = payloads.get("ast-graph.json")
    if isinstance(graph_payload, dict) and graph_payload.get("built_at_commit") != expected[0]:
        reasons.append("source-identity-mismatch:ast-graph.json")
    census = payloads.get("source-census.json")
    census_sources = census.get("sources") if isinstance(census, dict) else None
    if (
        not isinstance(census_sources, list)
        or len(census_sources) != 1
        or not isinstance(census_sources[0], dict)
        or (
            census_sources[0].get("source"),
            census_sources[0].get("resolved_commit"),
            census_sources[0].get("tree_digest"),
        )
        != (manifest.source, *expected)
    ):
        reasons.append("source-census-scope-mismatch")
    return reasons


def _census_payload_reasons(payloads: dict[str, object]) -> list[str]:
    if "source-census.json" not in payloads:
        return []
    census = payloads.get("source-census.json")
    if not isinstance(census, dict):
        return ["member-schema-mismatch:source-census.json"]
    return (
        ["source-census-incomplete"]
        if census.get("state") != "complete" or census.get("total_sources") != 1
        else []
    )


def _source_manifest_payload_reasons(
    manifest: CandidateManifest, payloads: dict[str, object]
) -> list[str]:
    if "source-manifest.json" not in payloads:
        return []
    source_manifest = payloads.get("source-manifest.json")
    if not isinstance(source_manifest, dict):
        return ["member-schema-mismatch:source-manifest.json"]
    return (
        ["source-manifest-scope-mismatch"]
        if source_manifest.get("source") != manifest.source
        else []
    )


def _health_payload_reasons(payloads: dict[str, object]) -> list[str]:
    if "health.json" not in payloads:
        return []
    health = payloads.get("health.json")
    if not isinstance(health, dict):
        return ["member-schema-mismatch:health.json"]
    comparisons = (
        (health.get("state") != "complete", "health-incomplete"),
        (bool(health.get("warnings")), "health-warning-bearing"),
    )
    return [reason for failed, reason in comparisons if failed]


def _disposition_payload_reasons(
    manifest: CandidateManifest, payloads: dict[str, object]
) -> list[str]:
    if "dispositions.json" not in payloads:
        return []
    dispositions = payloads.get("dispositions.json")
    if not isinstance(dispositions, dict) or dispositions.get("source") != manifest.source:
        return ["disposition-catalog-scope-mismatch"]
    return (
        ["source-ref-mismatch:dispositions.json"]
        if dispositions.get("source_ref") != manifest.source_ref
        else []
    )


def _graph_build_count_reasons(payloads: dict[str, object]) -> list[str]:
    graph_payload = payloads.get("ast-graph.json")
    build_payload = payloads.get("build-receipt.json")
    if not isinstance(graph_payload, dict) or not isinstance(build_payload, dict):
        return []
    nodes = graph_payload.get("nodes")
    links = graph_payload.get("links")
    hyperedges = graph_payload.get("hyperedges")
    if (
        not isinstance(nodes, list)
        or not isinstance(links, list)
        or not isinstance(hyperedges, list)
    ):
        return ["graph-build-count-mismatch"]
    counts = (len(nodes), len(links), len(hyperedges))
    expected = (
        build_payload.get("node_count"),
        build_payload.get("edge_count"),
        build_payload.get("hyperedge_count"),
    )
    return ["graph-build-count-mismatch"] if counts != expected else []


def _payload_reasons(manifest: CandidateManifest, payloads: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if "ast-graph.json" in payloads:
        reasons.extend(_graph_payload_reasons(payloads["ast-graph.json"]))
    reasons.extend(_census_payload_reasons(payloads))
    reasons.extend(_source_manifest_payload_reasons(manifest, payloads))
    if "build-receipt.json" in payloads:
        reasons.extend(_build_payload_reasons(payloads["build-receipt.json"]))
    reasons.extend(_health_payload_reasons(payloads))
    if "runtime.json" in payloads:
        reasons.extend(_runtime_payload_reasons(payloads["runtime.json"]))
    if "controls.json" in payloads:
        reasons.extend(_controls_payload_reasons(payloads["controls.json"]))
    reasons.extend(_disposition_payload_reasons(manifest, payloads))
    reasons.extend(_graph_build_count_reasons(payloads))
    if {
        "dispositions.json",
        "source-manifest.json",
        "source-census.json",
        "build-receipt.json",
    } <= payloads.keys():
        reasons.extend(_catalog_payload_reasons(payloads))
    reasons.extend(_identity_payload_reasons(manifest, payloads))
    return reasons


def _authority_reasons(
    manifest: CandidateManifest,
    authority: BaselineAuthority,
    payloads: dict[str, object],
) -> list[str]:
    by_name = {member.name: member for member in manifest.members}
    source_manifest = by_name.get("source-manifest.json")
    comparisons = (
        (manifest.source_ref, authority.source_ref, "authority-source-ref-mismatch"),
        (manifest.source_commit, authority.source_commit, "authority-source-commit-mismatch"),
        (manifest.source_tree, authority.source_tree, "authority-source-tree-mismatch"),
        (manifest.catalog_sha256, authority.catalog_sha256, "authority-catalog-mismatch"),
        (
            source_manifest.sha256 if source_manifest else None,
            authority.source_manifest_sha256,
            "authority-source-manifest-mismatch",
        ),
    )
    reasons = [reason for observed, expected, reason in comparisons if observed != expected]
    build = payloads.get("build-receipt.json")
    observed_counts = (
        (build.get("detected_count"), build.get("extracted_count"))
        if isinstance(build, dict)
        else None
    )
    accepted_counts = (authority.detected_count, authority.extracted_count)
    if observed_counts != accepted_counts:
        reasons.append("authority-build-count-mismatch")

    # Report OBSERVED vs ACCEPTED to stderr — never into `reasons`, which is a
    # machine-readable code other code and tests match on exactly. Overloading a
    # code with a human message was the first shape of this fix and it broke two
    # `"<code>" in receipt.reasons` assertions; the code is the contract, the
    # diagnostic is a different channel.
    #
    # Why the diagnostic exists at all: naming the drifted key without its values
    # is what made a graphify bump a multi-hour derivation chain. The build
    # refuses until these constants move and was the only thing that could
    # honestly say what to move them TO — then it deleted its output. Five
    # re-plans did not close that loop; printing the pair turns the next bump
    # into reading one line. (#373)
    details = [
        f"  {reason}: observed {observed!r}, accepted {expected!r}"
        for observed, expected, reason in comparisons
        if observed != expected
    ]
    if observed_counts != accepted_counts:
        details.append(
            f"  authority-build-count-mismatch: observed {observed_counts!r}, "
            f"accepted {accepted_counts!r}"
        )
    if details:
        print(
            "[graphify-baseline] authority drift — move these in _ACCEPTED_AUTHORITY:",
            *details,
            sep="\n",
            file=sys.stderr,
        )
    return reasons


def _verify_candidate(candidate: Path, authority: BaselineAuthority) -> BaselineVerification:
    entry_reasons = _candidate_entry_reasons(candidate)
    if entry_reasons:
        return BaselineVerification(
            state=BaselineState.FAILED,
            deterministic_complete=False,
            reasons=tuple(entry_reasons),
        )
    manifest_path = candidate / "manifest.json"
    try:
        manifest = msgspec.json.decode(manifest_path.read_bytes(), type=CandidateManifest)
    except OSError:
        return BaselineVerification(
            state=BaselineState.FAILED,
            deterministic_complete=False,
            reasons=("manifest-missing",),
        )
    except msgspec.DecodeError:
        return BaselineVerification(
            state=BaselineState.FAILED,
            deterministic_complete=False,
            reasons=("manifest-corrupt",),
        )
    reasons = _manifest_structure_reasons(manifest)
    member_reasons, payloads = _member_reasons(candidate, manifest)
    reasons.extend(member_reasons)
    reasons.extend(_authority_reasons(manifest, authority, payloads))
    reasons.extend(_payload_reasons(manifest, payloads))
    if manifest.semantic_evidence_present:
        reasons.append("uncertified-semantic-evidence")
    if manifest.release_evidence_present:
        reasons.append("uncertified-release-evidence")
    if reasons:
        return BaselineVerification(
            state=BaselineState.FAILED,
            deterministic_complete=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    return BaselineVerification(
        state=BaselineState.INCOMPLETE,
        deterministic_complete=True,
        reasons=("semantic-evidence-missing", "release-evidence-missing"),
    )


def verify_candidate(candidate: Path) -> BaselineVerification:
    """Verify one candidate against the immutable accepted Graphify trust root."""
    return _verify_candidate(candidate, _ACCEPTED_AUTHORITY)


def verify_dispositions(
    root: Path,
    catalog: DispositionCatalog,
    *,
    unclassified: tuple[graph.SourcePathEvidence, ...],
    ignored: tuple[graph.SourcePathEvidence, ...],
) -> DispositionVerification:
    """Fail closed unless observed omissions equal the reviewed catalog exactly."""
    observed = {
        (kind, item.path): item
        for kind, items in (
            (DispositionKind.UNSUPPORTED_FILE, unclassified),
            (DispositionKind.IGNORED_TREE, ignored),
        )
        for item in items
    }
    expected = {
        (entry.kind, entry.path): entry
        for entry in catalog.entries
        if entry.kind in {DispositionKind.UNSUPPORTED_FILE, DispositionKind.IGNORED_TREE}
    }
    reasons: list[str] = []
    for kind, path in sorted(expected.keys() - observed.keys()):
        reasons.append(f"missing-disposition:{kind.value}:{path}")
    for kind, path in sorted(observed.keys() - expected.keys()):
        reasons.append(f"unexpected-disposition:{kind.value}:{path}")
    for key in sorted(expected.keys() & observed.keys()):
        entry = expected[key]
        evidence = observed[key]
        if (entry.sha256, entry.size, entry.file_type) != (
            evidence.sha256,
            evidence.size,
            evidence.file_type,
        ):
            reasons.append(f"disposition-evidence-mismatch:{entry.path}")
            continue
        current = graph.source_path_evidence(root, entry.path)
        if (current.sha256, current.size, current.file_type) != (
            evidence.sha256,
            evidence.size,
            evidence.file_type,
        ):
            reasons.append(f"source-snapshot-drift:{entry.path}")
    return DispositionVerification(
        state=BaselineState.COMPLETE if not reasons else BaselineState.FAILED,
        reasons=tuple(reasons),
    )


def verify_catalog_bytes(root: Path, catalog: DispositionCatalog) -> DispositionVerification:
    """Verify every reviewed disposition against the current snapshot bytes."""
    reasons: list[str] = []
    for entry in catalog.entries:
        current = graph.source_path_evidence(root, entry.path)
        if (current.sha256, current.size, current.file_type) != (
            entry.sha256,
            entry.size,
            entry.file_type,
        ):
            reasons.append(f"disposition-evidence-mismatch:{entry.path}")
    return DispositionVerification(
        state=BaselineState.COMPLETE if not reasons else BaselineState.FAILED,
        reasons=tuple(reasons),
    )


def _write_json(path: Path, value: object) -> bytes:
    raw = msgspec.json.encode(value) + b"\n"
    path.write_bytes(raw)
    return raw


def _write_candidate_inputs(
    candidate: Path,
    runtime: RuntimeIdentity,
    controls: ControlsReceipt,
    catalog: DispositionCatalog,
) -> bytes:
    _write_json(candidate / "runtime.json", runtime)
    _write_json(candidate / "controls.json", controls)
    return _write_json(candidate / "dispositions.json", catalog)


def _detected_code_paths(root: Path, result: dict[str, object]) -> list[Path]:
    files = result.get("files")
    if not isinstance(files, dict):
        raise TypeError("Graphify detection omitted the typed files catalog")
    raw_code = files.get("code")
    if not isinstance(raw_code, list) or not raw_code:
        raise ValueError("Graphify detection produced no code inputs for AST extraction")
    resolved_root = root.resolve()
    paths: list[Path] = []
    for raw_path in raw_code:
        path = Path(str(raw_path)).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"Graphify detected an out-of-snapshot path: {path}") from exc
        paths.append(path)
    return paths


def _partition_catalog(
    catalog: DispositionCatalog,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[SourceDisposition, ...],
    tuple[SourceDisposition, ...],
]:
    return (
        tuple(
            entry.path
            for entry in catalog.entries
            if entry.kind is DispositionKind.UNSUPPORTED_FILE
        ),
        tuple(
            entry.path for entry in catalog.entries if entry.kind is DispositionKind.IGNORED_TREE
        ),
        tuple(entry for entry in catalog.entries if entry.kind is DispositionKind.ZERO_NODE_FILE),
        tuple(
            entry for entry in catalog.entries if entry.kind is DispositionKind.EXCLUDED_AST_FIXTURE
        ),
    )


def _exclude_reviewed_ast_fixtures(
    source: Path,
    code_paths: list[Path],
    entries: tuple[SourceDisposition, ...],
) -> tuple[list[Path], tuple[str, ...]]:
    excluded = tuple(sorted(entry.path for entry in entries))
    resolved_source = source.resolve()
    return (
        [path for path in code_paths if str(path.relative_to(resolved_source)) not in excluded],
        excluded,
    )


def _lpk_expected_nodes() -> tuple[dict[str, object], dict[str, object]]:
    common: dict[str, object] = {
        "_origin": "ast",
        "file_type": "code",
        "id": _LPK_COLLISION_ID,
        "source_file": _LPK_CORRECTION_PATH,
        "source_location": "L1",
    }
    return ({**common, "label": "sample.lpk"}, {**common, "label": "sample"})


def _pas_expected_node() -> dict[str, object]:
    return {
        "_origin": "ast",
        "file_type": "code",
        "id": _PAS_FILE_ID,
        "label": "sample.pas",
        "source_file": _PAS_SOURCE_PATH,
        "source_location": "L1",
    }


def _lpk_expected_edges() -> tuple[dict[str, object], dict[str, object]]:
    common: dict[str, object] = {
        "_origin": "ast",
        "confidence": "EXTRACTED",
        "relation": "contains",
        "source_file": _LPK_CORRECTION_PATH,
        "source_location": "L1",
        "weight": 1.0,
    }
    return (
        {**common, "source": _LPK_COLLISION_ID, "target": _LPK_PACKAGE_ID},
        {**common, "source": _LPK_PACKAGE_ID, "target": _LPK_COLLISION_ID},
    )


def _lpk_correction_receipt(entry: SourceDisposition) -> CompatibilityCorrection:
    expected_entry = (
        DispositionKind.COMPATIBILITY_CORRECTION,
        _LPK_CORRECTION_PATH,
        _LPK_CORRECTION_SHA256,
        _LPK_CORRECTION_NAME,
    )
    observed_entry = (entry.kind, entry.path, entry.sha256, entry.extraction_disposition)
    if observed_entry != expected_entry:
        raise ValueError("compatibility-correction-catalog-mismatch")
    return CompatibilityCorrection(
        name=_LPK_CORRECTION_NAME,
        source_path=_LPK_CORRECTION_PATH,
        source_sha256=_LPK_CORRECTION_SHA256,
        original_id=_LPK_COLLISION_ID,
        replacement_ids=(_LPK_FILE_ID, _PAS_FILE_ID),
        rewritten_edges=1,
    )


def _dict_records(value: object, drift_reason: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(drift_reason)
    return [dict(item) for item in value]


def _is_already_fixed_lpk_shape(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> bool:
    file_node, _ = _lpk_expected_nodes()
    file_edge, foreign_edge = _lpk_expected_edges()
    corrected_edge = {**foreign_edge, "target": _PAS_FILE_ID}
    return (
        [node for node in nodes if node.get("id") == _LPK_COLLISION_ID] == [file_node]
        and [node for node in nodes if node.get("id") == _PAS_FILE_ID] == [_pas_expected_node()]
        and [
            edge
            for edge in edges
            if edge.get("source") == _LPK_COLLISION_ID or edge.get("target") == _LPK_COLLISION_ID
        ]
        == [file_edge]
        and corrected_edge in edges
    )


def _validate_lpk_collision_shape(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> None:
    if _is_already_fixed_lpk_shape(nodes, edges):
        raise ValueError("compatibility-correction-not-applicable:upstream-already-fixed")
    colliding = [node for node in nodes if node.get("id") == _LPK_COLLISION_ID]
    if colliding != list(_lpk_expected_nodes()):
        raise ValueError("compatibility-correction-node-shape-drift")
    if [node for node in nodes if node.get("id") == _PAS_FILE_ID] != [_pas_expected_node()]:
        raise ValueError("compatibility-correction-pas-identity-drift")
    incident = [
        edge
        for edge in edges
        if edge.get("source") == _LPK_COLLISION_ID or edge.get("target") == _LPK_COLLISION_ID
    ]
    if incident != list(_lpk_expected_edges()):
        raise ValueError("compatibility-correction-edge-role-drift")
    _, foreign_edge = _lpk_expected_edges()
    if {**foreign_edge, "target": _PAS_FILE_ID} in edges:
        raise ValueError("compatibility-correction-edge-role-drift")


def _rewrite_lpk_collision(
    extraction: dict[str, object],
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> dict[str, object]:
    _, foreign_node = _lpk_expected_nodes()
    _, foreign_edge = _lpk_expected_edges()
    corrected = deepcopy(extraction)
    corrected["nodes"] = [node for node in nodes if node != foreign_node]
    corrected["edges"] = [
        {**edge, "target": _PAS_FILE_ID} if edge == foreign_edge else edge for edge in edges
    ]
    return corrected


def apply_compatibility_corrections(
    source: Path,
    extraction: dict[str, object],
    entries: tuple[SourceDisposition, ...],
) -> tuple[dict[str, object], tuple[CompatibilityCorrection, ...]]:
    """Correct the exact Graphify 0.9.42 LPK collision or fail on any drift."""
    if len(entries) != 1:
        raise ValueError("compatibility-correction-catalog-mismatch")
    entry = entries[0]
    receipt = _lpk_correction_receipt(entry)
    evidence = graph.source_path_evidence(source, entry.path)
    if (evidence.sha256, evidence.size, evidence.file_type) != (
        entry.sha256,
        entry.size,
        entry.file_type,
    ):
        raise ValueError("compatibility-correction-source-drift")
    nodes = _dict_records(extraction.get("nodes"), "compatibility-correction-node-schema-drift")
    edges = _dict_records(extraction.get("edges"), "compatibility-correction-edge-schema-drift")
    _validate_lpk_collision_shape(nodes, edges)
    return _rewrite_lpk_collision(extraction, nodes, edges), (receipt,)


def _apply_catalog_corrections(
    source: Path,
    extraction: dict[str, object],
    catalog: DispositionCatalog,
) -> tuple[dict[str, object], tuple[CompatibilityCorrection, ...]]:
    entries = tuple(
        entry for entry in catalog.entries if entry.kind is DispositionKind.COMPATIBILITY_CORRECTION
    )
    return (
        apply_compatibility_corrections(source, extraction, entries)
        if entries
        else (extraction, ())
    )


def _control_clone(source: Path, destination: Path, commit: str) -> Path:
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-local",
            "--no-hardlinks",
            "--no-tags",
            "--",
            source.resolve().as_uri(),
            str(destination),
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )
    subprocess.run(
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", commit],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return destination


def _failed_control(name: str, reasons: tuple[str, ...]) -> ControlOutcome:
    return ControlOutcome(name=name, expected="failed", observed="failed", reasons=reasons)


def _assert_control_path_is_gitignored(clone: Path) -> None:
    """Refuse to run the ignored-path control unless its fixture is really ignored.

    The whole arm rests on `_CONTROL_IGNORED_PATH` matching a pattern in the
    PINNED source's own `.gitignore`. That is an upstream fact, and upstream can
    change it in any release — at which point the file would simply be ordinary
    untracked source, detection would classify it as a document, and the control
    would report `failed` with no `ignored-paths` reason. The receipt would then
    say the arm ran while it measured nothing.

    `git check-ignore` answers the question directly, so ask it rather than
    assume it. Exit 0 means ignored, 1 means not ignored, anything else means the
    probe itself failed — and all three are distinguished here, because "could
    not ask" must never read as "asked and it was fine".
    """
    result = subprocess.run(
        ["git", "-C", str(clone), "check-ignore", "--quiet", "--", _CONTROL_IGNORED_PATH],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise ValueError(
            f"ignored-path control fixture {_CONTROL_IGNORED_PATH} is no longer matched by the "
            f"pinned source's .gitignore — the control would measure nothing; pick a new fixture"
        )
    raise ValueError(
        f"could not determine whether {_CONTROL_IGNORED_PATH} is gitignored "
        f"(git check-ignore exited {result.returncode}): {result.stderr.decode(errors='replace')}"
    )


def certify_controls(source: Path, catalog: DispositionCatalog) -> ControlsReceipt:
    """Run clean and opposite-direction controls against real Graphify source bytes."""
    from kb_setup import graphify_sdk
    from kb_setup.graphify_health import SourceCoveragePolicy

    cases: list[ControlOutcome] = []
    source_manifest(source, commit=catalog.source_commit, tree=catalog.source_tree)
    clean = verify_catalog_bytes(source, catalog)
    cases.append(
        ControlOutcome(
            name="clean",
            expected="complete",
            observed=clean.state.value,
            reasons=clean.reasons,
        )
    )
    unclassified, ignored, _, _ = _partition_catalog(catalog)
    with tempfile.TemporaryDirectory(prefix="kb-graphify-controls-") as controls_dir:
        controls_root = Path(controls_dir)
        unknown = _control_clone(source, controls_root / "unknown", catalog.source_commit)
        (unknown / "unknown.issue299").write_text("unknown\n", encoding="utf-8")
        detected, receipt = graphify_sdk.observe_detect(
            unknown,
            source_name="graphify",
            coverage_policy=SourceCoveragePolicy(
                optional_unclassified_paths=unclassified,
                optional_ignored_paths=ignored,
            ),
        )
        unknown_observed = tuple(
            sorted(
                set(graph.graphify_sdk_paths(unknown, detected.get("unclassified", [])))
                - set(unclassified)
            )
        )
        cases.append(
            _failed_control(
                "unknown-file",
                tuple(dict.fromkeys((*receipt.reasons, *unknown_observed))),
            )
        )

        changed = _control_clone(source, controls_root / "changed", catalog.source_commit)
        changed_entry = next(
            entry for entry in catalog.entries if entry.kind is DispositionKind.UNSUPPORTED_FILE
        )
        (changed / changed_entry.path).write_bytes(
            (changed / changed_entry.path).read_bytes() + b"\nissue-299-control\n"
        )
        changed_receipt = verify_catalog_bytes(changed, catalog)
        cases.append(_failed_control("changed-reviewed-file", changed_receipt.reasons))

        ignored_clone = _control_clone(source, controls_root / "ignored", catalog.source_commit)
        _assert_control_path_is_gitignored(ignored_clone)
        new_ignored = ignored_clone / _CONTROL_IGNORED_PATH
        new_ignored.parent.mkdir(parents=True, exist_ok=True)
        new_ignored.write_text("untracked ignored control\n", encoding="utf-8")
        _, ignored_receipt = graphify_sdk.observe_detect(
            ignored_clone,
            source_name="graphify",
            coverage_policy=SourceCoveragePolicy(
                optional_unclassified_paths=unclassified,
                optional_ignored_paths=ignored,
            ),
        )
        cases.append(_failed_control("untracked-ignored-path", ignored_receipt.reasons))

        drift = _control_clone(source, controls_root / "drift", catalog.source_commit)
        drift_manifest = source_manifest(
            drift, commit=catalog.source_commit, tree=catalog.source_tree
        )
        drift_member = next(member for member in drift_manifest.members if member.mode != "120000")
        (drift / drift_member.path).write_bytes((drift / drift_member.path).read_bytes() + b"\n")
        try:
            source_manifest(drift, commit=catalog.source_commit, tree=catalog.source_tree)
        except ValueError as exc:
            drift_reasons = (str(exc).split(":", 1)[0],)
        else:
            drift_reasons = ()
        cases.append(_failed_control("post-admission-snapshot-drift", drift_reasons))
    expected = {
        "clean": ("complete", ()),
        "unknown-file": ("failed", ("unclassified-files", "unknown.issue299")),
        "changed-reviewed-file": (
            "failed",
            (f"disposition-evidence-mismatch:{changed_entry.path}",),
        ),
        "untracked-ignored-path": ("failed", ("ignored-paths",)),
        "post-admission-snapshot-drift": ("failed", ("source-snapshot-drift",)),
    }
    complete = all((case.observed, case.reasons) == expected.get(case.name) for case in cases)
    return ControlsReceipt(
        state="complete" if complete else "failed",
        source_commit=catalog.source_commit,
        source_tree=catalog.source_tree,
        cases=tuple(cases),
    )


def build_from_snapshot(
    source: Path,
    output: Path,
    *,
    inputs: BaselineBuildInputs,
) -> CandidateManifest:
    """Build a deterministic AST candidate from one exact, immutable Git snapshot."""
    from kb_setup import graphify_sdk
    from kb_setup.graphify_health import SourceCoveragePolicy

    catalog, runtime, controls, authority = (
        inputs.catalog,
        inputs.runtime,
        inputs.controls,
        inputs.authority,
    )

    before = source_manifest(
        source,
        commit=catalog.source_commit,
        tree=catalog.source_tree,
    )
    catalog_bytes = verify_catalog_bytes(source, catalog)
    if catalog_bytes.state is not BaselineState.COMPLETE:
        raise ValueError("Graphify catalog bytes failed: " + ", ".join(catalog_bytes.reasons))
    unclassified_paths, ignored_paths, zero_node_entries, excluded_entries = _partition_catalog(
        catalog
    )
    detection, detection_receipt = graphify_sdk.detect_checked(
        source,
        source_name="graphify",
        coverage_policy=SourceCoveragePolicy(
            optional_unclassified_paths=unclassified_paths,
            optional_ignored_paths=ignored_paths,
        ),
    )
    census = graph.SourceCensusReceipt(
        source="graphify",
        kind="code",
        status=detection_receipt.state.value,
        declared_pin=catalog.source_commit,
        resolved_commit=catalog.source_commit,
        tree_digest=catalog.source_tree,
        categories=tuple(sorted(detection_receipt.reasons)),
        detected_count=detection_receipt.detected_sources,
        unclassified_count=len(detection_receipt.unclassified_paths),
        ignored_count=len(detection_receipt.ignored_paths),
        unclassified=tuple(
            graph.source_path_evidence(source, path)
            for path in detection_receipt.unclassified_paths
        ),
        ignored=tuple(
            graph.source_path_evidence(source, path) for path in detection_receipt.ignored_paths
        ),
        stderr=detection_receipt.stderr,
    )
    disposition = verify_dispositions(
        source,
        catalog,
        unclassified=census.unclassified,
        ignored=census.ignored,
    )
    if disposition.state is not BaselineState.COMPLETE:
        raise ValueError("Graphify source dispositions failed: " + ", ".join(disposition.reasons))
    for key in ("walk_errors", "skipped_sensitive"):
        value = detection.get(key)
        if isinstance(value, list) and value:
            raise ValueError(f"Graphify detection reported {key}: {value!r}")
    code_paths, excluded_paths = _exclude_reviewed_ast_fixtures(
        source, _detected_code_paths(source, detection), excluded_entries
    )
    code_paths, reviewed_metadata_paths = _exclude_reviewed_ast_fixtures(
        source, code_paths, zero_node_entries
    )

    if output.exists():
        raise ValueError(f"baseline output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kb-graphify-ast-cache-") as cache_dir:
        extraction, extraction_receipt = graphify_sdk.extract_checked(
            code_paths,
            root=source,
            cache_root=Path(cache_dir),
            admission=graphify_sdk.ExtractionAdmission(
                source_name="graphify",
                coverage_policy=SourceCoveragePolicy(),
                metadata_inventory=(),
            ),
        )
    extraction, compatibility_corrections = _apply_catalog_corrections(source, extraction, catalog)
    built_graph, build_receipt = graphify_sdk.build_checked([extraction], root=source)

    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as candidate_dir:
        candidate = Path(candidate_dir)
        graph_path = candidate / "ast-graph.json"
        artifact_receipt = graphify_sdk.artifact_checked(
            built_graph,
            {},
            graph_path,
            built_at_commit=catalog.source_commit,
        )
        after = source_manifest(
            source,
            commit=catalog.source_commit,
            tree=catalog.source_tree,
        )
        if after != before:
            raise ValueError("source-snapshot-drift: manifest changed during AST build")
        graph_payload = json.loads(graph_path.read_bytes())
        node_count, edge_count, hyperedge_count = (
            len(graph_payload.get(name, [])) for name in ("nodes", "links", "hyperedges")
        )
        # What no reviewer accounted for BY NAME. Reading `residual_stderr` and
        # not "stderr unless something was approved" matters even though a
        # non-empty residual cannot reach here (`require_complete` raised): the
        # old spelling let ONE approval hide every other warning on the same
        # receipt, and correctness that depends on an invariant enforced two
        # modules away stops holding the moment either module moves.
        warnings = tuple(
            warning
            for receipt in (detection_receipt, extraction_receipt, build_receipt, artifact_receipt)
            for warning in (
                (
                    receipt.stderr if receipt.residual_stderr is None else receipt.residual_stderr
                ).strip(),
            )
            if warning
        )
        build = BaselineBuildReceipt(
            status="complete",
            source_commit=catalog.source_commit,
            source_tree=catalog.source_tree,
            runtime_version=runtime.version,
            detected_count=len(code_paths) + len(excluded_entries) + len(zero_node_entries),
            extracted_count=len(code_paths),
            node_count=node_count,
            edge_count=edge_count,
            hyperedge_count=hyperedge_count,
            reviewed_metadata_paths=reviewed_metadata_paths,
            zero_node_paths=extraction_receipt.zero_node_paths,
            excluded_paths=excluded_paths,
            compatibility_corrections=compatibility_corrections,
            approved_classifications=extraction_receipt.approved_classifications,
            warnings=warnings,
        )
        health = BaselineHealth(
            state="complete" if node_count > 0 and not warnings else "failed",
            source="graphify",
            source_commit=catalog.source_commit,
            source_tree=catalog.source_tree,
            warnings=warnings,
        )
        _write_json(
            candidate / "source-census.json",
            graph.DetectionCensusReceipt(
                total_sources=1,
                status_counts=((census.status, 1),),
                category_counts=(),
                sources=(census,),
            ),
        )
        _write_json(candidate / "source-manifest.json", before)
        _write_json(candidate / "build-receipt.json", build)
        _write_json(candidate / "health.json", health)
        catalog_raw = _write_candidate_inputs(candidate, runtime, controls, catalog)
        members = tuple(
            ArtifactMember(
                name=name,
                sha256=hashlib.sha256((candidate / name).read_bytes()).hexdigest(),
                size=(candidate / name).stat().st_size,
            )
            for name in sorted(_REQUIRED_MEMBERS)
        )
        manifest = CandidateManifest(
            schema_id=_BASELINE_SCHEMA,
            source="graphify",
            source_ref=catalog.source_ref,
            source_commit=catalog.source_commit,
            source_tree=catalog.source_tree,
            catalog_sha256=hashlib.sha256(catalog_raw).hexdigest(),
            members=members,
            warnings=warnings,
            semantic_evidence_present=False,
            release_evidence_present=False,
        )
        _write_json(candidate / "manifest.json", manifest)
        verification = _verify_candidate(candidate, authority)
        if not verification.deterministic_complete:
            raise ValueError(
                "deterministic Graphify baseline failed verification: "
                + ", ".join(verification.reasons)
            )
        Path(candidate_dir).replace(output)
    return manifest


def build_baseline(repo_root: Path, output: Path) -> BaselineVerification:
    """Materialize the pinned Graphify source and build its deterministic AST baseline."""
    catalog = load_disposition_catalog(repo_root)
    graphify_manifest = historical_graphify_manifest(
        repo_root,
        ref=catalog.source_ref,
        commit=catalog.source_commit,
    )
    runtime = runtime_identity(repo_root)
    with tempfile.TemporaryDirectory(prefix="kb-graphify-baseline-source-") as source_dir:
        source = Path(source_dir) / "graphify"
        provenance = graph.materialize_source_snapshot(graphify_manifest, source)
        if (
            provenance.resolved_commit != catalog.source_commit
            or provenance.tree_digest != catalog.source_tree
        ):
            raise ValueError("Graphify source manifest and disposition catalog identity differ")
        build_from_snapshot(
            source,
            output,
            inputs=BaselineBuildInputs(
                catalog=catalog,
                runtime=runtime,
                controls=certify_controls(source, catalog),
                authority=_ACCEPTED_AUTHORITY,
            ),
        )
    return verify_candidate(output)


def certify_baseline_controls(repo_root: Path) -> ControlsReceipt:
    """Run only the real-source admission and mutation controls."""
    from kb_setup import graphify_env

    graphify_env.assert_pinned_graphify(repo_root)
    catalog = load_disposition_catalog(repo_root)
    graphify_manifest = historical_graphify_manifest(
        repo_root,
        ref=catalog.source_ref,
        commit=catalog.source_commit,
    )
    with tempfile.TemporaryDirectory(prefix="kb-graphify-controls-source-") as source_dir:
        source = Path(source_dir) / "graphify"
        provenance = graph.materialize_source_snapshot(graphify_manifest, source)
        if (
            provenance.resolved_commit != catalog.source_commit
            or provenance.tree_digest != catalog.source_tree
        ):
            raise ValueError("Graphify control source and disposition identities differ")
        return certify_controls(source, catalog)


def baseline_main(repo_root: Path, args: list[str]) -> int:
    """Build or verify the public Graphify-only deterministic candidate."""
    if not args or args[0] not in {"build", "controls", "verify"}:
        print("kb-setup graphify-baseline build|controls|verify [PATH]")
        return 2
    if args[0] == "controls":
        if len(args) != 1:
            print("kb-setup graphify-baseline controls")
            return 2
        controls = certify_baseline_controls(repo_root)
        print(msgspec.json.encode(controls).decode())
        return 0 if controls.state == "complete" else 1
    output = (
        Path(args[1])
        if len(args) == _MAX_BASELINE_ARGS
        else repo_root / "graphify-out/graphify-baseline"
    )
    if len(args) > _MAX_BASELINE_ARGS:
        print("kb-setup graphify-baseline build|controls|verify [PATH]")
        return 2
    receipt = build_baseline(repo_root, output) if args[0] == "build" else verify_candidate(output)
    print(msgspec.json.encode(receipt).decode())
    return 0 if receipt.deterministic_complete else 1
