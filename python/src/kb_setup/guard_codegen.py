# Copyright (c) 2026 Raymond Manaloto
"""`kb-guard-codegen` / `kb-guard-codegen-check` — schema-owned guard policy (G02, #755).

`.claude/mods/kb-settings-guard/hooks/protected-paths.ts` used to be a file whose
own header called itself generated while nothing generated it — the drift gate
it named did not exist. This module makes `schemas/guard-policy.schema.json` the
single authority and generates BOTH consumers from it: the Python enum
`kb_setup.generated.guard_policy.ProtectedPathSuffix` (via the ordinary
`[tool.datamodel-codegen]` batch — see `regenerate`) and the TypeScript literal
`register.ts` imports (via :func:`render_typescript`, since datamodel-codegen has
no TypeScript target).

**Three drift shapes, three different checkers — see :func:`check`.** The
native `datamodel-codegen --all-jobs --check` catches a generated Python file
that differs from its schema, and a generated Python file that was DELETED
(`MISSING: … file does not exist but should be generated`). Measured this
session, three-armed against the real tree: it does **not** catch a STALE EXTRA
generated-looking file left behind after a job is renamed or removed — a planted
`orphan_stale.py` carrying the generated-provenance header returned rc **0**.
This module adds that third check, and adds the cross-language check native
datamodel-codegen cannot do at all: does the committed `.ts` array still match
what the schema renders?

🔴 **`mise run kb-guard-codegen-check` must be HERMETIC** — no credentials, no
network, no shelling to `claude`/`codex` — so it can be reached transitively
through `pytest` (via `tests/test_guard_codegen.py`), which is in `GATE_TASKS`
and must run on a machine with no Claude credentials at all. It is deliberately
**not** added to `GATE_TASKS` itself: `kb-guard-inventory-check` set this
precedent (`gates.py` names it explicitly as OUT of that tuple, enforced
transitively through its own test module instead), and this ticket follows it
rather than expanding that tuple.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

from kb_setup.result import Rc

#: The one schema authority.
SCHEMA_PATH = Path("schemas/guard-policy.schema.json")

#: The generated TypeScript consumer `register.ts` imports.
TS_OUTPUT_PATH = Path(".claude/mods/kb-settings-guard/hooks/protected-paths.ts")

#: Where every `[tool.datamodel-codegen.jobs.*]` Python output lands. Scanned
#: for STALE EXTRAS — see `_stale_generated_files`.
GENERATED_DIR = Path("python/src/kb_setup/generated")

#: Every committed job's `custom-file-header` starts this way (verified against
#: all ten jobs in `pyproject.toml`), so a file opening with this exact text is
#: claiming to be generated output, whether or not any job still names it.
_GENERATED_MARKER_PREFIX = '# Copyright (c) 2026 Raymond Manaloto\n"""Generated'

_CODEGEN_ARGV = (
    "uv",
    "run",
    "--project",
    "{root}",
    "--no-sync",
    "--locked",
    "--group",
    "codegen",
    "datamodel-codegen",
)


def render_typescript(schema_path: Path) -> str:
    """Render the `.ts` artifact `register.ts` imports, from the schema's `enum`.

    The header is fixed, deterministic text — the schema's OWN repo-relative
    path (`SCHEMA_PATH`, a module constant, never derived from `schema_path`'s
    own string form) and the two task names that regenerate/check it. No
    absolute path, hostname, timestamp, or version string: any of those would
    make the rendered bytes machine-dependent and turn the drift check this
    function backs into a false positive on every other checkout.

    Keeps EXACTLY the shape already measured as loader-safe: `export const
    PROTECTED_SUFFIXES: readonly string[] = [...]` — no TS `enum`, no `as
    const`, no default export, no type-only export (`register.ts`'s own
    loader-constraints comment; each of those is an unprobed loader shape and
    the loader's failure mode is silent).
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    suffixes = schema["enum"]
    lines = [
        "// GENERATED — do not hand-edit.",
        "//",
        f"// Source: {SCHEMA_PATH.as_posix()}",
        "// Regenerate: mise run kb-guard-codegen",
        "// Drift check: mise run kb-guard-codegen-check",
        "//",
        "// A `.json` file cannot be used here: the hooks-module loader compiles every",
        "// import as TypeScript, so importing `./protected-paths.json` fails with",
        "// `does not parse: Unexpected token (1:13)`. A relative `.ts` import works,",
        "// which is why this file is TypeScript holding data.",
        "//",
        "// Ruled by Ray 2026-09-11 (grilling Q3): the settings pair PLUS the guard's",
        "// own machinery, because a lane that can edit `mise.toml` neuters every",
        "// `kb-*` guard task just as surely as one that edits `settings.json`.",
        "",
        "export const PROTECTED_SUFFIXES: readonly string[] = [",
    ]
    lines.extend(f"  {json.dumps(value)}," for value in suffixes)
    lines.append("];")
    return "\n".join(lines) + "\n"


def _run_native(repo_root: Path, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    """Invoke the SAME locked, pinned `datamodel-codegen` `test_codegen.py` uses.

    `--locked` refuses to run against anything but the resolved, pinned
    generator — no `$PATH`-shadowed binary, no drift against `uv.lock`.

    🔴 **`--no-sync` is load-bearing, not an optimisation.** `check()` can be
    called with a `repo_root` that shares this project's `.venv` but is not
    this project's own directory (a temp copy in a test, a worktree, a linked
    checkout). Measured this session: `uv run --project <other-dir>` WITHOUT
    `--no-sync` rebuilds and reinstalls the shared venv's `kb-setup` editable
    package pointing at `<other-dir>/python/src` — corrupting every OTHER
    process's `import kb_setup` in that same venv until something re-syncs it
    back. Two-armed: without the flag, `.venv/lib/…/_editable_impl_kb_setup.pth`
    flips to the other project's path; with it, the file is untouched.
    """
    argv = [arg.format(root=str(repo_root)) for arg in _CODEGEN_ARGV]
    return subprocess.run(
        [*argv, *extra_args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _expected_generated_outputs(repo_root: Path) -> set[Path]:
    """Every `[tool.datamodel-codegen.jobs.*].output`, read from the job table.

    C3: a second hard-coded list of generated paths is the exact defect this
    module exists to close, so nothing here names a path directly — every
    expected output is DERIVED from `pyproject.toml`.
    """
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    jobs = pyproject.get("tool", {}).get("datamodel-codegen", {}).get("jobs", {})
    outputs: set[Path] = set()
    for job in jobs.values():
        output = job.get("output")
        if isinstance(output, str):
            outputs.add((repo_root / output).resolve())
    return outputs


def _stale_generated_files(repo_root: Path) -> list[Path]:
    """Generated-provenance-marked files under `GENERATED_DIR` no job names.

    Keyed on the marker, never on "any file present that no job names": that
    is what lets `__init__.py` and `__pycache__/` sit in the same directory
    without tripping this check.
    """
    generated_dir = repo_root / GENERATED_DIR
    if not generated_dir.is_dir():
        return []
    expected = _expected_generated_outputs(repo_root)
    stale: list[Path] = []
    for candidate in sorted(generated_dir.glob("*.py")):
        resolved = candidate.resolve()
        if resolved in expected:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if text.startswith(_GENERATED_MARKER_PREFIX):
            stale.append(candidate)
    return stale


def check(repo_root: Path) -> Rc:
    """The drift gate. Detects all three shapes documented in the module docstring."""
    native = _run_native(repo_root, ["--all-jobs", "--check"])
    if native.returncode != 0:
        print("[guard-codegen-check] native `datamodel-codegen --all-jobs --check` found drift:")
        print(native.stdout + native.stderr)
        return Rc.FINDINGS

    stale = _stale_generated_files(repo_root)
    if stale:
        for path in stale:
            rel = path.relative_to(repo_root)
            print(f"[guard-codegen-check] STALE GENERATED FILE, named by no codegen job: {rel}")
        return Rc.FINDINGS

    schema_path = repo_root / SCHEMA_PATH
    ts_path = repo_root / TS_OUTPUT_PATH
    try:
        committed = ts_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[guard-codegen-check] cannot read {TS_OUTPUT_PATH}: {exc}")
        return Rc.NOT_RUN
    rendered = render_typescript(schema_path)
    if rendered != committed:
        print(
            f"[guard-codegen-check] {TS_OUTPUT_PATH} does not match what "
            f"{SCHEMA_PATH} renders — run `mise run kb-guard-codegen`"
        )
        return Rc.FINDINGS

    print(
        "[guard-codegen-check] clean: the schema, the generated Python enum, and the "
        "generated TS array all agree, and no stale generated file survives."
    )
    return Rc.OK


def regenerate(repo_root: Path) -> Rc:
    """Regenerate every `[tool.datamodel-codegen]` job, then the TS artifact.

    Wraps the native generator rather than duplicating it (C2): the Python side
    of `guard-policy` regenerates through the SAME `--all-jobs` batch every
    other schema uses, and only the TypeScript side is this module's own,
    because datamodel-codegen has no TypeScript target.
    """
    native = _run_native(repo_root, ["--all-jobs"])
    if native.returncode != 0:
        print("[guard-codegen] native `datamodel-codegen --all-jobs` failed:")
        print(native.stdout + native.stderr)
        return Rc.NOT_RUN

    schema_path = repo_root / SCHEMA_PATH
    ts_path = repo_root / TS_OUTPUT_PATH
    ts_path.write_text(render_typescript(schema_path), encoding="utf-8")
    print(f"[guard-codegen] regenerated {TS_OUTPUT_PATH} from {SCHEMA_PATH}")
    return Rc.OK


def regenerate_main(repo_root: Path) -> int:
    """CLI entry point for `mise run kb-guard-codegen`."""
    return int(regenerate(repo_root))


def check_main(repo_root: Path) -> int:
    """CLI entry point for `mise run kb-guard-codegen-check`."""
    return int(check(repo_root))
