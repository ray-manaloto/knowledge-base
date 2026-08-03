"""`currency.skill` — refresh a project-scoped agent skill as part of a bump.

The refresh runs an installer and then `git checkout --` on the files that
installer is known to damage. That second half is destructive, so every arm here
is about what it must REFUSE to do.
"""

from __future__ import annotations

import subprocess
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
