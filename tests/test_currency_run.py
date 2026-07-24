"""kb_setup.currency.run — the manual `stamp` CLI and the `daily` report.

Two behaviours are pinned here, each in BOTH directions:

* `stamp` without `--version` must read the ACTUAL binary, never fall back to the
  pin (stamping the pin is the false green G3 forbids); and
* `daily` must emit an explicit not-applicable line for a host-only tool, so
  "skipped here" is never indistinguishable from "nothing to report".
"""

from __future__ import annotations

from pathlib import Path

from kb_setup.currency import broad, config, run, sync


def _repo(tmp_path: Path, *, extra_toml: str = "") -> Path:
    (tmp_path / "mise.toml").write_text('[tools]\n"pipx:graphifyy" = "0.9.25"\n', encoding="utf-8")
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n' + extra_toml,
        encoding="utf-8",
    )
    artifact = tmp_path / "graphify-out" / "graph.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"nodes": []}', encoding="utf-8")
    return tmp_path


def _spec(root: Path) -> config.ToolSpec:
    return config.load(root)[0]


# ---------------------------------------------------------- stamp (finding 1) ----


def test_stamp_without_version_refuses_rather_than_stamping_the_pin(tmp_path, monkeypatch) -> None:
    """The false-green control: an unreadable binary + no --version must REFUSE.

    Before the fix this fell back to the pin (0.9.25) and wrote a green stamp
    nothing had verified. Now it must exit non-zero and write no stamp at all.
    """
    root = _repo(tmp_path)
    monkeypatch.setattr(sync, "observed_version", lambda _b: "")
    rc = run.stamp(root, tool="graphify", version="")
    assert rc == 2
    assert not (root / "graphify-out" / ".currency-stamp.json").exists()


def test_stamp_without_version_records_the_observed_binary_not_the_pin(
    tmp_path, monkeypatch
) -> None:
    """Control arm: with the binary readable it stamps what RAN, not the pin.

    The pin is 0.9.25 but the binary reports 0.9.23 (the stale-install drift this
    engine exists to expose) — the stamp must record 0.9.23, proving there is no
    pin fallback left.
    """
    root = _repo(tmp_path)
    monkeypatch.setattr(sync, "observed_version", lambda _b: "0.9.23")
    rc = run.stamp(root, tool="graphify", version="")
    assert rc == 0
    assert str(sync.read_stamp(root, _spec(root)).get("version")) == "0.9.23"


def test_stamp_with_explicit_version_uses_it(tmp_path, monkeypatch) -> None:
    """An explicit --version wins and does not consult the binary at all."""
    root = _repo(tmp_path)

    def _should_not_run(_b: str) -> str:  # pragma: no cover - must not be called
        raise AssertionError("observed_version must not run when --version is given")

    monkeypatch.setattr(sync, "observed_version", _should_not_run)
    rc = run.stamp(root, tool="graphify", version="0.9.99")
    assert rc == 0
    assert str(sync.read_stamp(root, _spec(root)).get("version")) == "0.9.99"


# ---------------------------------------------------------- daily (finding 3) ----


def test_daily_emits_a_not_applicable_line_for_a_host_only_tool(
    tmp_path, monkeypatch, capsys
) -> None:
    """A tool that does not apply here must be NAMED as not-checked, not dropped.

    `os = ["plan9"]` never matches a real platform, so the tool is host-only
    everywhere. `mise_outdated` is stubbed so the broad sweep needs no network.
    """
    root = _repo(tmp_path, extra_toml='os = ["plan9"]\n')
    monkeypatch.setattr(broad, "mise_outdated", lambda _r: ({}, ""))
    rc = run.daily(root)
    out = capsys.readouterr().out
    assert rc == 0
    assert "not checked on this host" in out
    assert "graphify" in out
    assert "plan9" in out


def test_daily_does_not_flag_an_applicable_tool_as_not_checked(
    tmp_path, monkeypatch, capsys
) -> None:
    """Control arm: a tool that DOES apply takes the normal path, no n/a line.

    `_run_one` is stubbed (it would otherwise hit the network) to return a record
    whose verdict has an upgrade, so the tool appears as a real deep-tracked line
    and NOT under 'not checked'.
    """
    from types import SimpleNamespace

    root = _repo(tmp_path)  # no `os` key ⇒ applies everywhere
    monkeypatch.setattr(broad, "mise_outdated", lambda _r: ({}, ""))
    record = SimpleNamespace(
        verdict=SimpleNamespace(
            has_upgrade=True,
            ambiguities=(),
            summary=lambda: "graphify 0.9.25 → 0.9.26",
        ),
        sync=SimpleNamespace(drifted=()),
    )
    monkeypatch.setattr(run, "_run_one", lambda _root, _spec: record)
    rc = run.daily(root)
    out = capsys.readouterr().out
    assert rc == 0
    assert "graphify 0.9.25 → 0.9.26" in out
    assert "not checked on this host" not in out
