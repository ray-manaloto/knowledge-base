# Copyright (c) 2026 Raymond Manaloto
"""`kb-worktree-ready` — make a fresh `git worktree` usable (S0).

WHY THIS EXISTS, measured 2026-09-13. A fresh worktree of this repo arrives
with ZERO `sources/*` clones (gitignored, re-fetched by `kb-build`) and no
`graphify-out/`. Two end-to-end tests therefore fail in every worktree and
pass in the main checkout at the same base:

    tests/test_skillopt_contract.py::test_live_installed_contract_and_repository_are_exact
    tests/test_graphify_catalog.py::test_the_real_repo_agrees_with_its_own_pin

and `kb-query` exits 2 in every worktree (no `graph.json`), so every worktree
lane silently falls back to grepping — this repo's first standing instruction,
broken by construction (#778, out of scope here).

MECHANISM: APFS copy-on-write, via Apple's `/bin/cp -c -R` — NOT symlinks and
NOT `git clone --local`. Both alternatives were measured and rejected:

- a whole-`sources/` symlink shadows the worktree's own committed manifests
  with the donor's, and `git status` reports every tracked file under it as
  DELETED;
- per-clone symlinks preserve the manifests but leave permanently UNTRACKED
  entries — `.gitignore`'s `sources/*/` has a TRAILING SLASH and matches
  directories only, so a symlink (mode 120000) escapes it; `git check-ignore`
  confirms (rc 1 on a clone symlink, rc 0 on a real one);
- `git clone --local` is silently ignored for a shallow source (`depth=1`),
  and 8 of 97 clones including `sources/graphify` are shallow.

`cp` on PATH here is this repo's pinned GNU coreutils and has no `-c` flag —
it must be invoked by absolute path. `shutil` has no `clonefile` binding.

FAIL CLOSED, and NOT by trusting `cp -c`'s own exit code. Apple's own man page
(read this session, contradicting the working assumption `cp -c` errors out):
*"if the target filesystem does not support cloning, cp will fallback to using
copyfile(2) instead to ensure the copy still succeeds."* So `cp -c -R` cannot
fail loudly on an unsupported filesystem — it silently does the 11 GB physical
copy the spec forbids. `_filesystem_type` checks BOTH donor and target are
`apfs` (via `mount(8)`'s own report, the source of truth macOS itself uses)
BEFORE any copy runs, and refuses rather than finding out afterward from how
long it took.

DONOR QUIESCENCE (a requirement an advisor consult named and a first draft of
this spec dropped). `/bin/cp -c -R` can observe a clone while `kb-build` /
`kb-update` mutates it underneath. A torn copy has a HEAD that does not match
the pin, which fails the very test this module exists to fix — and does so
INTERMITTENTLY, reading as flake rather than a missing check. So every copied
clone's HEAD is verified against its manifest's pinned commit immediately
after the copy; a mismatch removes the torn copy and refuses rather than
leaving it in place or retrying silently.

NATIVE MECHANISMS EVALUATED AND REJECTED, recorded so a reviewer applying
`use-tool-builtins.md` does not have to re-derive the answer from the same
file this diff edits:

- `worktree.symlinkDirectories` (`.claude/settings.json`, the same `worktree`
  object `baseRef` lives in) produces exactly the shared-mutable-clone /
  untracked-entry shape rejected above, and cannot serve the two graph FILES
  at all — the setting takes directories.
- The `WorktreeCreate` hook REPLACES Claude's worktree creation rather than
  observing it, any non-zero exit ABORTS creation, and `.worktreeinclude` is
  not processed when it is configured. Reimplementing the harness's
  branch/base behaviour to bolt on a copy step is a bad trade for what a
  post-creation repair step already does.
- `.worktreeinclude` itself is a COPY, not CoW (the full clones plus a
  756.3 MB `graph.json`, physically, per worktree), and only applies to
  worktrees Claude Code itself creates with git — a manual
  `git worktree add` (exactly what a real integration test needs) is
  untouched by it regardless.
- `[deps.uv] auto = true` (`mise.toml`) already runs `uv sync --locked` at the
  cwd before any task body starts, which covers the SAME-checkout case (run
  the task from inside the worktree). This module's own `uv sync --locked` is
  still required for the CROSS-checkout case (`--target`, run from the main
  checkout) — mise would have synced the caller's cwd, not the target.

SCOPE CUT, recorded rather than left implicit. Nothing calls this module
automatically. `Agent(isolation: "worktree")` and `EnterWorktree` both make
worktrees without asking us, so every harness-made worktree is still broken
until this task is run by hand or something is wired to call it — that wiring
is a later unit. In exchange, a refusal always names the remediation command.

RETURN CONTRACT: `Result`/`Ok`/`Err`, converted at the CLI boundary by
`exit_code` — the shape `recall_work.py` and `session_select.py` use, both
cited as this module's house precedent for refusal semantics. `Rc.NOT_RUN`
(127) is reserved for "the question was never actually answered": nothing in
the donor to copy, or the donor moved mid-copy. Asking this command to run
against the MAIN CHECKOUT (there is nothing to prepare — it already has
everything) or against a path that is not a registered worktree of this
repository is `Rc.BAD_REQUEST` (2) — the request itself, not the world, was
wrong.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import events
from kb_setup.generated.worktree import WorktreeItem, WorktreeItemStatus, WorktreeReadyReport
from kb_setup.result import Err, Ok, Rc, Result, exit_code

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Sequence

#: The clones this repo's own end-to-end tests actually need. A future test
#: needing a third clone adds it here — deliberately not "every clone": all 97
#: would be ~580 s / ~100 MB per worktree, and time, not disk, is the
#: constraint CoW does not remove.
REQUIRED_CLONES: tuple[str, ...] = ("skillopt", "graphify")

#: The two graph files `kb-query` and `graphify-catalog` need, relative to a
#: worktree's own `graphify-out/`. NOT the whole tree: `graphify-out/` also
#: holds two TRACKED subdirectories (`memory/`, `graphify-semantic-slice/`)
#: that already exist in a fresh worktree, and a symlinked or wholesale-copied
#: `graphify-out/` would shadow them the same way a whole-`sources/` symlink
#: shadows tracked manifests.
REQUIRED_GRAPH_FILES: tuple[str, ...] = (
    "graphify-out/graph.json",
    "graphify-out/graph-prose.json",
)

_CP = Path("/bin/cp")
"""Apple's `cp`, by absolute path — the pinned GNU coreutils `cp` on PATH here
has no `-c` flag and errors rather than cloning."""

#: `mount(8)`'s own report line: "<device> on <mountpoint> (<type>, ...)".
_MOUNT_LINE = re.compile(r"^.+ on (?P<mount>/\S*) \((?P<type>[^,)]+)[^)]*\)\s*$")

_USAGE = "kb-setup worktree-ready [--target PATH]"


def _run(argv: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _rev_parse(clone: Path) -> str:
    """`git -C clone rev-parse HEAD`, or `""` — never accept stderr as evidence."""
    proc = _run(["git", "-C", str(clone), "rev-parse", "HEAD"])
    return proc.stdout.strip() if proc.returncode == 0 and not proc.stderr else ""


def _registered_worktrees(start: Path) -> list[Path] | None:
    """Every worktree `git` at `start` knows about, main checkout first.

    `None` when `start` is not inside a git repository `git` can inspect —
    distinct from `[]`, which cannot happen (a repo always has at least the
    main worktree). Resolved via `git worktree list --porcelain`, MEASURED
    (this session, both the main checkout and a live linked worktree) to
    return the absolute main-checkout path identically from either vantage
    point — never parsed from `--git-common-dir`.
    """
    proc = _run(["git", "-C", str(start), "worktree", "list", "--porcelain"])
    if proc.returncode != 0:
        return None
    return [
        Path(line[len("worktree ") :]).resolve()
        for line in proc.stdout.splitlines()
        if line.startswith("worktree ")
    ]


def _best_mount_type(mount_output: str, target: str) -> str:
    """Pure: the longest-matching mountpoint's filesystem type for `target`.

    Split from `_filesystem_type` so the matching logic — the part a defect
    would actually live in — is testable against canned `mount(8)` text
    without shelling out, while `_filesystem_type` itself stays a thin,
    untested-by-design wrapper (`probes-need-a-control-arm.md`'s point about a
    mocked subprocess testing the mock does not apply to a PARSER).
    """
    best_mount, best_type = "", ""
    for line in mount_output.splitlines():
        match = _MOUNT_LINE.match(line)
        if not match:
            continue
        mount, fstype = match.group("mount"), match.group("type")
        if (target == mount or target.startswith(mount.rstrip("/") + "/")) and len(mount) > len(
            best_mount
        ):
            best_mount, best_type = mount, fstype
    return best_type


def _filesystem_type(path: Path) -> str:
    """The filesystem type backing `path`, via `mount`'s own report.

    Why not trust `cp -c`'s exit code: Apple's man page says a target
    filesystem that cannot clone makes `cp -c` fall back to `copyfile(2)`
    silently, so `cp` itself cannot tell us clonefile ran. This is the check
    that makes "fail closed if clonefile is unavailable" actually true, by
    asking BEFORE copying rather than trusting the copy's own success.
    """
    proc = _run(["mount"])
    if proc.returncode != 0:
        return ""
    return _best_mount_type(proc.stdout, str(path.resolve()))


def _clonefile_available(donor: Path, target: Path) -> bool:
    return _filesystem_type(donor) == "apfs" and _filesystem_type(target) == "apfs"


def _cow_copy(src: Path, dst: Path) -> str:
    """CoW-copy `src` onto `dst` via `/bin/cp -c -R`. Returns stderr, `""` on success."""
    proc = _run([str(_CP), "-c", "-R", str(src), str(dst)])
    if proc.returncode != 0:
        return proc.stderr.strip() or f"cp -c -R exited {proc.returncode}"
    return ""


def _pinned_commit(target: Path, name: str) -> str | None:
    """The commit `sources/<name>.manifest` pins in `target`'s own tree, or `None`.

    Read from `target`'s tracked manifest rather than a per-clone hardcoded
    constant: both required clones already carry a committed
    `sources/<name>.manifest`, and `manifest.load` is the shared parser
    (`graphify_catalog.pinned_commit` uses the same route) — one source of
    truth instead of two that can drift from each other.
    """
    from kb_setup import manifest

    path = target / "sources" / f"{name}.manifest"
    if not path.is_file():
        return None
    try:
        return manifest.load(path).commit
    except OSError, ValueError:
        return None


def _identity(path: Path) -> str:
    """One-line filesystem identity for a report field — never a published path."""
    try:
        st = path.stat()
    except OSError:
        return "absent"
    return f"{path} ({st.st_size} bytes, mtime {st.st_mtime:.0f})"


def _item(name: str, status: WorktreeItemStatus, detail: str = "") -> WorktreeItem:
    return WorktreeItem(name=name, status=status, detail=detail)


def _reuse_existing_clone(dst: Path, rel: str, pin: str | None) -> Result[WorktreeItem] | None:
    """Reuse `dst` if it is already a real clone, else say so.

    `None` means "not present, go copy it" — the only non-`Result` return in
    this module, deliberately, so the caller's branch reads as "try reuse,
    else copy" rather than a third `Result` state nothing else needs.
    """
    if not (dst.is_dir() and not dst.is_symlink() and (dst / ".git").exists()):
        return None
    head = _rev_parse(dst)
    if pin and head != pin:
        return Err(
            f"{dst} HEAD is {head or 'UNAVAILABLE'}, not the pin {pin} — repair or "
            f"remove it by hand and re-run; not overwriting an existing clone",
            rc=Rc.NOT_RUN,
        )
    return Ok(_item(rel, WorktreeItemStatus.already_present, f"HEAD {head or 'UNAVAILABLE'}"))


def _copy_clone(
    src: Path, dst: Path, rel: str, pin: str | None, *, fs_ok: bool
) -> Result[WorktreeItem]:
    if not fs_ok:
        return Err(
            f"clonefile is unavailable copying {src} to {dst} (not both APFS) — "
            f"refusing to physically copy {rel} rather than silently degrading",
            rc=Rc.NOT_RUN,
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    stderr = _cow_copy(src, dst)
    if stderr:
        return Err(f"copying {rel} failed: {stderr}", rc=Rc.NOT_RUN)

    head = _rev_parse(dst)
    if pin and head != pin:
        import shutil

        shutil.rmtree(dst, ignore_errors=True)
        return Err(
            f"{rel} copy HEAD was {head or 'UNAVAILABLE'}, not the pin {pin} — the donor "
            f"moved during the copy; removed the torn copy rather than leaving it in place",
            rc=Rc.NOT_RUN,
        )
    return Ok(_item(rel, WorktreeItemStatus.created, f"HEAD {head or 'UNAVAILABLE'}"))


def _prepare_clone(donor: Path, target: Path, name: str, *, fs_ok: bool) -> Result[WorktreeItem]:
    rel = f"sources/{name}"
    src, dst = donor / "sources" / name, target / "sources" / name
    if not (src / ".git").exists():
        return Ok(_item(rel, WorktreeItemStatus.skipped, "donor has no such clone"))

    pin = _pinned_commit(target, name)
    existing = _reuse_existing_clone(dst, rel, pin)
    if existing is not None:
        return existing
    return _copy_clone(src, dst, rel, pin, fs_ok=fs_ok)


def _prepare_graph_file(
    donor: Path, target: Path, rel: str, *, fs_ok: bool
) -> Result[WorktreeItem]:
    src, dst = donor / rel, target / rel
    if not src.is_file():
        return Ok(_item(rel, WorktreeItemStatus.skipped, "donor has no such file"))
    if dst.is_file() and not dst.is_symlink():
        return Ok(_item(rel, WorktreeItemStatus.already_present))
    if not fs_ok:
        return Err(
            f"clonefile is unavailable between {donor} and {target} (not both APFS) — "
            f"refusing to physically copy {rel} rather than silently degrading",
            rc=Rc.NOT_RUN,
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    stderr = _cow_copy(src, dst)
    if stderr:
        return Err(f"copying {rel} failed: {stderr}", rc=Rc.NOT_RUN)
    return Ok(_item(rel, WorktreeItemStatus.created))


def _uv_sync(target: Path) -> Err | None:
    """`uv sync --locked` in `target`.

    Never sets `UV_CACHE_DIR` — an explicitly supplied one is honoured by
    inheriting the ambient environment unchanged; none is silently invented.
    """
    proc = _run(["uv", "sync", "--locked"], cwd=target)
    if proc.returncode != 0:
        return Err(
            f"uv sync --locked failed in {target} (rc={proc.returncode}): {proc.stderr.strip()}",
            rc=Rc.NOT_RUN,
        )
    return None


def _resolve_target_and_donor(target: Path, donor: Path | None) -> Result[tuple[Path, Path]]:
    """Validate `target` is a registered LINKED worktree; resolve `donor`.

    One `Err` for both disqualifying cases (target IS the main checkout;
    target is not registered at all) — they are both `Rc.BAD_REQUEST` for the
    same reason ("the request itself was wrong"), and merging them is what
    keeps this module's return-statement count under `PLR0911`'s limit
    without hiding either message.
    """
    worktrees = _registered_worktrees(target)
    if not worktrees:
        return Err(f"{target} is not inside a git repository `git` can inspect", rc=Rc.BAD_REQUEST)
    main_checkout = worktrees[0]
    resolved_donor = donor.resolve() if donor is not None else main_checkout

    if target == main_checkout:
        return Err(
            f"{target} is the main checkout, not a linked worktree — it already has "
            f"everything a worktree needs. Run this from inside a linked worktree, or pass "
            f"--target <worktree path>",
            rc=Rc.BAD_REQUEST,
        )
    if target not in worktrees:
        return Err(
            f"{target} is not a registered linked worktree of this repository "
            f"(`git worktree list --porcelain` does not name it) — refusing to touch it",
            rc=Rc.BAD_REQUEST,
        )
    return Ok((target, resolved_donor))


def _prepare_all_items(donor: Path, target: Path) -> Result[list[WorktreeItem]]:
    """Every required clone, then every required graph file — Err short-circuits."""
    clones_present = [n for n in REQUIRED_CLONES if (donor / "sources" / n / ".git").exists()]
    files_present = [p for p in REQUIRED_GRAPH_FILES if (donor / p).is_file()]
    if not clones_present and not files_present:
        return Err(
            f"donor {donor} has none of the required clones or graph files — "
            f"examined {len(REQUIRED_CLONES)} clone(s): {', '.join(REQUIRED_CLONES)}; "
            f"examined {len(REQUIRED_GRAPH_FILES)} graph file(s): "
            f"{', '.join(REQUIRED_GRAPH_FILES)}",
            rc=Rc.NOT_RUN,
        )

    fs_ok = _clonefile_available(donor, target)
    items: list[WorktreeItem] = []
    for name in REQUIRED_CLONES:
        result = _prepare_clone(donor, target, name, fs_ok=fs_ok)
        if not isinstance(result, Ok):
            return result
        items.append(result.value)

    (target / "graphify-out").mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_GRAPH_FILES:
        result = _prepare_graph_file(donor, target, rel, fs_ok=fs_ok)
        if not isinstance(result, Ok):
            return result
        items.append(result.value)
    return Ok(items)


def prepare_existing(
    target: Path,
    donor: Path | None = None,
    *,
    sync: Callable[[Path], Err | None] | None = None,
) -> Result[WorktreeReadyReport]:
    """Make `target` — an EXISTING, registered linked worktree — usable.

    `sync` is an injectable seam, on `graphify_catalog.check`'s `authority`
    precedent (its docstring: "the real one is a module literal ... so a test
    fixture ... would drift against it unconditionally"): a real `uv sync
    --locked` needs a real uv project, and the tests here build a bare git
    fixture to exercise the copy/pin logic, not a full Python project. `None`
    (the default, at every real invocation) resolves to the module's own
    `_uv_sync` at CALL time rather than being bound into the signature, so a
    test can monkeypatch `worktree._uv_sync` and have callers that pass
    nothing pick it up.

    Repair is canonical (rather than create-then-repair) because the harness
    makes worktrees without asking us; a create-only entry point is
    unreachable in exactly the case that matters. Idempotent: re-running on an
    already-prepared worktree reports every row `already-present` and touches
    nothing.
    """
    sync = sync if sync is not None else _uv_sync
    resolved = _resolve_target_and_donor(target.resolve(), donor)
    if not isinstance(resolved, Ok):
        return resolved
    target, donor = resolved.value

    items_result = _prepare_all_items(donor, target)
    if not isinstance(items_result, Ok):
        return items_result

    refusal = sync(target)
    if refusal is not None:
        return refusal

    report = WorktreeReadyReport(
        schema_version=1,
        target=str(target),
        donor=str(donor),
        donor_graph=_identity(donor / "graphify-out" / "graph.json"),
        items=items_result.value,
    )
    return Ok(report)


def add(name: str, base: str) -> Result[WorktreeReadyReport]:
    """Create a new worktree `.claude/worktrees/<name>` off `base`, then prepare it.

    The base-commit invariant: resolve `base` to an OID ONCE, pass that OID to
    `git worktree add`, verify the new HEAD equals it immediately. Never
    `wt HEAD == main HEAD` — that is false for every legitimate feature-branch
    worktree.
    """
    worktrees = _registered_worktrees(Path.cwd())
    if not worktrees:
        return Err("not inside a git repository `git` can inspect", rc=Rc.BAD_REQUEST)
    donor = worktrees[0]

    oid_proc = _run(["git", "-C", str(donor), "rev-parse", "--verify", f"{base}^{{commit}}"])
    if oid_proc.returncode != 0 or not oid_proc.stdout.strip():
        return Err(f"cannot resolve base ref {base!r} to a commit", rc=Rc.BAD_REQUEST)
    oid = oid_proc.stdout.strip()

    target = donor / ".claude" / "worktrees" / name
    add_proc = _run(["git", "-C", str(donor), "worktree", "add", "-b", name, str(target), oid])
    if add_proc.returncode != 0:
        return Err(
            f"git worktree add failed (rc={add_proc.returncode}): {add_proc.stderr.strip()}",
            rc=Rc.NOT_RUN,
        )

    head = _rev_parse(target)
    if head != oid:
        return Err(
            f"new worktree HEAD is {head or 'UNAVAILABLE'}, not the resolved base {oid} — "
            f"the base-commit invariant was violated",
            rc=Rc.NOT_RUN,
        )
    return prepare_existing(target, donor=donor)


def render_summary(report: WorktreeReadyReport) -> str:
    """The stdout summary: donor identity, then one line per item."""
    lines = [
        f"[worktree-ready] {report.target}",
        f"  donor: {report.donor}",
        f"  donor graph: {report.donor_graph}",
    ]
    lines.extend(
        f"  {item.name:<28} {item.status.value:<16} {item.detail}" for item in report.items
    )
    return "\n".join(lines)


def parse(argv: Sequence[str]) -> Result[Path | None]:
    """`[--target PATH]`. No target means "the worktree I am standing in"."""
    target: Path | None = None
    pending = list(argv)
    while pending:
        item = pending.pop(0)
        if item == "--target":
            if not pending or pending[0].startswith("-"):
                return Err(f"--target needs a value (usage: {_USAGE})", rc=Rc.BAD_REQUEST)
            target = Path(pending.pop(0))
        else:
            return Err(f"unknown argument: {item} (usage: {_USAGE})", rc=Rc.BAD_REQUEST)
    return Ok(target)


def main(repo_root: Path, argv: Sequence[str] = ()) -> int:
    """`kb-setup worktree-ready [--target PATH]`.

    `repo_root` is `Path.cwd()` (`cli.py`'s dispatch convention) and doubles as
    the default target: a mise task's `dir` defaults to `{{ config_root }}`, so
    running this task from inside a worktree gives `cwd` = that worktree's
    root, and the same-checkout path resolves correctly with no flag.
    `--target` exists for the cross-checkout case.
    """
    parsed = parse(argv)
    if not isinstance(parsed, Ok):
        events.warn("worktree.refused", f"[worktree-ready] refusing — {parsed.message}")
        return exit_code(parsed)

    target = parsed.value if parsed.value is not None else repo_root
    result = prepare_existing(target)
    if not isinstance(result, Ok):
        events.warn("worktree.not_run", f"[worktree-ready] {result.message}")
        return exit_code(result)

    report = result.value
    events.say(
        "worktree.ready",
        render_summary(report),
        target=report.target,
        donor=report.donor,
    )
    return int(Rc.OK)
