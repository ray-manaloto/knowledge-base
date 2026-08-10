# Copyright (c) 2026 Raymond Manaloto
"""Launch a Claude Code session for this repo, with the environment PROVEN correct.

WHY THIS EXISTS. `mise run cc` used to be a thin shell wrapper that execed
``claude`` inside tmux. It worked, and it silently launched sessions whose
``graphify`` was the wrong version — which is the one failure this whole queue
cannot absorb, because `kb-build` resolves a bare ``graphify`` through ``PATH``
and stamps the corpus with the *pinned* version regardless of which binary
actually ran. A rebuild done by 0.9.25 and stamped 0.9.27 is unfalsifiable
afterwards.

THE THREE WAYS THE ENVIRONMENT LIES, all measured 2026-07-27:

1. **A stale mise install directory sits ahead of the shims on ``PATH``.**
   ``…/mise/installs/pipx-graphifyy/0.9.25/bin`` was at position 32 while
   ``mise which graphify`` correctly reported a different version. It does not
   follow the pin and it does not move when the pin moves — ``MISE_ENV_CACHE``
   freezes whatever was active when the shell's env cache was written. So the
   fix cannot be "strip the previous version"; it has to be "strip every
   install-dir entry that a shim already covers".

2. **tmux hands a new pane the CLIENT's ``PATH``** — which is why this module
   cleans its own environment before spawning tmux, and why it does NOT try to
   inject ``PATH`` through tmux.

   The earlier version of this note claimed tmux hands a new session the
   *server's* environment, and that ``tmux new-session -e PATH=…`` was the fix
   for it. Both halves were wrong, and the ``-e`` was doing nothing at all
   (#40). Three-way sentinel probe, 2026-07-27::

       env PATH=/SENTINEL_CLIENT/bin:/usr/bin:/bin \
         tmux new-session -d -s p -e "PATH=/SENTINEL_INJECTED/bin:/usr/bin:/bin" \
         /bin/sh -c 'printf "%s" "$PATH" > arm3.txt'
       # arm3.txt -> /SENTINEL_CLIENT/bin:/usr/bin:/bin

   The pane got the CLIENT's ``PATH``: not the injected one, and not the
   server's. Two control arms pin the mechanism down:

   * ``-e FOOBAR=hello_from_e`` arrived intact in the same pane, so ``-e`` is
     not broken in general — ``PATH`` specifically is overridden. It *is*
     stored in the session environment (``tmux show-environment`` shows the
     clean value while the pane process holds a dirty one), it is simply not
     what the pane's process gets.
   * the probe ran ``/bin/sh -c``, which sources no profile, so the login
     shell's ``mise activate`` is not the re-adder either. Running the same
     probe through ``zsh -lic`` produced an identical result.

   So the load-bearing step is :func:`cc_main` spawning tmux with
   ``env={**os.environ, "PATH": cleaned}``. That is inherited by the pane and
   is the only lever that works from here. Nothing on the tmux side —
   ``-e``, ``set-environment -g``, ``default-command`` — can beat the client's
   ``PATH``, so none of them is worth adding.

   **The CONDITION this holds under**, established by adversarial verification
   and worth carrying so the fact stays falsifiable: tmux overrides ``PATH``
   only when the creating client *has* one. Given a client started with
   ``env -i`` (no ``PATH`` at all), ``-e PATH=`` does reach the pane. The
   override is therefore not "``-e PATH=`` is broken" — it is *outranked*. It
   is unconditional **here** precisely because :func:`cc_main` always spawns
   tmux with a ``PATH`` in its environment. Note also that ``PATH`` is special:
   an arbitrary variable from the client (``FOO=bar``) does NOT leak into the
   pane, so this is not "tmux passes the client's whole environment".

   **What neither version of this module fixes:** ``new-session -A`` on an
   ALREADY-EXISTING session attaches instead of spawning, and
   ``update-environment`` does not list ``PATH`` — so an old session keeps the
   ``PATH`` it was born with, whatever this function does. That is the most
   likely reason a long-lived server drifts, and it is what ``cc-fresh``
   (kill the server first) exists to resolve.

   The durable protection is NOT this PATH hygiene at all: it is
   :func:`kb_setup.graphify_env.graphify_exe`, which resolves the binary
   through ``mise which`` at every call site that matters, so corpus
   correctness no longer depends on ``PATH`` order in the first place.

3. **A mise SHIM re-injects every install dir it was just cleaned of** — which
   made mechanisms 1 and 2 above correct and the launcher still ineffective.
   `clean_path` strips the install dirs, so ``tmux`` no longer resolves to a
   real binary and resolves to ``…/mise/shims/tmux`` instead. A shim does not
   exec the tool: it re-enters mise, which applies mise's full environment and
   PREPENDS every install dir back. The cleaning is therefore self-defeating by
   construction — it is the very act of cleaning that routes the launch through
   the thing that undoes it.

   Measured, with the control arm that names which side is broken::

       CLEAN=$(clean_path "$PATH")                     # installs=0, shims=2
       env PATH=$CLEAN .../installs/node/.../node -e … # installs=0   <- direct
       env PATH=$CLEAN .../shims/node            -e … # installs=154 <- shim

   End to end, the same contrast through tmux (server pid taken from
   ``tmux display-message -p '#{pid}'``, not a ``pgrep | head -1`` that could
   name the wrong process):

   * bare ``tmux`` (→ shim): server installs=154, pane installs=154;
   * absolute ``$(mise which tmux)``: server installs=**0**, pane installs=0,
     shims=2 — a session in which a bare ``graphify`` resolves through the
     shims, which is exactly what `doctor` demands.

   Hence :func:`shim_free`, and hence :func:`launch_argv` taking the resolved
   binaries rather than bare names. Note what does NOT fix it: unsetting mise's
   activate state (``__MISE_DIFF``, ``__MISE_ORIG_PATH``, ``__MISE_SESSION``,
   ``__MISE_ENV_CACHE_KEY``, ``MISE_ENV_CACHE``) leaves the shim at installs=154
   in every combination — the re-injection is what a shim IS, not a cache
   artifact, so there is no env var to switch it off.

   Why this hid for so long: the pane-inheritance test asserted that a sentinel
   *reached* the pane, and it does — a shim PREPENDS, it does not discard, so
   every original entry survives underneath the 154 new ones. A test that asks
   "did my value arrive?" cannot see "and 154 others arrived in front of it".
   The assertion that catches it is an ABSENCE one, on install dirs.

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

import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import events
from kb_setup.result import Err, Ok, Rc, Result, exit_code, external_from_returncode

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

#: The mise layout whose per-version `bin` directories shadow the shims. A path
#: entry containing this segment is a pinned-version escape hatch, not something
#: a session should inherit by accident.
_INSTALLS_SEGMENT = "/mise/installs/"

#: The mise shim directory segment. An entry here is version-resolving (mise
#: picks the version from the config for the cwd), which is what we want.
_SHIMS_SEGMENT = "/mise/shims"

#: `ps -Eww` prints a process's environment space-separated after its command,
#: so a value must be ended by the NEXT `NAME=`, never by the next space: this
#: machine's PATH contains `…/Application Support/JetBrains/Toolbox/scripts`,
#: which a whitespace split truncates. Only needed on macOS — Linux reads
#: `/proc/<pid>/environ`, which is NUL-separated and needs no parsing at all.
_PS_PATH_RE = re.compile(r"(?:^| )PATH=(.*?)(?= [A-Za-z_][A-Za-z0-9_]*=|$)", re.DOTALL)


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


def _env_path_of(pid: str) -> str | None:
    """The ``PATH`` of an arbitrary process, read from the OS, or None.

    Linux exposes ``/proc/<pid>/environ`` NUL-separated, so the read is exact.
    macOS has no ``/proc``; ``ps -Eww`` prints the environment space-separated
    after the command, which cannot be split on whitespace — this machine's
    ``PATH`` contains ``…/Library/Application Support/JetBrains/Toolbox/scripts``
    and a naive split truncates it there. Hence the lookahead for the next
    ``NAME=``: it ends the value at the following variable, not at a space.

    Control arm for that parser (2026-07-27): run against a process whose PATH is
    already known — our own — it reproduces ``os.environ["PATH"]`` byte for byte,
    space-bearing entry included. See `tests/test_launch.py`.

    Returns None rather than guessing when the environment cannot be read, which
    genuinely happens: in the same measurement an intermediate ``/bin/zsh``
    yielded 1,289 bytes with no ``PATH=`` in them while its ``claude`` parent
    yielded 26,863 with one. `session_path` turns that None into UNKNOWN.
    """
    procfs = Path("/proc") / pid / "environ"
    if procfs.is_file():
        try:
            entries = procfs.read_bytes().split(b"\0")
        except OSError:
            return None
        for entry in entries:
            if entry.startswith(b"PATH="):
                return entry[len(b"PATH=") :].decode("utf-8", "replace")
        return None
    try:
        out = subprocess.run(
            ["ps", "-Eww", "-o", "command=", "-p", pid],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if out.returncode != 0:
        return None
    match = _PS_PATH_RE.search(out.stdout)
    return match.group(1) if match else None


def session_path(
    env: Mapping[str, str],
    *,
    read_env_path: Callable[[str], str | None] | None = None,
) -> str | None:
    """The ``PATH`` of the Claude Code SESSION, or None if it cannot be read.

    `doctor` asks what the *session* has. ``os.environ["PATH"]`` does not answer
    that whenever mise sat between the two, and under the task that invokes the
    doctor it always does — twice over: ``mise run`` injects every install dir
    into a task's environment, and ``uv`` then resolves to ``…/mise/shims/uv``,
    a shim that re-enters mise and prepends them again (mechanism 3 in the module
    docstring). Judging our own PATH made the graphify check unable to report
    green under `mise run cc-doctor` — a probe with one face, in the module that
    argues hardest against them.

    From inside that task the session's PATH is NOT recoverable from the
    environment. Measured 2026-07-27, and each dead end is recorded because each
    looks plausible until probed:

    * ``__MISE_ORIG_PATH`` is frozen at ``mise activate``, not re-stamped per
      invocation. A sentinel directory and a fake install dir placed on the
      inbound PATH both failed to appear in it. Judging it would have hidden
      exactly the post-activation drift (#40, ``MISE_ENV_CACHE`` freezing a
      stale entry) that this check exists to find — a check that cannot fail,
      which is strictly worse than the one that could not pass.
    * ``__MISE_SHIM`` is unset under ``mise run``/``mise exec``, so it does not
      even mark the case the task hits.
    * ``__MISE_DIFF`` does change per invocation, but it carries the user's
      resolved secrets in cleartext (gzip+base64+msgpack, and mise's redaction
      is a stdout filter that never touches it). Not something to parse, and
      not something to log.
    * ``{{ get_env(name='PATH') }}`` in a task ``env`` block is mise's own
      documented recovery of "the original process environment", and it is the
      obvious thing to reach for — but it is bound to ``PRISTINE_ENV``, which
      reverses ``__MISE_DIFF`` and REMOVES every path mise added. Under an
      activated shell those are exactly the install dirs this check hunts, so it
      launders the drift. Measured from one caller PATH carrying a sentinel and
      a stale install dir: activated shell → 5 entries / **0** installs /
      sentinel; ``env -i`` → 5 entries / **1** install / sentinel. Its published
      proof used ``env -i``, where there is no diff to reverse. The condition was
      the whole finding — correct where measured, wrong here.

    So the session is identified rather than reconstructed. Claude Code exports
    **``CLAUDE_PID``**, its own process id, and being an ordinary variable it
    survives both mise layers untouched (verified: ``mise exec`` and the ``uv``
    shim both pass it through). Reading that process's environment gave 29
    entries with 0 install dirs and ``graphify`` on the shims, against the 192
    and 154 this process holds.

    Note what is NOT happening here: no cleaning. `clean_path` strips install
    dirs from whatever it is handed and would launder real drift, which is why
    `doctor` must never use it. This selects *which* PATH to judge and then
    judges it raw — a session that genuinely has a shadowing install dir still
    fails.

    None means "could not ask", never "asked and fine": outside a Claude Code
    session there is no ``CLAUDE_PID``, and even with one the environment is not
    always readable. `doctor` reports that as UNKNOWN.
    """
    # Resolved at call time, not bound as a default, so a test can substitute the
    # OS read without the module-level name being frozen into the signature.
    reader = _env_path_of if read_env_path is None else read_env_path
    pid = env.get("CLAUDE_PID")
    if not pid or not pid.isdigit():
        return None
    return reader(pid)


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


def teammate_note(repo_root: Path, *, in_tmux: bool) -> str:
    """One line describing what teammates will actually be. Never blocks.

    REPORTED rather than enforced, because neither state is wrong — but they are
    very different, and today they are indistinguishable at a glance. In-process
    teammates cannot be resumed and cannot spawn background subagents; split-pane
    ones can. A session that quietly landed in-process looks identical to one
    that did not, which is how a design assumption becomes an unobserved
    declaration.

    Reads THIS repo's `.claude/settings.json` rather than the ambient
    environment: Claude Code applies that env from settings *after* this runs, so
    `os.environ` would report "off" even where the repo enables it.
    """
    settings = repo_root / ".claude" / "settings.json"
    enabled = False
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        enabled = str(data.get("env", {}).get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "")) == "1"
    if not enabled:
        return (
            "teammates: DISABLED — this repo does not set "
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS, so no team is created"
        )
    where = "this tmux session" if in_tmux else "a tmux session it creates"
    return f"teammates: enabled, split-pane via {where}"


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


def _mise_which(tool: str, repo_root: Path) -> str | None:
    """`mise which <tool>` resolved for ``repo_root``, or None if mise cannot.

    Run with ``cwd=repo_root`` deliberately: mise resolves per-config, and the
    answer we want is the one THIS repo's `mise.toml` pins, not the one for
    whatever directory the task happened to be invoked from.

    A non-mise-managed tool (``claude`` here) exits non-zero, which is not an
    error — it is the signal to fall through to the PATH lookup.
    """
    try:
        out = subprocess.run(
            ["mise", "which", tool],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            cwd=repo_root,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if out.returncode != 0:
        return None
    resolved = out.stdout.strip()
    return resolved or None


def shim_free(
    tool: str,
    *,
    repo_root: Path,
    path: str,
    lookup: Callable[[str, Path], str | None] = _mise_which,
) -> str:
    """Resolve ``tool`` to a binary that is NOT a mise shim.

    This is the fix for mechanism 3 in the module docstring, and it is the whole
    reason the cleaning now survives: a shim re-enters mise and prepends every
    install dir back onto ``PATH``, so launching tmux through one hands the pane
    — and therefore ``claude``, and therefore every bare ``graphify`` inside the
    session — exactly the environment `clean_path` had just removed.

    ``path`` must be the RAW ``PATH``, not the cleaned one. That is not an
    oversight: the cleaned path is precisely the one on which a mise-managed
    tool can only resolve to a shim, so looking there would return the thing
    this function exists to avoid.

    Order, and why:

    1. ``mise which`` — authoritative for a mise-managed tool, and it names the
       version this repo pins rather than whichever install dir happens to sit
       first on an activated ``PATH`` (which may itself be the stale entry
       mechanism 1 is about).
    2. the raw ``PATH`` — covers a tool mise does not manage (a system or
       homebrew ``tmux``, and ``claude``, which lives in ``~/.local/bin``).
    3. whatever we found, or the bare name. Falling back to a shim is worse than
       ideal but strictly better than refusing to launch: a shim still runs the
       right tool, it just re-pollutes ``PATH``. That degradation is reported by
       `doctor` in the resulting session rather than guessed at here.
    """
    resolved = lookup(tool, repo_root)
    if resolved and _SHIMS_SEGMENT not in resolved:
        return resolved
    direct = shutil.which(tool, path=path)
    if direct and _SHIMS_SEGMENT not in direct:
        return direct
    return direct or resolved or tool


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


@dataclass(frozen=True)
class Binaries:
    """The two executables to launch, each resolved SHIM-FREE.

    Bundled rather than passed as two keyword arguments for the same reason
    :class:`Probes` is: they are one concern (which binary actually runs), and
    separating them pushed :func:`launch_argv` past the argument-count limit for
    no gain in clarity.

    The defaults are the bare names — the pre-fix behaviour, and wrong on any
    machine with mise activated. They exist so a test asserting argv SHAPE need
    not resolve anything; :func:`cc_main` always builds this with
    :meth:`resolve`.
    """

    tmux: str = "tmux"
    claude: str = "claude"

    @classmethod
    def resolve(cls, repo_root: Path, *, path: str) -> Binaries:
        """Resolve both through :func:`shim_free`. ``path`` is the RAW ``PATH``."""
        return cls(
            tmux=shim_free("tmux", repo_root=repo_root, path=path),
            claude=shim_free("claude", repo_root=repo_root, path=path),
        )


def launch_argv(
    repo_root: Path,
    sibling: Path,
    *,
    session: str,
    in_tmux: bool,
    binaries: Binaries | None = None,
) -> list[str]:
    """The exact command to exec: claude directly, or a tmux session wrapping it.

    ``binaries`` carries the SHIM-FREE executables (see :class:`Binaries`,
    :func:`shim_free`, and mechanism 3 in the module docstring). Launching
    through a mise shim would re-prepend every install dir onto the ``PATH``
    :func:`clean_path` had just stripped, which is the defect this module exists
    to prevent — so the binary that runs is part of the contract, not detail.

    There is deliberately no ``PATH`` parameter here, and no ``tmux new-session
    -e PATH=…``. That injection was measured to do nothing — tmux gives the pane
    the CLIENT's ``PATH`` and ignores the session-environment value for it (#40;
    the sentinel probe and its two control arms are in the module docstring).
    Delivering a clean ``PATH`` is therefore entirely the caller's job, done by
    :func:`cc_main` spawning this argv with ``env={**os.environ, "PATH":
    cleaned}``. Taking a ``path`` argument we could not honour would be a
    parameter that reads as a guarantee and is not one.

    Removing the ``-e`` rather than replacing it with another tmux-side trick is
    deliberate: every alternative loses to the client's ``PATH`` the same way,
    so the honest change subtracts a mechanism instead of adding one.

    Already inside tmux, we exec claude directly: nesting a server inside a pane
    gives split-pane teammates nowhere useful to go.
    """
    # `--permission-mode auto` is a FLAG, not a setting, and that is the whole
    # point: Claude Code ignores `permissions.defaultMode: "auto"` from project
    # settings — "only policy, user, and CLI-flag sources may grant auto mode
    # (projectSettings and localSettings are repo-controllable)". So the project
    # file cannot grant it and the flag can. Unattended goal turns need it.
    bins = binaries or Binaries()
    claude = [bins.claude, "--permission-mode", "auto", "--add-dir", str(sibling)]
    if in_tmux:
        return claude
    return [bins.tmux, "new-session", "-A", "-s", session, "-c", str(repo_root), *claude]


#: A doctor verdict. Three states, kept distinct for the reason the currency
#: engine keeps them distinct: collapsing "could not check" into "fine" is how a
#: broken environment reports green. UNKNOWN never passes as OK and never fails
#: the run — it says the question was not asked here.
OK, FAIL, UNKNOWN = "OK", "FAIL", "UNKNOWN"


@dataclass(frozen=True)
class Check:
    """One doctor result: what was asked, what came back, and why it matters."""

    name: str
    status: str
    detail: str


def doctor(repo_root: Path, sibling: Path, *, path: str | None, probes: Probes) -> list[Check]:
    """Verify a LIVE session's environment. Reports; never repairs.

    Deliberately different from :func:`preflight` in one way that is the whole
    point: preflight cleans ``path`` before judging it, because it is about to
    hand a cleaned PATH to a child. The doctor judges the **raw** PATH, because
    it is asking what the session it runs inside actually has. Cleaning first
    here would make it a check that cannot fail — it would launder exactly the
    drift it exists to find (#40 was found by hand for want of this).

    Raw, but of the right PATH: ``path`` must be the SESSION's, which is not
    this process's whenever mise sat in the launch chain — and under the task
    that invokes the doctor it always does. Callers get it from
    :func:`session_path`; passing ``os.environ["PATH"]`` straight in made this
    check unable to report green under its own mise task.

    ``path`` of None means the session's PATH could not be READ, which is not
    the same as a session with no PATH and must never be rendered as either a
    pass or a failure. It joins the two checks a python process genuinely cannot
    make — which skills a Claude Code session can see, and which permission mode
    it is in — as UNKNOWN with the reason. Claiming any of the three from out
    here would be a probe with one face.
    """
    checks: list[Check] = []

    pin = pinned_version(repo_root)
    resolved = None if path is None else probes.which("graphify", path)
    if path is None:
        checks.append(
            Check(
                "graphify",
                UNKNOWN,
                "the session's PATH could not be read, so this was NOT checked — "
                "not that it is fine. `CLAUDE_PID` names the session process and "
                "its environment is the only honest source: this process's own "
                "PATH is mise's, carrying every install dir mise injects for a "
                'task and a shim re-prepends. Pass `--path "$PATH"` from the '
                "session's shell to check it explicitly.",
            )
        )
    elif resolved is None:
        checks.append(Check("graphify", FAIL, "`graphify` does not resolve on PATH"))
    elif _SHIMS_SEGMENT not in resolved:
        found = probes.version_of(resolved)
        version_note = (
            "its version matches the pin"
            if found == pin
            else f"and it reports {found} against a pin of {pin}"
        )
        checks.append(
            Check(
                "graphify",
                FAIL,
                f"a bare `graphify` on this session's PATH resolves to {resolved} — "
                f"an install dir ahead of the shims — {version_note}. This is PATH "
                f"hygiene, NOT corpus correctness: every kb-* task resolves through "
                f"`mise which` and is unaffected. What is affected is anything that "
                f"still runs a bare `graphify` (the retrieval evals, the tier-1 "
                f"canary, you at a prompt), because a frozen install dir does not "
                f"follow the next bump.",
            )
        )
    else:
        found = probes.version_of(resolved)
        if pin is None:
            checks.append(Check("graphify", UNKNOWN, f"{repo_root.name} pins no graphify version"))
        elif found is None:
            # Distinct from a mismatch. Collapsing them printed "reports None but
            # the pin is X" — a version the binary never reported, which is the
            # state-fabrication this design exists to refuse. `preflight` has
            # always separated these two; the doctor did not.
            checks.append(Check("graphify", FAIL, f"could not read a version from {resolved}"))
        elif found != pin:
            checks.append(Check("graphify", FAIL, f"reports {found} but the pin is {pin}"))
        else:
            checks.append(Check("graphify", OK, f"{found} via the shims ({resolved})"))

    checks.append(
        Check("sibling", OK, f"{sibling} exists")
        if sibling.is_dir()
        else Check("sibling", FAIL, f"sibling repo not found at {sibling} — --add-dir would fail")
    )

    settings = repo_root / ".claude" / "settings.json"
    if not settings.is_file():
        checks.append(Check("hook-paths", UNKNOWN, f"no {settings}"))
    else:
        # An absolute home path in a hook is an outage on any other machine, and
        # one already happened. Substring, not a parse: it must catch the path
        # wherever it appears, including inside a command string.
        bad = [
            n
            for n, line in enumerate(settings.read_text(encoding="utf-8").splitlines(), 1)
            if "/Users/" in line
        ]
        checks.append(
            Check("hook-paths", OK, "no absolute /Users/ path in .claude/settings.json")
            if not bad
            else Check("hook-paths", FAIL, f"absolute /Users/ path on line(s) {bad}")
        )

    checks.append(
        Check(
            "skills",
            UNKNOWN,
            "not answerable from here — in-session, confirm BOTH a knowledge-base-only "
            "skill (kb-curator) and a dotfiles-only one (pr-workflow) are listed. One "
            "side alone passes while --add-dir is silently broken.",
        )
    )
    checks.append(
        Check(
            "permission-mode",
            UNKNOWN,
            "not answerable from here — in-session, confirm auto mode came from the "
            "--permission-mode flag. A projectSettings defaultMode is ignored as "
            "repo-controllable, so settings.json cannot grant it.",
        )
    )
    return checks


def doctor_main(repo_root: Path, argv: Sequence[str]) -> int:
    """`kb-setup cc-doctor --sibling <path> [--root <path>] [--path <PATH>]`.

    ``--path`` exists because the caller's shell can answer this for free: it
    expands ``$PATH`` before mise or a shim touches anything, so
    ``--path "$PATH"`` from the session's own shell is exact and needs no
    process introspection. Without it the session is found via ``CLAUDE_PID``
    (see :func:`session_path`), and if that cannot be read the graphify check
    reports UNKNOWN rather than judging this process's PATH. Non-zero on any
    FAIL; UNKNOWN never fails the run.
    """
    result = check_doctor(repo_root, argv)
    # Narrowed on `Ok`, not against `Err`: `Result` has a THIRD variant, and
    # `External` carries no `.value`. ty catches the negative form.
    if not isinstance(result, Ok):
        events.fail("cc_doctor.refused", f"[cc-doctor] {result.message}")
        return exit_code(result)

    results = result.value
    mark = {OK: "✔", FAIL: "✗", UNKNOWN: "?"}
    for c in results:
        # INFO even for a FAILING check, deliberately. These lines are the
        # TABLE — product — and they went to stdout before the conversion. The
        # sink routes WARNING+ to stderr (matching what the old code did with
        # `file=sys.stderr`), so raising a failing row's level here would move it
        # between streams: a behaviour change smuggled inside a refactor, which
        # is exactly what recipe rule 2 forbids. R9 still sees the run, because
        # `cc_doctor.failures` below is an ERROR and the `status` field is on
        # every row.
        events.say(
            "cc_doctor.check",
            f"  {mark[c.status]} {c.name}: {c.detail}",
            check=c.name,
            status=c.status,
        )
    failed = [c for c in results if c.status == FAIL]
    if failed:
        events.fail(
            "cc_doctor.failures",
            f"\n[cc-doctor] {len(failed)} FAILED. `mise run cc-fresh` relaunches on a "
            f"clean tmux server; that is the usual fix for a PATH problem.",
            failed=len(failed),
        )
        return exit_code(result)
    unknown = sum(c.status == UNKNOWN for c in results)
    events.say(
        "cc_doctor.ok",
        f"\n[cc-doctor] no failures ({unknown} not verifiable from here — check them in-session)",
        unknown=unknown,
    )
    return exit_code(result)


def check_doctor(repo_root: Path, argv: Sequence[str]) -> Result[list[Check]]:
    """The boundary (§2 R5): every doctor check, or why the request was refused.

    Returns rather than raises, and prints nothing — :func:`doctor_main`
    renders. Same split as ``skill_lint.check_skill_lint``/``skill_lint_main``,
    which is ``ruff``'s ``pub fn run(..) -> Result<ExitStatus>``
    (``crates/ruff/src/lib.rs:128``).

    The three outcomes the vocabulary separates here:

    * *Ran, nothing failed* — ``Ok(checks)``. UNKNOWN rows are present in the
      value and deliberately do not move the code: a check that could not be
      answered from here is not a failure, and flattening it into one is the
      false-red twin of the false-green this repo's doctrine is about.
    * *Ran, something FAILED* — ``Ok(checks, rc=Rc.FINDINGS)``. The doctor did
      its job; a broken environment is a finding.
    * *Never ran* — an unknown argument or a missing ``--sibling``.
      ``Err(reason, rc=Rc.BAD_REQUEST)``, the 2 this command already returned,
      now carrying its reason in the type rather than only on stderr.
    """
    sibling: Path | None = None
    explicit_path: str | None = None
    args = list(argv)
    i = 0
    while i < len(args):
        if args[i] in {"--sibling", "--root", "--path"} and i + 1 < len(args):
            if args[i] == "--sibling":
                sibling = Path(args[i + 1])
            elif args[i] == "--path":
                explicit_path = args[i + 1]
            else:
                repo_root = Path(args[i + 1])
            i += 2
            continue
        return Err(f"unknown argument {args[i]!r}", rc=Rc.BAD_REQUEST)
    if sibling is None:
        return Err("--sibling <path> is required", rc=Rc.BAD_REQUEST)

    results = doctor(
        repo_root.resolve(),
        sibling,
        # NOT os.environ["PATH"] — see `session_path`. Under `mise run` this
        # process holds mise's PATH (install dirs injected for the task, then
        # re-prepended by the `uv` shim), which describes our launcher and not
        # the session. None here means "could not read it", reported UNKNOWN.
        path=explicit_path if explicit_path is not None else session_path(os.environ),
        probes=Probes(which=_which, version_of=_version_of),
    )
    failed = any(c.status == FAIL for c in results)
    return Ok(results, rc=Rc.FINDINGS if failed else Rc.OK)


def cc_main(repo_root: Path, argv: Sequence[str]) -> int:
    """`kb-setup cc --sibling <path> [--session <name>]`. Renders, then converts.

    **This is the first real `External` in the codebase**, and converting it
    turned a reasoned claim into a measured one. The old last line was
    `return subprocess.run(...).returncode`, handing a raw `subprocess`
    returncode straight to `sys.exit`. For a child killed by a signal that
    returncode is negative, and the exit status it produces is two's-complement
    nonsense:

    | child died of | returncode | reported BEFORE | POSIX convention |
    |---|---:|---:|---:|
    | SIGINT (Ctrl-C) | -2 | **254** | 130 |
    | SIGKILL | -9 | **247** | 137 |
    | SIGTERM | -15 | **241** | 143 |

    Measured, not assumed. The dangerous part is that 254/247/241 are all
    *plausible* application exit codes, so nothing ever flagged them — a
    Ctrl-C'd session reported 254 and read as a program that chose to fail.
    `external_from_returncode` states the conversion once (`result.py`), and
    every row above now reports the number a shell would.

    Progressive output goes through §2.5's event stream: this function prints
    between the preflight, the tmux kill and the child launch, which is exactly
    why it could not be converted under recipe rule 3 until the sink existed.
    """
    args = list(argv)
    sibling: Path | None = None
    session: str | None = None
    fresh = "--fresh" in args
    args = [a for a in args if a != "--fresh"]
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
        events.fail("cc.bad_argument", f"[cc] unknown argument {args[i]!r}", argument=args[i])
        return 2
    if sibling is None:
        events.fail("cc.no_sibling", "[cc] --sibling <path> is required")
        return 2
    repo_root = repo_root.resolve()
    session = session or repo_root.name

    in_tmux = bool(os.environ.get("TMUX"))
    if fresh and in_tmux:
        events.fail(
            "cc.fresh_inside_tmux",
            "[cc] --fresh kills the tmux server, and you are inside it — that "
            "would kill this process before it could relaunch. Run it from a "
            "plain terminal instead.",
        )
        return 2

    checked = preflight(
        repo_root,
        sibling,
        path=os.environ.get("PATH", ""),
        probes=Probes(which=_which, version_of=_version_of),
        need_tmux=not in_tmux,
    )
    if not checked.ok:
        events.fail(
            "cc.preflight_failed",
            "[cc] refusing to launch — the environment would lie:",
            problems=list(checked.problems),
        )
        for problem in checked.problems:
            events.fail("cc.preflight_problem", f"  ✗ {problem}", problem=problem)
        events.fail(
            "cc.preflight_hint",
            "\n[cc] the usual cause is a tmux server started before the current "
            "pin: `tmux kill-server`, then run this from a fresh terminal.",
        )
        return 1

    # Resolved AFTER preflight (so a refusing run does no extra work) and BEFORE
    # the kill, so `--fresh` tears the server down with the same binary it will
    # rebuild it with. Both are shim-free: launching through a mise shim would
    # re-prepend every install dir onto the PATH we just cleaned, which is the
    # defect this whole module exists to prevent (mechanism 3, module docstring).
    # The RAW PATH is passed on purpose — see :func:`shim_free`.
    binaries = Binaries.resolve(repo_root, path=os.environ.get("PATH", ""))

    if fresh:
        # AFTER preflight, never before. Killing first meant any preflight
        # problem — a missing sibling, no `claude`, a wrong --root, a version
        # mismatch — destroyed every tmux session on the host (including
        # unrelated projects) and then launched nothing. A repair step that runs
        # before its own validation is not a repair, it is an outage with a
        # rollback nobody wrote.
        #
        # A missing tmux cannot reach here either: preflight runs with
        # need_tmux=True whenever we are not already inside tmux, so it refuses
        # above rather than raising FileNotFoundError out of this call —
        # `check=False` suppresses a non-zero exit, NOT a missing binary.
        #
        # No server running is the desired state, not an error, so a non-zero
        # exit from kill-server is ignored.
        subprocess.run([binaries.tmux, "kill-server"], check=False, capture_output=True, timeout=60)
        events.say(
            "cc.fresh_killed",
            "[cc] --fresh: tmux server killed; the new session starts from this shell's env",
        )

    argv_out = launch_argv(
        repo_root,
        sibling.resolve(),
        session=session,
        in_tmux=in_tmux,
        binaries=binaries,
    )
    events.say(
        "cc.preflight_ok",
        f"[cc] preflight OK — rooted in {repo_root.name}, --add-dir {sibling.name}",
        root=repo_root.name,
        sibling=sibling.name,
    )
    events.say("cc.teammates", f"[cc] {teammate_note(repo_root, in_tmux=in_tmux)}", in_tmux=in_tmux)
    # A CHILD, not `os.execvp`. Two reasons, and the second is the one that bit:
    #   * exec replaces the process image, so anything still buffered in stdout is
    #     LOST — observed on the first live run, where the OK line vanished and
    #     only tmux's error surfaced;
    #   * it lets this function return the launcher's real exit code instead of
    #     never returning, which is what makes the failure path testable.
    # stdio is inherited, so the interactive session behaves identically.
    # `os.environ` and NOT `graphify_env.clean_env()`, decided deliberately. That
    # helper strips mise's `__MISE_*` blob because a graphify subprocess WRITES the
    # corpus, so a leaked env becomes a committed artifact. Neither reason holds
    # here. This launches the user's own interactive session from a shell that
    # already carries those variables, so a plain `claude` typed at the same prompt
    # has identical exposure — the launcher creates none. And `__MISE_DIFF` is
    # live activation state a shell reverses on deactivate; removing it from an
    # interactive session changes mise's behaviour in ways nothing here has
    # measured, which is precisely how the `get_env(name='PATH')` mistake happened
    # (see `session_path`). Strip it here only with a measurement in hand.
    env = {**os.environ, "PATH": checked.path}
    completed = subprocess.run(argv_out, env=env, check=False)
    # THE conversion this module's docstring table is about. `.returncode` is
    # negative for a signal-killed child, and handing that to `sys.exit`
    # two's-complements it into a plausible-looking lie (Ctrl-C -> 254).
    # `External` is uv's variant: the child's verdict, passed through as the
    # child's, with the signal case converted once and named.
    return exit_code(external_from_returncode(completed.returncode))
