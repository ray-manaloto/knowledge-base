# Copyright (c) 2026 Raymond Manaloto
"""Deterministically generate strict msgspec source-group models."""

from __future__ import annotations

import subprocess
from pathlib import Path

GENERATOR_VERSION = "0.74.0"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "source-groups.schema.json"
OUTPUT = ROOT / "python" / "src" / "kb_setup" / "generated" / "source_groups.py"
TEMPLATES = ROOT / "schemas" / "templates"
FILE_HEADER = '''# Copyright (c) 2026 Raymond Manaloto
"""Generated source-group models; edit the schema and rerun the generator."""'''


def generate(output: Path = OUTPUT) -> None:
    """Generate the checked-in model with the reviewed generator contract."""
    version = subprocess.run(
        ["datamodel-codegen", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if version != f"datamodel-codegen {GENERATOR_VERSION}":
        raise RuntimeError(f"expected datamodel-codegen {GENERATOR_VERSION}, got {version!r}")

    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "datamodel-codegen",
            "--input",
            str(SCHEMA),
            "--input-file-type",
            "jsonschema",
            "--schema-version",
            "2020-12",
            "--schema-version-mode",
            "strict",
            "--strict-refs",
            "--output",
            str(output),
            "--output-model-type",
            "msgspec.Struct",
            "--target-python-version",
            "3.14",
            "--formatters",
            "isort",
            "ruff-format",
            "--custom-template-dir",
            str(TEMPLATES),
            "--custom-file-header",
            FILE_HEADER,
            "--disable-timestamp",
            "--extra-fields",
            "forbid",
            "--use-generic-base-class",
            "--use-specialized-enum",
            "--use-standard-collections",
        ],
        check=True,
    )


if __name__ == "__main__":
    generate()
