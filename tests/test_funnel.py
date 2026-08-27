# Copyright (c) 2026 Raymond Manaloto
"""Tests for kb_setup.funnel — the research-funnel gate.

Every scenario is built as REAL git state in a `tmp_path` repo (the shared
`git`/`commit_file`/`commit_files` fixtures from `conftest.py`), never asserted
against this working tree — `.claude/rules/probes-need-a-control-arm.md`
requires an arm that would fail if the change under test were reverted, and a
fixture built from real commits is what makes `drift` (say) actually
distinguishable from `clean` rather than both reading the same stub output.

Every case here is one row of the state table in the spec this module
implements: `clean`, `funnelled`, `exempt`, `drift`, `no_base`, plus the two
narrower cases the table's prose calls out by name — a delete-only docs change
(must stay `clean`, never `drift`) and an empty-reason trailer (must be
`drift`, never `exempt`).

The `git` fixture leaves a repo with one base commit on `main`
(`refs/remotes/origin/main` included) and `work` checked out — every test below
that does not explicitly `checkout` builds its scenario ON `work`, comparing
back against the untouched `main`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from kb_setup import funnel, gates
from kb_setup.result import Rc


def test_no_docs_delta_is_clean(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """A branch that never touches the watched directories has nothing to funnel."""
    commit_file("python/src/kb_setup/unrelated.py", "x = 1\n")

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "clean"
    assert v.docs_paths == ()
    assert v.sources_paths == ()
    assert funnel.main(tmp_path) == int(Rc.OK)


def test_docs_and_sources_delta_is_funnelled(
    git: Callable[..., str], commit_files: Callable[..., str], tmp_path: Path
) -> None:
    """A docs delta WITH a sources delta on the same branch — the happy path."""
    commit_files(
        {
            "docs/research/finding.md": "# a finding\n",
            "sources/newthing.manifest": "url = ...\n",
        }
    )

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "funnelled"
    assert v.docs_paths == ("docs/research/finding.md",)
    assert v.sources_paths == ("sources/newthing.manifest",)
    assert funnel.main(tmp_path) == int(Rc.OK)


def test_a_registry_only_edit_counts_as_funnelled(
    git: Callable[..., str], commit_files: Callable[..., str], tmp_path: Path
) -> None:
    """`sources/REGISTRY.md` is the mandate's own minimum bar — it must count.

    Without this, a session that registered a repo in the durable backlog
    (rather than writing a full manifest) would still be reported as `drift`,
    which would make the gate unsatisfiable for research that touched no repo
    worth ingesting yet.
    """
    commit_files(
        {
            "docs/research/finding.md": "# a finding\n",
            "sources/REGISTRY.md": "- owner/repo — a candidate source\n",
        }
    )

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "funnelled"


def test_docs_delta_with_no_sources_and_no_exemption_is_drift(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """The failure this gate exists to catch — measured 33-for-33 on a real branch."""
    commit_file("docs/artifacts/report.html", "<html></html>\n")

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "drift"
    assert v.docs_paths == ("docs/artifacts/report.html",)
    assert v.sources_paths == ()
    assert v.exempt_reason is None
    assert "sources" in v.note
    assert funnel.main(tmp_path) == int(Rc.FINDINGS)


def test_a_non_empty_exemption_trailer_excuses_the_drift(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """A `Funnel-exempt:` trailer with a real reason is the ONLY escape hatch."""
    commit_file("docs/research/finding.md", "# a finding\n")
    git(
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "chore: this research has nothing to funnel\n\n"
        "Funnel-exempt: already covered by issue #999, no new source found",
    )

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "exempt"
    assert v.exempt_reason == "already covered by issue #999, no new source found"
    assert v.sources_paths == ()
    assert funnel.main(tmp_path) == int(Rc.OK)


def test_an_empty_reason_trailer_is_not_an_exemption_and_stays_drift(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """`Funnel-exempt:` with nothing after the colon must NOT excuse the gate.

    Without this, a trailer added out of habit and left blank would silently
    pass — the exact "an env var or a bare flag would be invisible" failure the
    spec names, just with the value stripped instead of the key.
    """
    commit_file("docs/research/finding.md", "# a finding\n")
    git(
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "chore: forgot to fill in the reason\n\nFunnel-exempt:",
    )

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "drift"
    assert v.exempt_reason is None
    assert funnel.main(tmp_path) == int(Rc.FINDINGS)


def test_a_delete_only_docs_change_is_clean_not_drift(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """A branch that only DELETES a research doc produced no research.

    Built by putting the doc on `main` first (so the branch's delta is a pure
    deletion), then branching and removing it — the only way to exercise the
    `D` status letter rather than merely never having created the file.
    """
    git("checkout", "-q", "main")
    commit_file("docs/research/stale.md", "# outdated\n")
    git("checkout", "-q", "-b", "prune-branch")
    git("rm", "-q", "--", "docs/research/stale.md")
    git("commit", "-q", "-m", "remove stale finding")

    v = funnel.verdict(tmp_path, base="main")
    assert v.state == "clean"
    assert v.docs_paths == ()
    assert funnel.main(tmp_path) == int(Rc.OK)


def test_an_unresolvable_base_is_no_base_and_never_clean(
    git: Callable[..., str], commit_file: Callable[..., str], tmp_path: Path
) -> None:
    """A base ref that cannot be resolved must fail closed, not read as `clean`.

    Even with a real docs-only delta sitting right there — if this collapsed to
    `clean`, a broken `base` argument would silently defeat the whole gate.
    """
    commit_file("docs/research/finding.md", "# a finding\n")

    v = funnel.verdict(tmp_path, base="does-not-exist-anywhere")
    assert v.state == "no_base"
    assert v.state != "clean"
    assert v.docs_paths == ()
    assert v.sources_paths == ()
    assert "could not" in v.note.lower()


def test_main_reports_not_run_on_an_unresolvable_default_base(tmp_path: Path) -> None:
    """The CLI boundary's `no_base` arm: not a git repo at all.

    `review.base_sha` refuses closed on a directory with no `.git`, which is
    the cheapest realistic way to exercise this without the `git` fixture.
    `Rc.NOT_RUN`, never `Rc.OK` — the question was never asked.
    """
    assert funnel.main(tmp_path) == int(Rc.NOT_RUN)


def test_main_refuses_unexpected_arguments(tmp_path: Path) -> None:
    """`funnel` takes no flags today — an unknown one is refused, not ignored."""
    assert funnel.main(tmp_path, ["--nonsense"]) == int(Rc.BAD_REQUEST)


def test_render_never_prints_ok_for_a_could_not_check_state() -> None:
    """`no_base` must read as a refusal in the printed line too, not just the rc."""
    v = funnel.FunnelVerdict(
        state="no_base",
        docs_paths=(),
        sources_paths=(),
        exempt_reason=None,
        note="could not resolve 'main' — the gate could not ask its question.",
    )
    rendered = funnel.render(v)
    assert "OK" not in rendered
    assert "could not ask its question" in rendered


# --------------------------------------------------------------------------
# the trailer parser directly — the first one in this codebase
# --------------------------------------------------------------------------


def test_trailer_reason_ignores_ordinary_prose() -> None:
    """An ordinary commit message with no trailer block must never false-positive."""
    body = (
        "docs(mandate): why the project drifts, measured\n\n"
        "Some longer explanation text that happens to contain a colon: like this.\n"
    )
    assert funnel._trailer_reason(body) == ""


def test_trailer_reason_finds_a_non_empty_value() -> None:
    body = "chore: x\n\nFunnel-exempt: covered already\n"
    assert funnel._trailer_reason(body) == "covered already"


def test_trailer_reason_treats_a_blank_value_as_no_reason() -> None:
    body = "chore: x\n\nFunnel-exempt:\n"
    assert funnel._trailer_reason(body) == ""


# --------------------------------------------------------------------------
# the shipped constants, against the REAL repo
# --------------------------------------------------------------------------


def test_the_gate_is_on_the_ship_path_and_runs_exclusive() -> None:
    """Membership IS the change, and CONCURRENT_SAFE membership is pinned too.

    `funnel` must be a declared gate AND must NOT be concurrency-safe — its
    `git` calls against the same working tree `lint`/`test` may be touching
    have not been characterised, so it defaults to exclusive per
    `gates.CONCURRENT_SAFE`'s own fail-closed contract. Mirrors
    `test_graph_size.py`'s `test_the_gate_is_on_the_ship_path...` exactly.
    """
    assert "funnel" in gates.GATE_TASKS
    assert "funnel" not in gates.CONCURRENT_SAFE
