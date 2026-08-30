# Copyright (c) 2026 Raymond Manaloto
"""Look up package metadata through deps.dev's keyless v3 HTTP API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx2
import msgspec
from msgspec import UnsetType

from kb_setup import events
from kb_setup.generated.packages import (
    DepsDevV3Dependencies,
    DepsDevV3DependencyRelation,
    DepsDevV3Package,
    DepsDevV3PackageVersion,
    DepsDevV3System,
    DepsDevV3Version,
)
from kb_setup.generated.research_record import AdapterRecord, Arm, Kind, Null, Packages, Tier
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code

_BASE_URL = "https://api.deps.dev"
_HTTP_OK = 200
_HTTP_NOT_FOUND = 404
_HTTP_TIMEOUT = 30.0
_MAX_NAME_LENGTH = 200
_MAX_VERSION_LENGTH = 100
_MAX_LICENSES = 20
_MAX_CITED_LINKS = 20
_EXPECTED_POSITIONAL_ARGS = 2

type _Transport = httpx2.BaseTransport | None

_KNOWN_GOOD: dict[DepsDevV3System, str] = {
    DepsDevV3System.GO: "golang.org/x/text",
    DepsDevV3System.RUBYGEMS: "rails",
    DepsDevV3System.NPM: "react",
    DepsDevV3System.CARGO: "serde",
    DepsDevV3System.MAVEN: "com.google.guava:guava",
    DepsDevV3System.PYPI: "requests",
    DepsDevV3System.NUGET: "Newtonsoft.Json",
}


@dataclass(frozen=True, slots=True)
class _PackageFields:
    """Values derived from a package and its selected version."""

    version_count: int
    latest_version: str | None
    licenses: list[str]
    direct_dependency_count: int | None
    cited_links: list[str]


def _inputs(system: str, name: str) -> tuple[DepsDevV3System, str] | Err:
    """Normalize admissible package identity or return a typed bad request."""
    try:
        normalized_system = DepsDevV3System(system.strip().upper())
    except ValueError:
        allowed = ", ".join(member.value.lower() for member in _KNOWN_GOOD)
        return Err(f"system must be one of: {allowed}", rc=Rc.BAD_REQUEST)
    if normalized_system is DepsDevV3System.SYSTEM_UNSPECIFIED:
        return Err("SYSTEM_UNSPECIFIED is not a queryable package system", rc=Rc.BAD_REQUEST)

    normalized_name = name.strip()
    if not normalized_name:
        return Err("a package name is required", rc=Rc.BAD_REQUEST)
    if len(normalized_name) > _MAX_NAME_LENGTH:
        return Err(
            f"the package name must be at most {_MAX_NAME_LENGTH} characters",
            rc=Rc.BAD_REQUEST,
        )
    return normalized_system, normalized_name


def _package_path(
    system: DepsDevV3System,
    name: str,
    *,
    version: str | None = None,
    dependencies: bool = False,
) -> str:
    """Build one deps.dev path, percent-encoding every identity segment."""
    encoded_system = quote(system.value, safe="")
    encoded_name = quote(name, safe="")
    path = f"/v3/systems/{encoded_system}/packages/{encoded_name}"
    if version is None:
        return path
    encoded_version = quote(version, safe="")
    suffix = ":dependencies" if dependencies else ""
    return f"{path}/versions/{encoded_version}{suffix}"


def _display_command(path: str) -> str:
    """Render the exact secret-free HTTP request recorded in the envelope."""
    return f"GET {_BASE_URL}{path}"


def _ran_at(now: datetime | None) -> str:
    """Render an aware instant in the contract's exact UTC ``Z`` form."""
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _request(client: httpx2.Client, path: str) -> httpx2.Response | Err:
    """Issue one bounded request, mapping transport failures to ``NOT_RUN``."""
    command = _display_command(path)
    try:
        return client.get(path)
    except httpx2.TransportError as exc:
        return Err(f"deps.dev request failed for `{command}`: {exc}", rc=Rc.NOT_RUN)


def _decode[T](response: httpx2.Response, response_type: type[T], path: str) -> T | Err:
    """Decode one successful deps.dev response or fail closed."""
    try:
        return msgspec.json.decode(response.content, type=response_type)
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        return Err(
            f"deps.dev returned an unparsable payload for `{_display_command(path)}`: {exc}",
            rc=Rc.NOT_RUN,
        )


def _http_error(path: str, status_code: int) -> Err:
    """Map a non-answering HTTP status onto the shared result vocabulary."""
    return Err(
        f"deps.dev returned HTTP {status_code} for `{_display_command(path)}`",
        rc=Rc.NOT_RUN,
    )


def _fetch[T](client: httpx2.Client, path: str, response_type: type[T]) -> T | Err:
    """Fetch and decode one deps.dev endpoint whose only success is HTTP 200."""
    response = _request(client, path)
    if isinstance(response, Err):
        return response
    if response.status_code != _HTTP_OK:
        return _http_error(path, response.status_code)
    return _decode(response, response_type, path)


def _get_package(client: httpx2.Client, path: str) -> DepsDevV3Package | Err | None:
    """Fetch the package index, preserving 404 as the sole null candidate."""
    response = _request(client, path)
    if isinstance(response, Err):
        return response
    if response.status_code == _HTTP_NOT_FOUND:
        return None
    if response.status_code != _HTTP_OK:
        return _http_error(path, response.status_code)
    return _decode(response, DepsDevV3Package, path)


def _selected_version(versions: list[DepsDevV3PackageVersion]) -> str | Err | None:
    """Return the default version, the final fallback, or no version at all."""
    if not versions:
        return None
    selected = next((entry for entry in versions if entry.is_default is True), versions[-1])
    version_key = selected.version_key
    if isinstance(version_key, UnsetType) or isinstance(version_key.version, UnsetType):
        return Err("deps.dev package response omitted the selected version key", rc=Rc.NOT_RUN)
    if not version_key.version:
        return Err("deps.dev package response carried an empty selected version", rc=Rc.NOT_RUN)
    if len(version_key.version) > _MAX_VERSION_LENGTH:
        return Err(
            f"deps.dev selected version exceeds {_MAX_VERSION_LENGTH} characters",
            rc=Rc.NOT_RUN,
        )
    return version_key.version


def _version_fields(version: DepsDevV3Version) -> tuple[list[str], list[str]]:
    """Narrow optional wire fields into the bounded shared-record shape."""
    raw_licenses = version.licenses
    licenses = [] if isinstance(raw_licenses, UnsetType) else list(raw_licenses)[:_MAX_LICENSES]
    raw_links = version.links
    links = [] if isinstance(raw_links, UnsetType) else list(raw_links)
    cited_links: list[str] = []
    for link in links:
        url = link.url
        if isinstance(url, UnsetType):
            continue
        cited_links.append(url)
        if len(cited_links) == _MAX_CITED_LINKS:
            break
    return licenses, cited_links


def _package_fields(
    client: httpx2.Client,
    system: DepsDevV3System,
    name: str,
    package: DepsDevV3Package,
) -> _PackageFields | Err:
    """Resolve the selected version and its direct-dependency metadata."""
    raw_versions = package.versions
    versions = [] if isinstance(raw_versions, UnsetType) else list(raw_versions)
    latest_version = _selected_version(versions)
    if isinstance(latest_version, Err):
        return latest_version
    if latest_version is None:
        return _PackageFields(len(versions), None, [], None, [])

    version_path = _package_path(system, name, version=latest_version)
    version = _fetch(client, version_path, DepsDevV3Version)
    if isinstance(version, Err):
        return version
    licenses, cited_links = _version_fields(version)

    dependencies_path = _package_path(
        system,
        name,
        version=latest_version,
        dependencies=True,
    )
    dependencies = _fetch(client, dependencies_path, DepsDevV3Dependencies)
    if isinstance(dependencies, Err):
        return dependencies
    raw_nodes = dependencies.nodes
    nodes = [] if isinstance(raw_nodes, UnsetType) else list(raw_nodes)
    direct_dependency_count = sum(
        1 for node in nodes if node.relation == DepsDevV3DependencyRelation.DIRECT
    )
    return _PackageFields(
        len(versions),
        latest_version,
        licenses,
        direct_dependency_count,
        cited_links,
    )


def _null_record(
    client: httpx2.Client,
    system: DepsDevV3System,
    name: str,
    package_path: str,
    now: datetime | None,
) -> Result[AdapterRecord]:
    """Corroborate a 404 with the fixed same-system known-good package."""
    control_path = _package_path(system, _KNOWN_GOOD[system])
    control_response = _request(client, control_path)
    if isinstance(control_response, Err):
        return control_response
    return Ok(
        AdapterRecord(
            adapter="packages",
            tier=Tier.cheap,
            question=f"{system.value}/{name}",
            command=_display_command(package_path),
            trackers=None,
            links=None,
            packages=None,
            ran_at=_ran_at(now),
            total_count=0,
            hits=[],
            null_result=Null(
                arms=[
                    Arm(
                        kind=Kind.package,
                        command=_display_command(control_path),
                        result=f"status={control_response.status_code}",
                        discriminates=control_response.status_code == _HTTP_OK,
                    )
                ]
            ),
        )
    )


def _lookup_with_client(
    client: httpx2.Client,
    system: DepsDevV3System,
    name: str,
    now: datetime | None,
) -> Result[AdapterRecord]:
    """Run the package, version, and dependency stages on one client."""
    package_path = _package_path(system, name)
    package = _get_package(client, package_path)
    if isinstance(package, Err):
        return package
    if package is None:
        return _null_record(client, system, name, package_path, now)

    fields = _package_fields(client, system, name, package)
    if isinstance(fields, Err):
        return fields
    return Ok(
        AdapterRecord(
            adapter="packages",
            tier=Tier.cheap,
            question=f"{system.value}/{name}",
            command=_display_command(package_path),
            trackers=None,
            links=None,
            packages=Packages(
                system=system.value,
                name=name,
                version_count=fields.version_count,
                latest_version=fields.latest_version,
                licenses=fields.licenses,
                direct_dependency_count=fields.direct_dependency_count,
                cited_links=fields.cited_links,
            ),
            ran_at=_ran_at(now),
            total_count=fields.version_count,
            hits=[],
            null_result=None,
        )
    )


def lookup(
    system: str,
    name: str,
    *,
    transport: _Transport = None,
    now: datetime | None = None,
) -> Result[AdapterRecord]:
    """Look up versions, licences, links, and direct dependency count."""
    inputs = _inputs(system, name)
    if isinstance(inputs, Err):
        return inputs
    normalized_system, normalized_name = inputs

    with httpx2.Client(
        transport=transport,
        base_url=_BASE_URL,
        timeout=_HTTP_TIMEOUT,
    ) as client:
        return _lookup_with_client(client, normalized_system, normalized_name, now)


def _validate_presence(record: AdapterRecord) -> None:
    """Require exactly one packages outcome: payload or corroborated null."""
    has_packages = record.packages is not None
    has_null = record.null_result is not None
    if has_packages == has_null:
        raise msgspec.ValidationError("exactly one of packages or null_result must be present")


def _validate_null(record: AdapterRecord) -> None:
    """Pin a packages null to one package-kind control arm."""
    if record.null_result is None:
        return
    arms = record.null_result.arms
    if len(arms) != 1 or arms[0].kind is not Kind.package:
        raise msgspec.ValidationError("a packages null_result must have exactly one package arm")


def _validate_packages(record: AdapterRecord) -> None:
    """Defend non-negative package counters beyond generated constraints."""
    if record.packages is None:
        return
    if record.packages.version_count < 0:
        raise msgspec.ValidationError("version_count must be non-negative")
    direct_count = record.packages.direct_dependency_count
    if direct_count is not None and direct_count < 0:
        raise msgspec.ValidationError("direct_dependency_count must be non-negative")


def validate(record: AdapterRecord) -> None:
    """Enforce generated-field and semantic cross-field contract invariants."""
    msgspec.json.decode(msgspec.json.encode(record), type=AdapterRecord)

    if record.adapter != "packages":
        return
    if record.hits:
        raise msgspec.ValidationError("a packages record must have empty hits")
    if record.trackers is not None:
        raise msgspec.ValidationError("a packages record must not carry trackers")
    if record.links is not None:
        raise msgspec.ValidationError("a packages record must not carry links")

    _validate_presence(record)
    _validate_null(record)
    _validate_packages(record)


def main(argv: list[str], repo_root: Path) -> int:
    """Print one validated package record, or write it to ``--out PATH``."""
    del repo_root
    positionals: list[str] = []
    out_path: Path | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            if i + 1 >= len(argv):
                err = Err("--out requires a path", rc=Rc.BAD_REQUEST)
                events.fail(
                    "packages.bad_out_flag",
                    f"kb-research-packages: {err.message}",
                    adapter="packages",
                    outcome="bad_request",
                )
                return exit_code(err)
            out_path = Path(argv[i + 1])
            i += 2
            continue
        positionals.append(argv[i])
        i += 1

    event_system = positionals[0][:40] if positionals else ""
    event_name = positionals[1][:_MAX_NAME_LENGTH] if len(positionals) > 1 else ""
    started_at = time.perf_counter()
    result: Result[AdapterRecord]
    if len(positionals) != _EXPECTED_POSITIONAL_ARGS:
        result = Err("expected <system> <name>", rc=Rc.BAD_REQUEST)
    else:
        result = lookup(positionals[0], positionals[1])
    duration_s = time.perf_counter() - started_at
    if not isinstance(result, Ok):
        if isinstance(result, External):
            outcome = "external"
        elif result.rc is Rc.BAD_REQUEST:
            outcome = "bad_request"
        elif result.rc is Rc.NOT_RUN:
            outcome = "not_run"
        else:
            outcome = "error"
        events.fail(
            "packages.lookup_failed",
            f"kb-research-packages: {result.message}",
            adapter="packages",
            system=event_system,
            name=event_name,
            duration_s=duration_s,
            outcome=outcome,
        )
        return exit_code(result)

    record = result.value
    validate(record)
    text = msgspec.json.format(msgspec.json.encode(record).decode(), indent=2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n")
        events.say(
            "packages.wrote",
            f"[aggregated-research] wrote {out_path}",
            adapter="packages",
            system=event_system,
            name=event_name,
            duration_s=duration_s,
            outcome="ok",
            path=out_path,
        )
    else:
        events.say(
            "packages.result",
            text,
            adapter="packages",
            system=event_system,
            name=event_name,
            duration_s=duration_s,
            outcome="ok",
        )
    return exit_code(result)
