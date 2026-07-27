"""Launch a Claude Code session for this repo, with the environment PROVEN correct.

WHY THIS EXISTS. `mise run cc` used to be a thin shell wrapper that execed
``claude`` inside tmux. It worked, and it silently launched sessions whose
``graphify`` was the wrong version — which is the one failure this whole queue
cannot absorb, because `kb-build` resolves a bare ``graphify`` through ``PATH``
and stamps the corpus with the *pinned* version regardless of which binary
actually ran. A rebuild done by 0.9.25 and stamped 0.9.27 is unfalsifiable
afterwards.

THE TWO WAYS THE ENVIRONMENT LIES, both measured 2026-07-27:

1. **A stale mise install directory sits ahead of the shims on ``PATH``.**
   ``…/mise/installs/pipx-graphifyy/0.9.25/bin`` was at position 32 while
   ``mise which graphify`` correctly reported a different version. It does not
   follow the pin and it does not move when the pin moves — ``MISE_ENV_CACHE``
   freezes whatever was active when the shell's env cache was written. So the
   fix cannot be "strip the previous version"; it has to be "strip every
   install-dir entry that a shim already covers".

2. **tmux hands a NEW session the SERVER's environment, not the caller's.**
   ``update-environment`` does not include ``PATH``, so a session created
   through a server started hours ago inherits that server's ``PATH`` — even
   when launched from a pristine shell. Measured: a fresh login shell resolved
   ``graphify`` to 0.9.27 via the shims while a new session on the running
   server got 0.9.25. This is why the session is created with an explicit
   ``tmux new-session -e PATH=…`` rather than trusting inheritance.

WHY IT VALIDATES INSTEAD OF JUST FIXING. Repairing ``PATH`` silently would make
this module the next thing nobody checks. It refuses to launch when the
resulting environment still disagrees with the repo's pin, and says which check
failed — a launcher that cannot fail is the same defect class as a gate that
cannot fail (`.claude/rules/probes-need-a-control-arm.md`).

WHY IT IS SHARED. Both repos launch the same way and must not drift; this module
is the single implementation, and each repo's `mise run cc` is a thin call into
it. dotfiles already depends on this package (it runs `kb-setup md-budget` from
its hk config), so there is no new dependency.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: The mise layout whose per-version `bin` directories shadow the shims. A path
#: entry containing this segment is a pinned-version escape hatch, not something
#: a session should inherit by accident.
_INSTALLS_SEGMENT = "/mise/installs/"

#: The mise shim directory segment. An entry here is version-resolving (mise
#: picks the version from the config for the cwd), which is what we want.
_SHIMS_SEGMENT = "/mise/shims"


def clean_path(path: str) -> str:
    """Drop every mise *install-dir* entry from ``path``, keeping order otherwise.

    Not "drop the stale version" — drop the whole class. The stale entry does
    not track the pin (see the module docstring), so naming a version here would
    produce a guard that is correct only until the next bump and inert after it.
    That is exactly the bug this replaces: a snippet stripping ``0.9.26/bin``
    while ``0.9.25/bin`` was the entry actually present.

    The shims are left alone: they are the version-resolving entry, and removing
    them would break every mise-managed tool.
    """
    kept = [p for p in path.split(os.pathsep) if p and _INSTALLS_SEGMENT not in p]
    return os.pathsep.join(kept)


def pinned_version(repo_root: Path, tool: str = "pipx:graphifyy") -> str | None:
    """The version this repo pins for ``tool``, or None if it pins none.

    Reads ``mise.toml`` directly rather than shelling out to mise: this runs
    before the launch, and asking mise would answer for the *ambient* config,
    which is the very thing under suspicion.
    """
    config = repo_root / "mise.toml"
    if not config.is_file():
        return None
    tools = tomllib.loads(config.read_text(encoding="utf-8")).get("tools", {})
    spec = tools.get(tool)
    if isinstance(spec, str):
        return spec
    if isinstance(spec, dict):
        version = spec.get("version")
        return version if isinstance(version, str) else None
    return None


@dataclass(frozen=True)
class Probes:
    """The two environment lookups, injected so the checks are testable.

    Bundled rather than passed as separate keyword arguments: they are one
    concern (how we interrogate the machine), and separating them pushed
    :func:`preflight` past the argument-count limit for no gain in clarity.
    """

    #: ``(tool, path) -> resolved path or None``.
    which: Callable[[str, str], str | None]
    #: ``(resolved graphify path) -> version string or None``.
    version_of: Callable[[str], str | None]


@dataclass(frozen=True)
class Preflight:
    """The verdict: what will be launched, and every reason it should not be."""

    path: str
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True when nothing blocks the launch."""
        return not self.problems


def preflight(
    repo_root: Path,
    sibling: Path,
    *,
    path: str,
    probes: Probes,
    need_tmux: bool,
) -> Preflight:
    """Clean the environment, then verify it. Never repairs silently.

    Args:
        repo_root: The repo the session will be rooted in.
        sibling: The repo added with ``--add-dir``.
        path: The inbound ``PATH``.
        probes: How to interrogate the machine. See :class:`Probes`.
        need_tmux: Whether a tmux binary is required (false when already inside).

    The graphify check is the point of the whole module, and it is deliberately
    TWO assertions, because either alone passes in a broken state:

    * it must resolve through the **shims**, not an install dir — an install dir
      that happens to hold the right version today is still a frozen entry that
      will be wrong after the next bump;
    * its reported version must equal the repo's **pin** — the shims resolve
      per-cwd, so a session rooted in the wrong place resolves the wrong config.
    """
    cleaned = clean_path(path)
    problems: list[str] = []

    if not sibling.is_dir():
        problems.append(f"sibling repo not found at {sibling}")

    if probes.which("claude", cleaned) is None:
        problems.append("`claude` does not resolve on PATH")

    if need_tmux and probes.which("tmux", cleaned) is None:
        problems.append("`tmux` does not resolve on PATH (needed for split-pane teammates)")

    if not (repo_root / "mise.toml").is_file():
        # A silent skip here would be the worst outcome: `kb_setup.cli` derives
        # repo_root from the CWD, and inside a mise task the CWD is wherever mise
        # was invoked from, NOT the repo. Without this, a wrong root would find no
        # pin, skip the version check, and launch — passing for the one reason
        # that should refuse hardest.
        problems.append(f"{repo_root} has no mise.toml — that is not a repo root")

    pin = pinned_version(repo_root)
    resolved = probes.which("graphify", cleaned)
    if resolved is None:
        problems.append("`graphify` does not resolve on PATH")
    elif _SHIMS_SEGMENT not in resolved:
        problems.append(
            f"`graphify` resolves to {resolved}, which is not a mise shim — a "
            f"pinned install directory is shadowing the shims and will not follow "
            f"the pin"
        )
    elif pin is not None:
        found = probes.version_of(resolved)
        if found is None:
            problems.append(f"could not read a version from {resolved}")
        elif found != pin:
            problems.append(
                f"`graphify` reports {found} but {repo_root.name} pins {pin} — a "
                f"corpus rebuilt now would be stamped with the pin and built by "
                f"the other one"
            )

    return Preflight(path=cleaned, problems=tuple(problems))


def _which(tool: str, path: str) -> str | None:
    return shutil.which(tool, path=path)


def _version_of(binary: str) -> str | None:
    """`graphify --version` -> the bare version, or None if it cannot be read."""
    try:
        out = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except OSError, subprocess.SubprocessError:
        return None
    if out.returncode != 0:
        return None
    parts = out.stdout.split()
    return parts[-1] if parts else None


def launch_argv(
    repo_root: Path, sibling: Path, *, path: str, session: str, in_tmux: bool
) -> list[str]:
    """The exact command to exec: claude directly, or a tmux session wrapping it.

    ``-e PATH=…`` is the load-bearing part. tmux gives a new session the SERVER's
    environment rather than the caller's, so a verified PATH would be discarded
    on the way in — the session would launch with whatever the server was started
    with hours ago. Passing it explicitly is what makes the preflight mean
    something inside the session, not just outside it.

    Already inside tmux, we exec claude directly: nesting a server inside a pane
    gives split-pane teammates nowhere useful to go.
    """
    claude = ["claude", "--add-dir", str(sibling)]
    if in_tmux:
        return claude
    return [
        "tmux",
        "new-session",
        "-A",
        "-s",
        session,
        "-c",
        str(repo_root),
        "-e",
        f"PATH={path}",
        *claude,
    ]


def cc_main(repo_root: Path, argv: Sequence[str]) -> int:
    """`kb-setup cc --sibling <path> [--session <name>]`. Execs on success."""
    args = list(argv)
    sibling: Path | None = None
    session: str | None = None
    i = 0
    while i < len(args):
        if args[i] in {"--sibling", "--session", "--root"} and i + 1 < len(args):
            if args[i] == "--sibling":
                sibling = Path(args[i + 1])
            elif args[i] == "--root":
                # Explicit, because the default is CWD and inside a mise task the
                # CWD is not the repo. Callers pass $MISE_PROJECT_ROOT.
                repo_root = Path(args[i + 1])
            else:
                session = args[i + 1]
            i += 2
            continue
        print(f"[cc] unknown argument {args[i]!r}", file=sys.stderr)
        return 2
    if sibling is None:
        print("[cc] --sibling <path> is required", file=sys.stderr)
        return 2
    repo_root = repo_root.resolve()
    session = session or repo_root.name

    in_tmux = bool(os.environ.get("TMUX"))
    checked = preflight(
        repo_root,
        sibling,
        path=os.environ.get("PATH", ""),
        probes=Probes(which=_which, version_of=_version_of),
        need_tmux=not in_tmux,
    )
    if not checked.ok:
        print("[cc] refusing to launch — the environment would lie:", file=sys.stderr)
        for problem in checked.problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        print(
            "\n[cc] the usual cause is a tmux server started before the current "
            "pin: `tmux kill-server`, then run this from a fresh terminal.",
            file=sys.stderr,
        )
        return 1

    argv_out = launch_argv(
        repo_root, sibling.resolve(), path=checked.path, session=session, in_tmux=in_tmux
    )
    print(f"[cc] preflight OK — rooted in {repo_root.name}, --add-dir {sibling.name}")
    # A CHILD, not `os.execvp`. Two reasons, and the second is the one that bit:
    #   * exec replaces the process image, so anything still buffered in stdout is
    #     LOST — observed on the first live run, where the OK line vanished and
    #     only tmux's error surfaced;
    #   * it lets this function return the launcher's real exit code instead of
    #     never returning, which is what makes the failure path testable.
    # stdio is inherited, so the interactive session behaves identically.
    env = {**os.environ, "PATH": checked.path}
    return subprocess.run(argv_out, env=env, check=False).returncode
