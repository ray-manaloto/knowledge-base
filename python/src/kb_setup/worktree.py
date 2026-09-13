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

MECHANISM: copy-on-write, via `clonefile(2)` called directly — NOT symlinks,
NOT `git clone --local`, and NOT `/bin/cp -c`. All three were measured and
rejected:

- a whole-`sources/` symlink shadows the worktree's own committed manifests
  with the donor's, and `git status` reports every tracked file under it as
  DELETED;
- per-clone symlinks preserve the manifests but leave permanently UNTRACKED
  entries — `.gitignore`'s `sources/*/` has a TRAILING SLASH and matches
  directories only, so a symlink (mode 120000) escapes it; `git check-ignore`
  confirms (rc 1 on a clone symlink, rc 0 on a real one);
- `git clone --local` is silently ignored for a shallow source (`depth=1`),
  and 8 of the present clones including `sources/graphify` are shallow;
- `/bin/cp -c` CANNOT FAIL CLOSED, which is the whole reason this module calls
  the syscall instead. Apple's man page: *"if the target filesystem does not
  support cloning, cp will fallback to using copyfile(2) instead to ensure the
  copy still succeeds."* Measured across two real APFS volumes: rc 0, empty
  stderr, and 62,918,656 bytes of real disk consumed — a full physical copy
  reported as success.

FAIL CLOSED, by asking the thing itself. `clonefile(2)` returns `EXDEV` across
volumes and `ENOTSUP` where cloning is unsupported; it never falls back. The
first version of this module tried to reach the same guarantee by parsing
`mount(8)` and requiring both sides to report `apfs`, and a cold review armed
that layer and found it wrong twice over, each way resolving toward PERMIT — a
mountpoint with a SPACE in its name did not match the regex and the lookup then
fell through to `/` (which is `apfs`), and `apfs AND apfs` is not `same volume`
while `clonefile` is single-volume. Both defects are gone with the parser: see
`_clonefile` for the arms.

`shutil` has no `clonefile` binding, so `ctypes` is how the syscall is reached.
Note `cp` on PATH here is this repo's pinned GNU coreutils and has no `-c` flag
at all — a detail that no longer matters to this module and is recorded so the
`/bin/cp` form is not reintroduced as a simplification.

COUNTS ARE NOT QUOTED HERE. An earlier draft said "8 of 97 clones"; the tracked
manifests and the clones actually present are different numbers and both move.
Re-derive: `ls -d sources/*/ | wc -l` against `git ls-files sources/ | wc -l`.

DONOR QUIESCENCE (a requirement an advisor consult named and a first draft of
this spec dropped). `clonefile(2)` can observe a clone while `kb-build` /
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

import ctypes
import ctypes.util
import errno
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import events
from kb_setup.generated.worktree import WorktreeItem, WorktreeItemStatus, WorktreeReadyReport
from kb_setup.result import Err, Ok, Rc, Result, exit_code

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Sequence

#: The clones this repo's own end-to-end tests actually need. A future test
#: needing a third clone adds it here — deliberately not "every clone".
#: Copying every present clone was measured at ~580 s against ~3 s for these
#: two: TIME, dominated by inode count, is the constraint copy-on-write does
#: not remove. Disk is a non-issue either way.
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

_USAGE = "kb-setup worktree-ready [--target PATH]"


def _libc() -> ctypes.CDLL:
    """libSystem, with `clonefile(2)` typed. Module-level so it binds once."""
    lib = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    lib.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
    lib.clonefile.restype = ctypes.c_int
    return lib


_LIBC = _libc()


def _clonefile(src: Path, dst: Path) -> str:
    """Clone `src` to `dst` with `clonefile(2)`. `""` on success, else why not.

    🔴 THIS REPLACED `/bin/cp -c -R`, AND THE REASON IS THE WHOLE POINT OF THE
    CHECK IT DELETED. `cp -c` cannot report that cloning was unavailable —
    Apple's man page: *"if the target filesystem does not support cloning, cp
    will fallback to using copyfile(2) instead to ensure the copy still
    succeeds."* So a design that fails closed cannot be built on `cp -c`'s exit
    code, and the first version of this module tried to compensate by parsing
    `mount(8)` and requiring both sides to be `apfs`. A cold review armed that
    parser and found it wrong in two independent ways, each resolving toward
    PERMIT:

    - a mountpoint containing a SPACE did not match its regex, and the lookup
      then fell through to the longest match that did — always `/`, which is
      `apfs` here. A non-cloneable volume read as cloneable;
    - `apfs AND apfs` is not `same volume`, and `clonefile(2)` is single-volume.
      Measured across two real APFS volumes: `/bin/cp -c` returned rc 0 with
      empty stderr while consuming 62,918,656 bytes — a full physical copy.

    The syscall has neither problem, because it is the thing being asked about
    rather than a proxy for it. Armed both directions on this machine:

    | arm | result |
    |---|---|
    | same volume (control) | rc 0 |
    | across two APFS volumes | **-1 `EXDEV`** |
    | `dst` already exists | **-1 `EEXIST`** |
    | `src` missing | -1 `ENOENT` |

    `EXDEV` is what makes fail-closed true with no filesystem-type check at
    all, and `EEXIST` is load-bearing for a second reason — see
    `_prepare_clone`. It recurses directories including `.git`, which
    `graphify_catalog` requires (armed: a cloned tree's `.git/HEAD` is present).
    """
    ctypes.set_errno(0)
    rc = _LIBC.clonefile(os.fsencode(str(src)), os.fsencode(str(dst)), 0)
    if rc == 0:
        return ""
    code = ctypes.get_errno()
    return f"clonefile({src} -> {dst}) failed: {errno.errorcode.get(code, code)}"


def _run(argv: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _rev_parse(clone: Path) -> str:
    """`clone`'s OWN HEAD, or `""` — never an ancestor repository's answer.

    🔴 `git -C <path> rev-parse HEAD` WALKS UP. Handed a directory that is not
    a repository, it answers with the enclosing worktree's HEAD and reports
    success, so a caller comparing that against a pin gets a confident wrong
    answer about the wrong repository. Armed: `_rev_parse("python/src")`
    returned this checkout's own HEAD.

    That is why `--show-toplevel` is checked first: it is the question "is this
    path a repository root", and only then is HEAD worth reading. A cold review
    found the earlier version deleting a pre-existing directory and blaming a
    donor race that had not happened, on the strength of the walked-up answer.
    """
    top = _run(["git", "-C", str(clone), "rev-parse", "--show-toplevel"])
    if top.returncode != 0 or Path(top.stdout.strip() or "/dev/null").resolve() != clone.resolve():
        return ""
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


#: DELETED, deliberately, and recorded so nobody rebuilds it: `_MOUNT_LINE`,
#: `_best_mount_type`, `_filesystem_type` and `_clonefile_available` used to
#: parse `mount(8)` and require both sides to report `apfs`. That whole layer
#: existed only because `/bin/cp -c` cannot say whether it cloned. Asking
#: `clonefile(2)` directly answers the real question — *can this source be
#: cloned to this destination* — so the proxy, its regex and its two tests are
#: gone rather than fixed. See `_clonefile` for the arms.


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
    if dst.exists() and not (dst.is_dir() and not dst.is_symlink() and (dst / ".git").exists()):
        # Present but NOT a clone — a symlink, a file, or a plain directory an
        # interrupted run left behind. Refuse by name. Falling through to the
        # copy would surface this as a bare `EEXIST`, which is true and tells
        # the reader nothing about what to do; and the version before
        # `clonefile(2)` copied INTO such a directory and then deleted it.
        return Err(
            f"{dst} exists and is not a git clone — remove it by hand and re-run. "
            f"Not touching a path this task did not create",
            rc=Rc.BAD_REQUEST,
        )
    if not dst.exists():
        return None
    head = _rev_parse(dst)
    if pin and head != pin:
        return Err(
            f"{dst} HEAD is {head or 'UNAVAILABLE'}, not the pin {pin} — repair or "
            f"remove it by hand and re-run; not overwriting an existing clone",
            rc=Rc.NOT_RUN,
        )
    return Ok(_item(rel, WorktreeItemStatus.already_present, f"HEAD {head or 'UNAVAILABLE'}"))


def _copy_clone(src: Path, dst: Path, rel: str, pin: str | None) -> Result[WorktreeItem]:
    """Clone `src` onto a `dst` that must NOT already exist.

    Nothing here checks the filesystem first, and that is the design: the
    `clonefile(2)` call IS the check. It returns `EXDEV` across volumes and
    `ENOTSUP` where cloning is unsupported, so there is no path on which this
    silently performs a physical copy — which is precisely what `/bin/cp -c`
    could not promise.

    `EEXIST` is doing a second job. The earlier `cp -R` form, handed a `dst`
    that already existed as a plain directory, copied INTO it and produced
    `dst/<name>/` — after which the pin check read the wrong repository and the
    cleanup deleted a directory this module never created. The syscall refuses
    that case outright, so it cannot arise.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    failure = _clonefile(src, dst)
    if failure:
        return Err(f"copying {rel} failed: {failure}", rc=Rc.NOT_RUN)

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


def _prepare_clone(donor: Path, target: Path, name: str) -> Result[WorktreeItem]:
    rel = f"sources/{name}"
    src, dst = donor / "sources" / name, target / "sources" / name
    if not (src / ".git").exists():
        return Ok(_item(rel, WorktreeItemStatus.skipped, "donor has no such clone"))

    pin = _pinned_commit(target, name)
    existing = _reuse_existing_clone(dst, rel, pin)
    if existing is not None:
        return existing
    return _copy_clone(src, dst, rel, pin)


def _prepare_graph_file(donor: Path, target: Path, rel: str) -> Result[WorktreeItem]:
    """Clone one graph file, then prove the copy is the size the donor was.

    A clone has no pin to check it against, so the quiescence guarantee the
    clones get cannot be had here — but the asymmetry was total until a cold
    review named it, and a `kb-build` writing `graph.json` mid-copy yields a
    truncated file that the `already-present` branch then certifies on every
    later run. Comparing the size against the donor AFTER the copy catches the
    torn case cheaply; it is weaker than a pin and is stated as such rather
    than left to look like the clones' check.
    """
    src, dst = donor / rel, target / rel
    if not src.is_file():
        return Ok(_item(rel, WorktreeItemStatus.skipped, "donor has no such file"))
    if dst.is_file() and not dst.is_symlink():
        return Ok(_item(rel, WorktreeItemStatus.already_present))
    dst.parent.mkdir(parents=True, exist_ok=True)
    before = src.stat().st_size
    failure = _clonefile(src, dst)
    if failure:
        return Err(f"copying {rel} failed: {failure}", rc=Rc.NOT_RUN)
    copied, after = dst.stat().st_size, src.stat().st_size
    if copied != before or copied != after:
        dst.unlink(missing_ok=True)
        return Err(
            f"{rel} copied {copied} bytes; the donor read {before} before and {after} "
            f"after — it was being written during the copy. Removed the torn copy "
            f"rather than leaving it to be reported already-present forever",
            rc=Rc.NOT_RUN,
        )
    return Ok(_item(rel, WorktreeItemStatus.created, f"{copied} bytes"))


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

    # Running from a SUBDIRECTORY of a worktree used to refuse with "not a
    # registered linked worktree", which is false — you are inside one, just
    # not standing at its root. `git` already answers this; ask it rather than
    # requiring the caller to `cd` first.
    top = _run(["git", "-C", str(target), "rev-parse", "--show-toplevel"])
    if top.returncode == 0 and top.stdout.strip():
        target = Path(top.stdout.strip()).resolve()

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
    missing_clones = [n for n in REQUIRED_CLONES if n not in clones_present]
    missing_files = [p for p in REQUIRED_GRAPH_FILES if p not in files_present]

    # 🔴 REQUIRED means required. This refused only when EVERYTHING was absent
    # until a cold review armed it: a donor with the graph files but neither
    # clone returned `Ok`, printed two `skipped` rows and exited 0 — declaring
    # a worktree ready in which both tests this module exists to fix still
    # fail. `skipped` is a real status and it is the right ROW; what was wrong
    # is that no skipped REQUIRED item reached the exit code.
    if missing_clones or missing_files:
        return Err(
            f"donor {donor} is missing required material — "
            f"clones {missing_clones or 'none'} of "
            f"{len(REQUIRED_CLONES)} examined ({', '.join(REQUIRED_CLONES)}); "
            f"graph files {missing_files or 'none'} of "
            f"{len(REQUIRED_GRAPH_FILES)} examined ({', '.join(REQUIRED_GRAPH_FILES)}). "
            f"Run `mise run kb-build` in the donor, then re-run this",
            rc=Rc.NOT_RUN,
        )

    items: list[WorktreeItem] = []
    for name in REQUIRED_CLONES:
        result = _prepare_clone(donor, target, name)
        if not isinstance(result, Ok):
            return result
        items.append(result.value)

    (target / "graphify-out").mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_GRAPH_FILES:
        result = _prepare_graph_file(donor, target, rel)
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
