# Copyright (c) 2026 Raymond Manaloto
"""Armed controls for provider-neutral immutable artifact receipts."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import msgspec
import pytest
from kb_setup import artifact_download, cli
from kb_setup.artifact_download import (
    ArtifactError,
    ArtifactFile,
    DownloadOptions,
    DownloadPlan,
)
from kb_setup.generated.fetch_receipt import FetchReceipt, Status

REVISION = "a" * 40
PAYLOAD = b"reviewed artifact bytes\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
LICENSE = b"reviewed license text\n"
LICENSE_DIGEST = hashlib.sha256(LICENSE).hexdigest()


class FakeProvider:
    """No-network provider with inspectable plan/download calls."""

    name = "fake"

    def __init__(self, plan: DownloadPlan | None = None, *, extra: bool = False) -> None:
        """Construct a deterministic plan and optional extra-file attack."""
        self.value = plan or DownloadPlan(
            self.name,
            "owner/repository",
            REVISION,
            "MIT",
            "LICENSE",
            (
                ArtifactFile("LICENSE", len(LICENSE), LICENSE_DIGEST),
                ArtifactFile("weights/model.bin", len(PAYLOAD), DIGEST),
            ),
        )
        self.extra = extra
        self.downloads = 0

    def plan(self, source: str, revision: str) -> DownloadPlan:
        """Return reviewed metadata without external access."""
        del source, revision
        return self.value

    def download(self, plan: DownloadPlan, destination: Path) -> None:
        """Materialize deterministic bytes beneath the supplied staging root."""
        del plan
        self.downloads += 1
        target = destination / "weights" / "model.bin"
        target.parent.mkdir(parents=True)
        (destination / "LICENSE").write_bytes(LICENSE)
        target.write_bytes(PAYLOAD)
        if self.extra:
            (destination / "unexpected.txt").write_text("not reviewed", encoding="utf-8")

    def version(self) -> str:
        """Return a bounded fake provider version."""
        return "fake-1.0"


def _options(tmp_path: Path, *, apply: bool = False) -> DownloadOptions:
    return DownloadOptions(
        "fake",
        "owner/repository",
        REVISION,
        tmp_path / "artifact",
        tmp_path / "receipt.json",
        1_000,
        apply,
        "artifacts/model",
    )


def _receipt(path: Path) -> FetchReceipt:
    return msgspec.json.decode(path.read_bytes(), type=FetchReceipt)


def test_plan_is_default_and_receipt_is_strict_and_path_private(tmp_path: Path) -> None:
    provider = FakeProvider()
    options = _options(tmp_path)

    assert artifact_download.download(options, provider=provider) == 0
    receipt = _receipt(options.receipt or Path())

    assert provider.downloads == 0
    assert receipt.status is Status.planned
    assert receipt.revision == REVISION
    assert receipt.license_id == "MIT"
    assert receipt.license_path == "LICENSE"
    assert {item.path: item.sha256 for item in receipt.files}["weights/model.bin"] == DIGEST
    assert str(tmp_path).encode() not in (options.receipt or Path()).read_bytes()


def test_apply_stages_then_replaces_corrupt_existing_tree(tmp_path: Path) -> None:
    options = _options(tmp_path, apply=True)
    options.destination.mkdir()
    (options.destination / "corrupt.bin").write_bytes(b"corrupt")

    assert artifact_download.download(options, provider=FakeProvider()) == 0

    assert (options.destination / "weights" / "model.bin").read_bytes() == PAYLOAD
    assert not (options.destination / "corrupt.bin").exists()
    assert _receipt(options.receipt or Path()).status is Status.complete
    assert not list(tmp_path.glob(".artifact.*"))


def test_apply_replaces_preexisting_regular_file_destination(tmp_path: Path) -> None:
    options = _options(tmp_path, apply=True)
    options.destination.write_bytes(b"corrupt regular file\n")

    assert artifact_download.download(options, provider=FakeProvider()) == 0

    assert options.destination.is_dir()
    assert (options.destination / "weights/model.bin").read_bytes() == PAYLOAD
    assert not (tmp_path / ".artifact.previous").exists()


def test_receipt_failure_restores_preexisting_regular_file_destination(
    tmp_path: Path, monkeypatch
) -> None:
    options = _options(tmp_path, apply=True)
    options.destination.write_bytes(b"prior regular file\n")
    real_atomic = artifact_download._atomic_receipt

    def fail_complete(path: Path, payload: dict[str, object]) -> None:
        if payload["status"] == "complete":
            raise OSError("simulated complete receipt failure")
        real_atomic(path, payload)

    monkeypatch.setattr(artifact_download, "_atomic_receipt", fail_complete)
    with pytest.raises(OSError, match="complete receipt"):
        artifact_download.download(options, provider=FakeProvider())

    assert options.destination.read_bytes() == b"prior regular file\n"
    assert not (tmp_path / ".artifact.previous").exists()


@pytest.mark.parametrize(
    ("source", "revision"),
    [
        ("owner/repository", "main"),
        ("token@owner/repository", REVISION),
        ("https://example.invalid/owner/repository", REVISION),
    ],
)
def test_floating_or_credential_bearing_identity_is_rejected_before_provider(
    tmp_path: Path, source: str, revision: str
) -> None:
    provider = FakeProvider()
    options = replace(_options(tmp_path), source=source, revision=revision)

    with pytest.raises(ArtifactError):
        artifact_download.download(options, provider=provider)

    assert provider.downloads == 0
    assert not (options.receipt or Path()).exists()


@pytest.mark.parametrize(
    "plan",
    [
        DownloadPlan(
            "other", "owner/repository", REVISION, "MIT", "a", (ArtifactFile("a", 1, "0" * 64),)
        ),
        DownloadPlan(
            "fake", "owner/repository", "b" * 40, "MIT", "a", (ArtifactFile("a", 1, "0" * 64),)
        ),
        DownloadPlan(
            "fake",
            "owner/repository",
            REVISION,
            "MIT",
            "../escape",
            (ArtifactFile("../escape", 1, "0" * 64),),
        ),
        DownloadPlan(
            "fake",
            "owner/repository",
            REVISION,
            "MIT",
            "b",
            (ArtifactFile("b", 1, "0" * 64), ArtifactFile("a", 1, "0" * 64)),
        ),
        DownloadPlan(
            "fake",
            "owner/repository",
            REVISION,
            "MIT",
            "a",
            (ArtifactFile("a", 1, "0" * 64), ArtifactFile("a", 1, "0" * 64)),
        ),
        DownloadPlan(
            "fake",
            "owner/repository",
            REVISION,
            "bad/license",
            "a",
            (ArtifactFile("a", 1, "0" * 64),),
        ),
        DownloadPlan(
            "fake",
            "owner/repository",
            REVISION,
            "MIT",
            "missing",
            (ArtifactFile("a", 1, "0" * 64),),
        ),
    ],
)
def test_untrusted_plan_identity_path_and_order_are_rejected(
    tmp_path: Path, plan: DownloadPlan
) -> None:
    with pytest.raises(ArtifactError):
        artifact_download.download(_options(tmp_path), provider=FakeProvider(plan))


def test_declared_byte_limit_is_checked_before_transfer(tmp_path: Path) -> None:
    options = replace(_options(tmp_path), max_bytes=len(PAYLOAD) - 1, apply=True)
    provider = FakeProvider()

    with pytest.raises(ArtifactError, match="byte limit"):
        artifact_download.download(options, provider=provider)

    assert provider.downloads == 0


@pytest.mark.parametrize("mutation", ["digest", "extra"])
def test_partial_or_unplanned_bytes_fail_closed(tmp_path: Path, mutation: str) -> None:
    provider = FakeProvider(extra=mutation == "extra")
    if mutation == "digest":
        provider.value = replace(
            provider.value,
            files=(
                ArtifactFile("LICENSE", len(LICENSE), LICENSE_DIGEST),
                ArtifactFile("weights/model.bin", len(PAYLOAD), "0" * 64),
            ),
        )
    options = _options(tmp_path, apply=True)

    with pytest.raises(ArtifactError):
        artifact_download.download(options, provider=provider)

    assert (
        _receipt((options.receipt or Path()).with_name("receipt.json.attempt")).status
        is Status.failed
    )
    assert not options.destination.exists()
    assert not list(tmp_path.glob(".artifact.download-*"))


def test_symlink_from_provider_is_rejected(tmp_path: Path) -> None:
    class SymlinkProvider(FakeProvider):
        def download(self, plan: DownloadPlan, destination: Path) -> None:
            """Inject an unsafe symbolic link instead of reviewed bytes."""
            del plan
            (destination / "weights").mkdir()
            (destination / "weights" / "model.bin").symlink_to(tmp_path / "outside")

    options = _options(tmp_path, apply=True)
    with pytest.raises(ArtifactError, match="symbolic link"):
        artifact_download.download(options, provider=SymlinkProvider())
    assert not options.destination.exists()


def test_archive_named_payload_is_never_extracted(tmp_path: Path) -> None:
    archive = b"not-an-archive\n"

    class ArchiveProvider(FakeProvider):
        def download(self, plan: DownloadPlan, destination: Path) -> None:
            """Write an archive-named opaque payload without extraction."""
            del plan
            (destination / "LICENSE").write_bytes(LICENSE)
            (destination / "payload.tar").write_bytes(archive)

    provider = ArchiveProvider(
        DownloadPlan(
            "fake",
            "owner/repository",
            REVISION,
            "MIT",
            "LICENSE",
            (
                ArtifactFile("LICENSE", len(LICENSE), LICENSE_DIGEST),
                ArtifactFile("payload.tar", len(archive), hashlib.sha256(archive).hexdigest()),
            ),
        )
    )
    options = _options(tmp_path, apply=True)
    assert artifact_download.download(options, provider=provider) == 0
    assert (options.destination / "payload.tar").read_bytes() == archive


def test_receipt_fsync_failure_preserves_previous_bytes(tmp_path: Path, monkeypatch) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(b"previous\n")

    def refuse_fsync(_descriptor: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", refuse_fsync)
    with pytest.raises(OSError, match="simulated"):
        artifact_download.download(_options(tmp_path), provider=FakeProvider())
    assert receipt.read_bytes() == b"previous\n"
    assert not list(tmp_path.glob(".receipt.json.*"))


def test_receipt_directory_fsync_failure_rolls_back_replacement(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(b"previous\n")
    real_fsync = os.fsync
    calls = 0

    def refuse_directory_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated directory fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", refuse_directory_fsync)
    with pytest.raises(OSError, match="directory"):
        artifact_download.download(_options(tmp_path), provider=FakeProvider())
    assert receipt.read_bytes() == b"previous\n"
    assert not list(tmp_path.glob(".receipt.json.*"))


def test_publish_fsync_failure_rolls_back_existing_destination(tmp_path: Path, monkeypatch) -> None:
    options = _options(tmp_path, apply=True)
    options.destination.mkdir()
    previous = options.destination / "previous.bin"
    previous.write_bytes(b"previous artifact\n")
    real_fsync = os.fsync
    calls = 0

    def fail_publish_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated publish fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_publish_fsync)
    with pytest.raises(OSError, match="publish"):
        artifact_download.download(options, provider=FakeProvider())
    assert previous.read_bytes() == b"previous artifact\n"
    assert not (options.destination / "weights/model.bin").exists()
    assert not (tmp_path / ".artifact.previous").exists()
    assert (
        _receipt((options.receipt or Path()).with_name("receipt.json.attempt")).status
        is Status.failed
    )


def test_provider_exception_is_redacted_and_preserves_completed_receipt(tmp_path: Path) -> None:
    class HostileProvider(FakeProvider):
        def download(self, plan: DownloadPlan, destination: Path) -> None:
            """Write a partial file and raise a secret-bearing provider error."""
            del plan
            (destination / "partial").write_text("partial", encoding="utf-8")
            raise RuntimeError("SECRET_BODY_CANARY")

    options = _options(tmp_path, apply=True)
    receipt = options.receipt or Path()
    receipt.write_bytes(b"previous completed receipt\n")

    with pytest.raises(ArtifactError) as failure:
        artifact_download.download(options, provider=HostileProvider())

    assert str(failure.value) == "provider adapter failed without retained provider output"
    assert "SECRET_BODY_CANARY" not in str(failure.value)
    assert receipt.read_bytes() == b"previous completed receipt\n"
    attempt = receipt.with_name("receipt.json.attempt")
    assert _receipt(attempt).status is Status.failed
    assert b"SECRET_BODY_CANARY" not in attempt.read_bytes()
    assert not list(tmp_path.glob(".artifact.download-*"))


@pytest.mark.parametrize("control_flow", [KeyboardInterrupt, SystemExit])
def test_control_flow_after_publish_rolls_back_before_reraise(
    tmp_path: Path, monkeypatch, control_flow: type[BaseException]
) -> None:
    options = _options(tmp_path, apply=True)
    options.destination.mkdir()
    prior = options.destination / "prior.bin"
    prior.write_bytes(b"prior artifact\n")
    real_atomic = artifact_download._atomic_receipt

    def interrupt_complete(path: Path, payload: dict[str, object]) -> None:
        if payload["status"] == "complete":
            raise control_flow()
        real_atomic(path, payload)

    monkeypatch.setattr(artifact_download, "_atomic_receipt", interrupt_complete)
    with pytest.raises(control_flow):
        artifact_download.download(options, provider=FakeProvider())

    assert prior.read_bytes() == b"prior artifact\n"
    assert not (options.destination / "weights/model.bin").exists()
    assert not (tmp_path / ".artifact.previous").exists()


def test_destination_identity_distinguishes_same_named_paths(tmp_path: Path) -> None:
    first = replace(_options(tmp_path), destination_identity="models/one/artifact")
    second = replace(_options(tmp_path), destination_identity="models/two/artifact")
    artifact_download.download(first, provider=FakeProvider())
    first_digest = _receipt(first.receipt or Path()).destination_sha256
    artifact_download.download(second, provider=FakeProvider())
    second_digest = _receipt(second.receipt or Path()).destination_sha256
    assert first_digest != second_digest


def test_final_receipt_failure_rolls_back_artifact_and_records_failed_attempt(
    tmp_path: Path, monkeypatch
) -> None:
    options = _options(tmp_path, apply=True)
    options.destination.mkdir()
    prior = options.destination / "prior.bin"
    prior.write_bytes(b"prior artifact\n")
    receipt = options.receipt or Path()
    receipt.write_bytes(b"prior complete receipt\n")
    real_atomic = artifact_download._atomic_receipt

    def fail_complete(path: Path, payload: dict[str, object]) -> None:
        if payload["status"] == "complete":
            raise OSError("simulated final receipt failure")
        real_atomic(path, payload)

    monkeypatch.setattr(artifact_download, "_atomic_receipt", fail_complete)
    with pytest.raises(OSError, match="final receipt"):
        artifact_download.download(options, provider=FakeProvider())

    assert prior.read_bytes() == b"prior artifact\n"
    assert not (options.destination / "weights/model.bin").exists()
    assert receipt.read_bytes() == b"prior complete receipt\n"
    attempt = receipt.with_name("receipt.json.attempt")
    assert _receipt(attempt).status is Status.failed
    assert not (tmp_path / ".artifact.previous").exists()


def test_failed_attempt_is_replaced_by_clean_retry(tmp_path: Path) -> None:
    options = _options(tmp_path, apply=True)
    attempt = (options.receipt or Path()).with_name("receipt.json.attempt")
    attempt.write_text('{"stale":true}\n', encoding="utf-8")
    assert artifact_download.download(options, provider=FakeProvider()) == 0
    assert not attempt.exists()
    assert _receipt(options.receipt or Path()).status is Status.complete


def test_public_cli_refuses_missing_provider_without_echoing_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_source = "owner-private/repository"
    rc = artifact_download.main(
        tmp_path,
        [
            "--provider",
            "missing",
            "--source",
            private_source,
            "--revision",
            REVISION,
            "--destination",
            str(tmp_path / "artifact"),
        ],
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert captured.err == "artifact download refused: provider adapter is unavailable\n"
    assert private_source not in captured.err


def test_top_level_cli_dispatches_to_bounded_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(
        [
            "artifact-download",
            "--provider",
            "missing",
            "--source",
            "owner/repository",
            "--revision",
            REVISION,
            "--destination",
            str(tmp_path / "artifact"),
        ]
    )
    assert rc == 2
    assert capsys.readouterr().err == (
        "artifact download refused: provider adapter is unavailable\n"
    )


@pytest.mark.parametrize("destination", ["../outside", "__absolute__", "link/artifact"])
def test_provider_cannot_escape_project_output_boundary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    destination: str,
) -> None:
    outside = tmp_path.parent / "outside-artifact"
    if destination == "__absolute__":
        destination = str(outside)
    if destination.startswith("link/"):
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    provider = FakeProvider()
    rc = artifact_download.main(
        tmp_path,
        [
            "--provider",
            "fake",
            "--source",
            "owner/repository",
            "--revision",
            REVISION,
            "--destination",
            destination,
        ],
        provider=provider,
    )
    assert rc == 2
    assert capsys.readouterr().err == (
        "artifact download refused: artifact output path must be project-local\n"
    )
    assert provider.downloads == 0
    assert not outside.exists()


@pytest.mark.parametrize("receipt_relative", ["weights/model.bin", "weights"])
def test_receipt_cannot_replace_a_reviewed_payload(tmp_path: Path, receipt_relative: str) -> None:
    options = replace(
        _options(tmp_path),
        receipt=tmp_path / "artifact" / receipt_relative,
    )
    with pytest.raises(ArtifactError, match="collides"):
        artifact_download.download(options, provider=FakeProvider())
    assert not options.destination.exists()


@pytest.mark.parametrize("relation", ["equal", "ancestor"])
def test_receipt_and_destination_must_be_disjoint(tmp_path: Path, relation: str) -> None:
    destination = tmp_path / "artifacts" / "model"
    receipt = destination if relation == "equal" else tmp_path / "artifacts"
    options = replace(_options(tmp_path), destination=destination, receipt=receipt)

    with pytest.raises(ArtifactError, match="artifact destination"):
        artifact_download.download(options, provider=FakeProvider())

    assert not destination.exists()
    assert not receipt.exists()


@pytest.mark.parametrize(
    ("field", "length"),
    [("provider", 65), ("provider_version", 129)],
)
def test_provider_identifiers_match_receipt_schema_bounds(
    tmp_path: Path, field: str, length: int
) -> None:
    class LongVersionProvider(FakeProvider):
        def version(self) -> str:
            """Return an identifier beyond the receipt schema bound."""
            return "a" * length

    provider = FakeProvider() if field == "provider" else LongVersionProvider()
    options = _options(tmp_path)
    if field == "provider":
        provider.name = "a" * length
        options = replace(options, provider=provider.name)

    with pytest.raises(ArtifactError, match="provider"):
        artifact_download.download(options, provider=provider)

    assert not (options.receipt or Path()).exists()


def test_provider_schema_boundary_lengths_are_accepted(tmp_path: Path) -> None:
    class BoundaryProvider(FakeProvider):
        name = "p" * 64

        def version(self) -> str:
            """Return the exact maximum schema length."""
            return "v" * 128

    provider = BoundaryProvider()
    provider.value = replace(provider.value, provider=provider.name)
    options = replace(_options(tmp_path), provider=provider.name)

    assert artifact_download.download(options, provider=provider) == 0
    receipt = _receipt(options.receipt or Path())
    assert len(receipt.provider) == 64
    assert len(receipt.provider_version) == 128


def test_receipt_json_has_canonical_order_and_no_unknown_fields(tmp_path: Path) -> None:
    options = _options(tmp_path)
    artifact_download.download(options, provider=FakeProvider())
    raw = (options.receipt or Path()).read_bytes()
    value = json.loads(raw)
    assert raw == (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(msgspec.ValidationError):
        msgspec.json.decode(raw[:-2] + b',"unknown":true}\n', type=FetchReceipt)
