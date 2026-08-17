# Copyright (c) 2026 Raymond Manaloto
"""Deterministically generate strict msgspec fetch-receipt models."""

from __future__ import annotations

import subprocess
from pathlib import Path

GENERATOR_VERSION = "0.72.4"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "fetch-receipt.schema.json"
OUTPUT = ROOT / "python" / "src" / "kb_setup" / "generated" / "fetch_receipt.py"
TEMPLATES = ROOT / "schemas" / "templates"
FILE_HEADER = '''# Copyright (c) 2026 Raymond Manaloto
"""Generated fetch-receipt models; edit the schema and rerun the generator."""'''
# Resolve the generator from the LOCKED `codegen` dependency group, not from
# `$PATH`. A bare `datamodel-codegen` is whatever the machine happens to expose,
# and on this host that was an unpinned mise-global
# `pipx-datamodel-code-generator/0.73.0` shadowing the `==0.72.4` in
# `pyproject.toml` — so the version guard below failed on a host whose lockfile
# was perfectly correct, and would have kept failing until someone changed the
# machine. `uv run --group` reads `pyproject.toml`/`uv.lock` and cannot drift,
# which is the same reason nothing else here shells out to a bare interpreter.
#
# The guard is KEPT rather than deleted. It now asks a different and still worth
# asking question: not "is the right tool on PATH" (which this prefix settles)
# but "does the locked version still match the one this generator's flags and
# committed output were reviewed against" — which a lockfile bump can break.
# `--project` and `--locked` close the two remaining escape hatches: without
# `--project`, `uv run` discovers a project from the CALLER's cwd, so invoking
# this script from another directory can resolve a different project entirely
# (`--project` only fixes discovery; it does not change the cwd). Without
# `--locked`, a stale `uv.lock` is silently rewritten as a side effect of
# generating code; with it, staleness is an error a human has to look at.
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
