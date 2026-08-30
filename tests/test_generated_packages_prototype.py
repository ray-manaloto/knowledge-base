# Copyright (c) 2026 Raymond Manaloto
"""Offline round-trip proof for deps.dev's generated package model."""

from __future__ import annotations

from pathlib import Path

import msgspec
from kb_setup.generated.packages import DepsDevV3PackageKey
from kb_setup.generated_packages_prototype import round_trip_package

FIXTURE = Path(__file__).parent / "fixtures/research/deps-dev-pypi-requests.json"


def test_real_package_response_round_trips_with_lower_camel_case_keys() -> None:
    """A captured keyless response must populate and preserve the protobuf contract."""
    payload = FIXTURE.read_bytes()

    package, encoded = round_trip_package(payload)

    assert isinstance(package.package_key, DepsDevV3PackageKey)
    assert package.package_key.system == "PYPI"
    assert package.package_key.name == "requests"
    assert isinstance(package.versions, list)
    assert len(package.versions) == 161

    round_tripped = msgspec.json.decode(encoded)
    assert round_tripped == msgspec.json.decode(payload)
    assert set(round_tripped) == {"packageKey", "versions"}
    assert "package_key" not in round_tripped
    assert round_tripped["versions"][0]["publishedAt"] == "2012-01-22T05:08:17Z"
    assert round_tripped["versions"][0]["isDefault"] is False
    assert "published_at" not in round_tripped["versions"][0]
    assert "is_default" not in round_tripped["versions"][0]
