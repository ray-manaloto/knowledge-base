# Copyright (c) 2026 Raymond Manaloto
"""Generated fetch-receipt models; edit the schema and rerun the generator."""

from enum import Enum
from typing import Annotated, Literal

from msgspec import Meta
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


class Status(Enum):
    """Generated source-group enumeration."""

    planned = "planned"
    complete = "complete"
    failed = "failed"


type Sha256 = Annotated[str, Meta(pattern="^[0-9a-f]{64}$")]


class FetchReceiptFile(Struct):
    """Generated source-group contract type."""

    path: Annotated[str, Meta(max_length=1024, min_length=1)]
    size: Annotated[int, Meta(ge=0)]
    sha256: Sha256


class FetchReceipt(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    status: Status
    provider: Annotated[str, Meta(max_length=64, min_length=1)]
    provider_version: Annotated[str, Meta(max_length=128, min_length=1)]
    source: Annotated[str, Meta(pattern="^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")]
    revision: Annotated[str, Meta(pattern="^[0-9a-f]{40}$")]
    license_id: Annotated[str, Meta(pattern="^[A-Za-z0-9][A-Za-z0-9.+-]{0,63}$")]
    license_path: Annotated[str, Meta(max_length=1024, min_length=1)]
    destination_sha256: Sha256
    bytes_total: Annotated[int, Meta(ge=0)]
    files: Annotated[list[FetchReceiptFile], Meta(min_length=1)]
