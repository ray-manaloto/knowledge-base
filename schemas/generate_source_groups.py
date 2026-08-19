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

# Ported from `generate_fetch_receipt.py`, whose comment carries the full
# rationale. This generator was the ONLY one of the three still shelling out to a
# bare `datamodel-codegen` off `$PATH`; the cold lane rated that P1 on the
# 0.72.4 -> 0.74.0 bump. It is the stale-PATH class this repo has been bitten by
# repeatedly — a mise-global or pipx copy earlier on `$PATH` than the project
# venv runs INSTEAD, and the version guard below then reports the ambient tool's
# version, so the failure reads as "the pin is wrong" rather than "you ran the
# wrong binary".
#
# `--project` and `--locked` close the two remaining escape hatches: without
# `--project`, `uv run` discovers a project from the CALLER's cwd, so invoking
# this script from another directory can resolve a different project entirely;
# without `--locked`, a stale `uv.lock` is silently rewritten as a side effect of
# generating code, and with it staleness is an error a human has to look at.
_CODEGEN = (
    "uv",
    "run",
    "--project",
    str(ROOT),
    "--locked",
    "--group",
    "codegen",
    "datamodel-codegen",
)


def generate(output: Path = OUTPUT) -> None:
    """Generate the checked-in model with the reviewed generator contract."""
    version = subprocess.run(
        [*_CODEGEN, "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if version != f"datamodel-codegen {GENERATOR_VERSION}":
        raise RuntimeError(f"expected datamodel-codegen {GENERATOR_VERSION}, got {version!r}")

    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            *_CODEGEN,
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
