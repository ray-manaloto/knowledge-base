# Copyright (c) 2026 Raymond Manaloto
"""Retention for the raw-API-body telemetry sink.

`OTEL_LOG_RAW_API_BODIES=file:.agent/telemetry/` is the only NATIVE file sink
Claude Code offers, and it is enabled here deliberately (Ray, 2026-08-17:
maximum capture for self-learning). Nothing in Claude Code rotates or bounds it,
so this module is the other half of that decision — written in the same change
rather than left as a note, because an unbounded writer with no reaper is a disk
outage on a timer.

WHY SIZE COMES FIRST AND AGE SECOND. The sink writes the ENTIRE conversation
history on EVERY request, so a single long round costs O(n²) bytes in one day.
An age-only rule cannot see that: everything it wrote is from today. The primary
bound is therefore a byte ceiling with oldest-first eviction, and the age cutoff
is the secondary sweep that clears quiet weeks.

WHY NOT `kb-reclaim`. That task is this repo's general disk reaper and it
explicitly REFUSES to act inside the repository (`reclaim._guard_path`: "refusing
to act inside the repository"). That refusal is a safety property worth keeping,
so this directory needs its own reaper rather than a hole punched in that one.
"""

from __future__ import annotations

import time
from pathlib import Path

import msgspec

from kb_setup import events

#: Where the sink writes. Must match `.claude/settings.json`'s
#: `OTEL_LOG_RAW_API_BODIES` — a divergence leaves the real directory unreaped
#: while this one reports a tidy zero, so `test_the_reaper_reads_the_configured_sink`
#: pins the two together rather than trusting them to agree.
TELEMETRY_DIR = Path(".agent") / "telemetry"

#: The byte ceiling for the whole directory. Ours, chosen: two gigabytes is well
#: above what any single round has produced and far below anything that threatens
#: a development machine, so it bounds the pathological case without deleting
#: data anyone is likely to still want.
KEEP_BYTES = 2 * 1024 * 1024 * 1024

#: The secondary sweep. Bodies older than this are gone regardless of the byte
#: ceiling, because their value is analysing a round you can still remember.
KEEP_DAYS = 14


class Pruned(msgspec.Struct, frozen=True):
    """What one retention pass removed and what it left."""

    removed: int
    removed_bytes: int
    kept: int
    kept_bytes: int


def prune(
    repo_root: Path,
    *,
    keep_bytes: int = KEEP_BYTES,
    keep_days: int = KEEP_DAYS,
    now: float | None = None,
) -> Pruned:
    """Enforce the age cutoff, then the byte ceiling, oldest first.

    `now` is injected so a test can drive the age branch without sleeping or
    back-dating a file — the shape `model_limits.resolve_all(sources=...)` already
    uses here.

    An absent directory is an empty result, not an error: telemetry is opt-in
    through an env var, and a machine that has never enabled it has nothing to
    reap. Failing there would make this hook noisy on exactly the setups it has
    no work to do on.
    """
    root = repo_root / TELEMETRY_DIR
    if not root.is_dir():
        return Pruned(0, 0, 0, 0)
    # `(mtime, path)` so the ordering is total: two files written in the same
    # millisecond would otherwise evict in filesystem-iteration order, which is
    # not stable and would make this function's result depend on the platform.
    entries = sorted(
        ((p.stat().st_mtime, p) for p in root.rglob("*") if p.is_file()),
        key=lambda item: (item[0], str(item[1])),
    )
    cutoff = (time.time() if now is None else now) - keep_days * 86_400
    removed = removed_bytes = 0
    survivors: list[tuple[float, Path, int]] = []
    for mtime, path in entries:
        size = path.stat().st_size
        if mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
            removed_bytes += size
        else:
            survivors.append((mtime, path, size))
    # Byte ceiling second, over what the age sweep left. Oldest first, which is
    # the only eviction order that keeps the retained window contiguous — dropping
    # the LARGEST would leave holes in the middle of a round's history and make
    # the surviving set useless for the analysis it exists for.
    total = sum(size for _, _, size in survivors)
    kept: list[int] = []
    for _, path, size in survivors:
        if total > keep_bytes:
            path.unlink(missing_ok=True)
            removed += 1
            removed_bytes += size
            total -= size
        else:
            kept.append(size)
    return Pruned(removed, removed_bytes, len(kept), sum(kept))


def main(repo_root: Path) -> int:
    """CLI boundary. Always 0: a retention pass is housekeeping, never a gate.

    Wired into SessionSTART. SessionEnd was the obvious home and is the wrong one:
    every SessionEnd hook shares ONE budget, raised to the highest per-hook
    timeout across settings and capped at 60 s TOTAL — so a third hook would have
    competed with the transcript audit for it, and a killed SessionEnd hook is
    silent. A hook that can fail a session over disk tidiness is a hook people
    disable; one that can silently starve another hook is worse.
    """
    result = prune(repo_root)
    mib = 1024 * 1024
    events.say(
        "telemetry.prune",
        f"telemetry: kept {result.kept} file(s) ({result.kept_bytes / mib:,.1f} MiB), "
        f"removed {result.removed} ({result.removed_bytes / mib:,.1f} MiB) — "
        f"ceiling {KEEP_BYTES / mib:,.0f} MiB, {KEEP_DAYS}d",
    )
    return 0
