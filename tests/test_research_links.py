# Copyright (c) 2026 Raymond Manaloto
"""Hermetic contract tests for the lychee-backed `links` research adapter.

One test at the bottom is deliberately NOT hermetic: it shells the real
`lychee` binary against the tracked `links-check.toml` and a known-404 URL —
the regression arm for the exact bug premise-verification caught (a bare
positional URL panics lychee instead of reporting it as broken). Gated on
`shutil.which("lychee")`, mirroring this repo's existing skip convention for a
missing external binary (see `test_launch.py`'s `tmux` skip).
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import msgspec
import pytest
from kb_setup.generated.research_record import AdapterRecord, LinkResult, Links, Tier, Trackers
from kb_setup.research import links
from kb_setup.result import Err, Ok, Rc
from kb_setup.sinks import stdout_sink

FIXTURES = Path(__file__).parent / "fixtures" / "research"
NOW = datetime(2026, 8, 28, 2, 7, 38, tzinfo=UTC)

type Runner = Callable[[tuple[str, ...]], tuple[int, str, str]]

needs_lychee = pytest.mark.skipif(
    shutil.which("lychee") is None, reason="needs a real lychee binary"
)


def _stub_lychee(monkeypatch: pytest.MonkeyPatch, fixture: str, stderr: str = "") -> None:
    payload = (FIXTURES / fixture).read_text(encoding="utf-8")

    def _fake(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        return 0, payload, stderr

    monkeypatch.setattr(links, "_run_lychee", _fake)


def _record(result: object) -> AdapterRecord:
    assert isinstance(result, Ok)
    assert isinstance(result.value, AdapterRecord)
    return result.value


def test_clean_run_reports_one_ok_and_one_broken_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_lychee(monkeypatch, "lychee-clean.json")

    record = _record(links.check(("https://github.com/",), run=links._run_lychee, now=NOW))

    assert record.adapter == "links"
    assert record.trackers is None
    assert record.hits == []
    assert record.null_result is None
    assert record.links is not None
    assert record.links.checked == 2
    assert record.links.broken_count == 1
    assert [(r.ok, r.status_text) for r in record.links.results] == [
        (True, "200 OK (200)"),
        (False, "Rejected status code: 404 Not Found (404)"),
    ]
    links.validate(record)


def test_excluded_links_are_reported_as_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_lychee(monkeypatch, "lychee-excluded.json")

    record = _record(links.check(("https://example.com/",), run=links._run_lychee, now=NOW))

    assert record.links is not None
    assert record.links.checked == 2
    assert record.links.broken_count == 2
    assert all(r.ok is False and r.status_text == "Excluded" for r in record.links.results)
    links.validate(record)


def test_redirect_map_is_excluded_from_the_parsing_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live 3-entry run once produced 4 flattened rows via `redirect_map`.

    This fixture reproduces that shape (a URL present in both `error_map` and
    `redirect_map`); the control arm below fails if `redirect_map` is ever
    folded back into the union.
    """
    _stub_lychee(monkeypatch, "lychee-redirect-duplicate.json")

    record = _record(links.check(("https://example.org/",), run=links._run_lychee, now=NOW))

    assert record.links is not None
    assert len(record.links.results) == 2
    assert record.links.checked == len(record.links.results)
    links.validate(record)


@pytest.mark.parametrize(
    ("urls", "message"),
    [
        ((), "at least one URL"),
        (tuple(f"https://example.test/{i}" for i in range(61)), "at most 60"),
        (("ftp://example.test/",), "http:// or https://"),
        (("https://" + "a" * 2049,), "exceeds 2048"),
    ],
)
def test_bad_requests_are_typed_without_running_lychee(urls: tuple[str, ...], message: str) -> None:
    def _unexpected(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        pytest.fail("lychee must not run for a bad request")

    result = links.check(urls, run=_unexpected, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert message in result.message


def test_unparsable_stdout_fails_closed_as_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def _garbage(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        return 2, "", "Error while loading config file: links-check.toml"

    monkeypatch.setattr(links, "_run_lychee", _garbage)

    result = links.check(("https://example.test/",), run=links._run_lychee, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "Error while loading config" in result.message


def test_broken_links_do_not_fail_closed_despite_nonzero_rc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc=2 means lychee found broken links — a finding, not a failure."""
    payload = (FIXTURES / "lychee-clean.json").read_text(encoding="utf-8")

    def _rc2(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        return 2, payload, ""

    result = links.check(("https://github.com/",), run=_rc2, now=NOW)

    assert isinstance(result, Ok)


def test_run_lychee_uses_the_bounded_captured_subprocess_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", _fake)

    result = links._run_lychee(("--format", "json"))

    assert result == (0, "out", "err")
    assert captured == {
        "argv": ["lychee", "--format", "json"],
        "capture_output": True,
        "text": True,
        "errors": "replace",
        "check": False,
        "timeout": 120,
    }


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("missing"),
        PermissionError("denied"),
        subprocess.TimeoutExpired(["lychee"], 120),
    ],
    ids=["missing", "permission", "timeout"],
)
def test_run_lychee_maps_start_and_timeout_failures_to_127(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    def _raise(_argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr(subprocess, "run", _raise)

    returncode, stdout, stderr = links._run_lychee(("--format", "json"))

    assert returncode == 127
    assert stdout == ""
    assert stderr.startswith("lychee: ")


def _contract_record(
    *,
    results: list[LinkResult] | None = None,
    checked: int | None = None,
    broken_count: int | None = None,
    trackers: Trackers | None = None,
) -> AdapterRecord:
    rs = results if results is not None else []
    return AdapterRecord(
        adapter="links",
        tier=Tier.cheap,
        question="https://example.test/",
        command="lychee --format json --no-progress -v --config links-check.toml /tmp/x.txt",
        trackers=trackers,
        links=Links(
            checked=checked if checked is not None else len(rs),
            broken_count=broken_count
            if broken_count is not None
            else sum(1 for r in rs if not r.ok),
            results=rs,
        ),
        ran_at="2026-08-28T02:07:38Z",
        total_count=len(rs),
        hits=[],
        null_result=None,
    )


def test_validate_rejects_trackers_on_a_links_record() -> None:
    record = _contract_record(trackers=Trackers(has_issues=False, has_discussions=False))

    with pytest.raises(msgspec.ValidationError, match="must not carry trackers"):
        links.validate(record)


def test_validate_rejects_checked_result_count_mismatch() -> None:
    record = _contract_record(
        results=[
            LinkResult(url="https://example.test/", ok=True, status_text="200 OK"),
        ],
        checked=2,
    )

    with pytest.raises(msgspec.ValidationError, match="checked must equal"):
        links.validate(record)


def test_validate_rejects_broken_count_mismatch() -> None:
    record = _contract_record(
        results=[
            LinkResult(url="https://example.test/", ok=False, status_text="404"),
        ],
        broken_count=0,
    )

    with pytest.raises(msgspec.ValidationError, match="broken_count must equal"):
        links.validate(record)


def test_validate_rejects_an_excluded_link_marked_ok() -> None:
    record = _contract_record(
        results=[
            LinkResult(url="https://example.test/", ok=True, status_text="Excluded"),
        ],
    )

    with pytest.raises(msgspec.ValidationError, match="excluded link"):
        links.validate(record)


def _fix_now(monkeypatch: pytest.MonkeyPatch) -> None:
    original = links.check

    def _fixed(urls: tuple[str, ...], *, run: Runner) -> links.Result[AdapterRecord]:
        return original(urls, run=run, now=NOW)

    monkeypatch.setattr(links, "check", _fixed)


def test_main_prints_one_indented_json_document_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_lychee(monkeypatch, "lychee-clean.json")
    _fix_now(monkeypatch)

    returncode = links.main(["https://github.com/"], tmp_path)
    captured = capsys.readouterr()

    assert returncode == 0
    assert captured.err == ""
    assert captured.out.startswith('{\n  "adapter": "links"')
    decoded = msgspec.json.decode(captured.out, type=AdapterRecord)
    assert decoded.ran_at == "2026-08-28T02:07:38Z"


def test_main_bad_request_keeps_stdout_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    returncode = links.main([], tmp_path)
    captured = capsys.readouterr()

    assert returncode == 2
    assert captured.out == ""
    assert captured.err.startswith("ERROR: kb-research-links: at least one URL is required")


def test_main_out_flag_writes_the_record_and_emits_an_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jsonl_path = tmp_path / "events.jsonl"
    out_path = tmp_path / "record.json"
    buf = io.StringIO()
    _stub_lychee(monkeypatch, "lychee-clean.json")
    _fix_now(monkeypatch)

    with stdout_sink(stream=buf, jsonl_path=jsonl_path, offload=False):
        links.main(["https://github.com/", "--out", str(out_path)], tmp_path)

    assert out_path.is_file()
    decoded = msgspec.json.decode(out_path.read_text(encoding="utf-8"), type=AdapterRecord)
    assert decoded.adapter == "links"
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "links.wrote"


def test_main_missing_out_value_fails_as_bad_request(tmp_path: Path) -> None:
    returncode = links.main(["https://example.test/", "--out"], tmp_path)

    assert returncode == 2


@needs_lychee
def test_real_lychee_reports_a_known_404_as_broken_not_a_crash(tmp_path: Path) -> None:
    """The exact regression arm for rev 1's bug: a 404 must not panic lychee."""
    del tmp_path
    url = "https://github.com/ray-manaloto/this-repo-should-not-exist-zzz578test"

    result = links.check((url,))

    assert isinstance(result, Ok)
    record = result.value
    assert record.links is not None
    assert record.links.broken_count == 1
    assert record.links.results[0].ok is False
    links.validate(record)
