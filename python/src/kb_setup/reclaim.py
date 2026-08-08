# Copyright (c) 2026 Raymond Manaloto
"""Disk reclamation: measure what is reclaimable, and (only on `--apply`) reclaim it.

The policy lives in `reclaim.toml`; this module is the engine. Every category is a
`kind` handled by one scanner, so adding "clean up X" is a scanner plus a config
block — docker cleanup is one such subset, not the whole tool.

Two properties this module exists to guarantee, both tested:

* **Dry run is the default.** `plan()` never mutates anything; `apply()` is only
  reached from an explicit `--apply`. Nothing in `reclaim.toml` can flip that.
* **A category acts only inside its own declared roots.** `_guard_path` refuses a
  target that escapes them or lands inside this repository, so a typo in the
  config fails closed rather than deleting something else.

What it deliberately does NOT do: compact a container engine's disk image. On
macOS the engine's storage is one sparse file, and pruning frees space *inside*
it without shrinking the file. Rewriting a live VM disk is not something to
hand-roll (`use-tool-builtins.md`), and no `docker` subcommand on this platform
exposes it. So the docker scanner measures the image before and after and reports
whether it actually moved — turning a silent non-effect into a stated one.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024
#: Age filters are handed to docker as hours; it has no day unit.
_HOURS_PER_DAY = 24
#: `ollama list` columns: NAME ID SIZE UNIT MODIFIED… — fewer means a header or blank.
_OLLAMA_MIN_COLUMNS = 4
#: A concrete version is `major.minor.patch`; `0.9` and `latest` are channels.
_VERSION_DOTS = 2
#: Per category, how many findings are listed individually before the tail is summed.
_LIST_LIMIT = 12


@dataclass(frozen=True)
class Finding:
    """One reclaimable thing, with the size that justifies acting on it."""

    category: str
    label: str
    size_bytes: int
    detail: str
    #: Absolute path to remove, or None for a finding whose action is a command
    #: (docker prune) rather than a deletion.
    path: Path | None = None
    #: Context, not a candidate: printed, but NEVER summed into the reclaimable
    #: total. A container disk image is the worked example — its bytes are the
    #: same bytes the engine's own "reclaimable" figure already counts, so adding
    #: both double-counts the only part that could actually be freed.
    informational: bool = False


@dataclass
class Category:
    """One configured category, already merged with `[defaults]`."""

    name: str
    kind: str
    enabled: bool
    age_days: int
    min_size_mb: int
    options: dict = field(default_factory=dict)

    @property
    def min_size_bytes(self) -> int:
        """Findings below this are summed but not listed individually."""
        return self.min_size_mb * _MB


class ReclaimError(RuntimeError):
    """A configuration or safety violation — never a scan miss."""


def human(n: int) -> str:
    """Format a byte count the way `du -h` would, to one decimal."""
    if n >= _GB:
        return f"{n / _GB:.1f}G"
    if n >= _MB:
        return f"{n / _MB:.0f}M"
    return f"{n}B"


def _expand(raw: str) -> Path:
    """Expand `~` and resolve, without requiring the path to exist."""
    return Path(raw).expanduser()


def load_config(path: Path) -> list[Category]:
    """Parse `reclaim.toml` into categories, merging `[defaults]` into each."""
    if not path.is_file():
        raise ReclaimError(f"no reclaim config at {path}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    out: list[Category] = []
    for name, block in raw.get("category", {}).items():
        opts = {k: v for k, v in block.items() if k not in {"enabled", "kind", "age_days"}}
        out.append(
            Category(
                name=name,
                kind=block.get("kind", ""),
                enabled=bool(block.get("enabled", True)),
                age_days=int(block.get("age_days", defaults.get("age_days", 30))),
                min_size_mb=int(block.get("min_size_mb", defaults.get("min_size_mb", 100))),
                options=opts,
            )
        )
    return out


def _guard_path(target: Path, roots: list[Path], repo_root: Path) -> None:
    """Refuse a target outside every declared root, or inside this repository.

    This is the safety property that makes a config-driven deleter tolerable: the
    config chooses WHICH root, never whether the root is honoured.
    """
    resolved = target.resolve()
    if resolved == Path(resolved.anchor):
        raise ReclaimError(f"refusing to act on the filesystem root: {target}")
    if repo_root.resolve() in (resolved, *resolved.parents):
        raise ReclaimError(f"refusing to act inside the repository: {target}")
    for root in roots:
        rr = root.expanduser().resolve()
        if rr == resolved:
            # A root is a CONTAINER, never a candidate. Permitting equality let
            # `scan_dirs` emit the configured root as its own finding, so
            # `--apply` would have rmtree'd the whole of ~/Library/Caches. The
            # tests passed because they only ever asked "inside" vs "outside"
            # and never that the boundary itself is excluded.
            raise ReclaimError(f"refusing to act on the declared root itself: {target}")
        if rr in resolved.parents:
            return
    raise ReclaimError(f"{target} escapes every declared root {[str(r) for r in roots]}")


def _allocated(st: object) -> int:
    """Bytes a file actually occupies on disk, not the size it advertises.

    `st_size` is the APPARENT size. For a sparse file the two differ enormously,
    and a container disk image is always sparse: this repo's `Docker.raw` reports
    `st_size` 1858.2G against `st_blocks*512` 285.8G — the latter matching `du`.
    Summing apparent sizes once produced a report claiming 2.3TB was reclaimable
    on a 1.8TB disk. `st_blocks` is always 512-byte units per POSIX, regardless
    of the filesystem's own block size.
    """
    blocks = getattr(st, "st_blocks", None)
    if blocks is None:  # pragma: no cover - non-POSIX fallback
        return int(getattr(st, "st_size", 0))
    return int(blocks) * 512


def _dir_size(path: Path) -> int:
    """Allocated bytes under `path`, measured with `du` and only then by hand.

    `du` is not an optimisation here, it is the correct tool twice over
    (`use-tool-builtins.md`). It reports ALLOCATED blocks natively — the exact
    sparse-file semantics `_allocated` had to hand-roll — and it does so in C:
    `~/.npm/_cacache` (21GB of tiny files) takes **3.5s** via `du -sk` against
    minutes for a python `rglob` + per-file `stat`. The first version of this
    module used the python walk and a whole-machine scan never finished; it was
    killed after 15 minutes having printed nothing.

    The python fallback survives only for a host without `du`, and it is the
    slow path by construction, not the default.
    """
    if not path.exists():
        return 0
    if shutil.which("du"):
        # NOT `rc == 0`. `du` exits 1 when ANY subtree is unreadable while still
        # printing a correct total, and `~/Library/Caches` reproducibly exits 1
        # on macOS (sandboxed app caches) — the single largest configured tree.
        # Gating on rc threw the good number away and fell back to the slow walk
        # for exactly the path the du rewrite existed to speed up.
        _rc, out = _run(["du", "-sk", str(path)])
        if out:
            try:
                return int(out.split()[0]) * 1024
            except ValueError, IndexError:
                pass
    return _dir_size_slow(path)


def _dir_size_slow(path: Path) -> int:
    """Allocated bytes under `path` by walking it — the no-`du` fallback."""
    if path.is_file():
        return _allocated(path.stat())
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += _allocated(p.stat())
        except OSError:
            continue
    return total


def _run(argv: list[str], *, env_context: str | None = None) -> tuple[int, str]:
    """Run a command, returning (rc, stdout). Never raises on a non-zero rc."""
    cmd = list(argv)
    if env_context:
        cmd = [cmd[0], "--context", env_context, *cmd[1:]]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
    except (OSError, subprocess.TimeoutExpired) as err:
        return 1, f"{err}"
    return proc.returncode, proc.stdout.strip()


# ─── scanners ────────────────────────────────────────────────────────────────


def scan_docker(cat: Category, _repo_root: Path) -> list[Finding]:
    """Report each configured engine's reclaimable bytes and its disk-image size.

    Two numbers per engine, and they answer different questions: `docker system
    df` says what is reclaimable INSIDE the engine, while the disk image says
    what macOS has actually committed. They routinely disagree, which is the
    whole reason both are printed.
    """
    if not shutil.which("docker"):
        return []
    out: list[Finding] = []
    for eng in cat.options.get("engines", []):
        ctx = eng.get("context", "")
        rc, raw = _run(["docker", "system", "df", "--format", "json"], env_context=ctx)
        if rc == 0 and raw:
            out.extend(_docker_df_findings(cat.name, ctx, raw))
        img = _expand(eng.get("disk_image", ""))
        size = _dir_size(img)
        if size:
            out.append(
                Finding(
                    category=cat.name,
                    label=f"{ctx}: disk image on host",
                    size_bytes=size,
                    detail=f"{img} — pruning frees space INSIDE this, it may not shrink",
                    informational=True,
                )
            )
    return out


def _docker_df_findings(cat_name: str, ctx: str, raw: str) -> list[Finding]:
    """Turn `docker system df --format json` lines into per-type findings."""
    out: list[Finding] = []
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        reclaimable = _parse_size(str(row.get("Reclaimable", "")))
        if reclaimable <= 0:
            continue
        out.append(
            Finding(
                category=cat_name,
                label=f"{ctx}: {row.get('Type', '?')} reclaimable",
                size_bytes=reclaimable,
                detail=f"total {row.get('Size', '?')}, active {row.get('Active', '?')}",
            )
        )
    return out


def _parse_size(text: str) -> int:
    """Parse docker's human sizes (`120.9GB (48%)`) into bytes; 0 if unparsable."""
    head = text.split("(", maxsplit=1)[0].strip()
    units = {"TB": 1000**4, "GB": 1000**3, "MB": 1000**2, "kB": 1000, "B": 1}
    for suffix, mult in units.items():
        if head.endswith(suffix):
            try:
                return int(float(head[: -len(suffix)].strip()) * mult)
            except ValueError:
                return 0
    return 0


def scan_ollama(cat: Category, _repo_root: Path) -> list[Finding]:
    """Report ollama models, honouring the `keep` allowlist."""
    if not shutil.which("ollama"):
        return []
    rc, raw = _run(["ollama", "list"])
    if rc != 0:
        return []
    keep = set(cat.options.get("keep", []))
    out: list[Finding] = []
    for line in raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) < _OLLAMA_MIN_COLUMNS:
            continue
        name = parts[0]
        modified = " ".join(parts[4:])
        if name in keep or not _ollama_is_stale(modified, cat.age_days):
            continue
        out.append(
            Finding(
                category=cat.name,
                label=name,
                size_bytes=_parse_size("".join(parts[2:4]).replace(" ", "")),
                detail=modified or "no modified time reported",
            )
        )
    return out


def scan_dirs(cat: Category, _repo_root: Path) -> list[Finding]:
    """Report ENTRIES INSIDE each configured cache root that are older than `age_days`.

    Two things this deliberately does not do, both of which it used to.

    It never emits the configured root as a finding. Doing so made `--apply`
    an `rmtree` of the whole of `~/Library/Caches` — including caches of running
    applications — and, since most of that tree needs Full Disk Access, it would
    have failed partway and left it half-destroyed.

    And it no longer ignores `age_days`. The key was declared on every cache
    category and read by none of them, so a config advertising a 30-day window
    deleted everything. `reclaim.toml` says age applies everywhere; now it does.
    """
    cutoff = _age_stamp(cat.age_days)
    out: list[Finding] = []
    for raw in cat.options.get("paths", []):
        root = _expand(raw)
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            hit = _stale_entry(cat, entry, cutoff)
            if hit:
                out.append(hit)
    return out


def _stale_entry(cat: Category, entry: Path, cutoff: str) -> Finding | None:
    """One cache entry, or None if anything inside it was touched since `cutoff`.

    `whole_tree = true` opts a category out of the age check. It exists because
    the age filter is wrong for a CONTENT-ADDRESSED cache: `~/.npm/_cacache` has
    three top-level directories that every install touches, so an age-filtered
    scan reports 0B forever and the category is dead weight. It stays OFF by
    default and must be written per category, because "delete regardless of age"
    is exactly the behaviour that made the first version dangerous — the point is
    that it is now a stated choice rather than an unstated one. The root itself
    is still never a target; only its entries are.
    """
    if entry.is_symlink():
        return None
    if not cat.options.get("whole_tree", False) and _touched_since(entry, cutoff):
        return None
    size = _dir_size(entry)
    if size < cat.min_size_bytes:
        return None
    return Finding(
        category=cat.name,
        label=entry.name,
        size_bytes=size,
        detail=(
            "regenerable — WHOLE TREE, age ignored (whole_tree=true)"
            if cat.options.get("whole_tree", False)
            else f"regenerable — nothing inside modified since {cutoff[:10]}"
        ),
        path=entry,
    )


def _touched_since(path: Path, cutoff: str) -> bool:
    """True if ANY file under `path` was modified since `cutoff`.

    A directory's own mtime does not move when a file deep inside it is
    rewritten in place, so the entry's `st_mtime` is not a safe staleness
    signal for a cache tree. `find -newermt` answers the real question and
    `-quit` stops it at the first hit.

    The cutoff is an ABSOLUTE timestamp on purpose: the relative form
    (`-newermt '-30 days'`) is not accepted by the `find` on this machine at
    all, and on BSD `find` it silently matches nothing — indistinguishable
    from "no recent files", which would mark a live cache as stale.
    Control-armed in `tests/test_reclaim.py`.
    """
    rc, out = _run(["find", str(path), "-newermt", cutoff, "-print", "-quit"])
    if rc != 0 and not out:
        # Could not ask. Treat as RECENT — a scan that failed must never be
        # rendered as permission to delete (`probes-need-a-control-arm.md`).
        return True
    return bool(out.strip())


def _age_stamp(age_days: int) -> str:
    """The cutoff as `YYYY-MM-DDTHH:MM:SS`, which `find -newermt` accepts."""
    import datetime

    when = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=age_days)
    return when.strftime("%Y-%m-%dT%H:%M:%S")


def scan_files(cat: Category, _repo_root: Path) -> list[Finding]:
    """Report files matching the configured extensions, over size and age."""
    cutoff = _age_cutoff(cat.age_days)
    out: list[Finding] = []
    exts = tuple(cat.options.get("extensions", []))
    for raw in cat.options.get("paths", []):
        root = _expand(raw)
        if not root.is_dir():
            continue
        for p in root.iterdir():
            hit = _file_finding(cat, p, exts, cutoff)
            if hit:
                out.append(hit)
    return out


def _file_finding(cat: Category, p: Path, exts: tuple, cutoff: float) -> Finding | None:
    """One file's finding, or None when it fails any of the three filters."""
    try:
        if not p.is_file() or not p.name.endswith(exts):
            return None
        st = p.stat()
    except OSError:
        return None
    if st.st_size < cat.min_size_bytes or st.st_mtime > cutoff:
        return None
    age = int((_now() - st.st_mtime) / 86400)
    return Finding(
        category=cat.name,
        label=p.name,
        size_bytes=_allocated(st),
        detail=f"{age}d old — {p.parent}",
        path=p,
    )


def scan_mise_versions(cat: Category, _repo_root: Path) -> list[Finding]:
    """Report installed mise tool versions that are neither pinned nor newest."""
    root = _expand(str(cat.options.get("root", "~/.local/share/mise/installs")))
    if not root.is_dir():
        return []
    keep_newest = int(cat.options.get("keep_newest", 1))
    pinned = _mise_pinned() if cat.options.get("keep_pinned", True) else set()
    out: list[Finding] = []
    for tool in sorted(root.iterdir()):
        if tool.is_dir():
            out.extend(_stale_versions(cat, tool, keep_newest, pinned))
    return out


def _stale_versions(cat: Category, tool: Path, keep_newest: int, pinned: set[str]) -> list[Finding]:
    """Versions of one tool that may go: not pinned, not a channel alias, not newest."""
    versions = [
        d for d in tool.iterdir() if d.is_dir() and not d.is_symlink() and _is_concrete(d.name)
    ]
    versions.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    out: list[Finding] = []
    for d in versions[keep_newest:]:
        if f"{tool.name}@{d.name}" in pinned or d.name in pinned:
            continue
        size = _dir_size(d)
        if size >= cat.min_size_bytes:
            out.append(
                Finding(
                    category=cat.name,
                    label=f"{tool.name}@{d.name}",
                    size_bytes=size,
                    detail=f"superseded — {len(versions)} versions of {tool.name} installed",
                    path=d,
                )
            )
    return out


def _is_concrete(name: str) -> bool:
    """True for a full version like `0.9.35`, false for channels like `0.9` or `latest`."""
    return name.count(".") >= _VERSION_DOTS and name[0].isdigit()


def _mise_pinned() -> set[str]:
    """Every version any reachable mise config pins, as `tool@version` and bare."""
    rc, raw = _run(["mise", "ls", "--json", "--installed"])
    if rc != 0 or not raw:
        return set()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    pinned: set[str] = set()
    for tool, entries in data.items():
        for e in entries if isinstance(entries, list) else []:
            if isinstance(e, dict) and e.get("requested_version"):
                pinned.add(f"{tool}@{e.get('version', '')}")
                pinned.add(str(e.get("version", "")))
    return pinned


def scan_homebrew(cat: Category, _repo_root: Path) -> list[Finding]:
    """Ask `brew cleanup --dry-run` what it would free — do not walk paths.

    Homebrew earns its own kind rather than another cache path for one reason:
    `brew cleanup` also removes **old versions of installed formulae from the
    Cellar** and stale vendored portable-ruby trees, neither of which lives in
    `brew --cache`. A `dirs` category pointed at the cache can never reach them.

    The size is brew's own figure, so it stays right when brew's policy changes.
    """
    if not shutil.which("brew"):
        return []
    argv = ["brew", "cleanup", "--dry-run", f"--prune={cat.age_days}"]
    if cat.options.get("scrub", False):
        argv.append("--scrub")
    rc, out = _run(argv)
    if rc != 0:
        return []
    size = _brew_freed_bytes(out)
    if size <= 0:
        return []
    return [
        Finding(
            category=cat.name,
            label=f"brew cleanup --prune={cat.age_days}",
            size_bytes=size,
            detail=(
                "brew's own estimate: stale downloads, superseded Cellar versions "
                "and vendored ruby. Overlaps `caches_homebrew` on the cache portion "
                "only — enable one or the other to avoid counting those bytes twice"
            ),
        )
    ]


#: brew's summary reads "...would free approximately 9.1GB of disk space." — the
#: size is MID-SENTENCE, so it must be extracted by pattern rather than by
#: trimming the tail. The first version trimmed, handed `_parse_size` the string
#: "9.1GB of disk space", and got 0 back: the category reported "nothing found"
#: over a real 9.1GB. A silent zero from a parser is indistinguishable from an
#: empty result, which is why this pattern is pinned by its own test.
_BREW_SIZE_RE = re.compile(r"([\d.]+)\s*(TB|GB|MB|kB|B)\b")


def _brew_freed_bytes(out: str) -> int:
    """Pull the `would free approximately N` figure out of brew's summary line."""
    for line in reversed(out.splitlines()):
        if "free approximately" not in line:
            continue
        m = _BREW_SIZE_RE.search(line.rsplit("approximately", 1)[-1])
        if m:
            return _parse_size(f"{m.group(1)}{m.group(2)}")
    return 0


def _ollama_is_stale(modified: str, age_days: int) -> bool:
    """True when `ollama list`'s MODIFIED column is older than `age_days`.

    `ollama` prints a relative phrase ("2 weeks ago", "3 days ago"), not a
    timestamp, so this parses that phrase. An UNPARSABLE or empty value is
    treated as NOT stale — a model whose age could not be established must
    never become a deletion candidate. Before this existed, `age_days` was
    declared on the category and read by nothing, so `--apply` removed every
    model including one pulled minutes earlier.
    """
    units = {"second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}
    m = re.match(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", modified.strip())
    if not m:
        return False
    return int(m.group(1)) * units[m.group(2)] >= age_days


_SCANNERS = {
    "docker": scan_docker,
    "ollama": scan_ollama,
    "dirs": scan_dirs,
    "files": scan_files,
    "mise_versions": scan_mise_versions,
    "homebrew": scan_homebrew,
}


def _now() -> float:
    """Wall clock as epoch seconds — one seam so tests can pin it."""
    import time

    return time.time()


def _age_cutoff(age_days: int) -> float:
    """Mtime below this counts as stale."""
    return _now() - age_days * 86400


def plan(cats: list[Category], repo_root: Path) -> list[Finding]:
    """Scan every enabled category. Read-only by construction — nothing mutates."""
    out: list[Finding] = []
    for cat in cats:
        scanner = _SCANNERS.get(cat.kind)
        if not cat.enabled or scanner is None:
            continue
        # Printed BEFORE the scan, not after. Sizing a cache tree is the slow
        # part of this tool, and a scanner that announces itself only on
        # completion is indistinguishable from one that has hung.
        print(f"scanning {cat.name} ({cat.kind})…", flush=True)
        out.extend(scanner(cat, repo_root))
    return sorted(out, key=lambda f: f.size_bytes, reverse=True)


# ─── apply ───────────────────────────────────────────────────────────────────


def _category_roots(cat: Category) -> list[Path]:
    """The only directories this category is permitted to act inside."""
    if cat.kind == "mise_versions":
        return [_expand(str(cat.options.get("root", "~/.local/share/mise/installs")))]
    return [_expand(p) for p in cat.options.get("paths", [])]


def apply_docker(cat: Category) -> list[str]:
    """Prune each engine with docker's OWN age filter, then re-measure the image.

    The re-measure is the point. `docker system prune` reports what it freed
    inside the engine, and on macOS that number routinely has no effect on the
    host file — so a run that reports "freed 120GB" while the disk image is
    unchanged is reported as exactly that, rather than as 120GB of disk.
    """
    lines: list[str] = []
    hours = cat.age_days * _HOURS_PER_DAY
    prune = cat.options.get("prune", {})
    for eng in cat.options.get("engines", []):
        ctx = eng.get("context", "")
        img = _expand(eng.get("disk_image", ""))
        before = _dir_size(img)
        argv = ["docker", "system", "prune", "--force", "--filter", f"until={hours}h"]
        if prune.get("images", True):
            argv.append("--all")
        if not prune.get("containers", True):
            # `docker system prune` ALWAYS removes stopped containers and has no
            # flag to keep them, so honouring `containers = false` means not
            # running it. The key was previously declared and never read, which
            # let the config claim a protection it did not provide.
            lines.append(
                f"  {ctx}: SKIPPED system prune — reclaim.toml sets prune.containers=false"
            )
            continue
        if prune.get("volumes", False):
            argv.append("--volumes")
        rc, out = _run(argv, env_context=ctx)
        lines.append(f"  {ctx}: prune rc={rc} — {out.splitlines()[-1] if out else 'no output'}")
        if prune.get("build_cache", True):
            brc, bout = _run(
                ["docker", "builder", "prune", "--force", "--filter", f"until={hours}h"],
                env_context=ctx,
            )
            tail = bout.splitlines()[-1] if bout else ""
            lines.append(f"  {ctx}: builder prune rc={brc} — {tail}")
        after = _dir_size(img)
        lines.append(_image_delta_line(ctx, img, before, after))
    return lines


def _image_delta_line(ctx: str, img: Path, before: int, after: int) -> str:
    """State plainly whether the host-side disk image actually shrank."""
    if before == 0:
        return f"  {ctx}: no disk image found at {img} — host-side effect UNKNOWN, not zero"
    if after >= before:
        return (
            f"  {ctx}: disk image {human(before)} -> {human(after)} — DID NOT SHRINK. "
            f"Space was freed inside the engine; macOS still holds the file. "
            f"Reclaim it via Docker Desktop > Settings > Resources (or Troubleshoot > "
            f"Clean/Purge data). This tool will not rewrite a live VM disk."
        )
    return f"  {ctx}: disk image {human(before)} -> {human(after)} — freed {human(before - after)}"


def apply_deletions(cat: Category, findings: list[Finding], repo_root: Path) -> list[str]:
    """Delete this category's findings, refusing anything outside its roots."""
    roots = _category_roots(cat)
    lines: list[str] = []
    for f in findings:
        if f.path is None:
            continue
        try:
            _guard_path(f.path, roots, repo_root)
        except ReclaimError as err:
            lines.append(f"  REFUSED {f.label}: {err}")
            continue
        lines.append(_delete_one(f))
    return lines


def _delete_one(f: Finding) -> str:
    """Remove one finding's path, reporting the outcome rather than raising."""
    target = f.path
    if target is None or not target.exists():
        return f"  SKIP {f.label}: no longer present"
    try:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as err:
        return f"  FAILED {f.label}: {err}"
    return f"  removed {f.label} ({human(f.size_bytes)})"


def apply_ollama(_cat: Category, findings: list[Finding]) -> list[str]:
    """Remove ollama models through ollama's own CLI, never by deleting blobs.

    Blobs are content-addressed and shared between models, so deleting a blob
    directory by hand corrupts every other model that references it.
    """
    lines: list[str] = []
    for f in findings:
        rc, out = _run(["ollama", "rm", f.label])
        verb = "removed" if rc == 0 else f"FAILED rc={rc}"
        lines.append(f"  {verb} {f.label} ({human(f.size_bytes)}) {out}")
    return lines


def apply_homebrew(cat: Category) -> list[str]:
    """Run `brew cleanup` with its OWN prune window — never delete brew paths by hand."""
    argv = ["brew", "cleanup", f"--prune={cat.age_days}"]
    if cat.options.get("scrub", False):
        argv.append("--scrub")
    rc, out = _run(argv)
    tail = out.splitlines()[-1] if out else "no output"
    return [f"  brew cleanup rc={rc} — {tail}"]


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _report(findings: list[Finding], cats: list[Category]) -> int:
    """Print the ranked plan. Returns the total reclaimable bytes."""
    by_cat: dict[str, list[Finding]] = {}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)
    total = 0
    for cat in cats:
        hits = by_cat.get(cat.name, [])
        if not cat.enabled:
            print(f"\n{cat.name}: DISABLED in reclaim.toml")
            continue
        sub = sum(f.size_bytes for f in hits if not f.informational)
        total += sub
        n_real = sum(1 for f in hits if not f.informational)
        print(f"\n{cat.name} ({cat.kind}) — {human(sub)} across {n_real} item(s)")
        if not hits:
            print("  nothing found — scanned, not skipped")
        for f in hits[:_LIST_LIMIT]:
            tag = "  (context, not counted)" if f.informational else ""
            print(f"  {human(f.size_bytes):>7}  {f.label}  [{f.detail}]{tag}")
        if len(hits) > _LIST_LIMIT:
            rest = sum(f.size_bytes for f in hits[_LIST_LIMIT:] if not f.informational)
            print(f"  … and {len(hits) - _LIST_LIMIT} more totalling {human(rest)}")
    return total


def main(argv: list[str], repo_root: Path) -> int:
    """`kb-setup reclaim` — report by default, reclaim only on an explicit --apply."""
    apply_it = "--apply" in argv
    cfg_path = repo_root / "reclaim.toml"
    try:
        only = _opt_list(argv, "--only")
        skip = _opt_list(argv, "--skip")
        cats = load_config(cfg_path)
    except ReclaimError as err:
        print(f"reclaim: {err}")
        return 2
    cats = [c for c in cats if (not only or c.name in only) and c.name not in skip]
    if only and not cats:
        print(f"reclaim: --only {sorted(only)} matched no category in {cfg_path}")
        return 2
    findings = plan(cats, repo_root)
    total = _report(findings, cats)
    n_real = sum(1 for f in findings if not f.informational)
    print(f"\nreclaim: {human(total)} reclaimable across {n_real} finding(s)")
    if not apply_it:
        print("reclaim: DRY RUN — nothing was deleted. Re-run with `-- --apply` to reclaim.")
        return 0
    return _apply_all(cats, findings, repo_root)


def _opt_list(argv: list[str], flag: str) -> set[str]:
    """Comma-separated values for `flag`, or an empty set when absent."""
    if flag not in argv:
        return set()
    idx = argv.index(flag)
    if idx + 1 >= len(argv) or argv[idx + 1].startswith("--"):
        # A filter flag with no value used to return an empty set, which reads
        # as "no filter" and silently WIDENED `--only` to every category — the
        # opposite of what the user asked for, on the destructive path.
        raise ReclaimError(f"{flag} needs a comma-separated value")
    return {p.strip() for p in argv[idx + 1].split(",") if p.strip()}


def _apply_all(cats: list[Category], findings: list[Finding], repo_root: Path) -> int:
    """Execute every enabled category's reclamation, reporting each outcome."""
    print("\nreclaim: APPLYING")
    for cat in cats:
        if not cat.enabled:
            continue
        hits = [f for f in findings if f.category == cat.name]
        print(f"\n{cat.name}:")
        if cat.kind == "homebrew":
            lines = apply_homebrew(cat)
        elif cat.kind == "docker":
            lines = apply_docker(cat)
        elif cat.kind == "ollama":
            lines = apply_ollama(cat, hits)
        else:
            lines = apply_deletions(cat, hits, repo_root)
        for line in lines or ["  nothing to do"]:
            print(line)
    print("\nreclaim: done — re-run without --apply to see what remains")
    return 0
