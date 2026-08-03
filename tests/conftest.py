"""Shared fixtures — currently the real-git harness the review tests need.

`kb_setup.review`'s exempt-delta fallback is git behaviour end to end: ancestry,
`git diff --no-renames -z`, and what `git rev-list` yields in what order. A
stubbed subprocess can only confirm the stub, so those tests build an actual
repository.

It lives here because the harness landed TWICE in one commit — once in
`test_review.py` and once in `test_pr.py` — and had already diverged: one wrote
its lane reports under `cold:codex` and the other under `cold`, which only
looked equivalent because `report_path` strips the `:variant`. Duplicated setup
that has drifted before it is a day old is the Duplicated Code smell arriving on
schedule. (Standards lane, round 2.)
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from kb_setup import review

_GIT_TIMEOUT = 30

#: What a full receipt claims. `cold:codex` on purpose — the `:variant` is the
#: realistic form, and `report_path` strips it, so using it here keeps that
#: stripping exercised rather than assumed.
LANES_RAN = ("standards", "spec", "cold:codex", "silent-failure")


def apply_merge(argv: list[str]) -> None:
    """Model on disk what `graphify merge-graphs <in...> --out X` does.

    Not a convenience — a correctness requirement of every `build()` test that
    stubs `_run`. `build()` used to seed `graph.json` with an un-stubbed
    `shutil.copy`, so the file existed no matter what the stub did and the tests
    could assert on its CONTENT. Composing every corpus source in one merge (#120)
    removed that copy, so a stub that only records argv leaves `graph.json`
    missing and `build()` dies at the base snapshot — six tests failed that way,
    none of them about anything this stub understands.

    Concatenating the inputs is enough because the fixtures give each source
    distinguishable bytes; what the assertions need is "did THIS source
    contribute", not a real graph. Missing inputs are skipped so the self merge
    still models correctly when `graphify extract` was stubbed out and wrote no
    sub-graph.
    """
    a = [str(x) for x in argv]
    if "merge-graphs" not in a or "--out" not in a:
        return
    out = Path(a[a.index("--out") + 1])
    inputs = [Path(p) for p in a[a.index("merge-graphs") + 1 : a.index("--out")]]
    # Read every input BEFORE writing: `out` is itself an input on the self merge,
    # so writing first would truncate what we are about to read.
    body = "".join(p.read_text(encoding="utf-8") for p in inputs if p.is_file())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")


def merge_recorder(calls: list[list[str]]) -> Callable[..., None]:
    """A `graph._run` stub that records argv AND applies :func:`apply_merge`."""

    def run(argv: list[str], _root: Path) -> None:
        calls.append([str(a) for a in argv])
        apply_merge(argv)

    return run


@pytest.fixture
def git(tmp_path: Path) -> Callable[..., str]:
    """Return a `git(*args) -> stdout` bound to a fresh repo on a `work` branch.

    The repo has one empty commit on `main`, a `refs/remotes/origin/main`
    pointing at it, a `.gitignore` covering `.agent/`, and `work` checked out.

    The `.gitignore` is not incidental: receipts live under `.agent/`, and
    without it `pr._ship_preflight` refuses for a dirty tree before any receipt
    check runs — so a test would pass for the wrong reason.

    Neither is `origin/main`. The coverage gate resolves the branch's base
    against :data:`review.DEFAULT_BASE_REF` (#54), and a repo with no such ref
    fails CLOSED — correctly, but it would make every test here refuse on
    "could not resolve" instead of exercising the fallback it is aimed at. A
    real clone has this ref; a `git init` does not, and that gap between the
    fixture and the world is what the tests were quietly relying on. Created
    with `update-ref`, so there is no remote and no network.
    """

    def run(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT,
        )
        return proc.stdout.strip()

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, timeout=_GIT_TIMEOUT
    )
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "T")
    # A machine with `commit.gpgsign = true` globally would make every commit
    # below block on a pinentry prompt or fail for want of a key — a fixture that
    # passes here and hangs on someone else's laptop. Unset on this machine, so
    # this is the arm that could not have been discovered by running the suite.
    # (Cold lane, round 3.)
    run("config", "commit.gpgsign", "false")
    run("config", "tag.gpgsign", "false")
    (tmp_path / ".gitignore").write_text(".agent/\n", encoding="utf-8")
    run("add", "--", ".gitignore")
    run("commit", "-q", "-m", "base")
    run("update-ref", "refs/remotes/origin/main", run("rev-parse", "main"))
    run("checkout", "-q", "-b", "work")
    return run


@pytest.fixture
def commit_file(git: Callable[..., str], tmp_path: Path) -> Callable[..., str]:
    r"""Return `commit_file(rel, body="x\\n") -> sha`, committing one file."""

    def commit(rel: str, body: str = "x\n") -> str:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        git("add", "--", rel)
        git("commit", "-q", "-m", f"add {rel}")
        return git("rev-parse", "HEAD")

    return commit


@pytest.fixture
def commit_files(git: Callable[..., str], tmp_path: Path) -> Callable[..., str]:
    """Return `commit_files({rel: body, ...}) -> sha`, committing them TOGETHER.

    One commit carrying several paths is its own case, not a convenience: the
    fallback's refusal arm is a commit that touches an exempt path AND a reviewed
    one, and building that with two calls leaves the first file uncommitted and
    the tree dirty — which `_ship_preflight` refuses for a different reason
    entirely, so the test passes while proving nothing.
    """

    def commit(files: dict[str, str]) -> str:
        for rel, body in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        git("add", "--", *files)
        git("commit", "-q", "-m", f"add {', '.join(files)}")
        return git("rev-parse", "HEAD")

    return commit


@pytest.fixture
def receipt_for(tmp_path: Path) -> Callable[[str], None]:
    """Return `receipt_for(sha)`, writing a valid receipt and its lane reports.

    The base is resolved against the commit itself, not live HEAD, so the receipt
    records the range that was actually reviewed — the same distinction
    `base_sha`'s ``head`` parameter exists for.

    It names :data:`review.DEFAULT_BASE_REF` rather than the literal `"main"`,
    because that is what `ship`/`land` gate against (#54); hardcoding `"main"`
    here would make the fixture record one base while the code demanded another,
    and every test would refuse for a reason none of them is about.
    """

    def write(sha: str) -> None:
        for lane in LANES_RAN:
            report = review.report_path(tmp_path, sha, lane)
            report.parent.mkdir(parents=True, exist_ok=True)
            # Names the SHA: a report must DECLARE what it read, not merely sit
            # under a filename someone else chose (#56).
            report.write_text(f"NO FINDINGS — reviewed {sha}", encoding="utf-8")
        review.write_receipt(
            tmp_path,
            review.Receipt(
                sha=sha,
                fixed_point=review.DEFAULT_BASE_REF,
                fixed_point_sha=review.base_sha(tmp_path, review.DEFAULT_BASE_REF, head=sha),
                lanes_ran=LANES_RAN,
                lanes_skipped=(),
                findings=0,
                blocking=0,
            ),
        )

    return write
