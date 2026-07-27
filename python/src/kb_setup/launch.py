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


def launch_argv(repo_root: Path, sibling: Path, *, session: str, in_tmux: bool) -> list[str]:
    """The exact command to exec: claude directly, or a tmux session wrapping it.

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
    claude = ["claude", "--permission-mode", "auto", "--add-dir", str(sibling)]
    if in_tmux:
        return claude
    return ["tmux", "new-session", "-A", "-s", session, "-c", str(repo_root), *claude]


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


def doctor(repo_root: Path, sibling: Path, *, path: str, probes: Probes) -> list[Check]:
    """Verify a LIVE session's environment. Reports; never repairs.

    Deliberately different from :func:`preflight` in one way that is the whole
    point: preflight cleans ``path`` before judging it, because it is about to
    hand a cleaned PATH to a child. The doctor judges the **raw** PATH, because
    it is asking what the session it runs inside actually has. Cleaning first
    here would make it a check that cannot fail — it would launder exactly the
    drift it exists to find (#40 was found by hand for want of this).

    The two checks a python process genuinely cannot make are reported UNKNOWN
    with the reason, rather than asserted: which skills a Claude Code session can
    see, and which permission mode it is in, are facts only the session holds.
    Claiming them from out here would be a probe with one face.
    """
    checks: list[Check] = []

    pin = pinned_version(repo_root)
    resolved = probes.which("graphify", path)
    if resolved is None:
        checks.append(Check("graphify", FAIL, "`graphify` does not resolve on PATH"))
    elif _SHIMS_SEGMENT not in resolved:
        found = probes.version_of(resolved)
        matches = "matches" if found == pin else f"is {found}, pin is {pin}"
        checks.append(
            Check(
                "graphify",
                FAIL,
                f"resolves to {resolved} — an install dir shadowing the shims. Its "
                f"version {matches}, but the entry is frozen and will not follow the "
                f"next bump.",
            )
        )
    else:
        found = probes.version_of(resolved)
        if pin is None:
            checks.append(Check("graphify", UNKNOWN, f"{repo_root.name} pins no graphify version"))
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
    """`kb-setup cc-doctor --sibling <path> [--root <path>]`. Non-zero on any FAIL."""
    sibling: Path | None = None
    args = list(argv)
    i = 0
    while i < len(args):
        if args[i] in {"--sibling", "--root"} and i + 1 < len(args):
            if args[i] == "--sibling":
                sibling = Path(args[i + 1])
            else:
                repo_root = Path(args[i + 1])
            i += 2
            continue
        print(f"[cc-doctor] unknown argument {args[i]!r}", file=sys.stderr)
        return 2
    if sibling is None:
        print("[cc-doctor] --sibling <path> is required", file=sys.stderr)
        return 2

    results = doctor(
        repo_root.resolve(),
        sibling,
        path=os.environ.get("PATH", ""),
        probes=Probes(which=_which, version_of=_version_of),
    )
    mark = {OK: "✔", FAIL: "✗", UNKNOWN: "?"}
    for c in results:
        print(f"  {mark[c.status]} {c.name}: {c.detail}")
    failed = [c for c in results if c.status == FAIL]
    if failed:
        print(
            f"\n[cc-doctor] {len(failed)} FAILED. `mise run cc-fresh` relaunches on a "
            f"clean tmux server; that is the usual fix for a PATH problem.",
            file=sys.stderr,
        )
        return 1
    unknown = sum(c.status == UNKNOWN for c in results)
    print(f"\n[cc-doctor] no failures ({unknown} not verifiable from here — check them in-session)")
    return 0


def cc_main(repo_root: Path, argv: Sequence[str]) -> int:
    """`kb-setup cc --sibling <path> [--session <name>]`. Execs on success."""
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
        print(f"[cc] unknown argument {args[i]!r}", file=sys.stderr)
        return 2
    if sibling is None:
        print("[cc] --sibling <path> is required", file=sys.stderr)
        return 2
    repo_root = repo_root.resolve()
    session = session or repo_root.name

    in_tmux = bool(os.environ.get("TMUX"))
    if fresh:
        # A server outlives the pin that was current when it started, and a pane
        # inherits the PATH of whatever client created it — so a long-lived server
        # is the usual reason a session's environment disagrees with the repo.
        # Killing it is the remedy the preflight's own failure message names.
        if in_tmux:
            print(
                "[cc] --fresh kills the tmux server, and you are inside it — that "
                "would kill this process before it could relaunch. Run it from a "
                "plain terminal instead.",
                file=sys.stderr,
            )
            return 2
        # No server running is the desired state, not an error, so the status is
        # ignored rather than checked.
        subprocess.run(["tmux", "kill-server"], check=False, capture_output=True, timeout=60)
        print("[cc] --fresh: tmux server killed; the new session starts from this shell's env")

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

    argv_out = launch_argv(repo_root, sibling.resolve(), session=session, in_tmux=in_tmux)
    print(f"[cc] preflight OK — rooted in {repo_root.name}, --add-dir {sibling.name}")
    print(f"[cc] {teammate_note(repo_root, in_tmux=in_tmux)}")
    # A CHILD, not `os.execvp`. Two reasons, and the second is the one that bit:
    #   * exec replaces the process image, so anything still buffered in stdout is
    #     LOST — observed on the first live run, where the OK line vanished and
    #     only tmux's error surfaced;
    #   * it lets this function return the launcher's real exit code instead of
    #     never returning, which is what makes the failure path testable.
    # stdio is inherited, so the interactive session behaves identically.
    env = {**os.environ, "PATH": checked.path}
    return subprocess.run(argv_out, env=env, check=False).returncode
