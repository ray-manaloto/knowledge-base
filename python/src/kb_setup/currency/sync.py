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

import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

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
    entry = _tools_table(repo_root).get(spec.mise_key)
    if isinstance(entry, str):
        return entry, ()
    if isinstance(entry, dict):
        version = str(entry.get("version") or "")
        raw = entry.get("extras", [])
        extras = tuple(str(e) for e in raw) if isinstance(raw, list) else ()
        return version, extras
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


def observed_version(binary: str) -> str:
    """Execute `binary --version` and return the bare version, or "" on failure.

    This is the authoritative-but-slow reading (~0.4s of interpreter startup),
    used when STAMPING a build — where the honest answer is "whatever actually
    ran", not "whatever the pin says". A build that silently ran a stale binary
    must stamp the stale version, or the stamp launders the very drift it exists
    to expose.

    `check_sync` deliberately does not call this: it must stay cheap enough for a
    per-session hook.
    """
    found = shutil.which(binary)
    if not found:
        return ""
    try:
        res = subprocess.run(
            [found, "--version"], capture_output=True, text=True, check=False, timeout=30
        )
    except OSError, subprocess.TimeoutExpired:
        return ""
    if res.returncode != 0:
        return ""
    # Output is conventionally "<name> <version>"; take the last whitespace field.
    parts = (res.stdout or res.stderr).strip().split()
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


def write_stamp(repo_root: Path, spec: ToolSpec, *, version: str, source_ref: str = "") -> Path:
    """Record which version built the artifacts, next to them.

    graphify does not stamp its own output — `export.to_json()` writes only
    `built_at_commit`, and `graph.json` has no version field at all (verified
    against 0.9.25 source). So "which version built this graph?" is unanswerable
    from the artifact, and this sidecar is the answer. Written by the build task,
    never by a check.

    Fingerprints the PRIMARY graph and every declared generated output, so step 1
    catches a stale wiki/svg/GRAPH_REPORT.md the same way it catches a stale
    graph — Ray's "in sync with the graph AND generated outputs".
    """
    path = stamp_path(repo_root, spec)
    if path is None:
        raise ValueError(f"{spec.name}: no `stamp` path configured in currency.toml")
    artifact = repo_root / spec.artifact if spec.artifact else None
    payload = {
        "stamp_version": _STAMP_VERSION,
        "tool": spec.name,
        "version": version,
        "source_ref": source_ref,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "artifact_commit": _artifact_commit(artifact),
        "artifact_fingerprints": artifact_fingerprints(repo_root, spec),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def restamp_artifacts(repo_root: Path, spec: ToolSpec) -> Path | None:
    """Refresh only the fingerprints after `kb-artifacts` regenerated outputs.

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
    return write_stamp(
        repo_root,
        spec,
        version=str(existing.get("version", "")),
        source_ref=str(existing.get("source_ref", "")),
    )


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


def _check_resolution(spec: ToolSpec, pinned: str) -> tuple[Finding, str]:
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


def install_site_packages(binary: str, mise_key: str, *, deep: bool) -> Path | None:
    """The resolved install's `site-packages`, or None when it cannot be located.

    Free path: the binary resolves inside a mise install dir, so the root is a
    path prefix. When it resolves through a shim that prefix is invisible, and
    only `mise where` can supply it — a ~0.4s subprocess, so it is gated behind
    `deep` and never runs in the per-session hook.
    """
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


def _check_extra_probes(spec: ToolSpec, *, deep: bool) -> Finding:
    """Are the packages the extras are supposed to deliver actually installed?

    This is the half of "extensions tools are in sync" that comparing two config
    files cannot answer: `extras = ["all"]` in both files is satisfied even when
    the install is missing every package the extra was meant to provide.
    """
    if not spec.extra_probes:
        return Finding("extra-probes", SKIP, "no extra_probes declared for this tool")
    site = install_site_packages(spec.binary, spec.mise_key, deep=deep)
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
    if ref.lstrip("v") != pinned:
        return Finding(
            "manifest",
            DRIFT,
            f"{spec.manifest} pins {ref} but mise installs {pinned} — "
            f"the corpus describes code we do not run",
        )
    return Finding("manifest", OK, f"{spec.manifest} tracks the installed {ref}")


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
    stamp = read_stamp(repo_root, spec)
    if not stamp:
        return Finding("build-stamp", DRIFT, "artifacts have never been stamped — rebuild pending")

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

    pinned, declared_extras = pinned_version(repo_root, spec)
    if not pinned:
        return SyncStatus(
            tool=spec.name,
            pinned="",
            resolved="",
            findings=(Finding("pin", DRIFT, f"mise.toml has no pin for {spec.mise_key!r}"),),
        )

    resolution, resolved = _check_resolution(spec, pinned)
    return SyncStatus(
        tool=spec.name,
        pinned=pinned,
        resolved=resolved,
        findings=(
            Finding("pin", OK, f"mise.toml pins {spec.mise_key} at {pinned}"),
            resolution,
            _check_extras(spec, declared_extras),
            _check_extra_probes(spec, deep=deep),
            _check_manifest(repo_root, spec, pinned),
            _check_stamp(repo_root, spec, pinned),
        ),
    )
