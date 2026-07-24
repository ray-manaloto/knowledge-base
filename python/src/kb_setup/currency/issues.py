"""Step 4 — have any tracked issues or local watch items moved since last run?

"Tracked" covers two kinds deliberately. Upstream GitHub issues are fetched and
diffed; **local** watch items are findings of ours with no upstream ticket (the
`label_communities` JSON-schema gap is the founding example) and are carried
forward verbatim so they cannot decay into folklore.

The previous observation lives in the committed report, not in a cache: the
whole point of step 6 is that this history is reviewable, and a diff against an
untracked `~/.cache` would be neither reviewable nor reproducible on a fresh
clone.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from kb_setup.currency.config import ToolSpec, WatchItem

_TIMEOUT_S = 20.0
STATE_FILE = "watch-state.json"


@dataclass(frozen=True)
class Observation:
    """What one watch item looked like on one run."""

    key: str
    state: str = ""
    updated_at: str = ""
    comments: int = 0
    title: str = ""
    error: str = ""

    def differs_from(self, other: Observation | None) -> bool:
        """True when the fields we watch changed. An unreadable run never counts.

        An errored observation is explicitly NOT a change: a rate-limited or
        offline run would otherwise manufacture movement on every tracked issue
        and drown the real signal.
        """
        if other is None or self.error or other.error:
            return False
        return (
            self.state != other.state
            or self.updated_at != other.updated_at
            or self.comments != other.comments
        )


def observe(item: WatchItem, *, default_repo: str) -> Observation:
    """Fetch the current state of one watch item.

    A `local` item has no upstream to read, so it observes as itself — present,
    unchanged, and still owed a decision.
    """
    if item.kind != "issue":
        return Observation(key=item.key, state="local", title=item.note)

    repo = item.repo or default_repo
    if not repo:
        return Observation(key=item.key, error="no repo configured for this issue")

    try:
        res = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/issues/{item.ref}",
                "--jq",
                "{state:.state,updated_at:.updated_at,comments:.comments,title:.title}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return Observation(key=item.key, error=f"gh api failed: {e}")

    if res.returncode != 0:
        return Observation(key=item.key, error=res.stderr.strip()[:200] or "gh api failed")
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError as e:
        return Observation(key=item.key, error=f"non-JSON response: {e}")

    return Observation(
        key=item.key,
        state=str(data.get("state") or ""),
        updated_at=str(data.get("updated_at") or ""),
        comments=int(data.get("comments", 0) or 0),
        title=str(data.get("title") or ""),
    )


def observe_all(spec: ToolSpec) -> tuple[Observation, ...]:
    """Observe every watch item declared for this tool."""
    return tuple(observe(item, default_repo=spec.github) for item in spec.watch)


def _state_path(report_dir: Path, tool: str) -> Path:
    return report_dir / f"{tool}-{STATE_FILE}"


def load_previous(report_dir: Path, tool: str) -> dict[str, Observation]:
    """Last run's observations, keyed by watch-item key ({} on first ever run)."""
    path = _state_path(report_dir, tool)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Observation] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = Observation(
                key=str(key),
                state=str(value.get("state") or ""),
                updated_at=str(value.get("updated_at") or ""),
                comments=int(value.get("comments", 0) or 0),
                title=str(value.get("title") or ""),
            )
    return out


def save_current(report_dir: Path, tool: str, observations: tuple[Observation, ...]) -> Path:
    """Persist this run's observations so the next run can diff against them.

    An errored observation does not overwrite its entry — but its PRIOR value is
    carried forward rather than dropped. Dropping it would silently erase the
    baseline: the next run would see no previous value, treat the item as
    first-ever-observed, and report no change even if the issue had moved. A
    transient rate-limit would therefore hide exactly one real change, which is
    the worst possible moment to be blind.

    Items no longer in the config are pruned, so a removed watch entry does not
    linger forever.
    """
    path = _state_path(report_dir, tool)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_previous(report_dir, tool)

    payload: dict[str, dict[str, object]] = {}
    for o in observations:
        source = o if not o.error else previous.get(o.key)
        if source is None:  # errored on its very first observation — nothing to keep
            continue
        payload[o.key] = {k: v for k, v in asdict(source).items() if k not in {"key", "error"}}

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def changes(
    observations: tuple[Observation, ...], previous: dict[str, Observation]
) -> tuple[Observation, ...]:
    """Watch items whose watched fields moved since the previous run."""
    return tuple(o for o in observations if o.differs_from(previous.get(o.key)))
