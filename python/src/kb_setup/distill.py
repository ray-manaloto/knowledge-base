"""Distil a session's throwaway scripts into `skill -> mise task -> module` candidates.

Ray, 2026-08-06: *"self-learning/self-improvement workflow should review the
session and create skills of all manual steps being done… make it modular w
skill and mise/python function parameters so the pieces of code are re-usable.
i keep requesting this and it is not being done so we need to try and enforce
this somehow."*

The **enforcement** half shipped as :mod:`kb_setup.skill_lint` (#128) — a
SKILL.md may not instruct a command a mise task owns. This module is the half
that *produces* candidates instead of policing them (#219).

## What it detects, and why not the obvious thing

#219's first cut was *"a command sequence of >=3 steps appearing in >=2
sessions"*. That was **measured against 60 real transcripts (32,826 shaped
steps) and refuted** before this module was written: at every threshold and
every matching form the top of the list is `git add/commit/status/log` and
`grep` — commands that recur constantly and will never become a `kb-*` task.
Loosen the rule and git dominates (2,317 candidates); tighten it and recurrence
collapses (3). There is no threshold in between. The evidence table is
`.agent/kb/reports/agents/distill-detection-probe.md`.

So the unit here is **not frequency**. It is the specific act #160 records as
this repo's most expensive repeated manual step: **writing a throwaway script
and running it.** Five successive mutation harnesses were hand-authored, each
re-acquiring the same ``__pycache__`` defect, because none of them was ever a
module. That act is precisely detectable, needs no threshold, and gives the
detector the FAIL arm #219 demands: **a session that wrote no ad-hoc script
proposes nothing.** A distiller that always finds something is not a detector.

## What it deliberately does NOT do

It **proposes**; it never writes a module, a task or a skill. The 2026-08-06
self-reflection pass measured that a reading agent's output is *leads, not
findings* — 7 of 8 verified claims changed the answer, and 5 of 5 proposed issue
closes were refuted. A distiller with commit access would be that failure mode
with a keyboard.

## Reuse, not reimplementation

Transcript location and iteration come from :mod:`kb_setup.brain`, which already
does it for the SessionEnd audit; ``brain.transcripts_base`` and
``brain.project_transcripts`` were promoted from private for this caller, on the
precedent in ``hook_guard.decide``'s docstring — a caller reaching through a
private name is one that gets refactored out from under.

Every collaborator here is an injected parameter (``detect``, ``signature``,
``is_repo_source``), for the reason ``skill_lint.check`` states: a walker whose
policy is a parameter serves another question without a fork. That is #219's
acceptance criterion, not a style preference.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import brain

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Iterable, Iterator, Sequence

DEFAULT_SESSION_LIMIT = brain.DEFAULT_SESSION_LIMIT

# A script written under one of these prefixes is REPO SOURCE — it is the
# distilled form already, so observing it is not evidence of a manual step.
# Everything else (a scratchpad `.py`, a `/tmp` probe) is ad hoc by construction.
DEFAULT_SOURCE_PREFIXES: tuple[str, ...] = ("python/src/", "tests/")

# ...unless it sits inside a VENDORED clone, which carries its own `python/src`
# and `tests`. That is another project's source tree, so a script written there
# is still ad hoc. `sources/<name>/` clones are gitignored and re-fetched from a
# pinned manifest, which is exactly why one can appear in a transcript path.
DEFAULT_VENDORED_MARKERS: tuple[str, ...] = ("/sources/", "/raw/")

# An interpreter fed a heredoc: `python3 - <<'PY' … PY`, `uv run python - <<EOF`.
# The quoted-or-bare delimiter is captured so the body ends at the RIGHT marker;
# a fixed `EOF` would swallow the rest of a command that used `PY`.
#
# The closer is CONDITIONAL on the dash, and the indent class is **TABS ONLY**.
# Both halves were established by running real bash rather than by reasoning,
# and each half is a defect this pattern actually shipped:
#
#   `cat <<-'PY'` + tab-indented   PY  -> terminates      (so column-0-only MISSES it)
#   `cat <<-'PY'` + space-indented PY  -> does NOT terminate; that line is BODY
#   `cat  <<'PY'` + any indent         -> does NOT terminate
#
# v1 demanded column 0 for both forms, so a TAB-indented `<<-` terminator was
# missed and the lazy body ran forward to the next column-0 delimiter (cold
# lane, P1 on c1374b99e032). v2 then allowed `[ \t]*`, which is the MIRROR
# defect: a space-indented line equal to the delimiter is ordinary body content
# in bash, and treating it as a terminator silently truncates the rest of a real
# script (cold lane round 2, P1 on 37020536f63c).
#
# The round-1 report's own reproduction used SPACES, so the "corruption" it
# showed was in fact faithful bash behaviour. The observation was reproduced and
# the premise was not checked — which is why this comment cites `bash`, not a
# review.
_HEREDOC = re.compile(
    r"(?:^|[;&|]|&&|\|\|)\s*"
    r"(?:\S*/)?(?:python[\d.]*|uv\s+run\s+(?:--\S+\s+)*python[\d.]*)\b[^\n<]*"
    r"<<(?P<dash>-)?\s*['\"]?(?P<delim>[A-Za-z_]\w*)['\"]?\s*\n"
    r"(?P<body>.*?)^(?(dash)\t*)(?P=delim)$",
    re.DOTALL | re.MULTILINE,
)

# An interpreter fed a `-c` payload. Short one-liners are ordinary shell use, so
# a length floor keeps `python -c "print(1)"` out; MIN_INLINE_CHARS is the seam.
#
# The two quote styles get SEPARATE branches, because bash's escape rules differ
# and one rule applied to both is wrong in one direction or the other — verified
# against real bash, not inferred:
#
#   -c "print(\"hi\"); …"     -> `\"` is an escaped quote; the string continues
#   -c 'print(1)\'            -> single quotes have NO escapes at all; the
#                                backslash is literal and the quote CLOSES here
#
# v1 used a shared `.*?`, so an escaped double quote truncated the payload to 7
# characters — which then fell under the length floor, turning a partial capture
# into a total loss with no signal (cold lane, P2 on c1374b99e032). v2 applied
# escape-awareness to BOTH quote styles, the mirror defect: a single-quoted
# payload ending in a backslash kept scanning past its real terminator and glued
# unrelated shell text into the reported script (cold lane round 2, P1 on
# 37020536f63c).
_INLINE = re.compile(
    r"(?:^|[;&|]|&&|\|\|)\s*"
    r"(?:\S*/)?(?:python[\d.]*|uv\s+run\s+(?:--\S+\s+)*python[\d.]*)\b[^\n]*?"
    r"\s-c\s+(?:"
    r"'(?P<sbody>[^']*)'"
    r'|"(?P<dbody>(?:\\.|[^\\"])*)"'
    r")",
    re.DOTALL,
)

MIN_INLINE_CHARS = 120

# How many example scripts a candidate shows before eliding. A DISPLAY bound,
# named rather than inline so the report can state it (`probes` rule 3: a
# display bound is still a bound).
MAX_SHOWN = 4

# `import x`, `import x.y`, `from x import …` — the top-level module only.
_IMPORT = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", re.MULTILINE)

# Modules so ubiquitous in a probe that including them in a signature would make
# every probe look like every other one. Excluded from the fingerprint only —
# still reported, so a reader sees the real import list.
DEFAULT_UBIQUITOUS: frozenset[str] = frozenset({"sys", "os", "pathlib", "__future__"})

# The repo surfaces a probe can be ABOUT. Ordered most-specific first so a body
# mentioning `sources/extractions` is not also filed under bare `sources/`.
# Author-chosen, and deliberately so: this is the vocabulary of questions this
# repo asks, and a generic path-extractor would file every probe under `python/`.
DEFAULT_SURFACES: tuple[str, ...] = (
    "sources/extractions",
    "sources/media",
    "graphify-out/memory",
    "graphify-out/reflections",
    ".agent/kb/review",
    ".agent/kb/reports",
    ".agent/kb/gates",
    ".agent/plans",
    "python/src/kb_setup",
    ".claude/skills",
    ".claude/rules",
    ".claude/agents",
    "docs/research",
    "docs/currency",
    "docs/goals",
    "currency.toml",
    "mise.toml",
    "hk.pkl",
)


@dataclass(frozen=True)
class Policy:
    """Every knob this walker has, as ONE injectable value.

    A bundle rather than eight loose keyword arguments, for two reasons. It is
    what makes the pieces reusable in the sense #219 asks for — a caller that
    wants "an ad-hoc step means a shell heredoc" swaps ``detect`` and keeps
    everything else, and a test swaps ``min_scripts`` without restating the
    defaults. And it keeps :func:`distill` inside ruff's argument ceiling
    honestly, rather than by suppressing the rule that noticed the smell.

    ``detect`` and ``signature`` are the two that carry real policy: what counts
    as a script, and when two scripts are the same shape.
    """

    detect: Callable[[str], Iterable[tuple[str, str]]]
    signature: Callable[[str], str]
    is_repo_source: Callable[[str], bool]
    min_scripts: int = 2
    min_sessions: int = 1


@dataclass(frozen=True)
class Script:
    """One ad-hoc script observed in one session: authored inline, then run."""

    session: str
    kind: str
    imports: tuple[str, ...]
    body: str

    @property
    def excerpt(self) -> str:
        """First non-blank, non-import line — enough to recognise the probe."""
        for line in self.body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "import ", "from ", '"""')):
                return stripped[:120]
        return self.body.strip()[:120]


@dataclass(frozen=True)
class Candidate:
    """A recurring throwaway-script shape, proposed for distillation."""

    signature: str
    scripts: tuple[Script, ...]

    @property
    def sessions(self) -> tuple[str, ...]:
        """Distinct sessions this shape was written in, newest-first order kept."""
        return tuple(dict.fromkeys(s.session for s in self.scripts))

    @property
    def imports(self) -> tuple[str, ...]:
        """Every module any script in this group imported, sorted."""
        return tuple(sorted({imp for s in self.scripts for imp in s.imports}))


@dataclass(frozen=True)
class Report:
    """One distill run. ``candidates`` empty is the expected, common outcome."""

    candidates: tuple[Candidate, ...]
    scanned: tuple[str, ...]
    scripts_seen: int

    @property
    def found(self) -> bool:
        """True when at least one shape cleared both thresholds."""
        return bool(self.candidates)


def import_signature(body: str, *, ubiquitous: frozenset[str] = DEFAULT_UBIQUITOUS) -> str:
    """Fingerprint a script by its non-ubiquitous imports.

    Deliberately coarse, and stated as such wherever the report prints it: two
    probes that import ``{json, re}`` are grouped even if they ask different
    questions. A finer signature (call graph, argv shape) would split the very
    recurrence this module exists to surface — five mutation harnesses were five
    different programs solving one problem. Grouping too eagerly produces a lead
    a human discards in seconds; grouping too finely produces nothing at all,
    which is the failure the frequency probe already measured.

    A script with no distinctive import returns ``""`` and is never a candidate:
    a bare-stdlib one-liner has no shape to reuse.
    """
    mods = set(_IMPORT.findall(body)) - ubiquitous
    return "+".join(sorted(mods))


def surface_signature(
    body: str,
    *,
    surfaces: tuple[str, ...] = DEFAULT_SURFACES,
    ubiquitous: frozenset[str] = DEFAULT_UBIQUITOUS,
) -> str:
    """Fingerprint a script by the repo SURFACES it touches, plus its imports.

    :func:`import_signature` alone was measured and rejected as the default: over
    40 real sessions it put **153 of 785 scripts in one ``json`` bucket**, which
    is a pile rather than a lead. Imports say which *library* a probe used;
    surfaces say which *question* it asked, and that is the axis a distilled
    module would be named along — ``sources/extractions`` and
    ``.agent/kb/review`` are different tools no matter that both parse JSON.

    A script touching no known surface falls back to its imports, and one with
    neither returns ``""`` and can never be a candidate: a probe with no shape
    has nothing to reuse.
    """
    hit = tuple(s for s in surfaces if s in body)
    mods = sorted(set(_IMPORT.findall(body)) - ubiquitous)
    if not hit:
        return "+".join(mods)
    return " ".join(hit) + (f" [{'+'.join(mods)}]" if mods else "")


def detect_scripts(command: str) -> Iterator[tuple[str, str]]:
    """Yield ``(kind, body)`` for each ad-hoc script authored inside ``command``.

    Two shapes, both of which mean "a program was written here rather than
    called": an interpreter fed a heredoc, and an interpreter fed a ``-c``
    payload above :data:`MIN_INLINE_CHARS`. The length floor is what keeps
    ``python -c "print(1)"`` — ordinary shell arithmetic — out of the corpus.
    """
    for m in _HEREDOC.finditer(command):
        yield "heredoc", m.group("body")
    for m in _INLINE.finditer(command):
        # Exactly one of the two quote branches matches; the other is None.
        body = m.group("sbody") if m.group("sbody") is not None else m.group("dbody")
        if body is not None and len(body) >= MIN_INLINE_CHARS:
            yield "inline", body


def _tool_uses(path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    """Yield ``(tool_name, tool_input)`` for every tool call in one transcript.

    Defensive by design: a transcript is an append-only log written by another
    process, so a truncated final line is normal rather than exceptional and
    must not abort the scan.
    """
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name")
            payload = block.get("input")
            if isinstance(name, str) and isinstance(payload, dict):
                yield name, payload


def _written_script(
    payload: dict[str, object], *, is_repo_source: Callable[[str], bool]
) -> str | None:
    """The body of a `Write` of a ``.py`` file OUTSIDE the repo's source tree.

    A module written to ``python/src/`` is the distilled form already — counting
    it would make every real fix look like a manual step, which is the inverse
    of this module's job.
    """
    target = payload.get("file_path")
    body = payload.get("content")
    if not isinstance(target, str) or not isinstance(body, str):
        return None
    if not target.endswith(".py") or is_repo_source(target):
        return None
    return body


def repo_source(
    path: str,
    *,
    prefixes: tuple[str, ...] = DEFAULT_SOURCE_PREFIXES,
    vendored: tuple[str, ...] = DEFAULT_VENDORED_MARKERS,
) -> bool:
    """True when ``path`` names a file in THIS repo's committed source tree.

    A vendored clone under ``sources/<name>/`` carries its own ``python/src``
    and ``tests`` — that is somebody else's source, and an ad-hoc script written
    there is still ad hoc. The plain substring test called it ours and silently
    dropped it from detection (cold lane, P3 on c1374b99e032).

    A vendored marker only disqualifies when it appears **before** the source
    prefix. Testing it anywhere in the string was the mirror of the bug it fixed
    (cold lane round 2, P3): `python/src/.../sources/...` is still our source,
    and a bare substring test would have disowned it. Position is the whole
    question — "is the prefix inside a clone" is not "does the word appear".

    **What this still cannot see, stated because a check owes that:** it decides
    from the path string alone, so a `python/src` belonging to an unrelated
    checkout elsewhere on disk would read as ours. That case does not arise for
    the caller here — transcripts are located per project directory, so their
    paths are this project's — and closing it properly needs the repo root
    threaded to a predicate whose whole value is being a one-argument callable.
    If this is ever called on paths from another source, pass ``vendored`` or
    replace the predicate through :class:`Policy`.
    """
    anchored = f"/{path.replace('\\', '/')}"
    for prefix in prefixes:
        at = anchored.find(f"/{prefix}")
        if at == -1:
            continue
        if any(marker in anchored[:at] for marker in vendored):
            continue
        return True
    return False


def scripts_in(
    path: Path,
    *,
    detect: Callable[[str], Iterable[tuple[str, str]]] = detect_scripts,
    is_repo_source: Callable[[str], bool] = repo_source,
) -> list[Script]:
    """Every ad-hoc script authored in one transcript, in the order written."""
    session = path.stem
    found: list[Script] = []
    for name, payload in _tool_uses(path):
        bodies: list[tuple[str, str]] = []
        if name == "Bash":
            command = payload.get("command")
            if isinstance(command, str):
                bodies.extend(detect(command))
        elif name == "Write":
            body = _written_script(payload, is_repo_source=is_repo_source)
            if body is not None:
                bodies.append(("file", body))
        for kind, body in bodies:
            found.append(
                Script(
                    session=session,
                    kind=kind,
                    imports=tuple(sorted(set(_IMPORT.findall(body)))),
                    body=body,
                )
            )
    return found


DEFAULT_POLICY = Policy(
    detect=detect_scripts,
    signature=surface_signature,
    is_repo_source=repo_source,
)


def distill(
    root: Path,
    *,
    transcripts: Sequence[Path] | None = None,
    limit: int = DEFAULT_SESSION_LIMIT,
    policy: Policy = DEFAULT_POLICY,
) -> Report:
    """Group this project's recent ad-hoc scripts into distillation candidates.

    ``transcripts`` is injected by tests and by any caller that already knows
    which sessions it means; when ``None`` the project's ``limit`` most recent
    are located through :mod:`kb_setup.brain` rather than by a second locator.

    ``policy`` carries every decision this walker makes, so it serves a
    different notion of "an ad-hoc step" without being forked — the same reason
    ``skill_lint.check`` takes ``decide``. Vary one field with
    ``dataclasses.replace(DEFAULT_POLICY, min_scripts=1)``.

    The defaults are *2 scripts in 1 session* because writing the same probe
    twice in one sitting is already the cost this module exists to remove;
    requiring a second session would mean the lesson is only learnable after it
    has been paid for twice.
    """
    paths = (
        list(transcripts)
        if transcripts is not None
        else brain.project_transcripts(brain.transcripts_base(), root, limit=limit)
    )
    grouped: dict[str, list[Script]] = {}
    scripts_seen = 0
    for path in paths:
        for script in scripts_in(path, detect=policy.detect, is_repo_source=policy.is_repo_source):
            scripts_seen += 1
            key = policy.signature(script.body)
            if not key:
                continue
            grouped.setdefault(key, []).append(script)

    candidates = [
        Candidate(signature=key, scripts=tuple(group))
        for key, group in grouped.items()
        if len(group) >= policy.min_scripts
        and len({s.session for s in group}) >= policy.min_sessions
    ]
    candidates.sort(key=lambda c: (-len(c.scripts), -len(c.sessions), c.signature))
    return Report(
        candidates=tuple(candidates),
        scanned=tuple(p.stem for p in paths),
        scripts_seen=scripts_seen,
    )


def render(report: Report) -> str:
    """The human-facing proposal. Names evidence; never names a module for you."""
    out: list[str] = []
    n_sessions = len(report.scanned)
    if not report.scanned:
        return (
            "distill: NO TRANSCRIPTS FOUND — the detector did not run. "
            "This is not a clean result; check the project dir before reading it "
            "as 'nothing to distil'.\n"
        )
    out.append(
        f"distill: {n_sessions} session(s) scanned, "
        f"{report.scripts_seen} ad-hoc script(s) seen, "
        f"{len(report.candidates)} candidate(s)"
    )
    if not report.found:
        out.append(
            "  nothing to propose — no script shape recurred. That is the "
            "expected result for a session of one-off work, and it is what "
            "makes a proposal mean something."
        )
        return "\n".join(out) + "\n"

    out.append(
        "\n  Grouped by IMPORT SIGNATURE, which is deliberately coarse: two "
        "probes sharing imports are grouped even if they asked different "
        "questions. Treat each as a LEAD, not a finding."
    )
    for i, cand in enumerate(report.candidates, start=1):
        out.append(
            f"\n{i}. {cand.signature}  "
            f"— {len(cand.scripts)} script(s) across {len(cand.sessions)} session(s)"
        )
        out.append(f"   imports : {', '.join(cand.imports)}")
        out.extend(
            f"   [{script.kind:>7}] {script.session[:8]}  {script.excerpt}"
            for script in cand.scripts[:MAX_SHOWN]
        )
        if len(cand.scripts) > MAX_SHOWN:
            out.append(f"   … and {len(cand.scripts) - MAX_SHOWN} more")
        out.append("   propose:")
        out.append("     python/src/kb_setup/<name>.py   — the logic, with the")
        out.append("       varying parts as keyword-only PARAMETERS (see")
        out.append("       skill_lint.check(root, *, glob, exclude, decide))")
        out.append("     mise.toml  [tasks.kb-<name>]    — a seam, one command")
        out.append("     a skill ONLY if an agent must be told when to run it;")
        out.append("       otherwise wire the task into an existing skill")
    out.append(
        "\n  A candidate is evidence a program was written twice, not a "
        "decision that it should exist. Read the excerpts before building."
    )
    return "\n".join(out) + "\n"


def _int_flag(rest: list[str], name: str, default: int) -> int:
    """``--name <int>`` from ``rest``, or ``default``.

    A non-numeric value falls back rather than raising: this command is advisory
    and printing the proposal at the default limit beats aborting over a typo.
    """
    if name in rest and rest.index(name) + 1 < len(rest):
        raw = rest[rest.index(name) + 1]
        if raw.isdigit():
            return int(raw)
    return default


def distill_main(root: Path, args: Sequence[str] = ()) -> int:
    """CLI entry: print the proposal. Always rc 0 — a lead is not a failure.

    Deliberately never a gate. An undistilled probe is a signal about future
    cost, and a check that fails the build over it would be argued past within a
    round; `mise run kb-currency` is the same call for the same reason.
    """
    rest = list(args)
    report = distill(
        root,
        limit=_int_flag(rest, "--limit", DEFAULT_SESSION_LIMIT),
        policy=replace(
            DEFAULT_POLICY,
            min_scripts=_int_flag(rest, "--min-scripts", DEFAULT_POLICY.min_scripts),
        ),
    )
    print(render(report), end="")
    return 0
