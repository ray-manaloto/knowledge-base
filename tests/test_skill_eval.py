"""Tests for the advisory skill scorer (kb_setup.skill_eval).

The load-bearing behaviour here is not "does it compute a number" — it is what
it does when it CANNOT. Three distinct answers must stay distinct, the same
discipline the currency engine is built on: a real score, "this skill failed to
score", and "nothing on this host could score anything". Collapsing the last two
into `0.0` would render an uninstalled plugin as a catastrophic quality
regression, so every negative path below is paired with its positive control
(`.claude/rules/probes-need-a-control-arm.md`).
"""

from __future__ import annotations

import json
from pathlib import Path

from kb_setup import skill_eval

_REPO = Path(__file__).parent.parent.absolute()


def _report(*, composite: float | None = 65.5, layers: object = None) -> str:
    """A `plugin-eval --output json` payload, shaped like the real one."""
    payload: dict[str, object] = {
        "plugin_path": ".claude/skills/x",
        "layers": layers
        if layers is not None
        else [{"layer": "static", "score": 0.67, "anti_patterns": []}],
    }
    if composite is not None:
        payload["composite"] = {
            "score": composite,
            "dimensions": [
                {"name": "triggering_accuracy", "weight": 0.25, "score": 0.47},
                {"name": "output_quality", "weight": 0.15, "score": 0.0},
            ],
        }
    return json.dumps(payload)


# --------------------------------------------------------------- parsing ----


def test_parse_reads_the_composite_score():
    got = skill_eval._parse("x", _report(composite=65.5), vendored=False)
    assert got.score == 65.5
    assert got.error == ""


def test_parse_tolerates_leading_uv_chatter():
    """`uv` prepends build/install lines on a cold cache; that is not a failure."""
    noisy = "Building plugin-eval @ file:///...\nDownloaded pydantic-core\n" + _report()
    assert skill_eval._parse("x", noisy, vendored=False).score == 65.5


def test_parse_missing_composite_is_an_error_not_a_zero():
    """The FAIL direction that matters: absence must never read as a bad score.

    A skill whose report has no composite has not been measured. Returning 0.0
    would put it at the bottom of the table as though it had been measured and
    found terrible.
    """
    got = skill_eval._parse("x", _report(composite=None), vendored=False)
    assert got.score is None
    assert "composite" in got.error


def test_parse_rejects_non_json_and_non_objects():
    assert skill_eval._parse("x", "totally not json", vendored=False).score is None
    assert skill_eval._parse("x", "[1, 2, 3]", vendored=False).score is None


# ---------------------------------------------------------- anti-patterns ----


def test_anti_patterns_are_read_per_layer_not_top_level():
    """The real report nests them under `layers[]`; a top-level read finds none.

    This is the silent-false-green shape: a top-level lookup returns `()` for a
    skill that genuinely has anti-patterns, and the table then reports 0. The
    control arm is the top-level placement below, which must still yield none.
    """
    nested = _report(
        layers=[{"layer": "static", "anti_patterns": [{"name": "OVER_CONSTRAINED"}, "BLOATED"]}]
    )
    assert skill_eval._parse("x", nested, vendored=False).anti_patterns == (
        "OVER_CONSTRAINED",
        "BLOATED",
    )

    top_level = json.dumps({"composite": {"score": 1.0}, "anti_patterns": ["OVER_CONSTRAINED"]})
    assert skill_eval._parse("x", top_level, vendored=False).anti_patterns == ()


# ------------------------------------------------------- weakest dimension ----


def test_weakest_skips_dimensions_the_static_layer_cannot_reach():
    """`output_quality` is 0.0 on every static-only run — naming it helps nobody."""
    data = json.loads(_report())
    assert "triggering_accuracy" in skill_eval._weakest(data)


def test_weakest_breaks_ties_toward_the_heavier_dimension():
    data = {
        "composite": {
            "dimensions": [
                {"name": "light", "weight": 0.02, "score": 0.40},
                {"name": "heavy", "weight": 0.25, "score": 0.40},
            ]
        }
    }
    assert skill_eval._weakest(data).startswith("heavy")


def test_weakest_is_empty_when_every_dimension_is_unreachable():
    data = {"composite": {"dimensions": [{"name": "output_quality", "weight": 0.15, "score": 0.0}]}}
    assert skill_eval._weakest(data) == ""


# ------------------------------------------------------------- discovery ----


def test_skill_dirs_requires_a_skill_md_file(tmp_path: Path):
    """`.claude/skills/` also holds `references/` and `scripts/` subtrees.

    Handing one of those to plugin-eval scores a fragment as if it were a skill,
    so the presence of `SKILL.md` — not merely being a directory — is the test.
    """
    base = tmp_path / ".claude" / "skills"
    (base / "real").mkdir(parents=True)
    (base / "real" / "SKILL.md").write_text("---\nname: real\n---\n", encoding="utf-8")
    (base / "not-a-skill").mkdir()

    found = [p.name for p in skill_eval.skill_dirs(tmp_path)]
    assert found == ["real"]


def test_skill_dirs_is_empty_when_there_is_no_skills_dir(tmp_path: Path):
    assert skill_eval.skill_dirs(tmp_path) == []


def test_this_repos_own_skills_are_discovered():
    """Control arm for the two negatives above, against the real tree."""
    names = {p.name for p in skill_eval.skill_dirs(_REPO)}
    assert {"clear-prep", "kb-review", "kb-curator"} <= names


# ------------------------------------------------------------- provenance ----


def test_resolve_scorer_returns_none_when_no_checkout_exists(tmp_path: Path, monkeypatch):
    """None is a real answer; `main` renders it as NOT VERIFIABLE HERE, never 0."""
    monkeypatch.setattr(skill_eval, "_PLUGIN_ROOTS", (("pinned-clone", "nowhere/plugin-eval"),))
    assert skill_eval.resolve_scorer(tmp_path) is None


def test_resolve_scorer_finds_a_checkout_and_reads_its_version(tmp_path: Path, monkeypatch):
    root = tmp_path / "vendor" / "plugin-eval"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "plugin-eval"\nversion = "0.1.1"\n', encoding="utf-8"
    )
    monkeypatch.setattr(skill_eval, "_PLUGIN_ROOTS", (("pinned-clone", "vendor/plugin-eval"),))

    scorer = skill_eval.resolve_scorer(tmp_path)
    assert scorer is not None
    assert scorer.version == "0.1.1"
    # The label carries provenance: two scores from different scorers are not
    # comparable, so the report must always say which one ran.
    assert "pinned-clone" in scorer.label()


def test_version_is_empty_rather_than_wrong_when_unreadable(tmp_path: Path, monkeypatch):
    root = tmp_path / "vendor" / "plugin-eval"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    monkeypatch.setattr(skill_eval, "_PLUGIN_ROOTS", (("pinned-clone", "vendor/plugin-eval"),))

    scorer = skill_eval.resolve_scorer(tmp_path)
    assert scorer is not None
    assert scorer.version == ""
    assert "version unknown" in scorer.label()


def test_marketplace_copy_wins_over_the_pinned_clone(tmp_path: Path, monkeypatch):
    """Order is the contract: the copy whose `/eval` a session reaches scores first."""
    for rel in ("mkt/plugin-eval", "vendor/plugin-eval"):
        (tmp_path / rel).mkdir(parents=True)
        (tmp_path / rel / "pyproject.toml").write_text('version = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(
        skill_eval,
        "_PLUGIN_ROOTS",
        (("marketplace", "mkt/plugin-eval"), ("pinned-clone", "vendor/plugin-eval")),
    )
    scorer = skill_eval.resolve_scorer(tmp_path)
    assert scorer is not None
    assert scorer.origin == "marketplace"


# ---------------------------------------------------------------- report ----


def test_a_run_that_measured_nothing_says_so_instead_of_averaging_zero():
    scorer = skill_eval.Scorer(root=Path("/x"), origin="pinned-clone", version="0.1.0")
    out = skill_eval._render(scorer, [skill_eval.SkillScore(name="a", score=None, error="boom")])
    assert "NOT VERIFIABLE HERE" in out
    assert "0.0/100" not in out


def test_a_scored_run_reports_the_mean_and_names_its_scorer():
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0")
    out = skill_eval._render(
        scorer,
        [
            skill_eval.SkillScore(name="a", score=60.0),
            skill_eval.SkillScore(name="b", score=70.0),
        ],
    )
    assert "65.0/100" in out
    assert "marketplace" in out
    assert "NOT VERIFIABLE HERE" not in out


def test_main_is_advisory_even_with_no_scorer(tmp_path: Path, monkeypatch):
    """Advisory means advisory: a missing scorer must not fail a caller's gate."""
    monkeypatch.setattr(skill_eval, "_PLUGIN_ROOTS", (("pinned-clone", "nowhere"),))
    assert skill_eval.main([], tmp_path) == 0
