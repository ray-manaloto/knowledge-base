# Copyright (c) 2026 Raymond Manaloto
"""Inventory committed semantic chunks from one immutable Git tree snapshot."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import chunks

if TYPE_CHECKING:
    from collections.abc import Sequence

_AUTHORITY = "git_tree_snapshot"
_SCOPE = "sources/extractions/*.json"
_GIT_TIMEOUT_SECONDS = 30
_MAX_ENTRIES = 10_000
_MAX_BLOB_BYTES = 64 * 1024 * 1024
_MAX_TOTAL_BYTES = 512 * 1024 * 1024
_MAX_TREE_OUTPUT_BYTES = 8 * 1024 * 1024
_MAX_GIT_DIAGNOSTIC_BYTES = 8 * 1024
_LS_TREE_FIELD_COUNT = 4
_CAT_FILE_HEADER_FIELD_COUNT = 3
_OBJECT_ID_RE = re.compile(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_DIRECT_JSON_RE = re.compile(r"sources/extractions/([A-Za-z0-9][A-Za-z0-9._-]*\.json)\Z")
_REGULAR_BLOB_MODES = frozenset({"100644", "100755"})


class InventoryError(RuntimeError):
    """A typed fail-closed inventory error that never embeds path or blob bytes."""

    def __init__(self, code: str) -> None:
        """Create an error carrying only its stable diagnostic code."""
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractionRecord:
    """One extraction blob read from the resolved tree, never from the worktree."""

    chunk: str
    blob_oid: str
    size_bytes: int
    sha256: str
    status: str
    nodes: int
    edges: int
    hyperedges: int
    source_files: int
    source_urls: int
    captured_at: str
    producer_declared: bool
    issues: tuple[str, ...]


@dataclass(frozen=True)
class InventoryReceipt:
    """The committed authority and the checkout-currentness result kept separate."""

    authority: str
    scope: str
    resolved_commit: str
    resolved_tree: str
    inventory_digest: str
    complete: bool
    diagnostics: tuple[str, ...]
    records: tuple[ExtractionRecord, ...]


@dataclass(frozen=True)
class _TreeEntry:
    """Validated metadata for one regular blob in the resolved tree."""

    path: str
    chunk: str
    oid: str
    size: int


def _git(
    repo_root: Path,
    args: Sequence[str],
    *,
    stdin: bytes | None = None,
    output_cap: int = _MAX_TREE_OUTPUT_BYTES,
) -> bytes:
    """Run one bounded Git query and return stdout or a path/body-free typed error."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            input=stdin,
            capture_output=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InventoryError("git_unavailable_or_timed_out") from exc
    stderr = result.stderr or b""
    if len(stderr) > _MAX_GIT_DIAGNOSTIC_BYTES:
        raise InventoryError("git_stderr_limit_exceeded")
    if stderr:
        raise InventoryError("git_stderr_received")
    if result.returncode != 0:
        raise InventoryError("git_command_failed")
    stdout = result.stdout or b""
    if len(stdout) > output_cap:
        raise InventoryError("git_stdout_limit_exceeded")
    return stdout


def _resolve_object(repo_root: Path, revision: str, *, code: str) -> str:
    """Resolve exactly one commit/tree object id and reject ambiguous output."""
    try:
        raw = _git(repo_root, ["rev-parse", "--verify", revision], output_cap=256).strip()
    except InventoryError as exc:
        raise InventoryError(code) from exc
    if not _OBJECT_ID_RE.fullmatch(raw):
        raise InventoryError(code)
    return raw.decode("ascii")


def _tree_entry(record: bytes) -> _TreeEntry | None:
    """Parse one tree record, ignoring only non-JSON paths outside the scope."""
    metadata, separator, path_bytes = record.partition(b"\t")
    fields = metadata.split()
    if not separator or len(fields) != _LS_TREE_FIELD_COUNT:
        raise InventoryError("malformed_git_tree_record")
    mode_raw, kind_raw, oid_raw, size_raw = fields
    try:
        path = path_bytes.decode("utf-8", errors="strict")
        mode = mode_raw.decode("ascii")
        kind = kind_raw.decode("ascii")
        oid = oid_raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise InventoryError("noncanonical_extraction_path") from exc
    match = _DIRECT_JSON_RE.fullmatch(path)
    if match is None:
        if path.endswith(".json"):
            raise InventoryError("noncanonical_extraction_path")
        return None
    if mode not in _REGULAR_BLOB_MODES or kind != "blob":
        raise InventoryError("non_regular_extraction_blob")
    if not _OBJECT_ID_RE.fullmatch(oid_raw):
        raise InventoryError("malformed_git_tree_record")
    try:
        size = int(size_raw)
    except ValueError as exc:
        raise InventoryError("malformed_git_tree_record") from exc
    if size < 0 or size > _MAX_BLOB_BYTES:
        raise InventoryError("extraction_blob_size_limit_exceeded")
    return _TreeEntry(path=path, chunk=match.group(1), oid=oid, size=size)


def _parse_tree(raw: bytes) -> tuple[_TreeEntry, ...]:
    """Narrow raw ``ls-tree -z -l`` records to canonical direct-child JSON blobs."""
    entries: list[_TreeEntry] = []
    paths: set[str] = set()
    oids: set[str] = set()
    total = 0
    for record in raw.split(b"\0"):
        if not record:
            continue
        entry = _tree_entry(record)
        if entry is None:
            continue
        if entry.path in paths:
            raise InventoryError("duplicate_extraction_path")
        if entry.oid in oids:
            raise InventoryError("duplicate_extraction_blob_oid")
        paths.add(entry.path)
        oids.add(entry.oid)
        total += entry.size
        if len(entries) >= _MAX_ENTRIES:
            raise InventoryError("extraction_count_limit_exceeded")
        if total > _MAX_TOTAL_BYTES:
            raise InventoryError("extraction_total_size_limit_exceeded")
        entries.append(entry)
    return tuple(sorted(entries, key=lambda entry: entry.path))


def _read_blobs(repo_root: Path, entries: Sequence[_TreeEntry]) -> tuple[bytes, ...]:
    """Read every exact object id through one ``cat-file --batch`` process."""
    if not entries:
        return ()
    request = b"".join(entry.oid.encode("ascii") + b"\n" for entry in entries)
    header_allowance = len(entries) * 160
    output_cap = sum(entry.size for entry in entries) + header_allowance
    raw = _git(repo_root, ["cat-file", "--batch"], stdin=request, output_cap=output_cap)
    offset = 0
    bodies: list[bytes] = []
    for entry in entries:
        newline = raw.find(b"\n", offset)
        if newline < 0:
            raise InventoryError("malformed_git_blob_batch")
        header = raw[offset:newline].split()
        if len(header) != _CAT_FILE_HEADER_FIELD_COUNT:
            raise InventoryError("malformed_git_blob_batch")
        oid_raw, kind_raw, size_raw = header
        try:
            declared_size = int(size_raw)
        except ValueError as exc:
            raise InventoryError("malformed_git_blob_batch") from exc
        if (
            oid_raw.decode("ascii", errors="ignore") != entry.oid
            or kind_raw != b"blob"
            or declared_size != entry.size
        ):
            raise InventoryError("git_blob_identity_mismatch")
        start = newline + 1
        end = start + entry.size
        if end >= len(raw) or raw[end : end + 1] != b"\n":
            raise InventoryError("malformed_git_blob_batch")
        bodies.append(raw[start:end])
        offset = end + 1
    if offset != len(raw):
        raise InventoryError("malformed_git_blob_batch")
    return tuple(bodies)


def _worktree_diagnostics(repo_root: Path) -> tuple[str, ...]:
    """Report extraction-scope drift without reading or naming native paths."""
    diagnostics: list[str] = []
    for label, args in (
        ("worktree_staged", ["diff", "--quiet", "--cached", "--", "sources/extractions"]),
        ("worktree_unstaged", ["diff", "--quiet", "--", "sources/extractions"]),
    ):
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                check=False,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise InventoryError("git_worktree_check_failed") from exc
        stderr = result.stderr or b""
        if len(stderr) > _MAX_GIT_DIAGNOSTIC_BYTES:
            raise InventoryError("git_stderr_limit_exceeded")
        if stderr:
            raise InventoryError("git_stderr_received")
        if result.returncode == 1:
            diagnostics.append(label)
        elif result.returncode != 0:
            raise InventoryError("git_worktree_check_failed")
    untracked = _git(
        repo_root,
        ["ls-files", "--others", "-z", "--", "sources/extractions"],
        output_cap=_MAX_TREE_OUTPUT_BYTES,
    )
    if untracked:
        diagnostics.append("worktree_untracked")
    return tuple(diagnostics)


def _record(entry: _TreeEntry, body: bytes, known_ids: set[str]) -> ExtractionRecord:
    """Build a privacy-preserving semantic summary from one exact blob body."""
    issue_codes: tuple[str, ...]
    try:
        data = json.loads(body)
    except json.JSONDecodeError, UnicodeDecodeError, RecursionError:
        data = {}
        issue_codes = ("invalid_json",)
    else:
        issue_codes = (
            ("invalid_chunk_schema",)
            if chunks.validate(data, label="chunk", known_ids=known_ids)
            else ()
        )
    nodes = data.get("nodes") if isinstance(data, dict) else []
    edges = data.get("edges") if isinstance(data, dict) else []
    hyperedges = data.get("hyperedges") if isinstance(data, dict) else []
    node_rows = [row for row in nodes if isinstance(row, dict)] if isinstance(nodes, list) else []
    source_files = {str(row["source_file"]) for row in node_rows if row.get("source_file")}
    source_urls = {str(row["source_url"]) for row in node_rows if row.get("source_url")}
    dates = [
        value for row in node_rows if isinstance((value := row.get("captured_at")), str) and value
    ]
    producer_declared = isinstance(data, dict) and any(
        key in data for key in ("producer", "model", "extraction_receipt")
    )
    status = (
        "INVALID"
        if issue_codes
        else ("VALID_BOUND" if producer_declared else "VALID_PROVENANCE_UNBOUND")
    )
    return ExtractionRecord(
        chunk=entry.chunk,
        blob_oid=entry.oid,
        size_bytes=entry.size,
        sha256=hashlib.sha256(body).hexdigest(),
        status=status,
        nodes=len(nodes) if isinstance(nodes, list) else 0,
        edges=len(edges) if isinstance(edges, list) else 0,
        hyperedges=len(hyperedges) if isinstance(hyperedges, list) else 0,
        source_files=len(source_files),
        source_urls=len(source_urls),
        captured_at=max(dates, default=""),
        producer_declared=producer_declared,
        issues=issue_codes,
    )


def _known_ids(bodies: Sequence[bytes]) -> set[str]:
    """Collect string node ids without making malformed bodies observable."""
    ids: set[str] = set()
    for body in bodies:
        try:
            data = json.loads(body)
        except json.JSONDecodeError, UnicodeDecodeError, RecursionError:
            continue
        if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
            continue
        ids.update(
            row["id"]
            for row in data["nodes"]
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        )
    return ids


def _digest(commit: str, tree: str, records: Sequence[ExtractionRecord]) -> str:
    """Bind authority, scope, resolved identities, and record proofs canonically."""
    payload = {
        "authority": _AUTHORITY,
        "scope": _SCOPE,
        "resolved_commit": commit,
        "resolved_tree": tree,
        "records": [asdict(record) for record in records],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def snapshot(repo_root: Path) -> InventoryReceipt:
    """Return one immutable Git-tree inventory plus checkout-currentness diagnostics."""
    commit = _resolve_object(repo_root, "HEAD^{commit}", code="missing_or_unborn_head")
    initial_dirty = _worktree_diagnostics(repo_root)
    tree = _resolve_object(repo_root, f"{commit}^{{tree}}", code="missing_commit_tree")
    raw_tree = _git(
        repo_root,
        ["ls-tree", "-r", "-z", "-l", tree, "--", "sources/extractions"],
    )
    entries = _parse_tree(raw_tree)
    bodies = _read_blobs(repo_root, entries)
    known_ids = _known_ids(bodies)
    records = tuple(
        _record(entry, body, known_ids) for entry, body in zip(entries, bodies, strict=True)
    )
    diagnostics = list(dict.fromkeys((*initial_dirty, *_worktree_diagnostics(repo_root))))
    final_commit = _resolve_object(repo_root, "HEAD^{commit}", code="missing_or_unborn_head")
    if final_commit != commit:
        diagnostics.append("head_changed")
    if any(record.status == "INVALID" for record in records):
        diagnostics.append("invalid_chunks")
    return InventoryReceipt(
        authority=_AUTHORITY,
        scope=_SCOPE,
        resolved_commit=commit,
        resolved_tree=tree,
        inventory_digest=_digest(commit, tree, records),
        complete=not diagnostics,
        diagnostics=tuple(diagnostics),
        records=records,
    )


def report(repo_root: Path, argv: Sequence[str] | None = None) -> int:
    """Print the receipt and fail for invalid data, stale checkout, or Git errors."""
    if argv and any(arg != "--json" for arg in argv):
        print("extraction-inventory: ERROR invalid_arguments")
        return 2
    try:
        receipt = snapshot(repo_root)
    except InventoryError as exc:
        print(f"extraction-inventory: ERROR {exc.code}")
        return 1
    if argv and "--json" in argv:
        print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    else:
        print(f"authority: {receipt.authority}")
        print(f"scope: {receipt.scope}")
        print(f"resolved_commit: {receipt.resolved_commit}")
        print(f"resolved_tree: {receipt.resolved_tree}")
        print(f"inventory_digest: {receipt.inventory_digest}")
        print("status\tcaptured\tnodes\tbytes\tchunk")
        for record in receipt.records:
            print(
                f"{record.status}\t{record.captured_at or '-'}\t{record.nodes}\t"
                f"{record.size_bytes}\t{record.chunk}"
            )
        state = "COMPLETE" if receipt.complete else "INCOMPLETE"
        print(f"summary: {state}; {len(receipt.records)} committed chunks")
        for diagnostic in receipt.diagnostics:
            print(f"diagnostic: {diagnostic}")
    return int(not receipt.complete)
