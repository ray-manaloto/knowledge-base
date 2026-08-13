# Copyright (c) 2026 Raymond Manaloto
"""Controls for the provider-neutral large artifact downloader."""

from __future__ import annotations

import json
import shutil
import signal
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from kb_setup import artifact_download, cli

if TYPE_CHECKING:
    from pathlib import Path


class _Provider:
    name = "fake"

    def __init__(self, plan: artifact_download.DownloadPlan) -> None:
        self.plan_value = plan
        self.download_calls = 0

    def plan(
        self,
        source: str,
        revision: str,
        destination: Path,
        includes: tuple[str, ...],
    ) -> artifact_download.DownloadPlan:
        del source, revision, destination, includes
        return self.plan_value

    def download(
        self,
        plan: artifact_download.DownloadPlan,
        destination: Path,
        includes: tuple[str, ...],
        max_workers: int,
    ) -> Path:
        del includes, max_workers
        self.download_calls += 1
        for item in plan.files:
            path = destination / item.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x" * item.size)
        return destination

    def versions(self) -> dict[str, str]:
        return {"fake": "1.0"}


class _WrongSizeProvider(_Provider):
    def download(
        self,
        plan: artifact_download.DownloadPlan,
        destination: Path,
        includes: tuple[str, ...],
        max_workers: int,
    ) -> Path:
        del plan, includes, max_workers
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "weights.bin").write_bytes(b"x")
        return destination


def _plan(size: int = 4) -> artifact_download.DownloadPlan:
    revision = "a" * 40
    files = (artifact_download.ArtifactFile("weights.bin", size, None),)
    return artifact_download.DownloadPlan(
        "fake", "owner/model", revision, revision, files, size, 0, size
    )


def test_rejects_floating_revision_before_provider_call(tmp_path: Path) -> None:
    provider = _Provider(_plan())
    with pytest.raises(ValueError, match="immutable"):
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="fake",
                source="owner/model",
                revision="main",
                destination=tmp_path / "model",
                headroom_gib=0,
                max_workers=1,
            ),
            provider=provider,
        )
    assert provider.download_calls == 0


def test_rejects_token_bearing_source_before_receipt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository identifier"):
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="hf-xet",
                source="https://token@huggingface.co/owner/model",
                revision="a" * 40,
                destination=tmp_path / "model",
            )
        )


def test_dry_run_writes_plan_without_downloading(tmp_path: Path) -> None:
    provider = _Provider(_plan())
    destination = tmp_path / "model"
    receipt = tmp_path / "receipt.json"

    assert (
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="fake",
                source="owner/model",
                revision="a" * 40,
                destination=destination,
                includes=("*.bin",),
                headroom_gib=0,
                max_workers=2,
                receipt=receipt,
                dry_run=True,
            ),
            provider=provider,
        )
        == 0
    )

    payload = json.loads(receipt.read_text())
    assert payload["status"] == "planned"
    assert payload["resolved_revision"] == "a" * 40
    assert provider.download_calls == 0


def test_disk_preflight_uses_nearest_existing_target_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _Provider(_plan())
    inspected: list[Path] = []

    def disk_usage(path: Path) -> shutil._ntuple_diskusage:
        inspected.append(path)
        return shutil._ntuple_diskusage(total=100, used=0, free=100)

    monkeypatch.setattr(artifact_download.shutil, "disk_usage", disk_usage)
    destination = tmp_path / "nested" / "missing" / "model"
    assert (
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="fake",
                source="owner/model",
                revision="a" * 40,
                destination=destination,
                headroom_gib=0,
                max_workers=1,
                dry_run=True,
            ),
            provider=provider,
        )
        == 0
    )
    assert inspected == [tmp_path]


def test_insufficient_disk_fails_before_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _Provider(_plan())
    monkeypatch.setattr(
        artifact_download.shutil,
        "disk_usage",
        lambda _path: shutil._ntuple_diskusage(total=1, used=1, free=0),
    )

    with pytest.raises(OSError, match="insufficient disk"):
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="fake",
                source="owner/model",
                revision="a" * 40,
                destination=tmp_path / "model",
                headroom_gib=0,
                max_workers=1,
            ),
            provider=provider,
        )
    assert provider.download_calls == 0


def test_success_verifies_files_and_writes_complete_receipt(tmp_path: Path) -> None:
    provider = _Provider(_plan())
    destination = tmp_path / "model"

    assert (
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="fake",
                source="owner/model",
                revision="a" * 40,
                destination=destination,
                headroom_gib=0,
                max_workers=1,
            ),
            provider=provider,
        )
        == 0
    )

    payload = json.loads((destination / ".artifact-download.json").read_text())
    assert payload["status"] == "complete"
    assert payload["integrity"] == "size+immutable-provider-metadata"
    assert payload["process"]["pid"] > 0
    assert payload["process"]["start_token"]
    assert payload["process"]["command_sha256"]
    assert provider.download_calls == 1


def test_wrong_size_is_failed_not_complete(tmp_path: Path) -> None:
    provider = _WrongSizeProvider(
        replace(_plan(), files=(artifact_download.ArtifactFile("weights.bin", 4, None),))
    )
    destination = tmp_path / "model"
    with pytest.raises(RuntimeError, match=r"size:weights\.bin"):
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="fake",
                source="owner/model",
                revision="a" * 40,
                destination=destination,
                headroom_gib=0,
                max_workers=1,
            ),
            provider=provider,
        )
    assert json.loads((destination / ".artifact-download.json").read_text())["status"] == "failed"


def test_unsafe_provider_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        artifact_download._safe_relative("../secret")


def test_public_cli_dispatch_reaches_artifact_downloader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoked: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        artifact_download,
        "main",
        lambda _root, args: invoked.append(args) or 0,
    )

    assert cli._run(["artifact-download", "--dry-run"]) == 0
    assert invoked == [["--dry-run"]]


def test_cli_defaults_to_plan_and_requires_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[artifact_download.DownloadOptions] = []
    monkeypatch.setattr(
        artifact_download,
        "download",
        lambda options: seen.append(options) or 0,
    )
    args = [
        "--source",
        "gpt2",
        "--revision",
        "a" * 40,
        "--destination",
        str(tmp_path / "model"),
    ]

    assert artifact_download.main(tmp_path, args) == 0
    assert seen[-1].dry_run is True
    assert artifact_download.main(tmp_path, [*args, "--apply"]) == 0
    assert seen[-1].dry_run is False


def _control_receipt(tmp_path: Path, *, status: str = "downloading") -> Path:
    receipt = tmp_path / "model-download.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "artifact-download-v1",
                "status": status,
                "process": {
                    "pid": 4321,
                    "pgid": 4000,
                    "start_token": "Wed Aug 12 05:22:31 2026",
                    "command_sha256": "abc123",
                    "group_leader_start_token": "Wed Aug 12 05:22:30 2026",
                    "group_leader_command_sha256": "leader123",
                    "tmux_pane": "%42",
                },
            }
        ),
        encoding="utf-8",
    )
    return receipt


def _snapshot(
    *, pid: int = 4321, pgid: int = 4000, state: str
) -> artifact_download.ProcessSnapshot:
    return artifact_download.ProcessSnapshot(
        pid=pid,
        pgid=pgid,
        start_token=("Wed Aug 12 05:22:30 2026" if pid == pgid else "Wed Aug 12 05:22:31 2026"),
        command_sha256="leader123" if pid == pgid else "abc123",
        state=state,
    )


def _ignore_process_wait(_pid: int, *, stopped: bool) -> None:
    del stopped


def test_pause_uses_sigstop_and_writes_durable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _control_receipt(tmp_path)
    signals: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(
        artifact_download,
        "_process_snapshot",
        lambda pid: _snapshot(pid=pid, state="S+"),
    )
    monkeypatch.setattr(artifact_download, "_tmux_pane_pgid", lambda _pane: 4000)
    monkeypatch.setattr(artifact_download, "_process_is_stopped", lambda _pid: False)
    monkeypatch.setattr(artifact_download, "_wait_for_process_state", _ignore_process_wait)
    monkeypatch.setattr(
        artifact_download.os,
        "kill",
        lambda pid, sent: signals.append((pid, sent)),
    )

    result = artifact_download.control(receipt, "pause")

    assert signals == [(4321, signal.SIGSTOP)]
    assert result["status"] == "paused"
    assert result["pause_method"] == "posix-sigstop-process"
    assert json.loads(receipt.read_text())["status"] == "paused"


def test_resume_writes_downloading_before_sigcont(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _control_receipt(tmp_path, status="paused")
    observed_statuses: list[str] = []
    monkeypatch.setattr(
        artifact_download,
        "_process_snapshot",
        lambda pid: _snapshot(pid=pid, state="T+"),
    )
    monkeypatch.setattr(artifact_download, "_tmux_pane_pgid", lambda _pane: 4000)
    monkeypatch.setattr(artifact_download, "_process_is_stopped", lambda _pid: True)

    def send(_pgid: int, sent: signal.Signals) -> None:
        assert sent == signal.SIGCONT
        observed_statuses.append(json.loads(receipt.read_text())["status"])

    monkeypatch.setattr(artifact_download.os, "kill", send)
    monkeypatch.setattr(artifact_download, "_wait_for_process_state", _ignore_process_wait)

    result = artifact_download.control(receipt, "resume")

    assert observed_statuses == ["downloading"]
    assert result["status"] == "downloading"
    assert result["pause_method"] == "posix-sigstop-process"


def test_control_refuses_reused_pid_before_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _control_receipt(tmp_path)
    monkeypatch.setattr(
        artifact_download,
        "_process_snapshot",
        lambda pid: replace(_snapshot(pid=pid, state="S+"), command_sha256="different"),
    )
    monkeypatch.setattr(artifact_download, "_tmux_pane_pgid", lambda _pane: 4000)
    sent: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(artifact_download.os, "kill", lambda *args: sent.append(args))

    with pytest.raises(RuntimeError, match="process identity"):
        artifact_download.control(receipt, "pause")

    assert sent == []


def test_control_status_reports_actual_stopped_state_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _control_receipt(tmp_path, status="paused")
    before = receipt.read_bytes()
    monkeypatch.setattr(
        artifact_download,
        "_process_snapshot",
        lambda pid: _snapshot(pid=pid, state="T+"),
    )
    monkeypatch.setattr(artifact_download, "_tmux_pane_pgid", lambda _pane: 4000)
    monkeypatch.setattr(artifact_download, "_process_is_stopped", lambda _pid: True)

    result = artifact_download.control(receipt, "status")

    assert result["process_state"] == "stopped"
    assert receipt.read_bytes() == before


@pytest.mark.parametrize(
    ("action", "status", "stopped"),
    [("pause", "paused", "stopped"), ("resume", "downloading", "running")],
)
def test_control_is_idempotent_when_process_already_has_requested_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    status: str,
    stopped: str,
) -> None:
    is_stopped = stopped == "stopped"
    receipt = _control_receipt(tmp_path, status=status)
    before = receipt.read_bytes()
    monkeypatch.setattr(
        artifact_download,
        "_process_snapshot",
        lambda pid: _snapshot(pid=pid, state="T+" if is_stopped else "S+"),
    )
    monkeypatch.setattr(artifact_download, "_tmux_pane_pgid", lambda _pane: 4000)
    monkeypatch.setattr(artifact_download, "_process_is_stopped", lambda _pid: is_stopped)
    sent: list[tuple[object, ...]] = []
    monkeypatch.setattr(artifact_download.os, "kill", lambda *args: sent.append(args))

    result = artifact_download.control(receipt, action)

    assert result["status"] == status
    assert receipt.read_bytes() == before
    assert sent == []


def test_public_cli_dispatch_reaches_artifact_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoked: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        artifact_download,
        "control_main",
        lambda _root, args: invoked.append(args) or 0,
    )

    assert cli._run(["artifact-download-control", "status", "--receipt", "receipt.json"]) == 0
    assert invoked == [["status", "--receipt", "receipt.json"]]


def test_control_summary_reads_latest_carriage_return_progress(tmp_path: Path) -> None:
    receipt = tmp_path / "model-download.json"
    log = tmp_path / "colibri-canary.log"
    log.write_text(
        "Downloading bytes: 1.00GB, 5.0MB/s\rDownloading bytes: 1.01GB, 5.1MB/s\r",
        encoding="utf-8",
    )

    summary = artifact_download._control_summary(
        {
            "status": "downloading",
            "process_state": "running",
            "process": {"pid": 4321, "pgid": 4000},
        },
        receipt,
        log,
    )

    assert summary["last_progress"] == "Downloading bytes: 1.01GB, 5.1MB/s"
    assert summary["log"] == str(log)
