# Copyright (c) 2026 Raymond Manaloto
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
from dataclasses import dataclass, replace
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


@dataclass(frozen=True)
class _PinEdit:
    """Prepared pin edits, resolved before any file is written."""

    path: Path
    text: str
    old: str
    extra_path: Path | None = None
    extra_text: str = ""


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


def set_expected_version(text: str, tool: str, new_version: str) -> tuple[str, str]:
    """Move one ``[tool.<name>] expected`` value without reformatting the TOML."""
    section = f"[tool.{tool}]"
    lines = text.splitlines(keepends=True)
    active = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            active = stripped == section
            continue
        if not active or not stripped.startswith("expected"):
            continue
        match = re.search(r'(expected\s*=\s*")([^"]+)(")', line)
        if not match:
            raise ValueError(f"{section} expected line has no quoted version: {line!r}")
        old = match.group(2)
        lines[index] = line[: match.start(2)] + new_version + line[match.end(2) :]
        return "".join(lines), old
    raise KeyError(f"no expected version found under {section}")


def set_exact_dependency_version(
    text: str, package: str, current: str, new_version: str
) -> tuple[str, bool]:
    """Move an exact quoted dependency when this repo declares one."""
    old = f'"{package}=={current}"'
    if old not in text:
        return text, False
    return text.replace(old, f'"{package}=={new_version}"', 1), True


def _prepare_pin_edit(repo_root: Path, spec: ToolSpec, verdict: Verdict) -> _PinEdit:
    """Prepare either a mise pin or a self-managed expected/dependency pin edit."""
    if not spec.self_managed:
        path = repo_root / "mise.toml"
        text, old = set_pin_version(path.read_text(encoding="utf-8"), spec.mise_key, verdict.latest)
        return _PinEdit(path, text, old)

    path = repo_root / "currency.toml"
    if not path.is_file():
        raise NotAuthorizedError(
            f"{spec.name}: no `mise_key` and no currency.toml expected pin; "
            "bump it where it is actually pinned (for example pyproject.toml)"
        )
    text, old = set_expected_version(
        path.read_text(encoding="utf-8"), spec.name, verdict.latest.lstrip("v")
    )
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return _PinEdit(path, text, old)
    candidate, moved = set_exact_dependency_version(
        pyproject.read_text(encoding="utf-8"), spec.name, verdict.current, verdict.latest
    )
    return _PinEdit(path, text, old, pyproject if moved else None, candidate if moved else "")


def _authorize(spec: ToolSpec, verdict: Verdict, *, reviewed: bool) -> None:
    """Fail closed unless automation or an explicit reviewed decision authorizes the bump."""
    if spec.source_only:
        raise NotAuthorizedError(
            f"{spec.name} is an ingested source, not an installed tool — advance it with "
            f"`mise run kb-update -- {spec.name}`, which moves {spec.manifest} and "
            f"re-extracts, rather than editing a mise pin that does not exist"
        )
    if not verdict.auto_apply and not reviewed:
        raise NotAuthorizedError(
            f"{spec.name}: verdict is not auto-apply — "
            f"{len(verdict.ambiguities)} gate(s) still open; resolve them via the interview first"
        )
    if not verdict.has_upgrade:
        raise NotAuthorizedError(f"{spec.name}: no upgrade pending ({verdict.current} is current)")
    if not spec.mise_key and not spec.self_managed:
        raise NotAuthorizedError(
            f"{spec.name}: no `mise_key`, so there is no mise.toml pin to move — "
            "bump it where it is actually pinned (pyproject.toml for ruff/ty, or "
            "`expected` in currency.toml for a self-updating tool), then re-run"
        )


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


def apply(
    repo_root: Path,
    spec: ToolSpec,
    verdict: Verdict,
    *,
    reviewed: bool = False,
) -> ApplyResult:
    """Edit the committable files for an authorized bump; return what changed.

    Never rebuilds the graph (G8) and never opens a PR (H3) — that is the ship
    task's job. Raises `NotAuthorizedError` unless the verdict authorizes the bump,
    and propagates `manifest.resolve_tag`'s error if the target tag does not
    exist in git (the v1.0.0-trap guard).
    """
    _authorize(spec, verdict, reviewed=reviewed)

    pin = _prepare_pin_edit(repo_root, spec, verdict)
    if pin.old != verdict.current:
        # The file moved under us between the verdict and the apply. Refuse rather
        # than bump from a state the gates never evaluated.
        raise NotAuthorizedError(
            f"{spec.name}: {pin.path.name} pins {pin.old!r}, but the verdict was computed "
            f"against {verdict.current!r} — re-run the workflow before applying"
        )

    # Resolve EVERYTHING that can fail before writing ANYTHING, so a bad tag or a
    # missing manifest leaves the tree untouched rather than half-applied.
    changed: list[str] = [pin.path.name]
    if pin.extra_path is not None:
        changed.append(pin.extra_path.name)
    manifest_ref = ""
    manifest_commit = ""
    manifest_obj: mf.Manifest | None = None
    if spec.manifest:
        manifest_obj = mf.load(repo_root / spec.manifest)
        # `prefix=` is the half of #245 that did NOT land the first time. Without
        # it this call knows only `v<version>` and `<version>`, so an authorized
        # apply for codex (tagged `rust-v0.147.0`) raised "no tag found" and
        # aborted the whole bump — while `currency.toml` carried a comment saying
        # the prefix was wired in, because the SYNC half of it was.
        manifest_ref, manifest_commit = mf.resolve_tag(
            manifest_obj.url, verdict.latest, prefix=spec.tag_prefix
        )
        changed.append(spec.manifest)

    # Past this point nothing raises, so the two writes are effectively atomic.
    if manifest_obj is not None:
        mf.write_pin(manifest_obj, ref=manifest_ref, commit=manifest_commit)
    pin.path.write_text(pin.text, encoding="utf-8")
    if pin.extra_path is not None:
        pin.extra_path.write_text(pin.extra_text, encoding="utf-8")

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


def apply_source(
    repo_root: Path,
    spec: ToolSpec,
    *,
    source_ref: str,
    branch: bool = False,
) -> ApplyResult:
    """Move one reviewed source-only manifest to a resolved immutable commit."""
    if not spec.manifest:
        raise NotAuthorizedError(f"{spec.name}: no source manifest is declared")
    manifest_obj = mf.load(repo_root / spec.manifest)
    if branch:
        requested = replace(manifest_obj, ref=source_ref)
        ref, commit = source_ref, mf.latest_commit(requested)
    else:
        ref, commit = mf.resolve_tag(manifest_obj.url, source_ref, prefix=spec.tag_prefix)
    old = manifest_obj.commit
    mf.write_pin(manifest_obj, ref=ref, commit=commit)
    return ApplyResult(
        tool=spec.name,
        from_version=old,
        to_version=commit,
        changed=(spec.manifest,),
        note=(
            f"source pinned to {ref} @ {commit}; materialize with "
            f"`mise run kb-source-clone -- {spec.name}`"
        ),
    )
