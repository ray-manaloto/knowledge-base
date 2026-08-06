"""`currency.skill` — refresh a project-scoped agent skill as part of a bump.

The refresh runs an installer and then `git checkout --` on the files that
installer is known to damage. That second half is destructive, so every arm here
is about what it must REFUSE to do.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kb_setup.currency import skill
from kb_setup.currency.config import ToolSpec


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    for cfg in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(tmp_path), "config", *cfg], check=True, timeout=30)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"hooks": "ORIGINAL"}\n', encoding="utf-8")
    (tmp_path / ".claude" / "CLAUDE.md").write_text("# hand-authored\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills" / "graphify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "skills" / "graphify" / "SKILL.md").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, timeout=30)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True, timeout=30)
    return tmp_path


def _spec(
    *, skill_dir: str = ".claude/skills/graphify", skill_install: tuple[str, ...] = ("true",)
) -> ToolSpec:
    """A ToolSpec with only the fields this module reads.

    Explicit keywords rather than a dict splat: the splat needed a type
    suppression, and this repo rejects inline suppressions outright
    (`do-not.md` #9 — they all live in the one root pyproject.toml).
    """
    return ToolSpec(
        name="graphify",
        mise_key="pipx:graphifyy",
        skill_dir=skill_dir,
        skill_install=skill_install,
    )


def test_a_tool_with_no_declared_skill_is_a_clean_no_op(tmp_path) -> None:
    """Every other currency field switches a check ON when present; so does this."""
    result = skill.refresh(_repo(tmp_path), _spec(skill_dir="", skill_install=()))
    assert result.ran is False
    assert "no project-scoped skill" in result.note


def test_it_refuses_when_the_repair_target_is_already_dirty(tmp_path) -> None:
    """THE ARM THAT MATTERS: the repair is `git checkout --`, which destroys work.

    If someone is mid-edit on `.claude/settings.json`, running the installer and
    then reverting that path discards THEIR change along with the installer's
    damage — and nothing distinguishes the two afterwards. A skill refresh is
    never worth silently eating unrelated work, so it refuses instead.
    """
    root = _repo(tmp_path)
    (root / ".claude" / "settings.json").write_text('{"hooks": "MY UNCOMMITTED EDIT"}\n', "utf-8")

    result = skill.refresh(root, _spec())

    assert result.ran is False
    assert "refusing" in result.note
    kept = (root / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "MY UNCOMMITTED EDIT" in kept, "the refusal did not protect the file it refused for"


def test_an_installer_failure_is_reported_not_raised(tmp_path) -> None:
    """`apply()` has already written the pin and manifest when this runs.

    Raising here would abort a bump that was fully authorized and already
    partially on disk. The contract is: the pin lands, and the skill failure is
    visible in the note. Silence would be the worst of the three, because a skill
    is exactly the artifact nobody re-reads.
    """
    result = skill.refresh(_repo(tmp_path), _spec(skill_install=("false",)))
    assert result.ran is False
    assert "installer failed" in result.note


def test_it_repairs_settings_json_after_a_successful_install(tmp_path) -> None:
    """The installer damages `.claude/settings.json` every time it runs.

    Measured 2026-08-03 at 0.9.23 -> 0.9.31: it rewrote both hook commands to an
    absolute versioned binary path, dropped `"timeout": 15`, and stripped the
    trailing newline. The refresh is installer + repair; without the repair, a
    machine-specific path and a frozen version land in committed config.

    The fake installer here reproduces exactly that: it damages settings.json and
    changes the skill. The contract is that ONE is reverted and the other is not.
    """
    root = _repo(tmp_path)
    fake = root / "fake-install.sh"
    fake.write_text(
        "#!/bin/sh\n"
        'printf \'{"hooks": "/abs/path/0.9.32/bin/graphify"}\' > .claude/settings.json\n'
        "printf 'v2\\n' > .claude/skills/graphify/SKILL.md\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    result = skill.refresh(root, _spec(skill_install=("./fake-install.sh",)))

    assert result.ran is True
    assert result.repaired, "installer damaged settings.json but nothing was recorded repaired"
    settings = (root / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert settings == '{"hooks": "ORIGINAL"}\n', (
        "settings.json was not restored — an absolute versioned binary path would "
        "have landed in committed config, which is the defect graphify_exe prevents"
    )
    # CONTROL ARM: the repair must NOT revert the skill content we ran it for.
    skill_md = (root / ".claude" / "skills" / "graphify" / "SKILL.md").read_text(encoding="utf-8")
    assert skill_md == "v2\n", (
        "the repair reverted the SKILL.md update too — that would make the whole "
        "refresh a no-op while reporting success"
    )
    assert any("SKILL.md" in c for c in result.changed), (
        f"changed did not name the skill: {result.changed}"
    )


# --------------------------------------------------------------------------
# Cold-lane findings, PR round 1 (report `review-a95e0aa-cold.md`).
#
# The fixtures above could not exhibit either defect: the happy-path repair test
# only dirties files that already exist in the base commit, and the failure test
# uses `false`, which never touches disk. Both gaps are the same shape — a test
# whose fixture cannot reach the failure it is named for.
# --------------------------------------------------------------------------


def _installer(script: str) -> tuple[str, ...]:
    """A real installer that touches disk, as argv. `sh -c` keeps it one file."""
    return ("sh", "-c", script)


def test_an_untracked_repair_path_does_not_veto_the_whole_repair(tmp_path) -> None:
    """`git checkout -- a b` is ATOMIC: one bad pathspec reverts NEITHER.

    Control-armed in a scratch repo before fixing: with `tracked` modified and
    `untracked` present, `git checkout -- tracked untracked` exits 1 and `tracked`
    keeps its damaged contents. `_dirty` reads `git status --porcelain`, whose
    `??` lines are untracked files, so an untracked `_REPAIR` path lands in that
    argv — reachable for any consumer with no committed root `CLAUDE.md`, which
    this module's docstring explicitly invites.

    Before the fix this reported `repaired=(settings.json, CLAUDE.md)` and a note
    saying both were repaired, while settings.json sat on disk still damaged.
    """
    repo = _repo(tmp_path)
    # The installer damages a TRACKED repair path and creates an UNTRACKED one.
    result = skill.refresh(
        repo,
        _spec(
            skill_install=_installer(
                'printf \'{"hooks": "DAMAGED"}\\n\' > .claude/settings.json; '
                "printf 'untracked\\n' > CLAUDE.md",
            )
        ),
    )

    assert result.ran is True
    settings = (repo / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "ORIGINAL" in settings, "the tracked path must be reverted despite the untracked one"
    assert ".claude/settings.json" in result.repaired
    # The untracked file cannot be reverted — git has no version to restore. That
    # is reported, not hidden: it is real dirt in the working tree.
    assert "CLAUDE.md" in result.unrepaired
    assert "COULD NOT REVERT" in result.note


def test_a_clean_repair_reports_nothing_unrepaired(tmp_path) -> None:
    """Control arm for the test above — the ordinary case must stay quiet."""
    repo = _repo(tmp_path)
    result = skill.refresh(
        repo,
        _spec(
            skill_install=_installer('printf \'{"hooks": "DAMAGED"}\\n\' > .claude/settings.json')
        ),
    )
    assert result.ran is True
    assert result.unrepaired == ()
    assert "COULD NOT REVERT" not in result.note
    assert "ORIGINAL" in (repo / ".claude" / "settings.json").read_text(encoding="utf-8")


def test_a_half_finished_installer_does_not_leave_damage_unmentioned(tmp_path) -> None:
    """The pre-flight proved the tree was clean, so this dirt is OURS.

    A multi-file installer failing partway (disk full, permission error, its own
    assertion) is ordinary. Returning only "installer failed" left a
    machine-specific absolute path in settings.json for whoever committed next —
    the exact defect `_REPAIR` exists to prevent, reached by the one path it did
    not guard.
    """
    repo = _repo(tmp_path)
    result = skill.refresh(
        repo,
        _spec(
            skill_install=_installer(
                'printf \'{"hooks": "/abs/PARTIAL"}\\n\' > .claude/settings.json; exit 1'
            )
        ),
    )

    assert result.ran is False
    assert "installer failed" in result.note
    assert "ORIGINAL" in (repo / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert ".claude/settings.json" in result.repaired


def test_backups_beside_a_root_repair_path_are_cleared(tmp_path) -> None:
    """The old glob was `skill.parent.parent` — `.claude/`, for a `.claude/skills/*` skill.

    Both too wide (any `*.graphify-bak` anywhere under `.claude/`) and too narrow
    (never reaching a backup beside the ROOT `CLAUDE.md`, which is in `_REPAIR`).
    """
    repo = _repo(tmp_path)
    (repo / "CLAUDE.md.graphify-bak").write_text("stale\n", encoding="utf-8")
    (repo / ".claude" / "settings.json.graphify-bak").write_text("stale\n", encoding="utf-8")

    skill.refresh(repo, _spec())

    assert not (repo / "CLAUDE.md.graphify-bak").exists()
    assert not (repo / ".claude" / "settings.json.graphify-bak").exists()


# --------------------------------------------------------------------------
# ADDENDA — every arm below failed on 2026-08-06, when a refresh destroyed PR
# #190's hand-added paragraph in `references/query.md` and reported success.
# --------------------------------------------------------------------------

_ADDENDUM = skill.Addendum(
    path=".claude/skills/graphify/references/query.md",
    anchor="## Section\n",
    text="\nlocal note that upstream does not carry.\n",
)


def _wipes(body: str) -> tuple[str, ...]:
    """An installer argv that REGENERATES the addendum's file with ``body``.

    A real process writing real bytes, like `_installer` above — the point is
    that the addendum has to survive a genuine rewrite of the whole file, not a
    monkeypatched stand-in for one.
    """
    return (
        sys.executable,
        "-c",
        "import pathlib;"
        f"p = pathlib.Path({_ADDENDUM.path!r});"
        "p.parent.mkdir(parents=True, exist_ok=True);"
        f"p.write_text({body!r}, encoding='utf-8')",
    )


def test_an_addendum_wiped_by_the_installer_is_re_applied(tmp_path, monkeypatch) -> None:
    """The regression this exists for: a wiped local note comes back."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(skill, "ADDENDA", {".claude/skills/graphify": (_ADDENDUM,)})

    result = skill.refresh(repo, _spec(skill_install=_wipes("intro\n\n## Section\n\nupstream\n")))

    assert result.ran is True
    assert result.lost_addenda == ()
    assert _ADDENDUM.path in result.addenda
    assert _ADDENDUM.text in (repo / _ADDENDUM.path).read_text(encoding="utf-8")


def test_re_applying_an_addendum_twice_does_not_duplicate_it(tmp_path, monkeypatch) -> None:
    """Idempotence — two refreshes must not stack the paragraph."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(skill, "ADDENDA", {".claude/skills/graphify": (_ADDENDUM,)})

    skill.refresh(repo, _spec(skill_install=_wipes("## Section\n\nupstream\n")))
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, timeout=30)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "r1"], check=True, timeout=30)
    # The SECOND installer must NOT regenerate the file. The first version of
    # this test re-ran `_wipes`, which deleted the insertion before
    # `_apply_addenda` was reached — so `add.text in text` was never True and the
    # guard was never exercised. Mutation-confirmed by the cold lane on 5204e57
    # (F6): deleting the guard left all 21 arms passing.
    skill.refresh(repo, _spec(skill_install=("true",)))

    body = (repo / _ADDENDUM.path).read_text(encoding="utf-8")
    assert body.count(_ADDENDUM.text) == 1


def test_a_moved_anchor_is_reported_lost_rather_than_dropped(tmp_path, monkeypatch) -> None:
    """An anchor upstream moved must be NAMED, not silently skipped.

    Silence is what the destroying run did. The note has to say the tree is
    missing something, or the reviewer sees a routine regeneration diff.
    """
    repo = _repo(tmp_path)
    monkeypatch.setattr(skill, "ADDENDA", {".claude/skills/graphify": (_ADDENDUM,)})

    result = skill.refresh(repo, _spec(skill_install=_wipes("upstream renamed the heading\n")))

    assert result.ran is True
    assert result.addenda == ()
    assert len(result.lost_addenda) == 1
    assert "anchor moved" in result.lost_addenda[0]
    assert "LOCAL ADDENDUM LOST" in result.note


def test_a_missing_addendum_file_is_reported_distinctly(tmp_path, monkeypatch) -> None:
    """A file upstream deleted is a lost note too, with a different remedy."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(skill, "ADDENDA", {".claude/skills/graphify": (_ADDENDUM,)})

    result = skill.refresh(repo, _spec())  # `true` — writes nothing at all

    assert len(result.lost_addenda) == 1
    assert "file absent" in result.lost_addenda[0]


def test_a_tool_with_no_addenda_reports_none(tmp_path, monkeypatch) -> None:
    """CONTROL ARM: silence when nothing is configured for this skill_dir.

    Without it, a version that reported a lost addendum unconditionally would
    pass every arm above while crying wolf on every other tool.
    """
    repo = _repo(tmp_path)
    # The directory must EXIST, or `refresh` returns at its "not present" guard
    # before `_apply_addenda` runs and both assertions hold on dataclass defaults
    # — true even if `_apply_addenda` were deleted (cold lane on 5204e57, F7).
    (repo / ".claude" / "skills" / "other").mkdir(parents=True)
    monkeypatch.setattr(skill, "ADDENDA", {".claude/skills/graphify": (_ADDENDUM,)})

    result = skill.refresh(repo, _spec(skill_dir=".claude/skills/other"))

    assert result.ran is True
    assert result.lost_addenda == ()
    assert result.addenda == ()


def test_the_live_addenda_are_applied_in_the_shipped_tree() -> None:
    """The REAL entries must match the tree that ships.

    Every arm above uses a synthetic addendum, so an `ADDENDA` entry whose
    anchor never existed in the real file would pass all of them.
    """
    root = Path(__file__).resolve().parents[1]
    checked = 0
    for skill_dir, entries in skill.ADDENDA.items():
        if not (root / skill_dir).is_dir():
            continue
        for add in entries:
            body = (root / add.path).read_text(encoding="utf-8")
            assert add.anchor in body, f"{add.path}: anchor missing from the shipped file"
            assert add.text in body, f"{add.path}: addendum not applied in the shipped file"
            checked += 1
    # Without this the loop asserts NOTHING when ADDENDA is empty — which is the
    # deletion this arm exists to catch (cold lane on 5204e57, F11).
    assert checked > 0, "ADDENDA is empty or none of its skill_dirs ship — nothing was checked"


def test_a_failing_installer_that_wiped_an_addendum_still_reports_it(tmp_path, monkeypatch) -> None:
    """A half-finished installer deletes the note and THEN exits nonzero.

    `_apply_addenda` ran only on the success path, so `lost_addenda` kept its
    empty default and the one loss this mechanism exists to catch survived on
    the single path it did not cover (cold lane on 5204e57, F5).
    """
    repo = _repo(tmp_path)
    monkeypatch.setattr(skill, "ADDENDA", {".claude/skills/graphify": (_ADDENDUM,)})
    wipe_then_fail = (
        sys.executable,
        "-c",
        "import pathlib, sys;"
        f"p = pathlib.Path({_ADDENDUM.path!r});"
        "p.parent.mkdir(parents=True, exist_ok=True);"
        "p.write_text('upstream renamed the heading\\n', encoding='utf-8');"
        "sys.exit(3)",
    )

    result = skill.refresh(repo, _spec(skill_install=wipe_then_fail))

    assert result.ran is False
    assert len(result.lost_addenda) == 1
    assert "LOCAL ADDENDUM LOST" in result.note


def test_the_reverted_delta_carries_the_bytes_not_just_the_path(tmp_path) -> None:
    """`repair_delta` must hold the actual hunk, captured BEFORE the revert.

    After `git checkout --` there is nothing left to diff, so a capture taken
    afterwards would always be empty and the report would silently degrade to
    filenames — which is the state `mise.toml` described but no code produced
    (cold lane on 5204e57, F8).
    """
    repo = _repo(tmp_path)
    damage = _installer('printf \'{"hooks": "INSTALLER-DAMAGE"}\\n\' > .claude/settings.json')

    result = skill.refresh(repo, _spec(skill_install=damage))

    assert ".claude/settings.json" in result.repaired
    assert "INSTALLER-DAMAGE" in result.repair_delta
    assert "ORIGINAL" in result.repair_delta
    # And the file itself is back.
    assert "ORIGINAL" in (repo / ".claude" / "settings.json").read_text(encoding="utf-8")


def test_a_clean_run_carries_no_delta(tmp_path) -> None:
    """CONTROL ARM: nothing reverted means nothing to print."""
    assert skill.refresh(_repo(tmp_path), _spec()).repair_delta == ""


def test_dot_claude_claude_md_is_repaired_too(tmp_path) -> None:
    """The installer writes BOTH CLAUDE.md files; only the root one was covered.

    `install.py:263`/`:629` target `.claude/CLAUDE.md` while `:1708` targets the
    root one, and the pathspec `CLAUDE.md` does not match the former. That file
    is hand-authored here and sits at its `md_size_budget`, so an installer
    append breaks a gate rather than merely churning (cold lane on 5204e57, F9).
    """
    repo = _repo(tmp_path)
    damage = _installer("printf 'INSTALLER-APPENDED\\n' >> .claude/CLAUDE.md")

    result = skill.refresh(repo, _spec(skill_install=damage))

    assert ".claude/CLAUDE.md" in result.repaired
    assert "INSTALLER-APPENDED" not in (repo / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")


def test_the_version_stamp_gets_its_trailing_newline(tmp_path) -> None:
    """The installer writes it with no newline; tracked, that fails hk.

    Normalised by the module rather than by a caller's `mise run fmt`, because
    only one of the two callers runs one — `currency.apply` commits what this
    returns as-is, so an ordinary auto-applied bump produced a lint-failing
    commit (cold lane on 5204e57, F3).
    """
    repo = _repo(tmp_path)
    stamp = repo / ".claude" / "skills" / "graphify" / ".graphify_version"
    write_stamp = _installer(
        "printf '0.9.34' > .claude/skills/graphify/.graphify_version"  # no \n, as install.py does
    )

    # CONTROL ARM, and it is an ASSERTION rather than a comment claiming one:
    # run the same installer argv directly and confirm the raw output really
    # lacks the newline. Without this the test passes against a fixture that
    # already wrote one, proving nothing about `_normalise_stamp` (cold lane
    # round 2 on ea6ab63, P3).
    subprocess.run(write_stamp, cwd=repo, check=True, timeout=30)
    assert stamp.read_text(encoding="utf-8") == "0.9.34"

    skill.refresh(repo, _spec(skill_install=write_stamp))

    assert stamp.read_text(encoding="utf-8") == "0.9.34\n"


def test_the_graphify_addenda_registration_is_pinned() -> None:
    """The REGISTRATION is the contract, not just "each registered one applies".

    `test_the_live_addenda_are_applied_in_the_shipped_tree` checks that every
    CONFIGURED addendum is present in the tree — so deleting an entry deletes
    its own check, and the next skill refresh silently erases the note from the
    shipped file. Mutation-confirmed by the cold lane on ea6ab63: removing the
    23-line Step 5 entry passed the full suite.

    Same shape as `test_the_writer_set_names_every_graph_writer` — membership
    pinned, so removing one is a deliberate edit here rather than a silent loss.
    """
    entries = {a.path: a for a in skill.ADDENDA[".claude/skills/graphify"]}

    assert set(entries) == {
        ".claude/skills/graphify/references/query.md",
        ".claude/skills/graphify/SKILL.md",
    }
    # Each is pinned by the CLAIM it carries, not merely by existing: an entry
    # rewritten to say something else is the same silent loss with extra steps.
    assert "--undirected" in entries[".claude/skills/graphify/references/query.md"].text
    assert "mise run kb-label" in entries[".claude/skills/graphify/SKILL.md"].text
    assert "Step 5" in entries[".claude/skills/graphify/SKILL.md"].anchor


def test_a_failing_installer_still_normalises_the_stamp(tmp_path) -> None:
    """An installer that writes the stamp and fails LATER still lands the pin.

    `currency.apply` commits what it gets, so a newline-less tracked stamp then
    fails hk's `newlines` for a reason nobody would connect to a FAILED install
    (cold lane round 2 on ea6ab63).
    """
    repo = _repo(tmp_path)
    stamp = repo / ".claude" / "skills" / "graphify" / ".graphify_version"
    write_then_fail = (
        sys.executable,
        "-c",
        "import pathlib, sys;"
        "pathlib.Path('.claude/skills/graphify/.graphify_version')"
        ".write_text('0.9.34', encoding='utf-8');"
        "sys.exit(4)",
    )

    result = skill.refresh(repo, _spec(skill_install=write_then_fail))

    assert result.ran is False
    assert stamp.read_text(encoding="utf-8") == "0.9.34\n"


def test_a_failed_delta_capture_says_so_rather_than_reading_as_empty(tmp_path, monkeypatch) -> None:
    """A `git diff` that FAILED must not be indistinguishable from "no changes".

    `_git` runs with `check=False`, and the checkout on the very next line
    destroys the only copy of what the diff would have shown — so an unread rc
    turns a capture failure into a silent, permanent loss (cold lane round 2 on
    ea6ab63).
    """
    repo = _repo(tmp_path)
    real = skill._git

    def failing_diff(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(["git"], 128, stdout="", stderr="fatal: nope")
        return real(root, *args)

    monkeypatch.setattr(skill, "_git", failing_diff)
    damage = _installer('printf \'{"hooks": "DAMAGE"}\\n\' > .claude/settings.json')

    result = skill.refresh(repo, _spec(skill_install=damage))

    assert "COULD NOT CAPTURE" in result.repair_delta
    assert "128" in result.repair_delta
    # The revert itself still happened — only its diff is unavailable.
    assert "ORIGINAL" in (repo / ".claude" / "settings.json").read_text(encoding="utf-8")
