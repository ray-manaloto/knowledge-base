# Copyright (c) 2026 Raymond Manaloto
"""Keep the vendored Claude Code docs mirror current — `kb-setup ccdocs`.

WHY THIS EXISTS (#829). `sources/media/claude-code-docs/` is a committed copy of
`code.claude.com/docs/en`, vendored because a live site has no commit a
`sources/*.manifest` could pin (and `sources/*/` is a gitignored, re-cloned
tree). Vendoring fixed "the pages never reach git" and created the opposite
risk: a frozen copy nothing updates. Measured on the day it was vendored, 107 of
231 pages differed from a copy taken ONE day earlier, and a stale page answers
"does Claude Code do X?" exactly as confidently as a fresh one.

So there are two halves, on `currency.docs`' precedent:

* :func:`refresh` — NETWORK. Re-fetches every page as native `.md`, adds any page
  an inventory newly lists, rewrites `fetch.tsv` and the stamp. `mise run
  kb-ccdocs-refresh`.
* :func:`staleness` — OFFLINE, a stat and one small JSON read. Wired into
  `currency check`, the SessionStart path, so an old mirror is SAID at the start
  of every session instead of discovered after it misled one.

COMPLETENESS IS PART OF THE REFRESH, not a separate step. The page set is the
union of `llms.txt`, `sitemap.xml` and the mirror's own `fetch.tsv` — the last
keeps pages the site still serves but no inventory lists (six plugin pages that
existing `$CC` citations name). A page some inventory lists that can be neither
fetched nor kept from the previous copy is a FINDING: the run says which, and
exits non-zero. An inventory that cannot be read is NOT_RUN and nothing is
written — a refresh that shrank the page set because `llms.txt` timed out would
look exactly like a site that removed pages.

A page that fails or stops serving markdown KEEPS its previous copy and row (and
says so). Dropping it would silently break the citations into it; whether a page
removed upstream should leave the corpus is a human's call, never this module's.

KNOWN GAP: webclaw discovery (#829 scope item 2) is not here — webclaw is pinned
only in the user-global mise config, so this repo cannot call it reproducibly.
The one webclaw-captured page (`claude-tag`, whose `.md` redirects off-site) is
kept as-is by the keep-previous rule above.
"""

from __future__ import annotations

import http.client
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from kb_setup import events
from kb_setup.result import Rc

#: The mirror, its provenance table, and its freshness stamp — all tracked.
MIRROR = Path("sources") / "media" / "claude-code-docs"
FETCH_TSV = "fetch.tsv"
STAMP = "fetch.stamp.json"

PREFIX = "https://code.claude.com/docs/en/"
INVENTORIES = (
    "https://code.claude.com/docs/llms.txt",
    "https://code.claude.com/docs/sitemap.xml",
)

#: The docs churn daily (107/231 pages in one day, measured 2026-10-02), so a week
#: is already a lot of drift; a month would be most of the site.
STALE_AFTER_DAYS = 7

_TIMEOUT_S = 30
_PAGE_URL = re.compile(r"https://code\.claude\.com/docs/en/[A-Za-z0-9_./-]+")


@dataclass(frozen=True)
class Response:
    """One GET's outcome. ``error`` is set when no HTTP answer was obtained."""

    status: int
    content_type: str
    body: bytes
    error: str = ""


#: Injectable so tests never touch the network.
Fetcher = Callable[[str], Response]


@dataclass(frozen=True)
class Row:
    """One `fetch.tsv` line: url, ``status|content-type``, method, bytes."""

    url: str
    status: str
    method: str
    size: int

    def line(self) -> str:
        """The row as one tab-separated `fetch.tsv` line, no padding."""
        return f"{self.url}\t{self.status}\t{self.method}\t{self.size}"


def page_name(url: str) -> str:
    """`…/en/a/b` -> `a__b.md`, the flat scheme `$CC` citations already use."""
    if not url.startswith(PREFIX):
        msg = f"not a Claude Code docs page: {url}"
        raise ValueError(msg)
    return url.removeprefix(PREFIX).replace("/", "__") + ".md"


def fetch(url: str) -> Response:
    """One GET, no redirects followed: a redirect is not the page we asked for."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return Response(0, "", b"", f"refusing non-https url: {url}")
    conn = http.client.HTTPSConnection(parts.hostname, timeout=_TIMEOUT_S)
    try:
        conn.request("GET", parts.path or "/")
        resp = conn.getresponse()
        return Response(resp.status, resp.getheader("Content-Type", ""), resp.read())
    except (OSError, TimeoutError) as e:
        return Response(0, "", b"", f"fetch failed: {e}")
    finally:
        conn.close()


def read_rows(mirror: Path) -> dict[str, Row]:
    """The mirror's `fetch.tsv`, keyed by URL; empty when there is none yet."""
    path = mirror / FETCH_TSV
    if not path.is_file():
        return {}
    rows: dict[str, Row] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        url, status, method, size = line.split("\t")
        rows[url] = Row(url, status, method, int(size))
    return rows


def inventory_urls(text: str) -> set[str]:
    """Every English docs page URL in an inventory, normalised to no `.md`."""
    return {u.rstrip(".").removesuffix(".md") for u in _PAGE_URL.findall(text)}


class InventoryUnavailableError(RuntimeError):
    """An inventory could not be read, so the page set is unknown."""


def discover(fetcher: Fetcher, known: set[str]) -> set[str]:
    """The page set: every inventory's URLs plus the pages already mirrored."""
    found = set(known)
    for inv in INVENTORIES:
        resp = fetcher(inv)
        if resp.error or resp.status != HTTPStatus.OK:
            reason = resp.error or f"HTTP {resp.status}"
            msg = f"{inv}: {reason}"
            raise InventoryUnavailableError(msg)
        urls = inventory_urls(resp.body.decode("utf-8", errors="replace"))
        if not urls:
            msg = f"{inv}: listed no docs pages (format changed?)"
            raise InventoryUnavailableError(msg)
        found |= urls
    return found


@dataclass
class Outcome:
    """What one refresh did, per page: URLs, except ``unchanged`` (a count)."""

    added: list[str]
    changed: list[str]
    unchanged: int
    kept: list[str]
    missing: list[str]


def refresh(repo_root: Path, *, fetcher: Fetcher = fetch, now: datetime | None = None) -> Outcome:
    """Re-fetch every page; keep a previous copy whenever a fetch fails.

    Raises :class:`InventoryUnavailableError` before writing anything.
    """
    mirror = repo_root / MIRROR
    old = read_rows(mirror)
    urls = discover(fetcher, set(old))
    rows: dict[str, Row] = {}
    out = Outcome([], [], 0, [], [])
    for url in sorted(urls):
        target = mirror / page_name(url)
        resp = fetcher(url + ".md")
        ctype = resp.content_type
        if not resp.error and resp.status == HTTPStatus.OK and "markdown" in ctype:
            if url not in old or not target.is_file():
                out.added.append(url)
            elif target.read_bytes() != resp.body:
                out.changed.append(url)
            else:
                out.unchanged += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(resp.body)
            rows[url] = Row(url, f"{resp.status}|{ctype}", "md", len(resp.body))
        elif url in old and target.is_file():
            out.kept.append(f"{url} ({resp.error or f'HTTP {resp.status} {ctype}'})")
            rows[url] = old[url]
        else:
            out.missing.append(f"{url} ({resp.error or f'HTTP {resp.status} {ctype}'})")
    body = "".join(rows[u].line() + "\n" for u in sorted(rows))
    (mirror / FETCH_TSV).write_text(body, encoding="utf-8")
    stamp = {"fetched_at": (now or datetime.now(UTC)).isoformat(), "pages": len(rows)}
    (mirror / STAMP).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return out


def staleness(repo_root: Path, *, now: datetime | None = None) -> str:
    """OFFLINE: one line when the mirror is old or its stamp unreadable, else ``""``.

    Silent when the repo has no mirror at all — the currency engine is shared
    with dotfiles, which vendors none, and "not this repo's source" is not a
    finding. A mirror WITHOUT a readable stamp is reported, never read as fresh.
    """
    mirror = repo_root / MIRROR
    if not mirror.is_dir():
        return ""
    try:
        stamp = json.loads((mirror / STAMP).read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(stamp["fetched_at"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        why = type(e).__name__
        return f"{MIRROR}: freshness UNKNOWN ({why}) — run `mise run kb-ccdocs-refresh`"
    age = ((now or datetime.now(UTC)) - fetched).days
    if age >= STALE_AFTER_DAYS:
        return f"{MIRROR}: fetched {age} days ago — run `mise run kb-ccdocs-refresh`"
    return ""


def report_staleness(repo_root: Path) -> None:
    """The SessionStart line, printed beside `currency check`'s other headers."""
    line = staleness(repo_root)
    if line:
        print("[ccdocs] the vendored Claude Code docs may be stale (this is not drift):")
        print(f"[ccdocs]   {line}")


def main(repo_root: Path, args: Sequence[str] | None = None, *, fetcher: Fetcher = fetch) -> int:
    """`refresh` (network) or `check` (offline). 0 ok, 1 findings, 127 could not ask."""
    rest = list(args or [])
    mode = rest[0] if rest else ""
    if mode == "check" and len(rest) == 1:
        line = staleness(repo_root)
        if line:
            events.warn("ccdocs.stale", f"[ccdocs] {line}")
            return Rc.FINDINGS
        events.say("ccdocs.fresh", f"[ccdocs] {MIRROR} is fresh")
        return Rc.OK
    if mode != "refresh" or len(rest) != 1:
        events.fail("ccdocs.bad_request", "usage: kb-setup ccdocs refresh|check", args=rest)
        return Rc.BAD_REQUEST
    try:
        out = refresh(repo_root, fetcher=fetcher)
    except InventoryUnavailableError as exc:
        events.warn("ccdocs.not_run", f"[ccdocs] COULD NOT ASK, nothing written: {exc}")
        return Rc.NOT_RUN
    events.say(
        "ccdocs.refreshed",
        f"[ccdocs] {len(out.added)} added, {len(out.changed)} changed, "
        f"{out.unchanged} unchanged, {len(out.kept)} kept, {len(out.missing)} missing",
        added=len(out.added),
        changed=len(out.changed),
    )
    for url in out.added:
        events.say("ccdocs.added", f"[ccdocs]   added {url}")
    for note in out.kept:
        events.warn("ccdocs.kept", f"[ccdocs]   kept previous copy: {note}")
    for note in out.missing:
        events.fail("ccdocs.missing", f"[ccdocs]   MISSING: {note}")
    return Rc.FINDINGS if out.missing else Rc.OK
