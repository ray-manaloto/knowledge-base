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

import pytest
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


def test_anti_patterns_are_read_from_the_key_plugin_eval_actually_emits():
    """`flag` — measured from plugin-eval 0.1.0, not assumed.

    The reader looked for `name`/`type`/`pattern` and reported **0
    anti-patterns for all 7 of this repo's skills when 5 had one**. The claim
    reached the committed baseline, a commit message and a session handoff. The
    test above passed the whole time because its fixture used `name`: code and
    test shared one wrong assumption and agreed with each other, which is why a
    green suite proved nothing (`probes-need-a-control-arm.md`).

    This payload is copied from a real run, verbatim.
    """
    real = json.dumps(
        {
            "composite": {"score": 62.8, "anti_pattern_penalty": 0.95},
            "layers": [
                {
                    "layer": "static",
                    "anti_patterns": [
                        {
                            "flag": "DEAD_CROSS_REF",
                            "description": "Cross-reference to skill/agent 'baseline' cannot be "
                            "resolved. Dead links degrade ecosystem coherence.",
                            "severity": 0.05,
                        }
                    ],
                }
            ],
        }
    )
    got = skill_eval._parse("clear-prep", real, vendored=False)
    assert got.anti_patterns == ("DEAD_CROSS_REF",)
    # The penalty is carried too: it is the ONLY term that explains a composite
    # falling while every reported dimension improved.
    assert got.penalty == 0.95


def test_the_penalty_defaults_to_a_no_op_when_absent():
    """Control arm: a clean skill must not be rendered as penalised."""
    got = skill_eval._parse("x", _report(), vendored=False)
    assert got.penalty == 1.0
    assert got.anti_patterns == ()


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


def _skills(root: Path, *names: str) -> None:
    """A `.claude/skills/` tree holding one real skill per name."""
    for name in names:
        d = root / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def test_skill_dirs_requires_a_skill_md_file(tmp_path: Path):
    """`.claude/skills/` also holds `references/` and `scripts/` subtrees.

    Handing one of those to plugin-eval scores a fragment as if it were a skill,
    so the presence of `SKILL.md` — not merely being a directory — is the test.
    """
    _skills(tmp_path, "real")
    (tmp_path / ".claude" / "skills" / "not-a-skill").mkdir()

    found, unknown = skill_eval.skill_dirs(tmp_path)
    assert [p.name for p in found] == ["real"]
    assert unknown == []


def test_skill_dirs_is_empty_when_there_is_no_skills_dir(tmp_path: Path):
    assert skill_eval.skill_dirs(tmp_path) == ([], [])


def test_this_repos_own_skills_are_discovered():
    """Control arm for the two negatives above, against the real tree."""
    names = {p.name for p in skill_eval.skill_dirs(_REPO)[0]}
    assert {"clear-prep", "kb-review", "kb-curator"} <= names


def test_an_unresolved_name_is_reported_not_dropped(tmp_path: Path):
    """The #139 defect: a typo rendered identically to an empty corpus.

    `mise run kb-skill-score -- clear-prpe` printed "no skill directories under
    .claude/skills" with 7 skills present, because the filter dropped names with
    no `SKILL.md` silently. The unresolved name must survive to the caller.
    """
    _skills(tmp_path, "real")
    found, unknown = skill_eval.skill_dirs(tmp_path, ["reeal", "real"])
    assert [p.name for p in found] == ["real"]
    assert unknown == ["reeal"]


def test_main_exits_2_on_a_typod_skill_name_and_names_it(tmp_path: Path, capsys):
    """FAIL arm. Advisory covers findings, never a malformed request."""
    _skills(tmp_path, "real")
    assert skill_eval.main(["reeal"], tmp_path) == 2
    err = capsys.readouterr().err
    assert "reeal" in err
    assert "real" in err  # what IS present, so the typo is fixable from the message


def test_main_still_exits_0_when_the_corpus_really_is_empty(tmp_path: Path, capsys):
    """Control arm for the above: absence is a different answer, and stays rc 0."""
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    assert skill_eval.main([], tmp_path) == 0
    assert "no skill directories" in capsys.readouterr().err


def test_write_refuses_a_partial_run(tmp_path: Path):
    """A baseline written from one skill deletes every other skill's record."""
    _skills(tmp_path, "real", "other")
    assert skill_eval.main(["--write", "real"], tmp_path) == 2


def test_an_unrecognised_flag_is_refused_like_an_unknown_name(tmp_path: Path, capsys):
    """Cold lane, round 1: a bad flag ran a normal scoring pass and returned 0.

    Splitting argv on a leading `-` dropped every unrecognised flag out of
    `names`, and only an exact `"--write"` ever set the flag — so `--dry-run`, or
    a misspelling of `--write`, took the same path as a well-formed no-argument
    request, having done none of what was asked. The rule the module applies to
    an unknown SKILL has to apply here too.

    `--dry-run` rather than a misspelling on purpose: a plausible flag someone
    assumes exists is the case that actually happens, and it does not need a
    spell-checker exemption to sit in the test suite.
    """
    _skills(tmp_path, "real")
    assert skill_eval.main(["--dry-run"], tmp_path) == 2
    err = capsys.readouterr().err
    assert "--dry-run" in err
    assert "--write" in err  # what IS accepted, so the mistake is fixable from the message
    assert not (tmp_path / "docs" / "skills" / "baseline.json").exists()


def test_the_accepted_flag_still_works(tmp_path: Path):
    """Control arm for the above: rejection must not swallow the real flag."""
    assert skill_eval.main(["--write"], tmp_path) == 0  # no skills here -> rc 0, not 2


# -------------------------------------------------------------- vendored ----


def test_vendored_names_come_from_currency_toml(tmp_path: Path):
    (tmp_path / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "graphify"\nskill_dir = ".claude/skills/graphify"\n'
        '[tool.hk]\nmise_key = "hk"\n',
        encoding="utf-8",
    )
    assert skill_eval.vendored_names(tmp_path) == frozenset({"graphify"})


def test_vendored_names_are_empty_without_a_config(tmp_path: Path):
    assert skill_eval.vendored_names(tmp_path) == frozenset()


def test_a_malformed_config_does_not_kill_the_scoring_run(tmp_path: Path, capsys):
    """`config.load` RAISES on a bad table; an advisory scorer must not die of it."""
    (tmp_path / "currency.toml").write_text("[tool.broken]\npypi = 'x'\n", encoding="utf-8")
    assert skill_eval.vendored_names(tmp_path) == frozenset()
    assert "currency.toml" in capsys.readouterr().err


def test_this_repos_real_config_still_declares_the_vendored_skill():
    """Control arm against the real tree — the hardcoded set this replaced."""
    assert "graphify" in skill_eval.vendored_names(_REPO)


# ------------------------------------------------------------- baseline ----


def test_baseline_round_trips_and_deltas_against_the_same_scorer(tmp_path: Path):
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    skill_eval.write_baseline(tmp_path, scorer, [skill_eval.SkillScore(name="a", score=60.0)])

    loaded = skill_eval.load_baseline(tmp_path)
    assert loaded is not None
    assert loaded.delta(skill_eval.SkillScore(name="a", score=61.4), scorer) == "+1.4"
    assert loaded.delta(skill_eval.SkillScore(name="b", score=61.4), scorer) == "new"


def test_an_unchanged_score_is_never_rendered_as_a_regression():
    """Measured: re-running against a fresh baseline printed `-0.0` for 3 of 7.

    The baseline stores 1dp and the live score carries full precision, so a
    skill nobody touched differenced raw shows a minus sign — on the one column
    whose entire purpose is to say whether anything moved.
    """
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    baseline = skill_eval.Baseline(scorer=scorer.key(), scores={"a": 61.1})
    assert baseline.delta(skill_eval.SkillScore(name="a", score=61.14159), scorer) == "0.0"
    assert baseline.delta(skill_eval.SkillScore(name="a", score=61.0501), scorer) == "0.0"
    # Control arm: a real move of the same size still shows, with its sign.
    assert baseline.delta(skill_eval.SkillScore(name="a", score=61.2), scorer) == "+0.1"
    assert baseline.delta(skill_eval.SkillScore(name="a", score=61.0), scorer) == "-0.1"


def test_no_delta_across_two_different_scorers(tmp_path: Path):
    """Two scores from different plugin-eval builds are not comparable.

    The provenance line exists for this reason; a Δ that quietly spanned two
    builds would be exactly the false precision the module refuses elsewhere.
    """
    first = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    later = skill_eval.Scorer(root=Path("/x"), origin="pinned-clone", version="0.2.0", code_id="c2")
    skill_eval.write_baseline(tmp_path, first, [skill_eval.SkillScore(name="a", score=60.0)])

    loaded = skill_eval.load_baseline(tmp_path)
    assert loaded is not None
    assert loaded.delta(skill_eval.SkillScore(name="a", score=61.4), later) == "—"
    # ...and the reader is told WHY, rather than shown a column of dashes.
    out = skill_eval._render(later, [skill_eval.SkillScore(name="a", score=61.4)], baseline=loaded)
    assert "different scorer" in out


def test_a_failed_skill_refuses_the_whole_write_rather_than_erasing_its_history():
    """Cold lane, round 1 — the P2. Writing would DELETE `b`'s last known score.

    The payload is built from this run's results, so a skill with no number stops
    being a key and the next successful run reports it as `new` — a delta that
    silently never happened. One `subprocess.TimeoutExpired`, the case the
    timeout handling exists for, is enough to trigger it.
    """
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    with pytest.raises(ValueError, match="did not score"):
        skill_eval.write_baseline(
            Path("/nonexistent-should-not-be-reached"),
            scorer,
            [
                skill_eval.SkillScore(name="a", score=60.0),
                skill_eval.SkillScore(name="b", score=None, error="boom"),
            ],
        )


def test_the_refusal_leaves_the_existing_baseline_untouched(tmp_path: Path):
    """It must refuse BEFORE writing — a truncated file is the harm itself."""
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    good = [
        skill_eval.SkillScore(name="a", score=60.0),
        skill_eval.SkillScore(name="b", score=70.0),
    ]
    skill_eval.write_baseline(tmp_path, scorer, good)
    before = (tmp_path / "docs" / "skills" / "baseline.json").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="did not score"):
        skill_eval.write_baseline(
            tmp_path,
            scorer,
            [
                skill_eval.SkillScore(name="a", score=61.0),
                skill_eval.SkillScore(name="b", score=None),
            ],
        )
    assert (tmp_path / "docs" / "skills" / "baseline.json").read_text(encoding="utf-8") == before
    loaded = skill_eval.load_baseline(tmp_path)
    assert loaded is not None
    assert loaded.scores == {"a": 60.0, "b": 70.0}  # b's history survived


def test_partial_corruption_rejects_the_whole_baseline(tmp_path: Path):
    """Cold lane, round 2 — P2. Filtering bad entries out reported a lie.

    A dropped entry then reads as `new` in the Δ column: an assertion the skill
    has never been measured. Discarding the whole baseline reports "no Δ", which
    is merely an absence. Reproduced by the lane against the pre-fix code.
    """
    d = tmp_path / "docs" / "skills"
    d.mkdir(parents=True)
    (d / "baseline.json").write_text(
        json.dumps(
            {"scorer": "s", "scores": {"good": 5.0, "bad": "not-a-number", "also-bad": None}}
        ),
        encoding="utf-8",
    )
    assert skill_eval.load_baseline(tmp_path) is None


def test_a_boolean_score_is_corruption_not_the_number_one(tmp_path: Path):
    """`bool` subclasses `int`, so `true` would otherwise load as a score of 1.0."""
    d = tmp_path / "docs" / "skills"
    d.mkdir(parents=True)
    (d / "baseline.json").write_text(
        json.dumps({"scorer": "s", "scores": {"a": True}}), encoding="utf-8"
    )
    assert skill_eval.load_baseline(tmp_path) is None


def test_a_wholly_valid_baseline_still_loads(tmp_path: Path):
    """Control arm for the two rejections above."""
    d = tmp_path / "docs" / "skills"
    d.mkdir(parents=True)
    (d / "baseline.json").write_text(
        json.dumps({"scorer": "s", "scores": {"a": 5, "b": 6.5}}), encoding="utf-8"
    )
    loaded = skill_eval.load_baseline(tmp_path)
    assert loaded is not None
    assert loaded.scores == {"a": 5.0, "b": 6.5}


# ------------------------------------------------------- scorer identity ----


def test_the_key_carries_a_code_identity_not_just_a_version(tmp_path: Path, monkeypatch):
    """Cold lane, round 2 — P2. A pin bump can change the evaluator, not the version.

    `sources/agents.manifest` pins the fallback checkout by COMMIT while
    `plugins/plugin-eval/pyproject.toml` carries a static version maintained
    independently, so advancing the pin changes the scoring code while `key()`
    stays identical — and every later Δ silently compares two scorers.
    """
    root = tmp_path / "vendor" / "plugin-eval"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text('version = "0.1.0"\n', encoding="utf-8")
    (root / "src" / "score.py").write_text("THRESHOLD = 1\n", encoding="utf-8")
    monkeypatch.setattr(skill_eval, "_PLUGIN_ROOTS", (("pinned-clone", "vendor/plugin-eval"),))

    first = skill_eval.resolve_scorer(tmp_path)
    assert first is not None
    assert first.code_id

    # Same declared version, different scoring code — the exact case above.
    (root / "src" / "score.py").write_text("THRESHOLD = 2\n", encoding="utf-8")
    second = skill_eval.resolve_scorer(tmp_path)
    assert second is not None
    assert second.version == first.version == "0.1.0"
    assert second.key() != first.key(), "a code change must break comparability"

    # ...and a baseline from the first is refused by the second, rather than
    # producing a delta across two different evaluators.
    baseline = skill_eval.Baseline(scorer=first.key(), scores={"a": 60.0})
    assert baseline.delta(skill_eval.SkillScore(name="a", score=65.0), second) == "—"
    assert baseline.delta(skill_eval.SkillScore(name="a", score=65.0), first) == "+5.0"


def test_an_unreadable_checkout_never_compares_equal_to_another_one():
    """Two `code:unknown` keys are string-equal without being the same code.

    That is why `_code_id` returns "" rather than the digest of nothing (a
    constant, and therefore a false identity shared by every broken checkout).
    """
    blind = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="")
    assert "code:unknown" in blind.key()
    baseline = skill_eval.Baseline(scorer=blind.key(), scores={"a": 60.0})
    assert baseline.delta(skill_eval.SkillScore(name="a", score=65.0), blind) == "—"


# -------------------------------------------------------- atomic writing ----


def test_a_failed_second_write_leaves_the_delta_input_intact(tmp_path: Path, monkeypatch):
    """Cold lane, round 2 — P2. Two files, no atomic two-file write.

    The JSON is the only input to the Δ and the README renders it, so the JSON
    is written LAST: a failure then leaves the Δ computing against the intact
    OLD baseline. The reverse order would leave a new baseline no README
    documents, and the next run would absorb the movement silently.
    """
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    skill_eval.write_baseline(tmp_path, scorer, [skill_eval.SkillScore(name="a", score=60.0)])
    original = (tmp_path / "docs" / "skills" / "baseline.json").read_text(encoding="utf-8")

    real = Path.write_text
    calls = {"n": 0}

    def flaky(self: Path, data: str, encoding: str | None = None) -> int:
        calls["n"] += 1
        if calls["n"] == 2:  # the JSON, written second
            raise OSError("disk full")
        return real(self, data, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", flaky)
    with pytest.raises(OSError, match="disk full"):
        skill_eval.write_baseline(tmp_path, scorer, [skill_eval.SkillScore(name="a", score=99.0)])
    monkeypatch.undo()

    # The Δ input survived the failure...
    assert (tmp_path / "docs" / "skills" / "baseline.json").read_text(encoding="utf-8") == original
    # ...and no half-written temp file was left beside it.
    assert not list((tmp_path / "docs" / "skills").glob("*.tmp"))


def test_an_interrupted_write_never_truncates_the_committed_baseline(tmp_path: Path, monkeypatch):
    """The temp-then-rename, probed by the failure it exists for.

    Injecting an error *at* `write_text` cannot tell in-place from atomic — both
    leave the target untouched, which is why the first version of this test
    passed against a mutation that removed the rename entirely. The failure that
    discriminates is an interruption PART-WAY THROUGH: writing in place truncates
    the real file first, so a crash leaves a corrupt baseline that the next
    `load_baseline` (correctly) discards, silently losing every recorded score.
    """
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    skill_eval.write_baseline(tmp_path, scorer, [skill_eval.SkillScore(name="a", score=60.0)])
    target = tmp_path / "docs" / "skills" / "baseline.json"
    original = target.read_text(encoding="utf-8")

    real = Path.write_text
    calls = {"n": 0}

    def interrupted(self: Path, data: str, encoding: str | None = None) -> int:
        calls["n"] += 1
        if calls["n"] == 2:  # the JSON, written second
            real(self, data[: len(data) // 2], encoding=encoding)  # truncated on disk...
            raise OSError("interrupted mid-write")  # ...then the process dies
        return real(self, data, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        skill_eval.write_baseline(tmp_path, scorer, [skill_eval.SkillScore(name="a", score=99.0)])
    monkeypatch.undo()

    assert target.read_text(encoding="utf-8") == original, "committed baseline was truncated"
    assert skill_eval.load_baseline(tmp_path) is not None, "baseline left unreadable"
    assert not list((tmp_path / "docs" / "skills").glob("*.tmp")), "temp debris left behind"


def test_main_reports_a_write_failure_instead_of_crashing(tmp_path: Path, monkeypatch, capsys):
    """An uncaught traceback out of an advisory task is a worse report than rc 2."""
    _skills(tmp_path, "real")
    monkeypatch.setattr(
        skill_eval,
        "resolve_scorer",
        lambda _: skill_eval.Scorer(
            root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1"
        ),
    )
    monkeypatch.setattr(
        skill_eval,
        "score_one",
        lambda *_a, **_kw: skill_eval.SkillScore(name="real", score=60.0),
    )
    monkeypatch.setattr(
        skill_eval,
        "write_baseline",
        lambda *_a, **_kw: (_ for _ in ()).throw(OSError("read-only fs")),
    )
    assert skill_eval.main(["--write"], tmp_path) == 2
    assert "read-only fs" in capsys.readouterr().err


def test_an_unreadable_baseline_is_the_same_answer_as_none(tmp_path: Path):
    path = tmp_path / "docs" / "skills"
    path.mkdir(parents=True)
    (path / "baseline.json").write_text("{ not json", encoding="utf-8")
    assert skill_eval.load_baseline(tmp_path) is None


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


def test_the_comparability_key_carries_no_absolute_path():
    """It is written into a TRACKED file and compared across machines.

    Keying on `root` would commit one developer's home directory and make every
    Δ vanish on any other host, even when the identical build scored both.
    """
    scorer = skill_eval.Scorer(
        root=Path("/Users/someone/.claude/plugins/x"),
        origin="marketplace",
        version="0.1.0",
        code_id="abc123",
    )
    assert scorer.key() == "plugin-eval 0.1.0 [marketplace] code:abc123"
    assert "/Users/" not in scorer.key()
    # Control arm: the console label DOES still name the checkout that ran.
    assert "/Users/someone" in scorer.label()


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
    scorer = skill_eval.Scorer(
        root=Path("/x"), origin="pinned-clone", version="0.1.0", code_id="c1"
    )
    out = skill_eval._render(
        scorer, [skill_eval.SkillScore(name="a", score=None, error="boom")], baseline=None
    )
    assert "NOT VERIFIABLE HERE" in out
    assert "0.0/100" not in out


def test_a_scored_run_reports_the_mean_and_names_its_scorer():
    scorer = skill_eval.Scorer(root=Path("/x"), origin="marketplace", version="0.1.0", code_id="c1")
    out = skill_eval._render(
        scorer,
        [
            skill_eval.SkillScore(name="a", score=60.0),
            skill_eval.SkillScore(name="b", score=70.0),
        ],
        baseline=None,
    )
    assert "65.0/100" in out
    assert "marketplace" in out
    assert "NOT VERIFIABLE HERE" not in out


def test_every_accepted_flag_appears_in_the_cli_usage_text():
    """Every accepted flag must appear in `kb-setup`'s own usage line.

    Cold lane, round 1 — the P3. `--write` reached mise.toml and the rule file
    and never reached `kb-setup`'s own usage line, which is the one place a
    reader looks when the task's `--` passthrough is what confused them.

    Asserted against `_FLAGS` rather than the literal string, so a flag added
    later fails here instead of quietly repeating the omission.
    """
    usage = (Path(skill_eval.__file__).parent / "cli.py").read_text(encoding="utf-8")
    for flag in skill_eval._FLAGS:
        assert f"skill-score [{flag}]" in usage, f"{flag} missing from cli.py usage"


def test_main_is_advisory_even_with_no_scorer(tmp_path: Path, monkeypatch):
    """Advisory means advisory: a missing scorer must not fail a caller's gate."""
    monkeypatch.setattr(skill_eval, "_PLUGIN_ROOTS", (("pinned-clone", "nowhere"),))
    assert skill_eval.main([], tmp_path) == 0
