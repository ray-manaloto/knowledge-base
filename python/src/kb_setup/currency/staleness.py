"""Does the built graph still match the committed inputs it was built from?

The question the currency engine could not previously ask. `sync` compares the
tool against its pin and the OUTPUTS against the stamp; nothing compared the
INPUTS, so editing a manifest or landing a new extraction chunk left a graph that
described an older corpus while every check stayed green.

Three things this module refuses to do, each because the alternative was tried
and refuted:

* **It never rebuilds.** It reports; `mise run kb-build` fixes. A detector that
  repaired what it detected could never be observed failing.
* **It never blocks and always exits 0.** `graphify-out/` is gitignored and
  DERIVED, so a stale local graph is not part of what ships and cannot be a
  shipping defect (#88).
* **It reports under its own header**, not folded into the version-drift block.
  That block's remedy line says "run the tool-currency skill", which is the wrong
  fix for a stale graph and would print an instruction that does not repair what
  it is reporting.

It names WHAT moved, per path. A fingerprint proves THAT something changed and
never what — so the comparison is per-file and the paths are printed, following
`kb-update`'s changed-page worklist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup.currency import sync

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from kb_setup.currency.config import ToolSpec

#: Nothing to check here — no inputs declared, no stamp configured, wrong host.
#: Silent, and genuinely not-applicable rather than not-checked.
SKIP = "skip"
#: There is no build to compare against. NOT drift: a fresh clone has neither
#: stamp nor graph, and calling that "your whole corpus went stale" would make
#: the very first session in a new clone report a defect that does not exist.
NEVER_BUILT = "never-built"
#: A build exists but the question could not be asked — an unreadable stamp, or
#: one written before inputs were fingerprinted. Never rendered as a pass.
NOT_VERIFIABLE = "not-verifiable"
#: Asked, and the inputs disagree with what the graph was built from.
CHANGED = "changed"
#: Asked, and they agree.
OK = "ok"

_HEADER = "[graph]"


@dataclass(frozen=True)
class InputStatus:
    """One tool's graph-vs-inputs verdict.

    `changes` is populated only for :data:`CHANGED`, and each entry is a rendered
    `<path>  (<what>)` line rather than a bare path — which of *changed*, *added*
    and *removed* fired is the first thing a reader needs, and rebuilding that
    distinction from the path alone is impossible.
    """

    tool: str
    state: str
    detail: str = ""
    changes: tuple[str, ...] = ()

    @property
    def quiet(self) -> bool:
        """True when this verdict prints nothing. Only OK and SKIP are silent."""
        return self.state in (OK, SKIP)


def _read_stamp_strict(path: Path) -> dict[str, object] | None:
    """The stamp as a dict, or None when it exists and cannot be read.

    `sync.read_stamp` collapses absent and unreadable to `{}`, which is right for
    its caller and wrong here: absent means *never built* and unreadable means
    *not verifiable*, and this module's whole ordering rule depends on telling
    them apart. Callers check `path.exists()` first, so reaching this function at
    all means the file is there.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    return {str(k): v for k, v in data.items()} if isinstance(data, dict) else None


def check_inputs(repo_root: Path, spec: ToolSpec) -> InputStatus:
    """Compare the recorded inputs against the live ones for one tool.

    The ordering is the load-bearing part. **Absence of a build short-circuits to
    NEVER_BUILT before a single input is compared** (#89): a fresh clone has no
    recorded map at all, so comparing first would move 43 of 43 fingerprints and
    announce that the entire corpus had gone stale on the first session after a
    clone. That figure defeats every fingerprint scheme equally — sha256 included
    — so it is the reason for this ordering and is *not* evidence about which
    fingerprint to use.
    """
    if not spec.inputs or not spec.stamp or not spec.applies_here():
        return InputStatus(spec.name, SKIP)

    # `spec.stamp` is non-empty (guarded above), so this is a real path — read
    # directly rather than through `sync.stamp_path`, whose Optional return would
    # need narrowing that says nothing a reader does not already know.
    stamp_file = repo_root / spec.stamp
    missing = _no_build_reason(repo_root, spec, stamp_file)
    if missing is not None:
        return InputStatus(spec.name, NEVER_BUILT, missing)

    recorded, why_not = _recorded_inputs(spec, stamp_file)
    if recorded is None:
        return InputStatus(spec.name, NOT_VERIFIABLE, why_not)

    live = sync.input_fingerprints(repo_root, spec)
    # BEFORE the diff. An input that exists but cannot be read was not verified,
    # and `_diff` cannot say so: its `set(recorded) | set(live)` union only sees
    # paths one side knows about, so a file that is NEW and unreadable is missing
    # from both and the diff comes back empty — OK, for an input nobody read.
    # Reproduced end to end by the cold lane, round 2.
    blind = tuple(rel for rel, fp in live.items() if fp == sync.UNREADABLE)
    if blind:
        return InputStatus(
            spec.name,
            NOT_VERIFIABLE,
            f"{len(blind)} input(s) could not be read: {', '.join(blind)}",
        )

    changes = _diff(recorded, live)
    if changes:
        return InputStatus(spec.name, CHANGED, f"{len(changes)} input(s) moved", changes)
    return InputStatus(spec.name, OK)


def _recorded_inputs(spec: ToolSpec, stamp_file: Path) -> tuple[dict[str, str] | None, str]:
    """The stamp's recorded input map, or `(None, why it cannot be used)`.

    The two reasons are different states and are worded as such: a stamp we
    cannot parse, and one written by an engine that never asked the question.
    Both report *not verifiable* — neither may report a pass.
    """
    stamp = _read_stamp_strict(stamp_file)
    if stamp is None:
        return None, f"{spec.stamp} is unreadable"
    recorded = sync.stamped_input_fingerprints(stamp)
    if recorded is None:
        return None, "the stamp predates input fingerprinting — rebuild to record them"
    return recorded, ""


def _no_build_reason(repo_root: Path, spec: ToolSpec, stamp_file: Path) -> str | None:
    """Why there is no build to compare against, or None when one exists.

    Both halves are checked, and either alone is enough: an aborted build clears
    the stamp while leaving the graph, and a `rm graphify-out/graph.json` leaves
    the stamp while removing the graph. Reporting *never built* for both is right
    — neither state is a corpus that went stale.
    """
    if not stamp_file.exists():
        return "no build stamp"
    artifact = repo_root / spec.artifact if spec.artifact else None
    if artifact is not None and not artifact.exists():
        return f"{spec.artifact} is absent"
    return None


def _diff(recorded: dict[str, str], live: dict[str, str]) -> tuple[str, ...]:
    """Rendered `<path>  (<what>)` lines for every input that moved.

    Sorted by path so two runs over the same divergence print identically — an
    unstable order would make a diff of two reports look like new findings.
    """
    lines: list[str] = []
    for rel in sorted(set(recorded) | set(live)):
        if rel not in live:
            lines.append(f"{rel}  (removed since the build)")
        elif rel not in recorded:
            lines.append(f"{rel}  (added since the build)")
        elif recorded[rel] != live[rel]:
            lines.append(f"{rel}  (content changed)")
    return tuple(lines)


def report(statuses: Iterable[InputStatus]) -> None:
    """Print the non-clean verdicts under `[graph]`. Silent when everything agrees.

    The two non-clean shapes are kept apart for the same reason `sync`'s DRIFT and
    NOT-CHECKED are: "the inputs moved" and "we could not ask" are different
    answers, and one header over both lets the weaker borrow the stronger's
    weight — or lets a real finding be dismissed as a flaky probe.
    """
    loud = [s for s in statuses if not s.quiet]
    changed = [s for s in loud if s.state == CHANGED]
    blind: Sequence[InputStatus] = [s for s in loud if s.state != CHANGED]

    for status in changed:
        print(
            f"{_HEADER} corpus inputs changed since the graph was built — run `mise run kb-build`:"
        )
        for line in status.changes:
            print(f"{_HEADER}   {line}")
    for status in blind:
        if status.state == NEVER_BUILT:
            # Deliberately not the word "stale", and deliberately not in the
            # changed block: nothing has gone out of date, there is simply no
            # graph here yet. This is what a fresh clone sees.
            print(
                f"{_HEADER} no graph has been built here yet ({status.detail}) — "
                f"run `mise run kb-build`"
            )
        else:
            print(f"{_HEADER} NOT CHECKED against its inputs (this is not a pass): {status.detail}")
