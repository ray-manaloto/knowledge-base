# Copyright (c) 2026 Raymond Manaloto
"""Refresh provenance-bound, multi-site offline documentation mirrors (#837/#847).

Refresh combines llms.txt, sitemap.xml, webclaw map and known rows. Measured for
Claude Code, the map is a strict subset of the current page set; for agentsview,
it reads the same sitemap. The third inventory catches future divergence.
Native markdown is preferred. Webclaw may recover HTML or same-page redirects,
but never a moved page, 404/410, server failure or network error.

Unlisted 404/410 pages retire after three consecutive misses spanning seven
days. All writes are deferred until every fetch returns; they are not
transactional. An unavailable inventory writes nothing. CI never commits, so
misses accumulate only through committed refresh runs: local runs or #834's
future rolling PR. Check and SessionStart are offline and never invoke webclaw;
SessionStart also spawns nothing, so the codex-docs pin age (one `git log`) is
reported by `check` only.

This module's import closure is stdlib plus structlog, allowing the read-only CI
job to run without the project's graphify environment.
"""

from __future__ import annotations

import http.client
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import TypedDict, Unpack
from urllib.parse import urljoin, urlsplit

from kb_setup import events, manifest
from kb_setup.result import Rc

FETCH_TSV = "fetch.tsv"
STAMP = "fetch.stamp.json"
MISSES = "fetch.misses.json"
STALE_AFTER_DAYS = 7
RETIRE_AFTER = 3
RETIRE_MIN_AGE = timedelta(days=7)
_TIMEOUT_S = 30
_WEBCLAW_TIMEOUT_S = 120
_GIT_TIMEOUT_S = 10
_REFRESH_ARGS = 2
_URL = re.compile(r"https://[^\s<>\"')\]]+")


@dataclass(frozen=True)
class Site:
    """One site's fetch host, canonical page namespace and mirror policy."""

    key: str
    tag: str
    mirror: Path
    origin: str
    prefix: str
    inventories: tuple[str, ...]
    host_aliases: tuple[str, ...]
    index_sections: tuple[str, ...]
    grandfathered: tuple[str, ...]
    refresh_task: str


SITES: dict[str, Site] = {
    "claude-code": Site(
        key="claude-code",
        tag="ccdocs",
        mirror=Path("sources/media/claude-code-docs"),
        origin="https://code.claude.com",
        prefix="https://code.claude.com/docs/en/",
        inventories=(
            "https://code.claude.com/docs/llms.txt",
            "https://code.claude.com/docs/sitemap.xml",
        ),
        host_aliases=(),
        index_sections=(),
        grandfathered=("https://code.claude.com/docs/en/claude-tag",),
        refresh_task="kb-ccdocs-refresh",
    ),
    "agentsview": Site(
        key="agentsview",
        tag="avdocs",
        mirror=Path("sources/media/agentsview-docs"),
        origin="https://www.agentsview.io",
        prefix="https://www.agentsview.io/",
        inventories=("https://www.agentsview.io/llms.txt", "https://www.agentsview.io/sitemap.xml"),
        host_aliases=("agentsview.io",),
        index_sections=("", "docs"),
        grandfathered=(),
        refresh_task="kb-avdocs-refresh",
    ),
}


@dataclass(frozen=True)
class Response:
    """One native GET, with no redirect following; error means no HTTP answer."""

    status: int
    content_type: str
    body: bytes
    error: str = ""
    location: str = ""


@dataclass(frozen=True)
class WebclawPage:
    """Fallback markdown and the URL webclaw actually fetched."""

    final_url: str
    markdown: bytes


Fetcher = Callable[[str], Response]
Mapper = Callable[[Site], list[str] | None]
PageFetcher = Callable[[str], WebclawPage | None]
Git = Callable[..., subprocess.CompletedProcess[str]]


class _WebclawAdapters(TypedDict, total=False):
    mapper: Mapper | None
    page_fetcher: PageFetcher | None


@dataclass(frozen=True)
class Row:
    """One unchanged four-field fetch.tsv row: URL, status, method, bytes."""

    url: str
    status: str
    method: str
    size: int

    def line(self) -> str:
        """Render one tab-separated provenance row."""
        return f"{self.url}\t{self.status}\t{self.method}\t{self.size}"


def _site_path(site: Site, url: str) -> str | None:
    if "?" in url or "#" in url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = urlsplit(site.origin).netloc
    if parts.scheme != "https" or parts.netloc not in (host, *site.host_aliases):
        return None
    canonical = site.origin + (parts.path or "/")
    return canonical.removeprefix(site.prefix) if canonical.startswith(site.prefix) else None


def normalise(site: Site, url: str) -> str | None:
    """Return a canonical site page, dropping queries, fragments and assets."""
    relative = _site_path(site, url)
    if relative is None or Path(relative.rstrip("/")).suffix not in {"", ".md"}:
        return None
    path = relative.removesuffix(".md").strip("/")
    if path in site.index_sections:
        path = f"{path}/index" if path else "index"
    if not path or not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
        return None
    # `a/../b`, `a/./b` and `a//b` name a page another spelling also names, and
    # would mirror it twice under different flat filenames (cold review of 8e40ed1b).
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return None
    return site.prefix + path


def page_name(site: Site, url: str) -> str:
    """Map a canonical page to the existing flat a__b.md filename scheme."""
    canonical = normalise(site, url)
    if canonical is None:
        raise ValueError(f"not a {site.key} docs page: {url}")
    return canonical.removeprefix(site.prefix).replace("/", "__") + ".md"


def fetch(url: str) -> Response:
    """GET a native page without following redirects, retaining Location."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return Response(0, "", b"", f"refusing non-https url: {url}")
    conn = http.client.HTTPSConnection(parts.hostname, timeout=_TIMEOUT_S)
    try:
        conn.request("GET", parts.path or "/")
        resp = conn.getresponse()
        return Response(
            resp.status,
            resp.getheader("Content-Type", ""),
            resp.read(),
            location=resp.getheader("Location", ""),
        )
    except (OSError, TimeoutError, http.client.HTTPException) as e:
        return Response(0, "", b"", f"fetch failed: {type(e).__name__}: {e}")
    finally:
        conn.close()


def webclaw_map(site: Site) -> list[str] | None:
    """Read the third inventory; no crawl fallback or calls from offline checks."""
    try:
        result = subprocess.run(
            ["webclaw", "--map", "--no-map-crawl", site.origin],
            capture_output=True,
            text=True,
            timeout=_WEBCLAW_TIMEOUT_S,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return result.stdout.splitlines() if result.returncode == 0 else None


def webclaw_fetch(url: str) -> WebclawPage | None:
    """Read content.markdown and metadata.url from webclaw's JSON output.

    Measured: a 404 exits 1 with empty stdout. Claude-tag exits 0 but follows an
    off-site redirect to https://claude.com/docs/claude-tag/overview; the caller
    must validate the final URL before accepting any bytes.
    """
    try:
        result = subprocess.run(
            ["webclaw", "-f", "json", url],
            capture_output=True,
            text=True,
            timeout=_WEBCLAW_TIMEOUT_S,
            check=False,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        markdown = data["content"]["markdown"]
        final_url = data["metadata"]["url"]
    except OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError:
        return None
    if not isinstance(markdown, str) or not markdown.strip() or not isinstance(final_url, str):
        return None
    return WebclawPage(final_url, markdown.encode("utf-8"))


class MirrorUnreadableError(RuntimeError):
    """The previous provenance or retirement state cannot be read safely."""


class InventoryUnavailableError(RuntimeError):
    """An inventory is unavailable, so the refresh cannot establish coverage."""


def read_rows(mirror: Path) -> dict[str, Row]:
    """Read the unchanged four-field table, or return empty before first fetch."""
    path = mirror / FETCH_TSV
    if not path.exists():
        return {}
    rows: dict[str, Row] = {}
    try:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                url, status, method, size = line.split("\t")
                rows[url] = Row(url, status, method, int(size))
            except ValueError as e:
                raise MirrorUnreadableError(f"{path}:{n}: not a 4-field row ({e})") from e
    except (OSError, UnicodeError) as e:
        raise MirrorUnreadableError(f"{path}: {e}") from e
    return rows


def inventory_urls(site: Site, text: str) -> set[str]:
    """Extract site pages without truncating queries into valid page URLs."""
    return {
        canonical
        for raw in _URL.findall(text)
        if (canonical := normalise(site, raw.rstrip(".,;"))) is not None
    }


def discover(site: Site, fetcher: Fetcher, *, mapper: Mapper | None = None) -> set[str]:
    """Inventory membership only; known rows are added separately by refresh."""
    found: set[str] = set()
    for inv in site.inventories:
        resp = fetcher(inv)
        if resp.error or resp.status != HTTPStatus.OK:
            raise InventoryUnavailableError(f"{inv}: {resp.error or f'HTTP {resp.status}'}")
        urls = inventory_urls(site, resp.body.decode("utf-8", errors="replace"))
        if not urls:
            raise InventoryUnavailableError(f"{inv}: listed no docs pages (format changed?)")
        found |= urls
    mapped = (mapper or webclaw_map)(site)
    mapped_urls = inventory_urls(site, "\n".join(mapped)) if mapped is not None else set()
    if not mapped_urls:
        raise InventoryUnavailableError(
            f"{site.origin}: webclaw map unavailable or listed no pages"
        )
    return found | mapped_urls


@dataclass(frozen=True)
class _Miss:
    count: int
    first_seen: str


def _read_misses(mirror: Path) -> dict[str, _Miss]:
    path = mirror / MISSES
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        misses = {url: _parse_miss(value) for url, value in data.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise MirrorUnreadableError(f"{path}: {e}") from e
    return misses


def _parse_miss(value: dict[str, object]) -> _Miss:
    count, first_seen = value["count"], value["first_seen"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("miss count must be a positive integer")
    if not isinstance(first_seen, str) or datetime.fromisoformat(first_seen).tzinfo is None:
        raise ValueError("first_seen must be a timezone-aware ISO timestamp")
    return _Miss(count, first_seen)


@dataclass
class Outcome:
    """URLs added, changed, kept, missing or retired, and the stamp decision."""

    added: list[str]
    changed: list[str]
    unchanged: int
    kept: list[str]
    missing: list[str]
    stamped: bool = False
    retired: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Refresh:
    site: Site
    now: datetime
    listed: set[str]
    misses: dict[str, _Miss]
    rows: dict[str, Row] = field(default_factory=dict)
    writes: dict[Path, bytes] = field(default_factory=dict)
    out: Outcome = field(default_factory=lambda: Outcome([], [], 0, [], []))


def _retire(url: str, resp: Response, state: _Refresh) -> bool:
    site, misses = state.site, state.misses
    if (
        resp.error
        or resp.status not in {HTTPStatus.NOT_FOUND, HTTPStatus.GONE}
        or url in state.listed
    ):
        misses.pop(url, None)
        return False
    previous = misses.get(url, _Miss(0, state.now.isoformat()))
    miss = _Miss(previous.count + 1, previous.first_seen)
    misses[url] = miss
    age = state.now - datetime.fromisoformat(miss.first_seen)
    if miss.count >= RETIRE_AFTER and age >= RETIRE_MIN_AGE:
        misses.pop(url)
        events.fail(
            f"{site.tag}.retired",
            f"[{site.tag}]   RETIRED ({miss.count} consecutive 404s since {miss.first_seen}, "
            f"absent from every inventory): {url}",
        )
        return True
    events.warn(
        f"{site.tag}.retire_candidate",
        f"[{site.tag}]   retirement candidate ({miss.count} consecutive 404s "
        f"since {miss.first_seen}): {url}",
    )
    return False


@dataclass(frozen=True)
class _Page:
    body: bytes
    status: str
    method: str


def _moved(site: Site, url: str, resp: Response) -> bool:
    if not HTTPStatus.MULTIPLE_CHOICES <= resp.status < HTTPStatus.BAD_REQUEST:
        return False
    if resp.location and normalise(site, urljoin(url + ".md", resp.location)) == url:
        return False
    events.warn(f"{site.tag}.moved", f"[{site.tag}]   MOVED {url} -> {resp.location}")
    return True


def _page(
    site: Site, url: str, resp: Response, *, eligible: bool, fallback: PageFetcher
) -> _Page | None:
    ctype = resp.content_type
    if not resp.error and resp.status == HTTPStatus.OK and "markdown" in ctype:
        return _Page(resp.body, f"{resp.status}|{ctype}", "md")
    if resp.error or _moved(site, url, resp):
        return None
    same_page_redirect = HTTPStatus.MULTIPLE_CHOICES <= resp.status < HTTPStatus.BAD_REQUEST
    if not eligible or not (resp.status == HTTPStatus.OK or same_page_redirect):
        return None
    page = fallback(url)
    if page is None:
        return None
    if normalise(site, page.final_url) != url:
        events.warn(
            f"{site.tag}.webclaw_rejected",
            f"[{site.tag}]   webclaw rejected {url}: final_url {page.final_url}",
        )
        return None
    return _Page(page.markdown, "200|text/markdown; source=webclaw", "webclaw")


def _record_page(
    url: str,
    target: Path,
    page: _Page,
    *,
    old: dict[str, Row],
    state: _Refresh,
) -> Row:
    out = state.out
    if url not in old or not target.is_file():
        out.added.append(url)
    elif target.read_bytes() != page.body:
        out.changed.append(url)
    else:
        out.unchanged += 1
    state.writes[target] = page.body
    return Row(url, page.status, page.method, len(page.body))


def refresh(
    repo_root: Path,
    site: Site,
    *,
    fetcher: Fetcher | None = None,
    now: datetime | None = None,
    **adapters: Unpack[_WebclawAdapters],
) -> Outcome:
    """Fetch every page and defer all mirror writes until every fetch returns.

    Defaults resolve through module attributes at call time. Failed previous
    pages hold the stamp back, except grandfathered webclaw rows. Inventory or
    provenance errors raise before any writes, including deletions and misses.
    """
    native = fetcher or fetch
    fallback = adapters.get("page_fetcher") or webclaw_fetch
    instant = now or datetime.now(UTC)
    mirror = repo_root / site.mirror
    old = read_rows(mirror)
    for url in old:
        # A row that no longer names a page of this site would crash `page_name`
        # mid-loop; refuse before anything is fetched or written instead.
        if normalise(site, url) != url:
            raise MirrorUnreadableError(f"{mirror / FETCH_TSV}: not a {site.key} page: {url}")
    misses = _read_misses(mirror)
    listed = discover(site, native, mapper=adapters.get("mapper"))
    # A miss is only meaningful for a page this run is responsible for; one whose
    # row is gone and that no inventory lists would otherwise be rewritten forever.
    for url in [u for u in misses if u not in listed and u not in old]:
        del misses[url]
    state = _Refresh(site, instant, listed, misses)
    rows, writes, out = state.rows, state.writes, state.out
    stale_pages = 0
    for url in sorted(listed | old.keys()):
        target = mirror / page_name(site, url)
        resp = native(url + ".md")
        if _retire(url, resp, state):
            out.retired.append(url)
            continue
        eligible = url in listed or (url in old and old[url].method == "webclaw")
        page = _page(site, url, resp, eligible=eligible, fallback=fallback)
        if page is not None:
            rows[url] = _record_page(url, target, page, old=old, state=state)
        elif url in old and target.is_file():
            out.kept.append(f"{url} ({resp.error or f'HTTP {resp.status} {resp.content_type}'})")
            rows[url] = old[url]
            stale_pages += old[url].method != "webclaw" or url not in site.grandfathered
        else:
            out.missing.append(f"{url} ({resp.error or f'HTTP {resp.status} {resp.content_type}'})")
    _write_refresh(mirror, state)
    if (writes or out.retired) and not stale_pages and not out.missing:
        stamp = {"fetched_at": instant.isoformat(), "pages": len(rows)}
        (mirror / STAMP).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        out.stamped = True
    return out


def _write_refresh(mirror: Path, state: _Refresh) -> None:
    site, rows, misses, out = state.site, state.rows, state.misses, state.out
    mirror.mkdir(parents=True, exist_ok=True)
    for url in out.retired:
        (mirror / page_name(site, url)).unlink(missing_ok=True)
    for target, data in state.writes.items():
        target.write_bytes(data)
    body = "".join(rows[u].line() + "\n" for u in sorted(rows))
    (mirror / FETCH_TSV).write_text(body, encoding="utf-8")
    if misses:
        data = {url: {"count": m.count, "first_seen": m.first_seen} for url, m in misses.items()}
        (mirror / MISSES).write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        (mirror / MISSES).unlink(missing_ok=True)


def staleness(
    repo_root: Path, site: Site = SITES["claude-code"], *, now: datetime | None = None
) -> str:
    """Offline warning for an initialized mirror; a never-fetched site is silent.

    "Never fetched" means no `fetch.tsv`, no stamp and no page: a `.gitkeep`-only
    directory. A mirror holding pages but no readable stamp is still UNKNOWN, as
    it was before the engine became multi-site (cold review of 8e40ed1b).
    """
    mirror = repo_root / site.mirror
    if not mirror.is_dir():
        return ""
    if not ((mirror / FETCH_TSV).exists() or (mirror / STAMP).exists() or any(mirror.glob("*.md"))):
        return ""
    unknown = f"{site.mirror}: freshness UNKNOWN ({{}}) — run `mise run {site.refresh_task}`"
    try:
        stamp = json.loads((mirror / STAMP).read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(stamp["fetched_at"])
        age = ((now or datetime.now(UTC)) - fetched).days
    except (OSError, ValueError, KeyError, TypeError) as e:
        return unknown.format(type(e).__name__)
    if age < 0:
        return unknown.format("stamp is in the future")
    if age >= STALE_AFTER_DAYS:
        return f"{site.mirror}: fetched {age} days ago — run `mise run {site.refresh_task}`"
    return ""


def codex_docs_staleness(
    repo_root: Path, now: datetime | None = None, *, git: Git | None = None
) -> str:
    """Offline age of the last advance of the codex-docs pin.

    ONE measure on every host: the commit that last touched the manifest. The
    pinned upstream commit's own date would need the gitignored clone, so the
    same committed state would answer differently on a host that has run
    `kb-build` and one that has not (cold review of 8e40ed1b). The manifest is
    still parsed, so a malformed one reads as UNKNOWN rather than as fresh.
    """
    path = repo_root / "sources/codex-docs.manifest"
    if not path.exists():
        return ""
    label = "age of the last pin advance"
    remedy = "run `mise run kb-update -- codex-docs`"
    try:
        manifest.load(path)
        args = [
            "git",
            "-C",
            str(repo_root),
            "log",
            "-1",
            "--format=%cI",
            "--",
            str(path.relative_to(repo_root)),
        ]
        result = (git or subprocess.run)(
            args, capture_output=True, text=True, check=True, timeout=_GIT_TIMEOUT_S
        )
        result.check_returncode()
        fetched = datetime.fromisoformat(result.stdout.strip())
        age = ((now or datetime.now(UTC)) - fetched).days
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as e:
        return (
            f"sources/codex-docs.manifest: freshness UNKNOWN "
            f"({type(e).__name__}; {label}) — {remedy}"
        )
    if age < 0:
        return f"sources/codex-docs.manifest: freshness UNKNOWN (pin is in the future) — {remedy}"
    if age >= STALE_AFTER_DAYS:
        return f"sources/codex-docs.manifest: {label}: {age} days — {remedy}"
    return ""


def report_staleness(
    repo_root: Path, *, sites: Sequence[Site] | None = None, include_codex: bool = False
) -> None:
    """Print SessionStart findings, preserving Claude Code's exact header shape.

    The codex pin is OFF by default here: its age costs a `git` spawn (~200 ms,
    measured in the cold review of 8e40ed1b) on a path documented as ~10 ms and
    stat-only. `kb-docs-check` and the CI job ask it instead.
    """
    for site in sites if sites is not None else SITES.values():
        line = staleness(repo_root, site)
        if line:
            name = "Claude Code" if site.key == "claude-code" else "agentsview"
            print(f"[{site.tag}] the vendored {name} docs may be stale (this is not drift):")
            print(f"[{site.tag}]   {line}")
    if include_codex and (line := codex_docs_staleness(repo_root)):
        print("[codexdocs] the pinned Codex docs may be stale (this is not drift):")
        print(f"[codexdocs]   {line}")


def _refresh_main(
    repo_root: Path,
    site: Site,
    *,
    fetcher: Fetcher | None,
    mapper: Mapper | None,
    page_fetcher: PageFetcher | None,
) -> Rc:
    try:
        out = refresh(repo_root, site, fetcher=fetcher, mapper=mapper, page_fetcher=page_fetcher)
    except (InventoryUnavailableError, MirrorUnreadableError) as exc:
        events.warn(f"{site.tag}.not_run", f"[{site.tag}] COULD NOT ASK, nothing written: {exc}")
        return Rc.NOT_RUN
    events.say(
        f"{site.tag}.refreshed",
        f"[{site.tag}] {len(out.added)} added, {len(out.changed)} changed, "
        f"{out.unchanged} unchanged, {len(out.kept)} kept, {len(out.missing)} missing",
        added=len(out.added),
        changed=len(out.changed),
        retired=len(out.retired),
    )
    for url in out.added:
        events.say(f"{site.tag}.added", f"[{site.tag}]   added {url}")
    for note in out.kept:
        events.warn(f"{site.tag}.kept", f"[{site.tag}]   kept previous copy: {note}")
    for note in out.missing:
        events.fail(f"{site.tag}.missing", f"[{site.tag}]   MISSING: {note}")
    if not out.stamped:
        events.fail(
            f"{site.tag}.not_stamped",
            f"[{site.tag}] stamp NOT advanced: some pages are still old copies "
            "— re-run once they serve",
        )
        return Rc.FINDINGS
    return Rc.OK


def _check(repo_root: Path) -> Rc:
    findings = False
    for site in SITES.values():
        if line := staleness(repo_root, site):
            events.warn(f"{site.tag}.stale", f"[{site.tag}] {line}")
            findings = True
    if line := codex_docs_staleness(repo_root):
        events.warn("codexdocs.stale", f"[codexdocs] {line}")
        findings = True
    return Rc.FINDINGS if findings else Rc.OK


def main(
    repo_root: Path,
    args: Sequence[str] | None = None,
    *,
    fetcher: Fetcher | None = None,
    mapper: Mapper | None = None,
    page_fetcher: PageFetcher | None = None,
) -> int:
    """Dispatch refresh <site>|all or offline check with documented return codes."""
    rest = list(args or [])
    if rest == ["check"]:
        return _check(repo_root)
    if len(rest) != _REFRESH_ARGS or rest[0] != "refresh" or rest[1] not in (*SITES, "all"):
        events.fail(
            "docs.bad_request", "usage: kb-setup docs refresh <site>|all | check", args=rest
        )
        return Rc.BAD_REQUEST
    sites = list(SITES.values()) if rest[1] == "all" else [SITES[rest[1]]]
    return max(
        _refresh_main(repo_root, site, fetcher=fetcher, mapper=mapper, page_fetcher=page_fetcher)
        for site in sites
    )


if __name__ == "__main__":
    raise SystemExit(main(Path.cwd(), sys.argv[1:]))
