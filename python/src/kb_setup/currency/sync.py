"""Step 1 — is the tool we RUN the tool we PINNED, and did it build our artifacts?

This is the genuinely new check. Version *bumps* are already covered (Renovate,
`mise outdated --bump`); what nothing covered until now is the quieter question:
the pin says 0.9.25, but which binary does a shell actually reach, which version
built `graphify-out/`, and does the source manifest describe that same release?

It found a live defect the day it was written: `MISE_ENV_CACHE=1` had baked a
stale `.../installs/pipx-graphifyy/0.9.23/bin` into PATH *ahead* of the mise
shims, so every bare `graphify` call ran 0.9.23 under a 0.9.25 pin.

Everything here is offline and subprocess-free by design — the SessionStart hook
runs it on every session, so it must cost milliseconds, not seconds.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

OK = "ok"
DRIFT = "drift"
SKIP = "skip"  # not applicable / not verifiable here — never a failure

_STAMP_VERSION = 1


@dataclass(frozen=True)
class Finding:
    """One check's outcome. `status` is OK / DRIFT / SKIP; `detail` is the evidence."""

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

    def summary(self) -> str:
        """One line, suitable for a hook nudge or a landing-page row."""
        if self.ok:
            return f"{self.tool} {self.pinned}: in sync"
        first = self.drifted[0]
        extra = f" (+{len(self.drifted) - 1} more)" if len(self.drifted) > 1 else ""
        return f"{self.tool}: {first.check} — {first.detail}{extra}"


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
        version = str(entry.get("version", ""))
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
    parts = Path(found).absolute().parts
    if "shims" in parts:
        return "", "shim"
    if "installs" in parts:
        idx = parts.index("installs")
        # .../installs/<backend-tool>/<version>/... — the version is two along.
        if len(parts) > idx + 2:
            return parts[idx + 2], "install-dir"
    return "", f"outside-mise:{found}"


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


def write_stamp(repo_root: Path, spec: ToolSpec, *, version: str, source_ref: str = "") -> Path:
    """Record which version built the artifacts, next to them.

    graphify does not stamp its own output — `export.to_json()` writes only
    `built_at_commit`, and `graph.json` has no version field at all (verified
    against 0.9.25 source). So "which version built this graph?" is unanswerable
    from the artifact, and this sidecar is the answer. Written by the build task,
    never by a check.
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
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _artifact_commit(artifact: Path | None) -> str:
    """`built_at_commit` from a graphify graph.json, or "" when unavailable.

    Read with a streaming scan rather than json.load: these graphs run to hundreds
    of megabytes and a session-start hook must not parse one.
    """
    if artifact is None or not artifact.exists():
        return ""
    needle = b'"built_at_commit"'
    try:
        with artifact.open("rb") as fh:
            fh.seek(max(0, artifact.stat().st_size - 4096))
            tail = fh.read()
    except OSError:
        return ""
    idx = tail.rfind(needle)
    if idx < 0:
        return ""
    _, _, rest = tail[idx:].partition(b":")
    return rest.strip().strip(b",\n }").strip(b'"').decode("utf-8", "replace")


def read_stamp(repo_root: Path, spec: ToolSpec) -> dict[str, str]:
    """The recorded stamp, or an empty dict when absent/unreadable."""
    path = stamp_path(repo_root, spec)
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


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
        return Finding("resolution", SKIP, f"{spec.binary} is not on PATH here"), ""
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
        return Finding("extras", SKIP, "no extras declared for this tool")
    if tuple(sorted(declared)) != tuple(sorted(spec.extras)):
        return Finding(
            "extras",
            DRIFT,
            f"mise pin declares extras {list(declared)} "
            f"but currency.toml expects {list(spec.extras)}",
        )
    return Finding("extras", OK, f"pin declares the expected extras {list(spec.extras)}")


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


def _check_stamp(repo_root: Path, spec: ToolSpec, pinned: str) -> Finding:
    if not spec.stamp:
        return Finding("build-stamp", SKIP, "this tool declares no build stamp")
    stamp = read_stamp(repo_root, spec)
    if not stamp:
        return Finding("build-stamp", DRIFT, "artifacts have never been stamped — rebuild pending")
    built_with = stamp.get("version", "")
    artifact = repo_root / spec.artifact if spec.artifact else None
    live_commit = _artifact_commit(artifact)
    recorded_commit = stamp.get("artifact_commit", "")
    if live_commit and recorded_commit and live_commit != recorded_commit:
        return Finding(
            "build-stamp",
            DRIFT,
            f"artifacts were rebuilt outside the build task "
            f"(stamp says {recorded_commit[:8]}, artifact says {live_commit[:8]}) "
            f"— version unknown",
        )
    if built_with != pinned:
        return Finding(
            "build-stamp",
            DRIFT,
            f"artifacts were built by {built_with or 'an unknown version'} but the pin is {pinned} "
            f"— rebuild pending",
        )
    return Finding("build-stamp", OK, f"artifacts were built by the pinned {pinned}")


def check_sync(repo_root: Path, spec: ToolSpec) -> SyncStatus:
    """Run every applicable step-1 check for one tool. Offline, no subprocesses."""
    if not spec.applies_here():
        return SyncStatus(
            tool=spec.name,
            pinned="",
            resolved="",
            findings=(
                Finding(
                    "platform",
                    SKIP,
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
            _check_manifest(repo_root, spec, pinned),
            _check_stamp(repo_root, spec, pinned),
        ),
    )
