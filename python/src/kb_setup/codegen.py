# Copyright (c) 2026 Raymond Manaloto
"""Generate and verify committed models for versioned wire contracts."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_SCHEMA = Path("schemas/fetch-receipt.schema.json")
_OUTPUT = Path("python/src/kb_setup/generated/fetch_receipt.py")
_FLAGS = (
    "--input-file-type",
    "jsonschema",
    "--output-model-type",
    "msgspec.Struct",
    "--extra-fields",
    "forbid",
    "--use-generic-base-class",
    "--formatters",
    "black",
    "isort",
    "--disable-timestamp",
)


def _command(repo_root: Path, output: Path) -> list[str]:
    """Build the pinned generator invocation for the fetch receipt schema."""
    executable = shutil.which("datamodel-codegen")
    if executable is None:
        msg = "datamodel-codegen is unavailable; use `mise run codegen-fetch-receipt`"
        raise RuntimeError(msg)
    return [
        executable,
        "--input",
        str(repo_root / _SCHEMA),
        "--output",
        str(output),
        *_FLAGS,
    ]


def generate_fetch_receipt(repo_root: Path, output: Path | None = None) -> Path:
    """Generate the msgspec receipt model from the committed JSON Schema."""
    destination = output or repo_root / _OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(_command(repo_root, destination), check=True)
    return destination


def check_fetch_receipt(repo_root: Path) -> bool:
    """Regenerate in a temporary directory and byte-compare the tracked model."""
    expected = repo_root / _OUTPUT
    with tempfile.TemporaryDirectory(prefix="kb-fetch-receipt-codegen-") as directory:
        actual = generate_fetch_receipt(repo_root, Path(directory) / expected.name)
        if expected.is_file() and expected.read_bytes() == actual.read_bytes():
            return True
    return False


def main(repo_root: Path, args: list[str]) -> int:
    """Run the generation or freshness check command."""
    action = args[0] if args else "generate"
    if action == "generate" and len(args) == 1:
        print(generate_fetch_receipt(repo_root).relative_to(repo_root))
        return 0
    if action == "check" and len(args) == 1:
        if check_fetch_receipt(repo_root):
            print("[codegen-fetch-receipt] OK")
            return 0
        print("[codegen-fetch-receipt] STALE: run `mise run codegen-fetch-receipt`")
        return 1
    print("usage: kb-setup codegen-fetch-receipt [generate|check]")
    return 2
