"""Tests for class-aware markdown budgets (kb_setup.md_budget).

Every budget assertion here is paired with its FAIL direction, per
`.claude/rules/probes-need-a-control-arm.md`: a gate verified only on a clean
tree is decoration. The figures asserted are the ones established in the
dotfiles research artifact
`docs/research/runs/research-20260715-md-size-limits/report.md`.

This module is the SHARED engine — dotfiles consumes the same package — so the
tests cover both repos' shapes: this repo is Claude-only (a self-contained
root `CLAUDE.md`, no `AGENTS.md`), dotfiles uses a `@AGENTS.md` import stub.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kb_setup import md_budget

_REPO = Path(__file__).parent.parent.absolute()


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _commit(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    subprocess.run(["git", "-C", str(root), "add", rel], check=True)


# --- the documented figures --------------------------------------------------


def test_documented_line_target_is_200() -> None:
    """Pin the ONE documented figure: "target under 200 lines per CLAUDE.md"."""
    assert md_budget.DOCUMENTED_LINE_TARGET == 200


def test_skill_description_hard_cap_is_1536() -> None:
    """HARD truncation (v2.1.105). The only real cliff a repo here can hit."""
    assert md_budget.SKILL_DESCRIPTION_MAX == 1536


def test_byte_backstops_never_bind_before_the_documented_line_limit() -> None:
    """A byte cap that fires first would silently override the real guideline.

    This is precisely how the old 12000 cap misbehaved: it bound at ~60
    chars/line, blocking files well inside the documented 200-line target.
    """
    assert md_budget.EAGER_BYTE_BACKSTOP >= md_budget.DOCUMENTED_LINE_TARGET * 100
    assert md_budget.DEFERRED_BYTE_BACKSTOP >= md_budget.DEFERRED_LINE_LIMIT * 60


def test_no_budget_reuses_the_misattributed_12000() -> None:
    """Regression pin: 12000 is WINDSURF's figure, and is not ours to re-cite.

    It is real (docs.windsurf.com: "Limited to 12,000 characters per file";
    AGENTS.md is processed by the same Rules engine) and agnix enforces it as
    AGM-003 against AGENTS.md. It is absent from ANTHROPIC's docs — 0 hits over
    the 5.9MB corpus, vs 5 for MEMORY.md's cap. The predecessor step applied it
    to every CLAUDE.md/AGENTS.md captioned "per Claude Code memory docs", which
    named the wrong vendor. This module must not re-adopt it: AGENTS.md is
    capped by agnix, at the vendor that actually imposes the limit.
    """
    figures = {b.max_bytes for b in md_budget.BUDGETS.values()}
    figures |= {b.max_lines for b in md_budget.BUDGETS.values()}
    assert 12000 not in figures


# --- load-class classification -----------------------------------------------


def test_only_claude_md_is_an_entry_point() -> None:
    """Only CLAUDE.md is read: "Claude Code reads CLAUDE.md, not AGENTS.md".

    AGENTS.md reaches context ONLY via its stub's @import, so budgeting it
    standalone would double-count the eager total and blame the wrong file.
    """
    assert md_budget.classify("AGENTS.md") is None
    assert md_budget.classify("tests/AGENTS.md") is None
    assert md_budget.classify("CLAUDE.md") == "eager_root"
    assert md_budget.classify("tests/CLAUDE.md") == "nested"


def test_eager_and_lazy_classes_are_distinguished() -> None:
    assert md_budget.classify("CLAUDE.md") == "eager_root"
    assert md_budget.classify(".claude/CLAUDE.md") == "eager_root"
    assert md_budget.classify("python/CLAUDE.md") == "nested"
    assert md_budget.BUDGETS["nested"].max_lines > md_budget.BUDGETS["eager_root"].max_lines


def test_vendored_prefixes_are_out_of_scope() -> None:
    """The default carve-out is the UNION across consuming repos.

    `plugins/` matches nothing in THIS repo and is still listed: a shared
    default that dropped a consumer's carve-out would fail that repo, not this
    one. The graphify skill is installer-generated in both.
    """
    assert md_budget.classify("plugins/foo/skills/x/SKILL.md") is None
    assert md_budget.classify("plugins/foo/CLAUDE.md") is None
    assert md_budget.classify(".claude/skills/graphify/SKILL.md") is None


def test_exclude_is_overridable_per_consumer() -> None:
    """CONTROL ARM for the carve-out: with it removed, the same path IS budgeted.

    Without this, "returns None" is indistinguishable from a classifier that
    cannot see skills at all.
    """
    assert md_budget.classify(".claude/skills/graphify/SKILL.md", exclude=()) == "skill"
    assert md_budget.classify(".claude/skills/kb-curator/SKILL.md") == "skill"


def test_skills_and_rules_are_classified() -> None:
    assert md_budget.classify(".claude/skills/x/SKILL.md") == "skill"
    assert md_budget.classify(".claude/rules/x.md") == "rule_unscoped"


# --- frontmatter scoping -----------------------------------------------------


def test_paths_frontmatter_detected_only_as_real_frontmatter() -> None:
    scoped = '---\npaths:\n  - "src/**"\n---\n# R\n'
    assert md_budget.has_paths_frontmatter(scoped)


def test_prose_mention_of_paths_is_not_scoping() -> None:
    """Control arm: a substring match would hand an EAGER rule a lazy budget.

    The file must OPEN with `---`; a rule that merely discusses `paths:` in
    prose still loads at launch and must keep the tighter budget.
    """
    prose = "# Rule\n\nUse the paths: frontmatter key to scope a rule.\n"
    assert not md_budget.has_paths_frontmatter(prose)
    assert not md_budget.has_paths_frontmatter("---\nname: x\n---\n# no paths key\n")


# --- measurement -------------------------------------------------------------


def test_html_comments_are_not_counted() -> None:
    """Docs strip them before injection and RECOMMEND them for maintainer notes.

    Counting them taxes the exact practice Anthropic endorses as free.
    """
    raw = "<!-- a long maintainer note that costs zero context -->\n@AGENTS.md\n"
    lines, byte_n = md_budget.measure(raw)
    assert lines == 1
    assert byte_n == len("@AGENTS.md")


def test_measure_counts_real_content() -> None:
    lines, byte_n = md_budget.measure("# Title\n\nBody text\n")
    assert lines == 3
    assert byte_n == len("# Title\n\nBody text")


def test_rules_do_not_get_the_comment_discount() -> None:
    """Only CLAUDE.md is documented as comment-stripped; rules pay full price.

    Assuming the discount where it is unproven would make the gate UNDER-count
    the eagerly-loaded class — the failure direction that matters.
    """
    raw = "<!-- note -->\nbody\n"
    assert md_budget.measure(raw, strip_comments=False)[1] > md_budget.measure(raw)[1]


# --- import closure ----------------------------------------------------------


def test_closure_follows_a_bare_filename_import(tmp_path: Path) -> None:
    """`@AGENTS.md` has no slash — a path-shaped-only regex misses it entirely.

    That bug made dotfiles' root stub report a 1-file closure and silently
    defeated the whole point of budgeting closures.
    """
    root = _git_repo(tmp_path)
    (root / "CLAUDE.md").write_text("@AGENTS.md\n")
    (root / "AGENTS.md").write_text("# Real content\nline\n")
    _, _, files = md_budget.closure_size(root / "CLAUDE.md", root)
    assert {f.name for f in files} == {"CLAUDE.md", "AGENTS.md"}


def test_closure_does_not_count_the_import_directive_as_a_line(tmp_path: Path) -> None:
    """The directive is REPLACED by the imported content, not added to it.

    Counting it makes the root closure 201 lines and fails a file sitting
    legitimately at the documented 200 — for a reason unrelated to size.
    """
    root = _git_repo(tmp_path)
    (root / "CLAUDE.md").write_text("@AGENTS.md\n")
    (root / "AGENTS.md").write_text("\n".join(f"line {i}" for i in range(200)) + "\n")
    lines, _, _ = md_budget.closure_size(root / "CLAUDE.md", root)
    assert lines == 200


def test_backticked_import_is_literal_not_an_import(tmp_path: Path) -> None:
    """Docs: "writing `@README` keeps the text literal"."""
    root = _git_repo(tmp_path)
    (root / "CLAUDE.md").write_text("Mention `@AGENTS.md` literally.\n")
    (root / "AGENTS.md").write_text("# Should not be pulled in\n")
    _, _, files = md_budget.closure_size(root / "CLAUDE.md", root)
    assert {f.name for f in files} == {"CLAUDE.md"}


# --- the FAIL direction (control arms) ---------------------------------------


def test_gate_fails_on_an_oversized_unscoped_rule(tmp_path: Path) -> None:
    """CONTROL ARM: an eager rule over 200 lines must FAIL."""
    root = _git_repo(tmp_path)
    _commit(root, ".claude/rules/big.md", "\n".join(f"l{i}" for i in range(250)))
    report = md_budget.check(root)
    assert any("big.md" in v.path for v in report.violations)


def test_same_rule_passes_when_paths_scoped(tmp_path: Path) -> None:
    """The POSITIVE arm: scoping it changes the class and it passes.

    Together with the test above this proves the gate keys on LOAD CLASS, not
    merely on size — the entire point of the redesign.
    """
    root = _git_repo(tmp_path)
    body = '---\npaths:\n  - "src/**"\n---\n' + "\n".join(f"l{i}" for i in range(250))
    _commit(root, ".claude/rules/big.md", body)
    report = md_budget.check(root)
    assert not report.violations


def test_gate_fails_on_an_overlong_skill_description(tmp_path: Path) -> None:
    """CONTROL ARM: the one HARD truncation must be caught."""
    root = _git_repo(tmp_path)
    desc = "x" * (md_budget.SKILL_DESCRIPTION_MAX + 1)
    _commit(
        root,
        ".claude/skills/s/SKILL.md",
        f"---\nname: s\ndescription: {desc}\n---\n# S\n",
    )
    report = md_budget.check(root)
    assert any("TRUNCATED SILENTLY" in v.message for v in report.violations)


def test_skill_description_at_the_cap_passes(tmp_path: Path) -> None:
    """Boundary: exactly at the cap is fine; only OVER truncates."""
    root = _git_repo(tmp_path)
    desc = "x" * md_budget.SKILL_DESCRIPTION_MAX
    _commit(
        root,
        ".claude/skills/s/SKILL.md",
        f"---\nname: s\ndescription: {desc}\n---\n# S\n",
    )
    report = md_budget.check(root)
    assert not report.violations


def test_the_cap_counts_when_to_use_too(tmp_path: Path) -> None:
    """The 1,536 cap is on `description` + `when_to_use` COMBINED, not description alone.

    *"Appended to `description` in the skill listing and counts toward the
    1,536-character cap"* — `code.claude.com/docs/en/skills.md`. Measuring
    `description` alone lets a skill split its text across the two fields and pass
    a gate the harness would then truncate. Neither half here is over the cap; only
    their sum is, so this fails for the right reason. (Cold lane round 2, P2.)
    """
    root = _git_repo(tmp_path)
    half = "x" * (md_budget.SKILL_DESCRIPTION_MAX // 2 + 10)
    _commit(
        root,
        ".claude/skills/s/SKILL.md",
        f"---\nname: s\ndescription: {half}\nwhen_to_use: {half}\n---\n# S\n",
    )
    report = md_budget.check(root)
    assert any("TRUNCATED SILENTLY" in v.message for v in report.violations), (
        "combined description + when_to_use over the cap must be caught"
    )


def test_when_to_use_alone_under_the_cap_still_passes(tmp_path: Path) -> None:
    """CONTROL ARM: reading both fields must not make an ordinary skill fail."""
    root = _git_repo(tmp_path)
    _commit(
        root,
        ".claude/skills/s/SKILL.md",
        "---\nname: s\ndescription: a short one\nwhen_to_use: also short\n---\n# S\n",
    )
    report = md_budget.check(root)
    assert not report.violations


def test_gate_fails_when_an_import_target_blows_the_closure(tmp_path: Path) -> None:
    """CONTROL ARM: splitting into an @import must NOT evade the budget.

    Docs: "Splitting into @path imports helps organization but doesn't reduce
    context, since imported files load at launch." A per-file cap would pass a
    1-line stub importing a 500-line file; the closure budget must not.
    """
    root = _git_repo(tmp_path)
    _commit(root, "CLAUDE.md", "@AGENTS.md\n")
    _commit(root, "AGENTS.md", "\n".join(f"l{i}" for i in range(300)))
    report = md_budget.check(root)
    assert any("CLAUDE.md" in v.path for v in report.violations)
    assert any("AGENTS.md" in v.message for v in report.violations), (
        "the violation must NAME the oversized import target, not just the stub"
    )


def test_gate_fails_on_a_self_contained_oversized_root(tmp_path: Path) -> None:
    """This repo's shape: a root CLAUDE.md with NO import stub must still gate.

    dotfiles is only ever budgeted through a closure, so the no-import path is
    the one a dotfiles-only test suite would never exercise.
    """
    root = _git_repo(tmp_path)
    _commit(root, "CLAUDE.md", "\n".join(f"l{i}" for i in range(250)))
    report = md_budget.check(root)
    assert any("CLAUDE.md" in v.path for v in report.violations)


def test_clean_tree_passes(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    _commit(root, "CLAUDE.md", "@AGENTS.md\n")
    _commit(root, "AGENTS.md", "# Small\n")
    assert md_budget.check(root).violations == []


# --- the real repo -----------------------------------------------------------


def test_this_repo_is_within_budget() -> None:
    """The live gate: this repo must pass its own class-aware budgets."""
    report = md_budget.check(_REPO)
    detail = [f"{v.path}: {v.message}" for v in report.violations]
    assert report.violations == [], detail


def test_eager_total_is_reported() -> None:
    """The number that actually matters must be measurable, not just gated.

    Eager bytes are paid EVERY session regardless of the task; the old gate
    never surfaced them, which is how tens of KB of eager rules went unnoticed.
    """
    report = md_budget.check(_REPO)
    assert report.eager_bytes > 0
    assert report.counted > 0
