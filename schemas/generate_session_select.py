# Copyright (c) 2026 Raymond Manaloto
"""Deterministically generate strict msgspec session-selection models.

Cloned from `generate_fetch_receipt.py`, INCLUDING its hardened generator
resolution — not from `generate_source_groups.py`, which still calls a bare
`datamodel-codegen` off `$PATH`. That difference is the whole point: a bare name
is whatever the machine happens to expose, and on this host it was an unpinned
mise-global `pipx-datamodel-code-generator/0.73.0` shadowing the `==0.72.4` in
`pyproject.toml`. `uv run --project --locked --group codegen` reads the lockfile
and cannot drift.

WHY THIS CONTRACT IS GENERATED AT ALL, since the repo does hand-write some
records. `gates.py` and `review.py` hand-write their JSON because nothing else
parses it back. This one is parsed back by a DIFFERENT surface in a different
language: `kb-session-select` emits it, the `kb-session-review` skill passes it
on, and `session-review.js` re-refuses on its shape. A cross-surface contract
that already wants `schema_version` is exactly where this repo draws the codegen
line — and Ray's directive puts the burden on justifying a hand-written model,
not on justifying generation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

GENERATOR_VERSION = "0.72.4"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "session-select.schema.json"
OUTPUT = ROOT / "python" / "src" / "kb_setup" / "generated" / "session_select.py"
TEMPLATES = ROOT / "schemas" / "templates"
FILE_HEADER = '''# Copyright (c) 2026 Raymond Manaloto
"""Generated session-selection models; edit the schema and rerun the generator."""'''

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
    _canonicalise(output)


#: The repo's OWN formatter, run over the generated file as the last step.
#:
#: WHY THIS EXISTS AND `generate_fetch_receipt.py` HAS NO EQUIVALENT. Two isorts
#: disagree. `datamodel-codegen --formatters isort` emits
#: `from msgspec import UNSET, Meta` on one line and `from msgspec import
#: UnsetType` on the next; hk's ruff merges them into one. So `mise run fmt`
#: rewrote the generated file and the byte-comparison check then reported drift
#: — a gate failing on a file nobody had edited.
#:
#: fetch-receipt has never hit this because it declares no optional field, so it
#: never imports `UnsetType` and the two isorts never disagree about it. That is
#: luck, not design: the same divergence is waiting for the first optional field
#: added to any generated model.
#:
#: Fixed HERE rather than by excluding `generated/**` from hk. Excluding it would
#: settle which formatter owns those bytes by removing the other one, and would
#: silently stop checking a tracked python tree. Running the repo's formatter as
#: the generator's final step makes the two agree by construction — and because
#: the codegen check calls `generate()`, the temp file it compares against gets
#: the identical treatment.
_FORMAT = ("uv", "run", "--project", str(ROOT), "--locked", "ruff")


def _canonicalise(output: Path) -> None:
    """Apply ruff's import sort and format, so hk has nothing left to change."""
    subprocess.run([*_FORMAT, "check", "--select", "I", "--fix", "-q", str(output)], check=False)
    subprocess.run([*_FORMAT, "format", "-q", str(output)], check=True)


if __name__ == "__main__":
    generate()
