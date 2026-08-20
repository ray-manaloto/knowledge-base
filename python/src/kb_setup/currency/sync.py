# Copyright (c) 2026 Raymond Manaloto
"""Step 1 — is the tool we RUN the tool we PINNED, and did it build our artifacts?

This is the genuinely new check. Version *bumps* are already covered (Renovate,
`mise outdated --bump`); what nothing covered until now is the quieter question:
the pin says 0.9.25, but which binary does a shell actually reach, which version
built `graphify-out/`, and does the source manifest describe that same release?

It found a live defect the day it was written: `MISE_ENV_CACHE=1` had baked a
stale `.../installs/pipx-graphifyy/0.9.23/bin` into PATH *ahead* of the mise
shims, so every bare `graphify` call ran 0.9.23 under a 0.9.25 pin.

The DEFAULT path is offline and subprocess-free by design — the SessionStart
hook runs it on every session, so it must cost milliseconds, not seconds. Two
opt-in exceptions, never reached from the hook: `observed_version` (executes
`--version`, used only when STAMPING a build) and `check_sync(deep=True)` (one
`mise where`, so the extras probe can locate an install reached via a shim).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import build_outcome
from kb_setup.currency import _proc

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

OK = "ok"
DRIFT = "drift"
SKIP = "skip"  # nothing configured to check — genuinely not applicable
# Configured, but this run could not read it. Split out of SKIP because the two
# are opposites for an unattended decision: "no manifest is declared" means there
# is nothing to disagree with, while "the install path is not resolvable here"
# means the check that WOULD have disagreed never ran. Collapsing them let a bump
# auto-apply on a host that had verified almost nothing — the absence-of-evidence
# trap (`probes-need-a-control-arm.md`), one status wide.
BLIND = "blind"

# v1: version only · v2: single artifact_fingerprint · v3: artifact_fingerprints
# map covering the primary graph AND the generated outputs (wiki/graphml/svg/…).
_STAMP_VERSION = 3
_SCAN_WINDOW = 4096
# Streamed rather than slurped: an extraction chunk can run to tens of megabytes,
# and the digest is the same either way. 1 MiB is well past the point where the
# read syscall stops dominating.
_DIGEST_CHUNK = 1 << 20
#: Recorded in place of a digest for an input that exists but cannot be read.
#: Deliberately not a valid `sha256:` value, so no comparison can mistake it for
#: one — it means "this input was never verified", which is a third answer beside
#: agreed and disagreed.
UNREADABLE = "unreadable"
# A SHA-shaped VALUE is required, so a node merely NAMED "built_at_commit"
# cannot masquerade as the metadata key.
_COMMIT_RE = re.compile(rb'"built_at_commit"\s*:\s*"([0-9a-fA-F]{7,40})"')


@dataclass(frozen=True)
class Finding:
    """One check's outcome. `status` is OK / DRIFT / SKIP / BLIND; `detail` is the evidence."""

    check: str
    status: str
    detail: str


@dataclass(frozen=True)
class SyncStatus:
    """Every step-1 finding for one tool, plus the versions the checks resolved."""

    tool: str
    pinned: str
    resolved: str
    findings: tuple[Finding, ...]

    @property
    def drifted(self) -> tuple[Finding, ...]:
        """Findings that actively disagree — the only ones worth interrupting for."""
        return tuple(f for f in self.findings if f.status == DRIFT)

    @property
    def ok(self) -> bool:
        """True when nothing drifted. SKIPs do not make a run red."""
        return not self.drifted

    @property
    def blind(self) -> tuple[Finding, ...]:
        """Checks that were configured but could not be read on this run.

        Not red — a blind check has found nothing wrong — but it is the exact
        opposite of consent, so `decide._gate_sync` refuses to auto-apply while
        any of these is present.
        """
        return tuple(f for f in self.findings if f.status == BLIND)

    @property
    def verified(self) -> bool:
        """True when at least one check actually ran and agreed.

        A run of nothing-but-SKIPs is not a pass. Distinguishing it is the whole
        point of the three-state model: without this, a foreign platform rendered
        as `graphify : in sync` — the green wording, an empty version, and not a
        single check performed.
        """
        return any(f.status == OK for f in self.findings)

    def summary(self) -> str:
        """One line, suitable for a hook nudge or a landing-page row."""
        if self.drifted:
            first = self.drifted[0]
            extra = f" (+{len(self.drifted) - 1} more)" if len(self.drifted) > 1 else ""
            return f"{self.tool}: {first.check} — {first.detail}{extra}"
        if not self.verified:
            reason = self.findings[0].detail if self.findings else "no checks configured"
            return f"{self.tool}: not verifiable here — {reason}"
        return f"{self.tool} {self.pinned}: in sync"


# ---------------------------------------------------------------- mise pin ----


def _tools_table(repo_root: Path) -> dict[str, object]:
    path = repo_root / "mise.toml"
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    return tools if isinstance(tools, dict) else {}


def pinned_version(repo_root: Path, spec: ToolSpec) -> tuple[str, tuple[str, ...]]:
    """The pinned version and declared extras for `spec` from `mise.toml`.

    A pin is either a bare string or a table (`{ version = ..., extras = [...] }`);
    both forms are live in these repos, so both are read here.
    """
    if spec.python_package:
        return _python_project_pin(
            repo_root,
            spec.python_package,
            spec.python_project_dir,
            github=spec.github,
        )
    entry = _tools_table(repo_root).get(spec.mise_key)
    if isinstance(entry, str):
        return entry, ()
    if isinstance(entry, dict):
        version = str(entry.get("version") or "")
        raw = entry.get("extras", [])
        extras = tuple(str(e) for e in raw) if isinstance(raw, list) else ()
        return version, extras
    return "", ()


def _python_project_pin(
    repo_root: Path, package: str, project_dir: str = "", *, github: str = ""
) -> tuple[str, tuple[str, ...]]:
    """Read one exact PEP 508 dependency from the project's exported runtime set."""
    relative = Path(project_dir or ".")
    if relative.is_absolute() or ".." in relative.parts:
        return "", ()
    pyproject = repo_root / relative / "pyproject.toml"
    try:
        with pyproject.open("rb") as handle:
            project = tomllib.load(handle).get("project", {})
    except OSError, tomllib.TOMLDecodeError:
        return "", ()
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    version_pattern = re.compile(
        rf"{re.escape(package)}(?:\[([^]]+)\])?==([0-9]+(?:\.[0-9]+)+)",
        re.IGNORECASE,
    )
    vcs_pattern = re.compile(
        rf"{re.escape(package)}(?:\[([^]]+)\])?\s*@\s*"
        r"git\+https://github\.com/([^@\s]+)@([0-9a-f]{40})",
        re.IGNORECASE,
    )
    matches: list[tuple[str, tuple[str, ...]]] = []
    for requirement in dependencies if isinstance(dependencies, list) else []:
        version_match = version_pattern.fullmatch(str(requirement))
        vcs_match = vcs_pattern.fullmatch(str(requirement))
        if version_match:
            extras = tuple(
                part.strip() for part in (version_match.group(1) or "").split(",") if part
            )
            matches.append((version_match.group(2), extras))
        elif vcs_match and (not github or vcs_match.group(2).lower() == github.lower()):
            extras = tuple(part.strip() for part in (vcs_match.group(1) or "").split(",") if part)
            matches.append((vcs_match.group(3), extras))
    if len(matches) == 1:
        return matches[0]
    return "", ()


# ------------------------------------------------------- resolved version ----


def resolve_from_path(binary: str) -> tuple[str, str]:
    """What a bare `binary` call reaches, as (version, how) — without executing it.

    Three cases, all free:

    * a mise **shim** — mise resolves the pin itself at call time, so the version
      is correct by construction (given cwd is the project, which it is for every
      caller here). Returns ("", "shim").
    * a mise **install dir** — the version is a path segment
      (`.../installs/pipx-graphifyy/0.9.23/bin/graphify`), so it is readable
      directly. This is the case that catches the stale-PATH bug.
    * anything else — a homebrew/system/pipx copy shadowing mise entirely, which
      is drift regardless of what version it happens to be.

    Executing `--version` would be authoritative but costs ~0.4s of interpreter
    startup; that belongs in a deep check, not in a per-session hook.
    """
    found = shutil.which(binary)
    if not found:
        return "", "absent"
    # Deliberately NOT resolve(): a mise shim is a symlink to the `mise` binary
    # itself, so following it turns `.../shims/graphify` into `.../bin/mise` and
    # destroys the one fact this function exists to read. Caught by the control
    # arm on 2026-07-23 — the clean-PATH case reported "outside mise".
    resolved = Path(found).absolute()
    parts = resolved.parts
    if _is_mise_shim(resolved):
        return "", "shim"
    if "installs" in parts:
        # rindex, not index: a path can contain an earlier directory called
        # `installs` (a cache root, a nested checkout), and taking the first
        # match reads the "version" from the wrong segment entirely.
        idx = len(parts) - 1 - parts[::-1].index("installs")
        # .../installs/<backend-tool>/<version>/... — the version is two along.
        if len(parts) > idx + 2:
            return parts[idx + 2], "install-dir"
    return "", f"outside-mise:{found}"


def _mise_shim_dirs() -> tuple[Path, ...]:
    """Directories that are genuinely mise's shims, honouring MISE_DATA_DIR."""
    roots = []
    data_dir = os.environ.get("MISE_DATA_DIR")
    if data_dir:
        roots.append(Path(data_dir).expanduser() / "shims")
    roots.append(Path.home() / ".local" / "share" / "mise" / "shims")
    return tuple(roots)


def _is_mise_shim(resolved: Path) -> bool:
    """Whether `resolved` sits in MISE's shim dir — not merely in some `shims/`.

    pyenv, asdf and rbenv all use a directory called `shims`, so a bare segment
    test hands them a free pass: the caller then reports the PIN as the resolved
    version, a value nothing ever read from the binary. That is the same
    false-green this module exists to catch.
    """
    return any(resolved.is_relative_to(root) for root in _mise_shim_dirs())


def observed_version(
    binary: str,
    pattern: str = "",
    version_args: tuple[str, ...] = ("--version",),
) -> str:
    """Execute a tool's declared version command, or return ``""`` on failure.

    This is the authoritative reading, used when STAMPING a build — where the
    honest answer is "whatever actually ran", not "whatever the pin says". A
    build that silently ran a stale binary must stamp the stale version, or the
    stamp launders the very drift it exists to expose.

    `pattern` is a regex whose first group is the version. Without it the
    fallback is the last whitespace field, which is right for the conventional
    `<name> <version>` output and WRONG for anything richer: `mise --version`
    prints ``2026.7.15 macos-arm64 (2026-07-27)``, so the heuristic returned the
    build date. A tool whose output is not two fields must declare a pattern.

    Cost, measured 2026-07-27: ``mise --version`` 11.4 ms, ``graphify --version``
    50.6 ms — the latter is Python interpreter startup, which is why `check_sync`
    stays away from this for mise-managed tools. 11 ms is affordable in a
    per-session hook, which is what lets a self-managed tool be checked there.
    """
    found = shutil.which(binary)
    if not found:
        return ""
    try:
        res = subprocess.run(
            [found, *version_args], capture_output=True, text=True, check=False, timeout=30
        )
    except OSError, subprocess.TimeoutExpired:
        return ""
    if res.returncode != 0:
        return ""
    text = (res.stdout or res.stderr).strip()
    if pattern:
        match = re.search(pattern, text)
        # A pattern that does not match returns "" — the caller renders that as
        # "could not read", never as agreement. Silently falling back to the
        # last-field heuristic here would hide a stale pattern behind a
        # plausible-looking version.
        return match.group(1).lstrip("v") if match else ""
    parts = text.split()
    return parts[-1].lstrip("v") if parts else ""


# -------------------------------------------------------------- the stamp ----


def stamp_path(repo_root: Path, spec: ToolSpec) -> Path | None:
    """Absolute path of this tool's build stamp, or None when it declares none."""
    return repo_root / spec.stamp if spec.stamp else None


def artifact_fingerprints(repo_root: Path, spec: ToolSpec) -> dict[str, str]:
    """`{relpath: fingerprint}` for every declared output that currently exists.

    Keyed by the config-relative path (not absolute) so the stamp is portable
    across clones. A declared-but-absent output is simply omitted here; the
    identity check treats it as "regenerate pending" rather than silently
    passing, because a missing generated output IS drift the moment it is
    declared.
    """
    prints: dict[str, str] = {}
    for rel in spec.all_artifacts:
        fp = artifact_fingerprint(repo_root / rel)
        if fp:
            prints[rel] = fp
    return prints


def input_fingerprint(path: Path) -> str:
    """A CONTENT identity for one committed input: `sha256:<hex>`, or "" if unreadable.

    Deliberately NOT `artifact_fingerprint`'s `size:mtime_ns`. That stat is right
    for outputs and measured wrong for inputs: three ordinary git operations that
    leave the bytes identical — `git checkout --` of a reverted edit, a
    round-trip through a branch touching `sources/`, and a stash+pop — move the
    mtime on every affected file, so it fires on the whole class and cannot
    discriminate at all (eight-row table in
    `docs/research/reports/2026-07-31-size-mtime-false-drift.md`).

    Digesting is affordable *here* and not there: the inputs are 2.4 MB against
    the outputs' 341 MB — 142x — and sha256 over the input set measured 1.8 ms,
    best of 5. `git hash-object` was checked as the tool built-in first and is
    ~480x slower on this corpus (subprocess start-up dominates a 2.4 MB hash), so
    in-process `hashlib` wins; that is recorded so nobody re-runs the comparison.
    """
    try:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            while chunk := fh.read(_DIGEST_CHUNK):
                digest.update(chunk)
    except OSError:
        return ""
    return f"sha256:{digest.hexdigest()}"


def input_fingerprints(repo_root: Path, spec: ToolSpec) -> dict[str, str]:
    """`{relpath: sha256}` over every file matched by this tool's `inputs` globs.

    Keyed by the repo-relative POSIX path so the map is portable across clones and
    across platforms, and sorted so two builds of the same tree write byte-identical
    maps — a stamp that reordered itself would look like drift to any diff.

    An unreadable match is recorded as :data:`UNREADABLE`, never omitted and never
    "". Both alternatives were wrong, in opposite directions, and the omission
    shipped before the cold lane reproduced it end to end:

    * `""` would make one unreadable file compare EQUAL to a *different*
      unreadable file.
    * Omitting the key looked safe — a previously-readable file that goes
      unreadable does surface, as a removed path — but a file that is **new AND
      unreadable** is absent from the live map *and* from the recorded one, so
      `staleness._diff`'s `set(recorded) | set(live)` union never sees it and the
      check returns OK. An input nobody could read, reported as verified.

    The sentinel is not a digest and must never be treated as one: `check_inputs`
    short-circuits to *not verifiable* on seeing it, which is the honest answer.
    """
    prints: dict[str, str] = {}
    for pattern in spec.inputs:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file():
                continue
            prints[path.relative_to(repo_root).as_posix()] = input_fingerprint(path) or UNREADABLE
    return dict(sorted(prints.items()))


def stamped_input_fingerprints(stamp: Mapping[str, object]) -> dict[str, str] | None:
    """The recorded input map, or None when this stamp does not carry one.

    None and `{}` are different answers and the caller depends on it: None means
    "written by an engine that predates input fingerprinting, so the question was
    never asked" (⇒ *not verifiable*), while `{}` means "asked, and this tool
    declares no inputs" (⇒ nothing to compare). Collapsing them would render a
    stamp that never recorded anything as a clean pass.
    """
    if "input_fingerprints" not in stamp:
        return None
    raw = stamp.get("input_fingerprints")
    if not isinstance(raw, dict):
        return None
    return {str(k): str(v) for k, v in raw.items()}


def write_stamp(
    repo_root: Path,
    spec: ToolSpec,
    *,
    version: str,
    source_ref: str = "",
    inputs: Mapping[str, str] | None = None,
) -> Path:
    """Record which version built the artifacts, next to them.

    graphify does not stamp its own output — `export.to_json()` writes only
    `built_at_commit`, and `graph.json` has no version field at all (verified
    against 0.9.25 source). So "which version built this graph?" is unanswerable
    from the artifact, and this sidecar is the answer. Written by the build task,
    never by a check.

    Fingerprints the PRIMARY graph and every declared generated output, so step 1
    catches a stale wiki/svg/GRAPH_REPORT.md the same way it catches a stale
    graph — Ray's "in sync with the graph AND generated outputs".

    `inputs` is the committed-input digest map, and this function **never computes
    it**. Only a real build has standing to say what the graph was built from, so
    the caller supplies it (`graph._stamp_build` passes `input_fingerprints(...)`)
    and `None` OMITS the key entirely. Making that the signature rather than a
    convention is deliberate: a default that read the live tree would let
    `restamp_artifacts` — which regenerates derived views and never re-reads
    `sources/` — silently adopt whatever the inputs say *now* as what the graph
    was built from, laundering the exact drift this records. Same reasoning that
    keeps `version` carried forward rather than re-observed.

    `None` is also distinct from `{}`: absent means "this stamp never recorded
    inputs" (⇒ *not verifiable*), empty means "recorded, and there were none".
    """
    path = stamp_path(repo_root, spec)
    if path is None:
        raise ValueError(f"{spec.name}: no `stamp` path configured in currency.toml")
    artifact = repo_root / spec.artifact if spec.artifact else None
    # BEFORE the new fingerprints are taken, because `view_records` decides
    # "was this view just regenerated?" by diffing against what the PREVIOUS
    # stamp recorded. Reading it after would compare the map to itself.
    #
    # Unlike `inputs`, this is computed here rather than supplied by the caller,
    # and the asymmetry is the point. `inputs` answers "what was the graph built
    # FROM", which only a real build has standing to state — so a default that
    # read the live tree would launder drift. This answers "did these bytes move
    # since we last looked", which is a pure observation of what is on disk: any
    # writer may make it, and every writer must, or the one that forgot leaves a
    # view permanently claiming the graph it no longer describes.
    previous_views = stamped_views(read_stamp(repo_root, spec))
    payload = {
        "stamp_version": _STAMP_VERSION,
        "tool": spec.name,
        "version": version,
        "source_ref": source_ref,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "artifact_commit": _artifact_commit(artifact),
        "artifact_fingerprints": artifact_fingerprints(repo_root, spec),
        "views": view_records(repo_root, spec, previous_views),
    }
    if inputs is not None:
        payload["input_fingerprints"] = {str(k): str(v) for k, v in inputs.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def restamp_artifacts(
    repo_root: Path, spec: ToolSpec, *, views_before: Mapping[str, str] | None = None
) -> Path | None:
    """Refresh only the fingerprints after `kb-artifacts` regenerated outputs.

    `views_before` is the caller's `view_identities` snapshot from before it
    started working; a view may only be certified against the current graph when
    its identity changed inside that bracket. Omitting it is the safe default and
    means "I cannot say what I regenerated", which records unknown provenance
    rather than a guess. See `view_records` for the false pass that made the
    snapshot necessary.

    The derived outputs (wiki/svg/…) are generated FROM graph.json AFTER the
    build, so at build time they either don't exist or are stale. `kb-artifacts`
    calls this once it has regenerated them, updating the fingerprint map while
    preserving the version and source_ref the build recorded — those describe who
    built the GRAPH, which regenerating a derived view does not change. Returns
    None when there is no stamp to refresh (the build must run first).
    """
    path = stamp_path(repo_root, spec)
    if path is None or not path.exists():
        return None
    existing = read_stamp(repo_root, spec)
    written = write_stamp(
        repo_root,
        spec,
        version=str(existing.get("version", "")),
        source_ref=str(existing.get("source_ref", "")),
        # Carried forward verbatim, INCLUDING the None that means "this stamp
        # never recorded inputs". `kb-artifacts` reads graph.json and writes
        # derived views; it never reads `sources/`, so it has no standing to
        # restate what the graph was built from. Coercing None to `{}` here would
        # be the subtle wrong move: it turns "never recorded" into "recorded, and
        # there were none", which the staleness check reads as a clean pass.
        inputs=stamped_input_fingerprints(existing),
    )
    if views_before is not None and written is not None:
        _certify_views(repo_root, spec, written, views_before)
    return written


def _certify_views(
    repo_root: Path, spec: ToolSpec, stamp_file: Path, views_before: Mapping[str, str]
) -> None:
    """Re-derive the just-written stamp's `views` against the caller's snapshot.

    A SECOND write of a ~1 KB file rather than a sixth parameter on `write_stamp`,
    which 25 call sites reach and whose signature is already at its argument
    budget. The ordering that costs nothing to get right: the intermediate state
    is the UNBRACKETED map, so a process killed between the two writes leaves
    views reading *provenance unknown* — conservative, never a false pass.

    `view_records` rather than a local loop, so the one place that decides what a
    view record contains stays one place — including which of the three outcomes
    a given view earns.
    """
    try:
        payload = json.loads(stamp_file.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    payload["views"] = view_records(
        repo_root, spec, stamped_views(payload), observed_before=views_before
    )
    stamp_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _artifact_commit(artifact: Path | None) -> str:
    """`built_at_commit` from a graphify graph.json, or "" when unavailable.

    Read with a bounded scan rather than json.load: these graphs run to hundreds
    of megabytes and a session-start hook must not parse one.

    The pattern requires a SHA-SHAPED VALUE, not just the token. A bare
    `rfind(b'"built_at_commit"')` matches a node *named* `built_at_commit` just as
    readily as the real metadata key — and this corpus ingests graphify's own
    source, which contains that identifier. It would then partition on the next
    unrelated `:` and return confident nonsense. Both ends of the file are checked
    because "metadata last" is graphify's convention, not a guarantee.
    """
    if artifact is None or not artifact.exists():
        return ""
    try:
        size = artifact.stat().st_size
        with artifact.open("rb") as fh:
            fh.seek(max(0, size - _SCAN_WINDOW))
            window = fh.read()
            if not _COMMIT_RE.search(window):
                fh.seek(0)
                window = fh.read(_SCAN_WINDOW)
    except OSError:
        return ""
    matches = _COMMIT_RE.findall(window)
    return matches[-1].decode("utf-8", "replace") if matches else ""


def artifact_fingerprint(artifact: Path | None) -> str:
    """A cheap identity for the artifact's CONTENT state: `<size>:<mtime_ns>`.

    `built_at_commit` cannot do this job. It is the git HEAD at build time
    (graphify's `export.to_json` calls `_git_head()`), so every rebuild at the
    same commit writes the identical value — and rebuilding repeatedly at one
    commit is the normal development rhythm. The "rebuilt outside the build task"
    detector was therefore almost never able to fire, while claiming it could.

    A stat rather than a digest: these graphs are hundreds of megabytes and this
    runs in a per-session hook.
    """
    if artifact is None or not artifact.exists():
        return ""
    try:
        st = artifact.stat()
    except OSError:
        return ""
    return f"{st.st_size}:{st.st_mtime_ns}"


def deep_artifact_fingerprint(artifact: Path) -> str:
    """A CONTENT-sensitive identity for one declared output, or "" when unreadable.

    `artifact_fingerprint` is the right answer on the check path and the wrong one
    here, for DIRECTORIES specifically. It stats the directory, and a directory's
    mtime moves only when an ENTRY IS ADDED OR REMOVED — measured: rewriting a
    file in place does not move it, adding one does. So a `wiki/` regeneration
    that rewrote the same 9,465 page names would be invisible to it, and this
    function's caller would conclude the view had NOT been regenerated when it
    just had. The live tree shows the same gap from the other side: `wiki/`'s
    newest FILE is 79 microseconds newer than the directory itself.

    Hence `<entries>:<newest_mtime_ns>` for a directory, which moves for both an
    in-place rewrite and an added/removed page. It costs a full walk — 35.6-63.3 ms
    over the live `wiki/` — which is why it is deliberately NOT used by
    `artifact_fingerprint`'s callers on the ~10 ms SessionStart path. This one runs
    at STAMP time, immediately after an operation that took minutes.
    """
    if not artifact.exists():
        return ""
    if not artifact.is_dir():
        return artifact_fingerprint(artifact)
    entries = 0
    try:
        newest = artifact.stat().st_mtime_ns
        for entry in artifact.rglob("*"):
            entries += 1
            newest = max(newest, entry.stat().st_mtime_ns)
    except OSError:
        return ""
    return f"{entries}:{newest}"


def view_identities(repo_root: Path, spec: ToolSpec) -> dict[str, str]:
    """`{relpath: deep fingerprint}` for every declared derived view that exists NOW.

    A caller takes one of these BEFORE it starts work and hands it back to
    `view_records` afterwards, which is what turns "these bytes differ from the
    last stamp" into "these bytes changed DURING this operation". Those are not
    the same claim, and `view_records` documents what it cost to learn that.
    """
    return {
        rel: fp
        for rel in spec.artifacts
        if rel != spec.artifact and (fp := deep_artifact_fingerprint(repo_root / rel))
    }


def view_records(
    repo_root: Path,
    spec: ToolSpec,
    previous: Mapping[str, Mapping[str, str]] | None,
    *,
    observed_before: Mapping[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Which graph each declared derived view was last observed to be generated FROM.

    The fact `size:mtime_ns` alone can never carry (#182). A view that is stale
    *because nothing regenerated it* never moves, so the fingerprint map reads OK
    for it forever — measured on the live corpus, where `graph.graphml` and
    `wiki/` reported `recorded == live` while describing a graph 11 hours old.

    Two fields per view, and both are needed:

    * `identity` — the view's own `deep_artifact_fingerprint` when last observed.
      Its ONLY job is to answer "did this view change since the last stamp?", which
      is how a regeneration is detected without any caller having to declare one.
    * `graph` — the primary artifact's fingerprint at the moment the view was last
      observed to change. This is what the check compares against.

    `observed_before` is the caller's snapshot of those identities from BEFORE it
    started, and it is what makes the `graph` field earnable. A view may only be
    certified against the current graph when its identity changed *between that
    snapshot and now* — i.e. this operation is the one that regenerated it.

    **The version without the snapshot was unsound, and a cold review caught it.**
    It certified any view whose identity merely differed from the last STAMP, on
    the reasoning that a changed view must have just been regenerated. That
    inference has a hole with a real trigger, because `refresh_after_regen` is
    best-effort and swallows its own failures:

        kb-artifacts regenerates the views, its restamp fails silently
        -> the stamp still describes the OLD views
        kb-merge rewrites graph.json and restamps
        -> the views differ from the stamp, so all three were certified
           against a graph they PREDATE.  Reproduced end to end; `check_views`
           returned OK.

    A snapshot closes it because it brackets one operation rather than an
    unbounded gap. It also subsumes the boolean flag it replaces — a full
    `kb-artifacts`, a partial `kb-artifacts only=[graphml]`, a `kb-label` (which
    regenerates `GRAPH_REPORT.md` and nothing else) and a `kb-merge` (which
    regenerates none) all fall out of the same comparison, with nothing
    enumerated anywhere and no caller asserting more than it did.

    **What the bracket does NOT close, stated rather than left to be rediscovered.**
    It bounds one PROCESS, not the file. `primary_fp` is read when `view_records`
    runs, so if another `kb-*` operation rewrites `graph.json` after a view was
    regenerated inside this bracket but before this line, the view is certified
    against a graph it was never generated from. Nothing in `kb_setup` locks —
    `grep -rnE "FileLock|flock|fcntl" python/src/kb_setup/` returns nothing — and
    this repo's workflow is single-agent and serialized through `kb-*` tasks
    (`mise-tasks-only.md`), which is a convention rather than an enforcement.
    Reported by the cold lane, round 2, correctly rated narrow. Tracked rather
    than fixed here: a lock is a different change with its own failure modes, and
    inventing one inside a review round is how a narrow gap becomes a wide one.

    Three outcomes per view, and only the first is a certification:

    * changed within the bracket -> the current graph fingerprint;
    * unchanged since the stamp  -> carry the recorded fingerprint forward;
    * anything else — first sighting, or changed outside any bracket — `""`,
      which the check reads as *not verifiable*. "This file exists" is not
      evidence about which graph produced it.
    """
    known = dict(previous or {})
    before = observed_before or {}
    primary_fp = artifact_fingerprint(repo_root / spec.artifact) if spec.artifact else ""
    records: dict[str, dict[str, str]] = {}
    for rel in spec.artifacts:
        if rel == spec.artifact:
            # A config may legally list the graph in both `artifact` and
            # `artifacts` (`all_artifacts` de-duplicates it). "The graph was
            # generated from the graph" is not a view record.
            continue
        identity = deep_artifact_fingerprint(repo_root / rel)
        if not identity:
            # Absent or unreadable. Dropped rather than carried: a stale record
            # for a file that is gone would later be compared against a
            # regenerated one and silently pass.
            continue
        was = known.get(rel)
        if observed_before is not None and before.get(rel, "") != identity:
            # Changed while this caller was working. `observed_before is not None`
            # rather than a truthiness test on `before`: an EMPTY snapshot is a
            # real answer — no view existed when the caller started — and a view
            # that exists now therefore changed within the bracket. Collapsing
            # empty-to-absent would silently withhold certification from the
            # first `kb-artifacts` run in a fresh clone, which is the bootstrap
            # case this whole field exists to make one run long.
            graph_fp = primary_fp
        elif was is not None and str(was.get("identity", "")) == identity:
            graph_fp = str(was.get("graph", ""))
        else:
            graph_fp = ""
        records[rel] = {"identity": identity, "graph": graph_fp}
    return records


def stamped_views(stamp: Mapping[str, object]) -> dict[str, dict[str, str]] | None:
    """The recorded view-provenance map, or None when this stamp does not carry one.

    None and `{}` are different answers, exactly as in
    `stamped_input_fingerprints`: None means "this stamp carries no usable view
    provenance" — the key is absent, or present and corrupt — while `{}` means
    "asked, and this tool declares no derived views".

    **What collapsing them costs is the MESSAGE, not the verdict**, and that
    correction is owed to a mutation arm. An earlier draft of this docstring
    claimed collapsing them "would render every pre-#182 stamp a clean pass"; the
    arm that mutates this `return None` to `return {}` SURVIVED, and tracing it
    showed why the claim was false — with `{}` every view falls through to
    *provenance unknown* and `check_views` returns NOT_VERIFIABLE anyway, while
    `write_stamp` does `dict(previous or {})` and cannot tell them apart at all.
    So the distinction earns its place by telling a reader to run `kb-artifacts`
    rather than leaving them to infer it from three per-view lines — which is
    what `views.check_views` now says, and what its test now asserts, so the
    mutant dies on the difference that actually exists rather than on one that
    was only ever written down.

    Deliberately NOT gated on `_STAMP_VERSION`. A v3 stamp genuinely does prove
    what it claims — that every declared output matches what was fingerprinted —
    and bumping the version would report it as DRIFT whose remedy is a full
    `kb-build`, tens of minutes, to acquire a field a `kb-artifacts` run fills in.
    """
    if "views" not in stamp:
        return None
    raw = stamp.get("views")
    if not isinstance(raw, dict):
        return None
    out: dict[str, dict[str, str]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = {str(k): str(v) for k, v in value.items()}
    return out


def read_stamp(repo_root: Path, spec: ToolSpec) -> dict[str, object]:
    """The recorded stamp, or an empty dict when absent/unreadable.

    Values are NOT string-coerced: the stamp now carries a nested
    `artifact_fingerprints` map, and flattening it to `str(dict)` would make it
    unreadable on the way back in. Callers `str(...)` the scalar fields they use.
    """
    path = stamp_path(repo_root, spec)
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    return {str(k): v for k, v in data.items()} if isinstance(data, dict) else {}


def stamped_fingerprints(stamp: dict[str, object]) -> dict[str, str]:
    """The `{relpath: fingerprint}` map from a stamp, defended against bad shapes.

    A stamp hand-edited or written by an older engine may carry a non-dict here;
    that must read as "no fingerprints recorded" (⇒ the identity check reports
    a re-stamp is due), never raise.
    """
    raw = stamp.get("artifact_fingerprints")
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


#: Length of a full git object id — what `rev-list -n1` must return for the
#: answer to be a resolved commit rather than an error string.
_SHA_LEN = 40


# ------------------------------------------------------------ the manifest ----


def manifest_ref(repo_root: Path, spec: ToolSpec) -> str:
    """The `ref =` line of this tool's source manifest, or "" when it has none."""
    if not spec.manifest:
        return ""
    path = repo_root / spec.manifest
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("ref") and "=" in line:
            return line.partition("=")[2].strip()
    return ""


# ----------------------------------------------------------------- checks ----


def _check_resolution(repo_root: Path, spec: ToolSpec, pinned: str) -> tuple[Finding, str]:
    if spec.python_package:
        return _check_python_resolution(repo_root, spec, pinned)
    resolved, how = resolve_from_path(spec.binary)
    if how == "shim":
        return (
            Finding("resolution", OK, "resolves through the mise shim (pin applied at call time)"),
            pinned,
        )
    if how == "absent":
        # DRIFT, not SKIP. `applies_here()` has already answered "should this tool
        # exist on this host?" — so once we are past that, a missing binary is a
        # fact about the install, not something we were unable to check. Reporting
        # it as SKIP made a fresh clone (or a failed `mise install`) read as
        # "graphify 0.9.25: in sync" while there was no binary at all.
        return (
            Finding("resolution", DRIFT, f"{spec.binary} is not installed on this host"),
            "",
        )
    if how.startswith("outside-mise"):
        return (
            Finding(
                "resolution",
                DRIFT,
                f"{spec.binary} resolves outside mise: {how.split(':', 1)[1]}",
            ),
            "",
        )
    if resolved != pinned:
        return (
            Finding(
                "resolution",
                DRIFT,
                f"PATH reaches {resolved} but the pin is {pinned} "
                f"(a stale install dir is ahead of the mise shims)",
            ),
            resolved,
        )
    return Finding("resolution", OK, f"PATH reaches the pinned {resolved}"), resolved


def _check_python_resolution(
    repo_root: Path,
    spec: ToolSpec,
    pinned: str,
) -> tuple[Finding, str]:
    """Compare the locked project executable with its exact pyproject pin."""
    executable = repo_root / (spec.python_project_dir or ".") / ".venv" / "bin" / spec.binary
    if not executable.is_file():
        return Finding("resolution", DRIFT, f"{executable} is missing; run `mise deps`"), ""
    if re.fullmatch(r"[0-9a-f]{40}", pinned):
        observed = _installed_direct_url_commit(repo_root, spec)
        if observed != pinned:
            return (
                Finding(
                    "resolution",
                    DRIFT,
                    f"{spec.python_package} direct_url records {observed or 'UNKNOWN'} "
                    f"but pyproject pins {pinned}",
                ),
                observed,
            )
        return Finding("resolution", OK, f"locked uv environment runs {pinned[:12]}"), observed
    observed = (
        observed_version(str(executable), spec.version_pattern)
        if spec.version_args == ("--version",)
        else observed_version(str(executable), spec.version_pattern, spec.version_args)
    )
    if observed != pinned:
        return (
            Finding(
                "resolution",
                DRIFT,
                f"{executable} reports {observed or 'UNKNOWN'} but pyproject pins {pinned}",
            ),
            observed,
        )
    return Finding("resolution", OK, f"locked uv environment runs {observed}"), observed


def _installed_direct_url_commit(repo_root: Path, spec: ToolSpec) -> str:
    """Read the VCS commit recorded by the installed distribution."""
    venv = repo_root / (spec.python_project_dir or ".") / ".venv"
    normalized = spec.python_package.replace("-", "_")
    pattern = f"lib/python*/site-packages/{normalized}-*.dist-info/direct_url.json"
    for direct_url in sorted(venv.glob(pattern)):
        try:
            payload = json.loads(direct_url.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        vcs_info = payload.get("vcs_info", {})
        if isinstance(vcs_info, dict):
            commit = str(vcs_info.get("commit_id") or "")
            if re.fullmatch(r"[0-9a-f]{40}", commit):
                return commit
    return ""


def _redacted_path(found: str, repo_root: Path) -> str:
    """Collapse host-specific path prefixes so committed reports carry no username.

    These strings land verbatim in `docs/currency/runs/` pages, which are
    committed; an absolute path there publishes the username and the machine's
    checkout layout. The repository checkout and the home directory are the two
    prefixes that vary per host, so they are the two replaced with stable
    placeholders. Checkout first: it usually lives under home, and `~/dev/…`
    would still leak the layout.
    """
    path = Path(found)
    for prefix, label in ((repo_root, "<repo>"), (Path.home(), "~")):
        try:
            return f"{label}/{path.relative_to(prefix).as_posix()}"
        except ValueError:
            continue
    return found


def _check_self_managed(repo_root: Path, spec: ToolSpec) -> SyncStatus:
    """Step 1 for a tool that bootstraps the toolchain and pins nothing.

    Every mise-pin check is inapplicable here by construction, so none of them
    run: there is no `[tools]` entry to read, resolving OUTSIDE mise is the
    correct permanent state rather than drift, and there is no install-dir path
    segment to read a version from. What remains is the one question that
    matters — is the binary a shell actually reaches the version we reviewed?

    THE MANIFEST CHECK IS NOT ONE OF THE INAPPLICABLE ONES, and treating it as
    such was a silent hole. This function used to `return` before
    `check()` could reach `_check_manifest`, so a `manifest` key on an
    `expected`-based row was DEAD CONFIG: declared, parsed, never read. Measured
    2026-08-08 — `sources/mise.manifest` reverted THREE releases reported
    nothing, while the identical mutation on `hk` (mise-managed) fired, so the
    probe discriminates and the silence was the checker's, not the manifest's.

    That is #242's own defect reappearing one layer down: the issue was "tools
    with a manifest that this table never names", and the fix named them in a
    row shape whose code path could not act on the name. `applies_here` and
    `source_only` genuinely are inapplicable; "which source did we ingest" is a
    question about the REPO and does not care how the binary is managed.

    This costs one subprocess (~11 ms for mise), which the mise-managed path
    deliberately avoids. The trade is worth it only because the alternative is
    no check at all: a self-updating tool's version is not written down anywhere
    on disk that we could read for free.

    Drift here is a statement about the HOST, not the repo — the tool moved
    under us — so the detail says what to do about it rather than implying the
    config is wrong.
    """
    found = shutil.which(spec.binary)
    if not found:
        return SyncStatus(
            tool=spec.name,
            pinned=spec.expected,
            resolved="",
            findings=(
                Finding("resolution", DRIFT, f"{spec.binary} is not installed on this host"),
            ),
        )
    running = (
        observed_version(spec.binary, spec.version_pattern)
        if spec.version_args == ("--version",)
        else observed_version(spec.binary, spec.version_pattern, spec.version_args)
    )
    if not running:
        # BLIND, not DRIFT: an unreadable version is "could not ask". Rendering
        # it as disagreement would make a broken `version_pattern` look like a
        # tool upgrade, and send the reader to review release notes for a bump
        # that never happened.
        return SyncStatus(
            tool=spec.name,
            pinned=spec.expected,
            resolved="",
            findings=(
                Finding(
                    "version",
                    BLIND,
                    f"could not read a version from {_redacted_path(found, repo_root)}"
                    + (f" using pattern {spec.version_pattern!r}" if spec.version_pattern else ""),
                ),
            ),
        )
    # Compared against the RUNNING version, not `expected`: the manifest's job
    # is to describe the code we actually execute, which is the same question
    # the mise-managed path asks of its pin. On a self-updated host those two
    # differ, and the version finding above already says so.
    manifest = _check_manifest(repo_root, spec, running)
    if running != spec.expected:
        return SyncStatus(
            tool=spec.name,
            pinned=spec.expected,
            resolved=running,
            findings=(
                Finding(
                    "version",
                    DRIFT,
                    f"{spec.binary} on PATH is {running} but the reviewed version is "
                    f"{spec.expected} — it self-updated. Review the releases between "
                    f"them, then bump `expected` in currency.toml to record that you "
                    f"have",
                ),
                manifest,
            ),
        )
    return SyncStatus(
        tool=spec.name,
        pinned=spec.expected,
        resolved=running,
        findings=(
            Finding(
                "version",
                OK,
                f"{spec.binary} on PATH is the reviewed {running} "
                f"({_redacted_path(found, repo_root)})",
            ),
            manifest,
        ),
    )


def _check_source_only(repo_root: Path, spec: ToolSpec) -> SyncStatus:
    """Step 1 for a tracked thing that is INGESTED rather than installed.

    Every binary- and pin-shaped check is inapplicable by construction here (see
    `ToolSpec.source_only`), so none of them run — reporting a missing binary for
    something that was never meant to be installed is the false-red that makes a
    check ignorable. What remains is the one question the corpus can answer
    offline: does the committed manifest still describe the clone the graph was
    built from?

    `pinned` carries the manifest's `ref`, which is what `_run_one` feeds to the
    upstream probe as "current" — so the new-release check in steps 2-3 compares
    against what we actually ingested, not against a version nobody declared.
    """
    ref = manifest_ref(repo_root, spec)
    if not ref:
        return SyncStatus(
            tool=spec.name,
            pinned="",
            resolved="",
            findings=(Finding("manifest", DRIFT, f"{spec.manifest} has no readable `ref =` line"),),
        )

    commit = _manifest_field(repo_root, spec, "commit")
    findings = [Finding("manifest", OK, f"{spec.manifest} pins `ref = {ref}`")]
    if not commit:
        findings.append(
            Finding("manifest", DRIFT, f"{spec.manifest} has no readable `commit =` line")
        )
        return SyncStatus(tool=spec.name, pinned=ref, resolved="", findings=tuple(findings))

    findings.append(_check_source_clone(repo_root, spec, commit))
    # A source-only tool has no pin and no binary, but it CAN still have code
    # constants that re-state its revision — so the binding check applies here for
    # the same reason the manifest check does.
    findings.append(_check_ref_bindings(repo_root, spec))
    return SyncStatus(tool=spec.name, pinned=ref, resolved=commit[:12], findings=tuple(findings))


def _check_source_clone(repo_root: Path, spec: ToolSpec, commit: str) -> Finding:
    """Is the on-disk clone at the commit the manifest pins?

    A clone that has drifted ahead is the `clean-git-state.md` trap in its corpus
    form: the graph then describes bytes no fresh checkout would reproduce. An
    ABSENT clone is BLIND rather than DRIFT — `sources/<name>/` is gitignored and
    re-fetched by `kb-build`, so not having it yet is the normal state of a fresh
    checkout and says nothing about whether the pin is current.
    """
    clone = repo_root / "sources" / spec.name
    head_file = clone / ".git" / "HEAD"
    if not head_file.exists():
        return Finding(
            "clone",
            BLIND,
            f"sources/{spec.name}/ is not cloned here; `mise run kb-build` fetches it",
        )
    head = head_file.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref_path = clone / ".git" / head.partition("ref:")[2].strip()
        head = ref_path.read_text(encoding="utf-8").strip() if ref_path.exists() else ""
    if not head:
        return Finding("clone", BLIND, f"sources/{spec.name}/ HEAD could not be read")
    if head != commit:
        return Finding(
            "clone",
            DRIFT,
            f"sources/{spec.name}/ is at {head[:12]} but {spec.manifest} pins "
            f"{commit[:12]} — `mise run kb-update -- {spec.name}` moves the pin",
        )
    return Finding("clone", OK, f"sources/{spec.name}/ is at the pinned {commit[:12]}")


def _check_extras(spec: ToolSpec, declared: tuple[str, ...]) -> Finding:
    if not spec.extras:
        if declared:
            # One-directional checking hid a real supply-surface change: the pin
            # installing extras nobody declared is as much a drift as the reverse.
            return Finding(
                "extras",
                DRIFT,
                f"the mise pin installs extras {list(declared)} that currency.toml "
                f"does not declare",
            )
        return Finding("extras", SKIP, "no extras declared for this tool")
    if tuple(sorted(declared)) != tuple(sorted(spec.extras)):
        return Finding(
            "extras",
            DRIFT,
            f"mise pin declares extras {list(declared)} "
            f"but currency.toml expects {list(spec.extras)}",
        )
    return Finding("extras", OK, f"pin declares the expected extras {list(spec.extras)}")


def install_site_packages(
    binary: str,
    mise_key: str,
    *,
    deep: bool,
    repo_root: Path | None = None,
    python_package: str = "",
) -> Path | None:
    """The resolved install's `site-packages`, or None when it cannot be located.

    Free path: the binary resolves inside a mise install dir, so the root is a
    path prefix. When it resolves through a shim that prefix is invisible, and
    only `mise where` can supply it — a ~0.4s subprocess, so it is gated behind
    `deep` and never runs in the per-session hook.
    """
    if python_package and repo_root is not None:
        env = repo_root / ".venv" / "lib"
        return next(iter(sorted(env.glob("python*/site-packages"))), None)
    root = _pinned_install_root(mise_key) if deep else None
    if root is None:
        root = _install_root_from_path(binary)
    if root is None or not root.is_dir():
        return None
    return next(iter(sorted(root.glob("*/lib/python*/site-packages"))), None)


def _pinned_install_root(mise_key: str) -> Path | None:
    """Install root of the PINNED version, via `mise where` (one subprocess).

    Preferred in deep mode because the question is whether the *pinned* install
    has its extras. PATH may reach a different, stale install — that is a
    separate finding, already reported by the resolution check — and probing it
    would answer the wrong question.
    """
    proc, _ = _proc.run_capture(["mise", "where", mise_key], timeout=30)
    if proc is None or proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip())


def _install_root_from_path(binary: str) -> Path | None:
    """Install root inferred from the resolved binary's path — free, no subprocess.

    Only works when the binary resolves inside a mise install dir; a shim hides
    the prefix entirely.
    """
    found = shutil.which(binary)
    if not found:
        return None
    parts = Path(found).absolute().parts
    if "installs" not in parts:
        return None
    idx = parts.index("installs")
    return Path(*parts[: idx + 3]) if len(parts) > idx + 2 else None


def _check_extra_probes(repo_root: Path, spec: ToolSpec, *, deep: bool) -> Finding:
    """Are the packages the extras are supposed to deliver actually installed?

    This is the half of "extensions tools are in sync" that comparing two config
    files cannot answer: `extras = ["all"]` in both files is satisfied even when
    the install is missing every package the extra was meant to provide.
    """
    if not spec.extra_probes:
        return Finding("extra-probes", SKIP, "no extra_probes declared for this tool")
    site = install_site_packages(
        spec.binary,
        spec.mise_key,
        deep=deep,
        repo_root=repo_root / (spec.python_project_dir or "."),
        python_package=spec.python_package,
    )
    if site is None:
        return Finding(
            "extra-probes",
            BLIND,
            "install path not resolvable here"
            + ("" if deep else " without a subprocess (run the full workflow for a deep check)"),
        )
    missing = [p for p in spec.extra_probes if not (site / p).exists()]
    if missing:
        return Finding(
            "extra-probes",
            DRIFT,
            f"declared extras {list(spec.extras)} did not deliver {missing} (looked in {site})",
        )
    return Finding(
        "extra-probes", OK, f"all {len(spec.extra_probes)} probed extra package(s) present"
    )


def _check_manifest(repo_root: Path, spec: ToolSpec, pinned: str) -> Finding:
    if not spec.manifest:
        return Finding("manifest", SKIP, "this repo pins no source manifest for the tool")
    ref = manifest_ref(repo_root, spec)
    if not ref:
        return Finding("manifest", DRIFT, f"{spec.manifest} has no readable `ref =` line")
    if re.fullmatch(r"[0-9a-f]{40}", pinned):
        commit = _manifest_field(repo_root, spec, "commit")
        if commit != pinned:
            return Finding(
                "manifest",
                DRIFT,
                f"{spec.manifest} commits {commit or 'UNKNOWN'} but pyproject pins {pinned}",
            )
        return _check_source_clone(repo_root, spec, pinned)
    # `rust-v0.147.0` -> `0.147.0`. Strip the project's declared prefix BEFORE
    # the `v`, or a `rust-v` tag compares literally against an installed
    # `0.147.0` and reports drift on a manifest pinned exactly right (#245).
    bare = ref.removeprefix(spec.tag_prefix).lstrip("v") if spec.tag_prefix else ref.lstrip("v")
    if bare != pinned:
        # "mise installs" is TRUE only on the mise-managed path. Since 2026-08-08
        # this is also reached for `expected`-based tools (mise itself,
        # claude-code, ruff, ty), which mise does not install — the first armed
        # run printed "sources/claude-code.manifest pins v2.1.222 but mise
        # installs 2.1.226", asserting a manager that is not involved. A finding
        # that misnames its own evidence teaches the reader to distrust the
        # check, so the verb follows the row shape.
        how = "the running version is" if spec.self_managed else "mise installs"
        return Finding(
            "manifest",
            DRIFT,
            f"{spec.manifest} pins {ref} but {how} {pinned} — "
            f"the corpus describes code we do not run",
        )
    return _check_manifest_commit(repo_root, spec, ref)


def _check_manifest_commit(repo_root: Path, spec: ToolSpec, ref: str) -> Finding:
    """Does the manifest's `commit` actually name the tag its `ref` claims?

    `ref` agreeing with the installed version is NOT the invariant.`_ensure_clone`
    clones the ref and then checks out `commit`, so those two fields are what the
    corpus is really built from — and they are independent. A manifest reading
    `ref = v1.54.0` beside the PREVIOUS release's commit reported OK while
    `kb-build` extracted the old code: the same false-green `_check_manifest`
    exists to prevent, reached by a narrower mutation. The cold lane found it by
    executing exactly that, against the check that had just been armed for hk
    and fnox.

    Verified against the LOCAL clone rather than the network: it is the tree the
    build will actually use, it costs no round trip, and a missing clone is an
    UNKNOWN rather than a pass — "could not check" is never rendered green here.
    """
    commit = _manifest_field(repo_root, spec, "commit")
    if not commit:
        return Finding("manifest", DRIFT, f"{spec.manifest} has no readable `commit =` line")
    # BOTH identities of the tag, because an ANNOTATED tag legitimately has two
    # SHAs and they name the same tree: `ls-remote` (what `kb-manifest-add`
    # records) returns the TAG OBJECT, while `git rev-list -n1` PEELS to the
    # commit. Comparing the recorded tag-object SHA against the peeled one
    # reported drift on a manifest pinned exactly right — measured on
    # jdx/mise v2026.8.3, dd76a503e34e vs e6d9aed080ef (#246).
    #
    # This is NOT normalising until they agree: a checkout of either SHA
    # produces the same tree, so both are true answers to "what does this ref
    # name". A LIGHTWEIGHT tag returns one SHA for both, so the widening costs
    # no precision there — control-armed on astral-sh/uv 0.12.3, one SHA.
    #
    # NOT the bug #235 refuted: that was `manifest.latest_commit`, which passes
    # an exact ref to `ls-remote` and never peels. Different function.
    resolved = _tag_commit(repo_root, spec, ref)
    tag_object = _tag_commit(repo_root, spec, ref, resolver="rev-parse")
    if resolved is None:
        return Finding(
            "manifest",
            SKIP,
            f"{spec.manifest} pins {ref}; the local clone could not resolve that ref "
            f"(no clone, no `.git`, no such tag, or git unavailable), so `commit` was "
            f"NOT checked — run `mise run kb-build`",
        )
    if commit not in {resolved, tag_object}:
        return Finding(
            "manifest",
            DRIFT,
            f"{spec.manifest} pins `ref = {ref}` but `commit = {commit[:12]}`, and {ref} "
            f"resolves to {resolved[:12]} — kb-build checks out the COMMIT, so the corpus "
            f"would describe code the ref does not name",
        )
    return Finding("manifest", OK, f"{spec.manifest} tracks the installed {ref} at {commit[:12]}")


def _check_ref_bindings(repo_root: Path, spec: ToolSpec) -> Finding:
    """Does every code constant and committed artifact name the manifest's revision?

    The manifest check answers "does the corpus describe the code we run". This
    answers the question one layer in: **does the repo agree with itself about
    which revision that is.** They are different questions, and on 2026-08-15 the
    first was green while the second was two releases wrong — the pin, the
    manifest, the clone and `graphify_semantic_corpus` all read v0.9.43 while
    `graphify_baseline._ACCEPTED_GRAPHIFY_REF` and the committed disposition
    catalog read v0.9.42. Nothing reported it, because nothing looked.

    A binding whose pattern matches NOTHING is DRIFT, not SKIP. The anchor is a
    literal in a source file, so a rename silently converts the check into a
    no-op that still renders as declared — and a check that can only pass is not
    a check (`probes-need-a-control-arm.md`). Saying "the anchor is gone" is the
    honest answer and points straight at the repair.

    Offline and subprocess-free: every input is a committed file in this repo.
    """
    if not spec.ref_bindings:
        return Finding("ref-binding", SKIP, "this tool declares no revision bindings")
    if not spec.manifest:
        return Finding(
            "ref-binding",
            SKIP,
            "bindings are declared but the tool pins no source manifest to compare them against",
        )
    expected = {
        "ref": manifest_ref(repo_root, spec),
        "commit": _manifest_field(repo_root, spec, "commit"),
    }
    findings: list[str] = []
    for binding in spec.ref_bindings:
        want = expected.get(binding.field, "")
        if not want:
            findings.append(f"{binding.label}: {spec.manifest} has no readable `{binding.field} =`")
            continue
        path = repo_root / binding.path
        if not path.exists():
            findings.append(f"{binding.label}: file is missing")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(f"{binding.label}: unreadable ({exc})")
            continue
        found = re.search(binding.pattern, text)
        if found is None:
            findings.append(
                f"{binding.label}: the declared anchor matched nothing, so this binding "
                f"checked NOTHING — repair the pattern or the file"
            )
            continue
        observed = found.group(1)
        if observed != want:
            findings.append(f"{binding.label}: reads {observed} but {spec.manifest} pins {want}")
    if findings:
        return Finding(
            "ref-binding",
            DRIFT,
            "the repo disagrees with its own source manifest — " + "; ".join(findings),
        )
    return Finding(
        "ref-binding",
        OK,
        f"all {len(spec.ref_bindings)} revision bindings agree with {spec.manifest}",
    )


def _check_skill_stamp(repo_root: Path, spec: ToolSpec, pinned: str) -> Finding:
    """Does the installed agent skill (#315) describe the version we actually run?

    The fourth thing a bump has to carry, after the pin, the manifest and the
    clone — and historically the one nothing moved. `currency.apply` refreshes it
    on the bumps IT applies; every other route (a hand edit, a refresh that was
    never run) left it behind with no report. The stamp is gitignored, so the
    drift leaves no tracked trace for a reviewer to catch either.

    A declared stamp that does not EXIST is DRIFT: the skill dir is installed, so
    an absent stamp means the install predates stamping or was assembled by hand
    — in both cases the skill's version is unknown, and unknown is never green
    here. A skill dir that is itself absent is a different, honest SKIP: nothing
    was installed, so nothing can be stale.
    """
    if not spec.skill_stamp:
        return Finding("skill-stamp", SKIP, "this tool declares no skill version stamp")
    if spec.skill_dir and not (repo_root / spec.skill_dir).exists():
        return Finding(
            "skill-stamp",
            SKIP,
            f"{spec.skill_dir} is not installed here, so its skill cannot be stale",
        )
    stamp = repo_root / spec.skill_stamp
    if not stamp.exists():
        return Finding(
            "skill-stamp",
            DRIFT,
            f"{spec.skill_stamp} is missing, so the installed skill's version is UNKNOWN "
            f"— run `mise run kb-skill-refresh`",
        )
    installed = stamp.read_text(encoding="utf-8").strip()
    if not installed:
        return Finding(
            "skill-stamp",
            DRIFT,
            f"{spec.skill_stamp} is empty, so the installed skill's version is UNKNOWN "
            f"— run `mise run kb-skill-refresh`",
        )
    if installed != pinned:
        return Finding(
            "skill-stamp",
            DRIFT,
            f"the installed skill was generated by {installed} but the pin is {pinned} — "
            f"the skill documents a version we no longer run; run `mise run kb-skill-refresh`",
        )
    return Finding("skill-stamp", OK, f"the installed skill was generated by the pinned {pinned}")


def _manifest_field(repo_root: Path, spec: ToolSpec, key: str) -> str:
    """One `<key> =` line from this tool's source manifest, or ""."""
    if not spec.manifest:
        return ""
    path = repo_root / spec.manifest
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith(key) and "=" in line:
            return line.partition("=")[2].strip()
    return ""


_RESOLVERS = {
    # PEELS an annotated tag to the commit it points at.
    "rev-list": ("rev-list", "-n1"),
    # Returns the TAG OBJECT itself — what `git ls-remote` reports and what
    # `kb-manifest-add` therefore records. `rev-list` cannot produce this: it
    # peels for BOTH `<ref>` and `<ref>^{}`, which is why the first attempt at
    # #246 compared peeled against peeled and still reported drift.
    "rev-parse": ("rev-parse",),
}


def _tag_commit(
    repo_root: Path, spec: ToolSpec, ref: str, *, resolver: str = "rev-list"
) -> str | None:
    """What `ref` resolves to in the local clone, or None when unresolvable.

    None means UNKNOWN — no clone, no such tag, no git — and the caller reports
    SKIP for it rather than OK. Distinguishing "checked and agrees" from "could
    not check" is the whole posture of this engine.
    """
    if not spec.manifest:
        return None
    clone = repo_root / Path(spec.manifest).with_suffix("")
    if not (clone / ".git").is_dir():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(clone), *_RESOLVERS[resolver], ref],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:
        return None
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and len(sha) == _SHA_LEN else None


def _check_artifact_identity(
    repo_root: Path, spec: ToolSpec, stamp: dict[str, object]
) -> Finding | None:
    """Are ALL declared outputs still the ones this stamp describes? None when yes.

    The FINGERPRINT map is the authority. `built_at_commit` cannot answer this —
    it is the git HEAD, identical across every rebuild at one commit, which is
    the normal development rhythm. Keying the detector off it meant it almost
    never had a chance to fire, while the docs claimed it would.

    Every declared output must be present AND match. A declared output the stamp
    never fingerprinted (added to `artifacts` after the last build, or a v2 stamp
    that only fingerprinted the primary graph) is itself drift — "regenerate and
    re-stamp" — because a generated view nobody has fingerprinted cannot be
    asserted to match the graph.
    """
    try:
        stamped_with = int(str(stamp.get("stamp_version", 1)))
    except ValueError:
        stamped_with = 1
    if stamped_with < _STAMP_VERSION:
        # A pre-v3 stamp fingerprinted at most the primary graph, so it cannot
        # prove the generated outputs match. Say so rather than inheriting a
        # guarantee it was never able to make.
        return Finding(
            "build-stamp",
            DRIFT,
            "stamp predates generated-output fingerprinting and cannot prove the "
            "wiki/graphml/svg match the graph — rebuild to re-stamp",
        )
    recorded = stamped_fingerprints(stamp)
    stale: list[str] = []
    for rel in spec.all_artifacts:
        live = artifact_fingerprint(repo_root / rel)
        if not live:
            stale.append(f"{rel} (missing)")
        elif rel not in recorded:
            stale.append(f"{rel} (never stamped)")
        elif live != recorded[rel]:
            stale.append(f"{rel} (changed)")
    if stale:
        return Finding(
            "build-stamp",
            DRIFT,
            "generated outputs out of sync with the stamp — regenerate "
            f"(`mise run kb-artifacts`) or rebuild: {', '.join(stale)}",
        )
    return None


def _check_stamp(repo_root: Path, spec: ToolSpec, pinned: str) -> Finding:
    if not spec.stamp:
        return Finding("build-stamp", SKIP, "this tool declares no build stamp")
    # BEFORE the stamp is read, not inside the no-stamp branch. A failing detect
    # preflight aborts ahead of `graph._clear_stamp`, so a machine that has ever
    # built successfully keeps its OLD stamp through a failed rebuild — and this
    # function then returned OK for a build that is broken. Asking here means a
    # recorded failure is reported whatever the stamp says, which is the whole
    # point: the record is cleared only by a build that SUCCEEDS.
    # (Cold lane, P1 — the #397 defect reintroduced inside its own fix.)
    stamp = read_stamp(repo_root, spec)
    outcome = build_outcome.describe(repo_root, stamp_built_at=str(stamp.get("built_at", "")))
    if outcome is not None:
        # An INTERRUPT is not drift — nothing was verified and nothing is known
        # to be wrong. Reporting it as DRIFT made the check contradict its own
        # sentence, which said "not a defect". BLIND is never rendered as green.
        status = BLIND if outcome.kind == build_outcome.INTERRUPTED else DRIFT
        return Finding("build-stamp", status, outcome.text)

    if not stamp:
        return Finding(
            "build-stamp", DRIFT, "no build has run here yet — rebuild pending (never run)"
        )

    mismatch = _check_artifact_identity(repo_root, spec, stamp)
    if mismatch is not None:
        return mismatch

    built_with = str(stamp.get("version", ""))
    if built_with != pinned:
        return Finding(
            "build-stamp",
            DRIFT,
            f"artifacts were built by {built_with or 'an unknown version'} but the pin is {pinned} "
            f"— rebuild pending",
        )
    return Finding("build-stamp", OK, f"artifacts were built by the pinned {pinned}")


def check_sync(repo_root: Path, spec: ToolSpec, *, deep: bool = False) -> SyncStatus:
    """Run every applicable step-1 check for one tool.

    Offline and subprocess-free by default, which is what lets the SessionStart
    hook run it every session. `deep=True` additionally allows one `mise where`
    subprocess so the extras probe can locate an install reached through a shim;
    the full workflow uses it, the hook does not.
    """
    if not spec.applies_here():
        return SyncStatus(
            tool=spec.name,
            pinned="",
            resolved="",
            findings=(
                Finding(
                    "platform",
                    BLIND,
                    f"{spec.name} is declared for {list(spec.os)}; this host cannot check it",
                ),
            ),
        )

    if spec.source_only:
        return _check_source_only(repo_root, spec)

    if spec.self_managed:
        return _check_self_managed(repo_root, spec)

    pinned, declared_extras = pinned_version(repo_root, spec)
    if not pinned:
        owner = (
            f"pyproject.toml has no exact pin for {spec.python_package!r}"
            if spec.python_package
            else f"mise.toml has no pin for {spec.mise_key!r}"
        )
        return SyncStatus(
            tool=spec.name,
            pinned="",
            resolved="",
            findings=(Finding("pin", DRIFT, owner),),
        )

    resolution, resolved = _check_resolution(repo_root, spec, pinned)
    pin_owner = (
        f"pyproject.toml pins {spec.python_package} at {pinned}"
        if spec.python_package
        else f"mise.toml pins {spec.mise_key} at {pinned}"
    )
    return SyncStatus(
        tool=spec.name,
        pinned=pinned,
        resolved=resolved,
        findings=(
            Finding("pin", OK, pin_owner),
            resolution,
            _check_extras(spec, declared_extras),
            _check_extra_probes(repo_root, spec, deep=deep),
            _check_manifest(repo_root, spec, pinned),
            _check_ref_bindings(repo_root, spec),
            _check_skill_stamp(repo_root, spec, pinned),
            _check_stamp(repo_root, spec, pinned),
        ),
    )
