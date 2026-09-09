# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.recall_work` — the search-before-designing probe (#727).

Every test runs against a throwaway git repo from `conftest.git` (one commit on
`main`, an `origin/main` ref, `work` checked out) and never touches the live
`.agent/`, `graphify-out/memory/` or `~/.claude/plans`. `gh` is never executed:
a fake runner answers it while `git` runs for real, so the branch census is
measured against a real repository and the GitHub half is driven to each of its
states deliberately.

The two arms the module's contract makes mandatory (`probes-need-a-control-arm.md`):

* the POSITIVE arm — a topic that IS in a tracked file, a branch name and a plan
  is found by each probe, with the examined count beside each match;
* the CONTROL arm — a topic that matches nothing is EXAMINED (the counts are
  non-zero) and the CLI still exits `Rc.NOT_RUN` naming those counts, because a
  workflow step must never mistake "no prior work" for "the step did not run".
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec
import pytest
from kb_setup import recall_work
from kb_setup.generated.recall_work import (
    Branch,
    Probe,
    ProbeName,
    ProbeStatus,
    RecallWork,
    Verdict,
)
from kb_setup.result import Err, Ok, Rc

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

type Gh = Callable[[list[str]], tuple[int, str, str]]


def _offline(topic: str, tmp_path: Path, **overrides: object) -> recall_work.Options:
    """Options that touch nothing outside `tmp_path`: no siblings, no network, no live memory."""
    base = recall_work.Options(
        topic=topic,
        siblings=False,
        offline=True,
        memory_dir=tmp_path / "no-memory",
        plans_home=tmp_path / "no-plans-home",
    )
    return dataclasses.replace(base, **overrides)


def _with_fake_gh(handler: Gh) -> recall_work.Runner:
    """A runner that answers `gh` from `handler` (argv without the `gh`) and runs git for real."""

    def run(argv: Sequence[str], cwd: Path | None, timeout: float) -> tuple[int, str, str]:
        if argv and argv[0] == "gh":
            return handler(list(argv[1:]))
        return recall_work.subprocess_runner(argv, cwd, timeout)

    return run


def _probe(work: RecallWork, name: ProbeName) -> Probe:
    return next(p for p in work.probes if p.name is name)


def _branch(work: RecallWork, name: str) -> Branch:
    return next(b for b in work.branches if b.name == name)


# --- stems ------------------------------------------------------------------------


def test_stems_drop_stopwords_and_short_words_and_share_a_prefix_stem() -> None:
    """`dependency` and `dependencies` reach the same stem; `the`/`of`/`a` carry no topic."""
    assert recall_work.stems("the upgrade of a dependency") == ["upgrad", "dependenc"]
    assert recall_work.stems("dependencies") == recall_work.stems("dependency")
    # A stem that would fall under the floor keeps its whole spelling: cutting `mise`
    # to three letters would reach "promise" and "missing".
    assert recall_work.stems("mise pins") == ["mise", "pins"]


def test_a_topic_of_only_stopwords_is_a_bad_request(tmp_path: Path) -> None:
    result = recall_work.run(tmp_path, _offline("the of a", tmp_path))
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


# --- the positive arm ---------------------------------------------------------------


def test_the_topic_is_found_by_every_offline_probe_with_its_denominator(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """Tracked file, artifact page, branch name and a plan each match; `sources/` never does."""
    commit_file("docs/upgrade-plan.md", "# Upgrade plan\n\nHow we upgrade every dependency.\n")
    commit_file(
        "docs/artifacts/upgrade-grill.html",
        "<title>Upgrade grill</title><p>the dependency upgrade agreement</p>\n",
    )
    # A vendored copy of the same words must NOT be a hit: `sources/` is the graph's territory.
    commit_file("sources/vendored/notes.md", "upstream upgrade dependency notes\n")
    commit_file("README.md", "nothing about the topic here\n")
    git("branch", "feat/upgrade-deps", "work")
    plan = tmp_path / ".planning" / "2026-09-09-upgrade" / "task_plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Task Plan: dependency upgrade\n\n- upgrade the pins\n", encoding="utf-8")

    result = recall_work.run(tmp_path, _offline("dependency upgrade", tmp_path))

    assert isinstance(result, Ok), getattr(result, "message", result)
    work = result.value
    files = _probe(work, ProbeName.tracked_files)
    assert files.status is ProbeStatus.ran
    # The denominator is the whole tracked tree, cross-checked against git itself.
    assert files.examined == len(git("ls-files").splitlines())
    assert [h.ref for h in files.hits] == ["docs/upgrade-plan.md"]
    assert files.hits[0].summary == "Upgrade plan"
    pages = _probe(work, ProbeName.artifact_pages)
    assert (pages.examined, pages.matched) == (1, 1)
    assert pages.hits[0].summary == "Upgrade grill"
    branches = _probe(work, ProbeName.branches)
    assert [h.ref for h in branches.hits] == ["feat/upgrade-deps"]
    plans = _probe(work, ProbeName.plans)
    assert (plans.examined, plans.matched) == (1, 1)
    assert plans.hits[0].ref == ".planning/2026-09-09-upgrade/task_plan.md"
    assert plans.hits[0].summary == "Task Plan: dependency upgrade"
    assert work.matched_total == files.matched + pages.matched + branches.matched + plans.matched
    assert work.stems == ["dependenc", "upgrad"]


def test_main_writes_the_report_under_agent_kb_recall_and_exits_ok(
    git: Callable[..., str],
    commit_file: Callable[..., str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit_file("docs/notes.md", "dependency upgrade notes\n")
    git("branch", "chore/unrelated", "work")
    argv = ["dependency", "upgrade", "--offline", "--no-siblings"]
    argv += ["--memory-dir", str(tmp_path / "none"), "--plans-home", str(tmp_path / "none")]

    rc = recall_work.main(tmp_path, argv)

    assert rc == int(Rc.OK)
    report = tmp_path / ".agent" / "kb" / "recall" / "dependency-upgrade.md"
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    assert "docs/notes.md" in text
    # The census lists EVERY branch, not only the topic's: pending work is pending regardless.
    assert "chore/unrelated" in text
    assert "topic matches" in capsys.readouterr().out


# --- the control arm ----------------------------------------------------------------


def test_an_unmatched_topic_is_examined_and_refused_naming_the_counts(
    git: Callable[..., str],
    commit_file: Callable[..., str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The FAIL arm of #727: examined > 0, matched == 0, rc NOT_RUN, counts in the message."""
    commit_file("docs/notes.md", "dependency upgrade notes\n")
    git("branch", "feat/pending", "work")
    argv = ["quantum", "teapot", "--offline", "--no-siblings"]
    argv += ["--memory-dir", str(tmp_path / "none"), "--plans-home", str(tmp_path / "none")]

    rc = recall_work.main(tmp_path, argv)

    assert rc == int(Rc.NOT_RUN)
    err = capsys.readouterr().err
    assert "no prior work matched" in err
    assert "tracked_files 0/" in err  # the denominator travels with the zero
    assert "quantum, teapot" in err  # the stems, because a spelling is a bound
    # The branch census is still written: it is worth having whatever the topic.
    report = tmp_path / ".agent" / "kb" / "recall" / "quantum-teapot.md"
    assert "feat/pending" in report.read_text(encoding="utf-8")


def test_nothing_examined_is_refused_not_reported_as_empty(tmp_path: Path) -> None:
    """A root that is not a git checkout examines nothing, and says so with NOT_RUN."""
    root = tmp_path / "not-a-repo"
    root.mkdir()
    result = recall_work.run(root, _offline("dependency upgrade", tmp_path))
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "nothing was examined" in result.message
    assert not (root / ".agent").exists()


# --- the branch census ----------------------------------------------------------------


def test_branch_verdicts_current_merged_live_and_unverified(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """Checked out -> current; no unique commits -> merged; unique + gh says merged -> merged.

    Unique + gh says nothing -> live; unique + offline -> unverified. `work` is the
    fixture's checked-out branch and carries the unique commit the others are
    measured against.
    """
    git("remote", "add", "origin", "git@github.com:o/r.git")
    commit_file("docs/a.md", "x\n")  # `work` is now ahead of origin/main by one
    git("branch", "twin-of-main", "origin/main")
    git("branch", "feat/squashed", "work")
    git("branch", "feat/open", "work")

    calls: list[list[str]] = []

    def gh(argv: list[str]) -> tuple[int, str, str]:
        calls.append(argv)
        if argv[0] == "api":  # the issues probe's own calls: not under test here
            return 0, '{"has_issues": false}', ""
        merged = (
            '[{"number": 41, "headRefName": "feat/squashed"}, {"number": 9, "headRefName": "x"}]'
        )
        return 0, merged, ""

    online = recall_work.run(
        tmp_path,
        _offline("anything", tmp_path, offline=False),
        runner=_with_fake_gh(gh),
    )
    assert isinstance(online, Ok)
    assert _branch(online.value, "work").verdict is Verdict.current
    assert _branch(online.value, "twin-of-main").verdict is Verdict.merged
    squashed = _branch(online.value, "feat/squashed")
    assert (squashed.verdict, squashed.merged_pr, squashed.ahead) == (Verdict.merged, 41, 1)
    assert _branch(online.value, "feat/open").verdict is Verdict.live
    assert online.value.repos[0].slug == "o/r"
    # ONE merged-PR listing per repo, never one call per branch (the first live
    # run made 98 of them and took five minutes).
    assert sum(1 for argv in calls if argv[:2] == ["pr", "list"]) == 1

    offline = recall_work.run(tmp_path, _offline("anything", tmp_path))
    assert isinstance(offline, Ok)
    assert _branch(offline.value, "feat/open").verdict is Verdict.unverified
    # Sorted live-first so the report's top is the pending work.
    assert offline.value.branches[0].verdict in (Verdict.live, Verdict.unverified)


def test_a_gh_failure_leaves_a_branch_unverified_never_merged(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    git("remote", "add", "origin", "https://github.com/o/r")
    commit_file("docs/a.md", "x\n")
    git("branch", "feat/open", "work")

    def gh(_argv: list[str]) -> tuple[int, str, str]:
        return 1, "", "HTTP 403: API rate limit exceeded"

    result = recall_work.run(
        tmp_path, _offline("anything", tmp_path, offline=False), runner=_with_fake_gh(gh)
    )
    assert isinstance(result, Ok)
    assert _branch(result.value, "feat/open").verdict is Verdict.unverified
    assert "left unverified" in _probe(result.value, ProbeName.branches).detail


# --- issues -----------------------------------------------------------------------------


def test_issues_that_could_not_be_asked_are_never_reported_as_zero(
    git: Callable[..., str], tmp_path: Path
) -> None:
    git("remote", "add", "origin", "git@github.com:o/r.git")

    def gh(_argv: list[str]) -> tuple[int, str, str]:
        return 1, "", "HTTP 403: API rate limit exceeded for user"

    result = recall_work.run(
        tmp_path, _offline("dependency upgrade", tmp_path, offline=False), runner=_with_fake_gh(gh)
    )
    assert isinstance(result, Ok)  # the git probes still examined the repo
    issues = _probe(result.value, ProbeName.issues)
    assert issues.status is ProbeStatus.could_not_ask
    assert (issues.examined, issues.matched) == (0, 0)
    assert "rate limit" in issues.detail
    # A probe that could not ask is excluded from the totals, not counted as none.
    assert result.value.matched_total == sum(
        p.matched for p in result.value.probes if p.status is ProbeStatus.ran
    )


def test_issues_are_searched_open_and_closed_with_the_whole_repo_as_denominator(
    git: Callable[..., str], tmp_path: Path
) -> None:
    git("remote", "add", "origin", "git@github.com:o/r.git")
    seen: list[list[str]] = []

    def gh(argv: list[str]) -> tuple[int, str, str]:
        if argv[:2] == ["pr", "list"]:  # the branch census's one merged-PR listing
            return 0, "[]", ""
        seen.append(argv)
        if argv[:2] == ["api", "repos/o/r"]:
            return 0, '{"has_issues": true}', ""
        query = argv[argv.index("-f") + 1]
        if query.endswith("is:issue"):
            return 0, '{"total_count": 57, "items": []}', ""
        items = (
            '[{"number": 12, "state": "closed", "title": "Upgrade the pins", '
            '"updated_at": "2026-08-01T00:00:00Z"}, '
            '{"number": 30, "state": "open", "title": "Dependency upgrade round", '
            '"updated_at": "2026-09-09T00:00:00Z"}]'
        )
        return 0, f'{{"total_count": 2, "items": {items}}}', ""

    result = recall_work.run(
        tmp_path, _offline("dependency upgrade", tmp_path, offline=False), runner=_with_fake_gh(gh)
    )
    assert isinstance(result, Ok)
    issues = _probe(result.value, ProbeName.issues)
    assert issues.status is ProbeStatus.ran
    assert (issues.examined, issues.matched) == (57, 2)
    assert [(h.ref, h.state) for h in issues.hits] == [("#12", "closed"), ("#30", "open")]
    # The search goes through `gh api search/issues`, never `gh search`.
    assert all(argv[0] == "api" for argv in seen)
    assert any("q=repo:o/r is:issue dependency upgrade" in argv for argv in seen)


def test_issues_disabled_on_a_fork_is_skipped_not_could_not_ask(
    git: Callable[..., str], tmp_path: Path
) -> None:
    git("remote", "add", "origin", "https://github.com/o/fork")

    def gh(argv: list[str]) -> tuple[int, str, str]:
        if argv[:2] == ["pr", "list"]:
            return 0, "[]", ""
        assert argv[:2] == ["api", "repos/o/fork"]
        return 0, '{"has_issues": false}', ""

    result = recall_work.run(
        tmp_path, _offline("dependency upgrade", tmp_path, offline=False), runner=_with_fake_gh(gh)
    )
    assert isinstance(result, Ok)
    issues = _probe(result.value, ProbeName.issues)
    assert issues.status is ProbeStatus.skipped
    assert "issues disabled" in issues.detail


# --- plans and worktrees ---------------------------------------------------------------


def test_plans_are_read_from_the_repo_and_the_claude_home(
    git: Callable[..., str], tmp_path: Path
) -> None:
    git("rev-parse", "HEAD")  # the fixture's only job here is making tmp_path a repo
    handoff = tmp_path / ".agent" / "plans" / "session-2026-09-09.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text("# handoff\n\nthe dependency upgrade workflow\n", encoding="utf-8")
    home = tmp_path.parent / "claude-home-plans"
    home.mkdir(exist_ok=True)
    (home / "upgrade-plan.md").write_text("# Plan\n\nupgrade every dependency\n", encoding="utf-8")
    (home / "other.md").write_text("# Other\n\nnothing here\n", encoding="utf-8")

    result = recall_work.run(tmp_path, _offline("dependency upgrade", tmp_path, plans_home=home))

    assert isinstance(result, Ok)
    plans = _probe(result.value, ProbeName.plans)
    assert (plans.examined, plans.matched) == (3, 2)
    assert {h.ref for h in plans.hits} == {
        ".agent/plans/session-2026-09-09.md",
        str(home / "upgrade-plan.md"),
    }


def test_a_linked_worktree_is_listed_and_its_branch_can_match(
    git: Callable[..., str], tmp_path: Path
) -> None:
    linked = tmp_path.parent / f"{tmp_path.name}-wt"
    git("worktree", "add", "-q", "-b", "feat/upgrade-wt", str(linked), "main")
    try:
        result = recall_work.run(tmp_path, _offline("upgrade", tmp_path))
        assert isinstance(result, Ok)
        worktrees = _probe(result.value, ProbeName.worktrees)
        assert (worktrees.examined, worktrees.matched) == (1, 1)
        assert worktrees.hits[0].summary == "feat/upgrade-wt"
        # A branch checked out in ANY worktree is `current`, never a deletion candidate.
        assert _branch(result.value, "feat/upgrade-wt").verdict is Verdict.current
    finally:
        git("worktree", "remove", "--force", str(linked))


# --- the contract and the CLI grammar ----------------------------------------------------


def test_the_output_round_trips_through_the_generated_contract(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    commit_file("docs/notes.md", "dependency upgrade notes\n")
    git("branch", "feat/upgrade", "work")
    result = recall_work.run(tmp_path, _offline("dependency upgrade", tmp_path))
    assert isinstance(result, Ok)
    decoded = msgspec.json.decode(recall_work.render_json(result.value).encode(), type=RecallWork)
    assert decoded == result.value
    assert decoded.schema_version == 1


def test_the_report_slug_is_filesystem_safe() -> None:
    assert recall_work.slug("../../Dependency Upgrade / v2!") == "dependency-upgrade-v2"
    assert recall_work.slug("///") == "topic"


@pytest.mark.parametrize(
    ("args", "why"),
    [
        ([], "no topic"),
        (["--offline"], "flags but no topic"),
        (["--top", "x", "t"], "non-numeric --top"),
        (["--limit", "0", "t"], "non-positive --limit"),
        (["--bogus", "t"], "unknown flag"),
        (["t", "--repo"], "flag with no value"),
    ],
)
def test_a_malformed_request_is_a_bad_request(args: list[str], why: str) -> None:
    result = recall_work.parse(args)
    assert isinstance(result, Err), why
    assert result.rc is Rc.BAD_REQUEST, why


def test_a_valid_request_parses_words_into_one_topic() -> None:
    result = recall_work.parse(["dependency", "upgrade", "--offline", "--top", "3", "--repo", "/x"])
    assert isinstance(result, Ok)
    options = result.value
    assert options.topic == "dependency upgrade"
    assert (options.offline, options.top, options.repos) == (True, 3, (Path("/x"),))
    assert options.siblings is True
