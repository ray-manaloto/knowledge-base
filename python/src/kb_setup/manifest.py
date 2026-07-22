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
