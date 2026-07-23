"""Source manifests — `sources/<name>.manifest` pins an external repo by SHA.

The external repo is NEVER committed; the manifest (url + ref + commit) plus the
committed graph outputs make the KB reproducible without vendoring source.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Manifest:
    """A parsed `sources/<name>.manifest`: an external repo pinned by SHA."""

    name: str  # derived from the file stem (sources/graphify.manifest -> "graphify")
    path: Path
    url: str
    ref: str  # branch/tag to clone
    commit: str  # pinned SHA
    kind: str = "code"

    @property
    def clone_dir(self) -> Path:
        """Gitignored directory the source is cloned into (sibling of the manifest)."""
        return self.path.parent / self.name


def _parse(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        fields[key.strip()] = val.strip()
    return fields


def load(path: Path) -> Manifest:
    """Parse and validate one manifest file into a Manifest (raises on missing fields)."""
    f = _parse(path.read_text(encoding="utf-8"))
    missing = {"url", "ref", "commit"} - f.keys()
    if missing:
        raise ValueError(f"{path}: manifest missing required field(s): {sorted(missing)}")
    return Manifest(
        name=path.stem,
        path=path,
        url=f["url"],
        ref=f["ref"],
        commit=f["commit"],
        kind=f.get("kind", "code"),
    )


def load_all(sources_dir: Path) -> list[Manifest]:
    """Load every `*.manifest` under `sources_dir`, sorted by path."""
    return [load(p) for p in sorted(sources_dir.glob("*.manifest"))]


def latest_commit(m: Manifest) -> str:
    """Upstream HEAD of the manifest's ref (a `git ls-remote`, no clone)."""
    out = subprocess.run(
        ["git", "ls-remote", m.url, m.ref],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()
    if not out:
        raise RuntimeError(f"{m.name}: ref {m.ref!r} not found at {m.url}")
    return out.split()[0]


def write_commit(m: Manifest, commit: str) -> Manifest:
    """Rewrite the manifest's `commit =` line in place; return the updated Manifest."""
    lines = m.path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("commit"):
            nl = "\n" if line.endswith("\n") else ""
            lines[i] = f"commit = {commit}{nl}"
            break
    m.path.write_text("".join(lines), encoding="utf-8")
    return replace(m, commit=commit)


def name_from_url(url: str) -> str:
    """Derive the manifest stem from a repo URL (last path segment, no `.git`)."""
    return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


@dataclass(frozen=True)
class NewSource:
    """A repo source to pin: url (required) + optional ref/kind/name/comment.

    Bundled so `add()` stays a small (sources_dir, source, *, force) call. `name`
    defaults to the URL's last path segment; set it to disambiguate two repos that
    share a basename (e.g. two `antigravity-plugin-cc` forks).
    """

    url: str
    ref: str = "main"
    kind: str = "code"
    name: str | None = None
    comment: str | None = None

    @property
    def stem(self) -> str:
        """The manifest file stem (explicit name, else derived from the url)."""
        return self.name or name_from_url(self.url)


def add(sources_dir: Path, source: NewSource, *, force: bool = False) -> Manifest:
    """Create `sources/<stem>.manifest` for a new repo, SHA-pinned at upstream HEAD.

    The reusable replacement for hand-writing a manifest: resolve the pinned commit
    via `latest_commit` (a `git ls-remote`, no clone — same path `kb-update` uses),
    then write the file. Raises `FileExistsError` if the manifest already exists
    unless `force` (so re-adds don't silently clobber a deliberately-pinned SHA —
    advance an existing source with `kb-update`).
    """
    stem = source.stem
    path = sources_dir / f"{stem}.manifest"
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use kb-update to advance, or --force)")
    probe = Manifest(
        name=stem, path=path, url=source.url, ref=source.ref, commit="", kind=source.kind
    )
    commit = latest_commit(probe)
    header = "# Source manifest — reproducible-by-reference (Invariant 3)."
    body = f"# {source.comment}\n" if source.comment else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{header}\n{body}url = {source.url}\nref = {source.ref}\n"
        f"commit = {commit}\nkind = {source.kind}\n",
        encoding="utf-8",
    )
    return Manifest(
        name=stem, path=path, url=source.url, ref=source.ref, commit=commit, kind=source.kind
    )
