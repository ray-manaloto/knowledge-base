"""Detect when a tracked DOCUMENTATION page changes, not just a version.

WHY A VERSION PIN IS NOT ENOUGH. A tool's behaviour can change without its
version moving in a way you would notice, and — for a feature documented rather
than installed — the docs page IS the interface. `/goal` is the case that forced
this: its semantics live entirely at `code.claude.com/docs/en/goal.md`, and
Anthropic can revise that page any day without a Claude Code release that looks
relevant. A skill built on those semantics goes quietly stale, and nothing in a
version-only currency check would ever say so.

THE OFFLINE/NETWORK SPLIT IS LOAD-BEARING. `mise run kb-currency-check` is the
SessionStart path: offline, ~10ms, silent unless something drifted. Fetching two
URLs would destroy all three properties, so this module is deliberately in two
halves:

* :func:`staleness` — OFFLINE. Reads the committed fingerprint file and reports
  pages that have not been VERIFIED recently. It cannot detect a change; it
  detects that nobody has looked. That is a real and different finding.
* :func:`verify` — NETWORK. Fetches, hashes, compares, and is only ever called
  from the full `mise run kb-currency` run, which is already spending round
  trips.

Conflating them would either make every session pay for network I/O or let a
stale page look green forever. The engine's existing DRIFT / NOT-CHECKED / OK
distinction applies unchanged: an unreachable page reports NOT CHECKED, never
"unchanged".

The fingerprints are COMMITTED (`docs/currency/docs-fingerprints.json`) rather
than written under `graphify-out/`, which is gitignored. A baseline only one
machine can read cannot detect drift for anyone else, and a fresh clone would
silently start from "unknown" — the same false-green this engine refuses
everywhere else.
"""

from __future__ import annotations

import http.client
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from kb_setup.fetch import content_hash

#: A page fetcher: takes a URL, returns ``(body, error)`` with exactly one of the
#: two populated. Named so tests can substitute one without touching the network,
#: and typed concretely rather than as `object` — a bare `object` is not safe to
#: call, and typing it loosely to keep a test simple would push the looseness
#: into the production path.
Fetcher = Callable[[str], tuple[str, str]]

#: Where the committed baseline lives, beside the tool-currency run log.
FINGERPRINT_FILE = Path("docs") / "currency" / "docs-fingerprints.json"

#: How long a verification stays fresh before the offline check mentions it.
#: Long enough that a normal week of sessions stays silent, short enough that a
#: docs revision cannot sit unnoticed for a release cycle.
STALE_AFTER_DAYS = 30

_TIMEOUT_S = 20


@dataclass(frozen=True)
class DocsFinding:
    """One page's verdict. ``drifted`` and ``verified`` are independent.

    A page can be verified-and-drifted (we looked, it changed), verified-and-OK,
    or unverified (we could not look, or nobody has looked lately). The third is
    never rendered as the second.
    """

    url: str
    check: str
    detail: str
    drifted: bool = False
    verified: bool = False


def load(repo_root: Path) -> dict[str, dict[str, str]]:
    """The committed baseline, or an empty mapping when it does not exist yet."""
    path = repo_root / FINGERPRINT_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save(repo_root: Path, store: dict[str, dict[str, str]]) -> Path:
    """Write the baseline back, sorted so a diff shows content and not reordering."""
    path = repo_root / FINGERPRINT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fetch(url: str) -> tuple[str, str]:
    """One GET, as ``(body, error)``.

    HTTPSConnection over an explicit host rather than `urlopen(url)`, matching
    `currency.upstream`: the scheme is then a property of the class instead of an
    interpolated string, so a config value can never steer the request to
    `file:` or another scheme. Structural, not asserted.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return "", f"refusing non-https url: {url}"
    conn = http.client.HTTPSConnection(parts.hostname, timeout=_TIMEOUT_S)
    try:
        conn.request("GET", parts.path or "/")
        resp = conn.getresponse()
        if resp.status != HTTPStatus.OK:
            return "", f"HTTP {resp.status}"
        return resp.read().decode("utf-8", errors="replace"), ""
    except (OSError, TimeoutError) as e:
        return "", f"fetch failed: {e}"
    finally:
        conn.close()


def staleness(
    urls: tuple[str, ...],
    store: dict[str, dict[str, str]],
    *,
    now: datetime | None = None,
) -> list[DocsFinding]:
    """OFFLINE: which tracked pages nobody has verified lately.

    This deliberately cannot say a page changed — only that the baseline is old
    or absent. Reporting "not verified since <date>" is honest; reporting
    "unchanged" from a stale baseline would not be.
    """
    moment = now or datetime.now(UTC)
    findings: list[DocsFinding] = []
    for url in urls:
        entry = store.get(url)
        if not entry or not entry.get("checked_at"):
            findings.append(
                DocsFinding(url, "docs-baseline", "never verified — run `mise run kb-currency`")
            )
            continue
        try:
            checked = datetime.fromisoformat(entry["checked_at"])
        except ValueError:
            findings.append(DocsFinding(url, "docs-baseline", "unreadable checked_at timestamp"))
            continue
        age = (moment - checked).days
        if age >= STALE_AFTER_DAYS:
            findings.append(DocsFinding(url, "docs-staleness", f"not verified for {age} days"))
    return findings


def verify(
    urls: tuple[str, ...],
    store: dict[str, dict[str, str]],
    *,
    now: datetime | None = None,
    fetcher: Fetcher | None = None,
) -> tuple[list[DocsFinding], dict[str, dict[str, str]]]:
    """NETWORK: fetch each page, hash it, and compare against the baseline.

    Returns ``(findings, updated_store)``. The store is updated for every page
    that was successfully fetched — including a drifted one, because the point of
    recording is that the NEXT run compares against what we have now seen. A page
    that could not be fetched leaves its entry untouched, so an outage never
    overwrites a good baseline with nothing.
    """
    get: Fetcher = fetcher or _fetch
    moment = (now or datetime.now(UTC)).isoformat()
    updated = dict(store)
    findings: list[DocsFinding] = []
    for url in urls:
        body, err = get(url)
        if err:
            findings.append(DocsFinding(url, "docs-fetch", f"NOT CHECKED — {err}"))
            continue
        digest = content_hash(body)
        previous = store.get(url, {}).get("sha256", "")
        updated[url] = {"sha256": digest, "checked_at": moment}
        if not previous:
            findings.append(
                DocsFinding(url, "docs-baseline", "baseline recorded (first run)", verified=True)
            )
        elif previous != digest:
            findings.append(
                DocsFinding(
                    url,
                    "docs-drift",
                    "page CHANGED since the last check — re-read it, re-ingest via the "
                    "kb-curator skill, and update any skill built on it in the same change",
                    drifted=True,
                    verified=True,
                )
            )
        else:
            findings.append(DocsFinding(url, "docs-drift", "unchanged", verified=True))
    return findings, updated
