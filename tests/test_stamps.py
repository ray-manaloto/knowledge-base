# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.stamps — the shared best-effort currency-stamp refresh.

Extracted from `artifacts._restamp` (#179) so `kb-artifacts` and `kb-label`
share one implementation rather than two copies of the same four-exception-type
best-effort block — a duplicated block is precisely the kind of pair that
drifts, one getting a fix the other does not.
"""

from __future__ import annotations

import json
from pathlib import Path

from kb_setup import stamps
from kb_setup.currency import config, sync


def test_refresh_survives_a_malformed_currency_config(tmp_path: Path, capsys) -> None:
    """A broken currency.toml must not turn a successful caller into a failure.

    `config.load()` raises TypeError (not ValueError) when `[tool]` is not a
    table; `refresh_after_regen` is best-effort and must swallow it with a
    warning rather than raise.
    """
    (tmp_path / "currency.toml").write_text('tool = "not a table"\n', encoding="utf-8")
    # Must not raise — the guarantee refresh_after_regen documents.
    stamps.refresh_after_regen(tmp_path, tag="kb-label")
    assert "could not refresh the currency stamp" in capsys.readouterr().out


# --- the WARNING line's tag and cause survive too ----------------------------
#
# A mutant that hardcodes `print("[kb-artifacts] WARNING: could not refresh
# the currency stamp")` — dropping both `{tag}` and `{e}` — still satisfies the
# fixed-phrase substring check above, on EITHER caller. This is the failure
# path, hit while someone is already debugging, so it is the one place the
# message matters most: the tag says which command to blame
# (`_labelled`'s docstring: "`[kb-artifacts]` after a `kb-label` run would
# send them looking at the wrong task"), and `{e}` says WHY. Twin tests, one
# per tag, so neither can be hardcoded and still pass both.


def test_warning_path_carries_the_tag_and_the_cause_for_kb_label(tmp_path: Path, capsys) -> None:
    (tmp_path / "currency.toml").write_text('tool = "not a table"\n', encoding="utf-8")
    stamps.refresh_after_regen(tmp_path, tag="kb-label")
    out = capsys.readouterr().out
    assert "[kb-label]" in out
    assert "[kb-artifacts]" not in out
    # config.load()'s own TypeError text — proves `{e}` reached the message.
    assert "expected a [tool.<name>] table" in out


def test_warning_path_carries_the_tag_and_the_cause_for_kb_artifacts(
    tmp_path: Path, capsys
) -> None:
    """CONTROL ARM: same shape, the other tag — proves neither is hardcoded."""
    (tmp_path / "currency.toml").write_text('tool = "not a table"\n', encoding="utf-8")
    stamps.refresh_after_regen(tmp_path, tag="kb-artifacts")
    out = capsys.readouterr().out
    assert "[kb-artifacts]" in out
    assert "[kb-label]" not in out
    assert "expected a [tool.<name>] table" in out


def test_refresh_is_a_noop_without_a_config(tmp_path: Path) -> None:
    """Control arm: a repo with no currency.toml re-stamps nothing, cleanly."""
    stamps.refresh_after_regen(tmp_path, tag="kb-label")


# --- the tag really does reach the output ------------------------------------


def _repo_with_stamp(tmp_path: Path) -> Path:
    """A minimal repo with a currency.toml + an existing stamp to refresh.

    Mirrors `test_currency_sync.py`'s `_repo` fixture shape: a declared
    artifact must exist on disk before a stamp can fingerprint it.
    """
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    artifact = tmp_path / "graphify-out" / "graph.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    spec = config.load(tmp_path)[0]
    sync.write_stamp(tmp_path, spec, version="0.9.32")
    return tmp_path


def test_tag_reaches_the_printed_message_for_kb_label(tmp_path: Path, capsys) -> None:
    """A shared helper whose tag is ignored would blame the wrong task for every message."""
    repo = _repo_with_stamp(tmp_path)
    stamps.refresh_after_regen(repo, tag="kb-label")
    out = capsys.readouterr().out
    assert "[kb-label]" in out
    assert "[kb-artifacts]" not in out


def test_tag_reaches_the_printed_message_for_kb_artifacts(tmp_path: Path, capsys) -> None:
    repo = _repo_with_stamp(tmp_path)
    stamps.refresh_after_regen(repo, tag="kb-artifacts")
    out = capsys.readouterr().out
    assert "[kb-artifacts]" in out
    assert "[kb-label]" not in out


def test_refresh_actually_updates_the_artifact_fingerprint(tmp_path: Path) -> None:
    """The stamp's fingerprint for graph.json must track the file's CURRENT bytes."""
    repo = _repo_with_stamp(tmp_path)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    # Mutate the artifact after the stamp was written — the caller's whole
    # scenario: graph.json changed underneath an existing stamp.
    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps({"nodes": [{"id": "a"}]}), encoding="utf-8"
    )

    stamps.refresh_after_regen(repo, tag="kb-label")

    after = sync.read_stamp(repo, spec)
    live_fp = sync.artifact_fingerprint(repo / "graphify-out" / "graph.json")
    before_fps = sync.stamped_fingerprints(before)
    after_fps = sync.stamped_fingerprints(after)
    assert after_fps["graphify-out/graph.json"] == live_fp
    assert before_fps["graphify-out/graph.json"] != after_fps["graphify-out/graph.json"]
    # version/source_ref are carried forward, not re-derived by a restamp.
    assert after["version"] == before["version"]
