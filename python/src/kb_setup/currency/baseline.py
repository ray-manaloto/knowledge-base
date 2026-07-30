"""What upstream last offered, cached so the OFFLINE check can see a stale pin.

WHY THIS EXISTS. Step 1 (`mise run kb-currency-check`, the SessionStart hook)
compares the INSTALL against the PIN. Both live on this machine, so the check is
offline and ~10ms — and structurally blind to the third version in the picture:
what upstream actually offers. Measured 2026-07-29: graphify was pinned at 0.9.26
with **0.9.30** released, four releases of install-safety and node-identity fixes
behind, and every session reported clean because install and pin agreed with each
other. The hook was answering a narrower question than the one it looked like it
was answering.

Fetching in the hook would fix the blindness and destroy the three properties
that make it runnable every session (offline, milliseconds, silent when clean),
so the full run records what it saw here and the hook reads it back.

NOTHING IS CONSUMED BY RECORDING. This file is the opposite case to
`docs.py`'s fingerprints, and the difference is worth being explicit about
because the two look alike. There, advancing the stored hash SILENCES the
finding, so a drifted page keeps its old baseline until a human has read it.
Here the stored value is what we are behind, so advancing it can only ever
*raise* the signal — and what clears it is the PIN moving, which is the sync
itself. So every full run refreshes this, and drift persists until the bump
actually lands.

The store is COMMITTED, like the docs fingerprints and for the same reason: a
baseline only one machine can read cannot tell anyone else their pin is stale,
and a fresh clone would start from "unknown" while looking green.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kb_setup.currency.upstream import Version

#: Where the cache lives, beside the tool-currency run log.
BASELINE_FILE = Path("docs") / "currency" / "upstream-baseline.json"

#: How old an observation may be before the offline check says so. A cache nobody
#: has refreshed is not evidence that nothing has been released — the same
#: absence-of-evidence rule the rest of this engine follows. Matches
#: `docs.STALE_AFTER_DAYS`: one number for "how long a committed observation
#: stays credible" rather than two that can drift apart.
STALE_AFTER_DAYS = 30


@dataclass(frozen=True)
class BaselineFinding:
    """One tool's offline verdict against the cached upstream version."""

    tool: str
    check: str
    detail: str


def load(repo_root: Path) -> dict[str, object]:
    """The committed cache, or an empty mapping when it does not exist yet.

    Typed `dict[str, object]`, which is what it actually is: the values come
    straight from `json.loads` and are whatever the file held. The old
    `dict[str, dict[str, str]]` was a claim this function never checked, and
    `behind()` trusted it and crashed on `{"graphify": "oops"}`. A type that
    over-promises is how the callers stopped validating.
    """
    path = repo_root / BASELINE_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save(repo_root: Path, store: Mapping[str, object]) -> Path:
    """Write the cache back, sorted so a diff shows content and not reordering."""
    path = repo_root / BASELINE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def record(
    store: Mapping[str, object],
    tool: str,
    latest: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return `store` with `tool`'s observation refreshed.

    An empty `latest` is NOT recorded. A tool with no upstream channel (ffmpeg is
    presence-tracked) and a lookup that failed both arrive here as "", and writing
    that would turn an unreachable upstream into a cached claim that upstream
    offers nothing — the false-green this engine refuses everywhere else.
    """
    if not latest:
        return dict(store)
    updated: dict[str, object] = dict(store)
    updated[tool] = {
        "latest": latest,
        "observed_at": (now or datetime.now(UTC)).isoformat(),
    }
    return updated


def _stale(observed_at: str, now: datetime) -> bool:
    try:
        seen = datetime.fromisoformat(observed_at)
    except ValueError:
        return True
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return now - seen > timedelta(days=STALE_AFTER_DAYS)


def behind(
    tool: str,
    pinned: str,
    store: Mapping[str, object],
    *,
    now: datetime | None = None,
) -> BaselineFinding | None:
    """OFFLINE: is `pinned` behind the last upstream version we saw?

    Three outcomes, kept apart on the same principle as DRIFT / SKIP / OK:

    * no entry at all — say so. A tool nobody has ever run the full loop for is
      unchecked, not current, and silence would make the two identical.
    * an entry older than `STALE_AFTER_DAYS` — report the staleness even if the
      versions agree, because agreement with a months-old observation is not
      evidence of being current.
    * pinned genuinely behind — the finding this module exists for.
    * an entry we cannot READ or cannot COMPARE — unchecked, same as no entry.

    Returns None when the pin matches (or leads) a fresh observation.

    Every failure path yields a FINDING, never an exception. A crash is not a
    verdict: this runs inside the SessionStart hook, where an `AttributeError`
    from a hand-edited or half-written cache would surface as a broken session
    rather than as "could not check". Found by the cold lane — `load` only
    guarded JSON *syntax*, so `{"graphify": "oops"}` parsed fine and then blew up
    on `.get`.
    """
    moment = now or datetime.now(UTC)
    entry = store.get(tool)
    if entry is None or (isinstance(entry, dict) and not entry.get("latest")):
        return BaselineFinding(
            tool,
            "upstream-cache",
            "no upstream version has ever been recorded — run `mise run kb-currency` "
            "so the offline check can tell whether this pin is behind",
        )
    # MALFORMED is its own answer, not folded into "never recorded". Both block the
    # comparison, but one says nobody has run the loop and the other says the cache
    # is corrupt — and a hand-edited or half-written file deserves to be named as
    # such rather than reported as a missing run.
    latest = entry.get("latest") if isinstance(entry, dict) else None
    if not isinstance(latest, str):
        return BaselineFinding(
            tool,
            "upstream-cache",
            f"the recorded upstream entry is MALFORMED ({type(entry).__name__}) — "
            "delete it and re-run `mise run kb-currency`; until then whether this "
            "pin is behind is UNKNOWN",
        )
    raw_observed = entry.get("observed_at") if isinstance(entry, dict) else None
    observed = raw_observed if isinstance(raw_observed, str) else ""
    stale = _stale(observed, moment)
    seen = observed[:10] or "an unknown date"
    cur, new = Version.parse(pinned), Version.parse(latest)
    if cur is None or new is None:
        # NOT a string `!=` fallback. Two strings being different says nothing
        # about which is NEWER, so the old fallback reported "pinned at 0.9.26 but
        # upstream had nightly" — a direction it had no way to know, in the words
        # of a definite finding. Unorderable is unchecked. (Cold lane.)
        return BaselineFinding(
            tool,
            "upstream-cache",
            f"cannot compare pin {pinned!r} with the recorded upstream {latest!r} — "
            "one of them is not a numeric version, so whether this pin is behind is "
            "UNKNOWN rather than fine",
        )
    if new > cur:
        return BaselineFinding(
            tool,
            "upstream-version",
            f"pinned at {pinned} but upstream had {latest} as of {seen} — review the "
            "releases between them via the tool-currency skill",
        )
    if stale:
        return BaselineFinding(
            tool,
            "upstream-cache",
            f"last upstream check was {seen} (over {STALE_AFTER_DAYS} days ago), so "
            f"'{pinned} is current' rests on a stale observation — run "
            "`mise run kb-currency`",
        )
    return None
