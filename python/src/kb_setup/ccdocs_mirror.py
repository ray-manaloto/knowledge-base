# Copyright (c) 2026 Raymond Manaloto
"""Claude Code compatibility entry point for the multi-site docs mirror.

The shared engine refreshes native markdown, inventories webclaw discovery,
guards fallback redirects and retires persistently absent pages. Existing
`kb-setup ccdocs refresh|check`, flat filenames, provenance rows and [ccdocs]
SessionStart output remain bound to the Claude Code site (#829/#837/#847).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from kb_setup import docs_mirror, events
from kb_setup.docs_mirror import (
    FETCH_TSV,
    STALE_AFTER_DAYS,
    STAMP,
    Fetcher,
    InventoryUnavailableError,
    MirrorUnreadableError,
    Outcome,
    Response,
    Row,
    fetch,
    read_rows,
)
from kb_setup.result import Rc

__all__ = [
    "FETCH_TSV",
    "INVENTORIES",
    "MIRROR",
    "PREFIX",
    "STALE_AFTER_DAYS",
    "STAMP",
    "Fetcher",
    "InventoryUnavailableError",
    "MirrorUnreadableError",
    "Outcome",
    "Rc",
    "Response",
    "Row",
    "discover",
    "fetch",
    "inventory_urls",
    "main",
    "page_name",
    "read_rows",
    "refresh",
    "report_staleness",
    "staleness",
]

_SITE = docs_mirror.SITES["claude-code"]
MIRROR = _SITE.mirror
PREFIX = _SITE.prefix
INVENTORIES = _SITE.inventories


def page_name(url: str) -> str:
    """Keep the historical Claude Code flat filename scheme."""
    return docs_mirror.page_name(_SITE, url)


def inventory_urls(text: str) -> set[str]:
    """Extract canonical Claude Code page URLs from an inventory."""
    return docs_mirror.inventory_urls(_SITE, text)


def discover(fetcher: Fetcher, known: set[str]) -> set[str]:
    """Keep the historical inventory-plus-known page set interface."""
    return docs_mirror.discover(_SITE, fetcher) | known


def refresh(
    repo_root: Path, *, fetcher: Fetcher | None = None, now: datetime | None = None
) -> Outcome:
    """Refresh the Claude Code mirror through call-time engine defaults."""
    return docs_mirror.refresh(repo_root, _SITE, fetcher=fetcher, now=now)


def staleness(repo_root: Path, *, now: datetime | None = None) -> str:
    """Report only the Claude Code mirror's offline freshness."""
    return docs_mirror.staleness(repo_root, _SITE, now=now)


def report_staleness(repo_root: Path) -> None:
    """Preserve the historical Claude Code SessionStart output."""
    docs_mirror.report_staleness(repo_root, sites=(_SITE,), include_codex=False)


def main(
    repo_root: Path, args: Sequence[str] | None = None, *, fetcher: Fetcher | None = None
) -> int:
    """Keep kb-setup ccdocs refresh|check and its injectable native fetcher."""
    rest = list(args or [])
    if rest == ["refresh"]:
        return docs_mirror.main(repo_root, ["refresh", _SITE.key], fetcher=fetcher)
    if rest == ["check"]:
        if line := staleness(repo_root):
            events.warn("ccdocs.stale", f"[ccdocs] {line}")
            return Rc.FINDINGS
        events.say("ccdocs.fresh", f"[ccdocs] {MIRROR} is fresh")
        return Rc.OK
    events.fail("ccdocs.bad_request", "usage: kb-setup ccdocs refresh|check", args=rest)
    return Rc.BAD_REQUEST
