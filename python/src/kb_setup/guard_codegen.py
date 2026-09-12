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

🔴 **This module shipped in `688b6470` proving the three artifacts AGREE, and
that is true and insufficient** — a cold review of that commit found it reports
clean when the policy is emptied at its source, when the only consumer of the
generated artifact is deleted or silently disconnected, and when a schema edit
desynchronises the TS header's hand-copied rationale. `check()` now closes each
of those, on top of the original three:

1. native `datamodel-codegen --all-jobs --check` — a generated Python file that
   differs from its schema, or was deleted;
2. `_stale_generated_files` — a STALE EXTRA generated-looking file left behind
   after a job is renamed or removed (native `--check` provably misses this,
   measured three-armed against the real tree: rc **0** over a planted
   `orphan_stale.py` carrying the generated-provenance header);
3. the committed `.ts` array vs. what the schema renders — the one comparison
   native datamodel-codegen cannot do at all, having no TypeScript target;
4. a FLOOR on the policy's own size — an emptied or shrunk `enum` reports clean
   under checks 1-3 alone, since an empty enum is still internally consistent;
5. the TS header's hardcoded rationale sentence vs. the schema's live
   `description` — the two can desynchronise silently the moment either is
   edited alone;
6. whether `register.ts` still IMPORTS **and USES** the generated policy inside
   `isProtectedPath` — the schema can render a perfectly self-consistent
   artifact with zero live readers.

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
import re
import subprocess
import tomllib
from pathlib import Path

from kb_setup import guard_inventory
from kb_setup.result import Rc

#: The one schema authority.
SCHEMA_PATH = Path("schemas/guard-policy.schema.json")

#: The generated TypeScript consumer `register.ts` imports.
TS_OUTPUT_PATH = Path(".claude/mods/kb-settings-guard/hooks/protected-paths.ts")

#: Where every `[tool.datamodel-codegen.jobs.*]` Python output lands. Scanned
#: for STALE EXTRAS — see `_stale_generated_files`.
GENERATED_DIR = Path("python/src/kb_setup/generated")

#: 🔴 **Two axes, not one (F5).** Every committed job's `custom-file-header`
#: opens `# Copyright (c) <year> Raymond Manaloto\n"""Generated`, so a file
#: matching only the copyright line, or only a loose "generated" substring,
#: is the wrong test in OPPOSITE directions: the year rolls over on schedule
#: (making a bare year-pinned literal a check that can only pass, forever,
#: past the next copyright bump), while `python/src/kb_setup/generated/__init__.py`
#: — tracked, hand-authored, legitimately living in `GENERATED_DIR` — opens
#: `"""Schema-generated runtime contracts."""`, eight characters away from the
#: real marker's `"""Generated`. A marker loosened to ignore the year OR
#: widened to match any "generated" substring flags that file permanently.
#: Match BOTH: any four-digit year, AND a docstring opening EXACTLY
#: `"""Generated` (not `"""Schema-generated`).
_GENERATED_MARKER_RE = re.compile(r'\A# Copyright \(c\) \d{4} Raymond Manaloto\n"""Generated')

#: The floor `check()` enforces on the schema's own `enum` (F2). Independent of
#: today's actual count (nine, after this change) — this is the minimum below
#: which the policy is not doing its job at all, not a ceiling that must track
#: every future addition. Set to the five original settings/machinery paths
#: (`.claude/settings.json`, `.claude/settings.local.json`, `mise.toml`,
#: `hk.pkl`, `python/src/kb_setup/hook_guard.py`) that this guard existed to
#: protect before this ticket ever ran.
_MINIMUM_PROTECTED_PATHS = 5

#: F6: the TS header hardcodes this sentence as comment lines
#: (`render_typescript`, below) rather than deriving it from the schema, so an
#: editor of the schema's `description` alone can desynchronise the two
#: headers silently. This is the anchor `check()` looks for INSIDE the live
#: schema description — verified present in `schemas/guard-policy.schema.json`
#: today; its disappearance means the schema changed and the TS header did not.
_TS_RATIONALE_ANCHOR = (
    "own machinery, because a lane that can edit `mise.toml` neuters every "
    "`kb-*` guard task just as surely as one that edits `settings.json`."
)

#: F1: `register.ts` must both IMPORT and USE the generated policy inside
#: `isProtectedPath` — an import with no live use, or a use with no import (a
#: commented-out import; `register.ts:17-19` documents that a loader failure
#: here is SILENT), both leave the schema with zero live readers. Comments are
#: stripped before either regex runs, via `guard_inventory.strip_ts_comments`
#: — reused, not duplicated (C2/C7): its own comment already states that a
#: presence check over raw text is wrong in both directions.
_TS_IMPORT_RE = re.compile(
    r'import\s*\{\s*PROTECTED_SUFFIXES\s*\}\s*from\s*"\./protected-paths"\s*;'
)
_IS_PROTECTED_PATH_FN_RE = re.compile(
    r"export\s+function\s+isProtectedPath\s*\([^)]*\)\s*:\s*boolean\s*\{(?P<body>.*?)\n\}",
    re.DOTALL,
)

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
    """Invoke the pinned `datamodel-codegen` `test_codegen.py` also uses.

    🔴 **Neither `--locked` nor `--group codegen` constrains what actually runs
    here — restated after the first version of this docstring's claim did not
    reproduce (F7).** `--no-sync` (below) means uv performs NO resolution at
    all: four arms on this tree showed `--group <nonexistent>` runs identically
    whether or not `--no-sync` is present, and `--locked` behaves the same way
    — under `--no-sync` both flags are pure documentation of *intent*, inert in
    practice. **What actually constrains the invocation is the state of
    `.venv` at call time** — whichever `datamodel-codegen` that environment
    already has installed is what runs, `--locked`/`--group` or not. Kept
    anyway: they document the intended contract for a human reading this call,
    and cost nothing under `--no-sync`.

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


#: F3: markers a native `--all-jobs --check` run ACTUALLY EXECUTED its
#: comparison, rather than failed to launch at all (a bad `--project` path, an
#: unresolvable environment). Measured this session: a genuine drift report
#: opens either a unified diff (`--- <path>`) or a `MISSING: <path> (file does
#: not exist but should be generated)` line; a launch failure is a bare
#: `uv`-level `error: ...` line with neither shape.
_NATIVE_CHECK_RAN_MARKERS = ("--- ", "MISSING: ")


def _native_check_ran(native_output: str) -> bool:
    """Did the native `--check` run actually EXECUTE its comparison?

    `check()` must not conflate "ran and found drift" with "could not run at
    all" — the FIRST is real drift and belongs at `Rc.FINDINGS`; the SECOND is
    a tooling failure and belongs at `Rc.NOT_RUN`, exactly like `regenerate`'s
    own native-failure branch already does. Mislabelling the second as the
    first is the inversion this function exists to prevent (F3).
    """
    return any(marker in native_output for marker in _NATIVE_CHECK_RAN_MARKERS)


def _ts_rationale_is_current(schema_description: str) -> bool:
    """Does the schema's description still carry the TS header's rationale (F6)?

    `render_typescript` copies this rationale into TS comment syntax rather
    than deriving it, because a schema `description` is prose while a TS
    comment block is line-wrapped — there is no lossless one-way render for
    arbitrary prose that also has to stay loader-safe. This function is the
    gate's side of that trade: it does not re-derive the TS text, it detects
    when the two have DIVERGED, which is the failure mode a hardcoded copy
    actually has.
    """
    return _TS_RATIONALE_ANCHOR in schema_description


def _register_ts_consumes_policy(source: str) -> bool:
    """Does `register.ts` both IMPORT and USE the generated policy (F1)?

    Comments stripped, inside `isProtectedPath`. Neither half alone is
    sufficient — armed both ways this session:

    - the import commented out: the module then fails to load at all, SILENTLY
      (`register.ts:17-19`); a raw-text presence check reads the commented
      line and calls it clean;
    - the import intact but `isProtectedPath`'s body swapped for a literal
      array: TypeScript tolerates the now-unused import and the module loads
      fine, so an import-only check passes over a guard that protects nothing
      the schema actually names.

    Comment-stripping reuses `guard_inventory.strip_ts_comments` rather than a
    second TS parser (C2/C7) — its own comment already states that a presence
    check over raw text is wrong in both directions, which is exactly the
    defect an import-only or use-only check would repeat.
    """
    stripped = guard_inventory.strip_ts_comments(source)
    if _TS_IMPORT_RE.search(stripped) is None:
        return False
    match = _IS_PROTECTED_PATH_FN_RE.search(stripped)
    if match is None:
        return False
    body = match.group("body")
    return "PROTECTED_SUFFIXES" in body and ".some(" in body


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

    🔴 **Recurses (F4).** `__pycache__` is the only subdirectory under
    `GENERATED_DIR` today and holds no `.py`, so this changes no verdict on
    the committed tree — but a stale generated file one directory down used to
    be invisible to `glob("*.py")`, the one check this module adds over the
    native one.
    """
    generated_dir = repo_root / GENERATED_DIR
    if not generated_dir.is_dir():
        return []
    expected = _expected_generated_outputs(repo_root)
    stale: list[Path] = []
    for candidate in sorted(generated_dir.rglob("*.py")):
        resolved = candidate.resolve()
        if resolved in expected:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if _GENERATED_MARKER_RE.match(text) is not None:
            stale.append(candidate)
    return stale


def _check_floor(schema: dict) -> Rc | None:
    """F2: the policy must not be empty or shrunk below its floor."""
    enum_values = schema.get("enum", [])
    if len(enum_values) < _MINIMUM_PROTECTED_PATHS:
        print(
            f"[guard-codegen-check] {SCHEMA_PATH} has only {len(enum_values)} "
            f"entries, below the floor of {_MINIMUM_PROTECTED_PATHS} — a lane "
            "emptied or shrank the guard policy"
        )
        return Rc.FINDINGS
    return None


def _check_rationale(schema: dict) -> Rc | None:
    """F6: the schema's description must still carry the TS header's rationale."""
    if not _ts_rationale_is_current(schema.get("description", "")):
        print(
            f"[guard-codegen-check] {SCHEMA_PATH}'s description no longer carries "
            "the rationale render_typescript hardcodes as TS comment lines — "
            "update render_typescript to match the schema's current description"
        )
        return Rc.FINDINGS
    return None


def _check_native(repo_root: Path) -> Rc | None:
    """Native `--all-jobs --check`, discriminated from a launch failure (F3).

    Catches a generated Python file that differs from its schema, or was
    deleted.
    """
    native = _run_native(repo_root, ["--all-jobs", "--check"])
    if native.returncode == 0:
        return None
    combined = native.stdout + native.stderr
    if not _native_check_ran(combined):
        print(
            "[guard-codegen-check] native `datamodel-codegen --all-jobs --check` "
            "could not run at all (not drift — a launch/environment failure):"
        )
        print(combined)
        return Rc.NOT_RUN
    print("[guard-codegen-check] native `datamodel-codegen --all-jobs --check` found drift:")
    print(combined)
    return Rc.FINDINGS


def _check_stale(repo_root: Path) -> Rc | None:
    """The third drift shape native `--check` cannot see: a stale extra file (F4/F5)."""
    stale = _stale_generated_files(repo_root)
    if stale:
        for path in stale:
            rel = path.relative_to(repo_root)
            print(f"[guard-codegen-check] STALE GENERATED FILE, named by no codegen job: {rel}")
        return Rc.FINDINGS
    return None


def _check_ts_array(repo_root: Path, schema_path: Path) -> Rc | None:
    """The one comparison native datamodel-codegen cannot do: schema vs. committed TS."""
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
    return None


def _check_consumer(repo_root: Path) -> Rc | None:
    """F1: `register.ts` must still import and use the generated policy."""
    register_path = repo_root / guard_inventory.FUNCTION_HOOK_SOURCE_PATH
    try:
        register_source = register_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"[guard-codegen-check] cannot read {guard_inventory.FUNCTION_HOOK_SOURCE_PATH}: {exc}"
        )
        return Rc.NOT_RUN
    if not _register_ts_consumes_policy(register_source):
        print(
            f"[guard-codegen-check] {guard_inventory.FUNCTION_HOOK_SOURCE_PATH} no longer "
            "imports and uses PROTECTED_SUFFIXES inside isProtectedPath — the generated "
            "policy has no live consumer"
        )
        return Rc.FINDINGS
    return None


def check(repo_root: Path) -> Rc:
    """The drift gate. Detects every shape documented in the module docstring.

    Each shape is its own predicate (`_check_*`, above), returning `Rc | None`
    — `None` means that shape passed. This is factored out of one long
    function so each check is independently readable and testable, not to
    hide branches: every one of them still runs, in the same order, on every
    call.
    """
    schema_path = repo_root / SCHEMA_PATH
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # LAZY thunks, not eager values: each `_check_*` can be expensive (a
    # subprocess launch) or assume an earlier check already passed (the
    # native/stale/ts-array/consumer checks all assume a real repo tree), so
    # short-circuiting on the first failure is load-bearing, not an
    # optimisation.
    steps = (
        lambda: _check_floor(schema),
        lambda: _check_rationale(schema),
        lambda: _check_native(repo_root),
        lambda: _check_stale(repo_root),
        lambda: _check_ts_array(repo_root, schema_path),
        lambda: _check_consumer(repo_root),
    )
    for step in steps:
        result = step()
        if result is not None:
            return result

    print(
        "[guard-codegen-check] clean: the schema, the generated Python enum, and the "
        "generated TS array all agree, the policy meets its floor, the TS rationale "
        "matches the schema, no stale generated file survives, and register.ts still "
        "consumes the generated policy."
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
