# Copyright (c) 2026 Raymond Manaloto
"""Hermetic contract tests for the deps.dev-backed `packages` adapter."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import msgspec
import pytest
from kb_setup.generated.packages import DepsDevV3Link, DepsDevV3Version
from kb_setup.generated.research_record import (
    AdapterRecord,
    Arm,
    Kind,
    Null,
    Packages,
    Tier,
    Trackers,
)
from kb_setup.research import cli as research_cli
from kb_setup.research import packages
from kb_setup.result import Err, Ok, Rc
from kb_setup.sinks import stdout_sink
from msgspec import UNSET

FIXTURES = Path(__file__).parent / "fixtures" / "research"
NOW = datetime(2026, 8, 29, 14, 5, 17, tzinfo=UTC)

_PACKAGE_PATH = "/v3/systems/PYPI/packages/requests"
_VERSION_PATH = f"{_PACKAGE_PATH}/versions/2.34.2"
_DEPENDENCIES_PATH = f"{_VERSION_PATH}:dependencies"

type JsonPayload = dict[str, object] | list[object]
type Reply = tuple[int, bytes | JsonPayload]


def _transport(responses: dict[str, Reply], seen: list[str]) -> httpx2.MockTransport:
    """Return exact canned replies while retaining encoded request paths."""

    def _reply(request: httpx2.Request) -> httpx2.Response:
        path = request.url.raw_path.decode("ascii")
        seen.append(path)
        if path not in responses:
            pytest.fail(f"unexpected deps.dev request: {path}")
        status_code, payload = responses[path]
        content = payload if isinstance(payload, bytes) else msgspec.json.encode(payload)
        return httpx2.Response(status_code, content=content)

    return httpx2.MockTransport(_reply)


def _record(result: object) -> AdapterRecord:
    assert isinstance(result, Ok)
    assert isinstance(result.value, AdapterRecord)
    return result.value


def _package_payload() -> Packages:
    return Packages(
        system="PYPI",
        name="requests",
        version_count=161,
        latest_version="2.34.2",
        licenses=["Apache-2.0"],
        direct_dependency_count=2,
        cited_links=["https://github.com/psf/requests"],
    )


def _contract_record(
    *,
    with_package: bool = True,
    null_result: Null | None = None,
    trackers: Trackers | None = None,
) -> AdapterRecord:
    return AdapterRecord(
        adapter="packages",
        tier=Tier.cheap,
        question="PYPI/requests",
        command="GET https://api.deps.dev/v3/systems/PYPI/packages/requests",
        trackers=trackers,
        links=None,
        packages=_package_payload() if with_package else None,
        ran_at="2026-08-29T14:05:17Z",
        total_count=161 if with_package else 0,
        hits=[],
        null_result=null_result,
    )


def _fixed_lookup(
    monkeypatch: pytest.MonkeyPatch,
    record: AdapterRecord | None = None,
) -> None:
    fixed_record = _contract_record() if record is None else record

    def _lookup(system: str, name: str) -> Ok[AdapterRecord]:
        assert (system, name) == ("pypi", "requests")
        return Ok(fixed_record)

    monkeypatch.setattr(packages, "lookup", _lookup)


def test_known_hit_reports_versions_licenses_links_and_direct_dependencies() -> None:
    seen: list[str] = []
    transport = _transport(
        {
            _PACKAGE_PATH: (
                200,
                (FIXTURES / "deps-dev-pypi-requests.json").read_bytes(),
            ),
            _VERSION_PATH: (
                200,
                {
                    "versionKey": {
                        "system": "PYPI",
                        "name": "requests",
                        "version": "2.34.2",
                    },
                    "licenses": ["Apache-2.0"],
                    "links": [
                        {
                            "label": "SOURCE_REPO",
                            "url": "https://github.com/psf/requests",
                        },
                        {
                            "label": "HOMEPAGE",
                            "url": "https://requests.readthedocs.io/",
                        },
                    ],
                },
            ),
            _DEPENDENCIES_PATH: (
                200,
                {
                    "nodes": [
                        {"relation": "SELF"},
                        {"relation": "DIRECT"},
                        {"relation": "INDIRECT"},
                        {"relation": "DIRECT"},
                    ]
                },
            ),
        },
        seen,
    )

    record = _record(packages.lookup("pypi", " requests ", transport=transport, now=NOW))

    assert seen == [_PACKAGE_PATH, _VERSION_PATH, _DEPENDENCIES_PATH]
    assert record.adapter == "packages"
    assert record.tier is Tier.cheap
    assert record.question == "PYPI/requests"
    assert record.command == f"GET https://api.deps.dev{_PACKAGE_PATH}"
    assert record.trackers is None
    assert record.links is None
    assert record.hits == []
    assert record.null_result is None
    assert record.packages is not None
    assert record.packages.version_count == 161
    assert record.packages.latest_version == "2.34.2"
    assert record.packages.licenses == ["Apache-2.0"]
    assert record.packages.direct_dependency_count == 2
    assert record.packages.cited_links == [
        "https://github.com/psf/requests",
        "https://requests.readthedocs.io/",
    ]
    assert record.total_count == record.packages.version_count
    assert record.ran_at == "2026-08-29T14:05:17Z"
    packages.validate(record)


@pytest.mark.parametrize(
    ("system", "name", "primary_path", "control_path"),
    [
        (
            "go",
            "example.com/missing",
            "/v3/systems/GO/packages/example.com%2Fmissing",
            "/v3/systems/GO/packages/golang.org%2Fx%2Ftext",
        ),
        (
            "maven",
            "example.org:missing/artifact",
            "/v3/systems/MAVEN/packages/example.org%3Amissing%2Fartifact",
            "/v3/systems/MAVEN/packages/com.google.guava%3Aguava",
        ),
    ],
)
@pytest.mark.parametrize("control", [(200, True), (404, False)])
def test_known_miss_is_control_armed_with_encoded_package_paths(
    system: str,
    name: str,
    primary_path: str,
    control_path: str,
    control: tuple[int, bool],
) -> None:
    control_status, discriminates = control
    seen: list[str] = []
    transport = _transport(
        {
            primary_path: (404, {}),
            control_path: (control_status, {}),
        },
        seen,
    )

    record = _record(packages.lookup(system, name, transport=transport, now=NOW))

    assert seen == [primary_path, control_path]
    assert record.packages is None
    assert record.total_count == 0
    assert record.null_result is not None
    assert len(record.null_result.arms) == 1
    arm = record.null_result.arms[0]
    assert arm.kind is Kind.package
    assert arm.command == f"GET https://api.deps.dev{control_path}"
    assert arm.result == f"status={control_status}"
    assert arm.discriminates is discriminates
    packages.validate(record)


@pytest.mark.parametrize(
    ("system", "name", "message"),
    [
        ("unknown", "requests", "system must be one of"),
        ("SYSTEM_UNSPECIFIED", "requests", "not a queryable"),
        ("pypi", "   ", "name is required"),
        ("pypi", "x" * 201, "at most 200"),
    ],
)
def test_bad_requests_are_typed_without_calling_deps_dev(
    system: str,
    name: str,
    message: str,
) -> None:
    def _unexpected(request: httpx2.Request) -> httpx2.Response:
        pytest.fail(f"deps.dev must not run for a bad request: {request.url}")

    result = packages.lookup(
        system,
        name,
        transport=httpx2.MockTransport(_unexpected),
        now=NOW,
    )

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert message in result.message


def test_empty_versions_skip_version_and_dependency_requests() -> None:
    seen: list[str] = []
    transport = _transport(
        {
            "/v3/systems/NPM/packages/empty": (
                200,
                {"packageKey": {"system": "NPM", "name": "empty"}, "versions": []},
            )
        },
        seen,
    )

    record = _record(packages.lookup("npm", "empty", transport=transport, now=NOW))

    assert seen == ["/v3/systems/NPM/packages/empty"]
    assert record.packages is not None
    assert record.packages.version_count == 0
    assert record.packages.latest_version is None
    assert record.packages.licenses == []
    assert record.packages.direct_dependency_count is None
    assert record.packages.cited_links == []
    packages.validate(record)


def test_default_version_failure_is_not_run_instead_of_a_null() -> None:
    seen: list[str] = []
    package_path = "/v3/systems/NPM/packages/react"
    version_path = f"{package_path}/versions/19.1.1"
    transport = _transport(
        {
            package_path: (
                200,
                {
                    "versions": [
                        {
                            "versionKey": {
                                "system": "NPM",
                                "name": "react",
                                "version": "19.1.1",
                            },
                            "isDefault": True,
                        }
                    ]
                },
            ),
            version_path: (503, {}),
        },
        seen,
    )

    result = packages.lookup("npm", "react", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "HTTP 503" in result.message
    assert seen == [package_path, version_path]


def test_transport_and_decode_failures_are_not_run() -> None:
    def _offline(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("offline", request=request)

    transport_result = packages.lookup(
        "pypi",
        "requests",
        transport=httpx2.MockTransport(_offline),
        now=NOW,
    )
    decode_result = packages.lookup(
        "pypi",
        "requests",
        transport=_transport({_PACKAGE_PATH: (200, b"<html>")}, []),
        now=NOW,
    )

    assert isinstance(transport_result, Err)
    assert transport_result.rc is Rc.NOT_RUN
    assert "offline" in transport_result.message
    assert isinstance(decode_result, Err)
    assert decode_result.rc is Rc.NOT_RUN
    assert "unparsable payload" in decode_result.message


def test_unset_version_fields_are_narrowed_before_record_use() -> None:
    version = DepsDevV3Version(
        licenses=UNSET,
        links=[
            DepsDevV3Link(label="missing", url=UNSET),
            DepsDevV3Link(label="source", url="https://example.test/source"),
        ],
    )

    licenses, cited_links = packages._version_fields(version)

    assert licenses == []
    assert cited_links == ["https://example.test/source"]


def test_validate_rejects_another_adapter_payload() -> None:
    record = _contract_record(trackers=Trackers(has_issues=False, has_discussions=False))

    with pytest.raises(msgspec.ValidationError, match="must not carry trackers"):
        packages.validate(record)


@pytest.mark.parametrize(
    "case",
    [
        (False, None),
        (
            True,
            Null(
                arms=[
                    Arm(
                        kind=Kind.package,
                        command="GET https://api.deps.dev/control",
                        result="status=200",
                        discriminates=True,
                    )
                ]
            ),
        ),
    ],
    ids=["neither", "both"],
)
def test_validate_requires_exactly_one_payload_or_null(
    case: tuple[bool, Null | None],
) -> None:
    with_package, null_result = case
    record = _contract_record(with_package=with_package, null_result=null_result)

    with pytest.raises(msgspec.ValidationError, match="exactly one"):
        packages.validate(record)


def test_validate_rejects_a_non_package_null_arm() -> None:
    record = _contract_record(
        with_package=False,
        null_result=Null(
            arms=[
                Arm(
                    kind=Kind.issue,
                    command="GET https://api.deps.dev/control",
                    result="status=200",
                    discriminates=True,
                )
            ]
        ),
    )

    with pytest.raises(msgspec.ValidationError, match="one package arm"):
        packages.validate(record)


def test_main_out_flag_is_positionally_flexible_and_emits_an_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jsonl_path = tmp_path / "events.jsonl"
    out_path = tmp_path / "nested" / "record.json"
    buf = io.StringIO()
    _fixed_lookup(monkeypatch)

    with stdout_sink(stream=buf, jsonl_path=jsonl_path, offload=False):
        returncode = packages.main(
            ["pypi", "--out", str(out_path), "requests"],
            tmp_path,
        )

    assert returncode == 0
    decoded = msgspec.json.decode(out_path.read_bytes(), type=AdapterRecord)
    assert decoded.adapter == "packages"
    assert decoded.packages is not None
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "packages.wrote"


def test_main_missing_out_value_fails_as_bad_request(tmp_path: Path) -> None:
    returncode = packages.main(["pypi", "requests", "--out"], tmp_path)

    assert returncode == 2


def test_aggregated_research_dispatches_the_packages_verb(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fixed_lookup(monkeypatch)

    returncode = research_cli.main(["packages", "pypi", "requests"])
    captured = capsys.readouterr()

    assert returncode == 0
    assert captured.err == ""
    assert captured.out.startswith('{\n  "adapter": "packages"')
