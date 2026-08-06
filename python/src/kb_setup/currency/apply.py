"""Step 2's "and update" — apply an authorized bump to the committable files.

The engine EDITS two things and returns what changed: the `mise.toml` pin and,
if the tool has one, its source manifest (`ref` → the new tag, `commit` → that
tag's SHA). It does NOT open the PR — the repo's own ship task does (H3),
because the engine is shared and each repo ships differently.

Three invariants, each load-bearing:

* **G7 — authorization.** Only a verdict with `auto_apply=True` (all six gates
  passed) may be applied. `apply` re-checks this and refuses otherwise, so a
  caller cannot route an ambiguous verdict through by mistake. Fails closed.
* **G8 — committable parts only.** The pin and the manifest are edited; the graph
  is NOT rebuilt (`graphify-out/` is gitignored and huge). Step 1 then reports
  "rebuild pending" until `mise run kb-build` runs locally — the note this
  returns says exactly that.
* **H4 — session-only.** Nothing here is wired to the daily CI job. It is called
  only from the tool-currency skill, which a human is driving; the daily `run`
  reports drift and never applies.

The v1.0.0 trap (a version on PyPI but tagged nowhere in git) is guarded twice:
gate 2 already required a matching GitHub release before `auto_apply`, and
`manifest.resolve_tag` raises here if the git tag does not resolve — so a
manifest is never pinned to a tag that does not exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kb_setup import manifest as mf
from kb_setup.currency import skill

if TYPE_CHECKING:
    from pathlib import Path

    from kb_setup.currency.config import ToolSpec
    from kb_setup.currency.decide import Verdict


@dataclass(frozen=True)
class ApplyResult:
    """What an apply changed, for the caller (the ship task) to commit and PR."""

    tool: str
    from_version: str
    to_version: str
    changed: tuple[str, ...]  # repo-relative paths edited
    manifest_ref: str = ""  # "" when the tool declares no manifest
    manifest_commit: str = ""
    note: str = ""


class NotAuthorizedError(RuntimeError):
    """Raised when apply is asked to move a version the gates did not authorize."""


def _pin_line_matches(stripped: str, mise_key: str) -> bool:
    """Whether a stripped mise.toml line assigns `mise_key`.

    Matched structurally (`<key> =`), quoted or bare, so a mention of the key in
    a comment or another tool's value can never be mistaken for the assignment.
    """
    for head in (f'"{mise_key}"', mise_key):
        rest = stripped[len(head) :].lstrip()
        if stripped.startswith(head) and rest.startswith("="):
            return True
    return False


def set_pin_version(text: str, mise_key: str, new_version: str) -> tuple[str, str]:
    """Return `(new_text, old_version)` with `mise_key`'s pin moved to `new_version`.

    Deliberately a targeted TEXT edit, not `mise use` and not a tomllib
    round-trip. `mise use` INSTALLS as it edits (verified 2026-07-24: it failed
    to install a not-yet-released version and left the file untouched), which
    couples the pin edit to a successful install and breaks G8's "committable
    parts only, rebuild is separate". A tomllib round-trip would drop comments
    and reformat the whole file. This moves only the version token, preserving
    the table/bare form, the `extras`, comments, and layout.

    Raises `KeyError` if the key is not found and `ValueError` if its line has no
    recognisable version — never a silent no-op that reports success while
    changing nothing.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not _pin_line_matches(line.strip(), mise_key):
            continue
        # Table form: `... version = "0.9.25" ...`. Bare form: `KEY = "0.9.25"`.
        table = re.search(r'(version\s*=\s*")([^"]*)(")', line)
        if table:
            old = table.group(2)
            lines[i] = line[: table.start(2)] + new_version + line[table.end(2) :]
            return "".join(lines), old
        bare = re.search(r'=\s*"([^"]*)"', line)
        if bare:
            old = bare.group(1)
            lines[i] = line[: bare.start(1)] + new_version + line[bare.end(1) :]
            return "".join(lines), old
        raise ValueError(f"mise.toml line for {mise_key!r} has no version to replace: {line!r}")
    raise KeyError(f"no mise.toml pin found for {mise_key!r}")


def _skill_warnings(result: skill.SkillResult) -> list[str]:
    """The skill-refresh conditions that make a bump NOT clean, led with.

    Both are damage a reader would otherwise have to find by parsing prose, or
    by noticing an absence:

    - `unrepaired` — the installer's rewrite is still sitting in the working
      tree, so whoever commits the bump picks it up. `_repair` reports it by
      re-reading `git status`, never by trusting an exit code.
    - `lost_addenda` — a note THIS repo added to the generated skill is gone and
      could not be put back. It is invisible in the diff, because the file
      simply reads as regenerated; leading with it is the only way a reviewer
      learns it happened.

    Extracted from `apply` rather than inlined: the second condition pushed that
    function past its complexity ceiling, and the honest fix for "one more
    branch" is a named function, not a suppression (`do-not.md` #9).
    """
    warnings: list[str] = []
    # The reverted BYTES, not just the filenames — and here as much as at the
    # standalone entry point. `currency.apply` is the caller a human reads before
    # committing an auto-applied bump, so dropping the delta here is precisely
    # the "discarded without trace" case the capture exists to prevent, on the
    # path that gets less scrutiny (cold lane round 2 on ea6ab63).
    if result.repair_delta:
        warnings.append(
            "the installer's changes were reverted; it wanted:\n" + result.repair_delta.rstrip()
        )
    if result.lost_addenda:
        warnings.append(
            f"⚠ local addendum lost: {', '.join(result.lost_addenda)} — a note this repo "
            f"added to the generated skill is gone; re-anchor or retire it in "
            f"currency.skill.ADDENDA"
        )
    if result.unrepaired:
        warnings.append(
            f"⚠ working tree still dirty: {', '.join(result.unrepaired)} — "
            f"the installer's changes were NOT reverted; inspect before committing"
        )
    return warnings


def apply(repo_root: Path, spec: ToolSpec, verdict: Verdict) -> ApplyResult:
    """Edit the committable files for an authorized bump; return what changed.

    Never rebuilds the graph (G8) and never opens a PR (H3) — that is the ship
    task's job. Raises `NotAuthorizedError` unless the verdict authorizes the bump,
    and propagates `manifest.resolve_tag`'s error if the target tag does not
    exist in git (the v1.0.0-trap guard).
    """
    if spec.source_only:
        # Fail closed, and say what the real remedy is. A source-only tool has no
        # `[tools]` entry, so the pin edit below would fail anyway — but it would
        # fail with a KeyError about a mise key nobody declared, which reads as a
        # bug in the engine rather than as "this is the wrong verb for this tool".
        raise NotAuthorizedError(
            f"{spec.name} is an ingested source, not an installed tool — advance it with "
            f"`mise run kb-update -- {spec.name}`, which moves {spec.manifest} and "
            f"re-extracts, rather than editing a mise pin that does not exist"
        )
    if not verdict.auto_apply:
        raise NotAuthorizedError(
            f"{spec.name}: verdict is not auto-apply — "
            f"{len(verdict.ambiguities)} gate(s) still open; resolve them via the interview first"
        )
    if not verdict.has_upgrade:
        raise NotAuthorizedError(f"{spec.name}: no upgrade pending ({verdict.current} is current)")

    mise_path = repo_root / "mise.toml"
    new_text, old = set_pin_version(
        mise_path.read_text(encoding="utf-8"), spec.mise_key, verdict.latest
    )
    if old != verdict.current:
        # The file moved under us between the verdict and the apply. Refuse rather
        # than bump from a state the gates never evaluated.
        raise NotAuthorizedError(
            f"{spec.name}: mise.toml pins {old!r}, but the verdict was computed "
            f"against {verdict.current!r} — re-run the workflow before applying"
        )

    # Resolve EVERYTHING that can fail before writing ANYTHING, so a bad tag or a
    # missing manifest leaves the tree untouched rather than half-applied.
    changed: list[str] = ["mise.toml"]
    manifest_ref = ""
    manifest_commit = ""
    manifest_obj: mf.Manifest | None = None
    if spec.manifest:
        manifest_obj = mf.load(repo_root / spec.manifest)
        manifest_ref, manifest_commit = mf.resolve_tag(manifest_obj.url, verdict.latest)
        changed.append(spec.manifest)

    # Past this point nothing raises, so the two writes are effectively atomic.
    if manifest_obj is not None:
        mf.write_pin(manifest_obj, ref=manifest_ref, commit=manifest_commit)
    mise_path.write_text(new_text, encoding="utf-8")

    # THE SKILL, refreshed here rather than by a task someone must remember (Ray,
    # 2026-08-03). A project-scoped agent skill is the fourth thing a bump has to
    # carry — the pin and manifest are written above, the clone follows from
    # `graph._ensure_clone` on the next build — and it was the one nothing moved:
    # graphify's skill stamp sat at 0.9.23 across eight releases.
    #
    # AFTER the atomic writes, deliberately. It shells out to an installer, which
    # is the one step here that can fail for reasons unrelated to the version
    # (missing binary, dirty tree). Running it first would mean an installer
    # failure blocked a pin move that was otherwise fully authorized; running it
    # last means a failure is REPORTED in the note while the pin still lands.
    # `refresh` returns rather than raises for exactly that reason.
    skill_result = skill.refresh(repo_root, spec)
    if skill_result.changed:
        changed.extend(skill_result.changed)

    notes = [*_skill_warnings(skill_result)]
    notes.append("rebuild pending — run `mise run kb-build` locally to re-stamp the graph")
    if spec.skill_dir:
        notes.append(f"skill: {skill_result.note}")
    return ApplyResult(
        tool=spec.name,
        from_version=verdict.current,
        to_version=verdict.latest,
        changed=tuple(dict.fromkeys(changed)),
        manifest_ref=manifest_ref,
        manifest_commit=manifest_commit,
        note="; ".join(notes),
    )
