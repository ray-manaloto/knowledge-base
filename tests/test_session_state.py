"""Tests for `kb_setup.session_state` — the working-state snapshot (#144).

Driven against the real `git` fixture repo in `conftest.py`, per criterion 5:
no mocking of git internals. The only stubbed thing is `_gh`, because a test
must not make a network call — and stubbing it is what lets the third PR state
("could not ask") be armed at all, which is the one behaviour #144's design
comment says must exist.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from kb_setup import session_state


def _no_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub `_gh` as a repo with no open PR — rc=0 and a well-formed empty list."""
    monkeypatch.setattr(session_state, "_gh", lambda _args, _root: (0, "[]"))


def _gh_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub `_gh` as unreachable — the state that must not read as "no open PR"."""
    monkeypatch.setattr(
        session_state, "_gh", lambda _args, _root: (1, "gh: could not connect to api.github.com")
    )


# --------------------------------------------------------------------------
# criterion 6 — both arms: a clean tree and a dirty one
# --------------------------------------------------------------------------


def test_a_clean_tree_reports_an_empty_split(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean tree is an ordinary result: empty tuples, `read` True (criterion 4)."""
    _no_pr(monkeypatch)
    snap = session_state.gather(tmp_path)

    assert snap.changes.read is True
    assert snap.changes.staged == ()
    assert snap.changes.unstaged == ()
    assert snap.changes.untracked == ()
    assert snap.changes.clean is True


def test_a_dirty_tree_splits_staged_unstaged_and_untracked(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The three buckets are read from one `git status`, and kept apart."""
    _no_pr(monkeypatch)
    # tracked + committed, then modified in the worktree only -> unstaged
    (tmp_path / "tracked.txt").write_text("one\n", encoding="utf-8")
    git("add", "--", "tracked.txt")
    git("commit", "-q", "-m", "add tracked")
    (tmp_path / "tracked.txt").write_text("two\n", encoding="utf-8")
    # added to the index -> staged
    (tmp_path / "staged.txt").write_text("s\n", encoding="utf-8")
    git("add", "--", "staged.txt")
    # never added -> untracked
    (tmp_path / "untracked.txt").write_text("u\n", encoding="utf-8")

    snap = session_state.gather(tmp_path)

    assert snap.changes.read is True
    assert snap.changes.clean is False
    assert "staged.txt" in snap.changes.staged
    assert "tracked.txt" in snap.changes.unstaged
    assert "untracked.txt" in snap.changes.untracked
    # The buckets are disjoint here — a path modified only in the worktree must
    # not also be reported as staged, which is what reading X and Y as one status
    # character would do.
    assert "tracked.txt" not in snap.changes.staged
    assert "staged.txt" not in snap.changes.unstaged


def test_a_path_staged_and_then_modified_again_is_in_both_buckets(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`MM` is genuinely both, and collapsing it to one loses a real distinction.

    A handoff that says "staged: foo" when foo also has unstaged edits invites
    the reader to believe the staged content is the whole change.
    """
    _no_pr(monkeypatch)
    (tmp_path / "both.txt").write_text("a\n", encoding="utf-8")
    git("add", "--", "both.txt")
    (tmp_path / "both.txt").write_text("b\n", encoding="utf-8")

    changes = session_state.gather(tmp_path).changes

    assert "both.txt" in changes.staged
    assert "both.txt" in changes.unstaged


def test_a_rename_does_not_shift_the_entries_after_it(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r"""`-z` gives an R entry a SECOND NUL field; consuming it is not optional.

    THE ASSERTIONS ARE EXACT, and that is the whole point of this test. The
    fixture really does produce `R  zz-new-name.txt\\0old-name.txt\\0A  zzz-after.txt\\0`
    (probed directly, not assumed). Tracing the UNFIXED parse over those bytes:
    the origin field `old-name.txt` is read as a record whose X/Y are `o`/`l`
    and whose path is `-name.txt`, so it lands in staged AND unstaged — while
    `zzz-after.txt` still parses correctly afterwards.

    So the obvious arm — "is the later path still in staged?" — PASSES with the
    bug present. It is a fixture that cannot exhibit the harm, which is this
    repo's recurring false-pass (rule 3 of `probes-need-a-control-arm.md`). What
    discriminates is the SPURIOUS entry, so the buckets are asserted whole.
    """
    _no_pr(monkeypatch)
    (tmp_path / "old-name.txt").write_text("x\n", encoding="utf-8")
    git("add", "--", "old-name.txt")
    git("commit", "-q", "-m", "add old-name")
    git("mv", "old-name.txt", "zz-new-name.txt")
    # Sorts after the rename entries, so a one-field shift is visible around it.
    (tmp_path / "zzz-after.txt").write_text("a\n", encoding="utf-8")
    git("add", "--", "zzz-after.txt")

    changes = session_state.gather(tmp_path).changes

    assert changes.staged == ("zz-new-name.txt", "zzz-after.txt")
    assert changes.unstaged == ()
    assert changes.untracked == ()


def test_a_detached_head_does_not_report_a_checked_no_open_pr(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`git rev-parse --abbrev-ref HEAD` returns the literal "HEAD" when detached.

    `gh pr list --head HEAD` is then a well-formed query that matches nothing,
    so without a guard the snapshot would report a CHECKED "no open PR" for a
    session that is not on a branch at all.
    """
    monkeypatch.setattr(
        session_state, "_gh", lambda _a, _r: pytest.fail("must not ask gh about a detached HEAD")
    )
    git("checkout", "-q", "--detach")

    snap = session_state.gather(tmp_path)

    assert snap.detached is True
    assert snap.pr.state is session_state.PrState.UNVERIFIABLE
    assert "detached" in session_state.render(snap)


# --------------------------------------------------------------------------
# branch + commits
# --------------------------------------------------------------------------


def test_the_branch_and_recent_commits_are_gathered(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_pr(monkeypatch)
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "--", "a.txt")
    git("commit", "-q", "-m", "the newest subject")

    snap = session_state.gather(tmp_path)

    assert snap.branch == "work"
    assert snap.commits[0].subject == "the newest subject"
    assert snap.commits[0].sha
    # Newest first, and bounded by `limit`.
    assert len(snap.commits) <= session_state.DEFAULT_COMMITS


def test_commit_limit_is_honoured(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_pr(monkeypatch)
    for i in range(4):
        (tmp_path / f"c{i}.txt").write_text("x\n", encoding="utf-8")
        git("add", "--", f"c{i}.txt")
        git("commit", "-q", "-m", f"commit {i}")

    assert len(session_state.gather(tmp_path, limit=2).commits) == 2


def test_a_non_repo_reports_an_unread_state_rather_than_a_clean_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside a repo, git answers nothing — which is not "nothing changed".

    This is the same collapse the PR state is guarded against, one field over:
    an empty split rendered as a clean tree would be a claim nobody checked.
    """
    _no_pr(monkeypatch)
    snap = session_state.gather(tmp_path / "not-a-repo")

    assert snap.changes.read is False
    assert snap.changes.clean is False
    assert snap.branch is None


# --------------------------------------------------------------------------
# the design decision on #144 — three PR states, not two
# --------------------------------------------------------------------------


def test_no_open_pr_is_an_ordinary_result(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 4: the caller handles it like any other value, not as a special case."""
    _no_pr(monkeypatch)
    snap = session_state.gather(tmp_path)

    assert snap.pr.state is session_state.PrState.NONE
    assert snap.pr.number is None


def test_an_open_pr_is_reported_with_its_number_and_checks(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        session_state,
        "_gh",
        lambda _args, _root: (0, '[{"number": 144, "title": "the snapshot"}]'),
    )
    monkeypatch.setattr(
        session_state, "_checks_state", lambda _n: (True, "2 binding check(s) green")
    )

    pr = session_state.gather(tmp_path).pr

    assert pr.state is session_state.PrState.OPEN
    assert pr.number == 144
    assert pr.title == "the snapshot"
    assert "green" in pr.checks


def test_a_failed_gh_lookup_is_its_own_state_not_no_open_pr(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE load-bearing case (#144's design comment).

    `gh` unreachable, rate-limited or unauthenticated must not render as "no
    open PR" — that would put a claim in a handoff that nothing checked.
    """
    _gh_down(monkeypatch)
    pr = session_state.gather(tmp_path).pr

    assert pr.state is session_state.PrState.UNVERIFIABLE
    assert pr.state is not session_state.PrState.NONE
    assert pr.detail  # never silent about why


def test_unparsable_gh_output_is_unverifiable_not_no_open_pr(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rc=0 is not enough — a body we cannot read means we never got an answer.

    `gh` can exit 0 having printed a warning banner, and `json.loads` failing on
    that is "could not ask", not "asked and there is none".
    """
    monkeypatch.setattr(session_state, "_gh", lambda _args, _root: (0, "Welcome to gh!\nnot json"))

    assert session_state.gather(tmp_path).pr.state is session_state.PrState.UNVERIFIABLE


def test_a_well_formed_payload_of_the_wrong_shape_is_unverifiable(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid JSON that is not a list of PR objects is not an empty result.

    `json.loads` succeeding says the bytes are JSON, not that they answer the
    question — the same strictness `pr.checks_state` applies next door.
    """
    monkeypatch.setattr(session_state, "_gh", lambda _args, _root: (0, '{"message": "Not Found"}'))

    assert session_state.gather(tmp_path).pr.state is session_state.PrState.UNVERIFIABLE


def test_a_boolean_pr_number_is_refused_rather_than_rendered_as_pr_1(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`bool` is a subclass of `int`, so a bare isinstance check accepts `true`.

    `True == 1`, so the unguarded form renders a corrupt row as a confident
    "PR #1" — a specific, checkable, wrong claim, which is worse in a handoff
    than admitting the lookup failed. Same trap `gates._is_exit_code` documents.
    """
    monkeypatch.setattr(
        session_state, "_gh", lambda _a, _r: (0, '[{"number": true, "title": "t"}]')
    )

    assert session_state.gather(tmp_path).pr.state is session_state.PrState.UNVERIFIABLE


def test_the_pr_probe_asks_only_for_open_prs_on_this_branch(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pinned, because `gh pr view <branch>` resolves a PR REGARDLESS of state.

    `pr.py` records that exact defect: it returned a MERGED PR with rc=0 and let
    `ship` report success having opened nothing. A snapshot built on the same
    call would print a merged PR as the session's open one.
    """
    seen: list[list[str]] = []

    def record(args: list[str], _root: Path) -> tuple[int, str]:
        seen.append(args)
        return 0, "[]"

    monkeypatch.setattr(session_state, "_gh", record)
    session_state.gather(tmp_path)

    assert seen, "the PR probe never ran"
    argv = seen[0]
    assert argv[:2] == ["pr", "list"]
    assert "--state" in argv
    assert argv[argv.index("--state") + 1] == "open"
    assert "--head" in argv
    assert argv[argv.index("--head") + 1] == "work"
    assert "view" not in argv


def test_the_pr_probe_is_skipped_when_the_branch_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no branch there is nothing to ask ABOUT, and asking anyway lies.

    `gh pr list --head ""` would list the repo's open PRs on any branch, so a
    snapshot that could not read git would confidently name someone else's PR.
    """
    called: list[object] = []

    def record(args: list[str], _root: Path) -> tuple[int, str]:
        called.append(args)
        return 0, "[]"

    monkeypatch.setattr(session_state, "_gh", record)
    pr = session_state.gather(tmp_path / "not-a-repo").pr

    assert called == []
    assert pr.state is session_state.PrState.UNVERIFIABLE


def test_gathering_can_skip_the_pr_lookup_entirely(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#149's branch check needs the git data and should not pay for a network call."""
    monkeypatch.setattr(
        session_state,
        "_gh",
        lambda _a, _r: pytest.fail("gh must not be called when pr=False"),
    )
    snap = session_state.gather(tmp_path, pr=False)

    assert snap.branch == "work"
    assert snap.pr.state is session_state.PrState.UNVERIFIABLE
    assert "not requested" in snap.pr.detail


# --------------------------------------------------------------------------
# criterion 2 + 3 — separate functions, structured data
# --------------------------------------------------------------------------


def test_gather_returns_structured_data_not_a_string(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 3, pinned: a caller reads fields, it does not parse prose."""
    _no_pr(monkeypatch)
    snap = session_state.gather(tmp_path)

    assert isinstance(snap, session_state.Snapshot)
    assert not isinstance(snap, str)


def test_render_is_a_pure_function_of_a_snapshot(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 2: rendering re-reads nothing, so it can run without git or gh.

    Armed by rendering a snapshot from a DIFFERENT repo root — if `render`
    reached for live state it would disagree with the data it was handed.
    """
    _no_pr(monkeypatch)
    snap = session_state.gather(tmp_path)
    monkeypatch.setattr(session_state, "_gh", lambda _a, _r: pytest.fail("render must not call gh"))

    assert "work" in session_state.render(snap)


def test_render_prints_the_three_pr_states_differently(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The design comment's second half: the renderer must distinguish them.

    Structured data that says three things and a renderer that prints two of
    them the same way puts the collapse back in the artifact a human reads.
    """
    _no_pr(monkeypatch)
    none_text = session_state.render(session_state.gather(tmp_path))

    _gh_down(monkeypatch)
    unver_text = session_state.render(session_state.gather(tmp_path))

    monkeypatch.setattr(session_state, "_gh", lambda _a, _r: (0, '[{"number": 7, "title": "t"}]'))
    monkeypatch.setattr(session_state, "_checks_state", lambda _n: (True, "green"))
    open_text = session_state.render(session_state.gather(tmp_path))

    prs = {
        line
        for text in (none_text, unver_text, open_text)
        for line in text.splitlines()
        if "PR" in line
    }
    assert len(prs) == 3, f"two PR states rendered identically: {prs}"
    assert "none" in none_text
    assert "#7" in open_text
    # The unverifiable arm must not be readable as the absent one.
    assert "none" not in unver_text.split("PR")[1].split("\n")[0]


def test_render_marks_an_unread_tree_rather_than_showing_it_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_pr(monkeypatch)
    text = session_state.render(session_state.gather(tmp_path / "not-a-repo"))

    assert "clean" not in text.lower()


def test_render_says_clean_for_a_clean_tree(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_pr(monkeypatch)

    assert "clean" in session_state.render(session_state.gather(tmp_path)).lower()


# --------------------------------------------------------------------------
# criterion 1 + 5 — the module entry point
# --------------------------------------------------------------------------


def test_main_prints_the_snapshot_and_exits_zero(
    git: Callable[..., str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Criterion 1 + 5, driven at the entry point against the fixture repo."""
    _no_pr(monkeypatch)

    assert session_state.main([], tmp_path) == 0
    assert "work" in capsys.readouterr().out


def test_main_exits_zero_on_a_dirty_tree_too(
    git: Callable[..., str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The second arm at the entry point. A snapshot REPORTS; it never gates.

    An rc that tracked cleanliness would make this task unusable in the place it
    exists for — you take a snapshot precisely when there is something to say.
    """
    _no_pr(monkeypatch)
    (tmp_path / "dirty.txt").write_text("d\n", encoding="utf-8")

    assert session_state.main([], tmp_path) == 0
    assert "dirty.txt" in capsys.readouterr().out


def test_main_still_exits_zero_when_gh_is_unreachable(
    git: Callable[..., str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A snapshot with an unknown PR state is still a useful snapshot."""
    _gh_down(monkeypatch)

    assert session_state.main([], tmp_path) == 0
    assert "could not" in capsys.readouterr().out.lower()


def test_main_refuses_an_unknown_flag(
    git: Callable[..., str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2 for a request that could not be honoured — the split `kb-gates` draws.

    Silently ignoring `--no-pr` (say) would make the command take the opposite
    position from the one the command line states, and still exit 0.
    """
    _no_pr(monkeypatch)

    assert session_state.main(["--nonsense"], tmp_path) == 2


def test_main_accepts_the_no_pr_flag(
    git: Callable[..., str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_state, "_gh", lambda _a, _r: pytest.fail("--no-pr must not call gh")
    )

    assert session_state.main(["--no-pr"], tmp_path) == 0
