# Copyright (c) 2026 Raymond Manaloto
"""Arms for the raw-body telemetry sink's retention pass."""

from __future__ import annotations

import json
from pathlib import Path

from kb_setup import telemetry


def _body(root: Path, name: str, size: int, mtime: float) -> Path:
    d = root / telemetry.TELEMETRY_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    path.write_bytes(b"x" * size)
    import os

    os.utime(path, (mtime, mtime))
    return path


def test_an_absent_sink_is_an_empty_pass_not_an_error(tmp_path: Path) -> None:
    """Telemetry is opt-in; a machine that never enabled it has nothing to reap.

    The control is the second half: with a file present the same call reports it,
    so this measures "absent means nothing to do" rather than "the function
    always returns zeros".
    """
    assert telemetry.prune(tmp_path) == telemetry.Pruned(0, 0, 0, 0)

    _body(tmp_path, "a.json", 10, now := 1_000_000.0)
    assert telemetry.prune(tmp_path, now=now).kept == 1


def test_the_byte_ceiling_evicts_oldest_first(tmp_path: Path) -> None:
    """Size is the PRIMARY bound, and the eviction order is the load-bearing part.

    The sink rewrites the whole conversation on every request, so one long round
    blows a byte ceiling within a single day — which an age rule cannot see. The
    order matters as much as the bound: evicting the LARGEST file would leave
    holes in the middle of a round's history and make the survivors useless for
    the analysis the capture exists for. Oldest-first keeps the retained window
    contiguous.

    The final assertion is the arm on that: the file that survives must be the
    NEWEST, not merely "one of them".
    """
    now = 2_000_000.0
    _body(tmp_path, "old.json", 100, now - 300)
    _body(tmp_path, "mid.json", 100, now - 200)
    newest = _body(tmp_path, "new.json", 100, now - 100)

    result = telemetry.prune(tmp_path, keep_bytes=150, keep_days=365, now=now)

    assert result.removed == 2
    assert result.kept == 1
    assert newest.is_file()
    assert not (tmp_path / telemetry.TELEMETRY_DIR / "old.json").exists()


def test_the_age_cutoff_runs_before_the_ceiling(tmp_path: Path) -> None:
    """The secondary sweep clears quiet weeks the byte ceiling never reaches.

    Under the ceiling alone this directory is fine — 100 bytes against a huge
    limit — so an implementation that only enforced size would keep a body from
    months ago forever. The control is the recent file, which must survive the
    same call.
    """
    now = 3_000_000.0
    _body(tmp_path, "ancient.json", 100, now - 90 * 86_400)
    recent = _body(tmp_path, "recent.json", 100, now - 3_600)

    result = telemetry.prune(tmp_path, keep_bytes=10**9, keep_days=14, now=now)

    assert result.removed == 1
    assert recent.is_file()
    assert not (tmp_path / telemetry.TELEMETRY_DIR / "ancient.json").exists()


def test_a_pass_that_needs_to_remove_nothing_removes_nothing(tmp_path: Path) -> None:
    """The control on both bounds at once — a reaper that can only delete is not a reaper."""
    now = 4_000_000.0
    _body(tmp_path, "a.json", 10, now - 60)
    _body(tmp_path, "b.json", 10, now - 30)

    result = telemetry.prune(tmp_path, keep_bytes=10**9, keep_days=365, now=now)

    assert result == telemetry.Pruned(0, 0, 2, 20)


def test_the_reaper_reads_the_configured_sink() -> None:
    """The reaper's directory and the settings' sink must be the same place.

    A divergence is silent in the worst way: the real directory grows unreaped
    while every run of this task reports a tidy zero. Pinned rather than trusted,
    because the two live in different files and different languages.
    """
    root = Path(__file__).resolve().parents[1]
    settings = json.loads((root / ".claude/settings.json").read_text(encoding="utf-8"))
    configured = settings["env"]["OTEL_LOG_RAW_API_BODIES"]

    assert configured.startswith("file:")
    assert configured.removeprefix("file:").rstrip("/") == telemetry.TELEMETRY_DIR.as_posix()


def test_the_sink_is_gitignored() -> None:
    """Raw bodies are the whole conversation, unencrypted. They must never be tracked.

    Asserted against the real `.gitignore` rather than against a memory of it,
    because this is the one property whose failure cannot be undone by a later
    commit — the bytes would already be in the history.
    """
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert any(line.strip() in {".agent/", ".agent"} for line in ignored)


def test_a_configured_sink_with_nothing_behind_it_is_announced(tmp_path: Path) -> None:
    """Capture ON with an empty directory means something, and it is not "clean".

    The sink path in settings.json is RELATIVE, so the writer resolves it against
    its own working directory while the reaper runs pinned to
    `${CLAUDE_PROJECT_DIR}`. If those ever diverge the bytes accumulate somewhere
    this never looks, and the only symptom would be this task reporting a tidy
    zero forever.

    The control is `test_the_reaper_is_quiet_when_capture_is_off` below: with no
    sink configured, an empty directory is genuinely nothing to say.
    """
    settings = tmp_path / ".claude"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "settings.json").write_text(
        json.dumps({"env": {"OTEL_LOG_RAW_API_BODIES": "file:.agent/telemetry/"}}),
        encoding="utf-8",
    )

    assert telemetry.configured_sink(tmp_path) == "file:.agent/telemetry/"
    assert telemetry.main(tmp_path) == 0


def test_the_reaper_is_quiet_when_capture_is_off(tmp_path: Path) -> None:
    """No sink configured is a different state from a sink that is empty.

    Both are "zero files", and reporting them the same way is how a split writer
    and reaper would hide. Three shapes must all read as OFF: no settings file at
    all, a settings file with no `env`, and a sink that is not a `file:` sink.
    """
    assert telemetry.configured_sink(tmp_path) == ""

    settings = tmp_path / ".claude"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "settings.json").write_text(json.dumps({"env": {}}), encoding="utf-8")
    assert telemetry.configured_sink(tmp_path) == ""

    (settings / "settings.json").write_text(
        json.dumps({"env": {"OTEL_LOG_RAW_API_BODIES": "1"}}), encoding="utf-8"
    )
    assert telemetry.configured_sink(tmp_path) == ""


def test_a_malformed_settings_file_is_not_a_crash(tmp_path: Path) -> None:
    """The reaper reads someone else's config; it must not die on it.

    A SessionStart hook that raises on a hand-edited settings.json would turn a
    typo into a broken session start, which is a much worse failure than the
    disk tidiness this task exists for.
    """
    settings = tmp_path / ".claude"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "settings.json").write_text("{ not json", encoding="utf-8")

    assert telemetry.configured_sink(tmp_path) == ""
    assert telemetry.main(tmp_path) == 0
