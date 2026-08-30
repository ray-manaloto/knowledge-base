# Copyright (c) 2026 Raymond Manaloto
"""Offline proof that deps.dev payloads round-trip through generated models."""

from __future__ import annotations

import msgspec

from kb_setup.generated.packages import DepsDevV3Package


def round_trip_package(payload: bytes) -> tuple[DepsDevV3Package, bytes]:
    """Decode and re-encode one deps.dev package response."""
    package = msgspec.json.decode(payload, type=DepsDevV3Package)
    return package, msgspec.json.encode(package)
